# Adversarial review

Two passes:

* **Pass A** attacks the source and runtime mechanism.
* **Pass B** attacks the economic and transaction assumptions.

Each pass tries to break the leading candidates:

* **J**: late Jito credit;
* **X**: reserve top-up window.

## Pass A — mechanism

| Objection | Applies to | Resolution | Resolved? |
|---|---|---|---|
| "Jito tips are paid to the operator, not to the pool" | J | Claimant = TruStake `V_i` in all 178 claims (`claim_detail_1070.json`: claimant `FDBQ…` = V0). V2's operator takes 100% (TDA 10,000 bps) and TruStake gets nothing there, so that part *is* operator revenue. | Yes |
| "The credit is reconciled before deposits become valid" | J, X | No. Claims land 3,849–138k slots after the first SPB, and nothing reconciles them in-epoch (0/51). The live simulation shows `D_T = 106,921` with `λ = E`. | Yes |
| "VLB only sweeps under `no_merge = false` / for some statuses" | J | The sweep runs for every usable delegated V regardless of flags (P:2073-2098; I.1 validator-executed). Mainnet maintenance sweeps every epoch (`4TQL61…`: −13,814/−33,567/−33,391). | Yes |
| "The reward guard blocks the ordering" | J | The guard blocks VLB *during* the reward window only. Claims come later, when everything is open. | Yes |
| "The local test is legacy Stake" | J, X | It is. The decisive mechanism facts come instead from **mainnet Stake v5** (simulation: sweep, `Θ*`, fee) and from mainnet history (deposit and withdraw arithmetic replayed exactly). The local run adds the production *Staker* deposit path and the controls; none of those depend on Stake semantics. Differences: `ρ` (2,282,880 vs 1,666,240) and BPF vs builtin Stake. Both enter only absolute balances. | Yes, with that labelling |
| "The deployed Staker might reconcile inside `deposit`" | J, X | The mainnet binary is not byte-matched to source. However, the 1063 mainnet `deposit_to_specific_validator` minted exactly `floor(L·S/T)` with `T` *excluding* the 88,231 credited tips (exact replay), so the deployed binary does **not** reconcile. The cloned binary did the same locally. | Yes |
| "The claim can't be triggered by the assumed actor" | J | Not needed: Jito's bot triggers it. Permissionless triggering is source-only (master branch; deployed router version unverified) and does not change the economics. | Partially (source vs deployed) |
| "Top-up recipients: maybe the transfer was intended as a deposit and later refunded" | X | No refund or deposit appears in any reserve transaction 1030–1031. 1031 SPB minted fee on it (182,052,877). The stake bot delegated it in 1031. | Yes |
| "The 1030 reconstruction is wrong" | X | 2,518 integer `(T,S)` solutions all reproduce three independent public integers (1031 fee, 1032 fee, 1032 vault mint), within a 13k-lamport `T` interval. `S` agrees with the 1063 replay chain (S₁₀₆₃ − f₁₀₃₁ − vault mint − later fees ≈ S₁₀₃₀ to within the uncounted 1032–1062 fee mints). The residual risk is an unobserved writer in 1030–1032 (e.g. a removed validator's VLB), which would have shown as a reserve delta. | Largely; exactness before 1063 is not claimed |
| "A previously documented report describes the same root cause" | J, X | Yes. The repo's `tests/add_validator_donation.test.ts` validates an Immunefi report for the owner add, and `ASSUMPTION_LEDGER.md` A1 generalises to reserve and `V_i` donations. The README discusses reserve donations (donor-profit framing only). | **Strongest objection — stands** |

## Pass B — economics and transactions

| Objection | Applies to | Resolution | Resolved? |
|---|---|---|---|
| "Fees eliminate the advantage" | J | **Correct.** Withdrawal fee 10⁻³ vs gain ≤ 1.6 × 10⁻⁶ of `L`. Breakeven credit = 678× observed. | J refuted as exploit |
| "Fees eliminate the advantage" | X | Incorrect at `a/T` = 28%: the 0.1% fee is 280× smaller than the price gap | X survives |
| "Withdrawal fails" | X | Only below ≈ 1 SOL redemption, or at single-validator capacity. Routing over validators then the reserve works (model `exit_all`, local routed exit). The 1030 per-validator split was not reconstructed, but redemption ≤ the drainable total for all tested `L`. | Largely |
| "Rent and transaction costs exceed the gain" | J | Yes (realized −1.0M for a 1 SOL round trip) | J refuted |
| | X | No (≈ 0.0002 SOL vs ≥ 0.26 SOL) | X survives |
| "The attacker cannot observe or time it" | X | A reserve transfer is public; the window was 2.8 h | X survives |
| "The attacker cannot cause it" | X | **Correct.** X needs someone else's donation. Self-funding is always a loss (ECONOMIC §4). So X is opportunistic and non-repeatable on demand. Observed frequency: one large event in 51 epochs (~100 days). | Stands (limits severity) |
| "The required authority is unavailable" | X | The attacker needs a whitelist (KYC'd; revocable). Under the program rules a whitelisted user is not "privileged", but the program can expel it. | Stands as a mitigating factor |
| "A prior pool operation invalidates the witness" | X | The 1031 IncreaseValidatorStake came after the SPB; a depositor exiting after SPB and before ~31,8xx can use the reserve or validators. Its ordering relative to the exit is a routing detail. | Yes |
| "Operationally unrealistic or negligible" | J | Negligible: 0.008 SOL of Jito revenue in 100 days | J negligible |
| | X | One historical instance. Its donor is unattributed. If the donor is TruFin, the fix is operational (bundle an SPB). | Stands |
| "Is the loss really yield?" | X | The donation is value given to holders, in effect a yield transfer. No holder's previously recorded `T`-share falls (L9). | Classification: unrecognised yield, not principal |
| "Is the manager actually harmed?" | X | It holds 78% of supply today, so it would bear most of the dilution. The fee-recipient role is neutral (L6). | — |

## Disagreements between passes, reconciled by evidence

1. **Is X "new"?**
   * Pass A says no: the root cause is identical to the known report and to ledger A1.
   * Pass B says the *trigger* (an external top-up, not an owner add) and its *size* (28% of `T`)
     are new.
   * Reconciled: it is a **new trigger instance of a known root cause**. A fix to the known report
     that only bundles SPB into `add_validator` would not cover X. A fix that reconciles inside
     `deposit` would.
2. **Is J worth reporting?**
   * Both passes say no. The economics are negative by ≥ 678×, and the only realized instance went
     against the trader.

## Failed hypotheses kept on record

* "Inflation is credited late" (H7): falsified.
* "Manager fee capture depends on timing" (H8): falsified.
* "The withdrawal path is unavailable": falsified. WithdrawStake works; only WithdrawSol is
  unreachable.
* "One WithdrawStake suffices": falsified for redemptions above one validator's spare (local first
  run).
