# 交给 Codex 的后续实施计划：在 v10 实际进展上继续

审阅基准：`1fd6821fef15b26898a57c74d4715714f33ea779`。

本计划不是重新设计 DisasterTrace。保留 C1/C2/C3、E/F/D/MM、六组16类、X00—X09以及当前执行计划P0—P3；旧N1—N5/W任务用于追踪来源。代码修改默认发生在下一次获准的新工作范围，本请求本身仅授权本地审阅与文件规划。

## 一、现在最值得回答的问题

**同一个未来目标，在强共同信息后端上，额外资料究竟能改善多少；在实际截止和共享资源下，又能保留多少这种改善？**

按三层回答，不要求LLM必须获胜：

- 固定证据，比较原生程序、模型提取和预测后端，解释“能读懂”与“能利用”的差别。
- 固定后端，比较空证据、完整合法证据、预算内强程序和模型选择，解释“有用资料”与“取得有用资料”的差别。
- 固定候选，再看版本失效、重发、门控和截止，解释“好候选”与“及时生效”的差别。

既有四季结果已经显示：仅增强共同后端可以改善很多；读全补证还可能有额外作用；但首日预算总改善并不代表含事件块改善。因此，不能将所有差值包装成主动智能体贡献。

## 二、已有成果不得重新安排为从零实现

正式会话、measurement.v3、不可变API账本、原目录串行恢复、COPY/KEEP/两协议、E02程序汇总、匹配失败/缺失的组件对照、三种数值后端、四季下载、216预算轨迹、温度27B/235B回答和EMOS/ECC都已有实现/结果。需要补的是边界、强度、完整日历和独立性，不是另一套引擎。

本次两类红项是新局部输入风险。当前局部测试31通过/4失败不能代替或否定仓库720项；任何旧结果影响必须以实际输入和代码调用路径审计给出。

## 三、第一批运行范围

先执行 **P0.scope → P0.boundaries、P0.contract、P0.replay**。与此同时可做P1.archive的现有资料清单、P2.fullcalendar的新CPU注册草案和T1.temperature的只读稳定性设计。不得因等待下载或API而停止无依赖的代码与分析。

默认：已有本地文件、现有CPU与已安装依赖；不自动新增付费API、GPU、ACP云作业、大下载、持续采集、push或开启确认。先读真实cgroup/内存/磁盘上限再决定CPU并行，不能只按os.cpu_count()预设机器拥有64核。新资源授权必须绑定新批次、总量和停止规则，旧已消费launcher不重开。

首批必须交付实际diff、生产入口反例和绿色修复、旧结果影响表、阶段成本报告及至少一个可复算数据切片（材料齐备时），不能只再输出一份计划。

## 四、任务清单

下面任务的“代码入口”是已存在路径或已读入口；建议新增测试/输出名会标明。`WORK_PACKAGES.json`为同一清单的机器版本。

### P0.scope · 固定审阅增量与现有资格

依赖：无。执行范围：`local_cpu_existing_data`。

代码/资料入口：

- `LATEST_PROGRESS_V10_CN.md`
- `plans/v10_execution_20260914_01/FINAL_RESULT.json`
- `plans/v10_execution_20260914_01/NEXT_PHASE_PLAN_CN.md`

实施：

1. 读取实际HEAD及工作区改动；与审阅提交比较，后来的修复优先复用。
2. 保留C1/C2/C3、E/F/D/MM、X00—X09和当前P0—P3；建立到旧N/W任务的映射而不重置完成状态。
3. 记录原始银行、提示、冻结执行源码、已暴露日期和未开启确认资料；旧启动器与运行权限不继承。

验收：

- 没有reset/clean/覆盖未提交改动；HEAD差异可追踪。
- 每项状态分别列已实现、实际运行、独立复算和科学确认。
- 2812回答、720测试、12096机会等各自有单位，不相互折算。
- 不把旧v9校准、COPY或温度程序流重新计为新成果。

交付：`REVIEW_BASELINE.json`、`PROGRESS_DELTA_CN.md`、`EXPOSURE_LEDGER_DELTA.json`。

### P0.boundaries · 修复已复现的输入边界并核查真实影响

依赖：P0.scope。执行范围：`local_cpu_existing_data`。

代码/资料入口：

