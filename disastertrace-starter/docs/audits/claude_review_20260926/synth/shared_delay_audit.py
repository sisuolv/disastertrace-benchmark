"""Independent exact-expectation audit of run_v21_shared_delay_surface.py.

From the generator: a = c(4-d)/4, B(u,p) = p^2 + (1-2p)u
  fixed    = .25
  no_extra = .25(1-a) + a B(rho,p)   if d == 0 else .25    (literally the same tensor as active when d==0)
  rr       = .25(1-a) + a B(rho,p)   (fresh signal each available checkpoint, SAME acc rho, SAME p, F uses only
                                      the current signal -> identical expectation to active; costs up to 4-d queries)
  hash     = .25(1-a) + a B(rho,.65) (same shared signal as active, p fixed at .65 -> identical tensor to active if p=.65)
  active   = .25(1-a) + a B(rho,p)   (one shared signal, no adaptivity at all)
"""
from fractions import Fraction as Fr
from itertools import product
import json, math
from pathlib import Path

ROOT = Path("/mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/"
            "disastertrace-starter/artifacts/v21_execution_20260925_04/shared_delay_gpu")
REPS = ("5090a", "5090b", "h100_share")
NONACT = ("fixed", "no_extra", "source_rr", "source_hash")
RHOS = (0.50, 0.60, 0.70, 0.80, 0.90, 1.00); DELAYS = (0, 1, 2, 3); COVS = (0.50, 0.75, 1.00); PHS = (0.65, 0.80)


def B(u, p):
    return p * p + (1 - 2 * p) * u


def main():
    reps = {r: json.loads((ROOT / r / "result.json").read_text()) for r in REPS}
    rows = []
    idx = 0
    for p, c, d, r in product(PHS, COVS, DELAYS, RHOS):
        P, C, R = Fr(str(p)), Fr(str(c)), Fr(str(r))
        a = C * (4 - d) / 4
        base = Fr(1, 4) * (1 - a)
        ex = {"fixed": Fr(1, 4), "no_extra": base + a * B(R, P) if d == 0 else Fr(1, 4),
              "source_rr": base + a * B(R, P), "source_hash": base + a * B(R, Fr(13, 20)), "active": base + a * B(R, P)}
        mc = {}
        for rep in REPS:
            row = reps[rep]["rows"][idx]
            assert (row["rho"], row["delay_checkpoints"], row["coverage"], row["p_high"]) == (r, d, c, p)
            mc[rep] = row["method_losses"]
        rows.append({"idx": idx, "rho": r, "d": d, "c": c, "p": p, "ex": ex, "mc": mc,
                     "queries_per_covered_target": {"fixed": 0, "no_extra": 1 if d == 0 else 0, "source_rr": 4 - d, "source_hash": 1, "active": 1}})
        idx += 1
    assert idx == 144
    # Recompute published aggregate from result files (1-ulp-free: exact float compare for ties like the aggregate)
    deltas, fixd, wins, ties, losses = [], [], 0, 0, 0
    maxdev = 0.0; best_counts = {}
    win_rows = []
    identity_active_eq_hash = identity_active_eq_noextra = 0
    for row in rows:
        for rep, ml in row["mc"].items():
            b = min(ml[m] for m in NONACT)
            bm = min(NONACT, key=lambda m: ml[m]); best_counts[bm] = best_counts.get(bm, 0) + 1
            dlt = ml["active"] - b
            deltas.append(dlt); fixd.append(ml["active"] - ml["fixed"])
            if dlt < 0:
                wins += 1; win_rows.append((row["rho"], row["d"], row["c"], row["p"], rep, dlt, "beat:" + bm))
            elif dlt == 0:
                ties += 1
            else:
                losses += 1
            if row["p"] == 0.65 and ml["active"] == ml["source_hash"]:
                identity_active_eq_hash += 1
            if row["d"] == 0 and ml["active"] == ml["no_extra"]:
                identity_active_eq_noextra += 1
            for m in NONACT + ("active",):
                maxdev = max(maxdev, abs(ml[m] - float(row["ex"][m])))
    ex_d = [row["ex"]["active"] - min(row["ex"][m] for m in NONACT) for row in rows]
    active_minus_rr_mc = [ml["active"] - ml["source_rr"] for row in rows for ml in row["mc"].values()]
    # decomposition of exact gap
    src = {"fixed": 0, "source_hash": 0, "none(active==rr)": 0}
    for row, e in zip(rows, ex_d):
        if e == 0:
            src["none(active==rr)"] += 1
        else:
            bm = min(("fixed", "source_hash", "no_extra"), key=lambda m: row["ex"][m]); src[bm] = src.get(bm, 0) + 1
    # hindsight-min bias: E[active - min] where active==rr in expectation -> positive by construction
    out = {
        "rows_mc": len(deltas),
        "mc_mean_active_minus_fixed": sum(fixd) / len(fixd),
        "exact_mean_active_minus_fixed": float(sum(r["ex"]["active"] - r["ex"]["fixed"] for r in rows) / 144),
        "exact_mean_rr_minus_fixed": float(sum(r["ex"]["source_rr"] - r["ex"]["fixed"] for r in rows) / 144),
        "mc_mean_active_minus_best_nonactive": sum(deltas) / len(deltas),
        "exact_mean_active_minus_best_nonactive": float(sum(ex_d) / 144),
        "mc_wins_ties_losses": (wins, ties, losses),
        "exact_active_strict_wins": sum(e < 0 for e in ex_d), "exact_ties": sum(e == 0 for e in ex_d), "exact_losses": sum(e > 0 for e in ex_d),
        "exact_active_equals_rr_all_cells": all(r["ex"]["active"] == r["ex"]["source_rr"] for r in rows),
        "mc_active_minus_rr_mean": sum(active_minus_rr_mc) / len(active_minus_rr_mc),
        "mc_active_minus_rr_maxabs": max(abs(x) for x in active_minus_rr_mc),
        "exact_gap_source_counts": src,
        "mc_best_nonactive_method_counts": best_counts,
        "mc_wins_detail_first10": win_rows[:10],
        "mc_wins_beaten_method_counts": {k: sum(w[-1] == "beat:" + k for w in win_rows) for k in NONACT},
        "bitwise_identity_active_eq_hash_at_p065_of_216": identity_active_eq_hash,
        "bitwise_identity_active_eq_noextra_at_d0_of_108": identity_active_eq_noextra,
        "max_abs_dev_mc_vs_exact": maxdev,
        "queries_per_covered_target_note": "rr=4-d fresh retrievals; active/hash=1; no_extra=1 only if d==0",
    }
    Path("/tmp/dt_review/agent_synth/shared_delay_audit.json").write_text(json.dumps(out, indent=2, default=str) + "\n")
    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
