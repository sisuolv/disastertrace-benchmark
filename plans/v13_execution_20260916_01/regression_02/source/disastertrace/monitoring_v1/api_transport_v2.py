"""One-authority API dispatch and receipt-bound, append-only offline recovery.

The authority directory is trusted managed-worker state, not an adversarial
filesystem sandbox. An unknown remote execution is never resent.
"""

import base64
import fcntl
import hashlib
import json
import math
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from ..forecast_task.common import strict_json
from .spool_backend import digest, publish, read
from .targets import canonical_hash

VERSION = "receipt_bound_api.v2"


def policy_for(backend):
    backend.validate_binding()
    policy = backend.execution_contract.get("api_transport_v2")
    if not isinstance(policy, dict) or policy.get("version") != VERSION:
        raise ValueError("Frozen API v2 execution policy required")
    for key in ("input_cap", "output_cap", "read_limit_bytes", "deadline_wall_ns"):
        if type(policy.get(key)) is not int or policy[key] <= 0:
            raise ValueError("Invalid registered API cap or deadline")
    ids = policy.get("allowed_call_ids")
    if not isinstance(ids, list) or not ids or any(type(v) is not str for v in ids) or len(set(ids)) != len(ids):
        raise ValueError("Unique registered call roster required")
    if policy.get("dispatch_authority") != "single_local_authority":
        raise ValueError("Multi-node dispatch authority is not qualified")
    if not Path(policy["authority_directory"]).is_dir():
        raise ValueError("Existing trusted authority directory required")
    return policy


@contextmanager
def authority_lock(policy):
    with (Path(policy["authority_directory"]) / "dispatch.lock").open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def request_stop(backend):
    policy = policy_for(backend)
    with authority_lock(policy):
        path = Path(policy["stop_path"])
        if not path.exists():
            publish(path, {"schema": "disastertrace.api_stop.v2", "observed_wall_ns": time.time_ns(),
                           "execution_sha256": canonical_hash(backend.execution_contract)})


def _put_same(path, value):
    if path.exists():
        if read(path) != value:
            raise ValueError("Immutable API artifact conflicts")
    else:
        publish(path, value)


