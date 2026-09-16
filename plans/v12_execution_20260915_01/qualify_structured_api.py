"""Use the second and final compatibility slot for a synthetic schema probe."""
import datetime as dt
import hashlib
import json
import time
from pathlib import Path

from disastertrace.monitoring_v1.selection import parse_selection
from disastertrace.monitoring_v1.spool_backend import digest, publish, read
from siliconflow_worker import transport

ROOT=Path(__file__).resolve().parent


def main():
    if len(list(ROOT.glob("api_compatibility_*/ATTEMPT.json"))) != 1:
        raise ValueError("Expected exactly one previously consumed compatibility slot")
    auth=read(ROOT/"EXECUTION_AUTHORIZATION.json")
    if auth["max_model_compatibility_requests"]<2:
        raise ValueError("No second compatibility slot authorized")
    folder=ROOT/"api_compatibility_02";folder.mkdir(exist_ok=False)
    original=read(ROOT/"api_compatibility_01/REGISTRATION.json")
    request=original["request"]
    schema={"type":"object","additionalProperties":False,
        "required":["query_order","forecast_handles"],"properties":{
            "query_order":{"type":"array","items":{"type":"string","enum":["q0","q1"]}},
            "forecast_handles":{"type":"array","items":{"type":"string","enum":["t0","t1"]}}}}
    request["response_format"]={"type":"json_schema","json_schema":{
        "name":"monitoring_selector","strict":True,"schema":schema}}
    publish(folder/"REGISTRATION.json",{"at":dt.datetime.now(dt.timezone.utc).isoformat(),
        "request":request,"maximum_requests":1,"automatic_retries":0,
        "origin":"synthetic interface probe informed by current format failures; not weather evaluation or independent validation",
        "original_prompt_changed":False,"only_request_change":"response_format=json_schema, strict=true",
        "source_registration_sha256":digest(ROOT/"api_compatibility_01/REGISTRATION.json"),
        "provider_docs_sha256":digest(ROOT/"receipts/SILICONFLOW_CHAT_DOC.md"),
        "existing_formal_requests_and_parser_unchanged":True,"benchmark_model_requests":0})
    policy={"credential_path":auth["credential_path"],"base_url":"https://api.siliconflow.cn/v1"}
    publish(folder/"ATTEMPT.json",{"started_at":dt.datetime.now(dt.timezone.utc).isoformat(),"attempts":1})
    start=time.monotonic();result={"passed":False,"schema_passed":False,"instruction_passed":False,
        "attempts":1,"benchmark_model_requests":0,"automatic_retries":0}
    try:
        status,body,sha,redacted=transport(request,policy)
        publish(folder/"CAPTURE.json",{"http_status":status,"body":body.decode(errors="replace"),
            "original_body_sha256":sha,"redacted":redacted,"complete":len(body)<=4000000})
        result["http_status"]=status
        if status!=200:raise ValueError("Provider rejected strict schema mode")
        decoded=json.loads(body);choice=decoded["choices"][0]
        result.update(returned_model=decoded.get("model"),usage=decoded.get("usage"),finish_reason=choice.get("finish_reason"))
        if decoded.get("model")!=request["model"]:raise ValueError("Provider model identifier changed")
        answer=parse_selection(choice["message"]["content"],query_handles={"q0","q1"},target_handles={"t0","t1"},forecast_cap=2)
        result.update(schema_passed=choice["finish_reason"]=="stop",answer=answer,
            instruction_passed=answer=={"query_order":["q0"],"forecast_handles":["t0","t1"]})
        result["passed"]=result["schema_passed"] and result["instruction_passed"]
    except Exception as exc:
        result["error_type"]=type(exc).__name__
    result["seconds"]=time.monotonic()-start
    publish(folder/"RESULT.json",result);print(json.dumps(result),flush=True)


if __name__=="__main__":
    main()
