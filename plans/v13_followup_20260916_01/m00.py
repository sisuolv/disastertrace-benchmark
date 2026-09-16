"""Twelve single-attempt committed production selector v2 interface smokes."""
import argparse
import copy
import json
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from b00 import RUN, REPO, OUT as B00, now, verify, contract, restore_contract
from disastertrace.monitoring_v1.api_transport_v2 import deliver, validate_publication
from disastertrace.monitoring_v1.execution import bind_execution
from disastertrace.monitoring_v1.formal_session import FormalSession
from disastertrace.monitoring_v1.production import ProductionSpoolBackend
from disastertrace.monitoring_v1.selector_contract_v2 import parse_query_only
from disastertrace.monitoring_v1.spool_backend import digest, publish, read

OUT = RUN / "M00"
MODEL = "deepseek-ai/DeepSeek-V4-Flash"
CREDENTIAL = Path("/mnt/afs/260010168/.config/disastertrace/credentials/siliconflow.json")


def backend(case):
    return ProductionSpoolBackend(case / "spool", read(OUT / "MODEL_CONTRACT.json"),
        run_id="v13-m00-20260916-01-" + case.name, bound_files=read(case / "BACKEND_FILES.json"))


def prepare():
    OUT.mkdir(exist_ok=False)
    (OUT / "authority").mkdir()
    proposal = read(REPO / "plans/v13_execution_20260916_01/M00_PROPOSAL.json")
    cases = [r["case"] for r in proposal["roster"]]
    assert len(cases) == len(set(cases)) == 12
    source_files = read(RUN / "AUTHORIZATION.json")["source_files"]
    publish(OUT / "REGISTRATION.json", {
        "at": now(), "cases": cases, "requests_max": 12, "model": MODEL,
        "scope": "one real initial selector tick per exposed daily session; transport and output smoke only",
        "amendment_to_unsent_proposal": "same12cases; first real production commit replaces archived mid-session payload. No artificial checkpoint and no reuse of old request bytes.",
        "max_ticks_per_case": 1, "max_controller_steps_per_case": 3, "automatic_retries": 0,
        "request_selection_uses_Y": False, "full_day_forecast_experiment": False,
        "qualification_gate": "B00 first program day passes before any provider dispatch",
        "source_files": source_files, "runner_sha256": digest(Path(__file__)),
        "deadline_at": "2026-09-16T14:00:00+00:00", "empty_query_catalog": "not guaranteed; offline edges remain separate"})
    import datetime as dt
    deadline = int(dt.datetime.fromisoformat(read(OUT / "REGISTRATION.json")["deadline_at"]).timestamp()*1e9)
    publish(OUT / "MODEL_CONTRACT.json", {
        "model": MODEL, "weights": {"provider_managed": True, "checkpoint_revision_not_exposed": True},
        "tokenizer": {"provider_managed": True, "usage_source": "provider capture"},
        "adapter": {"version": "receipt_bound_api.v2", "runner_sha256": digest(Path(__file__))},
        "generation": {"temperature": 0, "max_tokens": 512, "enable_thinking": False, "stream": False},
        "runtime": {"kind": "single_node_committed_production_spool", "automatic_retries": 0},
        "api_transport_v2": {"version": "receipt_bound_api.v2", "model": MODEL,
            "base_url": "https://api.siliconflow.cn/v1", "input_cap": 32768, "output_cap": 512,
            "read_limit_bytes": 1048576, "deadline_wall_ns": deadline,
            "authority_directory": str(OUT / "authority"), "stop_path": str(OUT / "API_STOP.json"),
            "dispatch_authority": "single_local_authority", "allowed_call_ids": ["select-0"]}})
    for name in cases:
        case = OUT / name
        case.mkdir(); (case / "spool").mkdir()
        origin = B00 / name
        data, bank, configs = [read(origin / n) for n in ("DATA.json", "BANK.json", "CONFIGS.json")]
        files = {**source_files, str(Path(__file__)): digest(Path(__file__)),
            str(OUT / "MODEL_CONTRACT.json"): digest(OUT / "MODEL_CONTRACT.json"),
            str(OUT / "REGISTRATION.json"): digest(OUT / "REGISTRATION.json"),
            **{str(origin / n): digest(origin / n) for n in ("DATA.json", "BANK.json", "CONFIGS.json")}}
        publish(case / "BACKEND_FILES.json", files)
        cfg = copy.deepcopy(configs["B11_COVERAGE"])
        cfg.pop("execution_contract", None)
        cfg.update(selector_kind="llm", selector_contract_version="selector_query_only.v2", model_call_budget=1)
        cfg = bind_execution(cfg, backend(case))
        publish(case / "CONFIG.json", cfg)
        publish(case / "COMPARISON.json", contract({"M00": cfg}, data, bank).export())
    publish(OUT / "FREEZE.json", {"files": {str(p): digest(p) for p in OUT.rglob("*.json")}})


