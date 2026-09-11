"""Join chip footprints to official event polygons, preserving source aliases."""

from datetime import datetime
import io
import json
import sys

sys.path[:0] = [
    "/mnt/afs/260010168/.venvs/disastertrace-source-probe-libs-20260910",
    "/mnt/afs/260010168/.venvs/disastertrace-feasibility-libs-20260910",
]
import numpy as np
from shapely.geometry import Point, shape
import tifffile

from common import ROOT, capture, dump


def main():
    metadata, metadata_source = capture("sen1-metadata")
    events = json.loads(metadata)["features"]
    chips = json.loads((ROOT / "data/SEN1_SELECTION.json").read_text())["chips"]
    pairs, failures = [], []
    for chip in chips:
        try:
            layers = {}
            for layer in ["LabelHand", "S1Hand"]:
                body, source = capture("sen1-" + chip + "-" + layer)
                with tifffile.TiffFile(io.BytesIO(body)) as archive:
                    layers[layer] = (archive.asarray(), archive.pages[0].geotiff_tags, source)
            label, left, _ = layers["LabelHand"]
            sar, right, _ = layers["S1Hand"]
            if label.shape != (512, 512) or sar.shape != (2, 512, 512):
                raise ValueError("unexpected raster dimensions")
            if any(left[k] != right[k] for k in ["GeographicTypeGeoKey", "GTRasterTypeGeoKey", "GeogAngularUnitsGeoKey"]):
                raise ValueError("CRS or pixel convention differs")
            if left["GeographicTypeGeoKey"] != 4326:
                raise ValueError("spatial join requires EPSG4326")
            error = max(float(np.max(np.abs(np.array(left[k]) - right[k])))
                        for k in ["ModelPixelScale", "ModelTiepoint"])
            if error > 1e-10:
                raise ValueError("grid mismatch")
            i, j, _, x, y, _ = left["ModelTiepoint"]
            sx, sy, _ = left["ModelPixelScale"]
            center = Point(x + (256 - i) * sx, y - (256 - j) * sy)
            hits = [f for f in events if shape(f["geometry"]).covers(center)]
            if len(hits) != 1:
                raise ValueError("event spatial join missing or ambiguous")
            event = hits[0]["properties"]
            delta = (datetime.strptime(event["s1_date"], "%Y/%m/%d") -
                     datetime.strptime(event["s2_date"], "%Y/%m/%d")).days
            pairs.append({"chip": chip, "raw_chip_prefix": chip.split("_")[0], "event": event,
                "event_join": "unique official polygon covering chip center; no string alias guessed",
                "chip_center_lonlat": [center.x, center.y], "grid_error_degrees": error,
                "s1_minus_s2_days": delta, "same_grid": True,
                "label_counts": {str(int(v)): int(n) for v, n in zip(*np.unique(label, return_counts=True))},
                "source_ids": [layers[k][2]["capture_id"] for k in layers]})
        except Exception as error:
            failures.append({"chip": chip, "type": type(error).__name__, "error": str(error)})
    dump(ROOT / "analysis/SEN1_FEASIBILITY_03.json", {"planned_pairs": len(chips),
        "decoded_spatially_aligned_pairs": len(pairs), "pairs": pairs, "failures": failures,
        "metadata_source": metadata_source, "georef_tolerance_degrees": 1e-10,
        "prior_reports": ["SEN1_FEASIBILITY.json", "SEN1_FEASIBILITY_02.json"],
        "rights_status": "STAC proprietary field; official repository license evidence checked separately",
        "semantic_limit": "Published water labels, not necessarily newly flooded water; S1/S2 dates can differ."})
    print(json.dumps({"complete_pairs": len(pairs), "failures": len(failures),
                      "joins": [[x["chip"], x["event"]["location"], x["s1_minus_s2_days"]] for x in pairs]}, indent=2))


if __name__ == "__main__":
    main()
