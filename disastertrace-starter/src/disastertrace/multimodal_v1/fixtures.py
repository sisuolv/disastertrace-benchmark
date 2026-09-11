"""Explicitly synthetic small episode for offline regression tests."""

from dataclasses import asdict
from pathlib import Path

from shapely.geometry import box

from .compiler import rule_target
from .rendering import grid_for, layout_for, pixel_for, render
from .storage import digest, publish_bytes, write
from .types import ArtifactMeta, DeliveryEvent, FactKey, QuerySpec


def build_fixture(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    target = asdict(
        FactKey(
            "SYNTHETIC_EVENT",
            "nhc_forecast_wind_radii",
            "forecast_envelope_membership",
            34,
            "2024-09-10T18:00:00+00:00",
        )
    )
    layout = layout_for([-0.5, -0.5, 2.5, 1.5])
    positions = {"A": (1.5, 0.5), "B": (0.5, 0.5), "C": (1.25, 0.75)}
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
        for site, point in positions.items()
    ]
    artifacts = []
    for index, polygon in enumerate((box(0, 0, 1, 1), box(0, 0, 2, 1)), 1):
        aid = f"map-0{index}"
        png = render(polygon, layout, target["valid_at"], 34, "controlled_generated")
        path = f"{aid}.png"
        publish_bytes(output / "public" / path, png)
        meta = ArtifactMeta(
            aid,
            f"2024-09-10T0{index}:00:00+00:00",
            index,
            "image",
            "controlled_generated",
            FactKey(**target),
        ).public()
        artifacts.append(
            {
                "meta": meta,
                "public_content": {"layout": layout, "material": "controlled_generated"},
                "image_path": path,
                "image_sha256": digest(png),
            }
        )
    for index, lines in enumerate(
        (["WATCH A true", "WATCH B false"], ["WATCH A false", "WATCH B true", "WATCH C true"]), 1
    ):
        meta = ArtifactMeta(
            f"watch-0{index}",
            f"2024-09-10T0{index}:00:00+00:00",
            index,
            "text",
            "controlled_generated",
            FactKey(**rule_target(target)),
        ).public()
        artifacts.append({"meta": meta, "public_content": {"lines": list(lines)}})
    events = [
        asdict(DeliveryEvent(f"d{i}", aid, f"2024-09-10T{10 + cp:02d}:00:00+00:00", cp))
        for i, (cp, aid) in enumerate(
            ((0, "map-01"), (0, "watch-01"), (2, "map-02"), (3, "map-01"), (4, "watch-02"))
        )
    ]
    episode = {
        "schema": "disastertrace.multimodal_v1",
        "episode_id": "synthetic_rectangles",
        "split": "development",
        "material": "controlled_generated",
        "checkpoints": 5,
        "target": target,
        "queries": queries,
        "artifacts": artifacts,
        "branches": {
            "base": events,
            "without_maps": [e for e in events if not e["artifact_id"].startswith("map")],
            "without_watch_list": [e for e in events if not e["artifact_id"].startswith("watch")],
        },
        "private_facts": {
            "map-01": {"A": "outside", "B": "inside", "C": "outside"},
            "map-02": {"A": "inside", "B": "inside", "C": "inside"},
        },
        "private_rules": {
            "watch-01": {"A": True, "B": False},
            "watch-02": {"A": False, "B": True, "C": True},
        },
        "private_rule_lines": {
            "watch-01": {"A": "L1", "B": "L2"},
            "watch-02": {"A": "L1", "B": "L2", "C": "L3"},
        },
    }
    write(output / "episode.json", episode)
    return episode
