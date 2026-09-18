# DisasterTrace 汇报讲稿

状态快照：2026-09-08 12:52:04 UTC。20 页主讲 + 4 页附录，建议约 18–20 分钟。

本讲稿同时嵌入 PowerPoint 备注。各阶段以实际结果和冻结协议为准；P6 正在运行。

## 01｜DisasterTrace

建议时长：20 秒；主讲累计 00:00。

今天汇报的是 DisasterTrace 的最新进展。项目从极端天气相关的 LLM benchmark 出发，目前已经形成自动构题、真实模型采集、确定性评分和独立重算的完整流程。主线是：先解决输出能否交付和评分的问题，再观察状态与引用错误，最后通过配对重复和真实预报文本检验结论的稳健性。这里的“天气”是证据场景，模型当前承担的是证据使用与状态维护任务。

证据：S01 / S02 / S03。

## 02｜已完成真实评测，正进入可靠性验证

建议时长：45 秒；主讲累计 00:20。

当前最完整的实测成果是 P5：三种压力条件共 1,620 条 Qwen3-8B 回答全部收齐并完成独立审计，完整正确率为 83.95%。P6 的离线分析和框架已完成，新的 2,160 槽位配对实验正在执行，具体状态以本材料首页的时间戳为准。还要强调独立来源只有三个风暴，生成题目和重复采样不会增加风暴样本数。当前成果足以支持一个可复核的研究原型，但还不足以支持广域极端天气模型排行榜。

证据：S01 / S02 / S03。

## 03｜核心任务：每次证据更新后，给出当前有据状态

建议时长：65 秒；主讲累计 01:05。

当前模型输出风速、气压、纬度和经度，每个字段要有 known 或 unknown、数值和记录行号引用。U1 测局部更新及未更新字段保留，U2 测同一窗口修订与其他窗口或实体的区分，U3 测支持缺失时保持 unknown、随后有证据时恢复 known。基础平衡矩阵为三个来源、三个任务族、两个 case、两个 branch，共 36 个 episode，每个有五个 checkpoint。真实 NHC 数据仅提供初始气象数值；后续更新、实体、时间窗口和投递均明确是受控构造，不能说它们是官方真实修订。

证据：S04。

## 04｜三个方法共享累计证据，只改变额外答案载体

建议时长：50 秒；主讲累计 02:10。

snapshot 每轮只看截至当前已交付的累计证据；structured_state 额外接收本方法最近一份结构合法的完整答案；answer_history 接收此前所有结构合法答案。每个 checkpoint 都重新建立请求，各方法、episode、重复和条件保持载体隔离。结构合法但事实错误的答案会原样进入后续载体，不会用 Gold 修复；结构无效的答案记为失败并保留先前合法载体。由于累计证据始终可见，这不是内部长期记忆的直接测量，也不是等长度的提示对照。

证据：S04 / S05。

## 05｜无需逐题人工判分：用可执行语义建立评分链

建议时长：65 秒；主讲累计 03:00。

私有编译器根据结构化事件计算 Gold；另一条 public oracle 路径只解析真正给模型看的公开文本，检查 Gold 能否从公开证据得到。主分数由严格 scorer 确定，不使用 LLM judge，也不新增逐题人工标注。已知字段必须有正确数值和支持当前版本的引用，未知字段必须是 null 且没有证据；动作来自公开的风速规则。程序负例、性质测试和独立重算是验证这条链的手段。两种实现一致有助于发现实现错误，但仍可能共享不正确的语义前提，因此任务定义和科学主张依然需要审查。

证据：S04 / S06。

## 06｜迭代不是单调刷分：每轮回答一个新问题

建议时长：60 秒；主讲累计 04:05。

