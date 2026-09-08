# DisasterTrace：给 ChatGPT Pro 的完整复查交接文档

文档日期：2026-09-08。覆盖截至 P5 ACP GPU 评测完成、归档验收通过的状态。
仓库：<https://github.com/sisuolv/disastertrace-benchmark>；本轮分支：`next-phase-v1`。

本文供研究设计与代码复查使用，包含问题定义、已实现内容、真实结果、证据入口、
已知限制和后续工作。阅读本文不需要此前聊天记录。旧版
[REVIEW_FOR_CHATGPT_PRO.md](REVIEW_FOR_CHATGPT_PRO.md)保留早期 P1/校准准备阶段的事实；
本轮请以本文、[P5 实测入口](README_P5_ACP_V1.md)和对应冻结产物为起点。

## 1. 可以直接复制给 ChatGPT Pro 的任务

```text
请对附件/仓库中的 DisasterTrace benchmark 做一次严格的研究设计与代码复查。
先读 disastertrace-starter/REVIEW_FOR_CHATGPT_PRO_P5.md，再检查它引用的实际源码、
测试、冻结协议和原始证据。请先列出你实际能够访问的材料及其版本；私有仓库
无法访问、压缩包无法读取或不能运行代码时，请说明具体缺失，不要假定已经验证。

目标是评测 LLM 在受控天气记录流中处理局部更新、修订、作用域、缺失和旧证据
重放的可靠性。所有主评分必须由自动 Gold 和确定性规则完成，不新增逐题人工
标注、专家逐题裁决或 LLM judge。你的工作是审查研究与实现，不是替模型回答判分。

请优先寻找会改变分数、方法比较或研究结论的问题：
1. Gold 与公开输入隔离、时间/修订语义、独立 public oracle 是否存在共同错误；
2. 无效/缺失回答、引用、固定分母、历史载体、随机种子和采集审计是否正确；
3. 结构化解码是否只约束结构，有没有间接编码答案、引入不公平的语义帮助；
4. P4/P5 的硬件、种子、模型历史、来源依赖与零增量控制如何限制比较；
5. 与已有 benchmark 的差异是否成立，天气场景是否有不可替代的研究价值；
6. 后续应先做同硬件重复、扩大独立事件、第二模型，还是调整任务定义。

对每条发现给出：严重程度、文件/函数/行号、触发条件或最小反例、实际影响、
最小修复方案与验收测试。区分“已证实缺陷”“待验证假设”“已披露研究局限”。
不要把描述性结果升级为统计显著、因果记忆优势或天气预测能力。
不要仅用测试数量或文件 hash 证明科学有效性；也不要只给宽泛的扩功能清单。

你可以进行只读分析和不调用模型的离线重算。不要重启已消耗的 GPU/API 任务，
不要改写历史 Gold、评分器、回答或失败记录。若不能执行命令，不要声称测试通过。
最后给出一份按优先级排序、可以交给编码代理执行的最小下一阶段计划，每项说明
交付物、依赖、验收标准，以及它能消除什么不确定性。
```

建议让审阅者先完成主张与测量有效性检查，再展开实现细节。一次只收到本文时，
可以做设计层面审查；源码缺陷和真实运行是否可信，需要继续读取对应证据。

## 2. 获取材料与确定版本

本仓库保持私有。仅提供 GitHub URL 不保证审阅环境能访问；需要该环境已有对应
仓库访问能力，或由项目所有者提供文件附件。无需把模型 API 密钥或 GitHub 凭据
写入审阅提示词或文档。

| 材料 | 用途与边界 |
| --- | --- |
| `next-phase-v1` 分支 | 最新代码、各阶段历史记录和本文；请记录实际 commit SHA，分支以后可能更新 |
| [轻量复查附件](../publication/p5_review_20260908/chatgpt_pro_p5_review.zip) | 本文、代码、测试、关键协议和结果；适合先读，完整范围见包内清单，不代替全量采集复验 |
| [完整 P5 复查包](artifacts/p5_stress_level4_v1/p5_stress_level4_acp_v1_review.tar.gz) | 冻结源码、三组原始模型回答、P4 对照输入、复验脚本及许可；用于完整 P4/P5 CPU 重算 |
| [发布说明](../publication/p5_review_20260908/README.md) | 上传范围、版本核对、附件与冻结历史记录的关系 |

