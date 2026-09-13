# 新数值与固定证据接口独立复查

## 发现

**P2：状态 reducer 本身没有执行目标时间语义门槛。**

`disastertrace-starter/src/disastertrace/monitoring_fixed_v1/contracts.py:401` 的 `ForecastState.propose` 只检查 `at <= expires_at`，没有调用 `target.check_cutoff(at)`。本轮三个合成反例中，future physical 点目标的目标时刻、future product 的发布时刻、partial nowcast 的结束时刻，均已被 `Target.check_cutoff` 判为不合法，却仍能被 reducer 接受为 override，并在序列化恢复后继续生效。

这是状态接口的边界缺口，**不是已证明当前 GPU 输入或结果违规**。现有 144 个固定快照均由 EvidenceBundle 的 cutoff 检查放行；60 个数值样例也全部为正时效。后续会话回放必须在调用 reducer 前检查目标语义／机会截止，或在独立新版本 reducer 中补这个保证。不要修改已经绑定 GPU 作业的冻结模块来覆盖旧实验记录。

可复现反例为 `probe_boundaries.py`，结果在 `BOUNDARY_RESULTS.json`，绑定了被测模块 SHA256。这些脚本不修改冻结模块或数据，也不是新的模型调用。

## 实际输入检查

- 复原并核对全部 144 个航空 EvidenceBundle 的封装 hash；检查了其中 144 个资产的目标私有 entitlement、完成时间和逐条观测时刻。
- 没有在这些 policy 输入中发现 `outcome/evaluator_only/gold/gold_mask/expected_e` 标签字段；逐条观测均不晚于 cutoff。这个结论针对已构造样例，不保证任意第三方 provider 放入的字符串都没有隐含答案。
- 对全部 60 个正时效 EUPP 温度样例，核对 sourcepair 文件 hash、政策侧集合数组、point 支持、输出与原始集合的均值／中位数一致性，以及实际保留的缺失 publication_time。
- 独立重算 MAE：ensemble mean 为 1.4261969931608802 K，ensemble median 为 1.4508169555664163 K，与本轮报告一致。只是单站、三个起报日的数值集成诊断，不是独立极端天气过程结果。
- 当前 EUPP/SEEPS/水文资格报告保留历史可用时刻、日累计窗口、物理支持与调蓄口径等限制；未发现把这批源验证直接升级为正式 monitoring 或 C1/C2 增益的表述。

本轮未发现已构造 aviation 快照或 temperature 输出中的实际标签泄漏、单位混用或数值计分错误。E/F 分离在 SYSTEM、E_question 与独立 deterministic E reference 中保留。通用 EvidenceBundle 主要验证声明及依赖结构，来源文字和转换是否真的满足其声明仍需 provider 合同约束。

`verify_actual_inputs.py` 和 `ACTUAL_INPUT_RESULTS.json` 保存实际输入核验；两个复查脚本 Ruff 检查通过。

## 提示词后续对照的解释范围

在同一批固定输入中采用明确字符串枚举 `true/false/unknown/conflict`，并保持与既有 E 状态的确定映射，可以测试模型是否混淆“有证据”和“命题为真”。同一新命名下的 E-only 与 joint E/F 可以比较双输出任务影响。若拿新命名结果直接对比先前带填好示例的提示词，则同时改变了命名、示例锚定和输出格式，不能把全部差异归因于重命名一个因素，也不能解释为 F 收益。
