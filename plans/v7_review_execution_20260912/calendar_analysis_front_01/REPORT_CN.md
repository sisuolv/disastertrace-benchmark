# 同日历全机会比较

数据：`extension_front_range_03`。本报告由冻结 trace 生成。

| 方法 | 可结算机会 | 正例目标 | Brier | 相对共同基线增益 | 实际模型调用 | 请求 | E 可判定机会 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| model/qwen3_8b/round_robin/base_bound_override | 5826 | 14 | 0.00796316 | -0.00017107 | 1296 | 1296 | 1959 |
| model/qwen3_8b/risk/base_bound_override | 5826 | 14 | 0.00796316 | -0.00017107 | 1296 | 1296 | 1959 |
| model/qwen3_8b/batch_complete/base_bound_override | 5826 | 14 | 0.00796328 | -0.00017119 | 1296 | 1296 | 3876 |
| model/qwen3_8b/llm/base_bound_override | 5826 | 14 | 0.00779209 | +0.00000000 | 1296 | 648 | 0 |
| program/FOLLOW/base_bound_override | 5826 | 14 | 0.00779209 | +0.00000000 | 0 | 0 | 0 |
| program/FOLLOW/persistent_override | 5826 | 14 | 0.00779209 | +0.00000000 | 0 | 0 | 0 |
| program/round_robin/base_bound_override | 5826 | 14 | 0.00791724 | -0.00012515 | 0 | 1296 | 1959 |
| program/round_robin/persistent_override | 5826 | 14 | 0.00790829 | -0.00011620 | 0 | 1296 | 1959 |
| program/risk/base_bound_override | 5826 | 14 | 0.00790002 | -0.00010793 | 0 | 1296 | 1959 |
| program/risk/persistent_override | 5826 | 14 | 0.00789128 | -0.00009918 | 0 | 1296 | 1959 |
| program/coverage/base_bound_override | 5826 | 14 | 0.00791724 | -0.00012515 | 0 | 1296 | 1959 |
| program/coverage/persistent_override | 5826 | 14 | 0.00790829 | -0.00011620 | 0 | 1296 | 1959 |
| program/batch_complete/base_bound_override | 5826 | 14 | 0.00795122 | -0.00015913 | 0 | 1296 | 3876 |
| program/batch_complete/persistent_override | 5826 | 14 | 0.00794151 | -0.00014942 | 0 | 1296 | 3876 |
| program/all_read/base_bound_override | 5826 | 14 | 0.00799912 | -0.00020703 | 0 | 1944 | 5814 |
| program/all_read/persistent_override | 5826 | 14 | 0.00798908 | -0.00019699 | 0 | 1944 | 5814 |
| program/neighbor_persistence/base_bound_override | 5826 | 14 | 0.02162719 | -0.01383510 | 0 | 1944 | 5814 |
| program/neighbor_persistence/persistent_override | 5826 | 14 | 0.02163002 | -0.01383793 | 0 | 1944 | 5814 |
| program/capacity_revise_defer/base_bound_override | 5826 | 14 | 0.00786801 | -0.00007592 | 0 | 1296 | 1959 |
| program/capacity_revise_defer/persistent_override | 5826 | 14 | 0.00790870 | -0.00011661 | 0 | 1296 | 1959 |

增益为共同基线 Brier 减去该方法 Brier，正值表示损失下降。

程序全读与邻站持久性采用不紧的逻辑源预算；这是强对照及实际批量接口的敏感性参照，不能声称它们实际执行了历史线上批量请求。便宜程序的 1ms 记账不是测得的 CPU 延迟。

每个方法保留相同机会与结果掩膜。缺测界、按提前量/站点统计、24/72/168h 日历分组敏感性及同条件成对比较见 REPORT.json。成对比较的缺测界共享同一个目标结果；原始评分器逐机会的界仍是有效但可能更宽的保守界。多个提前量共享结果；日历块不能自动当作独立风暴。

资源计数同时列出实际用量、总硬上限及会话上限耗尽次数。源请求数和模型调用次数的配额可能生效，而 token/计算时间上限留有余量；不能把声明的预算维度都称为实际瓶颈。
