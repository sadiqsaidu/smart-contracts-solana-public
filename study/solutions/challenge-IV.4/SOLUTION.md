# Challenge IV.4 — Batch-Settlement Redesign: solution

Repository `17886b4027ace3b098e72b69cb42307409b1d6a5`. Cell mainnet-2026 (SPL 2.1.x, Stake v5,
`m = 10^9`, `ρ = 1,666,240`; `e = 5/100`, `w = 1/1000`, `d = 0`).

This is an independent first pass: the hints and the assumption ledger were not read before all
seven files were saved. A separate review pass appears at the end of this file.

**Evidence labels.** [Proved] by hand · [Src] source · [Model] exact-integer model ·
[Validator] local validator · [Hypothesis].

## Answer in brief

* **(a) Mechanism.** TBS is specified in `SPECIFICATION.md` and is implementable on the current
  deployment.
  * A new **immutable** custody program `trustake_batch` queues SOL per epoch.
  * A permissionless `settle(e)` instruction performs, in one instruction,
    `UpdateValidatorListBalance(every entry, program-verified pairs, no_merge=true) →
    UpdateStakePoolBalance → DepositSol(batch)`.
  * TruSOL is then claimed pro rata (`⌊L·N/B⌋`), and dust is burned.
  * The Staker keeps permissions only, and its status instructions gain an eviction hook. Both
    immediate-mint instructions are removed. The SPL manager re-points `sol_deposit_authority`
    once. SPL itself is unchanged.
* **(b) R1–R5.**

| Req. | Verdict | Bound / condition |
|---|---|---|
| R1 | **Holds** [Proved, Model] | `δ₁ = 0` for equal deposits. For any depositor, `c·P − L ∈ (−2P, 0]` (< 8.06 lamports at the live `P ≈ 4.03`). |
| R2 | **Holds** [Proved, Model, Validator E1], for `n ≤ N_MAX` | Per batch, the transfer to depositors is in `(−(m_b+1)·P, 0]`, never in their favor, and independent of every I.1 divergence. R2 is a safety property that needs no cell assumption once `settle` succeeds. |
| R2, literal "first maintenance" price | **Refuted** [Model, Validator E2] | 2 non-governance transactions; +3.50 SOL measured on the validator, +35.7 SOL in the model. |
| R3 | **Holds with `k = 1`** under L1–L7 [Proved, Model] | No non-governance actor can delay settlement past epoch `E+1`; the only non-governance delay is the reward payout. In the legacy cell, `k = ∞` via a cluster rent mismatch (funds stay cancellable). |
| R4 | **Policy B enforced** [Proved, Model] | A user losing whitelist status before settlement gets an exact refund. After settlement, they claim TruSOL. There is no freezing and no redirection. |
| R5 | **Holds iff `trustake_batch` is immutable** (or timelocked with a claim and cancel window) [Proved] | Custody inside the upgradeable Staker would be strictly new trust (Lemma NC). |

* **(c) Attacks.** See `ATTACK_ANALYSIS.md`, 18 classes.
  * The strongest attacks *on the alternatives* are A0 (literal spec, +35.7 SOL), the wrong-pair
    settler (validator: +2.68 SOL), and today's immediate deposit (+28.6 SOL; up to +147 SOL in
    randomized runs).
  * Against TBS itself, the main residual is **A3, uncredited yield**. Yield credited after
    settlement (e.g. Jito tips for epoch `E`) is shared with batch `E`. It is outside R2's I.1
    yardstick, and no latency choice removes it.
* **(d) Conjecture.**
  * **True** in its entry form (Theorem A): any design in which the depositor enters the pool in
    the deposit transaction must list every validator stake account in that transaction, so
    `Ω(n)` accounts. The bound is tight: "fresh" deposits use `2n + O(1)`.
  * **False** in its literal minting form, conditional on hypothesis H_M: escrow-mint mints in
    the deposit transaction with `O(1)` accounts and meets R2 per batch.
  * Theorem A also implies a hard ceiling: strict R2 is impossible for *any* TruStake-only design
    once `n` passes about 51 at 64 locks. VLB-based designs stop at 22.

## (a) Mechanism summary

* **Interpretation.** The price is that of the complete maintenance performed *inside* the
  settling instruction. This coincides with "first complete maintenance of `E+1`" when settlement
  is that maintenance. Proposition 0 proves the literal reading cannot satisfy R2.
* **State machines.**
  * Batch: `Open → Settled | Voided → closed`.
  * Ticket: `Pending → (cancel | evict → Refundable → refund) | claim`.
* **Custody.**
  * Queued lamports are held in a program-owned `Batch(e)`.
  * Minted TruSOL is held in `Vault(e)`, owned by `Batch(e)`.
  * Refunds go via the ticket account so a closing transfer is always rent-exempt.
  * DepositSol is funded from a System-owned `Funding` PDA that holds zero between transactions.
* **Pinned constants.** Pool, mint, and the SPL, Token and Stake programs. A permissionless
  settler routes other people's money, so the foreign-pool hole in today's Staker must be closed.
* **Guards.** `settle` checks:
  * `d ≤ 0`;
  * `T, S > 0`;
  * not paused;
  * coverage of every list entry by derived address (matched by key);
  * referral forced to the manager fee account;
  * `n = 0 ⇒ Voided` rather than a revert.

## (b) Key proof ideas

* **J6.** Inside `settle`, the observation is exactly I.1's definition of `Θ*`, with no possible
  interleaving and coverage enforced on-chain. By idempotence (D4), the mint sees `T = Θ*` and
  `S = Σ`.
