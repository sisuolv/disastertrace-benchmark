# DisasterTrace 下一阶段实施说明

日期：2026-09-07。开发分支：`next-phase-v1`。起点：`a23f73adadcbec077b9fcf2aecf8f45dfa4fe061`。

后续更新：本文件记录的 T0–T5 离线阶段之后，[T6 真实校准](README_T6_CALIBRATION_V1.md)已完成 270 个响应并通过独立审计，选择共同输出上限 8192。下文保留本离线阶段的范围和状态；最新实验结果与后续任务以 T6 说明为准。

本阶段执行了[四份方案的整合计划](../plans/INTEGRATED_NEXT_PHASE_PLAN_V1.md)中的 T0–T3 和 T4–T5：建立可恢复、可审计的校准执行器，以及有独立自动参考答案的 P2 动态证据任务。两者均完成离线实现；本阶段新增真实模型调用为 **0**，尚未产生新的模型成绩。

原整合计划与四份输入方案保留原有规划文字。本文件和 [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md)记录实施后的状态。旧 GitHub 审查快照、原项目目录和 P1 真实响应保持为历史基线。

## 1. 现在要评测什么

研究问题是：LLM 连续收到气象证据时，能否按照公开规则更新事实、保留未变字段、选择正确版本和来源，并在资料不足时回答 unknown。

当前有两条互补的轨道：

| 轨道 | 数据和任务 | 解决的问题 |
| --- | --- | --- |
| NHC 校准 | 既有官方公告；原来的五字段输出和评分 | P1 方法差异有多少随输出说明、输出上限变化；为下一轮选择共同输出设置 |
| P2 受控任务 | 三个开发风暴的初值，加明确标记的生成记录；四字段完整状态 | 对部分更新、同窗口纠正、旧版重放、范围隔离和缺失恢复分别测量 |

两条轨道分别报告，不合成一个总分。任务并不直接检验天气预测能力、实际应急行动最优性或模型内部记忆机制。三个开发风暴也不能代表一般极端天气总体。

## 2. 校准执行器完成了什么

三条件保持为 `legacy_4096`、`explicit_4096`、`explicit_8192`。每条件有三种方法：snapshot、structured_state、answer_history。每种方法使用 Ida、Florence、Dorian 的两个分支和五个检查点，共 **270 个计划响应机会、54 条独立载体轨迹**。

相对于旧离线准备包，新增：

1. **精确请求发送与解析前捕获。** 保存并发送同一份 prepared bytes；HTTP 错误、非 UTF-8、无效 envelope、超大或中断响应均尽可能保留有界记录。凭据反射检查发生在可持久化返回之前。
2. **共同超时。** 所有条件统一 180 秒 socket timeout 和独立的 180 秒网络总 deadline。真实传输在独立进程运行，到期终止并回收；本地慢服务测试覆盖此行为。磁盘持久化时间单独处理。
3. **一次实验共用账本。** 使用 Decimal 预留、结算、未知费用状态及尝试上限；最多 270 次、USD 3 是待启动范围的条件预算，不能保证完成全部请求。
4. **持久化和恢复。** 每槽位依次记录 reserved → send_intent → capture → settled → decision。已捕获而未完成解析的响应可离线恢复；只有发送意图、没有可靠响应时保留 unknown 并停止，日志损坏同样停止。
5. **独立审计。** 从协议、调度、实际请求、载体历史和响应重新计算费用及接受状态。审计器不调用运行时账本来证明该账本本身正确。
6. **报告和共同 cap 选择。** 保留全部 270 个分母；分别列已尝试、已收到、未发送、schema、length、事实及来源正确率、风暴内配对差异、usage、时延和费用。只有完整的真实采集与审计通过，才允许依据既有门槛推荐共同 cap。

程序演练虽然能模拟筛选规则通过，但 `selected_output_tokens` 仍为 null，`live_recommendation=false`。它不能证明 4096 或 8192 对真实模型已经足够。

