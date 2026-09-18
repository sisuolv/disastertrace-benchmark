# DisasterTrace v9：基于 6f71c879 当前结果的 Codex 后续执行计划

核对基线：`sisuolv/disastertrace-benchmark` / `next-phase-v1` / `6f71c8799ff69439a18f645e63b8c966ca21eec4`。
审查日期：2026-09-14。父提交为 `5ed0fb94ae7bf235b37e7528e201b603271edffa`。

本文件是新的建议计划，不是已完成声明，不授权新增 API、GPU、训练、数据批量下载或打开确认集。当前已暂停；先完成可离线完成的核查，再依据当时真实有效的新批次授权执行需要费用的部分。保留当前 v9、C1/C2/C3、E/F/D/MM、N1–N5 及继承的 W00–W19 / X00–X09，不创建另一个总体方向。

## 0. 执行者首先要做的事

读取实际 HEAD、`git status --porcelain=v2`、已暂存内容与当前最新入口。若 HEAD 已前进，先输出与本审查基线的差异，不把本文件视为对后续代码的认证。禁止 `reset --hard`、清除工作区、覆盖冻结捕获、改写失败日志或重启已消费 launcher。所有新输出写入唯一目录，变更计划以增补记录表达。

以下读取次序以当前发布为准：

1. 根目录 `LATEST_PROGRESS_20260914_CN.md`。
2. `publication/v9_followup_20260914/README_CN.md` 与 `REVIEW_FOR_CHATGPT_PRO_CN.md`。
3. `plans/v9_followup_execution_20260914_01/PAUSED_SUMMARY_CN.md`、`RUN_REPORT_CN.md`、`EXECUTION_STATUS.json`。
4. 同目录 `reports/regional_baselines_01/SUMMARY.json`、`reports/e_error_mechanisms_01/REPORT_CN.md`、普通与 Denver F 审计、温度完整日历报告。
5. `plans/v9_followup_roadmap_20260914_01/RESEARCH_ROADMAP_CN.md`，但其中较早的 577 项、Qwen3.8 144 次、温度未接线等语句必须由最新暂停结果覆盖，不机械重做。

复查包不含全部原生大数据、完整 F journal 和 checkpoint。已有本机审计成功不等于本次外部复查重跑成功。不得用当前源码直接替换旧批冻结源码重算后冒称原结果。

## 1. 当前实际起点与禁止重复项

| 项目 | 当前证据 | 后续定位 |
|---|---|---|
| 结果/比较合同导出隔离 | 当前 `outcomes.py` 用规范 JSON 深复制；旧封装问题已修改 | 核生产回归与调用方影响，不重复套用旧补丁 |
| 工程测试 | 发布报告 616 项通过 | 在实际环境记录本轮真正测试数，不能继承为本轮执行数 |
| 四区域数据与概率银行 | 3,303 次获取；净拟合 9,678、校准 2,780；时间范围分开 | 核映射作用与分布稳定性，不重复下载拟合材料 |
| E02 | 两模型共 1,008 次；42 个底层问题、126 条件实例/模型/表示/输出组合 | 已暴露开发材料，扩展前先解释槽位与汇总差别 |
| F 普通日历 | Jan6、Jan10；三地区、各三站、1h；每阈值 432 机会、431 结算 | 普通日历的选定日切片，不叫完整自然周或独立过程样本 |
| Denver 正例诊断 | Jan9 因已知三条 1km 正例入选；每阈值72机会 | 明确结果选择的探索诊断，绝不并入自然发生率主结果 |
| COPY | 当前 API 同批已有 FOLLOW/COPY_BASELINE/COPY_CURRENT | 不重新安排“首次实现 COPY”；当前 base-bound 下接近等价不是普遍结论 |
| 温度 | 24 月、192 程序轨迹、11,644 机会、3,645 唯一目标 | 连续版本程序轨已完成，新增的是补充信息/LLM/独立过程 |
| 原采集失败 | E01 938尝试、876结算、62未知；完整E02另批执行 | 不补采失败位置替换旧分数，不清零未知费用 |
| 资源与暂停 | 本轮无新增 GPU；有 API 和 ACP CPU 工作 | 新批次须重新绑定范围；评估成本与采集/复查成本分账 |

