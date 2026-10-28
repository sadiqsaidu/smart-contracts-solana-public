# I.1 — Read set, writer closure, and neutralization

Independent first solution. **P,S,K,N,B** abbreviate the archived files
`upstream/spl-2.1.1/processor.rs`, its `state.rs`,
`upstream/stake-v5.1.0/processor.rs`,
`upstream/token-4.0.0/processor.rs`, and
`upstream/agave-2.0.15/system_processor.rs`. Local **L/** means
`programs/staker/src/instructions/`. Exact source revisions are in VERIFICATION.md.

## Observation read set and legal writers

| Object / fields read | How used | Legal writers and closure of the search |
|---|---|---|
| Pool owner/type; validator_list, reserve_stake, pool_mint, withdraw bump, token_program_id, manager_fee_account, lockup | address/owner/PDA checks and usability, P:1870–1882,2190–2207; S:269–397,435–464 | SPL Initialize sets identity, lockup and bump; no later inspected instruction changes identities/lockup. SPL manager may replace fee account; only owner program writes data. Runtime loader upgrades are outside fixed code. |
| T,S,lambda,epoch fee,next fees,last-epoch fields | fee calculation, freshness rotation, output; P:2217–2288 | Initialize, deposits, withdrawals, SPB; fees/authorities via SPL configuration; no Staker direct write. |
| List owner/header/length; vote, validator seed, transient seed, A,tau,status,last_update | address derivation, tau read gate, status inclusion, cache sum; P:1900–1967,2099–2167,2227–2235 | SPL Initialize/Add/Remove/Increase/Decrease/VLB/WithdrawStake/DepositStake/Cleanup/SetPreferredValidator routing configuration; data-owner rules exclude direct external writes. |
| R: lamports and data length | reserve rent/subtraction; receives V sweeps and merges | Incoming lamports from ANY legal program; outgoing only Native Stake with pool authorities via inspected SPL CPIs. Native Initialize/Split/Merge/Withdraw govern state/length. No reserve drain/resize in reachable 2.1.1 fixed-rent operation. |
| V at each recorded seed: lamports, data length, decoded state, authorized staker/withdrawer, lockup, delegation.stake, status | no_merge sweep; state/status inclusion; Initialized V unconditional merge, P:1948–1959,2069–2162 | Stake program data and debits; any incoming lamport credit; rewards/cluster; pool controls native authorities; validator vote operator does not. Unusable data decodes are ignored unless a native CPI is attempted on apparently usable data. |
| X at recorded transient seed: lamports, decoded state/authorities/lockup; cached tau!=0 gate | no_merge contributes actual x when usable; P:1967–2064 | Same writers as V; plus gate/seed writers in SPL. Other seeds and all Y are NOT read directly. |
| Mint: initialization/decimals/supply; mint authority and token account during fee CPI | check_mint, fee mint, supply resync; P:2195,2250–2259,2284–2286 | Original Token InitializeMint, MintTo, Burn, SetAuthority; initialization fixes authority to SPL PDA. Transfer is not a supply writer. |
| Manager fee account: owner, data type/state,mint,extensions; token balance during CPI | invalid account suppresses fee; S:295–315 | Token initialization, transfers, burns, close, account authority; manager can point pool to another valid account. Fee recipient may be owned by another signer; account balance is not checked by the SPL validity helper but is checked for overflow during mint. |
| Clock epoch and (through native CPI) timestamp; Rent minimum_balance; EpochRewards.active; StakeHistory and activation-rate semantics | freshness, payout guard, sweep/merge validation; P:1863–1887; K:729–846,909–978 | Runtime/cluster only; ordinary users cannot rewrite sysvars. StakeHistory account supplied to VLB is consumed by legacy CPI; v5 uses its sysvar interface. |
| Account metas, executable program identities, instruction start/count, writable flags, compute budget | invocation validity and ability to commit | Transaction author chooses metas/arguments; runtime enforces permissions. These can make a call fail/skip; they are not successful arbitrary writes to economic state. |

No vote account is directly read by VLB/SPB. Vote authorities, commissions,
credits and delinquency matter indirectly through reward payouts and Stake
instructions. Ephemeral accounts and other transient seeds matter only when a
legal SPL instruction moves their value into the read set. Enumerating only
accounts owned by SPL would miss most of this table.

## Delta table (fresh pre-state)

`(dT,dS)` below means **`(Delta D_T, Delta D_S)`**, not deltas of the stored
fields. Amounts are integers in lamports or raw token units. `z` is an external
credit, `b` an external burn, `p/y` excluded prefunding. All successful transaction
rows keep `lambda=E`; epoch events are marked separately. Failed instructions
have zero program-state deltas. Sources are also developed in INVARIANT_LEMMAS.md.

Neutralization codes: **U** = correct affected VLB(s), then SPB; **S** = SPB
alone if the remaining cache is accurate; **0** = no present divergence;
**W** = wait/repair conditions below. For U/S, atomic composition is available
to the diverging action's signers if it fits a transaction, later execution is
permissionless, and proactive unconditional execution needs no divergence
detection. These qualifications apply to every U/S cell.

| Trigger / class | Minimum actor authority | Fields/accounts affected | Exact delta or bound `(dT,dS)` | Evidence | Fresh afterward? | Neutralization |
|---|---|---|---|---|---|---|
| System Transfer / TransferWithSeed to R | payer/source signer or valid base signer | R lamports | `(z,0)`; generalized reserve saturation gives `[0,z]` for an underfunded symbolic reserve | B:182–281; P:2221–2225 | yes | S |
| System transfer to counted usable V | source signer, no pool permission | v; later sweep R,A | `(z,0)` | P:2073–2127 | yes | U; S alone misses it |
| System transfer to usable recorded X with tau>0 | source signer | x | `(z,0)` | P:1967–2057 | yes | U |
| Credit to disabled X, other X seed, Y, absent/invalid V or zero-byte zombie | source signer | excluded account balance | `(0,0)` now; possible later incorporation below | P:1936–1967,2060–2062,2156–2162; K:134–160,619,969 | yes | 0; update cannot count an unreferenced gift |
| Credit to usable Stake V in ignored status | source signer, such account must exist | v and prospective g | `(max(0,v+z-d-rho)-max(0,v-d-rho),0)`, tight `[0,z]` | P:2081–2097,2124–2126 | yes | U for sweepable part; remaining excluded |
| Credit to usable Initialized listed V, even ReadyForRemoval | source signer; representation must exist | v, prospective merge into R | `(z,0)` when observation succeeds | P:2129–2154 | yes | U; v5 drained zombies are NOT Initialized |
| Native Stake Withdraw from outsider stake to any pool address | outsider withdrawer, plus custodian if lockup requires | external source; destination lamports | same destination-dependent credit formulas | K:729–846 | yes | U/S by destination |
| Token CloseAccount / other program account closure or lamport payment into read set | external close/withdraw authority; program may debit its own account | destination lamports; external source | same credit formulas; closure does not burn nonzero TruSOL | N:665–700; runtime owner debit rule | yes | U/S by destination |
| Staker add_validator | owner signer; staker PDA signs CPI | R,V,list entry | `(q+p,0)`, q=1,001,666,240; p=V prefunding | L/validators.rs:86–166; P:981–1034 | yes | S for p=0 and accurate cache; U otherwise |
| SPL AddValidatorToPool without wrapper donation | SPL staker signer (manager can install one) | R-q, V+q, A=q | `(p,0)` | P:894–1036 | yes | 0 if p=0, U otherwise |
| DepositSol / Staker deposit | whitelisted unpaused signer + Staker deposit PDA; or manager-enabled public deposit | R,T,S,Sigma | `(0,0)` | L/staking.rs:83–143; P:2652–2795 | yes | 0; prepend U/S to remove a preexisting gap |
| deposit_to_specific_validator | whitelisted unpaused signer; both Staker PDAs via CPI | DepositSol(L+rho), then Increase | `(incorporated prefunding,0)`; no prefund: `(0,0)` | L/staking.rs:276–395 | yes | U for included prefund; usual call 0 |
| Increase, fresh X | stake manager via wrapper; installed SPL staker; or targeted depositor | R-(L+rho), X, tau+=L+rho; Y possibly | `(p,0)` where p=X prefund; Y residual excluded | P:1631–1782; K:582–725 | yes if native Split succeeds | U; small Y prefund can cause failure instead |
| IncreaseAdditional, existing activating X | same; recorded transient seed required | R,Y,X,tau | `(y,0)` where y=Y prefund merged in full | P:1582–1599,1712–1724 | yes | U |
| Decrease variants | stake manager or installed SPL staker | V-L, reserve rent, Y,X,A,tau:=x | `(p+y,0)` for excluded prefunding actually included; zero otherwise | P:1322–1496 | yes on success | U if gain; otherwise 0 |
| RemoveValidatorFromPool | owner wrapper or installed SPL staker | deactivation epochs/status | `(0,0)` | P:1041–1176 | yes | 0; no_merge refresh needs no cooldown |
| WithdrawStake / slippage, external destination | token owner/delegate/multisig with enough tokens; no whitelist | source, destination, A/tau,T,S,Sigma | `(0,0)` including integer truncation | P:2861–2876,3027–3042,3060–3139 | yes | 0; prepend U to reconcile first |
| DepositStake after manager reconfiguration | authorized external stake depositor + configured deposit authority | external source,V,R,A,T,S,Sigma | `(0,0)` for externally sourced assets; catches cache omissions without changing H | P:2387–2647 | yes | 0; U/S for old gap |
| WithdrawSol after manager reconfiguration, external destination | holder/delegate and configured SOL-withdraw authority | R,T,S,Sigma | `(0,0)` | P:3149–3288 | yes | 0 |
| WithdrawSol routed to counted V or enabled X | same; holder controls payout destination | R-ell, counted recipient+ell,T-ell | `(ell,0)`; `[0,ell]` for partially observed destination | same; K:758–759 rejects self-transfer | yes | U |
| Burn/BurnChecked outside SPL withdrawal | holder/delegate/multisig; anyone for System/incinerator-owned token account in inspected Token | Sigma, token account | `(0,b)`, `0<=b<=account balance` and allowance where applicable | N:580–659 | yes | S; does not remint the burned tokens |
| Token transfers/approvals/revocations/account authority changes | holder/delegate/authority | token account balances/authority | `(0,0)` unless a separate lamport credit accompanies closure | N:221–513 | yes | 0 |
| VLB true, correct pairs | anyone paying transaction fee | R,V, A,tau,lambda_i, sometimes status/data | `(0,0)` on healthy successful observation domain; C catches up | P:1851–2170 | yes | intermediate U; does not itself change T/S |
| VLB false, successful merges/deactivation | anyone | R,V,X,stake metadata,A,tau,status,lambda_i | `(0,0)` for accounted assets; any newly captured excluded gift is nonnegative | P:1967–2167; K:909–978 | yes | finish with SPB; use no_merge to avoid merge failures where possible |
| SPB without complete VLB | anyone | T:=C; fee mint; S:=Sigma | `(-(C-T),-D_S)`; `0<=C-T<=D_T` under IH | P:2175–2290 | yes | partial or complete S; outstanding V/X gaps require U |
| Full U reconciliation | anyone | all observation fields plus T,S,mint | `(-D_T,-D_S)` | same | yes | neutralized; proactive execution permitted |
| CleanupRemovedValidatorEntries | anyone | list membership, only zero-cache Ready entries | `(-h,0)`, h=optional contribution of removed entries; `h<=H-C<=D_T`; usual h=0 | P:2295–2335; S:754–758 | yes | U before cleanup captures an observable gift; lost excluded reference cannot be repaired by SPB alone |
| Native Initialize/Split/Authorize of excluded resurrection accounts | legacy: anyone initializes Uninitialized; later current authorities sign; v5 zero-byte init fails | state/authorities and possibly lamports | zero for outsider authorities; nonnegative optional gift when made usable and referenced | K:134–160; legacy stake_state.rs:227–250; P:193–201 | yes | U for included gift; no permissionless way to recover v5 zero-byte PDA refill |
| Native DeactivateDelinquent | anyone with eligible delinquent and reference vote histories | deactivation epoch of V/X | `(0,0)` now; may affect later merge success | K:1194–1237 | yes | 0 for ledgers; U true avoids transient merge path; cooldown is separate |
| Validator vote/commission/withdraw-authority changes, voting or non-voting | validator operator's corresponding vote authority | vote account, future reward calculation/delinquency | `(0,0)` immediately; future rewards handled below | VLB/SPB read set excludes vote account; K:1194–1237 | yes | 0; not a stake-account debit authority |
| Stake rewards | cluster | stake lamports and delegation.stake | `(reward,0)` for counted assets when H defined; optional/excluded assets may contribute less | PROTOCOL_MODEL.md:415–416; reward-source qualification below | ordinarily pool stale during payout | later U after reward guard clears; no atomic user bundle with cluster payout |
| Epoch transition | cluster | E,Clock/history, reward state | no principal change by tick itself; lambda!=E | P:1884–1887,2230–2232 | **no** | U after payout, no divergence detection needed |
| Rent change (outside fixed-parameter theorem) | cluster | rho_R,rho_V and native rent rules | reserve: `max(R-rho'_R,0)-max(R-rho_R,0)`; ignored-V sweep contributions also change; either sign | P:1948,2081–2084,2219–2225 | yes if E unchanged | U/S books change, cannot reverse it; legacy may require W |
| Minimum delegation / activation feature change | cluster | action guards, native state classification | zero immediate principal delta at unchanged rent and representation; possible domain change | P:983–985,1616–1629; K:540–548 | possibly | 0 or W; not a claim about arbitrary feature semantics |
| Staker administration #1–16 | initializer/owner/pending owner/agent/custodian as applicable | Access, membership and whitelist PDAs | `(0,0)` | complete per-instruction table in INVARIANT_LEMMAS.md L15 | yes | 0 |
| SPL manager/staker/fee/funding/preferred/metadata administration; fee-account validity changes | relevant SPL authority or token-account owner | config and metadata; future fee eligibility | `(0,0)` immediately; later transition formulas still apply | P:1789–1848,3292–3559; S:295–315 | yes | 0; changes may alter future access or fee outcomes |
| Arbitrary upgrades, hard-fork edits, hypothetical slashing | runtime governance/program upgrade authority | potentially any field | unconstrained; no preservation theorem | excluded from fixed-source state machine | unconstrained | no universal permissionless neutralization claim |

## Authority and neutralization qualifications

1. U/S need a correct current list, seeds and pool identity. They do not require
   knowing whether a donation/burn occurred. Unconditional complete refresh is
   distinct from blindly submitting outdated account metas.
2. An observer cannot force its instructions into another actor's transaction.
   “Atomic: yes” means the diverging action can be constructed with its signer(s)
   and appended update(s), not that a third party can alter a signed transaction.
3. Changed entries can be updated atomically without refreshing unchanged entries
   if the latter are known accurate. For arbitrary unknown divergence, refresh
   every entry. Transaction size/locks/CU impose limits; bounded chunks may need
   later transactions. No claim of a universal mainnet account-lock constant is
   made without identifying the runtime feature set.
4. While EpochRewards.active, 2.1.1 VLB fails. A genuinely stale pool cannot be
   repaired by skipping its validators. SPB has no reward guard, but stale list
   entries reject it. Empty-list pools are a special case.
5. Native legacy rent mismatch: adding more SOL to the same V does not fix a
   sweep that always leaves `d+rho_current < h_effective+rho_stored`. Waiting for
   enough cooldown, or a valid authorized different operation, may be needed.
   No unconditional same-transaction or bounded-epoch repair is proved.
6. Ignored/zombie balances are not a ledger divergence. Refresh does not make
   them recoverable. Capturing an Initialized legacy donation before Cleanup
   needs correct ordering; recovering an unreferenced account may need privileged
   pool operations and cannot be promised permissionlessly.

## Why no ordinary writer is missing — and the precise completeness limit

For fixed account data owners, the only debit/data writers of R,V,X are Stake;
only SPL writes pool/list data; only Token writes mint data. Their dispatch
paths and signature requirements were enumerated. External programs can still
**credit** lamports without recipient consent, hence the generic credit class
closes the infinite set of possible donor programs. SPL CPIs close the paths by
which unobserved Y/other-seed accounts become observed. The read set contains
no dependency on whitelist balances, arbitrary token-account balances, or vote
data until another legal transition propagates it into the observed accounts.
This supplies writer completeness for the stated transition system.

This is not an unqualified theorem about every conceivable cluster event.
The exact modern mainnet runtime build, reward implementation, feature inventory,
upgradable deployment hashes, and arbitrary hard-fork edits were not available.
Legacy Agave reward code supports the model's nonnegative payout semantics;
current reward semantics are also a standing model assumption. The table does
not invent a proof that all future cluster writers preserve principal. Such
an unsupported broader completeness claim is expressly rejected.
