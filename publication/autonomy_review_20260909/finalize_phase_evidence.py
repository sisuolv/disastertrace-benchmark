"""Close one already audited phase and restore its evidence using CPU only."""

import argparse
from datetime import datetime, timedelta, timezone
import fcntl
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PROJECT = REPO / "disastertrace-starter"
AUTONOMY = PROJECT / "artifacts/autonomy_10h_v1"
sys.path.insert(0, str(AUTONOMY))

from disastertrace.forecast_task.common import digest, read, write
from seal_cohort_evidence_v3 import PHASES, successful_command

CPU = "/mnt/afs/260010168/.venvs/disastertrace-p4-review-cpu-v1/bin/python"
CORE = str(PROJECT / ".venv/bin/python")
RECEIPTS = REPO / "review-outputs/autonomy-publication-20260909"


def now():
    return datetime.now(timezone.utc).isoformat()


def command(label, argv, *, cwd=PROJECT, source_project=PROJECT):
    write(RECEIPTS / (label + "_intent.json"), {"at": now(), "argv": argv, "cwd": str(cwd),
          "environment": {"CUDA_VISIBLE_DEVICES": "", "PYTHONDONTWRITEBYTECODE": "1",
                          "PYTHONPATH": str(source_project / "src")}})
    log = RECEIPTS / (label + ".log")
    env = dict(os.environ, CUDA_VISIBLE_DEVICES="", PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1",
               PYTHONPATH=str(source_project / "src"), HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1",
               TOKENIZERS_PARALLELISM="false", OMP_NUM_THREADS="4")
    print(label, "started", now(), flush=True)
    with log.open("x") as stream:
        result = subprocess.run(argv, cwd=cwd, env=env, stdout=stream, stderr=subprocess.STDOUT)
    write(RECEIPTS / (label + "_result.json"), {"at": now(), "exit_code": result.returncode,
          "log_sha256": digest(log)})
    print(label, "exit", result.returncode, log.read_text()[-1200:], flush=True)
    if result.returncode:
        raise RuntimeError("CPU phase finalization command failed: " + label)


def finalize(phase):
    status_path = RECEIPTS / (phase + "_publication_pipeline_01_status.json")
    source_paths = [Path(__file__), HERE / "write_cohort_findings.py", HERE / "evidence_archive.py",
                    AUTONOMY / "seal_cohort_evidence_v3.py"]
    sources = {str(path): digest(path) for path in source_paths}
    write(RECEIPTS / (phase + "_publication_pipeline_01_claim.json"),
          {"at": now(), "pid": os.getpid(), "source_sha256": sources, "model_calls": 0,
           "gpu_submissions": 0, "phase": phase})
    final = {"status": "failed", "phase": phase, "model_calls": 0, "gpu_submissions": 0}
    try:
        bundle = PROJECT / "artifacts" / PHASES[phase][0]
        profiles = read(bundle / "PREREGISTRATION.json")["model_profiles"]
        reviews = AUTONOMY / "reviews_continuation_v2"
        deadline = datetime.fromisoformat(read(PROJECT / "artifacts/p7_forecast_live_v1/AUTONOMY_WINDOW.json")["autonomous_work_deadline"]) + timedelta(minutes=45)
        while True:
            locations = [reviews / ("LOCATION_" + phase + "_" + profile + ".json") for profile in profiles]
            predecessor = PROJECT / "artifacts" / ("p11_cohort_live_v1" if phase == "p12" else "p12_compact_grammar_v1") / "COMPLETED_ACCEPTANCE.json"
            if all(path.exists() for path in locations) and predecessor.exists():
                break
            if datetime.now(timezone.utc) >= deadline:
                raise RuntimeError("CPU closing grace ended before required verified results")
            time.sleep(30)
        for path, expected in sources.items():
            if digest(path) != expected:
                raise ValueError("CPU finalizer source changed after its claim")
        command(phase + "_findings_01", [CORE, str(HERE / "write_cohort_findings.py"), "--phase", phase])
        sealer = [CORE, str(AUTONOMY / "seal_cohort_evidence_v3.py"), "--phase", phase]
        command(phase + "_acceptance_seal_01", sealer)
        command(phase + "_acceptance_verify_01", sealer + ["--verify"])
        archive = HERE / ("evidence_" + phase)
        command(phase + "_archive_build_01", [CORE, str(HERE / "evidence_archive.py"), "build", "--repo", str(REPO),
                "--acceptance", (bundle / "COMPLETED_ACCEPTANCE.json").relative_to(REPO).as_posix(), "--output", str(archive)])
        cache = Path(read(RECEIPTS / "LOCAL_ARCHIVE_CACHE_ROOT_01.json")["root"]) / archive.name
        cache.mkdir(exist_ok=False)
        manifest = read(archive / "manifest.json")
        mirrored = {}
        for name in ["BUILD_CLAIM.json", "manifest.json", *manifest["parts"]]:
            source, target = archive / name, cache / name
            if source.is_symlink() or not source.is_file():
                raise ValueError("archive mirror requires regular files")
            expected = digest(source)
            shutil.copyfile(source, target)
            if digest(target) != expected:
                raise ValueError("local archive mirror changed bytes")
            mirrored[name] = expected
        write(RECEIPTS / ("LOCAL_MIRROR_EVIDENCE_" + phase.upper() + "_01.json"),
              {"at": now(), "source": str(archive), "destination": str(cache), "files_sha256": mirrored,
               "manifest_id": manifest["manifest_id"]})
        restored = Path(read(RECEIPTS / "LOCAL_RECONSTRUCTION_ROOT_01.json")["root"])
        restored_project = restored / "disastertrace-starter"
        successful_command(RECEIPTS, "local_base_restore_p11_01")
        # Different phase archives can be built independently; shared restoration is serialized.
        with (RECEIPTS / "local_restoration.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            command(phase + "_archive_restore_01", [CORE, str(HERE / "evidence_archive.py"), "restore",
                    "--bundle", str(cache), "--target", str(restored),
                    "--receipt", str(RECEIPTS / (phase.upper() + "_LOCAL_RESTORE_01.json"))])
            command(phase + "_restored_inventory_verify_01", [CPU,
                    str(restored_project / "artifacts/autonomy_10h_v1/seal_cohort_evidence_v3.py"),
                    "--phase", phase, "--verify"], cwd=restored_project, source_project=restored_project)
            for profile, location_path in zip(profiles, locations):
                location = read(location_path)
                audit = restored_project / location["finalization"] / "cpu_relocated"
                command(phase + "_restored_cpu_" + profile + "_01", [CPU, str(audit / "portable_review.py"),
                        "--execution", str(audit / "execution"), "--isolation-root", str(audit),
                        "--blocked-root", str(restored_project), "--blocked-root", str(PROJECT),
                        "--blocked-root", "/mnt/afs/260010168/models", "--review-spec", str(audit / "review_spec.json"),
                        "--output", str(audit / "INDEPENDENT_PUBLICATION_RECEIPT_01.json")],
                        source_project=restored_project)
        final.update(status="passed", acceptance_id=read(bundle / "COMPLETED_ACCEPTANCE.json")["acceptance_id"],
                     archive_manifest_id=manifest["manifest_id"], archive_path=archive.relative_to(REPO).as_posix())
    except BaseException as exc:
        final["error"] = type(exc).__name__ + ": " + str(exc)
        traceback.print_exc()
    finally:
        final["at"] = now()
        write(status_path, final)
        print(final, flush=True)
    return 0 if final["status"] == "passed" else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("p12", "p13", "p14"), required=True)
    args = parser.parse_args()
    raise SystemExit(finalize(args.phase))
