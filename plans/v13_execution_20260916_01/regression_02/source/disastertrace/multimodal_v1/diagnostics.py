"""Captured non-LLM controls and a read-only, independently written run audit."""

from pathlib import Path

from .compiler import public_view, reference_for
from .pixel_baseline import answer
from .runner import run_trajectories
from .scoring import rate, score_trajectory
from .source_audit import verify_sources
from .storage import canonical, digest, read, write
from .types import ModelCommit

POLICIES = (
    "public_pixel",
    "latest_arrival",
    "never_update",
    "value_only",
    "global_update",
    "center_text_changes_space",
    "missing_as_false",
)


def parse(text):
    return {"state": ModelCommit.parse(text).state}


def _expected_plan(build):
    episode = read(build / "private/episode.json")
    return {
        branch: [
            public_view(episode, branch, cp, build / "public")
            for cp in range(episode["checkpoints"])
        ]
        for branch in episode["branches"]
    }


def audit_capture(build, run, policy):
    templates = _expected_plan(build)
    expected_plan = {
        "trajectories": templates,
        "trajectory_order": list(templates),
        "backend_id": "mm_offline_" + policy,
        "origin": "offline_diagnostic",
    }
    if read(run / "plan.json") != expected_plan:
        raise ValueError("captured plan differs from public projection")
    audited = {}
    for branch, requests in templates.items():
        carrier, stopped, rows = None, False, []
        for cp, template in enumerate(requests):
            folder = run / branch / f"{cp:04d}"
            request = dict(template, carrier=carrier)
            request_hash = digest(canonical(request).encode())
            captured = read(folder / "outcome.json")
            has_intent, has_raw = (folder / "intent.json").exists(), (folder / "raw.txt").exists()
            if stopped:
                expected = {"status": "unattempted", "reason": "trajectory_stopped"}
                if has_intent or has_raw:
                    raise ValueError("dependent checkpoint executed after a stop")
            else:
                if read(folder / "request.json") != request:
                    raise ValueError("wire request or own history differs")
                if has_intent and read(folder / "intent.json") != {"request_sha256": request_hash}:
                    raise ValueError("intent is not bound to request")
                if has_raw:
                    if not has_intent:
                        raise ValueError("raw without dispatch intent")
                    raw = (folder / "raw.txt").read_bytes()
                    expected = {"raw_sha256": digest(raw), "request_sha256": request_hash}
                    try:
                        value = parse(raw.decode("utf-8"))
                    except (ValueError, TypeError, KeyError, RecursionError) as error:
                        expected.update(status="received_invalid", error_type=type(error).__name__)
                    else:
                        expected.update(status="received_valid", value=value)
                    carrier = {
                        "raw": raw.decode("utf-8", errors="replace"),
                        "invalid": expected["status"] == "received_invalid",
                        "missing": False,
                    }
                elif has_intent:
                    expected = {"status": "unknown", "request_sha256": request_hash}
                    stopped = True
                else:
                    error = read(folder / "preflight_error.json")
                    expected = {
                        "status": "failed_preflight",
                        "request_sha256": request_hash,
                        "error_type": error["error_type"],
                    }
                    stopped = True
            if expected != captured:
                raise ValueError("saved outcome differs from raw capture")
            rows.append(expected)
        audited[branch] = rows
    return audited


def reconstruct(build, runs):
    build, runs = Path(build), Path(runs)
    episode = read(build / "private/episode.json")
    references = read(build / "private/references.json")
    templates = _expected_plan(build)
    source_audit = verify_sources(build)
    for branch, requests in templates.items():
        for cp, request in enumerate(requests):
            if read(build / "public" / "requests" / branch / f"c{cp}.json") != request:
                raise ValueError("saved public request differs from current projection")
            recomputed = reference_for(episode, request)
            if recomputed != references[branch][cp] or parse(answer(request)) != recomputed:
                raise ValueError("private reference / independent public-pixel disagreement")
    summaries, reports = {}, {}
    for policy in POLICIES:
        captured = audit_capture(build, runs / policy, policy)
        reports[policy] = {
            branch: score_trajectory(references[branch], rows) for branch, rows in captured.items()
        }
        n = sum(r["strict_checkpoints"]["numerator"] for r in reports[policy].values())
        d = sum(r["strict_checkpoints"]["denominator"] for r in reports[policy].values())
        summaries[policy] = {
            "strict_checkpoints": rate(n, d),
            "complete_branches": rate(
                sum(r["episode_all_correct"] for r in reports[policy].values()),
                len(reports[policy]),
            ),
        }
    if summaries["public_pixel"]["strict_checkpoints"]["rate"] != 1:
        raise ValueError("positive program control failed")
    if any(summaries[p]["strict_checkpoints"]["rate"] == 1 for p in POLICIES[1:]):
        raise ValueError("a known-error control was not detected")
    return {
        "status": "passed",
        "origin": "offline_program_diagnostic",
        "eligible_for_llm_leaderboard": False,
        "model_calls": 0,
        "paid_api_calls": 0,
        "gpu_jobs": 0,
        "summaries": summaries,
        "reports": reports,
        "independent_source_audit": source_audit,
        "interpretation": "Branches share one real development event; program controls are not model results.",
    }


def run_diagnostics(build, output):
    build, output = Path(build), Path(output)
    output.mkdir(parents=True, exist_ok=False)
    templates = _expected_plan(build)
    for policy in POLICIES:
        result = run_trajectories(
            output / "runs" / policy,
            templates,
            lambda request, p=policy: answer(request, p),
            parse,
            backend_id="mm_offline_" + policy,
        )
        write(output / (policy + "_collection.json"), result)
    report = reconstruct(build, output / "runs")
    write(output / "report.json", report)
    return report
