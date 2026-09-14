"""Check whether the existing final DWD archive can prove historical input availability."""

import argparse
import csv
import datetime as dt
import io
import shutil
import zipfile
from pathlib import Path

from disastertrace.monitoring_v1.spool_backend import digest, publish, read


def main(out):
    root = Path(__file__).resolve().parents[3]
    out.mkdir(exist_ok=False)
    shutil.copyfile(__file__, out / "EXECUTED_SOURCE.py")
    source = root / "plans/v8_measurement_execution_20260913_01/temperature_daily_reference_01"
    archive = source / "tageswerte_KL_00460_19510101_20251231_hist.zip"
    original = root / "plans/v9_followup_execution_20260914_01/temperature_fullcalendar_01"
    with zipfile.ZipFile(archive) as zipped:
        member = "produkt_klima_tag_19510101_20251231_00460.txt"
        raw = zipped.read(member).decode("latin1")
    records = {}
    for row in csv.DictReader(io.StringIO(raw), delimiter=";"):
        row = {k.strip(): v.strip() for k, v in row.items()}
        day = dt.datetime.strptime(row["MESS_DATUM"], "%Y%m%d").date().isoformat()
        records[day] = row
    archive_sha = digest(archive)
    missing_references = 0
    references, origins, bindings = {}, {}, {str(archive): archive_sha}
    for case in sorted(original.glob("20??-??")):
        policies, outcomes = read(case / "POLICY.json")["rows"], read(case / "OUTCOMES.json")
        for name in ("POLICY.json", "OUTCOMES.json"):
            bindings[str(case / name)] = digest(case / name)
        for policy in policies:
            origins[policy["origin"]] = policy["cutoff"]
        for outcome in outcomes:
            assert outcome["source_sha256"] == archive_sha
            for ref in outcome["references"]:
                if ref is None:
                    missing_references += 1
                    continue
                row = records[ref["date"]]
                for field, value in ref["values_C"].items():
                    assert (None if row[field] == "-999" else float(row[field])) == value
                assert ref["native_QN_4"] == row["QN_4"]
                references[ref["date"]] = ref
    candidates = []
    for origin, cutoff in sorted(origins.items()):
        date = dt.datetime.fromtimestamp(origin / 1e6, dt.timezone.utc).date() - dt.timedelta(days=1)
        end = dt.datetime.combine(date + dt.timedelta(days=1), dt.time(), tzinfo=dt.timezone.utc)
        row = records.get(date.isoformat())
        reference = references.get(date.isoformat(), {})
        historical = reference.get("historical_available_at")
        candidates.append({"origin": origin, "cutoff": cutoff, "observation_date": date.isoformat(),
            "physical_window_completed": int(end.timestamp()*1e6) <= cutoff,
            "raw_archive_record_exists": row is not None,
            "minimum_C": None if row is None or row["TNK"] == "-999" else float(row["TNK"]),
            "maximum_C": None if row is None or row["TXK"] == "-999" else float(row["TXK"]),
            "historical_version_available_at": historical,
            "strict_historical_E_admitted": historical is not None and historical <= cutoff,
            "final_archive_revision_is_not_historical_first_seen": True})
    publish(out / "CANDIDATES.json", candidates)
    publish(out / "SOURCE_HASHES.json", bindings)
    publish(out / "RESULT.json", {"audit_passed": True, "raw_download_available": True,
        "native_reference_days_rechecked": len(references), "past_observation_candidates": len(candidates),
        "unresolved_reference_entries_retained": missing_references,
        "physical_windows_completed": sum(c["physical_window_completed"] for c in candidates),
        "native_records_present": sum(c["raw_archive_record_exists"] for c in candidates),
        "strict_historical_E_admitted": sum(c["strict_historical_E_admitted"] for c in candidates),
        "supplementary_data_gate": "NOT_QUALIFIED_FOR_STRICT_HISTORICAL_AS_OF",
        "reason": "The current final historical DWD archive verifies values and valid days, but has no bound historical release/revision timestamp per input.",
        "allowed_current_role": "provider-bound final outcomes, or explicitly declared archive-availability sensitivity study",
        "required_next_evidence": ["native contemporaneous report archive with issue/version timestamps",
            "or captured product first-seen and maturity for prospective monitoring"],
        "new_model_calls": 0, "new_downloads": 0, "new_C1_result": False, "confirmation_opened": False})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    main(args.out.absolute())
