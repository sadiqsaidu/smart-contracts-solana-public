# TruStake — Research Roadmap

This roadmap orders the fifteen challenges in `CHALLENGES.md` by conceptual dependency. For each
one it states:

* what you must already understand;
* what the challenge builds in you;
* which of its outputs later challenges consume;
* how the sequence leads to original research.

**Total effort.** Roughly 300–550 hours for a strong, motivated learner working alone. Level IV is
open-ended.

---

## 1. How the four documents fit together

| Document | Role | Spoiler level |
|---|---|---|
| `PROTOCOL_MODEL.md` | What the system *is*: state, transitions, equations, version deltas, regimes | None. It gives mechanics only; every challenge-targeted property is marked `open → X`. |
| `ASSUMPTION_LEDGER.md` | What the system *relies on*, and how well each assumption holds | Low to medium. It gives verdicts (true / false / regime-dependent) and confidence, never derivations. |
| `CHALLENGES.md` | What you must prove, construct or refute | None in the problems. Hints sit at the end in three tiers. |
| `RESEARCH_ROADMAP.md` | The order of attack and why | None. |

**If you want maximum difficulty**, read `PROTOCOL_MODEL.md` fully, but read the ledger entries for
a challenge only *after* attempting it. The ledger's verdicts are effectively one-bit hints.

---

## 2. Phase 0 — build your instruments first (15–30 h)

Every later phase needs at least one of the instruments below. Build them before attempting
Level II, because their quality bounds the rigor of everything else.

1. **Exact-integer accounting model.**
   * Re-implement, in any language with big integers, the upstream functions:
     * `calc_pool_tokens_for_deposit`, `calc_lamports_withdraw_amount`;
     * `Fee::apply` (ceiling!), `calc_epoch_fee_amount`, `get_lamports_per_pool_token`;
     * the `T`/`S`/`Σ` bookkeeping of DepositSol, WithdrawStake and UpdateStakePoolBalance,
       including the stale-`S` fee computation and the supply re-sync.
   * **Acceptance test:** it reproduces the printed PnL table of
     `tests/add_validator_donation.test.ts` in the test regime (minimum delegation 1 SOL, rent
     2,282,880) to within one lamport per instruction.
   * Used by II.1, II.2, III.1, III.2, IV.4.
2. **Routing and Split oracle.**
   * Port the WithdrawStake source-selection logic for 2.0.3, 2.1.x and 2.2.0, plus the native
     Split preconditions for legacy stake and for Stake v5, into one function
     `Redeem(state, p, src, cell)`.
   * Test it differentially against the source by reading, not guessing.
   * Used by II.3, III.4, IV.2.
3. **Abstract per-validator automaton.**
   * Write a guarded-command model of one validator entry over abstract epochs, parameterized by
     cell `(SPL version, Stake version)`.
   * Used by I.2, III.3, IV.3. It becomes the backbone of a model checker.
4. **Local validator harness, per cell.**
   * Agave 2.0.15 (pinned in `Anchor.toml`) gives the *legacy* stake cell, with rent 2,282,880 and
     minimum delegation 1 SOL.
   * A test validator from Agave ≥ 4.2 bundles BPF Stake v5.1.0.
   * Build SPL Stake Pool from tags `program@v2.0.3`, `v2.0.4`, `v2.1.0` and `v2.2.0`, and load it
     with `--bpf-program` instead of cloning mainnet. Cloning makes your results depend on the day
     you ran them; see `ASSUMPTION_LEDGER.md` J2.
   * Note: the research environment that produced this study could not download the toolchain or
     reach mainnet RPC. Nothing in it was executed on a validator. Your harness is the first place
     these claims meet reality.

---

## 3. Dependency graph

