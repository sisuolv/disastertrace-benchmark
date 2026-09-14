"""Frozen all-opportunity scoring for extraction-to-F and temperature-F pilots."""

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

from disastertrace.forecast_task.common import strict_json
from disastertrace.monitoring_v1.api_ledger import ApiLedger
from disastertrace.monitoring_v1.feature_scoring import claimed_support, field_agreement, forecast_controls
from disastertrace.monitoring_v1.feature_tasks import parse_features, parse_temperature, temperature_ensemble_probability
from disastertrace.monitoring_v1.native_feature_forecast import native_claims
from disastertrace.monitoring_v1.spool_backend import digest, publish, read


def observation(batch, model, task):
    cid = task["call_id"]
    policy = read(batch / "policy" / (cid+".json"))
    if model != "Qwen/Qwen3.8-27B":
        path = batch / "api/observations" / (model+"__"+cid+".json")
        result = read(path) if path.exists() else {"state": "MISSING_OBSERVATION"}
        if result["state"] != "RECEIVED":
            return result
        ledger = ApiLedger(batch / "api/ledger")
        attempt = ledger.attempt(model+"/"+cid)
        wire, response = read(attempt / "wire.json"), read(attempt / "response.json")
        request = read(attempt / "request.json")["payload"]
        if (digest(attempt / "response.raw") != wire["stored_body_sha256"]
                or strict_json((attempt / "response.raw").read_bytes()) != response
                or request["messages"] != policy["messages"] or request["model"] != model
                or response["choices"][0]["message"]["content"] != result["raw"]
                or read(attempt / "billing.json") != ledger.measured_bill(model+"/"+cid)):
            raise ValueError("API capture is not bound to the original policy/response/usage")
        result["elapsed_seconds"] = result["details"]["seconds"]
        result["ended_with_eos"] = response["choices"][0]["finish_reason"] == "stop"
        return result
    paths = list((batch / "gpu").glob("worker_*/"+cid+".response.json"))
    if len(paths) > 1:
        raise ValueError("Duplicate GPU answer")
    if not paths:
        return {"state": "MISSING_OBSERVATION"}
    path = paths[0]
    response = read(path)
    request_path = path.with_name(cid+".request.json")
    publication_path = path.with_name(cid+".publication.json")
    if (not publication_path.exists() or digest(request_path) != response["request_sha256"]
            or read(request_path)["messages"] != policy["messages"]):
        raise ValueError("Local answer has no original request/publication binding")
    publication = read(publication_path)
    elapsed = publication["lifecycle_seconds"]
    if (publication["response_sha256"] != digest(path) or elapsed < response["seconds"]
            or publication["published_observed_ns"] < publication["lifecycle_started_ns"]):
        raise ValueError("Invalid local lifecycle publication receipt")
    return {"state": "RECEIVED", "raw": response["raw"], "details": response,
            "elapsed_seconds": elapsed, "ended_with_eos": response["ended_with_eos"]}


