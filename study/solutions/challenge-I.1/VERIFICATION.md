# I.1 — Verification record: commands, results, limitations

Repository `17886b4027ace3b098e72b69cb42307409b1d6a5` (branch `main`, solution files untracked).
The first session wrote SOLUTION, INVARIANT_LEMMAS, WRITER_ENUMERATION, WITNESSES,
WELL_DEFINEDNESS, model.py and upstream/. It did not write this file and did no
validator execution. A second session (2026-10-28) audited those files against source,
added the harness, ran it, and wrote this file. Text added by the second session to the
earlier files is marked "Addendum".

## Evidence labels used throughout

| Label | Meaning |
|---|---|
| **Proved** | Mathematical argument in INVARIANT_LEMMAS.md over the fixed-source transition system. Not machine-checked. |
| **Source-verified** | Read in the archived upstream file at the cited line. |
| **Model-executed** | Exact-integer Python (`model.py`). It is a model of the source, not the program. |
| **Validator-executed** | A transaction or simulation ran on a local `solana-test-validator`, and the output is saved in `harness/results.json`. |
| **Not reproduced** | None of the above beyond source reading. |

## 1. Source provenance

`upstream/SHA256SUMS.json` hashes every archived file. Versions: SPL Stake Pool 2.1.1 and 2.0.3
(`processor.rs`, `state.rs`, `instruction.rs`, `lib.rs`, 2.1.1 `big_vec.rs`), Stake program
v5.1.0 (`processor.rs`, `helpers/`), SPL Token 4.0.0 `processor.rs`, and Agave 2.0.15
(`system_processor.rs`, `stake_state.rs`, `stake_instruction.rs`, rewards files).
`error.rs` was not archived for either SPL version. Error *display strings* therefore cannot be
attributed to a version from the archive.

Second-session source re-checks, all **source-verified**:

| Claim | Location |
|---|---|
| VLB sweep runs for every usable delegated V regardless of `no_merge` or status | spl-2.1.1/processor.rs:2073–2098 |
| Initialized usable V is merged into the reserve even with `no_merge` | spl-2.1.1/processor.rs:2129–2155 |
| Transient read is gated on cached `tau != 0`; with `no_merge`, no transient CPI | spl-2.1.1/processor.rs:1967–2064 |
| Wrong V/X PDA → `continue`, not an error | spl-2.1.1/processor.rs:1925–1946 |
| EpochRewards guard precedes all pair processing | spl-2.1.1/processor.rs:1884–1888 |
| SPB: `T := (R ⊖ rho_R) + Σ(A+tau)`, rejects stale entries, fee mint before `S := Sigma` | spl-2.1.1/processor.rs:2217–2286 |
| `MINIMUM_RESERVE_LAMPORTS = 0` | spl-2.1.1/lib.rs:34, 87–89 |
| ValidatorRemoval truncates `withdraw_lamports := v` **before** `T -= withdraw_lamports`; requires cached A = v afterwards | spl-2.1.1/processor.rs:3027–3043, 3104–3111, 3126–3139 |
| AddValidatorToPool caches exactly `required_lamports`, leaves T and lambda alone | spl-2.1.1/processor.rs:1000–1034 |
| DepositStake: `T += post−pre V lamports`; `A := actual post-merge V lamports` | spl-2.1.1/processor.rs:2452, 2518–2522, 2641, 2645 |
| Staker add_validator transfers `rent + max(min_delegation, MINIMUM_ACTIVE_STAKE)` from owner to reserve, then CPIs Add | programs/staker/src/instructions/validators.rs:86–166 |
| Legacy Withdraw uses stored `meta.rent_exempt_reserve` | agave-2.0.15/stake_state.rs:1014 |
| v5 Withdraw uses current `Rent::minimum_balance` | stake-v5.1.0/processor.rs:762, 788 |

No disagreement with the first session's source claims was found in these spot checks.

## 2. Deployed-binary fingerprint (read-only)

