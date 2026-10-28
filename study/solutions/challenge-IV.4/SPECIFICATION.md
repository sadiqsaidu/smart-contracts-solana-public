# IV.4 — Specification: TruStake Batch Settlement (TBS)

Repository `17886b4027ace3b098e72b69cb42307409b1d6a5`. Cell **mainnet-2026**: SPL Stake Pool 2.1.x,
Stake v5, `m = 10^9`, `ρ = 1,666,240`; fees `e = 5/100`, `w = 1/1000`, `d = 0`, referral 0.
Upstream line numbers `P:` refer to the archived SPL 2.1.1 `processor.rs`
(`../challenge-I.1/upstream/spl-2.1.1/`). Local `L:` refers to `programs/staker/src/`.

This is a design. No production code was changed and no program was built (`anchor` and
`cargo` are not installed). The SPL-level semantics it depends on were executed on a local
validator (`VERIFICATION.md` §4).

## 0. Interpretation of the problem statement (read first)

The problem says deposits of epoch `E` are converted "at a price determined by the first
complete maintenance of epoch `E+1`". Taken literally, this is incompatible with R2. TBS uses
the following reading instead:

> Batch `E` is converted by a single instruction, executed in some epoch `≥ E+1`, which itself
> performs a complete maintenance (`UpdateValidatorListBalance` over every entry, then
> `UpdateStakePoolBalance`) and mints immediately afterwards. The price is the one determined by
> **that** maintenance. When the settlement is the first complete maintenance of `E+1`, the two
> readings coincide.

Reason (Proposition 0, `PROOFS.md`): anyone can perform the first complete maintenance of `E+1`,
because UpdateVLB and UpdateSPB are permissionless. SPL DepositSol always prices at the
*current* recorded `T/S` (`P:2652–2795`), and a credit to a validator stake account after that
maintenance raises `Θ*` without changing `T`. Any mint after it, at that maintenance's price,
therefore transfers the credit's pro-rata share to depositors. Bounded search finds this
counterexample at prefix length 2, and it was executed on a validator (E2). Insisting on the
*first* maintenance would also let any outsider pre-empt it and block settlement forever (R3).

## 1. Architecture

| Component | Upgradeable? | Role |
|---|---|---|
| `trustake_batch` (**new program**) | **No** (upgrade authority revoked, or a timelock; see `PROOFS.md` R5) | Custody of queued SOL and of minted-but-unclaimed TruSOL; settlement |
| Staker (existing) | yes (unchanged trust) | Permissions only: `Access` (owner, paused), `UserStatus` (whitelist). Gains the eviction hook (§5.6). Loses `deposit` and `deposit_to_specific_validator`. |
| SPL Stake Pool | unchanged | `sol_deposit_authority` re-pointed **once** by the SPL manager (`SetFundingAuthority(SolDeposit)`) to `trustake_batch`'s PDA `["deposit"]` |

Why the custody program must be separate and immutable is proved in `PROOFS.md` §R5. In short,
today no TruFin-held key has custody of principal. A queue creates custody, and custody inside
an upgradeable program hands it to that program's upgrade authority.

Why both immediate-mint paths must be removed: any remaining instruction that mints at the
recorded price re-creates the I.1 stale window, and R2 fails for those deposits (witness
`immediate`: +28.6 SOL).

### Constants compiled into `trustake_batch`

```
POOL          = EyKyx9LKz7Qbp6PSbBRoMdt8iNYp8PvFVupQTQRMY9AM   // canonical pool (read 2026-10-28)
POOL_MINT     = 6umRHtiuBd1PC6HQhfH9ioNsqY4ihZncZXNPiGu3d3rN
SPL_PROGRAM   = SPoo1Ku8WFXoNDMHPsrGSTSG1Y47rzgn41SLUNakuHy
STAKER_PROGRAM= 6EZAJVrNQdnBJU6ULxXSDaEoK6fN7C3iXTCkZKRWDdGM
TOKEN_PROGRAM = TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA   // original SPL Token: no hooks
STAKE_PROGRAM = Stake11111111111111111111111111111111111111
// No validator-count constant: the runtime lock limit already bounds settle (§6). A constant
// in an immutable program would block settlement needlessly if the limit rises.
D_MAX_NUM     = 0       // largest SOL-deposit-fee numerator settlement accepts (README: d = 0)
```

Pinning `POOL` closes the hole that today's Staker leaves open, where every pool account is an
unchecked `AccountInfo` (`L:instructions/staking.rs:38–69`). In TBS, a permissionless settler
chooses accounts for *other people's* money, so a foreign pool would mean theft.

## 2. Accounts

All PDAs are derived from `trustake_batch`'s program id. `rent(x)` is the rent-exempt minimum.

