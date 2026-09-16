"""Reconstruct six frozen prefixes and continue the original policy without new data."""

import argparse
import datetime as dt
import json
import signal
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from disastertrace.monitoring_fixed_v1.admission import AdmissionEngine
from disastertrace.monitoring_fixed_v1.outcomes import ComparisonContract
from disastertrace.monitoring_v1 import formal_session
from disastertrace.monitoring_v1.session_checkpoint import SessionCoordinator
from disastertrace.monitoring_v1.spool_backend import digest, publish, read
from disastertrace.monitoring_v1.targets import canonical_hash


RUN = Path(__file__).resolve().parent
REPO = RUN.parents[1]
OLD = REPO / "plans/v11_execution_20260915_01/fullweek_02"


def timeout_handler(signum, frame):
    raise TimeoutError("Registered parent operation exceeded45minutes")


def materialize(row):
    started = time.monotonic()
    folder = RUN / "parents" / row["case"]
    folder.mkdir(exist_ok=False)
    publish(folder / "CLAIM.json", {"at": dt.datetime.now(dt.timezone.utc).isoformat(),
                                   "max_reconstruction": 1, "max_noop": 1})
    result = {"case": row["case"], "opportunity_id": row["opportunity_id"],
              "parent_policy": row["parent_policy"], "reconstruction_attempted": False,
              "noop_attempted": False, "model_calls": 0, "source_HTTP_calls": 0}
    try:
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(2700)
        if not str(Path(formal_session.__file__).resolve()).startswith(str(OLD / "source")):
            raise ValueError("Parent reconstruction must use the original frozen implementation")
        parent = REPO / row["directory"]
        contract, stop, original = (read(parent / name) for name in
                                   ("CONTRACT.json", "STOP.json", "FORMAL_REPORT.json"))
        if digest(parent / "CONTRACT.json") != row["contract_sha256"] or digest(parent / "STOP.json") != row["stop_sha256"]:
            raise ValueError("Registered parent contract/STOP changed")
        payload = contract["comparison"]["payload"]
        comparison = ComparisonContract(payload["invariants"], payload["allowed_interventions"])
        engine = AdmissionEngine.from_journal(parent / "admission.jsonl")
        formal_session._verify_run_reference(parent / "admission.jsonl", parent, engine, comparison)
        if stop["reason"] != "completed" or not stop["done"]:
            raise ValueError("Selected parent did not complete its original scope")
        result.update(parent_day_terminal_and_verified=True, original_journal_verification_replays=1)
        del engine
        case = parent.parent
        data, bank, configs = (read(case / name) for name in ("DATA.json", "BANK.json", "CONFIGS.json"))
        config = configs[row["parent_policy"]]
        cutoffs = sorted({r["cutoff"] for r in data["opportunities"]})
        next_tick = cutoffs.index(row["cutoff"])
        result["reconstruction_attempted"] = True
        coordinator = SessionCoordinator(data, bank, config)
        for _ in range(next_tick):
            coordinator.step()
        checkpoint = coordinator.snapshot()
        if checkpoint["payload"]["next_tick"] != next_tick:
            raise ValueError("Original public decision cursor differs")
        if checkpoint["payload"]["schema"] != "disastertrace.session_quiescent.v1":
            raise ValueError("Selected parent has unresolved invocation; no synthetic completion allowed")
        coordinator.persist(folder / "PARENT_CHECKPOINT.json")
        publish(folder / "PREFIX_REPORT.json", coordinator.report)
        boundary = {"kind": "reconstructed_from_frozen_prefix",
                    "checkpoint_sha256": digest(folder / "PARENT_CHECKPOINT.json"),
                    "checkpoint_payload_sha256": checkpoint["sha256"],
                    "parent_contract_sha256": digest(parent / "CONTRACT.json"),
                    "original_report_sha256": digest(parent / "FORMAL_REPORT.json"),
                    "original_directory": str(parent), "next_tick": next_tick,
                    "checkpoint_clock": checkpoint["payload"]["clock"],
                    "next_decision_cutoff": cutoffs[next_tick],
                    "next_public_wakeup": cutoffs[next_tick] - config["wakeup_seconds"] * 1_000_000,
                    "source_file": str(Path(formal_session.__file__).resolve()),
                    "source_sha256": digest(Path(formal_session.__file__)),
                    "pending": False, "source_and_data_hashes": contract["files"],
                    "intervention_boundary": "after the next ordinary shared public wakeup; no source/prediction action before plan activation"}
        publish(folder / "PARENT_BINDING.json", boundary)
        result.update(reconstruction_completed=True, checkpoint_clock=boundary["checkpoint_clock"],
                      next_public_wakeup=boundary["next_public_wakeup"], next_tick=next_tick)
        result["noop_attempted"] = True
        signal.alarm(2700)
        restored = SessionCoordinator.restore(checkpoint, data, bank)
        replay = restored.finish()
        publish(folder / "NOOP_REPORT.json", replay)
        differences = [key for key in sorted(set(original) | set(replay)) if original.get(key) != replay.get(key)]
        equivalence = {"passed": not differences, "comparison": "entire original report, no ignored fields",
                       "different_fields": differences, "original_sha256": canonical_hash(original),
                       "continuation_sha256": canonical_hash(replay),
                       "source_HTTP_calls": 0, "model_calls": 0,
                       "new_independent_weather_processes": 0}
        publish(folder / "NOOP_EQUIVALENCE.json", equivalence)
        result.update(noop_equal=not differences, different_fields=differences,
                      status="qualified_original_parent" if not differences else "noop_mismatch",
                      passed=not differences)
    except Exception as exc:
        result.update(passed=False, status="parent_not_reconstructable", error=type(exc).__name__,
                      message=str(exc), traceback=traceback.format_exc())
    finally:
        signal.alarm(0)
    result["seconds"] = time.monotonic() - started
    publish(folder / "RESULT.json", result)
    return result


