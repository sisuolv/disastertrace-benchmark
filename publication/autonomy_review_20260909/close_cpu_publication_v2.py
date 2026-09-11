"""Seal and restore the final supplement after persistent CPU recovery completes."""

import fcntl
import os
from pathlib import Path
import shutil
import traceback

import finalize_phase_evidence as helper

REPO, PROJECT, ROOT = helper.REPO, helper.PROJECT, helper.AUTONOMY
HERE, RECEIPTS = helper.HERE, helper.RECEIPTS
read, write, digest = helper.read, helper.write, helper.digest


def main():
    write(RECEIPTS / "CLOSE_GLOBAL_02_CLAIM.json", {
        "at": helper.now(), "pid": os.getpid(), "script_sha256": digest(__file__),
        "model_calls": 0, "gpu_submissions": 0, "collection_window_extended": False})
    final = {"status": "failed", "model_calls": 0, "gpu_submissions": 0, "collection_window_extended": False}
    try:
        recovery = read(RECEIPTS / "CPU_PUBLICATION_RECOVERY_03_STATUS.json")
        if recovery["status"] != "passed" or len(recovery["cases"]) != 6:
            raise ValueError("persistent six-case CPU recovery must pass first")
        if (ROOT / "COMPLETED_SUPPLEMENT.json").exists() or (HERE / "evidence_autonomy_supplement").exists():
            raise FileExistsError("supplement is already claimed; inspect instead of relaunching")
        for label in ("tables_export_01", "tables_verify_01", "dispatch_deadlines_build_03",
                      "dispatch_deadlines_verify_03", "final_gpu_accounting_build_01", "final_gpu_accounting_verify_01"):
            helper.successful_command(ROOT / "validation", label)
        helper.command("copy_reconstruction_receipts_02", [helper.CORE, str(HERE / "copy_reconstruction_receipts_v2.py")], cwd=REPO)
        findings = ROOT / "AUTONOMY_FINDINGS.md"
        if "WORKING DRAFT" in findings.read_text():
            raise ValueError("final findings remain a draft")
        write(RECEIPTS / "READY_TO_SEAL_02.json", {
            "at": helper.now(), "findings_sha256": digest(findings),
            "recovery_status_sha256": digest(RECEIPTS / "CPU_PUBLICATION_RECOVERY_03_STATUS.json"),
            "reconstruction_copy_sha256": digest(ROOT / "publication_reconstruction_02/COPY_RECEIPT.json"),
            "dispatch_check_id": read(ROOT / "dispatch_deadlines_v3.json")["analysis_id"],
            "gpu_accounting_id": read(ROOT / "gpu_snapshots_01/final_accounting_01.json")["analysis_id"]})
        argv = [helper.CORE, str(ROOT / "seal_autonomy_supplement.py")]
        helper.command("global_supplement_seal_02", argv)
        helper.command("global_supplement_verify_02", argv + ["--verify"])
        archive = HERE / "evidence_autonomy_supplement"
        helper.command("global_supplement_archive_build_02", [helper.CORE, str(HERE / "evidence_archive.py"),
                       "build", "--repo", str(REPO), "--acceptance",
                       "disastertrace-starter/artifacts/autonomy_10h_v1/COMPLETED_SUPPLEMENT.json", "--output", str(archive)])
        manifest = read(archive / "manifest.json")
        cache = Path(read(RECEIPTS / "LOCAL_ARCHIVE_CACHE_ROOT_02.json")["root"]) / archive.name
        cache.mkdir(exist_ok=False)
        mirrored = {}
        for name in ("BUILD_CLAIM.json", "manifest.json", *manifest["parts"]):
            source, target = archive / name, cache / name
            expected = digest(source)
            shutil.copyfile(source, target)
            if digest(target) != expected or digest(source) != expected:
                raise ValueError("supplement archive mirror differs")
            mirrored[name] = expected
        write(RECEIPTS / "LOCAL_MIRROR_EVIDENCE_SUPPLEMENT_02.json", {
            "at": helper.now(), "source": str(archive), "destination": str(cache), "files_sha256": mirrored})
        restored = Path(read(RECEIPTS / "LOCAL_RECONSTRUCTION_ROOT_02.json")["root"])
        restored_project = restored / "disastertrace-starter"
        with (RECEIPTS / "local_restoration.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            helper.command("global_supplement_restore_02", [helper.CORE, str(HERE / "evidence_archive.py"),
                           "restore", "--bundle", str(cache), "--target", str(restored), "--receipt",
                           str(RECEIPTS / "SUPPLEMENT_LOCAL_RESTORE_02.json")])
            for label, script in (("global_supplement_restored_verify_02", "seal_autonomy_supplement.py"),
                                  ("p11_addendum_restored_verify_02", "seal_p11_review_addendum.py")):
                helper.command(label, [helper.CPU, str(restored_project / "artifacts/autonomy_10h_v1" / script), "--verify"],
                               cwd=restored_project, source_project=restored_project)
        final.update(status="passed", acceptance_id=read(ROOT / "COMPLETED_SUPPLEMENT.json")["acceptance_id"],
                     archive_manifest_id=manifest["manifest_id"], archive_path=archive.relative_to(REPO).as_posix())
    except BaseException as exc:
        final["error"] = type(exc).__name__ + ": " + str(exc)
        traceback.print_exc()
    finally:
        final["at"] = helper.now()
        write(RECEIPTS / "CLOSE_GLOBAL_02_STATUS.json", final)
        print(final, flush=True)
    return 0 if final["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
