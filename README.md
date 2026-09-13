# DisasterTrace：LLM 极端天气证据推理评测审查包

## 最新进展：v7 类型化自适应闭环与真实 TAF 诊断（2026-09-13）

请先阅读 [最新结果](plans/v7_adaptive_execution_20260913/FINAL_REPORT_CN.md)、
[下一步执行顺序](plans/v7_adaptive_execution_20260913/NEXT_EXECUTION_CN.md) 和
[给 ChatGPT Pro 的复查任务](publication/v7_adaptive_review_20260913/REVIEW_FOR_CHATGPT_PRO_CN.md)。
整体研究方向仍以 [v7 总体计划](plans/v7_next_20260913_2/OVERALL_PLAN_CN.md) 为准。

本次同步上一轮 108 次模型调用及最新一轮 252 次真实 Qwen3-8B 调用。
最新一轮在 3 张 H100 上完成，无缺失、解析失败或重试；97 次数据请求全部成功，
解析 288 条 METAR 与 91 份完整 TAF，形成 432 个机会。313 项相关测试通过。

类型化证据已接入原有会话控制器，支持实际获取账本、截止评分和静止点跨进程恢复。
输入整理使 E-only 事实判断由 24/36 提高至 33/36；但全部 144 个含 F 的回答仍保持
共同基线，TAF 覆盖判断仅 6/18。新日期的程序全量取证还会恶化 Brier 损失。
这些是开发诊断，不构成主动策略增益、独立确认或全部 16 类灾害完成的证据。

复查材料：

- [轻量代码与报告阅读包](publication/v7_adaptive_review_20260913/DisasterTrace_V7_Adaptive_Review_20260913.zip)
- [最新完整 CPU 离线复查包](plans/v7_adaptive_execution_20260913/DisasterTrace_v7_typed_adaptive_20260913_review.zip)
- [前一轮结果](plans/v7_followup_execution_20260913/FINAL_REPORT_CN.md)
- [下载、验证与复现说明](publication/v7_adaptive_review_20260913/REPRODUCE_CN.md)

离线包可重算 36 份类型化日志、8 条恢复分支、252 次新回答及 108 次旧回答，
无需模型权重、API 或网络。完整材料另以去重归档保存，原始失败与冻结版本均保留。
下文是各阶段的历史记录；最新状态以本节入口为准。


## 最新进展：2026-09-13 固定证据与数据源验证

本次更新包含新固定证据/连续量接口、250项通过的相关测试、两年度本地基线对照、
LAMP/EUPPBench/SEEPS4ALL/水文历史样例，以及720次真实GPU调用及CPU复现包。
本地化在2024年改善、2026年变差；全读邻站资料没有稳定收益。v7科学准入仍为0/16，
不代表没有数据样例，也不宣称LLM预测优势已经成立。

- [完整执行报告](plans/v7_execution_20260913/FINAL_REPORT_CN.md)
- [整体与后续计划](plans/v7_execution_20260913/NEXT_PLAN_CN.md)
- [交给ChatGPT Pro/导师的复查说明](publication/v7_execution_20260913/REVIEW_FOR_CHATGPT_PRO_CN.md)
- [轻量阅读ZIP](publication/v7_execution_20260913/DisasterTrace_V7_Latest_Review_20260913.zip)
- [720次捕获的CPU复现ZIP](plans/v7_execution_20260913/replay/DisasterTrace_V7_CPU_Replay_20260913.zip)
- [完整材料归档与恢复方法](publication/v7_execution_20260913/REPRODUCE_CN.md)

原实验报告中的“本轮未新增GitHub发布”描述其05:45 UTC完成时的状态；本次单独发布
随后进行，不改写实验冻结。完整资料包含原始失败和负结果，模型权重及账号凭据不上传。


## 最新：v7 复查落实与真实模型验证

本轮在稳定 v7 上实现 monitoring_v1，补齐可见支持、联合可达性、目标时间、两协议、权限预算和缺失评分。
实际已核验 33,944 次模型调用、50 个完成的 H100 作业；当前测试记录 109 项通过。
当前是工程/真实区域开发结果，主动预测正收益和完整 16 类科学准入尚未证明。

