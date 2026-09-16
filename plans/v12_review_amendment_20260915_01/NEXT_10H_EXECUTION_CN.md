# v12 阶段 A：后续 10 小时执行规格（待复核）

状态：`proposed_for_review`。T0 是后续实际获准启动并写入新批次身份的时间，不是本文创建时间。本轮只制定计划，既有 v11 任务继续原流程。

目标：**修正已有结果的解释和输入守卫，查清 C2 的真实来源及状态恢复能力，并在条件满足时完成有界真实取证分支。** 10 小时后交付已完成、失败、不可评估与外部等待的完整清单，不要求以模型正收益作为成功条件。

## 1. 范围与资源

| 项目 | 本批上限/规则 |
|---|---|
| 经过时间 | 10 小时；8.5 小时后不新增研究分支；最后 1.5 小时保留给验收、清单和停止 |
| 新增 CPU/RAM | 总计最多 16 CPU、64 GiB；四个程序队列共享上限，不是每队列各 16 核 |
| 并行方式 | CCI 控制；优先一个 ACP CPU 作业内按独立任务/父状态并行，单会话事件顺序不变 |
| GPU/新模型 | 本批 GPU 0、新 benchmark 模型/模型 API 请求 0；后续 C 阶段最多 4 H100 |
| 数据与拟合 | 新上游来源 HTTP 0、新年度拟合 0、确认集访问 0；平台提交/状态接口不计作数据源或模型请求 |
| 父状态重建 | 最多 6 次，原捕获状态存在则不需要重建；失败占额度 |
| 无干预续跑 | 最多 6 次，继续原 B11_COVERAGE 策略；失败占额度 |
| 处理分支 | 最多 24 条＝六父状态×四个有限计划；不足不补抽，别名不重复执行 |
| 原任务 | 不重开分片、launcher 或旧 audit；不修改其 source、数据、合同、STOP、费用及失败 |

执行前读取当前配额和原作业状态；原审计资源另行计入总占用。配额不足时缩小本批并行度，不重复提交任务。GPU 不能解决本批主要的 Python 状态验证和 AFS I/O；若以后要改资源配置，记录具体配置变化和边界。

本批不包含年度补下、新模型兼容性试验、确认资料解封、TAF 真实处理干预、MM 推理、D/X09 或 online 采集。是否开展这些工作属于整体路线后续批次。

## 2. 10 小时时间安排

时间段表示目标窗口。依赖未满足时完成其他独立任务；不为了赶表格而跳过门槛。

| 相对时间 | 主工作 | 并行工作 | 到点决策/产物 |
|---|---|---|---|
| T0–0.5 h | 核实身份、原任务与保护清单，冻结本批工作范围 | 读取已有短回执；绑定六个父候选元数据 | `EXECUTION_BASELINE.json`；发现绑定冲突则停止受影响路径 |
| 0.5–2.5 h | E/年度摘要与 bank 守卫的定向回归和最小修复 | C2 完整来源普查、父状态库存、年度唯一原文/缓存/暴露清单；每队列默认 4 CPU | 三个修复影响表、来源范围状态、parent inventory；不启动新下载 |
| 2.5–4 h | 完成精确 query-plan 接口和子 fork 资格；先验证第一个原策略续跑 | 其余合格父前缀按上限重建；TAF/METAR 消费接口审计 | 第 4 小时检查：能否建立合格父状态和真实动作消费链 |
| 4–7.5 h | 仅对通过资格者运行四条有限计划，最多 24 条 | 已有审计完成则派生十配对与 E 报告；否则保留外部等待 | 行为/字段/特征/概率/采用/损失链；无收益和退化均记录 |
| 7.5–8.5 h | 关闭分支集合，核验完整分母、状态和预算 | 一次受影响 monitoring 回归与输入/原输出保护核验 | 不因结果好坏新增父状态、模型或日期 |
| 8.5–10 h | 不再启动新研究分支；生成局部验收与整批收尾 | 整理代码差异、证据索引、后续阻塞与复核包；回收本批资源 | `STATUS.json`、`RESULT_SUMMARY.json`、`FINAL_REPORT_CN.md`、`NEXT_ACTION.md` |

第 4 小时尚未有合格 fork/no-op 时：继续时间允许的修复与诊断，但默认本批不再开启处理分支；余下时间用于把具体失败条件、源状态和可复现测试做完整。不临时重做 840 条轨迹，也不换日期寻找成功案例。这个时间门槛属于执行规格，不是科学效果阈值。

