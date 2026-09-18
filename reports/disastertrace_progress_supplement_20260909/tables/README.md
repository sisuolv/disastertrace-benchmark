# 表格口径

所有百分比单位为百分数（0—100），所有主正确率以计划机会为分母。CSV 使用 UTF-8，条件标识与 `evidence/snapshot.json` 的 `runs` 对应。

| 表格 | 内容与口径 |
| --- | --- |
| `model_results.csv` | 九个运行条件的返回、结构合法、严格正确、未尝试、未知与报告 ID；返回子集比率单独标为 diagnostic |
| `method_results.csv` | 每个条件内的历史方法／载体分项；各行分母按原报告保留 |
| `status_results.csv` | 六风暴条件的参考状态分组，包含 planned、returned、strict_correct；不要仅用 returned 代替主分母 |
| `disjoint_errors.csv` | 固定优先级的互斥错误类别，包括 correct；每条件求和等于计划分母 |
| `paired_coverage.csv` | 六风暴条件之间的返回覆盖与正确数差异分解；由本包保存的逐槽位分析重新汇总，不构成因果校正 |
| `representation_pairs.csv` | 两风暴同前缀表示实验的四格结果，单位是配对，合计 422 |
| `context_censoring.csv` | 三个 DeepSeek 扩展条件的未尝试槽位归属；不假设其他未执行请求一定能容纳或答对 |
| `single_repeat_targets.csv` | 六风暴各方法的整目标成功与完整捕获目标数；明确 repeats=1 |

`p7_qwen3` 与 `p9_deepseek_r1` 是同一两风暴原生任务，三方法、两次重复，每条件计划 1,542。`p8_qwen3` 是 422 对单步表示分支，合计 844 份回答；它的合计正确数 261 是两种表示的总和，应报告 JSON 118／422 与文本 143／422 的配对结果，不能作为另一套完整轨迹主分数。

`p11_*`、`p12_*`、`p13_*`、`p14_*` 使用六风暴开发队列，三方法、一次重复，每条件计划 2,412。P11 是 system／任意 JSON 空白，P12 是 system／默认分隔符空白，P13 和 P14 分别是 DeepSeek 与 Qwen 的 user／默认空白条件。各条件独立产生自身历史，不是固定同前缀比较，也没有覆盖完整的角色×空白二乘二设计。

程序对照、受控字段级分数与这些实际模型回答表分开。大量检查点共享同一风暴、公告与目标，不能作为独立天气事件计算显著性。`unknown` 表示已留下提交记录但无可确认原始返回，与 `unattempted` 分开保留。
