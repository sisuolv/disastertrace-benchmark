# 正式评分并行交接

108 个方法运行及 288 个正式模型请求均完成后，原 Stage C 尾部仍串行核验 24 个评分组。为减少等待，本目录登记一次只涉及评分调度的交接；没有再次执行预测策略或发送模型请求。

- 原作业 `pt-ql97f4xq` 经平台停止后显示 `SUSPENDED`。本批将此状态映射为 `STOPPED`，原始平台状态及映射保存在 `ORIGINAL_JOB_TERMINAL.json` 和 `STOP_OBSERVATION_02.json`；不恢复这个已消费的作业，不声称其进程退出码为零。
- 停止前已完成的 3 个正式评分文件按路径和 SHA256 复用；其余 21 组交给新作业 `pt-g72ggm5x`，16 CPU / 64 GiB，12 个 worker。某个未完成组的原内部核验可能被中断，这属于验证工作，不计为新的天气轨迹。
- 每组调用同一个冻结包中的 `score_formal`，仍核验原始 journal、运行引用、源码与数据绑定、结果来源及完整分母。原模型回复、预测时点、费用和结果没有改变。
- 新评分写入本目录 `scores/`，已完成的原评分文件不覆盖。`RESULT.json` 记录每组实际路径、hash、是否复用及通过状态。
- 汇总 `../stage_C/RESULT.json` 通过 `finalization_kind=recorded_parallel_score_handoff` 指向本目录，保留 `original_serial_worker_completed_normally=false`。不能将该汇总解释成原串行 worker 正常跑完。

冻结登记在 `INTENT.json`，实际复用/剩余清单在 `REPLAY_ROSTER.json`，新作业回执与日志在 `../runtime/stage_c_audit_01/`。总报告的 `all_worker_exits_observed` 与 `all_worker_terminal_states_observed` 分开，平台停止不伪装成成功的进程退出。

运行最终以 `RESULT.json`、新作业 `EXIT.json` 及全批 `../RESULT_SUMMARY.json` 为准；提交成功或部分评分通过不代表全批完成。
