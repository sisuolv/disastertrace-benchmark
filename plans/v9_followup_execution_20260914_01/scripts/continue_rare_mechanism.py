"""One-use rare-event development extension, after the unchanged ordinary pilot."""

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]


def save(name,value):
    p=ROOT/"runtime"/name
    with p.open("x") as f:json.dump(value,f,indent=2)


def main():
    save("RARE_CLAIM.json",{"at":dt.datetime.now(dt.timezone.utc).isoformat()})
    deadline=time.monotonic()+6*3600
    complete=ROOT/"api_pilot_01/COMPLETE.json"
    while not complete.exists():
        pipeline=json.loads((ROOT/"runtime/PIPELINE_STATUS.json").read_text())
        if pipeline["phase"]=="STOPPED_AT_GATE" or time.monotonic()>deadline:
            save("RARE_STOPPED.json",{"reason":"upstream stopped or wait limit", "upstream":pipeline})
            return
        time.sleep(30)
    if not json.loads(complete.read_text())["all_completed"]:
        save("RARE_STOPPED.json",{"reason":"ordinary pilot has unfinished model sessions; original attempts preserved"})
        return
    registration=json.loads((ROOT/"RARE_MECHANISM_EXTENSION.json").read_text())
    path=ROOT/"scripts/run_api_rare_pilot.py"
    assert hashlib.sha256(path.read_bytes()).hexdigest()==registration["variant_sha256"]
    env=dict(os.environ,PYTHONPATH=str(ROOT.parents[1]/"disastertrace-starter/src"),PYTHONDONTWRITEBYTECODE="1")
    commands=[("rare_pilot",[sys.executable,str(path)]),
              ("rare_audit",[sys.executable,str(ROOT/"scripts/analyze_api_followup.py"),"F","--pilot","api_rare_pilot_01"])]
    for name,command in commands:
        with (ROOT/"runtime"/(name+".log")).open("x") as log:
            result=subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT)
        save(name+".exit.json",{"exit_code":result.returncode})
        if result.returncode:
            save("RARE_STOPPED.json",{"reason":"stage failure","stage":name,"exit_code":result.returncode})
            return
    save("RARE_COMPLETE.json",{"at":dt.datetime.now(dt.timezone.utc).isoformat(),"scope":"one outcome-selected exposed weather day; not population evaluation"})


if __name__=="__main__":
    main()