## 2. 科学合同保持不变，但把归因再分细一层

C1 评测共同专业信息下的资源分配/授权/选择/处理；C2 评测当前可见事实与共享资源下的可支持性，并诊断 E 与 F 的关系；C3 检查跨目标、资料与独立过程的可复现性。

必须区分六种可能导致分数变化的因素：

1. 额外数据内容改变；
2. 读取/缺测状态改变；
3. 频率单元或回退层次改变；
4. 后校准器改变；
5. 查询、提交时刻及版本状态改变；
6. 模型对同一信息的理解、概率生成或选择改变。

现有统计预测器用非空 `disclosed` 选择 evidence 校准器。即使 evidence cell 不达支持数而回退到相同 base cell、甚至返回的是 missing，后校准器仍可改变概率。此行为可以是明确的建模选择；它不是自动错误，但不能把这部分变化全归给新增气象事实。

不以候选方法必须胜出作为任务准入或交付门槛。未读不等于负例，证据充分不意味着未来有唯一正确概率，程序 all-read 失败不证明信息论上无价值。资料不足、字段/QC不明、无法结算分别记录，不让 LLM 补造 Gold。

## 3. 第一优先：不新增模型的概率归因审计

对应 N3 / N4、W06 / W11 / W12、X00 / X01 / X02。

### 3.1 新增逐预测解释记录

优先在 `monitoring_v1/calibration.py` 增加一个独立解释接口或可选记录器，保留原 `predict` 返回合同与旧映射语义。字段建议：

```text
bank_hash / mapping_version / fit_period / calibration_period
source_candidate_id / source_issued_at / dispatch_at
registered_query_ids / disclosed_query_ids / usable_fact_ids / missingness
attempted_cell_keys / selected_cell_key / selected_cell_n / fallback_level
raw_probability
post_calibration_family / post_calibration_block / calibrated_probability
visible_baseline_probability / visible_current_probability
proposed_probability / admission_status / effective_probability / cutoff
```

先在已有捕获上核算，不用未来标签决定运行时路由。离线评价侧可以关联未来结果，政策侧不能读取。

### 3.2 最少需要的对照

| 条件 | 特征与后校准处理 | 目的 |
|---|---|---|
| B-raw | 当前基础原始频率，无后校准 | 参考原始研究映射，不称官方概率 |
| B-cal | 基础特征 + base 校准器 | 现有合法起点 |
| E-raw | 补充特征/回退单元，无后校准 | 内容对频率投影的作用 |
| mapping-only | 保持基础原始概率，切到 evidence 校准器 | 隔离仅校准切换 |
| missingness-only | 保留实际请求、掩码、版本、时间与费用，不暴露新增值 | 区分访问/缺测条件与内容 |
| E-cal | 原补充特征 + evidence 校准器 | 完整原程序流程 |

这些条件是研究干预，不是永久删除 evidence 校准器的建议。分布不同可以合理需要分开校准。要求的是透明归因，并在独立时期检验；不要看到当前测试上的方向后再挑最有利的映射。

另按 `candidate=None` / 不覆盖 / 正常 TAF 分层。当前 no_taf key 不使用观测内容：先报告这个预测器适用范围；只有在独立训练/校准上建立新回退模型后，才能比较“无 TAF 时用观测”。

### 3.3 验收

已有原预测数值应逐条不变；新增记录与原单元/映射一致；能自动复现本审查 P1/P2 合成例子；扫描真实轨迹报告发生次数、损失贡献和不可核对比例。分成同捕获输入分析、固定时序反事实、新成本下真实程序闭环三种结果，不能混用。

禁止为验证该问题重跑原 API 请求。禁止在报告中把合成例子的0.1→0.35当作真实天气分数。

## 4. 第二优先：把 E 的可观测错误变成可部署的小管线对照

