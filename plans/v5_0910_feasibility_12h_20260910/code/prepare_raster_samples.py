"""Freeze exact HDF5 event ranges and training-split flood sample identities."""

import csv
import hashlib
import io
import json
import sys
import zipfile
from collections import defaultdict

sys.path.insert(0, "/mnt/afs/260010168/.venvs/disastertrace-source-probe-libs-20260910")
import h5py
import numpy as np

from common import ROOT, capture, dump
from range_reader import captured_file


def main():
    selection = json.loads((ROOT / "data/SEVIR_SELECTION.json").read_text())
    samples, probes, layouts = [], [], {}
    for event in selection["events"]:
        for row in event["rows"]:
            filename = row["file_name"]
            short = hashlib.sha256(filename.encode()).hexdigest()[:10]
            keys = ["sevir-header-" + short, "sevir-tail-" + short]
            handle, sources = captured_file(keys)
            with h5py.File(handle, "r") as archive:
                dataset = archive[row["img_type"]]
                index = int(row["file_index"])
                if dataset.chunks is not None:
                    raise ValueError("this small-sample reader requires contiguous data")
                assert archive["id"][index].decode() == event["id"]
                size = int(np.prod(dataset.shape[1:])) * dataset.dtype.itemsize
                start = dataset.id.get_offset() + index * size
                key = f'sevir-event-{short}-{index}'
                samples.append({"event_id": event["id"], "row": row, "capture_id": key,
                                "header_tail_ids": keys, "array_shape": list(dataset.shape[1:]),
                                "dtype": str(dataset.dtype)})
                layouts[filename] = {"shape": list(dataset.shape), "dtype": str(dataset.dtype),
                                     "offset": dataset.id.get_offset(), "sources": sources}
                probes.append({"id": key, "url": sources[0]["url"], "kind": "hdf5-event-range",
                               "max_bytes": size, "range": f"bytes={start}-{start+size-1}"})
    body, provenance = capture("sen1-train-list-retrieval-02")
    rows = list(csv.reader(io.StringIO(body.decode())))
    by_event = defaultdict(list)
    for row in rows:
        chip = row[0].split("_S1")[0]
        by_event[chip.split("_")[0]].append(chip)
    chips = [chip for country in sorted(by_event)[:4] for chip in sorted(by_event[country])[:2]]
    for chip in chips:
        for layer in ["LabelHand", "S1Hand"]:
            probes.append({"id": "sen1-" + chip + "-" + layer,
                           "url": "https://storage.googleapis.com/sen1floods11/v1.1/data/flood_events/HandLabeled/"
                                  + layer + "/" + chip + "_" + layer + ".tif",
                           "kind": "training-split-raster", "max_bytes": 4 * 1024**2})
    body, source = capture("sen1-catalog")
    licenses = defaultdict(int)
    examples = {}
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        assert archive.testzip() is None
        for name in archive.namelist():
            if name.endswith(".json") and not name.startswith("__MACOSX/") and not name.split("/")[-1].startswith("._"):
                record = json.loads(archive.read(name))
                if "license" in record:
                    licenses[record["license"]] += 1
                    examples.setdefault(record["license"], {"path": name, "record": record})
    dump(ROOT / "data/SEVIR_RANGE_MANIFEST.json", {"samples": samples, "layouts": layouts})
    dump(ROOT / "data/SEN1_SELECTION.json", {"basis": "first two lexical training chips from first four lexical event groups; no label/content selection",
                                            "train_split_source": provenance, "chips": chips})
    dump(ROOT / "analysis/SEN1_STAC_LICENSE.json", {"source": source, "license_counts": dict(licenses), "examples": examples})
    dump(ROOT / "specs/data_02.json", {"probes": probes})
    print(json.dumps({"sevir_samples": len(samples), "sen1_chips": chips,
                      "stac_licenses": dict(licenses), "probes": len(probes)}, indent=2))


if __name__ == "__main__":
    main()
