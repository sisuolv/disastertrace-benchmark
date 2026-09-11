# V6 数据选择交接包

这是 2026-09-11 数据可行性调查的收口目录。包括继承样例复核、真实匿名获取与解码、数据选择、16 类路线和下一阶段计划；正式新增模型评测尚未启动。

建议依次阅读：

1. [总体结论与执行路线](DATA_READINESS_REVIEW_CN.md)
2. [74 项来源逐项状态](SOURCE_FEASIBILITY.md) 和 [16 类覆盖/缺口](HAZARD_COVERAGE.md)
3. [已有 benchmark 的复用与研究定位](RELATED_BENCHMARK_COMPARISON.md)
4. [下一批获取清单](NEXT_ACQUISITION_MANIFEST.json)
5. [离线核验结果](VERIFY_REPORT.json)

机器可读入口：SOURCE_REGISTRY.json、source_access_report.jsonl、DATA_COUNTS.json、HAZARD_COVERAGE.json、BENCHMARK_RAW_LINKS.jsonl、SOURCE_DEPENDENCIES.json、ASSET_REUSE_INDEX.json、SPLIT_AND_DEPENDENCY_RISKS.json。

CAPTURE_INDEX.jsonl 记录每个探针，FILE_MANIFEST.jsonl 绑定本地字节；RUN_MANIFEST.json 绑定本次交接代码/报告。全量原始样例在本目录及相邻 `multihazard_source_validation_20260911`，继承原件另有仓库内路径。本目录不是独立包含全部数据的便携发布包。

离线复算，工作目录为仓库根：

```bash
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=/mnt/afs/260010168/.venvs/disastertrace-multihazard-libs-20260911 \
python3 plans/v6_0911_dataset_selection/audit_selection.py
python3 plans/v6_0911_dataset_selection/build_reports.py
python3 plans/v6_0911_dataset_selection/verify_selection.py
```

这三个命令不联网、不调用模型；会重算本轮派生审计和报告。已有 DOWNLOADED_AUDIT.json 绑定此前较大批次的解码结果，不能把较早 SAMPLE_CHECKS_02/03 的中间状态当成最新结果。VERIFY_REPORT 检查当前交接范围，不代表整个 V6 路线已完成。

执行记录说明：初始 SCOPE.json 的 registry digest 写错，已在 analysis/SCOPE_METADATA_CORRECTION_01.json 对照实际输入/原件纠正，配额未改。新审计首次遇到 Parquet 示例缺失值 NaN 的 JSON 序列化错误，已改为 null，原脚本和失败日志保留；其后通过。网络的超时、404、未完整响应和成功重试均保留。
