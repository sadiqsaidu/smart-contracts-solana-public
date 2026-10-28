# Executive summary: temporal recognition of validator revenue in TruStake

* **Basis:** repository `4f1d51a2a842273a4932378ab7d621da211e546a`, plus read-only mainnet data at
  epoch 1070 (2026-10-28) on `solana-core 4.3.2`.
* **Deployed programs:**
  * Stake v5.1.0, core BPF;
  * SPL Stake Pool binary `ec2dfefa…` (2.1.x processor);
  * Staker binary `5500ff7f…`.
* **Result type:** B+. A defensible negative result for Jito revenue, plus a conditional positive for
  one external-credit trigger that shares a known root cause.

## Answer to the research question

**Yes. Revenue reaches counted pool accounts later than the pool's reconciliation, every epoch.** The
consequences are negligible for the recurring revenue and material only for an occasional external
credit. That credit is a new trigger of an already-reported root cause.

1. **Native inflation: not late.**
   * It is credited at slot index ≤ 648 inside the reward window.
   * The guard chain is: VLB reverts while rewards are active; SPB needs every entry updated;
     DepositSol and WithdrawStake need `λ = E`.
   * So inflation is always recorded before any price-sensitive operation. [Source + 14 epochs of
     chain data]
2. **Jito MEV tips: late, always.**
   * There were 178 Tip Router `ClaimWithPayer` → tip-distribution `Claim` credits to TruStake
     validator stake accounts in epochs 1020–1070. **All 178 landed after that epoch's first
     UpdateStakePoolBalance** (median slot index 24,394 vs first SPB median 6,714).
   * None was recorded in-epoch; each waited for the next epoch's maintenance sweep.
   * A live mainnet simulation of `[VLB, SPB]` measured `Θ* − T` = **106,921** lamports, exactly the
     epoch's three claims. The 5% fee on it is 1,327 tokens.
   * Validator V2 takes 100% MEV commission, so the pool receives nothing from it.
3. **External reserve top-ups: late, occasional, once large.**
   * There were five durable-nonce System transfers to the reserve, from unattributed wallets.
   * One of them, **14.573 SOL at epoch 1030 slot index 406,775, was 28.3% of `T`**. `T` was
     reconstructed exactly to a 13k-lamport interval from three public integers.
   * It stayed unrecorded through the last 25,225 slots of the epoch.

## Does the timing change executable deposit pricing?

**Yes.**

* A Staker `deposit` in the window mints `floor(L·S/T)` against a `T` that excludes the credit.
* This was shown four ways:
  1. the source;
  2. an exact replay of the only mainnet in-window deposit (1063: +304 tokens vs an honest
     counterfactual);
  3. a local run of the **cloned production SPL and Staker binaries** (38,766,504,032 vs
     38,310,012,764 tokens);
  4. the model.
* Recording later does not reverse the extra mint; it only recognizes the credit.

## Can an ordinary actor exploit it?

| Actor | Jito late credit | Reserve top-up (1030-like) |
|---|---|---|
| Unwhitelisted outsider | No: cannot deposit (`UserNotWhitelisted`; direct DepositSol rejected) | No |
| Whitelisted depositor | **No profit.** The gain is ≤ 0.95·z (≤ ~0.0001 SOL per epoch). The 0.1% withdrawal fee exceeds it by 3–6 orders of magnitude, and breakeven needs a credit 678× larger. | **Yes, opportunistically.** It cannot create the credit (self-funding always loses) but can enter after a third party's credit. Hypothetical realized gain: +0.26 / +2.24 / +6.77 / +10.8 SOL for L = 1 / 10 / 50 / 200 SOL, capped at 13.84 SOL. **Did not happen historically.** |
| Holder, maintainer | Can close either window with one permissionless SPB (or VLB+SPB) | Same |

## Exact economics (selected)

* **Live pool, Jito.** `L` = 10 SOL: realized −9,026,977 lamports with the delay vs −9,040,311
  honest, so the delay contributes +13,334. `L` = 1,000 SOL: +95,185 from the delay, realized
  −992,228,867.
* **Historical realized effect of the Jito delay.** Once, in epoch 1063, and against the trader: about
  −3.6k lamports net (deposit +1,224, withdrawal −4,853).
* **Local production-binary round trip.** `z/T` = 1.25%, `L` = 40 SOL. The window gives +251,318,295
  vs −38,139,227 honest, so **+289,457,522 is attributable**. Redemption was routed over two
  validators, and every on-chain amount matched exact arithmetic (0 mismatches). This ran on
  **legacy Stake** (agave 2.0.15) and is not a Stake v5 reproduction. The v5 behaviour comes from
  the mainnet simulation and the history replay.

## Strongest counterarguments

* **Known root cause.** Same root cause as the Immunefi-reported owner `add_validator` window
  (repository test `tests/add_validator_donation.test.ts`). `study/ASSUMPTION_LEDGER.md` A1 already
  lists reserve and `V_i` donations.
* **Trigger is out of the attacker's hands.** X needs someone else's donation, possibly TruFin
  itself (unverified).
* **No historical loss.** Nobody traded in the large window.
* **Jito fails on economics.** It is unprofitable at any realistic MEV level.

## Classification

| Candidate | Class | Confidence |
|---|---|---|
| J: Jito late credit | **No exploitable issue established.** The delay is technically demonstrated on mainnet; the economic impact is negative. | High |
| X: external reserve top-up | **Duplicate or known behaviour** (root cause), with a new, larger operational trigger. Economically demonstrated on reconstructed public state; production reachability is conditional on a third-party donation. | Medium-high on the numbers; low on donor attribution |

Severity is not proposed as a new finding. If it were judged distinct, the closest listed impact would
be "Theft of unclaimed yield" (High). The mitigating factors are a known root cause, a non-attacker
trigger, zero realized loss, and a one-transaction operational fix.

**Worth a private operational note to TruFin:** reconcile (SPB, or VLB+SPB) after any reserve or
validator credit, including the daily Jito claim burst, and bundle SPB with any treasury top-up.

## Artifacts

All under `study/research/temporal-revenue-accounting/`:

* **Reports:** REVENUE_PROVENANCE, MAINNET_OBSERVATIONS, STATE_MODEL, TEMPORAL_ANALYSIS,
  HYPOTHESIS_MATRIX, ECONOMIC_ANALYSIS, REACHABILITY, WITHDRAWAL_FEASIBILITY, EXPERIMENTS,
  ADVERSARIAL_REVIEW, REPORTABILITY_ASSESSMENT, LIMITATIONS and PROGRESS (`.md`).
* **Directories:** `mainnet/` (read-only scripts and raw data), `model/` (exact-integer model, checks,
  1030 reconstruction), `harness/` (local production-binary round trip and cross-check).
