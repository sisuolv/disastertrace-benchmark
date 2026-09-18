# 交给 Codex 的第一批执行指令

你正在处理 `sisuolv/disastertrace-benchmark` 的 `next-phase-v1`。本审查固定在 `1fd6821fef15b26898a57c74d4715714f33ea779`。先检查HEAD和worktree；若有更新或未提交修改，读取差异再扩展，不要reset/clean、覆盖索引或删除旧产物。

## 本批范围

只执行 `CODEX_BACKLOG.json` 的 **VT00–VT03**：

1. 记录已完成v10成果和仍有效授权，不重复创建FormalSession、COPY、四季资料、EMOS/ECC、两个capsule。
2. 将 `checks/run_checks.py` 中温度非法日界、重复日期和NaN阈值反例迁入真实包测试，修复全部相关公开入口；只读扫描历史影响。共享准入规则但保留独立算术参考，不用一份运算覆盖所有审计。
3. 对现有一个小capsule先profile；在同次评分内复用已验证引擎对象，避免九臂19次from_journal，同时完整保留协议、事务、来源、结果与比较检查。不要直接从SNAPSHOTS计算正式分数或按mtime跳过完整性检查。
4. 绑定新运行的H15科学合同，诊断端点压缩与EMOS/ECC修复；先统计真实影响，再决定小范围版本化特征改动，不要事后替换旧字段语义。

## 明确不做

不重跑旧模型launcher；不自动启动新API/GPU、批量下载或训练；不打开Bay2025-02-17至23确认载荷；不新增监测引擎；不扩大为所有16类模型矩阵；不以需要LLM获胜作为准入条件。后续VT04–VT11按依赖和有效授权单独推进。

## 已核查但不要重复误判

v10已有三类softmax和固定总先验校准，F-only、query-only选择器、固定预测日程及温度连续F-only已运行。温度DWD最终档案的729天不是严格历史补证。单次评分19次重放是性能目标，不是已证实改变历史分数的bug；不要先承诺加速倍数。

## 交付

`BASELINE_DELTA.json`、`CONTRACT_PARITY_REPORT.json`、`HISTORICAL_IMPACT_SCAN.json`、`REPLAY_PROFILE.json`、`SCORER_EQUIVALENCE.json`、`FEATURE_SEMANTICS_AUDIT.json`。

这些是建议的新产物名称，不声称仓库已有。报告必须列新增源码与测试、真实数据扫描范围、零/非零影响、未完成项和权限，不把局部合成测试当完整历史验证。

第一批结束后，用现有P0–P3计划更新状态，不再另起一份竞争性的总研究计划。核心科研下一步为：完整历史季节角色→强共同信息基线→完整日历同后端预算实验→真实前缀C2/F修复→独立过程确认。