完整 P5 包为 **68,654,483 bytes**，SHA-256 为：

```text
ec52c2b8197358f253a570638bad02e86f8b42d1add410aceaca89865eb8f1b3
```

其 7,097 个成员已在归档阶段校验，详见
[archive_verification.json](artifacts/p5_stress_level4_v1/archive_verification.json)。
该包早于本文封存，因此不会含有本轮新写的复查文档；请同时提供本文。
包内 `published:false`、旧文档中的“尚未调用”是当时的状态，不能改写成事后状态。
仓库根目录的 `EXPORT_MANIFEST.json` 和 `handoff_validation/` 属于早期
`a23f73adadcbec077b9fcf2aecf8f45dfa4fe061` 快照，不是整个 P5 分支的新验收清单。

## 3. 研究目标：目前究竟在测什么

项目最初希望建立一个极端天气相关的 LLM benchmark，并结合已有开放评测框架。
为了避免新增逐题人工复核，当前落实为两个应分开理解的任务阶段：

1. 早期自动化天气公告轨：从 NHC 原始公告中解析事实、设置交付时序并核对引用。
2. 当前受控动态记录轨：继承真实来源中的初始气象数值，程序生成明确的状态更新、
   修订关系和交付事件，测试模型在每个 checkpoint 能否给出有据可查的当前状态。

当前最稳妥的定位是：**天气记录背景下的动态证据与显式状态更新可靠性评测**。
当前输入以文本化结构记录为主，没有完成广域多灾种、多模态预测 benchmark，
也不直接测数值天气预报、真实港口操作决策或开放式应急建议质量。

例如，某记录对同一实体、同一有效窗口给出风速 90 mph，后续 PATCH 仅把风速
改成 110 mph。正确行为是更新风速和它的当前引用，保留未更新的气压与位置；
旧记录再次送达不能把风速恢复成 90。其他实体或其他窗口的 120 mph 不应覆盖
当前目标。暂未交付任何支持的字段应为 unknown，支持到达后再恢复 known。
这个例子是语义说明，不是新增模型样本或官方气象修订。

## 4. 数据、时间语义与自动 Gold

### 4.1 来源与构造部分

原 NHC 准入资料目录包含 10 个完整事件，划分为 3 个开发事件和 7 个保留事件。
当前受控轨的三个开发来源组为 `AL092021`、`AL062018`、`AL052019`，分别对应
Ida 2021、Florence 2018、Dorian 2019。原目录有格式性拒收记录，这不是全体风暴
随机抽样，也不能证明模型预训练数据去污染。

真实来源提供初始四字段数值及其出处；实体标识、2040 年示例有效窗口、更新值、
修订图、交付时间和 `CONTROLLED_RECORD` 文本由程序构造，并带有
`controlled_generated` 来源标记。后续 PATCH 不是 NHC 发布的真实纠错历史。
`issued_at`、有效窗口和 `delivered_at` 是不同概念；受控交付不能被描述为已证明
历史上那一刻公众确实能够访问相应材料。

### 4.2 基础任务矩阵

| 维度 | 当前设计 |
| --- | --- |
| 四个字段 | `maximum_wind_mph`、`minimum_pressure_mb`、`latitude_deg`、`longitude_deg` |
| U1 | 局部 PATCH，未更新字段保留；包括变化值与同值更新的情况 |
| U2 | 同窗口修订与不同窗口/实体记录的区分，旧版本重放不应覆盖新版本 |
| U3 | 支持暂时缺失与后续恢复，包含支持一直可见的配对控制 |
| case / branch | 每来源、每任务族各有 primary/secondary 与 active/control |
| checkpoint | c0 至 c4，共五个；c0 尚无证据，是未知状态控制 |
| 基础规模 | 3 来源 × 3 任务族 × 2 case × 2 branch = 36 个 episode |
| 模型矩阵 | 36 episode × 5 checkpoint × 3 方法 = 540 个回答，一次采样 |

36 个 episode 由 18 个配对 root 展开，方法分别形成 108 条隔离轨迹。
这些数量都是设计单元，不能当成独立天气事件数。

