"""Independent cross-check of the local-validator run against exact SPL arithmetic.

Reads harness/results.json (written by late_credit_roundtrip.ts). Using only the recorded snapshots and
inputs, it recomputes every mint, fee and payout with Python integers, and compares each to the
program's actual on-chain result. Run: python3 -I compare_local.py results.json
"""
import json, sys

d = json.load(open(sys.argv[1]))
ceil = lambda a, b: -(-a // b)
st = {s["label"]: s for s in d["steps"]}
I = lambda x: int(x)
out, bad = [], 0


def cmp(name, model, chain):
    global bad
    ok = int(model) == int(chain)
    bad += not ok
    out.append({"name": name, "model": int(model), "chain": int(chain), "match": ok})


rt = d["roundtrip"]
L, z = I(rt["L"]), I(rt["z"])
c = st["X: after late credit z to V0"]
T, S = I(c["T"]), I(c["S"])
# 1. window deposit at the recorded price
cmp("window deposit mint = floor(L*S/T)", L * S // T, rt["minted"])
# 2. honest counterfactual: VLB+SPB first (r = z, fee f), then deposit
phi = ceil(z * 5, 100); f = S * phi // (T + z - phi)
cmp("counterfactual mint = floor(L*(S+f)/(T+z))", L * (S + f) // (T + z), rt["cf_minted"])
# 3. same-tx credit + deposit for depositor2
dsnap = st["X: after window deposit L"]
L2 = 5 * 10**9
cmp("credit+deposit same tx mint", L2 * I(dsnap["S"]) // I(dsnap["T"]), st["X: after same-tx credit z2 + deposit"]["minted2"])
# 4. same-tx VLB+SPB+deposit for depositor3
s2 = st["X: after same-tx credit z2 + deposit"]
T2, S2 = I(s2["T"]), I(s2["S"]); r3 = I(s2["D_T"]); phi3 = ceil(r3 * 5, 100); f3 = S2 * phi3 // (T2 + r3 - phi3)
L3 = 5 * 10**9
cmp("maintenance+deposit same tx: fee tokens", I(s2["feeTokens"]) + f3, st["X: after same-tx VLB+SPB+deposit (depositor3)"]["feeTokens"])
cmp("maintenance+deposit same tx: depositor3 mint", L3 * (S2 + f3) // (T2 + r3), st["X: after same-tx VLB+SPB+deposit (depositor3)"]["minted3"])
cmp("after depositor3: T", T2 + r3 + L3, st["X: after same-tx VLB+SPB+deposit (depositor3)"]["T"])
# 5. X+1 recognition fee
pre = st["X+1: before maintenance (stale)"]; post = st["X+1: after recognition maintenance"]
r = I(post["T"]) - I(pre["T"]); phi = ceil(r * 5, 100)
cmp("X+1 epoch-fee mint", I(pre["S"]) * phi // (I(pre["T"]) + r - phi), I(post["feeTokens"]) - I(pre["feeTokens"]))
# 6. routed exits, replayed sequentially from the post-recognition state
T, S = I(post["T"]), I(post["S"])
total = 0
for k, e in enumerate([e for e in rt["exits"] if "lamports" in e]):
    p = I(e["p"]); b = p - ceil(p, 1000); ell = b * T // S
    cmp(f"exit {k} ({e['source']}) payout", ell, e["lamports"])
    T -= ell; S -= b; total += ell
cmp("total WithdrawStake payout", total, sum(I(e["lamports"]) for e in rt["exits"] if "lamports" in e))
# The final stake-account balances exceed the payouts by the user's OWN stake reward during the
# deactivation epoch (only the V0-sourced account is delegated to the voting local validator).
# Cross-check: V0's own reward rate that epoch applied to the V0-sourced payout.
cooldown = I(rt["redeemed_lamports"]) - total
v0_reward = I(post["V"][0]) - I(st["X: after same-tx VLB+SPB+deposit (depositor3)"]["V"][0])
v0_base = I(st["X: after same-tx VLB+SPB+deposit (depositor3)"]["V"][0]) - I(d["env"]["stakeRent"])
v0_exit = sum(I(e["lamports"]) for e in rt["exits"] if e.get("source") == "V0" and "lamports" in e)
est = v0_exit * v0_reward // v0_base
out.append({"name": "cooldown stake reward on user's own stake (not pool value)", "observed": cooldown, "estimate_from_V0_rate": est,
            "relative_diff": abs(cooldown - est) / max(1, cooldown), "match": abs(cooldown - est) <= max(1, cooldown) // 1000})
bad += 0 if out[-1]["match"] else 1
after = st["X+1: after depositor redemption"]
cmp("pool T after redemption", T, after["T"])
cmp("pool S after redemption", S, after["S"])
# 7. economics. Isolated honest world: same start, SPB right after the credit, the same deposit L, the
# same X+1 inflation r, then full redemption at the resulting price (depositor2/3 omitted in both worlds).
def world(recognise):
    T0, S0 = I(c["T"]), I(c["S"])
    if recognise:
        ph = ceil(z * 5, 100); fz = S0 * ph // (T0 + z - ph); T0, S0 = T0 + z, S0 + fz; rz = 0
    else:
        rz = z
    n = L * S0 // T0; T1, S1 = T0 + L, S0 + n
    rr = rz + r; ph = ceil(rr * 5, 100); f1 = S1 * ph // (T1 + rr - ph); T2, S2 = T1 + rr, S1 + f1
    return n, (n - ceil(n, 1000)) * T2 // S2
n_l, ell_l = world(False); n_h, ell_h = world(True)
honest = {"window_minted": n_l, "window_redeemed": ell_l, "honest_minted": n_h, "honest_redeemed": ell_h,
          "delay_attributable_realized": ell_l - ell_h, "honest_pnl_before_tx_fees": ell_h - L, "window_pnl_before_tx_fees": ell_l - L}
extra = I(rt["minted"]) - I(rt["cf_minted"])
summary = {"extra_tokens_from_window": extra, "extra_value_at_final_price": extra * T // S if S else None,
           "realized_pnl_excluding_failed_controls": total - L - I(rt["tx_fees_after_deposit"]),
           "wallet_delta": I(rt["realized_pnl_wallet"]),
           "wallet_delta_decomposition": "payouts - L - tx fees + own cooldown stake reward - fees of the two failed control txs signed by the depositor",
           "honest_world_isolated": honest}
print(json.dumps({"comparisons": out, "mismatches": bad, "summary": summary}, indent=1))
sys.exit(1 if bad else 0)
