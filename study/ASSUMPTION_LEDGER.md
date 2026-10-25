# TruStake — Assumption Ledger

Each entry states an assumption on which TruStake's correctness, economics or availability depends,
and evaluates it against source code. Notation follows `PROTOCOL_MODEL.md` (§0 "Notation" and
"Three regimes"). Upstream line numbers refer to SPL Stake Pool **2.1.1** (code-identical to the
likely-deployed 2.1.0) unless prefixed `203:` for 2.0.3.

**Field definitions**

* **Status:**
  * *Proven* — follows from source by a short argument given here.
  * *Tested* — a repository test exercises it.
  * *External* — guaranteed by upstream/runtime, version-scoped.
  * *Asserted* — documentation or comments only.
  * *Refuted* — a witness exists.
  * *Regime-dependent* — the truth value changes with `(SPL version, Stake version, m, ρ)`.
* **Class:**
  * *Defect* — the implementation contradicts its own stated intent.
  * *Trade-off* — an accepted, documented design cost.
  * *Trusted-admin* — holds iff a privileged key behaves.
  * *Operational* — depends on off-chain procedure.
  * *Cluster* — depends on parameters TruStake does not control.
  * *Out-of-model* — the threat is unrealistic under the stated threat model.
* **Confidence** is in *this ledger's assessment*, not in the assumption.

**Spoilers.** Where an assessment is the subject of a challenge, the ledger gives the verdict and
the reason it matters, and leaves the derivation to the challenge (`→ X`).

**Execution caveat.** Nothing here was executed on a validator: the toolchain and mainnet RPC were
unreachable. Economic statements were checked with an exact-integer model of the upstream
arithmetic. Runtime and feature facts come from source reading by a research subagent (Agave
master, Stake v5.1.0, the feature-tracker history), not from on-chain state.

---

## 0. The meta-assumption

### L0 — "There is one environment."
* **Statement.** The environment in which the README's arguments were made, the environment the
  tests run in, and mainnet are the same environment.
* **Evidence.** `PROTOCOL_MODEL.md` §0 "Three regimes":
  * The scripts assert `m = 1` lamport on mainnet (`scripts/withdraw-stake.ts:313-333`).
  * The tests fund validators with `1 SOL + 2,282,880` (`tests/helpers.ts:531`).
  * Feature-tracker history shows SIMD-0490 (Stake v5, `m = 1 SOL`) active on mainnet since
    ~2026-06-18, and SIMD-0437 (rent → 1,666,240 per stake account) since 2026-09.
  * `test.sh:63-75` clones the live SPL program at test time and pins no version.
* **Why relied on.** Every quantitative safety claim in the README (fee deterrence, griefing cost,
  dust thresholds) is calibrated to one regime.
* **Status.** *Refuted* (three mutually inconsistent regimes).
* **Smallest invalidating change.** Already happened: a feature activation.
* **If it fails.** Every downstream entry marked *Regime-dependent* must be re-derived per regime.
* **Confidence.** High that the regimes differ. Medium on the exact mainnet values (no on-chain
  read).
* **Class.** Cluster plus Operational (stale documentation).

---

## 1. Share-price accounting and donations

### A1 — "A fresh pool prices correctly."
* **Statement.** If `λ = E`, DepositSol and WithdrawStake execute at the pool's true NAV.
* **Evidence.**
  * The only staleness guard is `last_update_epoch < clock.epoch` (DepositSol, WithdrawStake).
  * AddValidatorToPool writes neither `T` nor `λ`.
  * `tests/add_validator_donation.test.ts` deposit-first branch: `recordedLamportsAfterAdd ==
    recordedLamportsBeforeAdd` while the pool is fresh.
* **Why relied on.** README: "A pool holding live stake and a real token supply prices deposits
  proportionally."
* **Status.** *Refuted* (the repository test is the witness). Freshness is per-epoch;
  reconciliation is per-call.
