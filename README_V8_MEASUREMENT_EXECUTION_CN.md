# v8 当前执行入口

最近的代码、真实数据和大模型执行记录在：

- [执行入口](plans/v8_measurement_execution_20260913_01/README_CN.md)
- [详细结果与完成范围](plans/v8_measurement_execution_20260913_01/RUN_REPORT_CN.md)
- [实时任务状态](plans/v8_measurement_execution_20260913_01/EXECUTION_STATUS.json)
- [整体后续计划](plans/v8_measurement_execution_20260913_01/NEXT_PHASE_PLAN_CN.md)

本轮已完成 485 项核心相关回归及 17 项启动/分析补充检查、235B/8B 的 1,008 个固定输入正式回答、40 条真实全日历
程序轨迹及独立评分，扩展并验证了多区域原生资料。52 会话的四卡 235B 自适应实验
已全部结束，5,108 次调用与四组独立评分通过；原自动审计超时，完整结果来自有来源记录的补充审计。

温度扩展已实际完成原生六小时极值与 DWD 日值的两年配对、三日候选概率、
规范结果和 480 个准入快照回放，见
[日/多日温度闭环](plans/v8_measurement_execution_20260913_01/TEMPERATURE_DAILY_FORECAST_CN.md)。
四小时实时来源采集也已结束，34 次请求、25 个不同原生产品解析成功；没有实时模型预测提交。

已观察到完整证据和部分证据表现的明显差异，但尚无独立确认的 LLM 未来预测收益。
16 类灾害仍是完整路线，各子任务的实际资格分别登记；不以来源数量代替完成度。

本轮未 commit/push；原始索引副本、旧结果与失败记录保留。当前 Git 暂存内容与
原快照一致，索引缓存字节变化的只读核验见执行目录 `INDEX_EQUIVALENCE_01.json`。
