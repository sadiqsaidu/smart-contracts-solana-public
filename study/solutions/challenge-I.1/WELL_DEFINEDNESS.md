# I.1 — Is Theta* well-defined?

Independent first solution. P/S = archived SPL 2.1.1 processor/state;
P0/S0 = SPL 2.0.3; K = Stake v5.1.0 processor; A = Agave 2.0.15 stake_state.
Exact paths and commits appear in VERIFICATION.md.

## Separate three questions

1. A particular supplied VLB transaction can fail, even if lambda=E.
2. A correctly constructed complete observation can have a state-dependent
   failure. Then the operational definition gives no Theta*; one must not
   silently use an asset sum as though the observation succeeded.
3. If canonical observations succeed from the same snapshot, do they return the
   same total? For this source state machine, yes, as proved below.

For ordinary reachable fresh states in the **fixed mainnet cell**, the native
balance/authority arguments below eliminate economic CPI failures. With correct
accounts, supported sysvars and sufficient resources, a complete observation
exists and is unique. This is more precise than saying “no_merge is read-only”
or treating every intentionally malformed transaction as an undefined state.
For arbitrary fresh serialized states, changing-parameter histories, or legacy
runtime combinations, the function is partial. A fresh stamp alone supplies
none of the account/CPI preconditions.

## Exhaustive VLB(true) control-flow audit — SPL 2.1.1

| Stage | Failure / skip condition | Source and reachable-state interpretation |
|---|---|---|
| Dispatch/invocation | bad Borsh instruction, missing fixed accounts, unavailable program, insufficient privileges, invalid transaction/compute/resource limits | P:3563–3565 and 1857–1865; generic runtime invocation. Correct construction/chunking repairs these. |
| Clock/Rent | wrong/unreadable Clock account; Rent syscall failure | P:1863,1868. lambda=E does not validate supplied account metas. |
| Pool identity | wrong owner, bad serialization, invalid account type | P:1870–1874. No external writer may corrupt the canonical SPL-owned data under fixed code. |
| Pool-linked addresses | wrong validator-list address, withdraw PDA/bump, reserve address, stake-program id | P:1875–1882; S:269–290,320–333,435–464. No user withdraw-authority signature is required; SPL supplies it via invoke_signed. |
| Reward guard | EpochRewards sysvar read fails or active=true | P:1884–1887. Applies even for no_merge and even with zero pairs. |
| Pair/count/range | odd remaining account count; wrong list owner; malformed list header/vector; start+count outside list, overflow, invalid cast; corrupt vector length can cause bounds failure | P:1890–1912; big_vec.rs:89–106. Chunk size is not inherently capped at client convenience constant 4. |
| Pair address validation | wrong V or X PDA | P:1925–1946 **continues**, rather than returning an error. Does not refresh that entry. Even tau=0 needs the correct X key to pass the pair check. |
| Decoding V/X | malformed/empty/non-Stake bytes | P:1952–1959,2069–2072 converts deserialize errors to None. No failure merely because a zombie/missing stake account is supplied at the correct key. |
| Transient handling with no_merge=true | Initialized/Stake usable and old tau!=0: record x; otherwise record zero | P:1967–2064. No transient merge or deactivate CPI is executed. Consequently vote mismatch, partial warmup/cooldown, flags preventing deactivation, and X-to-V merge mismatch do not themselves make this branch fail. |
| Delegated V | usable metadata: compute g; if g>0 invoke Withdraw(V,R,g) | P:2073–2097. The sweep runs before status selection, including ignored statuses. Native failures propagate. |
| Status conversion | invalid encoded status on a usable delegated V | P:2099, S:641–645. Valid initialized SPL states have a recognized status. |
| V Active or DeactivatingValidator/All | record post-sweep v; no merge for no_merge=true | P:2100–2122. No requirement that V be fully active or fully inactive. |
| V DeactivatingTransient / ReadyForRemoval | A=0 after any successful sweep | P:2124–2126. Remaining principal is intentionally ignored, not withdrawn. |
| Initialized V | if metadata usable, **always Merge(V into R)**; failures propagate; then status set based on nonzero transient contribution | P:2129–2154, no no_merge guard. |
| Other V states / wrong metadata | ignore, A=0 | P:2156–2162. Wrong authority or lockup usually causes omission, not SignatureMissing. A native CPI can still fail on wrong ownership because the SPL decoding/usability check itself does not check V/X owner. |
| Final writes | writable/data-owner/borrow/serialization/runtime violations; list fields written | P:2165–2167. Every correctly processed entry receives E even if both contributions are zero. |

