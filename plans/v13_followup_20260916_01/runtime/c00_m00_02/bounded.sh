#!/bin/bash
set -u
cd /mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH=/mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/plans/v13_followup_20260916_01/source
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
set +e
timeout --signal=TERM 18000 /mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/disastertrace-starter/.venv/bin/python /mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/plans/v13_followup_20260916_01/resume_m00.py > /mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/plans/v13_followup_20260916_01/runtime/c00_m00_02/m00.log 2>&1
mrc=$?
/mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/disastertrace-starter/.venv/bin/python -c 'import json,sys;from pathlib import Path;Path(sys.argv[1]).write_text(json.dumps({"exit_code":int(sys.argv[2])})+"\n")' /mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/plans/v13_followup_20260916_01/runtime/c00_m00_02/M00_EXIT.json "$mrc"
timeout --signal=TERM 43200 /mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/disastertrace-starter/.venv/bin/python /mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/plans/v13_followup_20260916_01/c00_02.py execute --workers 6 > /mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/plans/v13_followup_20260916_01/runtime/c00_m00_02/c00.log 2>&1
crc=$?
/mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/disastertrace-starter/.venv/bin/python -c 'import json,sys,datetime;from pathlib import Path;Path(sys.argv[1]).write_text(json.dumps({"m00_exit":int(sys.argv[2]),"c00_exit":int(sys.argv[3]),"finished_at":datetime.datetime.now(datetime.timezone.utc).isoformat()})+"\n")' /mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/plans/v13_followup_20260916_01/runtime/c00_m00_02/EXIT.json "$mrc" "$crc"
if [ "$mrc" -ne 0 ]; then exit "$mrc"; fi
exit "$crc"
