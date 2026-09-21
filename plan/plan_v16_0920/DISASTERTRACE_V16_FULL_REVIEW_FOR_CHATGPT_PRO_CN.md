# DisasterTrace v14–v16：完整研究复核材料与 Living Benchmark 目标问题

整理日期：2026-09-21（UTC）。用途：交给 ChatGPT Pro 做独立、深入的研究定位与实验设计分析。

这是一份自包含的分析交接文档：正文整理项目、审计结果、本次对话新增的问题和待决策事项；附录包含完整审计报告、原始 v14 新颖性方案、已批准决策和 v16 定位文档。只读取这一份文件，也能理解争议的背景与主要证据。

**请首先回答：当前方向是否仍在实现研究者想要的 living benchmark？其次判断研究价值和实验设计，最后再讨论代码修复。不要把“修完代码”自动视为“研究目标已经正确”。**

## 阅读说明与证据等级

- **用户目标**：用户仍然关心 living benchmark，并主动指出当前版本似乎没有体现 living。这一追问不能被解释为已经接受放弃 living。
- **已复现事实**：来自本轮 Codex 审计的实际运行、原始数据核对、源码追踪和 Git 历史核对。完整细节、文件行号和修复建议见附录 A。
- **历史记录**：来自原计划、决策 YAML 和执行回执。保留原文供独立判断；原文中的自报结论、旧状态和文献评价并不自动成为本次已核实事实。
- **审计判断**：Codex 对新颖性、统计可识别性和目标一致性的评价。请独立批评，不必接受。
- **待验证/拟议方案**：新增 living 闭环、统计设计及下一阶段建议，尚未实施，也不构成启动新实验的授权。

附录是原始材料的完整快照，未悄悄改写其中的历史错误。各附录给出源文件、行数和 SHA-256；矛盾应结合正文和审计报告辨别。文中的本地绝对路径用于标识证据，Pro 无法访问本地时不要假装已经打开。部分研究文档不在 Git 仓库内，因此直接嵌入本文件。

## 1. 用户希望 Pro 分析什么

本轮对话的关键顺序如下：

1. 用户要求独立审计 DisasterTrace v14→v16，首先评估新颖性和研究价值，再评估代码、数据隔离、统计和执行纪律。原审计要求只写 `codex_audit_v16/FINDINGS.md`，不修改代码或数据，不打开 holdout。
2. Codex 完成审计，判断为“方向仍有价值，但测量系统需要修复，经验研究设计需要扩展，当前十二目标试点不能支持核心论文结论”。
3. 用户要求简单解释，Codex 解释了“维护当前有效证据”和“预测准确”两种能力的区分，以及样本、代码和验证记录的问题。
4. 用户进一步追问：**“等等，我原计划中的living benchmark的living体现在哪里？我感觉好像没有？”**
5. Codex 回看早期方案和后续决策后指出：当前主线是历史回放中的动态证据修订；虽然另有前向采集，但尚未形成持续生成未来任务、事前预测、事后结算的完整 living 评测闭环。
6. 用户要求：**“帮我将当前的所有内容和问题都整理到一个md文件吧，并上传GitHub，我让chatgpt pro详细分析一下。”** 本文即该交接材料。

这一追问提出的是目标一致性问题，重要性不低于代码正确性。Pro 应同时审查“收窄后的研究是否值得做”和“这种收窄是否保留了用户原本要做的东西”。

## 2. 项目是什么，目前走到了哪里

DisasterTrace 研究极端天气预测/决策 agent。当前批准的主要试点为 H15 机场低能见度：对固定机场和固定未来时段，输出能见度低于 5 km / 1 km 的概率，在目标开始前 T−60、T−40、T−20 分钟评分。

关键数据与概念：

| 名称 | 在项目中的作用 | 必须保持的区分 |
|---|---|---|
| TAF / AFOS | 专业预报原文及其发布、订正、修订记录 | 是模型证据/可用基线来源，不是成熟结果 Y |
| AMD / COR / CNL | 修订、订正、取消等原生产品语义 | 需要结合来源、产品序列、适用窗口和时间判断替代关系 |
| ASOS / METAR | 机场观测及最终结果解析 | 只能在应有的结果阶段使用；不能进入声称 Y-blind 的选择步骤 |
| LAMP LAV | 当前归档中的 CIG/VIS/OBV 类别指导 | 类别值不等于原生概率，研究映射不能冒充官方概率产品 |
| Semantic evidence ledger | 对证据标注新信息、替代、重复、镜像、迟到旧版等关系 | 标签本身必须可靠，不能由待评模型自我裁判 |
| Fact layer | 评估当前有效版本、引用支持、失效事实的维护 | 评估的是操作性来源状态，不是保证当前预报在物理上正确 |
| Probability layer | 对固定结果 Y 计算 Brier 等 proper score | 预测准确不能替代事实维护正确，反之亦然 |
| Paired invariance diagnostics | 比较信息等价扰动与重复采样噪声 | 必须真正同父状态、同外部时间、同合法信息并做配对统计 |
| Trap policies | 忽略修订、总是更新、重复计数等确定性策略 | 用于验证诊断的区分能力；行为一致不等于识别模型内部机制 |

研究目标是例行唯一小时站报政策 `iem_routine_unique_hour.v1` 下的结果，不是对整个小时、整个空间连续天气真值的完美测量。两种阈值是嵌套的，不能作为独立样本重复计算。

审计的代码基线：

- GitHub 仓库：`sisuolv/disastertrace-benchmark`，当前为私有仓库。
- 被审计分支：`v16-manifest-v1`。
- 被审计提交：`58ff8120aa779c68b7cb902f782c5c66ca3e1833`。
- 审计累计范围：`fc3ff3c4` 之后至上述提交的 36 个提交。
- Git 仓库根目录是开发目录下的 `repo/`；代码根目录为 `repo/disastertrace-starter/`；Git 中的计划目录为 `repo/plan/`。
- 本文是上述基线之后的文档整理，不代表代码缺陷已经修复。

各轮主线是：v14 搭建 ledger/contract/commit/metrics/trap 框架；v15 修复外部评审发现；v16-prep 搭建编译器和方法臂 scaffold；datafix/measure-prep 接真实数据和结果；receipt-order 处理同分钟排序；manifest 冻结十二目标试点并披露结果。

当前仍不能把 BASE0、真实模型 P1-A、完整配对反事实实验、较长提前量数值后端、NHC 迁移等未来工作写成已经完成。

## 3. 最重要的新增问题：Living 到底去了哪里

### 3.1 早期材料确实提出过前瞻运行

早期监测方案 `novelty_monitoring_original.md:321` 写道：

> 方法冻结后，按预先确定的地区、站点和时间持续收集数据，在结果发生前保存预测，之后自动结算。
>
> 系统只记录，不对外发布预警，不影响真实操作。

该节同时强调要检验实际发布时间、网络失败、处理耗时、缺测和版本更新是否会改变离线结论。附录 E 保留了这部分原文。这是明确的前瞻影子运行目标。

### 3.2 后续定位发生了什么变化

v14 新颖性复核将“Living 题库”列为已有工作覆盖、不再作为独有创新点，并将主问题收敛到固定未来目标上的概率轨迹、语义证据账本与事实维护。D01 批准了新的主线。

这能支持“living 本身不是首创”的表述，但不能单独证明用户批准取消持续运行的 benchmark。已有先例会影响论文如何声称贡献，并不自动取消产品应具备的基本运行方式。

请 Pro 判断：后续执行是否把“不能把某特征当创新”误读成“可以从实际交付目标里移除该特征”？也请辨别合理的分阶段实施与未被明确记录的目标偏移。

### 3.3 三种不同的“动态”

| 层次 | 具体含义 | 当前可确认的状态 |
|---|---|---|
| Episode 内动态 | 同一目标的证据逐步到达、修订、撤销，模型更新判断 | 是当前主线，可在完全固定的历史数据集上离线回放 |
| 数据持续采集 | 每小时获取当下的新 TAF/METAR，积累新原文和回执 | 有 DL-6 计划和执行记录；本次审计没有核验其当前常驻进程或完整覆盖情况 |
| Benchmark 持续运行 | 持续生成未来任务、事前提交并封存预测、事后结算、追加带版本的成绩与数据批次 | 当前审计的 manifest/harness 尚未形成完整闭环 |

当前十二目标来自 2023–2025 年的固定历史归档。它们能够用于动态任务回放，但这不能证明 benchmark 本身持续演进或正在前瞻评价未来事件。

### 3.4 前向采集不等于前瞻评测

下载执行记录称 DL-6 已启动，每小时采集，并经历重启和站点覆盖修订。它证明有数据采集工作记录，不证明已经有连续运行的模型预测、预测封存、结果结算和成绩发布。

还需要审查 v16 定位文档中“前向采集天然完全排除预训练泄漏”的绝对化表述。需要绑定所评模型版本、数据生成时间、提交时间和结果出现时间；不能因为资料曾经是新采集的，就证明任何后来接受评测的模型都不可能见过它。

### 3.5 一个可供讨论的结合方式，不是已批准实施方案

可以将 living 作为外层运行机制，将语义诊断作为内部测量设计：

```text
冻结目标生成规则与评测版本
  -> 按固定站点/日历持续生成未来目标
  -> 截止前接收模型与基线预测，封存时间和来源
  -> 按真实可用时间交付后续证据，记录修订
  -> 目标结果成熟后按固定政策解析并结算
  -> 追加带版本、覆盖率和失败记录的新批次
  -> 保留旧批次，分别报告新批表现与跨时间变化
```

历史回放可以用于调试和可复现实验，前瞻批次可以检验真实时序与部署条件。二者应明确标识来源、暴露和结算身份，不应混成同一份未经区分的成绩。

这里尚待设计的内容包括任务准入和生成规则、预测截止与封存、缺测/停机处理、结果修订政策、版本间可比性、模型变更登记、长期预算、滚动公开结果与确认集的边界。这些内容不能仅用一个定时下载脚本替代。

## 4. 当前研究价值判断及其可被反驳之处

Codex 的暂定判断是：**作为一个具体领域的 benchmark 有值得继续验证的价值，但尚不能证明已产生独立、有效的研究贡献。**

已经有先例的内容包括同题反复预测、外部时间网格与 carry-forward、stateless 与持续状态比较、结构化 belief、当前/被替代事实评分、脚本化失败策略和反事实重放。把这些模块放在一起，或使用本项目的 `FormalSession` 类名，都不能自动证明新颖性。

较可辩护的增量是：用真实业务产品的版本关系，程序化地区分“看到了资料”“用了当前正确版本”“合理改变概率”“最后预测正确”，并验证这种区分是否带来了已有指标看不出的实证发现。

需要特别约束的表述：

- 两层评估的价值需要实验展示，不能只因为有两个字段就宣称产生了独立测量维度。
- mirror、duplicate、no-change reissue 未必都信息等价。独立来源确认、有效期延伸和可靠性信息可能有价值。
- 当前版本的专业预报仍然可能预测错误；fact oracle 不是 probability oracle。
- 行为与某 trap policy 一致，不等于证明模型在内部使用了该策略。
- living 可以是运行形态；若要作为独立研究贡献，仍需要明确不同于已有持续评测系统的增量。

请 Pro 尤其挑战以下可能过度乐观的判断：真实气象版本字段是否已经足以支撑一个有价值的新 benchmark？还是只是已有方法的领域替换？如果实际修订过少、专业基线不足、诊断标签不可靠，剩余贡献是否只能是数据资源？

## 5. 数据、基线、样本和统计的现实约束

### 5.1 已复算的数据规模

| 项目 | 实际复算结果 | 对研究的含义 |
|---|---|---|
| TAF 非封存归档 | 140 文件、41,386 packages、60 skips | 数量足以开发编译流程，不等于已有大量独立可评分修订实验 |
| 同分钟语义验证 | 34 RRx、0 BBB 分类违规、37 个已解析 tie、5 个冲突 | 运行时如何处理 5 个冲突仍存在问题 |
| 当前冻结 cohort | 12 targets，3 checkpoints/target | 共 36 个评分行，但不是 36 个独立天气事件 |
| 正例 | 每个阈值均为 1 个正例 target，即 3 个正例 checkpoint | 两种阈值命中同一事件，不是两份独立验证 |
| 缺失 | 当前 12 targets 均能解析结果 | 只说明这一 cohort，不能推及全部历史/未来覆盖率 |
| LAMP 类别记录 | 152,325 records，CIG/VIS/OBV 各 50,775 | 无法因此宣称拥有原生专业概率基线 |
| LAMP 输入完整性 | 138 个正常 gzip、2 个空下载、2 个不完整恢复前缀 | 记录数可复现，但不能认证完整归档 |

当前 8.33% 是人为选取的 6/6 修订队列试点中的正例比例，不是自然机场天气风险率。恒零概率在这个特定等权 cohort 上的 Brier 为 `1/12`，提示结果容易由一个事件主导。

### 5.2 样本少，不同问题受影响的方式不同

- 预测优劣、罕见事件校准、跨天气过程泛化：一个正例事件显然无法支撑稳健结论。
- 重复信息导致的概率漂移：不依赖正例 Y，本质上需要足够的父状态、有效扰动、重复采样、配对设计和独立过程块。不能从“只有一个正例”直接算出它毫无统计功效。
- 同一目标的多个 checkpoint、两个嵌套阈值、同一父状态的多次抽样都不能当作独立天气过程。
- 当前没有完成足以确定所需样本量的开发期方差估计和确认性设计。不能编造一个看起来合适的 N，也不能“跑到显著为止”。

原方案本来就将 ≤12 目标设为仪器试点，D08 也明确禁止用小 N 做结论性推断。这不是团队从未认识到的小样本问题。真正缺少的是从仪器试点走向可判定研究结论的设计和证据。

### 5.3 阴性结果与“不知道”必须区分

如果预注册的贡献收缩条件是“账本诊断没有提供有用信号”，应先定义有科学意义的效果或等价界限，并有足够精度去判定。小样本没有显著差异不能自动触发“贡献已被证伪”。

当前实现将单次噪声差值的经验百分位区间与 agent 平均漂移比较，这不是平均配对效应的置信区间。报告必须区分：支持有效应、支持实际等价/效果足够小、证据不足。

### 5.4 基线和领域范围

- FOLLOW 和 ValuesBank 当前是 `NOT_TESTED` scaffold；旧版本某项分数不能直接代表新 cohort、新提前量的强度。
- 原生 LAMP 类别不能直接当作概率。研究者可以拟合概率后处理，但必须单独命名、分离训练/校准/评测，并与目标阈值和时点匹配。
- W4 已明确记录“防赢弱基线”要求，包括恒零、气候态、persistence、强后处理和已资格验证的程序预测器。风险不是没人意识到，而是尚未完成当前版本的执行验证。
- D05 延后 3h/6h 后端；20/40 分钟重算预测器也需要资格验证。沿用冻结的一小时预测可以是明确命名的 control，但不能冒充新时点已合格的预测器。
- NHC 尚无可运行的合格拓展实验，不等于领域本身不可用。D02 已纠正“同机构 best track 不可验证”和“没有本地 LICENSE 即不可用”的两种过强推理。
- 单领域可以做有价值的 benchmark；是否必须扩展灾种，应由机制覆盖、独立样本、基线和主张范围决定。

## 6. 十五项已复现实现问题

下表用于中文总览。附录 A 的 F01–F15 给出触发输入、实际输出、文件行号、验证方法和建议修复。`blocker` 表示阻碍有效实验或访问边界的强制执行，不表示已经发生了实际 holdout 泄露。

| ID | 严重性 | 具体问题 | 为什么影响研究 |
|---|---|---|---|
| F01 | blocker | 跨有效窗口的 AMD 丢失 supersession；同窗口不同来源反而可能被连成替代 | 核心诊断标签失真；真实 KSFO 样本中 171 个 AMD 有 155 个被标为 new_observation |
| F02 | blocker | 按全 TAF 窗口统计修订，包含评分结束后的修订；manifest 冻结的是 26–30h 源窗口，disclose 另建 1h 结果目标 | 入选统计不代表实验时段真实发生修订；目标合同未完整冻结 |
| F03 | blocker | STATELESS 只见当前包，APPEND 可见完整历史；runner 绕过 CommitProcessor | 状态比较混入信息量差异；概率 2.5 和错误 forecast_op 可直接进入生效状态 |
| F04 | blocker | LAMP、ASOS、disclose 的 holdout 防护不一致 | 当前上游隔离不能代替入口强制检查；模拟 rehash 后的保护日期 target 会尝试发现归档 |
| F05 | major | 信息等价筛选忽略 information_utility；用噪声单次分布替代配对均值推断 | 有信息的 reissue 被当过度反应；“无法区别于噪声”的统计解释无效 |
| F06 | major | 两份 gzip 恢复的是不完整 DEFLATE 前缀；无 CRC 时可接受被改动但仍可解析的值 | “只缺 trailer、内容完整”的回执错误；覆盖率和完整性被高估 |
| F07 | major | self-hash 与文件存在检查不能防止 disclose 后另名 refreeze；源指纹只含目录名与文件数 | 没有独立绑定的预注册/暴露身份，不能保证事前冻结 |
| F08 | major | commit hash 未包含 forecast_op | 不同生效行为拥有同一身份，破坏哈希链和重放语义绑定 |
| F09 | major | 列表类型字段可崩溃且丢失 attempt；时间验证/排序有漏洞；COPY_BASELINE 无 provider 仍可接受 | 失败分母、时间合法性和 fallback 不可靠 |
| F10 | major | validator 拒绝的 5 个 BBB/receipt 冲突，在 runtime 都能选出唯一赢家 | 报告“未解决”未落实到模型实际使用的数据状态 |
| F11 | major | 相同观测时间的冲突 routine reports 取输入顺序最后一条 | 交换输入顺序即可把同一 target 的 Y 从 0 改成 1 |
| F12 | major | 右删失上下界方向错误，所谓 KM survival 不是实际 product-limit | 可报告数学上不成立的延迟推断；测试也固化了错误期望 |
| F13 | major | 事实正确数按 operation 行统计，分母按唯一 slot | 两次正确操作一个 slot 可得到 correctness_rate=2.0 |
| F14 | major | 单一修订轨迹误判为唯一 ALWAYS_UPDATE；非空但不相关的预测更新可算已采纳修订 | 诊断的可区分性和事实采用率被高估 |
| F15 | minor | D11 guard 检查 wrapper 类型，不严格验证 element/value 语义 | 概率值装入类别 dataclass 可绕过语义边界 |

四个最直接的复现例子：

1. 同一来源原 TAF 有效期 `0112/0212`，之后 AMD 为 `0113/0212`，ledger 输出 `new_observation`，没有应有的版本关系。
2. `KDEN_20230811_12` 因五次 COR 入选，但 COR 都发生在目标开始 12:00 之后，不能支撑 T−60/T−40/T−20 的订正反应评测。
3. 完全相同 commit 的 `SET_PROBABILITY` 与 `KEEP_PROBABILITY` 得到同一 hash，生效概率却不同。
4. 已观测延迟 10，另一条删失于 20，代码给出的“均值上界”为 15；实际第二条若在 100 才响应，均值是 55，直接反例成立。

请不要把所有问题简化成“再多写测试”。需要先确定正确的语义和统计合同，再写能区分正确/错误实现的测试。

## 7. 哪些检查通过了，哪些结论不能由此推出

已完成的验证包括：

- 当前 revision 539 项、DL3R 49 项、外部回归 30 项，共 **618 passed**。
- 额外的 monitoring admission / TAF tasks / aviation 共 **56 passed**。
- 历史 v16-prep 351 passed；v16-datafix 380 passed；历史 manifest 28 passed。
- 实际 `run_disclose()` 运行结果与已提交报告一致，只有生成时间不同。
- TAF 140 份原文 SHA-256 与回执一致；允许读取的 LAMP 文件也与登记 hash 一致。
- 当前 freeze 没有发现直接 ASOS/Y 数据流入选择和排序；错误 self-hash 会在读取结果前拒绝。
- 当前十二目标和 checkpoint 不与 holdout 相交。

本轮审计没有读取或列出 `quarantine_holdout/`，没有打开实际封存日期数据，没有修改数据归档，也没有调用真实预测模型。

这些检查分别证明特定输入下的行为和可复现性，不能推导为：测量已经有效、没有任何未来访问漏洞、历史所有外部操作都合规、模型训练时没有见过历史数据、living 闭环已经运行，或研究新颖性已经得到实证证明。

## 8. 执行记录与历史认知需要纠正的内容

完整过程发现见附录 A 的 P01–P05，主要包括：

- `1768d60b1` 的 README 文档提交没有对应任务回执，区别于之前已经补齐的 RO4 遗漏。
- W2、MP T2、RA2 的若干文件行数与具体 commit 的实际文件不符。
- MP T1 声称排除 outcome tests 后 432 passed，但 shell 展开后的显式文件参数使 `--ignore` 未真正排除那 37 项；真正排除后是 395 passed。
- RA2 的 28 passed/real tests skipped 描述自相矛盾；在历史快照上实际为 28 passed、零 skip。
- 若干回执把已经在祖先 commit 中提交的文件仍描述为“并发、未跟踪”。
- gzip 回执正确复算了记录数，却错误推导为完整内容恢复。
- 外部下载执行报告已经记录过删除旧 TAF run 及对应隔离部分、丢失约二十余请求回执的事件。本次仅核对了这一文档记录，没有检查被保护路径、独立恢复事件或声称知道精确丢失量。
- 项目 briefing 对归档位置、两个 PATCH_LOG 的关系，以及“每一个历史问题都已覆盖”的描述存在误差。

评价这些问题时需要区分错误、遗漏、证据不足和已披露限制；不能仅据此推断动机或故意造假。保留历史记录、追加更正优于覆盖旧回执。

## 9. 文献邻近性：已知什么，仍需 Pro 核对什么

| 工作 | 当前可用证据 | 应怎样使用 |
|---|---|---|
| FutureSim | 审计阅读本地论文全文，原复核包含代码位置 | 同题多次预测、固定网格、carry-forward、持续/无状态对比有先例 |
| BLF | 原始方案中的近邻分析 | 结构化 belief 不能作为本项目首创；正式比较仍应核对原论文 |
| StateMemBench | 审计阅读本地全文 | 当前/被替代状态与脚本化策略已有先例 |
| BeliefShift, arXiv 2603.23848 | 本轮独立获取摘要，描述 2,400 条人工标注对话轨迹 | 不能轻描淡写成只有模型自评；摘要不足以证明其所有能力边界 |
| EvoSCM, arXiv 2609.01526 | 本轮独立获取摘要，提到 DiscoverPhysics 实验 | 原文“只是未验证协议”的判断需要更新；不因此自动判定它覆盖天气版本评测 |
| CORE/PERSIST, arXiv 2609.12373 | 出现在旧定位文档；本轮获取失败 | 未完成独立内容验证 |
| FinCacheServe 2607.26076、Belief-State Engine 2609.10036、Persistent Robotic Maps 2606.00318 | 本轮只获得搜索结果标题/编号，正文获取失败 | 仅作为后续检索候选，不是已证实的直接竞品 |

新的检索受到网络失败限制，没有建立“2026-09-19 到 09-21 没有任何新增竞品”的结论。Pro 若可联网，应重新核对标题、版本日期、全文方法和任务合同，并优先寻找真实版本化证据、物理结果、信念修订评分和持续前瞻评测的交叉工作。

