"""Measure one unchanged nine-arm historical score, retaining exact output."""

import argparse
import cProfile
import inspect
import json
import pstats
import resource
import time
from pathlib import Path

from disastertrace.monitoring_fixed_v1.admission import AdmissionEngine
from disastertrace.monitoring_fixed_v1.outcomes import ComparisonContract
from disastertrace.monitoring_v1.formal_session import score_formal
from disastertrace.monitoring_v1.spool_backend import digest, publish, read


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(exist_ok=False)
    config = read(args.case / "COMPARISON.json")["payload"]
    comp = ComparisonContract(config["invariants"], config["allowed_interventions"])
    arms = {name: args.case / name / "admission.jsonl"
            for name in read(args.case / "CONFIGS.json")}
    rows = read(args.case / "OUTCOMES.json")
    count = 0
    original = AdmissionEngine.from_journal

    def load(path):
        nonlocal count
        count += 1
        return original(path)

    AdmissionEngine.from_journal = load
    options = {"legacy": True} if "legacy" in inspect.signature(score_formal).parameters else {}
    profiler = cProfile.Profile()
    start, cpu = time.perf_counter(), time.process_time()
    profiler.enable()
    result = score_formal(rows, arms, comparison=comp, **options)
    profiler.disable()
    wall, cpu = time.perf_counter() - start, time.process_time() - cpu
    publish(args.out / "SCORES.json", result)
    profiler.dump_stats(str(args.out / "profile.pstats"))
    with (args.out / "PROFILE.txt").open("x") as stream:
        pstats.Stats(profiler, stream=stream).sort_stats("cumulative").print_stats(25)
    record = {"seconds": wall, "cpu_seconds": cpu, "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
              "from_journal_calls": count, "arms": len(arms), "score_sha256": digest(args.out / "SCORES.json"),
              "source": inspect.getfile(score_formal), "source_sha256": digest(Path(inspect.getfile(score_formal))),
              "mode": "legacy_journal_rescore_only; not new formal provenance admission",
              "cache_state": "uncontrolled filesystem cache; profile overhead included"}
    publish(args.out / "RESULT.json", record)
    print(json.dumps(record), flush=True)


if __name__ == "__main__":
    main()
