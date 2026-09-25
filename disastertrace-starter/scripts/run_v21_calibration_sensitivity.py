"""Synthetic sensitivity of active-policy confidence to signal reliability."""

from __future__ import annotations

import argparse
import json
import math
import platform
from pathlib import Path

import torch


RHOS = (0.50, 0.55, 0.60, 0.65, 0.70, 0.80, 0.90, 1.00)
P_HIGHS = (0.55, 0.65, 0.80, 0.95)


def run(out: Path, *, n: int, seed: int, device_name: str) -> dict:
    if n <= 1:
        raise ValueError("n must exceed one")
    if device_name == "auto":
        device_name = "cuda" if torch.cuda.is_available() else "cpu"
    if device_name.startswith("cuda") and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable")
    device = torch.device(device_name)
    rows = []
    for p_high in P_HIGHS:
        if not 0.5 < p_high < 1:
            raise ValueError("p_high must be in (0.5, 1)")
        p_low = 1.0 - p_high
        threshold = (p_high + 0.5) / 2.0
        for offset, rho in enumerate(RHOS):
            generator = torch.Generator(device=device)
            generator.manual_seed(seed + offset + int(1000 * p_high))
            y = (torch.rand(n, generator=generator, device=device) >= 0.5).float()
            correct = torch.rand(n, generator=generator, device=device) < rho
            signal = torch.where(correct, y, 1.0 - y)
            prediction = torch.where(signal > 0.5, torch.tensor(p_high, device=device), torch.tensor(p_low, device=device))
            gain = (torch.full_like(y, 0.5) - y).square() - (prediction - y).square()
            rows.append({
                "p_high": p_high,
                "p_low": p_low,
                "rho": rho,
                "n": n,
                "mean_gain_fixed_minus_active": float(gain.mean().item()),
                "gain_standard_error": float(gain.std(unbiased=True).item()) / math.sqrt(n),
                "analytic_reliability_threshold": threshold,
                "analytic_gain": 0.25 - p_high * p_high + rho * (2 * p_high - 1),
            })
    artifact = {
        "schema": "disastertrace.v21.synthetic_calibration_sensitivity.v1",
        "evidence_role": "SYNTHETIC_METHOD_DIAGNOSTIC",
        "synthetic": True,
        "empirical": False,
        "hypothesis": "more confident active updates require more reliable evidence",
        "config": {"n_per_cell": n, "seed": seed, "device_requested": device_name},
        "runtime": {"device": str(device), "torch": torch.__version__, "cuda_available": bool(torch.cuda.is_available()), "cuda_device": torch.cuda.get_device_name(device) if device.type == "cuda" else None, "python": platform.python_version()},
        "rows": rows,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    return artifact


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--n", type=int, default=500_000)
    parser.add_argument("--seed", type=int, default=410925)
    parser.add_argument("--device", default="auto")
    args = parser.parse_args()
    artifact = run(args.out, n=args.n, seed=args.seed, device_name=args.device)
    print(json.dumps({"status": "PASS", "out": str(args.out), "rows": len(artifact["rows"]), "device": artifact["runtime"]["device"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
