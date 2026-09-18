# 可交给 Codex 的首批执行指令（待用户明确批准）

这份指令本身不构成授权。用户当前要求整合与制定计划，不代表批准新API、云作业、拟合、确认或Git推送。先核当前请求的有效范围，不把旧十小时窗口或旧288请求重新激活。

## 1. 目标

在既有C1/C2/C3下执行IP00—IP06：修报告完整性、消费者身份、生产API许可/捕获/恢复边界，完成query-only接口离线资格，量化年度bank时间/信息与动作空间，登记下一批精确范围。不要增加核心框架或重复已经完成的年度下载、840旧轨迹、六父重建、旧24分支和旧288模型调用。

参考commit：`1eba36dd272c72573d1309c78d45dbe97dd8af12`。真实HEAD前进时先生成差异与问题处置，不reset。已修复/不适用项标明，禁止机械照单再改。

## 2. 启动读取

先读取工作目录实际`AGENTS.md`，再读最新入口、v12 `FINDINGS_AND_NEXT_GATES_CN.md`、`FINAL_VERIFICATION_01.json`、`RESULT_SUMMARY.json`、`FULLWEEK_FINDINGS_CN.md`、`SELECTOR_INTERFACE_V2_PROPOSAL_CN.md`、本包整体计划和`WORK_PACKAGES.json`。仅遇到不一致再查旧审查包，不每次重读全部134成员。

核查发布身份、开发身份、import实际路径、冻结branch/stage_C源码及运行回执。确认旧批次的来源/模型/账本/STOP/父状态不被修改。入口指向稳定batch和source哈希，发布后的HEAD在外部上传回执核验，避免文件自引用。

新输出目录候选：`plans/post_v12_integrated_1eba36d/`。若已存在，读取其run身份后决定新generation；不得覆盖现存失败或伪造授权。除有限当前源修复外，原冻结source和原结果只读。

## 3. 严格边界

```text
新气象来源 HTTP = 0
新被测模型/API 请求 = 0
新 GPU = 0
新拟合/校准 = 0
新科学父状态/分支批次 = 0（仅离线工程fixture与旧回执派生分析）
确认载荷/未来标签访问 = false（已暴露开发Y仅在评估侧允许）
Git push/覆盖 Library/远程文件 = 0
```

检索Git元数据、阅读官方文档与本批气象数据/模型请求分账。需要超出范围时只输出blocked与下一批规格，不能自动升级。没有资料就标not_evaluated，不能从ZIP摘要补造原始值。

## 4. 执行顺序

### IP00 身份与保护

生成基线、保护、已消费身份、实际nodeid集合差异和暴露账。保留开发脏工作区和暂存，不reset，不丢旧索引。750与628不是直接相减的缺测数。

### IP01 分析完整性和真实消费者

对`analyze_branches.py`建立缺1/缺全report、缺应有trace、重复机会、错误alias、score/hash冲突的red tests；按冻结roster修复。不能在缺臂时只算剩余组合还标完整。F可评分、C2证据可解释、合法失败回退是不同资格。

修`analyze_stage_c.py`真实consumer来源字段：FOLLOW映射、common bank、values bank分别标记；保留原损失。复核旧24路径/36配对的实际完备性，只派生影响表，不重新运行路径。

### IP02 API许可、完整捕获和恢复消费

针对实际`siliconflow_worker.py`及`production.py`，一次整合：最后发送许可、STOP/墙钟截止、request/execution/capture绑定、raw截断与脱敏前长度、恢复消费/费用/时机。

先把审查包的合成反例迁入真正导入路径测试。恢复须从原capture零HTTP补齐，经真实consumer处理；failure保留并用不可变reconciliation连接。未知请求不重发，过期结果不回填历史预测。定义许可点后已在途边界，不承诺跨网络exactly-once。

