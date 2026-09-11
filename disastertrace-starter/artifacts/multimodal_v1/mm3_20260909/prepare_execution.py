"""Freeze exact code, runtime, model and the first twelve development requests."""

import datetime
import hashlib
import json
from pathlib import Path
import shutil
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    assert json.loads((ROOT / "model_acquisition/COMPLETE.json").read_text())["files"] == 16
    assert json.loads((ROOT / "CPU_PROCESSOR_PREFLIGHT.json").read_text())["status"] == "passed"
    suite = ET.parse(ROOT / "CPU_TESTS_FINAL.xml").find("testsuite")
    assert suite is not None and int(suite.attrib["tests"]) == 16
    assert all(int(suite.attrib[k]) == 0 for k in ["errors", "failures", "skipped"])
    freeze = ROOT / "source"
    freeze.mkdir(exist_ok=False)
    files = [PROJECT / "src/disastertrace/__init__.py", PROJECT / "src/disastertrace/models.py"]
    files += list((PROJECT / "src/disastertrace/multimodal_v1").glob("*.py"))
    files += list((PROJECT / "src/disastertrace/multimodal_live_v1").glob("*.py"))
    files += [PROJECT / "tests/test_multimodal_live_v1.py"]
    for source in files:
        target = freeze / source.relative_to(PROJECT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    bindings = {str(p.relative_to(ROOT)): sha(p) for p in freeze.rglob("*") if p.is_file()}
    scope = {"schema": "mm3-vlm-execution-v1", "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
             "not_after_unix": time.time() + 3600,
             "model_directory": "/mnt/afs/260010168/models/Qwen3-VL-8B-Instruct-mm3-pinned-v1",
             "model_revision": json.loads((ROOT / "model_acquisition/plan.json").read_text())["revision"],
             "plan_sha256": sha(ROOT / "REQUEST_PLAN.json"), "source_sha256": bindings,
             "runtime_bindings_sha256": sha(ROOT / "RUNTIME_BINDINGS.json"),
             "runtime_versions": json.loads((ROOT / "CPU_PROCESSOR_PREFLIGHT.json").read_text())["runtime_versions"],
             "settings": {"max_new_tokens": 2048, "max_generation_seconds": 120,
                          "context_limit": 16384, "do_sample": False, "dtype": "bfloat16",
                          "attention": "sdpa", "seed": 20260909,
                          "image_max_pixels": 1048576, "image_min_pixels": 65536},
             "max_generations": 12, "max_worker_seconds": 3600, "max_h100_this_job": 1,
             "max_h100_global": 4, "retry_times": 0, "paid_api": False, "heldout": False,
             "interface_gate": "12 received contract-valid outputs, all EOS; semantic errors retained and reported",
             "scope": "one-event development diagnostic; no leaderboard inference"}
    with (ROOT / "EXECUTION.json").open("x") as stream:
        json.dump(scope, stream, indent=2)
        stream.write("\n")
    print("execution_sha256", sha(ROOT / "EXECUTION.json"))


if __name__ == "__main__":
    main()
