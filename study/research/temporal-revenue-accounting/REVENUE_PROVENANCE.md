# Revenue provenance

Repository `4f1d51a2a842273a4932378ab7d621da211e546a`, branch `study/solutions-I.1-IV.4`. Mainnet reads
2026-10-28, epoch 1070 (`mainnet/pool_state.json`). Evidence labels: **[Chain]** public mainnet data,
**[Sim]** read-only mainnet simulation, **[Src]** source read, **[Model]** exact-integer model,
**[Local]** local validator, **[Unverified]**.

## 1. The counted asset set

The pool is `EyKyx9LKz7Qbp6PSbBRoMdt8iNYp8PvFVupQTQRMY9AM`. SPB computes

```
T := (R − Rent(200)) + Σ_i (A_i + τ_i)          spl-2.1.1/processor.rs:2226-2240
```

On mainnet, `Rent(200)` is 1,666,240 (the current Rent sysvar, not the stored `rentExemptReserve` of
2,282,880). This was checked by recomputing `T` from the live accounts (§MAINNET_OBSERVATIONS 2). So
revenue matters to the pool only if it reaches one of these:

* the reserve `EDKjf7…` (read directly by SPB);
* a listed validator stake account `V_i`. VLB sweeps `v − d − Rent` into the reserve on every call,
  `no_merge` or not (processor.rs:2073-2098), then refreshes `A_i`;
* a listed transient `X_i`, only while `τ_i ≠ 0`.

The four `V_i` (all Active, `τ = 0`, validator seed suffix 0) are listed in
`mainnet/pool_state.json`.

## 2. Revenue categories

| # | Category | Source of value | Beneficiary | Controller | Destination (owner) | Auto / claim | Signer to pay | Epoch relation | Counted? | Changes | Can land after complete maintenance? |
|---|---|---|---|---|---|---|---|---|---|---|---|
| R1 | Native inflation (stake rewards) | protocol issuance | delegators, net of vote commission | runtime partitioned rewards (EpochRewards) | `V_i` (Stake program) | automatic | none (runtime) | earned in `e`, credited in `e+1` slot index 1–648 [Chain] | yes | `delegation.stake` and lamports both increase, so it is **not** an excess. VLB refreshes `A_i := v_i` | **No.** It is paid inside the reward window, when VLB reverts (`EpochRewardDistributionInProgress`, processor.rs:1884-1888). DepositSol and WithdrawStake revert while `λ < E` (processor.rs:2703, 2847). |
| R2 | Inflation vote commission | issuance | validator operator | runtime | vote account (Vote program) | automatic | — | as R1 | **no**, not a pool account | — | irrelevant |
| R3 | Jito MEV tips, delegator share | searcher tips paid into the validator's TipDistributionAccount (TDA) during `e` | stake accounts delegated to the validator at `e`, pro rata, net of the TDA `validator_commission_bps` | Jito tip-distribution `4R3gSG8B…` behind Tip Router `RouterBmu…` | `V_i` | **claim**: Tip Router `ClaimWithPayer` → tip-distribution `Claim` (merkle proof) | tx fee payer only. The Tip Router source has no caller check; its config/payer PDAs sign the inner Claim [Src, Jito master; deployed version not verified] | root uploaded during `e+1`; claims observed at `e+1` slot index 9,602–146,584 [Chain] | yes (excess over `d + Rent` in `V_i`) | lamports only. Delegation unchanged → swept at the next VLB | **Yes, every epoch observed** (178/178 claims in epochs 1020–1070) |
| R4 | Jito MEV tips, validator commission | tips | operator | Jito | operator-chosen claimant (vote account) | claim | — | as R3 | no | — | irrelevant |
| R5 | Jito tips of a 100%-commission validator | tips | operator only | Jito | operator | claim | — | — | **no**: V2's validator `DdCNGD…` sets 10,000 bps [Chain]. Its TDA for 1069 paid 59.32 SOL to 2 claimants out of 2,619 nodes; TruStake's `V2` received nothing in 51 epochs | — | — |
| R6 | Priority-fee distribution (Jito PFD program) | priority fees shared by validators | delegators | Jito PFD, also behind Tip Router | `V_i` | claim | — | — | would be counted | lamports | **None observed**: all 178 claims were tip-distribution (inner program `4R3g…`) [Chain] |
| R7 | Block fees / priority fees kept by the leader | users | validator identity | runtime | identity account | automatic | — | per block | no | — | — |
| R8 | Deliberate external credits to the reserve | whoever sends them | all holders at the next SPB (net 5% epoch fee) | sender | reserve | sender's own `SystemProgram.transfer` | sender | any slot | **yes** (SPB alone recognises it) | `R` | **Yes**: 5 transfers in 1020–1070, including **14.573 SOL at 1030 slot index 406,775**, from durable-nonce wallets sharing the nonce authority `EbsUZEF…` [Chain]. The sender is not attributed. |
| R9 | Credits to `V_i` by anyone (System transfer, Stake withdraw into it, account closure) | sender | holders at the next VLB+SPB | sender | `V_i` | sender | sender | any | yes | lamports | yes (I.1 W3, validator-executed) |
| R10 | Owner `add_validator` funding `q = Rent + max(m, 1e6)` | owner | holders at next SPB | Staker owner | reserve → new `V` (cached `A = q`, `T` untouched) | owner instruction | owner | any | yes | `A`, not `T` | yes (the known Immunefi report, `tests/add_validator_donation.test.ts`). None observed in 1020–1070 |
| R11 | Payments to accounts the pool does not list (ephemeral/zombie PDAs, vote accounts, operator wallets, an unlisted stake account) | — | — | — | — | — | — | — | **no** | none | [Model] check 6; [Local] control |

