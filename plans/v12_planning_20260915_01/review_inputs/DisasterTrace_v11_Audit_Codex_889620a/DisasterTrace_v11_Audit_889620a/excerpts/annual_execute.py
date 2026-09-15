def execute(out, repo):
    write(out / "LAUNCH_CLAIM.json", {"pid": os.getpid(), "at": dt.datetime.now(dt.timezone.utc).isoformat()})
    plan = read(out / "PLAN.json")
    for name, expected in plan["files"].items():
        if digest(out / name) != expected:
            raise ValueError("Frozen annual source or scope changed")
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        os.environ.pop(key, None)
    with ThreadPoolExecutor(max_workers=3) as pool:
        sample = list(pool.map(acquire_unit, [(out, repo, n) for n in plan["sample_units"]]))
        sample_ok = all(r["complete"] for r in sample)
        write(out / "SAMPLE_RESULT.json", {"passed": sample_ok, "results": sample})
        rest = [n for n in plan["units"] if n not in plan["sample_units"]]
        results = sample + (list(pool.map(acquire_unit, [(out, repo, n) for n in rest])) if sample_ok else sample)
    passed = len(results) == len(plan["units"]) and all(r["complete"] for r in results)
    write(out / "RESULT.json", {"passed": passed, "expected_units": 72,
        "completed_units": sum(r["complete"] for r in results), "results": results,
        "not_attempted": sorted(set(plan["units"]) - {r["unit"] for r in results}),
        "full_native_download_complete": False, "annual_fit_complete": False,
        "confirmation_opened": False, "model_calls": 0})
    raise SystemExit(0 if passed else 1)
