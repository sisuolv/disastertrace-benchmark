# 同日历全机会比较

数据：`extension_bay_area_01`。本报告由冻结 trace 生成。

| 方法 | 可结算机会 | 正例目标 | Brier | 相对共同基线增益 | 实际模型调用 | 请求 | E 可判定机会 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| model/qwen3_8b/round_robin/base_bound_override | 5832 | 53 | 0.02992253 | -0.00030873 | 1296 | 1296 | 1989 |
| model/qwen3_8b/risk/base_bound_override | 5832 | 53 | 0.02961379 | +0.00000000 | 1296 | 1296 | 1986 |
| model/qwen3_8b/batch_complete/base_bound_override | 5832 | 53 | 0.03026470 | -0.00065091 | 1296 | 1296 | 3771 |
| model/qwen3_8b/llm/base_bound_override | 5832 | 53 | 0.02961379 | +0.00000000 | 1296 | 648 | 126 |
| program/FOLLOW/base_bound_override | 5832 | 53 | 0.02961379 | +0.00000000 | 0 | 0 | 0 |
| program/FOLLOW/persistent_override | 5832 | 53 | 0.02961379 | +0.00000000 | 0 | 0 | 0 |
| program/round_robin/base_bound_override | 5832 | 53 | 0.02950960 | +0.00010419 | 0 | 1296 | 1989 |
| program/round_robin/persistent_override | 5832 | 53 | 0.02963882 | -0.00002503 | 0 | 1296 | 1989 |
| program/risk/base_bound_override | 5832 | 53 | 0.02961866 | -0.00000487 | 0 | 1296 | 1986 |
| program/risk/persistent_override | 5832 | 53 | 0.02972686 | -0.00011307 | 0 | 1296 | 1986 |
| program/coverage/base_bound_override | 5832 | 53 | 0.02950960 | +0.00010419 | 0 | 1296 | 1989 |
| program/coverage/persistent_override | 5832 | 53 | 0.02963882 | -0.00002503 | 0 | 1296 | 1989 |
| program/batch_complete/base_bound_override | 5832 | 53 | 0.02959783 | +0.00001597 | 0 | 1296 | 3771 |
| program/batch_complete/persistent_override | 5832 | 53 | 0.02970966 | -0.00009586 | 0 | 1296 | 3771 |
| program/all_read/base_bound_override | 5832 | 53 | 0.02933587 | +0.00027792 | 0 | 1944 | 5646 |
| program/all_read/persistent_override | 5832 | 53 | 0.02945967 | +0.00015412 | 0 | 1944 | 5646 |
| program/neighbor_persistence/base_bound_override | 5832 | 53 | 0.06418328 | -0.03456948 | 0 | 1944 | 5646 |
| program/neighbor_persistence/persistent_override | 5832 | 53 | 0.06503403 | -0.03542024 | 0 | 1944 | 5646 |
| program/capacity_revise_defer/base_bound_override | 5832 | 53 | 0.02964714 | -0.00003334 | 0 | 1296 | 1986 |
| program/capacity_revise_defer/persistent_override | 5832 | 53 | 0.02954439 | +0.00006940 | 0 | 1296 | 1986 |

增益为共同基线 Brier 减去该方法 Brier，正值表示损失下降。

程序全读与邻站持久性采用不紧的逻辑源预算；这是强对照及实际批量接口的敏感性参照，不能声称它们实际执行了历史线上批量请求。便宜程序的 1ms 记账不是测得的 CPU 延迟。

每个方法保留相同机会与结果掩膜。缺测界、按提前量/站点统计、24/72/168h 日历分组敏感性及同条件成对比较见 REPORT.json。多个提前量共享结果；日历块不能自动当作独立风暴。
