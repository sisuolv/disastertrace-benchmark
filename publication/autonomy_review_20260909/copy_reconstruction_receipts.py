"""Preserve completed publication command chains before the final evidence seal."""

from datetime import datetime, timezone
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PROJECT = REPO / "disastertrace-starter"
AUTONOMY = PROJECT / "artifacts/autonomy_10h_v1"
sys.path.insert(0, str(AUTONOMY))

from disastertrace.forecast_task.common import digest, read, write
from seal_cohort_evidence_v3 import PHASES, identity, successful_command

RECEIPTS = REPO / "review-outputs/autonomy-publication-20260909"
OUTPUT = AUTONOMY / "publication_reconstruction_02"


def main():
    if OUTPUT.exists():
        raise FileExistsError("the reconstruction receipt copy is already claimed")
    selected, cases, phases = {}, {}, {}

    def include(source, name=None):
        source = Path(source)
        name = name or source.name
        if source.is_symlink() or not source.is_file() or name in selected:
            raise ValueError("receipt is missing, nonregular or duplicated: " + name)
        selected[name] = (source, digest(source))

    def include_cpu_case(key, source):
        location = read(AUTONOMY / "reviews_continuation_v2" / ("LOCATION_" + key + ".json"))
        result = read(source)
        original = read(PROJECT / location["finalization"] / "cpu_relocated/receipt.json")
        if (result["status"] != "passed" or result["cli_exits"] != [0, 0, 0]
                or result["execution_id"] != location["execution_id"]
                or result["source_files"] != original["source_files"]
                or result["model_generations"] != 0 or result["network_blocked"] is not True
                or result["original_project_and_weights_blocked"] is not True
                or result["torch_and_vllm_loaded"] is not False
                or any(result["unexpected_blocked_attempts"].values())):
            raise ValueError("isolated CPU reconstruction receipt differs: " + key)
        name = "independent_cpu_" + key + ".json"
        include(source, name)
        cases[key] = {"execution_id": result["execution_id"], "report_id": location["report_id"],
                      "receipt": name, "source_files_match_original": True}

    restored = Path(read(RECEIPTS / "LOCAL_RECONSTRUCTION_ROOT_01.json")["root"])
    for name in ("LOCAL_RECONSTRUCTION_ROOT_01.json", "LOCAL_ARCHIVE_CACHE_ROOT_01.json",
                 "LOCAL_MIRROR_EVIDENCE_P6_P10_01.json", "LOCAL_MIRROR_EVIDENCE_P11_01.json",
                 "LOCAL_RESTORE_P6_P10_01.json", "LOCAL_RESTORE_P11_01.json"):
        include(RECEIPTS / name)
    for label in ("local_base_restore_p6_p10_01", "local_base_restore_p11_01",
                  "p11_restored_cpu_deepseek_r1_02"):
        successful_command(RECEIPTS, label)
        for suffix in ("_intent.json", "_result.json", ".log"):
            include(RECEIPTS / (label + suffix))
    include_cpu_case("p11_qwen3", AUTONOMY / "publication_reconstruction_01/INDEPENDENT_P11_RECEIPT_01.json")
    include_cpu_case("p11_deepseek_r1", restored / "disastertrace-starter/artifacts/p11_cohort_live_v1" /
                     "finalization_deepseek_r1_01/cpu_relocated/INDEPENDENT_PUBLICATION_RECEIPT_02.json")
    for phase in ("p12", "p13", "p14"):
        claim = read(RECEIPTS / (phase + "_publication_pipeline_01_claim.json"))
        status = read(RECEIPTS / (phase + "_publication_pipeline_01_status.json"))
        command_line = Path("/proc") / str(claim["pid"]) / "cmdline"
        if command_line.exists() and b"finalize_phase_evidence.py" in command_line.read_bytes():
            raise ValueError("publication controller is still writing: " + phase)
        if (status["status"] != "passed" or status["phase"] != phase
                or status["model_calls"] != 0 or status["gpu_submissions"] != 0):
            raise ValueError("publication pipeline has not completed: " + phase)
        for name, expected in claim["source_sha256"].items():
            if digest(name) != expected:
                raise ValueError("publication controller source changed")
        bundle = PROJECT / "artifacts" / PHASES[phase][0]
        acceptance = read(bundle / "COMPLETED_ACCEPTANCE.json")
        manifest = read(HERE / ("evidence_" + phase) / "manifest.json")
        identity(acceptance, "acceptance_id")
        identity(manifest, "manifest_id")
        if (status["acceptance_id"] != acceptance["acceptance_id"]
                or status["archive_manifest_id"] != manifest["manifest_id"]):
            raise ValueError("publication status names different evidence: " + phase)
        phases[phase] = {"acceptance_id": acceptance["acceptance_id"],
                         "archive_manifest_id": manifest["manifest_id"]}
        profiles = read(bundle / "PREREGISTRATION.json")["model_profiles"]
        labels = [phase + "_" + step + "_01" for step in (
            "findings", "acceptance_seal", "acceptance_verify", "archive_build",
            "archive_restore", "restored_inventory_verify")]
        labels.extend(phase + "_restored_cpu_" + profile + "_01" for profile in profiles)
        for label in labels:
            successful_command(RECEIPTS, label)
            for suffix in ("_intent.json", "_result.json", ".log"):
                include(RECEIPTS / (label + suffix))
        for suffix in ("_publication_pipeline_01_claim.json", "_publication_pipeline_01_status.json",
                       "_publication_controller_01.log", "_publication_controller_01_intent.json",
                       "_publication_controller_01_launch.json"):
            include(RECEIPTS / (phase + suffix))
        include(RECEIPTS / ("LOCAL_MIRROR_EVIDENCE_" + phase.upper() + "_01.json"))
        include(RECEIPTS / (phase.upper() + "_LOCAL_RESTORE_01.json"))
        for profile in profiles:
            key = phase + "_" + profile
            location = read(AUTONOMY / "reviews_continuation_v2" / ("LOCATION_" + key + ".json"))
            source = (restored / "disastertrace-starter" / location["finalization"] /
                      "cpu_relocated/INDEPENDENT_PUBLICATION_RECEIPT_01.json")
            include_cpu_case(key, source)
    OUTPUT.mkdir(exist_ok=False)
    copied = {}
    for name, (source, expected) in sorted(selected.items()):
        target = OUTPUT / name
        with target.open("xb") as stream:
            stream.write(source.read_bytes())
        if digest(target) != expected or digest(source) != expected:
            raise ValueError("receipt bytes changed while copying: " + name)
        copied[name] = {"source_path": str(source), "sha256": expected}
    write(OUTPUT / "COPY_RECEIPT.json", {
        "at": datetime.now(timezone.utc).isoformat(), "schema_version": "publication_reconstruction_copy_v1",
        "files": copied, "phases": phases, "cases": cases, "script_sha256": digest(__file__),
        "primary_accepted_evidence_unchanged": True, "model_calls": 0, "gpu_submissions": 0})
    print({"status": "passed", "files_copied": len(copied), "cases": sorted(cases)}, flush=True)


if __name__ == "__main__":
    main()
