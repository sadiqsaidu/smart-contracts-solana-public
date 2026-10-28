# Temporal analysis: ordering, commutativity, reconciliation

Notation is from `STATE_MODEL.md`. "Window" means the slots between an epoch's last SPB and the next
epoch's first SPB, minus the stale interval `[boundary, first SPB)`, during which price-sensitive
operations revert.

## 1. Mainnet timeline of one epoch (as observed; `MAINNET_OBSERVATIONS.md` §3)

```
slot index:  0 ........ ≤648 ........ 781–8,605 .......... 9,602–146,584 ............ 431,999 | next epoch
             boundary   inflation     first VLB+SPB        Jito claims for e−1                  | ω, then VLB sweeps the
             ω = true   credited      (λ := E)             credited to V0/V1/V3                 | claims and SPB records them
             λ < E      (L3)          D_T := 0             D_T := Σ claims, λ = E (fresh)       |
             deposits/withdrawals revert ◄───────────────► deposits/withdrawals succeed at T excluding the claims
```

## 2. Sequences

"Legal" means every instruction succeeds in the modelled source. A "price-sensitive success" means a
DepositSol or WithdrawStake executes while `D_T > 0`. "Effect" is the transfer relative to an
honest-reconciliation counterfactual (SPB immediately after the credit). The *Evidence* column uses
**M** = model check, **L** = local validator, **C** = mainnet chain/simulation.

| # | Sequence (within epoch `E`, after its first SPB unless stated) | Legal | Min. authority | Fresh? | `D_T` after | Price-sensitive success? | Effect | Later maintenance | Preventable by a third party? | Evidence |
|---|---|---|---|---|---|---|---|---|---|---|
| S1 | credit **before** the epoch's complete maintenance (e.g. a claim at slot index < first SPB) | yes | claimant: any | becomes fresh at SPB | 0 | — | none (recorded before the first deposit) | — | n/a | M, C (no claim ever landed this early: 0/178) |
| S2 | complete maintenance → credit → deposit | yes | depositor: whitelisted | yes | `a` | **yes** | depositor + ≈ `0.95·a·L/(T+a+L)`; incumbents − the same | recognises (does not reverse) | **yes**: anyone can run VLB+SPB (SPB alone for reserve credits) before the deposit | M, L, C (live `D_T` = 106,921) |
| S3 | maintenance → deposit → credit (same epoch) | yes | whitelisted | yes | `a` | yes | **identical to S2** (L7) | recognises | only by reconciling after the credit, before next epoch's mint; this deposit is already priced | M |
| S4 | credit and deposit in **one transaction** (`[credit, Staker.deposit]`) | yes | the depositor must fund or trigger the credit; for a Jito claim, any fee payer can include `ClaimWithPayer` | yes | `a` | yes | as S2; if self-funded, the depositor pays `a` (combined P&L < 0, see ECONOMIC_ANALYSIS §4) | recognises | not inside that tx | M, L |
| S5 | `[VLB, SPB, deposit]` in one transaction | yes | depositor | yes | 0 | yes, at reconciled price | 0 (honest counterfactual) | — | — | M, L |
| S6 | partial VLB on `V_0` → credit to `V_0` → VLB on `V_1` → SPB | yes | any | yes | `a` (missed) | yes | as S2 | next full VLB | yes | M |
| S7 | credit to `V_1` (not yet processed) → VLB on `V_1` → SPB | yes | any | yes | 0 | — | none | — | — | M |
| S8 | credit **during the reward window** (`ω`) | lamport credits to stake accounts are not blocked by the runtime [Unverified for Stake v5 restrictions; no Stake instruction is involved in a claim]; VLB, deposit and withdraw all revert | — | no (`λ < E`) | — | **no** | none (recorded at this epoch's first SPB) | — | — | M (guards) |
| S9 | multiple claims spread over the epoch | yes | — | yes | Σ credits so far | yes | each deposit's capture depends only on `D_T` at the *next recording*, not on its own timing within the window (L7) | — | yes | M, C (3 claims/epoch) |
| S10 | many depositors between credit and recording | yes | whitelisted | yes | `a` | yes | together they capture ≈ `0.95·a·ΣL/(T+a+ΣL)`, split pro rata | — | yes | M (follows from L5) |
| S11 | burn before fee calculation (`Σ < S`) | yes | holder | yes | 0 | — | burner gifts value. The fee uses recorded `S`, not `Σ` (M check "epoch fee uses recorded S"). | SPB sets `S := Σ` | — | M |
| S12 | claim directed to an unlisted account | yes | — | yes | 0 | — | none | — | — | M, L |
| S13 | withdrawal in the window | yes | holder | yes | `a` | yes | withdrawer forfeits ≈ `ℓ·a/(T+a)` to remaining holders | — | yes | M, C (1063: −4,853 lamports to the withdrawer) |
| S14 | external reserve top-up late in epoch `E` (observed 1030) | yes | anyone may send; depositor whitelisted | yes | `a` (28% of `T`) | yes | material (ECONOMIC_ANALYSIS §5) | recognises at `E+1` | **yes, by SPB alone**, 1 tx, ~11k CU | M, C |

## 3. Commutativity results

* **C1 (assets commute).** Any interleaving of credits, deposits, withdrawals and complete maintenance
  within an epoch yields the same final `T` after a closing complete maintenance (L5). It also yields
  the same manager-fee *value* up to rounding (L6).
* **C2 (allocations do not commute).** The final token allocation depends on whether each
  price-sensitive operation precedes or follows the recording of each credit, and on nothing else
  (L1, L7). Counterexample to full commutativity: S2 vs S5 with the same `L` and `a` (M: L = 10⁹,
  a = 5·10⁷ on the toy pool mints 250,000,000 vs 249,892,095).
* **C3 (credit and maintenance do not commute).** `credit; SPB` ≠ `SPB; credit` in `T`, but the
  difference disappears at the next complete maintenance. Maintenance never reverses a credit; it only
  records it.
* **C4 (deposit and maintenance commute for the depositor iff `D_T = 0`).** If `D_T = 0` before the
  deposit, `[SPB, deposit]` and `[deposit, SPB]` give the same mint (SPB is a no-op). Otherwise the
  depositor strictly prefers deposit-first. [L: S2 vs S5]

## 4. Information and control

| Question | Answer | Evidence |
|---|---|---|
| Can an actor *observe* a late credit? | Yes, immediately: `Σ(v_i − d_i − ρ)` from public accounts, or `simulateTransaction([VLB, SPB])` | C (`simulate_theta.json`) |
| Can an actor *cause* a Jito credit? | It can only cause the *timing*, after Jito uploads the root. `ClaimWithPayer` has no caller check [Src, master]; proofs are public [Unverified]. The amount is fixed by Jito's tree. | Src |
| Can an actor create or enlarge the tips? | Only by paying tips to the validator (its own money; ≈ 90–96% returns to all delegators pro rata). That is a donation with a commission haircut. | ECONOMIC_ANALYSIS §4 |
| Can an actor cause an external reserve top-up? | Only by paying it (a donation). The 1030 top-up was by a third party. | C |
| Can a holder protect incumbents? | Yes. A permissionless VLB+SPB after any credit sets `D_T = 0`. Observed bots never do this after claims (0/51 epochs). | C |
| Leader / ordering power | Not needed. The window lasts most of an epoch (L7). A leader can only reorder its own slots, and gains nothing a regular depositor cannot. | M |
| Competition | Other depositors split the same `0.95·a`. Any maintainer can zero it. | M |
