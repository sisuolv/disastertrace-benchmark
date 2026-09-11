"""Record actual ACP terminal states before releasing requested GPU slots."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess

from common import dump


def main(batch):
    records = []
    for sub in sorted((batch / "submissions").iterdir()):
        jid = (sub / "job-id.txt").read_text().strip()
        job = json.loads(subprocess.check_output(["/mnt/afs/260010168/bin/sco", "acp", "jobs", "describe",
            "--workspace-name=share-space", "--format=json", jid], text=True))
        records.append(job)
    print([(x["name"], x["state"]) for x in records])
    if any(x["state"] not in {"SUCCEEDED", "FAILED", "DELETED"} for x in records):
        raise SystemExit("jobs not all terminal yet")
    dump(batch / "ACP_TERMINAL.json", {"at": datetime.now(timezone.utc).isoformat(), "jobs": records})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=Path, required=True)
    main(parser.parse_args().batch)
