"""Synthetic reliability sweep for the v21 active-evidence hypothesis.

This experiment is deliberately independent of weather data and language
models.  A binary target is observed through a noisy signal.  The active
policy turns the signal into p=.8/.2, while the fixed baseline reports .5.
The sweep estimates when content-dependent selection has positive Brier value
and retains an adversarial low-reliability regime where it is harmful.
"""

from __future__ import annotations

import argparse
import json
import math
import platform
import time
from pathlib import Path

import torch


RELIABILITIES = (0.50, 0.55, 0.60, 0.65, 0.70, 0.80, 0.90, 1.00)


def _one(rho: float, n: int, seed: int, device: torch.device) -> dict[str, float | int | str]:
    gen = torch.Generator(device=device)
    gen.manual_seed(seed)
    y = (torch.rand(n, generator=gen, device=device) >= 0.5).to(torch.float32)
    correct = torch.rand(n, generator=gen, device=device) < rho
    signal = torch.where(correct, y, 1.0 - y)
    p_active = torch.where(signal > 0.5, torch.tensor(0.8, device=device), torch.tensor(0.2, device=device))
    p_fixed = torch.full((n,), 0.5, device=device)
    active_loss = (p_active - y).square()
    fixed_loss = (p_fixed - y).square()
    gain = fixed_loss - active_loss
    # Keep only scalar summaries on the host; this also avoids making the
    # evaluator-visible outcome part of any actor trace.
    mean_gain = float(gain.mean().item())
    std_gain = float(gain.std(unbiased=True).item())
    return {
        "rho": rho,
        "n": n,
        "seed": seed,
        "device": str(device),
        "active_mean_brier": float(active_loss.mean().item()),
        "fixed_mean_brier": float(fixed_loss.mean().item()),
        "mean_gain_fixed_minus_active": mean_gain,
        "gain_standard_error": std_gain / math.sqrt(n),
        "analytic_active_brier": 0.64 - 0.60 * rho,
        "analytic_gain": 0.60 * rho - 0.39,
    }


def run(*, out: Path, n: int, seed: int, shard: int, shards: int, device_name: str) -> dict:
    if n <= 1 or shard < 0 or shard >= shards or shards <= 0:
        raise ValueError("invalid n/shard configuration")
    if device_name == "auto":
        device_name = "cuda" if torch.cuda.is_available() else "cpu"
    if device_name.startswith("cuda") and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable")
    device = torch.device(device_name)
    started = time.time()
    rows = [_one(rho, n, seed + 1009 * shard + i, device) for i, rho in enumerate(RELIABILITIES)]
    artifact = {
        "schema": "disastertrace.v21.synthetic_signal_reliability_mc.v1",
        "evidence_role": "SYNTHETIC_METHOD_DIAGNOSTIC",
        "synthetic": True,
        "empirical": False,
        "hypothesis": "active content selection is useful only when signal reliability exceeds 0.65 for this p=.8/.2 policy",
        "config": {"n_per_rho": n, "seed": seed, "shard": shard, "shards": shards, "device_requested": device_name},
        "runtime": {
            "device": str(device),
            "torch": torch.__version__,
            "cuda_available": bool(torch.cuda.is_available()),
            "cuda_device": torch.cuda.get_device_name(device) if device.type == "cuda" else None,
            "python": platform.python_version(),
            "elapsed_seconds": time.time() - started,
        },
        "rows": rows,
        "decision_boundary": {"reliability_threshold": 0.65, "positive_gain_means_active_better": True},
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    return artifact


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--n", type=int, default=500_000)
    parser.add_argument("--seed", type=int, default=210925)
    parser.add_argument("--shard", type=int, default=0)
    parser.add_argument("--shards", type=int, default=1)
    parser.add_argument("--device", default="auto")
    args = parser.parse_args()
    artifact = run(out=args.out, n=args.n, seed=args.seed, shard=args.shard, shards=args.shards, device_name=args.device)
    print(json.dumps({"status": "PASS", "out": str(args.out), "device": artifact["runtime"]["device"], "rows": len(artifact["rows"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
