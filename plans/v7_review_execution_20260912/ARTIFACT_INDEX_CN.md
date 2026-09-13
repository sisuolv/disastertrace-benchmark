# 本轮文件阅读索引

先读 FINAL_REPORT_CN.md，再按本表定位。较早目录保留为历史输入、失败或较窄实验，不能只按文件数量推断完成范围。
表中路径相对本目录；大型原始数据和输出通过发布目录的 EVIDENCE_INDEX.json 定位并恢复。
本表只说明推荐入口和文件是否存在，不代替科学准入或完整复跑。

## Contracts and implementation

| 推荐文件 | 当前状态 |
| --- | --- |
| `PLAN_AMENDMENT_CN.md` | available |
| `OVERALL_EXECUTION_ROADMAP_CN.md` | available |
| `REVIEW_RESOLUTION.json` | available |
| `HAZARD_REVIEW_OVERLAY.json` | available |
| `NOVELTY_RECHECK_CN.md` | available |
| `review_replay_01/CORE_AND_ANALYSIS_VALIDATION_09.xml` | available |

## Native data and prior calibration

| 推荐文件 | 当前状态 |
| --- | --- |
| `extension_bay_area_01/REGIONAL_JOIN_AUDIT.json` | available |
| `extension_front_range_03/REGIONAL_JOIN_AUDIT.json` | available |
| `replication_2026_01/REGIONAL_JOIN_AUDIT.json` | available |
| `calibration_bank_01/CHECK_REPORT.json` | available |
| `calibration_bank_2025_01/CHECK_REPORT.json` | available |
| `independent_metar_validation_02/VERIFIED.json` | available |
| `independent_metar_validation_03/VERIFIED.json` | available |
| `independent_taf_validation_02/REPORT.json` | available |

## All-opportunity F and protocol results

| 推荐文件 | 当前状态 |
| --- | --- |
| `calendar_analysis_bay_02/REPORT.json` | available |
| `calendar_analysis_front_02/REPORT.json` | available |
| `calendar_analysis_replication_01/REPORT.json` | available |
| `wrapper_analysis_bay_01/REPORT.json` | available |
| `wrapper_analysis_front_01/REPORT.json` | available |
| `wrapper_analysis_replication_01/REPORT.json` | available |
| `static_baselines_bay_03/REPORT.json` | available |
| `static_baselines_front_02/REPORT.json` | available |
| `static_baselines_replication_01/REPORT.json` | available |
| `ranking_analysis_bay_01/REPORT.json` | available |
| `ranking_analysis_front_01/REPORT.json` | available |
| `ranking_analysis_replication_01/REPORT.json` | available |
| `figures_execution_01/PLOT_VALUES.json` | available |

## E coverage, model understanding and costs

| 推荐文件 | 当前状态 |
| --- | --- |
| `joint_E_analysis_bay_01/REPORT.json` | available |
| `joint_E_analysis_front_01/REPORT.json` | available |
| `joint_E_analysis_replication_01/REPORT.json` | available |
| `e_diagnostic_analysis_01/REPORT.json` | available |
| `e_order_analysis_01/REPORT.json` | available |
| `E_CASE_WALKTHROUGH_CN.md` | available |
| `WRAPPER_CASE_WALKTHROUGH_CN.md` | available |
| `report_event_profile_02/REPORT.json` | available |
| `resource_analysis_02/REPORT.json` | available |

## Native multimodal and source-version checks

| 推荐文件 | 当前状态 |
| --- | --- |
| `gpu_mm_01_validation_01/VERIFIED.json` | available |
| `bulk_service_validation_01/VERIFIED.json` | available |
| `live_observer_validation_01/VERIFIED.json` | available |
| `hydro_revision_validation_01/REPORT.json` | available |
| `HYDRO_PAYLOAD_VERSION_CHECK.json` | available |
| `hydro_metadata_validation_01/REPORT.json` | available |
| `hydro_stage_validation_01/REPORT.json` | available |

## Portable replay and actual execution

| 推荐文件 | 当前状态 |
| --- | --- |
| `packaged_replay_01_receipts/COMPLETE.json` | available |
| `packaged_replay_02_receipts/COMPLETE.json` | available |
| `packaged_replay_replication_01_receipts/COMPLETE.json` | available |
| `EXECUTION_STATUS.json` | available |
| `gpu_queue_01/STATUS.json` | available |
| `delivery_queue_01/STATUS.json` | available |
| `e_order_queue_01/STATUS.json` | available |
| `FINAL_ACCOUNT_CHECK.json` | available |
| `gpu_occupancy_validation_02/VERIFIED.json` | available |

## 版本解释

- Front Range 当前输入使用 extension_front_range_03；更早尝试保留，不替代该数据审计。
- 完整 Bay/Front 两协议比较使用 calendar_analysis_*_02；早期仅 base 协议或程序分析单列。
- Bay 常数强对照使用 static_baselines_bay_03，Front 使用 static_baselines_front_02；旧失败日志保留。
- charged selector 的首个独立核验使用 gpu_active_pilot_01_validation_02，后续日历使用各自冻结 v2 批次。
- 109 项实现/分析测试、原审阅包示例、排序/配对/发布补查分别记录；不能把重复运行加成独立测试或模型样本。
- e_order 队列只处理已有 96 个 E 案例的顺序复核；H08 检查只处理来源、原生水位链和阈值合同预检。
- 两次隔离发布包回放各重建 5,656 条已记录输出；回放没有新增模型推理。
