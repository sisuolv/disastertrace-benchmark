# DisasterTrace v7 整体研究方案与最新数据验证

此次发布把完整 v7 研究方案与新授权数据验证代码接到现有 `next-phase-v1` 历史之后。建议从 [整体主计划](../../plans/v7_0912_overall_research/OVERALL_PLAN_CN.md) 开始，再读 [16 类数据合同](../../plans/v7_0912_overall_research/HAZARD_DATA_PLAN_CN.md) 和 [近邻工作比较](../../plans/v7_0912_overall_research/RELATED_WORK_MATRIX_CN.md)。

本轮新增三个方面：

- 整体研究：共同专业预报上的多目标预算分配、可计算证据支持与有限可达性、选择性预测修订，配 10 组实验与 8 阶段路线。
- 数据验证：加入 EM-DAT、CMA、xBD 的本机解码/审计代码与结果。最新 97 条目中 86 有内容、7 为目录、2 待授权、2 缺目标原生内容；可读样例不等于合格预测任务。
- 工程规划：保留三个 v7 原方案的展开文本、整合后的下一步计划和本次整体计划，协议冲突及待实现状态明确记录。

`monitoring_v1` 尚未实现；本次没有新增模型/GPU 评测，也没有证明主动取证正收益。旧模型链的 1,120 条回复与第二轮只查官方预报的负结果仍保留。CMA 的单位/平均时长/时区合同、xBD 的配准与正类覆盖仍待解决。

[给 ChatGPT Pro 的复查任务](REVIEW_FOR_CHATGPT_PRO_CN.md)列出建议审阅顺序。`chatgpt_pro_v7_overall_review_20260912.zip` 是精选代码与文档附件；`EXPORT_MANIFEST.json` 绑定文件和哈希。原始科学数组、EM-DAT 工作簿、CMA 原始归档、xBD 大文件、模型权重、运行环境和凭据不在该附件中。完整科学重放需要许可允许的原始资料与依赖。

本包的 `export_snapshot.py` 只构建明确范围的发布副本，不提交或推送 Git。发布时使用现有远端 commit 为父节点、独立索引构建新提交；本机工作分支和现有暂存区保持原状。推送后的 commit/remote 核验回执保存在本机 `PUBLISH_RESULT.json`，避免在提交中伪造自引用的发布完成状态。
