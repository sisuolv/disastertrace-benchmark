"""Compile the first real-source seed with controlled text and delivery policies."""

import copy
import json
import random
import re
import shutil
from dataclasses import asdict
from pathlib import Path

from shapely.geometry import Point, mapping

from disastertrace.forecast_source.normalization import normalize
from disastertrace.forecast_source.parser_a import parse as parse_a
from disastertrace.forecast_source.parser_b import parse as parse_b

from .compiler import public_view, reference_for, rule_target, transition_obligations
from .geometry_reference import catalogue, load_forecasts, relation
from .pixel_baseline import answer, pixel_relation
from .rendering import grid_for, layout_for, pixel_for, render, tolerance_for
from .storage import canonical, digest, publish_bytes, read, write
from .types import ArtifactMeta, DeliveryEvent, FactKey, QuerySpec


def _select_sites(geometries, layout):
    randomizer = random.Random(20260909)
    x0, y0, x1, y1 = layout["extent"]
    tolerance = tolerance_for(layout, 8)
    sites = {}
    for _ in range(50000):
        point = (round(randomizer.uniform(x0, x1), 5), round(randomizer.uniform(y0, y1), 5))
        if any(geometry.boundary.distance(Point(point)) < tolerance * 2 for geometry in geometries):
            continue
        classes = tuple(geometry.covers(Point(point)) for geometry in geometries)
        if "A" not in sites and classes == (False, True):
            sites["A"] = point
        elif classes == (True, True):
            if "B" not in sites:
                sites["B"] = point
            elif "C" not in sites and Point(point).distance(Point(sites["B"])) >= 0.5:
                sites["C"] = point
        if len(sites) == 3:
            return sites
    raise ValueError("no seed sites pass the predeclared transition and margin criteria")


def _radii_in_text(raw, parsed, valid):
    normalized = normalize(raw)
    forecast = next(row for row in parsed["forecasts"] if row["valid_at"] == valid)
    start = forecast["forecast_line"]
    ends = [row["forecast_line"] - 1 for row in parsed["forecasts"] if row["forecast_line"] > start]
    block = normalized["text"].splitlines()[start : min(ends) if ends else None]
    found = []
    for text in block:
        match = re.fullmatch(r"34 KT\.+\s*(\d+)NE\s+(\d+)SE\s+(\d+)SW\s+(\d+)NW\.", text.strip())
        if match:
            found.append([int(x) for x in match.groups()])
    if len(found) != 1:
        raise ValueError("unique matching text radii row required")
    return found[0], forecast


def _artifact(aid, issued, version, modality, origin, target, content, **private):
    meta = ArtifactMeta(aid, issued, version, modality, origin, FactKey(**target)).public()
    return {"meta": meta, "public_content": content, **private}