### 4.3 自动化可信链条

生成器和私有 Gold 编译器构造任务真值；另一个 public oracle 只从模型能看到的
公开记录解析并重建答案，用来检查公开证据是否足以支持 Gold。还运行刻意错误的
程序控制，例如错误使用旧证据、忽略作用域或错误更新，观察评分是否能区分它们。
这些程序输出均为 diagnostic，不是模型回答。

相关实现：[generator.py](src/disastertrace/controlled/generator.py)、
[compiler.py](src/disastertrace/controlled/compiler.py)、
[public_oracle.py](src/disastertrace/controlled/public_oracle.py)、
[renderer.py](src/disastertrace/controlled/renderer.py)、
[scorer.py](src/disastertrace/controlled/scorer.py)。
两条实现一致降低了一类实现错误风险，但不能证明不存在共同语义错误或任务定义偏差。
请审阅它们的依赖和负例，判断“独立”是否足够有力。

## 5. 三种方法及信息公平性

| 方法 | 每轮可见公开证据 | 额外载体 |
| --- | --- | --- |
| snapshot | 截至当前已交付的累计证据 | 无以前的模型答案 |
| structured_state | 同一累计证据 | 本方法上一个结构合法的状态与动作 |
| answer_history | 同一累计证据 | 本方法此前结构合法的完整答案序列 |

每轮重新构造消息，不沿用未申明的对话缓存。结构合法但事实错误的答案仍进入该
方法后续载体；不使用 Gold 修复历史。无效答案保留为失败，但不替换上一个合法
载体。reasoning 内容不传到下一轮，三个方法和不同 episode 不共享答案。

这比较的是**累计证据条件下，显式答案载体对表现的影响**。三种方法的输入长度、
示例暴露和错误传播机会并不相同；由于所有原始公开证据仍在，不能直接推论模型
内部记忆是否更强。真正的有限证据窗口、压缩或增量观察需要另立协议和匹配控制。

## 6. 从 P1 到 P5 已经完成的工作

| 阶段 | 实际完成 | 解读边界 |
| --- | --- | --- |
| P1 与引用评分修订 | DeepSeek 小规模公告轨、真实采集/中断续跑、独立重算；90 个响应对应 91 次尝试 | 旧输出格式与预算失败保留；原 attempt 79 的费用仍未知 |
| T6 输出校准 | 270 个真实 DeepSeek 回答，按预定门槛选择共同 8192-token 上限 | 这是开发筛选，不是总体可靠性保证 |
| P2 首轮 | 270 个真实 DeepSeek 回答；6 个无效回答，3 处引用错误，共同格式门槛失败 | 无选择性重试；失败推动独立版本的公共输出契约 |
| P2 输出契约 v2 | 新的 270 个真实回答全部通过，三个方法各 90/90 完整正确 | 有天花板效应；不能替代新版 540 槽位的模型对照 |
| P3 平衡任务与本地模型 | 36 episode，540 个 Qwen3-8B 自由输出；200 个契约合法、340 个无效，193/540 完整正确 | 格式严重影响主分数；不能只用 193/200 宣称性能 |
| P4 结构约束输出 | 同一平衡任务，540 个真实 Qwen3-8B 回答，全部通过原始契约 | 仍有语义/引用错误，单独保留自由与受约束轨 |
| P5 三因素压力测试 | 三组各 540 个真实回答，共 1,620；全部通过契约，1,360 完整正确 | 三个依赖来源、一次采样、硬件/种子差异，结果为描述性 |

对应历史入口：
[P1](README_P1_DEEPSEEK.md)、[T6](README_T6_CALIBRATION_V1.md)、
[P2 v1](README_P2_DEEPSEEK_V1.md)、[P2 v2](README_P2_DEEPSEEK_OUTPUT_CONTRACT_V2.md)、
[P3](README_P3_LOCAL_BALANCED_V1.md)、[P4](README_P4_CONSTRAINED_OUTPUT_V1.md)。
不同任务版本、输出轨和重复数的成绩不能拼成一个模型排行榜。

## 7. P4/P5 的模型与解码设置

