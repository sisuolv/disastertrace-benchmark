"""One real bound case before the full registered comparison is dispatched."""

import argparse
import json
import shutil
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from fullweek import audit_case, run_arm


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    batch = args.batch
    card = json.loads((batch / "PLAN.json").read_text())["cases"][0]
    pilot = args.out
    pilot.mkdir(exist_ok=False)
    case = pilot / card["case"]
    case.mkdir()
    for name in ("REGISTRATION.json", "DATA_CARD.json"):
        shutil.copyfile(batch / name, pilot / name)
    for name in ("DATA.json", "BANK.json", "CONFIGS.json", "COMPARISONS.json", "ROSTER.json", "OUTCOMES.json"):
        shutil.copyfile(batch / card["case"] / name, case / name)
    tasks = [(case, arm, group) for group, arms in card["groups"].items() for arm in arms]
    with ProcessPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(run_arm, tasks))
    passed = all(r["state"] == "completed" for r in results)
    rows = audit_case((pilot, card)) if passed else []
    record = {"passed": passed, "results": results, "audited_rows": len(rows), "model_calls": 0}
    (pilot / "RESULT.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record), flush=True)
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