```
                         Phase 0 instruments
                                 │
          ┌──────────────────────┼──────────────────────┐
          ▼                      ▼                      ▼
   I.1 Two Ledgers      I.2 Transient Automaton   I.3 Whose Signature
     │    │                │      │      │              │
     │    └──────┐         │      │      └──────┐       │
     ▼           ▼         ▼      ▼             ▼       ▼
  II.1 Monotone  II.2 Price of   II.3 Exit     III.3 Belief   II.4 Privilege
     NAV         Freshness       Topology      Soundness      Lattice
     │    │          │           │    │           │    │         │
     ▼    │          │           │    ▼           │    ▼         │
  III.1 Fee        │           │  III.4 Control-  │  IV.3 Stuck  │
  Operator         │           │  lability ───────┼─────┐ Merges │
     │            │           │                   │     ▼        ▼
     ▼            │           └─────────────►  IV.2 Colluding Validator
  III.2 Inflation  │                              ▲
  Calculus         │                              │ (II.4)
     │            │
     ▼            ▼
  IV.4 Batch-Settlement Redesign ◄── I.1, II.1, II.2, III.1, III.2
  IV.1 Version Archaeology ◄── I.1, III.3 (version cells), II.3 (error surfaces)
```

The edges are *hard* prerequisites: the later challenge uses a definition, lemma or tool that the
earlier one produces.

---

## 4. Phase-by-phase plan

### Phase 1 — Reconstruction (Level I, 26–47 h)

| Challenge | Prerequisite concepts | What it develops | Outputs consumed later |
|---|---|---|---|
| **I.1 Two Ledgers** | Solana account model (lamports, owner, data); who may debit vs credit an account; the SPL accounting fields | Thinking in *ledgers and writers* rather than functions; potential-function style invariants; the habit of asking "who else can write this?" | `D_T`, `D_S`, the divergence catalog (II.1, II.2, IV.1, IV.4); the realizable-value notion (II.3) |
| **I.2 Transient Automaton** | Native stake lifecycle (activation, deactivation, warm-up, MergeKind); PDA creation via Allocate/Assign; zero-lamport semantics | Composing state machines owned by different programs; parameterizing a model by a *version space*; exhaustive exploration | The automaton (III.3, III.4, IV.3); the direction lemma (III.4, IV.2); the coupling insight (IV.3) |
| **I.3 Whose Signature** | CPI signing with PDAs; Anchor `/// CHECK` semantics; SPL authority checks | Frame and non-interference arguments; separating *program* guarantees from *configuration* guarantees; event semantics | The configuration-vs-program partition (II.4); the binding-asymmetry lens (IV.4) |

**Checkpoint (self-test before Phase 2).**

* From memory, list every account that `UpdateStakePoolBalance` reads.
* Explain why `λ = E` is consistent with `T ≠ Θ*`.
* State, for each of the four version cells, what remains at a transient address after a merge and
  who can touch it.

If any answer is shaky, return to `PROTOCOL_MODEL.md` §3–§5 and §9.

### Phase 2 — Advanced protocol reasoning (Level II, 49–90 h)

Recommended order: II.1 → II.2 → II.3 → II.4. II.4 can run in parallel at any time after I.3.

| Challenge | Prerequisites | What it develops | Feeds |
|---|---|---|---|
| **II.1 Monotone NAV?** | I.1; integer floor/ceiling algebra | Integer-exact proofs; recognizing non-arithmetic state changes (cleanup, sysvar changes) as accounting events; property-based testing | III.1 (fee inequality), III.2, IV.4 |
| **II.2 Price of Freshness** | I.1; the instrument from Phase 0, step 1 | Precise profit notions (round trip vs mark-to-market vs timing); regime analysis; critically evaluating a test as *evidence in a regime* | IV.1(b), IV.4; the "bundling" question links to transaction limits |
| **II.3 Exit Topology** | I.2; the routing oracle | Reasoning about global predicates that couple validators; layered lower bounds from two programs; liveness classification | III.4, IV.2; the client-router discrepancy list is directly actionable |
| **II.4 Privilege Lattice** | I.3 | Privilege composition across programs with different time semantics; combinatorial games over authorization graphs | IV.2 (governance latency), IV.4 (R5) |

**Checkpoint.**

* Explain why the repository's `add_validator_donation` test passes in its environment and what
  would change on a cluster with a different minimum delegation.
* Characterize, without notes, which holders can redeem in a pool where every validator holds
  between `q + κ` and `q + 1 SOL`.

