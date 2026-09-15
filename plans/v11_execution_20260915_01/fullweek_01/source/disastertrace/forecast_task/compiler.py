"""Compile references from admitted dual-parser products and original raw bytes."""

import hashlib
import html
from collections import Counter
from datetime import datetime
from itertools import pairwise
from pathlib import Path

from disastertrace.forecast_source import normalization, parser_a, parser_b

from .common import digest, fingerprint, read, verify
from .contract import FIELDS, empty_answer


def load_sources(root):
    root = Path(root)
    scope = read(root / "SOURCE_SCOPE.json")
    if scope["scope_id"] != fingerprint({k: v for k, v in scope.items() if k != "scope_id"}):
        raise ValueError("source scope identity differs")
    for filename, key in (("catalogue.json", "catalogue_sha256"), ("split.json", "split_sha256")):
        if digest(root / "input_evidence" / filename) != scope[key]:
            raise ValueError("split evidence differs")
    catalogue = read(root / "input_evidence/catalogue.json")
    split = read(root / "input_evidence/split.json")
    protected = sorted(
        {x["storm_id"] for x in catalogue["events"] if x["split"] == "heldout"}
        | set(split["splits"]["heldout"]["planned_event_ids"])
    )
    if protected != scope["protected_heldout_ids"] or any(
        item["storm_id"] in protected for item in scope["selected"]
    ):
        raise ValueError("heldout protection differs")
    acquisition_manifest = verify(root / "acquisition")
    review_manifest = verify(root / "review_v1")
    report = read(root / "review_v1/report.json")
    saved_products = read(root / "review_v1/products.json")
    canonicals = read(root / "review_v1/canonical.json")
    records = {item["source_id"]: item for item in report["records"]}
    selected = scope["selected"]
    if len(records) != len(selected) or set(records) != {x["source_id"] for x in selected}:
        raise ValueError("source review denominator differs")
    for module in (normalization, parser_a, parser_b):
        name = "src/disastertrace/forecast_source/" + Path(module.__file__).name
        if digest(module.__file__) != report["implementation_files"][name]:
            raise ValueError("parser code differs from admitted version")
    loaded, parsed_products, exclusions = [], [], []
    for selected_item in selected:
        source_id = selected_item["source_id"]
        if source_id != Path(source_id).name or source_id in (".", ".."):
            raise ValueError("invalid source path")
        record = records[source_id]
        fetched = read(root / "acquisition" / source_id / "result.json")
        if record["status"] != "admitted":
            exclusions.append({"source_id": source_id, "reasons": record["reasons"]})
            continue
        raw = (root / "acquisition" / source_id / "body.html").read_bytes()
        raw_hash = hashlib.sha256(raw).hexdigest()
        if fetched["status"] != "received" or not (
            raw_hash == fetched["raw_sha256"] == record["raw_sha256"]
        ):
            raise ValueError("admitted acquisition differs")
        first, second = parser_a.parse(raw), parser_b.parse(raw)
        if first != second or first != record["parser_a"] or second != record["parser_b"]:
            raise ValueError("saved admission cannot be reconstructed")
        if (first["storm_id"], first["advisory_number"]) != (
            selected_item["storm_id"],
            selected_item["advisory_number"],
        ):
            raise ValueError("source identity mismatch")
        normalized = normalization.normalize(raw)
        if normalized != canonicals[source_id]:
            raise ValueError("canonical source changed")
        loaded.append(
            {
                "source_id": source_id,
                "product": first,
                "canonical": normalized,
                "raw": raw,
                "retrieved_at": fetched["retrieved_at"],
                "url": fetched["url"],
            }
        )
        parsed_products.append(first)
    if parsed_products != saved_products or len(loaded) != report["admitted_bodies"]:
        raise ValueError("complete admitted product set differs")
    return loaded, {
        "scope_id": scope["scope_id"],
        "scope_file_sha256": digest(root / "SOURCE_SCOPE.json"),
        "acquisition_package_id": acquisition_manifest["package_id"],
        "review_package_id": review_manifest["package_id"],
        "planned_products": len(selected),
        "admitted_products": len(loaded),
        "quarantined_products": exclusions,
        "protected_heldout_ids": protected,
        "plan_exposure": scope["plan_exposure"],
    }


