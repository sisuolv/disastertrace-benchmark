# 验证尝试与保留的失败

所有旧源文件和原始回答保持冻结。以下都是 P6 新代码/测试/环境的验证过程，不是
替换 P5 失败回答或调高旧分数。

| 尝试 | 观察 | 修正/后续 |
| --- | --- | --- |
| `posthoc_001` | 捕获与 trace hash 核对失败 | 旧 trace 的 capture_sha256 是解析后 JSON 的 canonical fingerprint，不是含末尾换行的文件 SHA；新 overlay 分开记录两者 |
| `posthoc_002` | 完整 P5 对账通过 | 最终新增语义曝光输出后另建 `posthoc_final`，不覆盖先前结果 |
| `01_new_recovery_regressions_before` | 4 fail / 1 pass | 新实现缺部分 raw batch 恢复、complete/call 核验与 naive 时间拒绝；先保留失败再修复 |
| `02_unit_intermediate` | 44 pass | 引用、重复、恢复初步通过 |
| `03_expanded_tests` | 60 pass / 5 fail | 测试试图使用禁止覆盖的生产 writer 改写自己的临时 fixture；改为仅测试中的显式篡改及重算 seal，保留该次测试源码 |
| `04_unit_final` | 65 pass | 扩展的新测试全部通过；65 已含前面通过的测试，不相加 |
| `06_legacy_regression` | 1137 pass / 2 fail / 50 error；轻量环境缺少 transformers/jsonschema、未满足绑定的运行环境 | 保留退出1与失败列表；对应 constrained/stress 文件在现有安装环境重新验证 |
| `12_legacy_tokenizer_grammar` | 71 pass | CPU 上运行现有依赖，无权重加载/模型生成，无依赖升级 |

`posthoc_001_source/` 保存首次失败脚本，`posthoc_final_source/` 和 execution 中的
实现快照保存最终版本。最终实验候选冻结后没有因实测模型结果更改规则。

后续 full-matrix、CPU relocation、保全和验收的实际结果分别写入独立文件。
`VALIDATION_RESULTS.json` 对本轮旧测试逐项去重，记录首轮环境失败及其对应通过
证据。最终验收不把一次失败的全量命令称为退出 0，也不将 subset 重跑另算新测试。
全部1189个旧node已覆盖；71项重验中有19项与首轮通过重复，52项覆盖全部失败/错误。
第四份方案新增4项测试通过，与65项核心测试合计69项。最终辅助脚本lint首次发现
一处可合并的嵌套if，修正后另存 `22_final_lint_fixed`，保留原lint输出。