- `disastertrace-starter/src/disastertrace/monitoring_v1/feature_tasks.py`
- `disastertrace-starter/src/disastertrace/monitoring_v1/temperature_postprocess.py`
- `disastertrace-starter/src/disastertrace/monitoring_v1/native_feature_forecast.py`
- `disastertrace-starter/src/disastertrace/monitoring_v1/feature_scoring.py`

实施：

1. 将本包四个红测试转为当前包的直接导入测试，再检查实际数据构建和评分入口是否另有保护。
2. 统一温度目标和产品校验：UTC整日、正窗口、有限阈值、唯一日期、同成员完整性、对应变量/时长及截止。生产代码只维护一个共享规则；独立审计保留另一实现。
3. 能见度模型声明只允许有限非负lower；upper允许有限非负数或+inf，且区间非空。不得将+inf lower裁剪成正常特征。
4. 只读扫描真实冻结目标和原模型回答；输出affected/unchanged/not_evaluated。修复后的重新评分与新推理分别计数。

验收：

- 中午到次日中午、重复日期、非有限阈值均明确拒绝。
- [+inf,+inf]模型声明拒绝；合法P/M删失及9999等原合同不变。
- 日/三日合法概率逐项保持；同成员0.5而非边际乘积0.125的正向例通过。
- 原无效回答、费用和输入不被修补成有效原模型成绩。
- 生产入口若已拒绝某反例，要明确降低其实际影响，而不是扩大缺陷结论。

交付：`BOUNDARY_RED_GREEN.json`、`HISTORICAL_IMPACT.json`、`tests/test_temperature_contract_shared.py (suggested)`、`tests/test_visibility_claim_domain.py (suggested)`。

### P0.contract · 把描述性数据卡绑定到新的实验

依赖：P0.scope。执行范围：`local_cpu_existing_data`。

代码/资料入口：

- `plans/v10_execution_20260914_01/contracts/H15_REPORT_LABEL_DATA_CARD.json`
- `disastertrace-starter/src/disastertrace/monitoring_v1/formal_session.py`
- `disastertrace-starter/src/disastertrace/monitoring_v1/feature_tasks.py`
- `disastertrace-starter/src/disastertrace/monitoring_fixed_v1/outcome_policies.py`

实施：

1. 在新注册中绑定报告语义、解析器、提示、字段政策、比较精度和失败规则的不可变摘要。
2. 主报文与remarks分开；报告标签的单点、明确删失与物理测量范围不可混用。
3. 明确表示是否含原生结构化字段、模型提取还是评估器修复；工具处理若提供给策略则同权限、同计费。
4. 为温度和新来源沿用可得性等级：真实first_seen、文档证明历史发行、声明归档情景，不能互相晋级。

验收：

- 修改提示或标签政策触发新合同版本；不能回写旧冻结。
- 同一原生样例重建相同输入/标签，六个通用样例不计天气样本。
- 错误原字段不会因新提示成为旧回答正确。
- 结果标签与评估器修复信息不进入模型视图。
- H15报告标签、未来物理状态、产品发布事件在名称和评分中区分。

交付：`RUN_TASK_CONTRACT.json`、`CONTRACT_BINDING_TESTS.json`、`PROMPT_AND_PARSER_MANIFEST.json`。

### P0.replay · 先测量并消除同一次评分的重复重放

依赖：P0.scope。执行范围：`local_cpu_existing_data`。

代码/资料入口：

- `disastertrace-starter/src/disastertrace/monitoring_v1/formal_session.py`
- `disastertrace-starter/src/disastertrace/monitoring_fixed_v1/admission.py`
- `plans/v10_execution_20260914_01/scripts/audit_selector_timing.py`

实施：

1. 对解析、原始哈希读取、from_journal、provider验证、评分、输出和等待分别记录墙钟/CPU/内存/读取字节。
2. score_formal一次调用只重放每个不同arm一次，再将只读、已验证状态交给共同评分核心；保留全部正式资格和交易重放验证。
3. 禁用仅按路径的跨运行缓存。复用对象需绑定原始字节/合同/语义/机会/结果身份，并防止评分过程修改。
4. 用两个有范围的capsule验证原旧格式重放和当前正式入口，实际下载齐备后才声称搬迁通过。

验收：

