# 相关一手工作：可复用的部分、不能替代的部分

这是本次在线检索后的补充，不代表八份原ZIP都已经包含这些结论，也不代表相关依赖已装入用户环境。未发现的许可/源码字段不猜测。引入代码前固定upstream commit/tag、许可证和最小依赖；阶段A默认不自动下载或安装。

## 1. EarthVerse

论文：2026-08-24，arXiv:2608.23525v1。原文定义package-scoped科学调查，405任务、199事件、19灾害家族；它包含证据发现、工具、执行和过程诊断，不是简单静态QA。

```text
https://arxiv.org/html/2608.23525v1
https://github.com/CuiZHIQ/Earth-Verse
```

官方代码入口已核对：`tasks/<task_id>/`、`scripts/validate_submission.py`、`tools/earthverse_tools/`、`tools/meteorological_environments/`，以及配置/manifest。

建议复用：字段化任务合同、来源作用域、提交完整性验证和专业工具封装思路。接到IP01/IP05/IP11，形成“GET/PROCESS/WAIT任务卡和实际消费者义务”。不直接搬评分主分：EarthVerse公开流程包含judge/rubric，本项目概率真值和费用应保持确定性程序核验。也不把它的事后事件包当本项目截止前可见资料。

对novelty的要求：DisasterTrace应证明持续共同预报、多目标资源竞争、可行同状态分支、未来损失和采用时机，而不是重复“多源+工具+可追踪”。这是任务定位判断，不是全球首创保证。

## 2. Extreme Weather Bench（EWB）

论文：2026-05-01，arXiv:2605.01126。原文强调高影响天气的观测验证，并提供部分边缘事件以缓解只评极端案例的forecaster’s dilemma。论文数据可用性说明其结果使用v1.0.1；这个论文版本不等于当前包的最新版本。

```text
https://arxiv.org/html/2605.01126v1
https://github.com/brightbandtech/ExtremeWeatherBench
```

建议复用：事件卡、物理窗/空间支持、参考配对和事件/边缘条件分层。接到IP07、IP14、IP15。当前H15主评估仍保留全部自然日历；不能直接把EWB事件清单当历史公开时间或本项目独立天气过程的证明。若引入其数据，重新核来源版本、窗口和权利。

## 3. WeatherBench-X

这是现行开源评估框架，不在本次为它猜一个“最新论文日期”。官方README明确其按data loaders、interpolation、metrics、aggregation模块化，基于xarray，支持站点/卫星等稀疏数据；Apache-2.0代码许可。

```text
https://github.com/google-research/weatherbenchX
https://weatherbench-x.readthedocs.io/en/stable/
```

建议复用：对IP07/IP15的纯预测数值验证提供小型适配器，将已准入的预测/标签映射到独立Brier/连续变量等指标。先与本项目简单独立算术逐样本相等，再扩展。不要把admission、授权、共享预算、实际时钟和失败分母交给它替代；框架通用不等于数据语义自动正确。短期不为了一个H15任务启动Beam全栈迁移。

## 4. AFABench

论文首版2025-08-20，本次查到当前arXiv v3日期2026-02-22，编号2508.14734。它覆盖静态、贪心和非贪心主动特征获取策略；代码公开了EDDI/GDFS/DIME/JAFA等类别。当前README说明主要支持分类，而非直接提供所有回归任务。

```text
https://arxiv.org/abs/2508.14734
https://github.com/Linusaronsson/AFA-Benchmark
```

建议复用：状态—查询—停止的策略接口、静态/贪心/有限lookahead基线和小型非贪心单元测试思想，接到IP04/IP12。先移植一个轻量策略适配器，不移植全部Hydra/Snakemake/RL流水线。未读特征mask不能表达本项目的版本、时间、private/shared权限；动作价值估计只能用训练侧，不能直接读评估标签或未取证字段。

## 5. EcoAgent-Bench

论文：2026-08-06，arXiv:2608.05519v1。研究在预算内升级、节省和停止的决策，指出只看平均完成率会掩盖单边策略问题。

```text
https://arxiv.org/html/2608.05519v1
```

建议复用：在IP12/IP13中同时报告昂贵操作是否必要、遗漏值得的查询、预算使用与质量的关系，建立save/upgrade诊断面板。不要为了凑平衡而按评估损失重采自然日历，也不要强制非all/none才算合格。经济一致性指标不能替代proper forecast score；情景费用不能冒称真实账单。

本次没有明确核实该论文的官方独立代码仓库，不提供猜测URL，不把“论文称发布”写成“已验证代码可直接用”。

## 6. ForecastBench

官方项目与代码确认其使用持续更新的未来问题及后续结算；相关论文发表于ICLR2025。作为prospective协议参考，不作为H15标签或专业基线。

```text
https://forecastingresearch.org/research/forecastbench-a-dynamic-benchmark-of-ai-forecasting-capabilities
https://github.com/forecastingresearch/forecastbench
https://forecastbench.org/
```

建议复用：提前冻结submission、题目身份、结果成熟与更新记录的生命周期，接到IP16。不要复制网站排行榜作为天气技能证据；也不将其未来问题设计宣称的污染规避转移为本项目历史回放无污染。

## 7. EUPPBench及官方后处理代码

原始数据论文：2023，ESSD 15:2635–2653；这不是2026新发布工作，但对当前已实现温度链最直接。官方项目给出预报/参考配对、数据获取与后处理/验证代码入口。

```text
https://eupp-benchmark.github.io/EUPPBench-doc/
https://eupp-benchmark.github.io/EUPPBench-doc/files/EUPPBench_datasets.html
https://github.com/EUPP-benchmark/ESSD-benchmark
```

建议复用：温度支线的坐标/成员/起报/日窗和独立数值对照。已有EMOS/ECC保留，不又列成首次开发任务。分析就绪配对不证明当年每个补证版本的公开时间；原始成员谱系和DWD结果变量合同必须单独核验。

## 8. SiliconFlow官方结构化输出接口

官方Chat Completions文档区分json_schema与只保证JSON语法的json_object；具体模型、schema关键字和实际长天气请求仍需本项目资格验证。

```text
https://docs.siliconflow.cn/docs/api/chat-completions-post
```

建议复用：实际请求的response_format接口，绑定schema/hash/model/参数；不靠prompt建议替代结构约束，也不相信schema能替代本地权限、预算和时间校验。并行输出/长度/拒答仍须按失败合同处理。

## 9. 代码接入的统一最小验收

每个拟复用组件登记：论文版本、官方仓库、实际commit/tag、许可证、拟用函数/模块、依赖、输入输出字段、单位/时间/缺失语义和最小golden test。取得工具源不等于具备其数据许可；未指定固定版本的外部代码不写入冻结manifest。

本计划只确定“复用哪一层”。不在首批混入新模型下载、全量气象预报重跑、海量原始影像获取或更换已有测量内核。小适配器和独立算术先行，科学范围通过再扩展。
