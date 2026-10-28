# Progress

| Phase (mandate §) | Status | Output |
|---|---|---|
| 1 Environment: revision, background, code, binaries | done | HEAD `4f1d51a2a842273a4932378ab7d621da211e546a`, clean tree. SPL, Stake and Staker binaries dumped and hashed (MAINNET_OBSERVATIONS §1). |
| 2.1 Revenue provenance | done | REVENUE_PROVENANCE.md |
| 2.2 Mainnet state, history, timing | done (1020–1070) | MAINNET_OBSERVATIONS.md, `mainnet/` |
| 3 State model and transition system | done | STATE_MODEL.md, `model/temporal_model.py` |
| 4 Ordering and commutativity | done | TEMPORAL_ANALYSIS.md |
| 5 Hypotheses and evidence matrix | done | HYPOTHESIS_MATRIX.md |
| 6 Exact economics with counterfactuals | done | ECONOMIC_ANALYSIS.md, `model/results.json`, `model/window_1030_results.json` |
| 7 Reachability and actor models | done | REACHABILITY.md |
| 8 Withdrawal path | done (model + mainnet replay + local) | WITHDRAWAL_FEASIBILITY.md |
| 9 Verification (model, local validator) | done: model 54/54; local run 4 PASS 19/19 with 0 cross-check mismatches | EXPERIMENTS.md, `harness/` |
| 10 Adversarial review | done | ADVERSARIAL_REVIEW.md |
| 11 Reportability | done; nothing submitted | REPORTABILITY_ASSESSMENT.md |
| 12 Boundaries | respected: read-only mainnet, throwaway local keys, no production code modified, nothing pushed | — |
| 13–15 Deliverables | done | EXECUTIVE_SUMMARY.md, LIMITATIONS.md |

**Open questions:** see LIMITATIONS.md.

1. Donor identity (U1).
2. Status of the known add-validator report.
3. The deployed Tip Router version (U2).
