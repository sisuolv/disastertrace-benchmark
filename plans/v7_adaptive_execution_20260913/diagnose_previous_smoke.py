"""Re-audit all existing raw requests/responses; make no new model calls."""

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from disastertrace.monitoring_fixed_v1.contracts import EvidenceBundle, fingerprint
from disastertrace.monitoring_fixed_v1.heads import parse_response
from disastertrace.monitoring_fixed_v1.support_bridge import native_slot_support

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "v7_followup_execution_20260913"


def main(out):
    out.mkdir(exist_ok=False)
    source = PRIOR / "reports/model_smoke_02/RECORDS.json"
    capture = PRIOR / "gpu/heads_smoke_01/worker-0"
    rows = json.loads(source.read_text())
    records, bound_files = [], []
    for row in rows:
        cid = row["call_id"]
        request_path = capture / (cid + "-request.json")
        response_path = capture / (cid + "-response.json")
        request, response = (json.loads(p.read_text()) for p in (request_path, response_path))
        view = json.loads(request["messages"][1]["content"])
        bundle = EvidenceBundle.freeze(view)
        assert bundle.bundle_hash == request["bundle_hash"] == response["bundle_hash"]
        assert request["messages_sha256"] == fingerprint(request["messages"])
        assert hashlib.sha256(response["raw"].encode()).hexdigest() == response["raw_sha256"]
        assert response["raw"] == row["raw"]
        parsed = parse_response(response["raw"], bundle, row["head"])
        support = native_slot_support(bundle)
        if row["head"] != "f_only":
            assert support["status"] == row["expected_e"]
        else:
            assert row["expected_e"] is None
        assert parsed.e_status == row["e_status"]
        slot_states = Counter(s["status"] for s in support["slots"])
        missing = Counter(a["missingness"] for a in view["assets"])
        upper_censored = sum(
            s["support"] is not None and s["support"]["upper"] == "+inf" and s["provenance"] != []
            for s in support["slots"]
        )
        records.append(
            {
                **row,
                "registered_slots": len(support["slots"]),
                "disclosed_slots": sum(bool(s["provenance"]) for s in support["slots"]),
                "slot_status_counts": dict(slot_states),
                "source_missingness": dict(missing),
                "upper_censored_disclosed_slots": upper_censored,
                "input_tokens": request["input_tokens"],
                "input_bytes": len(request["messages"][1]["content"].encode()),
                "bundle_sha256": bundle.bundle_hash,
                "program_support_reparsed_from_native": support["status"],
                "all_unknown_control_correct": support["status"] == "undetermined"
                if row["head"] != "f_only"
                else None,
            }
        )
        for p in (request_path, response_path):
            bound_files.append(
                {
                    "path": str(p.relative_to(HERE.parent.parent)),
                    "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                }
            )
    groups = defaultdict(list)
    for row in records:
        groups[row["head"], row["condition"]].append(row)
    strata = []
    for (head, condition), values in sorted(groups.items()):
        strata.append(
            {
                "head": head,
                "condition": condition,
                "n": len(values),
                "truth_counts": dict(
                    Counter(v["program_support_reparsed_from_native"] for v in values)
                ),
                "predicted_E_counts": dict(Counter(v["e_status"] for v in values)),
                "E_correct": sum(v["e_correct"] is True for v in values)
                if head != "f_only"
                else None,
                "all_unknown_E_correct": sum(
                    v["all_unknown_control_correct"] is True for v in values
                )
                if head != "f_only"
                else None,
                "F_changed": sum(v["candidate_changed_baseline"] is True for v in values)
                if head != "e_only"
                else None,
                "input_tokens_min": min(v["input_tokens"] for v in values),
                "input_tokens_max": max(v["input_tokens"] for v in values),
            }
        )
    report = {
        "schema": "disastertrace.raw_smoke_failure_audit.v1",
        "audited_calls": len(records),
        "bound_native_inputs": len({r["bundle_sha256"] for r in records}),
        "new_model_calls": 0,
        "source_record_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "strata": strata,
        "verified": [
            "request/response/bundle hashes match",
            "all native METAR intervals reparse",
            "E-only matches the constant-unknown control on every call",
            "all F-bearing probabilities exactly retain their own common baseline",
        ],
        "interpretation": "Observed input-understanding failure and conservative F behavior; causation by prompt, context length or training is not identified by these captures.",
        "next_representation_test": "Fresh inputs: full lawful bundle versus task-focused native rows with the same report values, raw text and provenance. No support answers or hidden annotations in either condition.",
        "limits": [
            "12 exposed opportunities are not an independent process study",
            "no forced F changes or positive-gain admission rule",
        ],
    }
    assert all(r["e_status"] == "undetermined" for r in records if r["head"] == "e_only")
    assert not any(r["candidate_changed_baseline"] for r in records)
    for name, data in (
        ("REPORT.json", report),
        ("RECORDS.json", records),
        ("SOURCE_BINDINGS.json", bound_files),
    ):
        (out / name).write_text(json.dumps(data, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args().output)
