# Experiments

Every result below states what actually ran. "Model" means Python only; it is not validator
execution.

## 1. Mainnet read-only (public chain)

Node `v22.14.0` (`/tmp/trusol-redemption-tools/node-v22.14.0-linux-x64`), `@solana/web3.js` and
`@solana/spl-stake-pool` 1.1.8 from the repository's `node_modules`, Python 3.12.3.

| ID | Command (from repo root unless noted) | Exit | Output | Result |
|---|---|---|---|---|
| M1 | `NODE_PATH=$PWD/node_modules node study/research/temporal-revenue-accounting/mainnet/pool_state.js > …/pool_state.json` | 0 | `pool_state.json` | live pool, list and PDAs; three `V_i` with post-maintenance excess |
| M2 | `… fetch_history.js 1060 > history.json` and `… fetch_history.js 1020 > history_long.json` | 0 | 112 / 555 txs | maintenance, claims, user ops |
| M3 | `… claim_detail.js <sig> 1069` | 0 | `claim_detail_1070.json` | claim structure, TDA commission bps |
| M4 | `… simulate_theta.js` (sigVerify off, no signature) | 0 | `simulate_theta.json` | **`D_T` = 106,921 on Stake v5 / core 4.3.2; fee 1,327 tokens** |
| M5 | `python3 -I inflation_rewards.py pool_state.json 1059 1069` (in `mainnet/`), and `1029 1031` | 0 | `inflation_rewards.json`, `inflation_1029_1031.json` | effective slot index ≤ 648 |
| M6 | `python3 -I claim_timing.py > claim_timing.json` (in `mainnet/`) | 0 | `claim_timing.json` | 178/178 claims after the first SPB |
| M7 | `python3 -I pool_refs.py 25` | 0 | `pool_refs.json` | 25/25 oracle `RefreshPriceList` |
| M8 | inline scripts → `window_txs_1063.json`, `reserve_donations.json`, `window_1030_1032.json`, `donor_provenance.json`; `getProgramAccounts` → `token_holders.json` | 0 | — | exact 1063 amounts; 5 reserve top-ups; 1031/1032 fee mints; holder distribution |
| M9 | `solana program dump -um <id>` for SPoo1…, 6EZAJ…, Stake111… | 0 | scratchpad | sha256 `ec2dfefa…`, `5500ff7f…`, `3d2d39c5…` |

Rate-limit retries (HTTP 429) are logged in `mainnet/history*.stderr`. `getTokenLargestAccounts` was
refused by rate limiting; `getProgramAccounts` was used instead.

## 2. Exact-integer model

| ID | Command (in `model/`) | Exit | Result |
|---|---|---|---|
| P1 | `python3 -I run_checks.py > results.json` | 0 | **PASS, 54/54 checks.** Includes the exact mainnet history replay 1063→1070. It reproduces `T`, `S`, both `last_epoch_*`, the 1063 deposit mint 249,676,722 and the withdraw payout 3,995,999,997 **exactly**. |
| P2 | `python3 -I window_1030.py > window_1030_results.json` | 0 | 2,518 `(T,S)` solutions reproduce three public integers. `a/T` = 0.2828. Hypothetical window P&L +0.26 to +10.8 SOL. |

The check list in `model/results.json` covers:

* zero credit;
* credits before and after maintenance;
* counted validator, reserve, and unobserved account;
* partial updates;
* deposit before vs after the claim;
* L = 10⁶ to 10¹³;
* burn before the fee;
* rounding boundaries (unchanged / −1 / bounded);
* manager-fee value invariance;
* `T` commutativity, and `S` non-commutativity;
* withdrawal constraints and the fee exemption;
* epoch guards;
* mainnet-parameter round trips (all losses), breakeven, self-funded donations (all losses).

**Controls** show where the effect disappears: honest re-reconciliation (`D_T` → 0, mint = honest),
a credit to an unobserved account, and the reward-window guards.

The model does not encode signer classes. Authority is evidenced by the local controls (§3) and by
source (`REACHABILITY.md`).

## 3. Local validator: production SPL and Staker binaries

* **Command:**

  ```
  export PATH=/tmp/trusol-redemption-tools/node-v22.14.0-linux-x64/bin:$PATH
  SOLANA_BIN=/tmp/trusol-redemption-tools/solana-release/bin LEDGER_DIR=<scratch> \
    study/research/temporal-revenue-accounting/harness/run.sh > …/harness/results.json
  python3 -I study/research/temporal-revenue-accounting/harness/compare_local.py …/harness/results.json
  ```

* **Environment:** `solana-test-validator 2.0.15 (src:f8f3fe31; feat:607245837)` with the **legacy
  builtin Stake program**. Stake rent 2,282,880; minimum delegation 10⁹ (measured); 400 slots per
  epoch; RPC port 28899 (isolated).
* **Programs cloned from mainnet**, with hashes of the local dumps (run-stderr.txt):
  * SPL Stake Pool `ec2dfefaa70d560754a0000f39bd2cabc192b895d36205b3c428f601b6e1d7e1`, equal to mainnet;
  * TruStake Staker `5500ff7f90fcb90a76def41953f2d43e2613a494a85dc261843d8a8573cbb7d0`, equal to mainnet.