- 九arm正常路径从源码可见的19次重复加载降到预登记的每arm一次，实际计数验证。
- 逐机会概率、原分数、结果掩膜、准入状态和合同摘要与未优化原路径一致。
- 同路径内容改动、截断/未提交尾、协议不符、错误提供方、未封存机会仍拒绝。
- 记录真实前后耗时和峰值内存；没有测量不填写加速倍数。
- 不把197秒generate之外的时间全归因CPU/AFS，不声称GPU利用率。

交付：`PROFILE_BASELINE.json`、`REPLAY_EQUIVALENCE.json`、`SCORER_PERFORMANCE.json`、`CAPSULE_SCOPE_REPLAY.json`。

### P1.archive · 建立完整季节的拟合与校准资料

依赖：P0.scope、P0.contract。执行范围：`metadata_cpu_first; external_download_only_with_new_bounded_authorization`。

代码/资料入口：

- `plans/v10_execution_20260914_01/NEXT_PHASE_PLAN_CN.md`
- `disastertrace-starter/src/disastertrace/monitoring_v1/process_split.py`
- `plans/v10_execution_20260914_01/scripts/complete_seasonal_data.py`
- `plans/v10_execution_20260914_01/scripts/audit_full_dependencies.py`

实施：

1. 将当前计划的2023拟合/2024校准作为候选角色；先核已有缓存、历史格式和全季节覆盖，再冻结实际获取清单。
2. 先按月/站/产品分块做有限质量与兼容性预检；资源允许后只补缺块、单提供方限流并保留失败。不得默认两年全量已具备。
3. 所有输入回看、原生版本、派生父资产、目标结果与会话历史纳入跨角色依赖；边界清除长度按最大支持推导。
4. 2025四季数据仍为开发；当前确认周不读取。

验收：

- 实际清单逐月给成功/缺失/解析失败、正负目标及可得性等级。
- 训练和校准都覆盖季节，不把季节与数据角色等同。
- 角色间原生依赖冲突明确拒绝或清除，源镜像不计独立资料。
- 新下载有请求/字节/磁盘上限和停止条件；旧429/503及成功缓存保留。
- 无法获取某月不填造数据，也不因模型输赢换月份。

交付：`HISTORICAL_ACQUISITION_PLAN.json`、`SOURCE_COVERAGE_BY_MONTH.json`、`ROLE_AND_DEPENDENCY_MANIFEST.json`。

### P1.backend · 完整季节同信息强后端与稳定性

依赖：P0.boundaries、P0.contract、P1.archive。执行范围：`local_cpu_existing_data`。

代码/资料入口：

- `disastertrace-starter/src/disastertrace/monitoring_v1/native_feature_forecast.py`
- `disastertrace-starter/src/disastertrace/monitoring_v1/regional_calibration_v2.py`
- `plans/v10_execution_20260914_01/scripts/fit_native_feature_bank.py`
- `plans/v10_execution_20260914_01/scripts/audit_native_feature_bank.py`

实施：

1. 保留冬季原银行和去年周期开发消融；新bank单独冻结，使用相同物理信息单元的common/mask-age/values。
2. 每个物理单元的多缺证视图权重和为1；部署缺证模式必须在训练/校准中有覆盖。原始概率和后校准分别保存。
3. 先比较少量预登记线性/收缩或季节条件候选；只用训练及内层校准决定参数，不反复在2025开发结果挑主方法后称确认。
4. 报告OOD特征、站点/季节/缺证模式、端点闭合信息压缩、校准先验总量与概率单调性。
5. 对no-TAF合法补证已有新后端支持，测试保护而非重复从零实现。

验收：

- 拟合均值/方差、特征选取、先验、正则都仅来自合法训练角色。
- common与values-no-evidence不是同一个模型，报告中不得据此给纯信息因果归因。
- 同values银行的无证据/mask/内容比较有共同目标和失败掩膜。
- 高温/低能见度稀有正例不删除、不因极端数值自动裁为错误标签；数值特征截断单列。
- CDF在同信息条件下保持p1000<=p5000；不同策略信息不同不强行联合投影。
- 退出不要求模型或新bank一定获胜。

交付：`BANK_MANIFEST.json`、`BASELINE_QUALIFICATION.json`、`BACKEND_BY_SEASON_AND_MASK.json`、`INFORMATION_CONTROL_TABLE.json`。