def main(workers):
    rows = read(RUN / "PARENT_CANDIDATES.json")["parents"]
    if len(rows) != 6:
        raise ValueError("Exactly the six registered metadata parents are required")
    audit = read(OLD / "RESULT.json")
    if not audit["passed"] or digest(OLD / "ROWS.json") != audit["rows_sha256"]:
        raise ValueError("Original completed fullweek audit identity changed")
    publish(RUN / "PARENT_MATERIALIZATION_CLAIM.json", {
        "at": dt.datetime.now(dt.timezone.utc).isoformat(), "parents": len(rows),
        "max_reconstructions": 6, "max_noop_continuations": 6, "workers": workers,
        "script_sha256": digest(Path(__file__)),
        "candidate_roster_sha256": digest(RUN / "PARENT_CANDIDATES.json")})
    (RUN / "parents").mkdir(exist_ok=False)
    inventory = {"parents": rows, "originally_captured_midday_checkpoints": 0,
                 "scope": "registered parent directories, followed by real frozen reconstruction"}
    publish(RUN / "PARENT_CHECKPOINT_INVENTORY.json", inventory)
    results = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(materialize, row) for row in rows]
        for future in as_completed(futures):
            row = future.result()
            results.append(row)
            print(json.dumps({k: v for k, v in row.items() if k != "traceback"}), flush=True)
    results.sort(key=lambda row: row["case"])
    summary = {"passed_all_parents": all(row["passed"] for row in results),
               "qualified_parents": sum(row["passed"] for row in results), "results": results,
               "reconstruction_attempts": sum(row["reconstruction_attempted"] for row in results),
               "original_policy_continuation_attempts": sum(row["noop_attempted"] for row in results),
               "treatment_branches": 0, "model_calls": 0, "source_HTTP_calls": 0,
               "global_dates": 1, "independent_process_count": None}
    publish(RUN / "PARENT_MATERIALIZATION_REPORT.json", summary)
    publish(RUN / "C2_NOOP_EQUIVALENCE.json", {"passed_all_parents": summary["passed_all_parents"],
        "qualified_parents": summary["qualified_parents"], "results": [
            {k: row.get(k) for k in ("case", "noop_attempted", "noop_equal", "different_fields", "status")}
            for row in results]})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=6)
    main(parser.parse_args().workers)
