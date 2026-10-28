# IV.4 — Proofs of R1–R5 (and Proposition 0)

The design is `SPECIFICATION.md` (TBS). `P:` is SPL 2.1.1 `processor.rs`, `S:` its `state.rs`
(archived in `../challenge-I.1/upstream/spl-2.1.1/`). Evidence labels:

* **[Proved]** argument here; not machine-checked.
* **[Src]** read in source at the cited lines.
* **[Model]** exact-integer model, within the stated bounds.
* **[Validator]** executed on a local validator; see `VERIFICATION.md`.

## 0. Definitions and dependencies

**State and observation.** As in I.1:

* `T, S` are the recorded pool fields and `Σ` is the mint supply.
* `O` is the *complete observation*: `UpdateValidatorListBalance(start=0, no_merge=true)` over
  every list entry with the correct `(V_i, X_i)` pair, then `UpdateStakePoolBalance`.
* `Θ*(x) := T(O(x))`.
* `Σ*(x) := Σ(O(x))`. This includes the epoch fee that `O` mints, so pending fees are
  crystallized.
* The *net true price* is `P(x) := Θ*(x)/Σ*(x)`. The value of `k` tokens at `x` is `k·P(x)`.
  This is the yardstick for every "transfer" below.

**Transfer.** For a batch `b` with lamports `B` that receives `N` tokens at a mint producing
state `x₂`, the transfer to depositors is `τ_b := N·P(x₂) − B`. Incumbents are everyone holding
TruSOL other than the batch vault.

**Dependencies on Challenge I.1.** These were verified or executed in the I.1 session, see
`../challenge-I.1/VERIFICATION.md`:

| ID | Statement | Status |
|---|---|---|
| D1 | UpdateVLB with a wrong `(V,X)` pair `continue`s; it does not error (P:1925–1946). | [Src] [Validator] (I.1 and E3 here) |
| D2 | A System transfer of `z` to a listed usable validator stake account leaves `λ = E` and raises `Θ*` by exactly `z`, while `T, S, Σ` stay unchanged. | [Src] [Validator] (I.1 W3, E1/E2 here) |
| D3 | DepositSol(`L`) at a fresh pool with `d = 0`: `n = ⌊L·S/T⌋` (`T,S > 0`), `R += L`, `T += L`, `S += n`, `Σ += n`, nothing else. | [Src] P:2652–2795, S:162–171; [Validator] (I.1 W5a, E1 here) |
| D4 | `O` is idempotent: `Θ*(O(x)) = T(O(x))` and `S(O(x)) = Σ(O(x))`. | [Proved] below; [Validator] (E1 `DT_after = 0`) |
| D5 | In the v5 cell, a correctly formed complete `O` succeeds on reachable states outside the reward payout. | I.1 WELL_DEFINEDNESS.md, [Src] only; **not executed under v5** |

R1, R2, R4 and R5 depend only on D1–D4. R3 additionally depends on D5.

**Proof of D4.** Run `O` on `y = O(x)`.

* Every usable delegated V was swept to `v ≤ d + ρ`, so the second sweep is `0`, and
  `A_i := v_i` rewrites the same value (P:2081–2101).
* Every Initialized usable V was merged into the reserve in the first pass. It is now 0-byte
  (v5) or `Uninitialized` (legacy), decodes to the "ignore" arm, and keeps `A_i = 0`
  (P:2156–2162).
* Transients: `no_merge` writes `τ_i := x_i`, and `x_i` was not changed by the first pass
  (P:1967–2064).
* The reserve is unchanged, so SPB recomputes the same total. Hence `r = 0` and the fee is 0
  (P:2238–2247), giving `T(O(y)) = T(y)`.
* SPB sets `S := Σ` (P:2284–2286). ∎

## Proposition 0 — the literal "first complete maintenance" price refutes R2

**Claim.** Suppose a design mints batch `E`, in a transaction after the first complete
maintenance of `E+1`, at that maintenance's recorded price (i.e., without re-observing). Then
R2 fails. Two non-governance transactions suffice.

**Witness [Model] [Validator E2].**

1. Anyone performs `O` (tx 1).
2. Anyone transfers `z` lamports to a listed validator stake account `V_j` (tx 2; by D2, `T`
   is unchanged and `Θ*` rises by `z`).
