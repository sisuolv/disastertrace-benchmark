"""Numpy port of cost_matched `_one` (same logic, different RNG) + Bayes-posterior-F what-if, small n.
Cross-checks the exact formulas in cost_matched_audit.py for a handful of cells."""
import json, numpy as np
from fractions import Fraction as Fr

rng = np.random.default_rng(7)
N = 400_000; T = 4


def B(u, p):
    return p * p + (1 - 2 * p) * u


def one(rho, h, l, d, c, p):
    y = (rng.random(N) >= .5).astype(np.float64)
    cov = rng.random(N) < c
    avail = cov[:, None] & (np.arange(T)[None, :] >= d)
    ini = np.where(rng.random(N) < rho, y, 1 - y)
    q1p = np.where(ini > .5, h, l); q2p = np.where(ini > .5, l, h)
    q1 = np.where(rng.random(N) < q1p, y, 1 - y); q2 = np.where(rng.random(N) < q2p, y, 1 - y)
    act = np.where(ini > .5, q1, q2)
    F = lambda s: np.where(s > .5, p, 1 - p)
    loss = lambda pred: float(((np.where(avail, pred[:, None], .5) - y[:, None]) ** 2).mean())
    # Bayes posterior using BOTH acquired signals and the true (oracle) reliabilities
    def post(s0, a0, s1, a1):
        l1 = np.where(s0 > .5, a0, 1 - a0) * np.where(s1 > .5, a1, 1 - a1)
        l0 = np.where(s0 < .5, a0, 1 - a0) * np.where(s1 < .5, a1, 1 - a1)
        return l1 / (l1 + l0)
    out = {"no_extra": loss(F(ini)), "source_rr": loss(F(q1)), "source_hash": loss(F(q2)), "active": loss(F(act)),
           "bayes_rr": loss(post(ini, rho, q1, q1p)), "bayes_active": loss(post(ini, rho, act, h))}
    a = c * (4 - d) / 4
    ex = {"no_extra": .25 * (1 - a) + a * B(rho, p), "source_rr": .25 * (1 - a) + a * B((h + l) / 2, p),
          "active": .25 * (1 - a) + a * B(h, p)}
    return out, ex


res = []
for cell in [(0.6, 0.95, 0.5, 0, 1.0, 0.8), (0.9, 0.7, 0.6, 1, 0.5, 0.65), (0.7, 0.7, 0.5, 2, 1.0, 0.8), (0.9, 0.85, 0.5, 0, 1.0, 0.8)]:
    mc, ex = one(*cell)
    res.append({"cell": cell, "mc": {k: round(v, 5) for k, v in mc.items()}, "exact": {k: round(v, 5) for k, v in ex.items()}})
print(json.dumps(res, indent=1))
Path = __import__("pathlib").Path
Path("/tmp/dt_review/agent_synth/numpy_port_check.json").write_text(json.dumps(res, indent=1) + "\n")
