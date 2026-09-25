"""Cost-matched synthetic adaptive-source surface for v21.

Every method sees the same target outcomes, availability mask, checkpoints,
and forecast map.  ``source_rr`` and ``source_hash`` each use two retrievals
with a predeclared follow-up; ``active`` also uses two retrievals but chooses
between the two follow-ups from the first retrieved signal.  The experiment is
synthetic and cannot establish weather value or novelty.
"""

from __future__ import annotations

import argparse
import json
import math
import platform
import time
from pathlib import Path

import torch


RELIABILITIES = (0.60, 0.70, 0.80, 0.90)
FOLLOWUP_HIGH = (0.70, 0.85, 0.95)
FOLLOWUP_LOW = (0.50, 0.60)
DELAYS = (0, 1, 2, 3)
COVERAGES = (0.50, 1.00)
P_HIGH = (0.65, 0.80)
CHECKPOINTS = 4
METHODS = ("fixed", "no_extra", "source_rr", "source_hash", "active")


def _predict(signal: torch.Tensor, p_high: float) -> torch.Tensor:
    return torch.where(signal > 0.5, torch.tensor(p_high, device=signal.device), torch.tensor(1.0 - p_high, device=signal.device))


def _loss(prediction: torch.Tensor, y: torch.Tensor) -> float:
    return float((prediction - y.unsqueeze(1)).square().mean().item())


def _one(*, rho: float, followup_high: float, followup_low: float, delay: int, coverage: float, p_high: float, n: int, seed: int, device: torch.device) -> dict:
    if rho not in RELIABILITIES or followup_high not in FOLLOWUP_HIGH or followup_low not in FOLLOWUP_LOW or delay not in DELAYS or coverage not in COVERAGES or p_high not in P_HIGH:
        raise ValueError("invalid cost-matched surface cell")
    generator = torch.Generator(device=device)
    generator.manual_seed(seed)
    y = (torch.rand(n, generator=generator, device=device) >= 0.5).to(torch.float32)
    covered = torch.rand(n, generator=generator, device=device) < coverage
    available = covered.unsqueeze(1) & (torch.arange(CHECKPOINTS, device=device).unsqueeze(0) >= delay)
    initial_correct = torch.rand(n, generator=generator, device=device) < rho
    initial = torch.where(initial_correct, y, 1.0 - y)
    q1_probability = torch.where(initial > 0.5, torch.tensor(followup_high, device=device), torch.tensor(followup_low, device=device))
    q2_probability = torch.where(initial > 0.5, torch.tensor(followup_low, device=device), torch.tensor(followup_high, device=device))
    q1_correct = torch.rand(n, generator=generator, device=device) < q1_probability
    q2_correct = torch.rand(n, generator=generator, device=device) < q2_probability
    q1 = torch.where(q1_correct, y, 1.0 - y)
    q2 = torch.where(q2_correct, y, 1.0 - y)
    fixed = torch.full((n, CHECKPOINTS), 0.5, device=device)
    initial_prediction = _predict(initial, p_high).unsqueeze(1).expand(n, CHECKPOINTS)
    rr_prediction = _predict(q1, p_high).unsqueeze(1).expand(n, CHECKPOINTS)
    hash_prediction = _predict(q2, p_high).unsqueeze(1).expand(n, CHECKPOINTS)
    active_signal = torch.where(initial > 0.5, q1, q2)
    active_prediction = _predict(active_signal, p_high).unsqueeze(1).expand(n, CHECKPOINTS)
    predictions = {
        "fixed": fixed,
        "no_extra": torch.where(available, initial_prediction, fixed),
        "source_rr": torch.where(available, rr_prediction, fixed),
        "source_hash": torch.where(available, hash_prediction, fixed),
        "active": torch.where(available, active_prediction, fixed),
    }
    losses = {method: _loss(prediction, y) for method, prediction in predictions.items()}
    return {
        "rho_initial": rho,
        "followup_high": followup_high,
        "followup_low": followup_low,
        "delay_checkpoints": delay,
        "coverage": coverage,
        "p_high": p_high,
        "n_targets": n,
        "checkpoints": CHECKPOINTS,
        "method_losses": losses,
        "gain_fixed_minus_method": {method: losses["fixed"] - loss for method, loss in losses.items()},
        "query_counts": {"fixed": 0, "no_extra": 1, "source_rr": 2, "source_hash": 2, "active": 2},
        "scored_cells": n * CHECKPOINTS,
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
    for rho in RELIABILITIES:
        for high in FOLLOWUP_HIGH:
            for low in FOLLOWUP_LOW:
                for delay in DELAYS:
                    for coverage in COVERAGES:
                        for p_high in P_HIGH:
                            rows.append(_one(rho=rho, followup_high=high, followup_low=low, delay=delay, coverage=coverage, p_high=p_high, n=n, seed=seed + 1009 * cell, device=device))
                            cell += 1
    artifact = {
        "schema": "disastertrace.v21.synthetic_cost_matched_adaptive_surface.v1",
        "evidence_role": "SYNTHETIC_COST_MATCHED_ADAPTIVE_SELECTION_DIAGNOSTIC",
        "synthetic": True,
        "empirical": False,
        "hypothesis": "content-dependent follow-up selection can outperform fixed follow-up schedules when query count and F are held constant",
        "contract": {
            "methods": list(METHODS),
            "query_budget": "fixed=0, no_extra=1, source_rr/source_hash/active=2 per target; active and both controls are cost matched",
            "followup_rule": "q1 is high reliability when initial signal is 1; q2 is high reliability when initial signal is 0",
            "denominator": "n_targets * checkpoints for every method",
            "shared_f": "p_high/(1-p_high) from the final delivered signal, fixed across methods",
            "outcome": "one synthetic binary y per target, never exposed to actor",
        },
        "config": {"n_per_cell": n, "seed": seed, "device_requested": device_name, "cell_count": cell},
        "runtime": {"device": str(device), "torch": torch.__version__, "cuda_available": bool(torch.cuda.is_available()), "cuda_device": torch.cuda.get_device_name(device) if device.type == "cuda" else None, "python": platform.python_version(), "elapsed_seconds": time.time() - started},
        "rows": rows,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    return artifact


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--n", type=int, default=500_000)
    parser.add_argument("--seed", type=int, default=350925)
    parser.add_argument("--device", default="auto")
    args = parser.parse_args()
    artifact = run(out=args.out, n=args.n, seed=args.seed, device_name=args.device)
    print(json.dumps({"status": "PASS", "out": str(args.out), "device": artifact["runtime"]["device"], "rows": len(artifact["rows"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
