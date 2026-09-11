"""Natural fixed-valid-time NHC revisions with separately labeled delivery controls."""

from collections import Counter, defaultdict
import json
import re

from common import ROOT, digest, dump


def extract_forecast_independent(product, valid_time):
    day = valid_time[8:10]
    hhmm = valid_time[11:13] + valid_time[14:16]
    lines = product["raw_text"].splitlines()
    hits = []
    for index, line in enumerate(lines[:-1]):
        if line.startswith(("FORECAST VALID", "OUTLOOK VALID")) and day + "/" + hhmm + "Z" in line:
            tokens = lines[index + 1].split()
            if tokens[:2] == ["MAX", "WIND"]:
                hits.append(int(tokens[2]))
    if len(hits) != 1:
        raise ValueError("independent valid-time line extraction failed")
    return hits[0]


def main():
    chains = json.loads((ROOT / "data/NHC_REVISION_CHAINS.json").read_text())
    products = json.loads((ROOT / "data/NHC_PRODUCTS.json").read_text())
    by_product = {(p["storm_id"], p["advisory_number"]): p for p in products}
    selected = defaultdict(list)
    for chain in chains:
        if len(chain["revisions"]) >= 3 and len(selected[chain["storm_id"]]) < 3:
            selected[chain["storm_id"]].append(chain)
    public, private = [], []
    for storm, rows in sorted(selected.items()):
        for chain in rows:
            trace_id = "s" + digest((storm + chain["target_time"]).encode())[:16]
            target = {"storm_id": storm, "valid_time": chain["target_time"], "variable": "NHC forecast maximum wind", "unit": "kt"}
            revisions = [by_product[storm, r["advisory_number"]] for r in chain["revisions"][:3]]
            cards = []
            values = {}
            for product in revisions:
                cid = "n" + digest(product["source"]["sha256"].encode())[:10]
                cards.append({"id": cid, "issue_time": product["issue_time"], "source_url": product["source"]["url"],
                              "text": product["raw_text"]})
                value = extract_forecast_independent(product, chain["target_time"])
                expected = next(r["wind_kt"] for r in product["forecasts"] if r["valid_time"] == chain["target_time"])
                if value != expected:
                    raise ValueError("source parser and independent locator disagree")
                values[cid] = {"wind_kt": value, "source_id": cid, "issue_time": product["issue_time"]}
            product = revisions[1]
            line = next(line for line in product["raw_text"].splitlines() if line.startswith("MAX SUSTAINED WINDS"))
            current = {"id": "n" + digest((product["source"]["sha256"] + "current").encode())[:10],
                "issue_time": product["issue_time"], "source_url": product["source"]["url"],
                "text": "Published current-intensity estimate, not a future forecast. Storm " + storm + "\n" + line}
            other_product = next(p for p in reversed(products) if p["storm_id"] != storm)
            other = {"id": "n" + digest(other_product["source"]["sha256"].encode())[:10],
                "issue_time": other_product["issue_time"], "source_url": other_product["source"]["url"], "text": other_product["raw_text"]}
            deliveries = [cards[0], cards[1], current, cards[2], cards[0], cards[2], other]
            kinds = ["initial_forecast", "natural_same_target_revision", "current_intensity_distractor",
                     "natural_same_target_revision", "controlled_stale_redelivery", "controlled_duplicate", "other_storm_distractor"]
            states = []
            for index in range(len(deliveries)):
                eligible = {c["id"]: values[c["id"]] for c in deliveries[:index + 1] if c["id"] in values}
                state = max(eligible.values(), key=lambda r: r["issue_time"])
                states.append({"step": index, "kind": kinds[index], "expected": state,
                    "value_changed": index > 0 and states[-1]["expected"]["wind_kt"] != state["wind_kt"],
                    "source_changed": index > 0 and states[-1]["expected"]["source_id"] != state["source_id"]})
            public.append({"id": trace_id, "target": target, "deliveries": deliveries})
            private.append({"id": trace_id, "storm_id": storm, "target_time": chain["target_time"], "steps": states,
                "natural_source_ids": [p["source"]["capture_id"] for p in revisions],
                "independent_source_locator_check": True})
    dump(ROOT / "data/STATE_PUBLIC.json", public)
    dump(ROOT / "data/STATE_REFERENCES_PRIVATE.json", private)
    dump(ROOT / "analysis/STATE_CONSTRUCTION.json", {"traces": len(public), "storm_groups": len(selected),
        "checkpoints_per_trace": 7, "checkpoints": sum(len(t["steps"]) for t in private),
        "selection": "First3chronological chains per4development storms with at least3published forecast versions; no value-based selection.",
        "step_kinds": dict(Counter(s["kind"] for t in private for s in t["steps"])),
        "value_changes": sum(s["value_changed"] for t in private for s in t["steps"]),
        "source_changes": sum(s["source_changed"] for t in private for s in t["steps"]),
        "delivery_clock": "Controlled2026archive replay, not proven historical first availability.",
        "native_source": "Forecast/advisory text preserved; current-intensity distractor is an explicitly labeled source excerpt.",
        "outcome_loaded": False, "relation_to_pilot": "Same development source storms; additional diagnostic opportunities, not new independent events."})
    print(json.dumps({"traces": len(public), "checkpoints": sum(len(t["steps"]) for t in private)}))


if __name__ == "__main__":
    main()