模型是完整 BF16 Qwen3-8B，权重从官方 Qwen ModelScope 仓库获取并逐文件绑定
revision、大小和 SHA-256。该身份不应被写成未经观察的 Hugging Face commit。
模型卡、许可证和配置保留，发布包不含权重。

| 设置 | 实际协议 |
| --- | --- |
| Python / GPU 库 | Python 3.10.12；Torch 2.8.0+cu128；vLLM 0.10.2 V1；XGrammar 0.1.23 |
| 采样 | thinking enabled，temperature 0.6，top_p 0.95，top_k 20，min_p 0，repetition penalty 1 |
| 长度 | context 16,384；总生成上限 8,192，包含 reasoning 与最终答案 |
| 执行 | 单卡、tensor parallel 1、每批至多 12 条不同轨迹；按 checkpoint 波次执行 |
| 约束 | reasoning 不受 grammar 限制；生成关闭 thinking 的分隔符后约束最终 JSON |
| 硬件 | P4 为 H100 MIG 3g.40gb；P5 为三个独立完整 H100 80GB 作业 |

grammar 约束容器、字段名、类型与枚举，不提供正确气象值、当前 record_id/行号
集合、数值范围/精度、unknown 一致性或动作逻辑。评分仍使用原始严格任务解析器。
请检查属性顺序、EOS、特殊 thinking token 和 schema 表达是否引入额外帮助。

JSON 语法合法、结构 schema 合法、原始任务契约合法、语义完整正确是四个不同层次。
本次前面三个层次全过，不等于最后一个层次全过。

## 8. P5 压力因素、主要分数与错误

### 8.1 干预如何构造

| 因素 | 想测的失误 | 保持不变的主要对象 |
| --- | --- | --- |
| revision_chain，level 4 | 中间修订链干扰、引用未刷新或错误回滚 | 最终有效值、状态、当前引用和动作 Gold |
| irrelevant_scope，level 4 | 把其他实体/窗口的信息写入目标状态 | 同一目标与其 Gold |
| late_stale_replay，level 4 | 把晚到旧记录误当最新权威版本 | 版本继承关系和 Gold |

每组保留全部 36 个基础 episode 和 540 个回答机会。逐 checkpoint 比较 Gold，
逐方法比较 116 个指标分母，检查公开输入映射、程序 oracle 与机会集合。
修订链中六个没有可扩展 PATCH 的 episode 保留为零增量控制，不能只挑有变化的题。
level 16 不能在当前 context 内为全部程序载体保留完整 8192-token 输出预算，
尚未进入模型实验；不能截断证据后混进本轮结果。

### 8.2 真实模型结果

下表分子为完整正确 checkpoint，所有格子的分母均为 180。

| 条件 | snapshot | structured_state | answer_history |
| --- | ---: | ---: | ---: |
| P4 基础任务 | 167/180 (92.78%) | 178/180 (98.89%) | 145/180 (80.56%) |
| P5 修订链 | 150/180 (83.33%) | 164/180 (91.11%) | 135/180 (75.00%) |
| P5 无关作用域 | 155/180 (86.11%) | 154/180 (85.56%) | 135/180 (75.00%) |
| P5 旧记录重放 | 163/180 (90.56%) | 172/180 (95.56%) | 132/180 (73.33%) |

P5 总计 **1,360/1,620 = 83.95%**。全部 27 个预设格式单元为 60/60 合法、
零长度终止，通过既定 58/60 与至多两次长度终止的开发门槛。
无关作用域下 snapshot 仅比 structured_state 多正确一个 checkpoint，不能据此
建立稳定方法排名。详细表见 [RESULT_TABLES.md](artifacts/p5_stress_level4_v1/analysis/RESULT_TABLES.md)。

| 因素 | 值/状态错误 | 值正确但引用错误 | 错误 checkpoint | 动作错误 |
| --- | ---: | ---: | ---: | ---: |
| 修订链 | 27 | 79 | 91 | 7 |
| 无关作用域 | 34 | 100 | 96 | 11 |
| 旧记录重放 | 29 | 51 | 73 | 11 |
| 合计 | 90 | 230 | 260 | 29 |

320 处字段错误落在 260 个 checkpoint，29 个动作错误都与风速错误重叠，不能
额外算作 29 道错误题。动作只按风速规则选择 `prepare`、`monitor` 或
`request_evidence`，不是实际应急决策质量指标。

