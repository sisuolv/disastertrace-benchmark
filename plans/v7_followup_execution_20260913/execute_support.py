"""Reparse real report/TAF fixtures and validate shared-budget E witnesses."""

import argparse
import json
from itertools import pairwise
from pathlib import Path

from disastertrace.monitoring_fixed_v1.aviation import visible_e_status
from disastertrace.monitoring_fixed_v1.contracts import (
    EvidenceBundle,
    Target,
    fingerprint,
)
from disastertrace.monitoring_fixed_v1.support_bridge import (
    compile_recipes,
    native_slot_support,
    taf_coverage,
    taf_version_support,
)
from disastertrace.monitoring_v1.reachability import (
    Goal,
    Query,
    solve_joint,
    validate_witness,
)
from disastertrace.monitoring_v1.resources import Cost
from execute_admission import MATRIX, ROOT, save


def main(out):
    out.mkdir(exist_ok=False, parents=True)
    rows = json.loads((MATRIX / "MANIFEST.json").read_text())
    bundles = {
        r["call_id"]: EvidenceBundle.restore(
            json.loads((MATRIX / "policy" / (r["call_id"] + ".json")).read_text())
        )
        for r in rows
    }
    fixtures = []
    for item in rows:
        b = bundles[item["call_id"]]
        report = native_slot_support(b)
        if report["status"] != visible_e_status(b):
            raise ValueError("Native bridge disagrees with registered report predicate")
        fixtures.append(
            {
                "call_id": item["call_id"],
                "region": item["region"],
                "condition": item["condition"],
                "E_report": report,
                "TAF_coverage": taf_coverage(b),
            }
        )
    all_bay = [
        r for r in rows if r["region"] == "bay" and r["condition"] == "all_registered"
    ]
    first_cutoff = min(bundles[r["call_id"]].policy_view()["cutoff"] for r in all_bay)
    graph_rows = [
        r
        for r in all_bay
        if bundles[r["call_id"]].policy_view()["cutoff"] == first_cutoff
    ]
    graphs, query_metadata, goals = [], {}, []
    for r in graph_rows:
        b = bundles[r["call_id"]]
        p = b.policy_view()
        goals.append(Goal(p["target"]["target_id"], first_cutoff, compile_recipes(b)))
        receipt_map = {v["receipt_id"]: v for v in p["receipts"]}
        for a in p["assets"]:
            rc = receipt_map[a["receipt_ids"][0]]
            qid = a["content"]["query_id"]
            meta = {
                "cost": rc["cost"],
                "released_at": a["available_at"],
                "duration": rc["completed_at"] - rc["started_at"],
                "content_sha256": fingerprint(a["content"]),
            }
            if qid in query_metadata and meta != query_metadata[qid]:
                raise ValueError("Shared source/payment identity mismatch")
            query_metadata[qid] = meta
    if len(goals) > 4 or len(query_metadata) > 6:
        raise ValueError("Graph exceeds first finite scope")
    queries = [
        Query(q, Cost(**m["cost"]), m["released_at"], m["duration"])
        for q, m in query_metadata.items()
    ]
    start = first_cutoff - 120_000_000
    for budget in (1, 2, 3):
        limits = {
            "requests": budget,
            "bytes": budget * 2048,
            "tokens": 0,
            "compute_ms": budget * 100,
        }
        result = solve_joint(queries, goals, limits, concurrency=2, start=start)
        for w in result.frontier:
            validate_witness(w, queries, goals, limits, concurrency=2, start=start)
        graphs.append(
            {
                "limits": limits,
                "concurrency": 2,
                "start": start,
                "result": result.to_dict(),
                "every_witness_independently_validated": True,
                "individually_reachable": sum(
                    s == "reachable_relaxation"
                    for s in result.individual_status.values()
                ),
                "joint_E_upper": result.upper_bound,
            }
        )
    version_fixtures = []
    path = (
        ROOT
        / "plans/v7_review_execution_20260912/extension_bay_area_01/environment/BASELINE_CANDIDATES.json"
    )
    candidates = json.loads(path.read_text())
    for item in sorted(graph_rows, key=lambda r: r["opportunity_id"]):
        target = Target(**bundles[item["call_id"]].policy_view()["target"])
        selected = {
            c["source_id"]: {**c, "completed_at": c["available_at"]}
            for c in candidates
            if c["target_id"] == target.target_id and c["available_at"] <= first_cutoff
        }
        ordered = sorted(
            selected.values(), key=lambda c: (c["issued_at"], c["source_id"])
        )
        # Native product changes select a mechanics fixture, never future outcomes.
        pair = next(
            (
                (a, b)
                for a, b in pairwise(ordered)
                if a["projection"] != b["projection"]
            ),
            None,
        )
        if pair:
            earlier, later = pair
            version_fixtures.append(
                {
                    "target": target.to_dict(),
                    "source_fixture_kind": "real_archived_TAF_products",
                    "availability": "common product, declared historical release lag; no actual download receipt implied",
                    "disclosed_sources": [earlier, later],
                    "before": taf_version_support(
                        [earlier], target, at=earlier["completed_at"]
                    ),
                    "after": taf_version_support(
                        [earlier, later], target, at=later["completed_at"]
                    ),
                    "old_product_kept_as_history": True,
                }
            )
    report = {
        "schema": "disastertrace.real_support_bridge_report.v1",
        "bundles": len(fixtures),
        "base_opportunities": len({r["opportunity_id"] for r in rows}),
        "report_support_matches_registered_semantics": True,
        "native_TAF_coverage_supported": sum(
            r["TAF_coverage"]["status"] == "supported" for r in fixtures
        ),
        "native_TAF_coverage_unsupported": sum(
            r["TAF_coverage"]["status"] == "unsupported" for r in fixtures
        ),
        "real_target_revision_pairs": len(version_fixtures),
        "graph_targets": len(goals),
        "graph_queries": len(queries),
        "graph_budget_cases": len(graphs),
        "graph_uses_evaluator_only_recipes": True,
        "new_E_model_heads_run": False,
        "provider_scope": "native_H15; no physical-image gold or generic bounded-measurement adapter claimed",
        "new_raw_downloads": 0,
        "existing_source_bytes_reused": True,
    }
    save(out / "SUPPORT_BRIDGE_REPORT.json", report)
    save(
        out / "JOINT_WITNESSES.json",
        {
            "query_metadata": query_metadata,
            "goals": [
                {
                    "target_id": g.target_id,
                    "deadline": g.deadline,
                    "alternatives": [sorted(r) for r in g.alternatives],
                }
                for g in goals
            ],
            "cases": graphs,
        },
    )
    save(out / "REAL_TAF_VERSION_FIXTURES.json", version_fixtures)
    with (out / "E_FIXTURES.jsonl").open("x") as f:
        for row in fixtures:
            f.write(json.dumps(row, allow_nan=False) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args().output)
