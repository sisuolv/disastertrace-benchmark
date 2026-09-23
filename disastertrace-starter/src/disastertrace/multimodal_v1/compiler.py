"""Delivery-aware public views and branch-specific private reference states."""

import base64
import json
from dataclasses import asdict
from pathlib import Path

from .storage import digest
from .types import ArtifactMeta, FactKey, PublicEvidenceView, RuleSpec, select_version, tri_and, utc


def rule_target(target):
    return {**target, "product": "benchmark_watch_list", "variable": "watched"}


def validate_episode(episode):
    ids = [a["meta"]["artifact_id"] for a in episode["artifacts"]]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate artifact identity")
    assets = {a["meta"]["artifact_id"]: a for a in episode["artifacts"]}
    for branch, events in episode["branches"].items():
        if len({e["delivery_id"] for e in events}) != len(events):
            raise ValueError("duplicate delivery identity")
        for event in events:
            if (
                event["artifact_id"] not in assets
                or not 0 <= event["checkpoint"] < episode["checkpoints"]
            ):
                raise ValueError("delivery outside episode")
            if utc(event["delivered_at"]) < utc(assets[event["artifact_id"]]["meta"]["issued_at"]):
                raise ValueError("delivery precedes source issue")
        ordered = sorted(events, key=lambda x: (x["checkpoint"], utc(x["delivered_at"])))
        if any(
            utc(a["delivered_at"]) > utc(b["delivered_at"]) for a, b in zip(ordered, ordered[1:])
        ):
            raise ValueError("delivery chronology differs from checkpoints")
    if episode["split"] != "development":
        raise ValueError("this builder accepts development only")


def public_view(episode, branch, checkpoint, asset_root, information="full_modal"):
    validate_episode(episode)
    if branch not in episode["branches"] or not 0 <= checkpoint < episode["checkpoints"]:
        raise ValueError("unknown branch or checkpoint")
    if information not in {"full_modal", "text_only", "vision_only"}:
        raise ValueError("unsupported public information condition")
    allowed = (
        {"image", "text"}
        if information == "full_modal"
        else ({"text"} if information == "text_only" else {"image"})
    )
    events = sorted(
        (e for e in episode["branches"][branch] if e["checkpoint"] <= checkpoint),
        key=lambda e: (e["checkpoint"], utc(e["delivered_at"]), e["delivery_id"]),
    )
    visible_ids = {e["artifact_id"] for e in events}
    evidence = []
    for artifact in episode["artifacts"]:
        meta = artifact["meta"]
        if meta["artifact_id"] not in visible_ids or meta["modality"] not in allowed:
            continue
        meta = ArtifactMeta(**{**meta, "target": FactKey(**meta["target"])}).public()
        allowed_content = (
            {"layout", "material"} if meta["modality"] == "image" else {"lines", "projection"}
        )
        if set(artifact["public_content"]) - allowed_content:
            raise ValueError("unreviewed public content field")
        item = {"meta": meta, "content": artifact["public_content"]}
        if meta["modality"] == "image":
            layout = item["content"]["layout"]
            allowed_layout = {
                "size",
                "plot",
                "extent",
                "grid_rows",
                "grid_cols",
                "coordinate_order",
                "coordinate_crs",
                "display_projection",
                "palette",
                "boundary_rule",
            }
            if set(layout) != allowed_layout or set(layout["palette"]) != {"inside", "outside"}:
                raise ValueError("unreviewed image metadata field")
            root = Path(asset_root).resolve()
            path = root / artifact["image_path"]
            if path.is_symlink() or not path.resolve().is_relative_to(root):
                raise ValueError("image outside public asset root")
            data = path.read_bytes()
            if digest(data) != artifact["image_sha256"]:
                raise ValueError("public image bytes changed")
            item = {
                "meta": meta,
                "content": {
                    **item["content"],
                    "image_png_base64": base64.b64encode(data).decode("ascii"),
                },
            }
        evidence.append(item)
    delivered = {item["meta"]["artifact_id"] for item in evidence}
    queries = [
        {k: site[k] for k in ("site_id", "lon", "lat", "pixel", "grid")}
        for site in episode["queries"]
        if site["revealed_at"] <= checkpoint
    ]
    result = PublicEvidenceView(
        checkpoint=f"c{checkpoint}",
        target=episode["target"],
        queries=queries,
        evidence=evidence,
        deliveries=[
            {
                k: e[k]
                for k in (
                    "delivery_id",
                    "artifact_id",
                    "delivered_at",
                    "checkpoint",
                    "schedule_origin",
                )
            }
            for e in events
            if e["artifact_id"] in delivered
        ],
        rule=asdict(RuleSpec()),
    ).as_dict()
    result["output_contract"] = {
        "root": "Submit only a JSON object with key state; include every currently revealed site, no future sites.",
        "site_fields": {
            "relation": ["inside", "outside", "boundary_ambiguous", "unknown"],
            "watched": "boolean or null",
            "inspection_required": "boolean or null",
            "map_source": "applicable image artifact_id, or null when absent",
            "map_locator": "query grid label or point:<site_id>; null when map absent; whole-image citations disallowed",
            "rule_source": "applicable watch-list artifact_id or null when absent",
            "rule_locator": "L plus one-based line number, or null when absent",
        },
        "version_rule": "Match event, product, variable, threshold, absolute valid time and spatial scope; use latest issued_at then version among delivered evidence. A repeated delivery is not a new version.",
        "watch_scope": "Watch lists use product benchmark_watch_list and variable watched; other target fields must match.",
        "logic": "inspection_required = watched AND forecast_inside; false AND null is false; true AND null is null; boundary_ambiguous and unknown have null spatial truth.",
        "carrier": "Previous raw final answer is your own history, including errors. Recheck against currently supplied evidence.",
        "budgets": {"max_final_utf8_bytes": 65536, "max_sites": 64, "max_reference_chars": 80},
    }
    return json.loads(json.dumps(result, allow_nan=False))