请先阅读 [实际结果与交接](plans/v7_review_execution_20260912/FINAL_REPORT_CN.md)、
[保持 v7 的整体路线](plans/v7_review_execution_20260912/OVERALL_EXECUTION_ROADMAP_CN.md)、
[ChatGPT Pro 复查任务书](publication/v7_review_execution_20260912/REVIEW_FOR_CHATGPT_PRO_CN.md) 和
[离线复现说明](publication/v7_review_execution_20260912/REPRODUCE_CN.md)。

[精简阅读 ZIP](publication/v7_review_execution_20260912/DisasterTrace_v7_Implementation_Review_20260913.zip)
与 [完整证据索引](publication/v7_review_execution_20260912/EVIDENCE_INDEX.json) 分别提供。
负结果、解析失败和未结算机会保留。以下为旧阶段记录，应按各自版本和日期解释。


## 最新：v7 整体研究方案与数据验证（2026-09-12）

请先阅读 [v7 整体研究主计划](plans/v7_0912_overall_research/OVERALL_PLAN_CN.md)、
[16 类灾害数据合同](plans/v7_0912_overall_research/HAZARD_DATA_PLAN_CN.md) 和
[近邻工作与 novelty 对照](plans/v7_0912_overall_research/RELATED_WORK_MATRIX_CN.md)。
整体路线包含 10 组实验、8 个阶段；既有下一步计划作为实施附录保留。

最新 97 个来源/产品条目中 86 有解析内容、7 为目录、2 待授权、2 缺原生目标内容。
本轮加入 [EM-DAT/CMA/xBD 的实际审计与代码](plans/user_authorized_sources_20260912/README_CN.md)。
下载可读不等于任务准入；CMA 字段语义与 xBD 配准仍有门槛。
新的 monitoring_v1 尚未实现，本次没有新增模型或 GPU 评测，也未证明主动取证正收益。

用于进一步复查的 [ChatGPT Pro 任务书](publication/v7_overall_review_20260912/REVIEW_FOR_CHATGPT_PRO_CN.md)
与 [阅读附件](publication/v7_overall_review_20260912/chatgpt_pro_v7_overall_review_20260912.zip)
一并提供。原始大数据、模型权重及环境保留本地。

以下为既有阶段记录，其数字按对应版本解释。

## 最新：全部候选数据补缺与使用清单（2026-09-12）

当前 97 个来源/产品入口中，84 项有已解析样例、6 项可作事件目录，7 项仍有获取或授权缺口。
本轮实际补齐 TCIR、CAMELSH、CEMS、FloodNet、CrisisMMD、UrbanSARFloods、SenForFlood、GWIS、EFFIS。
完整 [数据报告](plans/all_dataset_utilization_20260912/README_CN.md)、[97 项清单](plans/all_dataset_utilization_20260912/usage_02/USAGE_REGISTRY_CN.md)
和 [16 灾种组合](plans/all_dataset_utilization_20260912/usage_02/HAZARD_CHAINS_CN.md) 已更新。

请将 [ChatGPT Pro 复查任务](publication/dataset_review_20260912/REVIEW_FOR_CHATGPT_PRO_CN.md)
或 [精选阅读 ZIP](publication/dataset_review_20260912/chatgpt_pro_dataset_review_20260912.zip) 交给审阅者。
93 次实际数据请求、约 975 MB 正文和 1,081 个文件的本机独立核验已有记录。
源码、回执和审计结果随仓库提供；新原始大数组与环境保留本地。
样本可读不代表 16 类预警链全部建成；本轮没有新模型调用，既有主动取证未显示收益的结果保留。

## 最新：ActiveWarning 最小闭环与复查材料（2026-09-12）

**真实数据、LLM 推理和自动评分的最小闭环已跑通；主动获取收益尚未得到支持。**
请先读 [最新进展](LATEST_PROGRESS_20260912_CN.md) 和 [ChatGPT Pro 复查说明](publication/active_warning_review_20260912/REVIEW_FOR_CHATGPT_PRO_CN.md)。
本次包含两轮 Qwen3-8B 的 1,120 条真实回复及完整数值复算材料，并提供 [精选阅读 ZIP](publication/active_warning_review_20260912/chatgpt_pro_active_warning_review_20260912.zip)。
真实未来水文试点作为并行补充，发布快照中的 18 个结果尚待观测；历史多事件回放可先行验证研究问题。

