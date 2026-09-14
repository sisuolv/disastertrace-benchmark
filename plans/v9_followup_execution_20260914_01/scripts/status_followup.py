"""Read existing progress without dispatching models or making network requests."""

from collections import Counter
import datetime as dt
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text()) if path.exists() else None


def status():
    data={"checked_at":dt.datetime.now(dt.timezone.utc).isoformat(),
          "pipeline":read(ROOT/"runtime/PIPELINE_STATUS.json"),
          "audits":read(ROOT/"runtime/AUDIT_STATUS.json"),
          "rare_complete":read(ROOT/"runtime/RARE_COMPLETE.json"),
          "rare_stopped":read(ROOT/"runtime/RARE_STOPPED.json"),
          "cpu_handoff":read(ROOT/"runtime/cpu_handoff_01/STATUS.json"),
          "training":{},"api":{},"temperature":None}
    for region in ["bay","new_york","chicago","denver"]:
        folder=ROOT/"regional_training_02"/region
        plan=read(folder/"SOURCE_NATIVE_PLAN.json")
        data["training"][region]={"bodies":len(list((folder/"native").glob("*.body"))),
            "planned":len(plan["requests"]) if plan else None,"result":read(folder/"RESULT.json")}
    for name in ["api_compatibility_01","api_evidence_01","api_evidence_02","api_pilot_01","api_rare_pilot_01"]:
        folder=ROOT/name
        budget=read(folder/"BUDGET.json")
        if budget is None:
            data["api"][name]={"started":False}
            continue
        calls=budget["calls"]
        data["api"][name]={"started":True,"terminal_file":(folder/"COMPLETE.json").exists(),
            "attempts":len(calls),"status_counts":dict(Counter(r["status"] for r in calls.values())),
            "settled_peak_fee_usd":sum(r.get("actual",0) for r in calls.values())/1e9,
            "unresolved_reservation_usd":sum(r["reserved"] for r in calls.values() if r["status"]!="settled")/1e9,
            "cap_usd":budget["limit_nanodollars"]/1e9}
        if name in ["api_pilot_01", "api_rare_pilot_01"]:
            exits = [read(p) for p in folder.glob("*/*/EXIT.json")]
            data["api"][name]["units"] = {
                "program_complete": sum(r["exit_code"] == 0 and not r["arm"].startswith("deepseek") for r in exits),
                "model_complete": sum(r["exit_code"] == 0 and r["arm"].startswith("deepseek") for r in exits),
                "failed": sum(r["exit_code"] != 0 for r in exits),
                "launched": len(list(folder.glob("*/*/RUN_CLAIM.json"))),
            }
    temperature=read(ROOT/"reports/temperature_stream_audit_01/VALIDATION.json")
    if temperature:
        data["temperature"]={k:temperature[k] for k in ["passed","windows","sessions","target_opportunities","unique_targets","model_calls"]}
    return data


if __name__=="__main__":
    print(json.dumps(status(),indent=2))
