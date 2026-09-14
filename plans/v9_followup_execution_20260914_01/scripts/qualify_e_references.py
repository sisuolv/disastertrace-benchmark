"""Qualify all eligible native E views, preserving unavailable-baseline exclusions."""

from pathlib import Path
import json

from disastertrace.monitoring_fixed_v1.aviation import AviationProvider
from disastertrace.monitoring_fixed_v1.support_bridge import native_slot_support
from disastertrace.monitoring_v1.spool_backend import publish, read
from evidence_diagnostic import independent_reference, messages

ROOT = Path(__file__).resolve().parents[1]
V8 = ROOT.parent / "v8_measurement_execution_20260913_01"
OUT = ROOT / "reports/e_reference_qualification_02"
TRUTH = {"supported": "true", "refuted": "false", "undetermined": "unknown", "inconsistent": "conflict"}


def main():
    OUT.mkdir(exist_ok=False)
    summaries = []
    exclusions = []
    for region in ["bay", "new_york", "chicago", "denver"]:
        dataset = V8 / "calendar_extension_01/dataset_v2_complete_02" if region == "bay" else V8 / "regional_calendar_extension_01" / region / "dataset_v2"
        provider = AviationProvider(dataset, read(V8/"contracts/BANK.json"))
        checked = candidates = largest = excluded = 0
        for opportunity in provider.opportunities.values():
            if opportunity["lead_hours"] != 1:
                continue
            for condition in ["common_only", "fixed_one", "all_registered"]:
                candidates += 1
                try:
                    bundle = provider.freeze(opportunity["opportunity_id"], condition,
                                             as_of=opportunity["cutoff"] - 600_000_000)
                except ValueError as error:
                    if not str(error).startswith("No usable current native baseline:"):
                        raise
                    exclusions.append({"region": region, "opportunity_id": opportunity["opportunity_id"],
                        "condition": condition, "reason": str(error), "scope": "static E view only; no continuous F opportunity deletion"})
                    excluded += 1
                    continue
                ref, native = independent_reference(bundle.policy_view()), native_slot_support(bundle)
                assert ref["fact_truth"] == TRUTH[native["status"]]
                assert ref["slots"] == {s["query_id"]: TRUTH[s["status"]] for s in native["slots"]}
                msg = messages(bundle.policy_view(), "full_bundle", "slotwise")
                upper = sum(len(m["content"].encode()) for m in msg) + 4096
                assert upper <= 32768
                largest = max(largest, upper)
                checked += 1
        row = {"region": region, "candidates": candidates, "native_reference_agreements": checked,
               "unavailable_baseline_views": excluded, "max_input_byte_allowance": largest}
        publish(OUT/(region+".json"), row)
        summaries.append(row)
        print(json.dumps(row), flush=True)
    publish(OUT/"EXCLUSIONS.json", exclusions)
    publish(OUT/"VALIDATION.json", {"passed": True, "summaries": summaries, "model_calls": 0,
        "engineering_dispatch_and_direct_equivalence": "../api_qualification_01",
        "bank_scope": "old bank borrowed for native interpretation and transport qualification only"})


if __name__ == "__main__":
    main()