这页是整个汇报的逻辑骨架。P1 发现大量输出失败，于是 T6 检验公共说明和输出预算。P2 在受控任务上仍有契约失败，所以新建共同输出契约 v2；v2 全对以后，问题变成任务能否区分模型和方法，于是 P3 平衡来源与情形并使用本地 Qwen3。P3 暴露严重格式问题，P4 将结构约束轨单列。P4 仍有语义错误，P5 增加三类压力。P5 的差异又受到随机种子、硬件与历史载体影响，于是 P6 先做错误归因，再跑匹配条件和重复。这些阶段的问题与协议不同，不应连成一条模型能力增长曲线。

证据：S07 / S08 / S09 / S10 / S11 / S01 / S02。

## 07｜第一轮转折：先保证模型能交付可评分答案

建议时长：65 秒；主讲累计 05:05。

P1 使用 DeepSeek，90 个评分回答对应 91 次物理尝试；重启后的一次明确补发单独保留，原尝试的收费状态仍未知。68 条结构有效，22 条无效，其中 20 条达到输出上限、两条结构错误。T6 新收集 270 条回答，分原说明 4096、明确说明 4096、明确说明 8192 三个条件，每条件 90 条。相同明确说明下，4096 的 snapshot 和 answer_history 仍分别只有 27/30、28/30 合法，8192 三方法都到 30/30。按预定门槛选择统一 8192；这是格式筛选，不能说更长输出对所有语义指标单调有益。

证据：S07 / S08。

## 08｜第二轮转折：契约修订奏效，小矩阵出现天花板

建议时长：60 秒；主讲累计 06:10。

P2 把任务推进到局部更新、同窗口修订和支持恢复。首轮 270 个回答中，264 个格式有效，完整正确 262 个；六个格式失败和三个引用字段错误保留，三个引用错误集中在两个合法 checkpoint，不能直接相加为九道错题。v2 统一了公共输出说明，明确 state、action、record_id 和 ASSERT 行引用；新的 270 条回答全部合法且完整正确。两轮采样时间不同，所以不能把全部变化都归因于提示词。不过开发矩阵全对确实说明：继续比较同一小矩阵已经很难观察方法差异，应扩展平衡设计与模型覆盖。

证据：S09 / S10。

## 09｜第三轮转折：将格式交付与语义正确分开看

建议时长：70 秒；主讲累计 07:10。

P3 扩展到 36 个平衡 episode，共 540 条 Qwen3-8B 自由输出，只有 200 条合法，完整正确 193 条。如果只报合法回答中的正确比例，会隐藏 340 条失败。P4 使用只约束最终 JSON 容器、字段、类型与枚举的 grammar，540 条全部通过原任务契约，完整正确 490 条。grammar 不包含 Gold、不提供正确 record_id 或行号，也不约束正确数值和动作，因此仍留下 15 个值或状态错误和 39 个引用错误。自由输出和受约束输出应分轨报告；解码分布及后续模型历史不同，这不是纯语义能力的同输入因果比较。

证据：S11 / S12。

## 10｜P5：在 Gold 不变的前提下加入三类压力

建议时长：50 秒；主讲累计 08:20。

P5 对基础任务做三种 level 4 变换：增加中间修订链，加入其他实体或窗口的无关记录，以及晚到的旧记录重放。每个 checkpoint 的目标值、状态、当前引用和动作 Gold 保持不变，方便比较。每因素 540 个新回答，总计 1,620。真实压力不是从 c0 就出现：修订链和 scope 首次改变输入在 c2，旧记录重放到 c4；六个修订链 episode 没有可扩展 PATCH，全程没有新增压力但仍保留。这些曝光和零增量信息对解释分数十分关键。

证据：S01 / S06。

## 11｜P5 真实结果：全合法后，方法差异仍然存在

建议时长：75 秒；主讲累计 09:10。

这张表给出 P4 基础任务和三组 P5 压力条件。P5 总完整正确是 1,360/1,620，即 83.95%，三组回答全部合法。structured_state 在基础、修订链和旧记录重放条件中较高；但在无关作用域条件下 snapshot 是 155/180，structured_state 是 154/180，只差一个 checkpoint，因此不能说结构化状态始终最佳。answer_history 在这次样本中的完整正确率较低，这提示历史答案可能带来传播或来源更新问题，但不能单凭这张表证明其内部机制。P4/P5 硬件和采样身份不同，只做描述性比较。

