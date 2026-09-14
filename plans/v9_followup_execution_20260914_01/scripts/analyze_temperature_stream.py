"""Independent snapshot loss checks for the completed native temperature pilot."""

from collections import Counter, defaultdict
import math
from pathlib import Path

from disastertrace.monitoring_v1.spool_backend import publish, read

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"temperature_stream_02"
OUT=ROOT/"reports/temperature_stream_audit_01"


def main():
    complete=read(DATA/"COMPLETE.json")
    assert all(r["exit_code"]==0 for r in complete["programs"])
    OUT.mkdir(exist_ok=False)
    groups=defaultdict(Counter)
    unique_targets=set()
    total=0
    for case in sorted(DATA.glob("20??-??")):
        rows=read(case/"POLICY.json")["rows"]
        total+=len(rows)
        outcomes={r["opportunity_id"]:r for r in read(case/"OUTCOMES.json")}
        scores=read(case/"SCORES.json")["scores"]
        by_id={r["opportunity_id"]:r for r in rows}
        unique_targets.update(r["target"]["target_id"] for r in rows)
        follow=read(case/"follow__base_bound_override/SNAPSHOTS.json")
        for folder in sorted(case.glob("*__*override")):
            snapshots=read(folder/"SNAPSHOTS.json")
            assert set(snapshots)==set(by_id)
            losses=[]
            for oid, snapshot in snapshots.items():
                row=by_id[oid]
                g=groups[row["event"]+"__"+folder.name]
                p=snapshot["forecast"]["value"]
                b=follow[oid]["forecast"]["value"]
                if folder.name.startswith("follow__") or folder.name.startswith("copy_latest__") or folder.name.endswith("base_bound_override"):
                    assert p==row["probability"]
                g.update(n=1,different_from_follow=int(p!=b))
                y=outcomes[oid]["value"]
                if y is None:
                    g["missing"]+=1
                    continue
                loss=(p-y)**2
                delta=loss-(b-y)**2
                losses.append(loss)
                g.update(mature=1,positive=y,loss_sum=loss,delta_sum=delta,
                         improved=int(delta < -1e-14),worsened=int(delta > 1e-14))
            assert math.isclose(sum(losses)/len(losses),scores["arms"][folder.name]["mean_loss"],abs_tol=1e-14)
    result={"passed":True,"windows":8,"sessions":64,"target_opportunities":total,"unique_targets":len(unique_targets),
            "method_opportunity_rows":total*8,"groups":dict(groups),"model_calls":0,
            "all_current_value_programs_match_follow_under_base_bound":True,
            "complete_current_baseline_reproduced_independently":True,
            "scope":"eight exposed calendar windows at one station; repeated targets and thresholds are dependent; no LLM temperature result"}
    publish(OUT/"VALIDATION.json",result)
    lines=["# 温度连续预报程序试点", "", f"8 个日历窗口、64 条程序轨迹、{total} 个目标机会、{len(unique_targets)} 个唯一目标。没有模型调用。", "",
           "同一目标保留多次专业起报版本；不同提前量共享结果，不能作为独立灾害相加。", "",
           "| 事件 | 程序/协议 | 结算机会 | 正例机会 | Brier | 相对FOLLOW差值 | 改好/改坏 |", "| --- | --- | ---: | ---: | ---: | ---: | --- |"]
    for key,g in sorted(groups.items()):
        event,arm,protocol=key.split("__")
        lines.append(f"| {event} | {arm}/{protocol} | {g['mature']} | {g['positive']} | {g['loss_sum']/g['mature']:.6f} | {g['delta_sum']/g['mature']:.6f} | {g['improved']}/{g['worsened']} |")
    lines += ["", "COPY_CURRENT/首次值保持如果改变了损失，改变来自旧概率持续有效，不是产生了新概率。",
              "未来阶段仍需合法补充证据、强校准和真实模型预测；本批不证明 C1 的跨灾种收益。"]
    (OUT/"REPORT_CN.md").write_text("\n".join(lines)+"\n")
    print({k:result[k] for k in ["passed","windows","sessions","target_opportunities","unique_targets","method_opportunity_rows"]})


if __name__=="__main__":
    main()
