# DisasterTrace benchmark：v22 计划复核与执行边界（2026-09-26）

## 先澄清版本关系

`plans_v22_0925` 是**最新的 v22 计划/复核包**；当前 GitHub 中的实现和实验基线仍是 **v21 release**，其代码 HEAD 为 `8a6e2162c86c46a139a7f438a6d63d8356e8917c`。因此本文件使用“v22-plan / v21-implementation-baseline”这个完整名称，避免把计划版本误写成代码版本。

本次 GitHub 提交 `ab4b1e324` 只增加审计文档和计划包，不改变 v21 的源代码、测试或历史实验结果。

## v22 计划包本身是什么

[`CHATGPT_PRO_REVIEW_AND_CODEX_PLAN_V22_20260925.zip`](packages/CHATGPT_PRO_REVIEW_AND_CODEX_PLAN_V22_20260925.zip) 是针对 `sisuolv/disastertrace-benchmark` 的独立复核和后续计划包，不是代码修复结果，也不是新实验授权。其 manifest 记录：

- requested/actual review HEAD 都是 `8a6e216`；
- 17 个后续任务仍是 proposed，不能当作已执行；
- 21 个函数/判定子集被复核，其中 11 个正控制、8 个反例、2 个范围缺口；
- 384 个合成解析条件被独立枚举；
- 读取了 6 个历史 GPU scheduler receipt，但没有新 GPU、provider、训练或天气下载；
- 没有执行完整 repository pytest；历史 226 项测试只是 `REPORTED_ONLY`；
- 没有读取 holdout、quarantine 或 protected window。

因此 package validation 的 PASS 只说明 ZIP、JSON、任务 DAG 和校验和完整，不等于 benchmark scientific PASS。

## 当前计划执行状态

| v22 计划层级 | 判定 | 当前含义 |
|---|---|---|
| P0-00 版本、材料和权限绑定 | **部分完成** | v22 package 已绑定 v21 HEAD，但完整历史计划目录、全量 manifest hash 和完整 checkout 复核仍有缺口。 |
| P0-01 已发布结果重建 | **部分完成** | 已有 v21 证据和独立审计，但 schema 入口、逐 cell 重聚合和完整 hash 核验仍需单独完成。 |
| P0-02 target/Y policy | **未关闭** | 当前 ASOS first-valid policy 不能自动等同于原计划 routine/terminal policy；冲突、QC、COR 和成熟版本需冻结。 |
| P0-03 共同网格和有效轨迹 | **未关闭** | Natural 行动轨迹尚未完整进入持续 forecast/scoring；方法缺失和失败分母需要全局登记。 |
| P0-04 TAF/evidence 语义 | **部分完成** | 单位和部分 TEMPO/PROB 处理已有实现，但 CNL、BECMG、尾窗及等时冲突仍需反例矩阵。 |
| P0-05 Natural 预算、时钟和终态 | **未关闭** | public-schedule future source 可重复 RETRIEVE；UPDATE 不保存有效 forecast，cap/timeout 还不能稳定结算。 |
| P0-06 delivery/repair | **部分完成** | 代码和 fixture 存在，但 parent、未来 delivery mask、repair 与 ordinary intervention 的隔离仍不充分。 |
| P0-07 provider transport | **未启动** | 只能先做 fake transport fault tests；没有 provider/model 授权和真实请求证据。 |
| P1 解析反证与真实开发可辨识性 | **未完成** | synthetic advantage 仍可能来自 generator 预先编码的路由先验；真实 active 评分不是内容依赖式 follow-up。 |
| P2 provider pilot / holdout | **BLOCKED** | 必须单独冻结模型身份、预算、失败分母、目标 roster 和授权；当前不能启动。 |

## 当前代码和实验的关键问题

