"""Resume the paused pipeline only after qualified collector and corrected E run."""

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]


def read(path):return json.loads(path.read_text())


def record(phase, **details):
    row={"at":dt.datetime.now(dt.timezone.utc).isoformat(),"phase":phase,**details}
    with (ROOT/"runtime/AFS_RECOVERY_EVENTS.jsonl").open("a") as f:
        f.write(json.dumps(row)+"\n");f.flush();os.fsync(f.fileno())
    temporary=ROOT/"runtime/AFS_RECOVERY_STATUS.next"
    temporary.write_text(json.dumps(row,indent=2)+"\n")
    temporary.replace(ROOT/"runtime/AFS_RECOVERY_STATUS.json")


def run(name,command):
    record(name+"_RUNNING")
    env=dict(os.environ,PYTHONPATH=str(ROOT.parents[1]/"disastertrace-starter/src"),PYTHONDONTWRITEBYTECODE="1")
    with (ROOT/"runtime"/(name+".log")).open("x") as log:
        result=subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT)
    with (ROOT/"runtime"/(name+".exit.json")).open("x") as f:json.dump({"exit_code":result.returncode},f)
    if result.returncode:raise RuntimeError(name+" failed; all original attempts retained")
    record(name+"_COMPLETE")


def main():
    with (ROOT/"runtime/AFS_RECOVERY_CLAIM.json").open("x") as f:
        json.dump({"at":dt.datetime.now(dt.timezone.utc).isoformat()},f)
    try:
        record("WAITING_FOR_REGRESSION")
        xml=ROOT/"validation/full_04.xml"
        deadline=time.monotonic()+600
        while not xml.exists():
            if time.monotonic()>deadline:raise RuntimeError("Regression wait timed out")
            time.sleep(10)
        suites=list(ET.parse(xml).getroot().iter("testsuite"))
        assert sum(int(s.attrib["tests"]) for s in suites)==616
        assert all(s.attrib["failures"]==s.attrib["errors"]==s.attrib["skipped"]=="0" for s in suites)
        qualification=read(ROOT/"reports/afs_capture_qualification_02/VALIDATION.json")
        assert qualification["passed"]
        capture=ROOT.parents[1]/"disastertrace-starter/src/disastertrace/monitoring_v1/api_capture.py"
        assert hashlib.sha256(capture.read_bytes()).hexdigest()==qualification["source_sha256"]
        card=read(ROOT/"AFS_CORRECTED_E_GATE.json")
        script=ROOT/"scripts/run_api_evidence_afs02.py"
        assert hashlib.sha256(script.read_bytes()).hexdigest()==card["source_sha256"]
        release={"at":dt.datetime.now(dt.timezone.utc).isoformat(),"tests":616,
            "afs_validation":qualification,"corrected_E":card,
            "supersedes_capture_binding_for_future_stages":"runtime/PIPELINE_RELEASE.json",
            "original_E_captures_and_freezes_unchanged":True,
            "source":{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [capture,script,xml]}}
        with (ROOT/"runtime/AFS_FIX_RELEASE.json").open("x") as f:json.dump(release,f,indent=2)
        run("E02_corrected_capture",[sys.executable,str(script)])
        run("E02_corrected_audit",[sys.executable,str(ROOT/"scripts/analyze_api_followup.py"),"E","--evidence","api_evidence_02"])
        audit=read(ROOT/"reports/api_evidence_audit_02/VALIDATION.json")
        assert audit["passed"]
        assert audit["budget"]["attempt_statuses"]=={"settled":1008}, "Corrected transport still has unresolved requests"
        assert not audit["budget"]["unmatched_reservations"]
        assert all(g["collection_failures"]==0 for g in audit["groups"].values())
        os.kill(236473,signal.SIGCONT)
        record("ORIGINAL_PIPELINE_RESUMED_WITH_QUALIFIED_CAPTURE",completed_corrected_E_calls=1008)
    except Exception as error:
        record("STOPPED_AT_RECOVERY_GATE",error_type=type(error).__name__,reason=str(error))
        raise


if __name__=="__main__":main()