* **Configuration matching mainnet:** deposit authorities = Staker deposit PDA; SOL withdraw authority
  = the pool's withdraw PDA; fees 5/100 epoch, 1/1000 withdrawal, deposit 0. The Staker was
  initialised locally (owner = agent, throwaway keys); the depositors were whitelisted through
  `add_user_to_whitelist`.
* **Deviations** (recorded in `results.json`):
  * pool `staker` = a local key;
  * the late credit is a System transfer, which has the same lamport effect as a Jito claim;
  * legacy Stake;
  * local rent and epoch length.

### Runs

| Run | Status | Notes |
|---|---|---|
| 1 | **invalid** | A nested background `&` was killed with its parent shell. No output. |
| 2 | **invalid** | Port collision with a stale validator from run 1 (`Faucet failed to start: Address already in use`). Partial output was discarded. |
| 3 | **failed (informative)** | All window steps passed. The single 40.26 SOL WithdrawStake from a 26.01 SOL validator was rejected: `Attempting to withdraw 40257335167 lamports from validator account with 26012359492 stake lamports, 1002282880 must remain` (0x17). This shows the routing constraint. |
| 4 | **PASS, 19/19 checks, exit 0** | Routed redemption V0 then V1 (`harness/results.json`). Independent Python cross-check: **0 mismatches** (`harness/compare_results.json`). |

### Run 4 measurements

All rows are epoch 2 (`X`) except where stated.

| Step | `T` | `S` | `D_T` | Notes |
|---|---:|---:|---:|---|
| after complete maintenance (no-role cranker) | 62,009,604,067 | 60,097,389,153 | 0 | `λ = E` |
| after late credit `z` = 777,777,777 to V0 | same | same | **777,777,777** | still fresh |
| after a 123,456,789 credit to an unobserved vote account | same | same | 777,777,777 | control |
| after window deposit `L` = 40 SOL (production Staker `deposit`) | 102,009,604,067 | 98,863,893,185 | 777,777,777 | minted **38,766,504,032** = `floor(L·S/T)`. Honest (simulated `[VLB, SPB, deposit]`): 38,310,012,764 |
| after `[credit 55,555,555 → V1, deposit 5 SOL]` in one tx | 107,009,604,067 | 103,709,706,189 | 833,333,332 | mint at the recorded price |
| after `[VLB, SPB, deposit 5 SOL]` in one tx | 112,842,937,399 | 108,560,017,926 | 0 | fee 40,085,221 tokens; reconciled mint |
| epoch 3, stale | — | — | — | Staker deposit and WithdrawStake both revert with 0x11 |
| epoch 3, after maintenance | 112,847,975,704 | 108,560,260,270 | 0 | `r` = 5,038,305 inflation, fee 242,344 = formula |
| WithdrawStake #0 from V0 | — | — | — | `p` = 24,083,890,099 → 25,010,076,612 (formula exact) |
| WithdrawStake #1 from V1 | — | — | — | `p` = 14,682,613,933 → 15,247,258,554 (formula exact) |
| epoch 4 | — | — | — | stake withdrawn; wallet +262,119,763 |

Wallet decomposition, exact:

```
262,119,763 = payouts 40,257,335,166 − L 40,000,000,000 − 45,000 tx fees
              + 4,844,597 own cooldown stake reward on the V0-sourced account
              − 15,000 fees of two failed control txs
```

The cooldown reward is the depositor's own yield. Estimated independently from V0's reward rate, it is
4,845,537, a 0.02% difference. It is **not** pool value and is excluded from attribution.

**Isolated honest-world comparison** (`compare_results.json`, `honest_world_isolated`):

| | Window deposit | Honest deposit |
|---|---:|---:|
| P&L before tx fees | **+251,318,295** | −38,139,227 |

So **+289,457,522** is attributable to the delay. That matches `0.95·z·L/(T+z+L)` ≈ 0.2875 SOL.

**Controls (all failed as expected, with logs in `results.json`):**

* non-whitelisted Staker deposit → `UserNotWhitelisted` (6009);
* direct SPL DepositSol → rejected (missing deposit-authority account/signature);
* WithdrawSol → 0x22 "Provided sol withdraw authority does not match";
* deposit and WithdrawStake while stale → 0x11.

**Interpretation.** On the production SPL and Staker code paths, a credit after maintenance is
invisible to the Staker deposit. It is recorded at the next maintenance, and the window depositor's
extra tokens are redeemable through routed WithdrawStake.

* The local `z/T` (1.25%) was chosen to be visible. It is ~8,000× the mainnet Jito ratio and ~1/23 of
  the 1030 top-up ratio.
* **This is not a Stake v5 reproduction.** The v5 facts come from M4 and the mainnet replays.

## 4. Not run

* A Stake v5 local validator. None is available; the mainnet simulation was used instead.
* A real Jito tip-distribution claim locally.
* The `deposit_to_specific_validator` window case (its pricing leg is covered by the mainnet 1063
  replay).
* Randomised search. The bounded deterministic cases were decisive, and the economics fail by orders
  of magnitude for J.
