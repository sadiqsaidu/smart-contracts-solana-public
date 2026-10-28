#!/usr/bin/env python3
"""Exact-integer reference model for Challenge IV.4 (batch settlement).

This is a MODEL of SPL Stake Pool 2.1.x arithmetic and of the proposed TruStake
batch program. It is not a Solana VM. Every quantity is a Python int and every
division is the upstream integer division (floor, or ceil where SPL uses ceil).

Value yardstick ("net true price"): the value of x tokens at state s is
    x * Theta*(s) / Sigma*(s)
where (Theta*, Sigma*) are total_lamports and mint supply after a hypothetical
complete observation [VLB(no_merge) on every entry, then SPB] at s. Sigma* includes
the epoch fee that observation would mint, so pending fees are crystallized.
Values are compared as exact Fractions.

Designs compared (see ../SPECIFICATION.md and ../ATTACK_ANALYSIS.md):
  immediate  - today's TruStake: DepositSol at the recorded T/S, per deposit
  batch      - proposed: queued lamports; settle = one instruction doing
               VLB(all, verified pairs) -> SPB -> DepositSol; pro-rata floor claims
  nonatomic  - batch, but settle trusts earlier maintenance (SPB? + DepositSol only)
  wrongpair  - batch, but the settler may pass wrong (V,X) pairs (no address check)
  escrowmint - deposit mints immediately into escrow at the recorded price;
               settle observes, burns the excess, pro-rata claims (conjecture (d))
  fresh      - immediate mint, but every deposit embeds VLB(all)+SPB (O(n) accounts)
"""
from __future__ import annotations

import copy
import json
import random
import sys
from dataclasses import dataclass, field
from fractions import Fraction

RHO = 1_666_240           # 200-byte stake account rent, mainnet-2026 cell
M = 1_000_000_000         # native minimum delegation (Stake v5)
Q = RHO + M               # SPL validator floor q = rho + max(m, 1e6)
EPOCH_FEE = (5, 100)
WITHDRAW_FEE = (1, 1000)


