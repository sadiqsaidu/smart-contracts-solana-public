# Hypothesis matrix

The criteria were fixed before evaluation. **Status:** Supported · Falsified · Conditional (holds only
under stated assumptions) · Unresolved.

There are two credit families. **J** is Jito tip claims, recurring (51/51 epochs) and tiny. **X** is
external reserve top-ups, occasional (5 in 51 epochs), one of them large.

| H | Statement | Falsification criterion | J: status and evidence | X: status and evidence |
|---|---|---|---|---|
| H0 | No material validator revenue reaches a counted pool asset after complete maintenance | Any credit to `R`, a listed `V_i` or a live `X_i` after the epoch's last SPB | **Falsified.** 178/178 claims landed in `V0/V1/V3` after the first SPB, never re-recorded in-epoch (C). Live `D_T` = 106,921 by mainnet simulation (Sim). | **Falsified** (not validator revenue, but a counted credit): 14.573 SOL at 1030:406,775 (C) |
| H1a | A post-maintenance credit cannot change a depositor's executable mint | `n_window ≠ n_honest` for some `L` | **Falsified.** +384 tokens at `L` = 1.005 SOL (M); local +456,491,268 tokens at `L` = 40 SOL, `z` = 0.78 SOL (L); 1063 mainnet deposit +304 tokens (C+M exact replay) | **Falsified** (M) |
| H1b | …nor produce a net positive transfer after all fees | Any `L` with realized round-trip P&L > 0 attributable to the delay | **Supported.** Realized P&L < 0 for every `L` from 1 to 1,000 SOL; breakeven needs a 678× larger credit (M) | **Falsified.** +0.26 to +10.8 SOL realized (M, reconstructed state) |
| H2 | A measurable recorded vs reconciled price gap exists | `Θ* − T > 0` while `λ = E` | **Supported.** `D_T/T` ≈ 1.1–5.6 × 10⁻⁶ (C, Sim) | **Supported.** `D_T/T` = 0.283 (C+M) |
| H3 | A window depositor captures value economically attributable to earlier holders | Delay-attributable MTM transfer that is material (≥ fees) | **Falsified as material**: ≤ 0.95·z ≈ 0.0001 SOL per epoch pool-wide; realized historical ≈ +1.2k lamports (C) | **Conditional-supported**: up to 13.84 SOL capturable; **no historical occurrence** (C) |
| H4 | The outcome requires privileged action or specific operational ordering | The credit or the window needs a non-attacker actor | **Supported**: Jito uploads and scheduling, and maintainers not re-running SPB (no profit anyway) | **Supported**: requires a third-party donation (sender unattributed; custodial durable-nonce pattern) **and** that no one runs SPB for 2.8 h |
| H5 | An actor with allowed capabilities realizes net gain without paying for the credit | Executable witness with P&L > 0, credit not funded by the actor | **Falsified** (M; L shows the mechanics but the fee dominates at mainnet magnitudes) | **Conditional**: holds for a whitelisted depositor *given* a third party's top-up. Not independently reproducible: the actor cannot create the credit without paying it (self-funded → loss, ECONOMIC §4) |
| H6 | Same root cause as known or accepted behaviour (the owner-funded validator-add window) | Find a mechanism not explained by "credit between SPB and price-sensitive op; freshness ≠ reconciliation" | **Supported.** Explained entirely by STATE_MODEL L1/L2. `ASSUMPTION_LEDGER.md` A1 already lists "a donation to the reserve, a donation to `V_i`". The README acknowledges anyone can credit the reserve and SPB folds it in. | **Supported** (same) |
| H7 | Native inflation is credited late | Any inflation credit observable at a price-sensitive op before recording | **Falsified.** The guard chain is L3 (S). Effective slots ≤ 648 are always before the first SPB (C, 14 epochs). | — |
| H8 | The manager's fee capture depends on recognition timing | Fee value differs between orders by more than rounding | **Falsified** (L6; M check) | **Falsified** |
| H9 | Mid-epoch re-reconciliation is blocked | VLB or SPB reverts after the first SPB | **Falsified.** Re-running is allowed: no skip of updated entries (P:1925-1946); I.1 N3; local `[VLB, SPB, deposit]`. Mitigation is available. | **Falsified** |
| H10 | External price consumers inherit the lag | A reader of `T/S` | **Supported**, at negligible size (`HFn8GnPA…` RefreshPriceList reads the pool) | **Supported.** In 1030 the feed under-stated TruSOL by 22% for ~3.4 h, then jumped. Downstream impact is unresolved and out of scope. |

## Net reading

* **Mechanism (H0, H2): established on mainnet.** Jito revenue is credited late, every epoch, to
  counted accounts. External top-ups are also recorded late.
* **Economics (H1b, H3, H5) for Jito: negative**, with a three-orders-of-magnitude margin.
* **Economics for top-ups: positive conditional on a third-party donation**, and identical in root
  cause to the known add-validator report (H6).
