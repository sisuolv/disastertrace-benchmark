"""Reconstruct every captured model interaction and settle on the CPU only."""

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

from disastertrace.active_warning_v1 import Episode, Outcome
from disastertrace.active_warning_v1.policies import run_episode, scenario_episode
from disastertrace.active_warning_v1.scoring import aggregate, score
from gpu_worker import digest, save
from launch_gpu import CLUSTER, requested_gpus

BASE = Path(__file__).resolve().parent
REPO = BASE.parents[1]


def read(path):
    return json.loads(path.read_text())


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def validate_capture(task_dir, prefix, messages, tokenizer, eos, plan, plan_sha):
    request = read(task_dir / (prefix + "-request.json"))
    response = read(task_dir / (prefix + "-response.json"))
    raw = (task_dir / (prefix + "-raw.txt")).read_text()
    require(
        request["messages"] == messages,
        "model request does not match legal replay view",
    )
    require(request["plan_sha256"] == plan_sha, "request plan identity changed")
    rendered = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True, enable_thinking=False
    )
    require(
        hashlib.sha256(rendered.encode()).hexdigest() == request["rendered_sha256"],
        "rendered prompt changed",
    )
    ids = tokenizer(rendered, add_special_tokens=False)["input_ids"]
    require(
        ids == request["input_ids"] and len(ids) == request["input_tokens"],
        "input tokens do not match request",
    )
    require(
        len(ids) + plan["max_new_tokens"] <= plan["context_limit"], "context overflow"
    )
    output_ids = response["output_ids"]
    require(
        all(type(t) is int and t >= 0 for t in output_ids), "invalid captured token IDs"
    )
    require(
        len(output_ids) == response["output_tokens"] <= plan["max_new_tokens"],
        "output cap or token count differs",
    )
    require(
        tokenizer.decode(output_ids, skip_special_tokens=True) == raw,
        "raw/token mismatch",
    )
    require(
        hashlib.sha256(raw.encode()).hexdigest() == response["raw_sha256"],
        "raw hash changed",
    )
    require(
        response["input_tokens"] == len(ids) and response["capture_prefix"] == prefix,
        "response metadata mismatch",
    )
    ended = bool(output_ids and output_ids[-1] in eos)
    require(response["ended_with_eos"] == ended, "EOS classification changed")
    require(
        math.isfinite(response["seconds"]) and response["seconds"] >= 0,
        "invalid latency",
    )
    details = {key: value for key, value in response.items() if key != "output_ids"}
    return raw if ended else "", details


def paired_reports(rows, traces):
    indexed = {(r["episode_id"], r["scenario"], r["policy"]): r for r in rows}
    trace_index = {(t["episode_id"], t["scenario"], t["policy"]): t for t in traces}
    comparisons = defaultdict(list)
    for row in rows:
        if row["scenario"] != "clean":
            continue
        other = indexed[row["episode_id"], "stale", row["policy"]]
        t0 = trace_index[row["episode_id"], "clean", row["policy"]]
        t1 = trace_index[row["episode_id"], "stale", row["policy"]]
        pairs = list(zip(row["checkpoints"], other["checkpoints"], strict=True))
        differences = [
            b["absolute_error"] - a["absolute_error"]
            for a, b in pairs
            if a["absolute_error"] is not None
        ]
        comparisons[row["family"], row["policy"]].append(
            {
                "episode_id": row["episode_id"],
                "group": row["group"],
                "prediction_changes": sum(
                    a["prediction"] != b["prediction"] for a, b in pairs
                ),
                "checkpoints": len(pairs),
                "stale_minus_clean_mae": mean(differences) if differences else None,
                "clean_queries": [r["tool_id"] for r in t0["receipts"]],
                "stale_queries": [r["tool_id"] for r in t1["receipts"]],
            }
        )
    result = []
    for (family, policy), items in sorted(comparisons.items()):
        by_group = defaultdict(list)
        for item in items:
            if item["stale_minus_clean_mae"] is not None:
                by_group[item["group"]].append(item["stale_minus_clean_mae"])
        result.append(
            {
                "family": family,
                "policy": policy,
                "targets": len(items),
                "changed_predictions": sum(i["prediction_changes"] for i in items),
                "scheduled_checkpoints": sum(i["checkpoints"] for i in items),
                "changed_acquisition_trajectories": sum(
                    i["clean_queries"] != i["stale_queries"] for i in items
                ),
                "group_macro_stale_minus_clean_mae": mean(
                    mean(v) for v in by_group.values()
                )
                if by_group
                else None,
                "per_target": items,
            }
        )
    return result


