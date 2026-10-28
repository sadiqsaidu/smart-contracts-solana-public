# I.1 — Inductive transition lemmas

Independent first solution. Source aliases: **P** and **S** are the archived
`upstream/spl-2.1.1/{processor,state}.rs`; **K** is
`upstream/stake-v5.1.0/processor.rs`; **L** is
`programs/staker/src/instructions/` in the repository. All claims concern
successful complete instructions, not intermediate CPI states or failed
transactions. A failed transaction rolls back its program effects; its external
fee payer is not one of the protected pool asset accounts.

## Inductive hypotheses (IH)

Use C,H,F,G from SOLUTION.md. Strengthen the two requested inequalities to:

1. `0 <= Sigma <= S <= T <= C <= H` in fresh states with successful observation.
2. `R>=rho_R`; reserve is Initialized, Stake-owned, with both authorities equal
   to the pool withdraw PDA and default lockup; its account length is unchanged.
3. A positive cached A is backed by a usable listed V in a counted status;
   `A_i<=v_i`. A positive tau is backed by the recorded usable X, `tau_i<=x_i`.
   More generally `A_i<=F_i` and `tau_i<=G_i` handle Initialized recovery states.
4. Mint authority is the pool withdraw PDA, freeze authority absent; only SPL
   mint paths can exercise it. List and pool data have their prescribed owners,
   addresses and valid encodings. Distinct validator votes/seeds identify distinct
   V/X accounts and do not alias reserve (standard PDA collision assumption).
5. Privileged configuration can change which public SPL operations are callable,
   but neither SetManager nor SetStaker changes the stake accounts' native
   authorities. No inspected SPL operation exports a withdraw-PDA signature.

IH is relative to fixed versions/rent, ordinary legal writers, and the initialized
canonical pool. Arbitrary account injection, slash/hard-fork rewrites and software
upgrades are not justified by IH. Domain failures are handled separately; they
are not assigned artificial signed differences.

## Base case — SPL Initialize

P:646–889 checks empty mint supply, mint/withdraw authority, absent freeze
authority, empty list, rent exemption, reserve Initialized state, default lockup
and both reserve authorities. It sets `T=S=R-rho_R` and mints that many tokens
to the manager. Hence `Sigma=S=T=C=H`, `lambda=E`. This also permits T=S=0.
Staker Initialize only creates access/agent/manager records and does not mutate
these pool accounts (L/initialize.rs:7–68).

## L1 — DepositSol and both slippage variants

P:2652–2795 transfers L into R, mints total `n(L)` across user/manager/referral
accounts and adds exactly L to T and n to S. Thus
`Delta(T,C,H)=(L,L,L)`, `Delta(S,Sigma)=(n,n)` and both gaps are unchanged.
Integer floor is not a gap: it occurs identically in S and actual mint supply.
Under `S<=T`, `n<=L`; special S=0 or T=0 branches mint L, preserving S<=T.
Success checks and checked arithmetic exclude overflow and zero user output.

Staker `deposit` (L/staking.rs:83–143) signs with its deposit PDA after whitelist
and pause constraints. `deposit_to_specific_validator` (276–395) composes
DepositSol(L+rho) and L3. Its local unchecked `amount+rent` can wrap depending
on compilation overflow settings; this cannot mint unbacked tokens: SPL receives
the wrapped amount, and the subsequent huge Increase must itself satisfy all
balance/checked-arithmetic conditions or roll back. The proof uses amounts
actually passed to successful CPIs, not an assumed unbounded local addition.

## L2 — AddValidatorToPool / Staker add_validator

P:894–1036 allocates/assigns V, splits q from R, delegates all V's delegatable
balance, appends `A=q,tau=0,last_update=E`; it writes neither T nor S.
Let a previously excluded, empty System V have prefunding p. Then `Delta C=0`,
`Delta H=p`, `Delta T=0`. `A=q<=q+p=v`; reserve floor is checked.
Staker additionally transfers the owner's q into R (L/validators.rs:86–166),
so `Delta C=q`, `Delta H=q+p`, `Delta D_T=q+p`, `Delta D_S=0`.
When the account is already allocated or Stake-owned, System Allocate rejects;
there is no successful overwrite that loses prior accounted assets.

## L3 — IncreaseValidatorStake / IncreaseAdditionalValidatorStake

