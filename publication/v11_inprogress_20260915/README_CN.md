# v11 当前代码与进行中实验快照

先读仓库根目录 `LATEST_PROGRESS_V11_CN.md`，再读本目录的
`REVIEW_FOR_CHATGPT_PRO_CN.md` 与 `PROGRESS_SNAPSHOT.json`。

本次上传包含当前代码、测试、整合计划、完成回执、真实预检和进行中任务的状态快照。
它不是整个 v11 已完成的发布。后台执行继续，GitHub 文件只代表标明时间的观察；
后续完成结果需要另一次发布。

主要入口：

- `disastertrace-starter/src/disastertrace/monitoring_v1/`：会话执行、数值合同、API 门槛等。
- `disastertrace-starter/src/disastertrace/monitoring_fixed_v1/`：正式评分与原生特征预测器。
- `disastertrace-starter/tests/test_monitoring_v11_boundaries.py`：本轮边界回归。
- `disastertrace-starter/tests/test_monitoring_native_feature_session.py`：共同信息银行的回归。
- `plans/v11_execution_20260915_01/REGRESSION_RESULT_02.json`：750 个不同测试通过的范围。
- `plans/v11_execution_20260915_01/profile_01/RESULT.json`：同一九方法日志的评分等价与性能测量。
- `plans/v11_execution_20260915_01/real_pilot_02/`：完整五组真实预检记录。
- `plans/v11_execution_20260915_01/c2_design_01/`：开发前缀登记和真实 E 构建检查。
- `plans/v11_planning_20260915_01/OVERALL_PLAN_CN.md`：整体研究计划。

`DisasterTrace_v11_progress_and_code.zip` 是本次新增/更新代码与阅读材料的压缩包，
逐文件身份见 `EXPORT_MANIFEST.json`。它不包含所有历史仓库文件、完整原始资料、模型权重、
Python 环境、运行中的 journal/checkpoint 或未读确认集，因此不能单独重建全部实验。
真实预检保留原目录绑定；其导出也不等于完成了新的可搬迁复算验证。

先前 v10 的两个有限 CPU 复算包和旧发布材料保留在仓库中，适用范围不因此扩大。
阅读快照无需运行任何采集/云提交/模型脚本。所有历史启动器的运行身份继续视为已消费。

发布通过独立 Git 对象库完成，开发 worktree 的 HEAD、索引和活动任务保持原状。
仓库继续使用私有 `sisuolv/disastertrace-benchmark` 的 `next-phase-v1` 分支。
