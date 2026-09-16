# v13 首批执行规格：离线修复、既有影响核查与停止

状态：`PROPOSED_NOT_RUN`。本文件供用户在正式执行前复核，当前没有启动这些工单。

## 1. 首批目标与范围

首批不是重新下载年度资料或再跑 288 次 API。目标是让下一次研究比较具备可靠的消费者、完整分母和可解释身份，并查清已知代码边界是否影响旧 v12 数据。

建议执行目录：`plans/v13_execution_<实际日期>_01/`。目录已存在时使用新后缀，不覆盖已有批次。规划目录本身不能作为执行 claim。

| 项目 | 拟议首批边界 |
|---|---|
| 工单 | A00—A06，完成或受阻后均收尾，不自动转 B/C/M |
| 允许工作 | 新代码、定向离线测试、只读历史影响扫描、同输入算术/特征诊断、后续 roster 草案 |
| 新天气 HTTP/API/被测模型 | 0/0/0 |
| GPU/新拟合/确认载荷 | 0/0/0 |
| 新完整日历实验/新 C2 科学分支 | 0/0 |
| Git 提交/推送 | 不包含在本批自动执行范围 |
| CPU | 优先已有环境；确需额外资源时在复核后的执行范围内选择单个 16 CPU/64 GiB 作业 |
| 时间 | 约 6—10 小时工作预算；不是保证所有未知缺陷均可在此时限内修好 |

这轮用户要求“正式执行前复核”，所以当前停在计划。此前资源使用偏好仍有参考价值；不能把本文件或旧运行授权当作本轮已经获准启动的凭证。

## 2. 执行前只读基线 A00

读取本规划入口、当前适用 AGENTS、v12 FINDINGS/RESULT_SUMMARY/FINAL_VERIFICATION、源码和发布回执。不要执行历史 launcher。

记录 published reference、development HEAD、source hashes、dirty/index hash、确认角色、已消费运行与请求 ID。使用 `GIT_OPTIONAL_LOCKS=0` 读取 Git，避免刷新 index；不 reset、不恢复用户已有文件、不按开发 HEAD 较旧而覆盖工作区。

允许修改清单与历史保护清单分开。冻结历史 source、原 24 分支、288 答卷、两个兼容请求、费用、journal、checkpoint、STOP 和旧评分均保留。代码修复进入当前模块的新版本或新批次派生分析模块，不直接重写已消费 v12 批次脚本。

按现有 JUnit/manifest 收集 v11/v12 唯一 node IDs，分类重叠、改名、按理由移除、缺依赖、未运行。只读对账不等于重跑通过；如原 XML 不全，明确无法核对，不用测试总数补猜。

输出：`BASELINE.json`、`PROTECTION_MANIFEST.json`、`EDIT_SCOPE.json`、`TEST_SCOPE_DIFF.json`。A00 必须先完成；下列 A01—A05 的互不依赖部分可由普通进程并行。共享生产接口的代码修改应串行合并，避免并发写同一文件。

## 3. A01：C2 完整性与实际消费者指纹

当前依据：`plans/v12_execution_20260915_01/analyze_branches.py` 遇缺报告继续，trace 用交集；`analyze_stage_c.py::paired` 仅按 F_COMMON 名字标记 bank 差异。

先将下列边界变成调用实际新分析入口的失败测试，不能只执行附件摘录函数或把探针的退出 0 当修复验收：

- 缺一份报告、缺全部报告、缺一个应有 trace、trace 为空。
- 重复 opportunity/call、同一机会多个合法调用、错误 parent/source/hash、alias 指向缺失执行。
- 合法失败或 fallback 没有预测调用，与实际有调用但丢 trace 的区分。
- 缺 Y 仍保留注册机会和 E 诊断；零特征/概率变化也能形成完整报告。
- FOLLOW 与 values 为不同消费者；COMMON/VALUES 区分实际 bank；方法重命名不改变配对身份。

实现以冻结 roster/alias/正式调用为 expected set 的外连接，先查重复再建 map。需 trace 的调用由实际调用合同定义，不能要求每个机会都伪造一条 trace。

输出独立维度：`execution_complete`、`analysis_complete`、`formal_qualification`、`scientific_scope`；正式资格区分 formal_bound、legacy_replay、engineering_diagnostic。配对指纹包含 consumer/code/bank/feature/calibration/common-info/schedule/adoption/failure/resource。

