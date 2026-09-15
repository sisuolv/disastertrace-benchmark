from pathlib import Path
import json, hashlib, zipfile

ROOT=Path(__file__).resolve().parent
S=ROOT/'specs'; S.mkdir(exist_ok=True)
COMMIT='889620a4fc4ee6ad70757dd3e832a40c7509126a'
REPO='https://github.com/sisuolv/disastertrace-benchmark'
def link(p): return f'{REPO}/blob/{COMMIT}/{p}'
source_items=[
('revision','branch snapshot','https://api.github.com/repos/sisuolv/disastertrace-benchmark/branches/next-phase-v1','turn351file0'),
('progress','LATEST_PROGRESS_V11_CN.md',link('LATEST_PROGRESS_V11_CN.md'),'turn353file0'),
('snapshot','publication/v11_inprogress_20260915/PROGRESS_SNAPSHOT.json',link('publication/v11_inprogress_20260915/PROGRESS_SNAPSHOT.json'),'turn358file0'),
('review','publication/v11_inprogress_20260915/REVIEW_FOR_CHATGPT_PRO_CN.md',link('publication/v11_inprogress_20260915/REVIEW_FOR_CHATGPT_PRO_CN.md'),'turn354file0'),
('plan','plans/v11_planning_20260915_01/OVERALL_PLAN_CN.md',link('plans/v11_planning_20260915_01/OVERALL_PLAN_CN.md'),'turn355file0'),
('execution','plans/v11_execution_20260915_01/README_CN.md',link('plans/v11_execution_20260915_01/README_CN.md'),'turn356file0'),
('fullweek','plans/v11_execution_20260915_01/fullweek.py',link('plans/v11_execution_20260915_01/fullweek.py'),'turn360file0;turn376file0'),
('Eproducer','disastertrace-starter/src/disastertrace/monitoring_v1/policies.py',link('disastertrace-starter/src/disastertrace/monitoring_v1/policies.py'),'turn377file0'),
('Estatus','disastertrace-starter/src/disastertrace/monitoring_v1/evidence.py',link('disastertrace-starter/src/disastertrace/monitoring_v1/evidence.py'),'turn379file0'),
('C2builder','plans/v11_execution_20260915_01/prepare_c2.py',link('plans/v11_execution_20260915_01/prepare_c2.py'),'turn362file0'),
('nativebuilder','plans/v8_measurement_execution_20260913_01/scripts/build_native_v2.py',link('plans/v8_measurement_execution_20260913_01/scripts/build_native_v2.py'),'turn367file0'),
('versions','disastertrace-starter/src/disastertrace/monitoring_v1/providers/versions.py',link('disastertrace-starter/src/disastertrace/monitoring_v1/providers/versions.py'),'turn368file0'),
('TAFE','disastertrace-starter/src/disastertrace/monitoring_fixed_v1/taf_tasks.py',link('disastertrace-starter/src/disastertrace/monitoring_fixed_v1/taf_tasks.py'),'turn374file0'),
('formal','disastertrace-starter/src/disastertrace/monitoring_v1/formal_session.py',link('disastertrace-starter/src/disastertrace/monitoring_v1/formal_session.py'),'turn363file0;turn364file0'),
('score','disastertrace-starter/src/disastertrace/monitoring_fixed_v1/admission.py',link('disastertrace-starter/src/disastertrace/monitoring_fixed_v1/admission.py'),'turn370file0'),
('temperature','disastertrace-starter/src/disastertrace/monitoring_v1/temperature_contract.py',link('disastertrace-starter/src/disastertrace/monitoring_v1/temperature_contract.py'),'turn361file0'),
('common','disastertrace-starter/src/disastertrace/monitoring_fixed_v1/native_feature.py',link('disastertrace-starter/src/disastertrace/monitoring_fixed_v1/native_feature.py'),'turn365file0'),
('annualcatalog','plans/v11_execution_20260915_01/annual_catalogs.py',link('plans/v11_execution_20260915_01/annual_catalogs.py'),'turn369file0'),
('annualnative','plans/v11_execution_20260915_01/annual_native_sample.py',link('plans/v11_execution_20260915_01/annual_native_sample.py'),'turn366file0'),
('fullanalysis','plans/v11_execution_20260915_01/analyze_fullweek.py',link('plans/v11_execution_20260915_01/analyze_fullweek.py'),'turn378file0'),
('APIdispatch','disastertrace-starter/src/disastertrace/monitoring_v1/api_capture_v2.py',link('disastertrace-starter/src/disastertrace/monitoring_v1/api_capture_v2.py'),'turn371file0'),
('APIledger','disastertrace-starter/src/disastertrace/monitoring_v1/api_ledger.py',link('disastertrace-starter/src/disastertrace/monitoring_v1/api_ledger.py'),'turn372file0'),
('AWC','Official TAF amendment semantics','https://aviationweather.gov/help/data/','turn811842search2'),
('AWCAPI','Official access and batch-cache scope','https://aviationweather.gov/data/api/','turn811842search0'),
('calibration','Official independent-fit/calibration requirement','https://scikit-learn.org/stable/modules/generated/sklearn.calibration.CalibratedClassifierCV','turn811842search5'),
]
(S/'sources.json').write_text(json.dumps({'reviewed_commit':COMMIT,'sources':[{'id':i,'path_or_title':p,'url':u,'citation_base':c,'status':'read_source_not_upstream_framework_executed'} for i,p,u,c in source_items]},ensure_ascii=False,indent=2)+'\n')
packages=[
('W00-status','W00','对账进行中任务与冻结来源',[],
 ['publication/v11_inprogress_20260915/PROGRESS_SNAPSHOT.json','plans/v11_execution_20260915_01/'],
 ['STATUS_RECONCILIATION.json','SOURCE_RUNTIME_MATRIX.json'],
 ['每条任务有实际作业ID、尝试ID、已验证终态或显式unknown，不从日志静默推断成功。','报告数量区分模型回答、程序轨迹、方法行、目标、时距和父过程。','正在运行的冻结源码和已消费launcher不得修改或重开；剩余工作使用独立尝试与明确范围。','新报告明确as_of，先核读本地新终态；不把本复查中的进行中状态永久沿用。']),
('W05-07-E-summary','W05/W07','修正E枚举并只读核算影响',['W00-status'],
 ['plans/v11_execution_20260915_01/fullweek.py','disastertrace-starter/src/disastertrace/monitoring_v1/evidence.py'],
 ['E_STATUS_SUMMARY_IMPACT.json','E_STATUS_RECOUNT.json'],
 ['四种真实状态supported/refuted/undetermined/inconsistent中恰有两种可判定，未知枚举必须拒绝。','从冻结frames/ROWS重新计数；旧统计、修订统计、差值和原哈希并存。','验证修订仅影响派生E字段，不改变原预测、机会、F结果、Brier和资源回执。','按方法/阈值/日期输出affected、unchanged、not_evaluated，缺日志不能当0影响。']),
('W11-universe','W11','从完整合法来源构建C2，不从可投影候选反推',['W00-status'],
 ['plans/v11_execution_20260915_01/prepare_c2.py','plans/v8_measurement_execution_20260913_01/scripts/build_native_v2.py','disastertrace-starter/src/disastertrace/monitoring_fixed_v1/taf_tasks.py'],
 ['C2_UNIVERSE_DIFF.json','C2_CALENDAR_CENSUS.json','C2_INTERVENTION_DEPENDENCY.json'],
 ['较新AMD不覆盖目标时，不因预过滤而复活旧覆盖版本；核心current_taf保持复用。','同刻不覆盖的另一版本仍参与语义冲突判断；等价镜像按既有规则处理。','保留NIL/CNL/unparsed/无产品/部分覆盖，公开输入仅含当时合法披露的资料。','现有144题保留为provided-packet诊断；完整版本/实际会话状态资格另列，不回写原Gold。','TAF E与METAR查询分支的依赖明确；TAF未变化时E不变是正确结果，不视为失败。','E的as_of来自实际checkpoint时钟；开始至cutoff之间的新产品不得提前进入旧状态。']),
('W07-close','W07','收口840条完整日历程序对照',['W05-07-E-summary'],
 ['plans/v11_execution_20260915_01/fullweek.py','plans/v11_execution_20260915_01/analyze_fullweek.py'],
 ['FULLWEEK_RECONCILIATION.json','FULLWEEK_PAIRED_REPORT_CN.md'],
 ['168个日条件、840轨迹、12096机会和60480方法行由ID逐项核验，不用计划数代替实际数。','合法失败留在登记中；不完整比较不声称最终赢家，不删除困难或无结果机会。','共同baseline流与预测开始/完成日程一致；common与values是不同银行的控制，不归因于纯取证。','按全日历/日期/地区/季节和正负例贡献同时呈现，缺失界与置信区间分开。']),
('W06-08-annual','W06/W08/W09','年度来源分层与季节覆盖的后端冻结',['W00-status'],
 ['plans/v11_execution_20260915_01/annual_catalogs.py','plans/v11_execution_20260915_01/annual_native_sample.py','disastertrace-starter/src/disastertrace/monitoring_v1/process_split.py'],
 ['ANNUAL_STAGE_LEDGER.json','NATIVE_PRODUCT_DEDUP_MANIFEST.json','ROLE_DEPENDENCY_MANIFEST.json','BANK_REGISTRATION.json'],
 ['失败KORD分片补取前核对有效重试范围；已成功五片和其他71个月复用，不重开整年launcher。','分别统计目录、原文、科学解析、任务连接、角色准入、拟合；2470条枚举不能算2470条已解析。','按原始产品ID/内容哈希去重月间padding，并保留未支持语法与缺报，机会分母不删。','2023内部选择、2024最终校准、2025已暴露开发分清；完整输入/结果/状态足迹purge。','部署缺证模式在拟合中有明确权重，保留raw与calibrated及旧银行；不以确认收益选模型。']),
('W01-02-contract','W01/W02/W05','补齐本轮新增路径需要的合同，不泛化重建',['W00-status'],
 ['disastertrace-starter/src/disastertrace/monitoring_v1/formal_session.py','disastertrace-starter/src/disastertrace/monitoring_v1/temperature_contract.py','disastertrace-starter/src/disastertrace/monitoring_fixed_v1/outcome_policies.py'],
 ['DATA_CARD_BINDING_REPORT.json','PROVIDER_QUALIFICATION_MATRIX.json','MEMBER_LINEAGE_MANIFEST.json'],
 ['数据卡文件哈希、schema语义、parser、prompt及结果身份分别绑定，不把文件存在当全部门槛已过。','保留正式v2目录/data/bank/report/journal/STOP和完整干预检查；legacy明确只读，不升格。','max-only合法目标不因未使用min字段缺失而被排除；点/区间/目标变量按实际消费资格处理。','成员shape不当lineage证明；三日路径绑定同起报和真实member ID，错置单日成员要被检测或降级。']),
('W10-11-branch','W10/W11','让真实同状态分支解释E到F而不追求必胜',['W11-universe','W01-02-contract'],
 ['plans/v11_execution_20260915_01/c2_design_01/','disastertrace-starter/src/disastertrace/monitoring_v1/session_checkpoint.py','disastertrace-starter/src/disastertrace/monitoring_v1/residual_reachability.py'],
 ['BRANCH_PARENT_MANIFEST.json','BRANCH_FEASIBILITY.json','FIELD_TO_LOSS_TRACE.jsonl'],
 ['72目标前缀映射到24父会话状态；不要每目标重新赠送完整共享预算。','分叉继承spent/reserved、cache、授权、pending、基线、override、时钟和继续策略；原pending只履行一次。','no_further_paid_query继续同一F日程，不等于终止整个会话；已取得或不可及时完成的动作保留状态。','分支评分覆盖所有受资源取舍影响的登记目标；局部改善与会话总机会成本分别报告。','分别记录字段/特征/概率/采用/损失变化，不把最终E归约当当前F直接输入，不合成无归档返回。']),
('W12-MM','W12/C3并行出口','一条同未来目标的原生多模态链',['W01-02-contract'],
 ['disastertrace-starter/src/disastertrace/multimodal_v1/','disastertrace-starter/src/disastertrace/multimodal_live_v1/','disastertrace-starter/src/disastertrace/monitoring_v1/'],
 ['MM_OPPORTUNITY_QUALIFICATION.json','MM_INPUT_PROVENANCE.json','MM_COMPARISON_REGISTRATION.json'],
 ['先按原始数据与合法时间配对，不用事后灾害中心、结果或有利分数选择图片。','图像确实进入VLM处理器，图像/ROI/波段/渲染/顺序/视觉token与调用回执可核验。','固定供图与主动选择分开；同源结构化表示、原图、专业工具、特权视觉事实分别标记。','可用资料的获取、再处理和再次推理分开计费，所有策略可用相同专业工具。']),
('W12-13-validate','W12/W13与前瞻分轨','有限模型机制、独立确认和真实前瞻',['W07-close','W06-08-annual','W10-11-branch'],
 ['plans/v11_planning_20260915_01/','plans/v11_execution_20260915_01/'],
 ['MODEL_MECHANISM_REGISTRATION.json','CONFIRMATION_GATE.json','LIVE_SHADOW_SCOPE.json'],
 ['先冻结共同后端、一个主要问题、强程序基线及总成本口径，不要求LLM获胜。','Bay保留周不因本计划打开；主次指标、过程组与精度/停止规则先冻结，不按阳性或收益续采。','历史未读取不等于模型预训练未见；前瞻必须真实先提交、后取得结果，API历史调用不算online。','D-sim与现实损失分开，复杂行动/联合预测不阻塞E/F/MM；原生MM未过不得宣称整体MM主链完成。']),
]
work=[]; tests=[]
for ident,parent,title,deps,paths,outputs,criteria in packages:
    ids=[]
    for n,req in enumerate(criteria,1):
        tid=ident+'-T'+str(n).zfill(2);ids.append(tid)
        tests.append({'id':tid,'work_package':ident,'requirement':req,'status':'specified_not_executed','evidence_required':['executable_test_or_real_roster_audit','raw_log','input_source_hashes']})
    work.append({'id':ident,'maps_to_existing':parent,'title':title,'depends_on':deps,'implementation_paths':paths,'required_outputs':outputs,'acceptance_ids':ids,'first_pass':'CPU/read-only unless separately authorized scope is verified'})