## 最新：16 类灾害整体方案与真实样例验证（2026-09-11）

请先读 [完善后的整体方案](plans/v6_blueprint_sample_validation_20260911/OVERALL_PLAN_REFINED_CN.md)、
[逐灾种数据合同](plans/v6_blueprint_sample_validation_20260911/HAZARD_SOURCE_MATRIX.md) 和
[逐来源样例清单](plans/v6_blueprint_sample_validation_20260911/SOURCE_SAMPLE_INVENTORY.md)。
本次整合两份整体蓝图，并实际执行 125 次有界请求；最终科学审计含 31 条科学内容解析
和 2 条渲染地图记录。97 项登记包含不同产品、继承和条件候选，不是独立数据集数量。
GHCNh、未来业务预报、冻雨/沙尘站报、雷达卫星及海岸/干旱产品均有实际样例证据；
权限、单位、时空支持、正例和配对缺口分别披露。新正式评测任务和模型调用为 0。

研究主线进一步确定为：在相同专业预报、资料预算和准备截止下，测量主动获取证据
对固定未来风险预测与决定的增量，并区分来源、表示、版本和状态造成的失效。
历史产品事实评测继续保留为 E 面板；F/D 的完整未来结果闭环仍待构建。

[本次发布与复查入口](publication/blueprint_review_20260911/README.md) 包含 ChatGPT Pro
复查问题、阅读 ZIP 和副本校验命令。原始数组和解析环境保留在数据工作区；GitHub
副本提供代码、方案、回执与审计记录，不能据此声称已独立重跑全部科学解码。

以下保留此前各阶段的进展与结果，历史“当前/最新”字样应按对应阶段理解。

## 最新复查：V6 数据选择与多灾种可行性核验（2026-09-11）

请从 **[给 ChatGPT Pro 的 V6 复查任务](publication/v6_review_20260911/REVIEW_FOR_CHATGPT_PRO_CN.md)** 开始，
再阅读 [数据选择与后续路线](plans/v6_0911_dataset_selection/DATA_READINESS_REVIEW_CN.md)、
[逐来源状态](plans/v6_0911_dataset_selection/SOURCE_FEASIBILITY.md) 和
[16 类灾种覆盖与缺口](plans/v6_0911_dataset_selection/HAZARD_COVERAGE.md)。

本轮登记 54 个原候选和 20 个互补来源，完成重点来源的真实取样、解码与数据审计。
ExEBench 寒潮包、EWB 小时观测、GLM、GEOID/CEMS、DroughtED 等的实际结果与限制已分别记录。
74 是来源登记项数；新增正式评测题、GPU 作业及模型调用均为 0。

可用 [单文件 Markdown 复查材料](publication/v6_review_20260911/CHATGPT_PRO_REVIEW_ALL_IN_ONE.md)
或 [代码与报告阅读包](publication/v6_review_20260911/disastertrace_v6_chatgpt_review.zip)。
本次发布包含代码、报告和审计清单；大体积原始数据保存在原工作区，完整解码重放的依赖范围见
[发布说明](publication/v6_review_20260911/README.md)。
此前 V5/Active Forecast 及 P5–P14 的实现与结果继续保留；下文“当前”字样属于对应历史阶段。

## 当前新增：P6 首轮离线里程碑

四份 plan_v3 已整合并完成第一阶段实现。入口为
[P6 离线结果](disastertrace-starter/README_P6_OFFLINE_V1.md) 与
[详细交接](disastertrace-starter/artifacts/p6_offline_v1/HANDOFF_POST_P5.md)。
P5 的230个纯引用错误已逐项细分，其中109个为同值旧版本引用；旧分数保持不变。
新候选为两条件、两重复、2160个机会。correct与invalid-control各2160条程序诊断、
实际tokenizer上下文检查、独立CPU迁移及新增69项测试完成，新增模型/GPU/API调用为0。
这批是离线准备，尚未发布P6到GitHub；下一步见
[后续执行计划](disastertrace-starter/artifacts/p6_offline_v1/NEXT_STEP_EXECUTION_PLAN.md)。