| Account | Seeds | Owner | Data | Lamports invariant |
|---|---|---|---|---|
| `Batch(e)` | `["batch", e as u64 LE]` | trustake_batch | `epoch, status ∈ {Open, Settled, Voided}, total B, minted N, claimed_tokens, unresolved, opener, bump` | `= rent + B + donations` while unsettled; `= rent + donations` afterwards |
| `Vault(e)` | `["vault", e as u64 LE]` | SPL Token; token owner = `Batch(e)` | token account, mint `POOL_MINT` | holds `N − Σ claimed` TruSOL |
| `Ticket(u)` | `["ticket", u]` | trustake_batch | `user u, batch e, amount L, state ∈ {Pending, Refundable}, bump` | `= rent` (Pending) or `rent + L` (Refundable) |
| `Funding` | `["funding"]` | **System** (no data) | — | `= f₀` between transactions; `f₀ = 0` unless someone donated, which is harmless (§5.5) |
| `DepositAuth` | `["deposit"]` | — (signing only) | — | the pool's `sol_deposit_authority` |

There is one ticket per user. A user with a Pending ticket in an older, still-unsettled batch
cannot enqueue into a new one until that ticket resolves. Claims are permissionless, so
resolution never depends on the user.

Read-only foreign accounts:

* `Access = PDA(["access"], STAKER_PROGRAM)`. The owner must be `STAKER_PROGRAM`; reads `is_paused`.
* `UserStatus(u) = PDA(["user", u], STAKER_PROGRAM)`. The owner must be `STAKER_PROGRAM`; reads `status`.

## 3. Batch and epoch boundaries

* The batch id is `Clock.epoch` at enqueue time. Batch `e` is **Open** for enqueue exactly while
  `Clock.epoch = e`. It closes implicitly at the boundary, with no instruction needed.
* Batch `e` is **settleable** when `Clock.epoch > e`, `status = Open`, and the pool's
  `EpochRewards` payout is not active (otherwise UpdateVLB reverts, `P:1884–1888`).
* Batches are independent. Batch `e` may be settled in any epoch `≥ e+1`. Each settlement
  observes the pool afresh, so settling `e` and `e+1` in the same epoch, in either order,
  gives each its own correct price.

## 4. State machines

```
Batch(e):   ∅ --open_batch--> Open --settle (n>0)--> Settled --close_batch (unresolved=0)--> ∅
                               |  \--settle (n=0)--> Voided  --close_batch (unresolved=0)--> ∅
                               |  (B may change by enqueue / cancel / evict while Open)

Ticket(u):  ∅ --enqueue--> Pending(e) --cancel (batch Open)-----------------> ∅   (L + rent → u)
                              |  \--evict (status(u) ≠ W, batch Open)--> Refundable --claim_refund--> ∅ (L + rent → u)
                              |--claim (batch Settled)--> ∅   (floor(L·N/B) TruSOL → ATA(u); rent → u)
                              \--claim (batch Voided)---> ∅   (L + rent → u)
```

## 5. Instructions (Anchor-oriented pseudocode)

The notation is Rust-like. `require!(c, Err)` aborts the transaction. All arithmetic is checked
and in `u128` where a product appears. Every account passed in is verified against its derivation.

### 5.1 `open_batch()` — anyone

```rust
let e = Clock::get()?.epoch;
init Batch(e) { epoch: e, status: Open, total: 0, minted: 0, claimed_tokens: 0,
                unresolved: 0, opener: payer.key }           // payer pays rent
init Vault(e) as token account (mint = POOL_MINT, owner = Batch(e))   // payer pays rent
```

### 5.2 `enqueue(amount: u64)` — signer `u`

```rust
let e = Clock::get()?.epoch;
require!(Access.owner == STAKER_PROGRAM && !Access.is_paused, Paused);
require!(UserStatus(u).owner == STAKER_PROGRAM && UserStatus(u).status == Whitelisted, NotWhitelisted);
require!(Batch(e).status == Open, BatchNotOpen);
require!(amount > 0, Zero);
match Ticket(u) {
    None                                    => init Ticket(u){user:u, batch:e, amount:0, state:Pending}; Batch(e).unresolved += 1,
    Some(t) if t.state==Pending && t.batch==e => {},             // top-up within the same batch
    _                                       => return Err(TicketBusy),
}
system_transfer(u -> Batch(e), amount);                          // lamports into program custody
Ticket(u).amount += amount;  Batch(e).total += amount;
```

### 5.3 `cancel()` — signer `u`. Allowed even while paused or blacklisted.

```rust
let t = Ticket(u); require!(t.state == Pending && Batch(t.batch).status == Open, NotCancellable);
Batch(t.batch).total -= t.amount;  Batch(t.batch).unresolved -= 1;
move_lamports(Batch(t.batch) -> u, t.amount);                    // owner-debit of program account
close Ticket(u) -> u;                                            // rent back
```