def qualify(batch, plan, references, banks):
    counts = Counter()
    for task in plan["tasks"]:
        cid = task["call_id"]
        bundle, reference = read(batch / "bundles" / (cid+".json")), references[cid]
        policy = read(batch / "policy" / (cid+".json"))
        if digest(batch / "policy" / (cid+".json")) != task["policy_sha256"]:
            raise ValueError("Policy hash mismatch")
        payload = strict_json(policy["messages"][1]["content"])
        if task["kind"] == "aviation_features":
            claims = native_claims(bundle["query_ids"], bundle["disclosed"], at=bundle["at"])
            if claims != reference["claims"] or set(payload["read_products"]) != set(bundle["disclosed"]):
                raise ValueError("Native extraction reference or visible IDs changed")
            for qid, product in payload["read_products"].items():
                for report in product["reports"]:
                    if set(report) != {"station", "observation_time", "raw"} or report["observation_time"] > bundle["at"]:
                        raise ValueError("Model policy exposes cached answers or future observations")
            parsed, _ = parse_features(json.dumps({"slots": claims}), task["read_ids"])
            controls = forecast_controls(bundle, banks, parsed)
            failed = forecast_controls(bundle, banks, None)
            for t in ("1000", "5000"):
                if not math.isclose(controls["values_native_raw"][t], reference["native_probabilities"][t], abs_tol=1e-12, rel_tol=0):
                    raise ValueError("Native future-probability reference changed")
                if controls["values_model_raw"][t] != controls["values_validmask_raw"][t]:
                    raise ValueError("Identical claims must use identical numerical mapping")
                if failed["values_model_raw"][t] != failed["values_validmask_raw"][t]:
                    raise ValueError("Invalid reply must use the matched fallback")
        else:
            if (payload["target"] != bundle["target"] or payload["current_complete_product"] != bundle["common"]
                    or payload["cutoff"] != bundle["cutoff"]):
                raise ValueError("Temperature policy differs from the full native product")
            if temperature_ensemble_probability(bundle) != reference["FOLLOW"]:
                raise ValueError("Same-member probability reference changed")
        counts[task["kind"]] += 1
    return {"passed": True, "native_units": dict(counts), "model_calls": 0,
            "plan_sha256": digest(batch / "PLAN.json"), "scorer_sha256": digest(Path(__file__)),
            "failed_call_matched_mask_verified": True, "native_policy_only_verified": True,
            "scope": "synthetic native-answer qualification; no model capability result"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--qualify-only", action="store_true")
    args = parser.parse_args()
    batch, out = args.batch.absolute(), args.out.absolute()
    out.mkdir(exist_ok=False)
    plan, references = read(batch / "PLAN.json"), read(batch / "evaluator/REFERENCES.json")
    for rel, sha in plan["files"].items():
        if digest(batch / rel) != sha:
            raise ValueError("Frozen experiment changed")
    banks = {mode: read(batch / "banks" / (mode+".json")) for mode in ("values", "mask_age", "common")}
    qualification = qualify(batch, plan, references, banks)
    if args.qualify_only:
        publish(out / "RESULT.json", qualification)
        print(json.dumps(qualification), flush=True)
        return
    publish(out / "INPUT_RECHECK.json", qualification)
    answers, rows, fields = [], [], []
    for model in [*plan["api_models"], "Qwen/Qwen3.8-27B"]:
        for task in plan["tasks"]:
            cid = task["call_id"]
            reference, bundle = references[cid], read(batch / "bundles" / (cid+".json"))
            captured = observation(batch, model, task)
            record = {**task, "model": model, "capture_state": captured["state"], "valid": False}
            answer = None
            if captured["state"] == "RECEIVED":
                record.update(elapsed_seconds=captured["elapsed_seconds"], ended_with_eos=captured["ended_with_eos"])
                try:
                    if task["kind"] == "aviation_features":
                        parsed, format_info = parse_features(captured["raw"], task["read_ids"])
                    else:
                        parsed, format_info = parse_temperature(captured["raw"])
                    record.update(format_info)
                    record["valid"] = bool(captured["ended_with_eos"] and captured["elapsed_seconds"] <= 600)
                    record["parsed_answer"] = parsed
                    if record["valid"]:
                        answer = parsed
                except (ValueError, KeyError, TypeError) as exc:
                    record["parse_error"] = type(exc).__name__
            answers.append(record)
            if task["kind"] == "temperature_F":
                baseline, future = reference["FOLLOW"], reference["future"]
                predictions = {"FOLLOW": baseline, "model_F": baseline if answer is None else answer}
                record["exact_baseline_copy"] = answer == baseline
                record["within_1e12_baseline_copy"] = answer is not None and abs(answer-baseline) <= 1e-12
                rows.append({**task, "model": model, "valid": record["valid"], "future_status": future["status"],
                             "outcome": future["value"], "probabilities": predictions})
                continue
            predictions = forecast_controls(bundle, banks, answer)
            predictions["FOLLOW"] = reference["original_baseline"]
            predictions["always_zero"] = {"1000": 0.0, "5000": 0.0}
            for qid, native in reference["claims"].items():
                for field in native:
                    agreement = ({"literal_exact": False, "semantic_exact": False, "numeric_tolerance": False}
                                 if answer is None else field_agreement(answer[qid][field], native[field], visibility=field == "visibility"))
                    fields.append({"call_id": cid, "model": model, "cohort": task["cohort"], "query_id": qid,
                        "field": field, "reference": native[field], "claim": None if answer is None else answer[qid][field],
                        "invalid_answer": answer is None, **agreement})
            for t in ("1000", "5000"):
                future = reference["future"][t]
                e = {qid: {"native": claimed_support(v, int(t)),
                     "claimed": "invalid" if answer is None else claimed_support(answer[qid], int(t))}
                     for qid, v in reference["claims"].items()}
                rows.append({**task, "model": model, "valid": record["valid"], "threshold": int(t),
                    "future_status": future["status"], "outcome": future["value"], "E_slot_statuses": e,
                    "probabilities": {method: values[t] for method, values in predictions.items()}})
    metrics = defaultdict(lambda: {"registered": 0, "scored": 0, "positive": 0, "valid": 0, "loss_sum": 0.0})
    for row in rows:
        group = [row["model"], row["kind"], row["cohort"], str(row.get("threshold", row.get("event")))]
        for method, p in row["probabilities"].items():
            if not math.isfinite(p) or not 0 <= p <= 1:
                raise ValueError("Invalid probability in frozen scorer")
            item = metrics["__".join(group+[method])]
            item["registered"] += 1
            item["valid"] += row["valid"]
            if row["future_status"] == "mature" and row["outcome"] is not None:
                item["scored"] += 1
                item["positive"] += row["outcome"]
                item["loss_sum"] += (p-row["outcome"])**2
    for item in metrics.values():
        item["brier"] = item["loss_sum"]/item["scored"] if item["scored"] else None
    for filename, values in (("ANSWERS.jsonl", answers), ("ROWS.jsonl", rows), ("FIELDS.jsonl", fields)):
        with (out / filename).open("x") as handle:
            for row in values:
                handle.write(json.dumps(row, sort_keys=True, allow_nan=False)+"\n")
    publish(out / "RESULT.json", {"passed": True, "benchmark_answers_registered": len(answers),
        "capture_states": dict(Counter(a["capture_state"] for a in answers)),
        "valid_by_model_kind": dict(Counter(a["model"]+"__"+a["kind"] for a in answers if a["valid"])),
        "method_opportunity_rows": len(rows), "metrics": dict(metrics),
        "api_ledger": ApiLedger(batch / "api/ledger").reduce(), "confirmation_opened": False,
        "forecast_timing": "warm fixed-packet <=600s; no active selector/source deployment claim",
        "units": {"aviation_ordinary": 72, "aviation_outcome_selected_diagnostic": 12,
                  "temperature_issuances": 8, "temperature_targets": 128},
        "inference_scope": "dependent exposed development; source and forecast rows are not independent weather processes"})
    print(json.dumps({"answers": len(answers), "rows": len(rows), "fields": len(fields)}), flush=True)


if __name__ == "__main__":
    main()