请使用能力矩阵比较，而不是要求某一篇论文必须同时具有本项目所有模块才算覆盖。附录原文中的“未占据”“强”等评价都是待批判的历史判断。

## 10. 请 ChatGPT Pro 优先回答的问题

### Q1. 用户的 living 目标有没有在后续收窄中丢失？

请给出对 living 的操作性定义，明确区分 episode 内动态、持续采集和持续前瞻评测。评估现有材料足以支持什么，不足以支持什么。指出原目标、D01 主线与当前交付之间的对应关系，避免把“不作为创新”误读为“不需要实现”。

### Q2. 这个项目究竟有什么值得发表的贡献？

请独立判断：是新的评测任务/数据合同、诊断方法、有意义的实证发现、living 基础设施，还是目前只能算工程/数据资源？给出一到两句可辩护的贡献表述，并列出成立所需的证据与最强反对意见。

### Q3. 哪条路线最符合目标与现实？

至少比较：A. 先完成离线证据修订 benchmark；B. living 外层运行机制与语义诊断内层结合；C. 重新把前瞻持续监测作为核心、缩减辅助诊断范围。请明确推荐及理由，而不是平均分配所有方向。

### Q4. 最小 living 闭环应交付什么？

请给出目标生成、合法信息、预测封存、基线执行、结果成熟与修订、异常处理、持续追加、版本化报告的最小合同和验收标准。说明哪些旧模块能复用，哪些必须新建，哪些目前不值得实现。

### Q5. H15 是否足以支撑这个研究？

请评估最后一小时是否拥有足够密度的真实证据修订，以及单领域的独立天气过程是否可形成有效样本。比较扩大时段/站点/过程、改变 checkpoint 设计、资格验证 NHC 的收益和成本。不要仅根据正例数否定不依赖 Y 的诊断，也不要靠重复 checkpoint 虚增 N。

### Q6. 如何设计可判定的实验与统计？

请分别设计预测质量、事实维护、信息等价漂移和持续运行可靠性的分析单位。明确配对方式、weather-process block、模型抽样重复、效果/等价界限、多重比较、缺测和删失。给出用开发数据确定样本量/精度的程序；缺乏方差时不要给出伪精确 N。

### Q7. 如何避免只赢弱基线或制造不公平对照？

请明确同目标、同时点、同合法信息的基线要求，categorical LAMP 的合法用法，旧 values bank 的可复用范围，以及 STATELESS/APPEND/STRUCTURED 应控制什么。解释如何让版本维护正确与概率预测正确分别产生可检验的信号。

### Q8. 审计结论本身有没有误判或过度推断？

请逐项审视 F01–F15，区分必须立刻修复的正确性错误、接口使用前提、尚未实现的研究功能，以及严重性是否合理。请尤其检查 novelty、低正例率与功效、未来 TAF 选择信息、gzip 完整性、语义等价定义和来源权威问题。

### Q9. 下一阶段应该怎样收敛，而不是继续堆工程？

请给出有依赖关系的少量工作包，每包写明目的、可复用模块、交付物、验收证据与停止条件。优先回答哪些缺陷必须在任何新模型运行前解决，哪些可以明确推迟。不要直接生成一个新的大而全 benchmark 架构。

### Q10. 什么结果应该使研究收缩或停止？

区分测量无效、经验结果无效应、样本不足和实际任务价值不足。给出支持继续、支持只发布数据资源、以及应改换问题的证据条件。阴性结果可以是合法终态，但没有显著性不能自动当成证伪。

## 11. 建议 Pro 的输出结构

1. **先给结论**：当前方向是否值得继续，living 是否实际缺位，最推荐的路线是什么。
2. **目标与证据对照表**：原始愿景、批准决策、当前实现、差距、必要性。
3. **独立新颖性评估**：强近邻、真实增量、必须放弃的表述、需要补核的文献。
4. **测量和实验设计**：准确的 estimand、比较条件、样本单位、配对与统计判定。
5. **最小 living benchmark 方案**：可执行的闭环、版本与暴露管理、验收条件。
6. **修复与推进顺序**：少量工作包、依赖、复用、优先级和明确停止条件。
7. **对 Codex 审计的不同意见**：逐条引用证据，清楚说明哪些判断不成立或应降级。
8. **真正需要研究者选择的事项**：只保留会改变研究目标/成本/授权的决策，不把常规实现细节变成提问。

请避免仅复述这份文档。需要在现有事实基础上作出明确判断，并指出缺失证据。不要把待实施建议写成已批准任务，不要默认打开封存集、产生付费模型调用、训练或重新获取数据。

## 12. 范围、保留事项与源码定位

原只读审计已结束。本次用户明确授权的是整理并上传文档，新增文档提交不代表执行了任何审计修复或研究实验。代码、测试、原始归档、原始审计报告和既有回执均保留。

`data_real_v16/` 仍不得写入；`quarantine_holdout/` 和 2025-02-17T00:00Z 至 2025-02-24T00:00Z 的实际封存数据仍不得打开、列出或读取。本文没有封存数据内容。

源码应以审计提交为准，避免将未来分支的修改误认为当时实现：