## 当前复查入口：P5 三因素 GPU 评测已完成

请先读新的中文 **[ChatGPT Pro 完整复查文档](disastertrace-starter/REVIEW_FOR_CHATGPT_PRO_P5.md)**。
它包含可直接复制的审阅任务、研究目标、数据与代码地图、真实结果、验证证据、
已知局限和下一阶段优先级，无需此前聊天记录。

2026-09-08：[P5 ACP H100 实测](disastertrace-starter/README_P5_ACP_V1.md)完成
1,620 个真实 Qwen3-8B 回答，三个独立单卡作业全部成功。所有回答通过原始输出
契约，完整正确为 1,360/1,620（83.95%）。90 处值/状态错误、230 处引用错误
及 29 处重叠的动作错误全部保留，无重试、缺失或长度终止。

| 条件 | snapshot | structured_state | answer_history |
| --- | ---: | ---: | ---: |
| P4 基础任务 | 167/180 | 178/180 | 145/180 |
| P5 修订链 level 4 | 150/180 | 164/180 | 135/180 |
| P5 无关作用域 level 4 | 155/180 | 154/180 | 135/180 |
| P5 旧记录重放 level 4 | 163/180 | 172/180 | 132/180 |

三来源、一次采样、新种子以及 P4 MIG/P5 完整 H100 的差异限制结论；零增量
控制也出现波动，表格为描述性开发结果。108 个因素变体不是 108 个独立风暴。
当前测量天气记录证据更新，不能据此宣称天气预报精度或内部记忆的因果优势。

完整发现见 [MODEL_FINDINGS.md](disastertrace-starter/artifacts/p5_stress_level4_v1/MODEL_FINDINGS.md)，
复现入口见 [REPRODUCE_ACP.md](disastertrace-starter/artifacts/p5_stress_level4_v1/REPRODUCE_ACP.md)。
全部 432,742 个最终输出/EOS token 重放、四套报告的独立 CPU 迁移重建与历史保全
均已通过。[完整 P5 复查包](disastertrace-starter/artifacts/p5_stress_level4_v1/p5_stress_level4_acp_v1_review.tar.gz)
约 68.7 MB，7,097 个成员已校验。也可先使用
[轻量复查附件](publication/p5_review_20260908/chatgpt_pro_p5_review.zip)。
私有仓库访问和附件范围见[发布说明](publication/p5_review_20260908/README.md)。

[下一阶段候选计划](disastertrace-starter/artifacts/p5_stress_level4_v1/NEXT_PHASE_PLAN_ACP.md)
优先改善同硬件重复性与独立来源覆盖；6,480 回答的候选重复矩阵尚未启动。
本次上传不增加模型调用。各旧阶段原始文件、失败记录与封存档案继续保留。

本轮使用用户新配置的 SSH 密钥，经 GitHub SSH 443 端口上传。既有 HTTPS OAuth
scope 不含 `workflow`，此前准备的 CI 配置继续随
[说明文档](disastertrace-starter/docs/ci/README.md)作为模板提供；本轮没有启用云端 Actions。

## 历史阶段记录

> 最新真实结果：[P2 输出契约 v2 实测](disastertrace-starter/README_P2_DEEPSEEK_OUTPUT_CONTRACT_V2.md)已完成 270/270 个响应，独立审计与重建通过，九个格式单元全部通过，三种方法在当前开发矩阵上全部正确。费用估计 USD 0.267236704，保守结算 USD 0.64265696，无本轮未知预留。请查看[详细发现](disastertrace-starter/artifacts/p2_deepseek_output_contract_v2/FINDINGS.md)、[后续计划](disastertrace-starter/artifacts/p2_deepseek_output_contract_v2/NEXT_PHASE_PLAN.md)和[ChatGPT Pro 复查入口](disastertrace-starter/artifacts/p2_deepseek_output_contract_v2/REVIEW_GUIDE.md)。当前满分暴露出小矩阵的天花板现象，下一步进入跨模型与平衡设计的离线准备。

