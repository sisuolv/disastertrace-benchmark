# 年度预测器下的查询策略比较

模型仅决定补充资料的查询顺序；概率由相同的冻结程序预测器产生。以下是已暴露开发数据的历史回放，不是独立确认或实时未来预报。
注册 12 个日会话，864 个机会，四个全球周块；正式比较完整：True。

派生损失与正式评分逐组核对：108/108 个方法会话的分母和损失总和一致。

| 方法 | 可结算/注册 | 正例 | Brier | 正例 Brier | 负例 Brier |
|---|---:|---:|---:|---:|---:|
| LLM_SELECTOR | 861/864 | 16 | 0.0085666 | 0.4018364 | 0.0011200 |
| FOLLOW | 861/864 | 16 | 0.0098354 | 0.2960346 | 0.0044163 |
| F_COMMON | 861/864 | 16 | 0.0072363 | 0.3512715 | 0.0007220 |
| F_BASE_ONLY | 861/864 | 16 | 0.0085985 | 0.4018364 | 0.0011526 |
| B11_BATCH | 861/864 | 16 | 0.0080626 | 0.4029625 | 0.0005852 |
| B11_COVERAGE | 861/864 | 16 | 0.0077496 | 0.4001473 | 0.0003195 |
| B00_COVERAGE | 861/864 | 16 | 0.0080397 | 0.3963101 | 0.0006878 |
| B01_COVERAGE | 861/864 | 16 | 0.0080551 | 0.4114518 | 0.0004169 |
| B10_COVERAGE | 861/864 | 16 | 0.0083151 | 0.4056324 | 0.0007919 |

| 参照方法 | 参照损失 - LLM 损失 | 是否更换预测器 bank |
|---|---:|---|
| FOLLOW | 0.0012689 | False |
| F_COMMON | -0.0013302 | True |
| F_BASE_ONLY | 0.0000320 | False |
| B11_BATCH | -0.0005040 | False |
| B11_COVERAGE | -0.0008170 | False |
| B00_COVERAGE | -0.0005269 | False |
| B01_COVERAGE | -0.0005114 | False |
| B10_COVERAGE | -0.0002515 | False |

API 请求意图 288，供应方报告 token 738634；没有完整供应方响应的请求 0。供应方实际账单未查询，不填作零成本。
合法 selector 回复 71/288。错误按原契约保留：{'Invalid selector schema': 192, 'valid': 71, 'Expecting value: line 1 column 1 (char 0)': 25}。
只读格式诊断：{'queries_instead_of_query_order': 147, 'not_a_plain_JSON_response': 25, 'query_handles_instead_of_query_order': 20, 'other_structural_or_semantic_error': 25}。没有把别名键或解释文字事后改成合法动作，也没有重跑预测。
无效 JSON 对象的实际顶层键组合：{'forecast_handles,queries': 126, 'forecasts,queries': 21, 'forecast_handles,query_handles': 20, 'f_handles,q_handles': 1, 'selected_forecast_handles,selected_queries': 9, 'selection': 13, 'forecast_handles,q0,q1,q2': 2}。字段别名与契约不一致和 JSON 外文字分别计数；这些是接口失败，不能单独作为取证推理能力结论。
无效回复、运输失败、费用未知和未取得资料的机会均保留。完整账本见 RESOURCE_AND_API_LEDGER.json。
相同结果掩膜保证方法间可比，不保证缺失无偏；逐预测值敏感性界及地区、周块分层见 ANALYSIS.json。
F_COMMON 与其他方法采用不同 bank，其差异不能全归因于查询策略。B00/B01/B10/B11 固定 coverage selector 比较预算分配和资料共享。
本轮不根据这些开发损失选择新的日期、模型或提示词；一次开发胜负不构成 novelty 或独立过程泛化证明。