### R3 in detail: the Jito path (one mainnet example)

`5jrnrWgr…AvEq` (slot 462,259,135, epoch 1070, slot index 19,135), from `mainnet/claim_detail_1070.json`:

* **Signer and fee payer:** `EG2ziPBR…` (fee 5,001). It is the only signer of all 178 claims.
* **Top level:** Tip Router `ClaimWithPayer(proof, amount, bump)`.
* **Inner:** tip-distribution `Claim`, with accounts:
  * config `STGR71…`;
  * TDA `87BQ…` (V0's validator, epoch 1069);
  * the merkle-root-upload authority `8F4j…` (a Tip Router PDA);
  * claim status `9gVZ…`, created and paid 1,178,560 by the router payer `6jWg4…`;
  * claimant `FDBQ…` = TruStake `V0`;
  * System program.
* **Effect on the stake account:** `V0` went from 13,100,200,442 to 13,100,219,303 (+18,861). The TDA was debited the same amount. The stake account's data was not touched.
* **TDA 1069 for V0's validator:**
  * `validator_commission_bps = 1000`;
  * `max_total_claim = 4,369,271,306`, of which 4,369,091,064 claimed by 140 of 183 nodes;
  * `expires_at = 1079`.

  Unclaimed amounts expire to Jito's expired-funds account, not to the pool.

Tip Router `process_claim_with_payer` (`jito-tip-router` master, `program/src/claim_with_payer.rs`,
fetched 2026-10-28) loads the NCN, Config and AccountPayer and checks the distribution program id. It
then `invoke_signed`s the claim with the router's PDAs. **It performs no check on the
transaction signer.** So an arbitrary party can trigger a claim whose merkle proof it holds. The proofs
are published off-chain by Jito ([Unverified] here). Whether the deployed router binary matches master
was **not** verified.

### What does not happen

* No Jito tip is assigned to TruStake's stake *delegation*. Tips arrive only as excess lamports.
* No claim was ever directed to the reserve or a transient.
* Native rewards never land outside the reward window (`mainnet/inflation_rewards.json`:
  effective slots 1–648 in epochs 1060–1070).
* The reserve (undelegated) earns no inflation (`getInflationReward` → `null`).

## 3. Exact per-epoch reconciliation (proof that R1 and R3 are the whole flow)

Epoch 1070:

```
T_1070 − last_epoch_total_lamports = 66,101,088,311 − 66,092,129,298 = 8,959,013
inflation(1069) for V0..V3 = 1,709,928 + 3,281,624 + 1,873,887 + 2,012,802 = 8,878,241   [getInflationReward]
Jito claims credited in 1069, swept at the 1070 VLB = 13,814 + 33,567 + 33,391 = 80,772   [history.json]
8,878,241 + 80,772 = 8,959,013   (exact)
```

The exact replay in `model/run_checks.py` §4 extends this from 1063 to 1070. It uses only R1, R3 and
the two user transactions of 1063, and it reproduces all of the following **to the lamport and
token**:

* `T_1070` and `S_1070`;
* both `last_epoch_*` fields;
* the 1063 deposit mint (249,676,722);
* the 1063 WithdrawStake payout (3,995,999,997).

No other writer of `T` or `S` acted in that interval, so there were no unobserved burns, donations or
deposits.

## 4. Share of revenue

| Item, per epoch (1060–1070) | Lamports | Relative to `T` ≈ 66.1 SOL |
|---|---:|---:|
| Native inflation to pool stake | 8.8–9.2 M | 1.34 × 10⁻⁴ |
| Jito tips claimed by pool stake | 72,688–166,611 (mean ≈ 99k) | ≈ 1.5 × 10⁻⁶ |
| Jito tips relative to inflation | — | ≈ 1.1% |

Over 1020–1070, the 178 claims total 8,036,936 lamports (≈ 0.008 SOL in ~100 days).
