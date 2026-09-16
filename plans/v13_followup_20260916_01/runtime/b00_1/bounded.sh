#!/bin/bash
set -u
cd /mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH=/mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/plans/v13_followup_20260916_01/source
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
set +e
timeout --signal=TERM 36000 /mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/disastertrace-starter/.venv/bin/python /mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/plans/v13_followup_20260916_01/b00.py execute --shard 1 --workers 12 > /mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/plans/v13_followup_20260916_01/runtime/b00_1/worker.log 2>&1
rc=$?
/mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/disastertrace-starter/.venv/bin/python -c 'import json,sys,datetime;from pathlib import Path;Path(sys.argv[1]).write_text(json.dumps({"exit_code":int(sys.argv[2]),"finished_at":datetime.datetime.now(datetime.timezone.utc).isoformat()})+"\n")' /mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/plans/v13_followup_20260916_01/runtime/b00_1/EXIT.json "$rc"
exit "$rc"
