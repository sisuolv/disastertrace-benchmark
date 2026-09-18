# 依据与来源映射

## 1. 证据等级

- **Gxx：本轮通过 GitHub 连接器读取的版本固定源码或发布报告。** 读取报告证明仓库记录了该结果，不等于本轮独立重跑完整实验。
- **P01—P08 / U09：用户附件。** 完整输入名称与 SHA256 见 INPUT_MANIFEST.json。旧附件的探针回执与本轮新执行的回执分开保存。
- **Rxx：本轮检索的原始论文或官方项目。** 可用于近邻比较和设计借鉴，不代表已在用户环境安装、运行或证明可无缝兼容。
- 本整合计划中的新 schema、工单、模块名与实验配置均为**建议**，不是对仓库现有接口的描述。

## 2. 当前仓库依据

参考提交：`1eba36dd272c72573d1309c78d45dbe97dd8af12`。
基础前缀：`https://github.com/sisuolv/disastertrace-benchmark/blob/1eba36dd272c72573d1309c78d45dbe97dd8af12/`。

| ID | 已读取的路径/对象 | 支持的判断 |
|---|---|---|
| G01 | `https://api.github.com/repos/sisuolv/disastertrace-benchmark/branches/next-phase-v1` | 核验时分支 HEAD、父提交与提交日期 |
| G02 | `LATEST_PROGRESS_V12_CN.md` | 已完成量、发布状态及科研边界 |
| G03 | `plans/v12_execution_20260915_01/FINDINGS_AND_NEXT_GATES_CN.md` | Stage C完整分母、接口失败、同一天正例、下一阶段门槛 |
| G04 | `plans/v12_execution_20260915_01/analyze_branches.py` | 缺报告跳过、trace交集及passed逻辑 |
| G05 | `plans/v12_execution_20260915_01/siliconflow_worker.py` | 入口截止、发送顺序、capture/脱敏/恢复 |
| G06 | `disastertrace-starter/src/disastertrace/monitoring_v1/production.py` | failure标记阻断恢复响应消费 |
| G07 | `plans/v12_execution_20260915_01/analyze_stage_c.py` | 配对消费者标记、分母与缺失敏感性计算 |
| G08 | `README.md`（当前及历史入口段落） | 最新v12与多个历史入口并存 |
| G10 | `plans/v12_execution_20260915_01/FULLWEEK_FINDINGS_CN.md` | 每阈值6048注册/6008结算；5km307正例；同values后端程序增量 |
| G11 | `disastertrace-starter/src/disastertrace/monitoring_v1/residual_query_plan.py` | catalog记录cached/requested，但eligible只筛related/available |
| G12 | `disastertrace-starter/src/disastertrace/monitoring_v1/selection.py` | 旧双字段契约、旧code fence与严格句柄校验行为 |
| G13 | `disastertrace-starter/src/disastertrace/monitoring_v1/temperature_postprocess.py` | raw统一要求min/max；跨日zip成员假设；ECC需求 |
| G14 | `plans/v7_0912_overall_research/OVERALL_PLAN_CN.md`（研究定义段） | 原C1/C2/C3、E/F/D、16类与P/R基线轨定位 |
| G15 | `disastertrace-starter/src/disastertrace/forecast_task/common.py` | 严格JSON、文件封存与探针使用的公共函数 |

G09 未使用；编号无需连续，不代表遗漏一份必需结果。

### 本轮隔离探针的关键 Git blob 核验

| 文件 | Git blob SHA1 |
|---|---|
| siliconflow_worker.py | `7d2efb6dce9d35f2904c454ab44098bd51e6d9ff` |
| analyze_branches.py | `dffffd3440ab1f6363c3f042759b78118898ec0e` |
| production.py | `cb5a8c7897bd2e08432e48498b151bc54f52d50b` |
| selection.py | `74f24e9e484e76c350334b55b8dbad2d1efe0c6c` |
| forecast_task/common.py | `31ed9e5f3cceabda9d9553b28be89ed1858bfc9f` |

这些 hash 在本轮连接器结果与附件源码副本之间匹配；不代表该提交所有文件都被检出或运行。

## 3. 公开论文与开源项目

### R01 — EarthVerse

论文：*EarthVerse: Benchmarking Scientific Agents Across Dynamic Earth Systems and Natural Hazards*，2026-08-24，arXiv v1。