```
solana program dump -um SPoo1Ku8WFXoNDMHPsrGSTSG1Y47rzgn41SLUNakuHy spoo1.so
sha256 ec2dfefaa70d560754a0000f39bd2cabc192b895d36205b3c428f601b6e1d7e1  (1,080,464 bytes)
```

* security.txt inside the binary: `source_release: program@v2.0.3`.
* Discriminating processor strings (count in binary / 2.0.3 / 2.1.1 sources):
  * "no longer allows decreases": 1 / 0 / 1
  * "Transient stake is activating or active, deactivating": 1 / 0 / 1
  * "Reserve stake account in unknown state": 0 / 1 / 0
* Conclusion: the deployed processor matches 2.1.x, and the security.txt release label is
  stale. This is consistent with the challenge's mainnet-2026 cell `s = 2.1.x`. It is a
  string fingerprint, **not** a reproducible-build match.
* Mainnet RPC `getVersion` returned `solana-core 4.3.2`. The runtime's native Stake program
  and feature set were not otherwise inspected.

The local validator's clone of the program has the same sha256, so the harness below ran the
deployed SPL binary.

## 3. Exact-integer model

```
python3 -I study/solutions/challenge-I.1/model.py
```

Rerun on 2026-10-28 in 0.1 s. The output is byte-identical to `model-results.txt`. It covers:
527,560 bounded arithmetic cases, 5,000 restricted random transitions, 24 chunk orders, and the
mainnet-parameter traces (W2, W3, W4, W5 removal truncation, W7 rent increase, W8 legacy sweep).
**Model-executed** only.

## 4. Local validator harness

Files: `harness/two_ledgers.ts`, `harness/run.sh`, output `harness/results.json`,
stderr `harness/run-stderr.txt`.

```
export PATH=/tmp/trusol-redemption-tools/node-v22.14.0-linux-x64/bin:$PATH
SOLANA_BIN=/tmp/trusol-redemption-tools/solana-release/bin LEDGER_DIR=<scratch> \
  study/solutions/challenge-I.1/harness/run.sh > study/solutions/challenge-I.1/harness/results.json
```

### Environment

* `solana-test-validator 2.0.15 (src:f8f3fe31; feat:607245837)`. The native Stake program is
  the builtin (legacy) one. Stake-account rent was measured at 2,282,880.
* The SPL Stake Pool program was cloned from mainnet-beta (read-only), sha256 as in §2.
* RPC on port 18899 with its own ledger, so it is isolated from `./test.sh`. Slots per epoch:
  512.
* Pool: created directly through SPL (manager = staker = a fresh keypair). There is **no
  deposit authority**, so DepositSol is permissionless. Fees: epoch 5/100, withdrawal 1/1000,
  deposit 0, referral 0. One validator: the local vote account.
* The Staker program was **not** deployed (`anchor` is not installed, and no Staker
  instruction is needed for these measurements). Gap arithmetic is identical. The
  whitelist/deposit-authority layer only changes *who* may deposit.
* Actors: `manager`, `anyone` (no pool role at all), `holder` (pool tokens from DepositSol).
* Theta* is measured by **simulating** `[VLB(no_merge=true), SPB]` with `sigVerify=false`
  and reading the simulated post-state of the pool account. Every snapshot also records
  `E` and `lambda`, and the harness asserts `lambda = E` and one constant epoch.

### Results (two full runs, identical amounts; the second is saved)