### P2.fullcalendar · 将预算控制从首日扩展至完整已有周

依赖：P0.boundaries、P0.contract。执行范围：`local_cpu_existing_data`。

代码/资料入口：

- `plans/v10_execution_20260914_01/seasonal_controls_01`
- `plans/v10_execution_20260914_01/reports/seasonal_budget_interpretation_01`
- `disastertrace-starter/src/disastertrace/monitoring_v1/forecast_schedule.py`
- `disastertrace-starter/src/disastertrace/monitoring_v1/formal_session.py`

实施：

1. 先使用已暴露四季完整周做开发分析；不用等待年度下载才进行此任务。新银行另立后续比较，不替换旧selector批次。
2. 首轮只运行FOLLOW、同values不补证、B11batch、B11coverage；round-robin先检查实际查询/状态是否等价，避免只为名称重复大矩阵。
3. 再按需要在全日历或预登记机制子集完成coverage的分配×授权四格。全程保持相同来源信用释放、日程、结果掩膜和两协议分表。
4. 明确每天重置还是整周持续会话；跨日缓存、预算、目标与未结束准备不得暗中丢弃。

验收：

- 完整周注册机会覆盖可核对，不借用其他集合的29/307正例数。
- 12区域周按4全局块及自然过程分层，不称12独立事件。
- 报告December等含事件块的help/harm与幅度，不能只突出平均改善。
- 缺失敏感性界与抽样不确定性不同字段、不同表头。
- 仅发生事件的子集指标标为条件诊断；完整日历主损失继续包含无事件时段。

交付：`FULL_WEEK_PROGRAM_REGISTRATION.json`、`FULL_WEEK_PAIRED_RESULTS.json`、`EVENT_AND_BACKGROUND_STRATA.json`、`QUERY_TRACE_EQUIVALENCE.json`。

### P2.confirm · 冻结自然过程分组和一次性确认

依赖：P0.contract、P1.backend、P2.fullcalendar。执行范围：`local_cpu_existing_data`。

代码/资料入口：

- `disastertrace-starter/src/disastertrace/monitoring_v1/process_split.py`
- `plans/v10_execution_20260914_01/scripts/audit_full_dependencies.py`
- `plans/v10_execution_20260914_01/NEXT_PHASE_PLAN_CN.md`

实施：

1. 按可核实天气过程/原生依赖和保守时空块分组，参数在开发时固定；日期块不是天然独立性证明。
2. 先明确主次阈值、模型/提示、工具、成本、采用、缺失和停止规则，再打开未暴露自然连续数据。
3. 保留Bay确认周，检查其角色及与已暴露资料关系；一个周不足以自动支持全年跨地区。
4. 样本量按开发过程间变异和预定区间精度确定；正过程不足报告不足，不按显著性追补有利日期。

验收：

- 实验未暴露与模型预训练未见过分开披露。
- 同天气过程的站点/提前量/阈值/profile放同组，不重复计算独立样本。
- ROC/AP在无正或无负时不强行填数；预警阈值仅开发期固定。
- 确认前冻结方法；开放后的失败/缺失/负结果不删除。
- 核心E/F确认不依赖D/MM/16类或更大模型；如最终方法来自P3则加入相应方法冻结依赖。

交付：`CONFIRMATION_PREREGISTRATION.json`、`PROCESS_SPLIT_AND_POWER_NOTE.md`、`UNOPENED_DATA_SCOPE.json`。

### P3.components · 固定证据的处理与预测利用比较

依赖：P0.boundaries、P0.contract、P1.backend。执行范围：`cpu_design_and_existing_response_analysis; model_calls_require_new_authorization`。

代码/资料入口：

- `disastertrace-starter/src/disastertrace/monitoring_v1/feature_tasks.py`
- `disastertrace-starter/src/disastertrace/monitoring_v1/feature_scoring.py`
- `disastertrace-starter/src/disastertrace/monitoring_v1/fixed_packet.py`
- `plans/v10_execution_20260914_01/scripts/prepare_feature_temperature_trial.py`

实施：

