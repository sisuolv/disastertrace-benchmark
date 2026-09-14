import os,subprocess,json,datetime,hashlib
from pathlib import Path
p=Path('/mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/plans/v10_execution_20260914_01/runtime/cpu_audit_01')
source=p/"source"
for name,sha in json.loads((p/"SOURCE.json").read_text()).items():
 assert hashlib.sha256((source/name).read_bytes()).hexdigest()==sha
cmd=['/mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/disastertrace-starter/.venv/bin/python', '/mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/plans/v10_execution_20260914_01/runtime/cpu_audit_01/source/audit_existing.py', '--historical', '/mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/plans/v9_followup_execution_20260914_01', '--out', '/mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/plans/v10_execution_20260914_01/reports/existing_audit_01', '--workers', '24']
env=dict(os.environ,PYTHONPATH=str(source),PYTHONDONTWRITEBYTECODE="1",OMP_NUM_THREADS="1",OPENBLAS_NUM_THREADS="1")
with (p/"worker.log").open("x") as f:
 r=subprocess.run(cmd,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=3600)
(p/"EXIT.json").write_text(json.dumps({"exit_code":r.returncode,"at":datetime.datetime.now(datetime.timezone.utc).isoformat()},indent=2)+"\n")
raise SystemExit(r.returncode)
