"""Extend the frozen 97-entry inventory with source-bound recovery results."""

import argparse
import copy
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
PRIOR = REPO / "plans/all_candidate_data_validation_20260912/CANDIDATE_REGISTRY.json"


def read(path):
    return json.loads(path.read_text())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.audit = args.audit.resolve()
    args.output.mkdir(parents=True, exist_ok=False)
    prior = read(PRIOR)
    audit = read(args.audit)
    policy = read(ROOT / "USE_POLICY.json")
    if audit["failures"]:
        raise ValueError("Cannot admit failed recovery audit")
    recovered = {
        r["source_id"]: r
        for r in audit["reports"]
        if r["level"] not in {"public_author_example_only", "code_metadata_only"}
    }
    sources = copy.deepcopy(prior["sources"])
    for source in sources:
        sid = source["source_id"]
        source["prior_state"] = source["state"]
        source["new_formal_task_admitted"] = False
        source["online_latency_validated"] = False
        source["inherited_network_recheck_this_round"] = False
        source["fresh_network_receipt_this_round"] = sid in recovered
        source["usage_categories"] = [
            k for k, v in policy["role_groups"].items() if sid in v["ids"]
        ]
        if not source["usage_categories"]:
            raise ValueError("Missing usage classification: " + sid)
        source["usage_cn"] = " / ".join(
            policy["role_groups"][k]["description_cn"]
            for k in source["usage_categories"]
        )
        source["role_hazards"] = sorted(
            set(
                [r["hazard"] for r in source["hazard_roles"]]
                + policy["additional_planned_hazards"].get(sid, [])
            )
        )
        source["role_hazards_are_not_validated_chains"] = True
        source["dependence_notes_cn"] = policy["dependence_notes"].get(
            sid, policy["default_dependence_note_cn"]
        )
        if sid in recovered:
            report = recovered[sid]
            source["state"] = "decoded_sample"
            source["decoded_content_available"] = True
            source["recovery_audit"] = {
                "path": str(args.audit.relative_to(REPO)),
                "sha256": hashlib.sha256(args.audit.read_bytes()).hexdigest(),
                "record": report,
            }
            source["current_summary_cn"] = policy["recovered"][sid]["summary_cn"]
            source["remaining_gates_cn"] = policy["recovered"][sid]["gates_cn"]
            source["authorization_action_cn"] = (
                "本次已取回的公开样本无需补授权；版本、用途及再分发条款仍逐源核对。"
            )
        if sid in policy["remaining_access"]:
            source["remaining_access"] = policy["remaining_access"][sid]
        source["ready_role"] = (
            "sample_content_with_task_gates"
            if source["state"] == "decoded_sample"
            else "event_index_only"
            if source["state"] == "catalog_records_only"
            else "conditional_not_required_for_core"
        )
    ids = [s["source_id"] for s in sources]
    if len(ids) != 97 or len(set(ids)) != 97:
        raise ValueError("Inventory denominator changed")
    by_id = {s["source_id"]: s for s in sources}
    for row in policy["hazard_chains"]:
        for key in ["forecasts", "references", "extra_evidence"]:
            if any(sid not in by_id for sid in row[key]):
                raise ValueError("Unknown hazard-chain source")
    batches = [read(p) for p in sorted(ROOT.glob("captures_*/MANIFEST.json"))]
    captures = [r for batch in batches for r in batch["rows"]]
    ranges = [read(p) for p in sorted((ROOT / "camels_zip_01/ranges").glob("*.json"))]
    network = {
        "batch_requests": len(captures),
        "range_requests": len(ranges),
        "logical_requests": len(captures) + len(ranges),
        "response_body_bytes": sum(r["bytes"] for r in captures + ranges),
        "http_200_206_curl_zero": sum(
            r["http_status"] in [200, 206] and r["curl_exit"] == 0
            for r in captures + ranges
        ),
        "scope": "Includes failed/partial/metadata responses; redirects and package installs are not counted as extra logical data requests.",
    }
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "prior_registry": {
            "path": str(PRIOR.relative_to(REPO)),
            "sha256": hashlib.sha256(PRIOR.read_bytes()).hexdigest(),
        },
        "source_count": len(sources),
        "state_counts": dict(Counter(s["state"] for s in sources)),
        "upgraded_ids": sorted(recovered),
        "network": network,
        "new_formal_tasks": 0,
        "new_model_calls": 0,
        "new_gpu_jobs": 0,
        "hazard_count": len(policy["hazard_chains"]),
        "hazard_chains": policy["hazard_chains"],
        "sources": sources,
        "limit": "97 source/product/delivery entries are not independent datasets. Role coverage is not task admission or a positive novelty result.",
    }
    (args.output / "USAGE_REGISTRY.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    )
    fields = [
        "source_id",
        "name",
        "prior_state",
        "state",
        "ready_role",
        "usage_cn",
        "current_summary_cn",
        "remaining_gates_cn",
        "dependence_notes_cn",
    ]
    with (args.output / "USAGE_REGISTRY.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(sources)
    lines = [
        "# 97 个候选来源的使用清单",
        "",
        "本表继承冻结的候选登记；本轮新取样条目有独立回执，其余复用原始资产。`decoded_sample` 仅指已解析指定样例，不是正式预测任务准入。目录条目可直接承担事件检索。",
        "",
        "| ID / 来源 | 状态 | 本轮可安排的角色 | 已有证据 | 仍需处理 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for s in sources:
        cells = [
            s["source_id"] + " " + s["name"],
            s["state"],
            s["usage_cn"],
            s["current_summary_cn"],
            s["remaining_gates_cn"],
        ]
        lines.append(
            "| "
            + " | ".join(str(x).replace("|", "/").replace("\n", " ") for x in cells)
            + " |"
        )
    (args.output / "USAGE_REGISTRY_CN.md").write_text("\n".join(lines) + "\n")
    lines = [
        "# 16 灾种的数据组合与准入缺口",
        "",
        "这是基于真实取样的候选组合，不代表 16 类均已建成闭环。`extra_evidence` 仍需证明在同一地点、有效窗和截止前可用。",
        "",
        "| 灾种 | 专业预报候选 | 结果/代理参考候选 | 补充证据/感知候选 | 最关键缺口 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for h in policy["hazard_chains"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    h["id"] + " " + h["name_cn"],
                    ", ".join(h["forecasts"]) or "尚未确定",
                    ", ".join(h["references"]),
                    ", ".join(h["extra_evidence"]),
                    h["gate_cn"],
                ]
            )
            + " |"
        )
    (args.output / "HAZARD_CHAINS_CN.md").write_text("\n".join(lines) + "\n")
    print(
        json.dumps(
            {
                k: result[k]
                for k in ["source_count", "state_counts", "upgraded_ids", "network"]
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
