"""Independent exact-expectation audit of run_v21_cost_matched_adaptive_surface.py.

Derived directly from the generator (not copied from the prior review):
  y ~ Bern(.5); covered ~ Bern(c); available at checkpoint t iff covered and t >= d  -> a = c(4-d)/4
  initial correct w.p. rho; q1 acc = h if initial==1 else l; q2 acc = l if initial==1 else h
  P(initial==1) = .5 for every rho  -> marginal acc(q1) = marginal acc(q2) = (h+l)/2
  active signal = q1 if initial==1 else q2  -> acc = h always (oracle routing)
  F(signal) = p if signal==1 else 1-p ; loss if correct (1-p)^2, if wrong p^2 -> B(u,p) = p^2 + (1-2p)u
Also computes a per-cell MC standard error (per-target variance / n) to z-score the GPU rows,
and a Bayes-posterior-F variant (uses initial + follow-up, knows reliabilities) as a what-if.
"""
from fractions import Fraction as Fr
from itertools import product
import json, math, sys
from pathlib import Path

ROOT = Path("/mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/"
            "disastertrace-starter/artifacts/v21_execution_20260925_04")
REPS = ("5090a", "5090b", "h100_share")
NONACT = ("fixed", "no_extra", "source_rr", "source_hash")
EQ2 = ("source_rr", "source_hash")
RHO = (0.60, 0.70, 0.80, 0.90); HI = (0.70, 0.85, 0.95); LO = (0.50, 0.60)
DEL = (0, 1, 2, 3); COV = (0.50, 1.00); PH = (0.65, 0.80)


def B(u, p):
    return p * p + (1 - 2 * p) * u


def per_target_var(u, p, c, d):
    """Variance of the per-target mean-over-4-checkpoints loss when the forecast signal has acc u."""
    f = Fr(4 - d, 4)
    # covered: L = .25(1-f) + f*l, l in {(1-p)^2 w.p. u, p^2 w.p. 1-u}; uncovered: .25
    vals = [(1 - c, Fr(1, 4)), (c * u, Fr(1, 4) * (1 - f) + f * (1 - p) ** 2), (c * (1 - u), Fr(1, 4) * (1 - f) + f * p * p)]
    m = sum(w * v for w, v in vals)
    return sum(w * (v - m) ** 2 for w, v in vals)


def bayes_brier(prior_terms):
    """Expected Brier of the exact posterior given conditionally independent binary signals.
    prior_terms: list of accuracies (each signal correct w.p. acc, indep given y). y ~ Bern(.5)."""
    tot = Fr(0)
    for obs in product((0, 1), repeat=len(prior_terms)):
        l1 = Fr(1, 2); l0 = Fr(1, 2)
        for o, acc in zip(obs, prior_terms):
            l1 *= acc if o == 1 else 1 - acc
            l0 *= acc if o == 0 else 1 - acc
        z = l1 + l0
        if z == 0:
            continue
        pi = l1 / z
        tot += z * pi * (1 - pi)  # E[(pi - y)^2 | obs] = pi(1-pi)
    return tot


