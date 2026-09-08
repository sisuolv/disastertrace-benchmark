"""Recheck the inherited P5 acceptance and independently reconstruct diagnostics."""

from pathlib import Path

from disastertrace.local_eval.storage import digest, now, read, write
from disastertrace.stress_eval import audit, execution

HERE = Path(__file__).resolve().parent
FACTORS = ("revision_chain", "irrelevant_scope", "late_stale_replay")


def main():
    accepted = read(HERE / "OFFLINE_ACCEPTANCE.json")
    if not accepted["offline_complete"] or accepted["model_calls"] != 0:
        raise ValueError("complete offline-only acceptance required")
    for name, expected in accepted["evidence_sha256"].items():
        if digest(HERE / name) != expected:
            raise ValueError("inherited acceptance evidence changed: " + name)
    results = {}
    for factor in FACTORS:
        unit = HERE / "units" / factor
        plan, episodes, slots = execution.verify(unit / "execution_offline")
        old = accepted["units"][factor]
        if plan["execution_id"] != old["execution_id"] or len(slots) != 540:
            raise ValueError("accepted factor identity mismatch")
        result = audit.report(
            unit / "execution_offline", unit / "diagnostic", unit / "diagnostic_report",
            verify=True,
        )
        if result["audit_id"] != old["audit_id"] or result["local_model_calls"] != 0:
            raise ValueError("diagnostic audit changed")
        results[factor] = {
            "execution_id": plan["execution_id"], "audit_id": result["audit_id"],
            "episodes": len(episodes), "slots": len(slots), "status": "passed",
        }
        print({"factor": factor, "status": "passed"}, flush=True)
    record = {
        "status": "passed", "verified_at": now(), "model_calls": 0,
        "offline_acceptance_sha256": digest(HERE / "OFFLINE_ACCEPTANCE.json"),
        "evidence_files_verified": len(accepted["evidence_sha256"]), "units": results,
    }
    write(HERE / "inherited_acceptance_verified.json", record)
    print(record)


if __name__ == "__main__":
    main()