def prepare_http(payload, policy, credential_path):
    credential = read(Path(credential_path))
    if credential["base_url"].rstrip("/") != policy["base_url"].rstrip("/"):
        raise ValueError("Credential endpoint differs from registered provider")
    key = credential["api_key"]
    if type(key) is not str or not key:
        raise ValueError("Private API credential required")
    request = Request(policy["base_url"].rstrip("/") + "/chat/completions",
                      data=json.dumps(payload, allow_nan=False).encode(),
                      headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    return request, (key.encode(),)


def read_bounded(response, limit):
    chunks, size = [], 0
    while size <= limit:
        part = response.read(min(65536, limit + 1 - size))
        if not part:
            return b"".join(chunks), True
        chunks.append(part)
        size += len(part)
    return b"".join(chunks), False


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def send_http(prepared, limit):
    try:
        response = build_opener(_NoRedirect()).open(prepared, timeout=120)
    except HTTPError as error:
        response = error
    with response:
        body, eof = read_bounded(response, limit)
        return response.status, body, eof


def capture_bytes(body, *, eof, limit, secrets=()):
    if type(body) is not bytes or len(body) > limit + 1 or type(eof) is not bool:
        raise ValueError("Invalid bounded wire capture")
    complete = eof and len(body) <= limit
    safe = body
    for secret in secrets:
        if secret:
            safe = safe.replace(secret, b"[REDACTED]")
    try:
        safe.decode("utf-8", errors="strict")
        utf8 = True
    except UnicodeDecodeError:
        utf8 = False
    return {"raw_prefix_length": len(body), "read_limit_bytes": limit,
            "eof_observed": eof, "truncated": len(body) > limit,
            "complete": complete, "raw_prefix_sha256": hashlib.sha256(body).hexdigest(),
            "raw_full_body_sha256": hashlib.sha256(body).hexdigest() if complete else None,
            "stored_body_base64": base64.b64encode(safe).decode("ascii"),
            "stored_body_sha256": hashlib.sha256(safe).hexdigest(), "strict_utf8": utf8,
            "redacted": safe != body, "transform": "exact_secret_byte_replacement.v1"}


def _paths(backend, call_id, policy):
    key = backend._key(call_id)
    def path(suffix):
        return backend.directory / (key + "." + suffix + ".json")
    anchor = Path(policy["authority_directory"]) / (key + ".capture_anchor.json")
    return path, anchor


def _decode_bound_capture(backend, call_id, trusted_anchor_sha256):
    policy = policy_for(backend)
    path, anchor_path = _paths(backend, call_id, policy)
    if call_id not in policy["allowed_call_ids"] or digest(anchor_path) != trusted_anchor_sha256:
        raise ValueError("Capture anchor is not the trusted original receipt")
    request, intent, anchor, capture = (read(p) for p in
        (path("request"), path("api_intent"), anchor_path, path("api_capture")))
    binding = {"call_id":call_id, "request_sha256":digest(path("request")),
               "execution_sha256":canonical_hash(backend.execution_contract)}
    if (any(obj.get(k) != v for obj in (intent, anchor, capture, request) for k,v in binding.items()
            if not (obj is request and k == "request_sha256"))
            or anchor.get("capture_sha256") != digest(path("api_capture"))
            or anchor.get("intent_sha256") != digest(path("api_intent"))
            or capture.get("intent_sha256") != anchor["intent_sha256"]
            or intent.get("claim_sha256") != digest(path("claim"))):
        raise ValueError("API capture lineage or trusted hash mismatch")
    if (not capture["complete"] or not capture["eof_observed"] or capture["truncated"]
            or capture["raw_prefix_length"] > policy["read_limit_bytes"]
            or capture["read_limit_bytes"] != policy["read_limit_bytes"]
            or capture["raw_full_body_sha256"] != capture["raw_prefix_sha256"]
            or not capture["strict_utf8"] or capture["http_status"] != 200):
        raise ValueError("Provider capture is incomplete or invalid")
    stored = base64.b64decode(capture["stored_body_base64"], validate=True)
    if hashlib.sha256(stored).hexdigest() != capture["stored_body_sha256"]:
        raise ValueError("Stored capture hash mismatch")
    if not capture["redacted"] and (len(stored) != capture["raw_prefix_length"]
            or hashlib.sha256(stored).hexdigest() != capture["raw_full_body_sha256"]):
        raise ValueError("Raw capture hash mismatch")
    decoded = strict_json(stored.decode("utf-8", errors="strict"))
    if decoded.get("model") != policy["model"]:
        raise ValueError("Provider returned a different model identifier")
    usage = decoded["usage"]
    tokens = [usage["prompt_tokens"], usage["completion_tokens"]]
    if any(type(v) is not int or v < 0 for v in tokens) or tokens[0] > policy["input_cap"] or tokens[1] > policy["output_cap"]:
        raise ValueError("Invalid or excessive provider token usage")
    choices = decoded["choices"]
    if len(choices) != 1 or choices[0]["message"].get("refusal"):
        raise ValueError("Provider refusal or unexpected number of choices")
    choice = choices[0]
    raw = choice["message"]["content"]
    elapsed = capture["elapsed_monotonic_ns"]
    if type(raw) is not str or type(elapsed) is not int or elapsed < 0:
        raise ValueError("Invalid final output or duration")
    result = {"schema":"disastertrace.spool_response.v1", **binding, "raw":raw,
              "raw_sha256":hashlib.sha256(raw.encode()).hexdigest(),
              "input_tokens":tokens[0], "output_tokens":tokens[1],
              "compute_seconds":elapsed / 1e9, "ended_with_eos":choice["finish_reason"] == "stop"}
    return policy, path, result, capture


def reconcile_capture(backend, call_id, *, trusted_anchor_sha256):
    """Zero HTTP. The expected hash comes from the trusted worker/authority receipt."""
    policy, path, result, capture = _decode_bound_capture(backend, call_id, trusted_anchor_sha256)
    failure_path = path("failure")
    if failure_path.exists():
        failure = read(failure_path)
        if (failure.get("capture_anchor_sha256") != trusted_anchor_sha256
                or any(failure.get(k) != result[k] for k in ("call_id","request_sha256","execution_sha256"))):
            raise ValueError("Failure lacks the original trusted capture receipt")
    worker = {**result, "transport_version":VERSION, "capture_anchor_sha256":trusted_anchor_sha256,
              "api_capture_sha256":digest(path("api_capture")), "provider_compute_seconds":None,
              "timing_basis":"monotonic HTTP elapsed; provider compute unknown"}
    _put_same(path("worker"), worker)
    result["worker_receipt_sha256"] = digest(path("worker"))
    _put_same(path("response"), result)
    if failure_path.exists():
        receipt = {"schema":"disastertrace.api_reconciliation.v2",
                   **{k:result[k] for k in ("call_id","request_sha256","execution_sha256")},
                   "failure_sha256":digest(failure_path), "response_sha256":digest(path("response")),
                   "capture_anchor_sha256":trusted_anchor_sha256,
                   "api_capture_sha256":digest(path("api_capture")), "new_http_attempts":0,
                   "old_forecast_adoption_reopened":False}
        _put_same(path("reconciliation"), receipt)
    return result


def validate_publication(backend, call_id):
    policy = policy_for(backend)
    path, _ = _paths(backend, call_id, policy)
    if not path("response").exists():
        return False
    worker = read(path("worker"))
    _, _, result, _ = _decode_bound_capture(backend, call_id, worker["capture_anchor_sha256"])
    result["worker_receipt_sha256"] = digest(path("worker"))
    if read(path("response")) != result:
        raise ValueError("Published response differs from original bound capture")
    if path("failure").exists():
        if not path("reconciliation").exists():
            return False
        receipt, failure = read(path("reconciliation")), read(path("failure"))
        if (receipt.get("schema") != "disastertrace.api_reconciliation.v2"
                or receipt.get("failure_sha256") != digest(path("failure"))
                or receipt.get("response_sha256") != digest(path("response"))
                or receipt.get("api_capture_sha256") != digest(path("api_capture"))
                or receipt.get("capture_anchor_sha256") != worker["capture_anchor_sha256"]
                or failure.get("capture_anchor_sha256") != worker["capture_anchor_sha256"]
                or receipt.get("new_http_attempts") != 0
                or receipt.get("old_forecast_adoption_reopened") is not False
                or any(receipt.get(k) != result[k] for k in ("call_id","request_sha256","execution_sha256"))):
            raise ValueError("Invalid append-only API reconciliation receipt")
    return True


def deliver(backend, call_id, *, credential_path, prepare=prepare_http, send=send_http, hook=None):
    policy = policy_for(backend)
    if call_id not in policy["allowed_call_ids"]:
        raise ValueError("Unregistered API call")
    path, anchor_path = _paths(backend, call_id, policy)
    request = backend.claim_ready(call_id, worker_id="single-authority-api-v2")
    binding = {"call_id":call_id, "request_sha256":digest(path("request")),
               "execution_sha256":request["execution_sha256"]}
    start_wall, start_mono = time.time_ns(), time.monotonic_ns()
    anchor_hash, remote_state = None, "not_sent"
    def event(name):
        if hook is not None: hook(name)
    def permit():
        if (Path(policy["stop_path"]).exists() or time.time_ns() >= policy["deadline_wall_ns"]
                or time.monotonic_ns() - start_mono >= policy["deadline_wall_ns"] - start_wall):
            raise ValueError("STOP or expired final local API permit")
    try:
        ready = read(path("ready"))
        controller = read(Path(ready["checkpoint_path"]))["payload"]["config"]
        if (policy["input_cap"] > controller["input_token_cap"]
                or policy["output_cap"] > controller["output_token_cap"]):
            raise ValueError("API allowance exceeds original controller reservation")
        if sum(len(m["content"].encode()) for m in request["messages"]) + 4096 > policy["input_cap"]:
            raise ValueError("Request exceeds conservative input allowance")
        payload = {"model":policy["model"], "messages":request["messages"], "temperature":0,
                   "max_tokens":policy["output_cap"], "enable_thinking":False, "stream":False}
        if request["request"].get("selector_contract_version") == "selector_query_only.v2":
            from .selector_contract_v2 import contract
            payload["response_format"] = contract(request["request"]["queries"])["provider_schema"]
        prepared, secrets = prepare(payload, policy, credential_path)
        event("before_permit")
        with authority_lock(policy):
            permit()
            intent = {"schema":"disastertrace.api_intent.v2", **binding, "payload":payload,
                      "claim_sha256":digest(path("claim")), "attempts":1, "automatic_retries":0,
                      "permit_wall_ns":time.time_ns(), "permit_monotonic_ns":time.monotonic_ns()}
            publish(path("api_intent"), intent)
            permit()
            send_gate_wall_ns = time.time_ns()
        # STOP after this local permit cannot revoke an in-flight request.
        event("after_permit")
        remote_state = "unknown"
        sending_mono = time.monotonic_ns()
        status, body, eof = send(prepared, policy["read_limit_bytes"])
        elapsed = time.monotonic_ns() - sending_mono
        event("after_http_before_capture")
        capture = {"schema":"disastertrace.api_capture.v2", **binding,
                   **capture_bytes(body, eof=eof, limit=policy["read_limit_bytes"], secrets=secrets),
                   "http_status":status, "intent_sha256":digest(path("api_intent")),
                   "send_gate_wall_ns":send_gate_wall_ns, "received_wall_ns":time.time_ns(),
                   "elapsed_monotonic_ns":elapsed}
        publish(path("api_capture"), capture)
        publish(anchor_path, {"schema":"disastertrace.api_capture_anchor.v2", **binding,
                              "intent_sha256":digest(path("api_intent")),
                              "capture_sha256":digest(path("api_capture"))})
        anchor_hash = digest(anchor_path)
        event("after_capture_before_publication")
        return reconcile_capture(backend, call_id, trusted_anchor_sha256=anchor_hash)
    except Exception as exc:
        if not path("failure").exists():
            publish(path("failure"), {**binding, "error_type":type(exc).__name__,
                    "capture_anchor_sha256":anchor_hash, "remote_execution":remote_state,
                    "new_HTTP_retry_allowed":False})
        raise


def cost_reconciliation(backend, pending, *, observed_at):
    """Use the actual production consumer; this receipt changes costs only."""
    raw, details = backend.resolve(pending["ticket"], pending["call_id"])
    return {"receipt_id":pending["call_id"],
            "actual":{"tokens":details["input_tokens"] + details["output_tokens"],
                      "compute_ms":math.ceil(details["seconds"] * 1000)},
            "proof":{**pending["binding"], "response_sha256":details["response_file_sha256"],
                     "observed_at":observed_at}}