单个原策略续跑或处理分支设置 45 分钟 wall-time 上限；消耗时间过长时记录 `stopped_time_limit`，已发生动作和未知费用保留。它是本批工程资源终态，不能伪装天气任务正常结束。8.5 h 起不新增分支；最迟 9.5 h 对本批仍运行的 worker 发出有记录的停止，10 h 汇总终态；原 v11 外部审计不在停止范围内。

## 3. 具体工作包与验收条件

### W00.refresh：先冻结保护边界

记录实际开发 HEAD/index、审查发布提交、原任务身份、源/数据/银行/配置 hash、新输出目录及起止时间。先核每个将要编辑的源文件是否被原任务绑定；旧 `fullweek_02/source` 保持不动。新执行器进入新版本源快照，父前缀重建仍使用旧冻结环境。

本次看到的原父合同绑定的是 `fullweek_02/source`，但执行时仍按每份实际合同核验，不能只凭路径印象修改文件。

产物：`EXECUTION_BASELINE.json`、`PRESERVATION_BEFORE.json`。未知 launcher owner、原绑定变化或确认集意外暴露使对应路径停止。

### W07.e_summary / W06.sample_summary / W01.bank_guard：三个最小修复

1. **E 汇总。** supported/refuted 计入可判定，undetermined/inconsistent 分列；没有 frame 另列。E 分母依据原 E roster，不随 Y 是否成熟删题。生产状态之外的新字符串受控报错，不把它归入“没有证据”。新增派生汇总与影响分类，原 F、Y、掩膜、损失及文件保持。
2. **年度样例失败分支。** 三样例只有两成功时，输出三个唯一 unit、两完成、一失败、其余 69 未尝试。真实 71/72 来自样例全成功的另一条路径，不拿这个 bug 解释。新摘要修复不重新下载原成功样例。
3. **校准 bank 守卫。** 在实际 consumer 拒绝负概率、反向/不兼容重叠的域、布尔、NaN/Inf 和巨大整数溢出；合法 sparse gap、端点与既有外推含义保持。先核清公共边界是否兼容再设计判断，不粗暴拒绝所有相接区间。扫描实际旧 bank 区分未受影响、入口拒绝、数值可能受影响；不能把 raw 整周直接判无效。

先从真实消费者构造失败回归，最小修改后定向通过；审查 ZIP 的抄录函数不替代生产导入检查。本批新回归数字由实际 nodeid/JUnit 去重生成，不抄历史 750。

产物：`E_STATUS_SUMMARY_IMPACT.json`、`ANNUAL_SUMMARY_IMPACT.json`、`BANK_GUARD_IMPACT.json`。若原审计尚未结束，E 整体数量标 pending；本地表达式和真实已结算父片段验证可独立完成。

### W11.universe / W11.wiring：补齐来源与实际消费关系

只读已暴露的开发日历和已有月样例，join NATIVE_PRODUCT_INDEX、SOURCES、请求/HTTP 回执、原文和版本。对来源普查保留普通 full、partial/no-coverage、取消/NIL、conflict、unsupported、镜像、无当前产品、档案范围未知；结果状态与 E 状态分开。

输出 public_catalog 和 evaluator_catalog 的字段白名单及来源依据。不存在可靠历史完整性时限制为声明档案情景。普查异常按产品/版本/目标/父会话/过程分别计数；月样例只作本已暴露范围的质量核查，不据其未来损失选父样本。

绘制实际消费者字段表，检查原始区间开闭信息是否在 feature_vector 压缩；先统计真实碰撞，不凭理论可能性重写特征并拟合新银行。TAF 输出 `wiring_audited_not_intervened`；METAR 的获取、返回、缺报、删失和可见支持分开。

产物：`SOURCE_UNIVERSE_CONTRACT.json`、`PUBLIC_CATALOG.json`、`EVALUATOR_CATALOG.json`、`C2_STATE_CENSUS.json`、`C2_CONSUMER_WIRING.json`。

### W11.parent_inventory / W11.parent_materialization / W11.noop_equivalence

父候选已在 [PARENT_CANDIDATES.json](PARENT_CANDIDATES.json) 列出，元数据规则独立于未来 Y 和损失。六个父目录目前无中途 checkpoint；这是一项实际风险，不预填“可重建”。

逐父运行门槛 `parent_day_terminal_and_verified`：原终态合法、合同与绑定文件匹配、原日志/公开输入/费用可核。可以独立验证该父日，不必等待全 840 条的最终聚合审计；父日验收失败时只阻塞该父，不删除对应 roster。

父库存记录 clock、下一 tick、事件队列、ledger spent/reserved/释放、授权、cache 父资产、pending 源/模型、baseline/override/version、随机种子及原 failure policy。原 checkpoint 优先；否则最多六次冻结前缀重建，不联网、不请求新模型、不推测未捕获的响应。

