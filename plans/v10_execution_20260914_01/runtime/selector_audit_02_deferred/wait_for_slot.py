import datetime as dt,json,subprocess,time
from pathlib import Path
out=Path(__file__).resolve().parent
plan=json.loads((out/"PLAN.json").read_text())
end=dt.datetime.fromisoformat(plan["deadline"])
terminal={"SUCCEEDED","FAILED","CANCELED","CANCELLED","STOPPED"}
while dt.datetime.now(dt.timezone.utc)<end:
 for job in plan["release_jobs"]:
  reply=subprocess.run(["/mnt/afs/260010168/bin/sco","acp","jobs","describe","--workspace-name=share-space","--format=json",job],capture_output=True,text=True,timeout=45,check=False)
  if reply.returncode: continue
  state=json.loads(reply.stdout)
  if state.get("state") in terminal and state.get("complete_time"):
   (out/"QUOTA_RELEASE_WITNESS.json").write_text(json.dumps(state,indent=2)+"\n")
   print("Owned job is terminal; submit the original unstarted audit once.",flush=True)
   result=subprocess.run(plan["command"],check=False)
   (out/"EXIT.json").write_text(json.dumps({"exit_code":result.returncode,"at":dt.datetime.now(dt.timezone.utc).isoformat()})+"\n")
   raise SystemExit(result.returncode)
 time.sleep(30)
(out/"EXIT.json").write_text(json.dumps({"exit_code":124,"reason":"No resource release before deadline; no extra submission"})+"\n")
raise SystemExit(124)
