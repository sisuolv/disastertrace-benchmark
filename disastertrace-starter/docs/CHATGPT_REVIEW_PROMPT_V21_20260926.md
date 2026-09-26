# ChatGPT independent review prompt — extreme_weather_benchmark v21

你是一个独立的 benchmark、机器学习实验和研究方法审计者。请审查本仓库当前 GitHub 版本，重点分析 v21 之后是否真的完成了原计划，以及哪些结论可以被真实证据支持。

请先读取并交叉核对：

1. `docs/audits/INDEPENDENT_REVIEW_V21_20260926_CN.md`
2. `docs/V21_RELEASE_20260925.md`
3. `artifacts/v21_execution_20260925_04/CLAIM_EVIDENCE_TABLE_V4.md`
4. `artifacts/v21_execution_20260925_04/PROTOCOL_GATE_V4.json`
5. `artifacts/v21_execution_20260925_04/HANDOFF_REPORT_V4.md`
6. `artifacts/v21_execution_20260925_04/REAL_DEV_DETERMINISTIC_SCORE.json`
7. `artifacts/v21_execution_20260925_04/G1_DEV_EPISODES_V3.json`
8. `artifacts/v21_execution_20260925_04/REAL_DEV_ASOS_OUTCOMES.json`
9. `src/disastertrace/monitoring_v1/natural_track_v18.py`
10. `src/disastertrace/monitoring_v1/natural_selector_policy_v21.py`
11. `src/disastertrace/monitoring_v1/active_policy_v21.py`
12. `src/disastertrace/monitoring_v1/interventions_v18.py`
13. `scripts/run_v21_real_dev_source_bridge.py`
14. `scripts/run_v21_real_dev_deterministic_score.py`
15. `scripts/run_v21_cost_matched_adaptive_surface.py`

不要只接受审计报告结论。对关键判断必须回到实际代码、JSON artifact 和测试结果。特别检查：

- public-schedule future source 是否会造成重复 RETRIEVE、查询预算失效或无法终止；
- `available_at=None` 的 delay intervention 是否被错误地变成具体时间；
- 真实开发集的 `active_age` 是否真的实现了内容依赖式二次查询；
- 24 个 episode 的实际月份、22/2 标签比例、72 个 checkpoint 的非独立重复问题；
- synthetic GPU 实验是否只是由数据生成器预先构造了 active 优势；
- artifact 中记录的 HEAD、worktree 状态和当前 GitHub HEAD 是否一致；
- 文档中的 CPU reproduction 和完整 pytest 是否真的可执行。

请输出一份独立报告，至少包括：

1. 当前 HEAD、分支、发布状态和证据包边界；
2. 原计划每个阶段的 `CLOSED / PARTIAL / NOT_CLOSED / BLOCKED` 判定；
3. 每条 finding 的严重性、精确 `file:line`、证据状态（`STATIC_CONFIRMED` 或 `PLAUSIBLE_UNVERIFIED`）；
4. 哪些结论只是工程/协议结论，哪些是实验结论，哪些仍不能声称；
5. 对天气价值、active policy、provider/LLM 效果和 novelty 的独立判断；
6. 下一阶段 3–5 个任务，每项给出目标、输入、成功标准、失败标准、预计成本和停止条件；
7. 明确列出当前不值得继续运行的实验。

请特别避免以下错误：

- 把 226 个测试通过当成科学假设成立；
- 把 fixed prior 的 Brier 改善当成 active policy gain；
- 把 synthetic GPU 成功当成真实天气价值；
- 把允许读取 January/March 当成实际样本已经覆盖两个季节；
- 把 one-query `active_age` 的平局写成对 content-adaptive follow-up 的最终否证；
- 在 runtime contract、样本分布和统计分母未修复前启动正式 holdout 或 provider 结论。

最终请给出一个单一、明确的总判断，例如：

`PARTIAL_PASS_ENGINEERING_INCONCLUSIVE_RESEARCH`

并解释下一步应该优先修复什么、哪些结果必须重新运行，以及在什么条件下才可以进入 provider、holdout 或 novelty claim 阶段。