优先在原 complete tick 后、下一个注册决策前的静止状态 fork。存在 pending 时，只有已有合法完成回执才能共享完成同一次过渡；记录变化后的真正 fork 时间，并对所有分支采用同一状态。缺少完整状态或完成证据标 `parent_not_reconstructable`，不能重新免费发请求。

子 fork 合同记录原合同/前缀与子实现关系，身份、路径变化显式允许，来源/状态变化不能混入管理差异。STOP 父目录不可重开；每个子分支 cache 初始状态相同，新增 cache 相互隔离。需有正式新身份验证，才能标 `formal_branch_qualified`。

无干预续跑继续原策略 γ，逐项对比科学状态、公共输入、查询/预测、budget 事件、候选与采用、原 F。允许的差异只有白名单里的管理身份/墙钟。只要实际预测或记账不一致，不能继续该父的干预比较。

产物：`PARENT_CHECKPOINT_INVENTORY.json`、`PARENT_MATERIALIZATION_REPORT.json`、`FORMAL_FORK_QUALIFICATION.json`、`C2_NOOP_EQUIVALENCE.json`。前两份同时满足复核提出的父可用性字段，不再维护多份互相矛盾的父状态真值表。

### W11.query_plan_interface / W11.branch_engineering

先在生产执行路径增加明确的有限 query-plan 类型，拒绝未知 selector/plan；绑定 query_id、source_id、source_version、payer_target、authorization_scope、顺序与实际 dispatch/completion receipt。保留原目录，不用过滤目录操纵原算法，不将程序调用计成模型调用。

fork 时先保存完整公开候选表，再按原合法可见性/目标关系/版本/授权构造固定 eligible 序列；不得按隐藏返回值或 Y 排序。预算和时限在逐步执行时用真实状态检查。缓存、已请求、不可用等也保留在候选库存与处置记录中。

四条计划语义固定为：

| 计划 | 精确含义 |
|---|---|
| no_further_paid_query | 余下会话不再发新增付费查询；免费更新、既定预测和截止封存继续 |
| first | 只处理 fork 冻结 eligible 序列的第 1 项；之后停止新增付费查询 |
| second | 只处理同一序列第 2 项；不存在时记 no_second_query，不换为第一项 |
| all | 按序处理 fork 冻结集合，不纳入未来新增候选；预算/截止/可用性阻止继续时保存可行前缀和未执行尾部 |

每条 planned 项必须有处置：executed、already_cached、already_requested、unavailable、unauthorized、budget_exhausted、late、failed 或未执行尾部的明确原因。first/second 命中缓存或不可行时不自动改选另一项。完成但内容缺报/不支持与运输失败分开。对 all，资源/合法性阻止下一项时结束新增查询；内容缺报本身不自动阻止计划中的下一项。所有规则以新合同为准，不能默默继承原启发式的跳过/补选。

`planned_query_order` 对比的是原计划；`executed_query_order` 必须等于按处置规则过滤后的实际可行序列。只比较接口返回 success 不够，必须追踪资产授权与回执，再核特征消费者。

固定 `U_parent`：原注册日会话在实际 fork 时尚未封存的机会，不能只保留被选中的单目标。四计划使用相同未来 Y、结算与缺失掩膜；主报该剩余会话的损失和资源，辅报原选中目标和全日。目标已在共享 pending 完成前截止则记录过期，不回填。

每条分支保留：fork/dispatch/completion/forecast slot、baseline 源与绑定、字段及 feature hash、candidate、采用/拒绝、实际生效概率、spent/reserved、同一掩膜上的 loss。分支因等待遇到 TAF 变化属于总效果；等时同基线字段检查为诊断，不创建额外真实处理分支。

产物：`RESIDUAL_QUERY_PLAN_CONTRACT.json`、`C2_BRANCH_ROSTER.json`、`PLANNED_EXECUTED_ACTIONS.json`、`C2_FIELD_TO_LOSS.json`、`C2_ENGINEERING_REPORT_CN.md`。四计划可能别名、无新增字段、概率不变或负收益；这些均保留。合成边界测试与真实天气分支分表。

### W06.inventory：年度数据下一批的准确规模

先修摘要，再盘点已存在的 71 个成功目录、失败精确请求、缓存 raw hash 与引用关系。拆分目录 reference、身份/版本、已验证原文、缺字节、内容冲突和未知 hash；输出成功片可复用清单和新恢复 generation 草案。

