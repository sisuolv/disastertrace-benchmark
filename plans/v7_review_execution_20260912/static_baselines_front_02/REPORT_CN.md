# 稀有事件的简单强对照

本对照在看到 2024 年首轮结果后补充，属于明确的事后诊断；不作为预注册确认实验。
两条规则固定为全零概率、此前月份已冻结映射中的总体频率，不使用评测期结果拟合参数。
它们对每个登记机会直接提供常数预测，不是两种修订 wrapper 的执行轨迹。

| 对照 | 固定概率 | Brier | 可结算机会 | 模型调用 / 查询 |
| --- | ---: | ---: | ---: | ---: |
| zero_event | 0.00000000 | 0.00720906 | 5826 | 0 / 0 |
| frozen_prior_month_frequency | 0.04282655 | 0.00842570 | 5826 | 0 / 0 |

## 已测模型相对简单对照的差异

正值表示模型 Brier 更低；所有方法保留同一结果掩膜和全部目标。

| 模型方法 | 相对全零预测增益 | 相对历史频率增益 |
| --- | ---: | ---: |
| model/qwen3_8b/round_robin/base_bound_override | -0.00075410 | +0.00046253 |
| model/qwen3_8b/risk/base_bound_override | -0.00075410 | +0.00046253 |
| model/qwen3_8b/batch_complete/base_bound_override | -0.00075421 | +0.00046242 |
| model/qwen3_8b/llm/base_bound_override | -0.00058303 | +0.00063361 |
| model/qwen3_8b/round_robin/persistent_override | -0.00058303 | +0.00063361 |
| model/qwen3_8b/risk/persistent_override | -0.00058303 | +0.00063361 |
| model/qwen3_8b/batch_complete/persistent_override | -0.00058303 | +0.00063361 |
| model/qwen3_8b/llm/persistent_override | -0.00058303 | +0.00063361 |

全零预测即使取得较小 Brier，也没有识别正例的能力。应联合报告事件率、正例目标数、
概率质量和已冻结的 E 诊断，不因大多数样本无事件而声称预警能力已得到验证。
历史频率来自湾区校准月；迁移到 Front Range 时只是明确的跨区常数基线。
按目标共享未知结果的缺测界与所有程序方法的比较见 REPORT.json。