1. 复用已有values_validmask/values_missingmask等诊断，建立冻结证据×后端的小矩阵，不重写旧E02归约。
2. 每组比较只改变模型提取、原生程序提取、同源特征或直接预测中的一个因素。新清楚合同从一开始固定，不沿用错误后澄清当确认。
3. 程序替换模型某字段的离线敏感性单列特权诊断，不改原模型成绩、不声称可识别的精确因果百分比。
4. 核端点closure等字段是否进入预测特征；相同特征导致同输出是后端表示边界，不是证据天然无用。

验收：

- 无效回答和全分母保留，不仅在双方成功交集评分。
- 语法有效、字段正确、最终E正确和F改善分表。
- 当前值/基线精确相等、容差相等及最终生效分别记录。
- 模型没有变概率是合法行为；不通过强迫改动制造novelty。
- 需要新输入/提示时计新调用；复用旧回答仅限明确的离线诊断。

交付：`FROZEN_COMPONENT_MATRIX.json`、`EXTRACTION_TO_FORECAST_REPORT.md`、`COMPONENT_SENSITIVITY_DIAGNOSTIC.json`。

### P3.acquisition · 固定后端下的查询选择、处理成本与延迟

依赖：P1.backend、P2.fullcalendar。执行范围：`cpu_controls_first; bounded_model_sessions_require_new_authorization`。

代码/资料入口：

- `disastertrace-starter/src/disastertrace/monitoring_v1/policies.py`
- `disastertrace-starter/src/disastertrace/monitoring_v1/forecast_schedule.py`
- `disastertrace-starter/src/disastertrace/monitoring_v1/residual_reachability.py`
- `plans/v10_execution_20260914_01/scripts/prepare_selector_trial.py`

实施：

1. 固定新后端、同来源预算48及预测日程，先比较现成强程序，再限定一个已验证模型作为selector。
2. 分别呈现相同总资源、相同预测机会和相同查询计划的时延诊断；selector开销不免费。
3. 保留按槽受控预算轨，同时为真实服务成本轨允许批量、缓存、同资产重处理；首次下载和重复模型处理分账。
4. 事件触发/短计划仅作为有限候选：用公开基线变化、实际合法新证据和已知截止触发，不读取未来更新时间。
5. 残余E参照继续为有限串行联合路径；不作为未来F或D最优，不把E覆盖最大化强加为F奖励。

验收：

- 后端和信息不同的批次不得直接归因selector。
- 查询预算相同不写成总成本相同。
- 旧模型查询脚本的固定时延回放标为条件诊断，不冒充新便宜闭环。
- 所有方法工具、缓存与处理权限对等，原生Gold不进入策略。
- 如只在无事件块改善，结论必须相应收窄。

交付：`SELECTOR_FIXED_BACKEND_REGISTRATION.json`、`COST_AND_LATENCY_FRONTIER.json`、`RESIDUAL_REFERENCE_SCOPE.json`。

### P3.revision · 区分候选、采用规则与持续保留

依赖：P0.contract、P3.components。执行范围：`local_cpu_existing_data`。

代码/资料入口：

- `disastertrace-starter/src/disastertrace/monitoring_fixed_v1/admission.py`
- `disastertrace-starter/src/disastertrace/monitoring_fixed_v1/copy_controls.py`
- `disastertrace-starter/src/disastertrace/monitoring_v1/forecast_provenance.py`

实施：

1. 保留FOLLOW、COPY_CURRENT、COPY_BASELINE、KEEP的动作身份与有效期差别。
2. 同已捕获候选比较两协议/门控的离线变化；需要策略重新决策的情况另跑闭环。
3. 同值重发、旧值持有、基线更新、过时完成与最终截止生效分开记录。

验收：

- 自动回退或旧值保留的收益不全部归给模型生成能力。
- 不同协议不合并单一模型分数。
- 门控不能看到未来结果；事后最优采用只作诊断。
- 冻结候选重放不计新预测次数或独立天气样本。

交付：`REVISION_FUNNEL.json`、`PROTOCOL_PAIRED_RESULTS.json`、`GATE_SCOPE.md`。

### T1.temperature · 温度F-only稳定性与数据资格

依赖：P0.boundaries、P0.scope。执行范围：`local_cpu_existing_data`。

代码/资料入口：

- `disastertrace-starter/src/disastertrace/monitoring_v1/temperature_postprocess.py`
- `disastertrace-starter/src/disastertrace/monitoring_v1/feature_tasks.py`
- `plans/v10_execution_20260914_01/scripts/fit_temperature_postprocess.py`
- `plans/v10_execution_20260914_01/scripts/audit_temperature_evidence_gate.py`