状态传递只根据 schema 决定：结构有效但事实错误的模型回答继续传递；结构无效则保留之前有效状态。不得用 Gold 修复答案，也不得把演练程序的输出放入模型历史。

费用报告区分保守峰值/缓存未命中账、可核验缓存计数和本地 UTC 时段支持的费用估计、以及未知预留。价格来自保存的 2026-09-06 快照；真实启动前仍须确认价格和限制适用。跨价格时段、缓存统计缺失或不一致时不强行估算。所有估计均不是账单；程序演练中的金额属于模拟。

执行包绑定完整递归源码、环境、协议、父准备包及固定 registry 绝对路径。重新指定输出目录或复制执行包不能重置同一执行身份的启动记录。AFS 上已测试竞争进程、异常退出和 fsync 失败；本地锁不构成分布式或服务端 exactly-once 保证。

实现入口：[执行协议](docs/CALIBRATION_EXECUTION_V1_1.md)、[采集器](src/disastertrace/automated/live_calibration.py)、[独立审计](src/disastertrace/automated/live_calibration_audit.py)、[报告](src/disastertrace/automated/calibration_report.py)。

## 3. P2 已经具备什么

P2 协议是 `disastertrace_controlled_v1`，代码独立位于 `src/disastertrace/controlled/`，不改旧 NHC parser 或 scorer。输出为风速、气压、纬度、经度四字段的完整状态，含 known/unknown 和逐字段引用；action 仅保留为公开阈值规则下的辅助指标。

| 家族 | 操作 | 必须检查 |
| --- | --- | --- |
| U1 部分更新与保留 | 只改风速，其他字段不重述，随后重放旧记录 | 新风速生效；压力等字段保留各自有效值及来源 |
| U2 同窗口纠正 | 在目标窗口修订同一个事实；匹配支使用另一个窗口的独立记录 | 采用同键正确版本，旧版不能覆盖，不被其他实体或窗口干扰 |
| U3 可恢复缺失 | 首次曝光前延后一个字段的全部支持，之后恢复交付 | 无证据时 unknown；支持到达后 known；后续省略不应清空已知状态 |

版本规则按实体、变量、有效窗口和 measurement kind 建立 FactKey；单位固定。第一版只接受可见父版本构成的单根、无环、无分叉链。非法单位、冲突和无效引用属于任务准入错误，不伪装成需要模型回答 unknown 的合法题目。

正式开发清单固定为 **18 条轨迹、每方法 90 个检查点、三方法 270 个拟执行模型槽位**。另有 **12 条微轨迹、60 个检查点**作为软件验收 fixtures，不计为额外真实风暴样本。

初值确实继承三个开发风暴 advisory009 中的值，并保存原文 hash、locator 和来源 URL；后续数值、窗口、实体、版本关系和卡片文本都明确标注为研究生成内容，不声称是官方历史纠错记录。

自动 Gold 使用两条独立语义路径：私有 Compiler A 从投递记录归约；Public oracle B 只读模型可见的公共卡片与查询规则，独立解析和选择版本。两者不共享权威版本 reducer，也不相互读取最终答案。

离线准备实际执行 **450 次 compiler/oracle 对照**及 **2,700 个程序诊断响应**。程序控制检验遗漏清空、全局最新文档、旧版到达覆盖、一直复制旧状态、一直 known/unknown、数值对但来源错等错误；按键取 latest-issued 在当前合法单链中能正确时，保留其通过结果。另有 ID 改名、时间平移、独立键交换、旧记录重复及 locator 移动等变形测试。

这满足不新增逐题人工标注或 LLM judge 的设计要求，但自动一致性不能替代对所有天气场景的语义覆盖证明。详见 [P2 使用入口](README_CONTROLLED_V1.md)、[语义规格](docs/P2_CONTROLLED_SEMANTICS_V1.md)与[自动 Gold 验证](docs/P2_AUTOMATIC_GOLD_VALIDATION.md)。

