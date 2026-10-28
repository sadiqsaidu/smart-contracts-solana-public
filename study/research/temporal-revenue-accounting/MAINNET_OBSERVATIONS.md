# Mainnet observations (read-only)

All reads used `https://api.mainnet-beta.solana.com` on 2026-10-28, around slots 462,403,763–462,409,500,
in epoch 1070 (slot index ≈ 163–170k). Mainnet epochs are 432,000 slots with no warm-up, so
`epoch = slot // 432000`. Only these read methods were used: `getAccountInfo`,
`getMultipleAccounts`, `getEpochInfo`, `getVersion`, `getSignaturesForAddress`, `getTransaction`,
`getInflationReward`, `getProgramAccounts`, `simulateTransaction` (no signature) and `solana program
dump`. Nothing was signed or sent.

Scripts and raw outputs are in `mainnet/`. sha256 values are listed at the end.

## 1. Deployed configuration (`mainnet/pool_state.json`, `mainnet/simulate_theta.json`)

| Item | Value |
|---|---|
| `getVersion` | `solana-core 4.3.2`, feature-set 3383571666 |
| Pool `EyKyx9LK…MY9AM` | owner SPoo1… |
| `T`, `S`, `λ` | 66,101,088,311 · 16,407,030,513 · 1070 |
| `last_epoch_total_lamports`, `last_epoch_pool_token_supply` | 66,092,129,298 · 16,406,919,327 |
| Mint `6umRHtiu…` | supply 16,407,030,513, decimals 9, mint authority = pool withdraw PDA `Gq5an4…`, no freeze authority |
| Manager | `D7iF7Zwx…` (System-owned) |
| Staker | `3Gu6VvL4…` = `PDA(["staker"], 6EZAJ…)` |
| Stake and SOL deposit authority | `BLTSuAqa…` = `PDA(["deposit"], 6EZAJ…)` |
| **SOL withdraw authority** | `Gq5an4…` = the pool's **own** withdraw PDA. Only SPL can sign for it, and SPL never invokes WithdrawSol on itself, so WithdrawSol is unreachable. The README says "withdraw PDA of the Staker program" (`4pKTCAr8…`); the deployed value is a different PDA with a stronger (impossible) effect. |
| Fees | epoch 5/100; stake and SOL withdrawal 1/1000; stake and SOL deposit 0/100; referrals 0; no pending fee changes |
| Preferred deposit / withdraw validator | none |
| Lockup | none |
| Validator list `8M7ZbLik…` | capacity 100, **n = 4**, all Active, all `τ = 0`, `λ_i = 1070` |
| Reserve `EDKjf7Yh…` | 11,877,875 lamports, Initialized (undelegated), `rentExemptReserve` field 2,282,880 |
| Stake program | `Stake1111…` owned by BPFLoaderUpgradeable (core BPF). security.txt `source_release: program@v5.1.0`. Dump sha256 `3d2d39c5…4c2c`. |
| SPL Stake Pool binary | dump sha256 `ec2dfefa…d7e1`. Same hash as the I.1/IV.4 sessions, which fingerprinted its processor strings as 2.1.x. |
| Staker `6EZAJ…` binary | dump sha256 `5500ff7f…b7d0` (800,056 bytes; 791,049 after trimming zero padding). It is **not** byte-identical to any local build: `staker-builds/*.so` (older, without the third-party-whitelist instructions) and `target/deploy/staker.so` (35,115 differing bytes) both differ. Its instruction-name strings include the third-party whitelist set present in the repository source. |

Rent check:

```
T = (R − 1,666,240) + ΣA_i = (11,877,875 − 1,666,240) + 66,090,876,676 = 66,101,088,311 ✓
```

The stored 2,282,880 would give a total 616,640 lower. SPB therefore uses current Rent.

### Validators (snapshot during epoch 1070)