每个方法/因素单元的未知状态为 156/156 正确。c0 控制全部正确，共 324/324；
c1-c4 合计为 1,036/1,296。后者是补充诊断，不能替换完整主分母。
主指标要求四字段的值/状态、当前引用与动作全部正确；另报已知值、已知有据、
未知、更新、保留、引用刷新和动作等指标，防止未知或粗粒度动作掩盖问题。

### 8.3 配对差异不能直接等同干预因果效应

P5 的所有 1,620 个 slot 都有新因素身份，种子随之改变；回答变化又会改变后续
模型载体。P4/P5 还有 MIG/完整 H100 的差异。即使六个零增量修订链控制未添加
记录，每方法 30 个 checkpoint 的正确数也从 snapshot 27 到 30、structured_state
28 到 25、answer_history 29 到 30。

因此，不能把每一分下降都归因于压力因素。比较器保留双向变化：例如无关作用域
snapshot 有 22 个“基础正确、压力错误”和 10 个“基础错误、压力正确”，净减少
12 个不是完整故事。请检查
[comparison.json](artifacts/p5_stress_level4_v1/stress_comparison/comparison.json)
中的来源、任务族、case、checkpoint 和有效强度分解。

## 9. 真实执行与验证证据

| 作业 | 实际结果 | 原始回答目录 |
| --- | --- | --- |
| `pt-rtvkp7h8` | 修订链，540/540，SUCCEEDED | [revision_chain run](work/p5-qwen3-revision-chain-v1) |
| `pt-rcxzh9sh` | 无关作用域，540/540，SUCCEEDED | [irrelevant_scope run](work/p5-qwen3-irrelevant-scope-v1) |
| `pt-g3y6l751` | 旧记录重放，540/540，SUCCEEDED | [late_stale_replay run](work/p5-qwen3-late-stale-replay-v1) |

三作业并行使用三卡，遵守最多四张 H100 的资源上限；不是三卡张量并行模型。
generation-disabled 预检作业 `pt-nmrxrdxx` 只加载和核验环境，模型回答数为 0。
实际评测在 2026-09-08 07:36:54 UTC 收齐，九个 collect/report/verify-report
子进程退出码均为 0，无平台重试、模型重试、缺失、长度终止或提取错误。
提交成功与最终完成分别记录，完成证据见
[completed_jobs_verified.json](artifacts/p5_stress_level4_v1/completed_jobs_verified.json)。

| 验证项 | 已观察到的证据 | 不能据此推出 |
| --- | --- | --- |
| P5 离线验收 | 1,118 既有 CPU 测试与 27 新测试通过；2,229 文件验收记录 | 1,145 个独立模型样本或本轮全部重新测试 |
| ACP 扩展测试 | 本轮 18 启动器测试与 7 比较器测试通过 | 与历史重复运行相加得到更大测试套件 |
| 新 live 验收 | 三个冻结执行，每组 540 条程序诊断；验收绑定 4,425 文件 | 程序诊断就是模型能力 |
| 原始 token 重放 | 432,742 个 final/EOS token，XGrammar 违规为 0 | 所有气象值/引用正确 |
| CPU 迁移复验 | 重建 P4+三组 P5 报告及分析/配对比较；原数据、权重与网络被阻止，环境无 Torch/vLLM | 重新生成模型答案或硬件可信证明 |
| 历史保全 | 9,092 项历史记录及 56 个 P4 源码文件保持一致；P5 64 文件冻结源码另验 | 所有旧阶段都能仅靠轻量附件完整重建 |
| 完整归档 | 7,097 个成员校验通过 | 外部研究审稿已经完成 |

本轮输入 5,398,068 tokens，生成 1,944,316，合计 7,342,384。
各组采集进程约 25.93、30.07、25.75 分钟，并行运行；不是单条请求延迟或公平的
硬件吞吐比较。P5 付费 LLM API 调用为 0，GPU 货币成本未知；历史 DeepSeek 成本
是另一阶段的捕获价格估计，不能将“零 API 调用”解释为整个项目免费。

关键身份：

