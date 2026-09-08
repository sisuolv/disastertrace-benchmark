# T6 完整实验交付

本轮已经完成：**270 次尝试 / 270 个响应，独立审计通过，共同输出上限 8192**。本轮 usage 费用估计 USD 0.628557504；保守结算账 USD 0.97628256；未结算和未知预留均为 0。费用估计不是账单。

## 阅读入口

- [主要发现和下一步](FINDINGS.md)：格式门槛、事实/引用差异及 P2 接入计划。
- [中文完整报告](runtime/REPORT_ZH.md)：九个条件/方法单元、逐风暴分母、预定配对差值和费用。
- [最终机器报告](runtime/report/report.json)、[独立进程审计](runtime/final_audit.json)、[自动错误清单](runtime/selected_cap_errors.json)。
- [P2 移交参数](P2_HANDOFF.json)：8192 作为初始设置，P2 仍需专用采集/审计接入，尚未授权模型调用。
- [原始启动、协议和运行说明](../../README_T6_CALIBRATION_V1.md)。

## 完整归档

[t6_results_v1.tar.gz](t6_results_v1.tar.gz) 包含冻结执行源码、授权和价格资料、启动前诊断记录、真实请求 journal、捕获响应、实际输入与独立评分投影、V1/V2 评分、最终审计和中文报告。程序诊断位于 `diagnostic/`，真实结果位于 `runtime/` 与 `work/t6-deepseek-calibration-v1/`，分别标明来源。

文件校验清单：[archive_manifest.json](archive_manifest.json)。实际归档与 1,616 个历史保护文件的核验结果：[verification.json](verification.json)。归档不含模型密钥，也不会追加模型调用。

在完整项目环境中，可执行只读校验：

```bash
.venv/bin/python artifacts/t6_deepseek_calibration_v1/package_results.py --verify-only
```

归档不自动解压、不重写原始路径，也不授权重跑实验。执行身份绑定冻结源码及原环境；重新运行数据处理需要匹配的环境。旧 P1 实验和 attempt 79 未知收费记录保持独立。

启动与验证记录：[preflight.json](preflight.json)、[最终执行记录](runtime/finalization.json)。后台进程已结束，不能重复 initial launch；本轮已用完授权的 270 次请求范围。
