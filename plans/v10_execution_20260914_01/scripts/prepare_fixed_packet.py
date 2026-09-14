"""Freeze a finite calendar E/F study before any new model calls."""

import argparse
import datetime as dt
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

from disastertrace.monitoring_fixed_v1.aviation import (
    AviationProvider,
    FrozenFrequencyPredictor,
)
from disastertrace.monitoring_fixed_v1.support_bridge import native_slot_support
from disastertrace.monitoring_v1.api_ledger import ApiLedger, call_spec
from disastertrace.monitoring_v1.fixed_packet import information_id, messages
from disastertrace.monitoring_v1.slot_forecast import predict_from_slots
from disastertrace.monitoring_v1.spool_backend import digest, publish, read
from disastertrace.monitoring_v1.targets import canonical_hash


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out = args.out.absolute()
    out.mkdir(exist_ok=False)
    root = Path(__file__).resolve().parents[3]
    old = root / "plans/v9_followup_execution_20260914_01"
    v8 = root / "plans/v8_measurement_execution_20260913_01"
    sys.path.insert(0, str(old / "scripts"))
    from evidence_diagnostic import independent_reference

    criteria = {
        "ordinary_regions": ["new_york", "chicago", "denver"],
        "ordinary_cutoff_dates": ["2025-01-06", "2025-01-10"],
        "diagnostic_region": "denver",
        "diagnostic_cutoff_dates": ["2025-01-09"],
        "cutoff_UTC_hours": [0, 6, 12, 18],
        "lead_hours": 1,
        "thresholds_m": [1000, 5000],
        "conditions": ["common_only", "all_registered"],
        "formats": ["direct", "slotwise"],
        "as_of_minutes_before_cutoff": 10,
        "selection_uses_new_future_labels": False,
        "diagnostic_warning": "Denver Jan9 was selected in v9 using known results; separate diagnostic only",
        "scope": "exposed development calendar, finite fixed-packet E/F; not adaptive C1 or independent confirmation",
        "registered_before_packet_preparation": dt.datetime.now(
            dt.timezone.utc
        ).isoformat(),
    }
    publish(out / "SELECTION.json", criteria)
    for directory in ("policy", "bundles", "evaluator", "banks", "source", "api"):
        (out / directory).mkdir()
    tasks, references, packets, rejections, inputs = [], {}, {}, [], {}
    truth = {
        "supported": "true",
        "refuted": "false",
        "undetermined": "unknown",
        "inconsistent": "conflict",
    }
    for region in criteria["ordinary_regions"]:
        dataset = v8 / "regional_calendar_extension_01" / region / "dataset_v2"
        bank_path = old / "reports/regional_baselines_01" / region / "BANK.json"
        inputs[str(bank_path)] = digest(bank_path)
        bank = read(bank_path)
        publish(out / "banks" / (region + ".json"), bank)
        provider = AviationProvider(dataset, bank)
        candidates = []
        for opportunity in provider.opportunities.values():
            when = dt.datetime.fromtimestamp(
                opportunity["cutoff"] / 1e6, dt.timezone.utc
            )
            day = when.date().isoformat()
            cohort = (
                "ordinary" if day in criteria["ordinary_cutoff_dates"] else "diagnostic"
            )
            if cohort == "diagnostic" and (
                region != criteria["diagnostic_region"]
                or day not in criteria["diagnostic_cutoff_dates"]
            ):
                continue
            if (
                when.hour not in criteria["cutoff_UTC_hours"]
                or when.minute != 0
                or opportunity["lead_hours"] != 1
                or opportunity["threshold_m"] not in criteria["thresholds_m"]
            ):
                continue
            candidates.append((cohort, day, opportunity))
        outcome_cache = {}
        for cohort, day, opportunity in sorted(
            candidates, key=lambda x: x[2]["opportunity_id"]
        ):
            oid = opportunity["opportunity_id"]
            case_name = region + "__" + day + "__" + str(opportunity["threshold_m"])
            case = (
                old
                / ("api_pilot_01" if cohort == "ordinary" else "api_rare_pilot_01")
                / case_name
            )
            if case_name not in outcome_cache:
                inputs[str(case / "OUTCOMES.json")] = digest(case / "OUTCOMES.json")
                outcome_cache[case_name] = {
                    r["opportunity_id"]: r for r in read(case / "OUTCOMES.json")
                }
            for condition in criteria["conditions"]:
                try:
                    bundle = provider.freeze(
                        oid, condition, as_of=opportunity["cutoff"] - 600_000_000
                    )
                    view = bundle.policy_view()
                    ref = independent_reference(view)
                    support = native_slot_support(bundle)
                    assert ref["fact_truth"] == truth[support["status"]]
                    assert ref["slots"] == {
                        s["query_id"]: truth[s["status"]] for s in support["slots"]
                    }
                    content = view["baseline"]["content"]
                    queries = content["E_question"]["query_ids"]
                    acquired = [a["content"]["query_id"] for a in view["assets"]]
                    forecast, details = FrozenFrequencyPredictor(
                        bank
                    ).predict_with_details(bundle)
                    native_slots_f = predict_from_slots(
                        bank,
                        content["legacy_target_contract"],
                        content["native_taf"],
                        queries,
                        acquired,
                        ref["slots"],
                    )
                    assert native_slots_f["probability"] == forecast.value
                except Exception as exc:  # noqa: BLE001 - Every rejected source packet is retained separately.
                    rejections.append(
                        {
                            "opportunity_id": oid,
                            "condition": condition,
                            "error_type": type(exc).__name__,
                        }
                    )
                    continue
                pid = canonical_hash([region, oid, condition])[:24]
                publish(out / "bundles" / (pid + ".json"), bundle.to_dict())
                packets[pid] = {
                    "region": region,
                    "cohort": cohort,
                    "day": day,
                    "opportunity_id": oid,
                    "condition": condition,
                    "bundle_sha256": bundle.bundle_hash,
                    "query_ids": queries,
                    "acquired_ids": acquired,
                    "information_id": information_id(view),
                    "threshold": opportunity["threshold_m"],
                    "cutoff": opportunity["cutoff"],
                    "target_id": opportunity["target_id"],
                    "station": view["target"]["entity"],
                }
                references[pid] = {
                    **ref,
                    "future": outcome_cache[case_name][oid],
                    "FOLLOW": view["baseline"]["forecast"]["value"],
                    "native_program": forecast.value,
                    "native_program_details": details,
                    "native_slots_f": native_slots_f,
                    "reference_kind": "disclosed_product_fact",
                }
                for reasoning in criteria["formats"]:
                    cid = canonical_hash([pid, reasoning])[:24]
                    policy = {"call_id": cid, "messages": messages(view, reasoning)}
                    publish(out / "policy" / (cid + ".json"), policy)
                    tasks.append(
                        {
                            **packets[pid],
                            "packet_id": pid,
                            "call_id": cid,
                            "representation": "full_bundle",
                            "reasoning": reasoning,
                            "policy_sha256": digest(out / "policy" / (cid + ".json")),
                        }
                    )
        for sub in ("public", "environment"):
            for p in (dataset / sub).glob("*.json"):
                inputs[str(p)] = digest(p)
    publish(out / "evaluator/REFERENCES.json", references)
    publish(out / "evaluator/REJECTIONS.json", rejections)
    publish(out / "INPUTS.json", inputs)
    publish(out / "PACKETS.json", packets)
    if rejections or len(packets) != 336 or len(tasks) != 672:
        publish(
            out / "PREPARATION_FAILED.json",
            {"packets": len(packets), "tasks": len(tasks), "rejected": len(rejections)},
        )
        raise ValueError(
            "Fixed calendar eligibility differs; retain failures before revising design"
        )
    for module in ("monitoring_v1", "monitoring_fixed_v1", "forecast_task"):
        shutil.copytree(
            root / "disastertrace-starter/src/disastertrace" / module,
            out / "source/disastertrace" / module,
            ignore=shutil.ignore_patterns("__pycache__"),
        )
    (out / "source/disastertrace/__init__.py").write_text(
        '"""Frozen v10 packet experiment."""\n'
    )
    for name in (
        "prepare_fixed_packet.py",
        "run_fixed_packet_api.py",
        "score_fixed_packet.py",
    ):
        shutil.copyfile(Path(__file__).parent / name, out / "source" / name)
    shutil.copyfile(
        old / "scripts/evidence_diagnostic.py", out / "source/evidence_diagnostic.py"
    )
    shutil.copyfile(
        old / "model_catalog/probe_01/deepseek_pricing.body",
        out / "source/PRICING.html",
    )
    specs, api_models = [], ["deepseek-flash", "deepseek-v4-pro"]
    compatibility = [
        {"role": "user", "content": 'Return only the JSON object {"ready":true}.'}
    ]
    publish(out / "api/COMPATIBILITY_REQUEST.json", compatibility)
    for model in api_models:
        specs.append(call_spec(model + "/compatibility", compatibility, model))
        for task in tasks:
            specs.append(
                call_spec(
                    model + "/" + task["call_id"],
                    read(out / "policy" / (task["call_id"] + ".json"))["messages"],
                    model,
                )
            )
    deadline = dt.datetime(2026, 9, 14, 22, 0, tzinfo=dt.timezone.utc)
    ledger = ApiLedger.create(
        out / "api/ledger",
        specs,
        limit_nanodollars=40_000_000_000,
        max_calls=len(specs),
        deadline_wall_ns=int(deadline.timestamp() * 1e9),
    )
    frozen = {
        str(p.relative_to(out)): digest(p)
        for name in ("policy", "bundles", "evaluator", "banks", "source")
        for p in (out / name).rglob("*")
        if p.is_file()
    }
    for name in (
        "SELECTION.json",
        "INPUTS.json",
        "PACKETS.json",
        "api/ledger/contract.json",
        "api/COMPATIBILITY_REQUEST.json",
    ):
        frozen[name] = digest(out / name)
    plan = {
        "schema": "disastertrace.fixed_packet_EF.v1",
        "tasks": tasks,
        "files": frozen,
        "underlying_opportunities": 168,
        "ordinary_opportunities": 144,
        "diagnostic_opportunities": 24,
        "api_models": api_models,
        "api_benchmark_calls": 1344,
        "api_compatibility_calls": 2,
        "api_workers": 16,
        "new_local_model": "Qwen/Qwen3.8-27B",
        "local_benchmark_calls": 672,
        "local_compatibility_calls": 4,
        "api_max_fee_usd": 40,
        "api_escrow_upper_nanodollars": sum(r["reserved_nanodollars"] for r in specs),
        "max_tokens": 512,
        "input_token_cap": 32768,
        "thinking": "disabled",
        "temperature": 0,
        "retries": 0,
        "last_worker_time": deadline.isoformat(),
        "confirmation_opened": False,
        "statistical_unit": "paired exposed opportunity; no independent confirmation claim",
        "primary_F": "all registered opportunities with FOLLOW fallback on invalid/failed/non-EOS answers",
        "derived_F": "model slot estimates through the unchanged frozen count map; no aggregate consumed",
        "coherence": "secondary equal-weight isotonic CDF projection, every method, identical information only",
        "timing": "fixed packets at cutoff minus 10 min; observed call latency reported, not full session acquisition",
        "E_state_counts_per_format": dict(
            Counter(r["fact_truth"] for r in references.values())
        ),
        "frozen_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    publish(out / "PLAN.json", plan)
    publish(
        out / "PREFLIGHT.json",
        {
            "passed": True,
            "two_E_reducers_agree": len(packets),
            "native_slots_equal_original_fuser": len(packets),
            "rejections": 0,
            "ledger_sha256": ledger.contract_sha256,
            "plan_sha256": digest(out / "PLAN.json"),
        },
    )
    print(
        json.dumps(
            {
                k: plan[k]
                for k in (
                    "underlying_opportunities",
                    "api_benchmark_calls",
                    "local_benchmark_calls",
                    "api_escrow_upper_nanodollars",
                    "E_state_counts_per_format",
                )
            }
        )
    )


if __name__ == "__main__":
    main()
