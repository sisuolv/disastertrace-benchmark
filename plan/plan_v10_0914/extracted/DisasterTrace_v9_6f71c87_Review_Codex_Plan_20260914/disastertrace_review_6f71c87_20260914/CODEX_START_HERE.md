# 给 Codex 的启动说明

请先完整阅读 `REVIEW_AND_CODEX_NEXT_PLAN_CN.md`、`specs/work_packages.json` 和验收规格。
参考提交为 `6f71c8799ff69439a18f645e63b8c966ca21eec4`，实际工作区可能已更新；先读取所有适用AGENTS.md、HEAD、未提交修改和冻结目录。不reset、不覆盖旧数据/Gold/输出/失败，不改变已消耗launch。

保持v9与N1—N5、C1/C2/C3、E/F/D/MM。首轮只做：

1. N1-maintain：核对已修的干预历史、结果时间、COPY、区域校准与温度连续轨，避免重复开发。
2. N3-coherence：在同实体/时间/信息条件下扫描嵌套阈值概率一致性；本文反例使用真实参数与合成输入，先量化真实影响，不预设已有评分全部错误。
3. N3-attribution：记录raw cell、fallback、原始概率、post-calibration family、缺报/读取模式；拆开校准切换与新天气内容收益。
4. N3-slot-bridge：离线复算已有逐槽输出，程序汇总作为新混合方法，不修改原E分数；明确当前fuser消费逐槽计数而不是最终fact_truth。

第一轮禁止新模型/API/GPU、大规模下载、重新打开确认周或公众告警。数据准备可以输出新范围，但不可自动继承历史费用授权。保持当前暂停，只执行用户明确批准范围。

交付实际代码、直接生产接口回归、原始日志、affected/unchanged/not_evaluated影响清单、清楚的比较合同和下一批资源清单。完整温度程序工作已完成，不得再次把它写成未开始。多模态和online各设一个近期出口，不让它们等待全部16类或复杂D。

不能仅返回下一份计划；不能通过强制模型改概率或按模型收益筛日期制造novelty。未证明处明确保留。
