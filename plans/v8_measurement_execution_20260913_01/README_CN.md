# DisasterTrace v8 执行入口

本目录记录 2026-09-13 的测量修复、真实资料验证、大模型实验和后续计划。
这是开发研究记录；不要将已下载资料、演练回调或单日诊断计作独立确认。

建议按此顺序阅读：

1. [本轮执行报告](RUN_REPORT_CN.md)：代码、数据、模型结果、未完成部分。
2. [当前机器状态](EXECUTION_STATUS.json)：正在执行的任务及最新回执位置。
3. [整体后续计划](NEXT_PHASE_PLAN_CN.md)：保持 v8 方向，按证据推进核心确认与扩展。
4. [回归矩阵](REGRESSION_MATRIX_07.json)：485 项当前核心相关测试及 17 项启动/分析补充检查；GPU 冻结版本的 439 项记录单独保留。
5. [数据暴露登记](data_governance_01/EXPOSURE_LEDGER.json) 和
   [16 类灾害资格差量](data_governance_01/HAZARD_ADMISSION_DELTA.json)。
6. [逐来源与灾种对照](DATA_ADMISSION_MATRIX_CN.md)：97 个登记项的实际样本证据、用途和门槛。

## 已有可直接检查的证据

| 内容 | 入口 |
| --- | --- |
| 235B/8B 的 1,008 个正式诊断回答 | `reports/large_model_diagnostic_01/VALIDATION.json` |
| 证据条件错误、模型配对、时间表示、全部改动的 F | `reports/large_model_analysis_01/` |
| 576 个 E 回答的可见区间核算与原始错误例子 | [证据案例说明](EVIDENCE_CASEBOOK_CN.md) |
| 40 条完整程序轨迹的独立评分 | `reports/program_calendar_optimized_audit_01/` |
| 52 会话的 235B 自适应批次及运行状态 | `gpu/adaptive_large_02/` |
| 同信息单目标/三目标输出的 X09 协议与状态 | [X09 说明](X09_PROTOCOL_CN.md)、`gpu/joint_targets_live_01/` |
| 真实剩余资源与联合可达性 | `reports/residual_c2_01/SUMMARY.json` |
| 本地 source/selector/predictor 原请求恢复 | `reports/real_committed_source_01/` 等三个独立目录 |
| 同一时钟上的在途请求与合成准备状态恢复 | `reports/real_preparation_recovery_summary_01/VALIDATION.json` |
| 两年点温度 | `temperature_extension_01/admission_01/REPORT.json` |
| 730 天官方日极值及采样遗漏验证 | [温度日值说明](TEMPERATURE_DAILY_REFERENCE_CN.md) |
| 原生六小时极值至未来日/三日概率、独立核算及480个准入快照 | [日/多日温度闭环](TEMPERATURE_DAILY_FORECAST_CN.md) |
| 日历之间的实际重复目标与资料重叠 | `data_dependence_audit_01/VALIDATION.json` |
| MRMS 官方语义资格 | `h07_extension_01/semantic_contract_01/QUALIFICATION.json` |
| HEFS 免费共同信息对照 | `hydro_e_extension_01/FREE_COMMON_BASELINE_CONTROL.json` |
| 24 条固定 F 合成决策轨迹 | `preparation_controls_01/VALIDATION.json` |
| 真实固定 F 流上的 12 条条件 D 策略回放 | `reports/admitted_decisions_01/VALIDATION.json` |
| 四小时34次请求、25个不同原生产品及接收时间 | `shadow_decode_complete_02/REPORT.json` |
| 无模型、无网络调用的真实 journal 搬迁回放 | `portable_relocation_01/VALIDATION.json` |

目录存在不代表实验通过。看 `VALIDATION.json`、`COMPLETE.json` 和进程退出回执；
GPU 平台显示 SUCCEEDED 也要核对独立评分。局部或未开始会话保留全部注册机会。

## 小型独立回放

`portable_replay_01/` 是可复制的 12.9MB 原始 journal 子集，无需模型权重、API key 或 GPU。
在一个新的目录副本中运行：

```bash
python3 replay.py
```

需要 Python 3.11 或更新版本。脚本禁用 Python 网络连接，核验清单并重放 Follow 与共享
batch 两个方法，每方法 216 个真实开发机会，比较原独立评分。新路径下的实际回放已通过，
见 `portable_relocation_01/`。该子集不重建上游原始下载，也不包含全部模型 token 的复核。

## 复查时最值得关注

固定输入诊断中的235B 在完整证据下表现更好，在部分证据下却大量作出无依据确定判断；288 个 F 提议均
沿用基线。因此目前没有大模型预测收益结论。当前数据日历的严重正例和独立过程不足，
后续必须完成区域基线、过程分组和冻结确认。16 类是最终路线，不是已完成的评测集合。

本轮保留旧源码、捕获、失败与索引；没有 commit 或 push。大型模型权重和受限原始资料
不属于小型复查包的交付范围。

## 最终交付入口

- [完整自适应分数表](ADAPTIVE_SCORECARD_CN.md)
- [完成范围与审计路径](RUN_REPORT_CN.md)
- [发布等级](RELEASE_LEVEL_REPORT_CN.md)
- [最终工作包状态](WORK_PACKAGE_PROGRESS_02.json)
- [本地复查包](review_local_02/DisasterTrace_v8_code_and_progress.zip)
