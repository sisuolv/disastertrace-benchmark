"""Recover interrupted publication on CPU from persistent accepted archive bytes."""

import fcntl
from pathlib import Path
import shutil
import tempfile
import traceback

import finalize_phase_evidence as helper

REPO, PROJECT, ROOT = helper.REPO, helper.PROJECT, helper.AUTONOMY
HERE, RECEIPTS = helper.HERE, helper.RECEIPTS
read, write, digest = helper.read, helper.write, helper.digest


def main():
    source = digest(__file__)
    write(RECEIPTS / "CPU_PUBLICATION_RECOVERY_02_CLAIM.json", {
        "at": helper.now(), "script_sha256": source, "model_calls": 0, "gpu_submissions": 0,
        "prior_interruption_sha256": digest(ROOT / "CPU_PUBLICATION_INTERRUPTION_02.json")})
    final = {"status": "failed", "model_calls": 0, "gpu_submissions": 0, "script_sha256": source}
    try:
        bundle = PROJECT / "artifacts/p14_qwen_prompt_role_v1"
        helper.successful_command(RECEIPTS, "p14_findings_01")
        if (bundle / "COMPLETED_ACCEPTANCE.json").exists() or (HERE / "evidence_p14").exists():
            raise ValueError("P14 completion path is already claimed; inspect rather than duplicate")
        argv = [helper.CORE, str(ROOT / "seal_cohort_evidence_v3.py"), "--phase", "p14"]
        helper.command("p14_acceptance_seal_02", argv)
        helper.command("p14_acceptance_verify_02", argv + ["--verify"])
        helper.command("p14_archive_build_02", [helper.CORE, str(HERE / "evidence_archive.py"), "build",
                       "--repo", str(REPO), "--acceptance", str((bundle / "COMPLETED_ACCEPTANCE.json").relative_to(REPO)),
                       "--output", str(HERE / "evidence_p14")])
        restored = Path(tempfile.mkdtemp(prefix="disastertrace-restored-publication-02-"))
        cache = Path(tempfile.mkdtemp(prefix="disastertrace-archive-cache-02-"))
        write(RECEIPTS / "LOCAL_RECONSTRUCTION_ROOT_02.json", {"at": helper.now(), "root": str(restored)})
        write(RECEIPTS / "LOCAL_ARCHIVE_CACHE_ROOT_02.json", {"at": helper.now(), "root": str(cache)})
        manifests = {}
        with (RECEIPTS / "local_restoration.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            for phase in ("p6_p10", "p11", "p12", "p13", "p14"):
                source_dir, target_dir = HERE / ("evidence_" + phase), cache / ("evidence_" + phase)
                target_dir.mkdir()
                manifest = read(source_dir / "manifest.json")
                mirrored = {}
                for name in ("BUILD_CLAIM.json", "manifest.json", *manifest["parts"]):
                    expected = digest(source_dir / name)
                    shutil.copyfile(source_dir / name, target_dir / name)
                    if digest(target_dir / name) != expected:
                        raise ValueError("Recovered archive mirror differs")
                    mirrored[name] = expected
                write(RECEIPTS / (phase + "_archive_mirror_02.json"), {"at": helper.now(), "files_sha256": mirrored})
                helper.command(phase + "_recovery_restore_02", [helper.CORE, str(HERE / "evidence_archive.py"), "restore",
                               "--bundle", str(target_dir), "--target", str(restored), "--receipt",
                               str(RECEIPTS / (phase + "_RESTORE_RECEIPT_02.json"))])
                manifests[phase] = {"manifest_id": manifest["manifest_id"], "acceptances": manifest["acceptances"]}
        restored_project = restored / "disastertrace-starter"
        for phase in ("p11", "p12", "p13", "p14"):
            helper.command(phase + "_recovery_inventory_02", [helper.CPU,
                           str(restored_project / "artifacts/autonomy_10h_v1" /
                               ("seal_cohort_evidence_v2.py" if phase == "p11" else "seal_cohort_evidence_v3.py")),
                           "--phase", phase, "--verify"], cwd=restored_project, source_project=restored_project)
        cases = {}
        reviews = read(ROOT / "reviews_continuation_v2/FINAL_STATUS.json")
        if reviews["status"] != "passed" or len(reviews["completed"]) != 6:
            raise ValueError("Six original verified model cases are required")
        for key, location in sorted(reviews["completed"].items()):
            audit = restored_project / location["finalization"] / "cpu_relocated"
            receipt = RECEIPTS / ("INDEPENDENT_CPU_" + key + "_02.json")
            label = key + "_recovery_cpu_02"
            helper.command(label, [helper.CPU, str(audit / "portable_review.py"), "--execution", str(audit / "execution"),
                           "--isolation-root", str(audit), "--blocked-root", str(restored_project),
                           "--blocked-root", str(PROJECT), "--blocked-root", "/mnt/afs/260010168/models",
                           "--review-spec", str(audit / "review_spec.json"), "--output", str(receipt)],
                           source_project=restored_project)
            result = read(receipt)
            if result["status"] != "passed" or result["cli_exits"] != [0, 0, 0]:
                raise ValueError("Fresh restored CPU case did not pass")
            cases[key] = {"execution_id": location["execution_id"], "report_id": location["report_id"],
                          "receipt": receipt.relative_to(REPO).as_posix(), "sha256": digest(receipt), "command": label}
        final.update(status="passed", cases=cases, manifests=manifests, restored_root=str(restored), cache_root=str(cache))
    except BaseException as exc:
        final["error"] = type(exc).__name__ + ": " + str(exc)
        traceback.print_exc()
    finally:
        final["at"] = helper.now()
        write(RECEIPTS / "CPU_PUBLICATION_RECOVERY_02_STATUS.json", final)
        print(final, flush=True)
    return 0 if final["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