3. The settlement mints `N = ⌊B·S/T⌋` (tx 3).

Then
`τ_b = N·P(x₂) − B ≈ B·(Θ*−T)/(Θ*+B) · (1 − e) > 0`, which grows without bound in `z`.

In the model, with `B = 200 SOL` and `z = 50 SOL`, `τ_b = +35.7 SOL`, and bounded search
finds no shorter prefix. A Jito tip claim is the same credit with no adversary involved. ∎

So R2 forces the price to be determined *in the minting transaction*. That is the TBS reading
(`SPECIFICATION.md` §0).

---

## J6 — the mint happens at `T = Θ*`, `S = Σ` [Proved]

Let `x₀` be the state when the `settle` instruction starts. Any instructions earlier in the
same transaction, including adversarial ones written by the settler, are already part of `x₀`.

* `settle` refuses unless it has located, by its own derivation from the list it reads, the
  correct `(V_i, X_i)` for every entry. The list must be `pool.validator_list` (SPEC §5.5).
  The VLB CPI therefore covers every entry with correct pairs, and D1's silent skip cannot occur.
* Within one instruction no other instruction interleaves. The CPI targets (SPL, Stake, System,
  original SPL Token) never call back into `trustake_batch` [Src: they invoke only
  Stake/System/Token].
* After VLB and SPB the state is `x₁ = O(x₀)`, and by D4, `T(x₁) = Θ*(x₁)` and `S(x₁) = Σ(x₁)`. ∎

## R2 — no stale transfer [Proved; Model; Validator E1]

**Theorem R2.** Assume the settle transaction succeeds, and let `m_b` be the number of tickets
claimed from batch `b`. Then:

1. At the mint, `−P(x₂) < τ_b ≤ 0`.
2. After every claim and the dust burn, the depositors of `b` together receive value in
   `(B − m_b·P_b − P_b, B]`, where `P_b = P(x₂)`. Equivalently, the transfer from depositors to
   other holders is under `(m_b + 1)` raw token units and is never negative.
3. The bound does not depend on the size, timing or type of any I.1 divergence that happened
   before settlement.

So `δ_b = (m_b + 1)·P_b` lamports per batch, all in the incumbents' favor. With the live
`P ≈ 4.0288` (`κ = 5`), this is under 4.03 lamports per claimant plus one.

*Proof.*

**(1) Mint rounding.** By J6 and D3 (`T₁, S₁ > 0` is checked; `d = 0` is checked, so
`N = n = ⌊B·S₁/T₁⌋`):

* `T₂ = T₁ + B`, `S₂ = Σ₂ = S₁ + N`, and `Θ*(x₂) = Θ*(x₁) + B = T₂`. The reserve is counted
  linearly because `R ≥ ρ_R`, so the saturating subtraction is exact.
* So `D_T(x₂) = D_S(x₂) = 0`, no fee is pending, and `P(x₂) = T₂/S₂`.
* `τ_b = N·T₂/S₂ − B = (N·T₁ − B·S₁)/(S₁ + N)`.
* Since `N = ⌊B·S₁/T₁⌋`, we have `B·S₁ − T₁ < N·T₁ ≤ B·S₁`, hence
  `τ_b ∈ (−T₁/(S₁+N), 0]`.
* Finally, `T₁/(S₁+N) < T₁/S₁ ≤ (T₁+B)/(S₁+N) = P(x₂)`, because `N·T₁ ≤ B·S₁`.

**Conservation.** The other holders own `S₁` tokens. Their value goes from `T₁` (at `x₁`, by
J6) to `S₁·P(x₂) = T₂ − N·P(x₂) = T₁ − τ_b`, so they gain exactly `−τ_b ≥ 0`.

**(2) Claims and dust.** Each claim is `c_u = ⌊L_u·N/B⌋`, so `Σ_u c_u ≤ N` and the residual is
`r = N − Σ c_u ≤ m_b − 1`. `close_batch` burns `r`. A burn transfers value from the burned
tokens to all remaining holders pro rata; at most `r` tokens' worth leaves the depositors. Add
(1).

