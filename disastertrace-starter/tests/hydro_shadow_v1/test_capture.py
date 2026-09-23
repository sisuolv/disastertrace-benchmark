"""HTTP and durable receipt failure cases, using a local server only."""

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from disastertrace.hydro_shadow_v1.capture import capture_json, file_hash, strict_json
from disastertrace.hydro_shadow_v1.pipeline import supervised_capture


@pytest.fixture
def server():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = {
                "/ok": b'{"value":1}',
                "/error": b'{"error":"unavailable"}',
                "/duplicate": b'{"value":1,"value":2}',
                "/nan": b'{"value":NaN}',
                "/large": b"x" * 1000,
            }[self.path]
            self.send_response(503 if self.path == "/error" else 200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_):
            pass

    http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{http.server_port}"
    http.shutdown()
    http.server_close()
    thread.join()


def test_successful_capture_binds_actual_bytes(server, tmp_path):
    body, receipt = capture_json(server + "/ok", tmp_path / "request")
    assert body == {"value": 1}
    assert receipt["complete"] and receipt["status"] == "received"
    assert receipt["sha256"] == file_hash(tmp_path / "request/response.raw")
    assert strict_json((tmp_path / "request/RECEIPT.json").read_bytes()) == receipt


@pytest.mark.parametrize("route", ["error", "duplicate", "nan", "large"])
def test_http_parse_and_size_failures_preserve_receipts(server, tmp_path, route):
    body, receipt = capture_json(server + "/" + route, tmp_path / "request", max_bytes=100)
    assert body is None and receipt["status"] == "failed"
    assert receipt["sha256"] == file_hash(tmp_path / "request/response.raw")
    assert receipt["bytes"] <= 101 and receipt["automatic_retries"] == 0
    if route == "large":
        assert not receipt["complete"] and receipt["bytes"] == 101


def test_used_capture_is_never_retried(tmp_path):
    directory = tmp_path / "consumed"
    directory.mkdir()
    with pytest.raises(FileExistsError):
        supervised_capture("http://unused.invalid/", directory)


def test_supervised_subprocess_capture(server, tmp_path):
    body, receipt = supervised_capture(server + "/ok", tmp_path / "request")
    assert body == {"value": 1} and receipt["status"] == "received"
    supervision = strict_json((tmp_path / "request/SUPERVISION.json").read_bytes())
    assert supervision["exit_code"] == 0 and not supervision["timed_out"]
