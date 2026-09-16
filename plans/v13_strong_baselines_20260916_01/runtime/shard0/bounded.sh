#!/bin/bash
set -u
cd /mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH=/mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/plans/v13_strong_baselines_20260916_01/source
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
rc=0
if [ "$rc" -eq 0 ]; then
  timeout --signal=TERM 46800 /mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/disastertrace-starter/.venv/bin/python /mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/plans/v13_strong_baselines_20260916_01/regression.py > /mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/plans/v13_strong_baselines_20260916_01/runtime/shard0/regression.log 2>&1
  rc=$?
fi
if [ "$rc" -eq 0 ]; then
  timeout --signal=TERM 46800 /mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/disastertrace-starter/.venv/bin/python /mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/plans/v13_strong_baselines_20260916_01/compatibility.py execute > /mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/plans/v13_strong_baselines_20260916_01/runtime/shard0/compatibility.log 2>&1
  rc=$?
fi
if [ "$rc" -eq 0 ]; then
  timeout --signal=TERM 46800 /mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/disastertrace-starter/.venv/bin/python /mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/plans/v13_strong_baselines_20260916_01/program.py --shard 0 --workers 12 > /mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/plans/v13_strong_baselines_20260916_01/runtime/shard0/program.log 2>&1
  rc=$?
fi
/mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/disastertrace-starter/.venv/bin/python -c 'import json,sys,datetime;from pathlib import Path;p=Path(sys.argv[1]);p.open('"'"'x'"'"').write(json.dumps({'"'"'exit_code'"'"':int(sys.argv[2]),'"'"'at'"'"':datetime.datetime.now(datetime.timezone.utc).isoformat()})+'"'"'\n'"'"')' /mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/plans/v13_strong_baselines_20260916_01/runtime/shard0/EXIT.json "$rc"
exit "$rc"
