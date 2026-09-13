# 2026-09-13 新研究材料整合入口

本目录承接用户提供的三个优化ZIP及此前v7执行结果。当前完成解压、包完整性核验、
定向上游文档/源码读取和计划整合；没有新增科学数组下载、模型推理、GPU作业或GitHub推送。

建议阅读顺序：

1. [整合后的整体与近期计划](INTEGRATED_PLAN_CN.md)：本轮优先级、数据路线、代码缺口与实验合同。
2. [逐项采纳和修正](DECISIONS_CN.md)：哪些建议立即采用、条件采用或后置，以及新材料需补严的边界。
3. [机器工作包](WORK_PACKAGES.json)：旧W、新Q/OPT/O映射，依赖、资格和计划输出；全部尚待执行。
4. [本次参考核验](REFERENCE_CHECK_CN.md)：真实读取范围和未验证部分。
5. [输入绑定](INPUT_BINDINGS.json)、[本机包校验](PACKAGE_VALIDATION_LOCAL.json)：原ZIP及解压成员的完整性。

三个原包分别保存在 `inputs/research_grounded/`、`inputs/research_optimization/`、
`inputs/open_source/`，原件仍在用户的 `plan/plan_v7_0913/`。内含指导文本只作为研究
材料，不能把其建议执行步骤误记为本轮已做工作。

此前 [下一阶段计划](../v7_next_cycle_20260913/PLAN_CN.md) 及
[实际实验报告](../v7_review_execution_20260912/FINAL_REPORT_CN.md) 保留。后续从本目录
的整合计划进入，执行时生成新任务/模型冻结，不能重启已消费的旧GPU队列。