P:1503–1784: Active status, usable V, required staker signature, reserve floor,
minimum delegation and recorded transient seed/activation checks. Put `a=L+rho`
(the actual saturating upstream value). R decreases by a and tau increases by a.
No T,S,Sigma change, so `Delta C=0`. Fresh X prefunding p becomes counted,
giving `Delta H=p`. With an existing activating X and ephemeral prefunding y,
all Y lamports merge into X, giving `Delta H=y`. With fresh X and Y, only a
is split from Y: y stays outside H, and `Delta H=p`, not y+p.

This last case must pass native Split. Under v5, if y>0 the split is partial:
X must already have rent, and Y must retain at least m delegated stake.
Typically `p>=rho` and `y>=q`; small y may make the operation fail instead of
producing a state. Full split when y=0 has a separate legal branch
(K:582–627). Orphan Y's remainder is external prefunding, never a debit of
recorded pool principal. No negative divergence follows from its exclusion.

L/validators.rs:349–416 calls the additional variant with a StakeManager-PDA
guard; L/staking.rs:337–386 exposes it atomically after an authorized deposit.

## L4 — Decrease variants

P:1179–1498. Let V lose L and reserve fund h of rent; new/current X acquires
`L+h+p+y`, where p and y are previously excluded prefunding actually incorporated.
For an ephemeral path `h=max(rho-y,0)` and Y is split in full or merged in full.
The list subtracts L from A and sets tau to the **absolute** X lamport balance.
Consequently `Delta H=p+y>=0` and
`Delta C=(old x-old tau)+p+y>=0` (omit old-x term for new X).
T,S,Sigma unchanged. For direct non-ephemeral variants use the same conservation
identity with the actual rent transfer h, possibly zero; already-counted assets
are conserved. Native minimums, rent floors, and active-status/seed/deactivation
checks are success preconditions, not assumptions that every requested decrease
will succeed. L/validators.rs:494–558 uses the additional/reserve-funded variant.

## L5 — RemoveValidatorFromPool

P:1041–1176 changes Active to DeactivatingAll or DeactivatingValidator and
deactivates relevant stakes. These statuses all count V under no_merge. There
is no lamport movement or token change: C,H,T,S,Sigma unchanged. Native activation
flags can reject deactivation; failed calls change none of the ledger quantities.
Minimum Staker actor: owner (L/validators.rs:225–267).

## L6 — UpdateValidatorListBalance(no_merge=true)

P:1851–2170. For each correct pair, a usable X is counted iff old tau!=0. Usable
V Stake sweeps `g=max(v-d-rho_V,0)` to reserve. Its recorded post-sweep A plus the
sweep equals F. Initialized V is fully merged into reserve; A becomes zero.
Therefore `Delta C=(F-old A)+(G-old tau)>=0`. Successful observation preserves H:
sweeps/merges move assets within H. T,S,Sigma are untouched. Repeating an update
is idempotent for H and for C once that pair is current. Wrong pairs are skipped,
preserving IH but not achieving a refresh. Detailed CPI-domain obligations are
in WELL_DEFINEDNESS.md.

## L7 — UpdateValidatorListBalance(no_merge=false)

Same cache lower-bound argument on **successful** calls. Usable X may merge to
reserve or V; usable removed V may merge to reserve; X may deactivate. These are
internal asset movements and valid status transitions. Delegated stake and
rent attribution may change, but total counted assets do not disappear. All
source lamports move on Merge in both native cells; v5 truncates the empty source.
Post-CPI V is re-read (P:2069–2072), avoiding a stale delegation in the sweep.
Freshness is only lambda, so a call can update C while the pool stays fresh.
Merge incompatibility is a failure, never an unexplained successful loss.

## L8 — UpdateStakePoolBalance, including calls WITHOUT preceding VLB

P:2175–2290 reads C and stamps `T'=C`. IH gives `T<=C<=H`. Thus
`D_T'=H-C>=0`; `Delta D_T=-(C-T)` and `0<=C-T<=D_T`.
It computes f from **old S**, mints f if the fee account is valid, then reads
the mint and sets `S'=Sigma'=Sigma+f`. Hence `D_S'=0`, regardless of prior burns.
It is incorrect to resync S before calculating f in a model.

