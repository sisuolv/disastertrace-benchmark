"""Reconcile every candidate, keeping delivery, content and task gates separate."""

from collections import Counter
from datetime import datetime, timezone
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
PRIOR = ROOT.parent / "v6_blueprint_sample_validation_20260911"

# These inherited claims refer to decoded content, not just HTTP/catalog access.
INHERITED_CONTENT = set("""
D01 D02 D05 D06 D07 D08 D10 D12 D15 D19 D21 D23 D26 D27 D28 D30 D31
D37 D38 D46 D47 D48 D50 D52 D54 D55 D56 D57 D58 D59 D60 D61 D62 D65 D66 D67
AW-HURDAT2 AW-HEFS AW-NIMS AW-GHCNH AW-GEFS AW-SPC AW-MESH AW-QPE AW-ABI
AW-METAR AW-TAF AW-IEM AW-EDDI AW-CPC AW-OFS AW-PETSS
""".split())
CATALOG_ONLY = {"D18", "D40", "D41", "D54", "D61", "D62", "D74"}
PARTIAL_INTENDED_CONTENT = {"D04", "D14", "D49", "D64"}


def main():
    sources = json.loads((PRIOR / "SOURCE_SAMPLE_INVENTORY.json").read_text())["sources"]
    assert len(sources) == 97 and len({s["source_id"] for s in sources}) == 97
    integrity = json.loads((ROOT / "INHERITED_INTEGRITY.json").read_text())
    assert integrity["all_passed"]
    overrides = json.loads((ROOT / "OVERRIDES.json").read_text())
    hazards = json.loads((PRIOR / "HAZARD_SOURCE_MATRIX.json").read_text())["hazards"]
    audits = []
    for name in ["NEW_AUDIT_02.json", "EXTENDED_AUDIT_03.json", "SUPPLEMENTAL_AUDIT.json"]:
        path = ROOT / name
        if path.exists():
            audits.extend((row, str(path.relative_to(REPO))) for row in json.loads(path.read_text())["reports"])
    checks = {}
    for row, path in audits:
        checks.setdefault(row["source_id"], []).append(dict(report=path, check_id=row["check_id"],
            level=row["level"], files=row.get("files", []), details=row.get("details"), error=row.get("error")))
    auth = ROOT.parent / "earthdata_auth_validation_20260912"
    authenticated = {"SMAP L4 SPL4SMGP v008": "AW-SMAPL4", "CAMS global atmospheric composition forecasts": "AW-CAMS",
                     "GloFAS forecast": "AW-GLOFAS", "EFAS historical forecast": "AW-EFAS", "ERA5-Land hourly": "D25"}
    auth_evidence = {}
    for item in json.loads((auth / "CURRENT_ACCESS_STATUS.json").read_text())["products"]:
        if item["product"] in authenticated:
            auth_evidence[authenticated[item["product"]]] = str((auth / item["evidence"]).relative_to(REPO))
    captures = {}
    for manifest in sorted(ROOT.glob("captures_*/MANIFEST.json")):
        for receipt in json.loads(manifest.read_text())["rows"]:
            captures.setdefault(receipt["source_id"], []).append(dict(
                receipt=str((manifest.parent / (receipt["id"] + ".json")).relative_to(REPO)),
                capture_id=receipt["id"], http_status=receipt["http_status"], curl_exit=receipt["curl_exit"],
                bytes=receipt["bytes"], scientific_validation=receipt["scientific_validation"]))
    result = []
    for source in sources:
        sid = source["source_id"]
        new = checks.get(sid, [])
        successful = [r for r in new if r["level"] != "decode_failed"]
        available = sid in INHERITED_CONTENT or sid in auth_evidence or bool(successful)
        state = "decoded_sample" if available else "no_decoded_target_sample"
        if available and sid in CATALOG_ONLY:
            state = "catalog_records_only"
        if sid in PARTIAL_INTENDED_CONTENT:
            state = "partial_intended_content" if available else state
        if sid == "D49" and any(c["level"] == "paired_content_decoded" for c in successful):
            state = "decoded_sample"
        if sid in {"AW-GWIS", "AW-WPC"} and not available:
            state = "rendered_product_only"
        if sid == "D09":
            available, state = True, "decoded_sample"
        update = overrides.get(sid, {})
        if "state" in update:
            state = update["state"]
        row = dict(source_id=sid, name=source["name"], state=state, decoded_content_available=available,
                   original_selection=source["selection"],
                   prior_sample_status=source["sample_status"],
                   inherited_rechecked=True,
                   new_scientific_checks=new,
                   new_fetch_attempts=captures.get(sid, []),
                   latest_auth_evidence=auth_evidence.get(sid),
                   inherited_evidence_refs=[str((PRIOR / p).resolve().relative_to(REPO)) for p in source["evidence_refs"]],
                   current_summary_cn=update.get("summary", source["sample_summary_cn"]),
                   remaining_gates_cn=update.get("gates", source["limitation_cn"]),
                   authorization_action_cn=update.get("authorization", "已取得样本的路径不需要额外授权；其他版本、镜像和再分发条件另核。" if available else "尚未取得目标内容，不据此推断一定需要新账号。"),
                   urls=source["urls"],
                   hazard_roles=[dict(hazard=h["hazard_id"], name=h["name_cn"], role=key)
                                 for h in hazards for key in ["forecast_sources", "outcome_and_observation_sources", "auxiliary_or_benchmark_sources", "conditional_extension_sources"]
                                 if sid in h[key]],
                   fresh_network_receipt_this_round=bool(captures.get(sid) or any("gee_collections" in c["check_id"] for c in new)),
                   new_formal_task_admitted=False,
                   online_latency_validated=False,
                   licence_status="See inherited source-specific licence evidence; this access audit is not blanket redistribution approval")
        result.append(row)
    counts = dict(Counter(r["state"] for r in result))
    report = dict(schema="disastertrace.all_candidates.validation.v1", generated_at=datetime.now(timezone.utc).isoformat(),
                  scope="All 97 registered candidate source/product entries; aliases and delivery paths are not independent sources.",
                  registered_candidates=len(result), state_counts=counts,
                  decoded_content_entries=sum(r["decoded_content_available"] for r in result),
                  all_candidates_have_decoded_target_samples=all(r["decoded_content_available"] for r in result),
                  all_candidates_formally_admitted=False, inherited_integrity_files=integrity["files"],
                  new_model_calls=0, new_gpu_jobs=0, sources=result)
    (ROOT / "CANDIDATE_REGISTRY.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    labels = {"decoded_sample": "实际样本已解析", "catalog_records_only": "仅事件/派生目录",
              "partial_intended_content": "目标内容仍不完整", "rendered_product_only": "仅渲染产品",
              "no_decoded_target_sample": "尚无目标样本", "authorization_pending": "账号/许可未完成"}
    text = ["# 全部候选数据的实际可用性核验", "", "这是一份数据来源审计，不能直接视为正式 benchmark 已覆盖全部灾种。", "",
            "97 个登记项包含同源产品和入口别名，不是 97 个独立数据集。真实样本可读、标签/质量合格、适合任务、可再分发分别判断。", "",
            "## 汇总", "", "| 状态 | 登记项数量 |", "| --- | ---: |"]
    text += [f"| {labels.get(k, k)} | {v} |" for k, v in counts.items()]
    text += ["", "## 逐项结果", "", "| ID | 来源/产品 | 实测状态 | 当前证据 | 剩余条件 |", "| --- | --- | --- | --- | --- |"]
    for row in result:
        summary = row["current_summary_cn"].replace("|", "/").replace("\n", " ")
        gates = row["remaining_gates_cn"].replace("|", "/").replace("\n", " ")
        text.append(f"| {row['source_id']} | {row['name']} | {labels[row['state']]} | {summary} | {gates} |")
    text += ["", "完整样本路径、SHA-256、解析结果、失败回执及对应灾种见 [CANDIDATE_REGISTRY.json](CANDIDATE_REGISTRY.json)。", "",
             "旧样本复核见 [INHERITED_INTEGRITY.json](INHERITED_INTEGRITY.json)。本轮新增解析见 [NEW_AUDIT_02.json](NEW_AUDIT_02.json)、[EXTENDED_AUDIT_03.json](EXTENDED_AUDIT_03.json)。", ""]
    (ROOT / "CANDIDATE_REGISTRY_CN.md").write_text("\n".join(text))
    with (ROOT / "CANDIDATE_REGISTRY.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["source_id", "name", "state", "decoded_content_available", "current_summary_cn", "remaining_gates_cn", "authorization_action_cn"])
        writer.writeheader()
        writer.writerows({k: r[k] for k in writer.fieldnames} for r in result)
    print(json.dumps({k: v for k, v in report.items() if k != "sources"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