def one(name):
    case, origin = OUT / name, B00 / name
    publish(case / "CLAIM.json", {"at": now(), "max_calls": 1})
    result = {"case": name, "passed": False, "http_attempts": 0}
    session = None
    start = time.monotonic()
    try:
        data, bank = read(origin / "DATA.json"), read(origin / "BANK.json")
        files = {**read(case / "BACKEND_FILES.json"),
                 **{str(case / n): digest(case / n) for n in ("CONFIG.json", "COMPARISON.json")}}
        api = backend(case)
        session = FormalSession(data, bank, read(case / "CONFIG.json"),
            comparison=restore_contract(read(case / "COMPARISON.json")), bound_files=files,
            directory=case / "SESSION", backend=api)
        session.step()
        cp = session.persist(case / "PENDING_CHECKPOINT.json")
        pending = cp["payload"]["pending_selector"]
        if pending["call_id"] != "select-0":
            raise ValueError("Smoke differs from registered initial selector")
        try:
            deliver(api, pending["call_id"], credential_path=CREDENTIAL)
        except Exception as exc:
            result["transport_error"] = type(exc).__name__
        # Consume the original response/failure once, including charged failures.
        session.step()
        after = session.persist(case / "CONSUMED_CHECKPOINT.json")
        report = session.report
        if after["payload"]["next_tick"] != 1:
            raise ValueError("Smoke did not reach its registered completed first tick")
        records = report["selector_calls"]
        if len(records) != 1 or report["actual_model_calls"] != 1:
            raise ValueError("Unexpected model dispatch count")
        request_path = next((case / "spool").glob("*.request.json"))
        request = read(request_path)
        response_path = next((case / "spool").glob("*.response.json"), None)
        valid = False
        if response_path is not None:
            raw = read(response_path)["raw"]
            try:
                parse_query_only(raw, request["request"]["queries"])
                valid = True
            except (ValueError, TypeError):
                pass
            result["provider_tokens"] = read(response_path)["input_tokens"] + read(response_path)["output_tokens"]
        result.update(contract_valid=valid, consumer_response_error=records[0].get("response_error"),
            consumer_parse_error=records[0].get("parse_error"),
            query_intent=records[0].get("query_intent"), resource_spent=report["resource_spent"],
            resource_reserved=report["resource_reserved"], actual_model_calls=report["actual_model_calls"],
            candidate_count=len(request["request"]["queries"]), next_tick=after["payload"]["next_tick"],
            publication_verified=validate_publication(api, "select-0"))
        result["passed"] = (valid and result["publication_verified"] and not records[0].get("response_error")
                            and not records[0].get("parse_error"))
        session.stop("registered_one_tick_smoke_complete")
        session.export_journal(session.directory / "admission.jsonl")
    except Exception as exc:
        result.update(error=type(exc).__name__, message=str(exc), traceback=traceback.format_exc())
        if session is not None and not (session.directory / "STOP.json").exists():
            session.stop("smoke_failed")
    result.update(http_attempts=len(list((case / "spool").glob("*.api_intent.json"))),
                  seconds=time.monotonic()-start, finished_at=now())
    publish(case / "RESULT.json", result)
    print(json.dumps({k: v for k, v in result.items() if k not in {"traceback", "query_intent"}}), flush=True)
    return result


def execute(workers):
    reg = read(OUT / "REGISTRATION.json")
    verify(reg["source_files"])
    verify(read(OUT / "FREEZE.json")["files"])
    publish(OUT / "CLAIM.json", {"at": now(), "workers": workers, "one_node_authority": True})
    deadline = read(OUT / "MODEL_CONTRACT.json")["api_transport_v2"]["deadline_wall_ns"]
    while not (B00 / "QUALIFICATION.json").exists() and time.time_ns() < deadline:
        time.sleep(30)
    if not (B00 / "QUALIFICATION.json").exists() or not read(B00 / "QUALIFICATION.json")["passed"]:
        publish(OUT / "RESULT.json", {"passed": False, "status": "program_qualification_blocked", "http_attempts": 0})
        return 1
    results = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(one, name): name for name in reg["cases"]}
        for f in as_completed(futures):
            try: results.append(f.result())
            except Exception as exc:
                results.append({"case": futures[f], "passed": False, "error": type(exc).__name__})
    passed = len(results) == 12 and all(r["passed"] for r in results)
    publish(OUT / "RESULT.json", {"passed": passed, "results": results, "finished_at": now(),
        "registered_requests": 12, "http_attempts": sum(r.get("http_attempts", 0) for r in results),
        "valid_outputs": sum(r.get("contract_valid", False) for r in results),
        "provider_tokens": sum(r.get("provider_tokens", 0) for r in results),
        "claim": "transport/schema/actual-consumer smoke only, no forecast skill claim",
        "formal_288_batch_launched": False, "confirmation_opened": False})
    return 0 if passed else 1


if __name__ == "__main__":
    p = argparse.ArgumentParser(); p.add_argument("mode", choices=["prepare", "execute"])
    p.add_argument("--workers", type=int, default=4); a = p.parse_args()
    if a.mode == "prepare": prepare()
    else: raise SystemExit(execute(a.workers))
