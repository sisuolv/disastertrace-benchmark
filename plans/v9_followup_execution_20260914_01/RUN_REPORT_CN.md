# 本批执行结果

状态：已完成本批注册范围。

616 项相关测试通过；密钥保存在 Git 仓库外；未打开独立确认周。首次 E 采集的 AFS 锁故障完整保留，正式 E 结果使用修复后的独立批次。

| 批次 | 已登记尝试 | 已结算响应 | 未知/待定 | 峰时费用上界USD |
| --- | ---: | ---: | ---: | ---: |
| api_compatibility_01 | 2 | 2 | 0 | 0.000085 |
| api_evidence_01 | 938 | 876 | 62 | 1.184498 |
| api_evidence_02 | 1008 | 1008 | 0 | 1.350812 |
| api_pilot_01 | 2304 | 2304 | 0 | 9.022021 |
| api_rare_pilot_01 | 384 | 384 | 0 | 1.510706 |

温度程序链：64 条连续轨迹、876 个机会、280 个唯一目标，来源是已审计 EUPP/DWD；没有温度模型调用。

E 诊断：42 个底层问题，多个视图和模型共享底层问题。

| 模型/输入/输出 | E正确 | 全字段正确 |
| --- | ---: | ---: |
| deepseek-flash__focused_slots__direct | 109/126 | 109/126 |
| deepseek-flash__focused_slots__slotwise | 126/126 | 126/126 |
| deepseek-flash__full_bundle__direct | 114/126 | 114/126 |
| deepseek-flash__full_bundle__slotwise | 125/126 | 125/126 |
| deepseek-v4-pro__focused_slots__direct | 84/126 | 84/126 |
| deepseek-v4-pro__focused_slots__slotwise | 101/126 | 101/126 |
| deepseek-v4-pro__full_bundle__direct | 85/126 | 85/126 |
| deepseek-v4-pro__full_bundle__slotwise | 106/126 | 106/126 |

## 普通日历 F 试点

first and final weekday of registered Jan6-12 calendar; all sites and hourly cutoffs

