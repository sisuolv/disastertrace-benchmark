"""Bounded public model metadata acquisition; no weights, packages or model generation."""

import hashlib
import json
from pathlib import Path
import urllib.parse
import urllib.request

from disastertrace.forecast_live.storage import now, write

ROOT = Path(__file__).resolve().parent
CANDIDATES = ("deepseek-ai/DeepSeek-R1-Distill-Qwen-7B", "Qwen/Qwen3-14B")
SELECTED_FILES = {"config.json", "tokenizer_config.json", "generation_config.json", "README.md", "LICENSE"}


def fetch(url, path):
    request = urllib.request.Request(url, headers={"User-Agent": "DisasterTrace-model-metadata/1"})
    with urllib.request.urlopen(request, timeout=60) as response:
        data = response.read(25_000_001)
        if len(data) > 25_000_000:
            raise ValueError("metadata response exceeds bounded size")
        with path.open("xb") as stream:
            stream.write(data)
        return data, {"url": url, "retrieved_at": now(), "status": response.status,
                      "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def main():
    write(ROOT / "ACQUISITION_CLAIM.json", {"created_at": now(), "candidates": CANDIDATES,
          "file_allowlist": sorted(SELECTED_FILES), "weight_downloads": False,
          "model_calls": 0, "automatic_retries": 0})
    results = []
    for model in CANDIDATES:
        folder = ROOT / model.replace("/", "--")
        folder.mkdir(exist_ok=False)
        base = "https://modelscope.cn/api/v1/models/" + model
        listing_url = base + "/repo/files?Revision=master&Recursive=true"
        write(folder / "listing_intent.json", {"url": listing_url, "at": now()})
        try:
            raw, receipt = fetch(listing_url, folder / "listing.json")
            write(folder / "listing_receipt.json", receipt)
            listing = json.loads(raw)
            if listing.get("Code") != 200:
                raise ValueError("model catalogue listing rejected")
            files = [f for f in listing["Data"]["Files"] if f["Type"] == "blob"]
            receipts = []
            for item in files:
                if item["Path"] not in SELECTED_FILES:
                    continue
                url = base + "/repo?" + urllib.parse.urlencode({"Revision": item["Revision"], "FilePath": item["Path"]})
                write(folder / (item["Path"] + ".intent.json"), {"url": url, "expected_sha256": item["Sha256"], "at": now()})
                _, saved = fetch(url, folder / item["Path"])
                if saved["sha256"] != item["Sha256"] or saved["bytes"] != item["Size"]:
                    raise ValueError("metadata bytes differ from official per-file digest")
                receipts.append({"path": item["Path"], "revision": item["Revision"], **saved})
            result = {"model": model, "status": "metadata_downloaded", "files": receipts,
                      "indexed_weight_bytes": sum(f["Size"] for f in files if f["Path"].endswith(".safetensors")),
                      "missing_requested_metadata": sorted(SELECTED_FILES - {r["path"] for r in receipts}),
                      "generation_authorized": False}
        except Exception as exc:
            result = {"model": model, "status": "failed", "error": type(exc).__name__ + ": " + str(exc)}
        write(folder / "RESULT.json", result)
        results.append(result)
        print({k: v for k, v in result.items() if k != "files"}, flush=True)
    write(ROOT / "METADATA_RESULTS.json", results)


if __name__ == "__main__":
    main()
