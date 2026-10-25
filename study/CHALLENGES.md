# TruStake — Challenge Collection

Fifteen problems in four levels, ordered by conceptual dependency. **No solutions appear in this
file.** Hints are collected after the last problem, in three escalating tiers per challenge, so
they are easy to avoid.

Read `PROTOCOL_MODEL.md` first. It defines every symbol used here (`T, S, Σ, Θ*, λ, E, q, μ, m,
ρ, κ, θ, A_i, τ_i, σ_i`, the version cells, and the integer price equations). Some challenges need
`ASSUMPTION_LEDGER.md` for context, and each says which entries.

---

## Standing conventions (apply to every challenge unless it says otherwise)

1. **Version cell.**
   * Behavior is evaluated in a cell `c = (s, k)`: SPL Stake Pool version
     `s ∈ {2.0.3, 2.1.x, 2.2.0}` and native Stake program `k ∈ {legacy, v5}`.
   * Cluster parameters `(m, ρ)` complete the cell.
   * Default cell **"mainnet-2026"**: `(2.1.x, v5)` with `m = 10^9`, `ρ = 1,666,240`.
   * Two named alternatives:
     * **"documented"**: `m = 1`, `ρ = 2,282,880`, with whatever SPL/Stake versions the problem
       states;
     * **"test"**: `(cloned, legacy)` with `m = 10^9`, `ρ = 2,282,880`.
2. **Fees.** `e = 5/100`, `w = 1/1000`, `d = 0`, referral `0`.
3. **Arithmetic.** Arithmetic is exactly the upstream integer arithmetic (`PROTOCOL_MODEL.md`
   §4.2). Any real-number idealization must be labeled as such, and the deviation it introduces
   must be bounded whenever a conclusion depends on it.
4. **Profit.** For an actor 𝔄 over an execution:
   * **Realized profit `Π_rt`:** final lamports minus initial lamports. All of the following must
     hold:
     * 𝔄 ends holding no TruSOL;
     * stake accounts received from WithdrawStake are valued at their lamport balance;
     * rent that 𝔄 can reclaim is counted as reclaimed;
     * transaction fees are `c = 5,000` lamports per signature, plus any priority fee the problem
       states.
   * **Mark-to-market profit `Π_mtm`:** the same, except TruSOL held at the end is valued at the
     final `P_true = Θ*/Σ`.
   * **Timing advantage:** `Π_mtm` minus `Π_mtm` of an explicitly specified counterfactual
     execution.
5. **Reachability.** A state is *reachable* if it is produced by a finite sequence of valid
   transactions, under the stated cell and actor powers, starting from a state reachable from
   initialization.
   * An *algebraic* witness (numbers satisfying the equations) is not a reachable witness unless
     the problem explicitly accepts one.
6. **Adversary.**
   * 𝔄 signs only for its own keys. It is whitelisted only if the problem says so.
   * It may compose any instructions it can sign into one atomic transaction.
   * Default ordering power is **non-leader**: 𝔄 sees others' transactions only after inclusion
     and cannot reorder them.
   * A **leader** adversary sees transactions forwarded to its slots and may insert or reorder
     within those slots.
7. **Liveness classes.** These are used whenever something is "blocked".
   * **client-recoverable:** an honest client succeeds by choosing different parameters.
   * **bounded-delay:** it clears automatically within `k` epochs.
   * **governance-bounded:** an owner or agent action clears it.
   * **permanent:** it cannot be cleared without a program upgrade.

---

# Level I — Fundamental reconstruction

## I.1 Two Ledgers

**Difficulty / effort.** Level I. 8–15 hours.

**Fundamental question.** The pool keeps a recorded balance sheet `(T, S)` that sets every price,
and the chain holds an actual one `(Θ*, Σ)`. Inside an epoch, what exactly can make them diverge,
who controls each divergence, and in which direction can it point?

**Formal problem statement.**
Work in cell mainnet-2026. Call a state *fresh* if `λ = E`. Define:

* `Θ*(x)`: the value `total_lamports` would take if, at `x`, one executed
  `UpdateValidatorListBalance(no_merge = true)` over every list entry (in any chunking) followed by
  `UpdateStakePoolBalance`;
* `Σ(x)`: the mint supply.

Let `D_T := Θ* − T` and `D_S := S − Σ`.

* **(a)** Prove or disprove that every reachable fresh state satisfies `D_T ≥ 0` and `D_S ≥ 0`. If
  either fails, give a witness with the fewest transactions, starting from a fresh state with
  `D_T = D_S = 0`.
* **(b)** Produce a complete list of transaction types that can change `D_T` or `D_S` while
  `λ = E`. Cover every program (Staker, SPL Stake Pool, SPL Token, System, Stake) and every signer
  class (anyone, holder, whitelisted user, stake manager, owner, SPL manager, validator operator,
  cluster). For each, give the sign, a magnitude bound, and the minimal actor class.
  * Prove completeness relative to the exact set of accounts and fields that UpdateVLB and
    UpdateSPB read.
* **(c)** For each item of (b), decide:
  * whether an honest party can neutralize it *atomically*, i.e. in the same transaction as the
    diverging action;
  * whether it can be neutralized *later*, permissionlessly;
  * whether neutralizing it requires knowing that it happened.
* **(d)** Is `Θ*` well-defined? Give every condition under which
  `UpdateValidatorListBalance(no_merge = true)` itself fails at a fresh state, or prove there are
  none. (Cell matters here; consider the legacy cell as well.)

**What you must produce.**
1. The invariant proof, organized as one inductive lemma per instruction.
2. The enumeration table.
3. The minimal witnesses.
4. A short argument for why your enumeration cannot be missing a writer.

**Source-code anchors.**
* Local: `staking.rs:83-143` (deposit); `staking.rs:276-395` (deposit_to_specific_validator);
  `validators.rs:86-166` (add_validator).
* Upstream 2.1.1 `processor.rs`:
  * DepositSol, WithdrawStake (including the ValidatorRemoval truncation);
  * UpdateVLB, including the `additional_lamports` sweep, which runs even with `no_merge`;
  * UpdateSPB (saturating reserve term; fee before supply re-sync);
  * AddValidatorToPool (writes neither `T` nor `λ`).
* `state.rs`: `stake_lamports`, `calc_epoch_fee_amount`.
* Test: `tests/add_validator_donation.test.ts:396-422`.

**Why the problem is difficult.**
* Writers of `D_T` include accounts the pool does not own and transactions it never sees.
* The definition of `Θ*` hides cases where the observation instruction itself mutates state or
  reverts.
* Integer truncations in the withdrawal path move value in one direction only, and you must decide
  which.

**Verification criteria.**
* Every enumerated item is backed by a transaction that a reader can replay on a local validator,
  or by an exact-integer computation.
* The proof states its inductive hypothesis explicitly and handles every instruction in
  `PROTOCOL_MODEL.md` §3.
* A reviewer trying to break (a) with orphaned, zombie, or pre-funded accounts fails.

**Deeper extension.**
Define the *realizable* value `V*(x)`: the maximum total lamports that holders can extract by
sequences of WithdrawStake from `x`, cooperating, without new deposits and with the manager's
fee-free exit allowed.
* Is `V* = Θ*`?
* Characterize `Θ* − V*` as a function of state and cell.
* Identify which lamports are *accounted but not realizable*, and whether that gap is permanent.

---

## I.2 The Transient Automaton in a Two-Dimensional Version Space

**Difficulty / effort.** Level I. 12–20 hours.

**Fundamental question.** Stake moves in or out of a validator only through one transient account
at a time. What is the exact automaton governing that account, and how does it change when two
*independent* programs (SPL and the native Stake program) change versions under it?

**Formal problem statement.**
Fix one list entry `i`. The abstract state is the tuple

`(st_i, [τ_i > 0], kind(X_i(σ_i)), kind(V_i), timing)`

where:
* `kind ∈ {absent, zombie-0B, Uninit-200B, Init(pool-authority), Init(foreign), Stake(pool; act, deact, warm-up status), Stake(foreign)}`;
* `timing` records the activation and deactivation epochs relative to `E`.

