"""Review preserved P1 outcomes and published score denominators without new calls."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from disastertrace.automated.common import file_hash, read_jsonl, strict_json, write_json
from disastertrace.automated.dynamic import parse_decision


def main() -> None:
    root = Path(__file__).resolve().parents[3]
    live = root / "work/p1-deepseek-development-v1"
    derived = root / "work/p1-deepseek-development-v1-interrupted-finalization"
    target = Path(__file__).with_name("result_review.json")
    if target.exists():
        raise ValueError("review exists")
    report = json.loads((derived / "report/report.json").read_text())
    methods = {}
    source_hashes = {}
    for method in ("snapshot", "structured_state", "answer_history"):
        collection = live / "runs" / method / "collection"
        requests = read_jsonl(collection / "requests.jsonl")
        outcomes = read_jsonl(collection / "outcomes.jsonl")
        responses = read_jsonl(collection / "responses.jsonl")
        assert len(outcomes) == len(responses)
        assert all(row["status"] in {"accepted", "invalid"} for row in outcomes)
        for name in (
            "plan.json",
            "requests.jsonl",
            "outcomes.jsonl",
            "responses.jsonl",
            "summary.json",
        ):
            path = collection / name
            source_hashes[str(path.relative_to(root))] = file_hash(path)
        v2_path = derived / "rescores" / method / "score_v2.json"
        v2 = json.loads(v2_path.read_text())
        source_hashes[str(v2_path.relative_to(root))] = file_hash(v2_path)
        checkpoints = {
            (row["episode_id"], row["checkpoint_id"]): row for row in v2["per_checkpoint"]
        }
        assert len(checkpoints) == 30
        invalids, citation_failures = [], []
        accepted = fields = values = grounded = known = known_grounded = actions = 0
        for outcome, response in zip(outcomes, responses):
            key = (outcome["episode_id"], outcome["checkpoint_id"])
            assert key == (response["episode_id"], response["checkpoint_id"])
            raw = response["raw_response"]
            scored = checkpoints[key]
            try:
                decision = parse_decision(raw)
            except (ValueError, TypeError, KeyError) as error:
                assert outcome["status"] == "invalid" and scored["status"] == "invalid"
                reason = outcome["metadata"]["finish_reason"]
                detail = None
                if reason == "length":
                    category = "length_empty" if raw == "" else "length_partial_json"
                    assert outcome["metadata"]["usage"]["completion_tokens"] == 4096
                    if raw:
                        try:
                            strict_json(raw)
                        except ValueError:
                            pass
                        else:
                            raise AssertionError("nonempty length failure should be truncated JSON")
                else:
                    category = "schema_violation"
                    parsed = strict_json(raw)
                    detail = {
                        "top_level_types": {
                            name: type(value).__name__ for name, value in parsed.items()
                        },
                        "action_keys": sorted(parsed["action"])
                        if isinstance(parsed["action"], dict)
                        else None,
                        "meaning": (
                            "state and action values are interchanged"
                            if isinstance(parsed["state"], str)
                            else "action is an object where a declared action string is required"
                        ),
                    }
                invalids.append(
                    {
                        "episode_id": key[0],
                        "checkpoint_id": key[1],
                        "category": category,
                        "finish_reason": reason,
                        "raw_content_characters": len(raw),
                        "completion_tokens": outcome["metadata"]["usage"]["completion_tokens"],
                        "reasoning_tokens": outcome["metadata"]["usage"][
                            "completion_tokens_details"
                        ]["reasoning_tokens"],
                        "parser_error_type": type(error).__name__,
                        "schema_detail": detail,
                    }
                )
                continue
            assert outcome["status"] == "accepted" and scored["status"] == "ok"
            accepted += 1
            actions += scored["action_correct"]
            for field, slot in scored["slots"].items():
                fields += 1
                values += slot["value_correct"]
                grounded += slot["grounded_correct"]
                if decision["state"][field]["status"] == "known":
                    known += 1
                    known_grounded += slot["grounded_correct"]
                if not slot["grounded_correct"]:
                    citation_failures.append(
                        {"episode_id": key[0], "checkpoint_id": key[1], "field": field, **slot}
                    )
        primary = v2["metrics"]
        assert fields == 5 * accepted and values == fields
        for metric, numerator, denominator in (
            ("schema_success", accepted, 30),
            ("state_accuracy", values, 150),
            ("grounded_state", grounded, 150),
            ("known_value_accuracy", known, 96),
            ("known_grounded_accuracy", known_grounded, 96),
            ("action_accuracy", actions, 30),
        ):
            assert primary[metric]["numerator"] == numerator
            assert primary[metric]["denominator"] == denominator
            assert report["methods"][method]["v2"]["metrics"][metric] == primary[metric]
        methods[method] = {
            "original_attempts": len(requests),
            "original_responses": len(responses),
            "accepted": accepted,
            "invalid": len(invalids),
            "missing": 30 - len(responses),
            "invalid_categories": dict(Counter(row["category"] for row in invalids)),
            "invalid_details": invalids,
            "primary_metrics": primary,
            "valid_response_only_diagnostics": {
                "value_correct": values,
                "field_opportunities": fields,
                "grounded_correct": grounded,
                "known_fields": known,
                "known_grounded_correct": known_grounded,
                "action_correct": actions,
                "checkpoint_opportunities": accepted,
                "interpretation": "Selection-conditioned diagnostic; never replaces all-planned primary denominators.",
            },
            "citation_failures_among_valid_answers": citation_failures,
        }
    history = derived / "runs/answer_history/collection"
    provenance = json.loads((history / "interruption_finalization.json").read_text())
    old = live / "runs/answer_history/collection"
    for name in ("plan.json", "requests.jsonl", "responses.jsonl"):
        assert (old / name).read_bytes() == (history / name).read_bytes()
    old_outcomes = read_jsonl(old / "outcomes.jsonl")
    new_outcomes = read_jsonl(history / "outcomes.jsonl")
    assert new_outcomes[:-1] == old_outcomes and len(new_outcomes) == 19
    assert new_outcomes[-1] == provenance["administrative_outcome"]
    assert new_outcomes[-1]["error"]["code"] == "offline_finalized_interrupted_attempt"
    assert provenance["provider_returned_error"] is False
    ledger = json.loads((live / "budget_ledger.json").read_text())
    assert file_hash(live / "budget_ledger.json") == provenance["original_budget_ledger_sha256"]
    assert ledger["active_attempt"] == 79 and ledger["pending_reservation_usd"] == 0.46678016
    preserved = json.loads((derived / "runs/answer_history/finalization.json").read_text())
    assert all(
        file_hash(live / name) == expected
        for name, expected in preserved["source_files_sha256"].items()
    )
    dorian = [
        row
        for row in json.loads((derived / "rescores/answer_history/score_v2.json").read_text())[
            "per_checkpoint"
        ]
        if row["episode_id"].startswith("al052019:")
    ]
    assert len(dorian) == 10 and all(row["status"] == "missing" for row in dorian)
    assert not any(
        row["episode_id"].startswith("al052019:") for row in read_jsonl(old / "requests.jsonl")
    )
    result = {
        "schema_version": "p1_independent_saved_result_review_v1",
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "new_provider_calls": 0,
        "review_script_sha256": file_hash(Path(__file__)),
        "verified": True,
        "original_provider_attempts": sum(row["original_attempts"] for row in methods.values()),
        "original_saved_responses": sum(row["original_responses"] for row in methods.values()),
        "planned_checkpoints": 90,
        "source_files_sha256": source_hashes,
        "methods": methods,
        "interruption_disposition": {
            "locally_generated_administrative_error": True,
            "provider_returned_error": False,
            "fabricated_model_responses": 0,
            "new_provider_calls": 0,
            "pending_reservation_preserved_usd": ledger["pending_reservation_usd"],
            "original_files_verified_unchanged": len(preserved["source_files_sha256"]),
            "history_unresolved_attempts": 1,
            "history_never_attempted": 11,
        },
        "interpretation_findings": [
            "Snapshot has 14 length failures: 12 empty contents and 2 truncated JSON contents; all report 4096 completion tokens. Its 2 other invalid answers violate the output schema.",
            "Answer-history has 4 invalid saved answers, all Florence base c0-c3, all empty content with length finish and 4096 reasoning/completion tokens.",
            "Every schema-valid answer has correct field values and actions. One snapshot wind citation is evaluator_unverifiable under frozen v2; this is not proof of a false weather claim.",
            "Answer-history Dorian has zero provider attempts: all ten missing slots reflect interruption, so its zero score is not evidence of model failure on Dorian.",
            "Primary metrics include all 90 planned checkpoints and 450 field opportunities. Valid-only diagnostics exclude failures and must not replace primary metrics.",
            "The three-method comparison is incomplete and confounded by fixed order and output cap; it supports no universal method ranking or causal memory claim.",
        ],
    }
    write_json(target, result)
    print(
        json.dumps(
            {
                "verified": True,
                "provider_attempts": 79,
                "saved_responses": 78,
                "planned_checkpoints": 90,
                "output": str(target),
            }
        )
    )


if __name__ == "__main__":
    main()
