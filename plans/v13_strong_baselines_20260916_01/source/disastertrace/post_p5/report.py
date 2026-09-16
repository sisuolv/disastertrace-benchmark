"""Reconcile all frozen P5 answers and add explanatory tables without rescoring history."""

from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path

from disastertrace.automated.common import canonical, fingerprint
from disastertrace.controlled import compiler, renderer, scorer
from disastertrace.controlled.schema import FIELDS, METHODS, parse_decision
from disastertrace.local_eval.storage import digest, inventory, read, seal, verify_seal, write

from .citations import classify_field
from .exposure import exposure_series
from .policies import POLICIES, solve

FACTORS = ("revision_chain", "irrelevant_scope", "late_stale_replay")


def load_run(project, factor, baseline):
    if factor == "base":
        from disastertrace.constrained_eval.execution import verify

        unit = project / "artifacts/p4_constrained_output_v1"
        run = project / "work/p4-qwen3-constrained-v1"
    else:
        from disastertrace.stress_eval.execution import verify

        unit = project / "artifacts/p5_stress_level4_v1/units" / factor
        run = project / ("work/p5-qwen3-" + factor.replace("_", "-") + "-v1")
    plan, episodes, slots = verify(unit / "execution_live")
    verify_seal(unit / "model_report")
    audited = read(unit / "model_report/audit.json")
    if audited["audit_id"] != baseline["reports"][factor]["audit_id"]:
        raise ValueError("report is not the independently reverified baseline")
    if inventory(run) != audited["run_files"]:
        raise ValueError("historical captures changed after independent verification")
    report = read(unit / "model_report/report.json")
    traces = read(unit / "model_report/trace.json")
    by_trace = {(r["method"], r["episode_id"], r["checkpoint_id"]): r for r in traces}
    by_slot = {(s["method"], s["episode_id"], s["checkpoint_id"]): s for s in slots}
    prepared = {}
    for path in sorted((run / "batches").glob("*.json")):
        batch = read(path)
        for slot, prompt in zip(batch["slots"], batch["prepared"]):
            prepared[slot["slot_index"]] = prompt
    rows = {}
    for method in METHODS:
        previous_by_episode = {}
        selected = sorted(
            (r for r in traces if r["method"] == method),
            key=lambda r: (
                next(i for i, ep in enumerate(episodes) if ep["episode_id"] == r["episode_id"]),
                r["checkpoint_id"],
            ),
        )
        reconstructed = scorer._score_rows(episodes, selected, method)
        if reconstructed != report["methods"][method]:
            raise ValueError("frozen score arithmetic differs")
        for scored in reconstructed["per_checkpoint"]:
            key = method, scored["episode_id"], scored["checkpoint_id"]
            slot, trace = by_slot[key], by_trace.get(key)
            ep = next(e for e in episodes if e["episode_id"] == scored["episode_id"])
            previous, history = previous_by_episode.get(ep["episode_id"], (None, []))
            request = renderer.render_request(
                ep, scored["checkpoint_id"], method=method, previous=previous, history=history
            )
            capture_path = run / "captures" / f"{slot['slot_index']:04d}.json"
            capture = read(capture_path) if capture_path.exists() else None
            prediction = None
            if trace is not None:
                if (
                    trace["request"] != request
                    or capture is None
                    or trace["capture_sha256"] != fingerprint(capture)
                ):
                    raise ValueError("capture, trace and declared carrier disagree")
                if trace["raw_response"] != capture["extracted"]["content"]:
                    raise ValueError("trace does not contain captured final content")
                try:
                    prediction = parse_decision(trace["raw_response"])
                except (ValueError, TypeError, KeyError, RecursionError):
                    pass
            base_id = slot.get("base_episode_id", ep["episode_id"])
            rows[(base_id, method, scored["checkpoint_id"])] = {
                "episode": ep,
                "slot": slot,
                "request": request,
                "decision": prediction,
                "gold": compiler.reference_at(ep, scored["checkpoint_id"]),
                "scored": scored,
                "capture": capture,
                "capture_sha256": None if capture is None else fingerprint(capture),
                "capture_file_sha256": None if capture is None else digest(capture_path),
                "prepared": prepared.get(slot["slot_index"]),
                "execution_id": plan["execution_id"],
                "request_origin": "captured" if trace is not None else "reconstructed_unsent",
            }
            if prediction is not None:
                previous_by_episode[ep["episode_id"]] = (
                    prediction,
                    history + [deepcopy(prediction)],
                )
    return plan, episodes, rows


