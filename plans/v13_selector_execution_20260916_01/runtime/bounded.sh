#!/bin/bash
set -u
cd /mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH=/mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/plans/v13_strong_baselines_20260916_01/source
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
set +e
timeout --signal=TERM 43200 /mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/disastertrace-starter/.venv/bin/python /mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/plans/v13_selector_execution_20260916_01/model_run.py --workers 4 > /mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/plans/v13_selector_execution_20260916_01/runtime/worker.log 2>&1
rc=$?
/mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/disastertrace-starter/.venv/bin/python -c 'import json,sys,datetime;from pathlib import Path;Path(sys.argv[1]).open('"'"'x'"'"').write(json.dumps({'"'"'exit_code'"'"':int(sys.argv[2]),'"'"'at'"'"':datetime.datetime.now(datetime.timezone.utc).isoformat()})+'"'"'\n'"'"')' /mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/plans/v13_selector_execution_20260916_01/runtime/EXIT.json "$rc"
exit "$rc"
