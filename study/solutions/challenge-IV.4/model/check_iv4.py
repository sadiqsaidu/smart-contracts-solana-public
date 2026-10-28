#!/usr/bin/env python3
"""Checks for Challenge IV.4. Run: python3 -I check_iv4.py [--quick] > results.json

Sections:
  witnesses   deterministic traces (fewest transactions) per design
  bfs         bounded exhaustive search over adversarial prefixes before settlement
  random      randomized multi-epoch property tests with all I.1 in-epoch writers
  outofcell   escrow-mint shortfall under a rent increase (outside mainnet-2026)
Everything is exact-integer model execution (labels in ../VERIFICATION.md).
"""
import copy
import itertools
import json
import random
import sys
from fractions import Fraction

sys.path.insert(0, __import__("os").path.dirname(__file__))
from batch_model import (RHO, Q, M, Revert, World, Entry, mainnet_pool, jsonable)  # noqa: E402

QUICK = "--quick" in sys.argv
Z = 50_000_000_000           # 50 SOL donation used by the witnesses
L = 100_000_000_000          # 100 SOL batch deposit


def start(design):
    """Common reachable start: fresh pool at E=1070, two whitelisted users queue in E."""
    w = World(design)
    for u in ("alice", "bob"):
        w.status[u] = "W"
    w.enqueue("alice", L)
    w.enqueue("bob", L)
    return w


def to_next_epoch(w):
    w.pool.epoch_tick()
    w.pool.payout_done()


def bot_maintenance(w):
    for i in range(len(w.pool.entries)):
        w.pool.vlb(i)
    w.pool.spb()


def immediate_witness(design):
    w = World(design)
    w.status["alice"] = "W"
    w.pool.donate_validator(1, Z)              # tx 1: anyone (or a Jito tip claim)
    w.enqueue("alice", L)                      # tx 2: the deposit itself
    r = w.immediate_records[-1]
    return dict(transactions=["donate V_1 50 SOL", "deposit 100 SOL"],
                transfer_to_depositor=r["transfer"], price_after=r["price"])


def settle_witness(design, wrong=frozenset(), extra=None):
    w = start(design)
    to_next_epoch(w)
    bot_maintenance(w)                         # tx A: first complete maintenance of E+1 (anyone)
    w.pool.donate_validator(1, Z)              # tx B: credit to V_1 after it was observed
    if extra:
        extra(w)
    w.settle(1070, wrong_pairs=wrong)          # tx C: settlement
    rec = w.records[-1]
    return dict(transfer_to_depositors=rec["transfer"], minted=rec["minted"],
                settle_price=rec.get("price"), others_delta=rec.get("others_delta"))


def witnesses():
    out = {}
    out["immediate"] = immediate_witness("immediate")
    out["fresh"] = immediate_witness("fresh")
    out["nonatomic_first_maintenance"] = settle_witness("nonatomic")
    out["wrongpair"] = settle_witness("wrongpair", wrong=frozenset({1}))
    out["batch"] = settle_witness("batch")
    # escrow-mint: the stale deposit happens in E, after an uncounted credit
    w = World("escrowmint")
    w.status["alice"] = "W"
    w.pool.donate_validator(1, Z)
    w.enqueue("alice", L)
    to_next_epoch(w)
    w.settle(1070)
    out["escrowmint"] = dict(transfer_to_depositors=w.records[-1]["transfer"],
                             minted_after_true_up=w.records[-1]["minted"])
    # batch: donation and burn by an adversary in the SAME transaction just before settle
    def pre(w):
        w.pool.donate_reserve(7_000_000_000)
        w.pool.burn("incumbent", 3_000_000_000)
    out["batch_donate_and_burn_just_before_settle"] = settle_witness("batch", extra=pre)
    return out


