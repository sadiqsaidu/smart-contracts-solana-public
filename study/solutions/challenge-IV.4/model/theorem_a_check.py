#!/usr/bin/env python3
"""Exact check of the Theorem A separation inequality (CONJECTURE.md, Lemma A2).

From a reconciled state (D_T = D_S = 0, so Theta* = T and Sigma* = Sigma = S), a credit z to an
unread validator account gives Theta*' = T + z and Sigma*' = S + f(z), with f the SPL epoch fee.
Claim: L*S/T - L*(S + f(z))/(T + z) >= L*S*(19*z - 20)/(20*T*(T + z)).
"""
import json, random, sys
from fractions import Fraction
sys.path.insert(0, __import__("os").path.dirname(__file__))
from batch_model import epochfee

rng = random.Random(4)
worst = None
cases = 0
for _ in range(200_000):
    T = rng.randrange(1, 10**18)
    S = rng.randrange(1, 10**18)
    z = rng.choice([1, 2, 19, 20, 21, rng.randrange(1, 10**6), rng.randrange(1, 10**18)])
    L = rng.randrange(1, 10**15)
    f = epochfee(z, T, S)
    lhs = Fraction(L * S, T) - Fraction(L * (S + f), T + z)
    rhs = Fraction(L * S * (19 * z - 20), 20 * T * (T + z))
    assert lhs >= rhs, (T, S, z, L, f)
    cases += 1
    ratio = (lhs - rhs) / (Fraction(L * S, T) + 1)
    worst = ratio if worst is None or ratio < worst else worst
# live mainnet numbers, z = T: separation as a fraction of the fair allocation
T, S, L = 66_101_088_311, 16_407_030_513, 100_000_000_000
z = T
f = epochfee(z, T, S)
sep = Fraction(L * S, T) - Fraction(L * (S + f), T + z)
print(json.dumps(dict(cases=cases, inequality_holds=True,
                      live_example=dict(T=T, S=S, L=L, z=z, fee_tokens=f,
                                        fair_tokens_credit_after=float(Fraction(L * S, T)),
                                        fair_tokens_credit_before=float(Fraction(L * (S + f), T + z)),
                                        separation_tokens=float(sep),
                                        separation_fraction_of_fair=float(sep / Fraction(L * S, T)))), indent=1))
