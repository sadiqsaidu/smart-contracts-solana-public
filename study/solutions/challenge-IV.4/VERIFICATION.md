# IV.4 — Verification record

Repository `17886b4027ace3b098e72b69cb42307409b1d6a5` (`main`; solution files untracked). Session
date 2026-10-28. No production code was modified. No transaction was sent to any public
cluster. Mainnet access was read-only (`getAccountInfo`, `getVersion`, the program clone
performed by `solana-test-validator --clone-upgradeable-program`).

## Labels

| Label | Meaning |
|---|---|
| **Proved** | By-hand argument in `PROOFS.md` / `CONJECTURE.md`; not machine-checked |
| **Src** | Read in archived upstream or local source at the cited lines |
| **Model** | `model/*.py` exact-integer execution, within the stated bounds |
| **Validator** | Client-composed transactions on a local `solana-test-validator`, output saved |
| **Hypothesis** | Unproved; see `OPEN_QUESTIONS.md` |

## 1. Inputs and provenance

* **Upstream sources.** The I.1 archive `../challenge-I.1/upstream/` (sha256 list in its
  `SHA256SUMS.json`): SPL 2.1.1 and 2.0.3, Stake v5.1.0, Token 4.0.0, Agave 2.0.15 excerpts.
  Agave 2.0.15 full tree at `/tmp/trusol-agave` (used for `runtime/src/bank.rs:3240–3251` and
  `sdk/src/feature_set.rs:541–543`).
* **Deployed SPL binary.** sha256 `ec2dfefa…d7e1`. Its processor strings fingerprint as 2.1.x
  (`../challenge-I.1/VERIFICATION.md` §2). The local clone had the same hash in both runs
  (`harness/run-stderr.txt`).
* **I.1 dependencies** D1–D5 (`PROOFS.md` §0). D1–D3 were validator-executed in the I.1
  session; D4 is proved here and executed in E1; D5 is source-only.

## 2. Live mainnet state (read-only, 2026-10-28)

Read with `harness/rpcread.py <pool>` (read-only `getAccountInfo`) plus an inline borsh walk for the fee and authority fields:

| Field | Value |
|---|---|
| pool `EyKyx9LKz7Qbp6PSbBRoMdt8iNYp8PvFVupQTQRMY9AM` owner | `SPoo1…` |
| `T`, `S`, `λ` | 66,101,088,311 · 16,407,030,513 · 1070 → `P_rec ≈ 4.0288`, `κ = 5` |
| `sol_deposit_authority` = `stake_deposit_authority` | `BLTSuAqa…` = `PDA(["deposit"], Staker)` (recomputed) |
| `staker` | `3Gu6VvL4…` = `PDA(["staker"], Staker)` (recomputed) |
| fees | epoch 5/100; stake and SOL withdrawal 1/1000; SOL and stake deposit 0; referrals 0 |
| validator list | capacity 100, **n = 4**, all Active, τ = 0, λ_i = 1070 |
| token program | `TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA` (original SPL Token) |
| feature `9LZdXeKG…` (tx lock limit 128) | account exists, **System-owned, empty → not activated** |
| `getVersion` | `solana-core 4.3.2` |

The model's base state uses exactly these balances.

## 3. Exact-integer model

```
cd study/solutions/challenge-IV.4/model
python3 -I check_iv4.py > results.json          # 13.2 s
python3 -I theorem_a_check.py > theorem_a_results.json
```

sha256 values:

* `results.json` `676b473d…431b`
* `batch_model.py` `c87edd4c…cce0`
* `check_iv4.py` `b85db3bb…a986`
* `theorem_a_check.py` `59823632…899`

Verdict line: `PASS: batch and fresh satisfy the bounds; flawed designs violate`.

**Witnesses** (transfer to depositors, lamports; `B = 200 SOL` for batch designs, `L = 100 SOL`
for immediate ones, credit `z = 50 SOL` to `V_1`):

| Design | Transfer |
|---|---:|
| immediate (today) | **+28,597,043,211** |
| nonatomic / literal first maintenance | **+35,699,122,518** |
| wrong-pair settle | **+35,699,122,518** |
| **batch (TBS)** | −0.583 |
| batch, donate 7 SOL and burn 3 TruSOL just before settle | −0.070 |
| fresh (immediate, O(n)) | −3.354 |
| escrow-mint | −3.091 |

**Bounded exhaustive search.** Every prefix of length ≤ 3 over 8 actions (maintenance, credit
to `V_0`, credit to reserve, burn, withdraw, owner add, epoch tick with payout, tick with payout
pending), inserted before settle:

| Design | Prefixes | Settled | Shortest violation |
|---|---:|---:|---|
| batch | 585 | 295 | **none** |
| escrow-mint | 585 | 295 | none |
| nonatomic | 73 | 12 | length 2: `[maintenance, donate_V0]` |
| wrongpair | 73 | 12 | length 2: `[maintenance, donate_V0]` |

**Randomized multi-epoch runs.** 400 seeds × 250 steps per design. Actions: enqueue, cancel,
status flips with hook, credits to `V_i` and reserve, burns, withdrawals, owner adds, epoch ticks
with rewards, payout completion, partial maintenance, settle attempts, claims, refunds, batch
closes, token transfers. After each run, all batches are drained.

| Design | Settles | Reverts (all during payout) | Claims | Refunds | Immediate deposits | Violations | Max transfer |
|---|---:|---:|---:|---:|---:|---:|---|
| batch | 1265 | 1210 | 363 | 491 | — | **0** | 0 (≤ 0) |
| escrow-mint | 1265 | 1250 | 535 | 0 | — | 0 | 0 |
| fresh | — | — | — | — | 1831 | **0** | 0 |
| immediate | — | — | — | — | 1216 | n/a | **+147 SOL** |
| nonatomic | 533 | 4954 | 107 | 571 | — | 6232 (liveness) | +21.45 SOL |

