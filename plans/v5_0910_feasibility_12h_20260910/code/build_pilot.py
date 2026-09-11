"""Construct a small retrospective development pilot from verified products.

No future outcome file is opened. Withheld-pool variants are declared controlled
interventions on availability; they are not claimed as natural sensor failures.
"""

import copy
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta

import numpy as np

from common import ROOT, digest, dump
from evidence_core import certificates, legal_cards, reference, validate_episode


def record(entity, variable, unit, support, value, quality="valid", version="original"):
    return {"entity": entity, "variable": variable, "unit": unit, "support": support,
            "value": value, "quality": quality, "version": version}


def card(source, records, issued_at, title):
    return {"id": None, "source": source, "records": records, "issued_at": issued_at,
            "available_at": 0, "cost": 1, "title": title}


def episode(key, family, group, question, target, cards):
    for i, item in enumerate(cards):
        item["id"] = "c" + digest((key + ":" + str(i)).encode())[:8]
    cards.sort(key=lambda c: c["id"])
    return {"id": "e" + digest(key.encode())[:16], "construction_key": key,
            "family": family, "group": group, "question": question,
            "target": target, "cutoff": 0, "cards": cards,
            "availability_profile": "retrospective fixed pool; logical delivery step 0, not proved historical availability",
            "split": "development", "variant": "complete_pool"}


def nhc_cases():
    products = json.loads((ROOT / "data/NHC_PRODUCTS.json").read_text())
    chains = json.loads((ROOT / "data/NHC_REVISION_CHAINS.json").read_text())
    index = {(x["storm_id"], x["advisory_number"]): x for x in products}
    cases = []
    for storm in sorted({x["storm_id"] for x in products}):
        eligible = [x for x in chains if x["storm_id"] == storm and len(x["revisions"]) >= 3]
        for chain in eligible[:3]:
            revisions = chain["revisions"][:3]
            chosen = [index[storm, r["advisory_number"]] for r in revisions]
            other_storm = next(x for x in sorted({p["storm_id"] for p in products}) if x != storm)
            chosen.append(index[other_storm, 1])
            cards = []
            for product in chosen:
                version = "advisory-" + str(product["advisory_number"])
                rows = [record(product["storm_id"], "maximum_sustained_wind_forecast", "kt",
                               f["valid_time"], f["wind_kt"], version=version) for f in product["forecasts"]]
                cards.append(card(product["source"]["capture_id"], rows, product["issue_time"],
                                  f'NHC {product["storm_id"]} {version}'))
            before, after = ["advisory-" + str(r["advisory_number"]) for r in revisions[:2]]
            target = {"entity": storm, "variable": "maximum_sustained_wind_forecast", "unit": "kt",
                      "supports": [chain["target_time"]], "operator": "revision_delta",
                      "versions": [before, after], "threshold": 10}
            question = (f"For {storm}, compare the maximum sustained wind forecasts valid at {chain['target_time']} "
                        f"in {before} and {after}. Did the forecast increase by at least 10 kt? "
                        "Use these exact two advisory versions; a later advisory is not a replacement for either.")
            cases.append(episode(storm + ":" + chain["target_time"], "NHC", storm, question, target, cards))
    return cases


def ghcn_cases():
    rows = json.loads((ROOT / "data/GHCND_RECORDS.json").read_text())["records"]
    index = {(x["station"], x["date"]): x for x in rows if x["variable"] == "TMAX"}
    stations = sorted({x[0] for x in index})
    cases = []
    for station in stations:
        for start in ["2021-06-01", "2021-06-13", "2021-06-25", "2021-07-07"]:
            dates = [(datetime.fromisoformat(start) + timedelta(days=i)).date().isoformat() for i in range(3)]
            keys = [(station, date) for date in dates]
            keys.append((next(s for s in stations if s != station), dates[0]))
            cards = []
            for key in keys:
                row = index[key]
                quality = "valid" if row["quality_flag"] == "" and row["value"] is not None else "invalid"
                cards.append(card("ghcnd-" + row["station"], [record(row["station"], "TMAX", "degC", row["date"],
                                  row["value"], quality)], "retrospective-2026-09-10", "GHCN-Daily station daily record"))
            target = {"entity": station, "variable": "TMAX", "unit": "degC", "supports": dates,
                      "operator": "count_threshold", "value_threshold": 35, "count_threshold": 2}
            question = (f"For station {station}, was TMAX at least 35 degC on at least two of these station dates: "
                        + ", ".join(dates) + "? Dates are station daily support, not asserted UTC day intervals. "
                        "This fixed threshold task is not a climatological heat-wave definition.")
            cases.append(episode(station + ":" + start, "GHCND", "station-" + station, question, target, cards))
    return cases


def usdm_cases():
    rows = json.loads((ROOT / "data/USDM_POINTS.json").read_text())
    cases = []
    for location in sorted({x["location"] for x in rows}):
        values = sorted([x for x in rows if x["location"] == location], key=lambda x: x["map_date"])
        supports = [x["map_date"] for x in values[:3]]
        cards = [card(x["source_capture"], [record(location, "USDM_category", "DM_level", x["map_date"], x["dm"])],
                      x["map_date"], "USDM point-in-polygon product reading") for x in values]
        target = {"entity": location, "variable": "USDM_category", "unit": "DM_level", "supports": supports,
                  "operator": "count_threshold", "value_threshold": 2, "count_threshold": 2}
        question = (f"At the declared {location} test point, was the USDM category D2 or above on at least two "
                    f"of the map dates {', '.join(supports)}? DM=-1 means outside D0-D4 polygons at this CONUS point. "
                    "These are different weekly states, not revisions of the same week's product.")
        cases.append(episode("USDM:" + location, "USDM", "USDM-CONUS-20240827-20240917", question, target, cards))
    return cases