**(3) Independence.** `τ_b` is a function of `(B, T₁, S₁)` and floor rounding alone. Every
pre-settlement divergence is inside `x₀` and therefore inside `T₁ = Θ*(x₀)` and
`S₁ = Σ*(x₀)`. Depositors' lamports never touch the pool before settlement:

* enqueue, cancel and evict move lamports between users, `Batch` and `Ticket` only (J5);
* claims move existing tokens only.

After settlement, depositors are ordinary holders. Later divergences act on all holders through
the same I.1 mechanisms, and there is no batch-specific transfer. ∎

**Scope.** R2 is a *safety* property. It needs neither I.1's `D_T ≥ 0` nor the mainnet-2026
cell: if `settle` succeeds in any cell, including after a rent change, J6 holds. Its
preconditions are coverage (enforced on-chain), `d ≤ D_MAX_NUM = 0`, the pinned pool and mint,
and the original SPL Token program. Execution: E1 shows the mint at the observed price with
same-transaction adversarial donations, and `D_T = D_S = 0` afterwards.

**Corollary (n > N_MAX).** For `n > N_MAX`, the settle transaction exceeds the lock limit and cannot be built. No design can recover strict R2 by
spreading the observation over several transactions: by Theorem A (`CONJECTURE.md`), the
entry transaction must access every `V_j`. A chunked variant with window `Δ` slots satisfies
only `τ_b ≤ (share of depositors) × (credits to already-observed accounts during Δ)`. That is
not a constant δ.

## R1 — intra-batch fairness [Proved; Model]

**Theorem R1.** Take two depositors `u, v` in the same Settled batch.

1. If `L_u = L_v`, they receive identical token amounts. The value difference is `δ₁ = 0`
   exactly, whatever the claim order or timing.
2. For any `u`, `c_u·P_b − L_u ∈ (−2P_b, 0]`. No depositor ever gains, and each loses less
   than two tokens' worth (8.06 lamports at the live price).
3. Refunded depositors (cancel, eviction, Voided) receive exactly `L` plus their ticket rent.

*Proof.*

1. `c = ⌊L·N/B⌋` is a function of `L` and of `(N, B)`, which are written once at settlement and
   frozen. `Batch.total` is never written in `Settled`. Tokens are fungible, so claim time does
   not matter.
2. Upper bound: `c_u·P ≤ (L_u·N/B)·P = L_u·(1 + τ_b/B) ≤ L_u`. Lower bound:
   `c_u·P > (L_u·N/B − 1)·P = L_u + L_u·τ_b/B − P > L_u − P − P`, using `τ_b > −P` and
   `L_u ≤ B`.
3. Direct from SPEC §5.3–5.8. ∎

[Model] 2,000 randomized batches, each with a forced duplicate amount. Duplicates were always
identical, every per-user gap was in `(−2P, 0]`, and the maximum dust was `5 < 6` claimants.

## R3 — liveness [Proved under assumptions; Model]

**Assumptions.**

* **L1.** Cell mainnet-2026 (Stake v5), and D5 holds.
* **L2.** The `EpochRewards` payout lasts fewer slots than an epoch (estimated a few hundred
  blocks; `PROTOCOL_MODEL.md` §7.4).
* **L3.** `n ≤ N_MAX` (22 at 64 locks, which is the mainnet rule; 54 at 128; the live `n` is 4).
* **L4.** At least one party is willing to pay for a settle transaction in epoch `e+1`. Any
  depositor of batch `e` is motivated.
* **L5.** No censorship of a fee-paying transaction for a whole epoch; a single leader controls
  only its own slots.
* **L6.** The compute for `n ≤ 22` sweeps fits 1.4 M CU (measured under legacy Stake in E4;
  unmeasured under v5).
* **L7.** The SPL program is not upgraded incompatibly.

"Governance" means owner, agents, stake manager, SPL manager, and upgrade authorities.

**Theorem R3.** Under L1–L7, batch `e` can be settled in epoch `e+1`, and no non-governance
actor can push its settlement past `e+1`. Hence **`k = 1`**: settlement occurs no later than
the epoch after the batch's own. The only non-governance delay inside `e+1` is the reward
payout (L2).

*Proof.* Enumerate every failure branch of `settle` (SPEC §5.5) with its writer:

| Branch | Who can cause it | Non-governance? |
|---|---|---|
| `Clock.epoch ≤ e` | time | — |
| reward payout active (P:1884–1888) | cluster, bounded by L2 | delay `< 1` epoch |
| paused | owner | governance |
| `d > D_MAX_NUM`; deposit authority changed; fee account changed | SPL manager | governance |
| `19 + 2n` exceeds the lock limit | only owner `add_validator` raises `n` (the only path that appends entries, P:894–1036 via staker PDA) | governance |
| `MissingPair` | changes to an entry's vote or seeds: Add (owner), Increase/Decrease (stake manager). VLB writes only status/active/transient/epoch (P:1989,2012,2119,2151–2153,2165–2167). `deposit_to_specific_validator` is removed in TBS. Cleanup (anyone) only deletes entries, and key-matching tolerates extra accounts. | no non-governance writer |
| VLB CPI failure | D5 excludes it in v5. Donations only add sweep CPIs, which succeed under v5's current-rent rule (stake-v5.1.0 processor.rs:762,788) | none in cell |
| SPB failure | requires stale entries, impossible right after full VLB; an invalid fee account means fee 0 (P:2241–2247) | none |
| DepositSol `DepositTooSmall` | avoided: `n = 0` yields Voided instead of a revert | none |
| compute exhaustion | bounded by L3, L6 | none |
| account substitution | client-recoverable; checked on-chain | — |
| pre-funded `Funding` PDA | harmless (SPEC §5.5); it cannot be allocated or assigned without the PDA signature | none |

Every non-governance branch is either impossible in the cell or bounded within `e+1`.
A leader adversary can only reorder within its own slots (L5). ∎

**Outside the cell.** In the legacy-Stake cell, a cluster rent decrease makes VLB's sweep
fail for stake accounts with a stored older rent (I.1 W8). If one treats the cluster as an
"actor", then **`k = ∞`** there until the stake cools down or governance repairs it. Funds are
not frozen, because `cancel` remains available.

[Model] In 400 × 250-step randomized runs, every settle revert occurred while the payout was
active. There were 0 unexplained reverts and 0 drain failures. The model does not model seeds,
Cleanup, or compute.

## R4 — blacklisting between deposit and settlement [Proved; Model]

**Policy B (normative).** Conversion is the minting act, so eligibility is evaluated at
settlement. A user whose status leaves `Whitelisted` while their ticket is Pending in an Open
batch is refunded in full. A user blacklisted *after* settlement still claims their TruSOL,
because the whitelist gates minting, not holding (`PROTOCOL_MODEL.md` §6.2).

**Theorem R4.**

1. **(Enforcement, J4)** At every settlement, every Pending ticket in the batch belongs to a
   whitelisted user.
2. **(No freezing)** From every reachable state, every ticket can reach ∅ without any TruFin
   key's signature. Under pause or SPL-manager obstruction, the depositor's own `cancel`
   suffices.
3. **(No redirection, J5)** Queued lamports and minted tokens can go only to the ticket's user,
   to the canonical pool reserve via DepositSol at settlement, or to burn (dust).
4. **(Bounded agent power)** The only effect an agent or custodian can have on a pending
   deposit is to refund it in full.

*Proof.*

1. Induction over instructions that create Pending tickets or change status.
   * `enqueue` requires `Whitelisted` now.
   * The Staker is the only writer of `UserStatus`, because it is the account owner.
     Each of its four instructions that set a status other than `Whitelisted` (SPEC §5.6) CPIs
     `evict` in the same instruction.
   * Status-setting instructions that create a `None` status (`init_if_needed`) concern users
     with no ticket, since `enqueue` requires an existing `Whitelisted` status.
   * `cancel`, `evict` and `claim` only remove Pending tickets.
   * `settle` and `evict` both write `Batch(e)`. The runtime serializes them, so a status change
     lands strictly before settlement (ticket evicted, `B` excludes it) or strictly after
     (ticket claimable).
2. Case analysis on (ticket state, batch status):
   * Pending/Open: `cancel` (user only; it checks neither pause nor status), or settle then claim.
   * Refundable: `claim_refund` (anyone).
   * Pending/Settled: `claim` (anyone; ATA creation is permissionless; the mint has no freeze
     authority, `init-pool.ts:63`).
   * Pending/Voided: `claim` (anyone).
   * Every close transfers at least `rent(ticket)`, which is above `rent(empty wallet)`, so the
     close never fails on rent.