def necessity_witnesses(view, episode, output):
    # Use declared experimental version identities in these controlled twins.
    # Actual source metadata stays in the private lineage, not misleading aliases.
    import base64

    maps = [a for a in episode["artifacts"] if a["meta"]["modality"] == "image"]
    pair = []
    for source in maps:
        request = copy.deepcopy(view)
        request["condition"] = (
            "controlled_necessity_witness; experimental image version; official geometry lineage private"
        )
        request["evidence"] = [
            item for item in request["evidence"] if item["meta"]["modality"] == "text"
        ]
        image = copy.deepcopy(
            next(item for item in view["evidence"] if item["meta"]["modality"] == "image")
        )
        image["meta"].update(
            artifact_id="paired-map", issued_at="2024-09-10T10:00:00+00:00", version=1
        )
        image["content"]["image_png_base64"] = base64.b64encode(
            (output / "public" / source["image_path"]).read_bytes()
        ).decode()
        request["evidence"].append(image)
        request["deliveries"] = [d for d in request["deliveries"] if d["artifact_id"] != "map-01"]
        request["deliveries"].append(
            asdict(DeliveryEvent("paired-delivery", "paired-map", "2024-09-10T10:00:00+00:00", 0))
        )
        pair.append(request)
    nonvisual = []
    for request in pair:
        projection = copy.deepcopy(request)
        for item in projection["evidence"]:
            item["content"].pop("image_png_base64", None)
        nonvisual.append(digest(canonical(projection).encode()))
    values = [json.loads(answer(request))["state"]["A"]["inspection_required"] for request in pair]
    expected_values = [
        episode["private_facts"][m["meta"]["artifact_id"]]["A"] == "inside" for m in maps
    ]
    if nonvisual[0] != nonvisual[1] or values != expected_values or values[0] == values[1]:
        raise ValueError("visual-necessity witness failed")
    text_pair = [copy.deepcopy(pair[1]), copy.deepcopy(pair[1])]
    for item in text_pair[1]["evidence"]:
        if item["meta"]["target"] == rule_target(view["target"]):
            item["content"]["lines"] = [
                s.replace("WATCH A true", "WATCH A false") for s in item["content"]["lines"]
            ]
    image_parts = [
        [item for item in request["evidence"] if item["meta"]["modality"] == "image"]
        for request in text_pair
    ]
    text_values = [
        json.loads(answer(request))["state"]["A"]["inspection_required"] for request in text_pair
    ]
    if image_parts[0] != image_parts[1] or text_values != [True, False]:
        raise ValueError("text-necessity witness failed")
    for name, requests in (("visual", pair), ("text", text_pair)):
        for index, request in enumerate(requests):
            write(output / "public" / "necessity" / f"{name}-{index}.json", request)
    return {
        "status": "passed",
        "scope": "controlled_modality_partition_only",
        "nonvisual_projection_sha256": nonvisual,
        "visual_pair_required": values,
        "text_pair_required": text_values,
        "image_and_metadata_equal_in_text_pair": True,
        "lineage": [m["meta"]["artifact_id"] for m in maps],
        "certifies_model_internal_pixel_use": False,
        "natural_full_text_necessity_claimed": False,
    }