def sevir_cases():
    arrays = json.loads((ROOT / "data/SEVIR_ARRAYS.json").read_text())
    qualified = {x["event_id"] for x in json.loads((ROOT / "analysis/SEVIR_FEASIBILITY_02.json").read_text())["alignments"]
                 if x["eligible_three_channel_clock"]}
    cases = []
    for row in sorted(arrays, key=lambda x: (x["event_id"], x["channel"])):
        if row["channel"] != "vil" or row["event_id"] not in qualified:
            continue
        array = np.load(ROOT / row["array_path"], allow_pickle=False)
        for frame in [18, 30]:
            field = array[:, :, frame]
            event = row["event_id"]
            at = (datetime.fromisoformat(row["row"]["time_utc"]) +
                  timedelta(minutes=row["offsets"][frame])).isoformat() + "Z"
            cards, supports, sizes = [], [], {}
            for qi, (ys, xs) in enumerate([(slice(0, 192), slice(0, 192)), (slice(0, 192), slice(192, 384)),
                                           (slice(192, 384), slice(0, 192)), (slice(192, 384), slice(192, 384))]):
                support = at + ":quadrant-" + str(qi)
                patch = field[ys, xs]
                values = {"positive": int(((patch >= 160) & (patch != 255)).sum()),
                          "negative": int((patch < 160).sum())}
                cards.append(card(row["sources"][-1]["capture_id"],
                                  [record(event, "VIL_encoded_ge_160", "pixel_counts", support, values)],
                                  at, f"SEVIR VIL frame {frame}, disjoint quadrant {qi}; 255 is missing"))
                supports.append(support)
                sizes[support] = int(patch.size)
            target = {"entity": event, "variable": "VIL_encoded_ge_160", "unit": "pixel_counts",
                      "operator": "area_threshold", "supports": supports, "support_sizes": sizes,
                      "total_pixels": int(field.size), "fraction_threshold": 0.01}
            question = (f"For SEVIR {event} at {at}, do the products establish that at least 1% of all "
                        f"{field.size} pixels have VIL encoded value >=160? Positive counts exclude 255; "
                        "negative counts are <160. The remainder is missing, never negative. Unread quadrants "
                        "are also unknown. This concerns a VIL product threshold, not surface rainfall or damage.")
            cases.append(episode(event + ":frame-" + str(frame), "SEVIR", row["row"]["episode_id"] or event,
                                 question, target, cards))
    return cases


def main():
    base = nhc_cases() + ghcn_cases() + usdm_cases() + sevir_cases()
    episodes = []
    interventions = []
    for item in base:
        validate_episode(item)
        episodes.append(item)
        altered = copy.deepcopy(item)
        relevant = [c for c in altered["cards"] if any(
            r["entity"] == item["target"]["entity"] and r["support"] in item["target"]["supports"]
            and (item["target"]["operator"] != "revision_delta" or r["version"] in item["target"]["versions"])
            for r in c["records"])]
        removed = relevant[0]["id"]
        altered["cards"] = [c for c in altered["cards"] if c["id"] != removed]
        altered["id"] = "e" + digest((item["construction_key"] + ":withheld").encode())[:16]
        altered["variant"] = "controlled_pool_withholding"
        altered["parent_id"] = item["id"]
        validate_episode(altered)
        episodes.append(altered)
        interventions.append({"parent": item["id"], "variant": altered["id"], "removed_card": removed,
                              "changes_to_measurements": False, "natural_source_outage": False})
    references = {}
    for item in episodes:
        refs = {"goal": reference(item, {c["id"] for c in legal_cards(item)}),
                "certificates": certificates(item)}
        references[item["id"]] = refs
    summary = {"base_cases": len(base), "controlled_variants": len(episodes) - len(base),
               "total_episodes": len(episodes), "families": dict(Counter(x["family"] for x in episodes)),
               "goal_decisions": dict(Counter(x["goal"]["decision"] for x in references.values())),
               "minimum_costs": dict(Counter(x["certificates"]["minimum_cost"] for x in references.values())),
               "independence": "Variants, neighboring targets and repeated frames are not independent events.",
               "native_raster_inference": False,
               "input_representation": "Task-relevant product facts; text versus an image containing exactly the same table rows.",
               "source_fact_role": "Published products and deterministic derived measurements, not independent physical ground truth.",
               "outcome_inputs_loaded": False, "prospective_forecasting": False,
               "claim_limit": "This pilot checks feasibility of support scoring and acquisition; it is not the final benchmark release."}
    dump(ROOT / "data/PILOT_EPISODES_PRIVATE.json", episodes)
    dump(ROOT / "data/PILOT_REFERENCES_PRIVATE.json", references)
    dump(ROOT / "data/PILOT_INTERVENTIONS.json", interventions)
    dump(ROOT / "analysis/PILOT_CONSTRUCTION.json", summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