def main():
    reps = {r: json.loads((ROOT / "cost_matched_gpu" / r / "result.json").read_text()) for r in REPS}
    cells = []
    for i, (r, h, l, d, c, p) in enumerate(product(RHO, HI, LO, DEL, COV, PH)):
        R, H, L, C, P = (Fr(str(x)) for x in (r, h, l, c, p))
        a = C * (4 - d) / 4
        base = Fr(1, 4) * (1 - a)
        ex = {"fixed": Fr(1, 4), "no_extra": base + a * B(R, P), "source_rr": base + a * B((H + L) / 2, P),
              "source_hash": base + a * B((H + L) / 2, P), "active": base + a * B(H, P)}
        acc = {"fixed": None, "no_extra": R, "source_rr": (H + L) / 2, "source_hash": (H + L) / 2, "active": H}
        # Bayes-F what-if: all acquired evidence, calibrated posterior; rr knows q1 acc depends on initial
        # rr/hash: with prob .5 initial==1 (q1 acc h), .5 initial==0 (q1 acc l). But P(initial==1)=.5 is
        # marginal; conditioning is on the observed initial so compute exactly by enumerating initial.
        def bayes_rr():
            # enumerate y, initial, q1 jointly
            tot = Fr(0)
            for i0 in (0, 1):
                qacc = H if i0 == 1 else L
                for q in (0, 1):
                    l1 = Fr(1, 2) * (R if i0 == 1 else 1 - R) * (qacc if q == 1 else 1 - qacc)
                    l0 = Fr(1, 2) * (R if i0 == 0 else 1 - R) * (qacc if q == 0 else 1 - qacc)
                    z = l1 + l0
                    if z:
                        pi = l1 / z; tot += z * pi * (1 - pi)
            return tot
        bayes = {"no_extra": bayes_brier([R]), "source_rr": bayes_rr(), "active": bayes_brier([R, H])}
        bayes = {k: base + a * v for k, v in bayes.items()}
        row = {"cell": i, "rho": r, "hi": h, "lo": l, "delay": d, "coverage": c, "p_high": p, "exact": ex, "acc": acc, "bayes": bayes}
        mc = {}
        for rep in REPS:
            rr = reps[rep]["rows"][i]
            assert (rr["rho_initial"], rr["followup_high"], rr["followup_low"], rr["delay_checkpoints"], rr["coverage"], rr["p_high"]) == (r, h, l, d, c, p)
            mc[rep] = rr["method_losses"]
        row["mc"] = mc
        cells.append(row)

    n = 500_000
    out = {}
    maxdev = 0.0; maxz = 0.0; worst = None
    sign_mismatch_best = 0; sign_mismatch_eq2 = 0
    best_method_counts = {}
    for row in cells:
        ex = row["exact"]
        ex_best = min(ex[m] for m in NONACT)
        ex_delta = ex["active"] - ex_best
        ex_eq2 = ex["active"] - min(ex[m] for m in EQ2)
        row["ex_delta"] = ex_delta; row["ex_eq2"] = ex_eq2
        row["ex_best_methods"] = [m for m in NONACT if ex[m] == ex_best]
        for rep, ml in row["mc"].items():
            for m in ex:
                dev = abs(ml[m] - float(ex[m]))
                if m != "fixed":
                    se = math.sqrt(float(per_target_var(row["acc"][m], Fr(str(row["p_high"])), Fr(str(row["coverage"])), row["delay"])) / n)
                    z = dev / se if se > 0 else 0.0
                    if z > maxz:
                        maxz = z
                if dev > maxdev:
                    maxdev = dev; worst = (row["cell"], rep, m, ml[m], float(ex[m]))
            mc_best_m = min(NONACT, key=lambda m: ml[m])
            best_method_counts[mc_best_m] = best_method_counts.get(mc_best_m, 0) + 1
            mc_delta = ml["active"] - ml[mc_best_m]
            mc_eq2 = ml["active"] - min(ml[m] for m in EQ2)
            sgn = lambda x: (x > 0) - (x < 0)
            if sgn(mc_delta) != sgn(float(ex_delta)):
                sign_mismatch_best += 1
            if sgn(mc_eq2) != sgn(float(ex_eq2)):
                sign_mismatch_eq2 += 1
    # MC aggregate recompute
    mc_deltas = []; mc_wins = 0; mc_eq2_wins = 0; mc_eq2 = []; mc_fix = []
    for row in cells:
        for rep, ml in row["mc"].items():
            dlt = ml["active"] - min(ml[m] for m in NONACT)
            mc_deltas.append(dlt); mc_wins += dlt < 0
            e2 = ml["active"] - min(ml[m] for m in EQ2); mc_eq2.append(e2); mc_eq2_wins += e2 < 0
            mc_fix.append(ml["active"] - ml["fixed"])
    ex_deltas = [r["ex_delta"] for r in cells]
    exw = sum(x < 0 for x in ex_deltas); ext = sum(x == 0 for x in ex_deltas); exl = sum(x > 0 for x in ex_deltas)
    tie_cells = [r for r in cells if r["ex_delta"] == 0]
    tie_mc_wins = sum(ml["active"] < ml["no_extra"] for r in tie_cells for ml in r["mc"].values())
    # rho=0.9 stratum vs equal-cost
    rho9_eq2 = [float(r["ex_eq2"]) for r in cells if r["rho"] == 0.9]
    # Bayes what-if
    b_act_minus_rr = [float(r["bayes"]["active"] - r["bayes"]["source_rr"]) for r in cells]
    b_act_minus_noextra = [float(r["bayes"]["active"] - r["bayes"]["no_extra"]) for r in cells]
    b_rr_minus_noextra = [float(r["bayes"]["source_rr"] - r["bayes"]["no_extra"]) for r in cells]
    summ = {
        "cells": len(cells),
        "max_abs_dev_mc_vs_exact_any_method": maxdev, "worst": worst,
        "max_z_mc_vs_exact": maxz,
        "exact_mean_active_minus_best_nonactive": float(sum(ex_deltas) / len(ex_deltas)),
        "mc_mean_active_minus_best_nonactive_1152": sum(mc_deltas) / len(mc_deltas),
        "exact_wins_ties_losses_per_replica": (exw, ext, exl),
        "tie_cell_definition": sorted({(r["rho"], r["hi"]) for r in tie_cells}),
        "tie_cells_mc_active_beats_no_extra_of_96": tie_mc_wins,
        "mc_wins_vs_best_nonactive_1152": mc_wins,
        "sign_mismatch_best_nonactive_of_1152": sign_mismatch_best,
        "mc_best_nonactive_method_counts": best_method_counts,
        "exact_best_nonactive_method_counts": {m: sum(m in r["ex_best_methods"] for r in cells) for m in NONACT},
        "exact_mean_active_minus_fixed": float(sum(r["exact"]["active"] - r["exact"]["fixed"] for r in cells) / len(cells)),
        "mc_mean_active_minus_fixed": sum(mc_fix) / len(mc_fix),
        "exact_eq2_all_negative": all(r["ex_eq2"] < 0 for r in cells),
        "exact_eq2_mean": float(sum(r["ex_eq2"] for r in cells) / len(cells)),
        "exact_eq2_min_max": (float(min(r["ex_eq2"] for r in cells)), float(max(r["ex_eq2"] for r in cells))),
        "closed_form_check": all(r["ex_eq2"] == -Fr(str(r["coverage"])) * (4 - r["delay"]) / 4 * (2 * Fr(str(r["p_high"])) - 1) * (Fr(str(r["hi"])) - Fr(str(r["lo"]))) / 2 for r in cells),
        "mc_eq2_wins_of_1152": mc_eq2_wins, "mc_eq2_mean": sum(mc_eq2) / len(mc_eq2),
        "sign_mismatch_eq2_of_1152": sign_mismatch_eq2,
        "rho0.9_exact_active_minus_eq2_max": max(rho9_eq2),
        "rr_equals_hash_exact_all": all(r["exact"]["source_rr"] == r["exact"]["source_hash"] for r in cells),
        "rr_hash_indep_of_rho": True,
        "bayesF_whatif": {
            "active_minus_rr_mean": sum(b_act_minus_rr) / len(cells), "active_minus_rr_max": max(b_act_minus_rr),
            "active_minus_noextra_mean": sum(b_act_minus_noextra) / len(cells),
            "rr_minus_noextra_max": max(b_rr_minus_noextra),
        },
    }
    Path("/tmp/dt_review/agent_synth/cost_matched_audit.json").write_text(json.dumps(summ, indent=2, default=str) + "\n")
    print(json.dumps(summ, indent=2, default=str))


if __name__ == "__main__":
    main()
