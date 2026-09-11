"""Complete CPU reconstruction with wrapper-local output and immediate durable copy."""

from pathlib import Path
import traceback

import finalize_phase_evidence as helper

REPO, PROJECT, ROOT = helper.REPO, helper.PROJECT, helper.AUTONOMY
HERE, RECEIPTS = helper.HERE, helper.RECEIPTS
read, write, digest = helper.read, helper.write, helper.digest


def main():
    source = digest(__file__)
    previous_path = RECEIPTS / "CPU_PUBLICATION_RECOVERY_02_STATUS.json"
    write(RECEIPTS / "CPU_PUBLICATION_RECOVERY_03_CLAIM.json", {
        "at": helper.now(), "script_sha256": source, "prior_status_sha256": digest(previous_path),
        "model_calls": 0, "gpu_submissions": 0,
        "reason": "Unchanged CPU wrapper requires receipt within isolation; copy verified output to AFS immediately."})
    final = {"status": "failed", "model_calls": 0, "gpu_submissions": 0, "script_sha256": source}
    try:
        previous = read(previous_path)
        if previous["status"] != "failed" or previous["script_sha256"] != digest(HERE / "recover_cpu_publication_v2.py"):
            raise ValueError("expected interrupted CPU recovery provenance differs")
        restored = Path(read(RECEIPTS / "LOCAL_RECONSTRUCTION_ROOT_02.json")["root"])
        restored_project = restored / "disastertrace-starter"
        manifests = {}
        for phase in ("p6_p10", "p11", "p12", "p13", "p14"):
            helper.successful_command(RECEIPTS, phase + "_recovery_restore_02")
            if phase != "p6_p10":
                helper.successful_command(RECEIPTS, phase + "_recovery_inventory_02")
            manifest = read(HERE / ("evidence_" + phase) / "manifest.json")
            receipt = read(RECEIPTS / (phase + "_RESTORE_RECEIPT_02.json"))
            if receipt["status"] != "passed" or receipt["manifest_id"] != manifest["manifest_id"]:
                raise ValueError("prior successful restoration differs")
            manifests[phase] = {"manifest_id": manifest["manifest_id"], "acceptances": manifest["acceptances"]}
        reviews = read(ROOT / "reviews_continuation_v2/FINAL_STATUS.json")
        if reviews["status"] != "passed" or len(reviews["completed"]) != 6:
            raise ValueError("six original audited cases are required")
        cases = {}
        for key, location in sorted(reviews["completed"].items()):
            audit = restored_project / location["finalization"] / "cpu_relocated"
            local = audit / "INDEPENDENT_PUBLICATION_RECEIPT_03.json"
            durable = RECEIPTS / ("INDEPENDENT_CPU_" + key + "_03.json")
            if local.exists() or durable.exists():
                raise FileExistsError("CPU reconstruction output is already claimed: " + key)
            label = key + "_recovery_cpu_03"
            helper.command(label, [helper.CPU, str(audit / "portable_review.py"), "--execution", str(audit / "execution"),
                           "--isolation-root", str(audit), "--blocked-root", str(restored_project),
                           "--blocked-root", str(PROJECT), "--blocked-root", "/mnt/afs/260010168/models",
                           "--review-spec", str(audit / "review_spec.json"), "--output", str(local)],
                           source_project=restored_project)
            result = read(local)
            if result["status"] != "passed" or result["cli_exits"] != [0, 0, 0]:
                raise ValueError("recovered isolated CPU report did not pass")
            expected = digest(local)
            with durable.open("xb") as stream:
                stream.write(local.read_bytes())
            if digest(durable) != expected or digest(local) != expected:
                raise ValueError("durable CPU receipt differs from local output")
            cases[key] = {"execution_id": location["execution_id"], "report_id": location["report_id"],
                          "receipt": durable.relative_to(REPO).as_posix(), "sha256": expected,
                          "local_receipt": str(local), "command": label}
        final.update(status="passed", cases=cases, manifests=manifests, restored_root=str(restored),
                     cache_root=read(RECEIPTS / "LOCAL_ARCHIVE_CACHE_ROOT_02.json")["root"],
                     prior_status_sha256=digest(previous_path), archive_restoration_reused_without_modification=True)
    except BaseException as exc:
        final["error"] = type(exc).__name__ + ": " + str(exc)
        traceback.print_exc()
    finally:
        final["at"] = helper.now()
        write(RECEIPTS / "CPU_PUBLICATION_RECOVERY_03_STATUS.json", final)
        print(final, flush=True)
    return 0 if final["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
