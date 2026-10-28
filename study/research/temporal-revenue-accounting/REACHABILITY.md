# Reachability, transaction legality and actor authority

## 1. Witness W-J: a late Jito credit followed by a window deposit

The start state is the **public observed state** of epoch 1070 after its first SPB (slot 462,248,568);
it was reached by legal history. Each step gives its classification:

* **C** public historical observation;
* **Sim** mainnet simulation;
* **L** local-validator execution with the production SPL and Staker binaries (legacy Stake);
* **M** exact-integer model;
* **S** source-derived.

| # | Trigger / instruction | Accounts written (w) / read (r) | Signers | Minimum privilege | Preconditions | Slot restriction | `λ = E`? | Balance change | Expected | Class |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | SPL `UpdateValidatorListBalance` (all pairs) + `UpdateStakePoolBalance` | w: list, reserve, `V_i`, pool, fee acct, mint. r: clock, stake history, EpochRewards | any fee payer | none | `¬ω`; correct pair seeds | after reward window | becomes true | `T := C`, fee mint | success | C (`4TQL61…`, `2Wz1uS…`) |
| 2 | Tip Router `ClaimWithPayer` → tip-distribution `Claim` | w: TDA, ClaimStatus, `V_i` (claimant), router payer PDA. r: NCN, configs | any fee payer (observed `EG2ziP…`) | none [Src master] | root uploaded; unclaimed; `E ≤ expires_at` | any slot after upload | unchanged | `v_i += a` | success | C (`5jrnrWgr…`); Sim shows `D_T = a` |
| 3 | Staker `deposit(L)` → SPL `DepositSol` (CPI signed by the deposit PDA) | w: payer, UserStatus, access, pool, reserve, user ATA, fee ATA, mint. r: withdraw PDA, programs | user | **whitelisted** user; not paused | `λ = E` | any slot with `λ = E` | unchanged | `T += L`, `n = floor(L·S/T)` minted | success; mints `n > n_honest` | L (production Staker, check "window deposit mints floor(L*S/T)"); M |
| 4 | epoch boundary + reward window | — | cluster | — | — | first ~650 slots | false | inflation credited | — | C |
| 5 | step 1 again in `E+1` | as step 1 | any | none | `¬ω` | after window | true | `T` += inflation + `a`; fee mint | success | C (every epoch) |
| 6 | SPL `WithdrawStake(p)` (1–5 txs, routed) | w: pool, list, `V_i` or reserve, user stake (prefunded ρ), user ATA, fee ATA, mint | holder | **none** beyond holding tokens | `λ = E`; split bounds | — | true | `ℓ = floor((p − ceil(p/1000))·T/S)` | success | C (1063 tx); L; M |
| 7 | Stake `Deactivate`, then `Withdraw` next epoch | user stake | holder | none | — | one-epoch cooldown | — | lamports to wallet | success | L; S |

**Legality.** Every step is legal, and steps 1, 2, 5 and 6 are executed on mainnet every epoch by
someone. **Profitability.** Never profitable: `ECONOMIC_ANALYSIS.md` §2 shows a 678× shortfall at
breakeven.

## 2. Witness W-R: an external reserve top-up followed by a window deposit

The start state is the reconstructed public state just before 1030 slot index 406,775.

| # | Trigger | Signers | Min. privilege | Result | Class |
|---|---|---|---|---|---|
| 1 | first SPB of 1030 | any | none | `D_T = 0` | C |
| 2 | `SystemProgram.transfer(14.573 SOL → reserve)` | donor | **the donor's own funds**; the depositor cannot cause it except by paying it themselves | `R += a`, `D_T = a` (0.283·T) | C (`2KJhxo5L…`) |
| 3 | Staker `deposit(L)` | whitelisted user | whitelisted | mints `floor(L·S/T)` | M (reconstructed `T,S`), L (same code path) |
| 4 | 1031 boundary; first SPB (any signer) | any | none | records `a`; fee 182,052,877 | C (`4sJPNCgL…`) |
| 5 | routed WithdrawStake + cooldown | holder | none | realized +0.26 to +10.8 SOL for `L` = 1–200 SOL | M |

Steps 1, 2 and 4 happened. Steps 3 and 5 did not happen historically; they are legal and executed
locally on the same code path (`EXPERIMENTS.md` §3).

## 3. Actor models

| # | Actor | Can enter the window (deposit)? | Can cause the credit? | Can exit? | Outcome on Jito (W-J) | Outcome on top-up (W-R) |
|---|---|---|---|---|---|---|
| 1 | Ordinary unwhitelisted outsider | **No**. Staker `deposit` → `UserNotWhitelisted` (6009); direct SPL `DepositSol` lacks the deposit-PDA signature (fails, L) | Only its timing: a Jito claim can be submitted by anyone [Src master]; a top-up only by paying it | n/a (holds no tokens). It could buy TruSOL on the secondary market, which is outside TruStake accounting. | none | none via TruStake |
| 2 | Whitelisted depositor | yes | timing of a Jito claim; any donation it pays | yes (WithdrawStake) | MTM ≤ 0.95·z; round trip loss | **Profitable** if it observes a third party's top-up |
| 3 | Existing TruSOL holder | no new entry | same | yes | Can only *avoid* a window withdrawal (loss ℓ·z/T); can protect itself and others by running VLB+SPB | can neutralise by SPB (permissionless) |
| 4 | Whitelisted + holder | yes | same | yes | as 2 | as 2 |
| 5 | Validator operator / Jito claimant | as its whitelist status | Controls MEV commission (V2 sets 100%) and *whether* tips exist. Claims are permissionless, so the operator has no special timing power. | — | Can shrink `z` to 0, never enlarge it except by paying tips | none |
| 6 | Leader (transaction ordering) | as its whitelist status | can reorder within its slots | — | No advantage: the window lasts most of an epoch (L7) | The same window would also be open to non-leaders |
| 7 | Trusted governance (Staker owner/agents, SPL manager, stake manager) | Owner/agents can whitelist themselves. The manager fee account is withdrawal-fee exempt. | Owner `add_validator` (`q` ≈ 1.0017 SOL), treasury top-ups (if the 1030 donor was TruFin; unverified) | yes | Manager-as-depositor would dilute mainly itself (78%) | Governance-only: out of scope as an attacker class; relevant as the *source* of the window (operational) |

## 4. Can the actor enter the window under realistic scheduling?

* **Jito.** The window is open for ≈ 99% of every epoch after the first SPB (L7). Entry needs nothing
  special. There is nothing worth entering for.
* **Top-up.** The 1030 window lasted 25,225 slots (≈ 2.8 h). The credit is a public System transfer
  to a known address, observable within one slot by any watcher of the reserve account. One deposit
  transaction suffices.
* **Competition.**
  * Any party can close the window with a single permissionless SPB (reserve credit) or VLB+SPB
    (`V_i` credit). In 51 epochs no observed maintainer ran one after a credit.
  * Other whitelisted depositors split the same bounded `0.95·a`.
  * Epoch boundary guards block deposits from the boundary until the first SPB, so the window cannot
    be extended across the boundary.
* **Freshness at entry.** `λ = E` held throughout both windows (Sim for 1070; the 1030 deposit window
  is post-SPB by construction).