* **R2.** DepositSol arithmetic then gives the exact identity
  `τ_b = (N·T₁ − B·S₁)/(S₁+N) ∈ (−P, 0]`. Every pre-settlement divergence is inside `T₁, S₁`,
  and depositors' lamports never touch the pool before that point.
* **R3.** Enumerate every revert branch of `settle` against its possible writers. The
  non-governance ones are the bounded payout window and cases impossible in the v5 cell (D5).
* **R4.** Induction over status writers, where the Staker is the sole owner of `UserStatus`.
  Batch write-lock serialization covers the settle/evict race.
* **R5.** Destination closure (J5) means queued value has no path to any TruFin key. The
  only TruFin-key effects are gating and refunding, which match today's "deposit refused".

## (c) Most important attacks

| Attack | Outcome |
|---|---|
| Donation or burn right before settlement | Captured by settle's own observation. Benefits incumbents and costs the donor. Model −0.07 lamports; E1 priced a same-transaction 20 SOL credit into the mint exactly. |
| Lowering the settlement price | Impossible for non-governance actors. Every in-epoch writer weakly raises `P_net`. |
| Griefing settlement | No non-governance revert branch. Seeds can only be changed by governance once `deposit_to_specific_validator` is gone. Cleanup is tolerated. Forced sweeps cost about 3.3k CU each (legacy). |
| Manager fees | Instant `d` increases turn into refusals (users cancel). Epoch fees hit only pre-entry rewards. |
| Transaction limits | `19 + 2n ≤ A_lock`. Mainnet's 128-lock feature is not activated, so `n ≤ 22`. The live pool has `n = 4`. |
| Uncredited yield (A3) | **Open economic leak.** Bounded by depositors' share of late-credited epoch-`E` yield. |

## (d) Conjecture

See `CONJECTURE.md`. The model of observability is locality plus commutation of transactions
with disjoint account sets.

* **Theorem A.** A credit `z` to an unlisted `V_j`, executed just before or just after the entry
  transaction, leaves identical final states. The fair allocations, however, differ by at least
  `L·S·(19z−20)/(20T(T+z))` tokens. This is checked exactly on 200,000 cases; at `z = T` it is
  48.7% of the fair allocation on the live pool.
* **Matching constructions.**
  * Fresh deposit: immediate entry, `2n + O(1)` accounts.
  * Escrow-mint: immediate mint, entry at settlement, `O(1)` per deposit, conditional on H_M.

## Verification (see `VERIFICATION.md`)

* **Model.**
  * Bounded search: 585 prefixes, no TBS violation; the flawed designs fail at length 2.
  * Randomized: 400 × 250-step runs per design with 0 violations for TBS, fresh and escrow-mint.
  * R1: 2,000 batches.
  * Theorem A inequality: 200,000 exact cases.
* **Validator.** E1–E4 on the cloned mainnet SPL binary with 23 validators, plus a lock-limit
  measurement (128 locally).

## What remains open (see `OPEN_QUESTIONS.md`)

* Stake v5 execution (D5, compute).
* H_M (monotone net price).
* The magnitude of the uncredited-yield leak.
* The mainnet 4.3.2 lock-limit rule.
* No Anchor prototype, and no machine-checked proofs.

## Files

`SPECIFICATION.md` · `PROOFS.md` · `ATTACK_ANALYSIS.md` · `CONJECTURE.md` · `VERIFICATION.md` ·
`OPEN_QUESTIONS.md` · `model/` (`batch_model.py`, `check_iv4.py`, `theorem_a_check.py`, results)
· `harness/` (`settle_semantics.ts`, `lock_limit.ts`, `run.sh`, `rpcread.py`, results).

## Review pass (after saving the independent solution)

**Read:** `CHALLENGES.md` → Hints → IV.4 (H1–H3); `ASSUMPTION_LEDGER.md` entries J1, J2, J3 (the
only entry that references IV.4) and G1; `RESEARCH_ROADMAP.md` lines naming IV.4.

| Source | Says | Agreement / correction |
|---|---|---|
| H1 | Decide what "the price" is and who observes it | Agrees: Proposition 0 and the settle-internal observation. |
| H2 | Treat settlement as one atomic event; attacks sit at the boundary between the last deposit and the settling update | Agrees: J6/R2. A0, A1, A3 and A5 are exactly those boundary attacks. |
| H3 | Count accounts needed to certify `T = Θ*` against the lock limit as `n` grows | Agrees: Theorem A and Corollary A4. |
| Ledger J1 | Staker does not bind to the canonical pool | Agrees: TBS pins pool and mint (A16). |
| Ledger J2 | A 2.1.0 binary self-reports `program@v2.0.3` | Agrees with the I.1 fingerprint used here. |
| Ledger J3 | An atomic fully-fresh deposit is impossible beyond ~24 validators at 64 locks | Agrees with `N_MAX = 22` (19 program-side fixed accounts vs ~14 client-side). |
| Ledger G1 | UpdateVLB reverts during payout (2.0.4+) | Agrees: the R3 payout delay. |
| Roadmap | IV.4 depends on III.2 ("dead shares vs batching") | **Omission found.** The independent pass did not analyse price inflation amplifying the P-denominated rounding bound. Added as **A19** in `ATTACK_ANALYSIS.md`; no verdict changes. |

**Corrections made during the independent pass, before this review (recorded, not hidden):**

1. The claim that E4 would show a 64/65-account boundary was wrong. The local validator's lock
   limit is 128 (measured), while mainnet's 128-lock feature is not activated. The text was
   rewritten and the hard `N_MAX` check removed from `settle` (`VERIFICATION.md` §4).
2. The Theorem A deposit threshold was first written with an algebra slip. It was corrected
   to `L > 80εT/(S(19 − 20/T))` before saving.