1. **public schedule 查询预算漏洞**：[`natural_track_v18.py:190-213`](../../src/disastertrace/monitoring_v1/natural_track_v18.py#L190-L213) 对未来公开 source 返回 `unavailable`，但不写入 `read`；[`natural_selector_policy_v21.py:118-135`](../../src/disastertrace/monitoring_v1/natural_selector_policy_v21.py#L118-L135) 和 [`active_policy_v21.py:43-77`](../../src/disastertrace/monitoring_v1/active_policy_v21.py#L43-L77) 按成功读取数计算预算。未来 source 可以被连续重试，违反 max-query 和终止合同。
2. **未知 availability 被伪造**：[`interventions_v18.py:500-503`](../../src/disastertrace/monitoring_v1/interventions_v18.py#L500-L503) 将 `None` 转换成 epoch 后一天。应显式返回 unknown/not-applicable 或拒绝该 intervention。
3. **真实 active 诊断对象错误**：[`run_v21_real_dev_deterministic_score.py:23-77`](../../scripts/run_v21_real_dev_deterministic_score.py#L23-L77) 评分的是 `fixed/earliest_source/hash_source/active_age` 四个 one-query arms；`active_age` 只是公开风险年龄排序，不是读取第一条内容后选择第二条 source。source bridge 的轨迹没有进入这份 score。
4. **真实样本和统计分母过弱**：24 个 target 实际全部在 2025-01，标签为 22 个负类、2 个正类；72 个 checkpoint 重复 target label，不能当作 72 个独立天气过程。active 与其他 source arms 打平，fixed 0.5 prior 的改善不能解释成 active gain。
5. **synthetic GPU 结果是条件性机制诊断**：六个 5090/H100 job 成功，但 generator 明确设置了“初始 signal=1 时 q1 更可靠、signal=0 时 q2 更可靠”。这支持一个构造机制假设，不支持天气价值或 novelty。
6. **发布和复现仍不闭合**：v21 快照记录的是旧 HEAD/dirty worktree；完整 pytest 收集存在重复模块名和缺失可选依赖；文档 CPU smoke 依赖 `torch`，但项目依赖没有声明。

## v22 计划允许的最小执行顺序

### P0：先修证据和合同

- 绑定当前 HEAD、计划包 hash、allowlist、旧结果和新输出目录；不覆盖历史 artifact。
- 修复 published reproduction 的 schema/type guard，重建已发布结果的共同分母和逐 target 对账。
- 冻结唯一 Target/OutcomePolicy，保留冲突、missing、timeout 和 unresolved，不补填标签。
- 修复 Natural 的 attempted/unavailable 状态、WAIT/STOP、max query 计数和 deadline 结算。
- 修复 chronology、同到达时间冲突、CNL/BECMG/尾窗的最小反例。
- provider 只先做 fake transport：HTTP、timeout、截断、schema、model mismatch、request ID 和崩溃恢复。

### P1：只做最有判别力的离线实验

- 对 cost-matched synthetic 做解析重建和 generator 反证：原路由、逆转、无信息、噪声提示、ID 任意置换、Bayes/完整证据后端。
- 在允许的 development 派生物上记录每个 target/checkpoint 的合法 candidate 数、内容差异、F 输入差异和实际 query cost；如果选择空间不可辨识，报告“不可辨识”，不要报告“active 无效”。
- intervention/repair 使用同一 parent、明确 delivery mask 和独立后缀；repair 不与普通 source intervention 混为一类。

### P2：provider 之前必须满足的条件

- 同一冻结 roster、同一公开目录、相同 source-query 上限、同一 F、无隐式重试；失败请求保留并计入分母。
- 明确 requested/returned model、endpoint、request ID、usage、latency、schema 和 raw capture；不得从历史模型名猜测当前 provider 身份。
- development、holdout、quarantine 和 protected window 的读取权限分开；没有单独授权就保持 BLOCKED。

## 研究判断

目前可以支持：版本化数据/时间/身份合同、受限 TAF/ASOS 工程绑定、Natural 协议的若干局部实现，以及一个经过人为构造的等成本 active mechanism sanity check。

目前不能支持：真实天气 forecast skill、content-adaptive active 的独立收益、provider/LLM 效果、跨季节/跨 hazard 泛化、完整 Natural agent 成功、算法首创 novelty 或论文级 value claim。

建议总状态写为：

`PARTIAL_PASS_ENGINEERING_INCONCLUSIVE_RESEARCH`

在 P0 合同与评分闭环完成前，不应启动正式 provider、holdout 或继续扩大同一 synthetic generator 的 GPU 网格。v22 的科学问题应改写为：在合法公开信息、共同 F、固定成本和固定时间合同下，content-dependent follow-up 在什么条件下有益、无效或有害。