def _support(source, line_number):
    mapped = source["canonical"]["line_map"][line_number - 1]
    if mapped["canonical_line"] != line_number:
        raise ValueError("noncontiguous provenance")
    raw_line = source["raw"][mapped["raw_byte_start"] : mapped["raw_byte_end"]]
    text = source["canonical"]["text"].splitlines()[line_number - 1]
    if hashlib.sha256(raw_line).hexdigest() != mapped["raw_line_sha256"]:
        raise ValueError("raw citation hash differs")
    if html.unescape(raw_line.decode("utf-8").rstrip("\r\n")).replace("\xa0", " ") != text:
        raise ValueError("raw citation cannot reconstruct displayed line")
    return {**mapped, "canonical_text": text}


def _claim(source, row):
    product = source["product"]
    answer = empty_answer({"storm_id": product["storm_id"], "valid_at": row["valid_at"]})
    answer["status"] = row["terminal_status"] or "numeric"
    for field in FIELDS:
        answer[field]["value"] = row[field + "_kt" if field == "max_sustained_wind" else field]
    answer["citation"] = {
        "source_id": source["source_id"],
        "forecast_line": row["forecast_line"],
        "wind_line": row["wind_line"],
    }
    indices = {product["issue_line"], product["center_line"], row["forecast_line"]}
    if row["wind_line"] is not None:
        indices.add(row["wind_line"])
    return {
        "answer": answer,
        "support": [_support(source, line) for line in sorted(indices)],
        "qualifier": row["qualifier"],
        "gust_kt": row["gust_kt"],
        "lead_hours_from_center": row["lead_hours_from_center"],
    }


def _transition(old, new):
    if old is None:
        return "first_checkpoint"
    if new["status"] == "not_stated":
        return "still_not_stated"
    if old["status"] == "not_stated":
        return "first_explicit"
    if old["citation"]["source_id"] == new["citation"]["source_id"]:
        return "no_new_coverage"
    if old["status"] != "numeric" or new["status"] != "numeric":
        return "terminal_revision"
    if old["max_sustained_wind"] == new["max_sustained_wind"]:
        return "unchanged_wind"
    return "changed_wind"


