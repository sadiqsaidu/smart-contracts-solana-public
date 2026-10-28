# IV.4(d) — The immediate-mint, O(1)-account conjecture

> **Conjecture.** No TruStake-only design that mints in the same transaction as the deposit can
> guarantee R2 using `O(1)` accounts per deposit for a pool with `n` validators.

**Result.**

* The conjecture is **true** when "mints in the same transaction" means the depositor *enters
  the pool* in that transaction, i.e. the deposit transaction fixes the depositor's entitlement
  (Theorem A, Corollary A3). The proof does not depend on how the program computes the amount.
* It is **false** if minting is separated from entry. The escrow-mint construction (§4) mints
  in the deposit transaction with `O(1)` accounts and meets R2 per batch. Its correctness is
  conditional on hypothesis H_M, which is model-checked but not proved.
* The operative constraint is therefore **where entitlement is fixed**, not where tokens are
  minted.
* Theorem A also gives a cluster-wide ceiling. Under the 64-account lock limit, *no*
  TruStake-only design guarantees R2 once `n` exceeds about 51; with TBS's VLB-based settlement
  the limit is `n ≤ 22`.

Labels: **[Proved]** · **[Src]** · **[Model]** · **[Validator]** · **[Hypothesis]**.

## 1. Model: what an on-chain program can observe

**R-1 (locality) [Src/runtime].** A transaction's effect depends only on:

* the pre-state of the accounts listed in its message;
* its instruction data and signatures;
* cluster-provided values: sysvars (Clock, Rent, EpochSchedule, EpochRewards, SlotHashes,
  Instructions) and syscalls.

No syscall exposes the lamports or data of an account that is absent from the message.
`sol_get_epoch_stake` returns a vote account's epoch-start delegated stake, which a System
transfer to a stake account does not change. Instruction data is untrusted.

**R-2 (commutation) [Src/runtime].** Let `c` and `τ` be two transactions in the same slot such
that neither reads or writes an account the other writes. Then `c;τ` and `τ;c` have the same
outcomes and the same post-state. If both succeed, every continuation therefore behaves
identically. Programs cannot observe transaction order except through state; within one slot,
Clock and SlotHashes are equal.

**Adversary.** Any party that can sign a System transfer from its own account. A non-leader
adversary suffices, because Theorem A is about the existence of a reachable bad execution. The
credit can just as well come from an honest donor or a Jito tip claim, which is a lamport credit
to stake accounts by a non-pool program.

**R2 yardstick.** This is the one used in `PROOFS.md` §0. A depositor of `L` who *enters* at a
transaction `τ` executed at pre-state `x` is owed `L·Σ*(x)/Θ*(x)` tokens, up to `ε` tokens.
`Θ*` and `Σ*` crystallize the pending epoch fee.

**Definition (entry transaction).** A design gives depositor `u` *entry at `τ`* if `u`'s final
token allocation is compared with the fair allocation at the pre-state of `τ`. Equivalently,
`u` bears no share of counted credits before `τ` and a pro-rata share of those after it.

* For an immediate-delivery design, `τ` is the deposit transaction.
* For TBS, `τ` is `settle`.

## 2. Theorem A — the entry transaction must read every value-bearing account

**Lemma A1 (credit) [Src; Validator].** Let `x` be a fresh, reconciled state
(`D_T = D_S = 0`, reachable: run `O`). Let `c` be a System transfer of `z` lamports to a listed,
usable, delegated validator stake account `V_j`. Then `c` succeeds and the pool stays fresh. It
leaves `T, S, Σ` unchanged and gives `Θ*(c(x)) = T + z` and `Σ*(c(x)) = S + f(z)`, where `f` is
SPL's `calc_epoch_fee_amount` (S:241–255).

* Sources: P:2073–2101 (sweep, then `A_j := v_j`) and P:2217–2286.
* Executed: I.1 W3 (`D_T = +777,777`), and E1/E2 here.

**Lemma A2 (separation) [Proved; Model].** For `T, S, L, z ≥ 1`:

```
L·S/T − L·(S + f(z))/(T + z)  ≥  L·S·(19z − 20) / (20·T·(T + z)).
```

*Proof.*

* Write `φ = ⌈z/20⌉ ≤ z`. The branch `f = r` needs `T + z = φ`, which is impossible when
  `T ≥ 1`; so `f(z) = ⌊S·φ/(T + z − φ)⌋ ≤ S·φ/T`.
* The left side equals `L·(S·z − T·f(z)) / (T·(T + z))`.
* `S·z − T·f(z) ≥ S·(z − φ) ≥ S·(19z − 19)/20`. ∎