对应 N3、W10 / W12、X04。

已核到 Pro 某原始回答将两个槽分别判断为 false/unknown，却将存在命题汇总为 false；参考应为 unknown。`evidence_diagnostic.parse` 接受字段合法但逻辑错误的结果、再由评分器处罚，是正确设计，不应修改 parser 自动修复旧输出。

新增四条清楚命名的候选管线：

1. model-direct：原模型总体结论。
2. model-slotwise-native：模型逐槽和模型自报总体结论，原样计分。
3. model-slotwise-program-reduce：只读取模型自己的逐槽结果，按公开固定逻辑汇总；保留原自报总体作为审计字段。
4. native-product-program：对同一合法公开产品执行已有确定性解析与归约，作为普通强基线；若使用图外信息/隐藏标注，则必须标为特权诊断。

第三条绝不读取 `REFERENCES.json` 或未来结果，也不把错误槽位替换为 Gold。输出失败或槽位缺失必须保留，不能通过程序猜测补齐。报告原始模型、派生程序汇总、新闭环管线三个身份。

E-F连接时不能用一个聚合布尔值伪装完整观测状态。固定预测器分别消费真实可见产品特征、模型预测的逐槽状态和相应未知/未获取掩码；目标、读取路径、银行与费用不变。先在 CPU/已捕获输出上测试接口，再独立冻结新模型调用。

覆盖状态按真实支持规则分层：正见证、部分反证、完整反证、删失跨阈、缺测、版本替代；没有自然冲突就说明空缺，合成冲突不算自然新增模型证据。自动置换 query_id、槽顺序、重复同源表示只能作为配对诊断，不能增加独立样本数。

预算比较同时报告输出格式长度和实际token。逐槽输出天然更长，不能将它与direct完全混称等计算推理比较。512tokens等请求上限与等总预算是两种设置。

## 5. 第三优先：完整报出同批 F 的方法、分母和资源

对应 N4 / W07 / W12 / X01。

当前执行器已定义 FOLLOW、COPY、batch、risk、coverage、四个quota/authorization组合以及两模型的selector/program和batch/LLM组合。主摘要只显示部分方法，后续必须从已有规范评分导出全方法表，不只展示相对FOLLOW的改善。

必须报告以下效应：

- LLM predictor vs COPY_CURRENT/COPY_BASELINE/FOLLOW。
- 同一固定program下，LLM selector vs batch/risk/coverage。
- 固定selector、固定predictor的quota × authorization。
- 统一结果掩膜下的Brier，及help/harm/no-change的次数和幅度。
- 每目标、站点/日、地区块的配对损失；相关机会不能作IID显著性样本。
- 新数值分别按精确、1e-6和0.005阈值报告；proposed/admitted/effective分开。
- 费用使用实际source/selector/predictor行为，API服务端compute未知继续保留；不能由HTTP时间宣称模型物理计算速度。

Denver 是已知结果选择的探索集。与自然Jan6/Jan10切片分表；后者也不是完整Jan6–12全周。按外部规则预登记事件集仍可能是富集集，不能因此称自然发生率样本。

已有表中 Denver 的 Pro selector 相对FOLLOW改善，较batch的增量更小。这个比较只提供开发线索，不能作为独立统计结论，更不能按该收益挑下一组站点。

## 6. 数据分组与独立确认：保留已完成的拟合工作，补真正缺口

对应 N2 / N3 / N5、W11 / W17。

四区域既有fit/calibration已完成，不用再安排“首次建立区域银行”。新增工作是检查：

- 完整输入回看和原生TAF有效窗；不能只有target支持。
- query slots与更早源版本的依赖；会话启动、持久override和记忆携带。
- 共享源资产、跨阈值相同观测、多提前量相同target、重叠三日温度窗。
- 拟合/校准/开发/确认之间无对象或时间窗交叠；过程相关块是保守界，不等于经气象识别的独立过程。
- 概率单元支持量、回退比例、来源缺失模式、地区和季节迁移。

