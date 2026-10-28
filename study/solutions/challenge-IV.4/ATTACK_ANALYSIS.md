# IV.4(c) — Attack analysis of TBS

**Threat model.**

* The default adversary 𝔄 is a non-leader. It signs only for its own keys, may be a whitelisted
  depositor and/or a TruSOL holder, and may compose any instructions it can sign into one atomic
  transaction.
* A *leader* adversary may also reorder or insert within its own slots.
* Governance actors (owner, agents, custodians, stake manager, SPL manager, upgrade authorities)
  are analysed separately. The cluster supplies epoch ticks, reward payouts and feature/rent
  changes.

**Classification.** **Economic** means an attack that moves value at legal prices.
**Instruction-level** means an attack that makes something revert or reach a bad state.

**Evidence.**

* `model/results.json` holds model output: witnesses, bounded search (`bfs`) and randomized runs.
* `harness/results.json` holds validator output for experiments E1–E4.

## Summary table

| # | Attack | Class | Fewest legal txs | Result against TBS | Evidence |
|---|---|---|---|---|---|
| A0 | Price at the literal "first maintenance of E+1" | economic | 2 (maintenance; credit to `V_j`) | **Breaks the literal spec**; TBS avoids it by observing inside `settle` | Model bfs (length 2); Validator E2 |
| A1 | Donation or burn just before settlement, same tx or earlier | economic | 1 | Captured by settle's own `O`: incumbents gain, donor loses, transfer ∈ (−P, 0] | Model witness −0.07 lamports; Validator E1 |
| A2 | Push the settlement price down | economic | — | Impossible for non-governance actors (proof below) | Proved |
| A3 | Settle before epoch-E yield is credited (Jito tips) | economic | 1 (settle early) | **Not prevented.** Outside R2's I.1 yardstick; bounded by depositors' share of the late-credited yield | Argument |
| A4 | Validator stake-state changes | instr. | 1 | No settle failure in the v5 cell; legacy rent mismatch can block (cluster) | Src; I.1 W8 |
| A5 | Epoch-boundary timing | economic | 1 | Only A3's leak; payout blocks settle for minutes | Src P:1884 |
| A6 | Griefing or denying settlement | instr. | — | No non-governance blocking branch (R3 table) | Proved; Model |
| A7 | Dust and integer rounding | economic | ≥ 1 | < 1 raw unit per claimant plus < 1 per batch, all to incumbents | Proved; Model (max dust 5 of 6) |
| A8 | Manager fee powers | economic | 1 (governance) | `d` instant → settle refuses (`D_MAX_NUM`); epoch fee hits pre-settle rewards only | Src |
| A9 | Blacklisting during settlement | instr. | 1 | Serialized on `Batch(e)`; evicted before or claimable after | Proved; Model J4 |
| A10 | Partial settlement and transaction limits | instr. | — | `n ≤ 22` atomic at mainnet's 64 locks; no strict R2 above `N_MAX` for any design (Theorem A) | Validator lock-limit run; Proved |
| A11 | Exit liquidity (II.3) | economic | — | Unchanged for TruSOL; `cancel` is a SOL exit for unsettled deposits | Src |
| A12 | Account substitution | instr. | 1 | All accounts derived or pinned; the wrong-pair skip is closed | Validator E3 shows why |
| A13 | Replay or double claim | instr. | 2 | Ticket closes; settle is one-shot | Proved |
| A14 | Reentrancy-like sequencing | instr. | 1 | No callbacks into `trustake_batch`; original SPL Token has no hooks | Src |
| A15 | Rent and account-closure edges | instr. | 1 | Pre-funded `Funding`, empty wallets, donations to `Batch` all handled | SPEC §5 |
| A16 | Foreign pool (today's unchecked pool accounts) | economic | 1 | Pool and mint pinned as constants | SPEC §1 |
| A17 | Bootstrap `S = 0` or `T = 0` | economic | — | `settle` refuses | SPEC §5.5 |
| A18 | Very small batch (`n = 0` tokens) | instr. | 1 | Voided (full refunds), no revert | SPEC §5.5 |
| A19 | Price inflation to enlarge rounding (III.2 "dead shares"); *added in review pass* | economic | 1 + gifts | δ is P-denominated: loss ≤ (m_b+1)·P per batch. Negligible on the live pool; real in a near-empty pool | Proved (below) |

## A0 — the literal specification is exploitable

Prefix: a complete maintenance in `E+1` (anyone), then a System transfer of `z` to listed `V_j`
(anyone), then a mint at the recorded price.

* **Model** (`B = 200 SOL`, `z = 50 SOL`): `τ_b = +35,699,122,518` lamports, i.e. +35.7 SOL to
  depositors. Bounded search over 6 action types found no shorter prefix.
* **Validator E2:** 23 validators, `B = 30 SOL`, `z = 20 SOL`. Measured numbers are in
  `VERIFICATION.md` §4.
* Jito tip claims are the same credit with no adversary involved. The fix is to observe inside
  the minting instruction (TBS `settle`).

## A1 — donation or burn just before settlement

Same-transaction prefix `[donate 7 SOL to reserve, burn 3 TruSOL]`, then `settle`:
`τ_b = −0.07` lamports (model). E1 put a 20 SOL credit to `V_5` and 3,333,333 lamports to the
reserve in the settle transaction. The mint's `T` equalled `Θ*(before) + 20,003,333,333`
exactly, i.e. the depositor paid the true price. The donor's gift goes to incumbents (95%) and
the manager (5% epoch fee). The depositors' tokens fall to match; they are not diluted.

Profit for 𝔄 as a depositor: a gift raises the price that 𝔄 itself pays. As an incumbent with
share `s`, 𝔄 recovers at most `s·0.95·z < z`. The attack is never profitable.

## A2 — the settlement price cannot be pushed down by non-governance actors

Claim: within an epoch, every non-governance transition weakly raises `P_net = Θ*/Σ*`. The
cases:

* Credits raise `Θ*`.
* Burns lower `Σ`.
* WithdrawStake pays `⌊b·T/S⌋ ≤ b·P_rec ≤ b·P_net`, because `P_rec ≤ P_net` at fresh states
  (I.1 `D_T, D_S ≥ 0` and the fee bound). The fee is a transfer to a holder.
* Token transfers are neutral.
* VLB/SPB are idempotent on `P_net` (D4).
* Owner `add_validator` (governance) is a gift.

Lowering requires a rent increase (cluster, outside the cell) or a governance fee change; the
epoch fee applies only to rewards. A settler therefore cannot obtain a cheap price for
depositors. The status of this claim is a proof sketch whose cases are covered by the model.

## A3 — uncredited yield at settlement (the residual economic leak)

Yield earned in epoch `E` that is credited only *after* settlement in `E+1` is shared with batch
`E`'s depositors, even though their SOL was idle during `E`. Jito MEV tip distributions are the
main example: they are claimed into stake accounts as lamports some hours into `E+1`.

* At the settlement instant this yield is not part of `Θ*`, so it is **not** an I.1 divergence,
  and R2 as stated is unaffected.
* Economically, depositors receive `B/(Θ*+B) × (late-credited yield)`. Any depositor can settle
  early, at the first post-payout slot, to capture it.

Mitigations, each a latency trade-off:

1. Settle not before slot offset `σ*` of `E+1`, for example the last 10% of the epoch. This
   still fails against claims delayed past `σ*`.
2. Settle at `E+2` instead. This doubles latency and the leak shifts to claims delayed by more
   than an epoch.
3. Accept the leak.

No setting removes it entirely. By Theorem A's information argument, a program cannot see yield
before it is credited. Its magnitude on mainnet is unmeasured (`OPEN_QUESTIONS.md` Q3).

## A4 — validator stake-state changes

| Change | Effect on `settle` |
|---|---|
| `DeactivateDelinquent` (anyone) on `V_j` or `X_j` | The `no_merge` path still records lamports (P:2100–2122); the sweep from deactivating stake is allowed. No failure. |
| Commission or vote-authority changes, vote account closure | Not in VLB's read set; affect future rewards only. |
| v5 zero-byte "zombie" at a drained `V_j`/`X_j` address | Decodes to `None`, contributes 0, consistent with cache (I.1). No failure. |
| Legacy cell: stored `rent_exempt_reserve` > current rent | Sweep `Withdraw` fails → `settle` reverts until the stake cools down (I.1 W8). Cluster-caused; `k = ∞` in that cell. Funds safe via `cancel`. |

## A5 — epoch-boundary timing

* Enqueueing in the last slot of `E` joins batch `E`, which settles within minutes of the
  boundary. That gives the shortest idle time; the only gain is A3's leak.
* Settlement is impossible while `EpochRewards.active` (P:1884–1888), a window estimated at a
  few hundred blocks.
* A leader adversary at the boundary can delay a settle by its own slots only.
* Within an epoch, `settle` reads a single `Clock.epoch`, so no straddling is possible.

## A6 — griefing the settler

Using the R3 enumeration (`PROOFS.md`):

* **No non-governance seed changes.** `deposit_to_specific_validator` is removed, and VLB never
  writes seeds.
* **Cleanup is harmless.** It can be run by anyone, deletes entries, and is tolerated by
  key-matching.
* **Forced sweeps are bounded.** Donations add at most `n ≤ 22` sweep CPIs. E4 reports compute
  with every entry swept.
* **`Funding` pre-funding is harmless.**
* **Lock contention.** `settle` write-locks the pool account. A spammer competing for the pool's
  lock pays fees and can only delay inclusion (assumption L5).
* **Settler cost** is the transaction fee plus priority fee. There is no settler reward, by
  design, to avoid a new privileged party. Depositors are the natural settlers.

## A7 — dust and rounding

* The mint floor costs depositors `< T₁/(S₁+N) < P` per batch (R2(1)).
* The claim floor costs `< 1` raw unit per claimant, and the residual (`≤ m_b − 1` raw) is
  burned at close.
* All of it goes to holders, never to depositors.
* At the live `P ≈ 4.03` lamports per raw unit, a batch of 10,000 depositors loses under
  40,300 lamports (0.00004 SOL) in total.
* [Model] Maximum dust was 5 with 6 claimants. 2,000 randomized batches stayed within
  `(−2P, 0]` per user.
* Spam tickets cost their creator ticket rent plus fees. Settlement cost is independent of the
  number of tickets (claims are per-user and pushed).

## A8 — manager fee powers

| Power | Today | Under TBS |
|---|---|---|
| SOL deposit fee `d`, instant (`SetFee`, no `FutureEpoch`) | applies to the next deposit | `settle` refuses while `d > D_MAX_NUM = 0`; depositors cancel. Converts a charge into a refusal. |
| Referral fee | needs `d > 0` | referral account forced to the manager fee account |
| Epoch fee `e` (two boundaries) | taken from rewards | taken in settle's SPB from rewards accrued *before* entry, i.e. the incumbents'. Correct attribution. |
| Withdrawal fee `w` | exit | unchanged |
| `SetFundingAuthority(SolDeposit)` | manager can open or close deposits | can block settlement (refusal → cancel), or let someone else mint at stale prices outside TBS (existing power) |

## A9 — blacklisting during settlement

`evict` and `settle` both write `Batch(e)`, so the runtime orders them. Two cases:

* **Evict first.** `B` excludes the ticket and the user gets an exact refund.
* **Settle first.** The ticket is claimable and the user receives TruSOL minted while they were
  whitelisted.

[Model] J4 held at every step of 400 × 250 randomized runs with status flips.

## A10 — partial settlement and transaction limits

* Atomic settlement needs `19 + 2n` accounts.
  * On mainnet, `A_lock = 64` (feature not activated), so `n ≤ 22`.
  * The local validator has `A_lock = 128`: 128 accounts pass and 129 fail
    (`harness/lock_limit_results.json`). Its 62–66-account settle-shaped transactions
    succeeded (E1, E4).
* For `n > 22`, *every* design loses strict R2 (Theorem A).
* A windowed chunk variant leaks at most the depositors' share of credits to already-observed
  accounts during the window. This is reported, not adopted.

## A11 — exit liquidity (II.3 interaction)

* Queued SOL is outside the pool. It neither helps nor hurts pool exits, and `cancel` returns it
  in SOL.
* Settled TruSOL faces the existing WithdrawStake constraints: under v5, splits from active
  stake must be at least 1 SOL; reserve withdrawals need no validator above `θ`.
* A settlement drops `B` into the reserve at once. Until the stake manager delegates it, routing
  is unchanged in 2.1.x (reserve exits are allowed only when no Active validator is above `θ`).
* TBS adds no new exit path for TruSOL and removes none.

## A12–A16 — sequencing and substitution

* **Substitution.**
  * Checked: pool, mint, token program, stake program, SPL program (constants); validator list
    and reserve (pool fields); `V_i`/`X_i` (derived from the list read on-chain).
  * Checked: `Access`/`UserStatus` (owner and seeds); `Batch`/`Vault`/`Ticket`/`Funding`
    (seeds); manager fee account (SPL compares it to the pool field); referral (forced).
  * E3 executes the consequence of omitting the pair check. With one wrong pair, VLB skipped
    entry 9, SPB succeeded, and DepositSol minted at a stale price.
* **Replay.** `settle` requires `Open`. `claim` and `claim_refund` close the ticket. Anchor's
  `close` prevents same-transaction revival. Re-creating a ticket starts a new, unrelated deposit.
* **Reentrancy.** CPI targets are SPL, Stake, System and original SPL Token. None invokes
  arbitrary programs, and Token-2022 transfer hooks do not exist on this mint
  (`token_program = Tokenkeg…`, read on-chain).
* **Rent.** `Funding`'s balance is `f₀` before and after (`f₀ ≥` rent-exempt minimum or 0).
  Ticket closes always carry more than the empty-wallet minimum. Donations to `Batch` go to the
  opener at close. The vault is closed after the burn.

## A19 — price inflation amplifies rounding (added after the hints/roadmap review)

Every TBS rounding bound is proportional to `P`: `(−(m_b+1)·P, 0]` per batch and `(−2P, 0]` per
depositor. An incumbent holding share `h` of `Σ` can raise `P` by a factor `k` by donating
`(k−1)·Θ*`. It recovers `h·0.95` of that donation and collects up to `h·(m_b+1)·k·P` of the
depositors' rounding per batch. On the live pool (`Θ* ≈ 66 SOL`, `Σ ≈ 1.64·10^10` raw units,
`P ≈ 4.03`), extracting 0.001 SOL per depositor needs `P ≈ 10^6`. That means donating about
`2.5·10^5 × 66 SOL`, of which at least 5% (the epoch fee) plus the depositors' share is lost.
Impractical.

In a near-empty pool, for example after a mass exit with `Σ` small, the same inflation is
cheap. This is the classic dead-shares problem, and batching neither causes nor fixes it. A
settle guard `S ≥ S_min` (dead shares) or a minimum batch size relative to `P` would bound it.
Neither is in the current specification.