For the fixed fee, `phi<=r=C-T`; if S<=T then
`S*phi <= r*(T+r-phi)`, so `0<=f<=r`. Special S=0 branch also gives f=r.
Consequently `Sigma+f<=S+f<=T+r=C`: the auxiliary S<=T invariant is preserved.
An invalid fee account causes f=0, not a forced failure (P:2240–2247).
Standalone SPB reconciles only C, so validator/transient donations can remain
in H-C. It does reconcile all outstanding external burns.

## L9 — WithdrawStake, all routing branches and slippage variant

P:2800–3144. Let `b=p-fee` and `ell0=floor(b*T/S)>0`.
For ordinary reserve/active/transient withdrawal, `ell=ell0`.
For ValidatorRemoval, `ell=v<=ell0<=v+kappa`, tau=0 and A must equal v at
completion (P:3126–3139); otherwise the entire instruction fails.

The successful CPI moves ell out of counted pool assets; T and the appropriate
cache balance decrease by **ell**. S and Sigma both decrease by b. Thus both
gaps are unchanged for an external destination. Any legal destination that
reintroduces value into the observation set is an additional nonnegative credit,
covered by L13. Remainder floors prevent reserve underfunding and non-removal
stake exhaustion. A positive cache remains backed by the actual remainder.

Since `b<=Sigma<=S` and `ell<=b*T/S`,
`T-ell >= T*(1-b/S) >= S-b`. This proves the auxiliary S<=T inequality without
assuming ell=b or ignoring floor/truncation. In particular, the loss of up to
kappa versus the quoted redemption is **not** a positive or negative D_T delta.

## L10 — CleanupRemovedValidatorEntries

P:2295–2335 and S:754–758 remove only ReadyForRemoval with A=tau=0. C,T,S,Sigma
are unchanged. A removed address may have a later external gift that H would
observe (notably legacy Initialized resurrection); losing its list reference
can reduce H by that optional contribution. It cannot reduce H below C because
the removed cache contribution is zero. V5 zero-byte refills contribute zero.
Thus a blanket assertion that every non-reconciliation H change is positive
would be too strong, even though the requested inequality survives.

## L11 — Manager-enabled DepositStake and WithdrawSol

These are unavailable with TruStake's original signing arrangement, but must
not be omitted when quantifying over manager transitions.
DepositStake (P:2387–2647) measures the post-minus-pre V balance, mints n for
that actual incoming amount, sweeps its SOL portion, adds the actual amount
to T, and sets A to actual post-sweep V. It preserves gaps except for catching
up preexisting cache omissions. The deposited source is external: a counted
pool source cannot be reauthorized to the deposit authority by an outsider.

WithdrawSol (P:3149–3288) burns b, subtracts ell from T and reserve; external
destination gives zero gap delta. If the manager has enabled it and its payout
destination is an included V/X, H is conserved but T drops ell: `Delta D_T=ell`.
If the destination is excluded, the standard debit applies. Source=destination
is rejected by Stake v5. Original configured authority cannot sign this path.
Redelegate is **always rejected** in this SPL version (P:3736–3738), even after
SetStaker; do not infer implementation from its enum presence.

## L12 — External burns and other Token operations

Token 4.0.0 processor:515–661 enforces mint authority and burn authority/balance.
External Burn/BurnChecked changes only `Sigma' = Sigma-b`, `0<=b<=Sigma`, giving
`Delta D_S=b`. Owners, approved delegates (bounded by allowance), and valid
multisig signers qualify. The inspected Token implementation additionally lets
anyone burn from token accounts whose token-owner is System/incinerator
(:614–642); the economic source still contains those tokens.

Transfer/TransferChecked, Approve/Revoke, account SetAuthority, token-account
initialization and zero-balance CloseAccount do not alter Sigma. CloseAccount's
lamport destination can donate to an observed pool asset (L13). Native mint
SyncNative cannot apply to TruSOL. MintTo/SetAuthority(MintTokens) require the
pool PDA, and no inspected external caller can furnish that signature. Freeze
requires the absent freeze authority. Token-2022 extensions are not silently
included in the original-token deployment.

## L13 — External lamport/data writers and representation changes

Any legal credit to R adds its amount to C,H. Credit to a usable counted V or
enabled usable X adds its amount to H; later VLB brings C up. Credit to a
disabled/unreferenced X/Y or zero-byte V5 zombie contributes zero until a legal
instruction incorporates it. Prefunding incorporation is L2–L4, not a second
external payment. An excluded usable Stake V contributes only its sweepable
extra; credit increases that by between zero and the credit amount.

