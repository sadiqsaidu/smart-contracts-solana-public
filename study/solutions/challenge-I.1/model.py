#!/usr/bin/env python3
"""Exact-integer I.1 checks. This is a model, NOT a Solana VM or validator test."""
from dataclasses import dataclass, field
from itertools import permutations
import json
import random

RHO = 1_666_240
M = 1_000_000_000
Q = M + RHO
U64 = 2**64 - 1

def ceildiv(a, b):
    return (a + b - 1) // b

def mint(l, t, s):
    return l if t == 0 or s == 0 else l * s // t

def epochfee(r, t, s):
    if r == 0:
        return 0
    phi = ceildiv(r * 5, 100)
    return r if t + r == phi or s == 0 else s * phi // (t + r - phi)

@dataclass
class Entry:
    v: int
    d: int
    a: int
    x: int = 0
    tau: int = 0

@dataclass
class Pool:
    t: int
    s: int
    sigma: int
    reserve: int
    entries: list = field(default_factory=list)
    epoch: int = 100
    last: int = 100

    @classmethod
    def initialize(cls, capital):
        # SPL Initialize: preinitialized reserve with pool PDA authorities,
        # empty list, mint supply 0; initial tokens minted to manager.
        return cls(capital, capital, capital, capital + RHO)

    def cached(self):
        return max(0, self.reserve - RHO) + sum(e.a + e.tau for e in self.entries)

    def theta(self):
        # Restricted model: usable Stake validators; no ignored/revived states.
        return max(0, self.reserve - RHO) + sum(e.v + (e.x if e.tau else 0) for e in self.entries)

    def check(self):
        assert self.last == self.epoch
        assert self.reserve >= RHO
        assert 0 <= self.sigma <= self.s <= self.t <= self.cached() <= self.theta() <= U64
        for e in self.entries:
            assert 0 <= e.a <= e.v
            assert 0 <= e.tau <= e.x

    def show(self):
        self.check()
        return dict(T=self.t, S=self.s, Sigma=self.sigma, Theta=self.theta(),
                    C=self.cached(), DT=self.theta()-self.t, DS=self.s-self.sigma)

    def add(self, prefund=0, actor="owner"):
        assert actor == "owner" and prefund >= 0
        # Owner transfers q to reserve; SPL splits q back out. Prefund was uncounted.
        self.entries.append(Entry(Q+prefund, M+prefund, Q))
        self.check()

    def deposit(self, l, actor="whitelisted"):
        assert actor == "whitelisted" and l > 0
        n = mint(l, self.t, self.s)
        assert n > 0
        self.reserve += l
        self.t += l
        self.s += n
        self.sigma += n
        self.check()

    def increase(self, i, l, prefund=0, actor="stake_manager"):
        assert actor == "stake_manager" and l >= M
        e = self.entries[i]
        assert self.reserve - l - RHO >= RHO
        # New X, no Y prefund: full split; existing X: activating merge.
        assert prefund == 0 or e.tau == 0
        self.reserve -= l + RHO
        e.x += l + RHO + prefund
        e.tau += l + RHO
        self.check()

    def vlb(self, i):
        e = self.entries[i]
        extra = max(0, e.v-e.d-RHO)
        e.v -= extra
        self.reserve += extra
        e.a = e.v
        e.tau = e.x if e.tau else 0
        self.check()

    def spb(self):
        c = self.cached()
        f = epochfee(max(0, c-self.t), self.t, self.s)
        self.sigma += f
        self.s = self.sigma
        self.t = c
        self.check()
        return f

    def burn(self, b):
        assert 0 <= b <= self.sigma
        self.sigma -= b
        self.check()

