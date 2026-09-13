# 填值示例敏感性诊断

本轮是真实新增推理。固定快照、共同基线和当前状态；单独比较资料利用，不能当端到端调度收益。

288 次调用中 288 次输出合同有效，E 判断正确 99/288。

| 地区/证据 | 机会 | E正确 | 基线Brier | 统计映射Brier | Qwen Brier | Qwen相对基线增益 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| bay/alternate_filled_example/all_registered | 24 | 20 | 0.078544 | 0.072870 | 0.456667 | -0.378123 |
| bay/alternate_filled_example/common_only | 24 | 0 | 0.078544 | 0.078544 | 0.456667 | -0.378123 |
| bay/alternate_filled_example/fixed_one | 24 | 0 | 0.078544 | 0.072192 | 0.456667 | -0.378123 |
| bay/no_filled_example/all_registered | 24 | 4 | 0.078544 | 0.072870 | 0.078544 | +0.000000 |
| bay/no_filled_example/common_only | 24 | 24 | 0.078544 | 0.078544 | 0.078544 | +0.000000 |
| bay/no_filled_example/fixed_one | 24 | 3 | 0.078544 | 0.072192 | 0.078544 | +0.000000 |
| front/alternate_filled_example/all_registered | 24 | 22 | 0.000781 | 0.001859 | 0.490000 | -0.489219 |
| front/alternate_filled_example/common_only | 24 | 0 | 0.000781 | 0.000781 | 0.490000 | -0.489219 |
| front/alternate_filled_example/fixed_one | 24 | 0 | 0.000781 | 0.000793 | 0.490000 | -0.489219 |
| front/no_filled_example/all_registered | 24 | 2 | 0.000781 | 0.001859 | 0.000781 | +0.000000 |
| front/no_filled_example/common_only | 24 | 24 | 0.000781 | 0.000781 | 0.000781 | +0.000000 |
| front/no_filled_example/fixed_one | 24 | 0 | 0.000781 | 0.000793 | 0.000781 | +0.000000 |

只有48个开发机会、2个正例；三个证据条件和两类预测器不增加独立天气过程数量。
不使用这张表选择灾害、确认期或宣布LLM普遍提高预报。具体逐条输出、失败、费用与资料响应见REPORT.json和ROWS.json。
