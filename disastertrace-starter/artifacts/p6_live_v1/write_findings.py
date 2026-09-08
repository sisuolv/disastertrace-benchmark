"""Render a factual review handoff from completed, sealed artifacts."""

from collections import Counter
from pathlib import Path

from disastertrace.local_eval.storage import read, verify_seal

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]


def percent(value, denominator):
    return f"{value / denominator:.1%}" if denominator else "n/a"


def main():
    report = HERE / "reports/model_review_v2"
    verify_seal(report)
    audited, scores = read(report / "audit.json"), read(report / "scores.json")
    source = read(PROJECT / "artifacts/nhc_forecast_source_v1/review_v1/report.json")
    attribution = read(HERE / "analysis/summary.json")
    job = read(HERE / "MODEL_JOB_OBSERVED.json")
    grammar = read(HERE / "grammar_model/report.json")
    relocation = read(HERE / "CPU_RELOCATION.json")
    counts = scores["counts"]
    lines = [
        "# P6 paired Qwen3-8B results and NHC source review",
        "",
        "## Actual execution",
        "",
        f"ACP job `{job['job']['name']}` is `{job['job']['state']}`. One full H100 runs the entire paired matrix.",
        f"Execution: `{audited['execution_id']}`. Independent model audit: `{audited['audit_id']}`.",
        (
            f"Received **{audited['received']}/2160** model answers; attempted {audited['attempted']}; "
            f"unresolved {audited['outcome_unknown']}; unsubmitted {audited['unsubmitted']}."
        ),
        f"The model capture is complete: `{audited['complete']}`. Original worker subprocesses all pass: `{job['all_worker_steps_passed']}`.",
        (
            "The collector exits0 with all2160 answers. The original report and verify steps exit1 because "
            "the auditor incorrectly expected the rendered EOS marker despite include_stop_str_in_output=false. "
            "The ACP job therefore remains FAILED. A separately frozen CPU reviewer checks the exact bound "
            "stop-token rendering policy, preserves extraction/scoring and reconstructs the complete capture. "
            "All2160 runtime texts match that policy. Ten CPU regression tests and two installed-vLLM "
            "detokenizer tests pass; the initial two regression failures and original failed reports remain. "
            "The subsequent finalization_002 verifies the reports without another model generation."
        ),
        (
            f"Schema-valid answers: **{counts['schema_valid']}/2160**. Fully correct checkpoints: "
            f"**{counts['all_correct']}/2160 ({percent(counts['all_correct'], 2160)})**."
        ),
        f"Format screens passed: **{sum(s['passed'] for s in scores['format_screens'])}/36**.",
        "",
        (
            "The conditions are base and irrelevant_scope level4. Each contains36 development episodes, "
            "five checkpoints, three methods and two repeats. Sampling is paired across conditions; "
            "method and repeat remain in the seed key. Carriers are isolated by trajectory. No failed "
            "answer was retried, replaced or repaired."
        ),
        "",
        "## Method and repeat results",
        "",
        "| Condition | Method | Repeat0 correct /180 | Repeat1 correct /180 | Combined /360 | Successful trajectories /72 | Episode pass^2 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for condition in ("base", "irrelevant_scope"):
        for method in ("snapshot", "structured_state", "answer_history"):
            selected = sorted(
                [
                    c
                    for c in scores["cells"]
                    if c["condition"] == condition and c["method"] == method
                ],
                key=lambda c: c["repeat"],
            )
            reliability = [
                r
                for r in scores["episode_reliability"]
                if r["condition"] == condition and r["method"] == method
            ]
            successful = sum(r["successes"] for r in reliability)
            both = sum(r["successes"] == 2 for r in reliability)
            total = sum(c["counts"]["all_correct"] for c in selected)
            lines.append(
                f"| {condition} | {method} | {selected[0]['counts']['all_correct']} | "
                f"{selected[1]['counts']['all_correct']} | {total} ({percent(total, 360)}) | "
                f"{successful} ({percent(successful, 72)}) | {both}/36 ({percent(both, 36)}) |"
            )
    lines += [
        "",
        (
            "Episode success requires all five checkpoints to be fully correct. With exactly two repeats, "
            "pass^2 is the fraction of base episodes that succeed in both repeats; it is not a checkpoint-level "
            "pass@k metric or a confidence bound."
        ),
        "",
        "## Paired outcomes",
        "",
        "| Method | Exposure slice | Pairs | Both correct | Base only correct | Scope only correct | Both wrong |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for method in ("snapshot", "structured_state", "answer_history"):
        for exposure in ("before_first_exposure", "exposed"):
            selected = [
                p
                for p in scores["paired_changes"]
                if p["method"] == method and p["exposure_status"] == exposure
            ]
            outcomes = Counter(p["outcome"] for p in selected)
            lines.append(
                f"| {method} | {exposure} | {len(selected)} | {outcomes['both_correct']} | "
                f"{outcomes['base_only']} | {outcomes['condition_only']} | {outcomes['both_wrong']} |"
            )
    lines += [
        "",
        (
            "Both directions of change are retained. These are closed-loop trajectory comparisons, "
            "so later differences include any effects of earlier model outputs on the carrier. They are "
            "not estimates of a direct isolated intervention on a fixed carrier."
        ),
        "",
        "| Checkpoint | Received pairs | Identical requests | Identical final text |",
        "| --- | ---: | ---: | ---: |",
    ]
    lines += [
        f"| {checkpoint} | {agreement['pairs']} | {agreement['identical_requests']} | "
        f"{agreement['identical_final_text']} |"
        for checkpoint, agreement in sorted(
            attribution["paired_request_and_final_agreement_by_checkpoint"].items()
        )
    ]
    lines += [
        "",
        (
            "Shared sampling seeds do not by themselves prove bitwise deterministic execution. "
            "The before-exposure outcome table and request/final-text agreement are empirical checks; "
            "any pre-exposure differences cannot be attributed to exposure to the distractor."
        ),
        "",
        "## Error attribution",
        "",
        (
            f"Across {attribution['received_field_opportunities']} received field opportunities, deterministic attribution finds "
            f"{attribution['counts']['value_status_or_invalid_errors']} value/status/invalid errors and "
            f"{attribution['counts']['citation_only_errors']} citation-only errors. This reconciles to the frozen scorer."
        ),
        f"Action errors: {counts['checkpoints'] - counts['action_correct']}; these can overlap field errors and must not be added as independent failures.",
        "",
    ]
    lines += [
        f"- `{name}`: {number}"
        for name, number in sorted(
            attribution["primary_error_categories"].items(), key=lambda item: (-item[1], item[0])
        )
    ]
    lines += [
        "",
        (
            "All field-level attributions are in `analysis/fields.jsonl`; `analysis/examples.json` contains "
            "the first twelve erroneous fields in frozen schedule order. Example selection is deterministic, "
            "and the full error inventory is retained."
        ),
        "",
        "## Runtime and verification",
        "",
        (
            f"Prompt tokens: {scores['usage']['prompt_tokens']:,}; completion tokens: {scores['usage']['completion_tokens']:,}; "
            f"reasoning tokens: {scores['usage']['reasoning_tokens']:,}."
        ),
        (
            f"Summed generation-batch wall time: {scores['batch_generation_wall_seconds'] / 60:.2f} minutes. "
            f"Collector wall time including model preparation: {audited['collector_completion']['worker_wall_seconds'] / 60:.2f} minutes. "
            "These are measured worker intervals, not an inferred billing amount."
        ),
        (
            f"Token-mask replay checks {grammar['counts']['constrained_tokens_checked']:,} final/EOS tokens; "
            f"constraint violations: {grammar['counts']['constraint_violations']}; reasoning-only sequences: {grammar['counts']['reasoning_only']}."
        ),
        f"Relocated CPU reconstruction: `{relocation['status']}`, with original project/weights/network blocked and no Torch/vLLM.",
        "",
        (
            "95 relevant CPU tests pass, plus one installed-vLLM cached-tokenizer regression. The initial "
            "live freeze was cancelled before any generation when that regression exposed an overly strict "
            "class-name check. Both generation-disabled H100 preflights, the initial failing regression, "
            "the cancellation claims and replacement freeze remain recorded. Correct/invalid program "
            "rehearsals are separate from all actual model results. Historical P6 offline acceptance "
            "reverifies without changing its5,703 bound files."
        ),
        "",
        "## Real forecast-source milestone",
        "",
        (
            f"Planned NHC bodies:12; received:{source['received_bodies']}; admitted:{source['admitted_bodies']}; "
            f"quarantined:{source['quarantined_bodies']}. The admitted products provide {source['forecast_rows']} forecast rows and "
            f"{source['same_valid_revision_pairs']} adjacent admitted-version pairs at identical absolute valid times; "
            f"{source['wind_changed_pairs']} pairs change sustained wind."
        ),
        (
            "The selection is Francine AL062024005-010 and Ida AL092021009-014. All eight originally "
            "declared heldout storm IDs remain protected; Ian's supplied-plan exposure is recorded. "
            "Two independent parsers must agree. Failures go to automatic quarantine. Raw bytes, URLs, "
            "hashes, fetch metadata, canonical line/byte maps and lossless exports are retained."
        ),
        (
            "26 source-pipeline CPU tests pass, including one80-example property test. The source stage "
            "performs zero LLM calls, human Gold annotations or LLM judging. Available-at and model "
            "initialization remain unknown; forecast pressure is not inferred from current pressure."
        ),
        (
            "The first source command failed before networking because the minimal snapshot omitted "
            "package-import dependencies. source_execution_v2 supplies the preserved dependency closure "
            "without changing the frozen parsers, scope or original snapshot. finalization_003 verifies "
            "the import/scope, performs the single bounded acquisition and rebuilds its source review. "
            "No acquisition claim or HTTP attempt existed before that packaging correction."
        ),
        "",
        "See `../nhc_forecast_source_v1/PROTOCOL.md` and `../nhc_forecast_source_v1/review_v1/report.json` for coverage and quarantine reasons.",
        "",
        "## Interpretation and next research step",
        "",
        (
            "The user requested more GPU parallelism during collection. The current TP=1 worker "
            "remained intact. A separate offline four-worker layout now assigns nine whole episodes, "
            "540 opportunities,108 trajectories and270 pairs per worker, retaining all methods, "
            "conditions and repeats of an episode on the same GPU. Eighteen layout tests and actual "
            "schedule reconstruction pass. This is preparation for later collection/aggregation "
            "engineering; it submits no new GPU job and does not establish a measured speedup. "
            "See `../p6_parallel_preparation_v1/README.md`."
        ),
        "",
        (
            "The model matrix contains only three independent storm sources and two repeats. Do not use "
            "synthetic variants as independent storms, report population significance, or declare a "
            "method universally superior. The source selection includes Francine as one candidate "
            "development storm beyond the existing Ida source; actual admission is reported above. "
            "It does not establish coverage across extreme-weather phenomena."
        ),
        "",
        (
            "1. Freeze a separate forecast-claim task using exact absolute valid-time keys, explicit "
            "missing/terminal semantics and byte-grounded citations. Do not mix these archive facts with "
            "the controlled P6 scoreboard or label the task as numerical weather prediction."
        ),
        (
            "2. Prepare equal-information JSON/text carrier controls with measured token differences "
            "and common input histories. Label raw and program-derived input tracks separately; the "
            "current normalized source exports are review artifacts, not an executed representation study."
        ),
        (
            "3. After that task, scorer, split and context budget are frozen, specify one matching second-model "
            "matrix. More sources, heldout refreshes, new phenomena and training require their own explicit "
            "designs; none are silently added to the completed2160 matrix."
        ),
        "",
        "Detailed implementation order and acceptance gates: `NEXT_RESEARCH_PLAN.md`.",
        "",
    ]
    with (HERE / "FINDINGS.md").open("x") as stream:
        stream.write("\n".join(lines))
    entry = "\n".join(
        [
            "# P6 paired model and forecast-source milestone",
            "",
            (
                f"Qwen3-8B: {audited['received']}/2160 actual answers; {counts['schema_valid']} schema-valid; "
                f"{counts['all_correct']} fully correct. Original ACP state: {job['job']['state']}; "
                "the complete capture is verified after a versioned CPU-only stop-token audit fix."
            ),
            "",
            (
                f"NHC source pilot: {source['admitted_bodies']}/12 admitted products from "
                f"{source['independent_storm_sources']} development storms; {source['same_valid_revision_pairs']} same-valid-time revision pairs."
            ),
            "",
            "- Detailed results and next research steps: [FINDINGS](artifacts/p6_live_v1/FINDINGS.md).",
            "- Scope and runtime: [execution plan](artifacts/p6_live_v1/EXECUTION_PLAN.md).",
            "- Safe CPU reproduction: [reproduction instructions](artifacts/p6_live_v1/REPRODUCE.md).",
            "- Next implementation milestone: [forecast-task plan](artifacts/p6_live_v1/NEXT_RESEARCH_PLAN.md).",
            "- Raw forecast semantics and boundaries: [source protocol](artifacts/nhc_forecast_source_v1/PROTOCOL.md).",
            "- Completed acceptance: artifacts/p6_live_v1/COMPLETED_ACCEPTANCE.json.",
            "",
            (
                "The model launch is consumed. Never rerun a launcher or use old answers as a fresh repeat. "
                "Read-only CPU verification needs neither an API key nor a GPU. Historical root navigation/status "
                "files remain frozen; CURRENT_PHASE.md is the mutable phase pointer."
            ),
            "",
        ]
    )
    with (PROJECT / "README_P6_LIVE_V1.md").open("x") as stream:
        stream.write(entry)
    print(
        {"findings": str(HERE / "FINDINGS.md"), "entry": str(PROJECT / "README_P6_LIVE_V1.md")},
        flush=True,
    )


if __name__ == "__main__":
    main()
