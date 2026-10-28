# Limitations, open questions and blocked verification

## Not verified

| # | Item | Why | Effect on conclusions |
|---|---|---|---|
| U1 | Identity of the 1030 / 1026 / 1046 reserve donors (`7ZiofVpt…`, `F6XMHN2y…`, nonce authority `EbsUZEFA…`) | No on-chain link to the TruStake authorities. Off-chain attribution is out of scope. | Decides whether candidate X's trigger is privileged (TruFin treasury) or a third party, and so its classification under the program's privileged-address exclusion |
| U2 | Deployed Tip Router binary vs `jito-tip-router` master | Not dumped or diffed | Only whether *anyone* can time a claim. J's economics are negative either way. |
| U3 | Jito merkle-root upload timing | Upload transactions not fetched | Claims are the first observed credit. An earlier upload would let anyone claim before maintenance (S1, which removes the lag). |
| U4 | Byte-identity of the deployed Staker with repository source | Mainnet hash `5500ff7f…` matches no local build | Mitigated: the deployed binary was cloned and executed locally, and its mainnet behaviour (no in-deposit reconciliation) is confirmed by the exact 1063 replay |
| U5 | Exact per-validator state at 1030 | Removed validators were not tracked; no historical snapshots | X's routing is shown against an upper bound, not an exact per-validator plan |
| U6 | `(T,S)` before 1063 | Reconstruction only. 1030 is pinned to an interval by three public integers; 1031–1062 was not replayed. | X's numbers carry a ±7k-lamport `T` uncertainty, which is immaterial |
| U7 | Stake v5 *execution* of the full round trip | Only a legacy local validator is available. Mainnet v5 evidence is simulation of maintenance plus replay of historical deposit and withdraw arithmetic. | The local run is **not** a Stake v5 reproduction. The v5-specific facts used (sweep, current-Rent floor, 1-SOL split minimum) come from mainnet simulation, chain history and v5.1.0 source. |
| U8 | Full Immunefi impact list | The fetch showed 12 of the "14" impacts | Severity mapping might change if a closer impact exists |
| U9 | Downstream oracle consumers (`HFn8GnPA…`, believed Kamino Scope) | Out of scope | A 22% under-statement for ~3.4 h in 1030 was not evaluated for lending-market effects |
| U10 | Secondary-market (Raydium CLMM) depth | Not measured | Only matters for exits outside WithdrawStake |
| U11 | Native reward behaviour under 4.3.2 features (e.g. block-revenue sharing) | Not inspected | Empirically irrelevant: per-epoch `T` growth reconciles exactly with `getInflationReward` + Jito claims (REVENUE_PROVENANCE §3) |

## Tests

* **Run and passed:**
  * `model/run_checks.py`: 54/54;
  * `model/window_1030.py`: 2,518 consistent solutions;
  * the mainnet simulation;
  * the exact history replay;
  * the local harness: run 4 PASS, 19/19, and the cross-check found 0 mismatches. Runs 1–2 were
    invalidated (killed shell; port collision). Run 3 failed on a single-split exit, which exposed the
    routing constraint (EXPERIMENTS §3).
* **Could not be run:**
  * a Stake v5 local validator;
  * a real Jito claim locally. The credit was a System transfer of the same lamport effect. A clone of
    the tip-distribution program with a self-built merkle tree was judged low value, because the pool
    observes only lamports.
* **Never tested:**
  * the Staker `deposit_to_specific_validator` path in the window (its DepositSol leg has identical
    pricing, per the mainnet 1063 replay);
  * pause and blacklist interactions;
  * WithdrawStake from a transient source.

## Open questions

1. Are external reserve top-ups a TruFin practice (for example a "boost" or a treasury rebalance)? If so,
   do they recur? Only one large one was found in 51 epochs.
2. Did the known add-validator report lead to a fix outside this repository (for example
   bot-side bundling)? The source still does not bundle SPB into `add_validator`.
3. Would TruFin accept running a VLB+SPB after the Jito claim burst (≈ slot index 50k) as a bot
   change? It costs one transaction per epoch.
