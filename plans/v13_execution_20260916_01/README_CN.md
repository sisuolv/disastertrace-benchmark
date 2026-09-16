# v13 首批执行入口：工程修复与历史核验

执行日期：2026-09-16。范围：用户批准的 A00—A06。

本批将 v13 计划中的合同修复落入当前代码，核验已有真实实验的影响，再停下供复核。没有启动新的天气下载、训练、模型 API、正式 C2 分支或确认集实验。资源使用遵循用户最新偏好：调用 CCI/ACP 的 16 CPU / 64 GiB，8 个测试进程并行；没有 GPU 计算需求。

- [一页结果](RESULT_SUMMARY_CN.md)：已完成什么、实际发现、下一步。
- [代码与研究影响](IMPACT_SUMMARY_CN.md)：修复的边界和科学解释。
- [后续执行次序](NEXT_STEPS_CN.md)：B00/C00/M00 的具体入口与限制。
- `FINAL_RESULT.json`、`STOP_RECEIPT_02.json`：补充验收后的最终收尾状态。
- `TEST_RECEIPTS_02.json`、`regression_02/RESULT.json`：最终合并回归覆盖 880 项唯一测试；首轮及失败保留。
- `FINAL_PRESERVATION_02.json`：4,506 个历史保护对象、当前源码/测试与 Git index。

## 主要代码

| 模块 | 本批改动 |
|---|---|
| `monitoring_v1/analysis_integrity.py` | 按注册机会/分支/调用核查完整性；先查重复，再建索引；多个调用不互相覆盖 |
| `monitoring_v1/comparison_fingerprint.py` | 根据实际消费者、bank、日程、权限与资源识别差异，避免仅按方法名字分类 |
| `monitoring_v1/api_transport_v2.py`、`production.py` | 最后派发许可、原字节捕获、独立管理回执、追加式恢复、实际消费者与结算 |
| `monitoring_v1/selector_contract_v2.py`、`policies.py`、`session_checkpoint.py` | 单字段 query_order；统一 prompt/schema/parser；固定程序预测与原调用续接 |
| `monitoring_v1/residual_query_plan.py` | 独立 v2 none/first_new/second_new/all_new；按权限/缓存/请求状态选新增 GET |

新 selector/residual/API 合同均显式启用。既有默认 v1 行为和冻结 v12 脚本保留。本目录的 `before/` 与 `regression_02/source/` 分别保存编辑前当前源码、最终测试源码。

## 可复查产物

`C2_INTEGRITY.json`、`METHOD_FINGERPRINTS.json`、`HISTORICAL_REPORT_IMPACT.json` 核查 6 父×4 分支及 108 方法会话。`API_HISTORICAL_IMPACT.json` 对账 288 正式与 2 兼容请求。`ACTION_SPACE_CENSUS.json` 仅使用原请求中的公开视图。

`CLOCK_INFORMATION_AUDIT_V2.json` 是 24 个固定 ID/hash 抽样目标的时钟分解。V2 只把首版误导性的 `future_weather` 字段改名为 `forecast_cutoff`，全部数值不变；物理目标时间始终位于 `target_contract`。首版保留并绑定其哈希。

`M00_PROPOSAL.json` 与 `m00_unsent/` 有 12 份未发送请求；`B00_ROSTER_PROPOSAL.json` 有 168 个日历单元；`C00_ROSTER_PROPOSAL.json` 有 12 个待材料化父状态候选。它们不是已执行实验或可直接复用的旧请求 claim。

## 复现与消费边界

测试的精确 argv、退出码、JUnit 与代码哈希见 `regression_02/REGISTRATION.json`、`regression_02/logs/*.result.json`。两次 CCI 作业 `pt-toomynpf`、`pt-nzzthw7l` 顺序运行，均 SUCCEEDED、退出码 0；不要重新运行其 claim。最终运行覆盖原 793 项历史范围与 87 项 v13 测试。

首次收尾后发现 selector v2 尚缺完整尾部 disposition 与严格前缀执行；`CLOSEOUT_AMENDMENT_01.json` 记录重开 A03/A06 的原因。新增四项测试先失败，再完成修复和新的冻结回归。原 `RESULT_SUMMARY.json` / `STOP_RECEIPT.json` 只代表首轮验收，不是最终代码状态。补充版同时验证原 pending source 的续接，保持零新科学实验。

`baseline.py`、`audit_history.py`、`diagnose_existing.py`、`prepare_handoff.py`、`finalize.py` 是本批入口；默认输出采用不可覆盖写入，重跑必须另建输出目录和身份，不能覆盖回执。首轮 `HISTORY_01.log` 保留文件字节哈希与 canonical JSON 哈希被错误混用的诊断失败；`HISTORY_02.log` 是修正后的实际成功运行。

本批没有 GitHub 推送。API 凭据保持在仓库外，不随本目录保存或发布。
