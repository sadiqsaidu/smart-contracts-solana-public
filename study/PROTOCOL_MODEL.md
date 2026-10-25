# TruStake — A First-Principles Protocol Model

> Companion documents: `ASSUMPTION_LEDGER.md` (what the design relies on), `CHALLENGES.md`
> (problems), `RESEARCH_ROADMAP.md` (order of attack).
>
> **Spoiler policy.** This document reconstructs *what the system is*: its state, transitions,
> equations and trust boundaries. Wherever a property is the subject of a challenge, it is stated
> as a candidate with status `open → Challenge X` instead of being proved or refuted here. The
> mechanics needed to *attempt* every challenge are all in this file.

---

## 0. Evidence base and conventions

| Item | Value |
|---|---|
| Repository commit | `d13da28` (2026-10-15), program `programs/staker`, Anchor 0.30.1 |
| Staker program id | `6EZAJVrNQdnBJU6ULxXSDaEoK6fN7C3iXTCkZKRWDdGM` (`lib.rs:13`) |
| Underlying program | SPL Stake Pool `SPoo1Ku8WFXoNDMHPsrGSTSG1Y47rzgn41SLUNakuHy` (`constants.rs:3-7`) — **external, upgradeable by its own authority** |
| Upstream sources read | crates `spl-stake-pool` 1.0.0, 2.0.1, 2.0.3, 2.1.1, 2.2.0; GitHub tags 2.0.4 and 2.1.0 (never published to crates.io) |
| Deployed upstream version | **Unknown.** Mainnet RPC and explorers were unreachable from the research environment. Evidence (release notes, a `program@v2.1.0-mainnet` branch whose code equals 2.1.1) suggests 2.1.0. Treat every upstream claim below as *version-scoped*. |
| Live pool parameters | epoch fee 5/100, stake-withdrawal fee 1/1000, SOL-deposit fee 0, referral 0 (`scripts/init-pool.ts:147-151`, `tests/add_validator_donation.test.ts:24-25,61-65`) |

**Baseline.** Unless marked, upstream line numbers refer to **v2.1.1** (`processor.rs`,
`state.rs`, `lib.rs`), which is code-identical to the v2.1.0 tag. Differences from v2.0.3 (the
version most public documentation describes) and v2.2.0 (the newest) are listed in §9.

**Provenance tags** used throughout:

* **[L]** enforced locally by the Staker program;
* **[U]** enforced by SPL Stake Pool (version-scoped);
* **[R]** guaranteed by the Solana runtime / native Stake, System or Token programs;
* **[O]** depends on off-chain operation (bots, scripts, key custody);
* **[I]** intended only (README/comments), not enforced;
* **[✗]** known false (witness exists);
* **[?]** open.

**Not executed.** The TypeScript test suite requires `solana-test-validator` plus a clone of the
mainnet SPL program; neither the Solana toolchain download nor mainnet RPC was reachable from the
research environment. Numeric claims in the study were instead checked with an exact-integer
Python re-implementation of the upstream arithmetic (`calc_pool_tokens_for_deposit`,
`calc_lamports_withdraw_amount`, `Fee::apply`, `calc_epoch_fee_amount`, and the
DepositSol/WithdrawStake/UpdateStakePoolBalance bookkeeping). The re-implementation reproduces the
repository's own `add_validator_donation` test outcome, which is the main evidence that it is
faithful.

### Notation

