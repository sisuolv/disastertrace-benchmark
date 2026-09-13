# v7 2026-09-13 执行入口

本目录落实 `../v7_integrated_20260913/` 的W0--W3有界执行，保留v7、C1/C2/C3及16灾种
路线。实际下载、CPU实现、720次真实GPU推理与可移植复现已完成；正式监测与跨独立
过程科学准入仍需后续门槛。最新精确状态以 `EXECUTION_STATUS.json` 为准。

## 建议阅读顺序

1. [FINAL_REPORT_CN.md](FINAL_REPORT_CN.md)：本轮到底做了什么、真实数字与限制。
2. [NEXT_PLAN_CN.md](NEXT_PLAN_CN.md)：基于结果修改后的整体路线与下一执行顺序。
3. [audit/two_year_summary/README_CN.md](audit/two_year_summary/README_CN.md)：两年强基线
   比较，2024与2026的本地化方向相反，全读不保证获益。
4. [gpu/combined_analysis_01/REPORT_CN.md](gpu/combined_analysis_01/REPORT_CN.md)：五种
   提示/任务条件的实际结果，保留示例复制与负结果。
5. [replay/EXECUTION_REPORT_CN.md](replay/EXECUTION_REPORT_CN.md)：独立CPU复现的范围、
   全量token核验与实际隔离限制。

机器入口为 `WORK_PACKAGE_STATUS.json`、`EXECUTION_STATUS.json`、`FINAL_VALIDATION.json`。
三者描述不同内容：工作完成范围、执行量、最后检查结果，不把“可解析”升级为“科学准入”。

## 按问题查证

| 问题 | 原始证据与说明 |
| --- | --- |
| 旧模型为什么几乎没有修订？ | [audit/REPORT_CN.md](audit/REPORT_CN.md) |
| 本地校准有没有真实新数据？ | [2023报告](audit/local_calibration_precheck/FULL_REPORT_CN.md)、[2025报告](audit/local_calibration_2025/FULL_REPORT_CN.md) |
| LAMP历史与概率能读取吗？ | [sources_lamp/README_CN.md](sources_lamp/README_CN.md) |
| EUPP/DWD、SEEPS到底解析了什么？ | [sources_numerical/REPORT_CN.md](sources_numerical/REPORT_CN.md) |
| 水文历史版本是否存在？为何未评分？ | [hydrology/REPORT_CN.md](hydrology/REPORT_CN.md) |
| 新接口有没有独立复查？ | [tests/final_integration_review/REVIEW_CN.md](tests/final_integration_review/REVIEW_CN.md) |
| 新推理能否无需GPU重放？ | [CPU复现ZIP](replay/DisasterTrace_V7_CPU_Replay_20260913.zip) |

## 复现命令

CPU复现ZIP解压后进入包目录，以Python3.10或以上运行：

```bash
python -I run_replay.py --output replay_result
```

输出目录必须是新目录。默认只需标准库；已安装Transformers/Tokenizers时可加
`--full-tokens`做完整重编码/解码。无需模型权重、网络、GPU或API Key；具体边界见
[包内说明](replay/package_01/README_CN.md)。

当前仓库源码回归从仓库根目录运行：

```bash
PYTHONPATH=disastertrace-starter/src disastertrace-starter/.venv/bin/python -m pytest \
  disastertrace-starter/tests/test_monitoring*.py \
  plans/v7_execution_20260913/tests/test_fixed*.py -q
```

本轮GPU结果保留各自冻结源码；当前源码经过边界修复后不等同于旧运行版本。以上测试
验证当前代码，CPU复现ZIP验证冻结调用，二者用途不同。不要重新启动任何已消费的
`gpu/*_01`运行目录或复用其提交登记。

## 交给导师或ChatGPT复查

先提供本报告和下一计划；需要逐项复算时提供CPU复现ZIP。重点检查：两年度对照是否
排除了事后选优、E正确是否与F收益分开、共同基线是否足够强、C1成本是否真实、C2
联合可达是否来自同一会话、下载样例是否被过度升级为正式灾种任务。

本轮未新增GitHub提交。现行已发布提交属于上一轮交付；本目录中的新代码和结果以
本地文件及哈希清单为准。历史输入/失败/索引保持检查见 `FINAL_VALIDATION.json`。
