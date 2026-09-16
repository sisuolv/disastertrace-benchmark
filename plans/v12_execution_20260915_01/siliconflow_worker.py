"""One committed selector request, bounded wire capture and offline reconciliation."""
import hashlib
import json
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from disastertrace.monitoring_v1.spool_backend import digest, publish, read


def transport(payload, policy):
    credential = read(Path(policy["credential_path"]))
    if credential["base_url"].rstrip("/") != policy["base_url"].rstrip("/"):
        raise ValueError("Registered provider endpoint changed")
    request = Request(policy["base_url"].rstrip("/") + "/chat/completions",
        data=json.dumps(payload, allow_nan=False).encode(),
        headers={"Authorization": "Bearer " + credential["api_key"], "Content-Type": "application/json"})
    try:
        response = urlopen(request, timeout=120)
    except HTTPError as error:
        response = error
    with response:
        body = response.read(4_000_001)
        status = response.status
    safe = body.replace(credential["api_key"].encode(), b"[REDACTED]")
    return status, safe, hashlib.sha256(body).hexdigest(), safe != body


def reconcile_capture(backend, call_id, policy):
    """Complete publication from the original durable response, with zero HTTP."""
    key = backend._key(call_id)
    directory = backend.directory
    request_path = directory / (key + ".request.json")
    request = read(request_path)
    capture = read(directory / (key + ".api_capture.json"))
    if capture["request_sha256"] != digest(request_path) or capture["http_status"] != 200 or not capture["complete"]:
        raise ValueError("Original provider capture cannot be reconciled")
    decoded = json.loads(capture["body"])
    if decoded.get("model") != policy["model"]:
        raise ValueError("Provider returned a different model identifier")
    usage = decoded["usage"]
    tokens = [usage["prompt_tokens"], usage["completion_tokens"]]
    if any(type(v) is not int or v<0 for v in tokens) or tokens[0]>policy["input_cap"] or tokens[1]>policy["output_cap"]:
        raise ValueError("Provider tokens exceed a registered call allowance")
    choice = decoded["choices"][0]; raw = choice["message"]["content"]
    if not isinstance(raw,str):
        raise ValueError("No final selector response")
    result = {"schema": "disastertrace.spool_response.v1", "call_id": call_id,
        "request_sha256": digest(request_path), "execution_sha256": request["execution_sha256"],
        "raw": raw, "raw_sha256": hashlib.sha256(raw.encode()).hexdigest(),
        "input_tokens": tokens[0], "output_tokens": tokens[1],
        "compute_seconds": (capture["received_wall_ns"]-capture["started_wall_ns"])/1e9,
        "ended_with_eos": choice["finish_reason"]=="stop"}
    worker = {**result, "provider": "siliconflow", "returned_model": decoded["model"],
        "provider_compute_seconds": None, "timing_basis": "HTTP elapsed; provider compute unknown",
        "api_capture_sha256": digest(directory / (key + ".api_capture.json")),
        "fees": "provider invoice not estimated; tokens and all call ceilings recorded"}
    worker_path = directory / (key + ".worker.json")
    if worker_path.exists():
        if read(worker_path) != worker:
            raise ValueError("Original worker receipt conflicts")
    else:
        publish(worker_path, worker)
    result["worker_receipt_sha256"] = digest(worker_path)
    response_path = directory / (key + ".response.json")
    if response_path.exists():
        if read(response_path) != result:
            raise ValueError("Original spool response conflicts")
    else:
        publish(response_path, result)
    return result


def deliver(backend, call_id, policy, *, send=transport):
    if call_id not in policy["allowed_call_ids"] or time.time_ns() >= policy["deadline_wall_ns"]:
        raise ValueError("Unregistered selector call or expired API phase")
    request = backend.claim_ready(call_id, worker_id="v12-siliconflow-original-selector")
    key = backend._key(call_id); directory=backend.directory
    request_path=directory/(key+".request.json")
    if sum(len(m["content"].encode()) for m in request["messages"])+4096>policy["input_cap"]:
        raise ValueError("Selector request exceeds conservative input allowance")
    payload={"model":policy["model"],"messages":request["messages"],"temperature":0,
        "max_tokens":policy["output_cap"],"enable_thinking":False,"stream":False}
    start=time.time_ns()
    publish(directory/(key+".api_intent.json"),{"request_sha256":digest(request_path),
        "payload":payload,"started_wall_ns":start,"attempts":1,"automatic_retries":0})
    try:
        status, body, original_sha, redacted=send(payload,policy)
        publish(directory/(key+".api_capture.json"),{"request_sha256":digest(request_path),
            "http_status":status,"body":body.decode("utf-8",errors="replace"),
            "original_body_sha256":original_sha,"redacted":redacted,"complete":len(body)<=4_000_000,
            "started_wall_ns":start,"received_wall_ns":time.time_ns()})
        return reconcile_capture(backend,call_id,policy)
    except Exception as exc:
        failure=directory/(key+".failure.json")
        if not failure.exists():
            publish(failure,{"call_id":call_id,"request_sha256":digest(request_path),
                "execution_sha256":request["execution_sha256"],"error_type":type(exc).__name__,
                "original_capture_present":(directory/(key+".api_capture.json")).exists(),
                "new_HTTP_retry_allowed":False})
        raise
