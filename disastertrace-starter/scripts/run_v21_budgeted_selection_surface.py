"""Synthetic finite-budget target-selection diagnostic for v21.

Targets have heterogeneous prior probabilities.  A noisy binary evidence query
has a fixed per-target reliability and a finite budget.  ``active_query`` uses
the prior uncertainty to choose which targets to query; uniform and hash
baselines spend the same number of queries without using uncertainty.  Every
method is scored on the same targets and denominator.
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
METHODS = ("fixed", "uniform_query", "hash_query", "active_query")


def _posterior(q: torch.Tensor, signal: torch.Tensor, rho: float) -> torch.Tensor:
    signal_one = signal > 0.5
    numerator = torch.where(signal_one, q * rho, q * (1.0 - rho))
    denominator = torch.where(
        signal_one,
        q * rho + (1.0 - q) * (1.0 - rho),
        q * (1.0 - rho) + (1.0 - q) * rho,
    )
    return numerator / denominator


def _loss(prediction: torch.Tensor, y: torch.Tensor) -> float:
    return float((prediction - y).square().mean().item())


def _one(*, rho: float, heterogeneity: float, budget: float, n: int, seed: int, device: torch.device) -> dict:
    if rho <= 0.5 or not 0.0 < heterogeneity < 0.5 or not 0.0 < budget <= 1.0:
        raise ValueError("invalid finite-budget surface cell")
    generator = torch.Generator(device=device)
    generator.manual_seed(seed)
    q = (0.5 + heterogeneity * (2.0 * torch.rand(n, generator=generator, device=device) - 1.0)).clamp(0.01, 0.99)
    y = (torch.rand(n, generator=generator, device=device) < q).to(torch.float32)
    correct = torch.rand(n, generator=generator, device=device) < rho
    signal = torch.where(correct, y, 1.0 - y)
    posterior = _posterior(q, signal, rho)
    query_count = max(1, int(round(budget * n)))
    query_count = min(query_count, n)
    uniform_order = torch.rand(n, generator=generator, device=device)
    uniform_mask = uniform_order.topk(query_count, sorted=False).indices
    hash_indices = torch.arange(n, device=device)
    hash_mask = hash_indices[:query_count]
    # Under this data-generating model, expected value is monotonic in q(1-q).
    active_mask = (q * (1.0 - q)).topk(query_count, sorted=False).indices
    fixed = q
    uniform = q.clone(); uniform[uniform_mask] = posterior[uniform_mask]
    hashed = q.clone(); hashed[hash_mask] = posterior[hash_mask]
    active = q.clone(); active[active_mask] = posterior[active_mask]
    predictions = {"fixed": fixed, "uniform_query": uniform, "hash_query": hashed, "active_query": active}
    losses = {method: _loss(prediction, y) for method, prediction in predictions.items()}
    return {
        "rho": rho,
        "heterogeneity": heterogeneity,
        "budget": budget,
        "n_targets": n,
        "query_count": query_count,
        "seed": seed,
        "method_losses": losses,
        "gain_fixed_minus_method": {m: losses["fixed"] - v for m, v in losses.items()},
        "query_counts": {"uniform_query": query_count, "hash_query": query_count, "active_query": query_count},
        "scored_cells": n,
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
    for heterogeneity in HETEROGENEITIES:
        for budget in BUDGETS:
            for rho in RHOS:
                rows.append(_one(rho=rho, heterogeneity=heterogeneity, budget=budget, n=n, seed=seed + 1009 * cell, device=device))
                cell += 1
    artifact = {
        "schema": "disastertrace.v21.synthetic_budgeted_selection_surface.v1",
        "evidence_role": "SYNTHETIC_FINITE_BUDGET_SELECTION_DIAGNOSTIC",
        "synthetic": True,
        "empirical": False,
        "hypothesis": "under a fixed evidence budget, uncertainty-aware active selection can beat uniform source retrieval when target priors are heterogeneous",
        "contract": {
            "methods": list(METHODS),
            "target_prior": "q uniform on [0.5-heterogeneity, 0.5+heterogeneity]",
            "query": "binary signal with correctness rho",
            "selection": "uniform/hash ignore q; active selects largest q(1-q)",
            "denominator": "n_targets per cell for every method",
            "query_budget": "identical query_count for all query methods in each cell",
        },
        "config": {"n_per_cell": n, "seed": seed, "device_requested": device_name, "cell_count": cell},
        "runtime": {
            "device": str(device),
            "torch": torch.__version__,
            "cuda_available": bool(torch.cuda.is_available()),
            "cuda_device": torch.cuda.get_device_name(device) if device.type == "cuda" else None,
            "python": platform.python_version(),
            "elapsed_seconds": time.time() - started,
        },
        "rows": rows,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    return artifact


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--n", type=int, default=1_000_000)
    parser.add_argument("--seed", type=int, default=270925)
    parser.add_argument("--device", default="auto")
    args = parser.parse_args()
    artifact = run(out=args.out, n=args.n, seed=args.seed, device_name=args.device)
    print(json.dumps({"status": "PASS", "out": str(args.out), "device": artifact["runtime"]["device"], "rows": len(artifact["rows"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