| 案例 | 方法 | 已结算/缺失 | 正例 | Brier | 相对FOLLOW变化 |
| --- | --- | --- | ---: | ---: | ---: |
| chicago__2025-01-06__1000 | batch_program | 72/0 | 0 | 0.009576 | 0.001720 |
| chicago__2025-01-06__1000 | deepseek-flash__batch_predictor | 72/0 | 0 | 0.007856 | 0.000000 |
| chicago__2025-01-06__1000 | deepseek-flash__llm_selector_program | 72/0 | 0 | 0.009490 | 0.001634 |
| chicago__2025-01-06__1000 | deepseek-v4-pro__batch_predictor | 72/0 | 0 | 0.007856 | -0.000000 |
| chicago__2025-01-06__1000 | deepseek-v4-pro__llm_selector_program | 72/0 | 0 | 0.009653 | 0.001797 |
| chicago__2025-01-06__1000 | follow | 72/0 | 0 | 0.007856 | 0.000000 |
| chicago__2025-01-06__5000 | batch_program | 72/0 | 8 | 0.155884 | 0.003473 |
| chicago__2025-01-06__5000 | deepseek-flash__batch_predictor | 72/0 | 8 | 0.152411 | 0.000000 |
| chicago__2025-01-06__5000 | deepseek-flash__llm_selector_program | 72/0 | 8 | 0.158227 | 0.005816 |
| chicago__2025-01-06__5000 | deepseek-v4-pro__batch_predictor | 72/0 | 8 | 0.152411 | 0.000000 |
| chicago__2025-01-06__5000 | deepseek-v4-pro__llm_selector_program | 72/0 | 8 | 0.152826 | 0.000414 |
| chicago__2025-01-06__5000 | follow | 72/0 | 8 | 0.152411 | 0.000000 |
| chicago__2025-01-10__1000 | batch_program | 72/0 | 0 | 0.007189 | 0.001452 |
| chicago__2025-01-10__1000 | deepseek-flash__batch_predictor | 72/0 | 0 | 0.005737 | 0.000000 |
| chicago__2025-01-10__1000 | deepseek-flash__llm_selector_program | 72/0 | 0 | 0.007619 | 0.001882 |
| chicago__2025-01-10__1000 | deepseek-v4-pro__batch_predictor | 72/0 | 0 | 0.005737 | -0.000000 |
| chicago__2025-01-10__1000 | deepseek-v4-pro__llm_selector_program | 72/0 | 0 | 0.007444 | 0.001707 |
| chicago__2025-01-10__1000 | follow | 72/0 | 0 | 0.005737 | 0.000000 |
| chicago__2025-01-10__5000 | batch_program | 72/0 | 27 | 0.125701 | 0.008694 |
| chicago__2025-01-10__5000 | deepseek-flash__batch_predictor | 72/0 | 27 | 0.117006 | 0.000000 |
| chicago__2025-01-10__5000 | deepseek-flash__llm_selector_program | 72/0 | 27 | 0.120668 | 0.003661 |
| chicago__2025-01-10__5000 | deepseek-v4-pro__batch_predictor | 72/0 | 27 | 0.117006 | 0.000000 |
| chicago__2025-01-10__5000 | deepseek-v4-pro__llm_selector_program | 72/0 | 27 | 0.113569 | -0.003437 |
| chicago__2025-01-10__5000 | follow | 72/0 | 27 | 0.117006 | 0.000000 |
| denver__2025-01-06__1000 | batch_program | 71/1 | 0 | 0.001256 | 0.001067 |
| denver__2025-01-06__1000 | deepseek-flash__batch_predictor | 71/1 | 0 | 0.000189 | 0.000000 |
| denver__2025-01-06__1000 | deepseek-flash__llm_selector_program | 71/1 | 0 | 0.000987 | 0.000798 |
| denver__2025-01-06__1000 | deepseek-v4-pro__batch_predictor | 71/1 | 0 | 0.000189 | 0.000000 |
| denver__2025-01-06__1000 | deepseek-v4-pro__llm_selector_program | 71/1 | 0 | 0.000409 | 0.000220 |
| denver__2025-01-06__1000 | follow | 71/1 | 0 | 0.000189 | 0.000000 |
| denver__2025-01-06__5000 | batch_program | 71/1 | 0 | 0.001209 | 0.000913 |
| denver__2025-01-06__5000 | deepseek-flash__batch_predictor | 71/1 | 0 | 0.000297 | 0.000000 |
| denver__2025-01-06__5000 | deepseek-flash__llm_selector_program | 71/1 | 0 | 0.000731 | 0.000435 |
| denver__2025-01-06__5000 | deepseek-v4-pro__batch_predictor | 71/1 | 0 | 0.000297 | 0.000000 |
| denver__2025-01-06__5000 | deepseek-v4-pro__llm_selector_program | 71/1 | 0 | 0.000804 | 0.000507 |
| denver__2025-01-06__5000 | follow | 71/1 | 0 | 0.000297 | 0.000000 |
| denver__2025-01-10__1000 | batch_program | 72/0 | 0 | 0.001247 | 0.001060 |
| denver__2025-01-10__1000 | deepseek-flash__batch_predictor | 72/0 | 0 | 0.000187 | 0.000000 |
| denver__2025-01-10__1000 | deepseek-flash__llm_selector_program | 72/0 | 0 | 0.000187 | 0.000000 |
| denver__2025-01-10__1000 | deepseek-v4-pro__batch_predictor | 72/0 | 0 | 0.000187 | 0.000000 |
| denver__2025-01-10__1000 | deepseek-v4-pro__llm_selector_program | 72/0 | 0 | 0.000646 | 0.000459 |
| denver__2025-01-10__1000 | follow | 72/0 | 0 | 0.000187 | 0.000000 |
| denver__2025-01-10__5000 | batch_program | 72/0 | 0 | 0.001196 | 0.000902 |
| denver__2025-01-10__5000 | deepseek-flash__batch_predictor | 72/0 | 0 | 0.000293 | 0.000000 |
| denver__2025-01-10__5000 | deepseek-flash__llm_selector_program | 72/0 | 0 | 0.000765 | 0.000471 |
| denver__2025-01-10__5000 | deepseek-v4-pro__batch_predictor | 72/0 | 0 | 0.000293 | 0.000000 |
| denver__2025-01-10__5000 | deepseek-v4-pro__llm_selector_program | 72/0 | 0 | 0.000612 | 0.000318 |
| denver__2025-01-10__5000 | follow | 72/0 | 0 | 0.000293 | 0.000000 |
| new_york__2025-01-06__1000 | batch_program | 72/0 | 0 | 0.006787 | -0.000008 |
| new_york__2025-01-06__1000 | deepseek-flash__batch_predictor | 72/0 | 0 | 0.006794 | 0.000000 |
| new_york__2025-01-06__1000 | deepseek-flash__llm_selector_program | 72/0 | 0 | 0.006691 | -0.000103 |
| new_york__2025-01-06__1000 | deepseek-v4-pro__batch_predictor | 72/0 | 0 | 0.006794 | 0.000000 |
| new_york__2025-01-06__1000 | deepseek-v4-pro__llm_selector_program | 72/0 | 0 | 0.006933 | 0.000139 |
| new_york__2025-01-06__1000 | follow | 72/0 | 0 | 0.006794 | 0.000000 |
| new_york__2025-01-06__5000 | batch_program | 72/0 | 12 | 0.123321 | 0.010053 |
| new_york__2025-01-06__5000 | deepseek-flash__batch_predictor | 72/0 | 12 | 0.113268 | 0.000000 |
| new_york__2025-01-06__5000 | deepseek-flash__llm_selector_program | 72/0 | 12 | 0.122423 | 0.009155 |
| new_york__2025-01-06__5000 | deepseek-v4-pro__batch_predictor | 72/0 | 12 | 0.113268 | 0.000000 |
| new_york__2025-01-06__5000 | deepseek-v4-pro__llm_selector_program | 72/0 | 12 | 0.130754 | 0.017486 |
| new_york__2025-01-06__5000 | follow | 72/0 | 12 | 0.113268 | 0.000000 |
| new_york__2025-01-10__1000 | batch_program | 72/0 | 0 | 0.000660 | 0.000306 |
| new_york__2025-01-10__1000 | deepseek-flash__batch_predictor | 72/0 | 0 | 0.000354 | 0.000000 |
| new_york__2025-01-10__1000 | deepseek-flash__llm_selector_program | 72/0 | 0 | 0.000430 | 0.000077 |
| new_york__2025-01-10__1000 | deepseek-v4-pro__batch_predictor | 72/0 | 0 | 0.000354 | 0.000000 |
| new_york__2025-01-10__1000 | deepseek-v4-pro__llm_selector_program | 72/0 | 0 | 0.000794 | 0.000440 |
| new_york__2025-01-10__1000 | follow | 72/0 | 0 | 0.000354 | 0.000000 |
| new_york__2025-01-10__5000 | batch_program | 72/0 | 0 | 0.007860 | 0.006194 |
| new_york__2025-01-10__5000 | deepseek-flash__batch_predictor | 72/0 | 0 | 0.001666 | 0.000000 |
| new_york__2025-01-10__5000 | deepseek-flash__llm_selector_program | 72/0 | 0 | 0.004740 | 0.003074 |
| new_york__2025-01-10__5000 | deepseek-v4-pro__batch_predictor | 72/0 | 0 | 0.001666 | 0.000000 |
| new_york__2025-01-10__5000 | deepseek-v4-pro__llm_selector_program | 72/0 | 0 | 0.001852 | 0.000186 |
| new_york__2025-01-10__5000 | follow | 72/0 | 0 | 0.001666 | 0.000000 |