实施：

1. 承认24月程序、128题27B/235B和EMOS/ECC均已有结果；不从头接流。
2. 按季节、提前量、事件持续期及过程检查hot-day后处理退化；拟合/内层校准/确认分开，2018已暴露。
3. 记录ECC秩重排、min/max修复次数及其对联合事件和边际的影响；修复后不笼统声称保留原copula或联合校准。
4. 同成员和同一起报身份贯穿三日；对缺日期/重复日期/成员错配/日边界给生产回归。
5. 729天DWD最终值仍主要为结果；0天严格历史补证资格不得改写。合法新来源核实后才追加C1，明确情景轨也只能按其假设报告。

验收：

- 5796fit、5720dev、128排除及共享目标依赖有完整分母。
- 高温日变差仍并列，不仅报告另外四种改善。
- 原始集合、EMOS、ECC、修复后路径等比较不混作同一处理。
- 新模型任务使用冻结的新合同和未暴露评测资料；不在128题反复调提示称泛化。
- 没有额外合法资料时F-only可独立发布，不阻塞核心，也不宣称温度C1。

交付：`TEMPERATURE_STABILITY_BY_PROCESS.json`、`ECC_REPAIR_IMPACT.json`、`TEMPERATURE_EVIDENCE_ADMISSION.json`。

### EXT.application · 有条件推进MM与准备反馈

依赖：P0.contract。执行范围：`design_and_existing_data_only; new_collection_or_model_runs_require_separate_authorization`。

代码/资料入口：

- `plans/v10_execution_20260914_01/OVERALL_PLAN_UPDATED_CN.md`
- `disastertrace-starter/src/disastertrace/monitoring_v1/preparation.py`
- `disastertrace-starter/src/disastertrace/monitoring_fixed_v1/decision_inputs.py`

实施：

1. MRMS精确累计区间与同目标预报/参考、HEFS物理量/成员/调控/断面资格分别推进；不同时铺开16条模型矩阵。
2. 多模态区分原图、同源专业产品、模型提取和评估器标签；原生图像进入模型不等于科学通过。
3. D先固定F做不同准备条件配对，再将准备状态接入查询/处理/预测同钟反馈。
4. 研究性准备成本与真实业务后果分开；没有使用方核准不宣称社会减灾收益。online仅有另行授权的预先提交/成熟结算才算模型前瞻。

验收：

- 新灾种逐项保持A0—A5及E/F/D/MM资格，不凭下载数量晋级。
- 预报更新不能退还已耗准备资源；pending模型不冻结现场准备。
- 准备偏好不进入固定证据预测器；自主取证改变证据后F可以改变。
- 未归档替代响应保留不可评估，不生成假资料补反事实。
- 不作为核心E/F确认的硬前置。

交付：`EXTENSION_ADMISSION_DELTA.json`、`DECISION_FEEDBACK_PROTOCOL.md`。

### DELIVERY.scope · 交付可执行增量与精确复算范围

依赖：P0.scope。执行范围：`local_cpu_existing_data`。

代码/资料入口：

- `plans/v10_execution_20260914_01/FINAL_RESULT.json`
- `publication/v10_execution_20260914/README_CN.md`

实施：

1. 每批输出改动、真实测试、数据/结果影响、原失败与阻塞。
2. 保留两个capsule边界；实跑前不要声称全部212结果或720测试已独立重建。
3. 调用成功、有效回答、兼容性失败、NOT_ATTEMPTED、未知费用分别列。
4. 旧启动器和原预算不续用；新收费/下载/云资源调用需要明确本批范围。

验收：

- 清单无凭据/临时签名URL/模型权重/字体。
- 测试通过数不累加重复复跑，样本数不按阈值/视图增殖。
- 文件链接只指向实际存在的文件；ZIP的每个清单条目可核验。
- 科学出口与工程完成分列，不以正收益才允许收尾。

交付：`BATCH_RESULT_CN.md`、`VALIDATION_SCOPE.json`、`ARTIFACT_MANIFEST.json`。

## 五、建议的小型实验矩阵

### A. 完整日历先做程序，不再只取首日