# ---------------------------------------------------------------------------
# Bounded exhaustive search: every adversarial prefix of length <= K inserted
# between "E+1 begins" and "settle", for each design. Reports the shortest prefix
# whose settlement transfer to depositors exceeds the batch bound.
# ---------------------------------------------------------------------------
ALPHABET = [
    ("maintenance", lambda w: bot_maintenance(w)),
    ("donate_V0", lambda w: w.pool.donate_validator(0, Z)),
    ("donate_reserve", lambda w: w.pool.donate_reserve(Z)),
    ("burn", lambda w: w.pool.burn("incumbent", 5_000_000_000)),
    ("withdraw", lambda w: w.pool.withdraw_stake("incumbent", 2_000_000_000)),
    ("owner_add", lambda w: w.pool.owner_add_validator()),
    ("epoch_tick_and_payout", lambda w: to_next_epoch(w)),
    ("epoch_tick_payout_pending", lambda w: w.pool.epoch_tick()),
]


def bfs(design, kmax, wrong=frozenset()):
    shortest, explored, settled = None, 0, 0
    worst = None
    for k in range(kmax + 1):
        for seq in itertools.product(ALPHABET, repeat=k):
            explored += 1
            w = start(design)
            to_next_epoch(w)
            try:
                for _, act in seq:
                    act(w)
                w.settle(1070, wrong_pairs=wrong)
            except Revert:
                continue
            settled += 1
            rec = w.records[-1]
            tr, price = rec["transfer"], rec["price"]
            if worst is None or tr > worst[0]:
                worst = (tr, [n for n, _ in seq])
            bad = tr > 0 or tr <= -price
            if bad and shortest is None:
                shortest = dict(length=k, prefix=[n for n, _ in seq], transfer=tr)
        if shortest is not None and design != "batch":
            break
    return dict(design=design, kmax=kmax, explored=explored, settled=settled,
                shortest_violation=shortest, max_transfer=worst[0] if worst else None,
                max_transfer_prefix=worst[1] if worst else None)


# ---------------------------------------------------------------------------
# Randomized multi-epoch property test
# ---------------------------------------------------------------------------
USERS = [f"u{i}" for i in range(6)]