def build_seed(source_root, output):
    source_root, output = Path(source_root), Path(output)
    output.mkdir(parents=True, exist_ok=False)
    inventory = read(source_root / "sources.json")
    scope = read(source_root / "scope.json")
    if (
        inventory["storm_id"] != "AL062024"
        or inventory["split"] != "development"
        or inventory["source_scope_sha256"] != digest((source_root / "scope.json").read_bytes())
        or "AL062024" in scope["protected_heldout_ids"]
    ):
        raise ValueError("source/split identity differs")
    shutil.copytree(source_root, output / "inputs")
    parsed, text_bytes, forecasts, catalogues = {}, {}, {}, []
    for item in inventory["records"]:
        path = source_root / item["path"]
        if path.is_symlink() or not path.resolve().is_relative_to(source_root.resolve()):
            raise ValueError("source escapes input root")
        raw = path.read_bytes()
        if digest(raw) != item.get("raw_sha256", item.get("sha256")):
            raise ValueError("source bytes differ from acquisition receipt")
        if item["role"] == "forecast_text":
            a, b = parse_a(raw), parse_b(raw)
            if a != b or a["storm_id"] != "AL062024" or a["advisory_number"] != item["advisory"]:
                raise ValueError("independent text parsers disagree")
            parsed[item["advisory"]], text_bytes[item["advisory"]] = a, raw
        elif item["role"] in {"wind_radii", "track_cone_context_only"}:
            catalogues.append(
                {"role": item["role"], "advisory": item["advisory"], "layers": catalogue(raw)}
            )
    for item in inventory["records"]:
        if item["role"] == "wind_radii":
            advisory = item["advisory"]
            forecasts[advisory] = load_forecasts(
                (source_root / item["path"]).read_bytes(),
                "AL062024",
                advisory,
                parsed[advisory]["issued_at"],
            )
    aligned = []
    maps = {
        a: {f["valid_at"]: f for f in rows if f["threshold_kt"] == 34}
        for a, rows in forecasts.items()
    }
    shared = sorted(set(maps[5]) & set(maps[7]))
    for valid in shared:
        for advisory in (5, 7):
            radii, forecast = _radii_in_text(text_bytes[advisory], parsed[advisory], valid)
            props = maps[advisory][valid]["properties"]
            if radii != [props[k] for k in ("NE", "SE", "SW", "NW")]:
                raise ValueError("text and GIS quadrant radii disagree")
            aligned.append(
                {
                    "valid_at": valid,
                    "advisory": advisory,
                    "text_radii_nm": radii,
                    "text_center": [forecast["longitude"], forecast["latitude"]],
                    "layer": maps[advisory][valid]["layer"],
                    "feature_index": maps[advisory][valid]["feature_index"],
                    "text_lead_hours_from_center": forecast["lead_hours_from_center"],
                    "gis_tau_from_synoptic": props["TAU"],
                    "independent_text_parsers_equal": True,
                }
            )
    if not shared:
        raise ValueError("no same-absolute-valid forecast pair")
    valid = shared[0]
    geometries = [maps[a][valid]["geometry"] for a in (5, 7)]
    extents = [g.bounds for g in geometries]
    extent = [
        min(x[0] for x in extents) - 0.35,
        min(x[1] for x in extents) - 0.35,
        max(x[2] for x in extents) + 0.35,
        max(x[3] for x in extents) + 0.35,
    ]
    layout = layout_for(extent)
    points = _select_sites(geometries, layout)
    queries = [
        asdict(
            QuerySpec(
                site,
                *point,
                tuple(pixel_for(point, layout)),
                grid_for(pixel_for(point, layout), layout),
                4 if site == "C" else 0,
            )
        )
        for site, point in sorted(points.items())
    ]
    target = asdict(
        FactKey("AL062024", "nhc_forecast_wind_radii", "forecast_envelope_membership", 34, valid)
    )
    artifacts, facts, pixel_checks, lineage = [], {}, [], []
    for index, advisory in enumerate((5, 7), 1):
        aid = f"map-{index:02d}"
        geometry = geometries[index - 1]
        png = render(geometry, layout, valid, 34)
        path = Path("maps") / (aid + ".png")
        publish_bytes(output / "public" / path, png)
        artifacts.append(
            _artifact(
                aid,
                parsed[advisory]["issued_at"],
                advisory,
                "image",
                "official_data_rendered",
                target,
                {"layout": layout, "material": "official_data_rendered"},
                image_path=path.as_posix(),
                image_sha256=digest(png),
            )
        )
        facts[aid] = {}
        for query in queries:
            sid = query["site_id"]
            expected = relation(geometry, points[sid], extent, tolerance_for(layout, 8))
            facts[aid][sid] = expected
            for size in (512, 768, 1024):
                actual = pixel_relation(png, layout, query["pixel"], size)
                pixel_checks.append(
                    {
                        "map": aid,
                        "site": sid,
                        "size": size,
                        "geometry_reference": expected,
                        "public_pixel_value": actual,
                        "pass": expected == actual and actual in {"inside", "outside"},
                    }
                )
        lineage.append(
            {
                "artifact_id": aid,
                "advisory": advisory,
                "layer": maps[advisory][valid]["layer"],
                "feature_index": maps[advisory][valid]["feature_index"],
                "properties": maps[advisory][valid]["properties"],
                "crs_wkt": maps[advisory][valid]["crs_wkt"],
                "geometry": mapping(geometry),
            }
        )
        _, forecast = _radii_in_text(text_bytes[advisory], parsed[advisory], valid)
        wind_line = normalize(text_bytes[advisory])["text"].splitlines()[forecast["wind_line"] - 1]
        context_target = dict(
            target, product="nhc_forecast_intensity", variable="center_max_sustained_wind"
        )
        artifacts.append(
            _artifact(
                f"context-{advisory:02d}",
                parsed[advisory]["issued_at"],
                advisory,
                "text",
                "official_text_excerpt",
                context_target,
                {
                    "lines": ["NHC intensity excerpt for " + valid, wind_line],
                    "projection": "controlled_modality_partition; locations, quadrant radii and other fields excluded",
                },
            )
        )
    if not all(row["pass"] for row in pixel_checks):
        write(output / "pixel_admission_failed.json", pixel_checks)
        raise ValueError("rendered pixels cannot support geometric reference at admitted sizes")
    rules = {"watch-01": {"A": True, "B": False}, "watch-02": {"A": False, "B": True, "C": True}}
    rule_lines = {}
    for index, (aid, watch) in enumerate(rules.items()):
        lines = ["Benchmark exercise watch list; not an official warning."] + [
            f"WATCH {k} {str(v).lower()}" for k, v in watch.items()
        ]
        rule_lines[aid] = {site: f"L{i + 2}" for i, site in enumerate(watch)}
        artifacts.append(
            _artifact(
                aid,
                f"2024-09-10T{10 + index * 4:02d}:00:00+00:00",
                index + 1,
                "text",
                "benchmark_rule",
                rule_target(target),
                {"lines": lines},
            )
        )
    schedule = [
        (0, "map-01"),
        (0, "context-05"),
        (0, "watch-01"),
        (1, "context-07"),
        (2, "map-02"),
        (3, "map-01"),
        (4, "watch-02"),
    ]
    base = [
        asdict(DeliveryEvent(f"d{i}", aid, f"2024-09-10T{10 + cp:02d}:00:00+00:00", cp))
        for i, (cp, aid) in enumerate(schedule)
    ]
    branches = {
        "base": base,
        "without_stale_replay": [e for e in base if e["checkpoint"] != 3],
        "without_new_map": [e for e in base if e["artifact_id"] != "map-02"],
        "without_maps": [e for e in base if not e["artifact_id"].startswith("map-")],
        "without_watch_list": [e for e in base if not e["artifact_id"].startswith("watch-")],
        "delayed_new_map": [
            dict(e, checkpoint=4, delivered_at="2024-09-10T14:00:00+00:00")
            if e["artifact_id"] == "map-02"
            else e
            for e in base
        ],
    }
    episode = {
        "schema": "disastertrace.multimodal_v1",
        "episode_id": "francine_005_007_fixed_valid_seed",
        "event_id": "AL062024",
        "global_event_id": "AL062024",
        "split": "development",
        "checkpoints": 5,
        "target": target,
        "queries": queries,
        "artifacts": artifacts,
        "branches": branches,
        "private_facts": facts,
        "private_rules": rules,
        "private_rule_lines": rule_lines,
        "material": "official_data_rendered",
        "text_partition": "controlled_modality_partition",
        "schedule_origin": "controlled_replay",
        "natural_historical_availability_verified": False,
    }
    references, obligations = {}, {}
    for branch in branches:
        references[branch], obligations[branch] = [], []
        for checkpoint in range(5):
            view = public_view(episode, branch, checkpoint, output / "public")
            gold = reference_for(episode, view)
            write(output / "public" / "requests" / branch / f"c{checkpoint}.json", view)
            references[branch].append(gold)
            obligations[branch].append(
                transition_obligations(references[branch][checkpoint - 1], gold)
                if checkpoint
                else {}
            )
    certificate = necessity_witnesses(
        public_view(episode, "base", 0, output / "public"), episode, output
    )
    write(output / "private" / "episode.json", episode)
    write(output / "private" / "references.json", references)
    write(output / "private" / "obligations.json", obligations)
    write(output / "private" / "geometry_lineage.json", lineage)
    write(output / "layer_catalogue.json", catalogues)
    admission = {
        "status": "passed",
        "event_count": 1,
        "episode_count": 1,
        "branch_count": len(branches),
        "planned_checkpoints": sum(len(rows) for rows in references.values()),
        "selected_valid_at": valid,
        "selection": "earliest shared forecast-valid 34 KT time; deterministic seed 20260909; predeclared class/margin sampling",
        "shared_valid_times": shared,
        "text_gis_alignment": aligned,
        "pixel_checks": pixel_checks,
        "source_kind": "official_data_rendered",
        "full_text_redundancy": "center and quadrant radii explicitly present",
        "native_original_graphics_admitted": False,
        "native_crs_preserved": True,
        "vlm_processor_validated": False,
        "model_calls": 0,
        "gpu_jobs": 0,
        "human_per_item_gold": False,
        "llm_judge": False,
        "necessity": certificate,
        "limits": [
            "one development storm",
            "controlled release schedule and watch rule",
            "no natural full-text visual necessity claim",
            "wind-radius envelopes are not actual point wind observations",
            "processor-specific admission remains MM-3",
        ],
    }
    write(output / "admission.json", admission)
    return admission