### 5.4 `evict(user)` — anyone. Also invoked by the Staker hook (§5.6).

```rust
require!(UserStatus(user).owner == STAKER_PROGRAM && UserStatus(user).status != Whitelisted, StillWhitelisted);
let t = Ticket(user); require!(t.state == Pending && Batch(t.batch).status == Open, NotEvictable);
Batch(t.batch).total -= t.amount;  Batch(t.batch).unresolved -= 1;
move_lamports(Batch(t.batch) -> Ticket(user), t.amount);
t.state = Refundable;
```

The refund lands in the ticket rather than the wallet. A small refund into an empty wallet would
leave it below the rent-exempt minimum and fail. Funds must never fail to leave the batch.

### 5.5 `settle(e)` — anyone. The only instruction that touches pool value.

```rust
// --- guards ---------------------------------------------------------------
require!(Clock.epoch > e && Batch(e).status == Open, NotSettleable);
require!(!Access.is_paused, Paused);                                    // pause: no Staker-mediated mint
require!(stake_pool.key == POOL && pool_mint.key == POOL_MINT, WrongPool);
require!(token_program == TOKEN_PROGRAM && stake_program == STAKE_PROGRAM
         && clock == sysvar::clock && stake_history == sysvar::stake_history, WrongProgram);
let pool = StakePool::deserialize(stake_pool)?;                          // owner == SPL_PROGRAM
require!(validator_list.key == pool.validator_list && reserve.key == pool.reserve_stake, WrongPool);
require!(pool.sol_deposit_fee.numerator <= D_MAX_NUM, DepositFeeTooHigh);
// --- complete-coverage check: the program derives every pair itself --------
let list = ValidatorList::deserialize(validator_list)?;
let pairs: Vec<AccountInfo> = for each entry i in list order {
    V_i = PDA([entry.vote, POOL, seed_suffix(entry.validator_seed_suffix)], SPL_PROGRAM);
    X_i = PDA(["transient", entry.vote, POOL, entry.transient_seed_suffix as u64 LE], SPL_PROGRAM);
    find V_i and X_i among remaining_accounts else Err(MissingPair)    // matched by key, not position
};
// --- observation: exactly the I.1 definition of Θ* --------------------------
cpi UpdateValidatorListBalance { start_index: 0, no_merge: true, pairs }   // all entries, one CPI
cpi UpdateStakePoolBalance {}                                               // T := Θ*, S := Σ (after fee)
let pool = StakePool::deserialize(stake_pool)?;                            // reload
require!(pool.last_update_epoch == Clock.epoch, NotFresh);                 // implied by SPB success
// --- mint ---------------------------------------------------------------------
let B = Batch(e).total;
if B == 0 { Batch(e).status = Settled; return Ok(()) }
require!(pool.total_lamports > 0 && pool.pool_token_supply > 0, Bootstrap);     // see ATTACK A17
let n = (B as u128 * pool.pool_token_supply as u128 / pool.total_lamports as u128) as u64;
if n == 0 { Batch(e).status = Voided; return Ok(()) }                            // DepositTooSmall avoided
move_lamports(Batch(e) -> Funding, B);
let v0 = Vault(e).amount;
cpi DepositSol { lamports: B, funding: Funding [signed], deposit_authority: DepositAuth [signed],
                 destination: Vault(e), manager_fee: pool.manager_fee_account,
                 referral: pool.manager_fee_account }                            // referral forced
let N = Vault(e).reload().amount - v0;
require!(N == n, UnexpectedMint);                                                // d = 0 ⇒ equality
Batch(e).status = Settled;  Batch(e).minted = N;
```

`Funding` is a System-owned PDA, as SPL's System transfer requires. Its balance is `f₀` before
the instruction, `f₀ + B` after the owner-debit of `Batch(e)`, and `f₀` after DepositSol. Every
rent-state transition is therefore legal, including when an attacker pre-funded it.

### 5.6 Staker hook (change to the existing, upgradeable Staker)

Every Staker instruction that sets `status(u) ≠ Whitelisted` takes two extra accounts,
`Ticket(u)` (address checked by seeds) and `Batch(ticket.batch)`. If `Ticket(u)` holds a
Pending ticket of an Open batch, the instruction CPIs `trustake_batch::evict(u)` after writing
the status. The instructions are: `add_user_to_blacklist`, `clear_user_status`,
`third_party_add_user_to_blacklist` and `third_party_clear_user_status` (`L:instructions/whitelist.rs`
and `L:instructions/third_party_whitelist.rs`). `evict` itself rechecks the status, so the hook
cannot evict a whitelisted user.

### 5.7 `claim(user)` — anyone (pushes to the user)

