# 下一批执行方案：先交付工程闭合与数据实验登记

状态：**计划，尚未执行本批修复。** 用户当前先审阅整体合理性。
本文件对应整体路线的阶段 A，并为阶段 B/C 准备精确范围；不直接启动新模型或打开确认数据。

## 1. 首批目标与范围

首批要交付：当前模块的正式回归、最小合同修复、原数据影响表、评分性能剖析/等价优化，
以及可交给后台执行的完整周和年度数据登记。预计 0.5—2 个工作日，实际按问题和出口判定。

可以立即并行的工作是源码/现有数据 CPU 检查、年度缓存清单和过程设计。
本机 cgroup 为 2 核/8 GiB；重放规模扩展时使用已授权的 ACP CPU 资源，不按 192 核 affinity 误配进程。
沿用用户已有资源授权；以下节点的“门槛”是数据/实验条件，不是每一步再问一次权限。

## 2. 工作包与已有入口

| ID | 内容 | 主要代码/资料入口 | 首批验收 |
|---|---|---|---|
| W00 | 刷新实际基线和保护清单 | 本目录 REVIEW_BASELINE；v10 FINAL_RESULT/GITHUB_UPLOAD；当前 Git 状态 | 后续变化有差异记录；不 reset 或改索引；v10 封闭状态保持 |
| W01 | 温度/响应合同及影响扫描 | monitoring_v1/feature_tasks.py、temperature_postprocess.py、native_feature_forecast.py、feature_scoring.py | 生产入口反例、合法例一致、历史命中/未核范围 |
| W02 | 正式来源、数据卡和结果绑定 | monitoring_v1/formal_session.py；monitoring_fixed_v1/admission.py、outcomes.py、outcome_policies.py | 正式伪装/错目录/错数据/错 provider 被拒绝；合法失败保留 |
| W03 | API 发送门槛和不完整状态 | monitoring_v1/api_ledger.py、api_capture_v2.py、spool_backend.py | 假时钟/假运输层测试；未知费用不回收、不重发 |
| W04 | 分段 profile 与同次评分复用 | formal_session.py::score_formal；admission.py::score_admitted；现有小真实日志 | 新旧科学字段/状态/分母等价，记录真实性能与内存 |
| W05 | 集成回归与有限复算 | tests/test_monitoring_*.py；两个现有 portable capsule | 实际 nodeid 和退出码；原小包范围复算，区别冻结旧源与当前新源 |
| W06 清单部分 | 全年获取登记 | v10 scripts/complete_seasonal_data.py、audit_full_dependencies.py、seasonal_completion_02/COMPLETE.json | 精确缺片/缓存、月/站/产品角色，尚未取得处不写成功 |
| W07 登记部分 | 完整周程序矩阵 | v10 scripts/run_seasonal_controls.py、run_multicutoff.py、seasonal_controls_01/REGISTRATION.json | 全日历 ID、五条件、48/day、日界、协议和失败政策 |
| W09 草案部分 | 过程/确认设计 | monitoring_v1/process_split.py、现有依赖审计 | 已暴露/未读身份、保守分组、统计与停止草案；不读 Bay 载荷 |

`monitoring_v1` 等相对入口位于 `disastertrace-starter/src/disastertrace/`。
机器队列见 `EXECUTION_QUEUE.json`，所有新工作初始为 planned。

## 3. W01：最小修复，不重写数值后端

将本轮 13 个探针中相关行为迁入当前 package 的 pytest。探针脚本保存的是旧行为观察，
修复后不能要求该脚本继续报告“旧缺口仍存在”；green tests 应验证新的拒绝合同。

温度共享校验应包含：严格整数时间、UTC 日界、正长度、日/三日变量关系、有限非布尔阈值、
日期唯一、目标覆盖、day_index、同起报/成员 lineage、有效数组。成员坐标从来源证明，不能凭等长猜测。
两个概率实现仍可独立逐成员计算。原生产品缺字段时需区分任务只消费某变量与产品整体资格，
不要无理由使合法只含 max 的辅助输入失效；在入口 schema 中明确要求，再验证真实调用者。

