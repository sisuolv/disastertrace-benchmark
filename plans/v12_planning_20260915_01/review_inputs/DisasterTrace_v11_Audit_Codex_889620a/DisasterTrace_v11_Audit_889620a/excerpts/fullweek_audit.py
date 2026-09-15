def audit(out, workers):
    plan = read(out / "PLAN.json")
    attempts = [r for shard in range(4) for r in read(out / ("COMPLETE_" + str(shard) + ".json"))["results"]]
    expected = {(c["case"], a) for c in plan["cases"] for a in c["arms"]}
    got = {(r["case"], r["arm"]) for r in attempts}
    if got != expected or len(attempts) != len(expected) or any(r["state"] != "completed" for r in attempts):
        publish(out / "INCOMPLETE.json", {"expected": len(expected), "attempted": len(attempts),
            "missing": sorted(expected-got), "failed": [r for r in attempts if r["state"] != "completed"]})
        raise ValueError("Incomplete registered comparison; failures retained")
    with ProcessPoolExecutor(max_workers=workers) as pool:
        rows = [r for part in pool.map(audit_case, [(out, c) for c in plan["cases"]]) for r in part]
    publish(out / "ROWS.json", rows)
    groups = defaultdict(list)
    for row in rows:
        groups[(row["threshold"], "all", row["arm"])].append(row)
        groups[(row["threshold"], row["week"], row["arm"])].append(row)
    metrics = {}
    for (threshold, block, arm), values in groups.items():
        settled = [r for r in values if r["loss"] is not None]
        metrics[f"{threshold}__{block}__{arm}"] = {"registered": len(values), "settled": len(settled),
            "positive": sum(r["outcome"] == 1 for r in settled), "missing": len(values)-len(settled),
            "brier": math.fsum(r["loss"] for r in settled)/len(settled) if settled else None,
            "e_determined": sum(r["e_status"] in {"entailed", "refuted"} for r in values)}
    publish(out / "RESULT.json", {"passed": True, "at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "trajectories": len(attempts), "method_rows": len(rows), "opportunities": 12096,
        "global_calendar_blocks": 4, "independent_confirmation": False, "model_calls": 0,
        "metrics": metrics, "rows_sha256": digest(out / "ROWS.json"),
        "qualification": "historical declared-availability development; code-bound scores and arithmetic audit, not independent physical truth"})
    print(json.dumps({"passed": True, "trajectories": len(attempts), "rows": len(rows)}), flush=True)