def trajectory_summary(rows):
    ordered = sorted(rows, key=lambda r: r["checkpoint_id"])
    bad = [not r["all_correct"] for r in ordered]
    intervals, start = [], None
    for i, failure in enumerate(bad + [False]):
        if failure and start is None:
            start = i
        if not failure and start is not None:
            intervals.append(
                {
                    "start_checkpoint": ordered[start]["checkpoint_id"],
                    "length": i - start,
                    "recovered_at": ordered[i]["checkpoint_id"] if i < len(bad) else None,
                    "right_censored": i == len(bad),
                }
            )
            start = None
    return {
        "first_error_checkpoint": next(
            (r["checkpoint_id"] for r in ordered if not r["all_correct"]), None
        ),
        "all_checkpoints_correct": not any(bad),
        "error_intervals": intervals,
    }


def _write_jsonl(path, rows):
    with path.open("x") as stream:
        for row in rows:
            stream.write(canonical(row) + "\n")


def analyze(project, baseline_path, output):
    project, output = Path(project), Path(output)
    baseline = read(Path(baseline_path) / "repo_baseline.json")
    if baseline["status"] != "passed" or not baseline["full_capture_verified"]:
        raise ValueError("full baseline capture verification is required for this P5 analysis")
    output.mkdir(parents=True, exist_ok=False)
    units = {factor: load_run(project, factor, baseline) for factor in ("base",) + FACTORS}
    fields, citations, pairs, trajectories = [], [], [], []
    counts, labels, by_cell = Counter(), Counter(), defaultdict(Counter)
    for factor in FACTORS:
        _plan, episodes, rows = units[factor]
        for ep in episodes:
            base_ids = {
                key[0]
                for key, row in rows.items()
                if row["episode"]["episode_id"] == ep["episode_id"]
            }
            if len(base_ids) != 1:
                raise ValueError("verified slots do not define one base episode")
            base_id = next(iter(base_ids))
            for method in METHODS:
                keys = [(base_id, method, cp["checkpoint_id"]) for cp in ep["checkpoints"]]
                left = [units["base"][2][k] for k in keys]
                right = [rows[k] for k in keys]
                exposure = exposure_series(
                    [r["request"] for r in left], [r["request"] for r in right]
                )
                earlier = defaultdict(list)
                checkpoint_rows, prior_gold = [], None
                for key, a, b, visible in zip(keys, left, right, exposure):
                    cp = key[2]
                    identity = {
                        "factor": factor,
                        "method": method,
                        "episode_id": ep["episode_id"],
                        "base_episode_id": base_id,
                        "checkpoint_id": cp,
                        "source_group": ep["group_id"],
                        "family": ep["family"],
                        "case": ep["case"],
                        "branch": ep["branch"],
                        "repeat": 0,
                    }
                    x, y = (
                        bool(a["scored"]["counts"]["all_correct"]),
                        bool(b["scored"]["counts"]["all_correct"]),
                    )
                    pair = {
                        **identity,
                        **visible,
                        "base_correct": x,
                        "condition_correct": y,
                        "outcome": "both_correct"
                        if x and y
                        else "base_only"
                        if x
                        else "condition_only"
                        if y
                        else "both_wrong",
                        "prompt_token_equal": None
                        if a["prepared"] is None or b["prepared"] is None
                        else a["prepared"]["prompt_token_ids"] == b["prepared"]["prompt_token_ids"],
                        "sampling_seed_equal": None
                        if a["prepared"] is None or b["prepared"] is None
                        else a["prepared"]["sampling"]["seed"] == b["prepared"]["sampling"]["seed"],
                        "response_equal": a["decision"] == b["decision"],
                        "prompt_tokens": None
                        if b["capture"] is None
                        else b["capture"]["prompt_tokens"],
                        "base_prompt_tokens": None
                        if a["capture"] is None
                        else a["capture"]["prompt_tokens"],
                    }
                    pairs.append(pair)
                    checkpoint_rows.append({**identity, "all_correct": y})
                    counts["planned_responses"] += 1
                    counts["received"] += int(b["capture"] is not None)
                    counts["all_correct"] += y
                    counts["incorrect_checkpoints"] += not y
                    counts["action_errors"] += not b["scored"]["counts"]["action_correct"]
                    counts["c0_all_correct" if cp == "c0" else "post_c0_all_correct"] += y
                    carrier_state = b["request"].get("previous_state")
                    if method == "answer_history" and b["request"]["answer_history"]:
                        carrier_state = b["request"]["answer_history"][-1]
                    for field in FIELDS:
                        expected = b["gold"]["state"][field]
                        predicted = None if b["decision"] is None else b["decision"]["state"][field]
                        row = classify_field(
                            b["request"],
                            field,
                            predicted,
                            expected,
                            all_record_ids={r["record_id"] for r in ep["records"]},
                            previous=None
                            if carrier_state is None
                            else carrier_state["state"][field],
                            earlier_correct_refs=earlier[field],
                            status=b["scored"]["status"],
                        )
                        old = b["scored"]["slots"][field]
                        if (row["legacy_value_correct"], row["legacy_grounded_correct"]) != (
                            old["value_correct"],
                            old["grounded_correct"],
                        ):
                            raise ValueError("diagnostic changed historical field score")
                        prior = None if prior_gold is None else prior_gold["state"][field]
                        transition = (
                            "initial"
                            if prior is None
                            else "unchanged_retention"
                            if prior == expected
                            else "support_arrival"
                            if prior["status"] == "unknown" and expected["status"] == "known"
                            else "provenance_only_update"
                            if prior["status"] == expected["status"]
                            and prior["value"] == expected["value"]
                            else "value_or_status_update"
                        )
                        row.update(
                            identity,
                            execution_id=b["execution_id"],
                            slot_id=b["slot"]["slot_id"],
                            request_sha256=fingerprint(b["request"]),
                            capture_sha256=b["capture_sha256"],
                            capture_file_sha256=b["capture_file_sha256"],
                            exposure_status=visible["exposure_status"],
                            transition=transition,
                            submitted=predicted,
                            expected=expected,
                        )
                        row["flags"]["prior_carrier_was_wrong"] = (
                            None
                            if carrier_state is None or prior is None
                            else carrier_state["state"][field] != prior
                        )
                        fields.append(row)
                        citations.extend(
                            {**identity, "field": field, "citation_index": i, **detail}
                            for i, detail in enumerate(row["citation_details"])
                        )
                        counts["field_errors"] += not row["legacy_grounded_correct"]
                        counts["value_status_errors"] += not row["legacy_value_correct"]
                        counts["citation_only_errors"] += row["citation_only_error"]
                        known = expected["status"] == "known"
                        counts["known_opportunities" if known else "unknown_opportunities"] += 1
                        counts["known_value_correct" if known else "unknown_correct"] += row[
                            "legacy_value_correct"
                        ]
                        if known:
                            counts["known_grounded_correct"] += row["legacy_grounded_correct"]
                        if row["citation_only_error"]:
                            labels[row["primary_error"]] += 1
                        if not row["legacy_grounded_correct"]:
                            by_cell[(factor, method, field)][row["primary_error"]] += 1
                        earlier[field].extend(expected["evidence"])
                    if not b["scored"]["counts"]["action_correct"]:
                        counts["action_errors_overlapping_wind"] += not b["scored"]["slots"][
                            "maximum_wind_mph"
                        ]["grounded_correct"]
                    prior_gold = b["gold"]
                trajectories.append(
                    {
                        **{
                            k: v
                            for k, v in checkpoint_rows[0].items()
                            if k not in ("checkpoint_id", "all_correct")
                        },
                        **trajectory_summary(checkpoint_rows),
                    }
                )
    expected_counts = {
        "planned_responses": 1620,
        "received": 1620,
        "all_correct": 1360,
        "incorrect_checkpoints": 260,
        "value_status_errors": 90,
        "citation_only_errors": 230,
        "field_errors": 320,
        "action_errors": 29,
        "action_errors_overlapping_wind": 29,
        "known_opportunities": 5076,
        "unknown_opportunities": 1404,
        "known_value_correct": 4986,
        "known_grounded_correct": 4756,
        "unknown_correct": 1404,
        "c0_all_correct": 324,
        "post_c0_all_correct": 1036,
    }
    if dict(counts) != expected_counts or sum(labels.values()) != 230:
        raise ValueError("frozen P5 conservation mismatch: " + str(dict(counts)))
    _write_jsonl(output / "field_diagnostics.jsonl", fields)
    _write_jsonl(output / "citation_details.jsonl", citations)
    _write_jsonl(output / "exposure_pairs.jsonl", pairs)
    _write_jsonl(output / "trajectory_errors.jsonl", trajectories)
    slice_counts = {}
    for factor in FACTORS:
        for method in METHODS:
            for exposure in ("before_first_exposure", "exposed", "never_exposed"):
                selected = [
                    r
                    for r in pairs
                    if (r["factor"], r["method"], r["exposure_status"])
                    == (factor, method, exposure)
                ]
                slice_counts[f"{factor}/{method}/{exposure}"] = {
                    "planned": len(selected),
                    "condition_correct": sum(r["condition_correct"] for r in selected),
                    "base_correct": sum(r["base_correct"] for r in selected),
                    "outcomes": dict(Counter(r["outcome"] for r in selected)),
                    "condition_accuracy": sum(r["condition_correct"] for r in selected)
                    / len(selected)
                    if selected
                    else None,
                }
    summary = {
        "status": "passed",
        "analysis_version": "p6_posthoc_v1",
        "counts": dict(counts),
        "citation_only_primary": dict(labels),
        "exposure_slices": slice_counts,
        "field_breakdown": {"/".join(k): dict(v) for k, v in by_cell.items()},
        "first_exposure_episodes": {
            factor: dict(
                Counter(
                    r["first_exposed_checkpoint"] or "never"
                    for r in pairs
                    if r["factor"] == factor
                    and r["method"] == "snapshot"
                    and r["checkpoint_id"] == "c0"
                )
            )
            for factor in FACTORS
        },
        "additional_model_calls": 0,
        "old_scores_changed": False,
    }
    write(output / "conservation.json", summary)
    _policies(units, output)
    paragraphs = [
        "# P6 对 P5 的只读诊断",
        "",
        "所有旧分数保持不变；字段、checkpoint 和动作分别计数。",
        "",
        "引用错误主类（只统计原有 230 个值正确但引用错误的字段）：",
        "",
        "| 主类 | 字段数 |",
        "| --- | ---: |",
    ]
    paragraphs += [f"| {k} | {v} |" for k, v in sorted(labels.items())]
    paragraphs += [
        "",
        "首次压力曝光（episode 数，不含方法重复）：",
        "",
        "```json",
        canonical(summary["first_exposure_episodes"]),
        "```",
        "",
        "完整曝光、双向变化、载体/种子/token 比较见 exposure_pairs.jsonl；恢复轨迹见 trajectory_errors.jsonl。",
        "标签描述可观测引用关系，不证明模型内部为何出错。零机会补充切片为 null。",
        "合法 latest-issued 对照见 shortcut_scores.json；更多线性修订记录不等于必须解析复杂分叉图。",
        "",
    ]
    (output / "DIAGNOSTIC_FINDINGS.md").write_text("\n".join(paragraphs))
    seal(output)
    return summary