模型响应允许有限非负 visibility lower；upper 允许合法有限值或 +inf。合法 P/M、9999/CAVOK
等原生政策不改。超大数与非有限量明确判 invalid，保留原回答和费用，不补成原生正确值。

只读扫描范围先锁定：原 128 个温度任务、对应模型捕获、24 月 POLICY/结果支持，以及
feature_temperature_trial_02、large_feature_trial_01、clarified_feature_trial_01 的提取回答。
同一题两模型或重复提示有不同回答身份，分别列出；扫描失败保留名单。
输出每种规则的命中 ID、旧/新资格与派生 F 影响；没有命中则不再跑模型。

## 4. W02：正式评分闭合但仍保留失败

先写实际集成反例：普通 run_session 伪装 formal 配置、错目录/合同/checkpoint、错 provider、
变更 data/bank、不合格 DWD 变量、缺一臂/机会、同目标跨提前量结果冲突。不是只测 helper。

建议内部结构如下，名称为待实现接口，不代表已有代码：

```text
FormalRunReference + canonical outcome records
  -> load and verify run provenance
  -> replay each journal once
  -> verify provider / comparison / baseline / intervention history
  -> immutable score context
  -> paired scoring and complete failure accounting
```

运行合同同时绑定数据卡、prompt/输出解析、来源/目标/query/银行/结果政策的角色和内容身份。
实验不变量如何绑定合同摘要要设计成无循环：先产生 immutable input-contract hash，
写入 experiment，再由生命周期回执绑定 journal/report；不能让合同和 experiment 互相要求最终 hash。

完整运行、合法失败、主动停止分别有终态。对于失败，后台按预登记规则封存可恢复状态和后续基线/
回退机会；必须标明这部分是 evaluator 恢复/情景结算，不伪装模型实际新提交。
若无法可信补齐状态，只报告不完整比较及失败分母，阻止输出“完整模型胜出”结论。

既有 JSON 科学字段不变是等价目标；新 provenance 字段或 schema 会改变外层摘要。
旧模式仍可只读重放，但不得改旧文件使其看似通过新注册门槛。

## 5. W03：API 只做离线修复与故障注入

先固定 deadline 是 claim 截止还是 no-new-dispatch 截止；推荐后者，并定义本地最后许可点。
STOP 与许可的本地顺序需要一致；许可之后已开始的 HTTP 不保证能撤销。
最终检查与持久化放在短临界区，网络等待不持有全局费用锁。

在 mkdir/预留/请求/发送意图/原响应/用量/终态等阶段注入失败。
首版只处理当前单逻辑请求的无覆盖登记和恢复，不做通用分布式事务引擎。
通过现有 contract 能知道预留上限的 incomplete claim 单独记录；没有完整证明不释放未知预留。
API key 由运行时私有文件读取；本批测试全用假文件与假运输层。

新 body schema 区分捕获前缀、存储脱敏内容、是否截断和完整 body 未知。
实际 HTTP 402 任务仍是未尝试下游，不借修复重开旧 424 个任务。

## 6. W04：性能检查点与正确性检查点

profile 顺序：一个小真实日志、一组九方法、必要时一个月。先在小范围确定读字节、CPU、
墙钟、峰值内存和 from_journal 次数，再决定是否扩大。冷/热缓存与机器配置分开记录。

第一项修改只在同次评分内去重验证，正常九方法的完整加载目标为九次；
不承诺因此快 19 倍或两倍。优化 OutcomeRegistry 也必须保留全目标/跨 lead 冲突检查。
可在当前源上添加计时，但原冻结运行的历史时间、请求和回答不变。

旧日志评分优化后的等价，不等于重新运行真实会话的时延必相同。若实际模型更快而改变入场时刻，
那是新系统运行结果，须重新登记并保留与历史诊断的区别。

