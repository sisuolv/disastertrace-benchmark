"""Conditional data-to-bank continuation; failures never launch downstream stages."""
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent


def main():
    outcomes=[]
    for name, result_path in [
        ("build_annual.py", ROOT/"annual_stage_B/joins/RESULT.json"),
        ("fit_annual.py", ROOT/"annual_stage_B/fit/RESULT.json"),
    ]:
        with (ROOT/"logs"/(name+".pipeline.log")).open("x") as log:
            completed=subprocess.run([sys.executable,str(ROOT/name),"execute","--workers","12"],stdout=log,stderr=subprocess.STDOUT)
        result=json.loads(result_path.read_text()) if result_path.exists() else {}
        outcomes.append({"stage":name,"exit_code":completed.returncode,"result":str(result_path),"passed":result.get("passed",False)})
        if completed.returncode or not result.get("passed"):
            break
    with (ROOT/"annual_stage_B/TAIL_RESULT.json").open("x") as f:
        json.dump({"at":dt.datetime.now(dt.timezone.utc).isoformat(),"stages":outcomes,
            "passed":len(outcomes)==2 and all(r["passed"] for r in outcomes),
            "confirmation_opened":False,"new_model_calls":0},f,indent=2)


if __name__=="__main__":
    main()
