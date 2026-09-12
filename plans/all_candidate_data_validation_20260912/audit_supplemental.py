"""Read bounded TCIR image arrays and reconstruct WeatherQA's official annotation sample."""

import io
import json
from pathlib import Path
import re
import struct
import tarfile
import zlib

import h5py
from PIL import Image

from audit_samples import ROOT, REPO, digest, stats


class PrefixFile(io.RawIOBase):
    """Expose a declared-size archive member, refusing reads outside captured bytes."""

    def __init__(self, prefix, declared_size):
        self.prefix, self.declared_size, self.position = prefix, declared_size, 0

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=0):
        self.position = offset + (self.position if whence == 1 else self.declared_size if whence == 2 else 0)
        if self.position < 0:
            raise ValueError("Negative member offset")
        return self.position

    def read(self, size=-1):
        if size < 0 or self.position + size > len(self.prefix):
            raise OSError("Requested HDF5 region has not been captured")
        data = self.prefix[self.position:self.position + size]
        self.position += size
        return data

    def readinto(self, buffer):
        data = self.read(len(buffer))
        buffer[:len(data)] = data
        return len(data)


def main():
    reports = []
    source = ROOT / "captures_09/tcir-confirmed-prefix.body"
    raw = source.read_bytes()
    prefix = zlib.decompressobj(31).decompress(raw, 64 * 1024 * 1024)
    header = tarfile.TarInfo.frombuf(prefix[:512], "utf-8", "strict")
    assert header.name == "TCIR-ALL_2017.h5" and prefix[512:520] == b"\x89HDF\r\n\x1a\n"
    with h5py.File(PrefixFile(prefix[512:], header.size), "r") as dataset:
        matrix = dataset["matrix"][:3]
        shape = list(dataset["matrix"].shape)
    assert matrix.shape == (3, 201, 201, 4)
    reports.append(dict(source_id="D04", check_id="tcir-three-native-image-arrays", level="numeric_sample_decoded",
                        files=[dict(path=str(source.relative_to(REPO)), sha256=digest(raw), bytes=len(raw))],
                        details=dict(member=header.name, declared_member_size=header.size, array_shape=shape,
                                     captured_uncompressed_prefix_bytes=len(prefix) - 512, samples=stats(matrix),
                                     unobserved_reads_refused=True, full_gzip_crc_checked=False,
                                     limitation="Three real four-channel arrays from a captured prefix. HDF5 info labels lie outside this prefix and remain unavailable. No missing bytes are filled or synthesized.")))

    parts = [ROOT / "captures_08/weatherqa-drive-prefix.body", ROOT / "captures_09/weatherqa-json-remainder.body"]
    receipts = [json.loads(p.with_suffix(".json").read_text()) for p in parts]
    assert all(r["curl_exit"] == 0 and r["http_status"] == 206 for r in receipts)
    assert [r["response_headers"]["content-range"] for r in receipts] == ["bytes 0-8388607/12803203", "bytes 8388608-12803202/12803203"]
    assert receipts[0]["url"] == receipts[1]["url"]
    assert receipts[0]["response_headers"]["last-modified"] == receipts[1]["response_headers"]["last-modified"]
    body = b"".join(p.read_bytes() for p in parts)
    assert len(body) == 12803203
    annotations = json.loads(body)
    assert len(annotations) > 3
    lookup = {path.removeprefix("./"): key for key, entry in annotations.items() for path in entry["para_paths"]}
    examples = []
    for path in sorted(ROOT.glob("captures_10/weatherqa-image-prefix-*.body")):
        raw = path.read_bytes()
        offset = 0
        while offset + 30 <= len(raw) and len(examples) < 3:
            if raw[offset:offset + 4] != b"PK\x03\x04":
                break
            h = struct.unpack_from("<4s5H3I2H", raw, offset)
            if h[2] & 8:
                break
            name = raw[offset + 30:offset + 30 + h[-2]].decode()
            start = offset + 30 + h[-2] + h[-1]
            end = start + h[7]
            if end > len(raw):
                break
            data = zlib.decompress(raw[start:end], -15) if h[3] == 8 else raw[start:end]
            assert len(data) == h[8] and zlib.crc32(data) == h[6]
            offset = end
            normalized = name.removeprefix("./")
            suffix = re.search(r"((?:19|20)\d{2}/[^/]+/[^/]+\.gif)$", normalized)
            if suffix:
                normalized = "md_image/" + suffix[1]
            if normalized not in lookup or not normalized.endswith(".gif"):
                continue
            with Image.open(io.BytesIO(data)) as image:
                image.load()
                info = dict(size=list(image.size), format=image.format)
            key = lookup[normalized]
            examples.append(dict(archive_path=str(path.relative_to(REPO)), member=name, member_sha256=digest(data),
                                 image=info, exact_annotation_path_matched=True, record_id=key,
                                 annotation=annotations[key]))
    files = parts + list(ROOT.glob("captures_10/weatherqa-image-prefix-*.body"))
    reports.append(dict(source_id="D49", check_id="weatherqa-official-json-and-images",
                        level="paired_content_decoded" if examples else "annotation_records_decoded",
                        files=[dict(path=str(p.relative_to(REPO)), sha256=digest(p.read_bytes()), bytes=p.stat().st_size) for p in files],
                        details=dict(full_annotation_json_reconstructed=True, bytes=len(body), sha256=digest(body),
                                     annotation_records=len(annotations), paired_examples=examples,
                                     first_annotations={k: annotations[k] for k in list(annotations)[:3]},
                                     limitation="Annotation text describes existing forecast discussion, not independent event truth. Each image is a weather-variable map; multiple maps are not automatically different time steps.")))
    (ROOT / "SUPPLEMENTAL_AUDIT.json").write_text(json.dumps(dict(reports=reports), indent=2, allow_nan=False) + "\n")
    print([(r["source_id"], r["level"]) for r in reports])


if __name__ == "__main__":
    main()