> 前一离线阶段：[共同输出契约 v2](disastertrace-starter/README_P2_OUTPUT_CONTRACT_V2.md)完成实现与验收，通过 1,074 项核心回归、9 项补充回归和完整程序诊断。该离线阶段的未批准提案与模板保留原样，实际模型授权和结果位于新的实测包中。

> 历史 v1 结果：P2 首轮 DeepSeek 开发比较已完成 270 个真实响应，独立审计和离线重算通过；共同格式门槛未通过。费用估计约 USD 0.299。请查看 [中文实测说明](disastertrace-starter/README_P2_DEEPSEEK_V1.md)、[主要发现](disastertrace-starter/artifacts/p2_deepseek_development_v1/FINDINGS.md)和[后续计划](disastertrace-starter/artifacts/p2_deepseek_development_v1/NEXT_PHASE_PLAN.md)。首轮实测作为 v2 的历史对照保留。

> 前一离线阶段：P2 已接入可恢复采集、独立审计与直接评分，验收通过 999 项测试及完整 270 槽预演，该离线阶段新增真实模型调用为 0。请查看 [P2 执行说明](disastertrace-starter/README_P2_EXECUTION_V1.md)和[验收记录](disastertrace-starter/artifacts/p2_execution_v1/README.md)。

> T6 真实校准已于 2026-09-07 完成：270 次尝试 / 270 个响应，独立审计通过，按预定门槛选择 8192 tokens。费用估计约 USD 0.629。请查看 [T6 结果与说明](disastertrace-starter/README_T6_CALIBRATION_V1.md)。下述“新增模型调用为 0”描述的是此前的 T0–T5 离线阶段。

> `next-phase-v1` 开发分支已实现四份方案整合后的 T0–T5 离线工作：校准执行器、独立审计、预算与恢复，以及 P2 动态证据任务。请先读[下一阶段实施说明](disastertrace-starter/README_NEXT_PHASE_V1.md)和[验收记录](disastertrace-starter/artifacts/next_phase_v1/README.md)。新增模型调用为 0；P2 尚未接入真实模型采集。下文保留 `a23f73a` 审查快照的历史说明，684 项测试等数字属于该基线。

以下段落保留早期独立代码与研究设计审查快照的说明。当时已完成一轮 DeepSeek 开发集比较，以及下一轮输出规范 / token 预算校准的离线准备；最新状态以本文开头的 P5 实测入口为准。

历史 [REVIEW_FOR_CHATGPT_PRO.md](disastertrace-starter/REVIEW_FOR_CHATGPT_PRO.md) 说明早期目标、数据、方法、结果与校准准备。当前复查请使用本文开头的 P5 版本。

## 历史审查快照事实

| 项目 | 状态 |
| --- | --- |
| 真实动态任务资料 | 10 个准入风暴，3 个开发、7 个留出；尚无留出集模型结果 |
| P1 模型实验 | DeepSeek，三种方法，90 个响应 / 91 次请求尝试；包含一次已记录的中断续跑 |
| P1 主要结果 | 已知字段及证据正确：snapshot 39/96，structured_state 96/96，answer_history 76/96 |
| 下一轮校准 | 原规范 / 4096、明确规范 / 4096、明确规范 / 8192，共 270 次拟执行请求，尚未运行 |
| 离线程序验证 | 上传副本在新环境下再次通过 684 项测试（57.41 秒）；历史校准包另有 6,979 项独立审计检查。不是新增模型成绩 |
| 人工与模型判分 | 不新增逐题人工标注或主观复核，不使用 LLM judge 作为主评分器 |

三种方法都看到当前已交付的累计证据。当前结果不证明因果记忆优势，也不能代表一般极端天气预测或真实应急决策能力。P1 中有 20 个输出上限失败、2 个结构错误，相关回答均保留在分母里。

## 阅读入口