* **Smallest invalidating change.** Any credit to an account the pool reads, between an
  `UpdateStakePoolBalance` and a deposit. Examples: an owner `add_validator`, a donation to the
  reserve, a donation to `V_i`, a holder's burn (supply side).
* **If it fails.** Value moves between incumbents and whoever trades at `P_rec` before
  reconciliation. → I.1, II.2.
* **Confidence.** High. **Class.** Trade-off (SPL design) plus Operational
  (`scripts/add-validator.ts` does not bundle the update the test proposes).

### A2 — "The epoch fee dilutes a donor's own equity" (README §"Why the epoch and withdrawal fees are load-bearing").
* **Statement.** Every donation is charged the epoch fee at reconciliation.
* **Evidence.**
  * `calc_epoch_fee_amount` (`state.rs`) computes fee *tokens* as
    `⌊S·⌈e r⌉/(T+r−⌈e r⌉)⌋`, with ceiling-then-floor.
  * UpdateSPB is permissionless and repeatable within an epoch.
  * Token burns change `Σ`, not `Θ`.
* **Status.** *Partially refuted*. In the exact-integer model:
  * there are pool states and increment sizes for which the minted fee is identically zero;
  * a donation can be split to avoid the fee;
  * burning tokens raises the price with no fee at all.

  Characterizations are left to III.1.
* **Smallest invalidating change.** A small recorded supply, a small reward increment, or
  substituting a burn for a donation.
* **If it fails.** The fee no longer deters price manipulation in exactly the states where
  manipulation is cheapest. → III.1, III.2.
* **Confidence.** High (exact-integer checks).
* **Class.** Trade-off (rounding direction), Asserted (README).

### A3 — "Donate-then-withdraw is non-profitable at any size" (README).
* **Status.** *Refuted* outside large-supply states.
  * In simulation, a bootstrap attacker using burns profits against a stream of ordinary deposits.
  * On large pools, round-trip profitability in owner-donation windows depends on
    `(T, q, e, w)` and on the regime.
* **Evidence.** README §"Deposit sizing and pool bootstrap"; DepositTooSmall guard; ceiling
  withdrawal fee; exact-integer simulation.
* **Smallest invalidating change.** The pool reaching small supply, or `q` growing (it grew about
  300× with `m = 1 SOL`).
* **If it fails.** Depositors near bootstrap can lose up to one token's worth per deposit, and the
  attacker captures most of it. → II.2, III.2.
* **Confidence.** High for existence of the counterexamples. Operational relevance depends on
  whether the live pool ever becomes small.
* **Class.** Trade-off; Asserted.

### A4 — "Floor rounding costs a depositor at most one token."
* **Status.** *Proven* (`mint(L) = ⌊L·S/T⌋`, so the loss is `< T/S` lamports).
* **Caveat.** "One token" is worth `κ` lamports, and `κ` is unbounded when supply is small.
  `κ` also widens the WithdrawStake routing tolerance (`θ = q + κ`). → III.2, II.3.
* **Confidence.** High. **Class.** —

### A5 — "Recorded supply equals mint supply."
* **Status.** *Refuted* between a holder's SPL-Token burn and the next UpdateSPB.
  * UpdateSPB computes the fee with the stale recorded `S`, then re-syncs `S := Σ`
    (`process_update_stake_pool_balance`).
  * Meanwhile, deposits and withdrawals price against the stale `S`.
* **If it fails.** A second, *liability-side* stale window. The fee formula over-mints relative to
  the post-burn supply.
* **Confidence.** High. **Class.** Trade-off.

### A6 — "Only whitelisted, unpaused, TruStake-mediated deposits mint TruSOL."
* **Status.** *External / Trusted-admin.*
  * Holds because `sol_deposit_authority` is the deposit PDA.
  * Other mints also exist: fee mints to the manager, and the deposit-fee/referral branches if
    `d > 0`.
  * The manager can set `sol_deposit_authority := None` at any time
    (`process_set_funding_authority`), with no freshness gate and no delay.
