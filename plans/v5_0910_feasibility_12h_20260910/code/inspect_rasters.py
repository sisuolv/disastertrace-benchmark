"""Decode captured real rasters and check temporal, spatial and label semantics."""

import io
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta

sys.path[:0] = ["/mnt/afs/260010168/.venvs/disastertrace-source-probe-libs-20260910"]
import h5py
import numpy as np
import tifffile

from common import ROOT, capture, digest, dump
from range_reader import captured_file


def sevir():
    manifest = json.loads((ROOT / "data/SEVIR_RANGE_MANIFEST.json").read_text())
    records, failed = [], []
    directory = ROOT / "data/sevir_arrays"
    directory.mkdir(exist_ok=False)
    for sample in manifest["samples"]:
        try:
            ids = sample["header_tail_ids"] + [sample["capture_id"]]
            handle, sources = captured_file(ids)
            row = sample["row"]
            index = int(row["file_index"])
            with h5py.File(handle, "r") as archive:
                array = archive[row["img_type"]][index]
                actual_id = archive["id"][index].decode()
            assert actual_id == sample["event_id"]
            assert list(array.shape) == sample["array_shape"]
            path = directory / (sample["capture_id"] + ".npy")
            np.save(path, array, allow_pickle=False)
            offsets = [int(x) for x in row["minute_offsets"].split(":")]
            details = {"event_id": actual_id, "channel": row["img_type"],
                       "row": row, "array_path": str(path.relative_to(ROOT)),
                       "array_sha256": digest(array.tobytes()), "file_sha256": digest(path.read_bytes()),
                       "shape": list(array.shape), "dtype": str(array.dtype),
                       "offsets": offsets, "strictly_increasing_offsets": all(a < b for a, b in zip(offsets, offsets[1:])),
                       "sources": sources, "encoded_min": int(array.min()), "encoded_max": int(array.max())}
            if row["img_type"] == "vil":
                valid = array != 255
                encoded = array.astype(np.float64)
                physical = np.zeros(array.shape, dtype=np.float64)
                mask = (encoded > 5) & (encoded <= 18)
                physical[mask] = (encoded[mask] - 2) / 90.66
                mask = (encoded > 18) & valid
                physical[mask] = np.exp((encoded[mask] - 83.9) / 38.9)
                details.update(valid_pixels=int(valid.sum()), missing_pixels=int((~valid).sum()),
                               physical_units="kg m-2 VIL, not surface precipitation",
                               max_valid_physical=float(physical[valid].max()) if valid.any() else None)
            else:
                details.update(physical_units="degrees C", scale=0.01,
                               scaled_min=float(array.min() * 0.01), scaled_max=float(array.max() * 0.01))
            records.append(details)
        except Exception as error:
            failed.append({"sample": sample, "error": str(error)})
    groups = defaultdict(list)
    for record in records:
        groups[record["event_id"]].append(record)
    alignments = []
    for event, rows in sorted(groups.items()):
        unique = len(rows) == 3 and {x["channel"] for x in rows} == {"ir069", "ir107", "vil"}
        same_grid = unique and len({tuple(x["offsets"]) for x in rows}) == 1
        ordered = all(x["strictly_increasing_offsets"] for x in rows)
        matched_geometry = len({tuple(x["row"][k] for k in ("llcrnrlat", "llcrnrlon", "urcrnrlat", "urcrnrlon", "proj")) for x in rows}) == 1
        alignments.append({"event_id": event, "rows": len(rows), "unique_channel_rows": unique,
                           "same_offset_grid": same_grid, "strictly_ordered": ordered,
                           "same_geographic_extent": matched_geometry,
                           "eligible_three_channel_clock": unique and same_grid and ordered and matched_geometry,
                           "event_type": rows[0]["row"]["event_type"]})
    report = {"planned_arrays": len(manifest["samples"]), "decoded_arrays": len(records),
              "failures": failed, "distinct_catalog_ids": len(groups), "alignments": alignments,
              "clock_eligible_events": sum(x["eligible_three_channel_clock"] for x in alignments),
              "temporal_admission": "Fail ambiguous ID/channel and nonmatching or nonmonotonic clocks; retain native arrays for diagnostics.",
              "future_predictive_claim": "No hail, flood or precipitation forecast accuracy follows from decoding VIL/IR."}
    dump(ROOT / "data/SEVIR_ARRAYS.json", records)
    dump(ROOT / "analysis/SEVIR_FEASIBILITY.json", report)
    return report


def sen1():
    selection = json.loads((ROOT / "data/SEN1_SELECTION.json").read_text())
    records, failed = [], []
    directory = ROOT / "data/sen1_arrays"
    directory.mkdir(exist_ok=False)
    metadata = json.loads(capture("sen1-metadata")[0])
    events = {x["properties"]["location"].lower(): x["properties"] for x in metadata["features"]}
    for chip in selection["chips"]:
        try:
            arrays, georef, sources = {}, {}, {}
            for layer in ["LabelHand", "S1Hand"]:
                body, source = capture("sen1-" + chip + "-" + layer)
                with tifffile.TiffFile(io.BytesIO(body)) as archive:
                    array = archive.asarray()
                    page = archive.pages[0]
                    georef[layer] = {"scale": list(page.tags[33550].value),
                                     "tiepoint": list(page.tags[33922].value),
                                     "geokeys": page.geotiff_tags}
                path = directory / (chip + "-" + layer + ".npy")
                np.save(path, array, allow_pickle=False)
                arrays[layer] = array
                sources[layer] = {"capture": source, "array_path": str(path.relative_to(ROOT)),
                                  "array_sha256": digest(array.tobytes()), "file_sha256": digest(path.read_bytes())}
            label, sar = arrays["LabelHand"], arrays["S1Hand"]
            assert label.shape == (512, 512) and sar.shape == (2, 512, 512)
            assert set(np.unique(label)).issubset({-1, 0, 1})
            assert georef["LabelHand"] == georef["S1Hand"]
            event = events[chip.split("_")[0].lower()]
            delta = (datetime.strptime(event["s1_date"], "%Y/%m/%d") -
                     datetime.strptime(event["s2_date"], "%Y/%m/%d")).days
            records.append({"chip": chip, "event": event, "s1_minus_s2_days": delta,
                            "label_counts": {
                                str(int(value)): int(count) for value, count in zip(*np.unique(label, return_counts=True))},
                            "sources": sources, "georef": georef["LabelHand"],
                            "same_grid": True, "label_semantics": "-1 no data/not valid; 0 not water; 1 water",
                            "raw_SAR_same_time_gold_qualified": delta == 0})
        except Exception as error:
            failed.append({"chip": chip, "error": str(error)})
    report = {"planned_training_chips": len(selection["chips"]), "decoded_pairs": len(records),
              "failed_pairs": failed, "events": sorted({x["chip"].split("_")[0] for x in records}),
              "s1_s2_date_offsets_days": dict(Counter(x["s1_minus_s2_days"] for x in records)),
              "release_admission": "Not selected for an unrestricted v1 release: official STAC says proprietary; README grants access but no explicit alternative license.",
              "label_scope": "Existing water annotations; no new per-item annotation and not automatically newly flooded water."}
    dump(ROOT / "data/SEN1_ARRAYS.json", records)
    dump(ROOT / "analysis/SEN1_FEASIBILITY.json", report)
    return report


if __name__ == "__main__":
    report = {"sevir": sevir(), "sen1": sen1()}
    dump(ROOT / "analysis/RASTER_FEASIBILITY.json", report)
    print(json.dumps(report, indent=2))
