# 稀有事件的概率排序与固定阈值诊断

这是在首轮 Brier 结果后补充的描述性检查，全部方法用同一可结算机会；不选择获胜阈值。
AP 的常数基准等于事件率。较好的排序和较差的 Brier 可以同时发生；排序不替代校准或损失。

| 方法 | AP | ROC AUC | 正例机会 |
| --- | ---: | ---: | ---: |
| model/qwen3_8b/round_robin/base_bound_override | 0.03941003 | 0.73717521 | 42 |
| model/qwen3_8b/risk/base_bound_override | 0.03941003 | 0.73717521 | 42 |
| model/qwen3_8b/batch_complete/base_bound_override | 0.03940942 | 0.73714434 | 42 |
| model/qwen3_8b/llm/base_bound_override | 0.03952583 | 0.73728841 | 42 |
| model/qwen3_8b/round_robin/persistent_override | 0.03952583 | 0.73728841 | 42 |
| model/qwen3_8b/risk/persistent_override | 0.03952583 | 0.73728841 | 42 |
| model/qwen3_8b/batch_complete/persistent_override | 0.03952583 | 0.73728841 | 42 |
| model/qwen3_8b/llm/persistent_override | 0.03952583 | 0.73728841 | 42 |
| shared_research_TAF_base | 0.03952583 | 0.73728841 | 42 |
| zero_event | 0.00720906 | 0.5 | 42 |

0.01/0.05/0.10/0.20/0.50 五个固定概率阈值的 TP/FP/FN/TN、precision、recall、FPR 均在 REPORT.json。
没有正例时 AP/recall 不可用；没有两类时 ROC 不可用。无报警时 precision 不伪造为 1。
同分数统一成组，避免由输入顺序制造 PR 优势。重复提前量仍共享同一结果，未给独立样本置信区间。
