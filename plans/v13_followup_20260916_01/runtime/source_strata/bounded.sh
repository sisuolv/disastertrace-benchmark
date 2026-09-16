#!/bin/bash
set -u
cd /mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH=/mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/plans/v13_followup_20260916_01/source
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
set +e
timeout --signal=TERM 46800 /mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/disastertrace-starter/.venv/bin/python /mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/plans/v13_followup_20260916_01/source_strata.py > /mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/plans/v13_followup_20260916_01/runtime/source_strata/worker.log 2>&1
rc=$?
/mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/disastertrace-starter/.venv/bin/python -c 'import json,sys;from pathlib import Path;Path(sys.argv[1]).write_text(json.dumps({"exit_code":int(sys.argv[2])})+"\n")' /mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/plans/v13_followup_20260916_01/runtime/source_strata/EXIT.json "$rc"
exit "$rc"
