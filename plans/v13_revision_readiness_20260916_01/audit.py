"""Read public annual clocks and historical receipts; no forecast or label read."""

import datetime as dt
import hashlib
import json
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

RUN=Path(__file__).resolve().parent
REPO=RUN.parents[1]
V12=REPO/"plans/v12_execution_20260915_01"
OLD=REPO/"plans/v10_execution_20260914_01/multicutoff_01"
HOUR=3_600_000_000


def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(name,value):
    with (RUN/name).open("x") as f:json.dump(value,f,ensure_ascii=False,indent=2);f.write("\n")


def unit(row):
    dataset=Path(row["dataset"]);build=read(dataset/"BUILD.json")
    paths=[dataset/"public"/n for n in ("TARGETS.json","OPPORTUNITIES.json")]
    for p in paths:
        if sha(p)!=build["files"][str(p.relative_to(dataset))]:raise ValueError("Public input differs from original BUILD")
    targets={t["target_id"]:t for t in read(paths[0])}
    opportunities=read(paths[1]);leads=Counter();feature_leads=Counter();windows=Counter()
    for o in opportunities:
        target=targets[o["target_id"]]
        lead=(target["physical_start"]-o["cutoff"])/HOUR
        if lead!=o["lead_hours"] or lead<=0:raise ValueError("Invalid registered lead")
        leads[str(lead)]+=1
        feature_leads[str((target["physical_start"]-(o["cutoff"]-600_000_000))/HOUR)]+=1
        windows[str((target["physical_end"]-target["physical_start"])/HOUR)]+=1
    return {"unit":row["unit"],"opportunities":len(opportunities),"registered_lead_hours":dict(leads),
        "fit_convention_feature_lead_hours":dict(feature_leads),"target_window_hours":dict(windows),
        "files":{str(p):sha(p) for p in paths+[dataset/"BUILD.json"]}}