| Step | Signer | T | S | Σ | Θ* | D_T | D_S |
|---|---|---:|---:|---:|---:|---:|---:|
| W0 baseline (VLB+SPB, DepositSol 3 SOL) | — | 23,000,000,000 | 23,000,000,000 | 23,000,000,000 | 23,000,000,000 | 0 | 0 |
| W1 System transfer 1,234,567 → reserve | anyone | 23,000,000,000 | 23,000,000,000 | 23,000,000,000 | 23,001,234,567 | **1,234,567** | 0 |
| N1 VLB+SPB | anyone | 23,001,234,567 | 23,000,061,725 | 23,000,061,725 | 23,001,234,567 | 0 | 0 |
| W2 Token Burn 7 | holder | 23,001,234,567 | 23,000,061,725 | 23,000,061,718 | 23,001,234,567 | 0 | **7** |
| N2 SPB alone | anyone | 23,001,234,567 | 23,000,061,718 | 23,000,061,718 | 23,001,234,567 | 0 | 0 |
| W3 System transfer 777,777 → listed V | anyone | 23,001,234,567 | 23,000,061,718 | 23,000,061,718 | 23,002,012,344 | **777,777** | 0 |
| N3 real VLB(no_merge) then SPB | anyone | 23,002,012,344 | 23,000,100,603 | 23,000,100,603 | 23,002,012,344 | 0 | 0 |
| W4 [transfer 4,242 → reserve, VLB, SPB] one tx | anyone | 23,002,016,586 | 23,000,100,815 | 23,000,100,815 | 23,002,016,586 | 0 | 0 |
| W5 pre: transfer 999 → reserve | anyone | 23,002,016,586 | 23,000,100,815 | 23,000,100,815 | 23,002,017,585 | 999 | 0 |
| W5a DepositSol 123,456,789 | holder | 23,125,473,375 | 23,123,547,321 | 23,123,547,321 | 23,125,474,374 | 999 | 0 |
| W5b WithdrawSol 100,000,003 tokens | holder | 23,025,565,052 | 23,023,647,319 | 23,023,647,319 | 23,025,566,051 | 999 | 0 |
| END after falsification attempts | — | unchanged | | | | 999 | 0 |

All rows have `E = lambda = 1`.