[Model] `model/theorem_a_check.py` verified the inequality exactly on 200,000 random
`(T, S, z, L)` up to `10^18`. On the live pool (`T = 66,101,088,311`, `S = 16,407,030,513`) with
`z = T`, the two fair allocations of a 100 SOL deposit differ by **48.7%**.

**Theorem A [Proved].** Suppose a design guarantees, for every reachable execution, that
depositor `u`'s final allocation is within `ε` tokens of the fair allocation at its entry
transaction `τ`. Then, for every deposit with `L > 80ε·T/(S·(19 − 20/T))` (for example
`L ≳ 17ε` lamports at the live price `T/S ≈ 4.03`), `τ` must include in its account list:

* every listed usable validator stake account `V_j`;
* every transient `X_j(σ_j)` with `τ_j ≠ 0`;
* the reserve.

*Proof.*

1. Suppose `V_j ∉ accounts(τ)`. Take a reachable reconciled `x`, a fresh donor `D ∉ accounts(τ)`,
   and `c` = transfer of `z = T` from `D` to `V_j` in the same slot as `τ`.
2. Executions `e₁ = …c;τ…` and `e₂ = …τ;c…` are both reachable. The leader may order either
   way, or the donor may send at either moment.
3. By R-2, `e₁` and `e₂` have equal post-states after `{c, τ}`, hence equal continuations, hence
   the same final allocation `t_u`.
4. In `e₁`, entry is at pre-state `c(x)`, with fair allocation `F₁ = L·(S+f(z))/(T+z)`. In `e₂`,
   it is at `x`, with `F₂ = L·S/T` (A1).
5. By A2 with `z = T`, `F₂ − F₁ ≥ L·S·(19T − 20)/(40·T²)`.
6. Both `|t_u − F₁| ≤ ε` and `|t_u − F₂| ≤ ε` would imply `F₂ − F₁ ≤ 2ε`, a contradiction for
   `L` above the stated threshold.
7. The same argument applies to `X_j` with `τ_j ≠ 0` (P:1967–2057 records `x_j`) and to the
   reserve (P:2223–2225). ∎

**Remarks.**

* Smaller `z` already suffices. The separation is about `0.95·L·z·S/(T(T+z))`, so a large
  deposit is broken by a small credit.
* The direction is fixed: in `e₁`, if `t_u` is fair for `e₂`, the depositor gains from
  incumbents.
* The theorem constrains *access* (account listed), not writes. A read-only listing suffices
  for the information argument.

**Corollary A3 (the conjecture, entry form) [Proved].** In a design whose deposit transaction
is the entry transaction, the deposit transaction accesses at least
`n + #{j : τ_j ≠ 0} + 1 = Ω(n)` accounts. `O(1)` per deposit is impossible.

**Corollary A4 (cluster ceiling) [Proved, given the lock limit].**

* Any entry transaction that mints through DepositSol also needs at least 12 further distinct
  accounts: fee payer, stake pool, withdraw authority, funding, destination, manager fee
  account, mint, System program, Token program, SPL program, deposit authority, and the
  validator list (needed to know which accounts are counted). So it needs at least
  `n + n_x + 12` locks. With the 64-lock limit (128 if the feature is active), strict R2 is unattainable for **any**
  TruStake-only design when `n > 52 − n_x`.
* VLB-based designs (TBS, "fresh") need `V_j` and `X_j` for every `j` plus 19 fixed accounts,
  so `n ≤ 22` at 64 locks (mainnet: the 128-lock feature is not activated) and `n ≤ 54` at 128
  (the local validator, measured: 128 accounts pass, 129 fail).
* A design that merely *reads* each `V_j` and reverts on any uncached lamport reaches about 51,
  but a 1-lamport donation per slot can keep it from ever succeeding (R3 failure).

## 3. Constructive matching upper bound: "fresh" immediate deposit

**Construction F.** The deposit instruction performs, in one instruction,
`VLB(all, verified pairs, no_merge=true) → SPB → DepositSol(L)`, with the same coverage checks
as TBS `settle` (SPEC §5.5).

**Theorem F [Proved; Model; Validator].** For `n ≤ N_MAX`, construction F gives immediate entry
with per-deposit transfer in `(−P, 0]` and `2n + O(1)` accounts. This matches Corollary A3 up
to the factor 2 for `X_j`. The proof is the same as R2(1): J6 plus D3.

* [Model] 400 randomized runs, 0 violations; witness transfer −3.35 lamports after a 50 SOL
  credit.
