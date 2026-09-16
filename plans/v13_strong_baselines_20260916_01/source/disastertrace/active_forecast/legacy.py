"""Read-only, development-only importer for the closed V5 feasibility bundle.

This adapter binds existing product facts, never imports outcomes and never
upgrades logical delivery or frame/map dates into proved public availability.
"""

import json
import re
from datetime import timedelta
from pathlib import Path

from .provenance import SourceReader, sha256
from .schema import Capture, Episode, SourceLocator, parse_exact, parse_instant


class FrozenPilotImporter:
    def __init__(self, bundle):
        self.bundle = Path(bundle).resolve()
        self.reader = SourceReader(self.bundle.parent.parent)
        self.nhc = self.read("data/NHC_PRODUCTS.json")
        self.ghcn = self.read("data/GHCND_RECORDS.json")
        self.usdm = self.read("data/USDM_POINTS.json")
        usdm_check = self.read("analysis/USDM_FEASIBILITY.json")
        self.nhc_sources = {p["source"]["capture_id"]: (i, p) for i, p in enumerate(self.nhc)}
        self.ghcn_rows = {
            (p["station"], p["date"], p["variable"]): (i, p)
            for i, p in enumerate(self.ghcn["records"])
        }
        self.ghcn_sources = {p["capture_id"]: p for p in self.ghcn["sources"]}
        self.usdm_rows = {(p["location"], p["map_date"]): (i, p) for i, p in enumerate(self.usdm)}
        self.usdm_sources = {p["source"]["capture_id"]: p["source"] for p in usdm_check["checks"]}
        self.arrays = {}
        for path in ("data/SEVIR_ARRAYS.json", "data/NATURAL_COVERAGE_ARRAYS.json"):
            for i, row in enumerate(self.read(path)):
                if row["channel"] == "vil":
                    key = row["sources"][-1]["capture_id"]
                    if key in self.arrays:
                        raise ValueError("ambiguous SEVIR source identity")
                    self.arrays[key] = (path, i, row)
        self._capture_cache = {}
        self.fact_checks = {
            "NHC_raw_wind_rows": 0,
            "GHCND_raw_daily_rows": 0,
            "USDM_frozen_point_rows": 0,
            "SEVIR_raw_tiles": 0,
        }

    def read(self, relative):
        return self.reader.resolve(self.reader.bind(self.bundle / relative, pointer=""))

    def read_prototype_json(self, relative):
        """Only the frozen comparator uses the prototype's IEEE-float JSON semantics."""
        body = self.reader.resolve(self.reader.bind(self.bundle / relative))
        return json.loads(body)

    def locator(self, relative, pointer, role="derived_product"):
        return self.reader.bind(self.bundle / relative, role=role, pointer=pointer)

    def capture(self, source):
        key = (source["capture_id"], source["sha256"])
        if key in self._capture_cache:
            return self._capture_cache[key]
        loc = SourceLocator(
            kind="whole_file", path=source["path"], sha256=source["sha256"], role="source_bytes"
        )
        self.reader.resolve(loc)
        content_range = source.get("headers", {}).get("content-range")
        origin_range = None
        if content_range:
            match = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)", content_range)
            if not match:
                raise ValueError("unrecognized source Content-Range")
            origin_range = tuple(int(v) for v in match.groups())
            if origin_range[1] - origin_range[0] + 1 != self.reader.bindings[loc.path]["bytes"]:
                raise ValueError("captured byte count differs from Content-Range")
        result = Capture(
            id=source["capture_id"],
            url=source["url"],
            captured_at=source["captured_at"],
            artifact=loc,
            origin_range=origin_range,
        )
        self._capture_cache[key] = result
        return result

    def sources_for(self, family, card):
        key = card["source"]
        if family == "NHC":
            return [self.nhc_sources[key][1]["source"]]
        if family == "GHCND":
            return [self.ghcn_sources[key]]
        if family == "USDM":
            return [self.usdm_sources[key]]
        if family == "SEVIR":
            return self.arrays[key][2]["sources"]
        raise ValueError("unsupported frozen pilot family")

    def support(self, family, label, card=None):
        if family == "NHC":
            return {"kind": "instant", "label": label, "valid_at": parse_instant(label)}
        if family == "GHCND":
            return {"kind": "station_day", "label": label, "day": label}
        if family == "USDM":
            if not re.fullmatch(r"\d{8}", label):
                raise ValueError("USDM map label must be YYYYMMDD")
            return {
                "kind": "product_date",
                "label": label,
                "day": f"{label[:4]}-{label[4:6]}-{label[6:]}",
            }
        match = re.fullmatch(r"(.+):quadrant-([0-3])", label)
        if not match or card is None:
            raise ValueError("SEVIR quadrant locator missing")
        _, _, array = self.arrays[card["source"]]
        height, width, _ = array["shape"]
        if height % 2 or width % 2:
            raise ValueError("frozen quadrant layout requires even dimensions")
        q = int(match[2])
        y0, x0 = (q // 2) * (height // 2), (q % 2) * (width // 2)
        return {
            "kind": "tile",
            "label": label,
            "valid_at": parse_instant(match[1]),
            "box": [y0, y0 + height // 2, x0, x0 + width // 2],
        }

    def record(self, episode_file, ei, ci, ri, family, card, row):
        snapshot = self.locator(episode_file, f"/{ei}/cards/{ci}/records/{ri}", "episode_snapshot")
        if self.reader.resolve(snapshot) != row:
            raise ValueError("record snapshot disagrees with supplied row")
        support = self.support(family, row["support"], card)
        locators = [snapshot]
        if family == "NHC":
            pi, product = self.nhc_sources[card["source"]]
            matches = [
                (i, f)
                for i, f in enumerate(product["forecasts"])
                if parse_instant(f["valid_time"]) == support["valid_at"]
            ]
            if len(matches) != 1:
                raise ValueError("forecast valid-time row is missing or ambiguous")
            fi, forecast = matches[0]
            if (
                row["entity"],
                row["variable"],
                row["unit"],
                row["value"],
                row["version"],
                row["quality"],
            ) != (
                product["storm_id"],
                "maximum_sustained_wind_forecast",
                "kt",
                forecast["wind_kt"],
                f"advisory-{product['advisory_number']}",
                "valid",
            ):
                raise ValueError("NHC fact differs from the source product")
            locators.append(self.locator("data/NHC_PRODUCTS.json", f"/{pi}/forecasts/{fi}"))
            capture = self.capture(product["source"])
            body = self.reader.resolve(capture.artifact)
            prefix = forecast["locator"].removesuffix("/MAX WIND").encode("ascii")
            matches = list(re.finditer(re.escape(prefix) + rb"[^\n]*\nMAX WIND\s+(\d+)\s+KT", body))
            if len(matches) != 1 or int(matches[0][1]) != row["value"]:
                raise ValueError("NHC raw wind locator does not establish the imported value")
            locators.append(
                SourceLocator(
                    kind="byte_range",
                    path=capture.artifact.path,
                    sha256=capture.artifact.sha256,
                    role="source_bytes",
                    start=matches[0].start(),
                    end=matches[0].end(),
                )
            )
            self.fact_checks["NHC_raw_wind_rows"] += 1
        elif family == "GHCND":
            gi, original = self.ghcn_rows[row["entity"], row["support"], row["variable"]]
            quality = (
                "valid"
                if original["quality_flag"] == "" and original["value"] is not None
                else "invalid"
            )
            if (
                row["value"] != original["value"]
                or row["quality"] != quality
                or row["unit"] != original["unit"]
            ):
                raise ValueError("GHCND derived row differs from imported fact")
            locators.append(self.locator("data/GHCND_RECORDS.json", f"/records/{gi}"))
            capture = self.capture(self.ghcn_sources[card["source"]])
            raw = self.reader.resolve(
                SourceLocator(
                    kind="json_pointer",
                    path=capture.artifact.path,
                    sha256=capture.artifact.sha256,
                    role="source_bytes",
                    pointer="",
                )
            )
            matches = [
                (i, r)
                for i, r in enumerate(raw)
                if r["STATION"] == row["entity"] and r["DATE"] == row["support"]
            ]
            if len(matches) != 1:
                raise ValueError("GHCND raw daily row missing/ambiguous")
            i, raw_row = matches[0]
            value = raw_row.get(row["variable"])
            flags = raw_row.get(row["variable"] + "_ATTRIBUTES", "").split(",")
            raw_quality = flags[1] if len(flags) > 1 else ""
            if (None if value is None else parse_exact(value)) != row[
                "value"
            ] or raw_quality != original["quality_flag"]:
                raise ValueError("GHCND raw value or quality flag mismatch")
            locators.append(
                SourceLocator(
                    kind="json_pointer",
                    path=capture.artifact.path,
                    sha256=capture.artifact.sha256,
                    role="source_bytes",
                    pointer=f"/{i}",
                )
            )
            self.fact_checks["GHCND_raw_daily_rows"] += 1
        elif family == "USDM":
            ui, original = self.usdm_rows[row["entity"], row["support"]]
            if (row["value"], row["variable"], row["unit"], row["quality"], card["source"]) != (
                original["dm"],
                "USDM_category",
                "DM_level",
                "valid",
                original["source_capture"],
            ):
                raise ValueError("USDM fact differs from frozen point calculation")
            locators.append(self.locator("data/USDM_POINTS.json", f"/{ui}"))
            self.fact_checks["USDM_frozen_point_rows"] += 1
        else:
            path, ai, array = self.arrays[card["source"]]
            if (row["entity"], row["variable"], row["unit"], row["quality"], array["dtype"]) != (
                array["event_id"],
                "VIL_encoded_ge_160",
                "pixel_counts",
                "valid",
                "uint8",
            ):
                raise ValueError("SEVIR fact scope differs from raw array metadata")
            # The catalog explicitly declares this otherwise naive column to be UTC.
            center = parse_instant(array["row"]["time_utc"].replace(" ", "T") + "Z")
            frames = [
                i
                for i, offset in enumerate(array["offsets"])
                if center + timedelta(minutes=offset) == support["valid_at"]
            ]
            if len(frames) != 1:
                raise ValueError("SEVIR frame instant missing or ambiguous")
            capture = self.capture(array["sources"][-1])
            tile = SourceLocator(
                kind="uint8_tile",
                path=capture.artifact.path,
                sha256=capture.artifact.sha256,
                role="source_bytes",
                array_shape=array["shape"],
                frame=frames[0],
                box=support["box"],
            )
            pixels = self.reader.resolve(tile)
            counts = {
                "positive": sum(160 <= v < 255 for v in pixels),
                "negative": sum(v < 160 for v in pixels),
            }
            if counts != row["value"]:
                raise ValueError("SEVIR raw tile counts differ from imported fact")
            array_path = (
                (self.bundle / array["array_path"]).relative_to(self.reader.root).as_posix()
            )
            self.reader.resolve(
                SourceLocator(
                    kind="whole_file",
                    path=array_path,
                    sha256=array["file_sha256"],
                    role="derived_product",
                )
            )
            locators.extend([self.locator(path, f"/{ai}"), tile])
            self.fact_checks["SEVIR_raw_tiles"] += 1
        for loc in locators:
            self.reader.resolve(loc)
        return {
            "entity": row["entity"],
            "variable": row["variable"],
            "unit": row["unit"],
            "support": support,
            "version": row["version"],
            "quality": row["quality"],
            "value": row["value"],
            "locators": locators,
        }

    def import_file(self, episode_file):
        result = []
        for ei, item in enumerate(self.read(episode_file)):
            if (
                item["split"] != "development"
                or type(item["cutoff"]) is not int
                or item["cutoff"] < 0
            ):
                raise ValueError(
                    "adapter admits only archived development episodes with logical steps"
                )
            family, cards = item["family"], []
            for ci, old_card in enumerate(item["cards"]):
                records = [
                    self.record(episode_file, ei, ci, ri, family, old_card, row)
                    for ri, row in enumerate(old_card["records"])
                ]
                issued_at = None
                if family == "NHC":
                    issued_at = self.nhc_sources[old_card["source"]][1]["issue_time"]
                    if parse_instant(old_card["issued_at"]) != parse_instant(issued_at):
                        raise ValueError("NHC issue time mismatch")
                cards.append(
                    {
                        "id": old_card["id"],
                        "cost": old_card["cost"],
                        "title": old_card["title"],
                        "source_id": old_card["source"],
                        "issued_at": issued_at,
                        "issue_label": old_card["issued_at"]
                        if issued_at
                        else ("Issue time unknown; frozen legacy label: " + old_card["issued_at"]),
                        "issue_missing_reason": None
                        if issued_at
                        else "archive has a support/capture label, not a product issue instant",
                        "availability": None,
                        "availability_missing_reason": "historical public availability was not proved",
                        "delivery_step": old_card["available_at"],
                        "captures": [self.capture(s) for s in self.sources_for(family, old_card)],
                        "records": records,
                    }
                )
            old_target = item["target"]
            target = {k: old_target[k] for k in ("operator", "entity", "variable", "unit")}
            target["supports"] = [
                self.support(family, label, item["cards"][0]) for label in old_target["supports"]
            ]
            if old_target["operator"] == "revision_delta":
                target.update(versions=old_target["versions"], threshold=old_target["threshold"])
            elif old_target["operator"] == "count_threshold":
                target.update(
                    value_threshold=old_target["value_threshold"],
                    count_threshold=old_target["count_threshold"],
                )
            else:
                array = self.arrays[item["cards"][0]["source"]][2]
                height, width, _ = array["shape"]
                if old_target["total_pixels"] != height * width or any(
                    old_target["support_sizes"][s["label"]]
                    != (s["box"][1] - s["box"][0]) * (s["box"][3] - s["box"][2])
                    for s in target["supports"]
                ):
                    raise ValueError("SEVIR target denominator or support size mismatch")
                target.update(
                    height=height, width=width, fraction_threshold=old_target["fraction_threshold"]
                )
            snapshot = self.locator(episode_file, f"/{ei}", "episode_snapshot")
            identity = "af1-" + sha256((snapshot.sha256 + snapshot.pointer).encode("ascii"))[:24]
            episode = Episode.model_validate(
                {
                    "schema_version": "active_forecast.v1",
                    "id": identity,
                    "origin": "real",
                    "family": family,
                    "group": item["group"],
                    "variant": item["variant"],
                    "split": item["split"],
                    "question": item["question"],
                    "target": target,
                    "time_policy": "archive_delivery",
                    "as_of": None,
                    "delivery_step": item["cutoff"],
                    "cards": cards,
                }
            )
            result.append((item, episode, snapshot))
        return result
