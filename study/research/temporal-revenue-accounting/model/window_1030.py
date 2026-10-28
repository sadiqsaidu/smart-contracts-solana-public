"""Reconstruct (T, S) around the epoch-1030 reserve top-up from public data, then evaluate what a
whitelisted depositor entering inside the unrecognised window could have obtained.

Public inputs (mainnet/*.json):
  top-up z      14,573,000,000 lamports -> reserve, epoch 1030 slot-index 406,775 (reserve_donations.json)
  1031 SPB fee  182,052,877 tokens minted to the manager fee account (window_1030_1032.json)
  1030 infl.    inflation_1029_1031.json (paid at the 1031 boundary)
  1030 claims   98,233 lamports (claim_timing.json, swept at 1031)
  1032 SPB fee  133,062 tokens;   1032 deposit L = 2,552,173,055 minted 637,098,094 (vault DepositSol)
Unknowns: T, S right after the 1031 boundary's maintenance inputs, i.e. T30 = T before the top-up.
Two exact equations (floor) pin them down to a small set; every solution is reported.
"""
import json, os
H = os.path.dirname(os.path.abspath(__file__)); M = os.path.join(H, "..", "mainnet")
ceil = lambda a, b: -(-a // b)
z = 14_573_000_000
infl30 = sum(r["amount"] for r in json.load(open(os.path.join(M, "inflation_1029_1031.json")))["epochs"]["1030"] if r)
infl31 = sum(r["amount"] for r in json.load(open(os.path.join(M, "inflation_1029_1031.json")))["epochs"]["1031"] if r)
ct = json.load(open(os.path.join(M, "claim_timing.json")))["epochs"]
claims30, claims31 = ct["1030"]["z_total"], ct["1031"]["z_total"]
f31, f32, L32, n32 = 182_052_877, 133_062, 2_552_173_055, 637_098_094
r31 = z + infl30 + claims30
r32 = infl31 + claims31
phi31 = ceil(r31 * 5, 100); phi32 = ceil(r32 * 5, 100)

def forward(T, S):
    f = S * phi31 // (T + r31 - phi31); T1, S1 = T + r31, S + f
    g = S1 * phi32 // (T1 + r32 - phi32); T2, S2 = T1 + r32, S1 + g
    return f, g, L32 * S2 // T2

# scan: for each S near the price implied by the 1032 deposit, find T satisfying the 1031 fee exactly
from fractions import Fraction as Fr
P = Fr(L32, n32)
S_c = int((P * (f31 + f32) - phi31 - r32) / (Fr(phi31, f31) - P))      # analytic centre
sols = []
for S in range(int(S_c * 0.999), int(S_c * 1.001), 500):
    # f31 = floor(S*phi/(T+r-phi))  =>  T in (S*phi/(f+1) - r + phi, S*phi/f - r + phi]
    lo = S * phi31 // (f31 + 1) - r31 + phi31 + 1; hi = S * phi31 // f31 - r31 + phi31
    for T in (lo, hi):
        if T <= 0: continue
        f, g, n = forward(T, S)
        if f == f31 and g == f32 and abs(n - n32) <= 2:
            sols.append((T, S, f, g, n))
# refine around the best coarse solution at unit resolution
best = min(sols, key=lambda s: abs(s[4] - n32)) if sols else None
exact = []
if best:
    for S in range(best[1] - 2_000, best[1] + 2_000):
        lo = S * phi31 // (f31 + 1) - r31 + phi31 + 1; hi = S * phi31 // f31 - r31 + phi31
        for T in range(max(lo, 1), hi + 1, max(1, (hi - lo) // 50 or 1)):
            f, g, n = forward(T, S)
            if f == f31 and g == f32 and n == n32:
                exact.append((T, S)); break
Ts = [t for t, _ in exact]; Ss = [s for _, s in exact]
T30, S30 = exact[len(exact) // 2] if exact else (None, None)   # central representative

def jit(L, T=T30, S=S30, withdraw_fee=(1, 1000)):
    """Whitelisted depositor enters after the top-up, before the 1031 SPB; exits after it."""
    n = L * S // T; T1, S1 = T + L, S + n
    f = S1 * phi31 // (T1 + r31 - phi31); T2, S2 = T1 + r31, S1 + f
    fee = ceil(n * withdraw_fee[0], withdraw_fee[1]); b = n - fee
    ell = b * T2 // S2
    # honest counterfactual: SPB right after the top-up (reserve credit: SPB alone suffices), then deposit
    fh = S * ceil(z * 5, 100) // (T + z - ceil(z * 5, 100)); Th, Sh = T + z, S + fh
    nh = L * Sh // Th; Th1, Sh1 = Th + L, Sh + nh
    r_rest = infl30 + claims30; phr = ceil(r_rest * 5, 100)
    fr = Sh1 * phr // (Th1 + r_rest - phr); Th2, Sh2 = Th1 + r_rest, Sh1 + fr
    ellh = (nh - ceil(nh, 1000)) * Th2 // Sh2
    return {"L": L, "minted": n, "minted_if_recognised": nh, "redeemed": ell, "redeemed_if_recognised": ellh,
            "realized_gain_before_tx_fees": ell - L, "honest_realized_before_tx_fees": ellh - L,
            "delay_attributable": ell - ellh, "value_from_incumbents_mtm": n * T2 // S2 - L,
            # routing feasibility: WithdrawStake can drain every validator to rent+min_delegation and then the
            # reserve to rent; with at most 5 listed validators (1031 shows a 5th transient) the pool can pay
            "redeemable_upper_bound": T + z + L - 5 * (1_666_240 + 10**9) - 1_666_240,
            "routing_feasible": ell <= T + z + L - 5 * (1_666_240 + 10**9) - 1_666_240,
            "tx_fees_estimate": 127_503 + 5 * 20_000}

out = {"inputs": {"z": z, "infl30": infl30, "claims30": claims30, "r31": r31, "phi31": phi31, "f31": f31, "infl31": infl31, "claims31": claims31, "f32": f32, "L32": L32, "n32": n32},
       "S_analytic_centre": S_c, "coarse_solutions": len(sols), "solutions_found": len(exact), "T30_range": [min(Ts), max(Ts)] if Ts else None, "S30_range": [min(Ss), max(Ss)] if Ss else None,
       "T30": T30, "S30": S30, "z_over_T": z / T30 if exact else None,
       "jit": [jit(L) for L in [10**9, 10 * 10**9, 50 * 10**9, 200 * 10**9]],
       "window_slots_until_1031_spb": (432000 - 406775) + ct["1031"]["first_spb_slot_index"],
       "deposit_window_slots_in_1030": 432000 - 406775}
print(json.dumps(out, indent=1))