- [审计代码基线](https://github.com/sisuolv/disastertrace-benchmark/tree/58ff8120aa779c68b7cb902f782c5c66ca3e1833/disastertrace-starter)
- [ledger.py](https://github.com/sisuolv/disastertrace-benchmark/blob/58ff8120aa779c68b7cb902f782c5c66ca3e1833/disastertrace-starter/src/disastertrace/revision_v1/ledger.py)
- [belief_commit.py](https://github.com/sisuolv/disastertrace-benchmark/blob/58ff8120aa779c68b7cb902f782c5c66ca3e1833/disastertrace-starter/src/disastertrace/revision_v1/belief_commit.py)
- [metrics.py](https://github.com/sisuolv/disastertrace-benchmark/blob/58ff8120aa779c68b7cb902f782c5c66ca3e1833/disastertrace-starter/src/disastertrace/revision_v1/metrics.py)
- [manifest.py](https://github.com/sisuolv/disastertrace-benchmark/blob/58ff8120aa779c68b7cb902f782c5c66ca3e1833/disastertrace-starter/src/disastertrace/revision_v1/manifest.py)
- [p1_harness.py](https://github.com/sisuolv/disastertrace-benchmark/blob/58ff8120aa779c68b7cb902f782c5c66ca3e1833/disastertrace-starter/src/disastertrace/revision_v1/p1_harness.py)

GitHub 仓库为私有。如果 Pro 无仓库访问权限，请直接把本 Markdown 作为附件提供。附录 A 已包含所有审计发现的触发场景与验证结果；无法额外读取源码的项目请标为未独立复核。

以下附录保留原始论证，帮助 Pro 对正文提出反对意见，而非仅接收一个已经替它下好结论的摘要。

## 附录 A：完整独立审计报告（英文原文）

源文件：`development/v14_revision_20260919_01/codex_audit_v16/FINDINGS.md`。完整原文，318 行。

源文件 SHA-256：`9ae5620361e11b21f35b85959ee47c83f0d8ad80060346e06e95cda12cd7919a`。

原报告末尾的“仅创建 FINDINGS.md、未提交/推送”描述的是原只读审计阶段。本次是在用户随后明确授权下整理和上传这一份新文档；代码基线未因此修复。

<details>
<summary>展开附录 A 原文</summary>

<!-- BEGIN SOURCE A -->
# DisasterTrace v14-v16 independent audit

Audited 2026-09-21 at `58ff8120aa779c68b7cb902f782c5c66ca3e1833`, including the cumulative history from `fc3ff3c4` and all 101 lines of the authoritative development-root `PATCH_LOG.md`.

## 0. Novelty and research value

### Verdict

**Novel benchmark idea worth pursuing, but the empirical scope must expand and the measurement contract must be repaired before the central claim is testable.** The defensible contribution is a weather-domain evaluation of how agents use operationally versioned evidence, jointly measuring source-state correctness and forecasting quality. It is not a new general method for belief revision, memory, forecasting, or counterfactual attribution. The present twelve-target instrument pilot does not substantiate a benchmark-paper result. It also does not falsify the proposed contribution.

This verdict comes from the original research argument and its nearest neighbors, independently of whether the implementation passes tests. The implementation findings strengthen the practical no-go for inference: several currently computed labels and comparisons fail to measure the constructs that make the proposed contribution interesting. Fixing these defects would restore the ability to conduct the research; it would not itself supply the missing empirical result.

### What remains after subtracting the precedents

I read the original `DisasterTrace_v14_Novelty_Review_and_Consolidated_Plan_20260919_CN.md`, the approved decisions, the subsequent positioning document, and the local FutureSim and StateMemBench fulltexts. The original review's strongest argument is narrower than a five-feature novelty checklist. At a fixed future target, evidence can change in two distinct ways: its operational status can change, and its predictive content can change. A replacement forecast may require removing a stale citation without requiring a large probability change. A repeated copy may require neither. Conversely, an agent can maintain impeccable source references and still forecast badly. An evaluation that distinguishes these cases can reveal failures hidden by a single proper score or an unconditional update-size statistic.

The nearest-neighbor subtraction is substantial:

| Component | What is already established | Defensible residual value here |
|---|---|---|
| Repeated forecasts, external scoring grid, carry-forward | FutureSim already evaluates repeated forecasts and compares persistent and stateless forecasting; its fulltext supports the original review's account. | Operational weather evidence, a specific target contract, and finer timing are a domain implementation. They do not independently establish novelty. |
| Structured beliefs and retained state | The original review correctly treats BLF-style structured belief output as a precedent. | A method arm to evaluate, not a new benchmark principle. |
| Current versus superseded facts and scripted failure policies | StateMemBench's fulltext describes symbolic event programs, current/superseded scoring, and lazy-reader policies. | Grounding such tests in native weather products and relating them to probabilities for a fixed observed outcome. |
| Information-equivalent perturbations | Invariance tests, paired controls, and resampling are established experimental tools. | A defensible equivalence predicate derived from operational provenance, with evidence that it isolates otherwise hidden forecasting failures. |
| Counterfactual continuation | The original review already concedes replay methodology to CAR and related work. | A reproducible implementation constrained to lawful evidence and commit interventions; demonstrated diagnostic usefulness. |

The fact that no paper uses this project's `FormalSession` class is not a scientific distinction. Nor does the absence of a paper containing all five components prove that their combination is non-obvious. The case for a benchmark rests on a new, consequential measurement opportunity: operational revision semantics let us ask whether a probability update is responsive to genuinely new information, stale information, or repeated information. The work becomes more than a repackaging only if this distinction is reliable and empirically changes what we learn about agents.

Two qualifications belong in the research claim itself. First, the fact layer is **operational source currentness and support**, not omniscient physical truth. A current TAF can be wrong about the weather. The outcome layer here is also a particular archived routine report, not continuous visibility everywhere throughout an hour. Second, a mirror or unchanged reissue is not automatically information-free. Independent provenance can supply corroboration; a reissue can extend validity or communicate confirmation. An equivalence test must hold source authority, support, applicability, availability, and reliability-relevant metadata fixed. String equality and a coarse `kind` label are insufficient. These are conceptual requirements even in a bug-free implementation.

### Prior art recheck and its limits

I independently fetched the current arXiv abstract pages for BeliefShift (`2603.23848`) and EvoSCM (`2609.01526`), and issued fresh arXiv searches ordered by newest announcement for belief revision, versioned evidence, belief consistency, and forecasting agents. Some requests succeeded; others timed out or failed at the network gateway. The date-filtered search for September 19-21 did not succeed. Consequently this is a fresh, bounded literature check, not an exhaustive assurance that nothing new exists.

BeliefShift remains a meaningful overlap. Its abstract describes 2,400 human-annotated conversational trajectories, temporal consistency, contradictions, evidence-driven revision, and BRA/DCS/CRR/ESI metrics. That is enough to reject a broad claim that evaluating evidence-responsive belief revision is new. It does not establish that BeliefShift evaluates calibrated probabilities against a fixed physical weather outcome or derives operational supersession from native product fields. The narrower DisasterTrace distinction therefore survives this check. The tracked positioning document's characterization as merely "model self-evaluated belief" is too dismissive for the evidence I could verify: the abstract explicitly describes human annotation. I did not verify BeliefShift's complete implementation and do not infer absent capabilities from its abstract alone.

EvoSCM's current abstract describes causal-model hypothesis maintenance through experiments and evaluation on DiscoverPhysics with improved predictions. That does not make it a direct weather-versioning competitor, but it does make the tracked positioning document's dismissal as an unvalidated protocol unsupported by the current abstract. Its relevance is to the boundary around causal hypothesis revision and intervention claims. Neither BeliefShift nor EvoSCM is newly published after the September 19 review; these checks correct the strength of the existing comparisons rather than announce a new post-review competitor.

The successful exact-phrase searches also returned FinCacheServe (`2607.26076`, dependency-consistent reuse over mutable enterprise documents), Belief-State Engine (`2609.10036`, planning under partial observability), and Belief Consistency Between Foundation-Model Evidence and Geometric Perception in Persistent Robotic Maps (`2606.00318`). I verified their search-result titles/identifiers, but attempts to retrieve their abstracts failed. They are unassessed candidates, not evidence that the gap is closed. The CORE/PERSIST (`2609.12373`) abstract request also failed; its listing in W4 is not independent verification of its contents.

No September 19-21 publication eliminating the narrow contribution was established by this audit. That finding must not be rewritten as "no newer prior art exists." The positive argument for value is the measurement distinction above, not a failed search. Before a paper submission, the comparison should use a capability matrix rather than the requirement that a competitor reproduce the whole project. In particular, source-version semantics outside weather and belief maintenance against non-linguistic observations deserve explicit comparison.

### What categorical-only LAMP changes

The archive and registered records inspected here supply categorical CIG/VIS/OBV guidance. They do not supply the native probability comparator anticipated in the original H15 baseline table. This materially weakens readiness for a claim about performance against professional probabilistic forecasts. A category is not a calibrated probability for `visibility < 5000 m` or `< 1000 m`, and category thresholds, forecast support, and issuance times must align before even a deterministic comparison is valid. Fitting a probability mapping can be legitimate, but the mapping is a separately trained research baseline, with its own calibration data and uncertainty.

The risk of "beating a weak baseline" is real. The original table labels FOLLOW weak and reports a much stronger historical one-hour program bank. Those old results do not establish baseline strength on this new cohort, at these three checkpoints. In the current harness, FOLLOW and ValuesBank are `NOT_TESTED` stubs, so their presence in a registry is not an executed contemporary comparison. An implementation-only win against always-zero or a hand-built TAF mapping could say little about useful forecast improvement.

There is, however, clear awareness on record. `repo/plan/plan_v16_0920/NOVELTY_POSITIONING_v16_CN.md:62` has an explicit checklist against weak-baseline wins: always-zero, development-period climatology, persistence, a qualified program bank, strong postprocessing, separately named product types, and qualification of the 20/40-minute predictors. The briefing's implication that this concern has gone unrecognized is incorrect. W4 is a synthesis of earlier concerns, not a data-driven demonstration that the current archive meets them.

A native probability product is not logically necessary for the narrower semantic benchmark. A well-qualified, strong statistical postprocessor using exactly the same lawful information can be a serious comparator. Carrying a frozen one-hour bank forecast forward is also a legitimate explicitly named control, but it does not confer qualification on a newly recomputed 20- or 40-minute model. The project should separate three claims: detecting evidence-handling failures, improving probability forecasts, and outperforming an operational probability product. The first may be useful even if the agent loses the forecasting comparison. The third is unavailable with this archive alone.

### Scope: narrow by approval, insufficient for a result

The practical implementation is currently an H15 last-hour pilot with checkpoints before one routine-report target slot. D05's deferred three/six-hour backends and the absence of an implemented qualified NHC experiment remove the easy route to a broader empirical claim. They do not automatically destroy a benchmark paper. One domain can suffice if it offers enough independent weather processes, operational revision types, credible baselines, and reproducible diagnostic findings. A second domain is evidence of transfer, not a substitute for validity in the first.

It is also inaccurate to present all this narrowness as an unnoticed retreat. The original review's section 1.2 explicitly says the at-most-twelve-target pilot is an instrument check, not statistical sufficiency. D08 at `RESEARCH_DECISIONS_v14_20260919.yaml:118` explicitly prohibits conclusive inference from small N. D02 made H15 the sole primary pilot and relegated NHC to qualification. D05 explicitly deferred the longer-lead fit. The current shortfall is that the instrument has not yet demonstrated the conditions needed to progress, not that an approved twelve-target definitive study unexpectedly became too small.

I also reject the stronger inference that NHC is scientifically unusable because the forecasting agency supplies best track or because a local LICENSE file is absent. D02 expressly corrects those two earlier arguments (`RESEARCH_DECISIONS_v14_20260919.yaml:39`). Operational archive completeness, issue-time provenance, target matching, redistribution terms, and mature outcomes still require qualification. An incomplete local implementation is not proof of impossibility. No NHC model run or new acquisition is needed to acknowledge this distinction.

More consequential than the domain count is whether the pilot actually exposes the intended semantic transitions. I recomputed the frozen manifest's selection from the real TAF archive. It ranks revisions over the whole TAF validity group, including revisions after the forecast target starts. For `KDEN_20230811_12`, all five counted corrections occur after 12:00; for `KDEN_20230826_18`, all four occur after 18:00. Neither supplies a scored correction in the declared pre-target checkpoint interval. The exact selected source-window groups have no visible package at either of their first two checkpoints under the declared two-minute lag. Earlier overlapping TAF windows can still provide evidence, so this is not a claim that agents receive no TAF at all. It means the selection statistics do not demonstrate the intervention coverage claimed for the pilot. Adding model calls to this cohort would not repair that mismatch.

### Sample size, dependence, and what can actually be learned

I reran the disclosure entry point against allowed ASOS files into a temporary output and independently checked the positive raw observation. There are **12 distinct targets, one positive target, and zero missing targets** at each threshold. The three positive checkpoint labels are repetitions of the same KDEN event. The 1 km and 5 km thresholds select that same event; they are nested outcomes, not independent replications. Thirty-six checkpoint rows, or seventy-two rows after stacking thresholds, cannot be treated as that many independent event trials.

This is inadequate for a general claim of forecasting superiority or robust rare-event calibration. Always-zero has mean Brier `1/12 = 0.08333` on this particular complete, equally weighted cohort. A comparison can be dominated by what happens on one weather event. Repeated sampling of the same twelve targets reduces Monte Carlo uncertainty about a model's behavior on those targets, but does not create new weather processes. A weather-block interval must reflect dependence across checkpoints, thresholds, nearby times, and stations affected by the same system. The disclosed 8.33% is also the prevalence of a selected 6/6 revision-enriched pilot, not an estimate of natural airport-event prevalence.

The prompt's suggested inference from low positive prevalence to no power for the duplicate-drift experiment needs correction. R2's drift under information-equivalent evidence does not require `Y=1`, or indeed Y at all. It can detect a large within-state response on negative-outcome episodes. Relevant quantities are the number and diversity of parent states and weather blocks, the number of qualifying interventions, the pairing design, repeated draws, and variance of the paired contrast. No exact power number follows from the positive count alone. It would be equally unjustified to declare R2 adequately powered because there are many commits.

For a defensible R2 experiment, define the unit as a registered parent state at a fixed external clock, with the same lawful information and model settings. Generate an identity branch and an information-equivalent perturbation branch; separately repeat identity branches to estimate stochastic variability. Record parent, intervention, clock, model, prompt, and draw identities. Estimate a paired effect across states, with weather-process dependence respected. Freeze a scientifically meaningful equivalence margin and the effect/precision criterion before confirmation. A central percentile range of individual noise draws is not a confidence interval for the average paired effect, and an observed mean inside that range is not evidence of equivalence.

The proposed falsification condition is consequently **not evaluable as a confirmatory decision under the present instrument design**. This is stronger than "the experiment has not run," but different from logical undecidability or a claim that every possible effect is undetectable at N=12. A huge deterministic implementation failure can be visible at N=1. What cannot be inferred is that a non-significant small experiment has shown the labels unhelpful. Positive evidence, a sufficiently precise practically-null result, and an imprecise result must remain distinct outcomes. Only the second can support the proposed contraction of the research claim on a prespecified equivalence criterion. D08 already flags small-N inference; W4 flags interval and pairing deficiencies. I found no completed variance-based design establishing adequate precision for this frozen cohort.

### What would make the claim testable

The next useful deliverable is a validated instrument and an exposure-accounted development study. First, bind the actual one-hour target, thresholds, report policy, normalized checkpoint weights, and source hashes before outcome resolution. Validate ledger labels against a deliberately diverse sample of real native revision chains, including cross-window amendments, conflicting receipt order, cancellations, late arrivals, and informative reissues. Count qualifying changes within legal checkpoint exposure, rather than counting all revisions to a long forecast window. A diagnostic enrichment cohort can be appropriate, provided it is explicitly distinguished from the population used for forecasting-performance estimates.

Second, give stateless recomputation access to the full lawful prefix with the same tools and budget as persistent arms, validate all commits through the same effective-state path, and run deterministic positive and negative controls. Demonstrate that fact repair without probability change, probability change without fact repair, stale adoption, and equivalent duplication yield distinct intended measurements. An oracle ledger supplies a fact-layer reference; it does not supply oracle probabilities. A trap-policy name is a behavioral consistency label, not proof of the agent's cognitive mechanism.

Third, qualify and execute the baseline suite on the same target/time support, estimate development variance and block structure, and register a sample range that can resolve the chosen effect or equivalence margin. Expand independent episodes and revision types before demanding additional domains. If H15's last hour rarely contains the needed transitions, a lawful checkpoint redesign or a qualified additional domain becomes necessary for the diagnostic question. It should not be replaced by selecting favorable outcomes after disclosure. The already disclosed twelve targets remain development material after any repair or reselection.

Finally, keep the confirmation set closed until methods, target contracts, statistics, and exposure identity are frozen. More observations from one confirmation weather system do not fix a shortage of independent systems. D09 itself requires enough independent processes; the existence of a reserved week is not proof that it meets that requirement. These are prerequisites for a future authorized experiment, not actions taken in this audit.

My research recommendation is to continue instrument repair and data qualification, with a narrower contribution sentence: **a benchmark for distinguishing operational evidence maintenance from probabilistic forecasting skill under real weather-product revisions**. Publication as that benchmark requires empirical discrimination and qualified comparisons. If corrected, adequately precise experiments show no useful distinction, a data/reproduction-resource contribution remains legitimate. Today's passing tests and sparse disclosure establish neither that success nor that negative conclusion.

Research references used above: the original review is under `/mnt/afs/260010168/extreme_weather_benchmark/plan/plan_v14_0919/`; its main contribution table is at line 148, experiment matrix at line 224, and scoring contract at line 243. Approved decisions are in the adjacent `RESEARCH_DECISIONS_v14_20260919.yaml`. W4 is `repo/plan/plan_v16_0920/NOVELTY_POSITIONING_v16_CN.md`. Public checks: <https://arxiv.org/abs/2603.23848> and <https://arxiv.org/abs/2609.01526>; the additional identifiers above have only the explicitly stated search-result verification.

## 1. Overall implementation assessment

The checkout reproduces its current test totals and most archive/selection counts, but it is **not ready for research inference or an unguarded new disclosure run**. The semantic ledger still misses cross-window amendments, the manifest selects revisions outside scored exposure and incompletely freezes the outcome contract, the harness confounds memory with information access and bypasses commit validation, and several statistical outputs have invalid interpretations. Real LAMP prefixes are recoverable, but their completeness was falsely certified. I found no direct ASOS/Y input to the existing freeze selection, no demonstrated modification of the committed manifest after disclosure, and no demonstrated holdout exposure in the audited revision runs. Those clean observations do not establish enforcement of the stronger preregistration and holdout guarantees. All fixes below are proposals; none was applied.

Path convention for sections 2-3: `src/`, `scripts/`, `tests/`, and `data_contracts/` are relative to `repo/disastertrace-starter/`. `PATCH_LOG.md` means the development-root receipt, outside Git. A **blocker** prevents the intended valid experiment or enforcement of its access boundary; it does not assert that a prohibited incident has already happened.

## 2. Concrete findings, ordered by severity

### F01 - blocker - Native supersession is still broken across validity windows

**Locations:** `src/disastertrace/revision_v1/ledger.py:295`, `src/disastertrace/revision_v1/ledger.py:374`; `tests/test_revision_ledger.py:1197`.

The active classifier groups predecessors by exact station/start/end, not provider/product lineage. I parsed an original `KJFK 011130Z 0112/0212` TAF followed by same-provider `TAF AMD KJFK 011330Z 0113/0212`: the amendment becomes `new_observation`, with no predecessor. Conversely, matching the exact window while changing provider/series incorrectly produces `amendment_supersedes`. The declared `ProductLineage` machinery is not used by this path. On real KSFO January 2023 data, 155 of 171 native AMD packages become `new_observation`; not every AMD necessarily has an available predecessor, but this scale and the controlled pair disprove the claimed general repair. The cross-window regression explicitly accepts either `supersedes` or `first`.

**Proposed fix:** implement explicit provider/series lineage and native replacement applicability across windows; keep unresolved ancestry explicit. Assert the exact expected predecessor, including a negative different-provider case. Do not redefine all AMDs as replacements without checking lineage.

### F02 - blocker - Manifest selection does not freeze the intended scored experiment

**Locations:** `src/disastertrace/revision_v1/manifest.py:284`, `src/disastertrace/revision_v1/manifest.py:315`, `src/disastertrace/revision_v1/manifest.py:433`; `scripts/build_episode_manifest_v16.py:379`.

Revision counts include every AMD/COR in the full source window. Recomputed real examples: the five corrections selecting `KDEN_20230811_12` occur at 12:29-14:28, after the 12:00 target start; the four selecting `KDEN_20230826_18` occur at 18:26-20:45. They cannot generate the scored pre-target correction response. This is future-TAF selection information, not demonstrated ASOS leakage. Separately, the manifest freezes 26-30-hour TAF validity ends and generic target IDs; disclosure ignores those ends and creates new one-hour, threshold-specific H15 targets. The outcome definition is therefore supplied by disclosure code rather than the frozen target contract.

**Proposed fix:** separate source windows from complete hashed outcome contracts, including threshold, report policy, one-hour support, and scoring-weight normalization. Select diagnostic transitions using lawful checkpoint availability and verify their counts. Treat this already disclosed manifest as development material after any redesign.

### F03 - blocker - Method arms have different information and bypass effective-state validation

**Locations:** `src/disastertrace/revision_v1/p1_harness.py:495`, `src/disastertrace/revision_v1/p1_harness.py:517`, `src/disastertrace/revision_v1/p1_harness.py:818`.

At step two of a two-entry run, I captured STATELESS receiving only entry B and `(history=None, state=None)`, APPEND receiving A+B, and STRUCTURED receiving a summary. There is no shared retrieval interface giving stateless recomputation the lawful prefix. Thus the comparison changes information access as well as state retention. Both runner paths also update state directly from returned dictionaries without `CommitProcessor`. A method returning `UPDATE`, `forecast_op=KEEP_PROBABILITY`, and probability `2.5` produces final probability `2.5` in all three arms. The same-sequence test does not constrain per-decision information or admission.

**Proposed fix:** expose the same lawful evidence/tool view to every arm, vary only state representation, and use one validated commit/effective-state path with explicit invalid-attempt retention and fallback. Test equality of accessible information at each decision and rejection/carry-forward of invalid probabilities.

### F04 - blocker - Holdout guards are not enforced at all archive entry points

**Locations:** `scripts/build_lamp_categorical_registry_v16.py:99`; `scripts/build_episode_manifest_v16.py:231`; `src/disastertrace/revision_v1/outcome_wiring.py:221`.

The LAMP builder reads every `lav-*.body` in its configured archive, without calendar exclusion. The ASOS loader checks a literal path substring before canonicalization and has no date gate. Disclosure checks a self-hash but does not validate holdout overlap before archive discovery. In a temporary, correctly self-hashed manifest containing a February 18, 2025 target, actual `run_disclose()` attempted the glob `KSFO/2025-02/*/*.body`. I intercepted `Path.glob` before archive access: no protected path was listed or opened. Existing upstream separation protects the current inputs; these entry points do not enforce the policy themselves.

**Proposed fix:** apply shared configured date and canonical-path guards before discovery or reads, validate target/checkpoint overlap at disclosure, and use allowlisted archive inputs. Test only synthetic temporary trees, including symlinks. This finding is an access-control defect, not evidence of an actual historical breach.

### F05 - major - Invariance measurement misclassifies informative reissues and compares unlike statistical quantities

**Locations:** `src/disastertrace/revision_v1/metrics.py:745`, `src/disastertrace/revision_v1/metrics.py:855`, `src/disastertrace/revision_v1/metrics.py:937`; `tests/test_revision_trap_policies.py:674`.

The overreaction filter ignores `information_utility`. A `no_change_reissue` explicitly marked `extension`, with probability moving from 0.1 to 0.8, contributes 0.7 to supposedly information-free drift. Separately, `[0, 0.2] * 500` yields noise mean 0.1 and interval `(0, 0.2)`; agent mean 0.15 is reported "Cannot distinguish from noise." These are individual-draw percentiles, not uncertainty in a paired mean; repeating the sample does not shrink the interval. The fixture tests replay deterministic policies or feed scalar arrays, without enforcing parent/time/intervention pairing.

**Proposed fix:** require an explicit semantic-equivalence predicate and implement the paired, block-aware contrast described in section 0. Report descriptive distributions as such until that estimator exists; do not use marginal percentiles or pointwise tolerance alone to claim practical equivalence.

### F06 - major - Recovered LAMP files are incomplete, and the fallback can accept changed payloads without CRC validation

**Locations:** `src/disastertrace/revision_v1/lamp_categorical.py:110`, `src/disastertrace/revision_v1/lamp_categorical.py:135`; `tests/test_revision_lamp_categorical.py:306`; `PATCH_LOG.md:98`.

I parsed the gzip headers and independently decompressed the raw DEFLATE streams. Both real files have `decompressor.eof == False`, disproving "intact stream, missing trailer only":

| File | Compressed bytes | Recovered bytes | Records | Last recovered selected-station cycle |
|---|---:|---:|---:|---|
| `lav-202505-0000z.body` | 343,913 | 13,899,291 | 792 | May 22, 00Z |
| `lav-202505-0600z_proxy.body` | 375,913 | 14,634,307 | 837 | May 24, 06Z |

The first ends mid-header at `" KA"`. In a synthetic stored-DEFLATE bulletin, changing VIS `1` to `7` triggers CRC failure with the trailer intact, but removing the trailer makes the parser accept the changed value. Cutting inside the payload also silently yields a partial bulletin's six records. The "corrupt middle" test actually corrupts the gzip magic header.

**Proposed fix:** distinguish checksum-verified, complete-DEFLATE/unverified-trailer, and incomplete-prefix recovery; record completeness and coverage, and reject or explicitly flag partial cards. Regex validity cannot authenticate numeric content. Preserve the raw archive unchanged.

### F07 - major - A self-hash and filename overwrite check do not enforce preregistration

**Locations:** `scripts/build_episode_manifest_v16.py:109`, `scripts/build_episode_manifest_v16.py:132`, `scripts/build_episode_manifest_v16.py:231`; `src/disastertrace/revision_v1/manifest.py:480`.

I altered/reordered manifest content in memory, recomputed `self_sha256`, and obtained successful integrity verification. `run_freeze()` only refuses an existing output filename and explicitly recommends deletion to regenerate; a different filename bypasses the check, with no disclosure/exposure state consulted. Disclosure has no independently anchored expected hash. The archive fingerprint hashes only directory name and file count; content changes preserving that count are invisible. The loaded calendar's valid sidecar is not checked against the manifest's recorded calendar hash.

**Proposed fix:** anchor run/cohort identity and expected manifest hash outside the replaceable document, record exposure, and reject another freeze for an exposed run regardless of filename. Hash the full source receipt/content inventory, target contracts, configuration, and relevant code version. No post-disclosure alteration of the actual committed manifest was demonstrated; the defect is in enforcement.

### F08 - major - Commit identity omits a field that changes effective behavior

**Locations:** `src/disastertrace/revision_v1/belief_commit.py:248`, `src/disastertrace/revision_v1/belief_commit.py:700`.

`forecast_op` is omitted from `compute_commit_id()`. I submitted otherwise identical valid commits with a 0.8 forecast, one `SET_PROBABILITY` and one `KEEP_PROBABILITY`, to fresh stores. Both are accepted with the same hash (`75ef8e0674e78d575ea49a71a326488a3818ce6fcfd5fb266b1b86e3192f782c`), but one sets the forecast and the other leaves it absent. Thus a parent/commit hash does not uniquely bind the transition semantics needed by replay.

**Proposed fix:** include every behavior-defining field, particularly `forecast_op`, in a versioned canonical identity. Add a test that the two commands have distinct IDs and the expected distinct effective states; preserve old identity semantics explicitly when reading historical records.

### F09 - major - Malformed submissions escape the failure denominator; time and baseline validation have additional holes

**Locations:** `src/disastertrace/revision_v1/belief_commit.py:69`, `src/disastertrace/revision_v1/belief_commit.py:178`, `src/disastertrace/revision_v1/belief_commit.py:493`, `src/disastertrace/revision_v1/belief_commit.py:543`, `src/disastertrace/revision_v1/belief_commit.py:594`.

An otherwise valid JSON commit with `operation=[]` or `episode_id=[]` raises uncaught `TypeError`, leaving zero attempt-log entries. The timestamp regex accepts `2023-99-99T25:61:61Z` on the unbound processor path. Lexicographic monotonicity rejects `00:30Z` after `01:00+01:00`, although it is thirty minutes later. `UPDATE` plus `COPY_BASELINE_SNAPSHOT` is accepted without a baseline provider and silently produces no forecast; only outer `FOLLOW_BASELINE` checks the provider. These were separate direct processor reproductions.

**Proposed fix:** validate all JSON field types before hashing/indexing, parse and normalize actual UTC instants, require providers for every operation that uses them, and ensure malformed attempts are durably represented with the registered fallback. Test both schema rejection and denominator retention.

### F10 - major - Runtime tie resolution accepts the five conflicts the validator rejects

**Locations:** `src/disastertrace/monitoring_v1/providers/versions.py:8`, `src/disastertrace/monitoring_v1/providers/versions.py:64`; `scripts/validate_dl3r_semantics.py:380`.

The validator checks BBB order against receipt order; the shared runtime selector does not. I recomputed the five real `bbb_contradicts_receipt_order` conflicts and passed their rows to the runtime resolver. All obtain a winner. Example: KSFO August 2024 selects AAB/receipt 226 over AAC/receipt 225. The other four occur in KSFO December 2024 and June 2025, KDEN June 2024, and KJFK July 2023. The validator's unresolved status is therefore not an enforced runtime property. I did not establish that any of these five belongs to a selected manifest target.

**Proposed fix:** share one resolution policy and carry unresolved conflict status into the ledger/current-product path, or make successful semantic validation a compulsory gate with explicit exclusions. Assert validator/runtime agreement on these real allowed examples and synthetic conflicting-order pairs.

### F11 - major - The unique-hour outcome changes when equal-time input rows are reordered

**Locations:** `src/disastertrace/revision_v1/outcome_wiring.py:166`, `src/disastertrace/revision_v1/outcome_wiring.py:352`.

Routine selection retains multiple rows at the same timestamp. Outcome resolution stably sorts by observation time and takes the last row, granting input order authority. I supplied two same-station routine reports at 12:56, one `10SM` and one `1/4SM`; swapping their input order changes the mature binary outcome from 1 to 0 for the same `iem_routine_unique_hour.v1` target. No correction/authority rule justifies that choice.

**Proposed fix:** collapse semantically identical duplicates, use explicitly registered native correction/version authority for genuine replacements, and mark unresolved disagreements missing/conflicting rather than selecting by row order. Freeze this rule in the outcome policy and test permutation invariance. This demonstrates an outcome-resolver defect, not an observed error in the current twelve disclosed labels.

### F12 - major - Right-censoring bounds and the advertised Kaplan-Meier quantity are mathematically wrong

**Locations:** `src/disastertrace/revision_v1/metrics.py:1102`; `tests/test_revision_metrics.py:982`.

One observed duration 10 and one duration censored at 20 produce lower bound 10 and upper bound 15, with an interpretation that the true mean lies between them. A permissible eventual second duration of 100 gives mean 55. Censoring time supplies a lower constraint, not a finite upper bound. The observed-only mean is not a general lower bound either. With observed 10, censor 5, censor 20, the function reports KM survival `1/3`; the actual product-limit value at time 10 is `1/2` because the early censor has left the risk set. A regression asserts the erroneous finite upper-bound calculation.

**Proposed fix:** implement actual risk-set/product-limit calculations and a preregistered restricted-mean horizon, or report the valid lower bound and unbounded upper tail. Correct the mathematical expectations in the tests.

### F13 - major - Fact correctness can exceed 100 percent

**Location:** `src/disastertrace/revision_v1/metrics.py:688`.

`compute_fact_layer_correctness()` counts correct operation rows in its numerator but unique required slots in its denominator. Two correct operations on slot `x`, with required slots `{"x"}`, produce `correctness_rate=2.0` and coverage 1.0 in a direct call. Repeated commits can therefore inflate the co-primary semantic score even though D08 explicitly rejects counting operations as compliance.

**Proposed fix:** evaluate one registered effective decision per slot/checkpoint, with an explicit policy for repeated/conflicting updates; alternatively reject duplicate slot decisions at this API boundary. Test duplicates and successive correct/incorrect decisions against the frozen scoring unit.

### F14 - major - Trap diagnostics still claim unique policies and adoption without sufficient evidence

**Locations:** `src/disastertrace/revision_v1/trap_policies.py:357`, `src/disastertrace/revision_v1/trap_policies.py:364`, `src/disastertrace/revision_v1/trap_policies.py:438`.

I generated a one-amendment trajectory with `apply_policy()`: ORACLE_LEDGER, LATEST_MENTION, DOUBLE_COUNT, ALWAYS_UPDATE, and STALE_HOLD all emit UPDATE, yet `identify_policy()` reports ALWAYS_UPDATE for every one. On a lone baseline update it similarly labels several table policies FOLLOW_ONLY. The shortcuts check distinction from some policies, not uniqueness among all policies. Separately, an UPDATE merely citing an amendment and containing a nonempty forecast update for an unrelated target with probability 0.5 is marked `properly_adopted=True`.

**Proposed fix:** compare the complete observed trajectory against every policy and report ambiguity unless exactly one matches. Compute adoption from validated effective facts and relevant evidence support, not any nonempty update payload. Retain policy consistency as a diagnostic rather than inferred internal mechanism.

### F15 - minor - D11's guard validates the wrapper, not categorical field semantics

**Locations:** `src/disastertrace/revision_v1/lamp_categorical.py:47`, `src/disastertrace/revision_v1/lamp_categorical.py:89`, `src/disastertrace/revision_v1/lamp_categorical.py:344`.

The guard correctly rejects ordinary foreign record classes/dictionaries. However, dataclass type hints are not runtime constraints: I constructed `LampCategoricalRecord` with element `PROB_VIS` and value `0.75`, and `assert_not_probabilistic()` accepted it. The parser also accepts arbitrary non-whitespace values under CIG/VIS labels. A future adapter that puts a probability into the categorical wrapper bypasses the advertised semantic boundary.

**Proposed fix:** validate product identity, enum membership, and native categorical value domains at construction/parsing and at the registration boundary, while explicitly handling documented missing sentinels. Keep native and derived probabilistic products separately named. No current probability conversion was found in the categorical archive path.

## 3. Checks that passed, and what they establish

### Recomputed tests and historical claims

I used the project's virtualenv, disabled bytecode and pytest's cache provider, and checked module resolution against the checkout/snapshot under test. Historical snapshots were extracted with `git archive` into automatically cleaned temporary directories, without checkout or branch changes.

| Verification | Independently observed result |
|---|---|
| Current `tests/test_revision_*.py` | 539 passed |
| Current `tests/test_validate_dl3r_semantics.py` | 49 passed |
| Both standing external review regression files | 30 passed |
| Combined current standing invocation | 618 passed, four existing deprecation warnings |
| Current monitoring admission, TAF tasks, and aviation suites | 56 passed |
| Historical v16-prep tip `494db21e0`, revision suite | 351 passed |
| Historical v16-datafix tip `19a4bdf04`, revision suite | 380 passed |
| Historical v16-MP T1 `a6c14b596`, exact recorded glob/ignore command | 432 passed; collection includes all 37 outcome tests |
| Same snapshot, with outcome test file actually omitted from arguments | 395 passed |
| Historical RA2 `e129c41c8`, manifest tests | 28 passed, zero skipped |

The current standing command, from the code root, was:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src ../../.venv/bin/python -B -m pytest \
  -o addopts= -q -p no:cacheprovider \
  tests/test_revision_*.py tests/test_validate_dl3r_semantics.py \
  ../../review_v15/regressions/test_review_a.py \
  ../../review_v15/regressions/test_review_b.py
```

The additional legacy files were `tests/test_monitoring_admission.py`, `tests/test_monitoring_taf_tasks.py`, and `tests/test_monitoring_aviation.py`. I did not claim to rerun the entire legacy repository or the separate support-bridge suite, which loads historical external bundles.

### Real-data recomputation and isolation

- **TAF counts and content identity:** using an explicit 35-month allowlist that excludes all of February 2025 before opening files, I recomputed 140 files, 41,386 packages, and 60 skips. All 140 body hashes match their receipts. KSFO January 2023 yields 303 packages: 171 AMD, 124 original, eight COR. The validator independently yields 34 RRx, zero BBB-kind violations, 37 resolved ties, and five conflicts. These receipt totals are reproducible; F01 and F10 concern what the runtime does with them.
- **Frozen selection:** recompiling the allowed archive and running selection in memory reproduces the stored twelve-target order and its selection statistics. The stored manifest self-hash is `e83cf42d0c51548971e6684fd65e459041a600bd6dd5e22edb823ec231e2b719`. The weakness of the input fingerprint and the scientific mismatch of those statistics are separate findings.
- **Direct Y isolation in freeze:** I read all of `manifest.py` and the builder script and traced their imports and inputs. The freeze path uses TAF packages and calendar/configuration data. Imported METAR parsing definitions perform no outcome-data read at import time. I found no ASOS values feeding selection or order. This is a data-flow conclusion about the current implementation, not proof of an immutable import-based security boundary.
- **Disclose ordering:** a mismatched manifest self-hash makes actual `run_disclose()` exit before ASOS discovery. The positive guard test and the correctly rehashed holdout counterexample in F04 were both exercised with archive discovery intercepted. Hash validation precedes outcomes, but a valid self-hash does not certify authorization or preregistration.
- **Actual disclosure entry point:** I ran `run_disclose()` on the existing allowed cohort with its output in a temporary directory. It exits successfully and matches the committed disclosure after normalizing only the generated timestamp: twelve targets, zero missing, one positive target/three positive checkpoint rows for each threshold. The raw KDEN February 22, 2024 16:53 routine METAR contains `1/4SM ... SN FG VV004`, independently supporting the positive target. The old 0%-positive/33%-missing disclosure is not the current result.
- **Current holdout exclusion:** the selected targets and checkpoints avoid the frozen interval; the main TAF iteration skips February 2025. For LAMP I read only the registry's explicitly named allowed files plus its named empty-download entries, after excluding protected dates/paths. No holdout directory or real holdout file was listed or opened.
- **LAMP counts:** the permitted 142-file rescan reproduces 152,325 records: KJFK 38,088 and each other station 38,079; each of CIG/VIS/OBV has 50,775 records. Tracked body hashes match. There are 138 clean gzip inputs, two genuine empty downloads, and two incomplete recovered prefixes. Record-count agreement does not establish complete downloads.
- **D11's existing useful boundary:** the categorical path does not convert category numbers to probabilities, and the guard rejects ordinary foreign record objects. F15 describes the narrower unchecked-field bypass.

### Test quality and cumulative scope

The suites contain real behavioral constraints; green status is not uniformly vacuous. Reviewed examples cover target-contract immutability, HOLD carry-forward, bad probabilities, future-evidence canaries, missing-outcome handling, WMO month/day boundaries, SPECI parsing, receipt-order acyclicity, and refusal of malformed archive/header inputs. The tests also demonstrate why green is not a certification of the research contract: the cross-window test permits the wrong predecessor status, censoring tests encode an incorrect bound, the harness checks the sequence seen over a run rather than equal information at each decision, and the gzip corruption fixture exercises the header rather than an altered decodable payload. The R4 scalar-noise fixtures do not implement a paired stochastic experiment. The manifest disclosure tests do not substitute for the actual entry-point run above.

I examined the full 36-commit cumulative chain and per-round changed-file lists, and classified added archive references and output operations. The only modification to an existing monitoring engine module is the documented RO1 change to `monitoring_v1/providers/versions.py`. The revision scripts' normal outputs are reports/contracts, not source archive bodies. Documentation also describes separately authorized acquisition writes; those instructions are not evidence that the read-only revision scripts executed them. No protected publication/sibling-tree write appears in the audited Git changes. Configurable output paths are not a general filesystem write prohibition, and Git cannot certify historical untracked/external writes or read access.

## 4. Process discrepancies beyond the briefing's retrospective

### P01 - minor - A post-signoff documentation commit has no task receipt

Commit `1768d60b1` adds the 78-line `repo/disastertrace-starter/README_V16_RECEIPT_ORDER_V1.md`. I matched the full commit chain against the entire authoritative log: there is no task receipt describing that file/commit. The RO-V entry ends its verified chain at `bd65f072f`; the later appearance of `1768d60b1` as another round's base is not a task receipt. This is separate from RO4's already caught and repaired omission. The initial scaffold and the early contract/scorer commits have identifiable task coverage even where an individual hash is omitted, so I do not classify those as missing tasks.

**Correction:** append a dated retrospective receipt describing the actual documentation-only change and its relationship to signoff. Do not invent an original contemporaneous verification.

### P02 - minor - Test-scope and file-size claims do not match the committed artifacts

The following values were independently recomputed from the specified commit's file bytes or historical test runs:

| Receipt | Claim | Observed |
|---|---|---|
| W2, `PATCH_LOG.md:45`, `d92ee8bfa` | Compiler/test files: 297/909 lines | 353/963 lines; the later W5 account corrects these |
| MP T2, `PATCH_LOG.md:74`, `d6eb43b8c` | Outcome source/test files: 498/650 lines | 484/969 lines |
| RA2, `PATCH_LOG.md:96`, `e129c41c8` | Manifest/script/test files: 525/350/590 lines | 626/475/759 lines |
| MP T1, `PATCH_LOG.md:72`, `a6c14b596` | 432 tests while excluding outcome wiring | Exact command includes its 37 tests; true exclusion gives 395 passed |
| RA2, `PATCH_LOG.md:96`, `e129c41c8` | 28 passed described as 23 unit plus five skipped real tests | 28 passed, none skipped in this environment; the file contains seven guarded real-integration tests |

The MP discrepancy is reproducible pytest behavior: the shell expands `tests/test_revision_*.py` into explicit filenames, so `--ignore=tests/test_revision_outcome_wiring.py` does not remove that explicitly requested file. Thus 432 is a reproducible total, but the claimed scope is false. The historical run and an explicit-argument omission distinguish this from an invented numerical mismatch.

MP T1 also describes the outcome file as untracked even though T2 commit `d6eb43b8c` is already its ancestor. RA3-fix similarly calls RA2 files concurrent/untracked while naming already-committed RA2 `e129c41c8` as its parent. Git ancestry proves the committed state; an earlier working-session narrative cannot be substituted for that state in a final receipt. These inconsistencies do not show that unrelated files were actually overwritten.

**Correction:** use command-generated counts and file inventories bound to the exact commit, record collected/skipped/passed separately, and distinguish observations from earlier workspace stages from verification of the committed result.

### P03 - major - The gzip recovery signoff certifies something its verification did not establish

`PATCH_LOG.md:98` and the final signoff at line 101 state that the real DEFLATE payloads were intact and only trailers were missing. F06 disproves this directly on the receipt-matching real files. The record counts 792/837 were verified correctly; promoting prefix recovery into complete-content recovery was the error. Checking regexes and a damaged magic header cannot establish payload integrity or completeness.

**Correction:** issue an explicit correction to the receipt and registry completeness claims, preserving the old record for provenance. Report verified prefix coverage separately from complete archive coverage. No archive repair or redownload was attempted in this audit.

### P04 - major audit-trail limitation - The separate acquisition record discloses a deletion omitted from the briefing

I read the outer `plan/plan_v16_0920/EXECUTION_STATUS_DL_v16_CN.md`. At line 50, section 5.1 records deletion of an abandoned TAF v1 run directory and its corresponding quarantined portion, permanently losing receipts for roughly twenty-plus requests. Sections 5.2-5.4 also disclose host-serialization overlap, reporting a substitute parser as pyIEM validation, and same-run proxy retries/status-file omission. These are documentary disclosures from the separately authorized acquisition session, not independently reconstructed filesystem events in this audit. I did not inspect any quarantined path to investigate them.

This materially limits the briefing's statements that its retrospective covers every previously caught defect and that no task in the project's history was authorized to write the archive. The revision rounds were read-only consumers; the separate acquisition session necessarily wrote it and records a preservation violation. Code diffs cannot disprove that reported interactive deletion, and a top-level directory mtime cannot establish that all descendants were preserved.

**Correction:** include these disclosed incidents and the permanent provenance gap in the consolidated project history, clearly distinguishing acquisition authority from downstream read-only authority. Do not claim forensic recovery or exact lost-request totals from the surviving Git history.

### P05 - note - Briefing path/history corrections

The Git root is `.../v14_revision_20260919_01/repo/`; the code root is its `disastertrace-starter/` subdirectory. Tracked planning files are under `repo/plan/`. The actual archive is `/mnt/afs/260010168/extreme_weather_benchmark/data_real_v16/`, not a sibling of this checkout under the development directory. The code-root `PATCH_LOG.md` is not unrelated ancient history: commit `43794bc50` introduces it during R3, and development-root receipt line 27 already acknowledges its wrong placement. The development-root log remains authoritative. These corrections matter for reproducibility, but the already disclosed wrong-log placement is not counted as a newly discovered violation.

### Audit preservation

This audit created only `codex_audit_v16/FINDINGS.md` as a persistent project output. It made no source, test, contract, planning, receipt, archive, or Git-history changes; no commit, branch, or push was performed. Synthetic reproductions, historical snapshots, and generated disclosure output used temporary directories. `data_real_v16` was read-only throughout, and the holdout was never opened or listed. Final repository status, including untracked files, is clean and HEAD remains `58ff8120aa779c68b7cb902f782c5c66ca3e1833`; the report is outside that Git tree. The lack of a historical violation in a Git diff is reported only as that bounded observation, not as proof that every past external action obeyed policy.
<!-- END SOURCE A -->

</details>

## 附录 B：原始 v14 新颖性复核与整合方案（完整原文）

源文件：`plan/plan_v14_0919/DisasterTrace_v14_Novelty_Review_and_Consolidated_Plan_20260919_CN.md`。完整原文，409 行。

源文件 SHA-256：`1dd3c3068c7b31785812b4313b970d4dcd4d3a6789ff0284e5c045567449147a`。

这是历史材料快照；其中的状态、自报结论、引用与权限描述须按其日期理解，并结合正文和附录 A 的更正，不能直接当作当前有效授权或独立核实事实。

<details>
<summary>展开附录 B 原文</summary>

<!-- BEGIN SOURCE B -->
# DisasterTrace v14：五份重设计方案的新颖性复核与统一执行计划

日期：2026-09-19。状态：`DRAFT_FOR_RESEARCHER_REVIEW`。作者：Claude（Fable 5.1）会话，基于 `plan/plan_v14_0919/` 下 1 个 md + 5 个 zip（已解压到 `extracted/`）。

本文是**复核与规划**，不是执行回执。本轮做了：通读五份方案；核对本机 v13 代码快照与结果回执；逐字读取最强近邻 FutureSim 的已克隆源码与论文全文、BLF 与 StateMemBench 论文全文；派出三个代理分别克隆参考仓库、逐条核验五份方案引用的 arXiv 论文、检索 2026 年 7–9 月新近工作。本轮**没有**修改任何仓库源码、运行模型、下载天气数据、重跑科学实验。

---

## 0. 一页结论

**新颖性判定：五份方案共同收敛的方向是对的，但它们的"剩余 gap"表述仍偏宽。按代码和论文逐项核对后，可辩护的贡献比它们写的更窄、也更具体。**

1. **已被完整覆盖、不能作为贡献的**：live 题库刷新（FutureX/ForecastBench/Claw-Eval-Live）；同一未来问题在外部时间轴上反复修订概率并按"截至当日最近一次预测"评分（FutureSim 代码 `environment/scorekeeping.py::get_prediction_as_of` 已实现，论文附录 C.3/C.4 已有 time-weighted score 与 update-size 指标）；"每轮从头判断 vs 持续修订"对照（FutureSim Fig. 6/11）；anchoring/过度自信诊断（FutureSim Fig. 5、冻结语料消融）；memory 消融；结构化 belief state（BLF）；当前事实 vs 被替代事实的闭池评分（StateMemBench）；干预后重跑后缀归因（CAR）；天气工具型 agent（AgentCaster/EarthVerse/SIREN）。
2. **尚未被占据、且能用实验证明必要性的**（本文推荐的主贡献）：
   - **语义证据账本（semantic evidence ledger）**：对每个证据包程序化标注 `new_observation / amendment_supersedes / lossless_duplicate / mirror / late_superseded / no_change_reissue`，来自 TAF/METAR/NHC 产品的原生版本字段（AMD/COR/CNL、issue/valid/available 时间、supersedes 链）。FutureSim 的新闻流没有这种可程序判定的信息等价关系；StateMemBench 有替代关系但是对话状态、无未来概率与物理结果。
   - **在同一固定物理目标上，把两层真值分开评**：事实层（哪个版本当前有效，可程序判定）与概率层（proper score 对成熟观测结果）。已有工作只做其一。
   - **配对不变性/合规性诊断**：信息等价包下的概率漂移（与重复采样噪声底比较）、替代版本到达后的失效引用比例、迟到旧版本的错误采用；这些是 FutureSim 的 update-size 指标做不到的"有条件"版本。
   - **程序陷阱策略（trap policies）**：借 StateMemBench 的 lazy-reader-policy 思想，定义 LATEST_MENTION、DOUBLE_COUNT、IGNORE_AMD、STALE_HOLD、FOLLOW_ONLY、ALWAYS_UPDATE 等确定性伪策略，把 agent 轨迹与陷阱策略的一致度作为可程序核验的失效标签，而不是 LLM judge。
   - **同父状态的合法反事实重放**（复用已有 `FormalSession.fork` / `AdmissionEngine.fork`），干预对象限定为账本中的证据包（扣留/延迟/替换为旧版）与模型自写 commit（Actual/Masked/Edited）。
3. **论文定位**：一个"评测合同 + 数据切片 + 诊断集 + 实证发现"的 benchmark 论文；不是新评测范式。若 §8 的 R1–R3 实验显示信息等价包下 agent 与 stateless 重算无可辨差异、且账本标签对概率损失无解释力，则贡献收缩为"领域数据与复现资源"，不靠堆灾种或调用量补救。
4. **本机现实**：v13 代码快照在（75 MB，60.6k 行、203 个测试文件），但 H15 原始 TAF/METAR 与年度 bank **不在本机**；快照测试收集有 46 个错误（缺兄弟脚本 + 缺 PIL/shapely）。真实数据 pilot 在本机是 BLOCKED，需从执行机同步（§3）。
5. **首批建议**：P0-00～P0-07（§10），全部 CPU、无 API、无下载，可在本机以合成 fixture 起步；真实 episode 编译等数据同步后再做。研究者需先冻结 §11 的 12 项决定，其中 D01（主问题）、D02（首个领域/目标）、D05（多提前量后端）三项阻塞 P1。

---

## 1. 五份方案的共识与分歧

五份包（`DisasterTrace_SOTA_Audit_Redesign`、`DisasterTrace_SOTA_Redesign(0/1/2)`、`DisasterTrace_Review_and_Codex_Package`）都是 2026-09-19 对 `sisuolv/disastertrace-benchmark@fc3ff3c` 的审阅，均由不同 LLM 会话独立生成，材料高度重叠。

### 1.1 共识（五包一致，本文采纳）

| 议题 | 一致结论 |
|---|---|
| 旧主线 | "共享查询预算下比下一份公告更快"不再作为主问题；query-only selector（M01）降为获取器消融 |
| 新主线 | 同一固定未来目标、证据持续到达/订正/替代时的概率修订与事实状态维护 |
| 真值 | 专业预报（TAF/NHC advisory）是输入和动态基线，不是 Y；Y 是成熟观测（IEM 例行站报、best track） |
| 评分 | 固定外生时间网格、每目标权重和为 1、HOLD 沿用、Brier/log 主分；RV 求和望远镜消去，不作轨迹主分 |
| 轨道 | Natural agent 为主表，硬预算为 controlled 消融 |
| 首个领域 | H15 机场低能见度；气旋为第二/替代 |
| 禁止 | 不宣称 first-live / first-memory / first-causal-replay；不 reset；不删旧结果；不无授权调 API/下载/GPU |
| 现状 | v13 B00/C00/B02/M01 完成；M01 LLM 未超过 fixed-hash/RR；3 正例；13 次 not_sent 未诊断；年度 bank 仅 1 h 资格 |

### 1.2 分歧与本文取舍

| 议题 | 各包立场 | 本文取舍 | 理由 |
|---|---|---|---|
| 剩余 gap 的表述 | Audit 包："证据有效性约束下的持续信念修订"；(2) 包："状态携带 vs 同信息重算的增益/退化"；(1) 包："源版本可核验的概率修订"；(0) 包同 (1) | 收窄为 §0 第 2 条：**语义证据账本 + 两层真值 + 配对不变性诊断 + 陷阱策略 + 合法反事实重放** | FutureSim 代码/论文已含"持续修订 + stateless 对照 + update size"，只讲"修订/状态"仍会被指为换数据 |
| pilot 规模 | 6 / 8–12 / 12–24 个 episode 不等 | 仪器 pilot ≤12 目标 × 3 checkpoint；不作统计充分性 | 与 v13 计划 C01 的 6×3×2×4=144 行上限兼容 |
| H15 多截止 | 各包均指出 1 h bank 不能冒充 3/6 h | 两条并行：①最后一小时内窄网格（T−60/−40/−20 min）作仪器 pilot；②多提前量后端仅在 D05 批准后另建 | 数据现实决定；不要为 pilot 先训练新模型 |
| 第二领域 | 一致 NHC 优先 | 同意，但建议**提前到 P0 做数据资格核查**（不训练、不调模型） | TC advisory 周期天然提供"同一目标多次修订 + 强专业基线 + 非稀有正例"，H15 的 1 h bank 反而缺这个（§7.4） |
| 归因方法 | 各包借 CAR | 同意，但**先用陷阱策略做程序化失效标签**，再做重放干预 | 便宜、无 API、可先在合成 fixture 上验证 |
| 视觉/16 类 | 一致 PAUSE | PAUSE | — |

---

## 2. 证据边界与本轮实际核查

| 核查项 | 结果 | 位置 |
|---|---|---|
| 五份方案 | 全部通读（4 份 22 节主报告、2 份 Codex 计划、gap 矩阵、commit schema、决策表、指标参考） | `extracted/` |
| v13 代码快照 | 存在；`src/disastertrace` 35 个子包、60,608 行、203 个测试文件 | `publication/v13_completed_20260917_01/snapshot/disastertrace-starter/` |
| v13 结果回执 | `RESULT_VALIDATION.json passed=true`，`full_scientific_replay=false`，`new_model_calls=0`；M01 12 方法 Brier 与 LATEST_PROGRESS 一致 | 同上 `publication/v13_completed_20260917/RESULT_VALIDATION.json` |
| selector 合同 | 确认只输出 `query_order`；系统提示写明"Forecasts are produced by the frozen program at fixed slots" | `monitoring_v1/selector_contract_v2.py` |
| H15 结果政策 | 确认 `final_archived_routine_report_not_continuous_physical_truth` + `iem_routine_unique_hour.v1` | `monitoring_fixed_v1/outcome_policies.py:29-42` |
| 多截止资格 | v13 `revision_readiness` 只读核验：年度 bank 315,792 机会全部 lead=1.0 h；引擎可表达多截止，预测器无 3/6 h 资格 | `plans/v13_revision_readiness_20260916_01/README_CN.md` |
| 测试收集 | `pytest --collect-only`（不写缓存）：46 个收集错误，全部为快照缺少兄弟脚本（`artifacts/autonomy_10h_v1/*.py`、`plans/v8_*/scripts/*.py`、`publication/autonomy_review_20260909/*.py`）或缺 `PIL/shapely/shapefile` | 用 `disastertrace-starter/.venv`（Python 3.10.12，pytest 9.1.1） |
| 原始数据 | 快照内无 TAF/METAR 原文与年度 bank（最大文件为 7.5 MB 结果 zip）；`development/disastertrace-next/.../artifacts` 11 GB 为 p1–p14 旧实验产物，按文件名未找到 TAF/METAR/bank | — |
| 本地 dev 仓库 / GitHub 分支结构 | `development/disastertrace-next` 在 `36082c4`（`next-phase-v1`，2026-09-08）且有未提交改动（README.md/RESULTS_20260909.md/disastertrace-starter/{BLOCKERS,CURRENT_PHASE,DECISIONS}.md 等，未触碰）。2026-09-19 用本地代理（见下一行）重试后 `git ls-remote` 不再超时：**GitHub 有两条独立线**——`main` 现为 `a23f73a`（2026-09-07，比 `fc3ff3c` 更早、目录结构完全不同，无 `monitoring_v1`/`monitoring_fixed_v1`，不含本文所有复用接口）；`next-phase-v1` 现为 `fc3ff3c4333915d10062ca6eaeb3163235cc111c`（正是本文已审阅、本节复用接口清单所依据的提交）。P0 工作区（development/v14_revision_20260919_01/）已改为从 `next-phase-v1`@`fc3ff3c` 建分支，不用 `main` | — |
| 网络代理 | `/mnt/afs/260010168/gee-network`（Mihomo，`proxy.sh start` 已由 CCI 启动脚本自动执行）把 `github.com`/`codeload.github.com` 等域名路由到已选节点；`source /mnt/afs/260010168/init-proxy.sh` 即可在当前 shell 设置 `HTTP(S)_PROXY=http://127.0.0.1:17890`。`api.github.com` 经代理仍 403（非网络问题）。已用于重跑 `git ls-remote` 与克隆官方 GEO-Bench-VLM（见 §12） | `/mnt/afs/260010168/gee-network/README.md` |
| FutureSim 代码 | 已克隆（`reference_code/futuresim@908322f`，2026-06-25）；**仓库根目录无 LICENSE 文件，pyproject 无 license 字段**；论文页标 CC BY 4.0 仅覆盖论文 | `reference_code/futuresim/` |
| 论文全文 | FutureSim 2605.15188、BLF 2604.18576、StateMemBench 2608.19652 全文已抓取并去标签 | `literature/fulltext/` |
| 代理任务 | 克隆 26 个仓库、核验 46 个 arXiv ID、检索新近工作 | 结果见 §4 与 `literature/` |

未做：未重跑任何 v13 实验；未读 Notion 与会议逐字稿原文（五包已转述，本文只引用其转述）；未核验每个上游仓库的许可证法律效力。

---

## 3. 仓库与本机现实对新计划的约束

1. **科学基线不变**：v13 完成结果（B00/C00/B02/M01）继续只读；新轨在新目录、新 ID 下追加。
2. **可复用引擎已在**（快照路径 `src/disastertrace/`）：
   - `monitoring_v1/formal_session.py`（`FormalSession`：绑定来源/执行/结果政策、不可覆盖保存、评估器结果禁入）
   - `monitoring_v1/session_checkpoint.py`（`capture_session/restore_session/SessionCoordinator`：整控制器检查点）
   - `monitoring_fixed_v1/admission.py`（`AdmissionEngine.fork/restore`、`TypedOpportunity`、`score_admitted`）
   - `monitoring_fixed_v1/outcomes.py`（`OutcomeRegistry`、`ComparisonContract`、`experiment_spec`）
   - `monitoring_fixed_v1/adoption.py`（outcome-blind 采用规则）、`monitoring_v1/state.py`（`MonitoringEngine`、`Baseline`、版本化预测）
   - `monitoring_v1/event_loop.py`（确定性时钟）、`monitoring_v1/scoring.py`（全机会 Brier、缺失界）、`monitoring_v1/targets.py`（`TargetSpec/Opportunity/canonical_hash`）
   - `monitoring_v1/providers/{aviation,taf_timeline,versions}.py`（TAF/METAR 原生解码、发布时间+声明延迟）
3. **需要新建的薄层**（§10）：语义证据账本编译器、belief commit 适配器、固定网格轨迹评分器、陷阱策略库、干预注册表。不建第二套 runner。
4. **数据阻塞**：本机没有年度原文链与 bank。P0 中所有"真实 episode"任务在本机标 BLOCKED，直到从执行机同步 `plans/v13_followup_20260916_01` 的数据目录或获得等价导出；合成 fixture 与 schema/测试工作不受影响。
5. **测试基线**：新代码的测试应能在快照 + `.venv` 下收集；对 46 个已知收集错误按 node 记录为 `pre-existing-missing-file/dep`，不计入新工作失败，也不为它们重建旧脚本。

---

## 4. 文献核验（代理结果）

原两个后台代理因网关模型不可用崩溃（`claude-fable-5-1` / `crs.hkust-gz.asia` 500 错误，与本机网络无关），未产出目标文件。本节由后续一轮直接核验补齐（复用两代理崩溃前留下的 `literature/raw/` 中间产物：47 条已解析 arXiv API 记录、35 个仓库存在性检查），完整结果见 `literature/arxiv_verification_20260919.md`（+`.json`）与 `literature/new_related_work_search_20260919.md`。

**(a) 46 个 arXiv ID 核验**：五包引用去重后共 46 个 arXiv ID，全部逐条核验标题与发布/最新版本日期。**0 个真实的标题/ID 错配**——没有发现某方案引用的 ID 实际指向不相关论文。发现 1 处编号惯例但非引用错误（`2608.00012` Obshazard-bench 的 ID 前缀是 8 月号段，但 arXiv API 返回发布日期为 2026-06-24，判断为审核队列延迟，标题与五包引用一致，直接查询已确认 `totalResults=1`）。

**(b) 官方代码定位**：更正了两处早前存在性检查（只查“仓库是否存在”，未查“是否官方”）留下的误判——① `microsoft/STATE-Bench` 不是 StateMemBench 的代码，而是另一个不相关的微软基准（“STATE-Bench: Benchmark For Enterprise Workflows”），StateMemBench 论文正文的相关工作对照表把两者列为并列的不同条目；StateMemBench 论文虽称“We release StateMemBench”，但仍未定位到其官方仓库。② `CrystalArchitect/blf-forecaster` 存在，但其 README 明确自述为非官方的“from-scratch reimplementation”，与 BLF 作者 Kevin Murphy 无关联，且无 LICENSE 文件；BLF 官方代码同样未定位。新确认两个官方仓库：STALE → `icedreamc/STALE`（README 自证“our paper”，有 LICENSE）；Who&When-Pro → `whowhenpro/whowhen_pro`（经官方项目页 `literature/raw/whowhenpro.html` 确认，无 LICENSE）。SIREN、CMB（Calibrating Criterion Revision）两篇经网页检索仍未找到公开代码。

**(c) 2026-07 至 09 新近工作检索**：四个方向（预测/信念修订、闭池符号事件记忆、反事实/因果重放归因、航空/热带气旋 LLM agent）均未检索到能整体复现本方案残余新颖性组合（真实版本化证据台账 + 两层真值 + 配对不变性诊断 + 确定性陷阱策略 + 绑定 FormalSession 的同父重放）的新条目，**新颖性判定（§6）维持不变**。但发现两条需要收窄表述边界的中等威胁：① BeliefShift（arXiv 2603.23848，信念一致性/漂移基准）与“两层真值+配对不变性诊断”的动机重叠，但没有程序可验证的证据台账标签、没有真实气象版本字段；② 反事实重放技术本身在 2026-05 至 08 已密集出现（CAR 之外还有 CausalFlow 2605.25338、When-Failures-Propagate 2608.20627、REFLECT 2606.09071、AgenTracer 2509.03312、DoVer 等共 6 篇），是拥挤赛道——§7/§10 描述"同父反事实重放"时应明确落点是"证据台账标签 + FormalSession/AdmissionEngine 既有 fork 语义的绑定"，不是重放技术本身首创。候选第二域（热带气旋/NHC，见 §7、D02）未发现直接竞争条目，可行性判断不受影响。

---

## 5. 最强近邻的代码级与论文级对照

### 5.1 FutureSim（arXiv 2605.15188，2026-05-14；`OpenForecaster/futuresim`）

已确认（源码 + 论文）：

| 能力 | 证据 | 对本项目的含义 |
|---|---|---|
| 同一问题在外部日期轴上反复提交/修订 | 论文 §3.1 "Agents may submit and revise forecasts while a question is active"；`env.py::submit_forecast` | "同目标多轮修订"不是贡献 |
| 按日网格取"截至当日最近一次预测"评分（= 固定网格 + HOLD 沿用） | `environment/scorekeeping.py::compute_daily_active_scores` 调用 `history.get_prediction_as_of(aid, effective_eval_date)` | 固定网格 + carry-forward 已有实现；我们只能在**网格粒度（分钟/小时）与目标物理支持**上不同 |
| time-weighted score、peer score、update size | 论文附录 C.3/C.4；`updater.py` 输出 `tw_score`、`avg_submission_tv_to_prev` | 修订幅度指标已有；我们的 overreaction 必须是**条件于账本标签**的版本 |
| stateless（每题结算前一天单独作答）vs 持续修订 | 论文 Fig. 6/11："evaluating each question independently one day before its resolution does not improve BSS" | 五包的 E1/X1/X2 有直接先例，须引用并把它作为已知结果 |
| anchoring / 过度自信 | Fig. 5（test-time adaptation）；冻结语料消融（"updates just keep reinforcing confidence without new evidence"） | "无新证据时不应更新"已有观察；我们的增量是**信息等价包（重复/镜像/同义重发）**而非"无新文章" |
| memory 消融 | Fig. 5 右 | 已有 |
| 动态人群基线 | Polymarket 对照（Fig. 4） | 专业预报基线对应此角色 |
| 泄漏与沙箱 | 附录 A.4、B.3、B.5 | as-of 隔离不是贡献 |
| 自由文本结果 + LLM answer matcher | `environment/ansmatching.py` | 我们用二元/连续物理结果、无 LLM judge：可信度差异，不是新颖性 |

未见于 FutureSim：证据版本/替代/订正语义；事实层单独评分；配对信息等价干预；同父状态后缀重放；分钟级发布时间；稀有事件下的过程分块统计；强领域程序基线。**许可：仓库无 LICENSE 文件，不能 vendor 源码，只能参考接口设计。**

### 5.2 BLF（arXiv 2604.18576，v4 2026-07-12）

单个问题、单一截止（cutoff = forecast date），10 步以内工具循环，每步同时输出动作与 JSON belief（p、confidence、evidence for/against、open questions）；提交概率裁剪到 [0.05, 0.95]；四层泄漏防御；ForecastBench 400 题上 SOTA。**没有**外部时间轴上的多次 checkpoint、HOLD、版本失效或事实层评分。它是"结构化 belief 输出格式"的先例，应作为本项目的一种方法臂（BLF-style），不是竞争 benchmark。官方代码：未定位。`CrystalArchitect/blf-forecaster` 是第三方非官方 reimplementation（README 自述与论文作者无关），无 LICENSE 文件，不可 vendor，仅可作为复现参考。

### 5.3 StateMemBench（arXiv 2608.19652，2026-08）

234 个多会话场景；闭池评分区分 current / superseded / other；五类失效（status/salience/sequence/compound/anti-trap）；场景由**符号事件程序**（值更新、范围例外、承诺、撤回）生成，正确答案由确定性评估器回放得到；**lazy reader policies**（信最新提及、信最频繁、不重算派生值、过早丢弃锚定决定）作为陷阱生成器。没有未来概率、物理结果、专业基线或时间网格。**借用**：把"事件程序 + 陷阱策略"移植为本项目的证据账本 + trap policies（§7.5）。

### 5.4 其他直接近邻（按五包转述，代理核验后更新）

| 工作 | 已覆盖 | 我们不同之处（须实验证明） |
|---|---|---|
| CAR（jaineet17/causal-agent-replay，Apache-2.0） | do(action/observation/context/policy)、后缀重跑 | 干预对象是**合法证据包与模型 commit**，世界是真实历史而非 SCM；复用已有 fork |
| AgentCaster（2510.03349） | 气象多模态工具、查询配额、SPC 专业对照 | 单次预测，无同目标修订轨迹 |
| EarthVerse / SIREN / ObsHazard | 地球科学工具、多阶段预警、多时相观测 | 无固定 Y 的概率轨迹与版本失效诊断 |
| RealBench / EWB / WB-X | 业务预报验证 | 面向 NWP 模型，不评 agent 状态 |
| AFABench | 固定预测器下的信息获取 | 静态特征，无外生更新与版本 |
| Claw-Eval-Live / FutureX / ForecastBench | 题库刷新与结算 | 与 episode 内修订不是同一维度 |

---

## 6. 新颖性判定表

| 候选贡献 | 判定 | 最近邻 | 需要的实验证据 | 若失败 |
|---|---|---|---|---|
| Living 题库 | 已覆盖 | FutureX/Claw/ForecastBench | 不主张 | — |
| 同目标持续修订 + 固定网格 HOLD 评分 | 已覆盖 | FutureSim（代码级） | 不主张；引用为先例 | — |
| stateless vs 持续 | 已覆盖 | FutureSim Fig. 6/11 | 作为复现对照 R1 | — |
| 结构化 belief | 已覆盖 | BLF | 作为方法臂 | — |
| 当前/替代事实评分 | 已覆盖（对话域） | StateMemBench/STALE | 作为事实层评分来源 | — |
| **语义证据账本 + 两层真值 + 配对不变性诊断** | **未占据（本文主张）** | 上述交叉 | R2/R3：账本标签能解释概率损失与失效，且与 stateless 重算有可辨差异 | 收缩为领域数据资源 |
| **陷阱策略程序化失效标签** | 未占据（机制借自 StateMemBench） | StateMemBench | R4：合成 fixture 上定位器召回/精度；真实轨迹上的策略一致度分布 | 只作诊断工具 |
| 合法反事实重放（证据/commit） | 方法已覆盖 | CAR/CMB | R6：no-op 分支逐字节一致；placebo 无效应；真实修复有效应 | 只作工程 |
| 专业基线 vs 观测真值 | 标准原则 | RealBench/EWB | 必要可信度，不列贡献 | — |
| 第二灾种（NHC） | breadth/validation | EarthVerse 等 | R9：同合同迁移 | 仅领域限定 |

**论文贡献句（候选）**：
1. 一个把气象产品的发布/有效/替代语义编译为程序可核验证据账本的固定目标修订评测合同，并公开 H15（与 NHC）真实 episode 切片。
2. 一组配对诊断（信息等价不变性、替代合规、迟到旧版采用、陷阱策略一致度）与同父反事实重放，能把"检索到"与"用对了"与"预测对了"分开。
3. 实证发现：在同一合法信息下，持续状态相对每轮重算与强程序基线在何种账本条件下受益/受损（允许负结果）。

---

## 7. 统一后的科学问题与任务合同

### 7.1 主问题

> 当同一固定未来极端天气目标的证据以真实的发布/有效/替代/重复语义持续到达、专业预报同步更新时，通用 agent 能否维护当前有效事实并保持校准的概率轨迹；其错误能否用证据账本标签与同父重放解释；持续状态相对同信息重算与强程序基线何时受益、何时受损？

### 7.2 Episode 形式

`E = (T, D, L, A, G, Y)`：`T` 固定目标集（entity/space/variable/unit/window/threshold/outcome_policy/target_id）；`D` 证据包序列；`L` 语义账本（每包的 `kind ∈ {new_observation, amendment_supersedes, correction, cancellation, lossless_duplicate, mirror, late_superseded, no_change_reissue, baseline_update}`，`supersedes`、`available_at` 与 `availability_basis ∈ {verified_publication, declared_lag, collector_first_seen}`）；`A` 动作 `{READ, SEARCH, TOOL, COMMIT(UPDATE), HOLD, FOLLOW_BASELINE, RETRACT, WAIT, STOP_ACTIVE}`；`G` 外生评分网格（每目标权重和 1，见 Y 前冻结）；`Y` 评估侧成熟结果（O/P/R 身份、版本、质量）。

`E0 → S0 → E1 → A1 → S1 → … → En → An → Sn → Y`，`S_t = (K_t, P_t, M_t, links)`：`K_t` 事实断言（supported/refuted/unknown/conflict + source_versions），`P_t` 固定目标概率，`M_t` 模型自写记忆。同 episode 内目标不变；滚动新窗口必须新 `target_id`。

### 7.3 Commit 接口（合并 Audit 包 schema 与 (2) 包接口）

```json
{
  "schema_version": "disastertrace.belief_commit.v14-draft",
  "episode_id": "…", "target_id": "…", "parent_commit_id": "…|null",
  "as_of": "server-validated ISO time",
  "operation": "UPDATE | HOLD | FOLLOW_BASELINE",
  "evidence_ids": ["asset@v2", "…"],
  "fact_updates": [{"slot": "taf_current_version", "operation": "SET|RETRACT|KEEP_UNKNOWN",
                    "support_status": "supported|refuted|undetermined|inconsistent",
                    "value": "…", "source_ids": ["…"]}],
  "forecast_updates": [{"target_id": "…", "event_probability": 0.0}],
  "next_action": {"kind": "WAIT|READ|SEARCH|TOOL|STOP_ACTIVE", "until_or_args": "…"}
}
```

规则：HOLD 时 `fact_updates/forecast_updates` 为空且沿用父状态；harness 只做 schema/身份/准入校验与原样保存，不补语义；无效输出保留错误并按预注册 fallback 生效；模型自写状态与系统生效状态分别记录。

### 7.4 首个领域与目标（供 D02/D05 决定）

| 领域 | 固定目标 | 专业基线 | Y | 多次修订来源 | 本机/数据状态 | 建议 |
|---|---|---|---|---|---|---|
| H15 机场能见度 | 站点 + 未来整点 + <5 km（嵌套 <1 km） | TAF 冻结研究映射（FOLLOW，Brier 0.0191，弱）；冻结程序 values bank（F_BASE_ONLY 0.0050，强，仅 1 h）；**建议登记 LAMP 概率产品作为真正的专业概率基线** | IEM 例行唯一小时站报（已有政策） | TAF 每 6 h + AMD/COR；METAR 每小时 + SPECI | 引擎/政策齐全；原始数据不在本机；仅 1 h 预测器 | **仪器 pilot 首选**：先在最后一小时内设 3 个 checkpoint（−60/−40/−20 min，或按 SPECI 到达）；3/6 h 需 D05 |
| H01 热带气旋（NHC） | 风暴 + 固定未来时刻（如 advisory 后 48 h）+ 强度 ≥ 阈值 / 位置误差 | NHC 官方预报（强，误差统计公开） | 冻结版本 best track（HURDAT2，事后分析） | 每 6 h advisory 天然修订同一 valid time 的预报 | `references/nhc_cohort_v1`、`artifacts/nhc_forecast_source_v1` 已有基础；无需新预测器 | **建议提前做数据资格（P0-07）**：它天然满足"同目标多次修订 + 强专业基线 + 非稀有正例"，可作为 H15 多提前量资格失败时的主 MVP |

### 7.5 陷阱策略库（新增，CPU 可做）

确定性伪 agent，读同一账本，输出概率/事实轨迹，用于 (a) 合成 fixture 的定位器验证，(b) 真实轨迹的"策略一致度"标签：

| 策略 | 行为 | 对应失效 |
|---|---|---|
| LATEST_MENTION | 只信最近到达的包，不看版本 | 迟到旧版误用 |
| DOUBLE_COUNT | 对 duplicate/mirror 再次更新 | overreaction |
| IGNORE_AMD | 忽略 amendment/correction | staleness |
| STALE_HOLD | 首个 commit 后永远 HOLD | 迟滞 |
| FOLLOW_ONLY | 永远 FOLLOW_BASELINE | 无自主修订 |
| ALWAYS_UPDATE | 每包都改概率 | 过度修订 |
| ORACLE_LEDGER | 正确处理账本（程序） | 事实层上界（非概率上界） |

---

## 8. 实验矩阵（统一编号，合并五包 E0–E8 / X1–X12）

| ID | 问题 / claim | 固定 | 改变 | 判据 | 数据 | 本机 CPU 无 API 可做？ |
|---|---|---|---|---|---|---|
| R0 | episode 合法性：只用当时信息，未来 canary 不可见 | — | — | canary 全部不可读；文件名/目录/索引无泄漏 | 合成 + 真实 | 是（合成） |
| R1 | stateless full-legal vs APPEND vs STRUCTURED（复现 FutureSim Fig. 6 结论在本域是否成立） | 模型、信息、网格 | 状态携带方式 | 轨迹 Brier、校准、成本 | 真实 | 否（需模型） |
| R2 | 信息等价不变性：duplicate/mirror/no_change_reissue 下概率漂移 vs 重复采样噪声底 | 语义信息、时间 | 有/无等价包 | \|Δp\| 超噪声底的比例；事实 slot 错误率 | 真实 + 合成 | 部分（陷阱策略、噪声底需模型） |
| R3 | 替代合规：amendment/late_superseded 下失效引用比例与概率损失 | 同上 | 版本到达顺序 | 事实层合规率；概率层 Brier 差 | 真实 | 否 |
| R4 | 陷阱策略定位器：合成已知失效 fixture 上的召回/精度；真实轨迹的策略一致度分布 | 账本 | 策略 | 定位器指标；一致度 | 合成 + 真实 | 是（合成） |
| R5 | commit-use：Actual / Masked（长度匹配 placebo）/ Edited（合法事实辅助）/ Oracle-ledger（特权诊断） | 父状态、信息 | commit 内容 | 后续 F 变化；Masked 降分不单独证明语义使用 | 真实 | 否 |
| R6 | 合法反事实重放：扣留/延迟证据、替换为旧版；no-op 分支逐字节一致 | 父状态、后续策略、种子 | 单个证据包 | EU(e\|s,γ) 分布；placebo 零效应 | 真实 | 部分（no-op 与程序臂） |
| R7 | Natural vs Controlled（B1/B2/B3） | 来源宇宙、基线 | 预算 | 质量–成本 Pareto；cap-hit 率 | 真实 | 否 |
| R8 | 专业/程序基线：FOLLOW、LAMP（若登记）、values bank、气候态、恒零 | — | 基线 | 全分母 Brier | 真实 | 是（若数据同步） |
| R9 | 独立过程 / 第二领域（NHC）迁移 | 冻结方法 | 过程块 / 领域 | 预注册；过程级区间 | 真实 | 部分（数据资格） |

顺序：R0/R4/R8（本机可起步）→ R1–R3（主问题）→ R5–R6（归因）→ R7/R9（范围）。不做全因子笛卡尔积；负结果是合法终态。

---

## 9. 指标合同（简式，公式沿用五包，指出先例）

- 轨迹主分：`Q = (1/N) Σ_j Σ_k w_jk · L(p_eff(j,t_k), Y_j)`，`Σ_k w_jk = 1`，网格与权重见 Y 前冻结；`p_eff` 取最后一次合法生效预测（HOLD 沿用；先例：FutureSim `get_prediction_as_of`）。
- 相对动态基线：`Δ = Q(baseline) − Q(agent)`，baseline 与 agent 同目标同时点。
- RV：`RV_jk = L(p_{k−1}) − L(p_k)`，只作事后描述；求和望远镜消去（五包一致）。
- 事实层：替代合规率、失效引用暴露时长、KEEP_UNKNOWN 正确率（程序参考，闭池评分，先例：StateMemBench）。
- Overreaction：`O = E|p' − p|` **仅在账本标 lossless_duplicate/mirror/no_change_reissue 的包上**，与同输入重复采样的 `E|p'' − p|` 比较（先例：FutureSim update size，但无条件）。
- Timeliness：账本标 amendment 的 `available_at` 到首次合规 commit 的间隔，未响应右删失。
- Calibration：按 lead / 过程分层的可靠性图 + Brier 分解；3 正例级别只描述。
- Cost：`(input/output/cached tokens, tool calls, bytes, wall, reserved, billed, unknown)` 分列；主报告 Pareto。
- 统计：weather-process block bootstrap；缺失 Y 界（不是 CI）；前瞻轨用 Choe & Ramdas confidence sequence。
- EU：`EU(e|s,γ) = E_r[L(rollout(s,¬e,γ,r)) − L(rollout(s,e,γ,r))]`，同父、固定后续策略、多种子。

---

## 10. Codex 执行计划（P0 可立即在本机起步）

通则（五包一致）：audit first；先 red 测试再最小实现；不 reset/clean；旧结果只读；新运行新目录新 ID；每 patch 交付 `Patch ID / claim / reused / files / tests+exit codes / preservation check / status PASS|FAIL|BLOCKED / next`。

### P0 — 合同、账本、评分器、陷阱策略（CPU，无 API）

| ID | 任务 | 复用 | 产物 / 验收 | 状态与依赖 |
|---|---|---|---|---|
| P0-00 | 只读审计：HEAD/快照身份、46 个收集错误按 node 登记、保护清单哈希、数据缺失清单 | — | `AUDIT_BASELINE.json`、`TEST_ROSTER.json`、`PROTECTED_ARTIFACTS.json`、`DATA_GAP.json` | **DONE (2026-09-19)**：Sonnet/simple-executor；4 份 audit JSON 产出；工作区 `development/v14_revision_20260919_01/audit/` |
| P0-01 | 语义证据账本编译器 `revision_v1/ledger.py`：从 TAF/METAR 原生字段（AMD/COR/CNL、issue/valid、SPECI）与 `providers/versions.py` 推导 `kind/supersedes/available_at/basis` | `providers/taf_timeline.py`、`versions.py` | 合成 fixture：每种 kind ≥3 例；未来包不可见；观测时间早但发布晚不入早视图 | **DONE (2026-09-19)**：Opus/complex-executor；22 测试全绿；commit `3d3aeafcd` |
| P0-02 | 目标/结果合同 `revision_v1/contracts.py`：固定 target_id、窗口、阈值、O/P/R；1 h bank 不得标 3/6 h | `targets.py`、`outcome_policies.py`、`OutcomeRegistry` | 移动窗口/阈值被拒；滚动窗口需新 ID；缺报≠负例 | **DONE (2026-09-19)**：Opus/complex-executor；30 测试全绿（累计 52）；commit `138b6b57f` |
| P0-03 | Commit 适配器 `revision_v1/belief_commit.py`：§7.3 schema、HOLD/FOLLOW 语义、原样保存、父哈希链、fallback 标注 | `SessionCoordinator`、`adoption.py` | HOLD 不改 p；无效输出留错误；commit 被下一步实际消费（哈希对账） | **DONE (2026-09-19)**：Opus/complex-executor；36 测试全绿（累计 88）；commit `c08f314e9` |
| P0-04 | 固定网格轨迹评分器 `revision_v1/metrics.py`：Q、Δ、RV、事实层、条件 overreaction、缺失界 | `scoring.py`、(1) 包 `METRIC_REFERENCE.py` | 手算一致；RV 求和=首末差；多提交不改权重；同 Y 多截止一致取值 | **DONE (2026-09-19)**：Opus/complex-executor；32 测试全绿（累计 120）；手算 Q/RV 望远镜和已核验；commit `b44d75fd6` |
| P0-05 | 陷阱策略库 `revision_v1/trap_policies.py` + 定位器 | — | 合成 fixture 上每策略被唯一识别；ORACLE_LEDGER 事实层满分 | **DONE (2026-09-19)**：Sonnet/simple-executor；46 测试全绿（累计 166）；7 策略唯一识别 + ORACLE_LEDGER 满分已核验；commit `9e5e59d6a` |
| P0-06 | 合成 episode fixtures + 未来 canary + no-op fork 逐字节一致测试 | `AdmissionEngine.fork` | 全部 red→green；无写入旧路径 | **DONE (2026-09-19)**：Opus/complex-executor；19 测试全绿（累计 185）；`AdmissionEngine.fork()` no-op 逐字节一致已核验；commit `ce914053f` |
| P0-07 | NHC 数据资格核查（只读）：advisory 版本链、valid time 对齐、best track 版本、许可 | `references/nhc_cohort_v1` | `NHC_READINESS.json`（六格：同目标预报/补充证据/独立结果/时间支持/自动评分/许可） | **DONE (2026-09-19)**：Sonnet/simple-executor；六格评估为 `INSUFFICIENT_LOCAL_DATA`（叙述型 advisory 无 FORECAST VALID 行；fstadv 未拉取；HURDAT2 同源非独立；无许可文件；无接线评分器）——本地数据尚不足以支持 P2-02 NHC 领域 |
| P0-08 | 真实 H15 episode 编译（≤12 目标×3 checkpoint，元数据规则选，不看 Y） | P0-01～03 | `EPISODE_MANIFEST.json`；每 checkpoint 早于窗口；变更/无变更分队列 | **BLOCKED（本机无数据）** |
| P0-09 | 13 次 not_sent 有界诊断（只追加对账，不重试） | `api_transport_v2.py`、`production.py` | 每请求终态或 unknown；预留≠计费 | 需原始回执；本机若无则 BLOCKED |

### P1 — 基线与自然轨（需 D01/D02/D05/D06/D10）

| ID | 任务 | 验收 |
|---|---|---|
| P1-00 | 基线族：FOLLOW（TAF 映射）、LAMP（若登记）、values bank、气候态、恒零、persistence；全部同目标同时点 | 全分母；无测试 Y 参与拟合/校准 |
| P1-01 | 方法臂：STATELESS / APPEND / STRUCTURED（§7.3）/ BLF-style / FutureSim-style harness 移植（仅接口，不 vendor 代码） | 同信息、同工具权限；模型状态哈希可对账 |
| P1-02 | Natural 与 Controlled 配置分离；安全上限、限流、WAIT 不暂停世界 | cap-hit 单列；旧 48 查询标 Controlled |
| P1-03 | 有限真实模型仪器测试（新授权、新 ID、≤12 episode） | 不要求模型胜出；invalid≠HOLD |
| P1-04 | 主对照冻结与运行（R1–R3、R7、R8） | 完整分母；过程级区间；允许负结果 |

### P2 — 归因、第二领域、确认与发布

| ID | 任务 | 验收 |
|---|---|---|
| P2-00 | 干预注册表 + 同父后缀重放（R6）：扣留/延迟/旧版替换、Actual/Masked/Edited commit。与 CAR 代数的映射：扣留/延迟证据 = `do_observation`/`do_context`；替换 commit = `do_context`；换模型续跑 = `do_policy`；重复采样噪声底 = `do_resample`。实现挂在 `AdmissionEngine.fork` 上，不引入 CAR 的 LangGraph/CrewAI 适配器 | no-op 逐字节一致；placebo 零效应；多种子 |
| P2-01 | 陷阱策略一致度在真实轨迹上的分布（R4 真实部分） | 与 R2/R3 损失的关联报告 |
| P2-02 | NHC 第二领域（R9）按 P0-07 资格进入 | 同合同、同评分原则 |
| P2-03 | 确认冻结（方法/统计规则/样本范围先冻结再开未读日历）；发布最小复算包、数据卡、许可清单 | 不跑到显著为止；负结果可发布 |

---

## 11. 研究者必须冻结的决定（合并五包 SD01–SD10 / R1–R8）

见 `RESEARCH_DECISIONS_v14_20260919.yaml`。摘要：

| ID | 决定 | 推荐默认 | 阻塞 |
|---|---|---|---|
| D01 | 主问题采用 §7.1；C2（归因）为解释层；预算为消融 | 采用 | P1 |
| D02 | 首个领域与目标 | H15 例行站报目标做仪器 pilot；NHC 并行做资格 | P0-08/P1 |
| D03 | checkpoint 网格与权重 | H15：最后一小时 3 点等权；NHC：advisory 周期 | P0-04 |
| D04 | 角色 | D（获取+状态+概率）为主 agent；B（对专业预报做概率修正）为数值终点；A（直接预测大气）仅诊断 | P1 |
| D05 | 多提前量后端 | 先不训练；仅在 H15 窄网格 pilot 结束且 NHC 资格失败时另立 | P1-00 |
| D06 | Natural 安全上限与 Controlled 网格 | Natural 主表；B1/B2/B3 消融 | P1-02 |
| D07 | 允许的干预 | 扣留/延迟/旧版替换/commit 三臂；Oracle 仅特权诊断 | P2-00 |
| D08 | 主估计量与样本规则 | 轨迹 Brier + 事实层合规；过程级 block bootstrap；不跑到显著 | P1-04 |
| D09 | 确认集与暴露规则 | 旧 Bay 周继续关闭；方法冻结后一次性开放 | P2-03 |
| D10 | 新模型/API/GPU/下载授权 | 每批新身份、预算、截止 | P1-03 |
| D11 | 专业概率基线 | 登记 LAMP（H15）与 NHC 官方预报（TC）为"原生概率/确定值"基线，与研究映射分名 | P1-00 |
| D12 | 数据同步 | 从执行机同步年度原文链与 bank 到本机，或指定执行机为唯一运行地 | P0-08 |

---

## 12. 开源复用与许可（reference_code）

2026-09-19 克隆代理已把 26 个新仓库（`--depth 1`，直连 github.com 成功，共 5.5 GB）加入 `reference_code/`，与原有 10 个合计 36 个、7.1 GB。完整字段（HEAD sha、提交日期、分支、许可证文件、大小、README 标题）见 `reference_code/_manifest_v14_20260919.json`；可重跑脚本 `reference_code/_clone_refs_v14_20260919.sh`（直连 → gh-proxy.com → ghfast.top → ghproxy.net 回退）。

| 仓库 | HEAD 日期 | 许可证文件 | 与本项目的关系 |
|---|---|---|---|
| futuresim（原有） | 2026-06-25 | **无**（pyproject 亦无字段） | 最强近邻；只借接口/指标定义，不 vendor |
| causal-agent-replay | 2026-07-09 | 无文件；pyproject 声明 Apache-2.0 | 干预/后缀重跑接口参考；复制前需作者确认 |
| StreamMemBench | 2026-07-17 | MIT（832 MB，含数据） | evidence anchor / 阶段诊断 |
| sentinel_environments | 2026-06-08 | MIT（3.1 GB，含 1.6 GB 合成媒体；README 标"pre-release"） | wait/poll/cost 接口 |
| forecastbench / forecastbench-sim | 2026-09-19 / 2026-07-13 | MIT / **GPL-3.0** | 结算/发布参考；sim 为 GPL，只借设计 |
| ComparingForecasters | 2023-10-24 | MIT | confidence sequence（前瞻轨） |
| Claw-Eval-Live | 2026-06-17 | CC-BY-4.0 | 冻结 release 设计 |
| Futurex-Eval | 2026-08-24 | 无（仅评测脚本，无数据） | LLM-judge scorer，不采用 |
| LEAP | 2026-09-02 | MIT | 证据解释与聚合分离的方法臂参考 |
| AgentMemoryBench（=s010m00n 同仓） / MemoryAgentBench | 2026-08-09 / 2026-08-20 | MIT / MIT | 记忆基线对照 |
| ClawArena | 2026-07-01 | MIT（703 MB） | 演化状态情景对照 |
| live-kbench / agents-last-exam | 2026-09-14 / 2026-09-03 | 根目录无 / Apache-2.0 + LICENSE-DATA | 仅 live 题库先例 |
| Obshazard-bench | 2026-06-24 | 无文件（README 称 MIT；仅脚本） | 多时相灾害 VQA 对照 |
| BrowseComp-Plus | 2026-05-28 | MIT | 冻结检索语料的设计 |
| stream-bench / LifelongAgentBench | 2024-10-24 / 2025-05-30 | Apache-2.0 / 无 | 背景 |
| NWP-Benchmark（RealBench） | 2026-05-22 | 无（README 自述草稿；数据/权重未发布） | 业务观测验证原则 |
| weatherbench2 / weatherbenchX（原有） / scores | 2026-09-10 / 09-16 / 09-14 | Apache-2.0 ×3 | 指标、对齐、block bootstrap |
| pyIEM / avwx-engine（原有） | 2026-09-18 / 2026-08-30 | MIT / MIT | NWS/TAF/METAR 解析（PROCESS 工具） |
| DeepResearch-Bench-II / deep_research_bench | 2026-09-11 / 2026-05-11 | Apache-2.0 + DATA_LICENSE / Apache-2.0 | 搜索评测背景 |
| GEOBench-VLM | 2026-05-17 | Apache-2.0 | `Tarekbouamer/GEOBench-VLM` 是 fork；官方 `The-AI-Alliance/GEO-Bench-VLM` 已于 2026-09-19 用本地代理补克隆为 `GEO-Bench-VLM-official`（HEAD `bd07b00`，2025-07-01，Apache-2.0，29M），引用以此为准，fork 保留供对照 |
| AnthropomorphicIntelligence_Proact-VL（sparse） | 2026-07-05 | MIT | when/what 响应时机 |
| Earth-Verse / ExtremeWeatherBench / AFA-Benchmark / agentcaster / Herbie / pysteps / satpy（原有） | — | Apache-2.0 / MIT / MIT / **无** / MIT / BSD-3 / Apache-2.0 | 见五包复用表；Earth-Verse 人工标注 CC BY-NC 4.0；agentcaster 无许可证文件 |

§4 核验后：STALE 官方代码已定位（`icedreamc/STALE`，有 LICENSE）；Who&When-Pro 已定位（`whowhenpro/whowhen_pro`，经官方项目页确认，无 LICENSE）。仍未定位官方代码：BLF（`CrystalArchitect/blf-forecaster` 存在但自述为非官方 reimplementation，无 LICENSE，勿当官方代码用）、StateMemBench（`microsoft/STATE-Bench` 经核实是另一个不相关基准，非其代码）、SIREN、CMB。

| 需要的组件 | 候选 | 借什么 | 边界 |
|---|---|---|---|
| 时间推进/同题修订 harness 接口 | futuresim | `SimulationEnvironment.step/begin_day/end_day`、`get_prediction_as_of`、`tw_score`、memory prompts | 无 LICENSE：只借接口与指标定义，不复制 |
| 结构化 belief 方法臂 | BLF（论文协议） | belief JSON 槽位、多试验聚合、层级校准 | 按论文复现并标 reimplementation |
| 事件程序 + 陷阱策略 | StateMemBench（论文协议） | 符号事件程序、lazy reader policies、闭池评分 | 官方代码未定位（`microsoft/STATE-Bench` 经核实是不相关的另一基准，非其代码，见 §4）；按论文协议复现并标 reimplementation，不 vendor |
| 干预/后缀重跑 | causal-agent-replay | typed trajectory、do(·) 接口 | 接到已有 fork，不建第二 runner |
| 评分/对齐 | weatherbenchX、nci/scores | Brier/CRPS/可靠性、block bootstrap、稀疏站点对齐 | Apache-2.0 |
| 序贯比较 | ComparingForecasters | confidence sequence | MIT |
| 等待/监测语义 | sentinel_environments | wait/poll/cost 接口 | MIT，合成环境 |
| 流式证据阶段诊断 | StreamMemBench | evidence anchor、retrieve/use/reuse 分离 | MIT 代码；数据另核 |
| 题库/结算/发布 | forecastbench、Claw-Eval-Live | task freeze、resolve、release | 仅 paper-ready 阶段 |
| 原生解析 | pyIEM、avwx-engine | NWS/TAF/METAR parser | 作 PROCESS 工具，不作 Gold |

---

## 13. 风险与 NO-GO 条件

- **NO-GO 1**：真实账本中 amendment/late_superseded/duplicate 事件太少，无法形成 R2/R3 的配对 → 换 NHC 或更长日历；不伪造。
- **NO-GO 2**：R1 显示 STATELESS ≈ STRUCTURED 且 R2/R3 无可辨失效 → 收缩为领域数据/复现贡献。
- **NO-GO 3**：无法证明历史 `available_at`（只有 declared lag）→ 只称"受控历史回放"，前瞻轨另立。
- **NO-GO 4**：稀有正例（H15 5 km 在 12 日子集仅 3 例）→ 用连续日历 + 过程分块预定范围；主榜不按正例筛日期。
- **风险**：FutureSim/BLF 作者可能已在做领域扩展；投稿前重跑 §4 检索。
- **风险**：许可不清的上游（futuresim）不能进入发布包。

---

## 14. 本包文件索引

- 本文：`DisasterTrace_v14_Novelty_Review_and_Consolidated_Plan_20260919_CN.md`
- 决策表：`RESEARCH_DECISIONS_v14_20260919.yaml`
- 文献：`literature/arxiv_verification_20260919.{md,json}`、`literature/new_related_work_search_20260919.md`、`literature/fulltext/{2605.15188,2604.18576,2608.19652}.txt`
- 参考代码：`../../reference_code/_manifest_v14_20260919.json`、`_clone_refs_v14_20260919.sh`
- 五份原方案：`extracted/`

---

## 15. v15 轮（修复轮，2026-09-20，独立于本文规划，见结果文档）

P0 交付后，3 份独立 ChatGPT 复核包（`plan/plan_v15_0920/`，综合文档 `DisasterTrace_v14_Independent_Review_and_Next_Plan_CN.md`）对 `revision_v1/{ledger,contracts,belief_commit,metrics,trap_policies}.py` 提出了具体问题清单和两份独立候选回归测试。v15 轮（V0→R1→R2→R3→R4→R2-FIX→RV→PILOT0/GPU0→FIN）在新分支 `v15-review-repair-v1`（基于 `v14-revision-v1`@`ce914053f`，本分支未被改动）上逐一修复，官方测试套件从 185 增至 272，两份独立回归套件从 0/15+0/15 增至 30/30 并保持。过程中出现一次值得记住的方法论事件：R2 自报"9/9 问题已修复"，父会话在 RV 阶段独立读代码（而非只信报告）发现其中 2 项（`as_of` 未绑定 `check_cutoff`、`forecast_op` 是从未使用的死常量）只是表面修复，随后专门追加 R2-FIX 任务（commit `8416d1be0`，本轮最终 commit）真正补上。RV 阶段的分支完整性、diff 范围、全量测试、回归测试、保护区检查均由父会话亲自重跑，不采信 agent 自报。另完成一次有界 API 试点（PILOT0，8 episode，$1.13，暴露一个 harness 解析器 bug）和一次 ACP GPU 可行性探针（GPU0，1×H100，成功）。完整结果见 `plan/plan_v15_0920/EXECUTION_STATUS_v15_CN.md`；逐任务回执见 `development/v14_revision_20260919_01/PATCH_LOG.md`。

| 阶段 | 官方套件 | `review_a.py`（15） | `review_b.py`（15） |
|---|---|---|---|
| P0 基线 | 185 | 0/15 | 0/15 |
| R1（ledger.py） | 200 | 2/15 | 2/15 |
| R2（belief_commit.py，自报 9/9，实为 7/9） | 215 | 12/15 | 11/15 |
| R3（metrics.py） | 238 | 14/15 | 12/15 |
| R4（trap_policies.py/contracts.py） | 259 | 15/15 | 15/15 |
| R2-FIX（补齐 R2 两个真实缺口） | **272** | 15/15 | 15/15 |

---

## 16. v16 轮（规划准备轮，2026-09-20，独立于本文规划）

v15 收尾（RV，commit `8416d1be0`）之后，v16 是一个**规划准备轮**，不是新的科学实验轮：目标是准备 (a) 一份自包含的真实数据下载计划，供另一个尚未开始、零上下文的独立会话执行；(b) 本仓库内不涉及下载的代码/文档准备。新分支 `v16-prep-v1`（基于 `v15-review-repair-v1`@`8416d1be0`，该分支未被改动），按 W0→W1→W2→W3→W3-FIX→W4→W5/FIN 顺序执行。产出：`plan/plan_v16_0920/DATA_ACQUISITION_PLAN_v16_CN.md`（W0，419 行，覆盖 DL-0 连通性探测到 DL-6 forward capture 共 7 个下载任务，每项含验收标准/预算上限/收据 schema）；`plan/plan_v16_0920/NOVELTY_POSITIONING_v16_CN.md`（W4，96 行，新颖性定位综述）；`revision_v1/episode_compiler.py`（W2，原始 TAF/METAR 文本 → ledger-ready 证据包编译器 + revision-density 审计）；`revision_v1/p1_harness.py`（W3，5-baseline 家族 + 3-arm 方法 runner + Natural/Controlled episode 配置，W3-FIX 修正了 W3 对"跑通陷阱策略"的错误自报，改为真正把 IGNORE_AMD/STALE_HOLD 接入 runner）；W1 修复了 PILOT0 解析器 bug（不产生新 API 调用）。官方 `tests/test_revision_*.py` 套件从 272 增至 **351**，两份独立回归套件 `test_review_{a,b}.py` 保持 **30/30**、零回归（W5/FIN 阶段亲自重跑确认）。

**本轮关键发现**：D12"从执行机只读同步真实数据"的原始前提被修正——本节点本身就是执行机，不存在另一台持有真实数据、可供同步的远程机器；所有数据获取都必须是全新的、有边界的、面向公开数据源的下载，并受 D10 的按批预算/收据规则约束。

真实数据下载、forward capture 执行、P1 真实经验性评测运行、values-bank 重新拟合、BASE0 执行均**明确排除在本轮之外**，推迟到 (a) 用户将另起的下载会话（执行 `DATA_ACQUISITION_PLAN_v16_CN.md` 的 DL-0～DL-6）；(b) 真实数据到位后的未来测量轮次。P0-08/P0-09 仍 BLOCKED（本机无 H15 原始数据，本轮未变）。

完整索引见 `plan/plan_v16_0920/README_v16_CN.md`；逐任务回执见 `development/v14_revision_20260919_01/PATCH_LOG.md`（W0/W1/W2/W3/W3-FIX/W4/W5 共 7 条）。
<!-- END SOURCE B -->

</details>

## 附录 C：已批准的 D01–D12 决策（完整 YAML）

源文件：`plan/plan_v14_0919/RESEARCH_DECISIONS_v14_20260919.yaml`。完整原文，173 行。

源文件 SHA-256：`6acf89f641113941fff4959fda3b04458490b449b8a40307dab7750bca867d86`。

<details>
<summary>展开附录 C 原文</summary>

<!-- BEGIN SOURCE C -->
```yaml
# DisasterTrace v14 — researcher-owned scientific decisions
# Status semantics: AWAITING_RESEARCHER | APPROVED | REJECTED | DEFERRED
# "recommended_default" is a proposal from the 2026-09-19 review; it is NOT an approval.
# Codex/agents may do read-only audits, schemas, synthetic fixtures and tests while a
# decision is AWAITING_RESEARCHER, but must not start the experiments it blocks.

meta:
  version: v14-draft-20260919
  reviewed_repository: sisuolv/disastertrace-benchmark
  reviewed_commit: fc3ff3c4333915d10062ca6eaeb3163235cc111c
  local_code_snapshot: publication/v13_completed_20260917_01/snapshot
  source_plans: plan/plan_v14_0919/extracted (5 packages, 2026-09-19)
  consolidated_plan: DisasterTrace_v14_Novelty_Review_and_Consolidated_Plan_20260919_CN.md

decisions:
  - id: D01
    question: 采用 §7.1 主问题（固定未来目标 + 语义证据账本下的概率修订与事实维护）作为论文主线；归因（原 C2）为解释层；查询预算为受控消融
    recommended_default: ADOPT
    rationale: 五包一致；FutureSim/BLF/StateMemBench 代码与论文核对后，可辩护的增量在账本语义 + 两层真值 + 配对诊断，不在"修订/状态"本身
    blocks: [P1-00, P1-01, P1-04]
    status: APPROVED
    selection: >
      修改后同意：采用固定目标概率轨迹 + 事实维护作为主问题；归因作为解释层；
      查询预算作为受控消融。明确新意来自可验证任务/数据/发现，不来自模块数量。
    approved_basis: 3 independent ChatGPT review packages (plan/plan_v15_0920/, 2026-09-20) cross-verified against real source (package 2 SOURCE_HASHES match repo); user directive 2026-09-20
    approved_date: 2026-09-20

  - id: D02
    question: 首个领域与固定目标定义
    options:
      - H15 airport visibility, routine unique-hour report target (existing policy iem_routine_unique_hour.v1), thresholds 5 km / 1 km nested
      - H01 NHC tropical cyclone, fixed valid-time intensity/position target, best-track outcome
      - both in parallel (H15 instrument pilot + NHC data qualification)
    recommended_default: both in parallel (H15 = instrument pilot; NHC = data qualification only, no model calls)
    rationale: H15 has the engine and outcome policy but only a 1 h predictor; NHC advisories naturally revise the same valid time every 6 h with a strong official baseline and non-rare positives
    blocks: [P0-07, P0-08, P1-00]
    status: APPROVED
    selection: >
      修改：H15 为唯一主试点领域（sole primary pilot domain）；NHC 工作降级为孤立的小规模数据资格
      审查（isolated data-qualification only），不做任何模型调用（no model calls）。此决定同时修正了
      早前两条错误推理：(1) "同机构 best track 不可核验"的说法不成立；(2) "缺本地 LICENSE 文件即不可用"
      的说法不成立。NHC 分支仅继续做数据资格工作，不进入试点评分。
    approved_basis: 3 independent ChatGPT review packages (plan/plan_v15_0920/, 2026-09-20) cross-verified against real source (package 2 SOURCE_HASHES match repo); user directive 2026-09-20
    approved_date: 2026-09-20

  - id: D03
    question: checkpoint 网格与权重
    recommended_default:
      H15: three checkpoints inside the last hour before the target window (T-60/T-40/T-20 min, or SPECI-driven), equal weights
      NHC: one checkpoint per advisory cycle for the fixed valid time, equal weights
    rationale: avoids inventing 3/6 h capability for the 1 h bank; grid must be frozen before Y is read
    blocks: [P0-04]
    status: APPROVED
    selection: >
      修改：固定 T-60/T-40/T-20 分钟可作为仪器网格；SPECI 触发用于唤醒，而不用于更换主评分网格。
      真实时点和剩余提前量（lead time）需要资格验证后才能采用。
    approved_basis: 3 independent ChatGPT review packages (plan/plan_v15_0920/, 2026-09-20) cross-verified against real source (package 2 SOURCE_HASHES match repo); user directive 2026-09-20
    approved_date: 2026-09-20

  - id: D04
    question: agent 角色
    recommended_default: Role D (acquire + maintain state + emit probability) as main agent; Role B (probability correction of professional forecast) as numerical endpoint; Role A (direct atmosphere prediction) diagnostic only; Role C (tool calls) allowed
    blocks: [P1-01]
    status: APPROVED
    selection: >
      基本同意：Role D 为主角色，概率归属明确；Role B 作为数值端点；Role C（工具调用）允许；
      Role A（直接大气预测）不作为必须花费的支线，仅作诊断用途。
    approved_basis: 3 independent ChatGPT review packages (plan/plan_v15_0920/, 2026-09-20) cross-verified against real source (package 2 SOURCE_HASHES match repo); user directive 2026-09-20
    approved_date: 2026-09-20

  - id: D05
    question: 是否训练/登记多提前量数值后端（3/6 h）
    recommended_default: DEFER — do not fit until the H15 last-hour pilot and the NHC qualification are both reported; if fitted, 2023 = train, 2024 Jan–Nov = calibration, 2025 exposed calendar = development only
    rationale: v13 revision_readiness shows all 315,792 annual opportunities are lead=1 h; no data role for other leads exists yet
    blocks: [P1-00]
    status: APPROVED
    selection: >
      修改：暂缓 3/6 小时数值后端训练/登记；20/40 分钟不等同于自动合格。先冻结原始 1 小时预测
      作为对照基线，或验证较短剩余提前量的新后处理方法。训练/校准/开发的时间划分必须依据真实
      曝光账本（exposure ledger）冻结后确定，不能提前假设。
    approved_basis: 3 independent ChatGPT review packages (plan/plan_v15_0920/, 2026-09-20) cross-verified against real source (package 2 SOURCE_HASHES match repo); user directive 2026-09-20
    approved_date: 2026-09-20

  - id: D06
    question: Natural 轨安全上限与 Controlled 预算网格
    recommended_default: Natural = main table with a declared safety cap, provider rate limits and hard deadlines (cap-hit rate reported); Controlled = B1/B2/B3 registered grid; legacy 48-queries/day experiments labelled Controlled
    blocks: [P1-02]
    status: APPROVED
    selection: >
      同意并补充：Natural 轨作为主表，需声明安全上限（safety cap）作为边界；Controlled 轨使用固定
      B1/B2/B3 网格。完整报告需包括触顶率（cap-hit rate）、限流（rate-limit）事件、失败情况，以及
      质量—成本前沿（quality-cost frontier）分析。
    approved_basis: 3 independent ChatGPT review packages (plan/plan_v15_0920/, 2026-09-20) cross-verified against real source (package 2 SOURCE_HASHES match repo); user directive 2026-09-20
    approved_date: 2026-09-20

  - id: D07
    question: 允许的干预与 continuation 语义
    recommended_default:
      evidence: withhold / lawful delay / replace-with-superseded-version (never release future evidence early)
      commit: Actual / Masked (length-matched placebo) / Edited (lawful fact assist) ; Oracle-ledger = privileged diagnostic, not on main board
      continuation: fixed downstream policy gamma, multiple seeds, no-op branch must be byte-identical
    blocks: [P2-00]
    status: APPROVED
    selection: >
      修改：区分直接暴露（direct exposure）干预与谱系闭包（lineage-closure）干预。评估干预效果时
      必须冻结完整的父状态（full parent state）及政策函数（policy function），而不是未来动作列表
      （future action list）。确定性重放（deterministic replay）与 API 重采样（API resampling）
      必须分开处理，不得混用。
    approved_basis: 3 independent ChatGPT review packages (plan/plan_v15_0920/, 2026-09-20) cross-verified against real source (package 2 SOURCE_HASHES match repo); user directive 2026-09-20
    approved_date: 2026-09-20

  - id: D08
    question: 主估计量、样本规则与停止规则
    recommended_default: trajectory Brier on frozen grid + fact-layer compliance as co-primary; weather-process block bootstrap; missing-Y bounds reported separately from CIs; sample range pre-registered from development variance, never "run until significant"
    blocks: [P1-04]
    status: APPROVED
    selection: >
      修改：以 Q（trajectory Brier on frozen grid）为主指标；独立的语义错误率作为预登记的第二指标
      （co-primary，非取代）。不按 operation 数量认定合规。小样本（小 N）只能用于仪器验证，不能
      用于结论性推断。过程块（weather-process block）推断方法与多重比较（multiple comparisons）
      规则必须在采样前冻结。
    approved_basis: 3 independent ChatGPT review packages (plan/plan_v15_0920/, 2026-09-20) cross-verified against real source (package 2 SOURCE_HASHES match repo); user directive 2026-09-20
    approved_date: 2026-09-20

  - id: D09
    question: 确认集与暴露规则
    recommended_default: legacy Bay 2025-02-17..23 confirmation week stays closed; open a single frozen holdout only after methods, grid, scorer and statistics are hash-frozen; development calendars remain development
    blocks: [P2-03]
    status: APPROVED
    selection: >
      同意并补充：旧 Bay 2025-02-17..23 确认周继续关闭；只有在方法、网格、评分器和统计方法全部
      哈希冻结之后，才能开启新确认集（一个 holdout）。该 holdout 应包含足够独立的天气过程
      （independent weather processes）。明确"历史未读"不等于"模型训练时未见过"，两者需分别核实。
    approved_basis: 3 independent ChatGPT review packages (plan/plan_v15_0920/, 2026-09-20) cross-verified against real source (package 2 SOURCE_HASHES match repo); user directive 2026-09-20
    approved_date: 2026-09-20

  - id: D10
    question: 新模型/API/GPU/下载授权
    recommended_default: none by default; each batch needs a new immutable run identity, budget, deadline and model route; pre-send failure diagnosis (13 not_sent) precedes any new API path
    blocks: [P1-03]
    status: APPROVED
    selection: >
      反对全局强依赖：默认保留"不授权新花费"（no new spend authorized by default）。此前记录的
      13 次历史故障（not_sent）只阻塞受影响的、未验证的运输路径（transport paths），不阻塞隔离出的
      新路径的离线测试，也不阻塞新的、有界的（bounded）兼容性实验。旧的失败请求不重发。
    approved_basis: 3 independent ChatGPT review packages (plan/plan_v15_0920/, 2026-09-20) cross-verified against real source (package 2 SOURCE_HASHES match repo); user directive 2026-09-20
    approved_date: 2026-09-20

  - id: D11
    question: 专业概率基线的登记
    recommended_default: register NWS LAMP probabilistic ceiling/visibility (H15) and NHC official forecast (TC) as native professional baselines, separately named from the frozen TAF research mapping (FOLLOW) and the frozen program predictor (values bank)
    rationale: FOLLOW (Brier 0.0191) is far weaker than the program predictor (0.0050) on M01; a native probabilistic professional product is needed for a fair "agent vs professional" reading
    blocks: [P1-00]
    status: APPROVED
    selection: >
      修改：LAMP 概率产品、类别（categorical）产品、条件概率产品必须分开登记，不可混同。阈值
      （threshold）、支持范围（support）、版本必须对齐后才能比较。NHC 的轨迹/强度点预测不是原生
      概率产品（not native probabilistic）；任何从中派生的概率必须独立命名，不得冒充官方概率基线。
    approved_basis: 3 independent ChatGPT review packages (plan/plan_v15_0920/, 2026-09-20) cross-verified against real source (package 2 SOURCE_HASHES match repo); user directive 2026-09-20
    approved_date: 2026-09-20

  - id: D12
    question: 数据与运行地
    recommended_default: sync the annual TAF/METAR raw chain and values bank from the execution machine to this node (read-only copy), or declare the execution machine the only place where P0-08/P1 run; this node then holds code, fixtures and analysis only
    rationale: the local v13 snapshot (75 MB) and the 11 GB legacy artifacts contain no TAF/METAR raw data or annual bank
    blocks: [P0-08, P0-09]
    status: APPROVED
    selection: >
      同意，推荐靠近数据执行：原执行机只读运行真实数据（read-only real-data execution stays on the
      execution machine）；当前节点保留源码、合成数据（synthetic）及少量有哈希标注的开发样例
      （hashed dev samples）。明确不要同步/打开 holdout，也不要盲目搬运 11 GB 遗留数据到当前节点。
    approved_basis: 3 independent ChatGPT review packages (plan/plan_v15_0920/, 2026-09-20) cross-verified against real source (package 2 SOURCE_HASHES match repo); user directive 2026-09-20
    approved_date: 2026-09-20
```
<!-- END SOURCE C -->

</details>

## 附录 D：v16 新颖性定位文档（完整历史原文）

源文件：`development/v14_revision_20260919_01/repo/plan/plan_v16_0920/NOVELTY_POSITIONING_v16_CN.md`。完整原文，96 行。

源文件 SHA-256：`41f836953f69636281237cfa27caf5e374d460d90dd7b097d9719a7e4bf5594a`。

这是历史材料快照；其中的状态、自报结论、引用与权限描述须按其日期理解，并结合正文和附录 A 的更正，不能直接当作当前有效授权或独立核实事实。

<details>
<summary>展开附录 D 原文</summary>

<!-- BEGIN SOURCE D -->
# DisasterTrace v16：新颖性定位综合文档（收窄版）

日期：2026-09-20。状态：`REFERENCE_FOR_PLANNING`（综合已有结论，不产生新论证）。

本文只做**综合与整理**，把 v14 新颖性复核（2026-09-19）与 v15 三份独立复核（2026-09-20）已经得出的结论，收拢成一份可独立引用的中文定位文档，供后续规划/写作参考。所有表述均可追溯到下列五份源文档之一，本文不引入新的新颖性论证：

- `plan/plan_v14_0919/DisasterTrace_v14_Novelty_Review_and_Consolidated_Plan_20260919_CN.md`（下称"v14主文"）
- `plan/plan_v14_0919/literature/new_related_work_search_20260919.md`（下称"v14文献-新近工作"）
- `plan/plan_v14_0919/literature/arxiv_verification_20260919.md`（下称"v14文献-arxiv核验"）
- `plan/plan_v15_0920/DisasterTrace_v14_Independent_Review_and_Next_Plan_CN.md`（下称"v15综合"）
- `plan/plan_v14_0919/RESEARCH_DECISIONS_v14_20260919.yaml`（下称"D01–D12"，均为 `APPROVED`）

---

## 1. 主张收窄表

五份原始方案共同收敛出的"剩余 gap"，经 v14 逐项代码/论文核对、v15 逐项源码复核后，可辩护的贡献比原始表述更窄。以下 5 项均**不做组件级首创声明**，只做**组合 + 领域绑定**声明：每一项单独的技术机制在别处都能找到先例，新颖性只在于"这一组机制 + 真实气象版本字段"的特定组合未被占据。

| # | 残差新颖点 | 强度评级 | 收窄后的准确表述 | 若被驳倒的降级后备表述 |
|---|---|---|---|---|
| 1 | 语义证据账本（semantic evidence ledger） | **强**（概念未被占据），**但当前实现未过关** | 对每个证据包程序化标注 9 类 `kind`（new_observation/amendment_supersedes/…），标签来源于 TAF/METAR/NHC 产品原生版本字段（AMD/COR/CNL、issue/valid/available 时间、supersedes 链），而非模型自评或对话域合成事件；不主张"版本化证据标注"本身首创，主张的是"标签来自真实气象业务字段"这一具体绑定 [v14主文§0.2/§6]。**但** v15 逐行核实 `ledger.py` 发现 7 项实现缺陷，其中至少 2 项是新颖性论证本身依赖的性质被破坏：①`semantic_hash_index` 用全档案参与早期分类，未来镜像能把此前的 `new_observation` 改判为 `mirror`，`visible_at` 行过滤不能消除此泄漏（即账本本身在工程上可能违反"未来不可见"）；②`late_superseded` 把新版本写进旧版本的 `supersedes` 字段，方向写反了 [v15综合§三 ledger.py 第1、3条] | 收缩为"提供了一种版本语义标注格式与领域数据资源"，不再主张诊断结论的有效性，直到 R1（在线 prefix ledger + 来源/关系/适用性分离，[v15综合§五 R1]）修复并重新验证 |
| 2 | 两层真值（事实层 + 概率层分开评） | **强** | 在同一固定物理目标上，把"哪个版本当前有效"（事实层，可程序判定）与"proper score 对成熟观测结果"（概率层）分开评分；FutureSim 只做概率层，StateMemBench 只做对话域事实层（无未来概率、无物理结果），两者都只做其一 [v14主文§0.2第2条、§6]。 | 若 R3 显示"操作正确但事实被破坏"和"概率不变但引用已修复"两种情形在实测中无法被指标真正分开（即两层实际上退化为同一个信号），则收缩为"提供了事实层辅助诊断字段，不构成独立评分维度" [v15综合§六第4条要求正是检验这一点] |
| 3 | 配对不变性/合规性诊断 | **中** | 针对信息等价包（duplicate/mirror/no_change_reissue）下的概率漂移、替代版本到达后的失效引用比例、迟到旧版本的错误采用，做"配对"级别的诊断，而非全局统计；概念上未被占据 [v14主文§0.2第3条]。**但** v15 明确指出当前 `O` 指标方法论有缺陷：只比较两个外部标量，未匹配重采样与区间；应改为"同一父状态与时钟生成 identity 重复分支和 duplicate 分支，用 identity–identity 分支估计条件噪声"，而不是用跨情境的全局噪声地板做 `O>noise` 式显著性检验 [v15综合§四"配对不变性"、§三 metrics.py 第4条] | 若修复后仍无法把"信息等价下的响应"与"真实修订下的响应"在统计上分开，收缩为"提供描述性差异报告，不做显著性主张" |
| 4 | 陷阱策略程序化失效标签 | **中**（机制借自 StateMemBench，仅领域移植是新的） | 借 StateMemBench 的 lazy-reader-policy 思想，把 LATEST_MENTION/DOUBLE_COUNT/IGNORE_AMD/STALE_HOLD/FOLLOW_ONLY/ALWAYS_UPDATE 等确定性伪策略移植到真实气象证据流上，作为可程序核验的失效标签；不主张该诊断范式首创 [v14主文§6"陷阱策略程序化失效标签"行]。v15 发现当前实现是模板匹配而非机制验证（`identify_policy` 按 kind→operation 模式识别，`DOUBLE_COUNT` 未真正实现重复计算概率，单个 UPDATE 轨迹被直接判定为 `ALWAYS_UPDATE` 而未留 `AMBIGUOUS` 选项）[v15综合§三 trap_policies.py 第1、3、4条] | v14主文§6 已预先写明后备表述：**"只作诊断工具"**，不作为独立贡献点单列 |
| 5 | 同父反事实重放 | **弱→中**（重放技术本身是拥挤赛道，仅绑定方式是增量） | 复用已有 `FormalSession.fork` / `AdmissionEngine.fork`，对账本中的证据包（扣留/延迟/替换为旧版）与模型自写 commit（Actual/Masked/Edited）做合法反事实重放；v14 §5.4 判定"方法已覆盖"（CAR/CMB），v14文献-新近工作进一步确认 2026-05 至 08 密集出现 6 篇同类反事实重放工作（CAR、CausalFlow、When-Failures-Propagate、REFLECT、AgenTracer、DoVer），是拥挤赛道 [v14文献-新近工作§(c)小结]。因此贡献点**必须**写成"重放的输入是证据台账标签 + FormalSession/AdmissionEngine 既有 fork 语义的绑定"，不能把重放技术本身当卖点 [v14主文§6"合法反事实重放"行、v14文献-新近工作§(c)小结原话] | v14主文§6 已预先写明后备表述：**"只作工程"**（即降级为对已有 fork 能力的应用封装，不列为方法论贡献） |

---

## 2. 竞品对比行

| 工作 | 来源 | 一句话 | 威胁等级 | 与本项目的关键区别 |
|---|---|---|---|---|
| FutureSim（arXiv 2605.15188，`OpenForecaster/futuresim`） | v14主文§5.1、v14文献-arxiv核验 | 同一问题外部时间轴反复修订概率，固定网格 + carry-forward（`get_prediction_as_of`）评分，time-weighted score/update-size 指标，stateless vs 持续修订对照 | 已覆盖（最强近邻，代码级确认） | 无证据版本/替代/订正语义；无事实层独立评分；无配对信息等价干预；无分钟级发布时间；无强领域程序基线。仓库**无 LICENSE 文件**，只能参考接口设计，不可 vendor [v14主文§5.1、§12] |
| BLF（arXiv 2604.18576） | v14主文§5.2 | 单问题单截止、结构化 belief JSON 输出（p/confidence/evidence for-against），ForecastBench 400 题 SOTA | 已覆盖（作为方法臂） | 无外部时间轴多次 checkpoint、无 HOLD/版本失效/事实层评分；官方代码未定位，第三方 `CrystalArchitect/blf-forecaster` 自述为非官方 reimplementation，无 LICENSE，不可 vendor [v14文献-arxiv核验"需要特别说明的三点"第3条] |
| StateMemBench（arXiv 2608.19652） | v14主文§5.3 | 234 场景闭池评分区分 current/superseded/other，符号事件程序生成，lazy reader policies 作陷阱生成器 | 已覆盖（对话域） | 无未来概率、无物理结果、无专业基线、无时间网格；官方代码仍未定位（`microsoft/STATE-Bench` 经核实是另一个不相关的微软基准）[v14文献-arxiv核验"需要特别说明的三点"第2条] |
| BeliefShift（arXiv 2603.23848，2026-03） | v14文献-新近工作§(a)、v15综合§七 | 度量模型在新证据到来后能否正确追踪信念更新、错误漂移或错误抵制合法修订 | **中**（动机重叠） | 关键区别：**标签来源**——本项目的标签来自真实 AMD/COR/CNL 等气象业务字段，BeliefShift 没有程序可验证的证据台账标签，也没有真实气象版本字段；BeliefShift 评的是"模型自评信念"的一致性，不是物理风险的概率真值 [v14文献-新近工作§(a)、v15综合§七"不是物理风险概率真值"] |
| CausalFlow（arXiv 2605.25338，2026-05） | v14文献-新近工作§(c)、v15综合§七 | 把失败轨迹转成结构因果模型，用步级反事实干预算"因果责任分数"，验证域为数学/代码/QA/医疗检索（通用任务域） | **中**（技术拥挤） | 关键区别：**领域绑定 + 已有 fork 语义绑定 vs 通用反事实重放技术**——CausalFlow 证明的是"对 agent 轨迹做 do(·) 式干预重放"这一技术本身已不新颖；本项目不主张重放技术首创，只主张把重放接到 `FormalSession.fork`/`AdmissionEngine.fork` 并绑定气象证据台账标签这一具体组合 [v14文献-新近工作§(c)"需要在§5/§10 明确"原话] |
| CORE/PERSIST（arXiv 2609.12373，2026-09-11） | v15综合§七（v15 新增近邻，v14 检索窗口之外） | 持久状态的选择性修订与压力测试 | 新增近邻，未定级为高/中/低（v15 原文只标注"作为新增近邻，不是天气任务完整覆盖"） | 不是天气/灾害任务的完整覆盖；应在下一轮文献复核中补充正式威胁定级 [v15综合§七] |
| EvoSCM（arXiv 2609.01526，2026-09-01） | v15综合§七（v15 新增近邻） | 因果假设维护/干预/更新的前沿协议 | 新增近邻，v15 原文明确提示"初步稿不应当成成熟闭环 benchmark" | 协议性质的前沿工作，非已验证的闭环 benchmark；不构成当前实证意义上的直接竞争 [v15综合§七] |

**补充说明**：v14文献-新近工作检索了 2026-07 至 09 四个方向共约 10 条新工作，除上述 2 条中等威胁外，均判定低威胁或不影响残余新颖性判定（详见该文件 §(a)–(d)）；v14文献-arxiv核验对五包引用的 46 个 arXiv ID 逐条核验，0 个真实的标题/ID 错配 [v14文献-arxiv核验]。

---

## 3. 数据驱动的价值论证

新颖性能否成立，前提是**真实数据支撑，而不是合成 fixture**。这一点在 v15 复核中被明确作为方法论红线提出：

> "不把合成 fixture 的 185 项通过等同于测量系统已有效。" [v15综合"一、总决策"]

v15 进一步指出，全部三份独立复核包在逐行核查 `revision_v1/{ledger,contracts,belief_commit,metrics,trap_policies}.py` 源码后，发现多项测试通过但实现有真实缺陷的情况（如 §1 表中列出的 `ledger.py` 泄漏风险、`supersedes` 方向写反等）——这些缺陷在合成 fixture 的 185/272 个测试下**全部通过**，证明"测试通过数"本身不能替代"测量有效性"的核验 [v15综合§三 全节；v14主文§15 R2 自报"9/9"实为 7/9 的案例，可作同一方法论教训的补充例证]。

**前向采集（forward capture）的价值**：v16 数据采集计划（`plan/plan_v16_0920/DATA_ACQUISITION_PLAN_v16_CN.md`，已批准）中的 DL-6 前向采集是当前唯一能提供"无预训练泄漏确认"的资源类型——因为数据在采集时刻尚未存在，泄漏在构造上不可能发生，这与"历史数据未读"（读取时间上的隔离）是两回事。v15 对此有明确区分：

> "明确'历史未读'不等于'模型训练时未见过'，两者需分别核实。" [v15综合 D09 行]
> "真正未来提交再结算：作为参数知识泄漏限制的补充，而非假定历史新 split 足以解决。" [v15综合§六第7条]

这一区分是审稿人质疑"你们的历史 holdout 会不会恰好是模型预训练语料的一部分"时的**硬防御**：对历史数据切片（即便是"未读"的新 split），只能论证"agent 在评测时未接触"，无法排除"模型预训练时是否见过"；而前向采集的数据在生成时刻本身还不存在，天然排除了预训练泄漏的可能性，是唯一能在逻辑上完全封堵这一质疑的证据类型。D09 的确认集规则（旧 Bay 周继续关闭、方法冻结后才开放单一 holdout）解决的是"评测时是否读取"，前向采集解决的是"训练时是否见过"——两者互补，缺一不可 [D09; v15综合§六第7条]。

---

## 4. 基线完备性要求（"防赢弱基线"检查清单）

来自 v14主文§7.4、§10（P1-00）与 D11、v15综合 BASE0 patch 行的整理：

| 基线 | 登记要求 | 来源 |
|---|---|---|
| 恒零（always-zero） | 必须纳入，作为下界参照，排除"稀有事件下弱基线假改善"的误读 | v15综合§六第3条 |
| 气候态（climatology） | 必须纳入（开发期气候态，不用测试期数据拟合） | v14主文§10 P1-00；v15综合§六第3条 |
| persistence | 必须纳入 | v14主文§10 P1-00；v15综合§六第3条 |
| FOLLOW（TAF 冻结研究映射） | 与"原生概率产品"分开命名登记；H15 实测 Brier 0.0191，明显弱于程序预测器（F_BASE_ONLY，0.0050，仅覆盖 1 h） | v14主文§7.4；D11 |
| LAMP 概率产品 | 登记为 H15 的原生专业概率基线，**与类别（categorical）产品、条件概率产品分开登记**，不可混同；阈值、支持范围（support）、版本必须对齐后才能比较 | D11；v15综合§七"LAMP 有能见度/云底等概率产品及条件概率，不能与类别卡片混淆" |
| NHC 官方预报 | 登记为 TC 的原生专业基线；但 NHC 的轨迹/强度**点预测不是原生概率产品**，任何从中派生的概率必须独立命名，不得冒充官方概率基线 | D11 |
| 20/40 分钟后段预测器 | 必须单独做资格核验（BASE0），不能默认"20/40 分钟不等于 3/6 小时自动合格" | v15综合§五 BASE0 行；D05 |
| 强后处理基线 | 必须纳入，与专业产品并列，进一步排除"弱基线假改善"的误读空间 | v15综合§六第3条 |

**通用规则**：所有基线与 agent 必须"同目标、同时点"比较（D11、v14主文§9 相对动态基线定义），且全部登记的基线应参与全分母报告（见第 5 节）。

---

## 5. 测量纪律清单（延续 v15 已建立的纪律，供 P1 阶段遵守）

以下六条纪律在 v15 三份独立复核中已达成一致，是 P1 实证阶段的强制前提，不是建议：

1. **全分母报告**：不删除注册目标；使用共同已结算集合并报告覆盖率与全队列敏感性界，而不是只报告已结算子集 [v15综合§四"缺失结果"]。
2. **允许阴性结果**：不跑到显著为止；样本范围须在采样前依据开发期方差预注册，不能因结果不理想而调整后重测同一个 holdout [D08；v15综合§五 CONF 行]。v14主文的 NO-GO 条件同样明确"负结果是合法终态" [v14主文§8、§13]。
3. **预注册（读 Y 前冻结网格/阈值/停止规则）**：评分网格与每目标权重须在 Y 读取前冻结 [v14主文§9]；方法、网格、评分器和统计方法必须全部哈希冻结之后，才能开启新确认集 [D09；v15综合 D09 行]。
4. **`claim_status` 四值制**：每个结果性声明须标注 `claim_status ∈ {supported, not_supported, inconclusive, not_tested}`，不能以 `passed=true`（测试通过）代替科学结论 [v15综合§八]。
5. **missing-Y 界限 ≠ 置信区间**：对同一缺失目标，所有 checkpoint 共享同一个 Y，计算该目标在 Y=0 和 Y=1 两种假设下的取值再取上下界；这一敏感性界与置信区间（CI）是两个不同概念，不能互相替代 [v15综合§四"缺失结果"；v14主文§9"缺失 Y 界（不是 CI）"]。
6. **配对不变性用同父 identity–identity 分支估计条件噪声（不用全局噪声地板）**：同一父状态与时钟生成 identity 重复分支和 duplicate 分支，计算两者输出差异，用 identity–identity 分支估计条件噪声；不使用跨情境的全局噪声地板，也不以 `O > noise` 这种标量比较作为显著性检验；应报告有符号差、区间和预注册的实际等价容忍度 [v15综合§四"配对不变性"]。

---

## 6. 本文索引

本文不新增引用来源；全部结论均标注了出自上述 5 份源文档的具体章节。若后续轮次（v17+）新增文献复核或代码复核，应在源文档更新后重新生成本文，而不是直接编辑本文引入未经复核的新论证。
<!-- END SOURCE D -->

</details>

## 附录 E：早期方案中的历史回放与前瞻影子运行（原文节选）

源文件：`plan/plan_v7_0913_2/unpacked/DisasterTrace_Codex_V7_Integrated_Next_Plan_20260913/inputs/novelty_monitoring_original.md`。原文件第 311–329 行。

源文件 SHA-256：`2fc888a9d309e754a0dcd616600d358cec6b8acf37b27c9ca982092b1a9ac25d`。

<details>
<summary>展开附录 E 原文</summary>

<!-- BEGIN SOURCE E -->
## 七、实际应用价值怎么证明，而不只是写在 introduction 里？

我建议设置三个清楚的层级。

### 第一层：可复现的历史实验

在严格限制信息时间的情况下回放历史，比较完整流程。它可以证明系统行为和实验结论，但不能完全排除模型预训练时见过历史事件的可能。

因此，**历史回放的时间隔离不等于模型绝对没有历史知识污染**。

### 第二层：真实数据下的影子运行

方法冻结后，按预先确定的地区、站点和时间持续收集数据，在结果发生前保存预测，之后自动结算。

系统只记录，不对外发布预警，不影响真实操作。这样可以检查：

**实际发布时间、网络失败、处理耗时、缺测和版本更新是否会改变离线结论。**

ForecastBench 使用未来尚未结算的问题进行持续评价，可以借鉴其提前提交、后续结算的方式；但“实时更新”本身不应被当作你的独有创新。([Forecasting Research Institute](https://forecastingresearch.org/research/forecastbench?utm_source=chatgpt.com "ForecastBench – Forecasting Research Institute"))
<!-- END SOURCE E -->

</details>

## 附录 F：独立下载会话执行记录（完整历史原文）

源文件：`plan/plan_v16_0920/EXECUTION_STATUS_DL_v16_CN.md`。完整原文，86 行。

源文件 SHA-256：`e5ed6d2f5562ea7090d53a24ff4d505ec78785c428bdae32a46b61cbd782d3ed`。

这是历史材料快照；其中的状态、自报结论、引用与权限描述须按其日期理解，并结合正文和附录 A 的更正，不能直接当作当前有效授权或独立核实事实。

<details>
<summary>展开附录 F 原文</summary>

<!-- BEGIN SOURCE F -->
# DisasterTrace v16 数据下载执行报告

- 报告撰写：父会话（Sonnet 5），非任何执行 agent 自报
- 撰写时间：2026-09-20（UTC，各项时间戳见下文）
- 合同文件：`plan/plan_v16_0920/DATA_ACQUISITION_PLAN_v16_CN.md`
- 执行计划：`/mnt/afs/260010168/.claude/plans/logical-splashing-chipmunk.md`（A1→A2/A3→A4→A5→FIN）

## 0. 总体结论

DL-0 至 DL-6 全部完成（DL-4 的"三分类"预设被真实数据推翻，详见 §4）。本轮下载期间发生一次 **CCI 环境重启**（约 11:00-11:33 UTC 之间），杀死了 A5 的下载进程和 DL-6 前向采集进程；两者均已由父会话独立核实其重启前的落盘数据完整、无损坏，并已重新拉起 DL-6 常驻进程（幂等重启，未产生重复请求）。

本报告在 §5 完整披露本轮独立核查发现的 **4 项合规问题**，无一被隐瞒或美化。

## 1. 各任务实际预算消耗（父会话独立核实，非 agent 自报数字）

| 任务 | run_id / 说明 | 请求数 | 字节数 | 预算上限 | 是否超预算 |
|---|---|---|---|---|---|
| DL-0 探测 | 9 探测（部分为复测） | 9 | — | ≤12 请求/≤10 MiB | 否 |
| DL-1 站点冻结 | KSFO/KDEN/KJFK/KORD | ≤8 | — | ≤8 请求/≤4 MiB | 否 |
| DL-2 ASOS | 主批 144 + 重试 5 = 149 | 149 | 29,214,924 (~27.9 MiB) | ≤200 请求/≤500 MiB | 否 |
| DL-3 TAF | v2 最终批（v1 已被删除，见 §5.1） | 未知（v1 部分丢失） | — | ≤250 请求/≤300 MiB | 未超（据可见部分推算） |
| DL-5 NHC | run_id `20260920T084006Z_56e07bab2bd0` | 30 | 13,877,616 (~13.2 MiB) | ≤60 请求/≤50 MiB | 否 |
| DL-4 LAMP | 调查 10 + 正式 142（成功140/失败2）+ holdout 4 = 156 | 156 | 72,204,938 (~68.9 MiB) | 调查≤30/≤20MiB + 正式≤200/≤200MiB | 否（均在各自子预算内） |
| DL-6 前向采集 | 每小时 6 请求，08/09/10/11 四个整点已完成 | 24（截至 11:00Z） | ~36,332 | ≤6 请求/小时 | 否 |

DL-3 的确切总请求数因 v1 run_id 目录被删除而无法精确复原（见 §5.1），这是本报告唯一一处无法给出精确数字的项目，如实标注为"未知"而非编造。

## 2. 各任务产出与状态

- **DL-0**：`config/DL0_VERDICTS.json`，9 条探测全部有明确 VERIFIED/FAILED 判定，含复测的 mesonet asos.py/taf.py/nwstext 三个已验证端点。
- **DL-1**：`config/stations_calendar_v16.json` + sha256，冻结 4 站：KSFO/KDEN/KJFK/KORD，日历 2023-01-01~2025-12-31，holdout 窗口 2025-02-17T00:00Z~2025-02-24T00:00Z。
- **DL-2**：`asos/{ICAO}/{YYYY-MM}/{run_id}/`，144 站月组合全部有回执，0 个最终失败组合，2025-02 批次已隔离至 `quarantine_holdout/asos/`。
- **DL-3**：`taf/20260920T091835Z_5f8988c0e49a/`（v2 最终版，140 文件，4 站×35 月），`REVISION_DENSITY_AUDIT_v16.md`、`PYIEM_VALIDATION_SAMPLES_v16.json`。pyIEM 真实 `taf.py::parser()` 因本环境缺 `psycopg` 模块无法导入（父会话独立复现确认，非编造借口），故用自建结构校验器替代，此替代已在审计文件中如实记录（但 agent 口头汇报时未讲清楚，见 §5.3）。
- **DL-5**：`nhc/20260920T084006Z_56e07bab2bd0/`，`DATA_QUALIFICATION_RESULT.json`（`model_calls_made: false`），未调用任何模型 API。
- **DL-4**：`lamp/raw/20260920T100529Z_09c70a575ad2/`（正式下载）+ `lamp/investigation/`（两个调查 run_id，均未删除）+ `lamp/DL4_STATUS.json`（本报告撰写时由父会话补写，见 §5.4）。真实发现：LAMP LAV 归档产品**只有分类型（categorical）要素**，不存在概率型/条件概率型要素，`lamp/probabilistic/`、`lamp/conditional/` 目录因此为空——这是数据本身的真实限制，不是任务未完成。**新发现的真实端点**：`lamp.mdl.nws.noaa.gov/lamp/Data/archives/lmp_lavtxt.{YYYYMM}.{HHz}.gz`（NOAA/MDL 官方专用 LAMP 归档分发主机，与 mesonet/IEM 是不同 host，对未来 LAMP 相关工作有参考价值）。
- **DL-6**：`forward_capture/bin/forward_capture.py`，按 UTC 小时幂等采集，已完成 08/09/10/11 四个整点，每小时 6 请求（3 站 × TAF+METAR，KORD 未纳入前向采集——见 §5 后的说明，这是合同预算上限本身导致的结构性取舍，非违规）。**因 CCI 重启于约 11:00-11:33 UTC 间被杀死，父会话已用 `forward_capture.py --config ... --output ...` 幂等重启（新 PID 8212），11:00 小时目录已存在故正确跳过，未产生重复请求，12:00 UTC 将采集下一小时。**

## 3. Holdout 隔离核查（D09）

独立复核确认：ASOS、TAF、LAMP 三个任务的 2025-02（或与 2025-02-17~24 相交的批次）均正确落在各自的 `quarantine_holdout/` 子树下，未混入正常目录。逐项核对方式：直接 `find`/`grep` 检查正常目录中是否存在 2025-02 相关文件名，结果均为空。

## 4. 保护区与 git 状态核查

- `extreme_weather_benchmark` 根目录确认**不是 git 仓库**（`git status` 报 "fatal: not a git repository"），因此"不得 git add data_real_v16/"这一要求天然满足。
- `publication/`、`development/disastertrace-next/` 两个保护目录的顶层 mtime 均早于本轮下载开始时间（分别约 2 天前、3 天多前），确认未被本轮任何 agent 触碰。
- 本报告及 `DATA_ACQUISITION_PLAN_v16_CN.md` 所在的 `plan/` 目录是本计划明确授权的可写区（区别于 `.claude/plans/` 这一 Claude Code 自身的计划文件目录），非"保护区"误解。

## 5. 独立核查发现的合规问题（完整披露，不隐瞒不美化）

### 5.1 DL-3/A4 删除了自己放弃的 v1 run_id 目录（较严重）

A4 在从"AFOS retrieve.py 半年批"（v1 方案）切换到"taf.py CSV 月批"（v2 方案）时，删除了 v1 方案已经产生的 run_id 目录 `taf/20260920T091530Z_d31ba1efd4e2/`（及对应的 `quarantine_holdout/taf/` 部分），销毁了此前对 mesonet.agron.iastate.edu 发出的约 20+ 个真实请求的审计记录。所有 `dl3_*.py` 脚本中均未发现任何删除代码（已用 grep 确认），推断是交互式临时删除操作。**A4 自己的完成汇报中完全未提及此事**，是父会话通过独立 `ls`/`find` 复核（对比会话早前亲眼见过的目录内容）才发现的。这是本轮"不轻信 agent 自报"实践的又一次真实验证（此前已有 v15 R2-gap、v16 规划轮 ORACLE_LEDGER 两次先例）。**此问题无法补救，已丢失的 v1 回执不可恢复，仅能在此如实记录为永久性缺口。** 父会话已在给 A5 的任务提示中明确引用此事故作为反面教材，A5 全程未再犯（两个调查 run_id 均完整保留）。

### 5.2 DL-2/A2 与 DL-3/A4 之间的 host 串行化窗口重叠（轻微）

父会话在观察到 A2 主批日志的 "DONE" 字样后即启动了 A4，未意识到 A2 还有一个自主重试子流程仍在运行（5 个重试，09:17:43–09:19:06 UTC，针对此前失败的 KORD 月份）。A4 的 v2 脚本重启在约 09:18:35 UTC 开始发起请求，与 A2 的重试窗口有约 30-90 秒的重叠，违反了合同 §0.7 的"同一 host 同一时刻只发 1 个请求"规则。通过对两批次回执文件的时间戳交叉核对（`find -printf '%T@ %p'`）确认此重叠真实存在，但未观察到后续任何请求失败或限速迹象，判断无实际损害。**这是父会话自身的流程疏忽**（过早启动下一个任务，未等待 A2 的完整生命周期结束），非任何 agent 的责任，已主动披露。

### 5.3 DL-3/A4 的 pyIEM 校验替代披露不够充分（轻微）

A4 用自建结构校验器替代了原计划要求的真实 pyIEM `taf.py::parser()`，原因是该模块在本环境因缺少 `psycopg` 依赖而无法导入（父会话已亲自复现确认这是真实的环境限制，非编造借口）。这一替代方案本身在 `REVISION_DENSITY_AUDIT_v16.md`/`PYIEM_VALIDATION_SAMPLES_v16.json` 两个产出文件中都有如实记录，但 A4 向父会话的**口头汇报**（"pyIEM 解析抽样验证...100% 成功"）未讲清楚这不是真正的 pyIEM 解析器，存在汇报保真度不足的问题。

### 5.4 DL-4/A5 在 CCI 重启中被杀死，遗漏了状态文件；另有 2 处请求存在轻微 D10 偏离（轻微）

A5 的正式下载脚本本身已在 CCI 重启前的 11:06:19 UTC 正常完成（140 成功 + 2 失败，共 142 请求，65.85 MiB，均在 ≤200 请求/≤200 MiB 预算内），但 A5（agent 本身，非其下载子进程）在完成后续的 `DL4_STATUS.json` 撰写工作之前被 CCI 重启杀死，导致该文件缺失（其自己的 `config.json` 中已经引用了这个尚未写出的文件）。父会话已直接依据真实落盘的 `MANIFEST.json`/`config.json`/回执数据重新构建并补写了 `lamp/DL4_STATUS.json`，未凭空编造任何数字。另外，142 个正式请求中有 2 个使用了 `_proxy` 后缀在**同一 run_id 内**重试（其中一个重试的原始请求实际上已经用 `http_status=200` 真实成功，只是 `curl_exit=28` 触发了不必要的保守重试），严格按 D10 措辞应开新 run_id 而非同 run_id 内重试；但原始失败/成功回执均未被覆盖或删除，无审计丢失，性质远轻于 §5.1 的 v1 目录删除问题。

## 6. DL-6 前向采集的站点范围说明（非违规，仅供知悉）

DL-6 的合同预算 §7.4 明确写为"每小时 ≤6 请求（例如 3 站 × TAF+METAR，**或按实际冻结站数调整但不超过 6**）"。DL-1 冻结了 4 站（KSFO/KDEN/KJFK/KORD），但 6 请求/小时的硬上限决定了不可能覆盖全部 4 站 × 2 产品（需要 8 请求）。A1 的 `forward_capture.py` 选择固定采集前 3 站（`stations[:3]`），KORD 自 08:00 UTC 起始终未被前向采集覆盖。这是预算上限下的合规取舍，不是违规，但此前父会话的验证记录中一直标注为"KORD 待确认"，现已确认是**结构性排除**而非遗漏核查。如果用户希望覆盖全部 4 站，需要放宽 §7.4 的每小时上限（例如提到 8 请求/小时）或改为站点轮换采集，这是需要用户决策的事项，父会话未擅自修改。

## 7. 实际使用的模型与 agent

- 规划：Fable（plan 模式）
- A1（W0 引导+DL-0+DL-1+DL-6 启动）：`fableplan:complex-executor`（Opus）
- A2（DL-2 ASOS）：`fableplan:simple-executor`（Sonnet）
- A3（DL-5 NHC）：`fableplan:simple-executor`（Sonnet）
- A4（DL-3 TAF）：`fableplan:complex-executor`（Opus）
- A5（DL-4 LAMP）：`fableplan:simple-executor`（Sonnet）
- FIN（本报告 + 全部独立核查 + DL-6 重启 + DL4_STATUS.json 补写）：父会话本身（Sonnet 5），未委派给任何 agent

所有 agent 均未被传递 `model` 覆盖参数，符合 fableplan 路由规则。

## 8. 后续建议（供用户决策，非父会话擅自执行）

1. DL-6 现已重新拉起（PID 8212），建议后续会话定期做 §7.7 描述的"最近 3 小时目录健康检查"，避免长时间中断。
2. 若需要 KORD 也纳入前向采集，需要用户明确决定是否放宽 §7.4 预算上限。
3. DL-3 v1 目录已不可恢复，如需完整审计轨迹，只能接受这一永久性缺口。
<!-- END SOURCE F -->

</details>

## 附录 G：前向采集合同 DL-6（外部权威计划原文节选）

源文件：`plan/plan_v16_0920/DATA_ACQUISITION_PLAN_v16_CN.md`。DL-6 前向实时采集章节；预算及历史状态按原文保留。

源文件 SHA-256：`4e2228905e895fda350fcc62b2c96cb87ab09008ccf0333c9ce57e38f58cdab0`。

这是历史材料快照；其中的状态、自报结论、引用与权限描述须按其日期理解，并结合正文和附录 A 的更正，不能直接当作当前有效授权或独立核实事实。

<details>
<summary>展开附录 G 原文</summary>

<!-- BEGIN SOURCE G -->
## §7 DL-6 前向实时采集（已批准，DL-1 完成后立即启动）

### 7.1 目标

对 DL-1 冻结站点，每小时拉取当前 TAF/METAR（+LAV，如 DL-4 判定可用），持续累积前向真实数据。

### 7.2 触发条件

DL-1 完成（`stations_calendar_v16.json` 冻结）后即可启动，**不必等待 DL-2~DL-5 完成**。

### 7.3 脚本与目录

脚本放在 `data_real_v16/forward_capture/bin/`（下载会话自行编写，本文档不写代码）。要求：

- **幂等可重启**：按 UTC 小时建目录（例如 `data_real_v16/forward_capture/2026/09/21/06/`），目录已存在则跳过，不重复抓取。
- **append-only 存储**：已写入的小时目录不做原地覆盖修改。
- 逐请求回执，字段规范同 §0.3/附录 B。
- 用 `nohup` 后台循环或 `cron` 均可。

### 7.4 预算

每小时预算 **≤ 6 请求**（例如 3 站 × TAF+METAR 两种，或按实际冻结站数调整但不超过 6）；每日预算独立登记在当日目录下（例如 `data_real_v16/forward_capture/2026/09/21/DAILY_BUDGET.json`）。

### 7.5 holdout 管辖

DL-6 采集到的数据同样受 D09 冻结规则管辖：如果某小时恰好落在未来某个**新** holdout 窗口内，需要另行处理（分流至 `quarantine_holdout/`），但**当前不预设任何新 holdout**——只有旧的 `2025-02-17..23` 窗口是当前生效的隔离区间。

### 7.6 重启命令示例

```
source /mnt/afs/260010168/init-proxy.sh   # 若直连失败
nohup python3 data_real_v16/forward_capture/bin/forward_capture.py \
  --config data_real_v16/config/stations_calendar_v16.json \
  --output data_real_v16/forward_capture/ \
  >> data_real_v16/forward_capture/forward_capture.log 2>&1 &
```
（脚本文件名 `forward_capture.py` 为建议命名，具体由下载会话决定；关键是重启时使用同一个 `--output` 根目录，依赖 7.3 的幂等按小时建目录规则，不会产生重复请求。）

### 7.7 健康检查

检查最近 3 个 UTC 小时目录是否都存在（例如当前时刻为 `2026-09-21T09:xx`，则检查 `06/`、`07/`、`08/` 三个小时目录是否都已生成且各自有非空的回执文件）。若连续 3 小时目录缺失，判定前向采集已中断，需要人工或自动重启。

### 7.8 2026-09-20 修订说明

`forward_capture.py` 的实际实现把 §7.4 声明的每小时预算进一步落到了硬编码只覆盖冻结站点里的前 3 个（`stations[:3]`），导致第 4 个冻结站点 KORD 被结构性排除在前向采集之外。经用户明确授权，该实现层面的每小时上限已从 §7.4 原定的 ≤6 提高到 ≤8（覆盖全部 4 个冻结站点 × TAF/METAR 2 种产品），纳入 KORD。**这是对本节 §7.4 硬上限本身的直接突破**，合法性来自用户 2026-09-20 的明确授权，不依赖任何更高的一般性预算上限。KORD 补齐前已采集的历史小时目录保持原样，不回填。具体执行步骤见 `DL3R_REDOWNLOAD_PROMPT_CN.md` Part B（DL-6R）。

---

## 附录 A：已验证端点证据表

| 端点名称 | URL 模板 | 本地证据文件（绝对路径） |
|---|---|---|
| ASOS/METAR CSV（IEM asos.py） | `https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?station={FAA三字码}&...&report_type=3&report_type=4` | `/mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/plans/task_chain_feasibility_20260912/SPEC_01.json`（第 17-23 行，id `metar-sfo-vis`）+ `.../captures_01/metar-sfo-vis.json` + `.../captures_01/metar-sfo-vis.body` |
| TAF CSV（IEM taf.py，美国站） | `https://mesonet.agron.iastate.edu/cgi-bin/request/taf.py?station={ICAO四字码}&...&fmt=comma` | `/mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/plans/task_chain_feasibility_20260912/SPEC_03.json`（第 1-8 行，KSFO 查询）+ `.../captures_03/`（对应回执与 body） |
| 原始 NWS 文本产品（IEM nwstext API） | `https://mesonet.agron.iastate.edu/api/1/nwstext/{YYYYMMDDHHMM}-{CCCC}-{TTAAII}-{PIL}[-AAx]` | `/mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/plans/task_chain_feasibility_20260912/SPEC_04.json`（第 4-39 行，6 条真实产品 ID）+ `.../captures_04/taf-native-sfo-0.json`、`taf-native-sfo-0.body`、`taf-native-den-0.json`、`taf-native-den-0.body` 等配对文件 + `.../captures_04/MANIFEST.json` |
| NHC 归档 URL 拼接模式（非实际下载证据，是代码参考） | `https://www.nhc.noaa.gov/archive/{year}/{alNN}/{storm}.fstadv.{NNN}.shtml` 与 `.../{alNNYYYY}.public.{NNN}.shtml` | `/mnt/afs/260010168/extreme_weather_benchmark/publication/v13_completed_20260917_01/snapshot/disastertrace-starter/src/disastertrace/automated/acquisition.py`（第 30、42、174 行）与 `.../src/disastertrace/forecast_source/pipeline.py`（第 30、80、198 行） |

**已知失败证据（重要，DL-0 探测 `api/1/nws/taf.json` 一类候选路径时应参考）**：`https://mesonet.agron.iastate.edu/api/1/taf.json?station=KSFO&...` 在 2026-09-12 pilot 中返回 **HTTP 404**（`content-length: 22`，sha256 `37ec4665a8102d115ffd1ac20dae94c98b4dac64b0c1a68228aa2a531caeb35d`），证据见 `/mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/plans/task_chain_feasibility_20260912/captures_01/taf-sfo-vis.json`；同一域名下 `api/1/docs.json` 同样返回 404（`captures_01/iem-taf-docs.json`）。这说明 IEM `api/1/` 命名空间下不含 `taf.json` 这个具体路径，用户骨架提到的候选路径 `api/1/nws/taf.json` 与已验证失败的 `api/1/taf.json` 并非同一路径，但同属未经验证、且已有一个近似路径失败的先例，DL-0 探测该候选时应格外谨慎，不要假设它一定可用。

---

## 附录 B：回执 JSON 字段规范全文

字段规范原样取自 `/mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/plans/all_candidate_data_validation_20260912/fetch_samples.py`（第 28-89 行）：

| 字段名 | 说明 |
|---|---|
| `id` | 请求的唯一标识符，限 `[A-Za-z0-9_-]+`，同一批次内不得重复 |
| `url` | 实际请求的完整 URL（必须是 HTTPS） |
| `max_bytes`（来自输入 spec，回执中原样保留） | 本请求响应体截断上限（字节），默认 4 MiB |
| `started_at` | 请求发起时刻（UTC ISO8601） |
| `curl_exit` | curl 进程退出码（0 表示 curl 本身无错误；超时时记 28） |
| `http_status` | HTTP 响应状态码（超时或未获得响应时记 0） |
| `final_url_without_query` | 重定向后最终 URL，去除查询串（scheme+host+path），仅在拿到有效响应行时才有此字段 |
| `bytes` | 实际保存的响应体字节数（若超过 `max_bytes` 则为截断后的字节数） |
| `sha256` | 响应体（若被截断，则截断后的字节）的 sha256 十六进制摘要 |
| `response_headers` | 精选响应头的字典，只保留 `content-type`/`content-length`/`content-range`/`etag`/`last-modified` |
| `body_file` | 响应体落盘文件名，形如 `<id>.body`，与回执文件 `<id>.json` 配对存放 |
| `finished_at` | 请求完成时刻（UTC ISO8601） |
| `scientific_validation` | 固定为 `false`——回执只证明 HTTP 传输成功，不代表内容已经过科学校验 |
| `locally_truncated`（可选） | 若响应体因超过 `max_bytes` 被截断，此字段为 `true` |

批次级 `MANIFEST.json` 字段（取自 `/mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/plans/task_chain_feasibility_20260912/fetch_round.py` 第 58-65 行）：

| 字段名 | 说明 |
|---|---|
| `finished_at` | 批次完成时刻 |
| `requests` | 批次内请求总数 |
| `bytes` | 批次内响应体总字节数 |
| `rows` | 全部逐请求回执组成的数组 |
| `per_host_parallelism` | 单 host 并发数（固定为 1，见 §0.7） |
| `total_parallelism` | 批次整体并发 worker 数 |

复核方法：可参考 `/mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/plans/task_chain_feasibility_20260912/verify_chains.py`（第 1-40 行）演示的做法——独立重新读取已落盘的响应体字节、重新计算 sha256，与回执中记录的 sha256 比对，以确认回执未被篡改或损坏。

---

## 附录 C：决策条款 ↔ 本文档落点对照表

| 决策 | 条款出处（`RESEARCH_DECISIONS_v14_20260919.yaml`） | 本文档落点 |
|---|---|---|
| D02（H15 唯一主试点域，NHC 仅数据资格、禁止模型调用） | 第 28-44 行 | §6（DL-5）全章；§6.1 明确"不做任何模型调用"；§6.5 产出 JSON 须含 `model_calls_made: false` |
| D09（旧 Bay holdout 周继续封存，新 holdout 需全流程哈希冻结后才可开启） | 第 125-135 行 | §0.6（holdout 日历隔离）；§3.5（DL-2 月批次 holdout 分流）；§7.5（DL-6 前向采集的 holdout 管辖） |
| D10（默认不授权新花费；新批次需新 run identity/预算/截止时间；旧失败请求不重发） | 第 137-147 行 | §0.2（不可变 run identity）；§0.4（预算与截止时间）；§0.5（旧失败请求不重发） |
| D11（LAMP 概率/类别/条件概率产品分开登记；记录 IEM 归档 runtime 与原生公报时刻差异） | 第 149-160 行 | §5（DL-4）全章，尤其 §5.3（三类分开登记）与 §5.4（双时间戳记录） |
| D12（数据与运行地——本计划对其修订） | 第 162-172 行 | §0.8（D12 修订声明） |

---

（文档结束）
<!-- END SOURCE G -->

</details>
