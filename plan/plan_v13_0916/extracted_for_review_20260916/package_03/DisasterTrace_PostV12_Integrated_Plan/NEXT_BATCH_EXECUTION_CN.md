# 下一批 R0：具体执行规格与验收

**当前状态：待复核。** 用户本轮请求整合计划，不等于批准实施、提交或启动云任务。以下所有输出路径均为建议；现有历史路径只读。

建议工作目录：`plans/post_v12_integrated_<fresh_run_id>/`。不能覆盖现有 `v12_execution_20260915_01` 冻结 source、结果或运行身份。新代码可位于经批准的当前开发模块或新的版本化运输模块；每次实际diff明确保护边界。

## 范围

| 资源/行为 | 默认上限 |
|---|---|
| 新天气来源 HTTP / 新API / 新被测模型请求 | 0 / 0 / 0 |
| GPU / 新拟合 / 确认载荷读取 | 0 / 0 / false |
| 新C2科学分支或重跑旧模型 | 0 |
| CPU | 已有本地；必要时最多一个16CPU/64GiB额外任务，需相应批准和配额检查 |
| 允许的诊断 | 读取已有报告与trace、局部合成故障、必要的旧捕获重算/同输入特征计算 |
| 发布 | 不自动push，不改可见性、不上传凭据或受限原文 |

new_source_HTTP与GitHub只读元数据访问分开；网络被禁环境下从本地可信清单核查并注明无法刷新，不能编造最新HEAD。

## R00 — 基线、状态与测试范围

输入：实际HEAD、工作区状态、适用AGENTS、v12总结/最终验证、source保护、call/run登记。解析指令不执行历史launcher。

输出：EXECUTION_BASELINE.json、PROTECTION_MANIFEST.json、CONSUMED_IDENTITIES.json、TEST_SCOPE_DIFF.json、CURRENT_STATE_CN.md。

验收：
- 新基线与已知1eba36d不同时逐文件/功能比较，已修复不重复做。
- published/development/source不同身份分别记录，保留用户dirty/index。
- 750/628按实际nodeid核对；未得到原XML时不宣称集合一致。
- 当前入口只记录已观察SHA，不要求包含自己的未来提交SHA；历史文件保留。
- 报告仓库读取、隔离执行和未取得真实平台状态的边界。

## R01 — C2派生完整性

定位：`plans/v12_execution_20260915_01/analyze_branches.py::main`；实际分支执行器和正式scorer只用于身份/算术核验，不因分析器问题重跑。

先构造基于生产入口的失败回归：缺1报告、缺全部报告、空trace、trace缺一个已执行call、重复opportunity、同opportunity多个合法call、alias引用缺失、错误trace/hash/score、合法无调用fallback、缺Y但有E。

具体修改：
- 使用注册父状态/规则/alias形成expected set，不以磁盘glob或报告已存在集合定义分母。
- report/trace/actions/score按真实hash和运行引用绑定；多call用call_id/执行身份管理，不以机会ID最后覆盖。
- 区分没有预测调用与预测调用的trace丢失；先对expected calls做外连接与差额报告，再做配对，不仅比较交集。
- 别名不重复算独立实验，但仍保留注册规则；整个U_parent完整保留。
- execution_complete、analysis_complete、formal_qualification、scientific_scope分别输出，不能用一个passed替代。

历史影响：原24个报告及36配对若全齐、F数值一致，写unchanged，缺失则not_evaluated/affected，不填零差异。新派生版本不覆盖原文本或JSON。

产物：C2_ANALYSIS_INTEGRITY.json、C2_HISTORICAL_IMPACT.json、C2_REVISED_REPORT_CN.md。

## R02 — 比较身份而非方法名称

定位：`analyze_stage_c.py::paired` 与实际config/正式报告；旧表达式只判断F_COMMON。

新比较记录由实际消费者推导：
```text
method_id; consumer_family; actual_bank_sha; baseline_mapping_sha;
feature_version; calibration_mode; source_contract_sha;
forecast_schedule_sha; adoption_contract_sha; resource_contract_sha
```

对于“是否同bank”，FOLLOW的适用消费者可能应标N/A/不同映射，不能false误解成同native bank。新metadata表达same_predictor和comparison_scope比只有bank_difference布尔更准确。旧invariant比较合同不篡改。

回归：FOLLOW vs LLM须为跨consumer；COMMON vs VALUES跨bank；VALUES的BASE/BATCH/COVERAGE/LLM同bank前提由hash验证。重命名方法不改变身份；相同名字不同bank不能误判。已配对数值Brier/敏感性界保持。

产物：METHOD_CONSUMER_MANIFEST.json、PAIR_PROVENANCE_IMPACT.json。

## R03 — 实际API全链恢复

定位：`siliconflow_worker.py::{deliver,transport,reconcile_capture}`、`monitoring_v1/production.py::ProductionSpoolBackend.resolve`，结合真实spool claim/ready与调用记账层。

建议状态至少区分REGISTERED、CLAIMED、PERMIT_ISSUED、DISPATCH_INTENT、CAPTURED、PUBLISHED、CONSUMABLE、NOT_SENT、UNKNOWN、RECONCILED。名称可沿用现有schema，不为命名再建框架；重要的是证据与消费者对应。

### 发送许可

实际最后本地许可需要验证call/request/payload/execution、作用域deadline、STOP、一次性claim与permit。模拟历史clock与真实wall期限分别记录。许可后进程被暂停无法保证未来绝不迟到，合同限定可证明的本地线性化点；源查询/预测采用再按实际时间评分。