**P2 目前是 `P2_OFFLINE_READY`，`live_ready=false`。** 新适配器只构造未发送请求；正式 P2 模型采集、响应来源审计和真实结果评分接入仍待后续实现。当前 scorer 明确限定程序诊断来源，不能把外部答案改个标签就写入 LLM 成绩表。

## 4. 如何复现

在仓库的 `disastertrace-starter/` 目录使用 Python 3.10。依赖安装可访问清华镜像，验收阶段阻断外部网络，允许测试用 loopback 服务。

```bash
python3 -m venv .venv
.venv/bin/python -m pip install \
  -i https://pypi.tuna.tsinghua.edu.cn/simple \
  -c ../handoff_validation/requirements-installed.txt -e '.[dev]'

.venv/bin/python scripts/reproduce_next_phase.py \
  --output work/next-phase-reproduction-001
```

选择不存在的输出路径。脚本依次执行当前 `tests/` 全套、新 NHC build、旧校准 prepare/verify、新执行 prepare/verify、270 槽程序演练、独立审计、报告、P2 prepare/verify。它清除子进程环境中常见的凭据变量，并记录各步骤命令、退出码、用时和日志 hash；不会运行真实采集命令。

每次输出包含：

| 路径 | 用途 |
| --- | --- |
| `commands.json`、`*.log` | 实际执行记录，区分测试运行与显式 skip |
| `build/`、`calibration/` | 新源码下的源数据构建及继承校准准备 |
| `execution/` | 冻结执行身份、协议及 `authorized=false` 的模板 |
| `rehearsal/` | 270 槽诊断 journal，模型调用为 0 |
| `execution_audit.json`、`report/` | 审计摘要、实际输入和独立评分投影、完整分母报告 |
| `p2/` | 来源绑定、生成任务、Gold、初始公共请求、程序控制、源码快照 |

验收日志和可移交归档见 [artifacts/next_phase_v1/README.md](artifacts/next_phase_v1/README.md)。完整运行目录位于 `work/next-phase-*`，不自动纳入 Git；归档保留冻结内容及校验清单。不要编辑 manifest 来适配不同路径或源码，换环境应重新 prepare。

仓库还增加了 [GitHub Actions 工作流](../.github/workflows/offline.yml)，运行同一离线入口。当前记录的是本机验收，尚无这份工作流在 GitHub 运行成功的记录。

## 5. 当前完成边界和下一步

| 阶段 | 状态 | 下一依赖 |
| --- | --- | --- |
| T0–T3 校准执行工程 | 离线实现与完整程序演练完成 | 真实启动前固定价格、模型限制和实际预算范围 |
| T4–T5 P2 语义与自动任务 | 离线实现、自动 Gold 和程序控制完成 | 校准结果及 P2 专用真实采集/审计接入 |
| T6 新鲜输出校准 | 未运行 | 一次独立的最多 270 次开发校准；无额外默认 canary 或补跑 |
| T7 P2 模型验证 | 未运行 | 独立的 P2 270 次开发矩阵，以及另行确定的第二模型 |
| T8 留出评估 | 未运行 | 协议、评分、全部模型配置、重复数和顺序统一冻结 |

建议下一步先进入 T6：沿用三条件和三方法，检查当时 `deepseek-v4-flash` 服务设置及价格，在执行包身份下记录实际范围后运行一个新鲜矩阵。旧 P1 的一次性续跑范围已用完；不得重新启动其后台进程。

T6 完整矩阵必须经过独立审计。共同 cap 的门槛是每个 explicit 条件下各方法 schema ≥29/30、length ≤1/30，取合格的较小 cap；矩阵不完整或两档均不合格时如实输出 `no_selection`，不按方法各挑最优参数。

之后补齐 P2 实际采集与审计，并以冻结的四字段协议做单独开发实验。NHC 校准的 cap 是起点，不能自动视为 P2 或第二模型已经通过可靠性检查。七个留出风暴仍未进行模型推理。

目前最新的真实模型证据仍是 P1 的 90 个响应 / 91 次尝试；原 attempt 79 的收费未知状态未改变。新增自动验收和程序得分不能解释为模型能力提高。