- [详细审查说明与八个重点问题](disastertrace-starter/REVIEW_FOR_CHATGPT_PRO.md)
- [当前实现状态](disastertrace-starter/IMPLEMENTATION_STATUS.md)
- [P1 真实实验报告](disastertrace-starter/work/p1-deepseek-background-continuation-v1/report/REPORT.md)
- [输出规范与校准协议](disastertrace-starter/docs/CALIBRATION_PROTOCOL_V1.md)
- [核心实现](disastertrace-starter/src/disastertrace/automated/) 与 [测试](disastertrace-starter/tests/)
- [资料快照说明](REFERENCE_BUNDLE.md) 与 [第三方来源和许可](disastertrace-starter/THIRD_PARTY_NOTICES.md)
- [导出文件清单](EXPORT_MANIFEST.json) 与 [审查包说明](REVIEW_PACKAGE.md)
- [本次新环境验证记录](handoff_validation/README.md) 与 [独立交付检查](handoff_audit/review_result.json)

## 目录结构

```text
disastertrace-starter/       原项目代码、测试、文档、配置与已保存实验资料
references/                 构建和测试使用的精简原始资料快照
handoff_audit/               本次交付的检查与实际执行记录
handoff_validation/          新环境依赖、完整测试和离线重建执行记录
INTEGRATED_BENCHMARK_PLAN.md  整体研究计划；较早进度文字以当前状态文档为准
```

`work/` 和 `artifacts/` 中的旧结果是历史证据，包括失败记录。部分旧 manifest 含原机器的绝对路径；不应改写它们以伪装成可移植的新实验。换环境后请使用新的输出路径构建和验证。

## 安装与离线验证

建议使用 Python 3.10 或更新版本。以下命令从仓库根目录开始，项目的 `../references/` 布局已保留。

```bash
cd disastertrace-starter
python3 -m venv .venv
.venv/bin/python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -e '.[dev]'
.venv/bin/python -m pytest tests -o addopts= -q
```

镜像暂不可用时可改用官方 PyPI。只运行 `tests/`：历史 `artifacts/` 中还保存了其他版本的独立测试，不应把这些归档测试自动混成同一次测试执行。`requirements-verified.txt` 记录了开发环境的一份依赖快照；它不构成所有 Python 版本的安装兼容保证。

Ubuntu / Debian 如果提示缺少 `ensurepip`，需要先安装与 Python 版本对应的 `python3-venv` 系统包。本次已在全新 Python 3.10 环境中完成依赖安装和全部测试，具体版本保存在 [依赖快照](handoff_validation/requirements-installed.txt)。

用本包资料重新构建并进行零模型调用的校准准备：

```bash
.venv/bin/disastertrace-auto build \
  --references ../references \
  --nhc-snapshot ../references/nhc_cohort_v1 \
  --output work/review-build-001

.venv/bin/python -m disastertrace.automated.calibration prepare \
  --build work/review-build-001 \
  --provider-config artifacts/p1_deepseek_development/provider.json \
  --output work/review-calibration-001

.venv/bin/python -m disastertrace.automated.calibration verify \
  --output work/review-calibration-001
```

输出目录必须不存在。54 个初始请求不会发送，1,080 个诊断回答来自程序；这些命令不读取模型凭据。不要以为此准备包已经实现新的真实采集器，或已授权 270 次付费请求。历史配置也不是启动旧批次的授权。

本次已实际执行这三个命令，全部成功，验证了 128 个校准文件、54 个未发送请求和 1,080 个程序诊断回答。新输出目录不纳入版本控制，执行日志单独保存在 `handoff_validation/`；新构建的 ID 与历史归档不同，符合来源路径变化的预期。

## 给审阅者的任务

请以代码和记录为依据，优先列出会改变研究结论的问题，并给出文件位置、影响、修正方式和验收标准。重点关注时间语义、可见证据与 Gold 隔离、格式 / 预算混杂、固定分母、证据支持规则、状态传递、测试代表性和下一阶段任务设计。

代码审查与研究设计建议不属于对 benchmark 样本新增主观判分。请不要启动任何模型调用，也不要把离线诊断结果或计划功能描述为真实模型实验结果。

本次私有 GitHub 审查快照由项目所有者明确授权。子目录 `AGENTS.md` 中保留的是历史阶段约束；本次导出授权不改变其中的模型实验范围，也不代表授权公开发布资料。
