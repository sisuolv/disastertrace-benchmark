# 复查任务：v13 完成结果

请固定当前 Git commit，先读根目录 `LATEST_PROGRESS_V13_CN.md`，再读本目录 `RESULT_VALIDATION.json`、`RESULTS_SNAPSHOT.json` 和三批最终结果。
本次 B00/C00/B02/M01 全部已结束。上次 `013c64f` 是进行中快照，旧文件中的等待状态不可作为最新结论。

希望你重点回答以下问题，并按 P0/P1/P2 列出代码、数据或回执依据：

1. 本次模型结果是否只支持“开发集上略好于 batch/coverage、未超过简单强程序”？检查 864 个机会、857 个可结算结果、7 个缺失、3 个正例，以及开发周/独立天气过程的区别。缺失 Y 敏感性界不能称作置信区间。
2. 13 个失败在运输记录中为 `BlockingIOError/not_sent/no HTTP intent`，消费者为 `unknown_execution`，仍保留 432,640 tokens 额度。这是否存在分类或资源结算问题？检查 `api_transport_v2.py`、`production.py`、`spool_backend.py` 和逐日 `API_AUDIT.json`。原日志仅支持已记录事实，根因尚未实测定位，不要臆造锁问题已解决。
3. 模型只输出查询顺序，程序生成 F。实际时延计费、查询前缀执行、尾部 disposition、及时采用是否会解释相对强程序差异？需要怎样的后续诊断才能区分这些影响？勿将选择器结果说成模型自主天气概率预测。
4. B02 的轮转/固定哈希与模型具有相同预算/权限条件；固定份额/私有 coverage 改变了实验因素。比较是否按消费者和干预身份解释？完整 B00 与 M01 子集的 Brier 不可直接横向比较。
5. C00 完成 12 父、48 GET 分支，但 TAF 时间覆盖全 full，父状态所需站报全部未取证。哪些 novelty 已有实证，哪些来源状态和 PROCESS/TIMING 机制仍缺？不要将未取证误记为源缺报。
6. `preservation_passed=false` 与 Git index 缓存变动是否已充分披露？冻结源码/前置绑定无变化和 Git index 字节不一致是不同检查，不能合并成“全部通过”。
7. 下一步优先级是否应为发送前失败诊断、动作/延迟/采用分析、独立过程与来源状态覆盖，再冻结方法后确认？当前 1 小时年度预测器不能直接推出 3/6 小时能力，16 灾种总体路线也不等于已落地 16 条主动链。

关键材料：

- `plans/v13_followup_20260916_01/B00/ROWS.json`、`RESULT.json`、`PAIRED_COMPARISONS.json`。
- `plans/v13_followup_20260916_01/C00/ANALYSIS.json`、`RESULT.json`、`SOURCE_STRATA/RESULT.json`（最后一项位于 followup 根目录）。
- `plans/v13_strong_baselines_20260916_01/ROWS.json`、`STRONG_BASELINE_COMPARISON.json`、`ACTION_EQUIVALENCE_REPORT.json`。
- `plans/v13_selector_execution_20260916_01/FINAL_RESULT.json`、`ROWS.json`、`COMPARISONS.json`、`cases/*/API_AUDIT.json`、`cases/*/CONSUMER_AUDIT.json`。
- `publication/v13_completed_20260917/audit_results.py`：发布期的行级算术核验，不等价于从原始资料独立复现全部实验。

不要因负结果否定 benchmark，也不要因运行完整或测试多就认可 novelty。请区分明确错误、证据缺口和研究局限；没有复跑的部分明确标注静态审查。ZIP 未包含完整原始数据或会话日志，不能据此声称完成独立科学重放。
