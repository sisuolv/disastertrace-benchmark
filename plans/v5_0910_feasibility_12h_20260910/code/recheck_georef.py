"""Replace exact floating-point equality with a declared subpixel tolerance.

The initial rejection report remains intact. This checks raw captures again,
without changing geographic coordinates or silently correcting source clocks.
"""

import io
import json
import sys
from datetime import datetime

sys.path.insert(0, "/mnt/afs/260010168/.venvs/disastertrace-source-probe-libs-20260910")
import numpy as np
import tifffile

from common import ROOT, capture, dump

TOL_DEGREES = 1e-10


def main():
    original = json.loads((ROOT / "analysis/SEVIR_FEASIBILITY.json").read_text())
    arrays = json.loads((ROOT / "data/SEVIR_ARRAYS.json").read_text())
    for check in original["alignments"]:
        rows = [x["row"] for x in arrays if x["event_id"] == check["event_id"]]
        coords = np.asarray([[float(r[k]) for k in ("llcrnrlat", "llcrnrlon", "urcrnrlat", "urcrnrlon")]
                             for r in rows])
        error = float(np.max(np.abs(coords - coords[0])))
        same = error <= TOL_DEGREES and len({r["proj"] for r in rows}) == 1
        check.update(same_geographic_extent=same, max_extent_difference_degrees=error,
                     eligible_three_channel_clock=check["unique_channel_rows"] and
                     check["same_offset_grid"] and check["strictly_ordered"] and same)
    original["clock_eligible_events"] = sum(x["eligible_three_channel_clock"] for x in original["alignments"])
    original["georef_tolerance_degrees"] = TOL_DEGREES
    original["supersedes_validation_report"] = "analysis/SEVIR_FEASIBILITY.json (exact string equality falsely rejected floating-point roundoff)"
    dump(ROOT / "analysis/SEVIR_FEASIBILITY_02.json", original)
    selection = json.loads((ROOT / "data/SEN1_SELECTION.json").read_text())["chips"]
    metadata = json.loads(capture("sen1-metadata")[0])
    events = {x["properties"]["location"].lower(): x["properties"] for x in metadata["features"]}
    pairs, failures = [], []
    for chip in selection:
        try:
            rows = {}
            for layer in ["LabelHand", "S1Hand"]:
                body, source = capture("sen1-" + chip + "-" + layer)
                with tifffile.TiffFile(io.BytesIO(body)) as archive:
                    data = archive.asarray()
                    geo = archive.pages[0].geotiff_tags
                    rows[layer] = (data, geo, source)
            label, left, _ = rows["LabelHand"]
            sar, right, _ = rows["S1Hand"]
            if label.shape != (512, 512) or sar.shape != (2, 512, 512):
                raise ValueError("raster dimensions differ")
            for field in ["GeographicTypeGeoKey", "GTRasterTypeGeoKey", "GeogAngularUnitsGeoKey"]:
                if left[field] != right[field]:
                    raise ValueError("CRS/pixel convention differs")
            error = max(float(np.max(np.abs(np.array(left[field]) - right[field])))
                        for field in ["ModelPixelScale", "ModelTiepoint"])
            if error > TOL_DEGREES:
                raise ValueError("actual grid misregistration")
            event = events[chip.split("_")[0].lower()]
            delta = (datetime.strptime(event["s1_date"], "%Y/%m/%d") -
                     datetime.strptime(event["s2_date"], "%Y/%m/%d")).days
            pairs.append({"chip": chip, "event": event, "grid_error_degrees": error,
                          "s1_minus_s2_days": delta, "same_grid": True,
                          "label_counts": {str(int(v)): int(n) for v, n in zip(*np.unique(label, return_counts=True))},
                          "source_ids": [rows[k][2]["capture_id"] for k in rows]})
        except Exception as error:
            failures.append({"chip": chip, "error_type": type(error).__name__, "error": str(error)})
    report = {"planned_pairs": len(selection), "decoded_spatially_aligned_pairs": len(pairs),
              "pairs": pairs, "failures": failures, "georef_tolerance_degrees": TOL_DEGREES,
              "supersedes_validation_report": "analysis/SEN1_FEASIBILITY.json (exact float equality issue)",
              "rights_status": "STAC proprietary; still excluded from unrestricted v1 release",
              "temporal_limit": "Same acquisition date alone does not prove pixel-level simultaneous label truth."}
    dump(ROOT / "analysis/SEN1_FEASIBILITY_02.json", report)
    print(json.dumps({"sevir_clock_eligible_events": original["clock_eligible_events"],
                      "sen1_complete_pairs": len(pairs), "sen1_failed_pairs": len(failures)}, indent=2))


if __name__ == "__main__":
    main()