银行是基于专业TAF特征的研究频率映射；B-raw也不是官方发布的事件概率。独立校准不保证未来区域总体已校准，当前1km条件校准后的开发损失普遍上升应保留。

确认周保持未打开。先冻结模型标识和返回标识、thinking、temperature、max_tokens、提示、支持规则、银行、资料宇宙、截止/费用、主要比较、缺失处理、样本规则及停止条件。过程间方差与正例决定规模，不把1008调用或多个视图作为效力基础。核心确认不等待D/MM/16灾种全齐，也不以正收益为入口。

## 7. 持久修订与真正的自适应比较

对应 N4 / W08 / W12 / X02–X03。

当前新API试点仅为 `base_bound_override`。COPY_CURRENT、COPY_BASELINE和FOLLOW同分在该设置下可能接近结构性结果；不能据此消去持续修订对照。

先用CPU构造合法自然版本链并验证：首次基线、模型/程序同值override、后续基线变化、旧回答延迟、撤回、过期和cutoff。保留自动 `typed_auto_propose` 与显式模型动作的区别。

新闭环有两种合法研究条件：

- 固定已捕获信息路径/声明延迟的机制回放，用于分离数值规则和采纳协议。
- 各方法按自己的实际执行和合法预算运行，用于完整系统表现。

不得将旧LLM耗时简单改短，然后继续使用旧后续输入来冒充新的程序轨迹。需要扩大到persistent或显式action head时，使用新协议/新冻结并保留原auto-propose结果，不另起总体研究版本。

一般并发恢复继续是独立资格；先覆盖两个在途请求的故障交错。外部请求未知时只查询原回执，不免费重试。API别名不是精确权重哈希，返回model/system_fingerprint等元数据保留，但不夸大可重复性。

## 8. 温度的正确下一步

对应 N5 / W13 / X06。

当前24月192条轨迹是连续共同版本与COPY/hold的程序控制，查询数和模型数均为0；这一阶段已经完成。现在有两条分级出口：

### 8.1 F-only模型验证

在完整免费站点集合、相同未来日/三日目标、相同结果与截止下比较原始成员概率、COPY/FOLLOW和模型预测。若没有合法附加资料，先只声明F能力，不宣称主动取证增量。

### 8.2 有附加资料的C1机制

先登记真正不在共同集合中的、截止前可获得的站点历史、其他产品或质量/环境证据，绑定原生时间与单位；不通过拆分免费集合成员或已提供完整产品制造付费查询价值。不同来源是否已被专业预报使用保留已知/未知身份，不断言统计独立。

保持：原生00–24UTC日界、day0排除、六小时区间极值而非瞬时样本极值、同一成员跨三日、跨起报成员身份不随意配对、缺失结果不当负例。target日期受已声明参考期约束，11,644与旧11,680的范围变化应自动列差异，不把未纳入的2019目标默默视为结算失败消失。

高温日、低温日、三日阈值是明确候选，不直接等于所有地区的官方热浪或霜冻损害。729个日期和重叠三日窗仍然相关。

## 9. 平行扩展，不阻塞主结果

- H07：MRMS实际累计端点、连续时间、网格、负码/质量与匹配预报通过后再进入原生MM/工具对照。VIL不当雨率，重叠累计不假装瞬时场。
- H08：HEFS的QINE断面、调蓄、成员、瞬时/平均语义核准前继续只用版本E。免费共同预报已能支持的命题不重新收费。
- X09：保留单/多目标同完整上下文；输出每请求相同上限与每目标组相同总预算分开。已消耗或未提交的旧启动器不重开。
- D：现有固定F准备与条件回放保留；下一步才是SessionCoordinator内D/取证/计算反馈，研究情景损失不能叫真实减灾。
- 前瞻：仅来源采集不是模型预报；新预测冻结和提交要另行授权，不等待前瞻才能推进历史核心。
- H01–H16范围保留，以原登记source ID增补E/F/MM/D/确认资格，不复制新的互相矛盾总表。