```text
live_acceptance_id  52a5bc44e44da133a44874b422c2adc17d111ce66e56ca41604475b97521c523
analysis_id         dfeaa56c70e85fe351bf52fe577d9207f1da69beefbbfb94ba60b835f9259c11
comparison_id       bfd5fb99fe2b84cce4a650e82e6602327b91996e979c99f6756f025345a3d4fe
```

还请保留失败轨迹的审查：早期新核验包装器用了错误返回键名，已有失败日志和
修正；原有后处理 lint 失败也保留。它们不应被写成始终无错误的一次执行。
详见 [REVIEW_GUIDE_ACP.md](artifacts/p5_stress_level4_v1/REVIEW_GUIDE_ACP.md)。

## 10. 建议的代码阅读路线

以下路径相对于 `disastertrace-starter/`。`src/` 便于阅读；判断实际某次模型执行
使用了什么代码时，以其 `execution_live/implementation_source/src/` 为准，不能
用之后的工作区代码替换历史绑定。

| 审查主题 | 入口 |
| --- | --- |
| 严格任务类型、数值与引用契约 | [controlled/schema.py](src/disastertrace/controlled/schema.py)、[controlled/output_contract.py](src/disastertrace/controlled/output_contract.py) |
| 来源与 Gold、公开 oracle、renderer | [controlled/generator.py](src/disastertrace/controlled/generator.py)、[controlled/compiler.py](src/disastertrace/controlled/compiler.py)、[controlled/public_oracle.py](src/disastertrace/controlled/public_oracle.py)、[controlled/renderer.py](src/disastertrace/controlled/renderer.py) |
| 主指标、固定分母与错误归因 | [controlled/scorer.py](src/disastertrace/controlled/scorer.py) |
| 平衡选择与压力变换 | [local_eval/data.py](src/disastertrace/local_eval/data.py)、[local_eval/difficulty.py](src/disastertrace/local_eval/difficulty.py)、[stress_eval/data.py](src/disastertrace/stress_eval/data.py) |
| 结构 grammar 与 Qwen reasoning | [constrained_eval/contract.py](src/disastertrace/constrained_eval/contract.py)、[constrained_eval/adapter.py](src/disastertrace/constrained_eval/adapter.py)、[constrained_eval/grammar.py](src/disastertrace/constrained_eval/grammar.py) |
| 冻结身份、请求、轨迹和采集 | [stress_eval/execution.py](src/disastertrace/stress_eval/execution.py)、[stress_eval/runtime.py](src/disastertrace/stress_eval/runtime.py) |
| 独立采集审计、原始回答重建 | [stress_eval/audit.py](src/disastertrace/stress_eval/audit.py)、[local_eval/adapter.py](src/disastertrace/local_eval/adapter.py) |
| ACP 一次启动与失败终止 | [launch_p5.py](artifacts/p5_stress_level4_v1/launch_p5.py)、[acp_worker.py](artifacts/p5_stress_level4_v1/acp_worker.py)、[acp_common.py](artifacts/p5_stress_level4_v1/acp_common.py) |
| 数据分析与配对校验 | [analyze_p5.py](artifacts/p5_stress_level4_v1/analyze_p5.py)、[compare_stress.py](artifacts/p5_stress_level4_v1/compare_stress.py) |
| 针对性回归 | [test_controlled_public_oracle.py](tests/test_controlled_public_oracle.py)、[test_controlled_scoring.py](tests/test_controlled_scoring.py)、[test_local_balanced.py](tests/test_local_balanced.py)、[test_constrained_eval.py](tests/test_constrained_eval.py)、[test_stress_level4.py](tests/test_stress_level4.py) |

完整状态见 [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md)，协议选择见
[DECISIONS.md](DECISIONS.md)，尚未消除的限制见 [BLOCKERS.md](BLOCKERS.md)。
这些文件保留了很多按时间追加的历史段落，应按最新阶段和记录日期解读。

## 11. 不调用模型的复现方式

最小审查先读取保存的报告和原始 capture，再使用冻结源码核对一个或多个完整 run。
不要运行 `launch_p5.py`、`acp_worker.py` 或历史生产 `collect`；这些执行已消耗。
复核既有分数无需密钥、GPU 或权重。

在完整仓库的项目目录内，建立独立 CPU 环境；若依赖已安装，可省略安装步骤：