用假的transport和临时文件做故障注入；不要读取用户API key，不执行余额/模型兼容请求。回归包括许可前后STOP、claim/凭据/I/O超时、capture/worker/response断点、两worker竞争、重复恢复、哈希冲突、UTF8/usage/model/finish_reason及截断脱敏。

### IP03 最小兼容query-only接口

建立一个合同源生成schema/prompt/parser；短期仍用`query_order`与必须为空的`forecast_handles`。public_slots不受模型控制。json_schema关键字支持只能作为未来真实资格，离线不得预填提供方通过。

用原真实公开天气视图构建fixture，包含空/全/子集/排序、长上下文、版本变化、无预算、拒答/截断/未知句柄。禁止把旧queries别名转正、强制模型非空或嵌入正确query。输出未来24请求登记提案，不发请求。

### IP04 时点与动作普查

只用旧冻结bank和已暴露资料，比较fit=-600s与真实预测slots。拆同资产改时间、同时间合法证据、真实时间推进；后到字段不能回填。记录TAF/current版本、已知/可得/已得、age/lead/mask、特征与概率，必要的Y仅评估侧。

普查原288决策，不只71合法；记录全不取/全取是否由预算、cache、失败或任务空间造成。不要要求事后最佳非all/none、正收益或程序非零regret。有限反事实科学实验只登记，未授权不开始批量分支。

### IP05 新语义与下一批设计

必要时新增residual v2 first_new等，保留v1重放。按授权作用域处理cached/requested；full inventory保留迟到/无预算等原因。设计GET/PROCESS/WAIT到真实F字段的映射；不改E布尔值制造F效果，不移除raw/projection守卫。

核既有multi-cutoff/修订回执，登记同一target多截止的资格缺口；旧lead1h每日重置不宣称一周持续agent。下一轮父状态与新bank关系先冻结；换bank不能静默换旧父状态。

### IP06 局部验收、完整批次状态与停止

并行节点由一个owner合并共享文件。定向red/green后只做一次相关当前回归，自动unique nodeid；历史XML不相加。旧源capsule复算和当前源迁移分表；未附完整档案不假装全复算。

依赖未完成则blocked_external；不为了全绿重启旧launcher。局部验收可先交付，但全批通过只覆盖真实完成范围。更新保护/影响表和短摘要后停止，不自动推进IP07以后。

## 5. 首批实际交付

`EXECUTION_BASELINE.json`、`PROTECTED_INPUTS.json`、`TEST_SCOPE_DIFF.json`；
`C2_ANALYSIS_INTEGRITY.json`、`PREDICTOR_PROVENANCE.json`、`HISTORICAL_IMPACT.json`；
`API_TRANSPORT_QUALIFICATION.json`、`RECOVERY_CONSUMER_QUALIFICATION.json`；
`SELECTOR_CONTRACT_V2.json`、`OFFLINE_WEATHER_INTERFACE_RESULT.json`；
`CLOCK_INFORMATION_AUDIT.json`、`ACTION_SPACE_CENSUS.json`；
`QUERY_PLAN_SEMANTICS_V2.json`、`GET_PROCESS_WAIT_CONTRACT.json`；
`PHASE_A_LOCAL_ACCEPTANCE.json`、`NEXT_BATCH_SCOPE.json`、`STOP_RECEIPT.json`。

这些是拟新增产物，不应在执行前写成已存在。实际报告只需回答：修了什么，旧结果实际受影响多少，时间/信息差异是什么，下轮准确需要哪些新身份和预算。

## 6. 后续不得自动跨越的门槛

年度完整日历程序桥接需要新范围登记；训练只在支持审计需要且有新授权时进行。真实接口默认24请求、后续selector最多288请求，各自独立；可选48配对接口方案取代24，不叠加。

新GET建议12父/48干预，原策略续行和父前缀重建单列；PROCESS/WAIT另限量。确认必须C1与C2同时冻结或使用隔离日历。温度、MM、D和prospective是独立路径，未授权不启动。
