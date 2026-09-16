"""Resolve verified cache roots and recover only the failed annual catalog slice."""
import csv
import datetime as dt
import importlib.util
import json
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

from disastertrace.monitoring_v1.spool_backend import digest, publish, read
from disastertrace.monitoring_v1.targets import canonical_hash

RUN = Path(__file__).resolve().parent
REPO = RUN.parents[1]
OLD = REPO / "plans/v11_execution_20260915_01"


def main():
    out = RUN / "annual_stage_B"
    out.mkdir(exist_ok=False)
    sources = out / "source"; sources.mkdir()
    for name in ("fetch_public.py", "prepare_native_fetch.py"):
        shutil.copy2(REPO / "plans/v7_review_execution_20260912" / name, sources / name)
    old = OLD / "annual_catalog_01/chicago__2023-01"
    plan = read(old / "SOURCE_CATALOG_PLAN.json")
    failed = [r for r in plan["requests"] if r["id"] == "metar-routine-KORD"]
    assert len(failed) == 1
    failed[0]["timeout"] = 240
    recovery = {**plan, "requests": failed, "limits": {"requests": 1, "bytes": failed[0]["max_bytes"] + 1},
        "pause_seconds": 0, "old_failure": str(old / "catalogs_retry_01/MANIFEST.json"),
        "change": "same exact URL; one fresh generation; timeout 240s; retain prior 429 and partial timeout"}
    publish(out / "CATALOG_RECOVERY_PLAN.json", recovery)
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        __import__("os").environ.pop(key, None)
    subprocess.run([sys.executable, str(sources / "fetch_public.py"), str(out / "CATALOG_RECOVERY_PLAN.json"), str(out / "catalog_recovery")], check=True, timeout=300)
    receipt = read(out / "catalog_recovery/metar-routine-KORD.json")
    recovered = receipt["complete"] and receipt["http_status"] == 200
    verified = out / "chicago__2023-01"; verified.mkdir()
    captures = verified / "catalogs_verified"; captures.mkdir()
    references, manifest = [], []
    for original in read(old / "catalogs/MANIFEST.json")["rows"]:
        base = out / "catalog_recovery" if original["id"] == "metar-routine-KORD" else old / "catalogs"
        row = read(base / (original["id"] + ".json"))
        if not row["complete"]:
            continue
        body = base / row["body_file"]
        if digest(body) != row["sha256"] or row["http_status"] != 200:
            raise ValueError("Annual companion identity changed")
        if not list(csv.DictReader(body.read_text().splitlines())):
            raise ValueError("Empty recovered annual source")
        for file in (body, base / (row["id"] + ".json")):
            shutil.copy2(file, captures / file.name)
            references.append({"original": str(file), "sha256": digest(file)})
        manifest.append(row)
    publish(captures / "MANIFEST.json", {"rows": manifest, "new_HTTP_requests": 1, "complete": recovered, "original_references": references})
    shutil.copy2(old / "CALENDAR.json", verified / "CALENDAR.json")
    # All three TAF catalogs were already complete even when the METAR slice failed.
    native = verified / "SOURCE_NATIVE_PLAN.json"
    subprocess.run([sys.executable, str(sources / "prepare_native_fetch.py"), "--catalogs", str(captures), "--output", str(native)], check=True)
    objects = {r["request_key"]: r for r in read(RUN / "ANNUAL_NATIVE_OBJECTS.json")}
    for request in read(native)["requests"]:
        key = canonical_hash({"id": request["id"], "url": request["url"]})
        entry = objects.setdefault(key, {"request_key": key, "id": request["id"], "url": request["url"], "request": request, "references": [], "verified_variants": [], "state": "missing_bytes"})
        entry["references"].append({"unit": "chicago__2023-01", "catalog_metadata": request["catalog_metadata"], "plan_sha256": digest(native)})
    inv = read(RUN / "ANNUAL_NATIVE_INVENTORY.json")
    spec = importlib.util.spec_from_file_location("inventory_helpers", RUN / "inventory_sources.py")
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    repaired, unresolved, cached_sources = [], [], {}
    for failure in inv["cache_binding_failures"]:
        manifest_path = REPO / failure["manifest"]
        source_map = cached_sources.setdefault(str(manifest_path), None)
        if source_map is None:
            source_map = read(manifest_path); cached_sources[str(manifest_path)] = source_map
        binding = source_map[failure["source_id"]]
        match = None
        for base in list(manifest_path.parents)[:3]:
            try:
                match = module.verify_source(binding, base); break
            except (OSError, ValueError, KeyError):
                pass
        if match is None:
            unresolved.append(failure); continue
        body, receipt_path, receipt = match
        key = canonical_hash({"id": failure["source_id"], "url": receipt["url"]})
        repaired.append({**failure, "resolved_base": str(base), "annual_request_key": key if key in objects else None})
        if key in objects:
            entry = objects[key]
            if not any(v["sha256"] == binding["sha256"] for v in entry["verified_variants"]):
                entry["verified_variants"].append({"body_path": str(body), "receipt_path": str(receipt_path),
                    "receipt_sha256": digest(receipt_path), "bytes": binding["bytes"], "sha256": binding["sha256"], "catalog_metadata": receipt.get("catalog_metadata")})
    for row in objects.values():
        n = len(row["verified_variants"])
        row["state"] = "missing_bytes" if n == 0 else "verified_cached" if n == 1 else "same_id_content_conflict"
    rows = sorted(objects.values(), key=lambda r: r["request_key"])
    publish(out / "OBJECTS.json", rows)
    publish(out / "CACHE_ROOT_RESOLUTION.json", {"repaired": repaired, "unresolved": unresolved,
        "reason": "Historical SOURCES paths are relative to acquisition root, which can differ from dataset directory", "old_inventory_preserved": True})
    publish(out / "PREPARATION_RESULT.json", {"catalog_recovery_complete": recovered,
        "completed_region_months": 72 if recovered else 71, "states": dict(Counter(r["state"] for r in rows)),
        "unique_requests": len(rows), "logical_references": sum(len(r["references"]) for r in rows),
        "cache_path_bindings_resolved": len(repaired), "cache_path_bindings_unresolved": len(unresolved),
        "new_source_HTTP_attempts": 1, "fit_complete": False, "confirmation_opened": False})
    missing = [r["request_key"] for r in rows if r["state"] == "missing_bytes"]
    publish(out / "DOWNLOAD_REGISTRATION.json", {"at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "objects_sha256": digest(out / "OBJECTS.json"), "missing_keys": missing,
        "initial_attempts_max": len(missing), "retry_attempts_max": min(1000, len(missing)),
        "max_bytes_each_attempt": 131073, "attempts_max": len(missing) + min(1000, len(missing)),
        "global_requests_per_second": 3, "transport_workers": 8,
        "rate_limit_policy": "429 globally halves rate and pauses 120 seconds; 5 rate-limit responses stop the batch",
        "new_generation_only": True, "deadline_at": "2026-09-16T00:24:27+00:00",
        "source_code_sha256": digest(sources / "fetch_public.py"), "confirmation_opened": False,
        "dataset_use": "2023 fit/internal selection; 2024 calibration with disclosed exposure; no fitting before role and semantic qualification"})
    print(json.dumps(read(out / "PREPARATION_RESULT.json")), flush=True)


if __name__ == "__main__":
    main()
