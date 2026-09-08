# P3 平衡开发集与本地 Qwen3-8B 实验

本阶段已完成：构建平衡版本、固定本地模型配置、采集 540 个真实回答、独立
审计/重建、验证纯 CPU 迁移复现，并准备后续难度版本。采集于 2026-09-07
19:40:46 UTC 完成；本轮初始启动已消耗，不能重新运行 collector。

关键结论：**流程完整，模型格式筛选未通过。** 共 200/540 个格式有效回答，
340 个无效回答；没有 length、缺失响应或额外重试。错误主要来自自由 JSON
输出结构，不能把总分直接解释成天气推理能力。

| 方法 | 格式有效 | 已知字段及引用正确 | checkpoint 全部正确 |
| --- | --- | --- | --- |
| snapshot | 80/180 | 168/564 | 75/180 |
| structured_state | 68/180 | 125/564 | 68/180 |
| answer_history | 52/180 | 60/564 | 50/180 |

先读以下文件：

- [详细结果与解释](artifacts/p3_local_balanced_v1/FINDINGS.md)
- [下一阶段建议](artifacts/p3_local_balanced_v1/NEXT_PHASE_PLAN.md)
- [给 ChatGPT Pro 的复查指南](artifacts/p3_local_balanced_v1/REVIEW_GUIDE.md)
- [无需 GPU/API 的复现说明](artifacts/p3_local_balanced_v1/REPRODUCE.md)
- [冻结研究规范](docs/P3_LOCAL_BALANCED_V1.md)
- [难度候选设计](artifacts/p3_local_balanced_v1/STRESS_DESIGN.md)
- [准备与测试记录](artifacts/p3_local_balanced_v1/SETUP_AND_VALIDATION.md)

新数据版本为 `3 来源 × 3 任务族 × 2 案例 × 2 分支 × 5 checkpoint × 3 方法`，
共 36 个 episode、108 条方法轨迹、540 个回答。仍然只有三个开发来源；七个
留出风暴未参与推理。数据/评分不需要新增逐题人工标注或 LLM judge。

真实模型为官方 Qwen3-8B 完整 BF16 权重，在 H100 MIG 40 GB 上用独立 vLLM
环境运行。共使用 1,822,573 tokens，采集子进程约 29 分 49 秒；没有付费 API
调用，GPU 货币成本未估算。推理进程已退出并释放 GPU。

原始记录在 `work/p3-qwen3-balanced-v1/`；实际报告在
`artifacts/p3_local_balanced_v1/model_report/`。`diagnostic_run/` 与
`diagnostic_report/` 是程序诊断。216 个难度候选只有离线验证，没有模型成绩。
旧 18 个共有 episode 的对照放在 `legacy_overlap/`，仅作描述性比较；不能把
旧 270 版本和新 540 版本总体成绩混合排行。

只读状态命令：

```bash
.venv/bin/python artifacts/p3_local_balanced_v1/status.py
```

当前代码入口为 `src/disastertrace/local_eval/`，执行使用其冻结副本。既有
`controlled` 生成/呈现/Gold/解析/评分代码保持不变。报告已在迁移目录及无
Torch/vLLM 的 CPU 环境重建，并禁止访问原运行数据、原权重与网络。

完整本地评审压缩包为
`artifacts/p3_local_balanced_v1/p3_local_balanced_v1_review.tar.gz`，清单与校验结果
分别为 `archive_manifest.json`、`archive_verification.json`。它包含本阶段代码、
规范、自动验证、540 个 raw 回答和结果，不包含 16.4 GB 权重或凭据，未发布至 GitHub。
