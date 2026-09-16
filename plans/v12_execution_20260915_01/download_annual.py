"""Bounded native acquisition with one global rate limit and durable attempts."""
import datetime as dt
import hashlib
import importlib.util
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "annual_stage_B"


def read(p):
    return json.loads(p.read_text())


def write(p, obj):
    with p.open("x") as f:
        json.dump(obj, f, allow_nan=False)


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


class Rate:
    def __init__(self, per_second, deadline):
        self.lock = threading.Lock()
        self.interval = 1 / per_second
        self.next = 0
        self.pause = 0
        self.hits = 0
        self.deadline = deadline
        self.stopped = False

    def acquire(self):
        while True:
            with self.lock:
                if self.stopped or time.time() >= self.deadline or (OUT / "STOP_REQUEST.json").exists():
                    return False
                now = time.monotonic()
                delay = max(self.next, self.pause) - now
                if delay <= 0:
                    self.next = now + self.interval
                    return True
            time.sleep(min(delay, 1))

    def feedback(self, status):
        with self.lock:
            if status == 429:
                self.hits += 1
                self.interval *= 2
                self.pause = time.monotonic() + 120
                self.stopped = self.hits >= 5
            elif status in (401, 403):
                self.stopped = True


def main():
    registration = read(OUT / "DOWNLOAD_REGISTRATION.json")
    if digest(OUT / "OBJECTS.json") != registration["objects_sha256"]:
        raise ValueError("Registered source universe changed")
    path = OUT / "source/fetch_public.py"
    if digest(path) != registration["source_code_sha256"]:
        raise ValueError("Registered HTTP implementation changed")
    records = {r["request_key"]: r for r in read(OUT / "OBJECTS.json")}
    keys = registration["missing_keys"]
    if any(records[k]["state"] != "missing_bytes" for k in keys) or len(keys) != len(set(keys)):
        raise ValueError("Download must use only unique, unverified registered sources")
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        os.environ.pop(name, None)
    attempts = OUT / "native_attempts"; attempts.mkdir(exist_ok=False)
    for prefix in {k[:2] for k in keys}:
        (attempts / prefix).mkdir()
    write(OUT / "DOWNLOAD_CLAIM.json", {"at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "script_sha256": digest(Path(__file__)), "registration_sha256": digest(OUT / "DOWNLOAD_REGISTRATION.json"),
        "initial_requests": len(keys), "retries_max": registration["retry_attempts_max"]})
    loader = importlib.util.spec_from_file_location("frozen_fetch", path)
    transport = importlib.util.module_from_spec(loader); loader.loader.exec_module(transport)
    rate = Rate(registration["global_requests_per_second"], dt.datetime.fromisoformat(registration["deadline_at"]).timestamp())

    def capture(key, generation):
        if not rate.acquire():
            return {"key": key, "generation": generation, "attempted": False, "status": "stopped_before_dispatch"}
        record = records[key]
        request = record["request"]
        if not request["url"].startswith("https://mesonet.agron.iastate.edu/api/1/nwstext/") or request["max_bytes"] != 131072:
            raise ValueError("Unregistered native endpoint or byte cap")
        stem = attempts / key[:2] / (key + f".g{generation}")
        write(stem.with_suffix(stem.suffix + ".intent.json"), {"key": key, "generation": generation, "request": request,
            "started_at": dt.datetime.now(dt.timezone.utc).isoformat()})
        started = time.monotonic()
        raw, fields = transport.curl_fetch(request)
        rate.feedback(fields["http_status"])
        body = stem.with_suffix(stem.suffix + ".body")
        with body.open("xb") as f:
            f.write(raw)
        receipt_path = stem.with_suffix(stem.suffix + ".json")
        receipt = {**request, **fields, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
            "body_file": body.name, "seconds": time.monotonic() - started,
            "finished_at": dt.datetime.now(dt.timezone.utc).isoformat(), "first_seen_is_historical": False,
            "as_of_admission": False, "generation": generation, "request_key": key}
        write(receipt_path, receipt)
        return {"key": key, "generation": generation, "attempted": True,
            "complete": receipt["complete"], "http_status": receipt["http_status"],
            "body_path": str(body), "receipt_path": str(receipt_path), "receipt_sha256": digest(receipt_path),
            "sha256": receipt["sha256"], "bytes": len(raw), "seconds": receipt["seconds"]}

    rows = []
    started = time.monotonic()
    def progress(final=False):
        successes = {r["key"] for r in rows if r.get("complete")}
        payload = {"at": dt.datetime.now(dt.timezone.utc).isoformat(), "planned_unique": len(keys),
            "attempts": sum(r["attempted"] for r in rows), "verified_new_unique": len(successes),
            "failed_attempts": sum(r["attempted"] and not r.get("complete", False) for r in rows),
            "bytes": sum(r.get("bytes", 0) for r in rows), "429_count": rate.hits,
            "current_global_rps": 1 / rate.interval, "seconds": time.monotonic() - started,
            "remaining_unverified": len(keys) - len(successes), "terminal": final,
            "confirmation_opened": False, "model_calls": 0}
        tmp = OUT / "DOWNLOAD_STATUS.tmp"; tmp.write_text(json.dumps(payload, indent=2)); tmp.replace(OUT / "DOWNLOAD_STATUS.json")
        print(json.dumps(payload), flush=True)

    def phase(todo, generation):
        iterator = iter(todo)
        with ThreadPoolExecutor(max_workers=registration["transport_workers"]) as pool:
            pending = set()
            def enqueue():
                key = next(iterator, None)
                if key is not None:
                    pending.add(pool.submit(capture, key, generation))
            for _ in range(registration["transport_workers"]):
                enqueue()
            while pending:
                done, pending = wait(pending, return_when=FIRST_COMPLETED)
                for future in done:
                    row = future.result(); rows.append(row)
                    if len(rows) % 100 == 0:
                        progress()
                    if not row["attempted"]:
                        rate.stopped = True
                    if not rate.stopped and time.time() < rate.deadline:
                        enqueue()
    phase(keys, 1)
    retry = sorted(r["key"] for r in rows if r["attempted"] and not r.get("complete") and r.get("http_status") not in (401, 403, 404))[:registration["retry_attempts_max"]]
    if retry and not rate.stopped:
        write(OUT / "RETRY_REGISTRATION.json", {"keys": retry, "generation": 2, "original_failures_retained": True})
        phase(retry, 2)
    write(OUT / "DOWNLOAD_RESULTS.json", rows)
    progress(final=True)


if __name__ == "__main__":
    main()
