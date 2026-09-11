"""Decode all selected native VIL frames and validate unaltered coverage bounds."""

from collections import Counter
from datetime import datetime, timedelta, timezone
import io
import json

import numpy as np

from build_pilot import card, episode, record
from common import ROOT, capture, digest, dump
from evidence_core import certificates, legal_cards, reference, validate_episode
from model_adapter import sha_file


def main():
    selection = json.loads((ROOT / "data/NATURAL_COVERAGE_SELECTION.json").read_text())
    directory = ROOT / "data/natural_coverage_arrays"
    directory.mkdir(exist_ok=False)
    arrays, reports, failures, episodes = [], [], [], []
    for sample in selection["samples"]:
        try:
            body, source = capture(sample["id"])
            etags = {x["headers"]["etag"] for x in sample["prior_sources"]} | {source["headers"]["etag"]}
            if len(etags) != 1:
                raise ValueError("source object version changed")
            values = np.frombuffer(body, dtype=np.dtype(sample["dtype"])).reshape(sample["shape"])
            row = sample["row"]
            offsets = [int(v) for v in row["minute_offsets"].split(":")]
            if values.shape != (384, 384, 49) or len(offsets) != 49 or any(a >= b for a, b in zip(offsets, offsets[1:])):
                raise ValueError("native shape/clock invalid")
            path = directory / (sample["id"] + ".npy")
            np.save(path, values, allow_pickle=False)
            arrays.append({"event_id": row["id"], "channel": "vil", "array_path": str(path.relative_to(ROOT)),
                "file_sha256": sha_file(path), "row": row, "offsets": offsets,
                "shape": list(values.shape), "dtype": str(values.dtype), "sources": sample["prior_sources"] + [source]})
            frames = []
            for index in range(49):
                data = values[:, :, index]
                pos = int(((data >= 160) & (data != 255)).sum())
                neg = int((data < 160).sum())
                missing = int((data == 255).sum())
                assert pos + neg + missing == data.size
                lower, upper = pos / data.size, 1 - neg / data.size
                decision = "yes" if lower >= .01 else "no" if upper < .01 else "unknown"
                frames.append({"frame": index, "positive": pos, "negative": neg, "missing": missing,
                    "missing_fraction": missing / data.size, "lower": lower, "upper": upper, "decision": decision})
            fraction = float(np.mean(values == 255))
            if abs(fraction - float(row["pct_missing"])) > 1e-10:
                raise ValueError("catalog missing fraction disagrees with decoded source")
            missing_frames = [f["frame"] for f in frames if f["missing"] > 0]
            first_missing = missing_frames[0]
            other = min((f for f in frames if f["frame"] != first_missing), key=lambda f: (f["missing"], f["frame"]))["frame"]
            chosen = [first_missing, other]
            for index in chosen:
                center = datetime.fromisoformat(row["time_utc"]).replace(tzinfo=timezone.utc)
                at = (center + timedelta(minutes=offsets[index])).isoformat().replace("+00:00", "Z")
                supports = [at + ":quadrant-" + str(q) for q in range(4)]
                cards = []
                for q, support in enumerate(supports):
                    y, x = divmod(q, 2)
                    patch = values[y * 192:(y + 1) * 192, x * 192:(x + 1) * 192, index]
                    counts = {"positive": int(((patch >= 160) & (patch != 255)).sum()), "negative": int((patch < 160).sum())}
                    cards.append(card(sample["id"], [record(row["id"], "VIL_encoded_ge_160", "pixel_counts", support, counts)],
                                      at, f"SEVIR VIL frame {index}, quadrant {q}; native255missing retained"))
                target = {"entity": row["id"], "variable": "VIL_encoded_ge_160", "unit": "pixel_counts",
                    "operator": "area_threshold", "supports": supports, "support_sizes": {s: 192 * 192 for s in supports},
                    "total_pixels": 384 * 384, "fraction_threshold": .01}
                question = (f"For SEVIR {row['id']} at {at}, do the archived products establish that at least1% of all147456pixels "
                    "have encoded VIL>=160?255is missing, not positive or negative. Keep the full-frame denominator. "
                    "This concerns the VIL product, not rainfall or damage.")
                item = episode(row["id"] + ":frame-" + str(index), "SEVIR", row["episode_id"] or row["id"], question, target, cards)
                item["variant"] = "native_missingness"
                validate_episode(item)
                answer = reference(item, {c["id"] for c in legal_cards(item)})
                if answer["decision"] != frames[index]["decision"]:
                    raise ValueError("independent whole-frame interval disagrees with card reference")
                episodes.append(item)
            reports.append({"event_id": row["id"], "catalog_missing_fraction": float(row["pct_missing"]),
                "decoded_missing_fraction": fraction, "frames": frames, "selected_frames": chosen,
                "frame_decisions": dict(Counter(f["decision"] for f in frames)),
                "partly_missing_frames": sum(0 < f["missing"] < 147456 for f in frames),
                "wholly_missing_frames": sum(f["missing"] == 147456 for f in frames)})
        except Exception as error:
            failures.append({"capture_id": sample["id"], "type": type(error).__name__, "error": str(error)})
    dump(ROOT / "data/NATURAL_COVERAGE_ARRAYS.json", arrays)
    dump(ROOT / "data/NATURAL_EPISODES_PRIVATE.json", episodes)
    dump(ROOT / "analysis/NATURAL_COVERAGE_FEASIBILITY.json", {"samples": reports, "failures": failures,
        "complete_native_arrays": len(reports), "frames_examined": sum(len(r["frames"]) for r in reports),
        "selected_episodes": len(episodes), "selected_decisions": dict(Counter(reference(e, [c["id"] for c in legal_cards(e)])["decision"] for e in episodes)),
        "selected_certificate_costs": dict(Counter(certificates(e)["minimum_cost"] for e in episodes)),
        "frame_selection": "First frame with any native255missing; another distinct frame with minimum missing count(earliest tie); no VIL threshold values used to select frames.",
        "source_values_modified": False, "controlled_withholding": False,
        "statistical_limit": "Coverage-stratified diagnostic, not natural missingness prevalence or independent49frame observations."})
    print(json.dumps({"arrays": len(reports), "frames": sum(len(r["frames"]) for r in reports), "episodes": len(episodes), "failures": failures,
        "decisions": dict(Counter(f["decision"] for r in reports for f in r["frames"]))}, indent=2))


if __name__ == "__main__":
    main()
