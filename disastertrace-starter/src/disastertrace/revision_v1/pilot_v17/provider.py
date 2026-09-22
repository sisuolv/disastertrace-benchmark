"""Local credential broker and append-only provider capture for the v17 pilot."""

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
from pathlib import Path
import socket
import socketserver
import struct
import threading
import time
import urllib.error
import urllib.request

MODELS = [
    "deepseek-ai/DeepSeek-V4-Flash",
    "Qwen/Qwen3.8-27B",
    "zai-org/GLM-5.3",
]
STAGE_CAPS = {"smoke": 12, "main": 432, "e2": 108, "e3": 24, "retry": 24}
API_BASE = "https://api.siliconflow.cn/v1"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def utc_now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def append_json(path, value):
    with Path(path).open("a", encoding="utf-8") as handle:
        handle.write(canonical(value) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def recv_message(conn):
    def exact(n):
        result = bytearray()
        while len(result) < n:
            block = conn.recv(n - len(result))
            if not block:
                raise ConnectionError("incomplete local frame")
            result.extend(block)
        return bytes(result)
    size = struct.unpack("!I", exact(4))[0]
    if size > 16 * 1024 * 1024:
        raise ValueError("local frame exceeds cap")
    return json.loads(exact(size))


def send_message(conn, value):
    body = canonical(value).encode()
    conn.sendall(struct.pack("!I", len(body)) + body)


def address(run):
    return "\0dt-v17-" + hashlib.sha256(str(Path(run).resolve()).encode()).hexdigest()[:20]


def call_broker(run, command, **kwargs):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
        conn.settimeout(660)
        conn.connect(address(run))
        send_message(conn, {"command": command, **kwargs})
        return recv_message(conn)


class Broker:
    def __init__(self, run, secret):
        self.run = Path(run)
        self.secret = secret
        self.lock = threading.Lock()
        self.counts = {name: 0 for name in STAGE_CAPS}
        self.requests = {}
        self.responses = {}
        self.model_locks = {name: threading.Semaphore(2) for name in MODELS}
        attempts = self.run / "attempts.jsonl"
        if attempts.exists():
            for line in attempts.read_text().splitlines():
                row = json.loads(line)
                self.requests[row["logical_id"]] = row
                self.counts[row["stage"]] += 1
        captures = self.run / "responses.jsonl"
        if captures.exists():
            for line in captures.read_text().splitlines():
                row = json.loads(line)
                self.responses[row["logical_id"]] = row

    def _http(self, suffix, body=None):
        headers = {"Authorization": "Bearer " + self.secret, "Content-Type": "application/json"}
        request = urllib.request.Request(
            API_BASE + suffix,
            data=canonical(body).encode() if body is not None else None,
            headers=headers,
            method="POST" if body is not None else "GET",
        )
        started = time.monotonic()
        try:
            with urllib.request.urlopen(request, timeout=480 if body is not None else 30) as response:
                data = response.read(16 * 1024 * 1024)
                parsed = json.loads(data)
                # Headers and request objects are never persisted.
                return {"http_status": response.status, "provider_response": parsed,
                        "error": None, "latency_s": time.monotonic() - started}
        except urllib.error.HTTPError as error:
            text = error.read(16384).decode(errors="replace").replace(self.secret, "[REDACTED]")
            return {"http_status": error.code, "provider_response": None,
                    "error": {"kind": "HTTPError", "body": text},
                    "latency_s": time.monotonic() - started}
        except Exception as error:
            return {"http_status": None, "provider_response": None,
                    "error": {"kind": type(error).__name__, "detail": str(error).replace(self.secret, "[REDACTED]")},
                    "latency_s": time.monotonic() - started}

    def handle(self, query):
        command = query.get("command")
        if command == "status":
            with self.lock:
                return {"counts": dict(self.counts), "total_attempts": sum(self.counts.values()),
                        "responses": len(self.responses), "pending": len(self.requests) - len(self.responses)}
        if command == "catalog":
            result = self._http("/models")
            response = result.get("provider_response") or {}
            available = {item.get("id") for item in response.get("data", [])}
            result["requested_models"] = {model: model in available for model in MODELS}
            result["observed_at"] = utc_now()
            (self.run / "model_catalog.json").write_text(canonical(result) + "\n")
            return {"http_status": result["http_status"], "requested_models": result["requested_models"],
                    "error": result["error"], "model_count": len(available)}
        if command != "chat":
            raise ValueError("unsupported broker operation")
        stage, logical_id, payload = query["stage"], query["logical_id"], query["payload"]
        if stage not in STAGE_CAPS or payload.get("model") not in MODELS:
            raise ValueError("unregistered stage/model")
        if payload.get("stream") is not False:
            raise ValueError("pilot broker requires non-streaming capture")
        if type(payload.get("max_tokens")) is not int or not 1 <= payload["max_tokens"] <= 8192:
            raise ValueError("invalid output cap")
        if not isinstance(logical_id, str) or not logical_id.startswith(stage + ":"):
            raise ValueError("logical identity must be stage scoped")
        body_hash = digest(payload)
        with self.lock:
            if logical_id in self.requests:
                if self.requests[logical_id]["request_sha256"] != body_hash:
                    raise ValueError("identity reused with different input")
                if logical_id in self.responses:
                    return {"reused_capture": True, **self.responses[logical_id]}
                return {"logical_id": logical_id, "status": "UNRESOLVED_PRIOR_ATTEMPT", "resend_allowed": False}
            if self.counts[stage] >= STAGE_CAPS[stage] or sum(self.counts.values()) >= 600:
                raise ValueError("attempt cap reached")
            if stage != "smoke" and not (self.run / "PROTOCOL_LOCK.json").exists():
                raise ValueError("real experiment not locked")
            if stage == "retry":
                parent = query.get("retry_of")
                original = self.responses.get(parent)
                if not original or original.get("http_status") not in (429, 500, 502, 503, 504):
                    raise ValueError("only explicit retryable HTTP responses may be retried")
                if any(item.get("retry_of") == parent for item in self.requests.values()):
                    raise ValueError("one retry maximum")
                if original["request_sha256"] != body_hash:
                    raise ValueError("retry input mismatch")
            row = {"logical_id": logical_id, "stage": stage, "model": payload["model"],
                   "request_sha256": body_hash, "created_at": utc_now(),
                   "max_tokens": payload["max_tokens"], "retry_of": query.get("retry_of"),
                   "metadata": query.get("metadata", {}), "attempt_number": sum(self.counts.values()) + 1}
            append_json(self.run / "attempts.jsonl", row)
            self.requests[logical_id] = row
            self.counts[stage] += 1
        with self.model_locks[payload["model"]]:
            result = self._http("/chat/completions", payload)
        record = {**row, **result, "completed_at": utc_now()}
        with self.lock:
            append_json(self.run / "responses.jsonl", record)
            self.responses[logical_id] = record
        return record


def serve(run):
    secret = os.environ.get("SILICONFLOW_API_KEY") or getpass.getpass("SiliconFlow credential (not echoed): ")
    if not secret:
        raise ValueError("empty credential")
    os.environ["SILICONFLOW_API_KEY"] = secret
    broker = Broker(run, secret)

    class Handler(socketserver.BaseRequestHandler):
        def handle(self):
            try:
                _, uid, _ = struct.unpack("3i", self.request.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                if uid != os.getuid():
                    raise PermissionError("local caller UID differs")
                result = broker.handle(recv_message(self.request))
            except Exception as error:
                result = {"broker_error": type(error).__name__, "message": str(error).replace(secret, "[REDACTED]")}
            send_message(self.request, result)

    class Server(socketserver.ThreadingUnixStreamServer):
        daemon_threads = True

    with Server(address(run), Handler) as server:
        Path(run, "runtime", "provider_process.json").write_text(
            canonical({"pid": os.getpid(), "started_at": utc_now(), "secret_persisted": False}) + "\n")
        print("Credential accepted in process memory; local provider broker ready.", flush=True)
        server.serve_forever(poll_interval=0.5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=["serve", "catalog", "status"])
    parser.add_argument("--run", required=True)
    args = parser.parse_args()
    if args.operation == "serve":
        serve(args.run)
    else:
        print(canonical(call_broker(args.run, args.operation)))