def ceildiv(a: int, b: int) -> int:
    return -(-a // b)


def mint_amount(l: int, t: int, s: int) -> int:
    """state.rs calc_pool_tokens_for_deposit."""
    return l if t == 0 or s == 0 else l * s // t


def epochfee(r: int, t: int, s: int) -> int:
    """state.rs calc_epoch_fee_amount (S is the RECORDED supply)."""
    if r == 0:
        return 0
    phi = ceildiv(r * EPOCH_FEE[0], EPOCH_FEE[1])
    return r if t + r == phi or s == 0 else s * phi // (t + r - phi)


def payout(b: int, t: int, s: int) -> int:
    """state.rs calc_lamports_withdraw_amount."""
    return 0 if s == 0 or b * t < s else b * t // s


class Revert(Exception):
    """An instruction failed; the whole transaction is rolled back."""


@dataclass
class Entry:
    v: int          # actual lamports of V_i
    d: int          # delegation.stake
    a: int          # cached active_stake_lamports
    lam: int        # entry last_update_epoch


@dataclass
class Pool:
    t: int
    s: int
    reserve: int
    entries: list
    epoch: int
    lam: int
    tokens: dict = field(default_factory=dict)   # holder -> raw TruSOL
    rewards_active: bool = False

    # ---- observation -------------------------------------------------
    @property
    def sigma(self) -> int:
        return sum(self.tokens.values())

    def vlb(self, i: int, correct_pair: bool = True):
        """UpdateValidatorListBalance(no_merge=true) on entry i (P:1851-2170)."""
        if self.rewards_active:
            raise Revert("EpochRewardDistributionInProgress")
        if not correct_pair:
            return  # P:1925-1946: wrong PDA -> `continue`, entry untouched
        e = self.entries[i]
        extra = max(0, e.v - e.d - RHO)        # sweep runs even with no_merge
        if extra:
            e.v -= extra
            self.reserve += extra
        e.a = e.v
        e.lam = self.epoch

    def spb(self):
        """UpdateStakePoolBalance (P:2175-2290)."""
        if any(e.lam < self.epoch for e in self.entries):
            raise Revert("StakeListOutOfDate")
        total = max(0, self.reserve - RHO) + sum(e.a for e in self.entries)
        r = max(0, total - self.t)
        f = epochfee(r, self.t, self.s)
        if f:
            self.tokens["manager"] = self.tokens.get("manager", 0) + f
        self.lam = self.epoch
        self.t = total
        self.s = self.sigma

    def observe(self):
        """(Theta*, Sigma*) via a hypothetical complete observation; None if undefined."""
        c = copy.deepcopy(self)
        try:
            for i in range(len(c.entries)):
                c.vlb(i)
            c.spb()
        except Revert:
            return None
        return c.t, c.sigma

    def price(self) -> Fraction:
        obs = self.observe()
        assert obs is not None
        return Fraction(obs[0], obs[1])

    # ---- SPL value-moving instructions -------------------------------
    def deposit_sol(self, holder: str, l: int) -> int:
        if self.lam != self.epoch:
            raise Revert("StakeListAndPoolOutOfDate")
        n = mint_amount(l, self.t, self.s)
        if n == 0:
            raise Revert("DepositTooSmall")
        self.reserve += l
        self.t += l
        self.s += n
        self.tokens[holder] = self.tokens.get(holder, 0) + n
        return n

    def withdraw_stake(self, holder: str, p: int) -> int:
        """WithdrawStake from the largest Active validator (routing simplified)."""
        if self.lam != self.epoch:
            raise Revert("StakeListAndPoolOutOfDate")
        if self.tokens.get(holder, 0) < p:
            raise Revert("InsufficientFunds")
        fee = 0 if holder == "manager" else ceildiv(p * WITHDRAW_FEE[0], WITHDRAW_FEE[1])
        b = p - fee
        ell = payout(b, self.t, self.s)
        if ell == 0:
            raise Revert("WithdrawalTooSmall")
        j = max(range(len(self.entries)), key=lambda k: self.entries[k].a)
        e = self.entries[j]
        if e.v - ell < Q or ell < M or e.d - ell < M:
            raise Revert("StakeLamportsNotEqualToMinimum / v5 split minimum")
        e.v -= ell
        e.d -= ell
        e.a -= ell
        self.t -= ell
        self.s -= b
        self.tokens[holder] -= p
        if fee:
            self.tokens["manager"] = self.tokens.get("manager", 0) + fee
        return ell

    # ---- external (non-pool) transitions -----------------------------
    def donate_reserve(self, z: int):
        self.reserve += z

    def donate_validator(self, i: int, z: int):
        self.entries[i].v += z       # System transfer, Jito tip claim, ...

    def burn(self, holder: str, k: int):
        if self.tokens.get(holder, 0) < k:
            raise Revert("InsufficientFunds")
        self.tokens[holder] -= k

    def owner_add_validator(self):
        # Staker add_validator: owner sends q to reserve, SPL splits q into V, caches A=q.
        self.entries.append(Entry(v=Q, d=M, a=Q, lam=self.epoch))

    def epoch_tick(self, rate_ppm: int = 180):
        self.epoch += 1
        for e in self.entries:
            g = e.d * rate_ppm // 1_000_000
            e.v += g
            e.d += g
        self.rewards_active = True

    def payout_done(self):
        self.rewards_active = False


def mainnet_pool() -> Pool:
    """Live TruStake balances read on 2026-10-28 (VERIFICATION.md section 2)."""
    a = [13_100_200_442, 24_488_454_515, 14_163_241_633, 14_338_980_086]
    t, s = 66_101_088_311, 16_407_030_513
    entries = [Entry(v=x, d=x - RHO, a=x, lam=1070) for x in a]
    reserve = t - sum(a) + RHO
    p = Pool(t=t, s=s, reserve=reserve, entries=entries, epoch=1070, lam=1070)
    p.tokens = {"incumbent": s - 1_000_000_000, "manager": 1_000_000_000}
    return p


# =====================================================================
# Batch program (proposed design) and the comparison designs
# =====================================================================
@dataclass
class Ticket:
    user: str
    batch: int
    amount: int
    state: str               # Pending | Refundable


@dataclass
class Batch:
    epoch: int
    total: int = 0
    status: str = "Open"     # Open | Settled | Voided
    minted: int = 0
    vault: int = 0
    unresolved: int = 0
    settle_price: Fraction | None = None
    transfer: Fraction | None = None
    esc_lamports: int = 0     # escrowmint only: lamports deposited for this batch
    esc_tokens: int = 0       # escrowmint only: tokens minted into escrow for this batch


class World:
    """Pool + users + batch program. `design` selects the settlement rule."""

    def __init__(self, design: str, pool: Pool | None = None):
        self.design = design
        self.pool = pool or mainnet_pool()
        self.status: dict[str, str] = {}
        self.paused = False
        self.batches: dict[int, Batch] = {}
        self.tickets: dict[str, Ticket] = {}
        self.wallet: dict[str, int] = {}        # lamports returned / held by users
        self.paid_in: dict[str, int] = {}       # lamports each user ever enqueued
        self.claimed: dict[str, int] = {}       # TruSOL each user ever claimed
        self.records: list[dict] = []           # per-settlement transfer records
        self.immediate_records: list[dict] = []
        self.escrow_lamports = 0                # escrowmint: deposited but unsettled
        self.escrow_tokens = 0

    # ---- user-facing instructions ------------------------------------
    def enqueue(self, user: str, l: int):
        if self.status.get(user) != "W" or self.paused:
            raise Revert("NotWhitelisted/Paused")
        e = self.pool.epoch
        if self.design in ("immediate", "fresh"):
            return self._immediate(user, l)
        b = self.batches.setdefault(e, Batch(epoch=e))
        t = self.tickets.get(user)
        if t is not None and not (t.state == "Pending" and t.batch == e):
            raise Revert("TicketBusy")
        if self.design == "escrowmint":
            p = self.pool
            n = p.deposit_sol("escrow", l)          # mints NOW at the recorded price
            self.escrow_lamports += l
            self.escrow_tokens += n
            b.esc_lamports += l
            b.esc_tokens += n
        if t is None:
            self.tickets[user] = t = Ticket(user, e, 0, "Pending")
            b.unresolved += 1
        t.amount += l
        b.total += l
        self.paid_in[user] = self.paid_in.get(user, 0) + l

    def cancel(self, user: str):
        t = self.tickets.get(user)
        if t is None or t.state != "Pending" or self.batches[t.batch].status != "Open":
            raise Revert("NotCancellable")
        if self.design == "escrowmint":
            raise Revert("lamports already in the pool")
        b = self.batches[t.batch]
        b.total -= t.amount
        b.unresolved -= 1
        self.wallet[user] = self.wallet.get(user, 0) + t.amount
        del self.tickets[user]

    def set_status(self, user: str, st: str):
        """Agent/custodian status change WITH the eviction hook (Policy B)."""
        self.status[user] = st
        t = self.tickets.get(user)
        if st != "W" and t is not None and t.state == "Pending" \
                and self.batches[t.batch].status == "Open" and self.design != "escrowmint":
            b = self.batches[t.batch]
            b.total -= t.amount
            b.unresolved -= 1
            t.state = "Refundable"

    def claim_refund(self, user: str):
        t = self.tickets.get(user)
        if t is None or t.state != "Refundable":
            raise Revert("NoRefund")
        self.wallet[user] = self.wallet.get(user, 0) + t.amount
        del self.tickets[user]

    def claim(self, user: str):
        t = self.tickets.get(user)
        if t is None or t.state != "Pending":
            raise Revert("NoClaim")
        b = self.batches[t.batch]
        if b.status == "Voided":
            self.wallet[user] = self.wallet.get(user, 0) + t.amount
        elif b.status == "Settled":
            c = t.amount * b.minted // b.total
            b.vault -= c
            self.pool.tokens["vault"] -= c
            self.pool.tokens[user] = self.pool.tokens.get(user, 0) + c
            self.claimed[user] = self.claimed.get(user, 0) + c
        else:
            raise Revert("NotSettled")
        b.unresolved -= 1
        del self.tickets[user]

    def close_batch(self, epoch: int):
        b = self.batches[epoch]
        if b.status == "Open" or b.unresolved:
            raise Revert("NotClosable")
        if b.vault:
            self.pool.burn("vault", b.vault)     # dust returns to all holders
            b.vault = 0

    # ---- settlement ---------------------------------------------------
    def settle(self, epoch: int, wrong_pairs: frozenset = frozenset()):
        p = self.pool
        b = self.batches.get(epoch)
        if b is None or b.status != "Open" or p.epoch <= epoch:
            raise Revert("NotSettleable")
        if self.paused:
            raise Revert("Paused")
        snapshot = copy.deepcopy(p)
        try:
            if self.design in ("batch", "escrowmint"):
                for i in range(len(p.entries)):
                    p.vlb(i)                       # program-verified pairs
                p.spb()
            elif self.design == "wrongpair":
                for i in range(len(p.entries)):
                    p.vlb(i, correct_pair=i not in wrong_pairs)
                p.spb()
            elif self.design == "nonatomic":
                p.spb()                            # trusts earlier VLBs (fails if stale)
            else:
                raise AssertionError(self.design)
            if self.design == "escrowmint":
                self._settle_escrowmint(b)
                return
            if b.total == 0:
                b.status = "Settled"
                return
            n = mint_amount(b.total, p.t, p.s)
            if n == 0:
                b.status = "Voided"
                return
            pre_value_others = self._value_excluding("vault")
            got = p.deposit_sol("vault", b.total)
            b.minted = b.vault = got
            b.status = "Settled"
            price = p.price()
            b.settle_price = price
            b.transfer = got * price - b.total
            self.records.append(dict(
                design=self.design, epoch=epoch, total=b.total, minted=got,
                transfer=b.transfer, price=price,
                others_delta=self._value_excluding("vault") - pre_value_others + b.transfer))
        except Revert:
            self.pool = snapshot
            raise

    def _settle_escrowmint(self, b: Batch):
        p = self.pool
        lb, tb = b.esc_lamports, b.esc_tokens
        if lb == 0:
            b.status = "Settled"
            return
        la, ta = self.escrow_lamports, self.escrow_tokens   # all unsettled batches
        # incumbent price excludes every escrowed lamport and token of every batch
        t_star = lb * (p.sigma - ta) // (p.t - la)
        if t_star > tb:
            give = tb
            shortfall = t_star - tb
        else:
            p.burn("escrow", tb - t_star)
            p.spb()                               # re-sync S := Sigma (r = 0, no fee)
            give, shortfall = t_star, 0
        p.tokens["escrow"] -= give
        p.tokens["vault"] = p.tokens.get("vault", 0) + give
        b.minted = b.vault = give
        b.total = lb
        b.status = "Settled"
        self.escrow_lamports -= lb
        self.escrow_tokens -= tb
        # value yardstick for this batch: price that excludes the OTHER batches' escrow
        others_l, others_t = self.escrow_lamports, self.escrow_tokens
        obs_t, obs_s = p.observe()
        price = Fraction(obs_t - others_l, obs_s - others_t)
        b.settle_price = price
        b.transfer = give * price - lb
        rec = dict(design="escrowmint", epoch=b.epoch, total=lb, minted=give,
                   transfer=b.transfer, price=price)
        if shortfall:
            rec["shortfall"] = shortfall
        self.records.append(rec)

    def _immediate(self, user: str, l: int):
        p = self.pool
        if self.design == "fresh":
            for i in range(len(p.entries)):
                p.vlb(i)
            p.spb()
        got = p.deposit_sol(user, l)
        self.claimed[user] = self.claimed.get(user, 0) + got
        self.paid_in[user] = self.paid_in.get(user, 0) + l
        price = p.price()
        self.immediate_records.append(dict(design=self.design, l=l, minted=got,
                                           transfer=got * price - l, price=price))

    def _value_excluding(self, holder: str) -> Fraction:
        price = self.pool.price()
        return sum(Fraction(v) * price for k, v in self.pool.tokens.items() if k != holder)


def jsonable(x):
    if isinstance(x, Fraction):
        return str(x) if x.denominator != 1 else x.numerator
    if isinstance(x, dict):
        return {k: jsonable(v) for k, v in x.items()}
    if isinstance(x, list):
        return [jsonable(v) for v in x]
    return x


if __name__ == "__main__":
    print("import this module; run check_iv4.py", file=sys.stderr)