def main(batch, output):
    from transformers import AutoTokenizer

    plan = read(batch / "PLAN.json")
    plan_sha = digest(batch / "PLAN.json")
    bindings = {}
    for relative, sha in plan["files"].items():
        require(
            digest(batch / relative) == sha, "worker input/source changed: " + relative
        )
    for relative, sha in plan["evaluation_bindings"].items():
        require(
            digest(REPO / relative) == sha,
            "predeclared evaluation changed: " + relative,
        )
    model = Path(plan["model"]["directory"])
    for item in plan["model"]["files"]:
        if not item["path"].endswith(".safetensors"):
            require(
                digest(model / item["path"]) == item["sha256"],
                "tokenizer/config changed",
            )
    tokenizer = AutoTokenizer.from_pretrained(model, local_files_only=True)
    eos = read(model / "generation_config.json")["eos_token_id"]
    eos = eos if isinstance(eos, list) else [eos]
    episodes = {
        e["id"]: Episode.model_validate(e) for e in read(batch / "episodes.json")
    }
    outcome_path = REPO / plan.get(
        "evaluator_outcomes_path",
        str((BASE / "dataset_v2/outcomes_private.json").relative_to(REPO)),
    )
    outcomes = {o["episode_id"]: Outcome.model_validate(o) for o in read(outcome_path)}
    all_traces, rows, workers = [], [], []
    expected_paths = set()
    call_counts = Counter()
    invalid_reasons = Counter()
    acquisition_choices = defaultdict(Counter)
    for worker, tasks in plan["workers"].items():
        root = batch / "runs" / worker
        complete = read(root / "COMPLETE.json")
        hardware = read(root / "HARDWARE.json")
        preflight = read(root / "PREFLIGHT.json")
        final = read(batch / "submissions" / worker / "FINAL.json")
        require(
            final["state"] == "SUCCEEDED"
            and requested_gpus(final) == 1
            and final["resource_pool"]["name"] == CLUSTER,
            "ACP execution not successful as declared",
        )
        require(
            hardware["count"] == 1
            and "H100" in hardware["name"]
            and hardware["bytes"] >= 75 * 1024**3,
            "hardware preflight differs",
        )
        require(hardware["hostname"] != plan["cci_hostname"], "worker is the CPU CCI")
        require(
            hardware["runtime_versions"] == plan["runtime_versions"], "runtime changed"
        )
        require(
            preflight
            == {
                "generation_calls": 0,
                "model_loaded": True,
                "model_hashes_verified": True,
            },
            "generation-disabled preflight not verified",
        )
        require(complete["plan_sha256"] == plan_sha, "worker completion plan differs")
        before_calls = call_counts["all"]
        for task in tasks:
            task_dir = root / task["run_id"]
            trace_path = task_dir / "TRACE.json"
            expected_paths.add(trace_path)
            episode = scenario_episode(episodes[task["episode_id"]], task["scenario"])
            prefixes = []

            def backend(
                system, prompt, stage, round_index, task_dir=task_dir, prefixes=prefixes
            ):
                prefix = f"{stage}-{round_index}"
                prefixes.append(prefix)
                messages = [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ]
                raw, details = validate_capture(
                    task_dir, prefix, messages, tokenizer, eos, plan, plan_sha
                )
                call_counts["all"] += 1
                call_counts[stage] += 1
                call_counts["ended_with_eos"] += int(details["ended_with_eos"])
                for suffix in ("-request.json", "-response.json", "-raw.txt"):
                    path = task_dir / (prefix + suffix)
                    bindings[str(path.relative_to(batch))] = digest(path)
                return raw, details

            replay = run_episode(
                episode, task["budget"], task["policy"], backend=backend
            )
            replay.update(run_id=task["run_id"], plan_sha256=plan_sha)
            captured = read(trace_path)
            require(
                replay == captured, "raw-response replay differs: " + task["run_id"]
            )
            require(
                set(task_dir.glob("*-request.json"))
                == {task_dir / (p + "-request.json") for p in prefixes},
                "unregistered request capture",
            )
            bindings[str(trace_path.relative_to(batch))] = digest(trace_path)
            all_traces.append(replay)
            rows.append(score(episode, outcomes[episode.id], replay))
            invalid_reasons.update(
                e["reason"] for e in replay["events"] if e["kind"] == "invalid"
            )
            acquisition_choices[
                episode.family, task["scenario"], task["policy"]
            ].update(r["tool_id"] for r in replay["receipts"])
        worker_calls = call_counts["all"] - before_calls
        require(
            complete["trajectories"] == len(tasks)
            and complete["model_calls"] == worker_calls,
            "worker completion counts differ",
        )
        require(
            worker_calls <= plan["max_calls_per_worker"], "worker call cap exceeded"
        )
        workers.append(
            {
                "worker": worker,
                "job_id": final["name"],
                "state": final["state"],
                "model_calls": worker_calls,
                "trajectories": len(tasks),
                "hardware": hardware,
            }
        )
    require(
        set((batch / "runs").glob("*/*/TRACE.json")) == expected_paths,
        "unregistered or missing trajectory",
    )
    require(
        call_counts["all"] == plan["maximum_model_calls"],
        "planned call coverage differs",
    )
    output.mkdir(exist_ok=False)
    for filename, values in (("traces.jsonl", all_traces), ("scores.jsonl", rows)):
        with (output / filename).open("x") as stream:
            for value in values:
                stream.write(json.dumps(value, allow_nan=False) + "\n")
    save(output / "SUMMARY.json", aggregate(rows))
    save(output / "PAIRED_STALE.json", paired_reports(rows, all_traces))
    save(
        output / "ACQUISITION_CHOICES.json",
        [
            {
                "family": key[0],
                "scenario": key[1],
                "policy": key[2],
                "tool_counts": dict(value),
            }
            for key, value in sorted(acquisition_choices.items())
        ],
    )
    save(output / "CAPTURE_BINDINGS.json", bindings)
    report = {
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "plan_sha256": plan_sha,
        "targets": len(episodes),
        "trajectories": len(rows),
        "scheduled_checkpoints": sum(len(r["checkpoints"]) for r in rows),
        "missing_checkpoint_submissions": sum(
            not c["submission_at_this_checkpoint"]
            for r in rows
            for c in r["checkpoints"]
        ),
        "calls": dict(call_counts),
        "invalid_reasons": dict(invalid_reasons),
        "unresolved_target_ids": sorted(
            eid for eid in episodes if outcomes[eid].status == "unresolved"
        ),
        "input_tokens": sum(r["model_input_tokens"] for r in rows),
        "output_tokens": sum(r["model_output_tokens"] for r in rows),
        "generation_seconds_sum": sum(r["model_seconds"] for r in rows),
        "raw_token_request_trace_reconstruction": "passed",
        "workers": workers,
        "automatic_retries": 0,
        "model_regeneration_during_collection": 0,
        "inference": "exposed development; four storms and one quiet river segment; no heldout or significance claim",
    }
    save(output / "COMPLETE.json", report)
    print(json.dumps({k: v for k, v in report.items() if k != "workers"}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=Path, default=BASE / "gpu_01")
    parser.add_argument("--output", type=Path, default=BASE / "model_results_01")
    args = parser.parse_args()
    main(args.batch.resolve(), args.output.resolve())
