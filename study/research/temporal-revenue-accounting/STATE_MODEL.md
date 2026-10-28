# State model

Executable form: `model/temporal_model.py`. Checks: `model/run_checks.py` (54 assertions, verdict PASS
in `model/results.json`). All integers. The source citations below are to
`study/solutions/challenge-I.1/upstream/spl-2.1.1/` (P = processor.rs, S = state.rs).

## 1. Variables

| Symbol | Meaning |
|---|---|
| `E` | `Clock.epoch` |
| `ρ` | `Rent::minimum_balance(200)` (1,666,240 on mainnet; 2,282,880 locally) |
| `m` | minimum delegation (10⁹ on mainnet) |
| `λ` | `stake_pool.last_update_epoch` |
| `T`, `S` | recorded `total_lamports`, `pool_token_supply` |
| `Σ` | mint supply |
| `R` | reserve lamports |
| `v_i`, `d_i`, `A_i`, `λ_i` | actual lamports, `delegation.stake`, cached `active_stake_lamports`, entry `last_update_epoch` of `V_i` |
| `τ_i`, `x_i` | cached and actual transient lamports |
| `ω` | `EpochRewards.active` |
| `Θ*` | final `T` of a correct, complete `VLB(no_merge=true)` + SPB with no interleaving (I.1's definition) |
| `D_T = Θ* − T`, `D_S = S − Σ` | the two gaps |
| `C = (R − ρ) + Σ(A_i + τ_i)` | cached total. SPB sets `T := C`. |

Revenue items carry an explicit **stage**, one per row of the mandate. They are never merged:

| Stage | Definition | On-chain witness | In `Θ*`? | In `C`? | In `T`? |
|---|---|---|---|---|---|
| `EARNED` | economically earned in epoch `e`, no entitlement recorded (tips in a TDA, vote credits accruing) | TDA lamports; vote credits | no | no | no |
| `ASSIGNED` | entitlement fixed (merkle root uploaded; reward partition computed) | TDA `merkle_root`; EpochRewards partition | no | no | no |
| `CLAIMABLE` | some permitted actor can pay it now | root present, not expired, ClaimStatus absent | no | no | no |
| `CREDITED` | lamports are in a counted pool account (`R`, `V_i`, or `X_i` with `τ_i ≠ 0`) | account lamports | **yes** | only if in `R` | no |
| `CACHED` | reflected in `A_i` (or in `R`, which SPB reads directly) | validator list | yes | yes | no |
| `RECORDED` | reflected in `T`; the epoch fee has been minted on it | pool account | yes | yes | yes |
| (`PRICED`) | in the price used by DepositSol and WithdrawStake | same as RECORDED, because both read `T,S` only | yes | yes | yes |

For Jito tips, `ASSIGNED` and `CLAIMABLE` coincide once the root is uploaded. For native inflation,
`ASSIGNED`, `CLAIMABLE` and `CREDITED` happen inside the runtime's reward window with no claimant.

The pool *owns* an item only from `CREDITED` on. Before that it is an entitlement of the stake account
under a third-party program (Jito) or the runtime. The entitlement is lost on expiry
(`expires_at = e + 10` observed).

## 2. Transitions

Each row gives the exact deltas, guards and minimum signer. "—" means unchanged.

| Transition | Guard | Signer | `R` | `v_i` | `d_i` | `A_i` | `T` | `S` | `Σ` | `D_T` | `D_S` | Stage effect |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `epoch_tick` | slot crosses boundary | cluster | — | — | — | — | — | — | — | — | — | `ω := true`; `λ < E` |
| `pay_inflation(i, a)` | `ω` | runtime | — | +a | +a | — | — | — | — | +a | — | EARNED→CREDITED |
| `end_rewards` | all partitions paid | runtime | — | — | — | — | — | — | — | — | — | `ω := false` |
| `earn_tip(i, a)` | — | searchers | — | — | — | — | — | — | — | 0 | — | →EARNED (TDA) |
| `upload_root(e)` | `E > e` | Jito upload authority (Tip Router NCN) | — | — | — | — | — | — | — | 0 | — | EARNED→CLAIMABLE |
| `claim(i, e)` | root present, not claimed, not expired | **any fee payer** (Tip Router has no caller check, [Src]) | — | +a | — | — | — | — | — | **+a** | — | CLAIMABLE→CREDITED |
| `donate(R, a)` | — | any | +a | — | — | — | — | — | — | +a | — | →CREDITED |
| `donate(V_i, a)` | — | any | — | +a | — | — | — | — | — | +a | — | →CREDITED |
| `VLB(I)` | `¬ω` (P:1884) | any | +Σ_{i∈I} e_i | −e_i | — | := v_i − e_i | — | — | — | 0 | — | CREDITED→CACHED for `V_i`, `i ∈ I` |
| `SPB` | every `λ_i = E` (P:2236) | any | — | — | — | — | := C | := Σ + f | += f | `Θ* − C` | 0 | CACHED→RECORDED |
| `DepositSol(L)` (via Staker) | `λ = E` (P:2703); whitelisted; not paused | user + Staker deposit PDA | +L | — | — | — | +L | +n | +n | 0 | 0 | — |
| `WithdrawStake(p, i)` | `λ = E` (P:2847); source rules | holder | — | −ℓ | −ℓ | −ℓ | −ℓ | −b | −b | 0 | 0 | — |
| `Burn(p)` | — | holder | — | — | — | — | — | — | −p | 0 | +p | — |
| `add_validator` (Staker) | owner | owner | (+q then −q) | new `V` with `q` | — | new `A = q` | — | — | — | +q | — | owner gift →CACHED |
| SetFee / SetManager / SetFundingAuthority | SPL manager | manager | — | — | — | — | — | — | — | — | — | governance (separate class) |

In these rows:

* `e_i = max(0, v_i − d_i − ρ)` (P:2085-2098);
* `n = floor(L·S/T)`, or `L` if `T = 0` or `S = 0` (S:162-171);
* `fee_w = ceil(p/1000)`, which is 0 if the burn source is the manager fee account (P:2861-2872);
* `b = p − fee_w`, and `ℓ = floor(b·T/S)` (S:176-186);
* `f = floor(S·φ/(T+r−φ))`, with `r = max(C − T, 0)` and `φ = ceil(5r/100)` (S:241-255).

## 3. Invariants and lemmas (proved by hand; executed in `run_checks.py`)

**L1 — Recognition is the only path from CREDITED to PRICED.** DepositSol and WithdrawStake read only
`T` and `S`. Only SPB writes `T` other than by the operation's own `±L` / `±ℓ`, and SPB uses `C`. `C`
moves only through VLB (for `V_i`) or directly (for `R`). So a credited item is priced iff a VLB of
its entry (for `V_i`) and then an SPB have executed after the credit.

**L2 — Freshness is not reconciliation.** `λ = E` is set by the first SPB of the epoch and is never
cleared within the epoch. No transition except `epoch_tick` makes `λ < E`. A credit after SPB leaves
the pool fresh with `D_T = a > 0`. [Model check: "late credit leaves the pool fresh"; Local: step
"after late credit"; Chain: `simulate_theta.json`]

**L3 — Inflation is always priced before use.** The guards chain as follows:

* `pay_inflation` requires `ω`;
* VLB requires `¬ω`;
* SPB requires every `λ_i = E`, which only a VLB in epoch `E` sets;
* DepositSol and WithdrawStake require `λ = E`, which only SPB sets.

So every inflation credit for epoch `e` is RECORDED before any price-sensitive operation of epoch
`e+1`. [Model check "inflation for epoch e"; Chain: effective slot ≤ 648 < first SPB ≥ 781 in all 14
epochs read.]

**L4 — Late credits are recorded at most one epoch late, by the next epoch's first maintenance.** A
credit at `(E, s)` after that epoch's last SPB stays out of `T` until the first SPB of `E+1`, which
needs a full VLB. Every VLB sweeps every usable delegated `V`, so the credit cannot be skipped. On
mainnet, 178/178 claims were recorded at the next epoch's first maintenance. [Chain]

**L5 — Commutativity of the asset total.** For a credit `a` and a deposit `L` within one epoch,
followed by complete maintenance, the final `T` is independent of order (`T₀ + a + L` either way). The
final `S` is not:

```
S_late − S_rec = floor(L·S₀/T₀) − floor(L·(S₀ + f_a)/(T₀ + a)) + (f_late − f_rec) ≥ 0
```

The difference is the depositor's extra tokens; it is ≈ `L·S₀·a·0.95/(T₀(T₀+a))` up to rounding.
Order changes the allocation, not the assets. [Model checks "final T invariant", "final S differs"]

**L6 — Manager-fee value is invariant to recognition time.** The fee's lamport value is
`φ(T+r)/(T+r)` either way, up to ≤ 2 lamports + `⌈T/S⌉` of floor error. The manager is neither a
winner nor a loser *as fee recipient*. As a holder (78% of supply on mainnet), the fee account is
diluted like any holder. [Model check]

**L7 — Credit position inside the window is irrelevant.** Between the epoch's last SPB and the next
epoch's first SPB, a deposit mints the same tokens whether it lands before or after a credit, because
neither changes `T,S`. The window is the entire remainder of the epoch, not the gap between a claim
and a sweep. [Model check "deposit before or after the claim mints the same"]

**L8 — Lag shift.** If every epoch's tips `z_e` are recorded at the start of `e+2` (earned in `e`,
credited in `e+1`, swept at `e+2`), consider a holder of constant share entering at `a` and leaving at
`b`.

* That holder receives `Σ_{e=a−1}^{b−2} z_e` instead of `Σ_{e=a}^{b−1} z_e`.
* The difference is `z_{a−1} − z_{b−1}`, a boundary term.
* Over a long holding, the lag redistributes only the first and last epoch's tips.
* Native inflation has the analogous one-epoch shift: `infl_e` is recorded at the start of `e+1`, and
  any deposit made in `e` shares it. That is generic to SPL pools.

[Model: `lag_lemma_examples`]

**L9 — Gaps are non-negative, and maintenance recognises rather than reverses.** This restates I.1:
`D_T, D_S ≥ 0`. No transition here takes value back from a depositor who entered at the stale price.
Later maintenance only moves the credit into `T`, which raises the depositor's tokens' value.

## 4. Partial functions and failure domain

`Θ*` is undefined while `ω = true` (VLB reverts), and before epoch 1 on a fresh local cluster (I.1).
Within the window that matters here — after the first SPB, outside `ω` — the mainnet simulation
succeeded at 74,507 CU for `n = 4`.

A wrong V/X pair is silently skipped (P:1925-1946), so a "maintenance" built with stale seeds can
succeed without recognising a credit. That is relevant for third-party maintainers (I.1 D1).
