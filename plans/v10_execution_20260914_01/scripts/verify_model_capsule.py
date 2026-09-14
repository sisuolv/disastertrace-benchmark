"""Rebuild all scores from frozen inputs and replies without model or network access."""

import argparse
import datetime as dt
import hashlib
import json
import math
import runpy
import socket
import sys
from collections import Counter, defaultdict
from pathlib import Path


def read(path):
    return json.loads(path.read_text())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--capsule", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()
    capsule, result_path = args.capsule.resolve(), args.result.absolute()
    if result_path.exists():
        raise FileExistsError("Use a fresh result path")
    manifest = read(capsule / "MANIFEST.json")
    forbidden = Path(manifest["original_root_blocked"])
    deny_counts = Counter()

    def audit(event, values):
        if event in {
            "socket.connect",
            "socket.getaddrinfo",
            "subprocess.Popen",
            "os.system",
        }:
            deny_counts["network_or_process"] += 1
            raise RuntimeError("Network and subprocess execution disabled")
        if event != "open" or not isinstance(values[0], (str, bytes)):
            return
        path = Path(
            values[0].decode() if isinstance(values[0], bytes) else values[0]
        ).resolve()
        if path.is_relative_to(forbidden) and not path.is_relative_to(capsule):
            deny_counts["original_workspace"] += 1
            raise RuntimeError("Original workspace access disabled")

    sys.addaudithook(audit)
    try:
        (forbidden / "__capsule_original_access_probe__").read_bytes()
    except RuntimeError:
        pass
    else:
        raise AssertionError("Original workspace read was not blocked")
    try:
        with socket.socket() as probe:
            probe.connect(("127.0.0.1", 9))
    except RuntimeError:
        pass
    else:
        raise AssertionError("Network was not blocked")
    expected_denials = dict(deny_counts)
    for name, item in manifest["files"].items():
        path = capsule / name
        if (
            path.is_symlink()
            or not path.resolve().is_relative_to(capsule)
            or path.stat().st_size != item["bytes"]
            or hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]
        ):
            raise ValueError("Capsule byte binding mismatch: " + name)
    batch = capsule / "study"
    rebuilt = result_path.with_name(result_path.stem + "_rescored")
    sys.path.insert(0, str(batch / "source"))
    old_argv = sys.argv
    sys.argv = [
        "score_feature_temperature.py",
        "--batch",
        str(batch),
        "--out",
        str(rebuilt),
    ]
    try:
        runpy.run_path(
            str(batch / "source/score_feature_temperature.py"), run_name="__main__"
        )
    finally:
        sys.argv = old_argv
    expected = batch / "final_audit_01/scores"
    comparisons = []
    for path in sorted(expected.iterdir()):
        actual = rebuilt / path.name
        if actual.read_bytes() != path.read_bytes():
            raise ValueError("Rescored file differs: " + path.name)
        comparisons.append(path.name)
    rows = [
        json.loads(line) for line in (rebuilt / "ROWS.jsonl").read_text().splitlines()
    ]
    answers = [
        json.loads(line)
        for line in (rebuilt / "ANSWERS.jsonl").read_text().splitlines()
    ]
    scores, grouped = read(rebuilt / "RESULT.json"), defaultdict(list)
    for row in rows:
        prefix = [
            row["model"],
            row["kind"],
            row["cohort"],
            str(row.get("threshold", row.get("event"))),
        ]
        for method, probability in row["probabilities"].items():
            grouped["__".join(prefix + [method])].append((row, probability))
    for key, values in grouped.items():
        mature = [
            (r, p)
            for r, p in values
            if r["future_status"] == "mature" and r["outcome"] is not None
        ]
        metric = scores["metrics"][key]
        if (
            metric["registered"] != len(values)
            or metric["scored"] != len(mature)
            or metric["positive"] != sum(r["outcome"] for r, _ in mature)
            or metric["valid"] != sum(r["valid"] for r, _ in values)
        ):
            raise ValueError("Independent score denominator mismatch")
        loss = math.fsum((p - r["outcome"]) ** 2 for r, p in mature)
        if not math.isclose(loss, metric["loss_sum"], abs_tol=1e-12, rel_tol=1e-12):
            raise ValueError("Independent Brier arithmetic mismatch")
        if mature and not math.isclose(
            loss / len(mature), metric["brier"], abs_tol=1e-12, rel_tol=1e-12
        ):
            raise ValueError("Independent mean Brier mismatch")
    references, count = read(batch / "evaluator/REFERENCES.json"), 0
    for task in read(batch / "PLAN.json")["tasks"]:
        if task["kind"] != "temperature_F":
            continue
        bundle = read(batch / "bundles" / (task["call_id"] + ".json"))
        target = bundle["target"]
        start = dt.datetime.fromtimestamp(
            target["physical_start"] / 1e6, dt.timezone.utc
        )
        end = dt.datetime.fromtimestamp(target["physical_end"] / 1e6, dt.timezone.utc)
        length = (end - start).days
        dates = {
            (start + dt.timedelta(days=i)).date().isoformat() for i in range(length)
        }
        products = [
            v for v in bundle["common"]["daily_products"] if v["target_date"] in dates
        ]
        if length not in {1, 3} or len(products) != length:
            raise ValueError("Incomplete independent future-day support")
        field = (
            "forecast_min_members_C"
            if target["variable"] == "daily_min_2m_temperature"
            else "forecast_max_members_C"
        )
        members = len(products[0][field])
        if members != 51 or any(len(p[field]) != members for p in products):
            raise ValueError("Independent member alignment mismatch")
        successes = 0
        for member in range(members):
            values = [p[field][member] for p in products]
            exceed = [
                v >= target["threshold"]
                if target["event_operator"] == "ge"
                else v < target["threshold"]
                for v in values
            ]
            # A three-day spell is a joint event of the same member on all days.
            successes += all(exceed)
        if successes / members != references[task["call_id"]]["FOLLOW"]:
            raise ValueError("Independent same-member event fraction mismatch")
        count += 1
    if dict(deny_counts) != expected_denials:
        raise ValueError("Scorer attempted forbidden access")
    result = {
        "passed": True,
        "manifest_files_verified": len(manifest["files"]),
        "registered_answers": len(answers),
        "received_answers": sum(r["capture_state"] == "RECEIVED" for r in answers),
        "valid_answers": sum(r["valid"] for r in answers),
        "invalid_answers_retained": sum(not r["valid"] for r in answers),
        "all_original_score_files_identical": comparisons,
        "independent_metric_groups": len(grouped),
        "independent_temperature_fractions": count,
        "blocked_access_probes": expected_denials,
        "scorer_forbidden_access_attempts": 0,
        "network_disabled": True,
        "original_workspace_access_blocked": True,
        "original_token_audit_included_but_not_rerun": True,
        "model_calls": 0,
        "scope": "complete captured-model score reconstruction, not model-generation or full-training reconstruction",
    }
    with result_path.open("x") as handle:
        json.dump(result, handle, indent=2)
        handle.write("\n")
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
