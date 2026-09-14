"""Product-content E tasks on original CNRFC files, without a physical flood F label."""

import csv
import datetime as dt
import hashlib
import io
import json
import math
import zipfile
from fractions import Fraction
from pathlib import Path

from disastertrace.monitoring_v1.reachability import Goal, Query, solve_joint, validate_witness
from disastertrace.monitoring_v1.resources import Cost
from disastertrace.monitoring_v1.support import EvidenceFact, Interval, classify, public_support

ROOT = Path(__file__).resolve().parents[1]
PRIOR = ROOT.parents[1] / "plans/v7_execution_20260913/hydrology"
OUT = ROOT / "hydro_e_extension_01"


def load(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(name, value):
    with (OUT / name).open("x") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")


def epoch(value):
    return round(value.timestamp() * 1_000_000)


def read_native(path, expected):
    if digest(path) != expected:
        raise ValueError("Inherited native archive hash changed")
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None or len(archive.namelist()) != 1:
            raise ValueError("One intact native CSV member required")
        name = archive.namelist()[0]
        raw = archive.read(name)
    rows = list(csv.reader(io.StringIO(raw.decode())))
    columns = [i for i, name in enumerate(rows[0]) if name == "SCOC1"]
    if rows[0][0] != "GMT" or len(columns) != 43 or {rows[1][i] for i in columns} != {"QINE"}:
        raise ValueError("Expected native 43-column SCOC1/QINE identity")
    if len(columns) != len(rows[0]) - 1:
        raise ValueError("This E task requires the station-specific hourly file")
    issued = dt.datetime.strptime(name[:10], "%Y%m%d%H").replace(tzinfo=dt.timezone.utc)
    values = {}
    for line, row in enumerate(rows[2:], 3):
        valid = dt.datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S").replace(tzinfo=dt.timezone.utc)
        vector = [Fraction(row[i]) for i in columns]
        if len(row) != 44 or any(v < 0 for v in vector) or valid in values:
            raise ValueError("Malformed or duplicate native row")
        mean = sum(vector) / 43
        values[epoch(valid)] = {
            "native_line": line,
            "raw_csv_row": ",".join(row),
            "mean": mean,
            "vector": vector,
        }
    if len(values) != 721 or min(values) != epoch(issued):
        raise ValueError("Native hourly horizon changed")
    return {
        "id": name,
        "archive": str(path),
        "sha256": expected,
        "csv_sha256": hashlib.sha256(raw).hexdigest(),
        "issued_at": epoch(issued),
        "available_at": epoch(issued + dt.timedelta(hours=3)),
        "rows": values,
    }


def e_support(products, target_time, at, acquired):
    # The public revision catalog determines the required version, even if unread.
    eligible = [p for p in products if p["available_at"] <= at]
    if not eligible:
        return "undetermined", Interval(0, math.inf), None
    newest = max(p["issued_at"] for p in eligible)
    current = [p for p in eligible if p["issued_at"] == newest]
    if len({p["csv_sha256"] for p in current}) != 1:
        return "inconsistent", None, None
    product = current[0]
    if (
        product["id"] not in acquired
        or acquired[product["id"]] > at
        or target_time not in product["rows"]
    ):
        return "undetermined", Interval(0, math.inf), product["id"]
    exact = product["rows"][target_time]["mean"]
    approximate = float(exact)
    if Fraction.from_float(approximate) == exact:
        interval = Interval(approximate, approximate)
    else:
        interval = Interval(
            math.nextafter(approximate, -math.inf), math.nextafter(approximate, math.inf)
        )
    fact = EvidenceFact(
        "SCOC1:QINE:" + str(target_time),
        newest,
        product["available_at"],
        "native_column_mean",
        "native_QINE_table_value",
        interval,
        "product_label",
        "product_exact",
        "policy",
        "CNRFC_QINE_rational_column_mean.v1",
    )
    support = public_support([fact], fact.field, fact.units, Interval(0, math.inf), at)
    status = classify(support, "ge", 5.0)
    expected = "supported" if exact >= 5 else "refuted"
    if status != expected:
        raise ValueError("Floating support does not certify the exact native rational predicate")
    return status, support, product["id"]


def main():
    OUT.mkdir(exist_ok=False)
    manifest = {r["path"]: r["sha256"] for r in load(PRIOR / "FILES.sha256.json")["files"]}
    save(
        "E_TASK_CARD.json",
        {
            "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "hazard": "H08",
            "reference_kind": "product_label",
            "support_assumption": "product_exact",
            "visible_information_scope": "policy",
            "support_rule_version": "CNRFC_QINE_rational_column_mean.v1",
            "E_predicate": "Arithmetic mean of the 43 raw QINE columns in the latest lawful station-specific product at the specified valid time is at least 5 native table units.",
            "interpretation": "An exact fact about forecast product contents; not a probability or future physical discharge observation.",
            "member_identity": "Native CSV column positions; no historical member-year mapping or probability weights inferred.",
            "unit_evidence": "Current official CNRFC UI documents kcfs; historical physical equivalence remains unqualified.",
            "calendar": "All 697 common native valid timestamps across the already acquired 20240101 and 20240102 cycles.",
            "availability": "nominal cycle plus3h declared scenario; not historical first-seen proof",
            "query": "one entire original hourly archive, shared across targets after charging its transfer",
            "recipe_subset": "three original target valid times 20240102/03/04 12Z, no label-based selection",
            "F_numeric_qualified": False,
            "flood_stage_qualified": False,
            "inundation_qualified": False,
            "model_calls": 0,
            "new_external_downloads": 0,
        },
    )
    products = [
        read_native(
            PRIOR / ("raw/cnrfc_hourly_" + date + ".zip"),
            manifest["raw/cnrfc_hourly_" + date + ".zip"],
        )
        for date in ("20240101", "20240102")
    ]
    old, new = products
    common = sorted(set(old["rows"]) & set(new["rows"]))
    if len(common) != 697:
        raise ValueError("Previously verified overlap changed")
    at = new["available_at"] + 10_000_000
    rows = []
    for target in common:
        cases = {}
        for name, instant, read in [
            ("old_current_and_read", new["available_at"] - 1, {old["id"]: old["available_at"]}),
            ("new_current_unread", at, {old["id"]: old["available_at"]}),
            ("new_current_read", at, {new["id"]: new["available_at"] + 5_000_000}),
            (
                "old_delivered_after_new",
                at,
                {new["id"]: new["available_at"] + 5_000_000, old["id"]: at - 1},
            ),
        ]:
            status, support, current = e_support(products, target, instant, read)
            cases[name] = {
                "E": status,
                "support": None if support is None else support.to_dict(),
                "current_product": current,
                "lawfully_acquired": read,
            }
        if (
            cases["new_current_unread"]["E"] != "undetermined"
            or cases["old_delivered_after_new"]["E"] != cases["new_current_read"]["E"]
        ):
            raise ValueError("Stale version affected current support")
        rows.append(
            {
                "target_native_valid_time": target,
                "cases": cases,
                "evaluator_reference": {
                    p["id"]: {
                        "raw_csv_row": p["rows"][target]["raw_csv_row"],
                        "native_line": p["rows"][target]["native_line"],
                        "mean_rational": str(p["rows"][target]["mean"]),
                        "archive_sha256": p["sha256"],
                    }
                    for p in products
                },
            }
        )
    save("VERSION_E_RECORDS.json", rows)
    target_times = [
        epoch(dt.datetime(2024, 1, day, 12, tzinfo=dt.timezone.utc)) for day in (2, 3, 4)
    ]
    reports = []
    for mode, budget, start in [
        ("session_shared", 1, new["available_at"]),
        ("target_private", 1, new["available_at"]),
        ("target_private", 3, new["available_at"]),
        ("session_shared", 1, at - 1),
    ]:
        qids = (
            [new["id"]]
            if mode == "session_shared"
            else [new["id"] + ":" + str(t) for t in target_times]
        )
        queries = [
            Query(
                q,
                Cost(requests=1, bytes=Path(new["archive"]).stat().st_size, compute_ms=1),
                new["available_at"],
                5_000_000,
            )
            for q in qids
        ]
        goals = [
            Goal(str(t), at, (frozenset([qids[0] if mode == "session_shared" else qids[i]]),))
            for i, t in enumerate(target_times)
        ]
        limits = {"requests": budget, "bytes": None, "tokens": None, "compute_ms": None}
        result = solve_joint(queries, goals, limits, concurrency=1, start=start)
        witnessed = []
        for witness in result.frontier:
            validate_witness(witness, queries, goals, limits, concurrency=1, start=start)
            settled = []
            for i, t in enumerate(target_times):
                allowed = qids[0] if mode == "session_shared" else qids[i]
                finishes = [end for q, begin, end in witness.starts if q == allowed]
                if len(finishes) > 1:
                    raise ValueError("A witness repeats the same archive query")
                finished = {new["id"]: finishes[0]} if finishes else {}
                status, _, _ = e_support(products, t, at, finished)
                if status in ("supported", "refuted"):
                    settled.append(str(t))
            if sorted(settled) != list(witness.resolved):
                raise ValueError("Native support differs from finite witness")
            witnessed.append(witness.to_dict())
        reports.append(
            {
                "authorization": mode,
                "budget": budget,
                "start": start,
                "deadline": at,
                "joint_lower": result.lower_bound,
                "joint_upper": result.upper_bound,
                "exact": result.exact,
                "witnesses": witnessed,
            }
        )
    # With one serial worker, three 5s private reads cannot fit the 10s deadline.
    if [r["joint_lower"] for r in reports] != [3, 1, 2, 0]:
        raise ValueError("Shared budget/time frontier changed")
    save("REACHABILITY.json", reports)
    save(
        "REPORT.json",
        {
            "product_cycles": 2,
            "common_native_target_times": 697,
            "evaluated_E_states": len(rows) * 4,
            "current_version_unread_states": 697,
            "late_old_product_resurrection": 0,
            "all_43_column_vectors_changed": all(
                old["rows"][t]["vector"] != new["rows"][t]["vector"] for t in common
            ),
            "protocol_case_results": reports,
            "resource_clock": "declared5s full-file service, single concurrent query",
            "scope": "Product-version E and finite shared-archive acquisition reference; no real LLM scheduler or physical flood F score.",
            "physical_F_gate": load(PRIOR / "SOURCE_SEMANTICS.json"),
            "model_calls": 0,
        },
    )
    save(
        "VALIDATION.json",
        {
            "passed": True,
            "native_source_hashes_verified": True,
            "exact_decimal_reference": True,
            "support_and_finite_witnesses_reconciled": True,
            "E_state_count": 2788,
            "files": {p.name: digest(p) for p in OUT.iterdir() if p.is_file()},
            "model_calls": 0,
        },
    )
    print(
        json.dumps(
            {
                "E_states": 2788,
                "joint_resolved_by_case": [r["joint_lower"] for r in reports],
                "physical_F": False,
            }
        )
    )


if __name__ == "__main__":
    main()