| Symbol | Meaning | Source |
|---|---|---|
| `E` | current cluster epoch | Clock sysvar |
| `λ` | `stake_pool.last_update_epoch` | state.rs |
| `T` | `stake_pool.total_lamports` (**recorded** assets) | state.rs |
| `S` | `stake_pool.pool_token_supply` (**recorded** liabilities) | state.rs |
| `Σ` | actual TruSOL mint supply | SPL Token mint |
| `R` | reserve stake account lamports | chain |
| `ρ` | rent-exempt minimum of a 200-byte stake account (2,282,880 lamports at today's rent) | Rent sysvar |
| `m` | native stake-program minimum delegation | `stake::tools::get_minimum_delegation` |
| `μ` | `max(m, 1_000_000)` = SPL `minimum_delegation` | `lib.rs:80-82` |
| `q` | `ρ + μ` = SPL `minimum_stake_lamports` ("validator floor") | `lib.rs:71-76` |
| `κ` | `⌈T/S⌉` = `get_lamports_per_pool_token` | `state.rs` |
| `e, w, d` | epoch, stake-withdrawal, SOL-deposit fee rates | state.rs `Fee` |
| entry `i` | `ValidatorStakeInfo`: `A_i` active, `τ_i` transient, `σ_i` transient seed, `ς_i` validator seed (u32), `st_i` status, `λ_i` last update | `state.rs:700-760` |
| `V_i` | validator stake account `PDA(vote_i, pool, ς_i?)` | SPL |
| `X_i(s)` | transient account `PDA("transient", vote_i, pool, s)` | SPL |
| `Y(s)` | ephemeral account `PDA("ephemeral", pool, s)` | SPL |

### Three regimes, not one

The cluster parameters `m` and `ρ`, and the behaviour of the native Stake program, are not
constants of the protocol. Three different regimes are in play:

* the one the repository *documents*;
* the one its *tests run in*;
* the one mainnet *currently runs*.

They disagree.

| Parameter | Repository's documented assumption | `solana-test-validator` (Agave 2.0.15, pinned in `Anchor.toml`) | Mainnet, Oct 2026 (feature-tracker evidence, **not verified on-chain**) |
|---|---|---|---|
| `m` | 1 lamport ("devnet and mainnet", `scripts/withdraw-stake.ts:313-333`, `tests/validators.test.ts:289`) | 1 SOL (all features active at genesis) | **1 SOL since ~2026-06-18**: SIMD-0490, BPF Stake v5 hard-codes it |
| `ρ` (200 bytes) | 2,282,880 (`tests/helpers.ts:531`) | 2,282,880 | **1,666,240**: SIMD-0437 step 2, 5080 lamports/byte; further steps pending |
| `q = ρ + μ` | 3,282,880 | 1,002,282,880 | 1,001,666,240 |
| Native Stake program | — | legacy native | BPF Stake v5.1.0 |
| Source account after a Merge or full Split | — | 200 bytes, `Uninitialized`, stale trailing bytes; **anyone can `Initialize` it** | truncated to **0 bytes**; a refilled one is an un-initializable "zombie" |
| Stake `Meta.rent_exempt_reserve` | — | authoritative | deprecated: ignored by Stake v5 and written as the constant 2,282,880 |
| SPL Stake Pool | — | whatever mainnet runs at test time (cloned, `test.sh:63-75`) | unknown; evidence points to 2.1.0 |

Consequences for reading the rest of this study:

* Every quantitative statement is regime-indexed. In particular, the owner's per-validator
  donation `q` is about 300× larger on current mainnet than the repository's comments assume.
* The repository's own tests run in a regime that differs from mainnet in rent and in
  merge-leftover semantics. They also run against an unpinned upstream SPL version.

Sources for the mainnet column: Agave `feature-set` and the Feature-Gate-Tracker git history,
`solana-program/stake` v5.1.0 (`program/src/lib.rs` `get_minimum_delegation`, `helpers/merge.rs`,
`processor.rs` `process_merge`/`process_split`/`process_initialize`), and SIMD-0118, 0437, 0490
and 0392. All were read in source by a research subagent; the dates come from tracker history and
news reports.

---

## 1. Architecture and the trust boundary

```
                         ┌───────────────────────────── Staker (Anchor) ─────────────────────────────┐
 owner (multisig) ──────►│ pause/unpause · set_pending_owner/claim · set_stake_manager                │
 agents ────────────────►│ add/remove agent · whitelist/blacklist/clear · add/remove 3rd-party agent │
 3rd-party agents ──────►│ onboard/blacklist/clear own users                                          │
 whitelisted users ─────►│ deposit · deposit_to_specific_validator ──(deposit PDA, staker PDA)──┐     │
 owner ─────────────────►│ add_validator · remove_validator ────────────(staker PDA)───────────┤     │
 stake manager ─────────►│ increase/decrease_validator_stake ───────────(staker PDA)───────────┤     │
                         └──────────────────────────────────────────────────────────────────────┼─────┘
                                                                                                ▼ CPI
 anyone ───────────────► SPL Stake Pool: UpdateValidatorListBalance · UpdateStakePoolBalance ·
                         CleanupRemovedValidatorEntries · WithdrawStake (token holders)
 SPL manager ──────────► SPL Stake Pool: SetFee · SetFundingAuthority · SetStaker · SetManager · metadata
 anyone ───────────────► System transfer (to ANY address) · Token burn/transfer of own TruSOL ·
                         Stake program instructions on accounts it can sign for or that need no signer
 cluster ──────────────► epoch tick · (partitioned) reward payout · rent/feature changes
```

### 1.1 Binding asymmetry (the central architectural fact)

* **Pool → program binding [U + deployment configuration].** The canonical pool names Staker
  PDAs in its authority fields:
  * `sol_deposit_authority = stake_deposit_authority = PDA_staker("deposit")`;
  * `staker = PDA_staker("staker")`;
  * `sol_withdraw_authority` = an address that never signs. The scripts set it to the SPL
    withdraw-authority PDA (`scripts/set-withdraw-authority.ts`), and the README describes a
    Staker PDA. Either way, `WithdrawSol` is unusable.

  SPL enforces these fields (`check_sol_deposit_authority`, `check_staker`). Configuration:
  `scripts/init-pool.ts`, `scripts/set-pool-staker.ts`, `tests/helpers.ts:309-511`.
* **Program → pool binding: none [L-absent].**
  * The Staker stores no pool address.
  * Every pool-side account in every instruction is an unchecked `AccountInfo`
    (`staking.rs:38-69,169-231`, `validators.rs:28-57,182-207,282-319,431-468`).
  * The only addresses the Staker checks are program ids, sysvars and its own PDAs.
  * The deposit PDA is re-derived in-program (`staking.rs:87-88,285-286`) and signs every
    `DepositSol` CPI. The staker PDA (`seeds=[b"staker"]`) signs every validator CPI.

**Consequence (definitional).** Every local guarantee ("only whitelisted users deposit",
"deposits can be paused") is a guarantee about *any* SPL pool that names these PDAs. For the
canonical pool it holds only while the SPL manager leaves the authority fields in place. A
manager key can remove the guarantee unilaterally with `SetFundingAuthority` (upstream
`process_set_funding_authority`). (Challenge I.3 asks for the precise non-interference theorem.)

### 1.2 PDA inventory

| PDA | Seeds | Program | Created by | Destroyed by | Role |
|---|---|---|---|---|---|
| Access | `["access"]` | Staker | `initialize_staker` (`init`) | never | owner, stake_manager, paused, pending_owner |
| Agent | `["agent", k]` | Staker | init, `add_agent`, `claim_ownership` (`init_if_needed`) | `remove_agent` (rent → remover) | membership marker |
| StakeManager | `["stake_manager", k]` | Staker | init, `set_stake_manager` | `set_stake_manager` (close → owner) | membership marker |
| UserStatus | `["user", u]` | Staker | any whitelist instruction (`init_if_needed`) | never | None / Whitelisted / Blacklisted |
| ThirdPartyAgent | `["third_party_agent", c]` | Staker | `add_third_party_agent` | `remove_third_party_agent` | custodian marker |
| ThirdPartyUser | `["third_party_user", u]` | Staker | custodian onboarding (`init`) | custodian clear, `agent_release_third_party_user` | claim: which custodian owns `u` |
| staker / deposit | `["staker"]` / `["deposit"]` | Staker | — (signing only) | — | SPL authorities |
| withdraw authority | `[pool, "withdraw"]` | SPL | — | — | stake/withdraw authority of every pool stake account; mint authority of TruSOL |
| `V_i` | `[vote, pool, (ς as u32 LE if ≠0)]` | SPL | AddValidatorToPool (Allocate+Assign, split from reserve) | merge into reserve / full WithdrawStake | validator stake |
| `X_i(s)` | `["transient", vote, pool, s LE u64]` | SPL | Increase/Decrease when `τ_i = 0` | merge (UpdateVLB) | in-flight stake |
| `Y(s)` | `["ephemeral", pool, s LE u64]` | SPL | Increase/Decrease (Additional variants) | split/merge in the same instruction | staging |

**Address-poisoning primitive [R].** The three SPL families are created with
`create_stake_account` = System `Allocate` + `Assign` signed by the PDA (`processor.rs:313-332`).

* System `Allocate` fails iff the account has data or a non-system owner. Lamports are never
  checked, so a pre-funded but empty system account is harmless.
* An account drained to zero lamports keeps its owner and data **until the end of the
  transaction**.

So any party that can append a System transfer *in the same transaction* as a drain leaves a
stake-owned account at that address, and the address can never be allocated again. What remains
depends on the native Stake program:

* **legacy native:** a 200-byte `Uninitialized` account (asserted in
  `tests/transient_poison.test.ts:282-286`);
* **BPF Stake v5:** a 0-byte zombie, which needs ≥ 650,240 lamports to survive at 5080
  lamports/byte.

The two cases differ in who can undo the poisoning:

* **Under v5**, the refill is unrecoverable. Only a Withdraw signed by the address itself can
  extract it, and SPL never signs for that.
* **Under legacy stake**, *anyone* may `Initialize` the 200-byte account (no signature is needed)
  with authorities of their choice. Under v5, Initialize requires `data_len = 200`, which the
  zombie does not have.
* So under legacy stake, anyone can withdraw the refill and thereby delete the account and free
  the address. That makes poisoning reversible, and the refill acts as a bounty for whoever undoes
  it. The two regimes give opposite answers to "is poisoning permanent?"

The repository tests this for transients (`tests/transient_poison.test.ts:249-288`) and for
ephemerals (`tests/ephemeral_poison.test.ts:213-302`).

The drain points that an outsider can compose with a transfer are:

* the merge of a matured transient in permissionless `UpdateValidatorListBalance`;
* the full split of `Y` inside a whitelisted user's `deposit_to_specific_validator`;
* the merge of a removed `V_i` into the reserve in `UpdateValidatorListBalance`;
* the full withdrawal of `V_i` through the `ValidatorRemoval` path of `WithdrawStake`.

The Staker's countermeasure is to take every seed from the caller (`lib.rs:119-141`). This turns
a permanent denial of service on a fixed address into the abandonment of one address, at a cost of
`ρ` to the attacker.

---

## 2. State space

**Staker state** (all [L]):

* `Access = (O, K, π, P)`: owner, stake manager, paused, pending owner (`Option`);
* `𝒜` = agent set;
* `𝒦` = set of keys with a StakeManager PDA;
* `status : U → {None, W, B}`, partial;
* `𝒞` = custodian set;
* `claim : U ⇀ 𝒞`.

**SPL pool state** (relevant fields, [U]):

* `(T, S, λ)`;
* fee state `(e, w, d)` plus `next_epoch_fee` and `next_stake_withdrawal_fee`, each a
  `FutureEpoch ∈ {None, One(x), Two(x)}`;
* authorities: `manager`, `staker`, `sol_deposit_authority`, `stake_deposit_authority`,
  `sol_withdraw_authority`, `manager_fee_account`;
* `preferred_*` (never set by TruStake, which has no CPI for instruction 5);
* the validator list `(A_i, τ_i, σ_i, ς_i, st_i, λ_i)_{i}`.

**Chain state that SPL reads but does not own as data:**

* lamports and `StakeStateV2` of the reserve, every `V_i`, every `X_i(σ_i)`, and every `Y(s)`
  touched;
* the Token mint (`Σ`) and token accounts;
* sysvars: Clock, Rent, StakeHistory, EpochRewards (2.0.4+).

**Cluster parameters** that the protocol does not control: `ρ`, `m`, the warmup/cooldown rate,
the reward-payout schedule, feature gates, and upstream program upgrades.

---

## 3. Transition system

### 3.1 Staker instructions [L]

Notation: `Guard ⟹ Effect`. "Signer x" means x signs the outer transaction.

| # | Instruction | Guard | Effect / CPI |
|---|---|---|---|
| 1 | `initialize_staker` | Access PDA absent (`init`) | `O, K` := given keys; Agent(O), StakeManager(K) created. Anyone can call it once (`initialize.rs:57-68`); the front-run risk is accepted in the README. |
| 2 | `pause` / `unpause` | signer = O; `¬π` / `π` | toggles `π`. Affects only #17 and #18 (`setters.rs:7-50`) |
| 3 | `set_pending_owner(P')` | signer = O | `P := Some(P')`. There is no way to set `None` except by claiming (`setters.rs:69-80`) |
| 4 | `claim_ownership` | signer = P | `O := P`, `P := None`; Agent(P) created if absent; the old owner remains an agent (`setters.rs:84-122`) |
| 5 | `set_stake_manager` | signer = O; StakeManager(old) exists; StakeManager(new) absent | create (new), close (old) → O; `K := new` (`setters.rs:126-175`). `old` is **not** compared with `K`. |
| 6 | `add_agent(x)` | signer ∈ 𝒜; Agent(x) absent | Agent(x) created, signer pays (`whitelist.rs:7-38`) |
| 7 | `remove_agent(x)` | signer ∈ 𝒜, x ≠ O, x ≠ signer | Agent(x) closed, rent → signer (`whitelist.rs:43-82`) |
| 8–10 | whitelist / blacklist / clear `(u)` | signer ∈ 𝒜; status ≠ target | `status(u)` := W / B / None (`init_if_needed`; clearing a never-seen user fails) (`whitelist.rs:87-205`) |
| 11–12 | add / remove third-party agent | signer ∈ 𝒜 | add or remove `c ∈ 𝒞`; claims untouched (`third_party_whitelist.rs:7-80`) |
| 13 | `third_party_add_user_to_whitelist(u)` | signer = c ∈ 𝒞; `claim(u)` absent; `status(u) ∈ {absent, None}` | `status(u) := W`, `claim(u) := c` (`:80-140`) |
| 14 | `third_party_add_user_to_blacklist(u)` | c ∈ 𝒞; `claim(u) = c`; `status ≠ B` | `status(u) := B` (`:143-195`) |
| 15 | `third_party_clear_user_status(u)` | c ∈ 𝒞; `claim(u) = c`; `status ≠ B` | `status(u) := None`; claim closed (`:198-254`) |
| 16 | `agent_release_third_party_user(u)` | signer ∈ 𝒜; claim exists | claim closed; status untouched (`:257-294`) |
| 17 | `deposit(L)` | `status(signer) = W`, `¬π` | CPI `DepositSol(L)` signed by the deposit PDA, on caller-supplied pool accounts; emits `Deposited{amount}` (`staking.rs:83-143`) |
| 18 | `deposit_to_specific_validator(L, s_t, s_e)` | `status = W`, `¬π` | CPI `DepositSol(L+ρ)`, then CPI `IncreaseAdditionalValidatorStake(L, s_t, s_e)` signed by the staker PDA, atomically; emits `DepositedToSpecificValidator{amount, validator}` (`staking.rs:276-395`) |
| 19 | `add_validator(ς)` | signer = O | System transfer `ρ+μ` from O to the reserve, then CPI `AddValidatorToPool(ς)` (`validators.rs:86-166`) |
| 20 | `remove_validator` | signer = O | CPI `RemoveValidatorFromPool` (`validators.rs:225-267`) |
| 21 | `increase_validator_stake(L, s_t, s_e)` | StakeManager(signer) exists | CPI `IncreaseAdditionalValidatorStake` (`validators.rs:349-416`) |
| 22 | `decrease_validator_stake(L, s_t, s_e)` | StakeManager(signer) exists | CPI `DecreaseAdditionalValidatorStake` with reserve (`validators.rs:494-558`) |

Remarks:

* The two events carry neither the user nor the pool.
* The owner cannot rebalance and the stake manager cannot add or remove validators.
* Pause blocks neither withdrawals nor validator management.
* TruStake has no instruction for SPL `SetPreferredValidator`, `Redelegate`, `DepositStake` or
  `WithdrawSol`. With the staker set to a PDA and the deposit authorities set to PDAs, these are
  unreachable for everyone except through a manager reconfiguration.

### 3.2 Upstream instructions reachable in TruStake's deployment [U]

Guards common to every freshness-gated instruction: `λ = E` (`StakeListAndPoolOutOfDate`). The
gated instructions are DepositSol, WithdrawStake, Increase, Decrease, Add, Remove, and SetFee for
the epoch and withdrawal fees. The *ungated* ones are UpdateVLB, UpdateSPB, Cleanup,
SetFundingAuthority, SetStaker, SetManager, and SetFee for the deposit and referral fees (which
take effect **immediately**, `state.rs` `update_fee`, `can_only_change_next_epoch`).

**DepositSol(L)** (byte-identical 2.0.3–2.2.0):

* `n := (T = 0 ∨ S = 0) ? L : ⌊L·S/T⌋`;
* `f_d := ⌈n·d⌉`; the user receives `n − f_d`, and the instruction requires `n − f_d > 0`
  (`DepositTooSmall`);
* `T += L`, `S += n`;
* the referral account receives tokens only if `d > 0`.

There is no slippage bound in the TruStake path (index 14, not 25).

**WithdrawStake(p)** from source `src`:

* Fee and payout:
  * `f_w := ⌈p·w⌉`, or `0` if the burn account is the manager fee account or the fee account is
    invalid;
  * `b := p − f_w`;
  * `ℓ := (b·T < S) ? 0 : ⌊b·T/S⌋`, and `ℓ > 0` is required (`WithdrawalTooSmall`).
* Threshold: `θ := q + κ` (2.2.0: `q + m + κ`).
* Routing (2.1.x):
  * `HA := ∃ i: st_i = Active ∧ A_i > θ`.
  * `HT := ∃ i: st_i = Active ∧ τ_i > θ`.
  * **reserve:** requires `¬HA ∧ ¬HT` and `R − ℓ ≥ ρ_R`.
  * **validator entry `j`** (any entry with `st_j = Active`):
    * if `HA`: source must be `V_j`, with remainder `≥ q`;
    * else if `HT ∨ τ_j ≠ 0`: source must be `X_j(σ_j)`, with remainder `≥ q`;
    * else (**ValidatorRemoval**): source `V_j`, requires `v_j ≤ ℓ ≤ v_j + κ`; then `ℓ := v_j`
      and `st_j := ReadyForRemoval`.
* Effects:
  * burn `b`, transfer `f_w` to the manager;
  * native `Split(src, ℓ)` into a user-provided stake account, then authorize it to the user;
  * `T −= ℓ`, `S −= b`, `A_j` or `τ_j −= ℓ`.

The native Split adds its own minimum-balance rules (§9, second table, and Challenge II.3). With
`m = 1 SOL`, any withdrawal from an *active* validator account must be ≥ 1 SOL and must leave
≥ 1 SOL delegated. The SPL threshold `θ` in 2.1.x does not include `m`.

**UpdateValidatorListBalance(start, no_merge)**:

* Permissionless; 2.0.4+ reverts while `EpochRewards.active`.
* Accounts are pairs `(V_i, X_i)`; a pair whose addresses do not match the entry is **skipped**
  (and that entry is then not refreshed).
* Transient part, executed only if `τ_i ≠ 0` (2.0.4+):
  * Initialized & usable: merge into the reserve (or record its lamports if `no_merge`);
  * Stake & usable:
    * inactive → merge into the reserve;
    * `st_i = Active` and both `X_i` and `V_i` have `activation_epoch < E` → **merge `X_i` into
      `V_i`**;
    * otherwise (status not Active and the transient not yet deactivated) → deactivate it;
    * then `τ_i := x_i`;
  * anything else contributes 0.
* Validator part (`V_i` a usable Stake):
  * first withdraw `extra = v_i − stake − ρ` to the reserve, **even if `no_merge`**;
  * `st_i = Active` → `A_i := v_i`;
  * `Deactivating*` and inactive → merge into the reserve, status downgraded;
  * `V_i` Initialized & usable → merge into the reserve and force `DeactivatingTransient` or
    `ReadyForRemoval`.
* Always sets `λ_i := E`.
* It can be called any number of times per epoch, by anyone, over any sub-range, with either
  `no_merge` value.

**UpdateStakePoolBalance** (permissionless; no reward guard in any version):

* Requires `λ_i = E ∀i`.
* `Θ := (R ⊖ ρ_R) + Σ_i (A_i + τ_i)`, where `⊖` is saturating subtraction (2.1.x;
  2.0.3 uses a checked subtraction of the stored `meta.rent_exempt_reserve`).
* `r := Θ ⊖ T`.
* Fee tokens:
  * `φ := ⌈r·e⌉`;
  * `f := 0` if `r = 0`;
  * `f := r` if `T + r = φ` or `S = 0`;
  * otherwise `f := ⌊S·φ / (T + r − φ)⌋`.
  * `f` is minted to the manager if the fee account is valid.
  * Note that `S` here is the **recorded** supply.
* If `λ < E`: rotate `FutureEpoch` fees, set `λ := E`, and stamp the `last_epoch_*` fields.
* `T := Θ`; `S := Σ` (re-synced from the mint).

**Increase(L, s_t, s_e)** (staker only):

* Guards:
  * `L ≥ μ`;
  * `st_i = Active`;
  * if `τ_i > 0`: `s_t = σ_i` **and** `X_i` is activating in this epoch;
  * the reserve keeps `≥ ρ` after splitting `L+ρ`.
* Lamport flow: reserve → `Y(s_e)` (`L+ρ`, then delegated) → merge into `X_i`, or split
  `L+ρ` into a fresh `X_i(s_t)`.
* Record: `τ_i += L+ρ`, `σ_i := s_t`.
* Recorded `T` is untouched; observed assets are conserved.

**Decrease(L, s_t, s_e)** (staker only):

* Guards:
  * `L ≥ μ`;
  * `v_i − L ≥ q`;
  * if `τ_i > 0`: `s_t = σ_i` **and** `X_i` is deactivating in this epoch;
  * 2.0.4+: `st_i = Active`.
* Lamport flow: reserve → `Y` (`ρ − y₀`, saturating) and `V_i → Y` (`L`); deactivate `Y`; then
  merge `Y` into `X_i` or split it fully into a fresh `X_i`.
* Record: `A_i −= L`; `τ_i := x_i` (**absolute**); `σ_i := s_t`.

**AddValidatorToPool(ς)**:

* Guards: `λ = E`; capacity; vote account not present.
* Flow: reserve → `V` split `q`, delegated; pushes `(A = q, τ = 0, λ_i = E, Active)`.
* **Writes neither `T` nor `λ`.**

**RemoveValidatorFromPool**:

* Requires `st = Active`.
* Deactivates `V` (unless already deactivated) and `X` (if usable and still activating).
* Sets `st := DeactivatingAll` if `τ > 0` (2.1.x; 2.0.3 conditions this on `X` being usable), else
  `DeactivatingValidator`.
* No lamports move.

**CleanupRemovedValidatorEntries**: permissionless. Deletes entries with
`st = ReadyForRemoval`; 2.0.4+ additionally requires `A = τ = 0`.

### 3.3 External transitions (not mediated by any pool program)

| Transition | Who | Effect on the pool's view |
|---|---|---|
| System transfer to the reserve | anyone | `R` ↑; folded into `T` at the next UpdateSPB (as "reward", fee-bearing) |
| System transfer to `V_i` | anyone | swept to the reserve by the next UpdateVLB(i) |
| System transfer to `X_i(σ_i)` while `τ_i>0` | anyone | absorbed when `τ_i := x_i` is recomputed |
| System transfer to `X(s)`/`Y(s)` not referenced by the list | anyone | outside the accounts the pool reads (or orphaned if SPL later splits around it) |
| SPL-Token `Burn` of own TruSOL | any holder | `Σ` ↓, `S` unchanged until UpdateSPB |
| Token transfer | any holder | none; TruSOL is freely transferable, with no freeze authority (`init-pool.ts:63`) |
| Native Stake instructions on accounts needing no pool signature | anyone | `Initialize` of any stake-owned, 200-byte, `Uninitialized`, rent-exempt account, with arbitrary authorities [R, verified]. `DeactivateDelinquent` on stake delegated to a vote account delinquent ≥ 5 epochs [R; see Challenge IV.3] |
| Epoch tick | cluster | `E += 1`; all freshness-gated SPL instructions blocked until UpdateVLB(all) and UpdateSPB |
| Reward payout | cluster | credits **both** lamports and `delegation.stake` over `M` block heights after one calculation block. Every stake instruction except `GetMinimumDelegation` fails with error 16 while `EpochRewards.active`; system transfers into stake accounts and reads by other programs remain allowed [R, verified]. Estimated `M` ≈ 300–700 blocks on mainnet (unverified) |
| Rent / feature change | cluster | changes `ρ`, `m` and the thresholds `q`, `θ`, and (2.1.x) the reserve term of `Θ`. Under 2.1.x the 2026 rent reduction (2,282,880 → 1,666,240) enters `Θ` as a +616,640-lamport, fee-bearing "reward" on the reserve; under 2.0.3 it never enters `Θ` |

---

## 4. Economic model

### 4.1 Ledgers

Two ledgers coexist:

* **Recorded:** `(T, S)`. These drive *every* price.
* **Observed / true:** `Θ*`, the total that a full UpdateVLB(no_merge) and UpdateSPB would
  compute now, and `Σ`, the mint supply.

Define:

* `P_rec := T/S` (the deposit/withdraw price);
* `P_true := Θ*/Σ` (what a holder's claim is worth once the books are closed).

Every value transfer between classes of participants in this protocol can be written as a trade
executed at `P_rec` while `P_rec ≠ P_true`.

**Writers of each quantity.**

| Quantity | Increased by | Decreased by |
|---|---|---|
| `T` | DepositSol (+L); UpdateSPB (:= Θ) | WithdrawStake (−ℓ); UpdateSPB (:= Θ) |
| `S` | DepositSol (+n); UpdateSPB (:= Σ, after fee mint) | WithdrawStake (−b); UpdateSPB (:= Σ) |
| `Σ` | DepositSol (+n); fee mint | WithdrawStake burn; **any holder's burn** |
| `Θ*` | deposits, rewards, donations to the reserve, `V_i` or `X_i(σ_i)` (`τ_i>0`), owner `add_validator` (+`q`), ValidatorRemoval truncation (keeps up to `κ`) | withdrawals; 2.1.x reserve-rent increase |

### 4.2 Price equations (integer-exact; identical in 2.0.3, 2.1.1 and 2.2.0)

```
mint(L)        = (T=0 ∨ S=0) ? L : ⌊L·S/T⌋                      (state.rs calc_pool_tokens_for_deposit)
fee(p; a/b)    = b=0 ? 0 : ⌈p·a/b⌉                               (state.rs Fee::apply — CEILING)
payout(b)      = (b·T < S ∨ S=0) ? 0 : ⌊b·T/S⌋                   (calc_lamports_withdraw_amount)
epochfee(r)    = r=0 ? 0 : (T+r = ⌈e r⌉ ∨ S=0) ? r : ⌊S·⌈e r⌉/(T+r−⌈e r⌉)⌋   (calc_epoch_fee_amount; T,S pre-update, S RECORDED)
κ              = ⌈T/S⌉                                          (get_lamports_per_pool_token)
```

The live pool has `d = 0`, so the deposit fee and referral branches are inert. The README's claim
that the referral account "cannot affect any funds" is correct **only while `d = 0`**. The SPL
manager can change `d` instantly (no `FutureEpoch`).

### 4.3 Validator-specific deposits

`deposit_to_specific_validator(L)` mints `mint(L+ρ)` tokens and moves exactly `L+ρ` from the
reserve into `X_i`, so the user's tokens are fully backed by pool assets [U arithmetic, §3.2]. The
`ρ` sitting in the transient is pool value. It returns to the reserve as `extra` after the merge
into `V_i`, or with the transient when it merges into the reserve. How this bears on the README's
statement that a validator-targeting depositor "bears a real recurring cost (SOL plus stake-account
rent)" is Challenge IV.2.

### 4.4 Owner-funded validator creation

`add_validator` sends `q` of the **owner's** lamports into the reserve, and the CPI splits them
into `V`, recorded as `A = q`. Because AddValidatorToPool writes neither `T` nor `λ`,
`Θ* − T = q` until the next UpdateSPB. That update books `q` as reward (fee-bearing).
`tests/add_validator_donation.test.ts` demonstrates the resulting window. Its quantitative scope
(which parameter regimes make the window profitable or merely redistributive) is Challenge II.2.

The program computes `q` at run time (`validators.rs:90-95`), so the size of the donation follows
the cluster:

* 3.28 M lamports in the regime the repository documents;
* about 1.0017 SOL under a 1-SOL minimum delegation. That is the regime of the repository's own
  tests and, per the feature-tracker evidence, of current mainnet.

### 4.5 Where tokens can come from and go to

* Mint authority = the SPL withdraw PDA (`init-pool.ts:63-69`).
* Minting happens only in Initialize, DepositSol, DepositStake (unreachable here) and the
  UpdateSPB fee.
* Burning happens in WithdrawStake and in user burns.
* Fee tokens are *transferred* (not burned) to the manager in WithdrawStake.

---

## 5. The per-validator automaton (TruStake + SPL 2.1.x)

### 5.1 Transient phase of an Active entry

| Phase | `τ_i` | `X_i(σ_i)` | Increase | Decrease | `deposit_to_specific_validator` |
|---|---|---|---|---|---|
| `∅` | 0 | absent / anything (ignored, 2.0.4+) | ✓ fresh seed (creates `Act(E)`) | ✓ fresh seed (creates `Deact(E)`) | ✓ fresh seed |
| `Act(E)` | >0 | activating, `activation_epoch = E` | ✓ only `s_t = σ_i` (merges) | ✗ (`WrongStakeStake`) | ✓ only `σ_i` |
| `Deact(E)` | >0 | `deactivation_epoch = E` | ✗ | ✓ only `σ_i` | ✗ |
| `Stale` | >0 | from an earlier epoch, unmerged | ✗ | ✗ | ✗ |

### 5.2 Transitions

* **Epoch tick:** `Act(E)`, `Deact(E)` → `Stale`.
* **UpdateVLB with merge:**
  * `Stale` and inactive → `∅` (merged into the reserve).
  * `Stale` and active: → `∅` (merged into `V_i`) **if the native Merge accepts the pair**,
    otherwise the whole instruction reverts.

Native mergeability (BPF Stake v5.1.0, `helpers/merge.rs`) works as follows. Each side is
classified by `(effective, activating, deactivating)`:

| Classification | Condition |
|---|---|
| `Inactive` | `(0,0,0)` or `Initialized` |
| `ActivationEpoch` | `(0, >0, ·)` |
| `FullyActive` | `(>0, 0, 0)` |
| error 5 (`MergeTransientStake`) | anything else, i.e. partly warmed up, or deactivating with effective stake remaining |

The mergeable pairs are I←I, I←AE, AE←I, AE←AE and FA←FA. Every other pair fails with error 6
(`MergeMismatch`).

SPL's guard before merging `X_i` into `V_i` only checks `activation_epoch < E` on both sides. It
does not check that `V_i` has not been deactivated (Challenge IV.3).
* **UpdateVLB with `no_merge`:** the phase is unchanged, `τ_i` is re-read, and `λ_i := E`.

### 5.3 Status component

```
Active ──Remove──► DeactivatingAll (τ>0) ──X merged──► DeactivatingValidator ──V merged──► ReadyForRemoval ──Cleanup (A=τ=0)──► ⊥
   │                                     └─V merged─► DeactivatingTransient ──X merged──┘
   ├──Remove (τ=0)──► DeactivatingValidator
   └──WithdrawStake ValidatorRemoval (¬HA ∧ ¬HT ∧ τ=0)──► ReadyForRemoval
```

The last edge is reachable by **any TruSOL holder** whenever no Active validator is above the
routing threshold. It is not an owner-only operation, and it composes with the poisoning primitive
of §1.2.

### 5.4 Coupling between entries

Entries are not independent:

* the reserve is shared (Increase requires `R − (L+ρ) ≥ ρ`; Decrease requires `R > ρ − y₀`);
* withdrawal routing quantifies over all entries (`HA`, `HT`);
* UpdateSPB requires every entry fresh.

(Challenges I.2 and III.4.)

---

## 6. Authorization model

### 6.1 Capability matrix

**Legend:** ✓ = can; ○ = can only through a public SPL path; — = cannot.

| Capability ↓ / Actor → | anyone | TruSOL holder | whitelisted user | custodian | agent | stake mgr | owner | SPL manager |
|---|---|---|---|---|---|---|---|---|
| Mint TruSOL by depositing | — | — | ✓ | — | — | — | — | ✓ (via `SetFundingAuthority`) |
| Redeem TruSOL (WithdrawStake) | — | ✓ | ✓ | — | — | — | — | ✓ (fee-free from the fee account) |
| Move pool stake between validators | — | ○ (by choosing a withdrawal source) | ○ (`deposit_to_specific_validator`) | — | — | ✓ | — | ✓ (via `SetStaker`) |
| Add a validator | — | — | — | — | — | — | ✓ | ✓ (via `SetStaker`) |
| Remove a validator | — | ○ (ValidatorRemoval + Cleanup when all ≤ θ) | ○ | — | — | — | ✓ | ✓ |
| Change the price (`P_true`) | ✓ (donate) | ✓ (burn) | ✓ | — | — | ○ (which validators earn) | ✓ (add_validator donation) | ✓ (fees) |
| Refresh the price (`T := Θ`) | ✓ | ✓ | ✓ | — | — | ✓ | ✓ | ✓ |
| Whitelist / blacklist | — | — | — | own users | ✓ | — | ✓ (as agent) | — |
| Grant agent | — | — | — | — | ✓ | — | ✓ | — |
| Pause deposits | — | — | — | — | — | — | ✓ | ✓ (via deposit authority) |
| Change fees | — | — | — | — | — | — | — | ✓ (`d` instantly; `e`, `w` after two boundaries; `w` capped) |

### 6.2 Grant and revocation properties

* **Owner** [L]:
  * The transfer is two-step.
  * The pending owner cannot be cleared to `None`; it can only be overwritten (e.g. with `O`
    itself, then claimed).
* **Stake manager.** Under the induction invariant `𝒦 = {K}`, the check
  "StakeManager(signer) exists" is equivalent to `signer = K`. The invariant holds because #1
  creates exactly one StakeManager PDA and #5 creates one and closes one existing PDA, so the
  closed one must be the unique current one.
* **Agents:**
  * Self-replicating: any agent creates agents.
  * Revocation is per key and needs a *different* agent.
  * The owner's agent PDA cannot be closed.

  (The dynamics are Challenge II.4(d).)
* **Custodians:**
  * Removing a custodian leaves its claims in place. If the same key is re-added, it regains
    blacklist and clear power over those users.
  * A TruFin `clear` of a custodian-blacklisted user returns the user to `None`. The custodian can
    then clear its claim and re-onboard the user (two steps), so "only TruFin can lift a
    blacklist" holds only in the narrow sense that TruFin performed `B → None`.
* **Whitelist semantics.**
  * The whitelist gates *minting through the Staker*.
  * It does not gate holding, receiving, redeeming, burning, donating, refreshing, or calling any
    SPL permissionless instruction.

---

## 7. Time and concurrency

### 7.1 Epoch-boundary protocol (TruStake's maintenance bot)

`scripts/update-pool.ts` does the following:

1. Sends **one** UpdateVLB over **all** validators with `no_merge = false` (CU limit 1.2M).
2. Sends UpdateSPB in a second transaction.

Consequences:

* Any single failing merge reverts the whole step (§5, Challenge IV.3).
* Between the two transactions, entries are fresh but `T` is not; DepositSol is still blocked
  because `λ < E`.
* Upstream sizes its client at 4 validators per instruction (`MAX_VALIDATORS_TO_UPDATE`). The
  script's single instruction therefore assumes a small validator set [O].
* Transaction limits [R] are 64 account locks per transaction, 1232 bytes for legacy and v0
  transactions, and 1.4M CU.
  * UpdateVLB uses 7 fixed accounts plus 2 per validator.
  * A legacy transaction without lookup tables, which is what the script builds, therefore fits
    roughly **≤ 12 validators**.
  * No transaction format fits more than about 27.
  * `init-pool.ts` sizes the list for 100 validators.
* Beyond about 24 validators, no single transaction can contain
  `[UpdateVLB(all), UpdateSPB, deposit]`. Freshness at the boundary is then necessarily a
  *multi-transaction*, non-atomic process.

### 7.2 Freshness is per epoch, not per state

The only staleness guard is `λ = E`. Nothing in SPL ties `T` to `Θ*` inside an epoch:

* UpdateSPB is idempotent-but-repeatable;
* AddValidator does not touch `T`;
* donations, burns, and (2.0.3) mid-payout updates all create intra-epoch gaps.

Challenge I.1 asks for the complete enumeration.

### 7.3 Atomicity and composition

* A Solana transaction is atomic and may interleave instructions of several programs signed by
  its signers.
* An adversary can therefore compose permissionless SPL instructions with its own transfers,
  burns and native Stake instructions. This is the mechanism behind merge-and-refill poisoning,
  and it allows:
  * atomic `[UpdateVLB*, UpdateSPB, deposit]` bundles at the boundary;
  * `[update, burn, update]` price moves.
* Every TruStake deposit write-locks the Access PDA and the pool account, so deposits within a
  slot are serialized. Their order is the leader's choice.
* **Visibility [R/O].** Solana has no public gossip mempool, but transactions travel in plaintext
  to RPC providers, forwarders and upcoming leaders. Jito's encrypted BAM path covers only part of
  the stake. Any seed carried in instruction data, including TruStake's "fresh random" transient
  and ephemeral seeds, is therefore visible before inclusion to the current leader. The leader can
  also insert its own transactions ahead of it. Random seeds defeat *prediction*, not
  *observation*.

### 7.4 Payout window

* **2.0.4+:** UpdateVLB reverts while `EpochRewards.active`. The pool therefore stays stale (all
  gated operations fail) until the payout completes; `tests/helpers.ts:211-229` waits for this.
  At 200 ms slots and about 1.2–1.4M stake accounts, the payout is estimated at a few hundred
  blocks, roughly 2–3 minutes of unavailability per epoch (unverified).
* **2.0.3:** there is no guard. An update during the payout can stamp `λ = E` with partially
  credited balances (Challenge IV.1).

---

## 8. Invariant catalog

The scope of every invariant is "all reachable states / all transitions" unless noted.

| ID | Statement | Scope | Status |
|---|---|---|---|
| N1 | `𝒦 = {K}` (exactly one StakeManager PDA, the current one) | Staker state | **[L] holds** (induction over #1, #5) |
| N2 | Agent(O) exists; `𝒜 ≠ ∅` | Staker state | **[L] holds** (#1 and #4 create it; #7 forbids `x = O`) |
| N3 | `claim(u) = c` ⇒ `c` executed #13 for `u` after the last close of `claim(u)` | Staker state | **[L] holds** (only #13 creates claims; Anchor `close` prevents revival) |
| N4 | Only SPL mints TruSOL; no account can be frozen | token | **[U]+deployment** (mint authority = SPL PDA; `freeze_authority = None`) |
| N5 | `S ≥ Σ` between updates, with equality right after UpdateSPB | pool | **[U] holds**; strict after any user burn |
| N6 | `T ≤ Θ*` whenever `λ = E` | pool | **[?] → Challenge I.1** |
| N7 | `P_rec` never decreases | pool | **[?] → Challenge II.1** (version- and cluster-dependent) |
| N8 | `P_true` never decreases | pool | **[✗]**; witness: `tests/add_validator_donation.test.ts`, deposit-first branch |
| N9 | Within one epoch, entry `i` is subject to Increase or to Decrease, never both | per entry | **[?] → Challenge I.2** |
| N10 | `τ_i > 0` ⇒ `X_i(σ_i)` is a pool-usable, delegated stake account | per entry | **[?] → Challenge III.3** (depends on both the SPL version and the Stake-program version) |
| N11 | `deposit_to_specific_validator` is value-neutral for its caller at `P_rec` | per call | **[U] holds** (mints for `L+ρ`; moves `L+ρ`) |
| N12 | Deposits are possible only for whitelisted signers while `¬π` | Staker | **[L] holds** *for TruStake-mediated deposits*; in general **[✗]** (manager can set `sol_deposit_authority := None`) |
| N13 | WithdrawSol is impossible | pool | **[U]+configuration** |
| N14 | No TruStake instruction can change the canonical pool when invoked with foreign pool accounts | cross-program | **[?] → Challenge I.3** |
| N15 | Every lamport in `Θ*` is eventually redeemable by holders | pool | **[?] → Challenge II.3** |
| N16 | A canonical maintenance transaction succeeds every epoch | liveness | **[?] → Challenge IV.3** |
| N17 | While a transient is in flight, any seed other than `σ_i` is rejected | per entry | **[U] holds** (Increase/Decrease `InvalidSeeds`; tested in `transient_poison.test.ts:458-518`) |

---

## 9. Version deltas that matter for TruStake

Each delta below was verified by reading both versions' source unless marked.

| Behavior | 2.0.3 | 2.1.x (likely deployed) | 2.2.0 |
|---|---|---|---|
| UpdateVLB during reward payout | allowed | reverts `0x2b` | reverts |
| UpdateVLB reads `X_i` when `τ_i = 0` | yes | no (skipped) | no |
| Counting a non-usable `V_i` | counted if any Stake | only if usable | same |
| Rent source for thresholds and the reserve term | stored `meta.rent_exempt_reserve` (mixed with the sysvar in Add/Increase/Decrease) | Rent sysvar everywhere; reserve term saturating | same |
| Withdraw routing `HA`/`HT` | any status | Active entries only | + `m` in the threshold |
| Withdraw from the reserve | floor check only (full drain possible) | must leave `ρ_R` (`0x23`) | same |
| ValidatorRemoval when `0<τ_j≤θ` | allowed | forbidden (transient source forced) | same |
| Remove with `τ>0` | `DeactivatingAll` only if `X` usable | always `DeactivatingAll` | same |
| Decrease on a non-Active entry | no explicit guard | `ValidatorNotFound` | same |
| Cleanup | `ReadyForRemoval` | `ReadyForRemoval ∧ A=τ=0` | + preferred-validator resets |
| Withdrawal-fee increase check | compares `Option`s (overflow passes); ×1.5 | fixed; ×1.5 and ≤ +0.5 pp | same |
| Pricing, fee, DepositSol, Increase arithmetic | — | identical | identical |

The TruStake repository pins no upstream version. Its tests clone whatever is deployed at
`SPoo1…` when they run (`test.sh:63-75`), so the suite's evidential content changes over time
without any commit.

**The second version axis: the native Stake program.** It is independent of SPL. Every behavior
below was verified in the stake v5.1.0 and Agave 2.0.15 sources.

| Behavior | legacy native (test-validator 2.0.15) | BPF Stake v5.1.0 (mainnet) |
|---|---|---|
| Minimum delegation | 1 SOL (all features active) | 1 SOL (hard-coded) |
| Merge source after merge | 200 bytes, `Uninitialized` | 0 bytes |
| AE←AE merge absorbs | `stake + rent_exempt_reserve` | **all** source lamports |
| Split from active/activating stake | "active" means effective > 0; destination delegation `= split − rent deficit` must be `≥ m` | destination must be pre-funded with rent; split `≥ 1 SOL`; source delegation after split `≥ 1 SOL` |
| Rent used | stored `meta.rent_exempt_reserve` | current Rent sysvar |
| Behavior during payout | all stake instructions fail | all except `GetMinimumDelegation` fail (error 16) |

SPL × Stake is a 2-D version space. Several invariants hold in some cells and fail in others
(Challenges I.2 and III.3).

---

## 10. Limitations of this model

* The deployed upstream version is unverified. Use a behavioral probe (Challenge IV.1(d)) or
  `solana-verify get-program-hash` before relying on version-scoped claims.
* Native Stake-program preconditions are taken from Agave sources where cited. They depend on
  feature gates, which differ between mainnet, testnet and `solana-test-validator`.
* Off-chain components (the maintenance bot, the stake-management bot, KYC agents, multisig
  latency) are modeled only as stated in the README and scripts.
* The economic model treats stake accounts received from WithdrawStake as worth their lamports. It
  ignores deactivation delay and secondary-market discounts unless a challenge says otherwise.
