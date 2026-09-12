"""Independently verify inherited/new bytes and representative decoded contracts."""

import argparse
import csv
import gzip
import hashlib
import io
import json
import tarfile
import zipfile
from collections import Counter
from pathlib import Path

import h5py
import numpy as np
import rasterio
import xarray as xr
from PIL import Image

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent


def read(path):
    return json.loads(path.read_text())


def digest_file(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024**2), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    inventory = read(ROOT / "usage_02/USAGE_REGISTRY.json")
    prior = read(REPO / inventory["prior_registry"]["path"])
    audit = read(ROOT / "decoded_02/AUDIT.json")
    reports = {r["source_id"]: r for r in audit["reports"]}
    expected = {}

    def register(path, sha256, size):
        item = (sha256, size)
        if path in expected and expected[path] != item:
            raise ValueError("Conflicting asset identities: " + path)
        expected[path] = item

    inherited = read(
        REPO / "plans/all_candidate_data_validation_20260912/INHERITED_INTEGRITY.json"
    )
    for r in inherited["files_checked"]:
        register(r["path"], r["expected_sha256"], r["expected_bytes"])
    for s in prior["sources"]:
        for check in s["new_scientific_checks"]:
            for f in check["files"]:
                register(f["path"], f["sha256"], f["bytes"])
    for f in read(ROOT / "decoded_02/SOURCE_BINDINGS.json"):
        register(f["path"], f["sha256"], f["bytes"])
    receipts = []
    for directory in sorted(ROOT.glob("captures_*")) + [ROOT / "camels_zip_01/ranges"]:
        for path in sorted(directory.glob("*.json")):
            r = read(path)
            if "body_file" not in r:
                continue
            body = directory / r["body_file"]
            register(str(body.relative_to(REPO)), r["sha256"], r["bytes"])
            receipts.append(r)
    checked = []
    for path, (sha256, size) in sorted(expected.items()):
        p = REPO / path
        actual_size = p.stat().st_size if p.exists() else None
        actual_hash = digest_file(p) if p.exists() else None
        checked.append(
            {
                "path": path,
                "bytes": actual_size,
                "sha256": actual_hash,
                "expected_bytes": size,
                "size_bound_in_original": size is not None,
                "passed": actual_hash == sha256
                and (size is None or actual_size == size),
            }
        )
    (args.output / "FILE_CHECKS.json").write_text(json.dumps(checked, indent=2) + "\n")
    assert all(r["passed"] for r in checked), "Source identity check failed"
    assert len(receipts) == inventory["network"]["logical_requests"] == 93
    assert (
        sum(r["bytes"] for r in receipts) == inventory["network"]["response_body_bytes"]
    )
    assert len(inventory["sources"]) == 97
    assert (
        dict(Counter(s["state"] for s in inventory["sources"]))
        == inventory["state_counts"]
    )
    assert inventory["state_counts"] == {
        "decoded_sample": 84,
        "authorization_pending": 4,
        "catalog_records_only": 6,
        "no_decoded_target_sample": 3,
    }
    assert len(inventory["hazard_chains"]) == 16
    assert not any(s["new_formal_task_admitted"] for s in inventory["sources"])
    checks = [
        "source_hashes",
        "97_entry_inventory",
        "16_hazard_roles",
        "network_accounting",
    ]

    hdf = ROOT / "extracted_inputs/TCIR-ALL_2017.h5"
    with gzip.open(ROOT / "captures_02/tcir-full-2017.body", "rb") as compressed:
        with tarfile.open(fileobj=compressed, mode="r|") as archive:
            members = []
            for member in archive:
                assert member.isfile() and member.name == hdf.name
                stream = archive.extractfile(member)
                h = hashlib.sha256()
                size = 0
                for chunk in iter(lambda stream=stream: stream.read(1024**2), b""):
                    h.update(chunk)
                    size += len(chunk)
                assert (
                    size == hdf.stat().st_size
                    and h.hexdigest() == expected[str(hdf.relative_to(REPO))][0]
                )
                members.append(member.name)
        while compressed.read(1024**2):
            pass
    assert members == [hdf.name]
    with (
        h5py.File(hdf, "r") as f,
        np.load(ROOT / "decoded_02/tcir_six_frames.npz") as frames,
    ):
        assert f["matrix"].shape == (4580, 201, 201, 4)
        assert np.array_equal(f["matrix"][:6], frames["matrix"], equal_nan=True)
        assert len(f["info/block0_values"]) == 4580
    checks.append("tcir_full_gzip_crc_and_extracted_member_hash_and_six_frames")

    for path in sorted((ROOT / "camels_zip_01").glob("member_*.nc")):
        with xr.open_dataset(path) as dataset:
            assert dataset.sizes["time"] == 394488
            assert np.all(np.diff(dataset.time.values) == np.timedelta64(1, "h"))
            assert dataset.streamflow.attrs["units"] == "m3 s-1"
            assert dataset.water_level.attrs["units"] == "m"
    checks.append("camelsh_nominal_grid_and_units")
    with zipfile.ZipFile(ROOT / "captures_01/cems-product-proxy.body") as archive:
        assert archive.testzip() is None
        features = [
            f
            for name in archive.namelist()
            if name.endswith(".json")
            for f in json.loads(archive.read(name))["features"]
        ]
        assert (
            len(features) == 604 and sum(f["geometry"] is None for f in features) == 2
        )
    checks.append("cems_crc_and_null_geometry_denominator")
    for ident in ["6279", "6287", "6332"]:
        with (
            Image.open(ROOT / f"captures_06/floodnet-{ident}-jpg.body") as image,
            Image.open(ROOT / f"captures_06/floodnet-{ident}_lab-png.body") as mask,
        ):
            image.load()
            array = np.asarray(mask)
            assert image.size == mask.size == (4000, 3000)
            assert not np.isin(array, [1, 3]).any()
    checks.append("floodnet_matched_negative_pairs")
    grids = []
    for path in sorted((ROOT / "captures_06").glob("senfor-000000-*.body")):
        with rasterio.open(path) as ds:
            grids.append((ds.shape, ds.crs, ds.transform))
    assert len(grids) == 7 and all(g == grids[0] for g in grids)
    checks.append("senfor_seven_aligned_components_without_invented_label_legend")
    selection = read(ROOT / "CRISIS_SELECTION.json")
    with zipfile.ZipFile(ROOT / "captures_01/crisismmd-splits-proxy.body") as archive:
        assert archive.testzip() is None
        annotations = list(
            csv.DictReader(
                io.StringIO(archive.read(selection["member"]).decode()), delimiter="\t"
            )
        )
    indexed = {r["image_id"]: r for r in annotations}
    for i, record in enumerate(selection["records"]):
        assert record == indexed[record["image_id"]]
        receipt = read(ROOT / f"captures_08/crisis-pair-{i}.json")
        assert receipt["url"].endswith(record["image"])
        with Image.open(ROOT / f"captures_08/crisis-pair-{i}.body") as image:
            image.load()
    checks.append("crisismmd_exact_original_annotation_image_join")
    prefix = (ROOT / "captures_10/urban-positive-mask-strips.body").read_bytes()
    tail = (ROOT / "captures_13/urban-positive-mask-tail.body").read_bytes()
    assert prefix[-65536:] == tail[:65536]
    window = np.frombuffer(prefix + tail[65536:], dtype="<f4").reshape(256, 18927)[
        :, 5632:5888
    ]
    assert np.array_equal(
        window, np.load(ROOT / "decoded_02/urban_matched_mask.npy", allow_pickle=False)
    )
    values, counts = np.unique(window, return_counts=True)
    assert dict(zip(values.tolist(), counts.tolist())) == {0: 50726, 1: 14755, 2: 55}
    checks.append("urban_partial_prefix_recovered_by_matching_tail_and_overlap")
    for sid, number, name in [
        ("AW-GWIS", 11, "gwis-native-chart-api"),
        ("AW-EFFIS", 15, "effis-native-chart-api"),
    ]:
        raw = read(ROOT / f"captures_{number:02d}/{name}.body")
        assert len(raw["x_data"]) == 5 and len(raw["y_data"]) == 8
        assert raw["y_data"] == reports[sid]["details"]["y_data"]
        assert all(
            len(values) == 5 and np.isfinite(values).all()
            for values in raw["y_data"].values()
        )
    assert reports["AW-EFFIS"]["details"]["shares_backend_with"] == "AW-GWIS"
    checks.append("fire_index_series_and_shared_lineage")
    result = {
        "passed": True,
        "checks": checks,
        "files_checked": checked,
        "unique_files": len(checked),
        "bytes_hashed": sum(x["bytes"] for x in checked),
        "prior_857_rechecked": len(inherited["files_checked"]),
        "logical_data_requests": len(receipts),
        "limit": "Asset preservation and sampled contracts; not full scientific QC, historical arrival certification or independent-event/novelty proof.",
    }
    (args.output / "VERIFY.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "files_checked"}))


if __name__ == "__main__":
    main()
