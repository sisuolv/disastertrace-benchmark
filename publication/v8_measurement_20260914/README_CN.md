# ChatGPT Pro 复查入口：v8 最新实验

请先阅读 ../../plans/v8_measurement_execution_20260913_01/REVIEW_REQUEST_CN.md，
然后按该文件中的 P0/P1 重点复查代码、数据合同和结果归因。

- [详细实验报告](../../plans/v8_measurement_execution_20260913_01/RUN_REPORT_CN.md)
- [完整分数表](../../plans/v8_measurement_execution_20260913_01/ADAPTIVE_SCORECARD_CN.md)
- [后续计划](../../plans/v8_measurement_execution_20260913_01/NEXT_PHASE_PLAN_CN.md)
- [最新工作包状态](../../plans/v8_measurement_execution_20260913_01/WORK_PACKAGE_PROGRESS_02.json)
- [可下载复查 ZIP](DisasterTrace_v8_code_and_progress.zip)

本 ZIP 是新生成的 review_local_03，修正了复查指南的最终结果路径；原 review_local_02
保留在原目录，旧哈希未改。ZIP 内的 published_to_github=false 记录的是本地构建时状态，
实际发布以 GitHub 提交及另存的推送/回读回执为准。

包含当前源码、冻结 GPU 批次源码、37 个相关测试文件、结果汇总和可搬迁的两个
216 机会 journal 回放样例；不含模型权重、凭据和全部大型原始数据/模型 token。
因此可阅读和复查当前实现，不能声称仅凭这个 ZIP 已完整复建所有上游数据及实验。
历史冻结源码与当前开发源码分别保存，核验原实验时应使用对应冻结版本。

重点核查：当前概率沿用与新信息增益是否混淆；E充分性与F收益是否分开；
共同基线、费用、时间和修订协议是否公平；单日少量正例能支持哪些结论；
补充审计的并行原日志回放、缓存与完整对照一致性是否充分。
独立过程、X09、原生MM、完整D和16灾种仍未全部完成，不应补成正面结论。

本次以既有 next-phase-v1 的最新远端提交为父提交，只更新明确列出的文件，
保留服务器开发工作区的原 HEAD、暂存内容和历史实验。
