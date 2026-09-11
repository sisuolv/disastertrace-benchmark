"""Freeze a new V2 execution while preserving the consumed V1 run."""

import hashlib
import importlib.metadata
import json
from pathlib import Path
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[2]
V1 = ROOT.parent / "mm3_20260909"
OFFLINE = ROOT.parent / "mm3_contract_v2_offline_20260909"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        json.dump(data, stream, indent=2)
        stream.write("\n")


def main():
    previous = json.loads((V1 / "COMPLETED.json").read_text())
    for name, expected in previous["local_files_sha256"].items():
        if sha(ROOT.parent / name) != expected:
            raise ValueError("prior evidence changed: " + name)
    candidate = json.loads((OFFLINE / "CANDIDATE_PLAN.json").read_text())
    prior_plan = json.loads((V1 / "REQUEST_PLAN.json").read_text())
    if sum(len(t["requests"]) for t in candidate["trajectories"]) != 12:
        raise ValueError("unexpected V2 opportunity count")
    for old, new in zip(prior_plan["trajectories"], candidate["trajectories"], strict=True):
        if (old["id"], old["branch"]) != (new["id"], new["branch"]):
            raise ValueError("trajectory semantics changed")
        for before, after in zip(old["requests"], new["requests"], strict=True):
            if {k: v for k, v in before.items() if k != "output_contract"} != {
                k: v for k, v in after.items() if k != "output_contract"
            }:
                raise ValueError("public evidence changed")
            if after["output_contract"]["format_version"] != "explicit_site_mapping_v2":
                raise ValueError("wrong output contract")
    candidate["schema"] = "mm3-contract-v2-live-12-v1"
    candidate["status"] = "frozen_for_new_execution"
    save(ROOT / "REQUEST_PLAN.json", candidate)
    save(ROOT / "SCOPE.json", {
        "user_action": "Execute the prepared V2 model validation",
        "max_generations": 12, "retries": 0, "paid_api_calls": 0,
        "event_id": "AL062024", "event_count": 1, "heldout": False,
        "training": False, "initial_history": "empty per independent trajectory",
        "history_policy": "own previous raw answer, including invalid answers",
        "h100_cards": 1, "global_h100_cap": 4, "max_worker_seconds": 3600,
        "prior_run_reused": False, "prior_acceptance_id": previous["acceptance_id"],
        "candidate_sha256": sha(OFFLINE / "CANDIDATE_PLAN.json"),
    })
    shutil.copytree(V1 / "source", ROOT / "source", ignore=shutil.ignore_patterns("__pycache__"))
    for path in (OFFLINE / "source").rglob("*.py"):
        target = ROOT / "source" / path.relative_to(OFFLINE / "source")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    (ROOT / "model_acquisition").mkdir()
    shutil.copyfile(V1 / "model_acquisition/plan.json", ROOT / "model_acquisition/plan.json")
    shutil.copyfile(V1 / "RUNTIME_BINDINGS.json", ROOT / "RUNTIME_BINDINGS.json")
    shutil.copyfile(V1 / "runtime-resolved.txt", ROOT / "runtime-resolved.txt")
    for name in ["verify_captures.py", "review_cpu.py"]:
        shutil.copyfile(V1 / name, ROOT / name)
    submit = (V1 / "submit_job.py").read_text().replace('name = "dt-mm3-vlm-" + stamp', 'name = "dt-mm3-v2-" + stamp')
    with (ROOT / "submit_job.py").open("x") as stream:
        stream.write(submit)
    old_execution = json.loads((V1 / "EXECUTION.json").read_text())
    versions = {k: importlib.metadata.version(k) for k in old_execution["runtime_versions"]}
    if versions != old_execution["runtime_versions"]:
        raise ValueError("runtime versions changed")
    for name, expected in json.loads((ROOT / "RUNTIME_BINDINGS.json").read_text()).items():
        if sha(Path(name)) != expected:
            raise ValueError("runtime implementation changed")
    sys.path.insert(0, str(ROOT / "source/src"))
    import torch
    from transformers import AutoProcessor
    from disastertrace.multimodal_live_v1.adapter import QwenBackend
    from disastertrace.multimodal_live_v1.preflight import check_readability
    from disastertrace.multimodal_v1.storage import read, now

    torch.set_num_threads(4)
    processor = AutoProcessor.from_pretrained(old_execution["model_directory"], local_files_only=True, trust_remote_code=False)
    processor.image_processor.size = {"shortest_edge": 65536, "longest_edge": 1048576}
    backend = QwenBackend(processor, None, old_execution["settings"])
    contexts, checks = [], []
    for trajectory in candidate["trajectories"]:
        for index, template in enumerate(trajectory["requests"]):
            slot = ROOT / "cpu_preflight" / trajectory["id"] / str(index)
            slot.mkdir(parents=True)
            request = dict(template, carrier=None)
            inputs = backend.prepare(request, slot)
            checks.extend(check_readability(request, inputs, processor, slot))
            info = read(slot / "processor.json")
            contexts.append({"trajectory": trajectory["id"], "checkpoint": template["checkpoint"],
                             "input_tokens": info["input_tokens"], "visual_tokens": info["visual_tokens"]})
    save(ROOT / "CPU_PREFLIGHT.json", {"status": "passed", "at": now(), "generations": 0,
         "runtime_versions": versions, "contexts": contexts, "readability_checks": checks,
         "prior_bound_files_verified": len(previous["local_files_sha256"]),
         "reused_tests": {"live_capture_tests": 16, "v2_contract_tests": 41,
                          "live_test_receipt_sha256": sha(V1 / "CPU_TESTS_FINAL.xml"),
                          "contract_test_receipt_sha256": sha(OFFLINE / "TESTS.xml")}})
    execution = dict(old_execution)
    execution.update(schema="mm3-contract-v2-live-execution-v1", created_at=now(),
                     not_after_unix=time.time() + 3600, plan_sha256=sha(ROOT / "REQUEST_PLAN.json"),
                     reference_sha256=sha(ROOT.parent / "mm0_2_20260909/build_02/private/references.json"),
                     source_sha256={str(p.relative_to(ROOT)): sha(p) for p in (ROOT / "source").rglob("*.py")},
                     prior_acceptance_id=previous["acceptance_id"])
    execution["source_sha256"]["model_acquisition/plan.json"] = sha(ROOT / "model_acquisition/plan.json")
    execution["source_sha256"]["SCOPE.json"] = sha(ROOT / "SCOPE.json")
    save(ROOT / "EXECUTION.json", execution)
    print(json.dumps({"status": "frozen", "requests": 12, "readability_checks": len(checks),
          "max_input_tokens_without_carrier": max(x["input_tokens"] for x in contexts),
          "execution_sha256": sha(ROOT / "EXECUTION.json"), "not_after_unix": execution["not_after_unix"]}))


if __name__ == "__main__":
    main()
