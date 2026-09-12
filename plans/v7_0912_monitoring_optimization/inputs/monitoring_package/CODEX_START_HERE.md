# Codex 首轮执行入口

完整阅读 `DISASTERTRACE_MONITORING_IMPLEMENTATION_CN.md` 和 `specs/`。这是实施计划，不是所有模块已经存在的说明。

先读取当前工作区全部适用AGENTS.md、实际HEAD、git status、依赖与可复用资产。参考提交是ae69453ff15bc3def6c513fafbfd8758437a8587，不得reset或覆盖本地未提交内容。旧结果、运行包和失败必须保留。

本轮优先实现M00、M01、M03、M04和M07的合成离线部分；M02先检查已有本地资产。真实任务和模型验收仍遵守工作包依赖，不以合成fixture通过假称真实任务通过。

建议新增 `disastertrace/monitoring_v1`，不要重建项目、默认安装全部外部框架或启用多Agent/网页UI。先交付真正可运行的contracts/state/budget/session reducer与测试，不只再生成空文档。

首先使以下行为可运行：

- 多目标共享一个预算与时钟，单个目标截止不会终止其他目标。
- FOLLOW随最新共同基线更新；OVERRIDE保持至明确改写或FOLLOW；NO_CHANGE不是FOLLOW。
- 相同源版本获取可复用；新的渲染、重复视觉推理与selector开销照实计量。
- 不同策略的缓存授权、预算、预测和carrier隔离。
- 并发预算先原子预留；请求与推理输入版本冻结；晚结果不生效；崩溃后未知调用不自动重做。
- 所有目标保留；未查询默认委托、模型失败和未结算结果分别报告。
- 模型进程无未来标签、grader、任意shell或隐私源路径；第三方AFA adapter禁止传label。

不运行新模型、训练、GPU任务或付费API，不自动开始新在线采集/大文件下载，不重启旧后台作业，不push。后续若需要新增范围，提交明确文件/查询白名单、字节/调用/并行/时间上限，使用用户已经明确允许的范围，不重复请求已知信息。

交付：实际改动清单、可执行离线CLI与测试、原始测试输出、尚未实现项、与旧结果不变的核验、下一批真实同区域任务的配对清单。`session_example.template.json`必须拒绝直接进入科学运行；它不是已验证数据。

所有验收测试JSON条目目前是planned_not_executed，执行后以独立结果文件记录pass/fail/blocked，不改计划为伪通过。
