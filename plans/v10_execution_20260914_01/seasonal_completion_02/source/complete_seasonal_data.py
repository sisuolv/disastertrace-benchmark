"""Continue failed seasonal captures once originals drain; reuse verified successes."""

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def publish(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, sort_keys=True, allow_nan=False)
        stream.write("\n")


def prepare(args):
    args.out.mkdir(exist_ok=False)
    shutil.copytree(args.original / "source", args.out / "source")
    shutil.copyfile(__file__, args.out / "source/complete_seasonal_data.py")
    publish(args.out / "PLAN.json", {
        "schema": "disastertrace.seasonal_continuation.v1", "original": str(args.original),
        "original_plan_sha256": digest(args.original / "PLAN.json"), "repo": str(args.repo),
        "deadline": "2026-09-14T23:45:00+00:00", "concurrent_fetchers": 1,
        "pause_seconds": 3, "additional_attempts_per_missing_url": 2,
        "native_request_ceiling_per_unit": 500, "units": read(args.original / "PLAN.json")["units"],
        "reuse": "Successful native captures and complete datasets remain original; only missing URLs are fetched.",
        "confirmation_opened": False, "model_calls": 0,
        "source": {str(p.relative_to(args.out)): digest(p) for p in (args.out / "source").rglob("*") if p.is_file()}})