- 论文：`https://arxiv.org/abs/2608.23525`
- 正文：`https://arxiv.org/pdf/2608.23525`
- 本轮查阅：摘要、方法/贡献相关文本，以及PDF第1、3页截图。
- 用途：package-scoped调查、可执行答案单元与过程依据的近邻；指导E单元设计。
- 复用边界：本轮没有验证其完整代码安装和逐文件许可，不作为首批工程硬依赖。不能将它描述为只做静态QA。

### R02 — SIREN

论文：*SIREN: Towards End-to-End Extreme-Weather Early Warning with Experience-Grounded LLM Agents*，2026-07-27，arXiv预印本。

- 摘要：`https://arxiv.org/abs/2607.24588`
- 正文：`https://arxiv.org/html/2607.24588v1`
- 用途：端到端预警链、各过程分解和领域Agent参照。
- 复用边界：本轮未验证可直接复用的官方代码安装/许可；不把论文页的模板会议文字当真实录用信息。

### R03 — FutureSim

论文：*FutureSim: Replaying World Events to Evaluate Adaptive Agents*，2026-05-14，arXiv预印本。

- 摘要：`https://arxiv.org/abs/2605.15188`
- 正文：`https://arxiv.org/html/2605.15188v1`
- 作者项目页：`https://openforecaster.github.io/`
- 用途：时序回放、持续预测更新、检索隔离与反馈时点审计。
- 复用边界：本轮正文中的Code跳转未成功获取完整仓库，不声称已核验具体函数；时间过滤不是预训练记忆污染的充分排除条件。

### R04 — SentinelBench

论文：*SentinelBench: A Benchmark for Long-Running Monitoring Agents*，2026-06。

- 正文：`https://arxiv.org/html/2606.05342v1`
- 官方仓库：`https://github.com/microsoft/sentinel_environments`
- 用途：event-driven等待/反应、无须动作场景、时效与资源分开评价。
- 复用边界：只借鉴监测生命周期和等待策略；其合成网页/应用不是天气物理环境。引入源码前冻结commit并核查许可证及依赖。

### R05 — AFABench

论文：*AFABench: A Generic Framework for Benchmarking Active Feature Acquisition*，2025预印本，2026 ACM论文记录及当前公开代码。

- 论文：`https://arxiv.org/abs/2508.14734`
- ACM记录：`https://doi.org/10.1145/3770855.3817493`
- 官方仓库：`https://github.com/Linusaronsson/AFA-Benchmark`
- 已核验的仓库信息：MIT；`afabench`包；模块化策略与预算评价；README明确当前限classification。
- 用途：轻量value selector/有限lookahead的接口和对照设计。
- 复用边界：不运行整个Snakemake全方法流水线，不把静态特征获取直接当多目标异步监测。

### R06 — Extreme Weather Bench

论文：*Extreme Weather Bench: A framework and benchmark for evaluation of high-impact weather*，2026-05-01。

- 论文：`https://arxiv.org/abs/2605.01126`
- 官方仓库：`https://github.com/brightbandtech/ExtremeWeatherBench`
- 文档：`https://extremeweatherbench.readthedocs.io/`
- 已核验的入口：`src/extremeweatherbench/data/events.yaml`、`EvaluationObject`、case/forecast/target/metric构造；MIT代码许可。
- 用途：evaluator-side过程索引、第二物理链的领域验证adapter。
- 复用边界：数据许可另查；事件富集不能替代自然日历；当前README“paper in preparation”文字落后于已公开论文，不据此判断论文不存在。

### R07 — TerraBench

论文：*TerraBench: Can Agents Reason Over Heterogeneous Earth-System Data?*，本轮阅读2026-07-01的v2。

- 正文：`https://arxiv.org/html/2606.13148v2`
- 作者仓库：`https://github.com/Takerdat23/TerraBench`
- 用途：artifact-centered执行、数值容差、工具过程与最终答案分开评价。
- 复用边界：本轮没有运行该工程；采用设计不等于直接引入其全部Agent框架或模拟器。复制代码前确认版本和许可。

## 4. 来源如何支持方案，而不是替代用户材料

用户附件和当前仓库决定已完成状态、原研究术语、保护范围与具体代码问题。外部工作只用于校准novelty边界、补强参照方法和缩短实现路径。新增value selector、条件性bank、ScenarioCard、并行DAG与门槛设计均是本次建议，不应回填成某篇论文或原ZIP已做过的结果。