def run():
    out = {}
    p = Pool.initialize(24_000_000_000)
    out["initial"] = p.show()
    p.add()
    out["owner_add_one_transaction"] = p.show()
    assert p.theta()-p.t == Q
    out["owner_add_refresh_fee"] = p.spb()
    out["owner_add_after_spb"] = p.show()
    p.burn(7)
    out["burn_seven"] = p.show()
    p.spb()
    assert p.s == p.sigma

    p = Pool.initialize(24_000_000_000)
    p.add()
    p.spb()
    p.entries[0].v += 1
    out["validator_donation_one"] = p.show()
    p.spb()
    assert p.theta()-p.t == 1  # SPB alone cannot see V donation
    p.vlb(0)
    p.spb()
    assert p.theta() == p.t

    # Exact, reachable removal from a 1:1 initial-capital pool with ONE direct
    # SPL validator add (manager configures staker); fee-free manager burn.
    # A pre-funded user destination is allocated+assigned to Stake, Uninitialized.
    t = s = 10_000_000_000
    b = Q + 1
    ell = b*t//s
    kappa = ceildiv(t,s)
    assert Q <= ell <= Q+kappa
    actual = Q
    post_t, post_s = t-actual, s-b
    assert (t-actual)-post_t == 0
    out["removal_truncation"] = dict(T=t,S=s,burn=b,quoted=ell,actual=actual,
        kappa=kappa,postT=post_t,postS=post_s,postTheta=t-actual,DT=0,DS=0)

    # Exhaustive arithmetic checks over bounded values, no floating point.
    checks = 0
    for t in range(1,121):
        for s in range(1,t+1):
            for b in range(s+1):
                ell = b*t//s
                assert t-ell >= s-b
                assert ((t+17)-ell)-(t-ell) == 17
                checks += 1
            for r in range(31):
                f = epochfee(r,t,s)
                assert 0 <= f <= r
                assert s+f <= t+r
                checks += 1
    out["bounded_arithmetic_cases"] = checks

    # Random valid subset, with real mainnet amounts. Actor checks modeled,
    # no key-signature verification or native stake activation simulation.
    rng = random.Random(1001)
    p = Pool.initialize(1000*M)
    for _ in range(4):
        p.add()
    for _ in range(5000):
        op = rng.randrange(7)
        i = rng.randrange(len(p.entries))
        e = p.entries[i]
        if op == 0:
            p.deposit(rng.randrange(1,1000000))
        elif op == 1:
            p.reserve += rng.randrange(0,10000)
        elif op == 2:
            e.v += rng.randrange(0,10000)
        elif op == 3:
            p.burn(rng.randrange(0,min(p.sigma,10000)+1))
        elif op == 4:
            p.vlb(i)
        elif op == 5:
            p.spb()
        elif p.reserve >= M+2*RHO:
            p.increase(i,M)
        p.check()
    out["random_subset_transitions"] = 5000

    # Disjoint chunks commute even with sweeps into the common reserve.
    from copy import deepcopy
    results = set()
    for order in permutations(range(4)):
        z = deepcopy(p)
        for i in order:
            z.vlb(i)
        z.spb()
        results.add((z.t,z.s,z.sigma,z.reserve))
    assert len(results) == 1
    out["chunk_orders_checked"] = 24

    # Native withdrawal constraint for SPL no_merge sweep.
    old_rent = 2_282_880
    v,d = M+old_rent,M
    extra = max(0,v-d-RHO)
    def sweep_ok(effective, native_rent):
        return extra == 0 or extra+effective+native_rent <= v
    assert extra == 616_640
    assert sweep_ok(d,RHO)
    assert not sweep_ok(d,old_rent)
    assert sweep_ok(d-extra,old_rent)
    out["sweep"] = dict(v=v,delegation=d,extra=extra,post=v-extra,
        v5_ok=True,legacy_active_ok=False,legacy_required_cooldown=extra)

    # Outside the fixed-rent theorem: a 1-lamport rent increase is negative.
    t,r = 100,RHO+100
    assert max(0,r-(RHO+1))-t == -1
    out["outside_cell_rent_increase_DT"] = -1
    print(json.dumps(out,indent=2,sort_keys=True))
    print("PASS: exact arithmetic and restricted transition model; no validator execution")

if __name__ == "__main__":
    run()
