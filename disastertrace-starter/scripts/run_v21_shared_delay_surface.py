"""Synthetic multi-target/shared-evidence policy surface for v21.

This is a diagnostic experiment, not a weather or provider evaluation.  Each
target has one binary outcome and a shared noisy source signal.  The same
target-level evidence is exposed to all checkpoints after a configurable
delay, with a target-level coverage mask.  The five policies use the same
targets, evidence contract, checkpoint count, and Brier denominator.
"""

from __future__ import annotations

import argparse
import json
import math
import platform
import time
from pathlib import Path

import torch


RHOS = (0.50, 0.60, 0.70, 0.80, 0.90, 1.00)
DELAYS = (0, 1, 2, 3)
COVERAGES = (0.50, 0.75, 1.00)
P_HIGHS = (0.65, 0.80)
CHECKPOINTS = 4
METHODS = ("fixed", "no_extra", "source_rr", "source_hash", "active")


def _signal_prediction(signal: torch.Tensor, p_high: float) -> torch.Tensor:
    p_low = 1.0 - p_high
    return torch.where(signal > 0.5, torch.tensor(p_high, device=signal.device), torch.tensor(p_low, device=signal.device))


def _mean_loss(prediction: torch.Tensor, y: torch.Tensor) -> float:
    return float((prediction - y.unsqueeze(1)).square().mean().item())


def _one(*, rho: float, delay: int, coverage: float, p_high: float, n: int, seed: int, device: torch.device) -> dict:
    if not 0.5 <= rho <= 1.0 or delay not in DELAYS or not 0.0 < coverage <= 1.0 or not 0.5 < p_high < 1.0:
        raise ValueError("invalid policy-surface cell")
    generator = torch.Generator(device=device)
    generator.manual_seed(seed)
    y = (torch.rand(n, generator=generator, device=device) >= 0.5).to(torch.float32)
    covered = torch.rand(n, generator=generator, device=device) < coverage
    shared_correct = torch.rand(n, generator=generator, device=device) < rho
    shared_signal = torch.where(shared_correct, y, 1.0 - y)
    available = covered.unsqueeze(1) & (torch.arange(CHECKPOINTS, device=device).unsqueeze(0) >= delay)
    fixed = torch.full((n, CHECKPOINTS), 0.5, device=device)

    # One retrieval at checkpoint zero, carried forward only if immediately available.
    no_extra_signal = _signal_prediction(shared_signal, p_high).unsqueeze(1).expand(n, CHECKPOINTS)
    no_extra = torch.where(available & (delay == 0), no_extra_signal, fixed)

    # Repeated source retrieval gets an independent noisy signal at each available checkpoint.
    rr_correct = torch.rand((n, CHECKPOINTS), generator=generator, device=device) < rho
    rr_signal = torch.where(rr_correct, y.unsqueeze(1), 1.0 - y.unsqueeze(1))
    source_rr = torch.where(available, _signal_prediction(rr_signal, p_high), fixed)

    # Hash/reuse is shared evidence with a conservative confidence update.
    source_hash = torch.where(available, _signal_prediction(shared_signal, 0.65).unsqueeze(1), fixed)
    active = torch.where(available, _signal_prediction(shared_signal, p_high).unsqueeze(1), fixed)

    predictions = {"fixed": fixed, "no_extra": no_extra, "source_rr": source_rr, "source_hash": source_hash, "active": active}
    losses = {method: _mean_loss(prediction, y) for method, prediction in predictions.items()}
    fixed_loss = losses["fixed"]
    return {
        "rho": rho,
        "delay_checkpoints": delay,
        "coverage": coverage,
        "p_high": p_high,
        "n_targets": n,
        "checkpoints": CHECKPOINTS,
        "seed": seed,
        "method_losses": losses,
        "gain_fixed_minus_method": {method: fixed_loss - loss for method, loss in losses.items()},
        "shared_evidence": True,
        "available_cells": int(available.sum().item()),
        "scored_cells": n * CHECKPOINTS,
    }


def run(*, out: Path, n: int, seed: int, shard: int, shards: int, device_name: str) -> dict:
    if n <= 1 or shards <= 0 or shard < 0 or shard >= shards:
        raise ValueError("invalid n/shard configuration")
    if device_name == "auto":
        device_name = "cuda" if torch.cuda.is_available() else "cpu"
    if device_name.startswith("cuda") and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable")
    device = torch.device(device_name)
    started = time.time()
    rows = []
    cell_index = 0
    for p_high in P_HIGHS:
        for coverage in COVERAGES:
            for delay in DELAYS:
                for rho in RHOS:
                    if cell_index % shards == shard:
                        rows.append(_one(rho=rho, delay=delay, coverage=coverage, p_high=p_high, n=n, seed=seed + 1009 * cell_index, device=device))
                    cell_index += 1
    artifact = {
        "schema": "disastertrace.v21.synthetic_shared_delay_surface.v1",
        "evidence_role": "SYNTHETIC_MULTI_TARGET_SHARED_EVIDENCE_DIAGNOSTIC",
        "synthetic": True,
        "empirical": False,
        "hypothesis": "active value depends jointly on evidence reliability, availability delay, coverage, and confidence; all methods share target/checkpoint denominator",
        "contract": {
            "target_outcome": "binary y sampled per target",
            "shared_evidence": "one noisy source signal per target reused after availability",
            "delay": "number of initial checkpoints without evidence",
            "coverage": "target-level probability that evidence ever becomes available",
            "methods": list(METHODS),
            "checkpoints": CHECKPOINTS,
            "brier_denominator": "n_targets * checkpoints for every method",
            "no_extra_definition": "single retrieval only when delay is zero, then carry-forward",
            "source_rr_definition": "independent noisy retrieval at every available checkpoint",
            "source_hash_definition": "shared signal with p=.65/.35 confidence",
            "active_definition": "shared signal with configured p_high/(1-p_high) confidence",
        },
        "config": {"n_per_cell": n, "seed": seed, "shard": shard, "shards": shards, "device_requested": device_name, "cell_count_total": cell_index, "cell_count_this_shard": len(rows)},
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
    parser.add_argument("--n", type=int, default=200_000)
    parser.add_argument("--seed", type=int, default=250925)
    parser.add_argument("--shard", type=int, default=0)
    parser.add_argument("--shards", type=int, default=1)
    parser.add_argument("--device", default="auto")
    args = parser.parse_args()
    artifact = run(out=args.out, n=args.n, seed=args.seed, shard=args.shard, shards=args.shards, device_name=args.device)
    print(json.dumps({"status": "PASS", "out": str(args.out), "device": artifact["runtime"]["device"], "rows": len(artifact["rows"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