共享文件系统故障不得由单机锁测试推断。并发有界，重复worker不能再次HTTP；不确定intent保持unknown。持久化与发送之间崩溃不允许“检测不到capture就免费重发”。

### 捕获

在脱敏和解码前记录captured_body_sha256、captured_bytes、capture_limit_bytes、truncated、完整EOF证据。stored_redacted_sha256与原字节分开。原body哈希只覆盖前缀时不得称完整wire body。JSON/UTF8错误、模型不匹配、usage错类型和超上限显式失败。

### 恢复与消费

恢复以原capture和绑定intent/request为输入，零HTTP，不覆盖旧failure。新增不可变resolution，生产resolve验证该resolution确实绑定原失败和新response后再接受。response存在但failure仍无有效resolution时保持拒绝。

晚恢复允许费用/证据审计，不允许把候选回填旧已封存时刻；不能重新打开STOP parent。完整恢复测试必须从生产消费者入口断言，不只断言api_capture/response文件存在。

### 最小故障矩阵

入口后跨deadline；claim期间STOP；许可前/后STOP；intent后崩溃；HTTP后捕获前中断；capture后worker/response写失败；旧failure+正确resolution；resolution错误hash；截断后脱敏缩短；bodyhash不匹配；双worker；响应迟到；费用未知不释放。

扫描原288及两个compat时，只使用原回执可支持的事实。缺最终许可时间证据不能直接宣称发生迟发或全部准时，标无法证明。新schema用新身份，旧schema只读兼容。

产物：API_DISPATCH_QUALIFICATION.json、CAPTURE_INTEGRITY.json、RECOVERY_CONSUMER_PROOF.json、API_HISTORICAL_IMPACT.json。

## R04 — Query-only v2离线接口

选择继承仓库两键输出：
```json
{"query_order":["q0","q2"],"forecast_handles":[]}
```

所有句柄动态枚举来自当次合法目录；第二键固定[]。使用provider支持的schema子集，客户端仍独立检查完整合同。缺第二键在此v2中仍是格式错误；若未来决定删键另立版本，不兼容地悄悄接受旧格式。

minItems=0，最大排序长度按合法候选总数，不按当前资金限制；执行可按已注册规则消费可行前缀。允许none/all，不强制subset/reordering。schema不含参考答案、未来效用、隐藏未读字段。

测试空/单项/全选、重复、未知、额外字段、JSON外文字、围栏（接受与否在v2先冻结）、拒答、截断、超长、无候选、无剩余预算、正常KEEP。对不同合法forecast_handles的旧接口诊断不应用来改变固定Fslots；v2则严格只接受[]。

新prompt和response_format都会变时，结果只叫“接口v2整体比较”，不声称schema单因素效果。旧217失败不可别名修复。

产物：QUERY_ONLY_V2_CONTRACT.json、SELECTOR_V2_OFFLINE_MATRIX.json、REAL_COMPAT_PROPOSAL.json（执行=false，最多24调用提案）。

## R05 — 版本化新获取语义

定位：`monitoring_v1/residual_query_plan.py::freeze_residual_plan`及实际plan消费者。

保留v1原规则；v2明确all_related_inventory与remaining_new集合，first_new/second_new/all_new只面向后者。每项可用性按(payer,scope,qid,receipt_state,cache_entitlement)而非裸qid判断。shared已买复用，private另一owner购买不自动赋权，pending不重复发，proved-not-sent是否可重新登记由新scope规定。

红绿例：首项已缓存、已申请未知、另一目标私有cache、会话共享cache、second不存在、不可用、迟到、预算耗尽、原父修改、alias。改变候选筛选是新行为，旧24分支按v1不变。

产物：RESIDUAL_PLAN_V2_TESTS.json、RESIDUAL_V1_IMPACT.json、NEW_ACTION_SEMANTICS.json。

## R06/R07 — 时点与选择空间诊断

只用已登记开发日历、已有响应、trace和bank；缺数据不下载。阶段A不偷跑新的科学分支。需要运行同输入数值转换的范围在诊断manifest记清。

时点对照先确定旧时刻就合法的信息交集，避免把更晚产品回填旧时刻；固定信息的age效果、晚时刻新增合法信息、实际整个pipeline分别报。角色边界保持2024 Jan–Nov，排除Dec，不因重新整理计划恢复全2024。

动作普查区分metadata差异、实际字段差异、feature差异、概率/采用差异和资源竞争；hindsight Y评估只在评估侧，不变成selector输入或父状态筛选规则。none/all最优、无效预算约束都可报告为结果。

产物：CLOCK_INFORMATION_SUPPORT_AUDIT.json、ACTION_SPACE_CENSUS.json、ROLE_AND_EXPOSURE_LEDGER.json、NEXT_BRANCH_REGISTRATION_PROPOSAL.json。

## R08 — 验收、停止与部分完成

依次完成定向失败、最小修复、定向通过、一次当前受影响合并回归；相关测试缺依赖/未运行逐项解释。只重算需要证明等价的现有包；旧冻结包复算和当前源迁移是不同资格。

输出SCOPE_ACCEPTANCE：每任务terminal_status、engineering_checks、historical_effect、scientific_scope、external_actions。不存在某资料时终态blocked/not_evaluable可以结束本批，不是passed。下一批特定gate只依赖相关已通过节点，温度/搬迁不阻塞API离线修复或H15分析。

四份用户摘要见OVERALL_PLAN第10节。STOP_RECEIPT由执行者记录实际值，计划文件不得预先写成执行已通过。未批准R1/R2/R3时停止，不自动增加调用、训练或确认读取。
