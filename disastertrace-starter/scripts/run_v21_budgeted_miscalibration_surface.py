"""Synthetic finite-budget selection surface with prior/reliability error.

This diagnostic keeps the true target process separate from the estimates used
by every query policy.  It tests whether uncertainty-aware selection remains
useful when the active policy does not know the true prior or signal
reliability.  It is not a weather or provider evaluation.
"""

from __future__ import annotations

import argparse
import json
import platform
import time
from pathlib import Path

import torch


RHOS = (0.55, 0.65, 0.75, 0.85, 0.95)
HETEROGENEITIES = (0.10, 0.30, 0.45)
BUDGETS = (0.10, 0.25, 0.50, 0.75)
CALIBRATIONS = {
    "calibrated": (1.0, 0.0),
    "underconfident": (0.5, -0.10),
    "overconfident": (1.5, 0.10),
}
METHODS = ("fixed", "uniform_query", "hash_query", "active_query")


def _posterior(q: torch.Tensor, signal: torch.Tensor, rho: float) -> torch.Tensor:
    one = signal > 0.5
    numerator = torch.where(one, q * rho, q * (1.0 - rho))
    denominator = torch.where(
        one,
        q * rho + (1.0 - q) * (1.0 - rho),
        q * (1.0 - rho) + (1.0 - q) * rho,
    )
    return numerator / denominator


def _loss(prediction: torch.Tensor, y: torch.Tensor) -> float:
    return float((prediction - y).square().mean().item())


def _one(*, rho: float, heterogeneity: float, budget: float, calibration: str, n: int, seed: int, device: torch.device) -> dict:
    if rho <= 0.5 or not 0.0 < heterogeneity < 0.5 or not 0.0 < budget <= 1.0:
        raise ValueError("invalid surface cell")
    scale, rho_bias = CALIBRATIONS[calibration]
    generator = torch.Generator(device=device)
    generator.manual_seed(seed)
    q_true = (0.5 + heterogeneity * (2.0 * torch.rand(n, generator=generator, device=device) - 1.0)).clamp(0.01, 0.99)
    y = (torch.rand(n, generator=generator, device=device) < q_true).to(torch.float32)
    correct = torch.rand(n, generator=generator, device=device) < rho
    signal = torch.where(correct, y, 1.0 - y)
    q_est = (0.5 + scale * (q_true - 0.5)).clamp(0.01, 0.99)
    rho_est = min(0.99, max(0.51, rho + rho_bias))
    posterior = _posterior(q_est, signal, rho_est)
    query_count = min(n, max(1, int(round(budget * n))))
    order = torch.rand(n, generator=generator, device=device)
    uniform_indices = order.topk(query_count, sorted=False).indices
    hash_indices = torch.arange(n, device=device)[:query_count]
    active_indices = (q_est * (1.0 - q_est)).topk(query_count, sorted=False).indices
    predictions = {
        "fixed": q_est,
        "uniform_query": q_est.clone(),
        "hash_query": q_est.clone(),
        "active_query": q_est.clone(),
    }
    predictions["uniform_query"][uniform_indices] = posterior[uniform_indices]
    predictions["hash_query"][hash_indices] = posterior[hash_indices]
    predictions["active_query"][active_indices] = posterior[active_indices]
    losses = {method: _loss(prediction, y) for method, prediction in predictions.items()}
    return {
        "rho_true": rho,
        "rho_est": rho_est,
        "heterogeneity": heterogeneity,
        "budget": budget,
        "calibration": calibration,
        "n_targets": n,
        "query_count": query_count,
        "seed": seed,
        "method_losses": losses,
        "active_minus_uniform": losses["active_query"] - losses["uniform_query"],
        "active_minus_best_non_active": losses["active_query"] - min(losses[m] for m in METHODS if m != "active_query"),
    }


def run(*, out: Path, n: int, seed: int, device_name: str) -> dict:
    if n <= 1:
        raise ValueError("n must exceed one")
    if device_name == "auto":
        device_name = "cuda" if torch.cuda.is_available() else "cpu"
    if device_name.startswith("cuda") and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable")
    device = torch.device(device_name)
    started = time.time()
    rows = []
    cell = 0
    for calibration in CALIBRATIONS:
        for heterogeneity in HETEROGENEITIES:
            for budget in BUDGETS:
                for rho in RHOS:
                    rows.append(_one(rho=rho, heterogeneity=heterogeneity, budget=budget, calibration=calibration, n=n, seed=seed + 1009 * cell, device=device))
                    cell += 1
    summary = {}
    for calibration in CALIBRATIONS:
        subset = [row for row in rows if row["calibration"] == calibration]
        summary[calibration] = {
            "cells": len(subset),
            "mean_active_minus_uniform": sum(row["active_minus_uniform"] for row in subset) / len(subset),
            "mean_active_minus_best_non_active": sum(row["active_minus_best_non_active"] for row in subset) / len(subset),
            "active_better_uniform_cells": sum(row["active_minus_uniform"] < 0 for row in subset),
            "active_better_best_non_active_cells": sum(row["active_minus_best_non_active"] < 0 for row in subset),
        }
    artifact = {
        "schema": "disastertrace.v21.synthetic_budgeted_miscalibration_surface.v1",
        "synthetic": True,
        "empirical": False,
        "methods": list(METHODS),
        "calibration_contract": "q_est=0.5+scale*(q_true-0.5), rho_est=clip(rho_true+bias); all methods use the same estimates",
        "config": {"n_per_cell": n, "seed": seed, "device_requested": device_name, "cell_count": cell},
        "runtime": {"device": str(device), "torch": torch.__version__, "cuda_available": bool(torch.cuda.is_available()), "cuda_device": torch.cuda.get_device_name(device) if device.type == "cuda" else None, "python": platform.python_version(), "elapsed_seconds": time.time() - started},
        "summary": summary,
        "rows": rows,
        "protected_boundary": {"holdout_read": False, "quarantine_read": False, "provider_calls": 0, "outcome_accessed": False},
        "interpretation": "Synthetic calibration diagnostic only; it does not establish weather value or novelty.",
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    return artifact


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--n", type=int, default=200_000)
    parser.add_argument("--seed", type=int, default=290925)
    parser.add_argument("--device", default="auto")
    args = parser.parse_args()
    artifact = run(out=args.out, n=args.n, seed=args.seed, device_name=args.device)
    print(json.dumps({"status": "PASS", "rows": len(artifact["rows"]), "device": artifact["runtime"]["device"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
