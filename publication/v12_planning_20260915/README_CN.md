# v12 整体计划与执行前复核材料

本次发布用于复核下一阶段计划。**新的阶段 A/B/C/D 均未启动；上传 GitHub 不改变执行授权状态。**

## 阅读顺序

1. [整体计划](../../plans/v12_planning_20260915_01/OVERALL_PLAN_CN.md)
2. [下一批执行规格](../../plans/v12_planning_20260915_01/NEXT_BATCH_EXECUTION_CN.md)
3. [七份审查意见取舍](../../plans/v12_planning_20260915_01/REVIEW_DECISIONS_CN.md)
4. [给 ChatGPT Pro 的复核说明](REVIEW_FOR_CHATGPT_PRO_CN.md)
5. [打包下载](DisasterTrace_v12_planning_review.zip)

## 发布范围

包含规划文档、22 个拟议工作项、原始七份输入、已解压审查材料、规划时的本地/平台观察、源码一致性与规划包验证记录。原始输入在 `plans/v12_planning_20260915_01/original_inputs/`，对应本机文件身份在 `REVIEW_INPUTS.json` 中保留。

代码审阅基准为父提交 `889620a4fc4ee6ad70757dd3e832a40c7509126a`。本次只追加规划/发布材料和仓库导航，不修改 benchmark 实现、冻结实验、银行、模型回答或运行日志。

规划中的进度固定在 2026-09-15 13:28—13:29 UTC；它不是实时状态。旧文档中的“尚未推送”和 `github_push_performed=false` 描述当时的规划过程，本次发布回执取代其发布状态，不改写旧记录。此前登记任务的后续实验结果不自动纳入本次快照。

ZIP 是计划复核包，不含全部原始气象数据、权重、运行中检查点或未打开的确认数据，不能作为整个 benchmark 的独立复现包。审查包里的脚本是审阅者提供的探针，并非本次新实现或新测试结果。

文件导出身份见 [EXPORT_MANIFEST.json](EXPORT_MANIFEST.json)；原始输入与发布路径映射见 [ORIGINAL_INPUTS.json](ORIGINAL_INPUTS.json)。