The list covers every fallible call on the no_merge=true path and its two
possible native CPIs. Remaining runtime failures (transaction fees, locks,
compute, account load/size, invocation permissions and executable availability)
are a separate universal execution boundary, not an economic sign convention.

## Sweep CPI: exact arithmetic and native checks

Let V have lamports v, delegation d, current rent r, and effective stake h used
by Native Withdraw. SPL 2.1.1 computes

```
g = (v saturating_sub d) saturating_sub r = max(v-d-r,0).
```

If g=0, there is no CPI and none of its checks can cause failure. If g>0,
v> d+r and the intended post-balance is exactly d+r. For 200-byte legitimate
accounts r>0, so this is a partial withdrawal, never a full drain.

Stake v5 Withdraw (K:729–846) requires: correct source Stake owner and decodable
state (K:44–51); source and destination different; correct withdrawer signer;
no active lockup absent a custodian; available sysvars; `g+h+r<=v`; checked
destination credit and writable/borrow validity. Native processing also rejects
every instruction except GetMinimumDelegation during active rewards
(K:1429 onward; see exact grep anchors in archived file).

In the mainnet cell, `h<=d`, so

```
g+h+r <= g+d+r = v.
```

Pool usability enforces both native authorities equal the signed SPL PDA and
default lockup; reserve identity is different and has correct writable metadata.
The stored `Meta.rent_exempt_reserve=2,282,880` is **ignored** by Stake v5
(lib.rs:21–28). Thus it cannot cause the 616,640-lamport mismatch in this cell.
There is no minimum-delegation check on this Withdraw path. Minimum delegation
belongs to Delegate/Split and must not be invented as a sweep restriction.

This inequality also covers deactivating and fully inactive V, including v5's
inactive Split copies with an old delegation larger than current balance: then
g=0, rather than arithmetic underflow or mandatory withdrawal failure.

## Unconditional Initialized-V merge

P:2140–2149 invokes Stake Merge even when no_merge=true. K:909–978 checks
distinct source/destination, ownership and decodable state, destination staker
signature, merge classifications, matching authorized keys and compatible
lockups; its helper `helpers/merge.rs:36–163` can reject transient classifications,
active-vote/deactivation mismatches, incompatible class pairs and arithmetic.
State writes, resize and lamport relocation can fail at the runtime boundary.

For canonical reachable Initialized V plus canonical reserve, both classify
Inactive, have identical authorities and default lockup. The Inactive/Inactive
branch returns no destination metadata rewrite; it transfers all v to R.
No delegation weighted-credit arithmetic is performed. V5 resizes the source
to zero; legacy writes Uninitialized while retaining 200 bytes (A:606–668).
This observation is mutating but total-preserving and idempotent on re-observation.

An arbitrary purported reserve in Stake/Uninitialized state, bad authorities,
bad lockup, or foreign ownership may fail. Canonical initialization checks it,
and the legal 2.1.1 operations preserve it (INVARIANT_LEMMAS.md). Do not assert
all possible bad reserve states are reachable attacks.

## Legacy comparison: distinguish both axes

**SPL 2.1.1 × legacy Stake**, current rent r versus stored native rent r0:
legacy A:974–1075 protects `h+r0`, not `h+r`. For g>0 the sweep succeeds only if

```
g+h+r0 <= v   <=>   d-h >= r0-r.
```

On active/non-deactivated stake h=d, so any `r0>r` and positive g causes
InsufficientFunds. Example: v=1,002,282,880; d=h=1,000,000,000;
r0=2,282,880; r=1,666,240. SPL tries g=616,640 and leaves 1,001,666,240,
below the native required 1,002,282,880. It fails even with no donation.
See WITNESSES.md for the historical-rent reachability qualification.

If r=r0 (the named legacy test cell at constant rent), the same h<=d proof
eliminates the mismatch. If r0<r, the sweep is conservative and succeeds.
If g=0 no CPI occurs. Cooldown can make `d-h>=r0-r`, restoring success.
An arbitrary finite cooldown bound is not proved: effective stake depends on
cluster history. Same-epoch deactivation of fully active stake does not by
itself remove effective stake. Donating more to V increases g equally and does
not fix the failing inequality. Warming down is not an atomic update operation.