```bash
cd disastertrace-starter
python3.10 -m venv .venv-review-p5
.venv-review-p5/bin/python -m pip install \
  -i https://pypi.tuna.tsinghua.edu.cn/simple \
  -r artifacts/p5_stress_level4_v1/requirements-review.txt

PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=artifacts/p5_stress_level4_v1/units/revision_chain/execution_live/implementation_source/src \
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
.venv-review-p5/bin/python -m disastertrace.stress_eval.cli report \
  --execution artifacts/p5_stress_level4_v1/units/revision_chain/execution_live \
  --run work/p5-qwen3-revision-chain-v1 \
  --output artifacts/p5_stress_level4_v1/units/revision_chain/model_report \
  --require-model --verify
```

其他因素对应 `irrelevant_scope` / `p5-qwen3-irrelevant-scope-v1` 和
`late_stale_replay` / `p5-qwen3-late-stale-replay-v1`。`--verify` 比较保存报告，
`--require-model` 拒绝把程序诊断当成模型结果。
依赖安装需要网络，之后的分数重建不调用网络模型。请不要把这些示例命令当成
已在审阅者新环境中执行成功的保证。

完整异地复验见 [REPRODUCE_ACP.md](artifacts/p5_stress_level4_v1/REPRODUCE_ACP.md)。
`verify_review.py` 重建四套报告、analysis 和 comparison，并记录阻止原路径/
权重/网络的检查。使用新解压目录，不覆盖已写的 `verification_result.json`。
旧 claim 中的绝对路径是历史 provenance；使用脚本明确传入的复制路径进行审计，
不能直接改旧 claim。XGrammar 实际 token 重放是另一项验证，需要固定 Torch/
XGrammar 依赖；它不属于最小 CPU 分数重建环境。

轻量附件缺少全量原始 captures、tokenizer 和历史运行，不应尝试用它宣称完整重算。
若附件不被审阅环境解析，可先解压并提供本文、`src/` 和关键 JSON/Markdown 文件。

## 12. 与已有 benchmark 和四份后续方案的关系

上游核查与来源证据保存在 [SOURCE_REVIEW.md](../SOURCE_REVIEW.md)、
[REFERENCE_BUNDLE.md](../REFERENCE_BUNDLE.md)和
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。这些是已保存的版本化核查记录，
不是本轮对上游最新提交重新做的全量文献搜索。

| 参考方向 | 当前借鉴价值 | 需要审查的区别 |
| --- | --- | --- |
| ExtremeWeatherBench | 天气事件组织与 forecast/target 评测边界 | 当前测 LLM 证据更新，尚无 forecast 误差指标，不能称为其完整复现 |
| CyPortQA / EarthVerse | 领域证据、输入组织、追踪与验证形式 | 当前不是全量多模态港口 QA 或开放 agent 任务集 |
| STATE-Bench / STALE | 状态更新、转移规则、过时信息与显式记忆基线思路 | 借鉴状态测量不等于已证明天气领域创新或复现 StateMem 类方法 |
| Inspect AI / lmms-eval | adapter、评测组织与后续导出接口参考 | 当前有自有冻结采集/审计链，尚未把整个上游框架作为已运行评测器 |

四份后续方案在 [plans/plan_v2/](../plans/plan_v2/) 中保留原文，整合入口为
[INTEGRATED_NEXT_PHASE_PLAN_V1.md](../plans/INTEGRATED_NEXT_PHASE_PLAN_V1.md)。
它们提出的输出校准、自动状态任务、可靠采集、难度扩展和后续泛化已经分别推进，
但“在计划中出现”不等于“已在 P5 实现”。请逐项核对当前代码与实测。

最需要外部判断的是：目前的领域化构造是否足以形成有价值的天气 benchmark，
还是应首先定位成更通用的动态证据任务，并以真实天气修订作为独立验证轨。
增加风暴名字和合成样本数无法单独解决这个问题。

## 13. 希望审阅者优先回答的具体问题

