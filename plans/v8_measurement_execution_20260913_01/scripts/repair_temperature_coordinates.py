"""One new, recorded attempt for exactly the failed coordinate transfers."""

import concurrent.futures
import datetime
import json
import time

import acquire_temperature_coordinates as acquisition

ROOT = acquisition.OUT
REPAIR = ROOT / "retry_01"


def main():
    while not (ROOT / "ACQUISITION.json").exists():
        time.sleep(10)
    original = json.loads((ROOT / "ACQUISITION.json").read_text())
    failed = original["failures"]
    REPAIR.mkdir(exist_ok=False)
    acquisition.save(
        REPAIR / "INTENT.json",
        {
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "reason": "Complete the preselected coordinate universe, without dropping timeouts.",
            "new_attempts_per_failed_object": 1,
            "max_workers": 4,
            "requests": [{"relative": r["relative"], "url": r["url"]} for r in failed],
            "selection_uses_outcomes": False,
        },
    )
    acquisition.OUT = REPAIR
    requests = [{"relative": r["relative"], "url": r["url"]} for r in failed]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(acquisition.fetch, requests))
    with (REPAIR / "RECEIPTS.jsonl").open("x") as handle:
        for receipt in results:
            handle.write(json.dumps(receipt) + "\n")
    acquisition.save(
        REPAIR / "COMPLETE.json",
        {
            "all_verified": all(r["status"] == "verified" for r in results),
            "repaired_objects": len(results),
            "original_failed_objects": len(failed),
            "original_acquisition_kept": True,
            "failures": [r for r in results if r["status"] != "verified"],
        },
    )
    print(
        json.dumps(
            {"repaired": len(results), "failed": sum(r["status"] != "verified" for r in results)}
        )
    )


if __name__ == "__main__":
    main()