## 10. API账本与复现最低要求

E01的62项未知与原始采集失败永久保留。当前 `ApiBudget` 将unknown作为终态，后续对账工具应采用追加更正记录，绑定原请求、原响应、usage与原费率；不修改原失败为模型成功，不新发HTTP。缺提供商账单时只能给保存费率的估计，未知不清零。

E02是完整新批次，不能称对E01失败位置的无成本修复。模型能力比较使用一致完成范围，并同时披露前期故障。

发布一个真正可搬迁的最小切片：一条完整72机会会话的公共资料/私有结果隔离包、银行、冻结源码、原调用/状态/回执、journal、评分以及明确缺失清单。原始文件许可不允许打包时提供有界重建路径。验证脚本默认断网、禁止模型调用、不依赖原服务器绝对路径。

目前审查ZIP访问失败并且其自身声明不含全部F日志，因此本次外部审查不声称完整复现616测试或所有会话。

## 11. 12个工作包及阶段出口

详细依赖见 `CODEX_WORK_ITEMS.json`。优先顺序：

1. **CPU立即做**：状态同步、校准来源审计、现有E管线归因、全方法报告、原费用对账。
2. **CPU/有限数据并行**：过程资格、温度新证据预检、持久修订/有限并发资格、C2真实图复放、H07/H08语义。
3. **新冻结后模型**：有区分力的E聚合管线、同预测器selector、多目标和温度；不得简单重复笛卡尔积。
4. **确认与交付**：独立过程、分级发布；允许零/负收益，不将D/MM/全16类变成核心的额外前置。

每包必须返回：实际代码改动、实际执行命令、通过/失败/跳过、原始与派生结果关系、资源与费用、文件哈希、剩余阻塞。计划完成数不等于研究结论数。

## 12. 交给 Codex 的执行摘要

你正在已有 v9 上继续工作。先同步本文件与真实工作区，不重置、不覆盖旧捕获，不重开E01/E02/F普通/F Denver/温度旧启动器。先离线复验校准切换与无TAF内容失活，给真实轨迹增加频率单元/校准器来源统计；把模型逐槽+程序汇总作为独立管线而非修复旧分数；导出全部强对照。维护已完成的区域银行和完整温度程序流，补真实附加证据、过程分组和协议资格。普通日历与结果选择的Denver分开。未有当前有效的新批次授权时，只执行安全CPU核查与计划，不启动API/GPU/批量下载/确认周。所有收益由冻结实验决定，不要求模型改概率或胜过基线。

## 13. 核查来源

本文所有仓库事实固定在 `6f71c8799ff69439a18f645e63b8c966ca21eec4`，关键路径如下：

- `LATEST_PROGRESS_20260914_CN.md`
- `publication/v9_followup_20260914/README_CN.md`
- `plans/v9_followup_execution_20260914_01/scripts/{evidence_diagnostic,fit_regional_baselines,build_process_manifest,run_api_pilot,run_temperature_fullcalendar,analyze_api_followup,analyze_e_error_mechanisms}.py`
- `plans/v9_followup_execution_20260914_01/reports/regional_baselines_01/SUMMARY.json`
- `plans/v9_followup_execution_20260914_01/reports/e_error_mechanisms_01/{REPORT_CN.md,VALIDATION.json}`
- `plans/v9_followup_execution_20260914_01/api_evidence_02/{policy/1079e059c870ec9994df3f67.json,captures/deepseek-v4-pro/1079e059c870ec9994df3f67/RESPONSE.json}`
- `disastertrace-starter/src/disastertrace/monitoring_v1/{calibration,regional_calibration,evidence,support,api_capture}.py`
- `disastertrace-starter/src/disastertrace/monitoring_fixed_v1/outcomes.py`
- `plans/v9_followup_roadmap_20260914_01/RESEARCH_ROADMAP_CN.md`

本次没有重新进行全面文献查新；保留原主张，不据此担保全球优先权。该计划中新的控制实验与排序为审查建议，不能计入当前已完成内容。