### Phase 3 — Olympiad-style depth (Level III, 75–145 h)

Recommended order: III.1 → III.2 (they share the integer fee machinery). III.3 can follow I.2
directly. III.4 needs II.3.

| Challenge | Prerequisites | What it develops | Feeds |
|---|---|---|---|
| **III.1 Fee Operator** | II.1; convexity and Jensen-type inequalities; Diophantine reasoning with nested floor/ceiling | Recognizing a protocol rule as an *operator* and studying its compositions and extremal partitions; exact characterization of rounding-null regions | III.2, IV.4 |
| **III.2 Inflation Calculus** | III.1; II.1; expected-value optimization over integer strategies | Adversarial optimization under integer constraints; tight bounds; turning a README claim into a theorem or counterexample | IV.4 (dead shares vs batching) |
| **III.3 Belief Soundness** | I.2; native stake sources (legacy and v5) | Treating program state as *beliefs about external accounts*; constructing attacks from lifecycle gaps between two programs; proofs that break when a single check is removed | IV.1 (fingerprints), IV.3 |
| **III.4 Controllability** | I.2, II.3; scheduling/control basics; stochastic races | Controllability under interference; correct accounting of value-preserving adversarial flows | IV.2 |

**Checkpoint.** You can explain a *mechanism*, not just a number, for each of these README
statements: why the epoch fee fails to deter manipulation at small supply; why the cost of
validator-targeted griefing is not "SOL plus rent"; and why "newer is safer" fails along one of the
two version axes in III.3.

### Phase 4 — Frontier (Level IV, 130–280 h)

Start with **IV.3** (the most concrete; it reuses your automaton), then **IV.1**, then **IV.2**,
and finish with **IV.4**, which integrates everything.

| Challenge | Prerequisites | Research character |
|---|---|---|
| **IV.3 Stuck Merges** | I.2, III.3, native merge table | Liveness theory for maintenance protocols; includes a prove-or-refute impossibility in its extension |
| **IV.1 Version Archaeology** | I.1, III.3, II.3 error surfaces; partitioned-reward runtime code | Behavioral fingerprinting with soundness proofs; temporal soundness of a guard against asynchronous credits |
| **IV.2 Colluding Validator** | III.4, II.3, II.4; vote-program commission rules (verify them yourself) | Multi-actor game with governance as a stopping time; the security budget implied by KYC |
| **IV.4 Batch-Settlement Redesign** | I.1, II.1, II.2, III.1, III.2, II.4 | Mechanism design with proofs; an open conjecture about the account-footprint lower bound for same-transaction fair minting |

---

## 5. Primary-source reading list, in order

1. **Staker program.** Read every file, in this order: `lib.rs`, `state/types.rs`,
   `instructions/staking.rs`, `validators.rs`, `setters.rs`, `whitelist.rs`,
   `third_party_whitelist.rs`. Note every `/// CHECK` and every `init_if_needed`.
2. **Repository evidence:**
   * `tests/add_validator_donation.test.ts`, `transient_poison.test.ts`,
     `ephemeral_poison.test.ts`, `withdrawals.test.ts`;
   * `scripts/update-pool.ts`, `withdraw-stake.ts`, `add-validator.ts`, `init-pool.ts`.

   Read the comments as *claims to test*.
3. **SPL Stake Pool 2.1.1** (crates.io source):
   * `state.rs`: the `calc_*` functions, `Fee::apply`, `FutureEpoch`, `StakeStatus` transitions;
   * `processor.rs`, in this order: DepositSol, WithdrawStake, UpdateVLB, UpdateSPB, Increase,
     Decrease, Add, Remove, Cleanup, SetFee, SetFundingAuthority, SetStaker;
   * `lib.rs`: the minimum functions.

   Then diff against 2.0.3 and 2.2.0 yourself, and read commit `0e56295` (2.0.4) *after* III.3(d).
4. **Native Stake program.**
   * BPF Stake v5.1.0: `processor.rs` (`process_split`, `process_merge`, `process_initialize`,
     `process_withdraw`, the EpochRewards gate) and `helpers/merge.rs`.
   * For contrast, Agave 2.0.15 `programs/stake/src/stake_state.rs`.
