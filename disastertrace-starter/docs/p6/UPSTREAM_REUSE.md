# 参考 benchmark 与开源复用记录

本轮实际阅读的是用户提供的四份 plan 和本仓库冻结代码。外部论文/README 的内容
来自 plan 的整理，本轮没有重新联网核验、克隆、下载或执行那些外部项目。
因此新登记均标记 `design_only / supplied_plan_only`，commit、license 与访问日期
在没有本轮证据时为 null。不能继承方案作者的“已核查”措辞作为本轮实际工作记录。

机器登记：`../../../plans/p6/source_registry.json`。

| 来源 | 本轮采纳的设计 | 没有执行的内容 |
| --- | --- | --- |
| ALCE | 值/状态正确性与逐引用来源支持分开，保留细粒度证据 | NLI/AutoAIS 或神经 judge |
| CheckList | 以 pytest 实现 MFT/INV/DIR，覆盖同值来源刷新、scope、重命名/时间/行序变换 | 上游整套生成器与历史依赖 |
| tau-bench | 多次运行的 episode 全程成功与 pass^k | 用户模拟器、retail/airline 数据、LLM 错误归因 |
| STATE-Bench | 状态/运行身份隔离与环境、成本记录的设计参考 | 其完整任务、学习轨或 UX judge |
| STALE/CUP-Mem | 当前 authority 与旧主张区分，后续方法设计参考 | 读取 .env 的上游 runner、embedding 或模型调用 |
| MemoryAgentBench | 增量证据轨作为未来独立协议，保留累计证据对照 | 混入本轮 E1 或采用其 judge 标签 |
| RULER | 长度和决策复杂度应独立控制 | 把长输入本身叫作更强记忆压力 |
| ExtremeWeatherBench | 独立事件覆盖、预报目标与观测区分 | 天气基础模型、再分析数据下载或 forecast 误差成绩 |
| NHC/Tropycal | 后续同绝对 valid time 的官方 forecast 版本及独立解析设计 | 新资料抓取、A-deck 调用、声称示例值已经本轮验证 |
| XGrammar/vLLM | 继承本项目已经冻结的结构轨与 token/采样契约 | 升级依赖、复制新上游代码、声称同 seed 保证跨硬件复现 |

本轮新增实现为本项目自有代码；实际直接复用的是现有 renderer、parser、scorer、
adapter、tokenizer 配置与冻结 backend 文件。它们的 SHA-256 在 execution 中绑定。
真实资料阶段如需直接复制外部代码，应先记录精确 commit、文件散列、许可证及
最小读取范围；当前设计登记不是已通过这一步的证据。

补充第四方案的14个引用条目单列在 `plans/p6/source_registry_supplement.json`，与
初始登记可能重叠，不应相加成26个独立 benchmark。StateMemBench/StateMem 的论文
建议与 Microsoft STATE-Bench 分开；LongMemEval、AFDBench 和 CAP/VTEC 仅作后续
边界参考。本轮实际使用已安装 Hypothesis 6.167.1 做纯程序性质测试，没有获取上游
新版本、打开其外部文档或启动在线 shrink/model 测试。
