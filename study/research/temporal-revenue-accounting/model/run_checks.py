"""Deterministic checks and mainnet-parameter scenarios for the temporal revenue model.

Run:  python3 -I run_checks.py > results.json      (from this directory)
Exits non-zero if any assertion fails. Every number is an exact integer.
"""
import copy, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from temporal_model import Pool, Validator, Rejected, Stage, RENT, MIN_DELEGATION, mainnet_1070, ceil_div

HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.join(HERE, "..", "mainnet")
state = json.load(open(os.path.join(MAIN, "pool_state.json")))
infl = json.load(open(os.path.join(MAIN, "inflation_rewards.json")))
results = {"checks": [], "scenarios": {}}
failures = []


def check(name, cond, **detail):
    results["checks"].append({"name": name, "pass": bool(cond), **detail})
    if not cond:
        failures.append(name)


def toy(T_extra=0):
    """Small reconciled pool: reserve 10 SOL + rent, two validators of 50 SOL."""
    vs = [Validator(50 * 10**9 + RENT, 50 * 10**9, 50 * 10**9 + RENT, 1) for _ in range(2)]
    T = 10 * 10**9 + 2 * (50 * 10**9 + RENT)
    p = Pool(T=T, S=T // 4, mint_supply=T // 4, reserve=10 * 10**9 + RENT, validators=vs, E=1, lam=1)
    p.balances = {"fee": 0, "inc": T // 4}
    return p


# ------------------------------------------------------------------ 1. structural checks
p = toy()
check("zero credit: D_T = D_S = 0 on a reconciled pool", p.gaps() == {"D_T": 0, "D_S": 0}, gaps=p.gaps())

p = toy(); p.donate(0, 777_777)
check("credit to counted validator: D_T = z", p.gaps()["D_T"] == 777_777)
p.vlb([0]); p.spb()
check("credit to counted validator: VLB(i)+SPB recognises it", p.gaps()["D_T"] == 0)

p = toy(); p.donate(-1, 1_234_567)
check("credit to reserve: D_T = z", p.gaps()["D_T"] == 1_234_567)
q = copy.deepcopy(p); q.spb()
check("credit to reserve: SPB alone recognises it", q.gaps()["D_T"] == 0)

p = toy(); p.earn_tip(None, 5_000_000, 1, kind="uncounted"); p.upload_root(1); p.claim(None, 1)
check("credit to an account the pool does not observe: no effect", p.gaps()["D_T"] == 0)

# partial updates: VLB on V0 only, then credit to V0 (already processed) and to V1 (not yet processed)
p = toy(); p.epoch_tick(); p.end_rewards(); p.vlb([0]); p.donate(0, 1000); p.donate(1, 2000); p.vlb([1]); p.spb()
check("partial update: credit to already-processed V0 is missed, credit to unprocessed V1 is recorded",
      p.gaps()["D_T"] == 1000 and p.T == toy().T + 2000, D_T=p.gaps()["D_T"])

# epoch restrictions
p = toy(); p.epoch_tick()
for name, f in [("VLB during reward distribution", lambda: p.vlb()), ("DepositSol on a stale pool", lambda: p.deposit_sol("x", 10**9)),
                ("WithdrawStake on a stale pool", lambda: p.withdraw_stake("inc", 10**9, 0))]:
    try:
        f(); ok = False
    except Rejected:
        ok = True
    check(f"rejected: {name}", ok)
try:
    p.end_rewards(); p.spb(); ok = False
except Rejected:
    ok = True
check("rejected: SPB before every entry is updated this epoch", ok)

# inflation is always recognised before any price-sensitive operation of the next epoch
p = toy(); p.epoch_tick(); p.pay_inflation(0, 3_000_000, 1); p.pay_inflation(1, 3_000_000, 1)
try:
    p.deposit_sol("x", 10**9); dep_ok = True
except Rejected:
    dep_ok = False
p.end_rewards(); p.vlb(); p.spb()
check("inflation for epoch e: deposits impossible until it is RECORDED", (not dep_ok) and p.outstanding()["CREDITED"] == 0
      and all(r.stage == Stage.RECORDED for r in p.revenue))


# ------------------------------------------------------------------ 2. late credit and deposit pricing
def window_run(L, z, recognise_before_deposit, deposit_before_claim=False, base=toy):
    p = base(); p.epoch_tick(); p.end_rewards(); p.vlb(); p.spb()           # complete maintenance
    p.earn_tip(0, z, p.E - 1); p.upload_root(p.E - 1)
    if deposit_before_claim:
        n = p.deposit_sol("dep", L); p.claim(0, p.E - 1)
    else:
        p.claim(0, p.E - 1)
        if recognise_before_deposit:
            p.vlb(); p.spb()
        n = p.deposit_sol("dep", L)
    p.epoch_tick(); p.end_rewards(); p.vlb(); p.spb()
    return p, n

for L in [10**6, 10**9, 10**11, 10**13]:
    z = 50_000_000
    late, n_late = window_run(L, z, False)
    early, n_early = window_run(L, z, True)
    before, n_before = window_run(L, z, False, deposit_before_claim=True)
    check(f"L={L}: deposit in window mints >= honest counterfactual", n_late >= n_early, n_late=n_late, n_early=n_early)
    check(f"L={L}: deposit before or after the claim mints the same (credit position inside the window is irrelevant)", n_late == n_before)
    check(f"L={L}: honest re-reconciliation removes the excess (control)", early.gaps()["D_T"] == 0)

# rounding boundaries (toy pool has S = T/4 exactly)
p = toy(); T, S = p.T, p.S
check("rounding: toy pool price is exactly 4", 4 * S == T)
check("rounding: a 1-lamport credit can leave the mint unchanged (L=5)", 5 * S // T == 5 * S // (T + 1) == 1)
check("rounding: a 1-lamport credit can lower the mint by one unit (L=4 at an exact boundary)", 4 * S // T - 4 * S // (T + 1) == 1)
for L, z in [(10**6, 1), (10**9, 1000), (10**12, 10**6)]:
    d = L * S // T - L * S // (T + z)
    bound = L * S * z // (T * (T + z))
    check(f"rounding: mint difference for L={L}, z={z} is within [floor(LSz/T(T+z)), +1]", bound <= d <= bound + 1, d=d, bound=bound)

# mint-supply change (external burn) before the fee calculation
p = toy(); p.burn("inc", 1000); p.donate(0, 10**8)
f_with_burn = copy.deepcopy(p); f_with_burn.vlb(); fb = f_with_burn.spb()
p2 = toy(); p2.donate(0, 10**8); p2.vlb(); fnb = p2.spb()
check("epoch fee uses recorded S (not the burned mint supply)", fb == fnb, fee_with_burn=fb, fee_without=fnb)

# commutativity lemma: manager fee VALUE is independent of when the credit is recognised (up to rounding)
def fee_value(recognise_mid):
    p = toy(); p.epoch_tick(); p.end_rewards(); p.vlb(); p.spb()
    p.donate(0, 10**8)
    if recognise_mid:
        p.vlb(); p.spb()
    p.deposit_sol("dep", 10**10)
    p.epoch_tick(); p.end_rewards(); p.vlb(); p.spb()
    return p.balances.get("fee", 0) * p.T // p.S, p
v_mid, pm = fee_value(True); v_late, pl = fee_value(False)
check("manager-fee value invariant to recognition time within 2 lamports + P", abs(v_mid - v_late) <= 2 + pm.T // pm.S, v_mid=v_mid, v_late=v_late)
check("final T invariant to recognition time (commutativity of credit and deposit for T)", pm.T == pl.T, T_mid=pm.T, T_late=pl.T)
check("final S differs (the allocation, not the asset total, depends on order)", pm.S != pl.S, S_mid=pm.S, S_late=pl.S)

# withdrawal constraints
p = toy()
for name, args in [("below min delegation", ("inc", 10**8, 0)), ("leaving < rent+min in V", ("inc", toy().balances["inc"] // 2, 0))]:
    try:
        p.withdraw_stake(*args); ok = False
    except Rejected:
        ok = True
    check(f"WithdrawStake rejected: {name}", ok)
p = toy(); ell = p.withdraw_stake("inc", 10**9, 0)
check("WithdrawStake fee = ceil(p/1000) tokens transferred to the fee account", p.balances["fee"] == 10**6)
p = toy(); p.balances["fee"] = 10**9; p.balances["inc"] -= 10**9
ell_fee = p.withdraw_stake("fee", 10**9, 0)
check("manager fee account is withdrawal-fee exempt (processor.rs:2861)", ell_fee == 10**9 * p.T // p.S or ell_fee > ell)

# ------------------------------------------------------------------ 3. mainnet-parameter scenario (epoch 1070 -> 1071)
CLAIMS_1069 = [18_861, 43_128, 0, 44_932]      # history.json, epoch 1070 claims (earned 1069)
INFL_1069 = [r["amount"] for r in infl["epochs"]["1069"][:4]]   # proxy for epoch-1070 inflation (assumption A-INF)
TX_FEES = {"deposit": 127_503, "withdraw_stake": 10_000, "deactivate": 5_000, "withdraw_sol": 5_000}  # observed 1063 values + base fee


def mainnet_trace(L, honest_mid_epoch, deposit=True, withdraw_validator=1):
    p = mainnet_1070(state)
    for i, z in enumerate(CLAIMS_1069):
        if z:
            p.earn_tip(i, z, 1069)
    p.upload_root(1069)
    for i, z in enumerate(CLAIMS_1069):
        if z:
            p.claim(i, 1069)
    D_T_window = p.gaps()["D_T"]
    if honest_mid_epoch:
        p.vlb(); p.spb()
    n = p.deposit_sol("dep", L) if deposit else 0
    p.epoch_tick()
    for i, a in enumerate(INFL_1069):
        p.pay_inflation(i, a, 1070)
    p.end_rewards(); p.vlb(); p.spb()
    out = {"D_T_in_window": D_T_window, "minted": n, "T": p.T, "S": p.S, "fee_tokens": p.balances["fee"]}
    out["others_value_pre_exit"] = p.balances["others"] * p.T // p.S
    out["fee_value_pre_exit"] = p.balances["fee"] * p.T // p.S
    if deposit:
        out["mtm_value"] = p.fair_value(n)
        ell, ntx = p.exit_all("dep")
        out["withdraw_lamports"] = ell
        out["withdraw_txs"] = ntx
        out["unredeemed_tokens"] = p.balances["dep"]
    out["others_value"] = p.balances["others"] * p.T // p.S
    out["fee_value"] = p.balances["fee"] * p.T // p.S
    out["final_T"], out["final_S"] = p.T, p.S
    return out

scen = {}
for L in [1_004_998_720, 10 * 10**9, 100 * 10**9, 1_000 * 10**9]:
    late = mainnet_trace(L, False); hon = mainnet_trace(L, True)
    base_late = mainnet_trace(L, False, deposit=False)
    fees = sum(TX_FEES.values())
    rec = {"L": L, "late": late, "honest": hon,
           "delay_attributable_tokens": late["minted"] - hon["minted"],
           "delay_attributable_mtm_lamports": late["mtm_value"] - hon["mtm_value"],
           "mtm_pnl_late": late["mtm_value"] - L,
           "mtm_pnl_honest": hon["mtm_value"] - L,
           "others_change_vs_no_deposit_pre_exit": late["others_value_pre_exit"] - base_late["others_value_pre_exit"],
           "fee_acct_change_vs_no_deposit_pre_exit": late["fee_value_pre_exit"] - base_late["fee_value_pre_exit"],
           "others_delay_attributable_pre_exit": late["others_value_pre_exit"] - hon["others_value_pre_exit"],
           "fee_acct_delay_attributable_pre_exit": late["fee_value_pre_exit"] - hon["fee_value_pre_exit"],
           "others_change_vs_no_deposit_after_exit": late["others_value"] - base_late["others_value"],
           "fee_acct_change_vs_no_deposit_after_exit": late["fee_value"] - base_late["fee_value"]}
    if "withdraw_lamports" in late:
        per_exit = TX_FEES["withdraw_stake"] + TX_FEES["deactivate"] + TX_FEES["withdraw_sol"]
        fl = TX_FEES["deposit"] + per_exit * late["withdraw_txs"]; fh = TX_FEES["deposit"] + per_exit * hon["withdraw_txs"]
        rec["realized_pnl_late"] = late["withdraw_lamports"] - L - fl     # stake rent prefund is refunded on final withdraw
        rec["realized_pnl_honest"] = hon["withdraw_lamports"] - L - fh
        rec["realized_delay_attributable"] = late["withdraw_lamports"] - hon["withdraw_lamports"]
    scen[str(L)] = rec
    check(f"mainnet L={L}: full redemption succeeded", late["unredeemed_tokens"] == 0 and hon["unredeemed_tokens"] == 0, txs=late["withdraw_txs"])
    check(f"mainnet L={L}: realized round trip is a loss even with the delay", rec.get("realized_pnl_late", -1) < 0, pnl=rec.get("realized_pnl_late"))
results["scenarios"]["mainnet_1070_jit_deposit"] = scen

# breakeven: smallest per-epoch late credit z (as a fraction of T) for which a deposit+WithdrawStake round trip
# (all fees above) breaks even, holding everything else at mainnet values (inflation capture INCLUDED).
def round_trip(L, z_total):
    p = mainnet_1070(state)
    p.donate(1, z_total)   # stands in for a late claim of size z_total (same accounting effect)
    n = p.deposit_sol("dep", L)
    p.epoch_tick()
    for i, a in enumerate(INFL_1069):
        p.pay_inflation(i, a, 1070)
    p.end_rewards(); p.vlb(); p.spb()
    ell, ntx = p.exit_all("dep")
    if p.balances["dep"]:
        return p.fair_value(n) - L      # cannot fully redeem: value at mark-to-market (only far above breakeven)
    return ell - L - TX_FEES["deposit"] - ntx * (TX_FEES["withdraw_stake"] + TX_FEES["deactivate"] + TX_FEES["withdraw_sol"])

L = 10 * 10**9
lo, hi = 0, 2 * 10**10
while lo < hi:
    mid = (lo + hi) // 2
    if round_trip(L, mid) >= 0:
        hi = mid
    else:
        lo = mid + 1
T0 = mainnet_1070(state).T
results["scenarios"]["breakeven"] = {"L": L, "z_breakeven": lo, "z_over_T": lo / T0, "observed_z_1069": sum(CLAIMS_1069),
                                     "ratio_needed_to_observed": lo / sum(CLAIMS_1069),
                                     "note": "z is the total unrecognised credit present at deposit time; inflation capture included"}
check("breakeven late credit is orders of magnitude above the observed Jito credit", lo > 100 * sum(CLAIMS_1069), z_breakeven=lo)

# self-funded credit (actor donates z to V, then deposits): combined P&L must be negative
def self_funded(L, z):
    p = mainnet_1070(state); p.donate(1, z); n = p.deposit_sol("dep", L)
    p.epoch_tick(); p.end_rewards(); p.vlb(); p.spb()
    return p.fair_value(n) - L - z
sf = {str(z): self_funded(100 * 10**9, z) for z in [10**6, 10**9, 50 * 10**9]}
results["scenarios"]["self_funded_mtm"] = sf
check("self-funded credit: donation + deposit is a mark-to-market loss", all(v < 0 for v in sf.values()), sf=sf)

# lag lemma: holder entering in epoch a and leaving in epoch b receives MEV of earning epochs
# [a-1, b-2] instead of [a, b-1]: a one-epoch shift, net of boundary terms only.
def holder_shift(entry, exit_, zs):
    lagged = sum(zs[e - 2] for e in range(entry + 1, exit_ + 1) if 0 <= e - 2 < len(zs))   # recorded at start of e
    fair = sum(zs[e] for e in range(entry, exit_) if 0 <= e < len(zs))
    return lagged - fair
zs = [80_772, 106_921, 99_000, 120_000, 70_000, 150_000]
results["scenarios"]["lag_lemma_examples"] = {f"{a}->{b}": holder_shift(a, b, zs) for a, b in [(1, 3), (1, 5), (2, 5)]}

# H6 comparison: owner-funded validator add window (q = rent + 1 SOL) vs observed Jito late credit
q = RENT + MIN_DELEGATION
results["scenarios"]["h6_comparison"] = {"owner_add_q": q, "jito_late_credit_1069": sum(CLAIMS_1069), "ratio": q / sum(CLAIMS_1069)}

# ------------------------------------------------------------------ 4. history replay 1063 -> 1070 (public data)
hist = json.load(open(os.path.join(MAIN, "history.json")))
claims_by_epoch = {}
for t in hist["txs"]:
    if any("ClaimWithPayer" in l for l in t["logs"]):
        claims_by_epoch[t["epoch"]] = claims_by_epoch.get(t["epoch"], 0) + sum(v for k, v in t["deltas"].items() if k.startswith("V"))
infl_by_epoch = {int(e): sum(r["amount"] for r in rs if r) for e, rs in infl["epochs"].items()}
L63, n63 = 1_004_998_720, 1_705_190_630 - 1_455_513_908
p63, fee63, b63, ell63 = 993_739_463, 993_740, 993_739_463 - 993_740, 3_995_999_997
T1070, S1070 = int(state["pool"]["total_lamports"]), int(state["pool"]["pool_token_supply"])
# T after the 1063 maintenance, by backward exact accounting (no fee dependence)
T63 = T1070 - sum(infl_by_epoch[e] for e in range(1063, 1070)) - sum(claims_by_epoch[e] for e in range(1063, 1070)) - L63 + ell63

def forward(S63):
    T, S = T63, S63
    n = L63 * S // T; T += L63; S += n
    ell = b63 * T // S; T -= ell; S -= b63
    trace = [{"epoch": 1063, "T_after_spb": T63, "S_after_spb": S63, "deposit_minted": n, "withdraw_lamports": ell}]
    for e in range(1064, 1071):
        r = infl_by_epoch[e - 1] + claims_by_epoch[e - 1]
        phi = ceil_div(r * 5, 100); f = S * phi // (T + r - phi)
        T += r; S += f
        trace.append({"epoch": e, "r": r, "fee_tokens": f, "T": T, "S": S})
    return T, S, n, ell, trace
lo, hi = 1, T63
while lo < hi:
    mid = (lo + hi) // 2
    if forward(mid)[1] >= S1070:
        hi = mid
    else:
        lo = mid + 1
Tf, Sf, n_rep, ell_rep, trace = forward(lo)
results["scenarios"]["history_replay"] = {"T_1063_after_spb": T63, "S_1063_after_spb": lo, "replayed_T_1070": Tf, "replayed_S_1070": Sf,
                                          "observed_T_1070": T1070, "observed_S_1070": S1070, "replayed_deposit_minted": n_rep, "observed_deposit_minted": n63,
                                          "replayed_withdraw_lamports": ell_rep, "observed_withdraw_lamports": ell63, "trace": trace,
                                          "last_epoch_total_lamports_check": {"replayed": trace[-2]["T"], "observed": int(state["pool"]["last_epoch_total_lamports"])},
                                          "last_epoch_supply_check": {"replayed": trace[-2]["S"], "observed": int(state["pool"]["last_epoch_pool_token_supply"])}}
check("history replay reproduces T_1070 exactly", Tf == T1070)
check("history replay reproduces S_1070 exactly", Sf == S1070, replayed=Sf, observed=S1070)
check("history replay reproduces the observed 1063 deposit mint exactly", n_rep == n63, replayed=n_rep, observed=n63)
check("history replay reproduces the observed 1063 WithdrawStake lamports exactly", ell_rep == ell63, replayed=ell_rep, observed=ell63)
check("history replay reproduces last_epoch_total_lamports", trace[-2]["T"] == int(state["pool"]["last_epoch_total_lamports"]))
check("history replay reproduces last_epoch_pool_token_supply", trace[-2]["S"] == int(state["pool"]["last_epoch_pool_token_supply"]))
# exact counterfactual for the observed 1063 transactions: z = claims credited in 1063 before the deposit
z63 = claims_by_epoch[1063]
S63 = lo
phi63 = ceil_div(z63 * 5, 100); f63 = S63 * phi63 // (T63 + z63 - phi63)   # honest SPB mints the epoch fee on z
n_cf = L63 * (S63 + f63) // (T63 + z63)
T_after_dep_cf, S_after_dep_cf = T63 + z63 + L63, S63 + f63 + n_cf
ell_cf = b63 * T_after_dep_cf // S_after_dep_cf
P_final = Tf / Sf
results["scenarios"]["history_1063_counterfactual"] = {
    "z_unrecognised_at_deposit": z63, "minted_actual": n63, "minted_if_recognised": n_cf, "extra_tokens": n63 - n_cf,
    "extra_tokens_value_at_1070_price": (n63 - n_cf) * Tf // Sf,
    "withdraw_actual": ell63, "withdraw_if_recognised": ell_cf, "withdrawer_shortfall_lamports": ell_cf - ell63,
    "honest_fee_tokens": f63,
    "note": "counterfactual = an honest VLB+SPB after the 1063 claims and before both transactions, including its epoch-fee mint"}

results["failures"] = failures
results["verdict"] = "PASS" if not failures else "FAIL"
print(json.dumps(results, indent=1, default=str))
sys.exit(1 if failures else 0)