补 `EXPOSURE_LEDGER`：source QA、labels viewed、losses viewed、losses used for method choice。共享静态站点/schema 不作为跨年份 purge 依据，动态来源/结果窗/派生依赖才进入足迹审计。无法追溯的历史暴露记 unknown，不写 never_seen。

产物：`ANNUAL_NATIVE_INVENTORY.json`、`EXPOSURE_LEDGER.json`、`NEXT_ACQUISITION_SPEC.json`。所有请求数/字节数有证据才填精确值；未知项保留。仅登记，不发送来源请求。

### W07.closeout：消费原全量正式审计

外部门槛 `original_fullweek_full_roster_formal_audit_verified`。由已有 coordinator 完成，不修改其冻结实现，不再提交第二份同等全量重放。

原结果齐全且 hash/roster 合格后，在新目录输出完整十配对、E 修订汇总、正/负例贡献、地区/季节分层以及缺失结果敏感性界。共同掩膜是方法间公平条件，不等同总体无偏；敏感性界不充当抽样置信区间。原 FOLLOW 携带银行标识不等于消费该银行。

原审计未在本批窗口结束时完成，产物标 `PENDING_EXTERNAL`，写清已有 job、状态与缺失回执。不要用局部胜负充当全表。原年度一个失败不改成整周失败。

## 4. 验收、收尾与后续放行分开

机器依赖见 [WORK_PACKAGES.json](WORK_PACKAGES.json)。原 `W05.acceptance` 的单一依赖拆为：

| 项目 | 如何判定 |
|---|---|
| `W05.local_acceptance` | 根据实际本地改动、定向/受影响回归、来源普查及已有分支回执验收；原外部审计不是硬依赖，未完成研究路径单列 |
| `W07.closeout` | 只有原完整正式审计可消费时，形成全量描述性比较 |
| `W05.full_acceptance` | 必须项均有合格结果、原审计/派生完整、实际父状态和分支资格满足；不能由局部通过代替 |
| `W05.batch_closeout` | 10 小时内把本批所有注册节点标明已完成、失败、不可评估、阻塞或停止；允许 `CLOSED_WITH_PENDING_EXTERNAL`，但不是科学 PASS |

`SCOPED_IMPLEMENTATION_ACCEPTANCE`、`BATCH_CLOSEOUT`、`SCIENTIFIC_COMPARISON_COMPLETE` 三个字段独立。合法缺报/失败的分支可被完整审计并如实报告；所有父状态不可重建、或只有合成验证时，不得宣称真实 C2 工程链完成。

原全量科学比较完成只表示冻结开发实验的比较完整，不表示 novelty 已证明或独立确认通过。完整验收未达标时阶段 B/C/D 状态仍是待复核；即使依赖通过也不凭脚本自动跨出当前授权范围。

## 5. 十小时后的预期交付

**基础交付：** 三类问题的实际回归/修复和影响范围、来源范围与状态普查、六父状态的可用性结论、精确查询接口/消费路径资格、年度缓存差额与暴露清单、可读终态报告。某项无法完成也须有具体失败输入、原因和剩余工作。

**条件交付：** 原审计完成后给出全量十配对；父资格、无干预续跑、动作接口在时间门槛内通过后给出最多 24 条真实处理分支及其状态到损失记录。不会承诺一定凑满 24 条或一定出现正收益。

**不在本批结论内：** 全年强银行、LLM 优于程序、C2 跨独立过程确认、全部 16 类闭环。它们各自需要后续阶段的真实证据。

## 6. 节约 Codex token 的实施方式

使用现有薄协调器思路和确定性脚本，不新增多 agent 编排。数据遍历、解析、hash、统计和状态轮询交给 CPU 程序；这些循环不需要逐条发送给 Codex，也不调用 LLM judge。

脚本每 1–5 分钟读取短状态或平台终态；完成、首次失败、合同/分母变化时写事件摘要。Codex 在启动、关键门槛、首次异常和收尾读取 `STATUS.json / RESULT_SUMMARY.json / NEXT_ACTION.md`；需要定位时才读取限定日志片段。不给 Codex 反复输入全量源文、七份旧审查或完整 journal。

保持三本账：Codex 编排 token、被测模型 token、CPU/GPU/网络/存储。没有 Codex 用量接口就不承诺节省比例。省 token 的对象是重复编排与日志阅读，不减少注册样本、强对照、失败分母或必要验收。

同一个任务单 owner，消耗后的身份不重用；中断后读回执，不重新执行已完成节点。定向 red/green 后合并一次受影响回归；只有新修改/失败才重跑。所有有界真实重建、续跑、分支和验证重放分别计数，不作为新增独立天气样本。
