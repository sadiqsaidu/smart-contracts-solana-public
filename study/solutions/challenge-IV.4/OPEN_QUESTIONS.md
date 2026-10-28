# IV.4 — Open questions, unproved claims, dependencies, limitations

## Unproved or conditional claims

| # | Claim | Current status | What would settle it |
|---|---|---|---|
| Q1 | D5: in the v5 cell, a correct complete `no_merge` observation succeeds on every reachable state outside the payout (needed for R3, `k = 1`) | I.1 source argument only. Executed only on legacy Stake (agave 2.0.15). | A validator with BPF Stake v5.1.0 (e.g. a newer `solana-test-validator`), plus a reachable-state fuzz of VLB(no_merge) |
| Q2 | H_M: the incumbents' net price does not fall between a deposit and its settlement (in cell). Needed for escrow-mint, the conditional counterexample to the literal conjecture. | Model: no shortfall in 400 runs. Proof sketch only. Fails under a rent increase. | A proof of monotone NAV for all in-cell writers (Challenge II.1 territory) |
| Q3 | Magnitude of the uncredited-yield leak (A3: Jito tips credited after settlement) | Unmeasured | Mainnet data on tip-claim timing for TruStake's validators, read-only |
| Q4 | Compute of `settle` with `n = 22` sweeps under **Stake v5 (BPF)** | Legacy builtin measured in E4; BPF Stake is costlier | Measure on a v5 validator; if it exceeds 1.4 M CU, `N_MAX` falls |
| Q5 | Account-lock limit on current mainnet (`solana-core 4.3.2`) | Feature `9LZd…` is not activated (read-only), so 64 under the Agave 2.0.15 rule. The local limit was measured at 128 (feature active). | Confirm the 4.3.2 rule in source; at 128, `N_MAX = 54` |
| Q6 | R-1/R-2 (locality and commutation) as runtime facts | Taken from runtime semantics; not proved from Agave source here | Cite and verify Agave's transaction loader and scheduler; watch for syscalls that expose account state |
| Q7 | The proofs are by hand | Not machine-checked | Lean/Coq formalization of J6 → R2 and of Theorem A |
| Q8 | No Anchor prototype exists | `anchor`/`cargo` unavailable; SPL-level semantics executed via client-composed transactions | Build `trustake_batch` and re-run E1–E4 through real CPIs, including CPI depth and account-info limits |

## Dependencies on other challenges

* **I.1** (verified or executed in the I.1 session, `../challenge-I.1/VERIFICATION.md`):
  * D1, the wrong-pair skip (validator-executed);
  * D2, credit → `Θ*` (validator-executed);
  * D3, DepositSol arithmetic (validator-executed);
  * D4, idempotence (proved here, executed in E1);
  * D5, definedness in v5 (source only);
  * `D_T, D_S ≥ 0` (needed only for A2 and H_M, not for R2).
* **II.1** (monotone NAV): H_M.
* **II.3** (exit constraints): A11 assumes the existing analysis and adds no new exit path.
* **IV.3** (stuck merges): TBS uses `no_merge = true`, so merge failures cannot block
  settlement. The bot's merging maintenance is still needed for the pool's own health.

## Design-level limitations and costs

1. **Latency.** SOL is idle for up to about one epoch (about 2 days) before conversion.
2. **Lost feature.** `deposit_to_specific_validator` is removed: it is an immediate-mint path, and
   its seed changes would be a non-governance griefing vector. Re-adding validator preference as
   ticket metadata acted on by the stake manager is possible but not designed here.
3. **Immutability.** R5 requires the custody program to be immutable, or timelocked with a claim
   and cancel window, so bugs cannot be hot-fixed.
4. **Pinned pool.** A pool migration needs a new `trustake_batch` deployment.
5. **Cell dependence of liveness.** In the legacy-Stake cell, a cluster rent decrease can block
   settlement indefinitely (`k = ∞`). Funds remain cancellable.
6. **`n ≤ 22`.** The validator set is capped for strict R2 (64 locks). Theorem A shows this is
   inherent up to constants, not a TBS artefact.
7. **Policy choice.** Policy B (refund on loss of whitelist before settlement) relies on a hook in
   the upgradeable Staker. If the hook fails, the result is a policy breach, not a loss. Policy A
   needs no hook but converts a blacklisted user's pending deposit.
8. **Settler incentives.** There is no reward. Liveness relies on depositors or a bot paying
   fees (L4).

## Research directions (deeper extension, not attempted beyond notes)

* **Asynchronous mint–redeem calculus.** Theorem A is the information lower bound for
  *credited* value. Uncredited yield (A3) needs a separate latency lower bound: a program cannot
  price yield before it is credited, so fair entry requires waiting until the yield source's
  crediting horizon.
* **Comparison with redemption-queue LST designs** using this formalism (entry transaction,
  observation footprint, crediting horizon): not done.
