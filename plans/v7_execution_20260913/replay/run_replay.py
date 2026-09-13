"""CPU replay from local frozen inputs; default runtime uses only stdlib."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import socket
import sys
from collections import Counter, defaultdict
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def check(condition, message):
    if not condition:
        raise ValueError(message)


def install_guard(registry):
    prefixes = [registry["original_project_prefix"], registry["original_model_prefix"]]
    counts = Counter()

    def audit(event, arguments):
        if event in {"socket.__new__", "socket.connect", "socket.getaddrinfo", "subprocess.Popen", "os.system"}:
            counts["network_or_process_denials"] += 1
            raise PermissionError("Replay blocks network and subprocesses")
        if event in {"open", "os.listdir", "os.scandir"} and arguments:
            path = arguments[0]
            if isinstance(path, (str, bytes)):
                absolute = os.path.abspath(os.fsdecode(path))
                if any(absolute == prefix or absolute.startswith(prefix + os.sep) for prefix in prefixes):
                    counts["original_path_denials"] += 1
                    raise PermissionError("Replay blocks original source/model paths")

    sys.addaudithook(audit)
    for path in prefixes:
        try:
            with open(path + "/config.json", "rb"):
                pass
        except PermissionError:
            continue
        raise ValueError("Original path guard failed")
    try:
        socket.socket()
    except PermissionError:
        pass
    else:
        raise ValueError("Network guard failed")
    return counts


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def replay(root, output, full_tokens=False, guard=False):
    registry = load(root / "REGISTRY.json")
    guard_counts = install_guard(registry) if guard else Counter()
    manifest = load(root / "PACKAGE_MANIFEST.json")["files"]
    for relative, expected in manifest.items():
        check(digest(root / relative) == expected, "Package file changed: " + relative)
    first = root / registry["batches"][0]["path"]
    sys.path.insert(0, str(first / "source"))
    from disastertrace.monitoring_fixed_v1.aviation import (
        FrozenFrequencyPredictor,
        model_messages,
        parse_response,
        visible_e_status,
    )
    from disastertrace.monitoring_fixed_v1.contracts import (
        EvidenceBundle,
        Forecast,
        Target,
        fingerprint,
    )

    check(Path(sys.modules[EvidenceBundle.__module__].__file__).resolve().is_relative_to(first / "source"), "Wrong core imported")
    bank = load(root / "matrix/BANK.json")
    predictor = FrozenFrequencyPredictor(bank)
    evaluator_bindings = load(root / "matrix/EVALUATOR_BINDINGS.json")
    evaluator = {}
    for original, relative in registry["evaluator_path_map"].items():
        path = root / relative
        check(digest(path) == evaluator_bindings[original], "Evaluator binding changed")
        evaluator[original] = load(path)
    selected = next(value for key, value in evaluator.items() if "matrix_01/evaluator/OUTCOMES" in key)
    labels = {(row["region"], row["opportunity_id"]): row for row in selected}
    check(len(labels) == len(selected) == 48, "Full development opportunity mask changed")
    for row in selected:
        region_key = "extension_bay_area_01" if row["region"] == "bay" else "extension_front_range_03"
        reference = next(value for key, value in evaluator.items() if region_key in key)
        truth = {item["target_id"]: item for item in reference}[row["target_id"]]
        check({k: v for k, v in row.items() if k not in {"region", "opportunity_id"}} == truth, "Selected outcome differs from independent evaluator table")
    matrix_manifest = load(root / "matrix/MANIFEST.json")
    original_calls = {row["call_id"]: row for row in matrix_manifest}
    program_reference = {row["call_id"]: row for row in load(root / "matrix/PROGRAM.json")}
    for item in matrix_manifest:
        bundle = EvidenceBundle.restore(load(root / "matrix/policy" / (item["call_id"] + ".json")))
        check(bundle.bundle_hash == item["bundle_hash"] and bundle.base_hash == item["base_hash"], "Matrix bundle registry changed")
        program, detail = predictor.predict_with_details(bundle)
        check(program.to_dict() == program_reference[item["call_id"]]["forecast"], "Program forecast replay differs")
        check(detail == program_reference[item["call_id"]]["mapping_details"], "Program map/backoff differs")
        check(visible_e_status(bundle) == program_reference[item["call_id"]]["e_status"], "Program E replay differs")
    eos = load(root / "tokenizer/generation_config.json")["eos_token_id"]
    eos = eos if isinstance(eos, list) else [eos]
    tokenizer = None
    if full_tokens:
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        from transformers import AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained(root / "tokenizer", local_files_only=True)
    rows = []
    batch_reports = {}
    for batch_meta in registry["batches"]:
        batch = root / batch_meta["path"]
        plan = load(batch / "PLAN.json")
        plan_sha = digest(batch / "PLAN.json")
        check(plan_sha == batch_meta["plan_sha256"], "Batch plan changed")
        check(plan["matrix_manifest_sha256"] == digest(root / "matrix/MANIFEST.json"), "Batch matrix binding changed")
        for relative, expected in plan["files"].items():
            check(digest(batch / relative) == expected, "Frozen batch source/input changed")
        for core_file in (first / "source/disastertrace").rglob("*.py"):
            relative = core_file.relative_to(first)
            check(digest(batch / relative) == digest(core_file), "Batch core versions differ")
        if batch_meta["name"] == "fixed_matrix_01":
            make_messages = lambda bundle, variant: model_messages(bundle)
        else:
            filename = "fact_truth_probe.py" if batch_meta["name"] == "fact_truth_probe_01" else "prompt_variants.py"
            make_messages = module(batch / "source" / filename, "prompt_" + batch_meta["name"]).model_messages
        batch_rows, totals = [], Counter()
        for worker, tasks in plan["workers"].items():
            directory = batch / ("worker-" + worker)
            complete = load(directory / "COMPLETE.json")
            hardware = load(directory / "HARDWARE.json")
            check(complete["plan_sha256"] == plan_sha and complete["model_calls"] == len(tasks), "Completion count differs")
            check(hardware["count"] == 1 and "H100" in hardware["name"] and hardware["hostname"] != plan["cci_hostname"], "Recorded GPU metadata differs")
            subtotal = Counter()
            for item in tasks:
                call_id = item["call_id"]
                original = original_calls[item.get("original_call_id", call_id)]
                for field in ("region", "opportunity_id", "condition", "bundle_hash", "base_hash"):
                    check(item[field] == original[field], "Variant changed frozen evidence/target")
                bundle = EvidenceBundle.restore(load(batch / "policy" / (call_id + ".json")))
                check(bundle.bundle_hash == item["bundle_hash"] and bundle.base_hash == item["base_hash"], "Task bundle identity differs")
                request = load(directory / (call_id + "-request.json"))
                response = load(directory / (call_id + "-response.json"))
                variant = item.get("prompt_variant", "original_filled_example")
                messages = make_messages(bundle, variant)
                check(request["messages"] == messages, "Recorded prompt differs from frozen reconstruction")
                check(request["messages_sha256"] == fingerprint(messages) == item["messages_sha256"], "Message hash differs")
                for capture in (request, response):
                    check(capture["plan_sha256"] == plan_sha and capture["bundle_hash"] == bundle.bundle_hash, "Capture binding differs")
                check(response["call_id"] == call_id, "Wrong response call ID")
                check(response["raw_sha256"] == hashlib.sha256(response["raw"].encode()).hexdigest(), "Raw output checksum differs")
                check(all(type(token) is int and token >= 0 for token in request["input_ids"] + response["output_ids"]), "Invalid token IDs")
                check(len(request["input_ids"]) == request["input_tokens"] == response["input_tokens"] == item["input_tokens"], "Input token accounting differs")
                check(len(response["output_ids"]) == response["output_tokens"] <= plan["max_new_tokens"], "Output token accounting differs")
                check(response["ended_with_eos"] == bool(response["output_ids"] and response["output_ids"][-1] in eos), "EOS record differs")
                if tokenizer is not None:
                    rendered = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, enable_thinking=False)
                    check(tokenizer(rendered, add_special_tokens=False)["input_ids"] == request["input_ids"], "Full input tokenization differs")
                    check(tokenizer.decode(response["output_ids"], skip_special_tokens=True) == response["raw"], "Full output decoding differs")
                policy = bundle.policy_view()
                base = Forecast(**policy["baseline"]["forecast"])
                program = predictor.predict(bundle)
                expected_e = visible_e_status(bundle)
                has_f = variant != "explicit_truth_E_only"
                actual_e, valid, error = None, True, None
                forecast = base if has_f else None
                try:
                    if not response["ended_with_eos"]:
                        raise ValueError("length_or_time_stop")
                    if variant.startswith("explicit_truth_"):
                        answer = json.loads(response["raw"])
                        expected_keys = {"fact_truth", "probability"} if has_f else {"fact_truth"}
                        check(isinstance(answer, dict) and set(answer) == expected_keys, "Invalid fact-truth schema")
                        support = {"true": "supported", "false": "refuted", "unknown": "undetermined", "conflict": "inconsistent"}
                        check(type(answer["fact_truth"]) is str and answer["fact_truth"] in support, "Invalid fact-truth string")
                        actual_e = support[answer["fact_truth"]]
                        if has_f:
                            target = Target(**policy["target"])
                            forecast = Forecast(target.contract_hash, "event_probability", "probability", answer["probability"])
                    else:
                        forecast, actual_e = parse_response(response["raw"], bundle)
                except (ValueError, TypeError) as exception:
                    valid, error, actual_e = False, str(exception), None
                    forecast = base if has_f else None
                label = labels[(item["region"], item["opportunity_id"])]
                row = {"batch": batch_meta["name"], "call_id": call_id, "region": item["region"], "opportunity_id": item["opportunity_id"], "condition": item["condition"], "variant": variant, "base_hash": bundle.base_hash, "bundle_hash": bundle.bundle_hash, "outcome": label["outcome"], "e_expected": expected_e, "e_actual": actual_e, "e_correct": actual_e == expected_e, "valid": valid, "error": error, "f_applicable": has_f, "base": base.value, "program": program.value, "model": forecast.value if forecast is not None else None, "input_tokens": response["input_tokens"], "output_tokens": response["output_tokens"]}
                batch_rows.append(row)
                for name in ("input_tokens", "output_tokens"):
                    subtotal[name] += response[name]
            check(all(subtotal[name] == complete[name] for name in subtotal), "Worker token sums differ")
            totals.update(subtotal)
        check(len(batch_rows) == plan["expected_calls"] == batch_meta["expected_calls"], "Incomplete batch")
        check(len({row["call_id"] for row in batch_rows}) == len(batch_rows), "Duplicate calls")
        batch_reports[batch_meta["name"]] = {"calls": len(batch_rows), "valid": sum(row["valid"] for row in batch_rows), "e_correct": sum(row["e_correct"] for row in batch_rows), "tokens": dict(totals), "f_applicable_calls": sum(row["f_applicable"] for row in batch_rows)}
        rows.extend(batch_rows)
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row["batch"], row["variant"], row["region"], row["condition"])].append(row)
    summaries = {}
    for key, group in sorted(grouped.items()):
        expected_ids = {oid for region, oid in labels if region == key[2]}
        check({row["opportunity_id"] for row in group} == expected_ids and len(group) == len(expected_ids), "Method does not retain the full opportunity mask")
        settled = [row for row in group if row["outcome"] is not None]
        summary = {"registered": len(group), "settled": len(settled), "positive": sum(row["outcome"] == 1 for row in settled), "valid": sum(row["valid"] for row in group), "e_correct": sum(row["e_correct"] for row in group), "e_accuracy_full_denominator": sum(row["e_correct"] for row in group) / len(group), "f_applicable": all(row["f_applicable"] for row in group)}
        if summary["f_applicable"]:
            summary["mean_brier_common_mask"] = {method: sum((row[method] - row["outcome"]) ** 2 for row in settled) / len(settled) if settled else None for method in ("base", "program", "model")}
            summary["gain_over_base_common_mask"] = {method: summary["mean_brier_common_mask"]["base"] - summary["mean_brier_common_mask"][method] if settled else None for method in ("program", "model")}
        summaries["/".join(key)] = summary
    result = {"schema": "portable_fixed_replay_result.v1", "verified": True, "captured_original_model_calls": len(rows), "new_model_calls": 0, "unique_development_opportunities": len(labels), "unique_positive_opportunities": sum(row["outcome"] == 1 for row in selected), "matrix_program_predictions_recomputed": len(matrix_manifest), "package_files_verified": len(manifest), "batches": batch_reports, "groups": summaries, "token_verification": "full_local_tokenizer_render_ids_decode" if full_tokens else "stdlib_lengths_integer_ids_EOS_and_capture_hashes_only", "guard": {"enabled": guard, "mechanism": "Python audit hooks; not OS sandbox", "denials": dict(guard_counts)}, "limits": ["Frozen-input replay, not raw dataset rebuilding or new inference", "48 exposed development opportunities; repeated conditions do not add weather processes", "Failed F outputs retain the common baseline and common outcome mask", "E-only calls have no model F score", "Historical availability assumptions remain declared archive scenarios"]}
    output.mkdir(parents=True, exist_ok=False)
    (output / "REPORT.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    (output / "ROWS.json").write_text(json.dumps(rows, indent=2, allow_nan=False) + "\n")
    print(json.dumps({key: result[key] for key in ("verified", "captured_original_model_calls", "new_model_calls", "matrix_program_predictions_recomputed", "token_verification", "guard")}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--full-tokens", action="store_true")
    parser.add_argument("--guard-original-paths-and-network", action="store_true")
    args = parser.parse_args()
    replay(Path(__file__).resolve().parent, args.output.resolve(), args.full_tokens, args.guard_original_paths_and_network)