(S/'work_packages.json').write_text(json.dumps({'reviewed_commit':COMMIT,'preserve_plan':'v11 W00-W13 C1/C2/C3 E/F/D/MM and 16 hazards','work_packages':work},ensure_ascii=False,indent=2)+'\n')
(S/'acceptance_tests.json').write_text(json.dumps({'status':'future_specs_not_completed_tests','count':len(tests),'tests':tests},ensure_ascii=False,indent=2)+'\n')
state={'reviewed_commit':COMMIT,'publication_as_of':'2026-09-15T12:06:47.602706+00:00','release_kind':'in_progress',
 'reported_tests':{'current':585,'supplemental_distinct':165,'total':750,'rerun_by_reviewer':False},
 'reported_model_calls_in_v11':0,'reported_preflight':{'arms':5,'method_rows':360},
 'fullweek':{'expected_daily_cases':168,'expected_trajectories':840,'expected_unique_opportunities':12096,'expected_method_rows':60480,'final_audit_at_snapshot':False},
 'annual_inventory':{'region_months':72,'logical_slices':432,'completed_region_months':71,'failed_region_months':1,'native_TAF_sample_enumerated':2470,'sample_regions_completed':0,'annual_fit_complete':False},
 'C2':{'prefixes':72,'parent_sessions':24,'tasks':144,'coverage_full':72,'branch_runs':0,'F_scored':False},
 'review_execution':{'byte_verified_modules':3,'module_scoped_checks':21,'E_summary_expression_checks':1,'full_suite_rerun':False,'production_C2_compiler_rerun':False,'actual_840_trajectory_impact_audited':False,'new_model_calls':0,'new_scientific_downloads':0,'zip_download':'DNS failure; not independently unpacked'},
 'warnings':['All completion claims after the publication as_of require fresh actual run receipts.','Do not modify frozen running sources or reopen consumed launchers.']}