Native Stake, System and Token account closure are distinct credit mechanisms.
Native debit, Split, Merge, Authorize, SetLockup, Delegate, MoveStake and
MoveLamports on accounted pool principal require protected authorities. Validator
operators control vote accounts, not the pool's stake-account authorities.
DeactivateDelinquent is permissionless with vote-history checks, but changes
only deactivation epoch; H under no_merge is unchanged. Changes in effective
stake affect future eligibility, not current counted principal.

V5 drained accounts have length zero (K:619,831,969); Initialize needs length
200 (K:134–160). Legacy Uninitialized resurrection can give control only over
an **already excluded** balance. Initialize to pool authorities is a gift and
then cannot be revoked by the initializer. Initialize to outsider authorities
fails the 2.1.1 usability filter. These cases cannot make cached principal
disappear. Runtime rent collection does not debit rent-exempt accounted assets
under fixed rent. Staker-created rent accounts are outside the observation set.

## L14 — Cluster transitions

At an epoch tick lambda remains old and the fresh predicate becomes false.
Reward payouts credit lamports and delegated stake by nonnegative integers;
they do not decrease accounted value. Once all list entries can be updated,
SPB reestablishes fresh equality. In 2.1.1 the VLB reward guard prevents the
ordinary nonempty pool from becoming fresh partway through payout.

For an extended changing-rent model with well-funded reserve and unchanged
membership, `Delta H=-Delta rho_R`; saturating reserve terms give the exact
general formula. This is a possible negative writer **outside** the fixed-rent
induction. A minimum-delegation change alone changes action guards, not H.
Arbitrary program/runtime upgrades have no invariant-preservation proof here.

## L15 — Every Staker administrative instruction (§3.1 #1–16)

All have zero deltas in the five ledger quantities. This follows by inspecting
their account types, Anchor init/close destinations and bodies, not just by
looking for T/S assignment:

| Instruction | Source in L | Actor / written state |
|---|---|---|
| initialize_staker | initialize.rs:7–68 | one-time initializer; Access, Agent, StakeManager |
| pause, unpause | setters.rs:7–50 | owner; pause flag |
| set_pending_owner | setters.rs:55–80 | owner; pending owner |
| claim_ownership | setters.rs:84–122 | pending-owner signer; Access/Agent |
| set_stake_manager | setters.rs:126–175 | owner; Access/new PDA, old PDA rent to owner |
| add_agent, remove_agent | whitelist.rs:7–82 | agent; Agent PDA; closure rent to signer |
| add_user_to_whitelist | whitelist.rs:87–123 | agent; UserStatus |
| add_user_to_blacklist | whitelist.rs:128–164 | agent; UserStatus |
| clear_user_status | whitelist.rs:169–205 | agent; UserStatus |
| add/remove_third_party_agent | third_party_whitelist.rs:7–75 | agent; custodian PDA |
| third_party_add_user_to_whitelist | same:82–138 | custodian; claim/UserStatus |
| third_party_add_user_to_blacklist | same:145–193 | owning custodian; UserStatus |
| third_party_clear_user_status | same:200–252 | owning custodian; UserStatus/claim closure |
| agent_release_third_party_user | same:259–294 | agent; claim closure |

The close recipients must sign these instructions and cannot be the pool's
unsigned asset PDAs. Subsequent voluntary transfers to the pool are L13.

## L16 — SPL administration and metadata

SetPreferredValidator (P:1789–1848), SetManager/SetFee/SetStaker/
SetFundingAuthority (P:3447–3559), and create/update token metadata
(P:3292–3444) do not change T,S,Sigma or the observation's asset fields.
Fees change future f/n/b; a manager-fee account closure changes whether f is
minted, not C or H. Access/pause/authority changes can affect who can take later
transitions. They cannot be treated as a grant of native stake withdraw authority.

## Conclusion and limits

The base case and L1–L16 establish the requested inequalities for the defined
fixed-cell state machine. They also explain why merely proving matched T/S
bookkeeping is insufficient: one needs the cache sandwich, native authority
protection, excluded-account treatment, and observation-domain proof.
This is not a mechanized proof of the complete VM, cryptography, or uninspected
mainnet runtime extensions; those completeness limits are explicit.