For each cell `c ∈ {2.0.3, 2.1.x} × {legacy, v5}`:

* **(a)** Construct the transition relation. Cover:
  * TruStake and SPL actions: Increase, Decrease, `deposit_to_specific_validator`, UpdateVLB
    (`merge` / `no_merge`), RemoveValidator, WithdrawStake (each source type), Cleanup;
  * cluster actions: epoch tick, reward payout;
  * adversarial actions: System transfer into `X_i(·)`, `V_i` or `Y(·)`; native `Initialize`;
    `DeactivateDelinquent` (when its precondition holds); and any merge-then-refill composition.

  State every guard precisely.
* **(b) Direction lemma.** Prove that in every epoch, the set of successful *increase-type*
  operations (Increase, `deposit_to_specific_validator`) on entry `i` and the set of successful
  Decrease operations are never both non-empty. Alternatively, exhibit a counterexample in some
  cell.
* **(c) Removal liveness.** Prove that from every reachable state with `st_i = Active`, the owner
  plus honest permissionless actions can delete entry `i` from the list within `K` epochs. Find
  the tight `K` per cell and a worst-case starting state. Determine whether an adversary can make
  `K` unbounded, and in which cells.
* **(d)** List the reachable states, per cell, that the upstream code comment ("Possible merge
  situations for transient stake …") does not anticipate.

**What you must produce.**
1. An executable model of the relation (any language). It must produce reachable-state tables.
2. Proofs of (b) and (c).
3. A per-cell reachable-state table.

**Source-code anchors.**
* Upstream 2.1.1: `process_update_validator_list_balance` (transient block guarded by
  `transient_stake_lamports != 0`; Active-status merge branch), `process_increase_validator_stake`
  (`check_if_stake_activating`), `process_decrease_validator_stake` (`check_if_stake_deactivating`,
  `st = Active` guard), `process_remove_validator_from_pool`, `process_withdraw_stake` (source
  selection).
* The 2.0.3 counterparts.
* Native: Stake v5.1.0 `helpers/merge.rs`, `process_merge`, `process_split`,
  `process_initialize`; Agave 2.0.15 `programs/stake/src/stake_state.rs`.
* Local: `validators.rs:349-558`, `staking.rs:276-395`.

**Why the problem is difficult.**
* Two state machines owned by different programs must be composed.
* Adversaries can place accounts at addresses SPL will later read.
* Epoch-relative timing and warm-up rate limits make "activating" a three-valued notion, not a
  boolean.
* The four cells differ in ways that are each small but compound.

**Verification criteria.**
* Exhaustive exploration of the abstract model agrees with hand-checked source traces.
* For the legacy cell, at least two non-obvious transitions are replayed on a
  `solana-test-validator` pinned to Agave 2.0.15.
* For the v5 cell, either a BPF-Stake-v5 test validator is used, or every v5-specific transition is
  justified by a line-cited source argument.

**Deeper extension.**
Compose `n` entries that share the reserve, the withdrawal-routing predicates (`HA`, `HT`) and the
freshness requirement of UpdateSPB.
* Prove that the reachable set is not the product of the per-entry automata.
* Find the smallest *coupled* invariant that guarantees simultaneous removal liveness for all
  entries.
* Alternatively, show that the state of one entry can delay the removal of another, and bound the
  delay.

---

## I.3 Whose Signature Is It?

**Difficulty / effort.** Level I. 6–12 hours.

**Fundamental question.** The canonical pool names TruStake's PDAs as its authorities, but TruStake
never names its pool. What does that asymmetry permit, what does it make meaningless, and what does
it leave intact?

**Formal problem statement.**
Let `C` be the canonical pool, configured as in `scripts/init-pool.ts` and
`scripts/set-pool-staker.ts`. Adversary 𝔄 is whitelisted and may create any number of SPL pools
`X ≠ C` with arbitrary managers, stakers, funding authorities and fee configurations.

* **(a)** Characterize exactly which TruStake instructions can complete successfully with pool-side
  accounts belonging to some `X ≠ C`, as a function of `X`'s authority fields. For each, state what
  the TruStake PDA signature authorizes inside `X`.
* **(b) Non-interference.** State and prove a theorem of the form:
  > No execution of TruStake instructions whose pool-side accounts belong to some `X ≠ C` changes
  > any account read by `C`'s accounting, nor any TruStake state account except ⟨your list⟩.

  Name every upstream check your proof depends on, with line references.
* **(c)** Partition TruStake's advertised guarantees into two kinds:
  * properties of the program alone;
  * properties of `C`'s configuration, which the SPL manager can revoke unilaterally.

  The guarantees to classify are: whitelist enforcement, pause, "deposit-stake operations are not
  permitted", "SOL withdrawals are not permitted", and the meaning of the events `Deposited` and
  `DepositedToSpecificValidator`.
* **(d) Events.** Construct an execution in which an off-chain consumer that trusts authentic
  TruStake events is misled about deposits into `C`. Quantify what 𝔄 can make it believe per
  lamport spent.
* **(e)** Can a role-holder's transaction (owner, stake manager) be redirected to `X` by account
  substitution in a client library? What client-side invariant closes the gap?

**What you must produce.** The theorem with its proof; an attack trace for (d); a described (not
applied) minimal program change that binds program to pool, with an argument about what it would
and would not change.

**Source-code anchors.**
* Local: `staking.rs:14-80` and `145-254` (every pool account is `/// CHECK` with no constraint);
  `staking.rs:87-88` and `285-286` (in-program PDA derivation); `validators.rs` (same pattern);
  `state/events.rs` (event payloads).
* Upstream: `check_sol_deposit_authority`, `check_staker`, `check_reserve_stake`,
  `check_validator_list`, `check_mint`, and the `manager_fee_account` equality checks in DepositSol;
  `process_set_staker`; `process_set_funding_authority`.

**Why the problem is difficult.**
* Non-interference across two programs with separate state needs a precise frame argument, not a
  list of checks.
* "An authentic event emitted by program P" and "an event about the protocol" are different
  predicates, and the code conflates them.

**Verification criteria.**
* The proof survives a reviewer who substitutes any single account.
* The event-spoofing trace runs on a local validator against a self-created pool.
* The partition in (c) is justified line by line.

**Deeper extension.**
Suppose TruStake stores the canonical pool address in `Access` and checks it.
* Formulate the strongest security property this yields, and prove it.
* Then characterize precisely what *still* cannot be guaranteed without trusting the SPL manager
  key.
* Design a manager configuration (for example, manager = a program-controlled PDA with time-locks)
  that recovers it, and analyze the new liveness risks it introduces.

---

# Level II — Advanced protocol reasoning

## II.1 Monotone NAV?

**Difficulty / effort.** Level II, proof-heavy. 12–25 hours.

**Fundamental question.** Is the TruSOL price a one-way ratchet? Which price, the recorded or the
true one, and under which operations, versions and cluster events?

**Formal problem statement.**
For `S > 0`, let `P_rec = T/S` and `P_true = Θ*/Σ`.

* **(a)** In cell mainnet-2026 with *fixed* cluster parameters, prove or disprove:
  `P_rec(x') ≥ P_rec(x)` for every transition `x → x'` with `S(x), S(x') > 0`.
  * Cover every SPL, TruStake, Token, System and Stake transition. Include DepositSol with
    `d = 0` and with an arbitrary manager-set `d`.
  * Cover WithdrawStake from every source, including the fee transfer and the ValidatorRemoval
    truncation.
  * Cover UpdateSPB, including the fee computed with stale `S`, the special branches of
    `calc_epoch_fee_amount`, and the supply re-sync.
* **(b)** Repeat (a) in cell `(2.0.3, legacy)`. Find *all* counterexamples, give a minimal
  reachable witness for each, and identify the upstream change that removes it.
* **(c)** Now allow cluster events: changes to lamports-per-byte rent and to the minimum
  delegation. Can `P_rec` decrease under 2.1.x? By how much per event? Compare 2.0.3, and explain
  the design choice behind each version's behavior.
* **(d)** Characterize exactly the transitions that decrease `P_true`. Bound the decrease per
  transition in terms of `D_T`, `D_S` (Challenge I.1) and the transaction's size.
* **(e) Lone-actor theorem.** Formulate and prove a statement of the following form, being precise
  about the class of executions:
  > An actor who interacts only through DepositSol, WithdrawStake, burns and transfers, in an
  > execution where nobody else acts and no rewards, donations or owner actions occur, cannot end
  > with more lamports than it began with.

**What you must produce.**
1. Per-instruction lemmas with integer-exact proofs.
2. Minimal witnesses.
3. A property-based test harness over an exact-integer model that searches for violations.

**Source-code anchors.**
* `state.rs` (2.0.3, 2.1.1, 2.2.0 are byte-identical): `calc_pool_tokens_for_deposit`,
  `calc_lamports_withdraw_amount`, `Fee::apply`, `calc_epoch_fee_amount`,
  `get_lamports_per_pool_token`.
* `processor.rs`: DepositSol; WithdrawStake; UpdateSPB (2.1.1 saturating reserve term vs 2.0.3
  checked `meta` subtraction).
* 2.0.3 `is_not_removed` vs 2.1.1 `is_removed`.
* 2.0.3 WithdrawStake source selection when `0 < τ_j ≤ θ`.

**Why the problem is difficult.**
* Floors and ceilings point in different directions in different instructions.
* The epoch-fee formula uses the *previous* `T` together with a possibly *stale* `S`.
* Monotonicity can fail through accounting changes that look like no-ops, such as list cleanup or
  a rent sysvar update. These are not arithmetic.

**Verification criteria.**
* Every lemma is checked exhaustively over small integer domains (say `T, S ≤ 200`) and fuzzed
  over realistic magnitudes.
* Every counterexample is a sequence of real instructions, not an algebraic state.
* The proof is robust to `d ∈ [0,1]`.

**Deeper extension.**
Introduce hypothetical slashing: at an epoch boundary, a fraction `s` of the stake on a subset of
validators is destroyed.
* Under the current UpdateSPB logic (no negative fee, saturating reward), who bears the loss?
* Can an informed holder profit by redeeming at a stale `P_rec > P_true` (a bank run), and under
  which routing constraints?
* Design the minimal change to UpdateSPB that keeps `P_rec ≤ P_true` and allocates losses
  pro rata. Prove it.

---

## II.2 The Price of Freshness

**Difficulty / effort.** Level II. 10–18 hours.

**Fundamental question.** The owner's validator-creation donation opens a window in which recorded
assets lag actual assets. Exactly how much value moves, to whom, and in which regimes is harvesting
it profitable rather than merely redistributive?

**Formal problem statement.**
Start from a fresh state with `T = Θ*` and `S = Σ`, and incumbents holding all `S` tokens.

1. The owner executes `add_validator`, so `Θ* = T + D` with `D = q` for the regime.
2. Before any UpdateSPB, a whitelisted 𝔄 executes `deposit(A)`.
3. Then UpdateSPB executes.
4. Then 𝔄 either
   * **(i)** immediately redeems all its tokens via WithdrawStake (a round trip), or
   * **(ii)** holds.

Questions:

* **(a)** Give exact integer expressions for:
  * `Π_rt(T, S, A, D)` under (i);
  * the timing advantage under (ii), relative to the counterfactual in which 𝔄 deposits `A`
    immediately *after* the update.
* **(b)** Determine `sup_A Π_rt` as a function of `(T, D, e, w)`, the set of `T` for which it is
  positive, and the maximizing `A`.
  * Derive the real-arithmetic answer.
  * Prove an explicit bound (a constant you compute) on its deviation from the integer optimum.
* **(c)** Evaluate for `D ∈ {3,282,880; 1,002,282,880; 1,001,666,240}`.
  * Decide which regime(s) correspond to the repository's test, the README's argument, and
    mainnet-2026. Explain precisely which assumption made the repository's test pass.
  * In the 1-SOL regime, check that the round trip in (i) is *executable* under WithdrawStake
    routing and native Split rules, and not merely algebraic (see II.3).
* **(d) Mitigation.** The test proposes bundling UpdateSPB into the `add_validator` transaction.
  * Prove that this closes *this* window.
  * List which divergences from I.1 it leaves open.
  * Decide whether "prepend a full UpdateVLB + UpdateSPB to every deposit" is feasible under
    transaction limits as a function of the validator count, and what it would close.

**What you must produce.**
1. Closed forms with proofs.
2. Integer error bounds.
3. A script reproducing the numbers.
4. A one-page assessment of the README section "Why the epoch and withdrawal fees are
   load-bearing" that distinguishes round-trip profit from value transfer.

**Source-code anchors.**
* Local: `validators.rs:86-166` (`q` is computed at run time, `validators.rs:90-95`);
  `tests/add_validator_donation.test.ts` (entire file, especially the `Mode` comment block and
  lines 499-590).
* Upstream: AddValidatorToPool (the pushed entry has `A = q`; `T` and `λ` are untouched);
  UpdateSPB; `calc_epoch_fee_amount`.

**Why the problem is difficult.**
* The fee is minted on the *whole* donation using a supply that already includes 𝔄's tokens.
* The withdrawal fee is a ceiling on tokens, not lamports.
* The profit notion changes the answer qualitatively.
* The test's regime is not the regime its comments describe.

**Verification criteria.**
* The closed form matches an exact-integer simulation to within your stated bound over a grid of
  `(T, A)`.
* For the test regime, your formula reproduces the repository test's printed PnL to within one
  lamport per instruction.

**Deeper extension.**
Owners add validators at random times. Holders who already intend to add capital can time *when*
they add it at zero round-trip cost.
* Model this as a mechanism-design problem. The owner chooses the bundling policy, donation timing
  and (if possible) donation recipient.
* Find the policy that minimizes expected incumbent dilution subject to the owner's budget, and
  prove its optimality.
* Then show whether *any* TruStake-only change can make the gift go exclusively to holders as of
  the moment the owner decided to add the validator.

---

## II.3 Exit Topology

**Difficulty / effort.** Level II. 15–25 hours.

**Fundamental question.** A holder can only exit through WithdrawStake, and the source is dictated
by a global routing rule layered over native Split rules. Which positions can exit, from which
states, and how does the answer depend on parameters the protocol does not control?

**Formal problem statement.**
Primary cell: mainnet-2026; comparison cells: `(2.2.0, v5)` and "documented". A state gives:
* for each Active entry, its lamports `v_i`, delegation `δ_i`, `A_i`, `τ_i` and transient account
  state;
* the reserve `R`;
* the price `(T, S)` and hence `κ`;
* the cell's `q`, `θ`, `m`.

* **(a)** Derive the exact predicate `Redeem(x, p, src)` under which one WithdrawStake of `p` tokens
  from source `src` (the reserve, some `V_j`, or some `X_j`) succeeds. Combine SPL routing, the SPL
  remainder checks, and the native Split preconditions for each source state (active, activating,
  deactivating, inactive, Initialized; partial vs full split).
* **(b) Exit set.** Let `ℰ(x)` be the set of `p` such that a holder of `p` tokens, acting alone, can
  burn all `p` tokens through some sequence of WithdrawStake calls.
  * Characterize `ℰ(x)`.
  * Determine whether there are reachable states, and how common, in which `ℰ(x)` excludes every
    `p` below a threshold `p₀(x) > 0`. Compute `p₀`.
  * Determine whether there are reachable states in which **no** `p > 0` can be redeemed at all.
  * For each phenomenon, give:
    * a minimal transaction sequence reaching it from a healthy state, and which actors it
      requires;
    * the cheapest recovery and who can perform it;
    * its liveness class.
* **(c)** Compare the three cells. Which phenomena are artifacts of `m`, which of the SPL version,
  and which of TruStake's choice to disable WithdrawSol? Relate your findings to upstream PR #756
  (in 2.2.0).
* **(d) The client router.** Compare `getStakeAccountToSplit` in `scripts/withdraw-stake.ts`
  (lines 239-333) with your predicate. Find states where it refuses a withdrawal that would
  succeed, and states where it proposes one that fails.
* **(e) Liquidation completeness.** Can all holders together, plus the manager's fee-free exit,
  drive `T` to zero from every reachable state? If not, find the minimal irreducible residual and
  its holders.

**What you must produce.**
1. The predicate as code plus proof.
2. A reachable-state witness for each phenomenon in (b).
3. The comparison table for (c).
4. The router discrepancy list.

**Source-code anchors.**
* Upstream 2.1.1 WithdrawStake: `has_active_stake` / `has_transient_stake` with the `is_active`
  filter, `minimum_lamports_with_tolerance`, the per-source remainder checks, and ValidatorRemoval.
* 2.2.0's added `stake_minimum_delegation` term.
* Native Stake v5.1.0 `process_split` (active branch: destination pre-funded,
  `split ≥ get_minimum_delegation()`, remaining delegation `≥ get_minimum_delegation()`; full-split
  branch).
* `lib.rs` `get_minimum_delegation`.
* Local and tests: `scripts/withdraw-stake.ts:113-333`; `tests/withdrawals.test.ts:230-340`.
* README: "SOL withdrawals are not permitted".

**Why the problem is difficult.**
* `HA` and `HT` quantify over all entries, so the redeemability of one position depends on the
  state of every validator.
* The tolerance depends on the price.
* Two programs impose overlapping lower bounds that differ in what they measure: lamports versus
  delegation, and recorded versus actual values.
* The parameter that matters most changed on mainnet without any change to TruStake.

**Verification criteria.**
* The predicate agrees with the upstream source on a randomized differential test against an
  instrumented port of the routing code.
* At least one phenomenon in (b) is reproduced on a local validator running BPF Stake v5. A
  test-validator built from Agave ≥ 4.2 bundles it. Note that Agave 2.0.15's native stake uses
  different Split semantics.

**Deeper extension.**
An adversary (a holder, whitelisted) chooses deposits to specific validators and withdrawals in
order to keep a target victim's `ℰ` empty for `k` consecutive epochs.
* Determine the minimal adversary capital as a function of `k`, `m`, the number of validators, and
  the stake manager's reaction policy.
* Then decide whether re-enabling `WithdrawSol` would solve the problem or merely move it, and to
  where.

---

## II.4 Privilege Lattice

**Difficulty / effort.** Level II. 12–22 hours.

**Fundamental question.** TruStake layers its own roles over SPL's. Once the layers are composed,
what does each key actually control? Does any role's compromise escalate, and can the honest keys
revoke it without a program upgrade?

**Formal problem statement.**
The keys are: owner `O` (multisig), stake manager `K`, agent `a`, custodian `c`, SPL manager `Mgr`,
and the operator `v` of a listed validator.

Consider each single-key compromise, and the pairs `{K, v}`, `{a, any whitelisted user}`, and
`{Mgr}` with `Mgr ≠ O`. For each:

* **(a)** Compute the closure: the newly reachable states and enabled instructions.
* **(b)** Compute the maximum value extractable from holders within `k` epochs, against holders who
  react rationally with detection delay `δ` epochs. Take into account:
  * `FutureEpoch` fee delays;
  * the withdrawal-fee increase caps (both 2.1.x rules, and the 2.0.3/2.0.4 overflow);
  * immediate SOL-deposit-fee changes;
  * the absence of `minimum_pool_tokens_out` in TruStake's deposit;
  * exit constraints from II.3.

  Define "extractable" precisely.
* **(c)** Decide whether the compromise is revocable by the remaining honest keys without an upgrade,
  and the minimum time to revoke.
* **(d) Agent hydra.** Model the agent set as a game:
  * any agent adds agents;
  * any agent removes any *other* agent except `O`;
  * the removal rent goes to the remover;
  * each transaction costs `c`;
  * each agent account costs `r` rent.

  An adversary holds one agent key and has budget `B`. The honest owner can issue one removal per
  `Δ` slots, and the adversary one addition per slot.
  * Prove whether the owner can guarantee eventual removal of all adversarial agents.
  * Compute the expected net transfer of rent between the parties.
  * Determine what the adversary can do to honest *non-owner* agents in the meantime.

**What you must produce.**
1. A lattice table with, for every cell, a proof or an attack trace.
2. The hydra theorem.
3. A ranked list of the three highest-consequence single points of failure.

**Source-code anchors.**
* Local: `setters.rs`, `whitelist.rs`, `third_party_whitelist.rs`, `validators.rs:269-487`.
* README: "Authorities".
* Upstream: `process_set_fee`, `StakePool::update_fee`, `Fee::check_withdrawal` (2.0.3 and 2.1.1),
  `can_only_change_next_epoch`, `process_set_funding_authority`, `process_set_staker`,
  `process_set_manager`.

**Why the problem is difficult.**
* Privileges compose across two programs with different time semantics: immediate, two epoch
  boundaries, and capped per change.
* Rational holder responses are themselves constrained by II.3.
* The hydra game requires a careful model of blockspace and payment flows.

**Verification criteria.**
* Each lattice cell is backed by a local-validator trace or a line-cited argument.
* The hydra result is checked by simulation over parameter grids.

**Deeper extension.**
Propose the *minimal* set of TruStake-only changes such that every single-key compromise is
either:
* revocable by one owner transaction within one epoch; or
* bounded by an explicit, configurable value cap.

Prove minimality: removing any one change breaks some cell. Then identify which cells *no*
TruStake-only change can fix, and explain why.

---

# Level III — Olympiad / Putnam-inspired

## III.1 The Fee Operator

**Difficulty / effort.** Level III. 15–30 hours.

**Fundamental question.** The epoch fee is applied to "whatever increased since the last call", by
anyone, any number of times. Treat it as an operator. What do its compositions, its extremal
partitions and its integer shadow look like?

**Formal problem statement.**

* **(a) Real model.** In the real-number idealization of UpdateSPB, the fee tokens for a reward
  `r` on a pool with value `V` and supply `S` are exactly `S·e r /(V + r − e r)`. Rewards
  `r_1, …, r_k > 0` with `Σ r_j = R` arrive sequentially, each followed by an update.
  * Prove that the holders' (non-manager) final value is maximized if and only if `k = 1`.
  * For fixed `k`, find the unique partition that *minimizes* the holders' final value, and that
    minimum.
  * Find the infimum over all `k`, and the rate at which it is approached.
* **(b) Integer model.** Let `F(T, S, r)` be the fee tokens minted by `calc_epoch_fee_amount` for
  reward `r` (exact v2.x arithmetic, `e = 5/100`).
  * Determine exactly the set `𝒵 = {(T, S) : F(T, S, r) = 0 for all r ≥ 1}`. Mind the branches
    `T + r = ⌈er⌉` and `S = 0`.
  * Generalize to `e = n/d` in lowest terms.
* **(c)** For `(T, S) ∉ 𝒵`, determine the largest `r*(T, S)` such that `F(T, S, r) = 0` for every
  `r ≤ r*`.
  * Prove that a donor who splits a donation `D` into chunks of size `≤ r*`, each followed by an
    UpdateSPB, pays zero epoch fee. Account for the fact that `T` and `S` drift between chunks.
  * Using the transaction limits in `PROTOCOL_MODEL.md` §7.1 and your own CU estimate (state it),
    compute the minimal number of transactions and the base-fee cost.
  * Decide for which `(T, S, D)` chunking is cheaper than paying the fee.
* **(d)** Evaluate the README's claim that the epoch fee "dilutes a donor's own equity" in each
  region you found, and connect it to III.2.

**What you must produce.** Proofs (an inequality argument for (a); an exact Diophantine
characterization for (b) and (c)), plus brute-force confirmation tables.

**Source-code anchors.**
* `state.rs`: `calc_epoch_fee_amount`, `Fee::apply` (ceiling).
* `processor.rs` UpdateSPB: `previous_lamports` is the recorded `T`; `S` is re-synced only *after*
  the fee mint; there is no once-per-epoch guard.

**Why the problem is difficult.**
* (a) needs the right change of variables before any classical inequality applies.
* (b) and (c) nest a ceiling inside a floor with a moving denominator.
* The boundary cases of (b) are where intuition fails.

**Verification criteria.**
* (a) matches high-precision numerics, including the claimed minimizer, against randomized search.
* (b) and (c) match brute force on `T, S ≤ 10^4` and on sampled realistic magnitudes.

**Deeper extension.**
Interleave deposits and withdrawals at stale prices between partial updates.
* Show that interleaving changes *who* pays the fee.
* Find the interleaving that maximizes one actor's share of fee-free value, and prove it optimal.
* Alternatively, in a continuous-time model where rewards arrive as a Poisson process and updates
  are called by a strategic third party, compute the expected holder factor and the updater's
  optimal policy.

---

## III.2 Inflation Calculus

**Difficulty / effort.** Level III. 20–40 hours.

**Fundamental question.** The README argues that fees make share-price inflation unprofitable. In
the integer world, which also has burns, ceilings, `DepositTooSmall`, and no slippage bound, where
exactly is the boundary between safe and exploitable pool states?

**Formal problem statement.**
Start with a pool `(T₀, S₀)`, with no active validators above `θ`, in which a whitelisted 𝔄 holds
all `S₀` tokens and has capital `C`. Victims arrive sequentially with deposits `L₁, L₂, …`. Each
victim submits a TruStake `deposit`, which fails without loss if and only if it would mint zero
tokens.

Two victim models:
* **(V1)** i.i.d. from a distribution `𝒟` on `[ℓ_min, ℓ_max]`;
* **(V2)** chosen adversarially against 𝔄.

Between victims, 𝔄 may perform any sequence of deposits, SPL-Token burns, reserve donations,
UpdateSPB calls, and WithdrawStake calls. Profit is `Π_rt`.

* **(a)** Prove that, for raising `P_rec`, burns weakly dominate reserve donations, and
  characterize when the two are equivalent (connect to III.1(b)).
* **(b)** For `e = 5/100` and `w = 1/1000`, determine the optimal *target supply* `k` and capital
  `C` as functions of `𝒟` and the number of victims `n`, together with the optimal expected profit.
  Prove that the optimal `k` lies in an explicit interval.
* **(c)** Determine the minimal number `S_dead` of permanently locked tokens minted at
  initialization (with `T_dead = S_dead`) such that every attacker strategy has non-positive
  expected profit for every `𝒟` supported on `[1 SOL, ∞)`. Prove tightness.
* **(d)** TruStake mints no dead shares and relies on a TruFin-held seed.
  * State the weakest behavioral condition on the seed holder (for example "never reduces below
    `s₀` tokens") under which (c)'s conclusion holds.
  * Show what breaks when the seed holder is the sole holder and partially exits.

**What you must produce.** Theorems with proofs, plus an exact-integer simulator reproducing the
optimal strategies and the `S_dead` bound.

**Source-code anchors.**
* `state.rs`: `calc_pool_tokens_for_deposit`, `calc_lamports_withdraw_amount`, `Fee::apply`.
* `processor.rs` DepositSol: `DepositTooSmall`.
* WithdrawStake: fee ceiling and `WithdrawalTooSmall`.
* UpdateSPB: supply re-sync.
* `staking.rs:83-143`: no slippage parameter.
* README: "Deposit sizing and pool bootstrap" and "Why the epoch and withdrawal fees are
  load-bearing".

**Why the problem is difficult.**
* 𝔄's own position must stay redeemable despite a withdrawal fee that is a ceiling on tokens.
* Failed victim deposits are free for the victim.
* Supply grows with each victim, so the attacker's share decays.
* Every quantity is an integer, so the optimum sits on boundaries.

**Verification criteria.**
* Your optimal strategy beats a broad randomized search in the simulator.
* Your `S_dead` bound is attacked by an adversarial optimizer (a search over burn, donate, and
  update schedules) and survives.

**Deeper extension.**
Victims adopt "simulate, then send" but 𝔄 is a **leader** adversary that can insert transactions
ahead of victims within its slots. Model the leader schedule as a stationary process in which 𝔄
leads a fraction `β` of slots. Compute the equilibrium expected victim loss, and decide whether a
slippage-bounded deposit (upstream index 25) eliminates it.

---

## III.3 Belief Soundness (the Phantom Transient)

**Difficulty / effort.** Level III. 20–35 hours.

**Fundamental question.** The validator list holds SPL's *beliefs* about accounts it does not fully
control. Can permissionless actors make those beliefs false, what does the protocol then do with
them, and how does the answer depend on two independently versioned programs?

**Formal problem statement.**
Define three soundness predicates for entry `i`:

* **B1 (provenance):** `τ_i > 0` implies that the account at `X_i(σ_i)` is the account most
  recently created at that address by SPL's `create_stake_account`, and that it has not been
  drained to zero lamports since.
* **B2 (conservation of pool-originated lamports):** no lamport that SPL itself moved into `V_i`
  or into any `X_i(s)` ever leaves the pool's accounting (`Θ*`), except by WithdrawStake to a
  holder or by a merge into the reserve or into `V_i`. Lamports that third parties send to these
  addresses are excluded.
* **B3:** `st_i = ReadyForRemoval` at the moment Cleanup deletes the entry implies
  `A_i = τ_i = 0`.

For each cell in `{2.0.3, 2.1.x} × {legacy, v5}`:

* **(a)** Decide B1–B3. For every failure, construct attack transactions starting from a reachable
  honest state. Use only permissionless actions plus, optionally, one whitelisted
  `deposit_to_specific_validator`. Compute the attacker's cost.
* **(b)** For every false-belief state, determine:
  * which instructions change behavior;
  * whether lamports become miscounted, orphaned, or destroyed;
  * the liveness class of each blocked operation;
  * the per-epoch cost of sustaining the state.
* **(c)** For every cell in which a predicate holds, prove it. Name exactly which upstream checks
  and which native-program properties the proof uses. Your proof must break if any one of them is
  removed.
* **(d)** *Without first reading the upstream 2.0.4 change (commit `0e56295`)*, list the defects
  you would fix in 2.0.3. Then read it and explain every difference between your list and theirs.

Note that a `solana-test-validator` pinned to Agave 2.0.15, cloning an SPL ≤ 2.0.3 binary, *is*
the `(2.0.3, legacy)` cell.

**What you must produce.**
1. A per-cell verdict table.
2. Attack transactions.
3. The soundness proofs.
4. The "rediscovered audit" comparison.

**Source-code anchors.**
* Upstream 2.0.3 vs 2.1.1 `process_update_validator_list_balance`: the transient branch and its
  `transient_stake_lamports != 0` guard; the handling of `Initialized` validator stake.
* `process_remove_validator_from_pool`.
* `process_withdraw_stake` (ValidatorRemoval and Transient sources).
* `is_not_removed` / `is_removed`.
* `create_stake_account`.
* Native: Stake v5.1.0 `process_merge` (`resize(0)` of the source) and `process_initialize`
  (`data_len == 200`, no signer); Agave 2.0.15 `stake_state.rs` merge (`set_state(Uninitialized)`
  without clearing).
* Local: `tests/transient_poison.test.ts:249-288`.

**Why the problem is difficult.**
* The attack surface is the *gap* between two programs' notions of an account's lifecycle.
* Neither program is wrong in isolation.
* Which cells are vulnerable is not monotone in "newer is safer" along both axes.

**Verification criteria.**
* Every attack runs on a local validator in the corresponding cell.
* Every soundness proof survives a reviewer who deletes one cited check: the reviewer must then be
  able to construct an attack.

**Deeper extension.**
Generalize to every PDA family SPL creates with Allocate + Assign.
* Define "lifecycle ownership": the creator is the only party able to end the account's existence.
* Prove that belief soundness for *all* list fields is impossible without lifecycle ownership.
* Alternatively, give a weaker sufficient condition that the 2.1.x design actually satisfies.

---

## III.4 Controllability of Allocation

**Difficulty / effort.** Level III. 20–40 hours.

**Fundamental question.** Given SPL's transient rules, how fast can the stake manager move stake
between validators? Which allocations can it *force* when holders and whitelisted users can push
stake in and pull it out of chosen validators?

**Formal problem statement.**
Abstract model, with every element justified from the source:

* `n` Active validators with excesses `x ∈ ℕⁿ` (lamports above `q`), and reserve liquidity `r`.
* **Epoch sequence:**
  1. maintenance merges last epoch's transients:
     * an increase of `L` becomes `x_i += L`, and its `ρ` returns to `r`;
     * a decrease of `L` becomes `r += L + ρ`;
  2. the stake manager chooses, for each `i`, at most one direction:
     * increase by `L ≥ μ`, consuming `L + ρ` of `r`;
     * decrease by `L ≥ μ` with `x_i − L ≥ 0`, consuming `ρ` of `r` immediately and returning
       `L + ρ` at the next merge;
  3. subsequent operations in the same epoch on `i` must keep that direction.
* Ignore rewards unless stated.

Questions:

* **(a) No interference.** Give an exact formula for the minimal number of epochs `N*(x, b, r)`
  needed to reach a target `b` with `Σ b = Σ x + r − r_keep`, and prove optimality.
  * Characterize the targets that are unreachable in any number of epochs. Mind the granularity
    `μ` and the reserve floor.
* **(b) Pushing.** A whitelisted adversary may, each epoch, call `deposit_to_specific_validator`
  on any set of at most `k` validators, with amounts `≥ μ` from its own funds. It wins the
  post-maintenance race with probability `π` per validator per epoch; a win puts the validator into
  `Act(E)`, which blocks decreases.
  * Determine the set of allocations the stake manager can force (keep forever within ε of a
    target share vector).
  * Determine the adversary's *true* cost per blocked validator-epoch (see
    `ASSUMPTION_LEDGER.md` E1). State your accounting.
* **(c) Pulling.** Holders may redeem from any validator allowed by routing (II.3) and thereby
  shape the allocation from the other side. Combine (b) and (c). Show whether a single actor with
  both powers and capital `C` can drive validator `j`'s share to at least `α` against an optimal
  stake manager, and find the minimal `C(α, n, μ, π)`.
* **(d)** Identify the governance actions (`remove_validator`, blacklisting, pause) that break each
  adversarial strategy. Find the governance latency `L` at which expected blocked validator-epochs
  stay below a given `β`.

**What you must produce.** Theorems with proofs for (a) and for the boundary of the controllable
set in (b) and (c); a simulator that validates them.

**Source-code anchors.**
* Upstream Increase (`check_if_stake_activating`, `L ≥ μ`, reserve floor) and Decrease
  (`check_if_stake_deactivating`, `v − L ≥ q`, reserve-funded rent); the UpdateVLB merge timing.
* Local: `staking.rs:276-395`.
* README: "Stake Management Bot".

**Why the problem is difficult.**
* The model has the flavor of a combinatorial scheduling problem with a one-step delay and a
  direction lock per coordinate.
* Interference arrives as value-preserving flows, so the adversary's cost is subtle.
* Probabilistic race outcomes turn controllability into a stochastic statement.

**Verification criteria.**
* `N*` is matched by brute-force search over small `n`, small amounts, and `μ` normalized to 1.
* The controllability boundary is confirmed by simulating optimal and heuristic policies.

**Deeper extension.**
Multiple adversaries with *different* targets (a tug-of-war). Characterize the stable allocations
and decide whether the stake manager's best response can make every adversary's expected cost
strictly positive.

---

# Level IV — Frontier challenges

## IV.1 Version Archaeology and the Payout Window

**Difficulty / effort.** Level IV. 30–60 hours. Parts (a) and (c) are well-posed; part (b)'s
numeric answer is exploratory (it depends on empirical data).

**Fundamental question.** You do not know which upstream binary is running, and the version
determines whether the pool can price at partially credited rewards. Can you identify the version
from behavior alone, and can you prove the newer guard actually closes the window?

**Formal problem statement.**

* **(a) Fingerprinting.** Design a procedure that identifies the deployed SPL version among
  `{2.0.2/2.0.3, 2.0.4, 2.1.x, 2.2.0}`. Constraints:
  * use only `simulateTransaction` and `sendTransaction` of instructions TruStake participants
    (holders, whitelisted users) can sign, plus reading any account;
  * do not read the program's bytes or hash;
  * cause no harm to the pool.

  Prove that every pair of versions is distinguished, and minimize the number of required
  on-chain transactions (simulations are free). Note that `security.txt` is unreliable: a 2.1.0
  build self-reports `program@v2.0.3`.
* **(b) The 2.0.3 window.** Model partitioned rewards: each stake account is credited at one of `M`
  block heights after the calculation block, with partition assignment determined by its address.
  * Determine which updates succeed during the window, and what `T` they record.
  * Express the value transferred to a depositor who deposits after a partial update and before a
    complete one, as a function of the credited fraction `f` of pool stake, `A`, `T` and `e`.
    Compare with II.2.
* **(c) Guard soundness.** Prove that the 2.0.4+ guard prevents any freshness stamp `λ = E` from
  being set on a state in which some pool stake account's reward for epoch `E` has not yet been
  credited. State every runtime assumption you use. Then search for a residual path that defeats
  it, or prove none exists.
* **(d) Liveness cost.** Quantify the guard's cost to TruStake users: the distribution of the
  blocked window, and which actors' operations fail. Decide whether any actor can lengthen the
  window.

**What you must produce.**
1. The fingerprint procedure and its proof.
2. The window model.
3. The soundness proof, or a counterexample.
4. A measured or estimated window distribution, with a statement of the data used.

**Source-code anchors.**
* Upstream `process_update_validator_list_balance` (the `EpochRewards::get()` guard, present from
  2.0.4); new error codes `0x2b`/`0x2c`; `SolWithdrawalTooLarge` from reserve withdrawals in 2.0.4+;
  `ValidatorNotFound` from Decrease on a non-Active entry; the changed log-text format.
* Agave `runtime/src/bank/partitioned_epoch_rewards/*`.
* Stake v5 `processor.rs` (EpochRewardsActive gate).
* Local: `tests/helpers.ts:211-232` (the test waits out the payout).

**Why the problem is difficult.**
* (a) must find behavioral differences reachable without privilege and without harm.
* (c) must reason about the exact ordering of reward distribution, the sysvar flag, and transaction
  execution within a block.

**Verification criteria.**
* The fingerprint is validated against all four binaries (built from tags) on local validators.
* The soundness argument cites runtime code for every ordering claim.

**Deeper extension.**
Generalize from "partially credited rewards" to *any* cluster-level asynchronous credit, such as
the block-revenue sharing proposed in SIMD-0123 (not active). Prove a general theorem:
* State the conditions under which a per-epoch freshness flag plus a "credit in progress" guard
  suffices for price correctness.
* Show what an LST must add when credits are continuous rather than epoch-aligned.

---

## IV.2 The Colluding Validator

**Difficulty / effort.** Level IV. 30–60 hours.

**Fundamental question.** TruStake lets any whitelisted user steer stake and delay the stake
manager, and every validator operator controls its commission. How much can a coalition of the two
extract before governance responds? What is the true cost of the "griefing" the README calls
self-healing?

**Formal problem statement.**
A coalition `{v, u}`: `v` operates listed validator `j` and can change its commission; `u` is
whitelisted. The pool has `s_j` stake on `j`. The per-epoch reward rate is `r`.

* First verify the current vote-program rules on *when* commission changes may take effect, and
  state them as model constraints.
* The stake manager detects misbehavior after `d_K` epochs and then tries to decrease `j` each
  epoch.
* The owner's `remove_validator` or an agent's blacklisting of `u` takes effect after `L_O ≥ d_K`
  epochs.
* Holders may redeem from `j` subject to II.3.
* After maintenance in each epoch, the coalition wins the race to put `j` into `Act(E)` with
  probability `π`.

Questions:

* **(a)** Find the coalition's optimal strategy and its expected extracted value
  `ℰ(s_j, r, d_K, L_O, π, m)`, net of its true costs. In the 1-SOL regime each block requires a
  `deposit_to_specific_validator` of at least `μ + ρ`.
* **(b)** Give two precise definitions of "no user funds are at risk" (README, `staking.rs:258-265`):
  * a *principal* notion;
  * a *value* notion that includes foregone rewards.

  Prove that the README's statement holds under the first and fails under the second.
* **(c)** Prove a lower bound on `ℰ` for a non-trivial parameter region, or prove `ℰ = O(d_K)` and
  explain the mechanism that caps it.
* **(d)** Design a minimal TruStake change and prove that it bounds `ℰ` by a function of `d_K`
  alone. Candidates include:
  * letting the stake manager call `remove_validator`;
  * a decrease path that overrides activating transients;
  * rate-limiting `deposit_to_specific_validator` per validator per epoch;
  * requiring user-directed deposits to settle a full epoch later.

  Analyze what each candidate costs honest users.

**What you must produce.**
1. The game model, with every rule justified from source.
2. The optimal strategies.
3. The bound proofs.
4. The design proposal with its proof.

**Source-code anchors.**
* Local: `staking.rs:256-395` (the permissionless validator choice and its rationale comment);
  `validators.rs:225-267` (removal is owner-only); `validators.rs:494-558`.
* Upstream: Increase (`check_if_stake_activating` merges same-epoch activations), Decrease
  (`check_if_stake_deactivating`), RemoveValidatorFromPool (deactivates an activating transient).
* README: "Stake Management Bot".

**Why the problem is difficult.**
* The game spans four actors with different powers and latencies.
* The coalition's capital is not spent but parked in the very pool it attacks.
* The answer depends on vote-program rules outside the repository.

**Verification criteria.**
* The game is simulated with explicit race probabilities.
* The bound is checked against the simulator.
* The design change's proof names every new guard it relies on.

**Deeper extension.**
Replace a single coalition with a market in which validator operators can *buy* blocking services
from whitelisted users. Characterize the equilibrium price of one blocked validator-epoch, and
determine what it implies for the security budget TruStake implicitly relies on through KYC.

---

## IV.3 Stuck Merges

**Difficulty / effort.** Level IV. 30–60 hours.

**Fundamental question.** Maintenance assumes every matured transient can be merged somewhere. Which
combinations of external events and permissionless actions make the canonical maintenance
transaction revert? For how long does that freeze everything that requires a fresh pool?

**Formal problem statement.**
Cell mainnet-2026 (compare `(2.1.x, legacy)`). Let `𝓜` be the maintenance strategy of
`scripts/update-pool.ts`: one UpdateVLB instruction over all validators with `no_merge = false` in
a legacy transaction, followed by UpdateSPB.

* **(a)** Using the native merge classification and mergeable-pair table, enumerate every
  `(X_i, V_i)` state pair at a post-payout epoch start for which SPL attempts a merge that the
  native program rejects. For each pair, give:
  * the events that produce it: `DeactivateDelinquent` after ≥ 5 delinquent epochs, warm-up or
    cool-down rate limiting, cluster restarts, anything else you find;
  * the actors able to cause each event, and their cost.
* **(b)** Determine which of these pairs a *whitelisted user* can induce, and under which
  preconditions on validator `j`.
* **(c)** Classify the failure of `𝓜` (permanent, bounded-delay, governance-bounded,
  client-recoverable). List every freshness-gated operation unavailable meanwhile, including the
  owner's `remove_validator`, and explain why the owner cannot remove the offending validator until
  maintenance succeeds by other means.
* **(d)** Design a maintenance algorithm. Its parameters are the chunking, the per-entry
  `no_merge` choice, the ordering, and retry rules. It must:
  * provably reach `λ = E` from every reachable post-payout state, given enough transactions;
  * minimize the number of epochs during which a matured transient stays unmerged;
  * remain correct when adversaries call UpdateVLB with `no_merge = true` or with wrong transient
    accounts.

  Prove it.

**What you must produce.**
1. The enumeration with a native-source citation for each rejection.
2. Attack traces.
3. The liveness classification.
4. The algorithm with its proof.

**Source-code anchors.**
* Upstream 2.1.1 UpdateVLB: the Active-status branch checks only `activation_epoch < E` on both
  `X_i` and `V_i` before merging; no Stake-program error is caught.
* RemoveValidatorFromPool requires `λ = E`.
* Native Stake v5.1.0: `helpers/merge.rs` (`get_if_mergeable`, the pair table), `DeactivateDelinquent`.
* Local: `scripts/update-pool.ts:25-150`; `programs/staker/src/staking.rs:276-395` (a whitelisted
  user can create a transient on any Active validator).

**Why the problem is difficult.**
* The failure lives in a *combination*: an external validator event, a permissionless native
  instruction, a whitelisted TruStake action, and a client choice.
* None of the four is wrong in isolation.

**Verification criteria.**
* Reproduce at least one stuck state on a local validator. One route: create a second vote account
  that never votes, which is delinquent from genesis. Note which native-stake cell your
  test-validator runs.
* Prove the algorithm correct against your executable model from I.2.

**Deeper extension.**
Prove or refute: *no* maintenance algorithm can simultaneously guarantee freshness every epoch and
merge every matured transient within one epoch of maturity. If refuted, give the algorithm. If
proved, characterize the Pareto frontier between the two objectives.

---

## IV.4 Batch-Settlement Redesign

**Difficulty / effort.** Level IV. 40–100 hours. A research problem whose outcome is open.

**Fundamental question.** Every stale-window phenomenon in this collection comes from minting at a
recorded price that may lag reality within an epoch. Can TruStake alone, with SPL unchanged,
eliminate intra-epoch value transfer by changing *when* deposits are priced? What does doing so
cost?

**Formal problem statement.**
Design a TruStake-only mechanism (new instructions and accounts are allowed; SPL is unchanged; the
whitelist and pause semantics are preserved). Deposits made in epoch `E` are converted at a price
determined by the first complete maintenance of epoch `E+1`, and the minted TruSOL is distributed
pro rata. Requirements:

* **R1 (intra-batch fairness).** No depositor receives more value than another depositor of the
  same amount in the same batch, up to a rounding term `δ` that you must bound.
* **R2 (no stale transfer).** None of the divergences enumerated in I.1 transfers more than `δ` per
  batch between incumbents and depositors.
* **R3 (liveness).** Settlement is permissionless. No non-governance actor can block it for more
  than `k` epochs; compute `k`.
* **R4 (policy).** Specify and enforce what happens to queued funds of a user who is blacklisted
  between deposit and settlement.
* **R5 (no new trust).** The mechanism adds no trust in TruFin keys beyond the existing trust.

Questions:

* **(a)** Specify the mechanism as a state machine.
* **(b)** Prove R1–R5 under explicit assumptions.
* **(c)** Analyze new attack surfaces: manipulating the settlement price *at settlement* (donations
  or burns just before the settling update), griefing the settler, dust accumulation, interaction
  with II.3's exit constraints, and interaction with the manager's fee powers.
* **(d) Research conjecture.** Prove or refute: no TruStake-only design that mints *in the same
  transaction as the deposit* can guarantee R2 using `O(1)` accounts per deposit for a pool with `n`
  validators.

**What you must produce.** A specification, proofs, an attack analysis, and either a proof or a
counterexample for (d). A prototype in Anchor is optional, but if built it must be tested on a
local validator.

**Source-code anchors.**
* Local: all of `staking.rs`; `lib.rs`.
* Upstream: DepositSol (prices at the recorded `T/S`); UpdateSPB; the transaction limits in
  `PROTOCOL_MODEL.md` §7.1.

**Why the problem is difficult.**
* Every fix moves the stale window somewhere else: to settlement, to the crank, or to the exit
  path.
* The proof must hold against all of I.1's divergences at once, including those caused by the
  cluster.

**Verification criteria.**
* A reviewer cannot construct a transfer larger than your `δ` using any divergence from I.1.
* The liveness proof holds against an adversary who controls settlement timing within the limits
  of R3.

**Deeper extension.**
Generalize to an *asynchronous mint–redeem calculus* for any LST over an asynchronous yield source:
* define the minimal information an on-chain program must observe to price fairly;
* prove a lower bound on the latency or the account footprint required;
* compare TruStake's design point with the redemption-queue designs used by other liquid-staking
  protocols, using your formalism rather than their documentation.

---
---

# Hints

Hints are tiered:

* **H1** redirects attention.
* **H2** suggests a model or technique.
* **H3** gives a foothold, never a full solution.

### I.1 Two Ledgers
* **H1.** List the *accounts* UpdateVLB and UpdateSPB read before listing instructions. Then ask,
  for each account, who besides SPL can write its lamports or data.
* **H2.** Treat `D_T` as a potential function and write `ΔD_T` per instruction as
  `ΔΘ* − ΔT`. Most instructions change both by the same amount; find the ones that do not.
* **H3.** Look closely at three places:
  * the `additional_lamports` sweep, and why it runs even with `no_merge`;
  * what WithdrawStake's ValidatorRemoval branch does to `withdraw_lamports` *after* the tokens
    are already priced;
  * how UpdateSPB's reserve term behaves under 2.1.x when the Rent sysvar changes.

### I.2 The Transient Automaton
* **H1.** The guard that matters most for the direction lemma is not in TruStake. Read the two
  `check_if_stake_*` helpers and ask what each does to a transient created in the *same* epoch.
* **H2.** Encode states as small records and actions as guarded commands. A breadth-first
  explorer over abstract epochs `{E−1, E, E+1}` suffices, provided you model warm-up as
  `{complete, partial}`.
* **H3.** For removal liveness, ask which instruction removal needs that itself requires `λ = E`.
  Then ask what happens to `λ` if the validator being removed is the one whose maintenance
  reverts.

### I.3 Whose Signature Is It?
* **H1.** Write down every account the deposit CPI passes and mark which ones SPL compares against
  fields of the pool account that was passed in.
* **H2.** Non-interference arguments are frame arguments: prove that the write set of every
  instruction is contained in accounts whose ownership or derivation ties them to the pool account
  passed in.
* **H3.** The events contain neither the pool nor the user. Consider a pool whose
  `sol_deposit_authority` is `None`, and what the TruStake deposit PDA's extra signature does to
  such a pool.

### II.1 Monotone NAV?
* **H1.** Split instructions into those that touch `(T, S)` arithmetically and those that touch
  them by *re-observation*. The first kind is a rounding question; the second is not.
* **H2.** For UpdateSPB, compare the post-update NAV with the pre-update NAV using the inequality
  the fee formula was designed to satisfy. Check it *with* integer rounding and *with* a stale `S`.
* **H3.** In 2.0.3, consider an entry that WithdrawStake moves to `ReadyForRemoval` while its
  transient is non-zero but below `θ`. Then consider what Cleanup does in 2.0.3 compared with
  2.1.1.

### II.2 The Price of Freshness
* **H1.** Separate three quantities: the value 𝔄 captures at reconciliation, the fee the manager
  mints, and the withdrawal fee on exit. Only one of them scales with `D`.
* **H2.** In the real model, write 𝔄's profit as a function of `X = T + A`. It has the form
  `α − βX − γ/X + const`.
* **H3.** The repository's test passes because of the value of one cluster parameter in the test
  regime, not because of anything in `add_validator`. Compute the donation size in each regime
  before computing anything else.

### II.3 Exit Topology
* **H1.** Ask what kind of stake account WithdrawStake hands the user from each source, and which
  native Split branch each source therefore hits.
* **H2.** Model each Active validator by its *excess delegation* above the floor. Check which
  intervals of excess allow a withdrawal of a given size under both programs' bounds at once.
* **H3.** Find the interval of excess in which SPL's routing still classifies a validator as
  "having active stake" while the native program refuses every split from it. Then ask what
  happens to *every* holder when all validators lie in that interval.

### II.4 Privilege Lattice
* **H1.** Start with the SPL manager, not the TruStake owner. List every SPL instruction that
  checks `manager` and note its time semantics.
* **H2.** Use a two-dimensional table, keys × (instant, ≤ 2 epochs, capped, never), and fill it
  before computing any value.
* **H3.** For the hydra, note who receives the rent when an agent is removed, and what an
  adversarial agent can do to honest agents other than the owner while the owner is busy.

### III.1 The Fee Operator
* **H1.** Track the *holders'* value, not the manager's, and find the per-update multiplicative
  factor it undergoes.
* **H2.** Take logarithms. The factor becomes a function of the log-growth of total value per
  step. Determine its convexity.
* **H3.** In the integer model, the fee rounds to zero exactly when a linear inequality in
  `⌈e r⌉`, `S`, `T` and `r` holds. Bound `⌈e r⌉ ≤ e r + (d−1)/d` and look at the coefficient of
  `r`.

### III.2 Inflation Calculus
* **H1.** A burn changes `Σ` and leaves `Θ` alone. Ask what the epoch-fee formula sees when
  `r = 0`.
* **H2.** Parameterize the attack by the attacker's post-inflation token count `k`. Express:
  * the victim's rounding loss as a fractional part;
  * the attacker's share of it;
  * the attacker's exit cost via `⌈k·w⌉`.
* **H3.** For `k` below `1/w` the exit fee is exactly one token. Compare one token's value with the
  expected rounding loss of one victim, and count how many victims you need. Then ask what dead
  shares do to the attacker's share.

### III.3 Belief Soundness
* **H1.** The interesting moment is right after a merge drains `X_i`. Ask what bytes remain there
  under each Stake program, and whether anyone can turn them back into a stake account.
* **H2.** Treat each cell as the pair (does SPL read `X_i` when `τ_i = 0`?, can anyone re-create a
  pool-usable account at `X_i` without SPL?). The predicate fails exactly where both answers allow
  it.
* **H3.** In the legacy cell, `Initialize` needs no signature and lets you choose the withdrawer.
  Choose the pool's withdraw authority, then ask what `UpdateValidatorListBalance(no_merge = true)`
  does next under 2.0.3.

### III.4 Controllability of Allocation
* **H1.** Without interference, the binding constraints are the one-epoch settlement delay and the
  reserve floor, not the per-epoch direction lock. Ask when the direction lock binds at all.
* **H2.** Changes smaller than `μ` cannot be made directly. Find a two-move decomposition and its
  epoch cost.
* **H3.** For interference, separate *share* from *amount*. The adversary's pushes raise `x_j` but
  also raise the total; ask what the stake manager must do elsewhere to keep `j`'s share fixed, and
  where its liquidity comes from.

### IV.1 Version Archaeology
* **H1.** Versions differ in which *error* they return in edge cases a holder can reach. Simulation
  is free and harmless.
* **H2.** Build a distinguishing tree: each probe should split the remaining candidate set,
  ideally in half.
* **H3.** Candidates to consider:
  * a WithdrawStake from the reserve sized to leave less than rent;
  * a probe whose log text format changed between versions;
  * an UpdateValidatorListBalance during the first blocks of an epoch.

### IV.2 The Colluding Validator
* **H1.** The README counts the deposit as a cost. Write the coalition's balance sheet and check
  whether it is one.
* **H2.** Model each epoch as a race with outcome probability `π`, and model governance as a
  stopping time. The value extracted is commission times stake times the number of epochs before
  the stopping time.
* **H3.** Compare the latency of the actor who *can* undo the attack (owner) with that of the actor
  who is *supposed* to undo it (stake manager), and look for the instruction that makes the
  difference.

### IV.3 Stuck Merges
* **H1.** SPL decides to merge `X_i` into `V_i` from activation epochs alone. List the states of
  `V_i` that this check does not exclude.
* **H2.** Use the native mergeable-pair table as a matrix and overlay the states each external
  event produces.
* **H3.** `DeactivateDelinquent` needs no signature from the pool. Combine it with a whitelisted
  user's `deposit_to_specific_validator` on the same validator. Then ask which flag the canonical
  script never sets.

### IV.4 Batch-Settlement Redesign
* **H1.** Decide first what "the price" is: `P_rec` after which update, and observed by whom.
* **H2.** Treat settlement as a single atomic event and prove R2 relative to that event. The
  attacks then live at the boundary between the last deposit of a batch and the settling update.
* **H3.** For the conjecture, count the accounts a transaction must read to certify `T = Θ*`, and
  compare with the transaction lock limit as `n` grows.
