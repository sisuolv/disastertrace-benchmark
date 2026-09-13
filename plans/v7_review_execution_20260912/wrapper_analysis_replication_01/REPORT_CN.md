# 两种修订协议的独立执行与固定输出复算

正值表示 persistent_override 的 Brier 更低。全部使用相同登记机会和结果掩膜。

| 方法 | 分别实际运行的 persistent − bound 收益 |
| --- | ---: |
| model/qwen3_8b/round_robin | +0.000000000 |
| model/qwen3_8b/risk | +0.000000000 |
| model/qwen3_8b/batch_complete | +0.000000000 |
| model/qwen3_8b/llm | +0.000172175 |
| program/FOLLOW | +0.000000000 |
| program/round_robin | -0.000000632 |
| program/risk | -0.000000628 |
| program/coverage | -0.000000632 |
| program/batch_complete | -0.000000596 |
| program/all_read | -0.000000652 |
| program/neighbor_persistence | -0.000003457 |
| program/capacity_revise_defer | +0.000000000 |

## 固定候选与完成时间，仅更换 wrapper

| 候选轨迹的原始协议 | persistent 相对 bound 收益 | 改善 / 恶化 / 不变机会 |
| --- | ---: | --- |
| model/qwen3_8b/round_robin/base_bound_override | +0.000000000 | 0 / 0 / 5796 |
| model/qwen3_8b/risk/base_bound_override | +0.000000000 | 0 / 0 / 5796 |
| model/qwen3_8b/batch_complete/base_bound_override | +0.000000000 | 0 / 0 / 5796 |
| model/qwen3_8b/llm/base_bound_override | -0.000344351 | 0 / 2 / 5794 |
| model/qwen3_8b/round_robin/persistent_override | +0.000000000 | 0 / 0 / 5796 |
| model/qwen3_8b/risk/persistent_override | +0.000000000 | 0 / 0 / 5796 |
| model/qwen3_8b/batch_complete/persistent_override | +0.000000000 | 0 / 0 / 5796 |
| model/qwen3_8b/llm/persistent_override | +0.000000000 | 0 / 0 / 5796 |

分别运行会改变提示中的当前状态，也保留推理和实际耗时差异；不能把全部差异归因于回退规则。
固定输出复算使用同一组行动、概率和时间，仅改变协议，不是模型在另一协议下重新作出的决策。
两项结果不能相加或换算为因果贡献百分比。已接受、失效、主动撤销、迟到和回退次数见 REPORT.json。
共同基线仍为 R 轨的 TAF 研究映射；相对它的收益不等于超越官方概率预报。
