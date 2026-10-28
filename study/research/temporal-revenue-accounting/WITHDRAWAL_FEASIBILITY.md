# Withdrawal feasibility

## 1. Routes that exist on the deployed pool

| Route | Status | Evidence |
|---|---|---|
| `WithdrawSol` (SPL) | **Unreachable.** `sol_withdraw_authority = Gq5an4…`, the pool's own withdraw PDA. SPL requires that authority to sign (error 0x22 when another key is supplied), and only SPL could sign for its PDA. | Chain (`pool_state.json`); Local control "WithdrawSol by a token holder" failed with `Provided sol withdraw authority does not match the program's` |
| Staker SOL withdraw | Does not exist (no such instruction in `lib.rs`) | Src |
| `WithdrawStake` from a validator stake `V_i` | **Available** to any holder; no whitelist check | Src (processor.rs:2800-3140); Chain (1063 tx `2srEWZq8…`); Local |
| `WithdrawStake` from the reserve | Only when no Active validator has `A_i > ρ + m + ⌈T/S⌉`. The reserve must keep ≥ ρ. | Src processor.rs:2898-2938 |
| `WithdrawStake` from a transient | Only if no validator has active stake above the tolerance | Src |
| `ValidatorRemoval` source | Only when no Active entry exceeds the tolerance; takes the whole account | Src (ASSUMPTION_LEDGER C3) |
| Secondary market (Raydium CLMM, via the vault transaction of 1032) | Exists [Chain: `IncreaseLiquidityV2` to `CAMMCzo5…`]; depth not measured | Chain |

## 2. Constraints that bind a window depositor

1. **Freshness.** WithdrawStake reverts while `λ < E` (0x11). This held locally ("WithdrawStake
   while stale") and holds per source on mainnet. A depositor who enters in epoch `E` can exit in `E`
   (before the credit is recorded, which forfeits the gain) or in `E+1` after its first SPB.
2. **Per-split bounds.**
   * The source must keep `ρ + m` (`StakeLamportsNotEqualToMinimum`, 0x17).
   * The Stake v5 Split destination must reach `m` = 1 SOL on mainnet.
   * The user prefunds the destination with ρ (1,666,240 on mainnet, 2,282,880 locally), which is
     refunded at final withdrawal.
   * So one exit transaction pays at most `v_i − ρ − m` from validator `i`, and at least about `m`.
   * Locally, a single 40.26 SOL WithdrawStake from a 26.01 SOL validator failed with exactly
     `Attempting to withdraw 40257335167 lamports from validator account with 26012359492 stake
     lamports, 1002282880 must remain` (first harness run; `EXPERIMENTS.md` §3).
3. **Routing.**
   * A large redemption needs several WithdrawStake transactions, over validators first.
   * Live pool: the spare is ≈ 13.1 + 24.5 + 14.2 + 14.3 − 4 × 1.0017 ≈ 62.1 SOL. The reserve opens
     only after every validator is at its floor.
   * Model `exit_all`: 100 SOL and 1,000 SOL redemptions need 5 WithdrawStakes; ≤ 10 SOL needs 1.
4. **Fee.**
   * `ceil(p/1000)` pool tokens are transferred to the manager fee account. The withdrawal fee is a
     transfer, not a burn, so it raises no other holder's price.
   * The fee account itself is exempt (processor.rs:2861).
5. **Cooldown.**
   * A validator-sourced stake account is delegated. Deactivate, wait one epoch, then withdraw.
   * A reserve-sourced account is Initialized and can be withdrawn immediately.
   * During cooldown the account earns its own stake rewards for the deactivation epoch. That is the
     owner's yield, not pool value.
6. **Rounding.**
   * `ℓ = floor(b·T/S)` loses less than 1 lamport.
   * The deposit floor loses less than 1 token (≈ 4.03 lamports).
   * These are negligible against the 0.1% fee.
7. **Lockup / authorities.** Pool lockup is zero. The destination authorities are set to the user by
   the split's `Authorize` CPIs (1063 tx logs: `Split`, `Authorize`, `Authorize`).
8. **Later maintenance does not claw back.** Recording only raises `T`. No transition reverses a
   depositor's tokens (STATE_MODEL L9).
9. **Pool changes after entry.** A stake-manager rebalance between entry and exit changes only *which*
   source pays. Total redeemable value is fixed by `T,S`. If the stake manager moved every lamport
   into transients at once, exit would be limited to the transient route until the next merge (a
   delay, not a loss).

## 3. Executed or verified

| Case | Result |
|---|---|
| Mainnet 1063: WithdrawStake 993,739,463 tokens from V0 | paid 3,995,999,997 = `floor(992,745,723 · T/S)` with the replayed `T,S` (exact) |
| Local: window depositor full redemption (routed) | see `EXPERIMENTS.md` §3 |
| Model: `exit_all` for 1.005, 10, 100 and 1,000 SOL on the live pool | full redemption in 1, 1, 5 and 5 transactions; 0 tokens left |
| 1030 reconstruction | redemption ≤ `T + a + L − 5(ρ+m) − ρ` for every tested `L` (routing upper bound; the per-validator split of 1030 was not reconstructed) |

## 4. Conclusion

A window depositor's tokens **are redeemable** on the production configuration, with one constraint:
a minimum redemption of about 1 SOL from a validator. Redemption requires waiting for the next
epoch's first SPB, plus one cooldown epoch for validator-sourced stake.

* For the **Jito** case, the redemption fee alone exceeds the gain by 3–6 orders of magnitude, so
  there is **no profitable executable withdrawal**. The gain is MTM-only and returned at exit (L8).
* For the **1030 reserve top-up** case, a routed redemption would have realized a profit for any
  `L` ≥ 1 SOL. This is a reachable executable outcome under the reconstructed state, but it was not
  executed historically.
