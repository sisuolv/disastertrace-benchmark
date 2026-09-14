"""Real AFS thread/process contention checks with zero provider requests."""

import concurrent.futures
import hashlib
import json
import multiprocessing
import os
from pathlib import Path

from disastertrace.monitoring_v1 import api_capture
from disastertrace.monitoring_v1.spool_backend import digest, publish, read

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"reports/afs_capture_qualification_02"


def ledger_worker(args):
    path, worker = args
    budget=api_capture.ApiBudget(path)
    for index in range(32):
        cid=f"worker-{worker}-{index}"
        budget.transact(cid,1000)
        budget.transact(cid,actual=400)
    return 32


def main():
    OUT.mkdir(exist_ok=False)
    publish(OUT/"PROCESS_BUDGET.json",{"limit_nanodollars":200_000,"max_calls":128,"calls":{}})
    with multiprocessing.get_context("spawn").Pool(4) as pool:
        counts=pool.map(ledger_worker,[(str(OUT/"PROCESS_BUDGET.json"),i) for i in range(4)])
    ledger=read(OUT/"PROCESS_BUDGET.json")
    assert len(ledger["calls"])==sum(counts)==128
    assert all(r["status"]=="settled" and r["actual"]==400 for r in ledger["calls"].values())
    publish(OUT/"CAPTURE_BUDGET.json",{"limit_nanodollars":2_000_000_000,"max_calls":64,"calls":{}})
    key=OUT/"OFFLINE_FIXTURE.key"
    key.write_text("not-a-provider-credential")
    os.environ["DISASTERTRACE_DEEPSEEK_KEY_FILE"]=str(key)

    class Response:
        status=200
        def __enter__(self):return self
        def __exit__(self,*args):return False
        def read(self,limit):
            return json.dumps({"usage":{"prompt_tokens":10,"completion_tokens":5},"model":"offline_afs_fixture",
                "choices":[{"finish_reason":"stop","message":{"content":'{"ok":true}'}}]}).encode()

    class Opener:
        def open(self,*args,**kwargs):return Response()

    api_capture.build_opener=lambda *args:Opener()
    budget=api_capture.ApiBudget(OUT/"CAPTURE_BUDGET.json")
    captures=OUT/"captures"
    captures.mkdir()

    def run(index):
        directory=captures/str(index)
        raw, details=api_capture.capture([{"role":"user","content":"Offline AFS concurrency fixture"}],
            "deepseek-flash",str(index),directory,budget)
        assert json.loads(raw)=={"ok":True}
        wire=read(directory/"WIRE_RECEIPT.json")
        assert digest(directory/"RESPONSE.body")==wire["stored_body_sha256"]==wire["original_body_sha256"]
        assert details["model_returned"]=="offline_afs_fixture"
        return details["fee_upper_nanodollars"]

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        fees=list(pool.map(run,range(64)))
    ledger=read(OUT/"CAPTURE_BUDGET.json")
    assert len(ledger["calls"])==64 and all(r["status"]=="settled" for r in ledger["calls"].values())
    assert sum(fees)==sum(r["actual"] for r in ledger["calls"].values())
    source=ROOT.parents[1]/"disastertrace-starter/src/disastertrace/monitoring_v1/api_capture.py"
    result={"passed":True,"actual_filesystem":"AFS","parallel_processes":4,"process_ledger_calls":128,
        "parallel_threads":4,"wire_captures_verified":64,"actual_model_calls":0,"HTTP_requests":0,
        "source_sha256":hashlib.sha256(source.read_bytes()).hexdigest(),"no_lost_or_duplicate_ledger_entries":True}
    publish(OUT/"VALIDATION.json",result)
    print(json.dumps(result),flush=True)


if __name__=="__main__":main()
