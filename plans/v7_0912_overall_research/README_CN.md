# DisasterTrace v7 整体研究方案入口

先读 [整体研究与建设方案](OVERALL_PLAN_CN.md)。它将最终目标、novelty、全部 16 类灾害、自动评分、实验和完整路线放在同一研究合同中；[原下一步计划](../v7_0912_monitoring_optimization/PLAN_CN.md)继续作为工程附录。

- [逐灾种数据与任务合同](HAZARD_DATA_PLAN_CN.md)：数据来源、处理、未来目标、强基线与准入条件。
- [近邻工作和开源代码核查](RELATED_WORK_MATRIX_CN.md)：特别比较 EarthVerse、SIREN、Obshazard、SentinelBench、FutureSim 与 AFA。
- [创新约束](NOVELTY_CONTRACT.json)、[十组实验](EXPERIMENT_MATRIX.json)、[八个全程阶段](MASTER_MILESTONES.json)：供执行与复查的结构化索引。
- [97 条目用途快照](SOURCE_USAGE_MAP.json)、[16 类机器合同](OVERALL_HAZARD_CONTRACTS.json)：继承访问证据，未把取样解码提升为正式任务准入。
- [文献阅读记录](literature/REVIEW_INDEX.json)、[读过的正文节选](literature/REVIEWED_SECTIONS.json)：保留访问/传输边界；不是完整系统查新。

在仓库根目录运行：

```bash
python plans/v7_0912_overall_research/validate_plan.py
```

输出 [规划结构验证](validation/PLAN_VALIDATION.json)。检查 JSON、里程碑依赖、来源/实验 ID、本地引用、绑定输入哈希及 Python 语法；不运行模型、下载科学数据或宣称科学任务通过。历史输入哈希若改变，应先核对变化并建立新计划快照，不静默重写旧依据。

本包及其文献下载器不含访问数据源的凭据。公开源码文本是阅读证据，未执行；实际复用仍须按所选上游许可证处理。
