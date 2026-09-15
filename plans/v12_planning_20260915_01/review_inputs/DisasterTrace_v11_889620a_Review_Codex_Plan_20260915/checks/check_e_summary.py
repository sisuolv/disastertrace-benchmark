"""Reproduce a source-expression bug, not a full-calendar rerun.

The expression below is copied from fullweek.py::audit at the reviewed commit.
The four statuses are those emitted by evidence.exists_report_support and
preserved by policies.py::run_session -> report.frames[].e_statuses.
No stored result is edited by this diagnostic.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
statuses = ["supported", "refuted", "undetermined", "inconsistent"]
values = [{"e_status": value} for value in statuses]
published_expression = sum(r["e_status"] in {"entailed", "refuted"} for r in values)
expected = sum(r["e_status"] in {"supported", "refuted"} for r in values)
assert published_expression == 1 and expected == 2
assert "entailed" not in statuses
result = {
    "reviewed_commit": "889620a4fc4ee6ad70757dd3e832a40c7509126a",
    "passed": True,
    "scope": "Direct expression-level reproduction with synthetic status rows; not a production journal or full-calendar replay",
    "source": "plans/v11_execution_20260915_01/fullweek.py::audit",
    "source_git_blob_sha": "c2f9c3877f5e3c1236a4c595ac87b91544efbe52",
    "producer": "monitoring_v1/policies.py -> monitoring_v1/evidence.py::exists_report_support",
    "fixture_statuses": statuses,
    "published_e_determined": published_expression,
    "expected_e_determined": expected,
    "consequence": "Every actual supported row is omitted by this E-summary expression. Actual affected counts require a scan of the captured roster.",
    "F_probabilities_or_Brier_modified": False,
    "real_calendar_impact_recomputed": False,
    "model_calls": 0,
}
(HERE / "E_SUMMARY_REPRODUCTION.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(result, ensure_ascii=False, indent=2))
