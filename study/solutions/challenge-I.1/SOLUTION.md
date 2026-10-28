# Challenge I.1 — Two Ledgers

Independent solution, repository `17886b4027ace3b098e72b69cb42307409b1d6a5`.
Only I.1 is addressed. No hint or assumption-ledger text was read before this
solution and its five companion documents were saved. See VERIFICATION.md for
the evidence boundary; a Python execution is not a validator execution.

## Result and scope

For the specified fixed cell, both **`D_T >= 0` and `D_S >= 0` hold**, on the
domain of successful canonical observation. There is no reachable negative-gap
transaction witness within that transition system. In fact the proof establishes
the stronger sandwich `0 <= Sigma <= S <= T <= C <= H`, defined below, at
fresh instruction boundaries. Ordinary transactions can make either gap strictly
positive. A pool epoch stamp is not a balance reconciliation.

This is a theorem about SPL Stake Pool **2.1.1**, native Stake **5.1.0**, original
SPL Token, fixed `m=1,000,000,000`, fixed stake-account rent `rho=1,666,240`,
the canonical initialized pool, and successful instructions of the inspected
programs. Manager reconfiguration is included; it does not convey the pool's
withdraw-PDA signature to the manager. Program upgrades, arbitrary hard-fork
account rewrites, confiscation/slashing not implemented by these programs, and
changes to the specified rent are not transitions of this fixed-code theorem.
They are identified explicitly in the writer table, rather than silently
assumed harmless. The actual deployed binaries were not verified.

`Theta*` is **not an unconditional observation function on arbitrary fresh
serialized states or arbitrary calls**. It is a partial function with invocation,
runtime, arithmetic and CPI preconditions. For ordinary states reachable from
initialization in the fixed mainnet cell, properly constructed complete updates
outside reward distribution succeed (with sufficient transaction resources),
and their total is independent of entry order/chunking. Legacy Stake can fail
even on a correctly formed call because it protects stored rent; details and
the exact failure inequality are in WELL_DEFINEDNESS.md. Malformed calls do not
disprove existence of a canonical successful observation.

## Exact state and arithmetic

`T = stake_pool.total_lamports`; `S = stake_pool.pool_token_supply`;
`Sigma = pool_mint.supply`; `E = Clock.epoch`;
`lambda = stake_pool.last_update_epoch`. Fresh means `lambda=E`, not that
validator-list balances equal current lamports. Actual code rejects `< E`;
reachable clocks/stamps never produce `lambda>E`.

`Theta*(x)` is the final `T` after correctly addressed
`UpdateValidatorListBalance(no_merge=true)` on every entry, then
`UpdateStakePoolBalance`, without intervening external changes or epoch changes.
The observation is hypothetical: its manager-fee mint does not redefine
`Sigma(x)`. `D_T=Theta*(x)-T(x)` and `D_S=S(x)-Sigma(x)` are signed mathematical
integer differences, not wrapping u64 subtractions.

Let `R` be reserve lamports, `A_i,tau_i` cached validator/transient balances,
`v_i,x_i` their actual balances at the recorded PDA seeds. Let
`rho_a = Rent.minimum_balance(account.data_len())`, and `q=rho+max(m,1,000,000)`
`=1,001,666,240`. In the reachable reserve `R>=rho_R` and its length is 200.
Define the **cached total**

```
C = (R saturating_sub rho_R) + sum_i(A_i + tau_i).
```

For a usable delegated V (both authorities are the pool withdraw PDA and lockup
equals the pool lockup), set `g_i=max(0,v_i-d_i-rho_Vi)`, where `d_i` is delegated
stake. Its observation contribution `F_i` is `v_i` for statuses Active,
DeactivatingValidator, DeactivatingAll, and `g_i` for DeactivatingTransient or
ReadyForRemoval. A usable Initialized V contributes **all `v_i`**, because it is
merged into reserve even under `no_merge=true`. Other V states contribute zero.
Let `G_i=x_i` exactly when `tau_i != 0` and X decodes as usable Initialized or
Stake, otherwise zero. On the successful, well-funded observation domain:

```
H = R - rho_R + sum_i(F_i + G_i) = Theta*.
```

For underfunded or arbitrary states use the operational formula instead: add
all sweeps and Initialized-V merges to R, apply reserve saturation once, then
add post-observation A and tau. Do not substitute total lamports at every known
PDA: unreferenced transients, ephemerals and zombies are generally excluded.

Exact price operations (P=upstream/spl-2.1.1/processor.rs; S=its state.rs):

```
n(L) = L if T=0 or S=0, else floor(L*S/T)                 S:162–171
fee(p,a,b) = 0 if b=0, else ceil(p*a/b)                   S:939–949
b = p - fee(p,1,1000)                                   P:2861–2872
ell0 = 0 if S=0 or b*T<S, else floor(b*T/S)               S:176–186
kappa = ceil(T/S), subject to checked T+S-1 arithmetic   S:261–265
r = max(C-T,0); phi=ceil(5*r/100)
f = 0 if r=0; r if T+r=phi or S=0;
    otherwise floor(S*phi/(T+r-phi))                     S:241–255
```

Withdrawal fees are transfers, not supply destruction. For ValidatorRemoval,
require `v<=ell0<=v+kappa` (saturating upper bound); replace `ell0` by `ell=v`
**before** subtracting it from T and splitting stake (P:3027–3042,3068–3107).
Thus truncation changes price/claims but contributes **zero** to either gap.
The protocol model's suggestion that truncation itself increases `Theta*-T`
(`PROTOCOL_MODEL.md:446`) is not supported by the implementation.

