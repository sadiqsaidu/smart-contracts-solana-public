# Reportability assessment

**Nothing was submitted to Immunefi.** This assessment was written only after the technical and
economic results in the other files.

## 1. Current program terms (read 2026-10-28)

* **Page and date.** `https://immunefi.com/bug-bounty/trufin/scope/`, last updated **08 October 2026**.
  The page uses the name "TruYields".
* **In-scope assets:**
  * the Solana staker and whitelist contracts `6EZAJ…` (listed with the *devnet* cluster);
  * the GitHub repository `TruFin-io/smart-contracts-solana-public` (added 25 June 2026).
* **Impacts:**
  * Critical: "Direct theft of any user funds… other than unclaimed yield", permanent freezing,
    insolvency;
  * High: "**Theft of unclaimed yield**", permanent freezing of unclaimed yield, temporary freezing;
  * Medium: griefing, block stuffing, inability to operate.
* **Exclusions relevant here:**
  * attacks requiring privileged addresses;
  * bugs in external libraries;
  * centralization risks;
  * "lack of liquidity impacts".
* **Not addressed by the page:** known issues and stale share price.
* **Unverified.** The page summary came from a fetch tool, and the full impact list ("14 impacts") was
  only partly visible.

## 2. Candidates

### J — late-credited Jito tips (recurring)

| Criterion | Finding |
|---|---|
| Affected component | SPL Stake Pool pricing (`DepositSol` and `WithdrawStake` read the recorded `T`), reached through the Staker `deposit` CPI |
| Root cause | Recording requires a separate permissionless VLB+SPB, while freshness is per epoch. Jito claims land after the epoch's maintenance. |
| Minimum privilege | Whitelisted depositor |
| Third-party dependence | Jito root upload and claiming |
| Repeatable? | Every epoch, but with a negative expected value |
| Maximum value exposed | ≤ 0.95·z per epoch (z ≤ 369,656 observed) ≈ **0.00035 SOL** |
| Realized loss | ≈ 1.2k lamports, once (1063), against the trader |
| Exposure duration | ~1 epoch per credit |
| Permissionless mitigation | VLB+SPB after the claims (≈ 75k CU) |
| Distinct from known? | No; another trigger of the ledger-A1 root cause |
| **Classification** | **No exploitable issue established** (technically demonstrated; economically negative by ≥ 678×) |

### X — external reserve top-up window (occasional)

| Criterion | Finding |
|---|---|
| Affected component | Same as J. The credit is to the reserve, so SPB alone records it. |
| Root cause | Identical to J and to the known add-validator report: a credit between SPB and a price-sensitive operation within a fresh epoch. The Staker `deposit` does not reconcile, and SPL `DepositSol` cannot. |
| Minimum attacker privilege | Whitelisted (KYC'd) depositor |
| Trigger | A third party's direct transfer to the reserve. The 1030 sender is unattributed (custodial durable-nonce wallets); it is possibly TruFin itself, which would make the trigger a privileged operational action. |
| Repeatable? | Opportunistic only. The attacker cannot create the credit without paying for it (self-funded → loss). One large instance in 51 epochs. |
| Maximum value exposed (observed instance) | 0.95 × 14.573 ≈ **13.84 SOL**. Realizable gains, all tested `L` routing-feasible: 2.24 SOL at `L` = 10 SOL; 6.77 SOL at 50; 10.8 SOL at 200 (reconstructed state, model). |
| Realized loss | **0.** Nobody deposited in the window. |
| Principal / yield split | No principal: no holder's previously recorded share is reduced. The loss is of credited-but-unrecognised value, a donation or yield intended for holders. The 5% manager fee is unaffected. |
| Victims | Holders at recording. The manager fee account holds 78% today. |
| Exposure duration | Credit → next epoch's first SPB. In 1030 the deposit window was 25,225 slots (~2.8 h). |
| Permissionless mitigation | Anyone can run SPB in one transaction. Operationally, a donor can bundle `[transfer, SPB]`. Structurally, the Staker `deposit` could prepend a full VLB+SPB, but at `n = 4` that costs 2n+O(1) accounts (IV.4 Theorem A). |
| Publicly acknowledged? | README "Fees" section (reserve donations are folded in by SPB; argued unprofitable *for the donor*). `ASSUMPTION_LEDGER.md` A1 names reserve and `V_i` donations as invalidating "a fresh pool prices correctly". The repository test validates an Immunefi report on the owner-add window. |
| Overlap with the add-validator report | Same root cause and same victims/beneficiary structure. The trigger differs (external top-up vs `add_validator`). It is larger (28% of `T` vs `q` ≈ 1.0017 SOL ≈ 1.5% of `T`). A fix confined to `add_validator` would not cover it. |
| **Classification** | **Duplicate or known behaviour** (root cause), with a **new operational trigger**. Economically demonstrated on reconstructed public state; **production reachability is conditional** on a third-party donation, which is not attacker-controllable. |

## 3. Severity (conservative)

* **J:** none. Below any impact threshold and unprofitable.
* **X:** if TruFin treated it as distinct from the known report, the closest listed impact is
  **"Theft of unclaimed yield" (High)**. I would not propose that severity, for these reasons:
  1. The root cause is already reported and documented (ledger A1; repository test).
  2. The trigger depends on a third party, possibly a privileged one, and the program excludes
     privileged-address requirements.
  3. It cannot be produced on demand.
  4. Zero realized loss.
  5. The fix is an operational practice (bundle SPB with any top-up, or run SPB promptly after
     credits).
* A defensible framing is **informational or operational**: "external reserve top-ups recreate the
  known add-validator pricing window at ~15× its size (14.573 SOL vs `q` ≈ 1.0017 SOL); the maintenance bot should reconcile after any
  reserve or `V_i` credit and after Jito claims."
* **Confidence:** high for the technical facts (mainnet simulation, exact replays); medium-high for
  the 1030 reconstruction; low on the donor's identity and therefore on the privilege
  classification.

**Evidence still needed** before any private report:

* the donor identity, and whether such top-ups are routine;
* the status and scope of the known add-validator report and its fix;
* a per-validator reconstruction of 1030 for exact routing;
* confirmation that the deployed Tip Router matches master (relevant only to J's timing).

## 4. Does anything warrant further private review?

Yes, operationally rather than as a bounty item. TruFin should know three things:

1. A 14.573 SOL reserve credit left a ~28% recorded-price gap open for ~2.8 hours of deposit
   window.
2. Jito claims are always recorded one epoch late.
3. Their maintenance bots never reconcile after credits, although a single permissionless SPB
   (reserve) or VLB+SPB (validator credit) closes the window.

That is a reasonable item for a private note under the existing known-issue thread. It is not a new
critical or high finding.