def compile_sources(sources, source_identity):
    if len({s["source_id"] for s in sources}) != len(sources):
        raise ValueError("duplicate source ID")
    claims, metadata, documents, episodes, opportunities, references, candidates = (
        {},
        {},
        {},
        {},
        {},
        {},
        [],
    )
    source_pairs = []
    for source in sources:
        product, sid = source["product"], source["source_id"]
        claims[sid] = {row["valid_at"]: _claim(source, row) for row in product["forecasts"]}
        if len(claims[sid]) != len(product["forecasts"]):
            raise ValueError("duplicate forecast target")
        metadata[sid] = {
            "source_id": sid,
            "storm_id": product["storm_id"],
            "advisory_number": product["advisory_number"],
            "issued_at": product["issued_at"],
            "center_at": product["center_at"],
            "retrieved_at": source["retrieved_at"],
            "available_at": None,
            "initialization_at": None,
            "raw_sha256": hashlib.sha256(source["raw"]).hexdigest(),
            "canonical_text_sha256": hashlib.sha256(
                source["canonical"]["text"].encode()
            ).hexdigest(),
            "url": source["url"],
        }
    for storm in sorted({s["product"]["storm_id"] for s in sources}):
        ordered = sorted(
            (s for s in sources if s["product"]["storm_id"] == storm),
            key=lambda s: s["product"]["issued_at"],
        )
        issued = [s["product"]["issued_at"] for s in ordered]
        if len(set(issued)) != len(issued):
            raise ValueError("tied issue times unsupported")
        targets = sorted({row["valid_at"] for s in ordered for row in s["product"]["forecasts"]})
        start = datetime.fromisoformat(issued[0])
        for step, source in enumerate(ordered, 1):
            sid = source["source_id"]
            elapsed = (datetime.fromisoformat(issued[step - 1]) - start).total_seconds() / 3600
            metadata[sid].update(delivery_step=step, delivery_elapsed_hours=elapsed)
            documents[sid] = {
                "delivery_step": step,
                "delivery_elapsed_hours": elapsed,
                "numbered_text": "".join(
                    f"L{i:04d}|{line}\n"
                    for i, line in enumerate(source["canonical"]["text"].splitlines(), 1)
                ),
            }
        for valid_at in targets:
            query = {"storm_id": storm, "valid_at": valid_at, "measurement_kind": "forecast"}
            episode_id = "target-" + fingerprint(query)[:24]
            ids, previous_ids, old = [], [], None
            versions = [s["source_id"] for s in ordered if valid_at in claims[s["source_id"]]]
            for earlier, later in pairwise(versions):
                source_pairs.append(
                    {"storm_id": storm, "valid_at": valid_at, "older": earlier, "newer": later}
                )
            for step, source in enumerate(ordered, 1):
                sid = source["source_id"]
                checkpoint_id = f"{storm}-delivery-{step:02d}"
                included = valid_at > issued[step - 1]
                candidate = {
                    "episode_id": episode_id,
                    "query": query,
                    "checkpoint_id": checkpoint_id,
                    "delivery_step": step,
                    "forecast_reference_at": issued[step - 1],
                    "included": included,
                    "exclusion_reason": None if included else "target_not_future",
                }
                candidates.append(candidate)
                if not included:
                    continue
                opportunity_id = "query-" + fingerprint(candidate)[:24]
                visible = [s["source_id"] for s in ordered[:step]]
                eligible = [v for v in visible if valid_at in claims[v]]
                answer = (
                    claims[eligible[-1]][valid_at]["answer"] if eligible else empty_answer(query)
                )
                opportunities[opportunity_id] = {
                    "episode_id": episode_id,
                    "checkpoint_id": checkpoint_id,
                    "query": query,
                    "delivery_step": step,
                    "delivery_elapsed_hours": documents[sid]["delivery_elapsed_hours"],
                    "forecast_reference_at": issued[step - 1],
                    "visible_source_ids": visible,
                    "previous_checkpoint_ids": list(previous_ids),
                }
                references[opportunity_id] = {
                    "answer": answer,
                    "transition": _transition(old, answer),
                    "all_values_unchanged": old is not None
                    and all(old[f] == answer[f] for f in (*FIELDS, "status")),
                }
                ids.append(opportunity_id)
                previous_ids.append(checkpoint_id)
                old = answer
            if not ids:
                raise ValueError("target with no prospective checkpoint")
            episodes[episode_id] = {"query": query, "opportunity_ids": ids}
    public = {
        "schema_version": "forecast_task_public_v1",
        "documents": documents,
        "episodes": episodes,
        "opportunities": opportunities,
    }
    private = {
        "schema_version": "forecast_task_reference_v1",
        "sources": metadata,
        "claims": claims,
        "references": references,
    }
    counts = {
        "independent_storms": len({m["storm_id"] for m in metadata.values()}),
        "products": len(sources),
        "unique_targets": len(episodes),
        "forecast_rows": sum(len(x) for x in claims.values()),
        "terminal_source_rows": sum(
            c["answer"]["status"] != "numeric" for x in claims.values() for c in x.values()
        ),
        "source_revision_pairs": len(source_pairs),
        "candidate_checkpoints": len(candidates),
        "included_checkpoints": len(opportunities),
        "excluded_checkpoints": sum(not c["included"] for c in candidates),
        "statuses": dict(
            sorted(Counter(r["answer"]["status"] for r in references.values()).items())
        ),
        "transitions": dict(sorted(Counter(r["transition"] for r in references.values()).items())),
        "episode_lengths": dict(
            sorted(Counter(str(len(e["opportunity_ids"])) for e in episodes.values()).items())
        ),
    }
    manifest = {
        "schema_version": "forecast_task_dataset_v1",
        "source_identity": source_identity,
        "selection": "all_storm_union_targets_x_deliveries_then_strictly_future_v1",
        "counts": counts,
        "source_revision_pairs": source_pairs,
        "public_sha256": fingerprint(public),
        "reference_sha256": fingerprint(private),
        "candidate_sha256": fingerprint(candidates),
        "product_raw_sha256": {sid: m["raw_sha256"] for sid, m in metadata.items()},
        "generation_authorized": False,
    }
    manifest["dataset_id"] = fingerprint(manifest)
    return {
        "public": public,
        "private_reference": private,
        "candidates": candidates,
        "dataset": manifest,
    }


def compile_bundle(source_root):
    return compile_sources(*load_sources(source_root))
