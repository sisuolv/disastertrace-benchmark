"""Build an all-calendar source-bound airport development cohort."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import shutil
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from disastertrace.monitoring_v1.providers.aviation import parse_metar, parse_taf
from disastertrace.monitoring_v1.providers.taf_timeline import unavailable_product
from disastertrace.monitoring_v1.support import classify
from disastertrace.monitoring_v1.targets import Opportunity, TargetSpec, utc_us

ROOT = Path(__file__).resolve().parent
HOUR = 3_600_000_000
MINUTE = 60_000_000


def stamp(us):
    return datetime.fromtimestamp(us / 1_000_000, timezone.utc).isoformat().replace("+00:00", "Z")


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")


def capture(directory, ident, bindings):
    directory = directory.resolve()
    path = directory / (ident + ".body")
    receipt_path = directory / (ident + ".json")
    receipt = json.loads(receipt_path.read_text())
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if (not receipt.get("complete") or receipt.get("curl_exit", 0) != 0 or receipt["http_status"] != 200
            or digest != receipt["sha256"] or len(raw) != receipt["bytes"]):
        raise ValueError("Unverified source capture: " + ident)
    bindings[ident] = {"path": str(path.relative_to(ROOT)), "sha256": digest, "bytes": len(raw),
                       "receipt_path": str(receipt_path.relative_to(ROOT)),
                       "receipt_sha256": hashlib.sha256(receipt_path.read_bytes()).hexdigest()}
    return raw, receipt


def csv_rows(raw):
    reader = csv.reader(io.StringIO(raw.decode("utf-8")), strict=True)
    header = next(reader)
    if len(set(header)) != len(header):
        raise ValueError("Duplicate CSV columns")
    rows = []
    for values in reader:
        if len(values) != len(header):
            raise ValueError("CSV field count mismatch")
        rows.append(dict(zip(header, values), _line=reader.line_num))
    return rows


def build(contract_path, metar_directory, taf_directory, output):
    contract = json.loads(contract_path.read_text())
    output.mkdir(parents=True, exist_ok=False)
    code_files = [Path(__file__).resolve(), Path(parse_taf.__code__.co_filename).resolve(), Path(unavailable_product.__code__.co_filename).resolve()]
    implementation = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in code_files}
    snapshot = output / "implementation"
    package = snapshot / "disastertrace/monitoring_v1"
    (package / "providers").mkdir(parents=True)
    (snapshot / "disastertrace/__init__.py").write_text('"""Frozen data-builder package."""\n')
    original_package = Path(parse_taf.__code__.co_filename).resolve().parents[1]
    for name in ("__init__.py", "targets.py", "support.py", "providers/__init__.py", "providers/aviation.py", "providers/taf_timeline.py"):
        shutil.copyfile(original_package / name, package / name)
    shutil.copyfile(Path(__file__).resolve(), snapshot / "build_regional.py")
    sources, failures, reports, products = {}, [], [], []
    unparsed_products = []
    by_slot = defaultdict(list)
    for station in contract["stations"]:
        source_id = "metar-routine-" + station
        raw, _ = capture(metar_directory, source_id, sources)
        for row in csv_rows(raw):
            record = {"source_id": source_id, "source_line": row["_line"], "archive_valid": row["valid"],
                      "archive_station": row["station"], "raw": row["metar"]}
            try:
                parsed = parse_metar(row["metar"], observation_time=row["valid"].replace(" ", "T") + ":00Z", report_type="routine")
                if parsed.station != station or row["station"] not in {station, station[1:]}:
                    raise ValueError("Station join mismatch")
                slot_start = parsed.observation_time // HOUR * HOUR
                record.update(station=station, observation_time=parsed.observation_time,
                              visibility=None if parsed.visibility is None else parsed.visibility.to_dict(),
                              temperature_c=parsed.temperature_c, weather=list(parsed.weather),
                              quality_flags=list(parsed.quality_flags), decoded=True, slot_start=slot_start)
                by_slot[(station, slot_start)].append((record, parsed))
            except (ValueError, KeyError) as exc:
                record.update(decoded=False, failure=str(exc))
                failures.append({"kind": "metar_decode", **record})
            reports.append(record)
    manifest = json.loads((taf_directory / "MANIFEST.json").read_text())
    if manifest["attempted"] != manifest["planned"]:
        raise ValueError("Native TAF acquisition has not completed")
    for row in manifest["rows"]:
        source_id = row["id"]
        raw, metadata = None, None
        try:
            raw, receipt = capture(taf_directory, source_id, sources)
            metadata = receipt["catalog_metadata"]
            parsed = parse_taf(raw.decode(), station=metadata["station"],
                               archive_issue=metadata["issued_at"].replace(" ", "T") + ":00Z")
            products.append((source_id, parsed))
        except (ValueError, KeyError) as exc:
            failures.append({"kind": "taf_decode", "source_id": source_id, "failure": str(exc)})
            if raw is not None and metadata is not None:
                try:
                    unparsed_products.append(unavailable_product(raw.decode(), station=metadata["station"],
                        archive_issue=metadata["issued_at"].replace(" ", "T") + ":00Z", source_id=source_id, reason=str(exc)))
                except (ValueError, UnicodeDecodeError) as envelope_error:
                    failures.append({"kind": "taf_envelope_unresolved", "source_id": source_id, "failure": str(envelope_error)})
    thresholds = contract["thresholds_m"]
    cutoffs = range(utc_us(contract["cutoff_start"]), utc_us(contract["cutoff_end_exclusive"]), HOUR)
    targets, opportunities, outcomes, baseline_candidates, evidence_pairs = {}, [], {}, [], []
    queries, query_results = {}, {}
    for cutoff in cutoffs:
        for station in contract["stations"]:
            for lead in contract["lead_hours"]:
                start = cutoff + lead * HOUR
                slot = by_slot[(station, start)]
                unique = {r["raw"]: (r, p) for r, p in slot}
                for threshold in thresholds:
                    target_id = f"{station}-{stamp(start)}-vis-lt-{threshold}m"
                    opportunity_id = target_id + "-cutoff-" + stamp(cutoff)
                    target = TargetSpec(target_id=target_id, entity=station, variable="visibility", units="m",
                        event_operator="lt", threshold=threshold, spatial_support="station:" + station,
                        physical_start=start, physical_end=start + HOUR, report_policy="iem_routine_unique_hour.v1",
                        outcome_kind="archived_native_report", temporal_semantics="future_physical")
                    opportunity = Opportunity(opportunity_id, target, cutoff)
                    targets[target_id] = asdict(target)
                    opportunities.append({"opportunity_id": opportunity_id, "target_id": target_id, "cutoff": cutoff,
                                          "lead_hours": lead, "threshold_m": threshold})
                    status, y, reference = "missing_routine_slot", None, []
                    if len(unique) > 1:
                        status = "ambiguous_routine_slot_or_revision"
                    elif len(unique) == 1:
                        record, parsed = next(iter(unique.values()))
                        reference = [{"source_id": record["source_id"], "source_line": record["source_line"]}]
                        if parsed.visibility is None or "nil_report" in parsed.quality_flags:
                            status = "missing_native_visibility"
                        else:
                            support = classify(parsed.visibility, "lt", threshold)
                            status = "settled_final_archived_report" if support in {"supported", "refuted"} else "censored_straddles_threshold"
                            y = 1 if support == "supported" else 0 if support == "refuted" else None
                    outcomes[target_id] = {"target_id": target_id, "outcome": y, "status": status, "references": reference,
                                           "physical_start": start, "physical_end": start + HOUR,
                                           "outcome_reference_kind": "final_archived_routine_report_not_continuous_physical_truth"}
                    for source_id, product in products:
                        if product.station != station or product.issued_at + 2 * MINUTE > cutoff:
                            continue
                        try:
                            projection = product.project(start, start + HOUR)
                        except ValueError:
                            continue
                        baseline_candidates.append({"opportunity_id": opportunity_id, "target_id": target_id,
                            "source_id": source_id, "issued_at": product.issued_at, "available_at": product.issued_at + 2 * MINUTE,
                            "valid_until": min(product.valid_end, start), "projection": projection,
                            "raw": product.raw, "amendment_kind": product.amendment_kind,
                            "probability": None, "probability_status": "awaiting_separate_development_calibration"})
                    for product in unparsed_products:
                        if (product["station"] == station and product["issued_at"] + 2 * MINUTE <= cutoff
                                and product["valid_start"] <= start and start + HOUR <= product["valid_end"]):
                            baseline_candidates.append({"opportunity_id": opportunity_id, "target_id": target_id,
                                "source_id": product["source_id"], "issued_at": product["issued_at"],
                                "available_at": product["issued_at"] + 2 * MINUTE,
                                "valid_until": min(product["valid_end"], start), "raw": product["raw"],
                                "amendment_kind": product["amendment_kind"], "projection_status": "unavailable",
                                "projection": {"status": "unparsed", "reason": product["reason"],
                                    "native_valid_start": product["valid_start"], "native_valid_end": product["valid_end"],
                                    "raw_sha256": hashlib.sha256(product["raw"].encode()).hexdigest()},
                                "probability": None, "probability_status": "frozen_fallback_required_not_a_valid_TAF_probability"})
                    # At whole-hour cutoffs, the immediately preceding slot may
                    # still be in the declared 5-minute publication tail.
                    evidence_slot = cutoff - 2 * HOUR
                    relevant = []
                    for neighbor in contract["stations"]:
                        if neighbor == station:
                            continue
                        query_id = f"routine-{neighbor}-{stamp(evidence_slot)}"
                        relevant.append(query_id)
                        queries[query_id] = {"query_id": query_id, "station": neighbor, "slot_start": evidence_slot,
                            "slot_end": evidence_slot + HOUR, "available_at": evidence_slot + HOUR + 5 * MINUTE,
                            "catalog_kind": "registered_routine_slot_not_payload_existence", "upper_bytes": 2048,
                            "archive_cost": {"requests": 1, "bytes": 2048, "tokens": 0, "compute_ms": 100},
                            "latency_ms": 1000}
                        values = by_slot[(neighbor, evidence_slot)]
                        unique_values = {r["raw"]: (r, p) for r, p in values}
                        qstatus, disclosed = "missing", []
                        if len(unique_values) > 1:
                            qstatus = "conflicting_or_multiple_routine_reports"
                        elif len(unique_values) == 1:
                            record, parsed = next(iter(unique_values.values()))
                            if "correction_chronology_unproven" in parsed.quality_flags:
                                qstatus = "correction_chronology_unproven"
                            elif parsed.visibility is not None:
                                qstatus = "disclosed_product_fact"
                                disclosed = [record]
                            else:
                                qstatus = "missing_native_visibility"
                        query_results[query_id] = {"query_id": query_id, "status": qstatus, "reports": disclosed,
                            "reference_kind": "product_label", "support_assumption": "product_exact",
                            "visible_information_scope": "policy_after_query", "support_rule_version": "native_metar_interval.v1"}
                    evidence_pairs.append({"opportunity_id": opportunity_id, "e_predicate": "any_registered_neighbor_slot_below_threshold",
                                           "threshold_m": threshold, "query_ids": relevant, "deadline": cutoff,
                                           "F_target_id": target_id, "mode": "E_certified"})
    all_products = [{"source_id": source, "station": product.station, "issued_at": product.issued_at,
                     "valid_start": product.valid_start, "valid_end": product.valid_end, "status": product.status,
                     "amendment_kind": product.amendment_kind, "clause_operators": [c.operator for c in product.clauses]}
                    for source, product in products] + unparsed_products
    latest = {}
    for candidate in baseline_candidates:
        key = candidate["opportunity_id"]
        if key not in latest or (candidate["issued_at"], candidate["source_id"]) > (latest[key]["issued_at"], latest[key]["source_id"]):
            latest[key] = candidate
    # Canceled/NIL revisions cannot silently expose an older active product.
    for opportunity in opportunities:
        target = targets[opportunity["target_id"]]
        visible_products = [p for p in all_products if p["station"] == target["entity"] and p["issued_at"] + 2 * MINUTE <= opportunity["cutoff"]
            and (p["valid_start"] is None or p["valid_start"] <= target["physical_start"])
            and (p["valid_end"] is None or target["physical_end"] <= p["valid_end"])]
        if visible_products:
            last = max(visible_products, key=lambda p: (p["issued_at"], p["source_id"]))
            if last["status"] in {"nil", "canceled"}:
                latest.pop(opportunity["opportunity_id"], None)
    counts = {}
    for threshold in thresholds:
        subset = [o for o in opportunities if o["threshold_m"] == threshold]
        statuses = Counter(outcomes[o["target_id"]]["status"] for o in subset)
        counts[str(threshold)] = {"opportunities": len(subset), "settlement": dict(statuses),
            "positive_opportunities": sum(outcomes[o["target_id"]]["outcome"] == 1 for o in subset),
            "unique_positive_targets": len({o["target_id"] for o in subset if outcomes[o["target_id"]]["outcome"] == 1}),
            "complete_native_taf_opportunities": sum(o["opportunity_id"] in latest and latest[o["opportunity_id"]].get("projection_status") != "unavailable" for o in subset),
            "unparsed_latest_taf_fallback_opportunities": sum(o["opportunity_id"] in latest and latest[o["opportunity_id"]].get("projection_status") == "unavailable" for o in subset)}
    report = {"built_at": datetime.now(timezone.utc).isoformat(), "stage": "real_program_inputs_not_model_results",
        "contract_sha256": hashlib.sha256(contract_path.read_bytes()).hexdigest(), "metar_rows": len(reports),
        "decoded_metar_rows": sum(r["decoded"] for r in reports), "native_taf_bulletins_decoded": len(products),
        "unparsed_native_taf_envelopes_preserved": len(unparsed_products),
        "taf_operators": dict(Counter(c.operator for _, p in products for c in p.clauses)),
        "station_report_counts": dict(Counter(r.get("station", "unresolved") for r in reports)),
        "targets": len(targets), "opportunities": len(opportunities), "query_pool": len(queries),
        "by_threshold": counts, "query_statuses": dict(Counter(q["status"] for q in query_results.values())),
        "failures": failures, "independent_event_count": None, "confirmation": False,
        "image_join_verified": False, "historical_first_seen_verified": False,
        "probability_baseline_calibrated": False, "source_registry_replaced": False,
        "implementation_sha256": implementation}
    if implementation != {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in code_files}:
        raise ValueError("Implementation changed while building")
    write(output / "SOURCES.json", sources)
    write(output / "REGIONAL_JOIN_AUDIT.json", report)
    write(output / "public/TARGETS.json", list(targets.values()))
    write(output / "public/OPPORTUNITIES.json", opportunities)
    write(output / "public/QUERY_CATALOG.json", list(queries.values()))
    write(output / "public/E_F_PAIRS.json", evidence_pairs)
    write(output / "environment/BASELINE_CANDIDATES.json", baseline_candidates)
    write(output / "environment/LATEST_BASELINES.json", list(latest.values()))
    write(output / "environment/QUERY_RESULTS.json", list(query_results.values()))
    write(output / "environment/NATIVE_PRODUCT_INDEX.json", all_products)
    write(output / "private/OUTCOMES.json", list(outcomes.values()))
    write(output / "private/DECODED_REPORTS.json", reports)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=ROOT / "REGIONAL_CONTRACT.json")
    parser.add_argument("--metar", type=Path, default=ROOT / "captures_03")
    parser.add_argument("--taf", type=Path, default=ROOT / "captures_04")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, default=ROOT)
    args = parser.parse_args()
    ROOT = args.source_root.resolve()
    build(args.contract, args.metar, args.taf, args.output)
