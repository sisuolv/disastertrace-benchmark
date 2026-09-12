"""Overlay three authorized source validations on the frozen 97-entry registry."""

import argparse
import copy
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PRIOR = REPO / "plans/all_dataset_utilization_20260912/usage_02/USAGE_REGISTRY.json"


def bind(path):
    return {
        "path": str(path.relative_to(REPO)),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    prior = json.loads(PRIOR.read_text())
    sources = copy.deepcopy(prior["sources"])
    local = json.loads((ROOT / "outputs_02/AUDIT.json").read_text())["reports"]
    emdat, cma = local
    xbd = json.loads((ROOT / "xbd_audit_02/AUDIT.json").read_text())
    verification = json.loads((ROOT / "verification_01/VERIFICATION.json").read_text())
    if not verification["checks_passed"]:
        raise ValueError("Independent source verification has not passed")
    for name, expected in verification["audit_hashes"].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected:
            raise ValueError("Audit changed after independent verification")
    updates = {
        "D39": {
            "state": "catalog_records_only",
            "decoded_content_available": True,
            "current_summary_cn": f"用户授权 XLSX 已完整解析：{emdat['actual_rows']:,} 条、47 列；核心天气灾害 {emdat['core_weather_country_records']:,} 条国家记录、{emdat['core_weather_event_groups']:,} 个事件编号组。",
            "remaining_gates_cn": "只作事件目录；7,463 条核心记录缺经纬度，日期粒度不一；灾害报告阈值与漏报偏差、2026 年未完结、事件归并和再分发条件需遵循。缺记录不能作负例。",
            "usage_cn": "多灾种事件定位、分层抽样、事件组去重；不能当作逐像元真值或历史实时预警输入。",
            "ready_role": "event_catalog_with_resolution_limits",
            "validated_sample_hazards": sorted(
                {
                    h
                    for example in emdat["examples"]
                    if len(example["candidate_hazards"]) == 1
                    for h in example["candidate_hazards"]
                }
            ),
            "source_audit": bind(ROOT / "outputs_02/AUDIT.json"),
        },
        "D73": {
            "state": "decoded_sample",
            "decoded_content_available": True,
            "current_summary_cn": f"用户提供 CMA RAR 的 77 个年度文件均通过 CRC；1949—2025 年，{cma['storm_segments']:,} 个气旋段、{cma['point_records']:,} 个时次，保留 734 行可选第七列。",
            "remaining_gates_cn": "官方格式页仍返回 468。经纬度比例、风速单位/平均时段、缺失码及 UTC 定义待原始文档绑定；最佳路径是事后分析，历史预报配对和发布时间另验。",
            "usage_cn": "西北太平洋气旋事后轨迹/强度参考候选；已验证 +6/+12/+24 小时原始时钟配对结构，字段定义通过后才进入数值评分。",
            "ready_role": "raw_track_reference_with_semantic_gates",
            "validated_sample_hazards": ["H01"],
            "source_audit": bind(ROOT / "outputs_02/AUDIT.json"),
            "dependence_notes_cn": "CMA 事后分析与 IBTrACS 中 CMA 机构字段可能同源，不能当作两份独立真值；跨洋盆不能仅按名字和时刻拼接 NHC 链。",
        },
        "D44": {
            "state": "decoded_sample",
            "decoded_content_available": True,
            "current_summary_cn": f"真实取得 3 组 Florence 灾前/后 GeoTIFF 与标签，6 个 TIFF + 6 个 JSON；官方 geotransforms {xbd['metadata_entries']:,} 项且 SHA1 通过。灾后 286 无损、176 未分类。",
            "remaining_gates_cn": "三组来自同一 Florence 过程、原 hold split，现为开发样例。像素/经纬度标签转换与 native affine 不一致，空间评分阻断；样例无损伤正类；完整分卷未下载校验，原始 PNG 与 TIFF 像素配准未证实。",
            "usage_cn": "建筑影响与灾前/后多模态数据适配候选；当前只准入数据结构诊断，待配准、正例和时点合同通过再建评分任务。",
            "ready_role": "decoded_native_pair_with_spatial_and_class_gates",
            "validated_sample_hazards": ["H01", "H08"],
            "source_audit": bind(ROOT / "xbd_audit_02/AUDIT.json"),
            "dependence_notes_cn": "GeoTIFF、challenge 标签和 geotransforms 为同一 xBD 影像身份的不同交付形式；三组同一 Florence 过程，不增加独立事件/来源数。",
        },
    }
    for source in sources:
        sid = source["source_id"]
        if sid not in updates:
            continue
        source["prior_state"] = source["state"]
        source.update(updates[sid])
        source["remaining_access"] = None
        source["authorization_action_cn"] = (
            "本轮所需内容已通过用户提供文件或授权链接取得，无新的账号授权步骤；访问成功不代表允许公开再分发。"
        )
        source["latest_auth_evidence"] = {
            "kind": "user_supplied_file"
            if sid != "D44"
            else "user_authorized_signed_download",
            "signed_query_saved_in_registry": False,
        }
        source["new_scientific_checks"] = [
            source["source_audit"],
            bind(ROOT / "verification_01/VERIFICATION.json"),
        ]
        source["fresh_network_receipt_this_round"] = sid == "D44"
        source["new_formal_task_admitted"] = False
        source["online_latency_validated"] = False
        source["licence_status"] = (
            "User-authorized acquisition/use in this workspace; raw data and signed links remain local; redistribution terms not independently approved."
        )
        if sid == "D39":
            source["role_hazards"] = source["validated_sample_hazards"]
        if sid == "D44":
            source["new_fetch_attempts"] = []
            for path in sorted((ROOT / "captures").glob("xbd_*/RECEIPT.json")):
                r = json.loads(path.read_text())
                source["new_fetch_attempts"].append(
                    {
                        "receipt": str(path.relative_to(REPO)),
                        **{
                            key: r[key] for key in ["http_status", "curl_exit", "bytes"]
                        },
                    }
                )
    if len(sources) != 97 or any(
        current != old
        for current, old in zip(sources, prior["sources"])
        if current["source_id"] not in updates
    ):
        raise ValueError("Unrelated inherited source records changed")
    counts = dict(Counter(s["state"] for s in sources))
    if counts != {
        "decoded_sample": 86,
        "catalog_records_only": 7,
        "authorization_pending": 2,
        "no_decoded_target_sample": 2,
    }:
        raise ValueError("Unexpected registry state counts")
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "prior_registry": bind(PRIOR),
        "source_count": len(sources),
        "state_counts": counts,
        "upgraded_ids": sorted(updates),
        "unchanged_source_entries": 94,
        "network": verification["network"],
        "network_scope_is_current_xbd_batch_only": True,
        "inherited_network_summary": prior["network"],
        "new_formal_tasks": 0,
        "new_model_calls": 0,
        "new_gpu_jobs": 0,
        "hazard_count": prior["hazard_count"],
        "hazard_chains": prior["hazard_chains"],
        "hazard_chains_inherited_unchanged_not_new_admissions": True,
        "sources": sources,
        "limit": "97 source/product/delivery entries are not independent datasets; sample decoding is not task readiness or novelty validation. Only D39, D44 and D73 changed in this overlay.",
    }
    (args.output / "USAGE_REGISTRY.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    columns = [
        "source_id",
        "name",
        "state",
        "ready_role",
        "current_summary_cn",
        "remaining_gates_cn",
    ]
    with (args.output / "USAGE_REGISTRY.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(sources)
    lines = [
        "# 97 项候选数据使用清单：用户授权数据补充",
        "",
        "2026-09-12。仅更新 EM-DAT、CMA、xBD 三项，其余 94 项逐字段继承上一版。",
        "",
        "86 项已解析目标内容，7 项事件/派生目录，2 项待授权，2 项未取到目标样例。条目数不等于独立数据集数，更不等于完成预测闭环的任务数。",
        "",
        "| 编号 | 来源 | 当前状态 | 实测与用途边界 |",
        "| --- | --- | --- | --- |",
    ]
    for s in sources:
        text = s["current_summary_cn"] + " " + s["remaining_gates_cn"]
        lines.append(
            f"| {s['source_id']} | {s['name']} | {s['state']} | {text.replace('|', '/').replace(chr(10), ' ')} |"
        )
    (args.output / "USAGE_REGISTRY_CN.md").write_text("\n".join(lines) + "\n")
    with (args.output / "EMDAT_HAZARD_COUNTS.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            [
                "emdat_subtype",
                "country_records",
                "candidate_hazards",
                "mapping_is_unambiguous",
            ]
        )
        by_subtype = {
            r["Disaster Subtype"]: r["candidate_hazards"] for r in emdat["examples"]
        }
        for name, count in sorted(emdat["core_weather_subtypes"].items()):
            hazards = by_subtype[name]
            writer.writerow([name, count, ";".join(hazards), len(hazards) == 1])
    print(
        json.dumps(
            {
                "source_count": len(sources),
                "state_counts": counts,
                "changed_ids": sorted(updates),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
