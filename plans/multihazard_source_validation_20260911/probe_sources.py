"""Bounded anonymous GET probes with persistent per-attempt evidence."""

import argparse
import concurrent.futures
import hashlib
import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests


ROOT = Path(__file__).resolve().parent


def now():
    return datetime.now(timezone.utc).isoformat()


def read(path):
    return json.loads(path.read_text())


def write(path, obj):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(obj, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


class Budget:
    def __init__(self, scope):
        self.scope = scope
        self.lock = threading.Lock()
        self.deadline = datetime.fromisoformat(scope["created_at"]).timestamp() + scope["max_wall_seconds"]
        self.attempts = 0
        self.bytes = 0
        self.hosts = {}
        for directory in (ROOT / "attempts").iterdir():
            intent = read(directory / "intent.json")
            self.attempts += 1
            result = directory / "response.json"
            self.bytes += read(result)["captured_bytes"] if result.exists() else intent["byte_reservation"]

    def reserve(self, url, limit, probe_id):
        with self.lock:
            if time.time() >= self.deadline:
                raise RuntimeError("scope_deadline")
            if self.attempts >= self.scope["max_http_attempts"]:
                raise RuntimeError("scope_request_limit")
            if self.bytes + limit > self.scope["max_captured_response_body_bytes"]:
                raise RuntimeError("scope_byte_limit")
            self.attempts += 1
            self.bytes += limit
            path = ROOT / "attempts" / f"{self.attempts:04d}"
            path.mkdir(exist_ok=False)
            write(path / "intent.json", {"url": url, "probe_id": probe_id, "at": now(), "byte_reservation": limit})
            return path

    def finish(self, reserved, actual):
        with self.lock:
            self.bytes -= reserved - actual

    def host(self, url):
        with self.lock:
            host = urlsplit(url).netloc
            if host not in self.hosts:
                self.hosts[host] = (threading.Semaphore(self.scope["max_per_host_requests"]), threading.Lock(), [0.0])
            return self.hosts[host]


def fetch(url, probe, budget):
    scope = budget.scope
    limit = probe.get("max_bytes", 512 * 1024)
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or parts.username or parts.password:
        raise ValueError("unsupported or credential-bearing URL")
    path = budget.reserve(url, limit, probe["id"])
    semaphore, start_lock, last_start = budget.host(url)
    body = bytearray()
    result = {"url": url, "started_at": now(), "http_status": None, "headers": {}, "error": None,
              "complete": False, "truncated": False, "attempt_path": str(path.relative_to(ROOT))}
    started = time.monotonic()
    try:
        with semaphore:
            with start_lock:
                delay = scope["minimum_per_host_start_interval_seconds"] - (time.monotonic() - last_start[0])
                if delay > 0:
                    time.sleep(delay)
                last_start[0] = time.monotonic()
            if time.time() >= budget.deadline:
                raise RuntimeError("scope_deadline_before_network")
            network_started = time.monotonic()
            result["network_started_at"] = now()
            result["queue_seconds"] = round(network_started - started, 3)
            with requests.Session() as session:
                # Disable implicit .netrc authentication and environment credentials.
                session.trust_env = False
                headers = {"User-Agent": "DisasterTrace-source-availability-research/0.1",
                           "Accept-Encoding": "identity", "Accept": "*/*"}
                if probe.get("range"):
                    headers["Range"] = probe["range"]
                with session.get(url, headers=headers, stream=True, allow_redirects=False,
                                 timeout=(scope["connect_timeout_seconds"], scope["read_timeout_seconds"])) as response:
                    result["http_status"] = response.status_code
                    kept = ("Content-Type", "Content-Length", "Content-Encoding", "Content-Range", "Accept-Ranges",
                            "Location", "ETag", "Last-Modified", "Date", "Retry-After", "Server")
                    result["headers"] = {key.lower(): response.headers[key] for key in kept if key in response.headers}
                    while len(body) < limit:
                        if time.monotonic() - network_started >= scope["per_attempt_wall_seconds"] or time.time() >= budget.deadline:
                            result["truncated"] = True
                            result["stop_reason"] = "time_limit"
                            break
                        block = response.raw.read(min(16384, limit - len(body)), decode_content=False)
                        if not block:
                            result["complete"] = True
                            break
                        body.extend(block)
                    if len(body) == limit:
                        result["complete"] = response.headers.get("Content-Length") == str(len(body))
                        result["truncated"] = not result["complete"]
                        if result["truncated"]:
                            result["stop_reason"] = "body_limit"
    except Exception as error:
        result["error"] = {"type": type(error).__name__, "message": str(error)[:700]}
    finally:
        result["captured_bytes"] = len(body)
        result["body_sha256"] = hashlib.sha256(body).hexdigest()
        result["finished_at"] = now()
        result["elapsed_seconds"] = round(time.monotonic() - started, 3)
        with (path / "body.bin").open("xb") as stream:
            stream.write(body)
        write(path / "response.json", result)
        budget.finish(limit, len(body))
    return result


def probe_one(probe, budget):
    result = {"id": probe["id"], "requested_url": probe["url"], "kind": probe["kind"], "attempt_paths": []}
    url = probe["url"]
    seen = set()
    try:
        for _ in range(budget.scope["max_redirects"] + 1):
            if url in seen:
                result["stop_reason"] = "redirect_loop"
                break
            seen.add(url)
            response = fetch(url, probe, budget)
            result["attempt_paths"].append(response["attempt_path"])
            result["final"] = response
            status = response["http_status"]
            if status not in (301, 302, 303, 307, 308):
                break
            location = response["headers"].get("location")
            if not location:
                result["stop_reason"] = "redirect_without_location"
                break
            url = urljoin(url, location)
        else:
            result["stop_reason"] = "redirect_limit"
    except Exception as error:
        result["stop_reason"] = str(error)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", required=True)
    parser.add_argument("--spec", required=True)
    args = parser.parse_args()
    scope = read(ROOT / "SCOPE.json")
    spec_path = ROOT / args.spec
    spec = read(spec_path)
    batch = ROOT / "batches" / args.batch
    batch.mkdir(exist_ok=False)
    write(batch / "CLAIM.json", {"started_at": now(), "spec": args.spec,
                                "spec_sha256": hashlib.sha256(spec_path.read_bytes()).hexdigest(),
                                "probe_count": len(spec["probes"])})
    budget = Budget(scope)
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=scope["max_concurrent_http_requests"]) as executor:
        jobs = {executor.submit(probe_one, probe, budget): probe for probe in spec["probes"]}
        for future in concurrent.futures.as_completed(jobs):
            result = future.result()
            write(batch / (result["id"] + ".json"), result)
            results.append(result)
            final = result.get("final", {})
            print(json.dumps({"completed": len(results), "total": len(jobs), "id": result["id"],
                              "status": final.get("http_status"), "bytes": final.get("captured_bytes"),
                              "error": final.get("error") or result.get("stop_reason")}, ensure_ascii=False), flush=True)
    write(batch / "COMPLETED.json", {"finished_at": now(), "completed": len(results),
                                    "cumulative_http_attempts": budget.attempts,
                                    "cumulative_captured_body_bytes": budget.bytes})


if __name__ == "__main__":
    main()
