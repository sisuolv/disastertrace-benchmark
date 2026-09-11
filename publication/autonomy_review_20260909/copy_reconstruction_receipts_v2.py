"""Bind persistent CPU recovery receipts without rewriting interrupted commands."""

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


def validate_cpu_case(result, original, location):
    if (original["status"] != "passed" or not original["source_files"]
            or result["status"] != "passed" or result["cli_exits"] != [0, 0, 0]
            or result["execution_id"] != location["execution_id"]
            or result["execution_id"] != original["execution_id"]
            or result["package_id"] != original["package_id"]
            or result["source_files"] != original["source_files"]
            or result["model_generations"] != 0 or result["network_blocked"] is not True
            or result["original_project_and_weights_blocked"] is not True
            or result["torch_and_vllm_loaded"] is not False
            or result["unexpected_blocked_attempts"] != {
                "forbidden_import": 0, "network": 0, "original_path": 0, "subprocess": 0}):
        raise ValueError("isolated CPU reconstruction receipt differs")


def main():
    if OUTPUT.exists():
        raise FileExistsError("the persistent reconstruction copy is already claimed")
    selected, cases, phases = {}, {}, {}

    def include(source, name=None):
        source = Path(source)
        name = name or source.name
        if source.is_symlink() or not source.is_file() or Path(name).name != name:
            raise ValueError("receipt is missing or nonregular: " + name)
        value = (source, digest(source))
        if name in selected and selected[name] != value:
            raise ValueError("conflicting receipt copy: " + name)
        selected[name] = value

    def command(label):
        successful_command(RECEIPTS, label)
        for suffix in ("_intent.json", "_result.json", ".log"):
            include(RECEIPTS / (label + suffix))

    status = read(RECEIPTS / "CPU_PUBLICATION_RECOVERY_03_STATUS.json")
    claim = read(RECEIPTS / "CPU_PUBLICATION_RECOVERY_03_CLAIM.json")
    source_hash = digest(HERE / "complete_cpu_reconstruction_v3.py")
    interruption = AUTONOMY / "CPU_PUBLICATION_INTERRUPTION_02.json"
    prior_status = RECEIPTS / "CPU_PUBLICATION_RECOVERY_02_STATUS.json"
    prior_claim = read(RECEIPTS / "CPU_PUBLICATION_RECOVERY_02_CLAIM.json")
    if (status["status"] != "passed" or status["model_calls"] != 0 or status["gpu_submissions"] != 0
            or claim["model_calls"] != 0 or claim["gpu_submissions"] != 0
            or status["script_sha256"] != source_hash or claim["script_sha256"] != source_hash
            or claim["prior_status_sha256"] != digest(prior_status)
            or status["prior_status_sha256"] != digest(prior_status)
            or prior_claim["prior_interruption_sha256"] != digest(interruption)
            or prior_claim["script_sha256"] != digest(HERE / "recover_cpu_publication_v2.py")
            or read(prior_status)["status"] != "failed"):
        raise ValueError("persistent CPU recovery has not passed with unchanged source")
    for name in ("CPU_PUBLICATION_RECOVERY_02_CLAIM.json", "CPU_PUBLICATION_RECOVERY_02_STATUS.json",
                 "CPU_PUBLICATION_RECOVERY_03_CLAIM.json", "CPU_PUBLICATION_RECOVERY_03_STATUS.json",
                 "LOCAL_RECONSTRUCTION_ROOT_02.json", "LOCAL_ARCHIVE_CACHE_ROOT_02.json",
                 "recovery_controller_02.log", "recovery_controller_03.log",
                 "p11_deepseek_r1_recovery_cpu_02_intent.json", "p11_deepseek_r1_recovery_cpu_02_result.json",
                 "p11_deepseek_r1_recovery_cpu_02.log"):
        include(RECEIPTS / name)
    for name, expected in read(interruption)["preserved_receipts_sha256"].items():
        if digest(RECEIPTS / name) != expected:
            raise ValueError("interrupted command evidence changed: " + name)
        include(RECEIPTS / name)
    # Missing exits on interrupted commands stay missing; only the new chain can pass.
    for pattern in ("CLOSE_GLOBAL_01*", "p12_publication_*", "p13_publication_*"):
        for path in RECEIPTS.glob(pattern):
            include(path)
    for label in ("p14_findings_01", "p14_acceptance_seal_02", "p14_acceptance_verify_02", "p14_archive_build_02"):
        command(label)
    archive_keys = {"p6_p10", "p11", "p12", "p13", "p14"}
    if set(status["manifests"]) != archive_keys:
        raise ValueError("recovery archive scope differs")
    for phase in sorted(archive_keys):
        folder = HERE / ("evidence_" + phase)
        manifest = read(folder / "manifest.json")
        identity(manifest, "manifest_id")
        record = status["manifests"][phase]
        if record != {"manifest_id": manifest["manifest_id"], "acceptances": manifest["acceptances"]}:
            raise ValueError("recovery names a different accepted archive: " + phase)
        mirror_path = RECEIPTS / (phase + "_archive_mirror_02.json")
        mirror = read(mirror_path)
        names = {"BUILD_CLAIM.json", "manifest.json", *manifest["parts"]}
        if set(mirror["files_sha256"]) != names:
            raise ValueError("archive mirror is incomplete")
        for name, expected in mirror["files_sha256"].items():
            if digest(folder / name) != expected:
                raise ValueError("accepted archive changed after local mirroring")
            if name in manifest["parts"] and manifest["parts"][name]["sha256"] != expected:
                raise ValueError("archive part differs from the manifest")
        restore_path = RECEIPTS / (phase + "_RESTORE_RECEIPT_02.json")
        restore = read(restore_path)
        if (restore["status"] != "passed" or restore["model_calls"] != 0
                or restore["manifest_id"] != manifest["manifest_id"]
                or restore["evidence_paths"] != len(manifest["files"])
                or restore["objects_verified"] != len(manifest["objects"])):
            raise ValueError("archive restoration receipt differs")
        include(mirror_path)
        include(restore_path)
        command(phase + "_recovery_restore_02")
        if phase == "p6_p10":
            continue
        acceptance_path = PROJECT / "artifacts" / PHASES[phase][0] / "COMPLETED_ACCEPTANCE.json"
        acceptance = read(acceptance_path)
        identity(acceptance, "acceptance_id")
        if manifest["acceptances"] != {acceptance_path.relative_to(REPO).as_posix(): {
                "acceptance_id": acceptance["acceptance_id"], "sha256": digest(acceptance_path),
                "evidence_files": len(acceptance["evidence_sha256"])}}:
            raise ValueError("phase archive and original acceptance differ")
        command(phase + "_recovery_inventory_02")
        phases[phase] = {"acceptance_id": acceptance["acceptance_id"], "archive_manifest_id": manifest["manifest_id"]}
    reviews = read(AUTONOMY / "reviews_continuation_v2/FINAL_STATUS.json")
    if reviews["status"] != "passed" or len(reviews["completed"]) != 6 or set(status["cases"]) != set(reviews["completed"]):
        raise ValueError("all six original model conditions require recovered CPU receipts")
    for key, item in sorted(status["cases"].items()):
        location = read(AUTONOMY / "reviews_continuation_v2" / ("LOCATION_" + key + ".json"))
        if location != reviews["completed"][key] or any(item[k] != location[k] for k in ("execution_id", "report_id")):
            raise ValueError("recovered CPU case has a different original identity")
        source = REPO / item["receipt"]
        if source != RECEIPTS / ("INDEPENDENT_CPU_" + key + "_03.json") or digest(source) != item["sha256"]:
            raise ValueError("persistent CPU receipt path or digest differs")
        audit = PROJECT / location["finalization"] / "cpu_relocated"
        result, original = read(source), read(audit / "receipt.json")
        validate_cpu_case(result, original, location)
        report = read(audit / "report.json")
        identity(report, "report_id")
        if report["report_id"] != location["report_id"]:
            raise ValueError("original isolated report differs from the location")
        label = key + "_recovery_cpu_03"
        if item["command"] != label:
            raise ValueError("unexpected CPU reconstruction command")
        command(label)
        name = "independent_cpu_" + key + ".json"
        include(source, name)
        cases[key] = {"execution_id": location["execution_id"], "report_id": location["report_id"],
                      "receipt": name, "source_files_match_original": True}
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
        "at": datetime.now(timezone.utc).isoformat(), "schema_version": "publication_reconstruction_copy_v2",
        "files": copied, "phases": phases, "cases": cases, "script_sha256": digest(__file__),
        "recovery_status_sha256": digest(RECEIPTS / "CPU_PUBLICATION_RECOVERY_03_STATUS.json"),
        "prior_interruption_sha256": digest(interruption), "primary_accepted_evidence_unchanged": True,
        "model_calls": 0, "gpu_submissions": 0, "missing_prior_command_exits_not_inferred": True})
    print({"status": "passed", "files_copied": len(copied), "cases": sorted(cases)}, flush=True)


if __name__ == "__main__":
    main()
