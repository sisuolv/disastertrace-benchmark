# 同案例的证据判断诊断

两个模型接收字节一致的 96 个案例和条件定义；每种真实 E 状态各 32 例。
这是固定披露的诊断，不是未来 F 收益或主动调度实验。

| 模型 | 条件 | 正确 / 96 | supported | refuted | undetermined | token / 例 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| qwen3_8b | joint_F_E | 57 | 13/32 | 20/32 | 24/32 | 1964.0 |
| qwen3_8b | E_only | 65 | 3/32 | 32/32 | 30/32 | 784.3 |
| qwen3_8b | E_examples | 75 | 30/32 | 32/32 | 13/32 | 868.9 |
| qwen3_8b | E_fact_table | 51 | 8/32 | 32/32 | 11/32 | 430.1 |
| qwen3vl_32b | joint_F_E | 63 | 29/32 | 3/32 | 31/32 | 1979.5 |
| qwen3vl_32b | E_only | 81 | 20/32 | 30/32 | 31/32 | 780.1 |
| qwen3vl_32b | E_examples | 72 | 23/32 | 32/32 | 17/32 | 865.0 |
| qwen3vl_32b | E_fact_table | 88 | 32/32 | 32/32 | 24/32 | 425.8 |

## 成对变化

下表以右侧条件为参照，完整保留两边同时正确和同时错误的情况。

| 候选 VS 参照 | 仅候选正确 | 仅参照正确 | 净正确变化 |
| --- | ---: | ---: | ---: |
| qwen3_8b/joint_F_E VS qwen3_8b/E_only | 12 | 20 | -8 |
| qwen3_8b/E_examples VS qwen3_8b/E_only | 27 | 17 | +10 |
| qwen3_8b/E_fact_table VS qwen3_8b/E_only | 8 | 22 | -14 |
| qwen3vl_32b/joint_F_E VS qwen3vl_32b/E_only | 12 | 30 | -18 |
| qwen3vl_32b/E_examples VS qwen3vl_32b/E_only | 6 | 15 | -9 |
| qwen3vl_32b/E_fact_table VS qwen3vl_32b/E_only | 14 | 7 | +7 |
| qwen3vl_32b/joint_F_E VS qwen3_8b/joint_F_E | 25 | 19 | +6 |
| qwen3vl_32b/E_only VS qwen3_8b/E_only | 19 | 3 | +16 |
| qwen3vl_32b/E_examples VS qwen3_8b/E_examples | 8 | 11 | -3 |
| qwen3vl_32b/E_fact_table VS qwen3_8b/E_fact_table | 37 | 0 | +37 |

## 解释边界

规则示例与标准事实表的效应随模型而变；因此不能假设提示增强或表格化总会改善 C2。
事实表来自同一组已读产品的确定性解释，没有额外隐藏标签，但属于明确辅助条件。
联合 F/E 条件同时改变任务负荷、输出合同和输入长度，准确率差不能归因给单一机制。
Qwen3-VL-32B 在这里只接收文本；本结果不支持图像收益。
记录的 token 与运行时间可复核，但实际耗时包含框架开销，且没有重复种子或独立过程确认。
未来损失、预算调度收益与两种 wrapper 效果由独立的完整日历实验检验。
