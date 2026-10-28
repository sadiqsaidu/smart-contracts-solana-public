# I.1 — Minimal traces, reachability, and failed counterexamples

Independent first solution. All traces below are **source-derived and/or exact
integer model executions**, not transactions executed on a validator.

## Negative witnesses in the target cell

There are none under the fixed-cell assumptions proved in INVARIANT_LEMMAS.md.
Both inequalities hold; a “fewest transactions to make a gap negative” therefore
has no finite value. Do not confuse the following one-transaction positive-gap
witnesses with counterexamples to a nonnegative inequality.

## Common reachable base

Use fresh epoch E=100 outside reward distribution, canonical pool/list/mint
identities, default lockup, SPL withdraw PDA mint/native stake authority, no
freeze authority, 5/100 epoch fee, 1/1000 withdrawal fee, zero deposit/referral
fee. Create and initialize the reserve with `R=24,001,666,240` lamports and both
authorities assigned to the pool PDA. Initialize an empty mint with that mint
authority and a valid manager token account. SPL Initialize with empty list
mints `24,000,000,000` tokens to the manager and sets

```
T = S = Sigma = C = Theta* = 24,000,000,000
R = 24,001,666,240; lambda = E = 100; D_T = D_S = 0.
```

This is produced by valid initialization operations, not by assigning arbitrary
pool balances in a genesis fixture. Account-creation payers sign their creation
transactions; the manager signs SPL Initialize; native Initialize requires no
signature for the supplied authority keys. Staker authority configuration can
be installed normally by the SPL manager. Initialization's pre-minted capital
belongs to the fee account, which makes later manager burns/withdrawals legal.
Source: SPL 2.1.1 processor.rs:646–889. model.py starts from the exact resulting
integer state; it does not execute those setup instructions.

## W1 — One-lamport reserve credit, one transaction

An unrelated funded System account signs `SystemProgram::Transfer(1, reserve)`.
The reserve need not sign. End state: R increases by 1, T,S,Sigma unchanged,
Theta* and C increase by 1. `(D_T,D_S)=(1,0)`, lambda unchanged.
For an already funded reserve the transfer creates no rent-transition issue.
Zero transactions cannot change a starting equal state, so one is minimal for
strict asset divergence. `[transfer, SPB]` in one signed transaction leaves
both ledgers reconciled; fee mint may be zero from integer rounding.

## W2 — Burn seven raw token units, one transaction

Starting from any equal fresh state with a holder balance at least seven,
the holder (or valid approved delegate) signs `Burn(7, mint)`.
`Delta Sigma=-7`; `Delta S=Delta T=Delta Theta*=0`; `(D_T,D_S)=(0,7)`.
Source: Token processor.rs:580–659. `[Burn(7), SPB]` neutralizes it atomically
and does not restore the burned tokens. One token unit would also suffice.
The recorded model trace performs this after W3 refresh:

```
T=Theta*=25,001,666,240
S=24,048,173,275; Sigma=24,048,173,268; D_S=7.
```

No public holder can invert this witness by MintTo: the mint authority is a PDA
whose signature is unavailable outside the inspected SPL code.

## W3 — Owner-funded AddValidator, one transaction

Start from the common base. Choose a valid initialized vote account not in the
list and an unused validator PDA at the requested seed, with no prefunding.
Owner signs Staker add_validator. The wrapper transfers
`q=1,001,666,240` to reserve; SPL staker-PDA-authorized Add allocates V, splits
q from reserve and delegates `m=1,000,000,000`. Reserve returns to its initial
balance. List gains `A=q,tau=0,last_update=E,Active`; lambda remains E.

| Quantity | Before | After |
|---|---:|---:|
| T | 24,000,000,000 | 24,000,000,000 |
| S and Sigma | 24,000,000,000 | 24,000,000,000 |
| Theta* and C | 24,000,000,000 | 25,001,666,240 |
| D_T | 0 | 1,001,666,240 |
| D_S | 0 | 0 |

The owner supplies q plus transaction fees from its own external balance.
The valid vote account need not sign Add. Sufficient list capacity and reserve
rent floor hold. Source: L/validators.rs:86–166; P:894–1036.
The repository test `tests/add_validator_donation.test.ts:396–422` asserts the
unchanged T/freshness distinction; it was inspected, not run here.

SPB afterward computes `r=q`, `phi=50,083,312`,
`f=floor(24,000,000,000*50,083,312/24,951,582,928)=48,173,275` tokens.
It sets T=25,001,666,240 and S=Sigma=24,048,173,275.
Appending SPB to Add produces that final state atomically, provided other
entries were accurate. Fresh V prefunding instead requires VLB to capture it.

## W4 — Donation to V exposes why SPB alone is insufficient

From W3's fully refreshed equal state, transfer one lamport to V.
V has `v=q+1,d=m`; cached A remains q. H increases by 1, C does not.
Calling SPB alone leaves `D_T=1`. VLB(true) sweeps exactly one lamport to R and
rewrites A=q; C increases by 1. SPB now sets T=H. All instructions need only
the donor/fee-payer signature. The model executes this integer trace.
For X with tau>0, substitute an x credit and re-read tau; there is no X sweep
under no_merge. At tau=0 the same transfer is not observed at all.

## W5 — ValidatorRemoval rounding is NOT a negative or positive gap witness

Construct another reachable equal pool with initial capital 10,000,000,000,
R=10,001,666,240, empty list, and all tokens initially in the fee account.
If originally bound to Staker, the SPL manager may install a signing staker;
direct SPL Add then transfers q from reserve to a new V, without an owner
donation. Thus T=S=Sigma=Theta*=10,000,000,000, V=A=q, tau=0,
R=9,000,000,000. This setup is reachable by valid instructions and uses the
manager actor allowed by the problem; it is not a claim that a public outsider
can bypass Staker's Add authorization.