* **Confidence.** High. **Class.** Trusted-admin.

---

## 2. Fee economics, thresholds and rounding

### B1 — "Epoch and withdrawal fees will never be set to zero" (README).
* **Status.** *Asserted* (manager's discretion).
* **Constraints on the manager.**
  * Changes are delayed two epoch boundaries (`FutureEpoch::Two`).
  * Withdrawal-fee *increases* are capped:
    * 2.1.x: ×1.5 and +0.5 pp per change;
    * 2.0.3/2.0.4: ×1.5, but the check compares `Option`s and passes on multiplication overflow
      (`203:state.rs:955-988`).
* **If `w → 0`.** The fee deterrence in owner-donation windows disappears, and round trips become
  profitable at every pool size. → II.2.
* **Confidence.** High. **Class.** Trusted-admin.

### B2 — "Deposit and referral fees are fixed at zero; the referral account is inert" (README, `staking.rs:66-69`).
* **Status.** *Asserted*; true only while `d = 0`.
* **Why it matters.**
  * `SetFee(SolDeposit)` and `SetFee(SolReferral)` take effect **immediately**
    (`can_only_change_next_epoch` excludes them).
  * TruStake's deposit uses DepositSol (index 14) with no `minimum_pool_tokens_out`.
* **Smallest invalidating change.** One manager transaction.
* **If it fails.**
  * A manager (or a compromised manager key) can sandwich in-flight deposits with a 100% deposit
    fee.
  * With a non-zero referral fee, every depositor can route the referral share to an account they
    control: a self-rebate.
  * → II.4.
* **Confidence.** High. **Class.** Trusted-admin.

### B3 — "The withdrawal-fee ceiling makes dust unredeemable."
* **Status.** *Proven.*
  * `fee = ⌈p·w⌉`, so `p = 1` burns nothing and the instruction fails with
    `WithdrawalTooSmall`.
  * The effective rate is `1/p` for `p ≤ 1/w = 1000` tokens.
* **Confidence.** High. **Class.** Trade-off.

### B4 — "Fees are always collected."
* **Status.** *External; manager-controlled.*
  * If the manager fee account fails `check_manager_fee_info`, WithdrawStake charges no fee and
    UpdateSPB mints none.
  * The manager can also withdraw from the fee account itself fee-free.
* **Class.** Trusted-admin.

---

## 3. Owner-funded validator creation and freshness

### C1 — "Funding a new validator from the owner's pocket does not affect holders unfairly."
* **Statement.** The owner's `q` is a gift.
* **Status.** *Refuted as a fairness statement; true as a solvency statement.*
  * Who receives the gift depends on who trades between `add_validator` and the next UpdateSPB.
  * `scripts/add-validator.ts` does not bundle an update.
  * The gift's size is regime-dependent: 3.28 M lamports in the documented regime, ~1.0017 SOL in
    the 1-SOL regime.
* **Confidence.** High. **Class.** Operational. → II.2.

### C2 — "Fees make capturing the owner's donation unprofitable."
* **Status.** *Regime-dependent.*
  * The repository's own test shows a profitable round trip in its (1-SOL) regime.
  * In the documented 1-lamport regime, the same round trip loses money at realistic TVLs.
  * The non-round-trip *timing* advantage is positive in every regime.
* **Confidence.** High (exact-integer reproduction of the test). **Class.** Trade-off. → II.2.

### C3 — "A validator stays in the pool until the owner removes it."
* **Status.** *Refuted.* The WithdrawStake `ValidatorRemoval` source lets **any holder** take a
  validator's entire stake account and mark the entry `ReadyForRemoval`. Permissionless Cleanup
  then deletes it. Conditions:
  * no Active entry exceeds `θ`;
  * the chosen entry has `τ_j = 0`;
  * the holder can pay `v_j` to `v_j + κ` lamports' worth of tokens.
* **Smallest invalidating change.** All validators at or near their floor: the bootstrap state, or
  the moment after the stake manager drains them.
* **If it fails.**
  * The owner must re-add the validator and pay `q` again.
  * Composed with poisoning, re-adding at the same `validator_seed` fails (see C4).
* **Confidence.** High (2.1.1 WithdrawStake, ValidatorRemoval branch). **Class.** Trade-off
  (upstream design).

### C4 — "A removed validator can be re-added with seed 0" (`scripts/add-validator.ts`, `seed = 0`).
* **Status.** *Refuted under adversarial conditions.*
  * The old `V` PDA is drained either by a permissionless UpdateVLB merge or by a full
    `ValidatorRemoval` withdrawal.
  * In the same transaction, an outsider can refill it and poison the address (PROTOCOL_MODEL
    §1.2).
* **Routable.** The program takes `validator_seed: u32` from the caller.
* **Class.** Operational.

---

## 4. Bootstrap, zero supply and near-empty pools

### D1 — "The 1:1 branch is reachable only at a fresh pool or after every holder exits" (README).
* **Status.** *Proven for the branch itself* (`T = 0 ∨ S = 0`).
* **Caveat.** The pathologies that matter need only *small* `S`, not zero. One dominant holder can
  produce small `S` by burning.
* **Confidence.** High. **Class.** —. → III.2.

### D2 — "Seeding the pool prevents manipulation."
* **Status.** *Operational.*
  * TruStake mints no dead shares and applies no virtual offset.
  * The seed is an ordinary, withdrawable TruFin position.
* **If it fails** (the seed is withdrawn while the pool is small). D1's caveat applies.
* **Class.** Operational.

### D3 — "A donation into an empty-supply pool is harmless."
* **Status.** *Refuted.* With `S = 0`, `calc_epoch_fee_amount` returns `r`, so the manager is
  minted `r` tokens and owns the entire donation.
* **Class.** Trade-off (upstream).

---

## 5. Validator-specific deposits and stake-management interference

### E1 — "A griefer bears a real recurring cost (SOL plus stake-account rent)" (README §"Stake Management Bot"; `staking.rs:258-265`).
* **Status.** *Refuted as stated.*
  * `deposit_to_specific_validator(L)` mints tokens for `L+ρ` and moves exactly `L+ρ` into
    pool-owned stake.
  * The SOL is converted, not consumed; it keeps earning yield.
  * The true cost is transaction and priority fees, plus optional exit fees and an opportunity
    cost that must be defined relative to an alternative.
* **Capital required per blocked validator per epoch.** `≥ μ + ρ` (~1 SOL in the 1-SOL regime).
* **Confidence.** High. **Class.** Asserted (documentation error). → IV.2.

### E2 — "The delay lasts an epoch and is self-healing."
* **Status.** *Refuted as a protocol property; true as an operational expectation.*
  * Nothing prevents repetition each epoch.
  * Each epoch is a race after maintenance, decided by the leader's ordering.
  * The bound is governance latency (blacklisting by an agent, or the owner's `remove_validator`).
* **Class.** Operational. → III.4, IV.2.

### E3 — "No other user's deposit or withdrawal path is affected."
* **Status.** *Mostly true.*
  * Other users' `deposit_to_specific_validator` on the same validator must use the recorded seed
    and fails while a *deactivating* transient is in flight.
  * Withdrawal routing is affected only through `HT`.
* **Class.** Trade-off.

---

## 6. Transient and ephemeral PDA lifetime, seed selection, account poisoning

### F1 — "Fresh random seeds make poisoning a nuisance, not a DoS" (README, `lib.rs:119-141`).
* **Status.** *True against adversaries who cannot observe pending transactions.*
  * Instruction data travels in plaintext to RPCs and leaders. The current leader can observe an
    honest seed and insert, ahead of it, a transaction that poisons that exact address.
  * Ephemeral addresses are pool-global, so a whitelisted user's `deposit_to_specific_validator`
    can poison the *stake manager's* ephemeral seed.
  * Cost to the attacker: a zombie's rent per attempt (≥ 650,240 lamports under Stake v5;
    `ρ` under legacy stake).
  * Effect: the honest transaction fails and must be retried. This is bounded delay, limited to
    slots the attacker leads.
* **Confidence.** Medium. Leader insertion is standard; the end-to-end composition was not executed.
* **Class.** Trade-off.

### F2 — "A poisoned address is lost forever."
* **Status.** *Regime-dependent.*
  * **Stake v5** (0-byte zombie): permanent, and the refill is unrecoverable.
  * **Legacy stake** (200-byte `Uninitialized` leftover): anyone can `Initialize` it with
    authorities of their choice and withdraw the refill, which deletes it.
* **Note.** The repository's `transient_poison` test asserts the legacy shape
  (`data.length == StakeProgram.space`), which mainnet no longer produces.
* **Confidence.** High (both stake sources read). **Class.** Cluster.

### F3 — "The validator list's transient fields describe a real in-flight transient."
* **Statement.** `τ_i > 0 ⇒ X_i(σ_i)` is pool-usable stake.
* **Status.** *Regime-dependent.* Holds in some (SPL × Stake) cells and fails in at least one
  reachable cell. Upstream 2.0.4 contains a fix whose commit message describes this class.
* **Confidence.** Medium-high. **Class.** Defect in old upstream (fixed). → III.3.

### F4 — "A pre-funded ephemeral is harmless."
* **Status.** *Proven per path.*
  * Merge path (a transient exists): the pre-funding is absorbed; under v5, AE←AE merges add all
    lamports. It becomes a fee-bearing donation.
  * Split path: the pre-funding stays behind as an untracked delegated stake account that SPL
    never touches again.
  * Neither path harms holders. The split path destroys the attacker's lamports and poisons the
    seed.
* **Class.** —.

### F5 — "While stake is in flight, only the recorded seed is accepted."
* **Status.** *External, Tested* (`InvalidSeeds`; `tests/transient_poison.test.ts:458-518`).

---

## 7. Epoch transitions, stale observations, maintenance ordering

### G1 — "Updating at the start of an epoch captures that epoch's rewards."
* **Status.** *Version-dependent.*
  * **2.0.3:** UpdateVLB(no_merge) succeeds during partitioned reward payout, so `λ = E` can be
    stamped on partially credited balances.
  * **2.0.4+:** UpdateVLB reverts while `EpochRewards.active`. The pool is unusable for that
    window, estimated at a few hundred blocks.
* **Confidence.** High on code; medium on window length. **Class.** Defect (fixed upstream). → IV.1.

### G2 — "The canonical maintenance transaction succeeds every epoch" (`scripts/update-pool.ts`).
* **Status.** *Refuted under several reachable conditions.*
  * The script uses one UpdateVLB instruction over all validators, `no_merge=false`, in a legacy
    transaction with no lookup tables.
  * More than ~12 validators exceed the transaction size limit.
  * Any merge the native Stake program rejects reverts everything. Examples: a force-deactivated
    validator stake combined with an active transient, or partial warmup under the rate limit.
  * Recovery requires chunking or `no_merge` for the affected entries, which the script does not
    do.
  * While maintenance fails, every freshness-gated instruction is blocked, including the owner's
    `remove_validator`.
* **Confidence.** High for the transaction limits; medium-high for the merge conditions (native
  merge rules read in Stake v5.1.0). **Class.** Operational. → IV.3.

### G3 — "UpdateStakePoolBalance runs once per epoch."
* **Status.** *Refuted.* It is permissionless and repeatable. Each call charges the epoch fee on
  the positive change since the last *recorded* total.
* **If it fails.** The fee depends on how the reward stream is partitioned among calls.
* **Class.** Trade-off. → III.1.

### G4 — "Cluster parameters (rent, minimum delegation) are stable."
* **Status.** *Refuted.* Both changed on mainnet in 2026.
  * Under 2.1.x, the 2026 rent decrease entered `Θ` as a +616,640-lamport, fee-bearing "reward" on
    the reserve.
  * A rent *increase* would be a silent decrease of `T`. That decrease is not fee-netted and is not
    reversible.
  * The 1-SOL minimum delegation rewrote every threshold `q`, `θ` and the native Split rules.
* **Confidence.** Medium (activation dates from the tracker). **Class.** Cluster. → II.1, II.3.

### G5 — "Every holder can redeem on-chain."
* **Statement.** Any TruSOL position can be redeemed via WithdrawStake, the only exit, since
  `WithdrawSol` is disabled by configuration.
* **Status.** *Refuted in the 1-SOL regime*, by source reasoning (not executed).
  * Stake v5 requires every Split from active or activating stake to move ≥ 1 SOL and to leave
    ≥ 1 SOL delegated.
  * SPL routing forces the active path whenever any Active entry exceeds `θ`. Under 2.1.x, `θ`
    does not include `m`.
  * So positions worth less than ~1 SOL are locked out of on-chain redemption in ordinary pool
    states.
  * There also appear to be reachable states in which *no* position can redeem. Upstream 2.2.0
    (PR #756) changes the threshold for exactly this band.
* **Smallest invalidating change.** The SIMD-0490 activation itself.
* **If it fails.** Small holders' only exit is a secondary market. A reachable global freeze lasts
  until the stake manager or owner acts, and the stake manager may be unable to.
* **Confidence.** Medium. Depends on the regime holding on mainnet and on the deployed SPL version;
  worth verifying on a local validator with BPF Stake v5.
* **Class.** Cluster, plus Trade-off (the "withdraw stake only" design). → II.3.

---

## 8. Whitelist and third-party agent authorization

### H1 — "The whitelist enforces KYC on TruSOL holders."
* **Status.** *Refuted by design.*
  * It gates minting through the Staker only.
  * TruSOL is freely transferable (no freeze authority).
  * Blacklisted users can still redeem, burn, donate and run maintenance.
* **Class.** Trade-off (documented: "Whitelist checks are not enforced on withdrawals").

### H2 — "A compromised agent can be contained by removing it."
* **Status.** *Doubtful.*
  * Agent power is self-replicating: any agent adds agents.
  * Removal is per key and needs a *different* agent.
  * The removal rent goes to the remover.
* **Confidence.** High on mechanics. **Class.** Trusted-admin. → II.4(d).

### H3 — "Removing a custodian revokes its power over its users."
* **Status.** *Refuted.* Claims persist after removal; re-adding the same key revives its blacklist
  and clear powers. `agent_release_third_party_user` exists precisely to clean up orphans.
* **Class.** Operational.

### H4 — "Only a TruFin agent can move a user out of Blacklisted" (`third_party_whitelist.rs:219-221`).
* **Status.** *True in the narrow sense.*
  * Only an agent can perform `B → None`.
  * After that, the owning custodian can clear its claim and re-onboard the user to `W` in two
    transactions.
* **Class.** Trade-off.

---

## 9. Authority transfers and privilege composition

### I1 — "The SPL manager is the owner multisig" (README: "should be set to the owner account").
* **Status.** *Asserted; not enforced anywhere.*
* **If it fails** (the manager key is weaker or compromised), the manager can, without TruStake's
  involvement:
  * remove the whitelist and pause guarantees (`SetFundingAuthority`);
  * sandwich deposits (B2);
  * detach TruStake as staker (`SetStaker`), then add validators and move stake;
  * raise fees within the caps;
  * redirect fee revenue.

  TruStake's guarantees reduce to the manager key.
* **Class.** Trusted-admin. → II.4.

### I2 — "A stake-manager compromise is bounded."
* **Status.** *Partially true.*
  * It cannot add or remove validators or move funds out.
  * It can concentrate all re-allocatable stake on any listed validator, including one whose
    operator raises commission.
  * The bound is the owner's reaction time.
* **Class.** Trusted-admin. → II.4, IV.2.

### I3 — "Ownership transfer is clean."
* **Status.** *Proven with caveats.*
  * Two-step transfer.
  * The pending owner can be overwritten but never cleared to `None`.
  * The old owner remains an agent until another agent removes it.
* **Class.** Trade-off.

### I4 — "There is exactly one stake manager."
* **Status.** *Proven.*
  * The Staker checks "a StakeManager PDA exists for the signer", not `signer == access.stake_manager`.
  * These are equivalent by the invariant N1: `initialize_staker` creates one PDA;
    `set_stake_manager` creates one and closes one existing PDA, which must be the unique one.
* **Class.** —.

### I5 — "Initialization cannot be front-run" (accepted in audit).
* **Status.** *Trade-off.* `initialize_staker` is callable by anyone once. Accepted for an
  already-initialized deployment.

---

## 10. Cross-program assumptions

### J1 — "The Staker acts only on the canonical pool."
* **Status.** *Not enforced.*
  * No pool address is stored or checked.
  * The deposit and staker PDAs sign for any pool that names them, or any pool whose deposit
    authority is `None`.
  * Non-interference with the canonical pool rests on SPL's per-pool account checks.
  * The emitted `Deposited` and `DepositedToSpecificValidator` events carry neither user nor pool,
    so an authentic event from the program is not evidence of a deposit into TruStake.
* **Confidence.** High. **Class.** Trade-off. Event semantics are a Defect if any consumer relies on
  them. → I.3.

### J2 — "Upstream semantics are fixed."
* **Status.** *Refuted.*
  * Since mid-2025, at least four semantically distinct upstream versions exist: 2.0.2/2.0.3,
    2.0.4, 2.1.x, 2.2.0. Two of them were never published to crates.io.
  * The deployed version is not pinned or recorded by TruStake, and could not be verified here.
  * A 2.1.0 binary self-reports `program@v2.0.3` in `security.txt`.
* **Class.** Cluster/Operational. → IV.1.

### J3 — "An atomic, fully-fresh deposit is always constructible."
* **Status.** *Refuted* beyond ~24 validators. 64 account locks per transaction rule out
  `[UpdateVLB(all), UpdateSPB, deposit]` in one transaction, so freshness at the boundary is
  multi-transaction.
* **Class.** Cluster. → II.2(d), IV.4.

### J4 — "The local test validator reproduces mainnet semantics."
* **Status.** *Refuted* for rent (2,282,880 vs 1,666,240), merge leftovers (200-byte vs 0-byte),
  the stake program (native vs BPF v5), and the SPL version (whatever is cloned at run time).
* **Class.** Operational. Affects F2, F3 and every test that asserts exact lamport amounts.

---

## Summary: defect vs. trade-off

| Kind | Entries |
|---|---|
| Documentation or analysis that no longer matches the code or the cluster | L0, A2, A3, E1, E2, G5 (stated cost and liveness arguments) |
| Upstream defects already fixed, relevant if the deployed version is old | F3, G1, B1-overflow (2.0.3/2.0.4), C3 orphaning variants (2.0.3) |
| Operational gaps in the repository's scripts | C1 (no bundled update), C4 (seed 0), G2 (single legacy maintenance transaction, no `no_merge` fallback) |
| Trusted-admin surfaces larger than the README states | A6, B2, I1, H2 |
| Genuine design trade-offs, correctly accepted | A4, B3, D2, E3, H1, I3, I5, F5 |
| Cluster-parameter exposure with no protocol-level mitigation | G4, G5, J3 |

**The five assumptions to re-verify first**, because their failure has the largest consequence and
the least evidence:

1. G5 (small-holder redemption under the 1-SOL regime);
2. G2 (maintenance liveness);
3. L0/J2 (which regime and which upstream version are actually live);
4. B2/I1 (manager-key composition);
5. A1/C1 (intra-epoch value transfer around owner actions).
