# DisasterTrace：post-v12 综合后续计划

状态：**仅规划与复核；未授权、未启动新的 benchmark 执行。**

参考分支 `next-phase-v1`，本次回读 HEAD 为 `1eba36dd272c72573d1309c78d45dbe97dd8af12`。对应提交时间 2026-09-16 03:03:53 UTC（纽约 2026-09-15 23:03:53；北京 2026-09-16 11:03:53）。启动时必须再次核验真实 HEAD，而不是 reset 回该版本。

建议阅读顺序：

1. [整体整合计划](DisasterTrace_PostV12_Integrated_Plan_CN.md)：研究问题、已有结果、优先级、阶段出口。
2. [审查意见取舍](REVIEW_DECISIONS_CN.md)：8 个 ZIP 与 1 份 Markdown 的共识、冲突和限定。
3. [可交给 Codex 的首批指令](CODEX_FIRST_BATCH_CN.md)：有限 CPU/offline 工作与停止条件。
4. [机器工作包](WORK_PACKAGES.json)：IP00—IP16 的依赖、产物、权限与预算。
5. [相关工作与代码复用](RELATED_WORK_AND_REUSE_CN.md)：本次查询的一手文献、官方代码和适配边界。

`INPUT_MANIFEST.json` 保存原始附件与成员哈希；`REVIEW_SCOPE_AND_SOURCE_CHECKS.json` 区分本次源码阅读/字节校验和未重新执行的历史实验。`SOURCE_INDEX.json` 保存当前代码依据。`PACKAGE_VALIDATION.json` 是**文档/DAG/打包校验**，不是研究、代码或模型验收。

本包不重复装入 8 个原 ZIP、原始大数据、模型权重或 API 凭据；不是完整实验复现包。不将原审查包里的测试回执冒称本轮新运行。本次没有修改用户 GitHub 代码、启动云作业、发送被测模型请求或打开确认数据。