Prepare a separate 200-byte Stake-owned Uninitialized withdrawal destination,
pre-funded with rho by its creator. Its balance is outside pool accounting.
The manager fee-token owner signs WithdrawStake with
`p=b=q+1=1,001,666,241`; the source is the fee account, so withdrawal fee is zero.
There are no Active A or tau above `theta=q+kappa=q+1`; V=A=q and tau=0.
`kappa=1`, `ell0=b`, and `v<=ell0<=v+1`. SPL truncates ell to q. Native v5 full
Split copies the m delegation, transfers q and clears source data; destination
rent is sufficient; user authority is then installed. A becomes zero and status
ReadyForRemoval. All source/list subtraction constraints pass.

```
T' = Theta*' = 8,998,333,760
S' = Sigma' = 8,998,333,759
D_T' = D_S' = 0.
```

The one-lamport mismatch is between quoted and actual payout, not between
recorded and observed totals. model.py checks these exact numbers.

## W6 — Prefunding and orphan attempts

These are exact source transition formulas; no validator execution is claimed.

* Add: prefund unused System V by p; Add includes q+p but initially records q.
  Direct Add gives +p divergence; wrapper Add gives +(q+p). Never negative.
* Increase, existing X: a fresh System Y prefunded by y receives L+rho and is
  merged in full. Pool observation increases by y, tau initially by L+rho only.
* Increase, fresh X: Y's prior y remains after splitting exactly L+rho. The
  excluded remainder equals the external prefund; no original recorded amount
  vanished. On v5 a nonzero y makes the Split partial, so require destination
  rent and remaining source delegation. For example y=q and X prefund p=rho
  with L=m satisfy both: Y retains q with m delegated, X receives q+p.
  The pool gains p, while y remains excluded.
* Decrease incorporates Y's full balance and sets tau to actual x; gains are
  included prefunding, not losses of reserve rent.
* V5 merge/full-split-and-refill leaves 0-byte Stake-owned data. No Initialize
  is legal; both usable-state checks fail, so its balance was never accounted.
* Legacy refill leaves 200-byte Uninitialized data. Initialize with outsider
  authorities fails SPL 2.1.1 usability; Initialize with pool authorities is an
  irrevocable gift relative to the initializer. Cleanup of a zero-cache entry
  may discard an optional observed gift, but cannot erase cached backing.

Source: P:1322–1496,1631–1782,193–201,1967–2167; K:134–160,582–627,909–978.
The repo poisoning tests describe legacy behavior; they are not evidence that
v5 zero-byte accounts can be initialized.

## W7 — A negative asset gap requires leaving the fixed-rent theorem

Extended model only: initialize an empty pool with R=rho+100, T=S=Sigma=100,
then let the cluster increase the current reserve rent by one without an epoch
tick. SPB's hypothetical total is `max(R-(rho+1),0)=99`, so D_T=-1 while lambda=E.
There are **zero user transactions after the equal start**, but one privileged
cluster parameter event. It is not a mainnet-2026 transaction counterexample;
rho no longer equals the specified constant. model.py checks the integer result.
If the intended reachable-state quantifier includes arbitrary rent-changing
histories, the asset inequality must be qualified by this counterexample,
rather than asserted unconditionally. The token-supply inequality survives it.

## W8 — Legacy observation failure; historical reachability matters

In a legacy runtime, create and delegate a validator when rent is r0=2,282,880,
so d=m and v=m+r0, and refresh the pool. A cluster rent reduction to
r=1,666,240 while retaining legacy Native Stake leaves the stored r0 unchanged.
With lambda still E, SPL 2.1.1 VLB(true) requests a sweep of 616,640 but legacy
Stake requires h+r0=v, so fails InsufficientFunds. No user signature can waive
that balance check. Further donation to V does not repair it.

This is reachable **in a history that permits that rent event and retains legacy
Stake**, not from initialization at immutable r=1,666,240. It is a symbolic
legacy comparison backed by exact source constraints and model arithmetic,
not a reproduced mainnet incident. In Stake v5 the exact same lamport/delegation
numbers permit the sweep, because current r is authoritative.

## Attempts to falsify the results

Checked: fee ceiling versus floor; raw supply burns; manager fee exemption;
post-truncation T subtraction; VLB post-merge re-read; zero tau gating;
prefunded Y partial-split minimums; ignored/status-gated V; reserve saturation;
staker versus native withdrawer authority; vote operator permissions; wrong-pair
skips; and atomic rollback on post-CPI errors. None supplies a negative mainnet
fixed-cell witness. Source-based reachability arguments are not substituted
for local execution: all unexecuted transaction recipes remain labeled as such.

## Addendum (second session, 2026-10-28): which traces were executed

The header above ("not transactions executed on a validator") was true when written.
Since then, `harness/results.json` validator-executes these traces against the deployed SPL
binary (legacy Stake, rho = 2,282,880):

* W1-type reserve credit: z = 1,234,567 gave (D_T, D_S) = (1,234,567, 0).
* W2-type burn: 7 raw units gave (0, 7).
* W4-type V credit: z = 777,777 gave (777,777, 0). SPB alone would miss it; VLB swept
  exactly 777,777 to the reserve.

In each case the actor was an unprivileged signer or an ordinary holder, and the pool stayed
at lambda = E. The pool and validator were created by SPL instructions directly, not by
model fixtures. W3 (Staker add_validator), W5 (removal truncation), W6, W7 and W8 remain
source- or model-only (VERIFICATION.md §5).