历史影响扫描只核旧 6 父×4 规则及已有 108 方法会话，不重新运行策略。正常完整输入的 Brier、分母和已知缺失界应保持；若发现真实错误，输出新版本更正与 lineage，不覆盖旧分数。

产物：`C2_INTEGRITY.json`、`METHOD_FINGERPRINTS.json`、`HISTORICAL_REPORT_IMPACT.json`。

## 4. A02：实际 API 生命周期一体化

复用现有 spool/ledger/coordinator，新增共享运输实现或明确的新版本，不再次复制出互不一致的多个 batch worker。

合同至少覆盖：

```text
registered -> claim -> bind/prepare -> final local permit -> durable intent
-> send once -> durable capture -> validate -> publish -> consume/settle
                                     -> append-only recovery if provable
```

许可检查靠近真正发送，绑定作用域、请求/执行、STOP、deadline 和一次性身份。UTC 用于记录锚点，单调钟用于耗时；wall deadline 与 replay cutoff 不混算。短临界区不持锁跨网络，许可之后在途请求不能假装被 STOP 撤回。

捕获在脱敏/UTF-8 解码前记录原字节数、读取上限、EOF/截断、captured-prefix hash。完整时才给 full-body hash；脱敏文件有自己的 hash/transform identity。预期 hash 需与可信上层 receipt 绑定，不能仅依赖可被一起修改的同一个 JSON。旧 capture 不能补造原本未记录的完整性证据。

生产消费者必须识别合法追加的 reconciliation receipt。原 `.failure.json` 保留，恢复绑定原 request/execution/intent/capture/failure/新 response；零新 HTTP、一次结算。晚恢复只允许适用的账务/审计，不倒填旧天气截止或重开已经结束的会话。

最小故障覆盖：claim/凭据/I/O 后到期；permit 前后 STOP；双 worker；intent 后崩溃；HTTP 后无 capture；capture 后发布失败；首次哈希不符；脱敏缩短使截断误判；非法 UTF-8；错误模型/usage；恢复后 resolve—coordinator—ledger 真消费；重复恢复、晚恢复与 unknown reserve。

本轮 mock/fault-injection 无网络。未验证 AFS 多节点锁时，新 API 路线限制单派发权威。不承诺 provider exactly-once；未知远端执行不自动重发、清零费用或释放保留额。

历史影响最多扫描原 288 正式+2 兼容请求回执，结果为 observed_affected / observed_unchanged / insufficient_evidence。缺最终 permit 时间戳不意味着已证明迟发，也不能证明全数及时。

产物：`TRANSPORT_V2_CONTRACT.json`、`DISPATCH_CAPTURE_RECOVERY_TESTS.json`、`API_HISTORICAL_IMPACT.json`。

## 5. A03：selector_query_only.v2

推荐唯一模型输出：

```json
{"query_order": ["q0", "q2"]}
```

新合同源同时生成 system/输入说明、logical schema、provider schema、本地 parser。现有执行接口若仍需双字段，固定适配器补空 `forecast_handles`；不让模型生成，不作为 v1 失败回复的事后修复。

query_order 是有序意图；最大长度按合法候选数而非当前能买几条。预算、截止、缓存和权限由执行器决定实际前缀，并完整记录尾部未执行原因。空选、全取、重排均合法；没有候选时只允许空列表，避免空 enum 非法 schema。

离线检查合法空/全/子集、重复 key/handle、未知 handle、额外字段、类型、长输入/输出、拒答、截断、代码围栏、空目录、无预算、晚返回。v2 推荐严格裸 JSON；v1 原有完整围栏处理不改。provider 未支持的 schema 限制仍由本地验证，禁止静默降级。

真实供应方行为不由本批合成测试背书。本批仅生成 M00 的最多 12 请求草案，不发送，也不枚举新路由试错。原生成参数是否延续由后续请求清单明确冻结。

产物：`QUERY_ONLY_V2_CONTRACT.json`、`SELECTOR_V2_OFFLINE_MATRIX.json`、`M00_PROPOSAL.json`（execution=false）。

## 6. A04：新增获取语义与 E/F 边界

保留 residual v1 的 first/second/all 语义和旧结果。v2 使用 none/first_new/second_new/all_new，按付款者、authorization scope、query ID、receipt 状态和 cache entitlement 生成 remaining_new。

