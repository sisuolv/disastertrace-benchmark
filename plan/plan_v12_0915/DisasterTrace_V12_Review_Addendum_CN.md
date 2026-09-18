# DisasterTrace v12 计划复核补充：阶段 A 执行前修订

## 0. 身份与适用范围

- 审阅的远端提交：808ca1912c7065ff6c774004626867676118a9cf。
- 该提交发布日期：2026-09-15 14:02:13 UTC；生产实现基准为父提交 889620a4fc4ee6ad70757dd3e832a40c7509126a。
- v12 记录的本地状态观察约为 2026-09-15 13:28—13:29 UTC，不代表服务器实时状态。
- 本文件是计划评审建议，不是用户执行授权。execution_authorized=false。不得凭本文件启动任务。
- 审阅方式：读取 v12 计划、机器任务表、状态回执并静态追踪关键生产源码；没有重新运行 750 项测试，没有执行原整周实验、真实分支或新模型调用。

## 1. 评审结论

保留 C1/C2/C3 和 A→B→C→D。阶段 A 适合有限推进，但分支节点应先通过父状态可恢复性和显式动作入口检查。收口报告、来源普查和最小校验可以独立推进，不等待温度/API/MM。

不要将以下状态等同：代码可用、真实数据链可用、原回执通过、当前修订通过、机制实验有可辨别性、独立科学确认通过。

## 2. 应保留的 v12 设计

1. 原 840 条整周轨迹、冻结输入、失败、Y、费用、预测与原审计保持不变；修订 E 和配对报告写新目录。
2. 从完整已登记原生索引及其来源回执开始，先过滤可见性与权限，再按版本规则确定当前产品，最后判断覆盖。
3. 共同 TAF 处理与邻站 METAR 获取分开。旧 144 个 TAF 题保持旧身份，其中 72 个是 coverage，72 个是 revision。
4. 三个 2024-02 原生月样例已经构建完成，不再作为“首次构建”重跑；71/72 是地区月目录完成情况，不是年度原文/拟合完成率。
5. 程序工程分支不等待全年新后端；新后端科学比较另注册。
6. 温度、API、MM、独立确认分别放行。没有正收益不是工程失败，程序对照不得人为削弱。

## 3. 阶段 A 必须补齐的执行规格

### 3.1 新增 W11.parent_materialization：先证明父状态确实存在或可重建

源码依据：
- plans/v11_execution_20260915_01/prepare_c2.py::main 标注 checkpoint_materialized=false。
- plans/v11_execution_20260915_01/fullweek.py::run_arm 使用 finish 后导出终态 journal，没有在该路径中持久化 noon 中间 checkpoint。
- monitoring_v1/formal_session.py::restore 要求原目录/正式标记，拒绝已存在 STOP 的目录；finish 封存 completed。

实施规则：
- 优先读取真实持久化 checkpoint，记录原运行身份、前缀日志和来源哈希。
- 若缺中间 checkpoint，只允许另外登记最多 6 个父状态的确定性前缀重建；使用原冻结源码、配置、动作记录和已捕获响应，不访问网络、不重新生成模型答案。
- 明确区分 originally_captured 与 reconstructed_from_frozen_prefix。前缀复算不计新增天气样本、来源下载或模型实验。
- 将“原 840 条实验不重跑”与“最多 6 条前缀工程重建”分别登记，不用前者含糊禁止或默许后者。
- 不删除原 STOP，不改旧 CONTRACT，不篡改路径/hash 伪装原会话恢复。
- 建立新的分支运行身份和可验证的父子引用；保留旧输入、银行、来源情景、失败策略和已消费预算。
- 如记录不足以恢复 cache、授权、pending、预算、时钟和覆盖状态，标 parent_not_reconstructable；不凭最终概率反推内部状态，不另挑有利父状态替换。

交付：PARENT_CHECKPOINT_INVENTORY.json、PARENT_MATERIALIZATION_REPORT.json。

验收：对每个可重建父状态，以原策略进行无干预续行，重建相同的科学状态、可见输入、预算事件和预测；运行 UUID/新物理文件路径等管理字段单列，不通过粗略忽略科学字段实现“等价”。

计数单列：最多 6 个父状态重建、最多 6 条原策略无干预续行、最多 24 条干预分支。它们不能相加成独立天气过程。

### 3.2 显式实现有限查询计划，不能仅修改 query_limit_per_tick

源码依据：session_checkpoint.py 的 CONTROLS 未提供精确 query_id 序列；policies.py 的程序路径按 coverage、目标顺序和 stable_rank 等规则选取。

新增最小受控动作接口，冻结：
- fork 时刻的候选集合、公开排序、可见来源范围；
- query_id、source/version、payer/授权、计划顺序；
- 首选项、第二项和 all 的确切含义；
- 当前不可负担、已缓存、不可用、迟到、别名与失败状态。

