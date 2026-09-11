"""Predeclare coverage-stratified VIL samples without inspecting target values."""

from collections import Counter
import csv
import hashlib
import io
import json
import sys

sys.path.insert(0, "/mnt/afs/260010168/.venvs/disastertrace-source-probe-libs-20260910")
import h5py
import numpy as np

from common import ROOT, capture, dump
from range_reader import captured_file


def main():
    body, source = capture("sevir-catalog-full")
    rows = list(csv.DictReader(io.StringIO(body.decode())))
    layouts = json.loads((ROOT / "data/SEVIR_RANGE_MANIFEST.json").read_text())["layouts"]
    counts = Counter((r["id"], r["img_type"]) for r in rows)
    candidates, rejections = [], []
    for row in rows:
        if row["img_type"] != "vil" or row["file_name"] not in layouts or not 0 < float(row["pct_missing"] or 0) < 1:
            continue
        offsets = [int(v) for v in row["minute_offsets"].split(":")]
        if counts[row["id"], "vil"] != 1 or len(offsets) != 49 or any(a >= b for a, b in zip(offsets, offsets[1:])):
            rejections.append({"id": row["id"], "reason": "duplicate identity or invalid native clock", "pct_missing": row["pct_missing"]})
            continue
        candidates.append(row)
    selected, groups = [], set()
    for lower, upper in [(0, 0.01), (0.01, 0.1), (0.1, 1.0)]:
        n = 0
        for row in sorted(candidates, key=lambda r: (r["time_utc"], r["id"])):
            fraction = float(row["pct_missing"])
            group = row["episode_id"] or row["time_utc"][:10]
            if lower < fraction <= upper and group not in groups:
                selected.append(row)
                groups.add(group)
                n += 1
                if n == 2:
                    break
    probes, samples = [], []
    for row in selected:
        short = hashlib.sha256(row["file_name"].encode()).hexdigest()[:10]
        keys = ["sevir-header-" + short, "sevir-tail-" + short]
        handle, provenance = captured_file(keys)
        with h5py.File(handle, "r") as archive:
            dataset = archive["vil"]
            index = int(row["file_index"])
            if archive["id"][index].decode() != row["id"] or dataset.chunks is not None:
                raise ValueError("source identity/storage mismatch")
            size = int(np.prod(dataset.shape[1:])) * dataset.dtype.itemsize
            start = dataset.id.get_offset() + index * size
            ident = "sevir-coverage-" + short + "-" + str(index)
            samples.append({"id": ident, "row": row, "shape": list(dataset.shape[1:]), "dtype": str(dataset.dtype),
                            "header_tail_ids": keys, "prior_sources": provenance})
            probes.append({"id": ident, "kind": "source-natural-coverage", "url": provenance[0]["url"],
                           "range": f"bytes={start}-{start+size-1}", "max_bytes": size})
    dump(ROOT / "data/NATURAL_COVERAGE_SELECTION.json", {"source": source, "samples": samples,
        "candidates": len(candidates), "rejections": rejections,
        "selection": "At most2chronological distinct-process samples per catalog missing-fraction stratum(0,.01],(.01,.1],(.1,1); existing verified storage files; all49frames inspected after acquisition.",
        "label_based_selection": False, "coverage_stratified": True,
        "limit": "Deliberately samples coverage defects, not their natural population prevalence."})
    dump(ROOT / "specs/data_07.json", {"probes": probes})
    print(json.dumps({"samples": len(samples), "candidates": len(candidates), "clock_rejections": len(rejections),
                      "selected": [(x["row"]["id"], x["row"]["pct_missing"]) for x in samples]}))


if __name__ == "__main__":
    main()