**SPL 2.0.3 × legacy Stake**: P0:2042–2045 uses stored r0 in the sweep, so
legacy agrees with its rent basis. P0 has no EpochRewards guard; no_merge paths
with no CPI can proceed during reward distribution, but any positive sweep or
Initialized-V merge calls native Stake and fails its reward guard (legacy
stake_instruction.rs:68–82). This is distinct from SPL 2.1.1's unconditional
early rejection. P0 reads X even when tau=0, and counts delegated V even if
its metadata is unusable (P0:1952,2041–2099); those changes alter its observation
domain and exclude reuse of the mainnet-cell invariants without another proof.
Its Initialized-V branch calls a status-conversion helper (P0:2122), which can
fail on an invalid status byte; legal statuses themselves are accepted
(S0:619–649).

**SPL 2.0.3 × v5**: sweep protects stored r0 while native protects r. At the
specified r<r0 it is conservative; a future r>r0 could fail with the opposite
mismatch. These comparisons do not substitute either version for mainnet-2026.

## Reward-active freshness nuance

VLB 2.1.1 can certainly reject a call to a fresh pool while EpochRewards.active,
for example a zero-pair call to an already initialized empty pool. But an empty
list needs **zero** VLB instructions to cover every entry; SPB alone defines its
total. This is not a counterexample to existence of Theta*.

Under ordinary epoch scheduling, an existing nonempty pool enters the reward
window with lambda<E. Its entries have old epoch stamps, VLB cannot advance
them, and SPB rejects them. Add/increase/decrease/deposit-stake creation cannot
manufacture current entries during active rewards because their native Stake
CPIs fail, and Add requires a fresh pool. Removing all zero-balance entries can
leave an empty pool, but not a fresh nonempty pool with new delegated stake.
Thus a fresh-nonempty, reward-active serialization is not automatically a
reachable mainnet counterexample. Arbitrary cluster flag toggles would be an
additional transition not proved by this scheduler argument.

## The final SPB also has preconditions

Theta* includes SPB, not just VLB. P:2179–2288 checks supplied accounts, pool
and list validity/owners, mint identity and decoding, fee-account **address**,
withdraw PDA, reserve identity, token-program id, list epoch stamps, and checked
`sum(A+tau)`. It reads Rent, Clock, calculates the fee, optionally performs
MintTo, reads mint supply and serializes the pool. Bad address is an error;
a fee account at the correct address with invalid token state merely suppresses
the fee. Mint overflow/authority/owner/freeze errors, borrow/write failures,
unavailable sysvars and arithmetic overflow are possible on arbitrary inputs.

For normal fixed-cell reachable states, the stronger sandwich gives
`Sigma<=S<=T<=C<=H`. With a 5% fee, `f<=C-T`; therefore `Sigma+f<=C` and
manager-account balance plus f cannot exceed total supply plus f. With finite
cluster capitalization within u64 and distinct accounted addresses, the
lamport sum cannot overflow. Epoch-fee multiplication uses u128 and fits for
valid bounded operands. Invalid account data and authorities cannot be created
by the permitted writers. Resource limits are addressed by chunking VLB, not
by omitting entries. No blanket guarantee is asserted for fabricated u64-max
genesis/account states outside these bounds.

P0:2185–2196 additionally requires reserve Initialized and **checked** subtraction
of stored rent; an underfunded reserve gives CalculationFailure. 2.1.1 instead
uses actual data length/current rent and saturating subtraction. Saturation does
not turn an arbitrary underfunded-reserve deposit into a theorem-preserving
transition; the reserve floor is an explicit reachable-state lemma.

## Uniqueness of successful observations

Take a fixed snapshot, correct pairs, full coverage, no interposed external
instructions, fixed sysvars and no fee updates until the single final SPB.
For each pair, its no_merge transformer:

- reads only that entry's V/X and shared immutable pool/sysvars;
- leaves X untouched and rewrites its cache from the same x/read gate;
- either sweeps a deterministically computed g, or merges an Initialized V;
- adds a nonnegative amount to the shared reserve and rewrites only that entry.