不能通过删除 DATA.json 的查询目录来强迫选取某个 query，因为这会改变冻结环境；不能将未注册 selector 名称的默认行为当成指定动作实现。

必须核对 planned_query_order 与 executed_query_order，区分计划中的 all 与由于预算/时限仅执行了前缀。all 只指 fork 时冻结集合，不包含未来尚未可见的报告。

如果 fork 时无 pending，优先在该静止边界分支。若有 pending，先按原身份结算一次，所有分支继承相同过渡，不把结果回填到较早时刻。

交付：RESIDUAL_QUERY_PLAN_CONTRACT.json、PLANNED_EXECUTED_ACTIONS.json。

### 3.3 两类 C2 的执行深度必须分别标记

A 的四个查询计划主要验证 METAR 获取链，不自动验证 TAF 处理错误链。

当前 NativeFeaturePredictor 会从原始 TAF 和已授权资产重新构造特征；feature_vector 会校验原文投影一致性。只修改 E 答案不会改变 F，而直接篡改原始 projection 可能被拒绝。

因此：
- TAF 轨本批先完成来源/字段依赖和实际消费入口审计；没有生产路径干预回执时标 wiring_audited_not_intervened。
- METAR 轨通过真实分支验证查询完成、授权、字段、特征、概率、采用及未来损失。
- 后续处理实验采用“不可变原始资产 + 明确来源的解析/提取结果 + 固定预测器”的受控入口；特权修复只能由评估器执行并单列，不能冒充可部署工具。

E 状态 schema 分开：
- METAR 事实：supported/refuted/undetermined/inconsistent。
- TAF 产品题：resolved/unknown/unsupported/conflict，另有 coverage=full/partial/none。
- 原生索引状态、缺 frame、未执行状态另列。

### 3.4 等时不变性与真实等待效果分表

查询耗时可能导致共同 TAF 更新、override 失效、资料 age 改变或错过预测槽位。它们不等同于邻站观测数值本身的作用。

每条路径至少记录：
parent_clock、fork_clock、dispatch_at、completion_at、forecast_slot、baseline_version、baseline_binding、source_version、raw_field_hash、feature_hash、candidate_probability、adoption/rejection_reason、active_probability、remaining_budget、selected_target_loss、remaining_session_loss。

主表保留实际声明时延下的有限计划总效果。字段/时延隔离使用相同逻辑时间与共同预报版本的诊断回放，明确不冒充实际部署。新增对照应在 24 条分支上限内安排或留到下一批，不能自动扩预算。

no_further_paid_query 不是原策略无干预续行。前者是一项处理，后者专门检验恢复正确性。

### 3.5 统一自然来源普查与有限集合保证

NATIVE_PRODUCT_INDEX 不是可直接给所有策略读取的隐藏答案表。原生索引需和 SOURCES、请求/HTTP 回执、原文字节、版本、声明的可用时间进行连接。

划分 public_catalog 与 evaluator_catalog；CNL、冲突、解码失败、未来 Y 等信息若不是当时公开可见元数据，不得通过排序、文件名或字段提前暴露。

完整仅指已登记、有来源绑定的档案宇宙，不宣称覆盖现实中全部可能来源或已证明历史 first-seen。

普查保留普通 full；异常按 product/version、目标窗口、父状态及天气过程分别计数。8 conflict + 4 unparsed 不能当 12 个独立灾害，也不能用来直接选择有利确认日。

### 3.6 将机器验收依赖改成分轨

WORK_PACKAGES.json 中 W05.acceptance 硬依赖 W07.closeout 和分支，与“外部审计未完成时独立部分仍可交付”的文字需要统一。

建议：
- W05.local_acceptance 验收本批实际修改过的代码、来源普查和已有分支结果；外部未完成节点标 blocked_external，不伪装通过。
- W07.closeout 等原完整审计，通过后生成整周派生分析。
- W05.full_acceptance 在全部必需轨道有完整回执后给完整批次结论。

为分支显式增加 external_gate：parent_day_terminal_and_verified；全批授权、各任务授权与资源范围均须写入新批准记录，不能只依据 dependencies satisfied 自动启动 B/C/D。

## 4. 原有修复的精确影响边界

### E 汇总

fullweek.py::audit 使用 entailed/refuted，而 evidence.py::exists_report_support 返回 supported/refuted 等。新统计应计 supported+refuted，并区分缺 frame/未执行；不跨 schema 全仓库替换字符串。

保持旧 F、Y、roster、mask、loss 和原文件 hash；新 E 统计附受影响机会 ID。

### 年度摘要

annual_catalogs.py::execute 在 sample_ok=false 时得到 sample+sample。当前三个样例通过，因此不能用该缺陷解释真实 71/72，也不能推断已经重复发送 HTTP。

