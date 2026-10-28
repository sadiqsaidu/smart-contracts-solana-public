"""Exact-integer model of TruStake / SPL Stake Pool 2.1.x revenue recognition.

Arithmetic follows study/solutions/challenge-I.1/upstream/spl-2.1.1:
  deposit      state.rs:162-171   n = L if T==0 or S==0 else floor(L*S/T)
  withdraw     state.rs:176-186   ell = 0 if b*T < S or S==0 else floor(b*T/S)
  fee.apply    state.rs:939-949   ceil(amt*num/den)
  epoch fee    state.rs:241-255   f = floor(S*phi/(T+r-phi)), phi = ceil(r*5/100)
  VLB sweep    processor.rs:2073-2098   excess = v - d - rent  -> reserve (every call, no_merge or not)
  VLB guard    processor.rs:1884-1888   reverts while EpochRewards.active
  SPB          processor.rs:2217-2286   T := (R - rent) + sum(A_i); fee mint; S := mint supply
  freshness    processor.rs:2703 (DepositSol), :2847 (WithdrawStake)
  WithdrawStake processor.rs:2800-3140  fee exempt iff burn_from == manager fee account;
               validator source must keep rent + min_delegation; reserve only if no validator has
               available lamports; split destination prefunded with rent by the user.

Revenue stages (never collapsed):
  EARNED      economically earned in epoch e, no on-chain assignment yet (tips sitting in a TDA,
              inflation not yet computed)
  ASSIGNED    an on-chain entitlement exists (merkle root uploaded / reward partition computed)
  CLAIMABLE   can be paid now by some permitted actor
  CREDITED    lamports are in a pool-controlled counted account (V_i or reserve)
  CACHED      reflected in the validator-list cache (swept to reserve or A_i refreshed)
  RECORDED    reflected in T (and the epoch fee has been minted on it)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
import copy

RENT = 1_666_240            # mainnet Rent::minimum_balance(200), measured (window_txs_1063.json)
MIN_DELEGATION = 1_000_000_000


def ceil_div(a: int, b: int) -> int:
    return -(-a // b)


class Stage(IntEnum):
    EARNED = 0
    ASSIGNED = 1
    CLAIMABLE = 2
    CREDITED = 3
    CACHED = 4
    RECORDED = 5


class Rejected(Exception):
    """The modelled program would return an error; the transaction has no effect."""


@dataclass
class Revenue:
    kind: str          # "inflation" | "jito" | "donation" | "uncounted"
    earned_epoch: int
    validator: int     # index into the list, -1 = reserve, None = account outside the pool
    amount: int
    stage: Stage = Stage.EARNED
    credited_at: tuple | None = None   # (epoch, step)
    recorded_at: tuple | None = None


@dataclass
class Validator:
    lamports: int       # actual lamports of V_i
    delegation: int     # delegation.stake
    cached: int         # A_i (active_stake_lamports)
    last_update_epoch: int


@dataclass
class Pool:
    T: int
    S: int
    mint_supply: int
    reserve: int
    validators: list[Validator]
    E: int
    lam: int
    rewards_active: bool = False
    epoch_fee: tuple[int, int] = (5, 100)
    withdrawal_fee: tuple[int, int] = (1, 1000)
    deposit_fee: tuple[int, int] = (0, 100)
    balances: dict[str, int] = field(default_factory=dict)   # token holders; "fee" = manager fee account
    revenue: list[Revenue] = field(default_factory=list)
    step: int = 0
    log: list = field(default_factory=list)

    # ---------------------------------------------------------------- observation
    def theta_star(self) -> int:
        """Final T of a correct complete VLB(no_merge=true)+SPB with no interleaving."""
        p = copy.deepcopy(self)
        p.rewards_active = False      # hypothetical: the observation itself is undefined while active
        p._vlb(range(len(p.validators)))
        p._spb(mint_fee=False)
        return p.T

    def gaps(self):
        return {"D_T": self.theta_star() - self.T, "D_S": self.S - self.mint_supply}

    def fair_value(self, tokens: int) -> int:
        """Mark-to-market: lamports for `tokens` at the fully reconciled post-fee price (floor)."""
        p = copy.deepcopy(self)
        p.rewards_active = False
        p._vlb(range(len(p.validators)))
        p._spb(mint_fee=True)
        return tokens * p.T // p.S

    # ---------------------------------------------------------------- cluster transitions
    def epoch_tick(self):
        self.E += 1
        self.rewards_active = True
        self._mark("epoch_tick", E=self.E)

    def pay_inflation(self, i: int, amount: int, earned_epoch: int):
        """Partitioned stake reward: increases delegation and lamports of V_i (only while active)."""
        if not self.rewards_active:
            raise Rejected("inflation rewards are only paid inside the reward-distribution window")
        v = self.validators[i]
        v.delegation += amount
        v.lamports += amount
        self.revenue.append(Revenue("inflation", earned_epoch, i, amount, Stage.CREDITED, (self.E, self.step)))
        self._mark("pay_inflation", i=i, amount=amount)

    def end_rewards(self):
        self.rewards_active = False
        self._mark("end_rewards")

    def earn_tip(self, i: int | None, amount: int, earned_epoch: int, kind="jito"):
        self.revenue.append(Revenue(kind, earned_epoch, i, amount, Stage.EARNED))

    def upload_root(self, earned_epoch: int):
        for r in self.revenue:
            if r.kind in ("jito", "uncounted") and r.earned_epoch == earned_epoch and r.stage == Stage.EARNED:
                r.stage = Stage.CLAIMABLE    # ASSIGNED and CLAIMABLE coincide once the root is uploaded
        self._mark("upload_root", epoch=earned_epoch)

    def claim(self, i: int | None, earned_epoch: int):
        """Tip Router ClaimWithPayer -> tip-distribution Claim: plain lamport credit to the claimant.
        Delegation is unchanged. Claimant outside the pool (i is None) changes nothing the pool observes."""
        for r in self.revenue:
            if r.stage == Stage.CLAIMABLE and r.validator == i and r.earned_epoch == earned_epoch:
                if i is not None:
                    self.validators[i].lamports += r.amount
                r.stage = Stage.CREDITED
                r.credited_at = (self.E, self.step)
                self._mark("claim", i=i, amount=r.amount)
                return r.amount
        raise Rejected("nothing claimable")

    def donate(self, target: int, amount: int):
        """System transfer by anyone: target -1 = reserve, i = V_i."""
        if target == -1:
            self.reserve += amount
        else:
            self.validators[target].lamports += amount
        self.revenue.append(Revenue("donation", self.E, target, amount, Stage.CREDITED, (self.E, self.step)))
        self._mark("donate", target=target, amount=amount)

    # ---------------------------------------------------------------- SPL maintenance
    def _vlb(self, idx):
        if self.rewards_active:
            raise Rejected("EpochRewardDistributionInProgress")
        for i in idx:
            v = self.validators[i]
            excess = max(0, v.lamports - v.delegation - RENT)
            if excess:
                v.lamports -= excess
                self.reserve += excess
            v.cached = v.lamports
            v.last_update_epoch = self.E
            for r in self.revenue:
                if r.validator == i and r.stage == Stage.CREDITED:
                    r.stage = Stage.CACHED
        for r in self.revenue:   # reserve credits are "cached" as soon as they exist (SPB reads R directly)
            if r.validator == -1 and r.stage == Stage.CREDITED:
                r.stage = Stage.CACHED

    def vlb(self, idx=None):
        self._vlb(range(len(self.validators)) if idx is None else idx)
        self._mark("vlb", idx=list(idx) if idx is not None else "all")

    def _spb(self, mint_fee=True):
        if any(v.last_update_epoch < self.E for v in self.validators):
            raise Rejected("StakeListOutOfDate")
        total = max(0, self.reserve - RENT) + sum(v.cached for v in self.validators)
        r = max(0, total - self.T)
        fee = self._epoch_fee_tokens(r)
        if fee and mint_fee:
            self.balances["fee"] = self.balances.get("fee", 0) + fee
            self.mint_supply += fee
        elif fee:
            self.mint_supply += fee
        self.T = total
        self.S = self.mint_supply
        self.lam = self.E
        for rv in self.revenue:
            if rv.stage == Stage.CACHED:
                rv.stage = Stage.RECORDED
                rv.recorded_at = (self.E, self.step)
        return fee

    def _epoch_fee_tokens(self, r: int) -> int:
        if r == 0:
            return 0
        num, den = self.epoch_fee
        total = self.T + r
        phi = ceil_div(r * num, den) if den else 0
        if total == phi or self.S == 0:
            return r
        return self.S * phi // (total - phi)

    def spb(self):
        fee = self._spb()
        self._mark("spb", fee=fee, T=self.T, S=self.S)
        return fee

    # ---------------------------------------------------------------- user operations
    def deposit_sol(self, who: str, L: int) -> int:
        if self.lam < self.E:
            raise Rejected("StakeListAndPoolOutOfDate")
        n = L if (self.T == 0 or self.S == 0) else L * self.S // self.T
        num, den = self.deposit_fee
        dfee = ceil_div(n * num, den) if num else 0
        if n - dfee == 0:
            raise Rejected("DepositTooSmall")
        self.reserve += L
        self.T += L
        self.S += n
        self.mint_supply += n
        self.balances[who] = self.balances.get(who, 0) + n - dfee
        if dfee:
            self.balances["fee"] = self.balances.get("fee", 0) + dfee
        self._mark("deposit_sol", who=who, L=L, minted=n)
        return n - dfee

    def withdraw_stake(self, who: str, p: int, i: int) -> int:
        """WithdrawStake from validator i. Returns lamports split into the user's stake account
        (the user separately prefunds that account with RENT, which is refundable)."""
        if self.lam < self.E:
            raise Rejected("StakeListAndPoolOutOfDate")
        if self.balances.get(who, 0) < p:
            raise Rejected("insufficient pool tokens")
        fee = 0 if who == "fee" else ceil_div(p * self.withdrawal_fee[0], self.withdrawal_fee[1])
        b = p - fee
        ell = 0 if (self.S == 0 or b * self.T < self.S) else b * self.T // self.S
        if ell == 0:
            raise Rejected("WithdrawalTooSmall")
        P_up = (self.T + self.S - 1) // self.S                 # get_lamports_per_pool_token
        tol = RENT + MIN_DELEGATION + P_up
        if i == -1:
            # reserve source: only when no validator has active lamports above the tolerance
            if any(v.cached > tol for v in self.validators):
                raise Rejected("StakeLamportsNotEqualToMinimum (validators have lamports available)")
            if self.reserve - ell < RENT:
                raise Rejected("SolWithdrawalTooLarge")
            self.reserve -= ell
            self.T -= ell
            self.S -= b
            self.mint_supply -= b
            self.balances[who] -= p
            if fee:
                self.balances["fee"] = self.balances.get("fee", 0) + fee
            self._mark("withdraw_stake", who=who, p=p, fee=fee, burned=b, lamports=ell, i=i)
            return ell
        v = self.validators[i]
        if v.lamports - ell < RENT + MIN_DELEGATION:
            raise Rejected("StakeLamportsNotEqualToMinimum")
        if ell < MIN_DELEGATION:
            # Stake v5 Split from an active stake: the destination must hold >= min delegation
            raise Rejected("split below minimum delegation")
        v.lamports -= ell
        v.delegation -= ell
        v.cached -= ell
        self.T -= ell
        self.S -= b
        self.mint_supply -= b
        self.balances[who] -= p
        if fee:
            self.balances["fee"] = self.balances.get("fee", 0) + fee
        self._mark("withdraw_stake", who=who, p=p, fee=fee, burned=b, lamports=ell, i=i)
        return ell

    def _ell_for(self, who: str, p: int) -> int:
        fee = 0 if who == "fee" else ceil_div(p * self.withdrawal_fee[0], self.withdrawal_fee[1])
        b = p - fee
        return 0 if (self.S == 0 or b * self.T < self.S) else b * self.T // self.S

    def exit_all(self, who: str):
        """Redeem every token of `who` by WithdrawStake: from validators (largest first), each split
        bounded by the validator's spare lamports (V - rent - min_delegation) and >= min_delegation,
        then from the reserve once no validator has lamports above the tolerance.
        Returns (lamports, number_of_withdraw_transactions); leftover dust stays in balances."""
        got, txs = 0, 0
        while self.balances.get(who, 0) > 0:
            bal = self.balances[who]
            done = False
            for i in sorted(range(len(self.validators)), key=lambda j: -self.validators[j].lamports) + [-1]:
                if i == -1:
                    spare = self.reserve - RENT
                else:
                    spare = self.validators[i].lamports - RENT - MIN_DELEGATION
                lo, hi = 0, bal                      # largest p with ell(p) <= spare (ell is monotone in p)
                while lo < hi:
                    mid = (lo + hi + 1) // 2
                    if self._ell_for(who, mid) <= spare:
                        lo = mid
                    else:
                        hi = mid - 1
                if lo == 0:
                    continue
                try:
                    got += self.withdraw_stake(who, lo, i); txs += 1; done = True
                    break
                except Rejected:
                    continue
            if not done:
                break
        return got, txs

    def burn(self, who: str, p: int):
        self.balances[who] -= p
        self.mint_supply -= p
        self._mark("burn", who=who, p=p)

    def owner_add_validator(self, lamports: int, delegation: int):
        """Staker add_validator: owner transfers rent+min_delegation into the reserve, SPL Add moves
        it into a new V and caches it, without touching T (the documented H6 window)."""
        self.reserve += lamports
        self.reserve -= lamports
        self.validators.append(Validator(lamports, delegation, lamports, self.E))
        self.revenue.append(Revenue("owner_add", self.E, len(self.validators) - 1, lamports, Stage.CACHED, (self.E, self.step)))
        self._mark("owner_add_validator", lamports=lamports)

    # ---------------------------------------------------------------- bookkeeping
    def _mark(self, op, **kw):
        self.step += 1
        self.log.append((self.step, self.E, op, kw))

    def outstanding(self):
        out = {s.name: 0 for s in Stage}
        for r in self.revenue:
            out[r.stage.name] += r.amount
        return out


def mainnet_1070(state: dict) -> Pool:
    """Pool exactly as read on mainnet in epoch 1070 (pool_state.json) with the epoch-1069 Jito
    claims removed, i.e. the state right after the 1070 maintenance and before any claim."""
    vs = []
    for v in state["validators"]:
        A = int(v["active_stake_lamports"])
        d = int(v["stake_account_state"]["parsed"]["info"]["stake"]["delegation"]["stake"])
        vs.append(Validator(A, d, A, int(v["last_update_epoch"])))
    pool = state["pool"]
    p = Pool(T=int(pool["total_lamports"]), S=int(pool["pool_token_supply"]), mint_supply=int(state["mint"]["supply"]),
             reserve=int(state["reserve"]["lamports"]), validators=vs, E=int(state["epochInfo"]["epoch"]), lam=int(pool["last_update_epoch"]))
    p.balances = {"fee": 12_826_524_466}
    p.balances["others"] = p.S - p.balances["fee"]
    return p