def main():
    reg=read(RUN/"REGISTRATION.json")
    for name,h in reg["files"].items():
        if sha(Path(name))!=h:raise ValueError("Frozen readiness input changed")
    joins=read(V12/"annual_stage_B/joins/RESULT.json")
    if not joins["passed"] or len(joins["results"])!=72:raise ValueError("Annual joins incomplete")
    with ProcessPoolExecutor(max_workers=2) as pool:units=list(pool.map(unit,joins["results"]))
    lead=Counter();feature_lead=Counter()
    for row in units:
        lead.update(row["registered_lead_hours"]);feature_lead.update(row["fit_convention_feature_lead_hours"])
    banks={}
    for mode in ("common","values"):
        p=V12/"annual_stage_B/fit"/("BANK_"+mode+".json");bank=read(p)
        index=bank["feature_names"].index("lead_hours")
        banks[mode]={"path":str(p),"sha256":sha(p),"mapping_version":bank["mapping_version"],
            "lead_feature_mean":bank["mean"][index],"lead_feature_scale":bank["scale"][index],
            "lead_feature_coefficients":[c[index] for c in bank["coefficients"]]}
    plan=read(OLD/"PLAN.json")
    for name,h in plan["files"].items():
        if sha(OLD/name)!=h:raise ValueError("Historical multicutoff frozen file changed")
    completion=read(OLD/"COMPLETE.json")
    expected={(r["case"],arm) for r in plan["cases"] for arm in r["arms"]}
    actual=[(r["case"],r["arm"]) for r in completion["results"]]
    if len(actual)!=len(expected) or set(actual)!=expected:raise ValueError("Historical method roster differs")
    multi=[]
    for row in plan["cases"]:
        data=read(OLD/row["case"]/"DATA.json");cutoffs=defaultdict(set)
        for o in data["opportunities"]:cutoffs[o["target_id"]].add(o["cutoff"])
        multi.append({"case":row["case"],"targets":len(cutoffs),"opportunities":len(data["opportunities"]),
            "cutoffs_per_target":dict(Counter(str(len(x)) for x in cutoffs.values()))})
    old_result=read(REPO/"plans/v10_execution_20260914_01/reports/multicutoff_analysis_01/RESULT.json")
    write("MULTICUTOFF_PRIOR_EVIDENCE.json",{"passed":True,"historical_cases":multi,
        "registered_trajectories":len(expected),"historical_report":old_result,
        "inspection":"registered inputs/hash and completion roster reconciled; historical score receipts read, not re-executed or upgraded to new-source formal acceptance",
        "same_target_history_exists":True,"uses_current_annual_native_bank":False})
    ready=set(lead)=={"1.0"}
    result={"audit_passed":True,"multilead_predictor_qualified":False,
        "status":"NEW_C01_EXPERIMENT_NOT_RUN_PREDICTOR_SUPPORT_UNQUALIFIED",
        "units":units,"registered_lead_hours":dict(lead),"fit_convention_feature_lead_hours":dict(feature_lead),
        "banks":banks,"all_annual_public_inputs_single_lead":ready,
        "scope":"public input support superset; no outcomes or fit/calibration labels read; dynamic purge can remove rows but cannot create new leads",
        "bank_decision":"proposed retained annual bank audited; B01 final decision awaits complete B00",
        "new_model_calls":0,"new_forecasts":0,"new_fits":0,"confirmation_opened":False,
        "finished_at":dt.datetime.now(dt.timezone.utc).isoformat()}
    write("FIXED_TARGET_REVISION_RESULT.json",result)
    write("FIXED_TARGET_REVISION_PROPOSAL.json",{
        "status":"NO_LAUNCHER_UNQUALIFIED","fixed_targets_max":6,"cutoffs_per_target_max":3,
        "protocols":["base_bound_override","persistent_override"],"program_conditions_max":4,"score_rows_max":144,
        "target_weights":"each fixed target has total weight1 split equally over its registered cutoffs; methods share exact Y and outcome version",
        "requirements":["freeze a predictor with documented lead support or explicitly label an extrapolation-only diagnostic",
            "reconstruct all legal earlier-lead public products and query links without moving late evidence backward",
            "metadata-only target/lead roster before labels; bind annual bank decision and protocol",
            "preserve 2023fit/2024calibration/2025development roles and dynamic-source purging if one new fit is justified"],
        "recommended_sequence":"finish fixed-consumer B02 and GET first; evaluate one bounded multilead/slot-aligned fit separately if the revised claim needs it",
        "claims_allowed_now":"shared-budget lead1h development evaluation; older exposed multi-cutoff protocol diagnostic",
        "claims_not_established":"current annual predictor is validated for3h/6h forecasting or continuous same-target revision gains"})
    text=f'''# C01 多截止修订资格核验

本次只读核验已完成，没有运行新的预测实验。

已有 v10 历史实验确实包括同一目标在 6/3/1 小时截止下的修订：12 个 case、108 个唯一目标、324 个机会、216 条程序轨迹。登记文件 hash 和完成分母已重新核对。旧分析记录 5,832 个方法行；这是旧区域银行的开发诊断，不是当前年度原生特征银行的验证。本次没有重新执行旧评分或将旧回执升级为当前正式验收。

实际扫描了年度构建的全部 {len(units)} 个月份单元、{sum(lead.values())} 个公开机会，目标提前量分布为 `{dict(lead)}`。按照冻结训练代码的 `cutoff - 600s` 时点，lead 特征分布为 `{dict(feature_lead)}`。这些是训练/校准输入的上层集合；后续剔除可以减少行数，无法增加新的提前量。

所以当前引擎可以表达多截止，但年度预测器没有获得 3/6 小时的训练支持和评测资格。现有 B00/B02 的固定 1 小时目标继续运行；已知训练时点与真实预测时槽的轻微偏移仍保留为限制，不能由此次核验抹除。

下一步若要正式宣称当前预测器的多截止修订能力，需要先确定支持这些提前量的预测器及对应合法资料链。新实验上限仍为 6 个固定目标 × 3 个截止 × 2 个协议 × 4 个条件 = 144 行；每个目标跨截止的总权重固定。先完成 B02 和 GET，再决定是否用一个独立登记的多提前量/时槽对齐拟合解决此缺口。
'''
    (RUN/"README_CN.md").write_text(text)
    print(json.dumps({k:v for k,v in result.items() if k not in ("units","banks")}),flush=True)


if __name__=="__main__":main()