Checked every step: J1 escrow conservation, J4 policy invariant, vault non-negativity, I.1
`D_T, D_S ≥ 0` at fresh states. Checked per settlement: `−P < τ_b ≤ 0`. Checked at drain: no
frozen tickets, every batch closable.

**R1.** 2,000 batches with a forced duplicate amount: duplicates identical, per-user gap in
`(−2P, 0]`, maximum dust 5 with 6 claimants.

**Theorem A inequality.** 200,000 exact cases hold. Live example with `z = T`: separation of
48.7% of the fair allocation.

**Out of cell.** A rent increase produces an escrow-mint shortfall of 769,687,923 tokens. This
demonstrates H_M's conditionality.

**Model limitations.**

* Withdraw routing is simplified to the largest Active validator.
* Transients, seeds, Cleanup, compute and the Staker's own accounts are not modelled.
* Rewards are a uniform ppm rate.
* The model reproduces the upstream integer formulas but is not the program.

## 4. Local validator

```
export PATH=/tmp/trusol-redemption-tools/node-v22.14.0-linux-x64/bin:$PATH
SOLANA_BIN=/tmp/trusol-redemption-tools/solana-release/bin LEDGER_DIR=<scratch> \
  study/solutions/challenge-IV.4/harness/run.sh > study/solutions/challenge-IV.4/harness/results.json
```

**Environment.**

* `solana-test-validator 2.0.15` with legacy builtin Stake and rent 2,282,880.
* All features active; the lock limit is 128.
* SPL cloned from mainnet (hash above).
* 1024-slot epochs. Setup ran in epoch 0, experiments in epoch 1 (asserted).
* 23 validators: the local vote account plus 22 vote accounts created by the harness.
* Pool with no deposit authority; fees 5/100, 1/1000, 0.
* The "depositor" keypair stands in for the batch `Funding` PDA. The settle sequence is sent as
  top-level instructions, **not through a `trustake_batch` program**, which was not built.

The first attempt failed in setup on transaction size (three vote accounts per transaction,
1333 > 1232 bytes). It was fixed to one per transaction. The second attempt (saved) reported
`PASS`.

| Exp. | Transaction(s) | Key measured values |
|---|---|---|
| **E1** atomic settle | one v0 transaction, 62 accounts, 556 bytes, 205,836 CU: `[transfer 20 SOL → V_5, transfer 3,333,333 → reserve, VLB(23 pairs, no_merge), SPB, DepositSol(30 SOL)]` | `T` at mint = 103,055,839,573 = `Θ*`(before) + 20,003,333,333 (**donations priced in**). Minted 24,413,882,307 = `⌊B·S/T⌋` exactly. After: `D_T = 0`, `D_S = 0`. Transfer −0.79 lamports. |
| **E2** non-atomic | tx1 VLB+SPB (anyone); tx2 transfer 20 SOL → V_7; tx3 DepositSol(30 SOL) alone | `D_T` at mint = 20,000,000,000. Minted 24,413,882,307 vs fair ≈ 21,363,267,710. **Transfer +3,495,734,967 lamports (+3.50 SOL).** |
| **E3** wrong pair | after a 20 SOL credit to V_9: `[VLB with V_9/X_9 replaced by random keys, SPB, DepositSol]`, 61 accounts, 195,940 CU | VLB and SPB succeeded. `D_T` at mint = 20,000,000,000. **Transfer +2,675,354,972 lamports (+2.68 SOL).** |
| **E4** settle-shaped, padded | after crediting 1,000,003 lamports to every `V_i`: `[VLB(23), SPB(+pad), DepositSol(1 SOL)]` with 61, 65, 66 accounts | All succeeded. 270,895 CU with all 23 sweeps; 196,060 / 196,267 CU with no sweeps pending. About 3.3k CU per sweep CPI on legacy Stake. |
| **Lock limit** | separate run (`harness/lock_limit.ts`, fresh validator): 1-lamport transfer padded through a lookup table | feature owner `Feature111…` (active); 64, 65, 127, **128 accounts succeed; 129 fails**. |

**Correction recorded.** Before running E4, `SPECIFICATION.md`, `PROOFS.md`, `ATTACK_ANALYSIS.md`
and `CONJECTURE.md` claimed E4 would show "64 accounts succeed, 65 fail". E4 instead succeeded
at 65 and 66. The cause is the lock-limit feature, active on the test validator and not
activated on mainnet. The claims were rewritten (`N_MAX = ⌊(A_lock − 19)/2⌋`: 22 on mainnet, 54
locally), and the hard `N_MAX` check was removed from `settle` (SPEC §1, §5.5, §6).

**What the validator evidence does and does not show.**

* **Shows, on the deployed SPL binary:**
  * the atomic sequence prices same-transaction donations into the mint and leaves `D = 0`
    (J6, D4);
  * the two flawed alternatives transfer whole SOL to depositors (Proposition 0, wrong-pair
    risk);
  * the size and compute of a 23-validator settle-shaped transaction;
  * the runtime's lock limit on that cluster.
* **Does not show:**
  * any `trustake_batch` code (none exists);
  * CPI-specific limits (depth, account-info count);
  * Stake v5 compute or behaviour;
  * the mainnet lock limit (inferred from the feature account plus 2.0.15 source).

## 5. Scope and safety

* All new files are confined to `study/solutions/challenge-IV.4/`. Validator ledgers are in the
  session scratchpad.
* Every keypair is a throwaway generated inside the harness.
* Validators ran on ports 18899+ and were stopped at the end; no harness validator is left
  running.