def reference_for(episode, view):
    metas = [item["meta"] for item in view["evidence"]]
    ids = {item["artifact_id"] for item in metas}
    map_meta = select_version(metas, ids, view["target"], "image")
    rule_meta = select_version(metas, ids, rule_target(view["target"]), "text")
    state = {}
    for query in view["queries"]:
        site = query["site_id"]
        relation = (
            episode["private_facts"][map_meta["artifact_id"]][site] if map_meta else "unknown"
        )
        watched = (
            episode["private_rules"][rule_meta["artifact_id"]].get(site) if rule_meta else None
        )
        inside = True if relation == "inside" else (False if relation == "outside" else None)
        state[site] = {
            "relation": relation,
            "watched": watched,
            "inspection_required": tri_and(watched, inside),
            "map_source": map_meta["artifact_id"] if map_meta else None,
            "map_locator": query["grid"] if map_meta else None,
            "rule_source": rule_meta["artifact_id"] if rule_meta and watched is not None else None,
            "rule_locator": episode["private_rule_lines"][rule_meta["artifact_id"]].get(site)
            if rule_meta and watched is not None
            else None,
        }
    return {"state": state}


def transition_obligations(previous, current):
    result = {
        k: []
        for k in (
            "must_change_value",
            "must_change_provenance",
            "must_preserve_value",
            "must_preserve_provenance",
            "must_remain_unknown",
            "must_recheck_dependencies",
        )
    }
    for site, new in current["state"].items():
        if site not in previous["state"]:
            continue
        old = previous["state"][site]
        for name in ("relation", "watched", "inspection_required"):
            obligation = "must_preserve_value" if old[name] == new[name] else "must_change_value"
            result[obligation].append(site + "." + name)
            if old[name] == new[name] and (new[name] is None or new[name] == "unknown"):
                result["must_remain_unknown"].append(site + "." + name)
        for name in ("map_source", "map_locator", "rule_source", "rule_locator"):
            key = "must_preserve_provenance" if old[name] == new[name] else "must_change_provenance"
            result[key].append(site + "." + name)
        if any(old[k] != new[k] for k in ("relation", "watched", "map_source", "rule_source")):
            result["must_recheck_dependencies"].append(site + ".inspection_required")
    return result