证据：S01 / S12 / S13。

## 12｜主要可观察错误：值正确，来源却没有正确绑定

建议时长：65 秒；主讲累计 10:25。

P6 对 P5 的原始输出做确定性归因，原评分保持不变。230 个纯引用字段错误中，109 个是同值旧版本，48 个是未知记录 ID，26 个是错误有效窗口或测量类型，19 个是错误变量或单位，12 个是异值旧版本，11 个是越界行号，五个是错误实体。109/230 为 47.39%，是最大的主类，但不是所有引用错误。主类按预定优先级互斥归类，多个混合引用的细节另行保留。320 处字段错误落在 260 个错误 checkpoint；29 个动作错误都与风速错误重叠，不能再加成额外错题。

证据：S02 / S13。

## 13｜真实例子：60 mph 没变，正确引用已经换了

建议时长：50 秒；主讲累计 11:30。

这是按固定排序选出的真实 P5 错误，展示的是 Dorian 初值来源派生的受控任务，不是官方修订。模型回答风速 60 mph，数值正确，但引用的是旧记录 record-62dacf3b5260c5a4f615951f 的第二行；当前权威记录已变为 record-0db797c9653dc4d169f593f5 的第二行。按“数值正确”可以得分，按“当前版本有据”必须失分。这说明 benchmark 的价值不只在数值抽取，还在同值更新后能否刷新来源。这里观察到了旧引用，并没有从文本推断模型内部是否真正遗忘。

证据：S14。

## 14｜能力边界：当前合法任务可由简单公开策略完整求解

建议时长：45 秒；主讲累计 12:20。

P6 审计了七个不读取 Gold 的公开程序策略。按完整事实键选择已交付断言中发布时间最大者，在基础任务和三个压力条件下都是 180/180，与独立 oracle 一致。这个结果来自当前合法域的约束：每个键只有线性版本链，父先交付，子发布时间严格增加，没有合法分叉或撤销。因此当前任务可以测显式状态维护、作用域过滤和精确引用，但不应声称必须依靠复杂版本图推理。相反，忽略作用域的最后交付策略在 scope 条件下只有 78/180，说明按正确键过滤本身仍是必要条件。

证据：S15。

## 15｜P6：把历史分差变成更有解释力的配对问题

建议时长：65 秒；主讲累计 13:05。

P5 到 P4 的分数变化混合了处理因素、不同种子、MIG 与完整 H100 差异，以及后续历史载体的分叉；连六个没有新增压力的修订链对照也会波动。P6 因此选择最小 E1：base 与 scope level 4，三方法，两次重复，共 2,160 个机会。跨条件配对种子相同，condition 属于运行身份但不进入种子身份；方法和 repeat 仍隔离，条件先后顺序平衡，同一完整 H100 执行。报告 both_correct、base_only、condition_only、both_wrong 四种结局，同时看五个 checkpoint 全对的 episode success 和两次均成功的 pass^2。它改善设计，但两次重复、三个来源和不同输入长度仍限制推论。

证据：S05 / S16。

## 16｜最新执行状态：P6 正在收集真实回答

建议时长：45 秒；主讲累计 14:10。

这页的保存条数与时间戳由只读状态脚本生成，演示时应按该时间理解。唯一模型作业为 pt-gxxtikov，使用一张完整 H100，计划 2,160 个回答，不选择性补跑。自动 CPU 后处理已经安排，收集完成后仍要核对作业终态、独立报告、token grammar 重放和迁移重建。P6 离线正确程序和无效对照已经分别跑了 2,160 个槽位，共 4,320 个程序回答；这些用于验证评分和失败分母，绝不能当成新的模型成绩。若后续运行结束，应依据新的最终报告更新此页。

证据：S03 / S16。

## 17｜下一条数据主线：官方预报的真实多版本证据