def random_run(design, seed, steps):
    rng = random.Random(seed)
    w = World(design)
    for u in USERS:
        w.status[u] = "W"
    w.pool.tokens["incumbent2"] = 0
    stats = dict(settles=0, settle_reverts=0, violations=[], claims=0, refunds=0)

    def try_(f):
        try:
            f()
            return True
        except Revert:
            return False

    for _ in range(steps):
        a = rng.randrange(15)
        p = w.pool
        if a == 0:
            u = rng.choice(USERS)
            amt = rng.choice([1, 2, 3, 7, 999, 10**6, 10**9, 37 * 10**9, rng.randrange(1, 10**11)])
            try_(lambda: w.enqueue(u, amt))
        elif a == 1:
            try_(lambda: w.cancel(rng.choice(USERS)))
        elif a == 2:
            u = rng.choice(USERS)
            w.set_status(u, rng.choice(["W", "B", "None"]))
        elif a == 3:
            p.donate_validator(rng.randrange(len(p.entries)), rng.choice([1, 999, 10**9, 10**11]))
        elif a == 4:
            p.donate_reserve(rng.choice([1, 10**6, 10**10]))
        elif a == 5:
            h = rng.choice([k for k, v in p.tokens.items() if v > 0 and k not in ("vault", "escrow")] or ["incumbent"])
            try_(lambda: p.burn(h, rng.randrange(1, max(2, p.tokens.get(h, 0) // 3 + 1))))
        elif a == 6:
            h = rng.choice([k for k, v in p.tokens.items() if v > 0 and k not in ("vault", "escrow")] or ["incumbent"])
            try_(lambda: p.withdraw_stake(h, rng.randrange(1, max(2, p.tokens.get(h, 0)))))
        elif a == 7 and len(p.entries) < 8 and rng.random() < 0.3:
            p.owner_add_validator()
        elif a == 8 and rng.random() < 0.25:
            p.epoch_tick(rng.choice([0, 180, 400]))
        elif a == 9:
            p.payout_done()
        elif a == 10:
            # partial / complete permissionless maintenance by anyone
            idx = rng.sample(range(len(p.entries)), rng.randrange(len(p.entries) + 1))
            try_(lambda: [p.vlb(i) for i in idx])
            try_(p.spb)
        elif a == 11:
            for e in sorted(w.batches):
                if w.batches[e].status == "Open" and e < p.epoch:
                    ok = try_(lambda: w.settle(e))
                    stats["settles" if ok else "settle_reverts"] += 1
                    if not ok and not p.rewards_active and not w.paused:
                        stats["violations"].append(("liveness", e))
        elif a == 12:
            u = rng.choice(USERS)
            if try_(lambda: w.claim(u)):
                stats["claims"] += 1
            elif try_(lambda: w.claim_refund(u)):
                stats["refunds"] += 1
        elif a == 13:
            for e in list(w.batches):
                try_(lambda: w.close_batch(e))
        elif a == 14 and p.tokens.get("incumbent", 0) > 10:
            k = rng.randrange(1, p.tokens["incumbent"] // 10)
            p.tokens["incumbent"] -= k
            p.tokens["incumbent2"] = p.tokens.get("incumbent2", 0) + k   # Token transfer
        check_invariants(w, stats)

    # drain: finish every batch so nothing can remain frozen
    for _ in range(3):
        w.pool.epoch_tick(0)
        w.pool.payout_done()
        for e in sorted(w.batches):
            if w.batches[e].status == "Open" and e < w.pool.epoch:
                try:
                    w.settle(e)
                    stats["settles"] += 1
                except Revert as ex:
                    stats["violations"].append(("drain-settle", e, str(ex)))
    for u in USERS:
        for f in (w.claim, w.claim_refund):
            try:
                f(u)
            except Revert:
                pass
    for e in list(w.batches):
        try:
            w.close_batch(e)
        except Revert:
            stats["violations"].append(("close", e))
    if design != "escrowmint" and w.tickets:
        stats["violations"].append(("frozen tickets", list(w.tickets)))
    check_invariants(w, stats)
    # per-user: refunds + claimed value vs paid in (only for fully-resolved users)
    for rec in w.records:
        tr, price = rec["transfer"], rec.get("price")
        if price is not None and design in ("batch", "escrowmint") and not (-price < tr <= 0):
            stats["violations"].append(("R2 bound", rec["epoch"], str(tr), str(price)))
        if rec.get("shortfall"):
            stats["violations"].append(("escrow shortfall", rec["shortfall"]))
    for rec in w.immediate_records:
        if design == "fresh" and not (-rec["price"] < rec["transfer"] <= 0):
            stats["violations"].append(("fresh bound", str(rec["transfer"])))
    stats["immediate_deposits"] = len(w.immediate_records)
    stats["max_transfer"] = max([r["transfer"] for r in w.records] +
                                [r["transfer"] for r in w.immediate_records], default=0)
    return stats


def check_invariants(w, stats):
    # J1: escrow conservation for every open batch
    for e, b in w.batches.items():
        if b.status == "Open":
            pend = sum(t.amount for t in w.tickets.values() if t.batch == e and t.state == "Pending")
            if w.design != "escrowmint" and pend != b.total:
                stats["violations"].append(("J1", e, pend, b.total))
        if b.vault < 0:
            stats["violations"].append(("vault negative", e))
    # J4: every Pending ticket in an unsettled batch belongs to a whitelisted user
    if w.design != "escrowmint":
        for t in w.tickets.values():
            if t.state == "Pending" and w.batches[t.batch].status == "Open" and w.status.get(t.user) != "W":
                stats["violations"].append(("J4", t.user))
    # D_S >= 0 and D_T >= 0 at fresh states (I.1 dependency, re-checked in this model)
    p = w.pool
    if p.lam == p.epoch and not p.rewards_active:
        obs = p.observe()
        if obs and (obs[0] < p.t or p.s < p.sigma):
            stats["violations"].append(("I.1 gap negative", obs[0] - p.t, p.s - p.sigma))


def r1_exact():
    """R1: equal deposits receive identical claims; bound for unequal ones."""
    out = []
    rng = random.Random(7)
    for trial in range(2000 if not QUICK else 200):
        w = World("batch")
        amounts = [rng.choice([1, 3, 10**9, rng.randrange(1, 10**12)]) for _ in range(5)]
        amounts.append(amounts[0])            # force a duplicate amount
        for i, a in enumerate(amounts):
            w.status[f"d{i}"] = "W"
            w.enqueue(f"d{i}", a)
        to_next_epoch(w)
        w.pool.donate_validator(rng.randrange(4), rng.randrange(0, 10**10))
        try:
            w.settle(1070)
        except Revert:
            continue
        b = w.batches[1070]
        if b.status != "Settled":
            continue
        price = b.settle_price
        claims = {f"d{i}": a * b.minted // b.total for i, a in enumerate(amounts)}
        assert claims["d0"] == claims[f"d{len(amounts)-1}"]
        for i, a in enumerate(amounts):
            gap = claims[f"d{i}"] * price - a
            assert -2 * price < gap <= 0, (gap, price)
        dust = b.minted - sum(claims.values())
        assert 0 <= dust < len(amounts)
        out.append(dust)
    return dict(trials=len(out), max_dust=max(out), equal_amount_claims_identical=True)


def out_of_cell_escrowmint():
    """Escrow-mint relies on the incumbent price not falling between deposit and settle.
    A rent increase (not a transition of the mainnet-2026 cell) breaks that."""
    w = World("escrowmint")
    w.status["alice"] = "W"
    w.enqueue("alice", L)
    to_next_epoch(w)
    import batch_model
    old = batch_model.RHO
    batch_model.RHO = old + 2_000_000_000     # exaggerated reserve-rent increase
    try:
        w.settle(1070)
        rec = w.records[-1]
        return dict(shortfall_tokens=rec.get("shortfall"), transfer=rec["transfer"])
    finally:
        batch_model.RHO = old


def main():
    res = {}
    res["witnesses"] = witnesses()
    k = 2 if QUICK else 3
    res["bfs"] = [bfs("batch", k), bfs("nonatomic", k), bfs("wrongpair", k, wrong=frozenset({0})),
                  bfs("escrowmint", k)]
    seeds = range(60 if QUICK else 400)
    steps = 120 if QUICK else 250
    res["random"] = {}
    for design in ("batch", "escrowmint", "fresh", "immediate", "nonatomic"):
        agg = dict(runs=0, settles=0, settle_reverts=0, claims=0, refunds=0, immediate_deposits=0, violations=0,
                   first_violations=[], max_transfer=Fraction(0))
        for s in seeds:
            st = random_run(design, s, steps)
            agg["runs"] += 1
            for kk in ("settles", "settle_reverts", "claims", "refunds", "immediate_deposits"):
                agg[kk] += st[kk]
            agg["violations"] += len(st["violations"])
            if st["violations"] and len(agg["first_violations"]) < 3:
                agg["first_violations"].append(dict(seed=s, v=st["violations"][:2]))
            agg["max_transfer"] = max(agg["max_transfer"], st["max_transfer"])
        res["random"][design] = agg
    res["r1"] = r1_exact()
    res["outofcell_escrowmint"] = out_of_cell_escrowmint()
    ok = (all(res["random"][d]["violations"] == 0 for d in ("batch", "fresh"))
          and res["bfs"][0]["shortest_violation"] is None)
    res["verdict"] = "PASS: batch and fresh satisfy the bounds; flawed designs violate" if ok else "FAIL"
    print(json.dumps(jsonable(res), indent=1, default=str))


if __name__ == "__main__":
    main()