def _policies(units, output):
    totals, rows, difficulty = defaultdict(Counter), [], []
    from disastertrace.controlled.public_oracle import parse_evidence

    for factor, (_, episodes, _) in units.items():
        for ep in episodes:
            for cp in ep["checkpoints"]:
                request = renderer.render_request(ep, cp["checkpoint_id"], method="snapshot")
                gold = compiler.reference_at(ep, cp["checkpoint_id"])
                predictions = {policy: solve(request, policy) for policy in POLICIES}
                for policy, prediction in predictions.items():
                    totals[(factor, policy)]["checkpoints"] += 1
                    totals[(factor, policy)]["all_correct"] += prediction == gold
                    totals[(factor, policy)]["value_correct_fields"] += sum(
                        prediction["state"][f]["value"] == gold["state"][f]["value"]
                        and prediction["state"][f]["status"] == gold["state"][f]["status"]
                        for f in FIELDS
                    )
                if predictions["latest_issued_per_key"] != gold:
                    raise ValueError(
                        "latest-issued sufficiency counterexample in frozen legal domain"
                    )
                rows.append(
                    {
                        "factor": factor,
                        "episode_id": ep["episode_id"],
                        "checkpoint_id": cp["checkpoint_id"],
                        "policy_disagreement_signature": {
                            p: fingerprint(v) for p, v in predictions.items()
                        },
                        "distinct_decisions": len({canonical(v) for v in predictions.values()}),
                    }
                )
                entries = parse_evidence(request)
                unique = {e["assertion"]["revision_id"]: e for e in entries}
                depths = {}
                for revision, entry in unique.items():
                    parent = entry["assertion"]["supersedes"]
                    depths[revision] = 0 if parent is None else depths[parent] + 1
                difficulty.append(
                    {
                        "factor": factor,
                        "episode_id": ep["episode_id"],
                        "checkpoint_id": cp["checkpoint_id"],
                        "delivered_record_count": len(request["evidence"]),
                        "unique_assertion_count": len(unique),
                        "revision_depth": max(depths.values(), default=0),
                        "id_lengths": sorted({len(e["record_id"]) for e in entries}),
                        "competing_values_per_field": {
                            f: len(
                                {
                                    e["assertion"]["value"]
                                    for e in entries
                                    if e["assertion"]["variable"] == f
                                    and all(
                                        e["assertion"][k] == v for k, v in request["target"].items()
                                    )
                                }
                            )
                            for f in FIELDS
                        },
                    }
                )
    write(
        output / "shortcut_scores.json",
        {
            "model_calls": 0,
            "method_information": "public_only_snapshot",
            "scores": {"/".join(k): dict(v) for k, v in totals.items()},
        },
    )
    _write_jsonl(output / "policy_disagreements.jsonl", rows)
    _write_jsonl(output / "difficulty_manifest.jsonl", difficulty)