| 优先级 | 检查问题 | 希望获得的证据或建议 |
| --- | --- | --- |
| 最高 | Gold、未来证据、source group/episode 元数据能否通过任意 prompt、工具或 carrier 路径泄漏？ | 指明实际调用链与可复现的越界输入，区分“评估进程持有 Gold”与“模型实际收到 Gold” |
| 最高 | Gold compiler 与 public oracle 是否共享会隐藏错误的逻辑？版本 DAG、迟到父版本、同值修订、半开时间窗口是否有漏测？ | 给一个可执行最小反例和独立期望结果 |
| 最高 | fixed denominator、missing/invalid、引用位置、known/unknown 和动作重叠归因是否与宣称一致？ | 手算一个边界案例并对照 scorer；不要只看摘要百分比 |
| 高 | grammar 有没有把语义正确性编码进搜索空间？free/constrained 轨比较是否完整披露额外输出约束？ | 检查真实 schema、backend 调用和 token-mask 重放，列出可达但语义错误的答案 |
| 高 | 轨迹隔离、意图落盘、崩溃前缀、防重复启动、回答接受和传播是否正确？ | 根据 capture/journal/claim 重建请求；检验 wrong-but-valid 与 invalid 两条路径 |
| 高 | P5 等 Gold、来源映射、种子和双向配对统计是否足以支撑当前表述？ | 检查六个零增量控制及有效强度；明确不能消除的混杂 |
| 高 | 怎样避免把同风暴分支、方法、checkpoint 和 repeat 当独立样本？ | 给出来源级统计与重复波动的报告方案，指出 3 个来源的剩余限制 |
| 高 | 当前任务的科学增量是什么，哪些模板/答案先验可能造成捷径？ | 检查 c0、数值/阈值、字段类型、公开说明与程序基线，而非仅建议扩大数量 |
| 中 | 先做 6,480 次重复对照是否比先扩充来源更值得？ | 给最小能改变结论的实验，并说明新增计算解决与解决不了的问题 |
| 中 | 可移植复现、上游许可、模型身份、数据清单与 CI 尚有什么缺口？ | 区分已复验步骤、第三方可复验性和尚未执行的 hosted CI |

建议输出顺序为：重大结论风险与已证实缺陷、待验证假设、已经披露的局限、可执行
下一阶段计划。若没有找到某类缺陷，请明确说明检查范围与仍缺失的证据。

## 14. 当前建议的后续顺序，供复查修订

1. **先冻结审查结果与问题清单。** 修分数的缺陷必须先给反例；新修复建独立版本，
   保留本轮所有原始结果。验收是问题能复现、修复被针对性测试覆盖、旧记录仍可重算。
2. **准备同硬件重复设计。** 候选矩阵为基础 + 三因素，4 条件 × 540 回答 × 3 repeats
   = 6,480 回答，尚未启动。需要新 repeat/trajectory/seed 身份、隔离调度和预先
   固定的完整预算；目前执行器只接受一次 repeat，不能复制旧 slot/claim 来实现。
   在推理前完成跨 repeat 载体隔离、完整诊断、停止前缀和 CPU 重算验收。
3. **扩充独立开发事件。** 在生成前声明事件选择原则，保持七个既有 heldout 不参与
   调参；检查真实 event identity、来源证据、parser、Gold/public oracle 和负例。
   更多 repeats 只估计采样波动，不能代替更多独立天气来源。
4. **在相同任务版本加入第二模型。** 固定权重/服务版本、输出能力与预算，对严格
   grammar、普通 JSON mode 和自由输出分轨，历史 DeepSeek 的 270 个回答不填入
   新 540/1,620 矩阵。先验证 adapter，再执行新的有界模型实验。
5. **最后冻结 heldout 与更广的天气任务。** 冻结模板、分布、种子、模型、评分器和
   失败处理后再看保留集。新事件、新数值、新操作泛化分开报告。其他灾种与真实
   公告修订优先选择具有可执行标签的来源；开放建议与主观灾害决策另设研究目标。

更大 context、level 16、有限观察窗口、复杂记忆系统和训练不是本轮已完成内容。
详细候选计划见 [NEXT_PHASE_PLAN_ACP.md](artifacts/p5_stress_level4_v1/NEXT_PHASE_PLAN_ACP.md)。
上述次序允许审阅者根据证据调整，核心要求是每一步明确它改善的是实现正确性、
任务有效性、重复稳定性还是跨事件泛化，不能用一种验证替代另一种。