回归验证唯一 unit，逻辑月/请求次数/失败/未尝试分开。阶段 A 仅生成精确缺片与原文去重清单，不发送新请求。

### 银行准入

validate_feature_bank 在 calibrated=true 时 previous=-1.0 可放行负 value，且缺少跨块域顺序约束。修入口的数值和域检查；保留合法间隙与原外推语义，不静默重排或裁剪。

扫描真实使用 calibrated 的银行。当前 raw 整周不能仅凭此缺陷判无效；报告 unchanged/affected/not_evaluated。

## 5. 阶段 B/C/D 的补充门槛

### B：角色与暴露账本

保留 2023 内部拟合/选择、2024 校准、已读 2025 开发。增加 EXPOSURE_LEDGER，区分仅检查来源质量、读取标签、查看损失、使用损失选择特征/模型。质量检查不自动污染校准，但已经用于方法选择的数据不能继续声称独立校准。

按目标窗、回看窗、原生来源/修订、派生资产和会话记忆执行 purge；不要把所有共享的 schema/静态站点元数据都当成结果泄漏连接。

去重清单分别记录唯一原始身份、已有已验证缓存、缺字节对象、同 ID 异字节冲突、跨月引用。未取回字节不能凭空做内容哈希去重。

### C：真实选择空间与单一模型角色

当前 feature_vector 每目标最多两个补证槽位；先统计整个会话可选 query 数、实际受益目标数、剩余预算、重复资料和动作等价类。不能因为字段数少就否认全局资源竞争，也不能因为会话长就宣称复杂信息搜索已成立。

保持 12×24=288 的本地 selector 开发上限和兼容性最多 2 次。确认固定 forecast schedule 配置生效：生产代码已有忽略 forecast_handles、按公共 slots 预测的路径。模型角色、预测后端、原生提取和预算不同时变更。

C2 工程选择没有真实不同路径时，保留退化；如要拓展样本，另登记按公开源状态/元数据分层的机制批次，不替换当前冻结六个父状态。

### D：C2 主张也需要独立确认

当前确认草案主要针对 LLM 相对强程序的 Brier（两个阈值）。若论文主张重心提高到 C2，还应提前冻结对应的关键处理/取证干预及分析单位。

至少区分：恢复与字段传播的确定性等价；真实过程中的处理/取证效果；固定信息和时间后的剩余差异。确认时不根据显著性挑机制。

“未显著优于”不等于“没有价值”。只有预先设定有意义的等价/非劣界并获得足够精度，才作相应的无实质差异表述；否则报告效应与不确定性不足。

## 6. 阶段 A 最终交付与结论级别

1. 整周结果：原审计完整时交付全分母配对分析与 E 修订；否则列精确缺口。
2. C2 来源：完整已登记宇宙、三类状态 schema、字段依赖与公开信息隔离。
3. C2 分支：父状态来源、恢复等价、实际动作核对、字段到损失和有效路径数；只称工程验证。
4. 数据计划：KORD 精确缺片、去重原文与缓存差额、角色/暴露账本。
5. 代码验收：定向 red/green、当前真实 nodeid 去重测试数、冻结输入/旧结果不变校验、资源终态。

工程完成可以包含零收益、无传播、无有效替代路径的诚实结论；它不能被自动提升为 C2 科学确认或 B/C/D 执行授权。

## 7. 本次主要源码依据

所有路径均固定在上述提交：
- plans/v12_planning_20260915_01/OVERALL_PLAN_CN.md
- plans/v12_planning_20260915_01/NEXT_BATCH_EXECUTION_CN.md
- plans/v12_planning_20260915_01/WORK_PACKAGES.json
- plans/v12_planning_20260915_01/REVIEW_DECISIONS_CN.md
- plans/v12_planning_20260915_01/CURRENT_STATE_01.json
- plans/v11_execution_20260915_01/prepare_c2.py
- plans/v11_execution_20260915_01/fullweek.py
- plans/v11_execution_20260915_01/annual_catalogs.py
- plans/v8_measurement_execution_20260913_01/scripts/build_native_v2.py
- disastertrace-starter/src/disastertrace/monitoring_v1/formal_session.py
- disastertrace-starter/src/disastertrace/monitoring_v1/session_checkpoint.py
- disastertrace-starter/src/disastertrace/monitoring_v1/policies.py
- disastertrace-starter/src/disastertrace/monitoring_v1/evidence.py
- disastertrace-starter/src/disastertrace/monitoring_v1/native_feature_forecast.py
- disastertrace-starter/src/disastertrace/monitoring_fixed_v1/native_feature.py
- disastertrace-starter/src/disastertrace/monitoring_fixed_v1/taf_tasks.py

该索引是本次静态复核依据，不是所有文件已经通过新增运行验收的声明。