5. **Runtime.**
   * Agave `svm/src/account_loader.rs` (zero-lamport accounts across transactions);
   * `programs/system/src/system_processor.rs` (Allocate/Assign);
   * `runtime/src/bank/partitioned_epoch_rewards/`.
6. **SIMDs:** 0118 (partitioned rewards), 0490 (Stake v5, 1-SOL minimum delegation), 0437/0438
   (rent reduction and its safeguard), 0392 (relaxed rent checks), 0385/0160 (transaction limits).

---

## 6. Where original research is most likely

These directions emerged from the investigation. Each can grow beyond TruStake.

1. **Belief soundness for account-reading programs** (III.3 → its extension).
   * Programs like SPL Stake Pool store beliefs about accounts whose lifecycle they do not fully
     own.
   * A general theory would make "lifecycle ownership" and provenance first-class:
     * when is a cached field sound;
     * which runtime features (zero-lamport semantics, resize-on-drain) are load-bearing;
     * how soundness behaves across independently upgraded programs.
2. **Freshness versus reconciliation** (I.1, II.2, IV.1, IV.4).
   * Most LSTs gate on "updated this epoch" and price at a recorded ratio.
   * A formal account of the gap between those two notions — its writers, its sign, and its
     bounds — and of the minimal on-chain information needed to close it would apply to every
     epoch-based LST.
3. **Regime-indexed security claims** (L0, J2, J4, II.3).
   * TruStake's documented safety arguments were calibrated to cluster parameters that changed
     beneath an unchanged program.
   * A methodology that states every economic or liveness claim as a function of
     `(program versions, cluster parameters)` would be valuable. So would continuous tests that
     re-evaluate claims when a feature gate activates.
4. **The fee operator** (III.1 → its extension).
   * The extremal-partition result and the rounding-null region are protocol-independent
     statements about "fee on positive deltas since the last permissionless call".
   * They apply to any vault with a permissionless harvest function.
5. **Maintenance liveness** (IV.3 → its extension).
   * The prove-or-refute question about simultaneous freshness and prompt merging is a clean,
     general problem about maintenance protocols that depend on external state transitions.

---

## 7. Verification priorities and responsible conduct

Some items in this study may describe live behavior of a deployed protocol. The study could not
confirm any of them on-chain. Verify them on a **local validator in the correct cell** before
forming conclusions, in roughly this order:

1. `ASSUMPTION_LEDGER.md` G5 / Challenge II.3: redemption of sub-1-SOL positions, and the possible
   global freeze band under 2.1.x with a 1-SOL minimum delegation.
2. G2 / IV.3: maintenance-transaction failure modes (transaction size beyond ~12 validators;
   merge-incompatible states).
3. L0 / J2 / IV.1(a): which SPL version and which cluster regime are actually live.
4. A1 / C1 / II.2: the size of the owner-donation window in the current regime.

**Never test against the live pool or mainnet accounts.** If a finding holds on a faithful local
reproduction and plausibly affects the deployed system, follow the program's `security.txt` policy
(`lib.rs:15-23`: Immunefi program; contact `security@trufinlabs.com`) rather than publishing.

---

## 8. Known limitations of this study (carry these forward)

* No validator execution: the toolchain and mainnet RPC were unreachable. Economic claims were
  checked with an exact-integer re-implementation of the upstream arithmetic, which reproduces the
  repository's donation test.
* The deployed SPL version is inferred (most likely 2.1.0), not verified.
* Mainnet feature activations (1-SOL minimum delegation, rent reduction) are dated from Agave's
  feature-tracker history and news reports, not from on-chain feature accounts.
* Upstream and native-program facts were gathered partly by research subagents. The key ones were
  re-checked in source for this study:
  * the 2.1.1 UpdateVLB transient guard and EpochRewards guard;
  * 2.1.1 WithdrawStake routing;
  * the v5 Split minimum-delegation rule.

  Agreement between subagents is not independent proof. Where only one source supports a claim,
  the ledger says so through its confidence field.