(S/'review_scope.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n')
findings=[
 {'id':'F01','severity':'P1','status':'confirmed_expression_bug','source':'fullweek.py::audit','claim':'E summary counts entailed/refuted but producer uses supported/refuted; positive certified statuses are omitted.','actual_impact':'not_yet_scanned','F_Brier_direct_effect':False},
 {'id':'F02','severity':'P1','status':'confirmed_source_selection_boundary; real frequency not scanned','source':'prepare_c2.py + build_native_v2.py','claim':'C2 universe is built from already projectable target candidates, excluding some current noncovering/cancelled/conflicting source records. Supplied-packet references may remain internally correct.','actual_impact':'not_yet_scanned'},
 {'id':'F03','severity':'research_gate','status':'confirmed_design_disconnect','source':'prepare_c2.py DESIGN','claim':'Paid METAR branches do not change a fixed free TAF coverage question; separate processing and acquisition experiments and connect real F-consumed fields.'},
 {'id':'F04','severity':'scope_gate','status':'declared_unfinished','source':'temperature_contract.py and latest scope report','claim':'Shape validation is not member lineage; keep legal max-only acceptance and require source lineage for joint trajectory claims.'}
]
(S/'findings.json').write_text(json.dumps({'findings':findings},ensure_ascii=False,indent=2)+'\n')
print('packages',len(work),'acceptance specifications',len(tests),'sources',len(source_items))