```rust
let t = Ticket(user); require!(t.state == Pending, NoClaim);
match Batch(t.batch).status {
  Settled => { let c = (t.amount as u128 * N as u128 / B_settled as u128) as u64;   // floor
               token_transfer(Vault(t.batch) -> ATA(user, POOL_MINT), c) signed by Batch(t.batch);
               Batch.claimed_tokens += c; }
  Voided  => move_lamports(Batch(t.batch) -> user, t.amount),
  Open    => return Err(NotSettled),
}
Batch(t.batch).unresolved -= 1;  close Ticket(user) -> user;
```

`B_settled` is the `total` frozen at settlement (`Batch.total` is never written after `Settled`).
The ATA must exist; anyone may create it, since ATA creation is permissionless.

### 5.8 `claim_refund(user)` — anyone

```rust
require!(Ticket(user).state == Refundable, NoRefund);
close Ticket(user) -> user;                 // L + rent; total ≥ rent(ticket) > rent(empty wallet)
```

### 5.9 `close_batch(e)` — anyone

```rust
require!(Batch(e).status ∈ {Settled, Voided} && Batch(e).unresolved == 0, NotClosable);
let r = Vault(e).amount;                    // dust: N − Σ floor(L·N/B) < number of claimants
if r > 0 { token_burn(Vault(e), r) signed by Batch(e) }     // returns dust value to all holders
close Vault(e) -> opener;  close Batch(e) -> opener;        // opener's rent and any donations
```

## 6. Transaction-size budget for `settle`

| # | Account | | # | Account |
|---|---|---|---|---|
| 1 | settler (signer, fee payer) | | 11 | reserve (w) |
| 2 | `trustake_batch` program | | 12 | Clock sysvar |
| 3 | `Batch(e)` (w) | | 13 | StakeHistory sysvar |
| 4 | `Funding` (w) | | 14 | Stake program |
| 5 | `Vault(e)` (w) | | 15 | manager fee account (w) |
| 6 | `Access` | | 16 | pool mint (w) |
| 7 | `DepositAuth` | | 17 | Token program |
| 8 | stake pool (w) | | 18 | System program |
| 9 | SPL withdraw authority | | 19 | SPL Stake Pool program |
| 10 | validator list (w) | | | + `V_i, X_i` for every entry |

`F = 19`, so the transaction needs `19 + 2n` distinct accounts, and `N_MAX = ⌊(A_lock − 19)/2⌋`.

* The lock limit `A_lock` is 128 if feature `increase_tx_account_lock_limit`
  (`9LZdXeKGeBV6hRLdxS1rHbHoEUsKqesCC2ZAPTPKJAbK`) is active, else 64 (Agave 2.0.15
  `runtime/src/bank.rs:3240–3251`).
* **Mainnet:** that feature account is System-owned with no data, i.e. not activated (read-only
  check, 2026-10-28). So `A_lock = 64` and **`N_MAX = 22`** under the 2.0.15 rule; whether
  `solana-core 4.3.2` changed the rule is unverified.
* **Local test validator:** the feature is active, and the limit was measured at exactly 128
  (128 accounts succeed, 129 fail; `harness/lock_limit_results.json`). There `N_MAX = 54`.
* One fewer account is possible by using `Funding` as the deposit authority (`n ≤ 22` still at
  64). The live pool has `n = 4`.

Other limits:

* The VLB CPI carries `7 + 2n ≤ 51` account infos.
* CPI depth: batch → SPL → Stake/System/Token is 3.
* Size: well under 1232 bytes with an address lookup table (556 bytes measured for a 62-account settle-shaped transaction, E1).
* Compute: one optional sweep `Withdraw` CPI per entry; 270,895 CU measured with all 23 entries swept, under legacy Stake (E4);
  **unmeasured under Stake v5** (`OPEN_QUESTIONS.md`).

## 7. Invariants (proved in `PROOFS.md`)

| ID | Statement |
|---|---|
| J1 | For an Open batch: `Batch(e).total = Σ { t.amount : t Pending, t.batch = e }` and `lamports(Batch(e)) ≥ rent + total`. |
| J2 | A Refundable ticket holds `rent + amount` lamports, and only `close → user` debits it. |
| J3 | For a Settled batch: `Vault(e).amount = N − claimed_tokens ≥ Σ_{unclaimed} ⌊L·N/B⌋`. |
| J4 | (Policy B) Every Pending ticket of an Open batch belongs to a user whose status is `Whitelisted`. |
| J5 | (Destination closure) Batch lamports go only to `Funding → reserve` (settle), to the ticket's user, to the ticket, or to the opener (rent and donations after resolution). Vault tokens go only to `ATA(ticket.user)` or are burned. Ticket lamports go only to `ticket.user`. |
| J6 | At the instant DepositSol executes inside `settle`, `T = Θ*` and `S = Σ`. |
