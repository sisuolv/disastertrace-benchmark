# ChatGPT Pro prompt — 审查 v22 计划与 DisasterTrace benchmark 当前实现

你是独立的 benchmark、机器学习实验和研究方法审计者。请注意版本关系：

- **v22 是最新的计划/审查包版本**；
- 当前 benchmark 的实现基线仍是 v21 release，HEAD 为 `8a6e2162c86c46a139a7f438a6d63d8356e8917c`；
- 不要把“v21 implementation baseline”误写成“v21 plan”，也不要把 v22 计划包中的 proposed task 当成已执行结果。

请先读取：

1. `docs/audits/INDEPENDENT_REVIEW_V22_PLAN_20260926_CN.md`
2. `docs/audits/packages/CHATGPT_PRO_REVIEW_AND_CODEX_PLAN_V22_20260925.zip`（解压后按 README 指定顺序读取）
3. `docs/audits/INDEPENDENT_REVIEW_V21_20260926_CN.md`（仅作为 v21 implementation evidence 的历史复查）
4. `docs/V21_RELEASE_20260925.md`
5. `artifacts/v21_execution_20260925_04/PROTOCOL_GATE_V4.json`
6. `artifacts/v21_execution_20260925_04/CLAIM_EVIDENCE_TABLE_V4.md`
7. `artifacts/v21_execution_20260925_04/HANDOFF_REPORT_V4.md`
8. `src/disastertrace/monitoring_v1/natural_track_v18.py`
9. `src/disastertrace/monitoring_v1/natural_selector_policy_v21.py`
10. `src/disastertrace/monitoring_v1/active_policy_v21.py`
11. `src/disastertrace/monitoring_v1/interventions_v18.py`
12. `scripts/run_v21_real_dev_source_bridge.py`
13. `scripts/run_v21_real_dev_deterministic_score.py`
14. `scripts/run_v21_cost_matched_adaptive_surface.py`

请独立回答：

- v22 计划逐项哪些已完成、部分完成、未完成或被阻塞；
- v21 implementation baseline 的哪些结果可以被 v22 计划继承，哪些只能标为 reported-only；
- public-schedule future source 是否会重复 RETRIEVE、违反预算或不终止；
- `available_at=None` 的 delay 是否被错误伪造成具体时间；
- 真实 development score 是否真的测量内容依赖式 follow-up；
- 24 个 target 的实际月份、22/2 标签比例和 72 checkpoint 的非独立性；
- synthetic GPU advantage 是否由 generator 直接构造；
- artifact HEAD、GitHub HEAD、worktree 和 reproduction 文档是否一致；
- 当前是否有资格启动 provider、holdout 或 novelty claim。

每条 finding 要给出：严重性、精确 `file:line`、`STATIC_CONFIRMED` 或 `PLAUSIBLE_UNVERIFIED`、复现方式、修复建议和停止条件。必须区分工程正确性、程序执行成功、方法有效性和研究 novelty/value。

请输出：

1. `v22_plan_status` 总表；
2. `implementation_status`；
3. `experiment_evidence_status`；
4. `novelty_value_judgment`；
5. 下一阶段 3–5 个按依赖排序的任务，每项包括目标、输入、成功标准、失败标准、资源和停止条件；
6. 当前不值得继续运行的实验；
7. 明确总判断，例如 `PARTIAL_PASS_ENGINEERING_INCONCLUSIVE_RESEARCH`。

审查完成后，请生成一个可交给 Codex 的 ZIP 执行包，文件名建议：

`CHATGPT_PRO_V22_FOLLOWUP_PACKAGE_<UTC>.zip`

ZIP 至少包含：

- `README.md`：阅读顺序、仓库/HEAD/计划版本边界；
- `REVIEW_REPORT.md`：完整独立结论；
- `PLAN_TRACEABILITY_MATRIX.md`：v22 任务到代码/证据/缺口的映射；
- `CLAIM_EVIDENCE_MATRIX.md`：每项 claim 的 VERIFIED/REPORTED_ONLY/INCONCLUSIVE/BLOCKED/CONTRADICTED；
- `TASKS.json`：每个任务的依赖、文件、命令、成功/失败标准、权限边界和停止条件；
- `CODEX_HANDOFF.md`：Codex 可直接执行的顺序，但不要默认授权 provider、holdout、quarantine 或新 GPU；
- `SOURCE_INVENTORY.json` 和 `EXECUTION_MANIFEST.json`；
- `validate_package.py` 与 `SHA256SUMS.txt`。

ZIP 只应包含去敏的代码审查、计划和合成统计，不要放 API key、原始天气/ASOS archive、holdout、quarantine、protected window 或未经授权的 provider response。把“计划包完整”与“benchmark 科学结论成立”严格分开。
