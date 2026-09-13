"""Reconstruct service-observation brackets from captured catalogs and native bodies."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


def load(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(args):
    source = args.source.resolve()
    contract = load(source / "CONTRACT.json")
    complete = load(source / "COMPLETE.json")
    status = load(source / "STATUS.json")
    if complete["completed_polls"] != contract["polls"] or status["completed_polls"] != contract["polls"]:
        raise ValueError("Not all bounded polls completed")
    if status["model_calls"] or complete["historical_first_seen_proved"]:
        raise ValueError("Observer scope changed")
    for name, expected in contract["implementation_sha256"].items():
        if digest(source / "source" / name) != expected:
            raise ValueError("Frozen observer implementation changed")
    args.output.mkdir(exist_ok=False)
    shutil.copyfile(__file__, args.output / "verify_live_observer.py")
    bindings, catalogs, natives = {}, {}, []
    for folder in sorted(source.glob("*-*")):
        if not folder.is_dir() or not folder.name.startswith(("catalog-", "native-")):
            continue
        manifest = load(folder / "MANIFEST.json")
        tick = int(folder.name.rsplit("-", 1)[1])
        for record in manifest["rows"]:
            receipt = folder / (record["id"] + ".json")
            if load(receipt) != record:
                raise ValueError("Capture receipt differs from manifest")
            body = folder / record["body_file"]
            if body.stat().st_size != record["bytes"] or digest(body) != record["sha256"]:
                raise ValueError("Captured body differs from receipt")
            if not datetime.fromisoformat(contract["started_at"]) <= datetime.fromisoformat(record["started_at"]) < datetime.fromisoformat(contract["stop_after_utc"]):
                raise ValueError("Request started outside its registered observer window")
            if datetime.fromisoformat(record["finished_at"]) < datetime.fromisoformat(record["started_at"]):
                raise ValueError("Receipt completion precedes start")
            bindings[str(receipt)] = digest(receipt)
            bindings[str(body)] = record["sha256"]
            if folder.name.startswith("catalog-"):
                key = (tick, record["station"])
                if key in catalogs:
                    raise ValueError("Duplicate station poll")
                catalogs[key] = (receipt, record, body)
            else:
                metadata = record["catalog_metadata"]
                if record["complete"] and metadata["station"] not in body.read_text():
                    raise ValueError("Native bulletin does not name the registered station")
                natives.append(record)
    total = len(catalogs) + len(natives)
    if total > contract["maximum_requests"] or len(catalogs) != contract["polls"] * len(contract["stations"]):
        raise ValueError("Observer request count differs")
    first, last = {}, {}
    for tick in range(contract["polls"]):
        for station in contract["stations"]:
            receipt, record, body = catalogs[tick, station]
            if not record["complete"]:
                continue
            products = {r["product_id"]: r for r in csv.DictReader(io.StringIO(body.read_text())) if r["station"] == station}
            for ident, row in products.items():
                first.setdefault((station, ident), {
                    "station": station, "product_id": ident, "nominal_issue": row["valid"],
                    "first_observed_at": record["finished_at"], "poll": tick,
                    "previous_successful_poll_started_at": last.get(station),
                    "initial_or_unbracketed_sighting": station not in last,
                    "catalog_receipt": str(receipt),
                })
            last[station] = record["started_at"]
    recorded = {(r["station"], r["product_id"]): r for r in status["first_observations"]}
    if len(recorded) != len(status["first_observations"]) or recorded != first:
        raise ValueError("First-observation records do not reconstruct from catalogs")
    if status["native_body_attempts"] != len(natives):
        raise ValueError("Native bulletin attempt count changed")
    bracketed = [r for r in first.values() if not r["initial_or_unbracketed_sighting"]]
    result = {
        "verified_at": datetime.now(timezone.utc).isoformat(), "polls": contract["polls"],
        "catalog_requests": len(catalogs), "native_requests": len(natives), "total_requests": total,
        "successful_catalogs": sum(r[1]["complete"] for r in catalogs.values()),
        "successful_native_bodies": sum(r["complete"] for r in natives),
        "unique_product_sightings": len(first), "left_censored_sightings": len(first) - len(bracketed),
        "bracketed_service_sightings": bracketed, "input_bindings": bindings,
        "new_model_calls": 0, "new_network_requests": 0,
        "historical_first_seen_proved": False, "global_first_seen_proved": False,
        "scope": "Reconstructed first observation by this polling service. Initial sightings are left-censored; brackets rely on service-snapshot freshness. No F outcome or historical availability amendment.",
    }
    (args.output / "VERIFIED.json").write_text(json.dumps(result, indent=2) + "\n")
    lines = ["# 有界实时版本观察核验", "",
             f"{contract['polls']} 次轮询，{len(catalogs)} 次目录请求，{len(natives)} 次原生公告请求。",
             f"共 {len(first)} 个版本发现，其中 {len(first)-len(bracketed)} 个初始发现左删失，{len(bracketed)} 个有服务轮询区间。", "",
             "| 站点/产品 | 上次成功轮询开始 | 首次发现响应完成 |", "| --- | --- | --- |"]
    for row in bracketed:
        lines.append(f"| {row['station']} / {row['product_id']} | {row['previous_successful_poll_started_at']} | {row['first_observed_at']} |")
    lines += ["", "所有原始目录和公告字节与回执哈希一致；从目录重新计算得到的发现记录与观察器相同。",
              "此区间仅描述该服务的快照观察，依赖目录新鲜性，不证明全球首次发布；不会改变历史重放的延迟假设。",
              "不包含未来 F 结算或新的模型调用，历史最小闭环不需要等待本观察器。", ""]
    (args.output / "REPORT_CN.md").write_text("\n".join(lines))
    print(json.dumps({k: result[k] for k in ("polls", "total_requests", "unique_product_sightings", "global_first_seen_proved")}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args())