## (a) Proof

INVARIANT_LEMMAS.md gives the induction, including the stronger cache and
authority invariants. Initialization establishes equality. Deposits and
withdrawals move recorded and observed assets by the same integer amount;
mint and burn bookkeeping moves S and Sigma by the same amount. External
credits add only nonnegative observed assets; external burns decrease Sigma.
Rebalancing conserves previously accounted assets and can incorporate excluded
prefunding. Cache refreshes cannot reduce C below T, and C cannot exceed H.
UpdateSPB sets `T=C` and, after its fee mint, `S=Sigma`.

This is a source-based mathematical proof, not a machine-checked proof of all
Solana execution. Its explicit runtime assumptions, failure domain and external
writer boundary are part of the claim. No proof is asserted across arbitrary
program upgrades or cluster account edits.

## (b) Divergences and completeness

WRITER_ENUMERATION.md inventories the complete read set, its legal writers,
authority classes, signed deltas, freshness, and neutralization. The principal
positive mechanisms are: reserve credits; usable listed validator/transient
credits; owner-funded validator adds; incorporation of previously excluded
prefunding; external burns; cluster stake rewards when the observation is
available. Reconciliation reduces gaps; changing membership may discard only
uncached optional contributions. Lamport credits can come from System transfer,
native Stake withdraw, Token account closure, or any other program debiting its
own account, not just the System Program. Manager-enabled WithdrawSol can route
its payout back into a counted pool account, making a donation while burning.

Zero-effect cases matter: Token transfers, native delinquency deactivation,
vote commission/credits changes before rewards, ordinary rebalances, ignored
PDA refills, and all Staker administration instructions. Epoch transitions
break freshness. A rent increase can decrease H and disprove the asset inequality
in an **extended changing-parameter model**; it is not a transaction witness
inside the fixed cell.

## (c) Neutralization

Neutralization here means reconciling the ledgers, not undoing a donation,
restoring burned tokens, or reversing fee distribution. Append correct VLBs
then SPB after a transaction's mutations, or put them before a later price-sensitive
operation. For reserve-only credits, known accurate cache, owner Add with no
prefunding, or supply-only burns, SPB alone suffices. V/X donations require their
VLB refresh before SPB. Updates require no owner, whitelist, stake-manager or
SPL-manager signature. A client can run them unconditionally: detecting a gap
first is unnecessary, though reading the current account list/seeds is necessary.

Atomic composition requires that the action's signer cooperate and that all
instructions/accounts fit one transaction. An honest observer cannot append to
someone else's already signed/included transaction. Large lists require chunks;
multi-transaction maintenance is not atomic and does not exclude interleaving.
Cluster events cannot be part of a user transaction. Reward-distribution guards
and genuine Stake failures require waiting or another repair; an update that
reverts does not neutralize anything. See each table row and the legacy failure
discussion for the exceptions.

## (d) Definedness and order

See WELL_DEFINEDNESS.md for the exhaustive branch audit of no_merge, both native
Stake cells, SPL 2.0.3 comparison, bad account handling, error propagation, fee
calculation, and order independence. No-merge avoids transient merge/deactivation
branches; it does **not** avoid the validator sweep or Initialized-validator
merge. Wrong pair addresses are silently skipped, so a successful instruction
is not proof that the requested entries were observed. Correct complete
coverage is necessary even while lambda=E.

## Evidence and unresolved boundaries

The Python model passed 527,560 bounded arithmetic cases, 5,000 transitions of
a restricted valid subset, 24 chunk orders, and deterministic mainnet-parameter
traces. WITNESSES.md records the exact starting states and signatures for the
source-derived traces. No transaction was executed on a local validator. The
available validator is 2.0.15/legacy; it was deliberately not used as evidence
for Stake v5 behavior. The mainnet runtime version/feature inventory and deployed
program hashes are unknown, so completeness is relative to the specified source
transition system, not an empirical audit of all current mainnet programs.

Files: INVARIANT_LEMMAS.md, WRITER_ENUMERATION.md, WITNESSES.md,
WELL_DEFINEDNESS.md, VERIFICATION.md, model.py, model-results.txt, and upstream/.

## Addendum (second session, 2026-10-28)

The text above was left unchanged. Two of its evidence statements are superseded:

* "The actual deployed binaries were not verified." The mainnet `SPoo1…` binary has now
  been fingerprinted (VERIFICATION.md §2). Its processor strings are 2.1.x even though its
  security.txt says `program@v2.0.3`. This is consistent with the stated cell.
* "No transaction was executed on a local validator." A harness (`harness/`) has now run
  against the deployed SPL binary on a local agave 2.0.15 / legacy-Stake validator. It
  validator-executes the following, with exact integer agreement:
  * the one-transaction positive witnesses for reserve credit, validator-account credit, and
    external burn;
  * permissionless later neutralization by a signer with no pool role;
  * atomic neutralization;
  * D_T/D_S invariance under DepositSol and WithdrawSol;
  * the `no_merge` sweep mutation;
  * the wrong-pair silent skip;
  * an `UnsupportedSysvar` failure of VLB(no_merge=true) at a fresh epoch-0 pool.

None of this changes the verdicts: both inequalities hold in the fixed cell; Theta* is a
partial function with the failure conditions in WELL_DEFINEDNESS.md. The epoch-0 failure is a
concrete instance of that document's "EpochRewards sysvar read fails" row. Items still not
reproduced on a validator are listed in VERIFICATION.md §5.