满足身份验证后，把 CPU 审计安排在 GPU 模型释放后独立执行。暂不引入跨运行持久缓存，
不省略 source hash 或“先落盘、后外部调用”的顺序。

## 7. 回归如何一次做够

已有轻量执行器 `plans/v10_execution_20260914_01/scripts/run_checks.py` 是通用命令包装器，
可用新输出目录收集命令、日志和退出码。其他 v10 脚本可能硬编码旧路径、日期、运行 ID 和状态，
只能先读后迁移逻辑，不能直接重启。尤其 `status_and_reconciliation.py` 的 main 会写旧式状态，
新调度器不应直接复用它的入口。

步骤：受影响模块局部回归 → 一组真实当前入口的旧/新对照 → 核心更改完成后的完整 monitoring 回归
→ 两个 capsule 的限定重建/当前迁移验证。只有新改动、失败或未解决风险才重复扩大回归。

生产正确性和本轮合成探针分母分开。完整测试记录实际 nodeid，不能用旧 720 固定填新通过数。
仅运行冻结 capsule 不会自动证明新源码正确：还须对其中适用输入运行当前路径并比较。
新合同改变可见数据时该输入只作 legacy 对照，不能强迫所有旧 capsule 获得新正式资格。

## 8. 低 token 后台交接协议

首批工程脚本由 Codex 编写和检查；确定性采集/重放不需要逐行解释给模型。
建议在现有 runner 外增加很薄的批次协调器，首版仅负责依赖、精确 ID、一次运行身份、
完成自动验证与摘要。没有新 agent 团队或新的 benchmark 引擎。

建议节点状态为 `planned / ready / running / completed_scope / failed / blocked / not_attempted`。
脚本生成 `STATUS.json` 和新 generation 的 immutable 回执；汇总文件是派生视图，不是覆盖原错误的账本。
云任务显示 SUCCEEDED 不足以进入 completed_scope，还必须核 exact IDs、退出码、审计与必需产物。
注册启动返回值不明时按请求身份核平台，不能马上再提相同云任务。

普通节点摘要应包含：

```json
{
  "task_id": "W07",
  "state": "running",
  "registered_ids_sha256": "<bound roster hash>",
  "expected": null,
  "completed": 0,
  "failed": 0,
  "not_attempted": 0,
  "missing_expected_ids": [],
  "resource_jobs": [],
  "heartbeat_at": null,
  "scientific_gates_passed": null,
  "needs_agent_reasoning": false,
  "next_action": "wait_for_registered_job_completion",
  "full_evidence_manifest": "<path>"
}
```

这是接口示例，不是已运行状态。真实值在新批次登记后自动填入。
后台每 1—5 分钟机器检查或接收平台完成事件，按 signature 聚合错误；Codex 不为每次 heartbeat
重新推理。关键例外为 hash/合同变化、分母缺片、评分不等价、模型未知费用、无法解释的资源状态。

断线重启只读短入口、当前节点与摘要；需要修 bug 才打开相关函数和第一处完整失败。
读过且内容未变的七份方案不再重复加载。Codex token 没有可访问统计时明确未知，使用输出字节/
工具调用/重复读取次数作为代理，不能伪造节省比例。

## 9. 首批结束时给用户看的内容

至少交付：

1. 哪些当前函数已改、哪些意见经核验降级，附源与合同哈希。
2. 哪些原真实记录受影响，哪些没有已知影响，哪些尚未核查。
3. 一次评分从多少次完整重放降到多少，实际墙钟/内存如何变化，所有正确性约束是否仍在。
4. 完整周五条件的精确 ID 和年度缺片计划；尚未运行的部分清楚标为 planned。
5. 测试及有限复算范围、所有失败、资源是否终止、下一唯一任务。

本批不以“新模型赢了”作为完成标准。若缺陷修复范围比预计大，先交付可核查的部分与阻塞，
不静默减少测试、不另起大模型任务制造进度。