另一目标的私有缓存不授予本目标访问权；shared 已买可复用；pending/UNKNOWN 不能再次发送。证明未发送的失败能否新登记由新合同明确，不默认免费 retry。

测试首项已缓存/已请求、另一目标私有缓存、共享缓存、无第二项、不可用、预算耗尽、迟到、parent 变化、alias。保留全部排除和执行 disposition。none 是不再付费查询，仍有共同基线更新和固定预测，不等于停止整个会话或原策略等价续行。

复用支持和联合可达性代码，保留 E 状态与 F 概率不同语义；有限图时间/费用见证不可拼接。第一批只做合同/合成或旧输入核查，不执行新的真实多父矩阵。

产物：`RESIDUAL_V2_CONTRACT.json`、`RESIDUAL_V1_IMPACT.json`、`C00_ROSTER_PROPOSAL.json`。

## 7. A05：有限时点、动作和旧结果影响诊断

元数据范围为已有 288 正式请求，字段只取其当时 public view/已有回执。区分句柄形式差异、真实来源差异和下游特征/概率差异；未知值只留评估侧，不回送选择器。

数值时点诊断上限：从原 12 个已暴露开发日各按公开 ID/hash 固定两个目标，共最多 24 个。不按 Y/损失挑选，缺本地资料保留缺口不补样。目标合同、观测/产品身份、cutoff−600 秒和实际 slot、source age、TAF 版本、合法披露集、feature/logit/probability 分开记录。

可以做既有同输入转换与算术，不重拟合、不注册新正式天气会话、不枚举新 GET 反事实。Stage C 没有原训练时点 capture 的目标须注明这是离线重建视图，不伪称实际历史运行记录。

输出 drift/no_material_drift/insufficient_support，并给下一批固定 bank 桥接的具体清单。当前有缺证子集训练，不再重新提出“增加缺证子集”作为未实现功能。

产物：`CLOCK_INFORMATION_AUDIT.json`、`ACTION_SPACE_CENSUS.json`、`ROLE_LEDGER.json`、`B00_ROSTER_PROPOSAL.json`。

## 8. A06：验收、收尾与停下来的条件

先定向 red→green，再跑一次当前受影响测试集合和有限旧输入复算。保存命令、node IDs、退出码、JUnit、stdout/stderr、源/输入/结果哈希；skipped、缺 fixture、未跑均不能写通过。不自动安装包或下载缺失天气资料。

收尾器只要求 A00 已有基线，观察 A01—A05 的终态或达到本批截止，不要求全部成功才能写报告。它必须同时输出：

1. `batch_closed`：所有本批工作均停止/完成/受阻且状态可解释。
2. `engineering_complete`：所有本批必需验收是否实际通过。
3. `gate_readiness`：B00、C00、M00 各自的前提，而非统一一盏绿灯。
4. `scientific_claims_added`：首批没有新模型增益或独立确认结论；新报告更正若有，逐项写明。

产物：`TEST_RECEIPTS.json`、`IMPACT_SUMMARY_CN.md`、`NEXT_GATE_DECISION.json`、`STOP_RECEIPT.json`、一页 `RESULT_SUMMARY_CN.md`。blocked 可以收尾，但 engineering_complete 必须为 false 或明确 partial，不能被上游 passed 覆盖。

建议时间分配：基线/范围约 0.5—1 h；核心修复约 3—5 h；有限普查与历史影响约 1—2 h；合并回归与收尾约 1—2 h。复杂缺陷超过预算时交付已完成差异和剩余明确阻塞，不临时扩大任务。

## 9. 下一批的具体出口

| 后继 | 本批必须提供的前提 | 不需要等待的支线 |
|---|---|---|
| B00 年度同日历程序桥接 | A00/A01/A05 的有效结果；新 roster 与固定消费者身份 | 真实 API、温度、全部 PROCESS、原生图像 |
| C00 多父 GET | A00/A01/A04；已选后端；实际 parent 与所需源状态资格 | 模型获胜、所有温度/MM 资格 |
| M00 真实接口小试 | A00/A02/A03；12 请求清单与真实调用范围冻结 | 完整周科学效果、全部 C2 处理实验 |
| M01 正式 selector 比较 | M00；B00/B02；冻结后端/日历、强程序和消费链 | 与该研究主张无关的完整 16 类扩展 |

这些是提案条件，不是已获得执行许可的状态。首批结尾停止，供用户查看代码、影响和门槛后再决定后续执行范围。
