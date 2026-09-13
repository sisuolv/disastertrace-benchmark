# E真值语义与单/双任务头诊断

保持相同144个快照；E-only没有提交F，不赋予隐含基线预测成绩。

| 地区/任务/证据 | 机会 | E正确 | Qwen Brier（仅联合任务） |
| --- | ---: | ---: | ---: |
| bay/explicit_truth_E_only/all_registered | 24 | 21 | 未提交F |
| bay/explicit_truth_E_only/common_only | 24 | 24 | 未提交F |
| bay/explicit_truth_E_only/fixed_one | 24 | 19 | 未提交F |
| bay/explicit_truth_joint_EF/all_registered | 24 | 21 | 0.078544 |
| bay/explicit_truth_joint_EF/common_only | 24 | 24 | 0.109623 |
| bay/explicit_truth_joint_EF/fixed_one | 24 | 17 | 0.078544 |
| front/explicit_truth_E_only/all_registered | 24 | 22 | 未提交F |
| front/explicit_truth_E_only/common_only | 24 | 24 | 未提交F |
| front/explicit_truth_E_only/fixed_one | 24 | 17 | 未提交F |
| front/explicit_truth_joint_EF/all_registered | 24 | 24 | 0.000781 |
| front/explicit_truth_joint_EF/common_only | 24 | 24 | 0.083836 |
| front/explicit_truth_joint_EF/fixed_one | 24 | 4 | 0.000781 |

属于相同开发材料上的语义/任务干扰诊断，不是独立天气确认；与旧提示的差异不能单独归因于字段改名。