## 正例机制 F 诊断

outcome-selected exploratory mechanism diagnostic: entire Denver Jan9 day containing all three previously exposed 1km positives; no future label in policy requests; not natural prevalence

| 案例 | 方法 | 已结算/缺失 | 正例 | Brier | 相对FOLLOW变化 |
| --- | --- | --- | ---: | ---: | ---: |
| denver__2025-01-09__1000 | batch_program | 72/0 | 3 | 0.038161 | -0.001493 |
| denver__2025-01-09__1000 | deepseek-flash__batch_predictor | 72/0 | 3 | 0.039654 | 0.000000 |
| denver__2025-01-09__1000 | deepseek-flash__llm_selector_program | 72/0 | 3 | 0.038075 | -0.001579 |
| denver__2025-01-09__1000 | deepseek-v4-pro__batch_predictor | 72/0 | 3 | 0.039654 | 0.000000 |
| denver__2025-01-09__1000 | deepseek-v4-pro__llm_selector_program | 72/0 | 3 | 0.037827 | -0.001827 |
| denver__2025-01-09__1000 | follow | 72/0 | 3 | 0.039654 | 0.000000 |
| denver__2025-01-09__5000 | batch_program | 72/0 | 11 | 0.136583 | -0.001439 |
| denver__2025-01-09__5000 | deepseek-flash__batch_predictor | 72/0 | 11 | 0.138021 | 0.000000 |
| denver__2025-01-09__5000 | deepseek-flash__llm_selector_program | 72/0 | 11 | 0.135560 | -0.002462 |
| denver__2025-01-09__5000 | deepseek-v4-pro__batch_predictor | 72/0 | 11 | 0.138021 | 0.000000 |
| denver__2025-01-09__5000 | deepseek-v4-pro__llm_selector_program | 72/0 | 11 | 0.135428 | -0.002594 |
| denver__2025-01-09__5000 | follow | 72/0 | 11 | 0.138021 | 0.000000 |

负的 Brier 差值表示损失下降。不同阈值和重复视图共享事件，不作独立样本相加；按已知结果选择的正例机制诊断单独报告。

这些结果检验本批工程和开发预测行为，不证明独立天气过程泛化、16类灾害完成或真实历史首次公开时间。数值变化也不自动等于新预测信息。

下一阶段优先补充有正例的分离历史窗口、过程级统计、系统校准、同总资源的逐槽E/F及持久覆盖协议，再进行温度模型评价。
