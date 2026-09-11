"""Close a completed feasibility task without changing historical run scopes."""

from datetime import datetime, timezone
import json

from common import ROOT, dump
from model_adapter import sha_file


def main():
    scope = json.loads((ROOT / "SCOPE.json").read_text())
    verify = json.loads((ROOT / "verification/final_01/VERIFICATION.json").read_text())
    resources = json.loads((ROOT / "RESOURCE_ACCOUNTING.json").read_text())
    background = json.loads((ROOT / "checkpoints/BACKGROUND_PROCESS_CHECK.json").read_text())
    if verify["status"] != "passed" or resources["active_account_jobs"] or resources["terminal_jobs"] != 28:
        raise ValueError("task is not ready for closure")
    if background["matching_local_source_or_model_workers"] or not background["all_source_batches_completed"]:
        raise ValueError("local source/model work is not terminal")
    docs = ["README.md", "FINAL_PLAN_CN.md", "RESULTS_CN.md", "FINAL_DATASETS.json",
            "REVIEW_FOR_CHATGPT_PRO_CN.md", "REPRODUCIBILITY.md", "RESOURCE_ACCOUNTING.json",
            "reports/NOVELTY_AUDIT_CN.md", "analysis/FINAL_RESULTS_02.json", "verification/final_01/VERIFICATION.json"]
    bound = {name: sha_file(ROOT / name) for name in docs}
    now = datetime.now(timezone.utc)
    started = datetime.fromisoformat(scope["created_at"])
    result = {"status": "feasibility_objective_completed", "started_utc": started.isoformat(),
        "completed_utc": now.isoformat(), "authorized_deadline_utc": scope["deadline_utc"],
        "elapsed_wall_seconds": (now - started).total_seconds(),
        "within_authorized_window": now <= datetime.fromisoformat(scope["deadline_utc"]),
        "outcomes": ["Core source selection fixed with provenance and limits", "Literature collision audit and narrowed contribution documented",
            "Executable support/acquisition/state/coverage development diagnostics completed", "Seven GPU waves independently replayed",
            "All28GPUjobs successfully terminal; no account GPU jobs active", "Final Chinese plan and external review document written"],
        "not_yet_claimed": ["Complete scalable benchmark release", "Final heldout model evaluation", "Guaranteed global novelty",
            "General weather prediction skill", "Globally representative hazard coverage", "Portable public release"],
        "original_scope_reopened": False, "new_git_commit_or_push": False, "deliverable_sha256": bound}
    if not result["within_authorized_window"]:
        raise ValueError("cannot report within-window completion")
    dump(ROOT / "CLOSURE.json", result)
    ledger_path = ROOT / "TASK_LEDGER.json"
    ledger = json.loads(ledger_path.read_text())
    dump(ROOT / "checkpoints/TASK_LEDGER_BEFORE_CLOSURE.json", ledger)
    for task in ledger["tasks"]:
        task["status"] = "complete"
    ledger["completed_utc"] = now.isoformat()
    ledger["latest_checkpoint"] = "Feasibility objective completed; final plan and source selection recorded;3599calls;28H100jobs terminal;7raw replays agree; inherited12baseline files unchanged. Full benchmark development remains in FINAL_PLAN_CN.md."
    ledger_path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "elapsed_hours": result["elapsed_wall_seconds"] / 3600}))


if __name__ == "__main__":
    main()