| i | Vote | Vote commission | TDA MEV commission (1069) | `V_i` lamports | Cached `A_i` | Excess (`v − d − 1,666,240`) |
|---|---|---:|---:|---:|---:|---:|
| 0 | `Ak5BJzQe…` | 10% | 1000 bps | 13,100,219,303 | 13,100,200,442 | **18,861** |
| 1 | `GrefCNn5…` | 4% | 400 bps | 24,488,497,643 | 24,488,454,515 | **43,128** |
| 2 | `DdCNGDpP…` | 5% | **10000 bps** | 14,163,241,633 | 14,163,241,633 | 0 |
| 3 | `AX6v1G9G…` | 7% | 700 bps | 14,339,025,018 | 14,338,980,086 | **44,932** |

### Holders (`mainnet/token_holders.json`)

49 token accounts, of which 10 are non-zero.

* **78.177%** of supply (12,826,524,466) is in the manager fee account `5aiXfi…`.
* The next holders have 9.98%, 6.28% and 4.34%.
* The 4.34% holder owns `5Yw2bZ…` (owner `6nk2EX…`) and is the actor of the 1063 transactions below.

### Other readers of the pool account

A sample of 25 of the latest 1,000 signatures that reference the pool (`mainnet/pool_refs.json`)
consisted entirely of `RefreshPriceList` transactions to `HFn8GnPA…`. That program is believed to be
Kamino's Scope oracle **[Unverified identity]**. External price feeds therefore read recorded `T/S`.

## 2. Θ* measured on the live runtime (simulation)

`mainnet/simulate_theta.js` simulated `[ComputeBudget, VLB(no_merge=true, all 4 pairs), SPB]`:

* sigVerify off, fee payer = the public crank `4X8avq…`;
* context slot 462,408,833 (epoch 1070, slot index 168,833).

Results:

| | Value |
|---|---|
| Pre `T` | 66,101,088,311 |
| Simulated `Θ*` | **66,101,195,232** |
| `D_T = Θ* − T` | **106,921** = 18,861 + 43,128 + 44,932 (exactly this epoch's three claims) |
| Simulated fee mint | **1,327** tokens, equal to `floor(16,407,030,513 · 5,347 / (66,101,088,311 + 106,921 − 5,347))` with `φ = ceil(5·106,921/100) = 5,347` |
| Simulated reserve | 11,877,875 → 11,984,796. Each `V_i` swept back to `A_i` by `Stake::Withdraw` CPIs. |
| Compute | 74,507 CU. Stake `Withdraw` 7,384 CU each, consistent with BPF Stake. |

This is the **Stake v5 / solana-core 4.3.2** behaviour, not a legacy reproduction. The late Jito credit
is counted by the pool's own observation, and it is absent from `T`.

## 3. Credit timing (`mainnet/history_long.json`, `mainnet/claim_timing.json`)

`fetch_history.js 1020` fetched every signature and transaction for the reserve, the manager fee
account, all four `V_i` and their recorded `X_i`. That is 555 transactions over epochs 1020–1070.

The pool account itself is excluded. It is referenced read-only by thousands of oracle transactions,
and every write to `T` also writes the reserve, a `V_i` or the fee account.

| Statistic (51 epochs) | Value |
|---|---|
| Epochs with Jito claims to pool stake | 51 / 51 |
| Claims | 178, all via Tip Router `ClaimWithPayer` → tip-distribution `Claim`, all signed by `EG2ziPBR…` |
| Claims landing **after** the epoch's first SPB | **178 / 178** (minimum lag 3,849 slots) |
| Claims recognised in the same epoch (VLB/SPB after the last claim) | **0** |
| First SPB slot index | min 781, median 6,714, max 8,605 |
| Claim slot index | min 9,602, median 24,394, max 146,584 |
| Claimed lamports per epoch | min 72,688, median 141,904, max 369,656, total 8,036,936 |
| Native rewards effective slot index (1059–1069; 1029–1031) | 1–648, always before maintenance |
| Maintenance signers | `SBKL57…`, `SBKL5V…`, `SBKLXe…`, `SBKLuS…`, `SFLY3R…`, `4X8avq…`, `3RVJPt…`. The first five run redundant VLB/SPB each epoch. `4X8avq…` also signs TruStake stake-management and vault transactions. |

### Worked example: epoch 1070

| Event | Slot | Slot index | Signature | Pool-asset delta |
|---|---:|---:|---|---|
| VLB sweep of 1069 claims | 462,248,564 | 8,564 | `4TQL61n9UeM1PKiaFETNECHEPSapETzBqohPHJDMeiZFtNCgvuVMsjaS3Lvv87SaJMGxH3d2zXbByCoD4hFPVRS6` | reserve +80,772; V0 −13,814; V1 −33,567; V3 −33,391 |
| First SPB | 462,248,568 | 8,568 | `2Wz1uSWwMgfud6ukhJHHTRP5p3ygU8Ne5Bw81pvQUCEVuvDu9E1miw6Qq475ifvzDNH1AYJtQHKeHPV2gh6Pes26` | `T` := 66,101,088,311 |
| Claim → V0 | 462,259,135 | 19,135 | `5jrnrWgrh5EGu8oAEZ9krvBLHS5QB2qHAEPTgUeaxEsV331AGcKqaLUKdbjCJcS7EYYT3SNw9XLK2XakMfZSAvEq` | +18,861 |
| Claim → V1 | 462,270,339 | 30,339 | `5aEC2StGL6F3d3iqgvCaNw3vPq86VVUGFykX9XiyG3YBhqQvhXqFrCPhjLUxZFVvXg7YJzt723kwR13LXESV7VCC` | +43,128 |
| Claim → V3 | 462,270,521 | 30,521 | `cU4UuRepbSCi1JGc4Yhifh8VD8jRAyxpxgJ8gL7HrLcgijvbuFbghTpRkuQqMXNewZv85i43cecxKQYPgbQCTPz` | +44,932 |
| Simulated observation | 462,408,833 | 168,833 | — | `D_T` = 106,921 |

## 4. Price-sensitive user transactions inside an unrecognised window

Across 1020–1070, exactly two user transactions executed while claimed tips were unrecognised. Both
were in epoch 1063, both by `6nk2EX…` (`mainnet/window_txs_1063.json`).

| Event | Slot | Slot index | Signature | Data |
|---|---:|---:|---|---|
| First SPB 1063 | 459,222,587 | 6,587 | `382pFUmNWu8Tb7G1Mrijd9dbEpW1m99Xty6v9tmNaookf3oiFCAXocH1DmQyQ78vttJJXNYCfuN51Gz6gxgTiAcf` | — |
| Claim → V3 | 459,236,275 | 20,275 | `qoxxWiDrEU5TT3nKRgA1pr5fCaBo6T835FJVdbPZ3R4JpQurcm3H1Ja6VdEGWUPX3CnqonM18APt9q6CUjZCAsv` | +43,937 |
| Claim → V1 | 459,244,380 | 28,380 | `4jUPQqwxuUCuUyEXvwG3a4SU4wNjnHSCHpSjvkuKXgcsSXkfbnobVDTEs4d2nuhoMk8nDUuo5ryvZYer7kTGWyfQ` | +18,434 |
| Claim → V0 | 459,248,092 | 32,092 | `r2XTxC7qSEf1nPAx3ECqxUGY1Lh6ezRbfguqPNMWht1TZqiABinW6KRV5GygXj8GqC7qYAPYEvAcSMvXgXtwmpQ` | +25,860 |
| Staker `deposit_to_specific_validator` | 459,641,963 | 425,963 | `3JUCKw3Nt9we69yWfx8T3if7A3vyZ5YF6FeuxV7Gq7kS5SzfM8oRTZxQxYSiWPuMozsCrPckW1fVfqqPoqBC9G4B` | DepositSol `L` = 1,004,998,720; **minted 249,676,722** |
| WithdrawStake from V0 | 459,642,231 | 426,231 | `2srEWZq8TSYmxtgDFnLbTkU8wTiQgkxY1CESjg1kJb8dEPhXetMhXCU8h4FjRJaHNRYwo65S6XWPRTGhjAc9Yt2e` | burned 992,745,723 plus fee 993,740 to the manager; **paid 3,995,999,997**; destination prefunded with 1,666,240 rent |
| VLB 1064 | 459,655,019 | 7,019 | `4BnqAP7iPbieAKx2YcQkYj8mxfXUgtQ4AXM5vTqZkEQXiwn2ycGNBvhPs2JjAMEq3ZRdC9Nb2kYxBCvgjLGUqGGx` | sweeps the 88,231; merges X1 |

The exact replay (`model/run_checks.py` §4) reconstructs:

* `T = 69,029,448,647` and `S = 17,149,321,808` after the 1063 SPB;
* the mint and payout above, exactly.

The counterfactual (an SPB after the claims and before both transactions) would have minted 304 fewer
tokens, worth 1,224 lamports, and paid the withdrawer 4,853 lamports more. **The realised transfer
was 4,853 − 1,224 ≈ 3.6k lamports *against* this actor**, since its withdrawal was larger than its deposit.

## 5. External reserve credits (`mainnet/reserve_donations.json`)

All five use durable-nonce System transfers with the nonce authority `EbsUZEFA…`.

| Epoch | Slot index | Slot | Signature | Sender | Lamports |
|---:|---:|---:|---|---|---:|
| 1026 | 136,710 | 443,368,710 | `5azpQ6goCNECvMNGbP2HyA8Hvg3fUvadzRBXLmCDXffpq2jFTkzzpVDndCwTcJyE3g3iw2VmnFbRrT7wANZk4Tsc` | `F6XMHN2y…` | 1,400,000 |
| 1026 | 136,769 | 443,368,769 | `5zso3nYgTQQbhZfSKNiX2MhqVd2SXsYAJEGLH3QSbqu7E6z4eKiq4Ha9Ee9bsefMWw1LRoJz9n8fTavk7DbjQ4zz` | `F6XMHN2y…` | 2,100,000 |
| 1026 | 136,808 | 443,368,808 | `4r3FMP8eudvsNhs1KxnDVNvj48zet8pNnvRZxPU4eojGZoSK13vTq1FjriVgrfrkXqPkpwLHHMmoZw1kPT7sQfb2` | `F6XMHN2y…` | 1,800,000 |
| **1030** | **406,775** | 445,366,775 | `2KJhxo5LiRvusHPYKceKboAxQJ3LBDeNDXPEGMnZG2VdFJ1hwV4Bn4QzzS4zc4VXuomvWZxevjgLqAHj25rRLCSy` | `7ZiofVpt…` | **14,573,000,000** |
| 1046 | 362,051 | 452,234,051 | `3DLrLv8wBE68Fwg8STHeXYt8SYQAF6zuAtDZa8GT1dY9ZWscBtjREeKdtKkQXW8Ec4uGLaMzdDrvAxTwYd4MYy3w` | `F6XMHN2y…` | 1,900,000 |

Each was recognised only at the next epoch's SPB. For 1030 that was 1031 slot index 5,696, signature
`4sJPNCgLwJBdDV1TtvEWeb8YojWeGxMzomZbUvnFZ3J2FE6pHu33v1g28a8hdZM4avFfwijtQQ6xNLNgLHgfHtU5`. Its fee mint
was **182,052,877** tokens (`mainnet/window_1030_1032.json`).

`model/window_1030.py` reconstructs the pool just before the 1030 credit:

* `T ∈ [51,534,565,104, 51,534,578,342]`, `S ∈ [16,325,531,238, 16,325,534,543]`;
* 2,518 integer solutions, each reproducing the 1031 and 1032 fee mints and the 1032 vault deposit mint
  (`L` = 2,552,173,055 → 637,098,094) exactly;
* the credit was therefore **28.3% of `T`**.

No deposit or withdrawal occurred in the 25,225 slots from the credit to the epoch boundary. The 1031
stake-management bot then delegated 4 × 3,647,859,059 from the reserve at slot index ~31,8xx.

**Sender identity is unresolved.**

* `7ZiofVpt…` (117 SOL) and `F6XMHN2y…` (987 SOL) are System-owned. `F6XMHN2y…` is highly active.
* Both use durable nonces under `EbsUZEFA…`, a pattern typical of custodial signing infrastructure.
* Nothing on-chain links them to the Staker owner, the pool manager `D7iF7…` or the stake manager.

## 6. What could not be observed

* **Historical account snapshots.** RPC serves current state only. Past `T` and `S` were
  *reconstructed* from transactions plus `getInflationReward`. They are exact for 1063–1070 (replay
  checks), and bounded to a ±7k-lamport interval for 1030.
* **Removed validators.** Accounts that were removed earlier were not tracked.
  * 1033–1045 show 4–5 claims per epoch. All of them touched tracked accounts, and the reconstruction
    for 1030 does not depend on those epochs.
  * Exactness before 1063 is not claimed.
* **Jito's off-chain merkle trees and the upload transactions.** The timing of root uploads relative to
  maintenance was not read. Claims are the earliest observed credit.
* **`getTokenLargestAccounts`** was rate-limited. Holders were read with `getProgramAccounts` instead.

## 7. File hashes (sha256)

```
dcd8d0e091f012bae8b2d7082d8afd0d53a88cc49d59b83cf5b6bd0995072bca  mainnet/claim_detail.js
05b00887efaf60d6ef2fbd9173f42f3f62ebd3e2fbc1c653ecf2bcb217c5422c  mainnet/claim_detail_1070.json
d25d2b156db9f7532bf74df4666363d0d7911eac5ae4a95fabeb36ba0dd746af  mainnet/claim_timing.json
c606320b4926d2659c52f2ab0f985f6c79ca3a9a39b1f7b05ced082e8a57353f  mainnet/donor_provenance.json
2868775ad3a1255a28868d2b5a728c8ac5e6a07e6877ab1728f737f397321cb7  mainnet/fetch_history.js
4b56476091d104587a832fffaa87cd1888d28254102aa61e1e0765935d8995ab  mainnet/history.json
42671b97c24f3667636efa31c5e4a1f9caa3076751d2a2e4ee55b6fe80594c0f  mainnet/history_long.json
dcf4fa8423031ebbd620d14e80b1d4a95add4fc76ae0fbf5f2088d972bd8ac71  mainnet/inflation_1029_1031.json
4ca3b177c8b9cb97cca4589cf7636fd38e195534f0cbdbb9603e1d05963bdb4d  mainnet/inflation_rewards.json
13a4590a2ef311296f021c948feb19cb17d9c3923f269340bbce307362862bec  mainnet/inflation_rewards.py
4c71a887b96dbc50d1c2bb1acfeb483d43bdb3f21b417a2b07bf9c4d269808b1  mainnet/pool_refs.json
b3a385813bff3cebaec0f7cf389e8a2b3dcdd03c41341dab10c72070380b28d5  mainnet/pool_refs.py
5f5d2af39e42c39a4e8d1bec37879ee19399fc021b14ca5e61679409ea360fac  mainnet/pool_state.js
119ac70e84576f734f304dfdb36a36c9d9578056fa0f62edee7897665510363c  mainnet/pool_state.json
e45c8dfe1d9d04806ae8923333a7876065c145ff57e8d9d530fb98f63038a17e  mainnet/reserve_donations.json
9e314d76b0ed30f81edc47863260734e55095c77b5e4caa7d0eb831f73df2cc2  mainnet/simulate_theta.js
4c9f0aa54440db3c1c8ab748ea0415039ac73d91e6d7f23b73083ed7f8b3b834  mainnet/simulate_theta.json
7437514c2629002e0649f959918598640e5b0463223675b5f8fa76213ded291f  mainnet/token_holders.json
f4ce9baec856fda5f48b92f3159c9f9dbff55dd81ad2f980b7a7559d2df5fd2d  mainnet/window_1030_1032.json
7b6433169ab0fab33cb6ff82e026b47de6aaf010e2f871850b0625dcce718f61  mainnet/window_txs_1063.json
```