* [Validator] E1 executes exactly this instruction sequence, with adversarial donations earlier
  in the same transaction.

Construction F settles R2 for I.1 divergences, but not the *uncredited-yield* leak (an epoch-`E`
deposit captures epoch-`E` rewards paid at `E+1`). That is the economic motivation for E+1
pricing; see `ATTACK_ANALYSIS.md` A3.

## 4. Escrow-mint: minting immediately with O(1) accounts and still meeting R2 per batch

**Construction EM.**

* **Deposit** (`O(1)` accounts, about 15): DepositSol(`L`) at the *recorded* price, minting
  `t_u = ⌊L·S/T⌋` into a program escrow. The ticket records `(L_u, t_u)`.
* **Settlement** (`O(n)`, once per batch, `n ≤ N_MAX`):
  1. Run `O`. Let `L_all, t_all` be the lamports and tokens of all unsettled batches.
  2. Compute `t*_b = ⌊L_b·(Σ − t_all)/(Θ* − L_all)⌋`.
  3. Burn `t_b − t*_b` from escrow, then run SPB again to re-sync `S`.
  4. Pro-rata floor claims.

**Theorem EM [Proved conditional on H_M; Model].** If `t*_b ≤ t_b + k_b`, where `k_b` is the
number of deposits in `b` (rounding), then batch `b`'s transfer is in `(−(2m_b + 1)·P_b, 0]`.
It is measured at the incumbents' net price excluding all escrow. Entry is at settlement, so EM
satisfies Theorem A with the settle transaction as `τ`.

*Proof sketch.*

* After `O`, the incumbents' tokens are `Σ − t_all` and their assets are `Θ* − L_all`.
* `t*_b` buys `L_b` at exactly that price (floor).
* Burning the excess returns its value to all non-escrow holders pro rata.
* The per-claim floor and dust are as in R1/R2. ∎

**Hypothesis H_M (monotone incumbent net price).** In the mainnet-2026 cell, between a deposit
and its settlement, the incumbents' net price `P_inc` never falls below the recorded price paid
at the deposit. Then `t*_b ≤ t_b + k_b`. Supporting facts:

* `P_rec ≤ P_net` at a fresh state, by I.1 `D_T, D_S ≥ 0` and the fee bound
  `(T+r−φ)/S ≥ T/S`.
* In-cell writers raise `P_net`: rewards net of fee, gifts, withdrawals at `P_rec ≤ P_net`, and
  burns.
* A rent **increase** lowers it. That is outside the cell, and `model/check_iv4.py` constructs
  the shortfall: 769,687,923 tokens.

[Model] There was no shortfall in 400 in-cell randomized runs. **H_M is not proved here.** It is
a monotone-NAV statement in the territory of Challenge II.1.

**What EM shows.** If "mints in the same transaction" is read literally, EM is a (conditional)
counterexample: it mints in the deposit transaction with `O(1)` accounts and meets R2 per batch.
It pays for this with delayed delivery, Policy A only (tokens already exist, so a blacklisted
user cannot be refunded in SOL), and no cancellation.

## 5. Loopholes considered and excluded

| Escape attempt | Why it fails or is out of scope |
|---|---|
| Randomly chosen subset of validators checked per deposit | A message's account list is fixed at signing. For each concrete `τ`, some `V_j ∉ τ`, and Theorem A applies to that execution. |
| Snapshot or oracle account updated elsewhere | The snapshot is not `V_j`; R-2 still commutes `c` and `τ`. A signed off-chain attestation adds a trusted party (R5) and has the same window. |
| Later true-up or clawback | Delivered tokens cannot be clawed back (no freeze authority). Any later correction sees identical final states in `e₁` and `e₂` (R-2). |
| Insurance or subsidy fund pays the difference | Not TruStake-only value; unbounded in `z`; adds trust. |
| Allow only tiny deposits `L ≲ 17ε` | Trivial; excluded by the threshold. |
| Jito bundles to make multi-transaction settlement atomic | A block-builder service, not protocol semantics; a leader adversary ignores it. |
| Redefine fairness to let depositors share pre-entry credits | That contradicts R2's I.1 yardstick. |

## 6. Remaining gap

1. R-1/R-2 are taken from runtime semantics, not proved from source. A future syscall exposing
   arbitrary account state would void R-1.
2. H_M is unproved, so EM's counterexample is conditional.
3. The "entry" definition fixes what R2 means for non-batch designs. Under a different
   yardstick the theorem changes.
4. Account-lock limits (64 vs 128) shift Corollary A4's constants, not its form.
