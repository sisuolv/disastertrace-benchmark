"""Stage-boundary audits; computation stays in subprocesses rather than polling chats."""

import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]


def record(phase, **details):
    row={"at":dt.datetime.now(dt.timezone.utc).isoformat(),"phase":phase,**details}
    with (ROOT/"runtime/AUDIT_EVENTS.jsonl").open("a") as f:
        f.write(json.dumps(row)+"\n"); f.flush(); os.fsync(f.fileno())
    temporary=ROOT/"runtime/AUDIT_STATUS.next"
    temporary.write_text(json.dumps(row,indent=2)+"\n")
    temporary.replace(ROOT/"runtime/AUDIT_STATUS.json")


def main():
    with (ROOT/"runtime/AUDIT_CLAIM.json").open("x") as f:
        json.dump({"started_at":dt.datetime.now(dt.timezone.utc).isoformat()},f)
    record("WAITING_FOR_STAGE_RESULTS")
    deadline=time.monotonic()+6*3600
    done=set()
    while time.monotonic()<deadline:
        for stage, folder in [("E","api_evidence_01"),("F","api_pilot_01")]:
            if stage in done or not (ROOT/folder/"COMPLETE.json").exists():
                continue
            record(stage+"_AUDIT_RUNNING")
            command=[sys.executable,str(ROOT/"scripts/analyze_api_followup.py"),stage]
            env=dict(os.environ,PYTHONPATH=str(ROOT.parents[1]/"disastertrace-starter/src"),PYTHONDONTWRITEBYTECODE="1")
            with (ROOT/"runtime"/(stage+"_AUDIT.log")).open("x") as log:
                result=subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT)
            if result.returncode:
                record("STOPPED_AT_AUDIT_FAILURE",stage=stage,exit_code=result.returncode)
                return
            done.add(stage)
            record(stage+"_AUDIT_COMPLETE")
        if done=={"E","F"}:
            record("REGISTERED_API_AUDITS_COMPLETE")
            return
        status=json.loads((ROOT/"runtime/PIPELINE_STATUS.json").read_text())
        if status["phase"]=="STOPPED_AT_GATE":
            record("UPSTREAM_STOPPED",completed_audits=sorted(done),upstream=status)
            return
        time.sleep(30)
    record("WAIT_LIMIT_REACHED",completed_audits=sorted(done))


if __name__=="__main__":
    main()
