"""Collect and independently verify both full diagnostics before live acceptance."""

from pathlib import Path

from disastertrace.automated.common import fingerprint
from disastertrace.local_eval.storage import digest, now, read, write
from disastertrace.repeat_live import audit, launch, package, runtime

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]


def main():
    execution = HERE / "execution_live"
    plan, _, _ = package.verify(execution)
    diagnostics = {}
    for mode in ("correct", "invalid-control"):
        run = PROJECT / "work/p6-live-v1/diagnostics" / mode
        report = HERE / "diagnostics" / mode
        result = runtime.collect(execution, run, mode=mode)
        summary = audit.report(execution, run, report)
        verified = audit.verify_report(execution, run, report)
        diagnostics[mode] = {"audit": summary, "score_counts": read(report / "scores.json")["counts"],
                             "verified": verified["status"] == "passed"}
        print({"mode": mode, "collection": result, "audit_id": summary["audit_id"],
               "counts": diagnostics[mode]["score_counts"]}, flush=True)
    acceptance = {"status": "live_ready", "at": now(), "execution_id": plan["execution_id"],
                  "implementation_files": plan["implementation_files"], "new_tests_passed": True,
                  "tests_receipt_sha256": digest(HERE / "TEST_RESULTS.json"),
                  "model_generations": 0, "diagnostics": diagnostics}
    acceptance["acceptance_id"] = fingerprint(acceptance)
    launch.validate_acceptance(execution, acceptance)
    write(HERE / "LIVE_READY_ACCEPTANCE.json", acceptance)
    print({"status": "live_ready", "acceptance_id": acceptance["acceptance_id"]}, flush=True)


if __name__ == "__main__":
    main()