Exact-integer cross-checks (the program's results equal the formulas in SOLUTION.md):

* N1 epoch fee: `r = 1,234,567`, `phi = ceil(5r/100) = 61,729`,
  `f = floor(S·phi/(T + r − phi)) = 61,725`. Minted: 61,725.
* W5a: `floor(L·S/T) = 123,446,506` tokens minted. T rose by exactly 123,456,789.
* W5b: fee `ceil(p/1000) = 100,001` (a transfer, not a burn), burn `b = 99,900,002`,
  payout `floor(b·T/S) = 99,908,323`. T fell by exactly the payout and S by exactly b.

Other validator-executed facts:

* **`no_merge` mutates state.** A real VLB(true) after W3 moved exactly 777,777 lamports from
  V (1,003,060,657 → 1,002,282,880) to the reserve (22,001,234,567 → 22,002,012,344).
* **Wrong-pair skip.** The simulated VLB(true)+SPB with random V/X keys *succeeded* and returned
  `T` (23,001,234,567), missing the 777,777 donation.
* **Reward-guard failure.** At epoch 0, VLB(true) failed with `UnsupportedSysvar`
  (the EpochRewards sysvar does not exist yet). The pool was fresh (lambda = E = 0).
* **Falsification attempts by an unprivileged key** (all failed, all expected):
  * Stake Withdraw from the reserve: `missing required signature for instruction`.
  * Stake Withdraw from V: same error.
  * Token MintTo on the pool mint: `custom program error: 0x4` ("owner does not match").
  * System transfer out of the stake-owned reserve: signature verification failed.

### What this does and does not establish

* It **validator-executes** the following one-transaction witnesses in the cell
  (SPL 2.1.x deployed binary, legacy Stake, rho = 2,282,880): W1 (reserve credit, D_T +z),
  W2 (external burn, D_S +b), and validator-account credit (D_T +z via the sweep). It also
  executes later permissionless neutralization by a no-role signer (VLB+SPB, or SPB alone for
  burns), atomic neutralization in the donor's own transaction, and exact gap invariance under
  DepositSol and WithdrawSol.
* The rent constant differs from mainnet-2026 (2,282,880 vs 1,666,240). None of the executed
  rows depends on it: each delta is the transferred amount or a formula in which the rent
  cancels. Absolute balances (e.g. V = 1,002,282,880) do reflect the local rent.
* The minimum delegation on the local cluster was 1 SOL. V = 1 SOL + rent, matching
  `q = rho + max(m, 1,000,000)` with `m = 10^9`.

## 5. Not reproduced (source and model only)

* Staker-wrapped `add_validator` one-transaction D_T = +q (W3). Source-verified (§1).
  `tests/add_validator_donation.test.ts:396-422` covers the same distinction but was not run.
  It needs the Staker deployed via `anchor`, which is unavailable here.
* ValidatorRemoval truncation (W5 in WITNESSES.md). Source-verified and model-executed. Not run.
* Prefunded / zombie / orphan transient and ephemeral cases (W6).
* Legacy rent-mismatch sweep failure (W8). The local cluster has no rent mismatch.
* Rent increase making D_T negative (W7). This lies outside the fixed cell, and a
  cluster rent change cannot be driven locally.
* Stake v5 behavior in general. No v5 runtime was available. All v5 claims are source-verified
  against stake-v5.1.0 only.
* Order and chunk independence with several validators (model-executed, 24 orders, only).
* Cluster reward payouts while the pool is fresh.

## 6. Limitations of the completeness claim

Writer completeness (WRITER_ENUMERATION.md) holds relative to the archived source versions and
the runtime's ownership/debit rules. It does not cover program upgrades, hard-fork account edits,
current-mainnet reward implementation details beyond the model's nonnegativity assumption, or
features of `solana-core 4.3.2` that were not inspected.

## 7. Scope discipline

* No transaction was sent to any public cluster. Mainnet access was limited to `getVersion`,
  the program clone done by `solana-test-validator --clone-upgradeable-program`, and
  `solana program dump`.
* No production program source was modified. New files are confined to
  `study/solutions/challenge-I.1/`.
* No private keys other than throwaway keypairs generated inside the harness were used.

## 8. Post-solution validation pass (hints and assumption ledger)

All six solution files were saved before this pass. The pass read only
`CHALLENGES.md` → Hints → I.1, and `ASSUMPTION_LEDGER.md` entries L0, A1, A5, C1 and G4.

| Source | What it says | Agreement with the independent solution |
|---|---|---|
| Hint H1 | Read set first, then non-SPL writers | This is the structure of WRITER_ENUMERATION.md. |
| Hint H2 | `ΔD_T = ΔΘ* − ΔT` per instruction | This is the potential-function form of INVARIANT_LEMMAS.md. |
| Hint H3(a) | Sweep runs under `no_merge` | Matches. Also validator-executed here (§4). |
| Hint H3(b) | ValidatorRemoval truncation after pricing | Matches. The truncation shifts value between the withdrawer and incumbents (payout v instead of ell0 ≤ v + kappa). T falls by v, exactly as Θ* does, so the gap effect is **zero**. This contradicts the suggestion at `PROTOCOL_MODEL.md:446`. |
| Hint H3(c) | 2.1.x reserve term under Rent change | Matches the "Rent change" row of WRITER_ENUMERATION.md and witness W7: a decrease adds `Δrho_R` to Θ*, an increase subtracts it, with saturation. |
| A1, A5, C1 | Freshness is not reconciliation; burn and owner-add stale windows | Matches W1–W4 and the table. |
| G4 | The 2026 rent decrease to 1,666,240 (SIMD-0437) entered Θ as a +616,640 fee-bearing gain; an increase would silently lower T | Matches in sign and amount (2,282,880 − 1,666,240 = 616,640 on a 200-byte reserve). |

**Nuance recorded, no correction.** The independent solution classifies a rent change as
outside the fixed-parameter theorem. That is correct for the cell as specified, where rho is
a constant. G4 points out that a rent *decrease* actually happened on mainnet in 2026. So
"cluster parameter change" is not hypothetical as a writer class. It belongs in the (b) table
as a real, historically exercised positive writer. The table already has it, with both signs.
Only a rent *increase* would break `D_T ≥ 0`, and no such mainnet event is known. The verdict
in (a) therefore stands with the qualification already stated: `D_T ≥ 0` holds at fixed rho
and fails, by `Δrho_R` on the reserve, if rent rises within an epoch.

No error in the saved solution was revealed by this pass.