建议时长：60 秒；主讲累计 14:55。

下一步希望让天气场景更实质：读取官方 NHC forecast advisory，针对同一绝对有效时刻，问当前已交付的公告中哪一版本明确覆盖该时刻、值是什么、依据在哪一行。已冻结的来源试点最多 12 份正文：Francine 的 005 到 010，Ida 的 009 到 014。双解析器及自动隔离机制已准备，实际获取和准入状态以快照记录为准。新任务先做经纬度和最大持续风速 KT，保留终止状态和来源行。发布时间、预报有效时刻、抓取时间及受控交付步骤必须分开；使用已发布预报仍是证据使用评测，不等于模型自身数值预报。

证据：S17 / S18。

## 18｜后续按可验收里程碑推进

建议时长：60 秒；主讲累计 15:55。

近期第一优先级是把 P6 收尾，得到按条件、方法、repeat、来源和整条 episode 的完整结果。第二步是从双解析准入的 NHC 文本建立离线 forecast-claim 任务，自动枚举同一绝对有效时刻的查询，并保留所有排除与隔离记录。第三步是载体表示对照：同一份已保存答案分别渲染成 JSON 和文本表格，信息完全保留、错误不修复，单独测 token 长度。随后再选择与冻结任务匹配的第二模型，并扩大独立开发事件。最终冻结后再使用保留事件；已有八个声明保留 ID 都必须保护，不能只保护七个通过格式准入的风暴。

证据：S18。

## 19｜当前成果与仍然缺少的证据

建议时长：45 秒；主讲累计 16:55。

目前贡献可以表述为：构建了一个自动评分、可审计的动态天气证据评测原型；分开报告格式与语义；观察到明确的数值和来源绑定错误，并开始配对重复验证。尚缺的证据包括广泛独立天气事件、同协议多模型重复、真实公告版本的完整任务验证，以及等信息或等长度载体控制。三个风暴不足以推断总体排名；受控 PATCH 不等于真实气象修订；累计公开证据不支持内部长期记忆结论；程序满分证明评分流程能跑通，不证明模型高分或科学定义完全正确。

证据：S04 / S05 / S15 / S18。

## 20｜汇报应落在三个结论上

建议时长：30 秒；主讲累计 17:40。

收束时可以说：第一，项目已从方案走到真实模型评测和可离线复核的工程闭环。第二，P4/P5 显示输出合法并不等于值和当前引用正确，P5 的纯引用错误尤其值得研究。第三，P6 正在用配对重复提高解释力，随后通过官方多版本预报文本和同协议模型比较检验外部有效性。这是下一阶段最有价值的工作，目标是让分数具有明确含义和可解释的失败模式。

证据：S01 / S02 / S03 / S18。

## 21｜附录 A｜真实运行结果总表

附录：按提问选讲。

本表可以用于回答到底跑了多少、各轮发生了什么。T6 的三个条件合计 270，不是三个 270；P5 的三个条件合计 1,620；P1 的 90 个回答跨 91 次尝试。这里不把任何程序诊断计入模型结果，也不把不同任务版本汇总为模型能力分数。详细分子分母和局限见 ITERATION_RESULTS.md。

证据：S07–S13。

## 22｜附录 B｜指标与错误怎样计数

附录：按提问选讲。

完整正确要求四字段的状态、数值、当前来源引用和动作全部正确。已知数值正确与已知数值加当前引用正确单独报告；未知字段也有独立分母。P6 整条 episode 成功要求五个 checkpoint 全对，pass^2 要求同一个条件和方法下的两次 episode 都成功，它不是“多试几次取最好”的 pass@k。所有无效、未返回和未提交机会仍留在预定分母；中断报告明确标 incomplete。

证据：S04 / S05 / S13。

## 23｜附录 C｜完成证据与可复查交付

附录：按提问选讲。

