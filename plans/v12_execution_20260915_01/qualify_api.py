"""One bounded transport/schema qualification; not a weather experiment."""
import datetime as dt
import hashlib
import json
import time
from pathlib import Path
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parent


def write(path, value):
    with path.open("x") as out:
        json.dump(value, out, indent=2, allow_nan=False)


def main():
    folder = ROOT / "api_compatibility_01"
    folder.mkdir(exist_ok=False)
    model = "deepseek-ai/DeepSeek-V4-Flash"
    request = {"model": model, "messages": [
        {"role": "system", "content": "Return only a JSON object with keys query_order and forecast_handles. Values are arrays of the supplied handles. This is a synthetic interface qualification, not a forecast."},
        {"role": "user", "content": "Budget permits one query. Query q0 serves t0 and t1; query q1 serves only t0. Choose the query serving most targets. Forecast both targets. Query handles: q0,q1. Target handles: t0,t1."}],
        "temperature": 0, "max_tokens": 512, "stream": False,
        "enable_thinking": False}
    write(folder / "REGISTRATION.json", {"model": model, "role": "query_only_selector_candidate",
        "at": dt.datetime.now(dt.timezone.utc).isoformat(), "max_requests": 1,
        "request": request, "request_sha256": hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest(),
        "scientific_comparison": False, "source_data": "synthetic interface fixture",
        "credential_in_artifacts": False, "automatic_retries": 0})
    secret = json.loads(Path(json.loads((ROOT / "EXECUTION_AUTHORIZATION.json").read_text())["credential_path"]).read_text())
    write(folder / "ATTEMPT.json", {"started_at": dt.datetime.now(dt.timezone.utc).isoformat(), "attempts": 1})
    start = time.monotonic()
    result = {"passed": False, "model": model, "attempts": 1, "benchmark_model_requests": 0}
    try:
        wire = urllib.request.Request(secret["base_url"].rstrip("/") + "/chat/completions",
            headers={"Authorization": "Bearer " + secret["api_key"], "Content-Type": "application/json"},
            data=json.dumps(request).encode())
        try:
            response = urllib.request.urlopen(wire, timeout=120)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            result["http_status"] = response.status
            body = json.load(response)
        write(folder / "RESPONSE.json", body)
        if result["http_status"] != 200:
            raise ValueError("Provider rejected compatibility request")
        choice = body["choices"][0]
        answer = json.loads(choice["message"]["content"])
        result.update(passed=answer == {"query_order": ["q0"], "forecast_handles": ["t0", "t1"]},
            finish_reason=choice.get("finish_reason"), returned_model=body.get("model"),
            usage=body.get("usage"), answer=answer)
    except Exception as exc:
        result["error_type"] = type(exc).__name__
    result["seconds"] = time.monotonic() - start
    write(folder / "RESULT.json", result)
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