def run_command(folder, name, command, plan, out):
    remaining = (dt.datetime.fromisoformat(plan["deadline"]) - dt.datetime.now(dt.timezone.utc)).total_seconds()
    if remaining <= 0:
        raise TimeoutError("Registered continuation deadline reached")
    publish(folder / (name + ".command.json"), {"command": command})
    env = dict(os.environ, PYTHONPATH=str(out / "source"), PYTHONDONTWRITEBYTECODE="1")
    for key in ("http_proxy", "https_proxy", "all_proxy", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
        env.pop(key, None)
    with (folder / (name + ".log")).open("x") as stream:
        result = subprocess.run(command, cwd=plan["repo"], env=env, stdout=stream,
                                stderr=subprocess.STDOUT, timeout=remaining, check=False)
    publish(folder / (name + ".exit.json"), {"exit_code": result.returncode})
    if result.returncode:
        raise RuntimeError("Recorded continuation stage failed: " + name)


def eligible(directory, expected):
    selected = {}
    if not directory.exists():
        return selected
    for ident, spec in expected.items():
        path = directory / (ident + ".json")
        if not path.exists():
            continue
        row = read(path)
        body = directory / row.get("body_file", "MISSING")
        if (row.get("url") == spec["url"] and row.get("complete")
                and row.get("http_status") == 200 and row.get("curl_exit", 0) == 0
                and body.is_file() and digest(body) == row.get("sha256")
                and body.stat().st_size == row.get("bytes")):
            selected[ident] = path
    return selected


def complete_captures(folder, original, spec_path, name, plan, out):
    specification = read(spec_path)
    expected = {r["id"]: r for r in specification["requests"]}
    if len(expected) != len(specification["requests"]):
        raise ValueError("Duplicate source IDs")
    chosen = {}
    for prior in (name, name + "_retry_01", name + "_complete_02"):
        for ident, path in eligible(original / prior, expected).items():
            chosen.setdefault(ident, path)
    python = str(Path(plan["repo"]) / "disastertrace-starter/.venv/bin/python")
    fresh_attempts = 0
    for attempt in range(1, plan["additional_attempts_per_missing_url"] + 1):
        missing = [row for ident, row in expected.items() if ident not in chosen]
        if not missing:
            break
        suffix = name + "_missing_" + str(attempt)
        retry_plan = folder / (suffix + "_PLAN.json")
        publish(retry_plan, {**specification, "requests": missing, "pause_seconds": plan["pause_seconds"],
            "limits": {"requests": len(missing), "bytes": sum(r["max_bytes"] + 1 for r in missing)},
            "continuation_parent_sha256": digest(spec_path), "originals_preserved": True})
        run_command(folder, suffix, [python, str(out / "source/fetch_public.py"),
                                    str(retry_plan), str(folder / suffix)], plan, out)
        manifest = read(folder / suffix / "MANIFEST.json")
        if manifest["attempted"] != len(missing):
            raise ValueError("Incomplete registered retrieval denominator")
        fresh_attempts += manifest["attempted"]
        chosen.update(eligible(folder / suffix, expected))
    if set(chosen) != set(expected):
        raise ValueError("Still unavailable source IDs: " + ",".join(sorted(set(expected) - set(chosen))))
    merged = folder / (name + "_verified")
    merged.mkdir(exist_ok=False)
    rows, provenance = [], []
    for ident, path in sorted(chosen.items()):
        row = read(path)
        shutil.copyfile(path, merged / path.name)
        shutil.copyfile(path.parent / row["body_file"], merged / row["body_file"])
        rows.append(row)
        provenance.append({"id": ident, "chosen_receipt": str(path), "receipt_sha256": digest(path),
                           "body_sha256": row["sha256"], "reused_original": original in path.parents})
    publish(merged / "MANIFEST.json", {"planned": len(expected), "attempted": len(expected), "rows": rows,
        "merged_verified_sources": True, "new_physical_attempts": fresh_attempts,
        "attempted_semantics": "merged coverage; physical attempts remain in original and continuation receipts"})
    publish(merged / "PROVENANCE.json", provenance)
    return merged


def execute(args):
    out = args.out
    plan = read(out / "PLAN.json")
    publish(out / "LAUNCH_CLAIM.json", {"pid": os.getpid(), "at": dt.datetime.now(dt.timezone.utc).isoformat()})
    for name, sha in plan["source"].items():
        if digest(out / name) != sha:
            raise ValueError("Frozen continuation source changed")
    original = Path(plan["original"])
    if digest(original / "PLAN.json") != plan["original_plan_sha256"]:
        raise ValueError("Original seasonal plan changed")
    while not (original / "COMPLETE.json").exists():
        if dt.datetime.now(dt.timezone.utc) >= dt.datetime.fromisoformat(plan["deadline"]):
            raise TimeoutError("Original source batch did not drain before continuation deadline")
        time.sleep(20)
    original_result = read(original / "COMPLETE.json")
    if {r["unit"] for r in original_result["units"]} != set(plan["units"]):
        raise ValueError("Original unit denominator mismatch")
    publish(out / "ORIGINAL_DRAINED.json", {"complete_sha256": digest(original / "COMPLETE.json"),
        "at": dt.datetime.now(dt.timezone.utc).isoformat(), "original_results": original_result["units"]})
    python = str(Path(plan["repo"]) / "disastertrace-starter/.venv/bin/python")
    results = []
    for unit in plan["units"]:
        old = original / unit
        folder = out / unit
        folder.mkdir(exist_ok=False)
        old_result = read(old / "RESULT.json")
        try:
            if old_result["complete"]:
                dataset = old / "dataset_v2"
                status = "reused_verified_original_dataset"
            else:
                for name in ("CALENDAR.json", "SOURCE_CATALOG_PLAN.json"):
                    shutil.copyfile(old / name, folder / name)
                catalogs = complete_captures(folder, old, folder / "SOURCE_CATALOG_PLAN.json", "catalogs", plan, out)
                native_plan = folder / "SOURCE_NATIVE_PLAN.json"
                run_command(folder, "prepare_native", [python, str(out / "source/prepare_native_fetch.py"),
                    "--catalogs", str(catalogs), "--output", str(native_plan)], plan, out)
                if len(read(native_plan)["requests"]) > plan["native_request_ceiling_per_unit"]:
                    raise ValueError("Native source ceiling exceeded")
                native = complete_captures(folder, old, native_plan, "native", plan, out)
                stage, dataset = folder / "dataset_stage_v1", folder / "dataset_v2"
                run_command(folder, "decode", [python, str(out / "source/build_regional_stage_v1.py"),
                    "--contract", str(folder / "CALENDAR.json"), "--metar", str(catalogs), "--taf", str(native),
                    "--source-root", str(folder), "--output", str(stage)], plan, out)
                run_command(folder, "native_contract", [python, str(out / "source/build_native_v2.py"),
                    "--dataset", str(stage), "--source-root", str(folder), "--output", str(dataset)], plan, out)
                status = "completed_in_new_continuation"
            result = {"unit": unit, "complete": True, "status": status, "dataset": str(dataset),
                "dataset_files": {str(p.relative_to(dataset)): digest(p) for p in dataset.rglob("*") if p.is_file()},
                "source_root": str(dataset.parent), "original_result_sha256": digest(old / "RESULT.json")}
        except Exception as exc:  # Each predeclared unit remains in the final denominator.
            result = {"unit": unit, "complete": False, "error_type": type(exc).__name__, "error": str(exc)}
        publish(folder / "RESULT.json", result)
        results.append(result)
        print(json.dumps({k: v for k, v in result.items() if k != "dataset_files"}), flush=True)
    publish(out / "COMPLETE.json", {"units": results, "all_complete": all(r["complete"] for r in results),
        "confirmation_opened": False, "model_calls": 0, "at": dt.datetime.now(dt.timezone.utc).isoformat()})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--original", type=Path)
    parser.add_argument("--repo", type=Path)
    parser.add_argument("--execute", action="store_true")
    arguments = parser.parse_args()
    if arguments.execute:
        execute(arguments)
    else:
        prepare(arguments)