P5 的三个作业全部成功，九个采集、报告、核验子进程退出零；432,742 个 final/EOS token 重放没有 grammar 违规，完整 P4 和三组 P5 报告在无 Torch/vLLM 的 CPU 副本中重建。P6 离线正确与无效程序报告也完成迁移重建。测试执行之间有重复，不能简单相加。GitHub 的 P5 快照在私有仓库 next-phase-v1，已验证提交为 dd5ee358；P6 本地进度比该提交更新。PPT 和讲稿独立保存，不修改实验源码或运行记录。

证据：S01 / S02 / S19。

## 24｜附录 D｜已有 benchmark 的设计参考

附录：按提问选讲。

ALCE 提示区分值正确与引用支持，CheckList 提供最小功能、不变量和方向性测试思路，tau-bench 启发整条 episode 与多次重复的可靠性，RULER 提醒将长度和决策复杂度分开。MemoryAgentBench、STATE-Bench、STALE/CUP-Mem 提供状态与历史实验的边界参考，ExtremeWeatherBench 则提醒独立天气事件和预报目标的重要性。本轮采纳的是提供方案中的设计整理，没有新下载并复现这些项目的完整任务或成绩；实际运行依赖是项目已有的 vLLM、XGrammar 等冻结实现。

证据：S20。

## 证据索引

机器报告的数据与 SHA-256 清单另见 `report_data.json` 和 `evidence/source_index.json`。

- S01：[P5 完整模型发现](/mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/disastertrace-starter/artifacts/p5_stress_level4_v1/MODEL_FINDINGS.md)
- S02：[P6 离线交接与归因](/mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/disastertrace-starter/artifacts/p6_offline_v1/HANDOFF_POST_P5.md)
- S03：[P6 当前导航](/mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/disastertrace-starter/CURRENT_PHASE.md)
- S04：[受控任务语义](/mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/disastertrace-starter/docs/P2_CONTROLLED_SEMANTICS_V1.md)
- S05：[P6 配对重复协议](/mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/disastertrace-starter/docs/p6/MEASUREMENT_PROTOCOL.md)
- S06：[P5 压力协议](/mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/disastertrace-starter/docs/P5_STRESS_LEVEL4_V1.md)
- S07：[P1 实测入口](/mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/disastertrace-starter/README_P1_DEEPSEEK.md)
- S08：[T6 实测入口](/mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/disastertrace-starter/README_T6_CALIBRATION_V1.md)
- S09：[P2 v1 实测入口](/mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/disastertrace-starter/README_P2_DEEPSEEK_V1.md)
- S10：[P2 v2 实测入口](/mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/disastertrace-starter/README_P2_DEEPSEEK_OUTPUT_CONTRACT_V2.md)
- S11：[P3 实测报告](/mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/disastertrace-starter/artifacts/p3_local_balanced_v1/model_report/report.json)
- S12：[P4 实测报告](/mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/disastertrace-starter/artifacts/p4_constrained_output_v1/model_report/report.json)
- S13：[P5 错误守恒计数](/mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/disastertrace-starter/artifacts/p6_offline_v1/posthoc_final/conservation.json)
- S14：[实际错误例子](/mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/disastertrace-starter/artifacts/p6_offline_v1/actual_examples/EXAMPLES.md)
- S15：[简单求解器适用边界](/mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/disastertrace-starter/docs/p6/SOLVER_EQUIVALENCE.md)
- S16：[P6 实时执行交接](/mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/disastertrace-starter/artifacts/p6_live_v1/CONTINUE.md)
- S17：[NHC 来源冻结范围](/mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/disastertrace-starter/artifacts/nhc_forecast_source_v1/SOURCE_SCOPE.json)
- S18：[后续研究计划](/mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/disastertrace-starter/artifacts/p6_live_v1/NEXT_RESEARCH_PLAN.md)
- S19：[GitHub 发布核验](/mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/review-outputs/p5-publication-20260908/publication_receipt.json)
- S20：[上游设计参考范围](/mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/disastertrace-starter/docs/p6/UPSTREAM_REUSE.md)
