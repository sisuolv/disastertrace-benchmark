# 同日历全机会比较

数据：`replication_2026_01`。本报告由冻结 trace 生成。

| 方法 | 可结算机会 | 正例目标 | Brier | 相对共同基线增益 | 实际模型调用 | 请求 | E 可判定机会 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| program/FOLLOW/base_bound_override | 5796 | 14 | 0.00719313 | +0.00000000 | 0 | 0 | 0 |
| program/FOLLOW/persistent_override | 5796 | 14 | 0.00719313 | +0.00000000 | 0 | 0 | 0 |
| program/round_robin/base_bound_override | 5796 | 14 | 0.00719341 | -0.00000028 | 0 | 1296 | 1953 |
| program/round_robin/persistent_override | 5796 | 14 | 0.00719404 | -0.00000091 | 0 | 1296 | 1953 |
| program/risk/base_bound_override | 5796 | 14 | 0.00719331 | -0.00000018 | 0 | 1296 | 1938 |
| program/risk/persistent_override | 5796 | 14 | 0.00719393 | -0.00000081 | 0 | 1296 | 1938 |
| program/coverage/base_bound_override | 5796 | 14 | 0.00719341 | -0.00000028 | 0 | 1296 | 1953 |
| program/coverage/persistent_override | 5796 | 14 | 0.00719404 | -0.00000091 | 0 | 1296 | 1953 |
| program/batch_complete/base_bound_override | 5796 | 14 | 0.00719394 | -0.00000081 | 0 | 1296 | 3804 |
| program/batch_complete/persistent_override | 5796 | 14 | 0.00719453 | -0.00000141 | 0 | 1296 | 3804 |
| program/all_read/base_bound_override | 5796 | 14 | 0.00719435 | -0.00000122 | 0 | 1944 | 5718 |
| program/all_read/persistent_override | 5796 | 14 | 0.00719500 | -0.00000188 | 0 | 1944 | 5718 |
| program/neighbor_persistence/base_bound_override | 5796 | 14 | 0.02035676 | -0.01316363 | 0 | 1944 | 5718 |
| program/neighbor_persistence/persistent_override | 5796 | 14 | 0.02036021 | -0.01316709 | 0 | 1944 | 5718 |
| program/capacity_revise_defer/base_bound_override | 5796 | 14 | 0.00719313 | +0.00000000 | 0 | 1296 | 1938 |
| program/capacity_revise_defer/persistent_override | 5796 | 14 | 0.00719313 | +0.00000000 | 0 | 1296 | 1938 |

增益为共同基线 Brier 减去该方法 Brier，正值表示损失下降。

程序全读与邻站持久性采用不紧的逻辑源预算；这是强对照及实际批量接口的敏感性参照，不能声称它们实际执行了历史线上批量请求。便宜程序的 1ms 记账不是测得的 CPU 延迟。

每个方法保留相同机会与结果掩膜。缺测界、按提前量/站点统计、24/72/168h 日历分组敏感性及同条件成对比较见 REPORT.json。成对比较的缺测界共享同一个目标结果；原始评分器逐机会的界仍是有效但可能更宽的保守界。多个提前量共享结果；日历块不能自动当作独立风暴。

资源计数同时列出实际用量、总硬上限及会话上限耗尽次数。源请求数和模型调用次数的配额可能生效，而 token/计算时间上限留有余量；不能把声明的预算维度都称为实际瓶颈。
