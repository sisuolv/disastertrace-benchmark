# 整体灾害蓝图与样例验证：GitHub 阅读入口

2026-09-11。目标仓库 `sisuolv/disastertrace-benchmark`，分支 `next-phase-v1`。

建议阅读顺序：

1. [完善后的整体方案](../../plans/v6_blueprint_sample_validation_20260911/OVERALL_PLAN_REFINED_CN.md)。
2. [16 类灾害的数据合同](../../plans/v6_blueprint_sample_validation_20260911/HAZARD_SOURCE_MATRIX.md)。
3. [逐来源样例与选择清单](../../plans/v6_blueprint_sample_validation_20260911/SOURCE_SAMPLE_INVENTORY.md)。
4. [最终科学解析记录](../../plans/v6_blueprint_sample_validation_20260911/NEW_SAMPLE_AUDIT_05.json) 与 [请求计数](../../plans/v6_blueprint_sample_validation_20260911/CAPTURE_SUMMARY.json)。
5. [主动预警研究设计与文献比较](../../plans/v6_active_warning_review_20260911/RESEARCH_PLAN_CN.md)。

给 ChatGPT Pro 的重点问题见 [复查说明](REVIEW_FOR_CHATGPT_PRO_CN.md)。[阅读附件](disastertrace_blueprint_review.zip) 包含本次选定代码、文档、请求回执和审计报告；[发布清单](PUBLICATION_FILES.json) 记录 SHA256。

ZIP 内的 `READING_SCOPE.json` 提供随包文件哈希；解压后同一副本检查命令会自动读取它。附件不重复包含 ZIP 自身、仓库发布清单或发布后的验证记录。

本次数据核验实际执行 125 次请求，保存约 90.52 MiB 响应；最终解析有 31 条科学内容记录及 2 条渲染地图记录。来源清单 97 项包含继承、拆分和候选项，不能解释为 97 个独立可用数据集。新正式评测任务、模型调用和 GPU 作业仍为 0。

## GitHub 副本的范围

本次上传方案、采样/解析/制表/验证代码、请求规格、结构化回执、统计和审计结果，并补充尚未发布的主动预警研究计划及 NHC/水文连接报告。两份用户蓝图在 `inputs/` 中以明确名称保存。

大型原始 HTTP payload、NetCDF/GRIB/雷达数组、完整图片、解析环境和模型权重保留在原工作区。原审计中的本地路径和原始哈希照实保留；它们证明审计引用的对象身份，不意味着这些数据已包含在 GitHub 副本中。

`plans/v6_blueprint_sample_validation_20260911/VERIFY_REPORT.json` 是上传前数据工作区的检查记录；其同目录 `verify_delivery.py` 依赖原始数组和当时 Git 状态，不能直接用于检查本发布副本。请运行不联网、不调用模型的阅读副本检查：

```bash
python publication/blueprint_review_20260911/verify_snapshot.py
```

该检查核验随包文件、关键计数和新阅读入口，不重跑科学解码或模型实验。结果见 [PUBLICATION_VALIDATION.json](PUBLICATION_VALIDATION.json)。历史报告对应各自生成时刻；最新研究方向和数据边界以本入口链接的整体方案为准。

## 原始输入

- [整体数据蓝图 01](inputs/overall_blueprint_01_CN.md)。
- [整体数据蓝图 02](inputs/overall_blueprint_02_CN.md)。

本复查说明由 Codex 编写，不表示 ChatGPT Pro 已实际完成审查。