Distinct entries' V/X accounts do not alias. Their only shared economic write
is addition to R; these additions commute. For a usable Initialized reserve,
Inactive/Inactive merge does not alter metadata. Repeating a processed entry
adds nothing more (g becomes zero or V becomes empty). Cache writes agree.
Therefore disjoint or overlapping correct chunks that cover every entry give
the same post-VLB reserve/cache and final T; SPB's single fee uses the same T,S
and total too. model.py checks all 24 orders for four nontrivial entries.

This is not a concurrency theorem for maintenance split across real transactions:
donations, burns, cleanup/seed changes, rewards or epoch ticks between chunks can
change the snapshot. Nor does allowing arbitrary wrong-pair “successful” calls
define the required full observation. Skipped entries can leave a fresh but
inaccurate cache and a different SPB result; that sequence did not update every
entry as required.

## Addendum (second session, 2026-10-28): executed evidence and a version note

This section was added after the text above was saved. Nothing above was
rewritten; where the addendum changes an evidence label, it says so.

1. **Reward-guard failure reproduced on a validator.** On a freshly booted
   agave 2.0.15 test validator at epoch 0, `UpdateValidatorListBalance(no_merge=true)`
   against a fresh pool (lambda = E = 0) failed before touching any pair:
   `Program log: Error: UnsupportedSysvar` / `failed: Unsupported sysvar`
   (harness/results.json, key `epoch0Vlb`). This is the `EpochRewards::get()?`
   at P:1885. The sysvar does not exist until the first epoch boundary. The
   failure is neither `active = true` nor anything a user signature can fix.
   For that window Theta* is **undefined in the local cell even though the
   pool is fresh**. The table row "Reward guard" above was a source claim; it is
   now also executed. The mainnet-2026 cluster has had the sysvar since partitioned
   rewards activated. The window is therefore a cluster-history condition, not
   a mainnet-2026 failure, but it exists for any 2.1.x deployment on a cluster
   whose EpochRewards sysvar is absent. `tests/helpers.ts:686-702` already
   retries exactly this error after moving an epoch forward. SPL 2.0.3 (P0) has
   no such guard, so it cannot fail this way.

2. **`no_merge = true` mutates lamports, executed.** A real
   VLB(no_merge=true) after a 777,777-lamport transfer to the listed
   validator stake account moved exactly 777,777 lamports from V
   (1,003,060,657 → 1,002,282,880) into the reserve (key `noMergeMutation`).
   The observation is not read-only. Simulating it, as the harness does for
   Theta*, is the only way to observe without committing that move.

3. **Wrong pair addresses are silently skipped, executed.** With V/X replaced
   by random keys, the simulated VLB(true)+SPB succeeded and returned
   `total_lamports = T` (23,001,234,567). The correct observation returned
   T + 777,777 (key `wrongPairObservation`). A successful instruction is not
   evidence that the entries were observed.

4. **Which SPL version mainnet actually runs.** The mainnet `SPoo1…` program
   data (sha256 `ec2dfefaa70d560754a0000f39bd2cabc192b895d36205b3c428f601b6e1d7e1`,
   dumped read-only 2026-10-28) declares `source_release: program@v2.0.3` in
   its security.txt. Its processor log strings, however, are 2.1.x. It contains
   "Validator is marked for removal and no longer allows decreases" and
   "Transient stake is activating or active, deactivating." (present in 2.1.1
   P, absent from P0). It lacks "Reserve stake account in unknown state"
   (present in P0, absent from 2.1.1). The security.txt label is therefore
   stale; the challenge's `2.1.x` cell assignment is consistent with the
   deployed processor. This is a string fingerprint, not a reproducible-build
   hash match against 2.1.1.

5. **Legacy-cell rent failure (W8), source re-checked, not executed.** Legacy
   Withdraw compares against the stored `meta.rent_exempt_reserve`
   (agave-2.0.15/stake_state.rs:1014). v5 compares against current
   `Rent::minimum_balance` (stake-v5.1.0/processor.rs:762, 788). 2.1.1's sweep
   uses current rent (P:1948, 2081–2084). The local validator has
   stored = current rent = 2,282,880, so the mismatch cannot be reproduced
   there without a rent change, which `solana-test-validator` does not expose.