已有12区域周仍是开发集合。先用FOLLOW、同values不补证、B11batch、B11coverage四种方法，在完整连续窗口运行并保留两种协议分表。已知coverage与round-robin同分不证明它们所有路径等价，应先检查查询和状态再决定是否少跑重复臂。

完成矩阵不是最大化会话数量。四格分配/授权实验在下一步补齐，其目的在固定selector/predictor下检验两个因素，而不是与后端不同的模型结果直接比较。

每个表同时给全部注册、可结算、缺失、唯一目标、正/负目标、自然过程组及来源查询数。按日历块、天气过程、站点和lead分层；错误发生和未发生时的损失贡献都保留，但只在事件子集的条件平均不能代替自然总体损失。

### B. 组件对照：尽量一次只改一件事

| 对照 | 固定 | 改变 | 可解释的结果 |
|---|---|---|---|
| common vs强同信息后端 | 完整共同资料、目标、结果 | 后端及校准方法 | 共同信息利用，不是取证贡献 |
| values空/缺测模式/完整内容 | 同一values后端 | 合法额外输入 | 条件于该后端的信息响应 |
| 原生解码 vs模型提取 | 同原文、同后端 | 提取方法 | 真实字段错误与F损失联系 |
| 程序归约 vs模型最终E | 模型自己的槽位 | 已声明逻辑归约 | 输出一致性改善，不替换原模型成绩 |
| 同候选两协议 | 候选、原完成时点 | 采纳/有效期规则 | 协议保护与陈旧修订，不是新推理 |
| 不同selector | 固定后端、信息宇宙、预算 | 查询或处理策略 | 策略效果和成本，需进一步分开时延 |

多环节可能交互；以上不构成精确因果分解。原生修复字段、事后最佳动作和评估标签只在诊断路径，不能默默喂给普通策略。

### C. 后续模型批次

已有27B与235B足以进行有限对照，不以增加规模或购买更多API作为门槛。先选一个固定后端和一组预登记新过程，再选择一个模型角色：提取、直接预测或selector；不要在同批同时更换提示、后端、季节数据、预算和协议然后只报一个模型分数。

同每次输出上限不是同总资源。同源批处理、缓存及专业解析工具必须对所有方法可用。严格裸JSON与允许整段围栏属不同协议，旧格式失败保留；新协议从第一次调用前冻结。兼容性HTTP402、NOT_ATTEMPTED不计能力错误，已发送未知费用不能归零。

## 六、性能工作不能跳过科学核验

优化对象是重复计算，不是删掉验证。建议将已完整验证journal的不可变评分视图传递给共享评分函数，正式/历史入口各自负责资格，避免互相递归重放。同一次score调用的对象复用可以先实现；跨运行缓存必须另立强完整性方案，不在本轮仓促添加。

记录输入规模、arm数、事件数、读取字节、CPU/墙钟、峰值内存；先以小真实capsule保持逐字段相等，再扩到完整周。不要把未测阶段的耗时估算写成实测加速。既有两个capsule只重算其包含范围，不重新生成模型答案。

## 七、确认和发表出口

工程版可在原始结果与复算范围清楚时先交付。机制论文需至少一个稳定、可解释的发现，并在未用于选择方法的过程上验证。发现可以是正也可以是负，例如：同证据原生方法有用而模型不用；正确提取仍被失配后端抵消；某策略在无事件时改善却在含事件块伤害；额外处理虽提高候选却错过生效窗口。

不必等待完整16类、D、MM或真正在线才做核心确认，但不要借核心通过自动晋级这些支线。D的准备仿真损失是研究指标，缺少业务验证不能称真实减灾收益。温度没有合法额外证据时可以保持F-only并独立报告，DWD最终档案的0天严格补证资格必须保留。

## 八、收尾模板

每批BATCH_RESULT_CN.md回答：

1. 实际改了哪些函数/数据合同，依据哪个提交？
2. 实际执行哪些测试、真实数据或模型调用，多少失败/缺失/未尝试？
3. 哪些旧结果不变，哪些受影响，哪些还未检查？
4. 哪项实验排除了哪种解释，仍不能说明什么？
5. 后续已冻结的最小任务与具体阻塞是什么？

同时附原始日志、源码摘要、数据范围、费用/时间单位和复算命令。不要把新文档、文件数量、重复测试次数或总调用量当作科学进度。