3. Enumerate every debit of `Batch`, `Vault`, `Ticket` and `Funding` in SPEC §5. The
   destinations are `Funding`, then the reserve in the same instruction; `ticket.user`; `Ticket`
   (evict); the opener (rent and stray donations, only after `unresolved = 0`); and burn. No
   destination is an instruction argument except `user`, and that is bound to the ticket's seeds.
4. Follows from (1)–(3). The refund is exact and immediate (permissionless `claim_refund`). ∎

**Dependency and residual risk.** Strict enforcement relies on the hook in the *upgradeable*
Staker. If the hook is missing or wrong, the failure is a policy breach (a blacklisted user's
pending deposit gets converted at a fair price), not a loss of value. Permissionless `evict` is
a backup but races settlement.

**Alternative, Policy A.** Authorize at enqueue and ignore later status changes. It needs no
hook and gives agents no power over pending deposits. However, it mints TruSOL through TruStake
for a user who is blacklisted at minting time, which I read as not preserving whitelist
semantics. Both policies satisfy (2) and (3).

## R5 — no new trust [Proved, conditional on immutability]

**Lemma NC (today, no TruFin key can move existing principal).** [Src]

* The Staker's PDAs hold two SPL roles.
  * `staker` permits Add, Remove, Increase, Decrease and SetPreferred. Redelegate is disabled:
    the deployed binary contains "Redelegate will not be enabled" (`../challenge-I.1/VERIFICATION.md` §2).
  * `sol/stake_deposit_authority` permits only inflows.
* None of these debits pool assets to an arbitrary account. Outflows (WithdrawStake/WithdrawSol)
  require burning pool tokens held by the signer (P:2800–3288).
* The SPL manager controls fees and authorities. Epoch-fee changes are delayed by
  `FutureEpoch`, and withdrawal-fee increases are capped. These act on future rewards and
  flows, not on existing assets.
* The Staker upgrade authority can therefore change permissions and validator choice (yield),
  but not principal. ∎

**Theorem R5.** Assume `trustake_batch` is immutable. For every depositor and every incumbent,
the outcomes that depend on actions by TruFin-controlled keys (owner, agents, custodians, stake
manager, SPL manager, Staker upgrade authority) form a subset of the outcomes those keys could
already impose:

* *delay of conversion, with the user able to take `L` back at any time*. This is induced by
  pause, `d > 0`, a changed funding authority, `n > N_MAX`, or a Staker upgrade that sets
  `paused`. It equals today's "your deposit transaction is refused";
* *full refund of a pending deposit*, induced by blacklist or clear. It equals today's "a
  blacklisted user's deposit is refused";
* the SPL manager's existing powers (fees, authorities). The `D_MAX_NUM` check turns an
  instant deposit-fee increase into a refusal rather than a charge.

The settlement price is fair within δ irrespective of these actions (R2). Owner gifts
(`add_validator`) before settlement accrue to incumbents, exactly as gifts did before.

*Proof.* J5 means no new value destination exists. `trustake_batch` checks a signature only
from the user (enqueue, cancel). It reads `Access` and `UserStatus` for `paused` and
`whitelisted` respectively, and both can only gate or refund. The Staker upgrade authority, as
sole writer of those accounts, therefore gains only gating and refunding power. Everything else
is the existing SPL manager power. ∎

**Necessity: R5 fails if the custody code is upgradeable by a TruFin key `K`.** `K` can replace
the program with one that transfers `Batch(e)` lamports and `Vault(e)` tokens to itself. That is
principal, so by Lemma NC this is strictly new trust.

**Smallest change.** Make `trustake_batch` immutable (revoke the upgrade authority), or put it
behind a timelock of at least `t_settle + t_claim` with an announced upgrade. During that window
anyone can push all claims (permissionless) and depositors can `cancel`, so nothing remains in
custody when an upgrade lands. The second option needs a watcher (a liveness assumption).

**Residual new trust (not in keys).** Immutability means a bug in `trustake_batch` cannot be
patched. This is an operational risk, not a key-holder power. One governance action is also
needed: the SPL manager's one-time `SetFundingAuthority(SolDeposit → trustake_batch::deposit)`.
