"""Read-only evidence validation; write fresh replay receipts, never run models."""

import argparse
import contextlib
from datetime import datetime, timezone
import io
import json
from pathlib import Path

from audit_extra import main as replay_extra
from audit_gpu import main as replay_gpu
from common import ROOT, dump
from model_adapter import sha_file

WAVES = ["wave1", "wave2", "wave3_32b", "wave4_internvl", "wave5_diagnostics",
         "wave6_natural_coverage", "wave7_natural_assistance"]


def main(output):
    output.mkdir(parents=True, exist_ok=False)
    report = {"started_at": datetime.now(timezone.utc).isoformat(), "checks": [], "failures": []}
    checked_files = {}

    def check(path, expected):
        path = Path(path).resolve()
        if path not in checked_files:
            checked_files[path] = sha_file(path)
        if checked_files[path] != expected:
            raise ValueError("file binding mismatch: " + str(path))

    try:
        for item in json.loads((ROOT / "BASELINE.json").read_text()):
            check(ROOT.parent.parent / item["path"], item["sha256"])
        report["checks"].append({"name": "preserved_baseline", "files": 12, "status": "passed"})
        for directory in sorted((ROOT / "attempts").iterdir()):
            response = json.loads((directory / "response.json").read_text())
            body = directory / "body.bin"
            if body.stat().st_size != response["captured_bytes"]:
                raise ValueError("HTTP body length changed")
            check(body, response["body_sha256"])
        report["checks"].append({"name": "source_attempt_body_integrity", "attempts": len(list((ROOT / "attempts").iterdir())), "status": "passed"})

        def source_refs(value):
            if isinstance(value, list):
                for child in value:
                    source_refs(child)
            elif isinstance(value, dict):
                if "path" in value and "sha256" in value:
                    rel = value["path"]
                    check((ROOT.parent.parent if rel.startswith("plans/") else ROOT) / rel, value["sha256"])
                for child in value.values():
                    source_refs(child)

        source_refs(json.loads((ROOT / "FINAL_DATASETS.json").read_text()))
        report["checks"].append({"name": "selected_source_and_artifact_bindings", "status": "passed"})
        for number, wave in enumerate(WAVES, 1):
            batch = ROOT / "gpu" / wave
            plan = json.loads((batch / "PLAN.json").read_text())
            terminal = json.loads((batch / "ACP_TERMINAL.json").read_text())
            if len(terminal["jobs"]) != 4 or any(j["state"] != "SUCCEEDED" for j in terminal["jobs"]):
                raise ValueError("missing successful terminal GPU job")
            for rel, expected in plan["bound_files"].items():
                check(batch / rel, expected)
            for path, expected in plan["runtime_files"].items():
                check(path, expected)
            for worker, assignment in plan["workers"].items():
                hardware = json.loads((batch / "runs" / worker / "HARDWARE.json").read_text())
                if hardware["count"] != 1 or "H100" not in hardware["name"]:
                    raise ValueError("actual GPU hardware mismatch")
                done = json.loads((batch / "runs" / worker / "DONE.json").read_text())
                if done["tasks"] != len(assignment["tasks"]) or done["requests"] > assignment["max_calls"]:
                    raise ValueError("worker completion denominator differs")
                intent = json.loads((batch / "submissions" / worker / "INTENT.json").read_text())
                check(batch / "PLAN.json", intent["plan_sha256"])
                check(batch / "submissions" / worker / "run.sh", intent["runner_sha256"])
            destination = output / ("WAVE%d_REPLAY.json" % number)
            with contextlib.redirect_stdout(io.StringIO()):
                if number == 5:
                    replay_extra(destination)
                else:
                    replay_gpu(batch, destination)
            original = ROOT / ("analysis/WAVE%d_AUDIT.json" % number)
            if json.loads(original.read_text()) != json.loads(destination.read_text()):
                raise ValueError("recomputed audit differs from accepted report")
            report["checks"].append({"name": wave, "status": "passed", "replay_sha256": sha_file(destination),
                                     "plan_sha256": sha_file(batch / "PLAN.json")})
            print(wave + " raw replay and source/runtime bindings passed", flush=True)
        result = json.loads((ROOT / "analysis/FINAL_RESULTS_02.json").read_text())
        if result["total_captured_calls"] != 3599 or result["total_intents"] != 3599:
            raise ValueError("final call accounting differs")
        for name, expected in result["input_files"].items():
            check(ROOT / "analysis" / name, expected)
        report["status"] = "passed"
    except Exception as error:
        report["status"] = "failed"
        report["failures"].append({"type": type(error).__name__, "message": str(error)})
        raise
    finally:
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        report["unique_files_hashed"] = len(checked_files)
        report["model_inference_performed"] = False
        dump(output / "VERIFICATION.json", report)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args().output.resolve())
