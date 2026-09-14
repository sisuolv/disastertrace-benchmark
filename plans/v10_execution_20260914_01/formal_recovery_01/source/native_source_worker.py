"""Read one registered native product in a separate, claimed worker process."""

import argparse
import hashlib
import json
import time
from pathlib import Path

from disastertrace.monitoring_v1.spool_backend import digest, publish, read
from disastertrace.monitoring_v1.targets import canonical_hash


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--data", type=Path, required=True)
    args = parser.parse_args()
    path = args.request
    key = path.name.removesuffix(".request.json")
    if not (path.parent / (key + ".claim.json")).is_file():
        raise ValueError("A durable worker claim is required")
    start = time.process_time()
    request, data = read(path), read(args.data)
    query_id = request["request"]["query_id"]
    product = next(r for r in data["query_results"] if r["query_id"] == query_id)
    raw = json.dumps(product, sort_keys=True, separators=(",", ":"))
    seconds = time.process_time() - start
    value = {"call_id": request["call_id"], "request_sha256": digest(path),
        "execution_sha256": request["execution_sha256"], "raw": raw,
        "raw_sha256": hashlib.sha256(raw.encode()).hexdigest(),
        "input_tokens": 0, "output_tokens": 0, "compute_seconds": seconds,
        "ended_with_eos": True}
    publish(path.parent / (key + ".source_provenance.json"), {
        "source_data_sha256": digest(args.data), "product_sha256": canonical_hash(product),
        "timing_scope": "worker CPU parse/serialize; lifecycle clock separately includes wall wait"})
    receipt = path.parent / (key + ".worker.json")
    publish(receipt, value)
    publish(path.parent / (key + ".response.json"), {**value,
        "schema": "disastertrace.spool_response.v1", "worker_receipt_sha256": digest(receipt)})


if __name__ == "__main__":
    main()
