# v12：原整周结果的修订解释

原840条轨迹、60480方法行已经通过原正式审计；本报告只派生分析，不重新生成原预测。
已暴露开发日历，只有四个全局周；不作为独立确认或新LLM实验。

| 阈值 | 方法 | Brier | 正例/已结算 | 缺失 |
|---|---|---:|---:|---:|
| 1000m | FOLLOW | 0.00724308 | 29/6008 | 40 |
| 1000m | F_COMMON | 0.00445879 | 29/6008 | 40 |
| 1000m | F_BASE_ONLY | 0.00469660 | 29/6008 | 40 |
| 1000m | B11_BATCH | 0.00465430 | 29/6008 | 40 |
| 1000m | B11_COVERAGE | 0.00449992 | 29/6008 | 40 |
| 5000m | FOLLOW | 0.04279855 | 307/6008 | 40 |
| 5000m | F_COMMON | 0.03615101 | 307/6008 | 40 |
| 5000m | F_BASE_ONLY | 0.03842806 | 307/6008 | 40 |
| 5000m | B11_BATCH | 0.03472680 | 307/6008 | 40 |
| 5000m | B11_COVERAGE | 0.03393755 | 307/6008 | 40 |

gain = 参考损失 - 方法损失，正数表示改善。

| 阈值 | 比较 | 平均gain |
|---|---|---:|
| 1000m | FOLLOW -> F_COMMON | 0.00278429 |
| 1000m | FOLLOW -> F_BASE_ONLY | 0.00254648 |
| 1000m | FOLLOW -> B11_BATCH | 0.00258879 |
| 1000m | FOLLOW -> B11_COVERAGE | 0.00274316 |
| 1000m | F_COMMON -> F_BASE_ONLY | -0.00023781 |
| 1000m | F_COMMON -> B11_BATCH | -0.00019551 |
| 1000m | F_COMMON -> B11_COVERAGE | -0.00004113 |
| 1000m | F_BASE_ONLY -> B11_BATCH | 0.00004231 |
| 1000m | F_BASE_ONLY -> B11_COVERAGE | 0.00019668 |
| 1000m | B11_BATCH -> B11_COVERAGE | 0.00015438 |
| 5000m | FOLLOW -> F_COMMON | 0.00664754 |
| 5000m | FOLLOW -> F_BASE_ONLY | 0.00437049 |
| 5000m | FOLLOW -> B11_BATCH | 0.00807175 |
| 5000m | FOLLOW -> B11_COVERAGE | 0.00886099 |
| 5000m | F_COMMON -> F_BASE_ONLY | -0.00227705 |
| 5000m | F_COMMON -> B11_BATCH | 0.00142421 |
| 5000m | F_COMMON -> B11_COVERAGE | 0.00221345 |
| 5000m | F_BASE_ONLY -> B11_BATCH | 0.00370126 |
| 5000m | F_BASE_ONLY -> B11_COVERAGE | 0.00449050 |
| 5000m | B11_BATCH -> B11_COVERAGE | 0.00078924 |

F_COMMON与其他values后端不同；同后端补证比较应使用F_BASE_ONLY。BATCH为48次/日预算内策略。
E修订补上supported肯定状态，保留缺frame和缺Y；不改变原F、Y、分母、掩膜或Brier。
十个比较均为新增开发描述性分析。缺失敏感性界不是置信区间，不按当前输赢扩展确认日期。
