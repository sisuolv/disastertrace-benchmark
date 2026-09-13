"""Freeze a new calendar and a bounded 252-call development diagnostic."""

import argparse
import json
import shutil
import socket
from collections import Counter, defaultdict
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from gpu.gpu_worker import digest, save
from transformers import AutoTokenizer

from disastertrace.monitoring_fixed_v1.aviation import AviationProvider
from disastertrace.monitoring_fixed_v1.contracts import Target, fingerprint
from disastertrace.monitoring_fixed_v1.representations import model_messages
from disastertrace.monitoring_fixed_v1.taf_tasks import TafEvidenceTask, evaluate
from disastertrace.monitoring_fixed_v1.taf_tasks import messages as taf_messages
from disastertrace.monitoring_v1.providers.aviation import parse_taf

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
HOUR = 3_600_000_000


def taf_tasks():
    native = HERE / "source_native_01"
    captured = json.loads((native / "MANIFEST.json").read_text())
    grouped, failures = defaultdict(list), []
    for receipt in captured["rows"]:
        p = native / receipt["body_file"]
        if (
            not receipt["complete"]
            or receipt["http_status"] != 200
            or digest(p) != receipt["sha256"]
        ):
            raise ValueError("Incomplete native source acquisition")
        m = receipt["catalog_metadata"]
        issue = m["issued_at"].replace(" ", "T") + ":00Z"
        try:
            product = parse_taf(p.read_text(), station=m["station"], archive_issue=issue)
            if product.status != "active":
                failures.append(
                    {
                        "source_id": receipt["id"],
                        "reason": "not_active",
                        "native_status": product.status,
                    }
                )
                continue
        except ValueError as exc:
            failures.append({"source_id": receipt["id"], "reason": str(exc)})
            continue
        source = {
            "source_id": receipt["id"],
            "station": m["station"],
            "raw": p.read_text(),
            "issued_at": product.issued_at,
            "available_at": product.issued_at + 120_000_000,
            "completed_at": product.issued_at + 120_000_000,
        }
        grouped[m["station"]].append((source, product))
    tasks, annotations = [], []
    for station, sources in sorted(grouped.items()):
        sources.sort(key=lambda r: (r[0]["issued_at"], r[0]["source_id"]))
        if len(sources) < 3:
            raise ValueError("Preregistered TAF cases unavailable; do not replace stations")
        for i, (source, native) in enumerate(sources[:2]):
            for label, start, end in (
                ("full", native.valid_end - 2 * HOUR, native.valid_end - HOUR),
                ("partial", native.valid_end - HOUR // 2, native.valid_end + HOUR // 2),
                ("none", native.valid_end, native.valid_end + HOUR),
            ):
                ident = "taf-window-" + fingerprint([station, source["source_id"], start, end])[:24]
                target = Target(
                    ident,
                    "station:" + station,
                    "visibility",
                    "m",
                    "event_probability",
                    "interval",
                    start,
                    end,
                    "future_physical",
                    "iem_routine_unique_hour.v1",
                    "lt",
                    5000,
                )
                task = TafEvidenceTask.freeze(
                    {
                        "schema": "disastertrace.taf_E_task.v1",
                        "task_id": ident,
                        "kind": "coverage",
                        "target": target.to_dict(),
                        "as_of": source["completed_at"],
                        "availability_basis": "declared_archive_scenario",
                        "products": [source],
                    }
                )
                reference = evaluate(task)
                assert reference["answer"]["coverage"] == label
                tasks.append(task)
                annotations.append(
                    {
                        "task_hash": task.task_hash,
                        "source_kind": "real_native_TAF",
                        "target_selection": "native-validity-edge E question; not a scored future visibility forecast",
                        "reference": reference,
                    }
                )
        for i in range(2):
            (old, _), (new, native) = sources[i : i + 2]
            if old["issued_at"] >= new["issued_at"]:
                raise ValueError("Non-strict chronological pair; keep gate open")
            start = max(new["completed_at"] + HOUR, native.valid_start + HOUR)
            target = Target(
                f"taf-revision-{station}-{i}",
                "station:" + station,
                "visibility",
                "m",
                "event_probability",
                "interval",
                start,
                start + HOUR,
                "future_physical",
                "iem_routine_unique_hour.v1",
                "lt",
                5000,
            )
            for condition, disclosed in (("old_only", [old]), ("both", [old, new]), ("none", [])):
                ident = (
                    "taf-revision-"
                    + fingerprint([station, i, [p["source_id"] for p in disclosed]])[:24]
                )
                task = TafEvidenceTask.freeze(
                    {
                        "schema": "disastertrace.taf_E_task.v1",
                        "task_id": ident,
                        "kind": "revision",
                        "target": replace(target, target_id=ident).to_dict(),
                        "as_of": new["completed_at"],
                        "availability_basis": "declared_archive_scenario",
                        "products": disclosed,
                    }
                )
                tasks.append(task)
                annotations.append(
                    {
                        "task_hash": task.task_hash,
                        "source_kind": "real_native_TAF",
                        "target_selection": "same station/window, changing only the legally disclosed source set",
                        "reference": evaluate(task),
                    }
                )
    if len(tasks) != 36:
        raise ValueError("Preregistered native task count differs")
    return tasks, annotations, failures


def main(dataset, output):
    mission = json.loads((HERE / "MODEL_MISSION.json").read_text())
    prior = json.loads(
        (HERE.parent / "v7_followup_execution_20260913/gpu/heads_smoke_01/PLAN.json").read_text()
    )
    bank = json.loads(
        (ROOT / "plans/v7_execution_20260913/evidence_bundle/matrix_01/BANK.json").read_text()
    )
    provider = AviationProvider(dataset, bank)
    cutoffs = sorted({o["cutoff"] for o in provider.opportunities.values()})[:2]
    selected = [
        o
        for o in provider.opportunities.values()
        if o["cutoff"] in cutoffs and o["lead_hours"] in {1, 3} and o["threshold_m"] == 5000
    ]
    if len(selected) != 12:
        raise ValueError("Frozen calendar selection has the wrong count")
    output.mkdir(parents=True, exist_ok=False)
    (output / "policy").mkdir()
    source = output / "source"
    for module in ("monitoring_v1", "monitoring_fixed_v1"):
        shutil.copytree(
            ROOT / "disastertrace-starter/src/disastertrace" / module,
            source / "disastertrace" / module,
            ignore=shutil.ignore_patterns("__pycache__"),
        )
    (source / "disastertrace/__init__.py").write_text('"""Frozen monitoring-only package."""\n')
    shutil.copyfile(HERE / "gpu/gpu_worker.py", source / "gpu_worker.py")
    shutil.copyfile(HERE / "MODEL_MISSION.json", output / "MODEL_MISSION.json")
    tokenizer = AutoTokenizer.from_pretrained(prior["model"]["directory"], local_files_only=True)
    workers, inputs = {"0": [], "1": [], "2": []}, []

    def add(payload, request, row, worker):
        rendered = tokenizer.apply_chat_template(
            request, tokenize=False, add_generation_prompt=True, enable_thinking=False
        )
        n = len(tokenizer(rendered, add_special_tokens=False)["input_ids"])
        if n + prior["max_new_tokens"] > prior["context_limit"]:
            raise ValueError("Input exceeds frozen context cap")
        row = dict(row, input_tokens=n, messages_sha256=fingerprint(request))
        save(output / "policy" / (row["call_id"] + ".json"), payload)
        workers[worker].append(row)
        inputs.append({**row, "input_sha256": fingerprint(payload)})

    for opportunity in sorted(selected, key=lambda o: o["opportunity_id"]):
        for condition in mission["evidence_conditions"]:
            bundle = provider.freeze(opportunity["opportunity_id"], condition)
            view = bundle.policy_view()
            started = view["cutoff"] - 60_000_000
            if (
                max(
                    [view["baseline"]["available_at"]] + [a["completed_at"] for a in view["assets"]]
                )
                > started
            ):
                raise ValueError("A preregistered input is not available before invocation")
            for worker, head in enumerate(mission["heads"]):
                for representation in mission["representations"]:
                    cid = fingerprint(
                        [
                            "adaptive.development.20250203.v1",
                            opportunity["opportunity_id"],
                            condition,
                            head,
                            representation,
                        ]
                    )[:24]
                    add(
                        bundle.to_dict(),
                        model_messages(bundle, head, representation),
                        {
                            "call_id": cid,
                            "input_kind": "bundle",
                            "head": head,
                            "condition": condition,
                            "representation": representation,
                            "opportunity_id": opportunity["opportunity_id"],
                            "logical_started_at": started,
                            "logical_cutoff": view["cutoff"],
                            "bundle_hash": bundle.bundle_hash,
                        },
                        str(worker),
                    )
    native, annotations, failures = taf_tasks()
    for task in native:
        view = task.view()
        cid = fingerprint(["adaptive.native_E.v1", task.task_hash])[:24]
        add(
            view,
            taf_messages(task),
            {
                "call_id": cid,
                "input_kind": "taf_task",
                "head": "taf_" + view["kind"],
                "representation": "complete_native_products",
                "condition": view["kind"],
                "task_id": view["task_id"],
                "logical_started_at": view["as_of"],
                "logical_cutoff": view["as_of"] + 60_000_000,
                "bundle_hash": task.task_hash,
            },
            "2",
        )
    total = sum(len(v) for v in workers.values())
    if total != mission["expected_total_calls"]:
        raise ValueError("Frozen model-call cap changed")
    plan = {
        **{
            k: prior[k]
            for k in (
                "model",
                "runtime_versions",
                "seed",
                "max_new_tokens",
                "max_generation_seconds",
                "context_limit",
            )
        },
        "schema": "disastertrace.adaptive_development_model.v1",
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "workers": workers,
        "files": {str(p.relative_to(output)): digest(p) for p in output.rglob("*") if p.is_file()},
        "max_calls_per_worker": max(len(v) for v in workers.values()),
        "max_worker_seconds": 3600,
        "max_concurrent_gpus": 4,
        "expected_calls": total,
        "cci_hostname": socket.gethostname(),
        "retries": 0,
        "model_mission_sha256": digest(HERE / "MODEL_MISSION.json"),
        "outcomes_packaged": False,
        "tools": [],
        "online_inference": False,
        "old_launches_reused": False,
    }
    save(output / "PLAN.json", plan)
    save(
        HERE / "reports/NATIVE_TASK_REFERENCES.json",
        {
            "tasks": annotations,
            "parser_exclusions": failures,
            "native_coverage_counts": dict(
                Counter(a["reference"]["answer"].get("coverage") for a in annotations)
            ),
            "native_unsupported_model_cases": sum(
                a["reference"]["answer"]["status"] == "unsupported" for a in annotations
            ),
            "synthetic_edge_tests_are_separate": True,
        },
    )
    save(
        output / "CPU_PREFLIGHT.json",
        {
            "tasks": total,
            "worker_counts": {k: len(v) for k, v in workers.items()},
            "inputs_available": True,
            "generation_calls": 0,
            "min_input_tokens": min(i["input_tokens"] for i in inputs),
            "max_input_tokens": max(i["input_tokens"] for i in inputs),
            "plan_sha256": digest(output / "PLAN.json"),
        },
    )
    save(output / "EXPOSURE_LEDGER.json", inputs)
    print(
        json.dumps(
            {
                "frozen_calls": total,
                "worker_counts": {k: len(v) for k, v in workers.items()},
                "plan_sha256": digest(output / "PLAN.json"),
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    main(args.dataset, args.output)
