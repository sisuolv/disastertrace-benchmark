# DisasterTrace P6：后续方案整合与首轮离线实施交接

日期：2026-09-08。起点提交：`dd5ee358f9708e2eb2f2032db9eaac14fa237adc`。

本轮依据用户最初提供的三份 plan_v3 与执行中补充的第四份方案，完成第一阶段的代码与完整程序演练。
**新增模型回答为 0。** P5 的 1620 条真实回答与 P6 的 4320 条程序回答严格分开。
最终验收以同目录 `OFFLINE_ACCEPTANCE.json` 为准；本文不会把尚未实施的 live 启动
或真实 forecast 资料轨列为完成。

## 1. 四份计划如何合并

共同主线是：先说明 P5 到底错在哪里，再修复重复实验的身份与测量，再扩展真实
来源和模型覆盖。本轮将其落实为 `plans/INTEGRATED_P6_PLAN_V1.md` 中的 P6-00–05。

两份方案推荐最小 E1 为 base/scope 两条件、两次重复、2160 机会；第三份建议三次
重复。我们选前者作为唯一冻结候选，不并行堆叠多个矩阵。实现允许将来另立三次
重复版本，但没有把所有提案同时启动或提前改变原有任务。

本轮保留原 renderer、严格 parser、scorer、Gold 和公开信息策略。新增代码位于
`src/disastertrace/post_p5/` 与 `src/disastertrace/repeat_eval/`。旧 P1–P5 的 source
snapshot、capture、报告、acceptance 和消耗过的 claim 均不重写。

## 2. P5 已重新核验，而不只是重抄旧表

使用冻结 P5 实现和独立 CPU 环境，重新核验 P4 和三组 P5 的原始报告、capture 与
trace；核对 P5 OFFLINE acceptance 的 2229 项和 LIVE acceptance 的 4425 项。
这是对历史样本的复验，不是新运行模型。具体记录在 `baseline/` 与 `baseline.log`。

P5 原分数继续保持：1620 个回答，1360 个 checkpoint 全部正确、260 个不全正确。
共有 6480 个字段机会，其中 90 个值/状态错误、230 个纯引用错误，合计 320 个字段
错误。29 个动作错误全部与风速字段错误重叠，不能再加成 349 个独立错误。

## 3. 引用错误现在可以逐项追溯

| 值正确但引用错误的主类 | 字段数 |
| --- | ---: |
| 已被取代的旧版本，数值与当前相同 | 109 |
| 不存在的 record ID | 48 |
| 有效窗口或 measurement kind 不符 | 26 |
| 变量或单位不符 | 19 |
| 已被取代的旧版本，数值与当前不同 | 12 |
| 行号越界 | 11 |
| 实体不符 | 5 |
| 合计 | 230 |

109/230 的主类是“值没变但来源过时”。这说明版本更新的来源定位是值得继续研究
的维度；它不能证明模型内部只是忘记更新引用，也不能据此删掉这些错误。

输出保留逐字段主类、逐引用定位/ASSERT/行 hash、多个错误引用、正确与错误引用
混合、重复引用、是否匹配前一载体引用，以及首次错误和恢复区间。
主类采用固定优先级，逐引用细项不扩大字段分母。值错误不重复计入 230 个纯引用错。

入口：`posthoc_final/DIAGNOSTIC_FINDINGS.md`、`conservation.json`、
`field_diagnostics.jsonl`、`citation_details.jsonl`、`trajectory_errors.jsonl`。

## 4. 按真实输入计算压力曝光

| 条件 | 首次实际出现 | 基础 episode 数 |
| --- | --- | ---: |
| revision_chain | c2 | 30 |
| revision_chain | 全程无变化 | 6 |
| irrelevant_scope | c2 | 36 |
| late_stale_replay | c4 | 36 |

不能把所有 checkpoint 都标为已承受压力。revision 的 6 个零效应 episode 继续留在
主分母和独立控制切片；stale 的 c0–c3 属于首次曝光前。新增唯一记录、已有记录
修改、额外交付、目标/无关 ASSERT 数和当前目标状态分别比较。

`exposure_pairs.jsonl` 同时记录证据字节、公开语义、实际 carrier、prompt tokens、
sampling seed 和双向正确性变化。历史 P4/P5 的硬件和种子差异，以及由之前回答
造成的 carrier 差异，仍使这些配对差异只能作描述性分析。

## 5. 简单程序揭示了当前 benchmark 的能力边界

我们新增或明确了 7 个公开策略：initial_only、last_delivered、两种频率策略、
按事实键 latest-issued、scope-blind-last-delivered、public oracle。
它们没有访问私有 Gold，程序输出在生成后才与独立 compiler 的 Gold 比较。

按事实键 latest-issued 与 public oracle 在 P4 和三组 P5 上均为 180/180。
当前合法语义限定单条版本链、父先子后、严格推进 issue time，所以这个简单程序
足以确定链头。这是任务域的事实，不应把它叫作作弊或故意破坏合法规则来降分。

相比之下，scope-blind-last-delivered 在 scope 组为 78/180；这说明 scope 筛选
确实有可测差异，但现有程序结果没有证明需要一般复杂图推理。
完整规则、结果和适用前提见 `docs/p6/SOLVER_EQUIVALENCE.md`；主张边界见
`docs/p6/CLAIM_AUDIT.md`。

## 6. 新 E1 的设计与实现

```text
2 conditions × 36 episodes × 5 checkpoints × 3 methods × 2 repeats
= 2160 slots / 432 trajectories / 1080 condition pairs
```

同一配对的采样 seed 不含 condition，运行身份却必须含 condition；因此两条件种子
匹配且历史状态隔离。每条轨迹有五个有序 checkpoint，不同 repeat 不共享状态。
调度使用独立 RNG，按 checkpoint 波次构造相邻条件对，每批至多 12 个请求。
两个 repeat 将同一配对的条件先后顺序反转；每个 repeat/cp 两种先后顺序各 54 对。

沿用 Qwen3-8B、BF16、8192 输出预留、16384 context、原 thinking 和结构约束轨。
当前代码明确拒绝模型模式，GPU/hardware 验证标为 false。

冻结 execution ID：

```text
0b4a7d7a56d1f82694b3973e89670fc44eb7a098c8708c4689e775fa3a58fb80
```

更详细的身份、随机性、输入/统计与帮助层级见 `docs/p6/MEASUREMENT_PROTOCOL.md`。

## 7. 为什么先做 raw-first 和独立恢复

collector 在发送前落盘意图与开始标记，收到后先保存整个 raw batch，然后才逐条
提取和解析。raw 通过独占原子发布保存，不能覆盖已存在的结果。
合法但错误的回答原样进入自己的历史，无效 JSON 保留上一合法状态。

若只返回一部分槽位：按 attempt_id 保留已知结果，其他标 unknown 并停止。
若提取时抛异常：已落盘的其他 raw 可由 CPU 重建。若 raw 保存前退出：不把未知
当作未收费/未发送/可以重试。本轮没有自动补调用逻辑。

独立 auditor 从 raw tokens、公开数据和冻结调度重新建立请求/状态；它不信任
collector 的 state_after、接受结果或 complete 标记。它会拒绝种子/重复/请求/
载体篡改，即使外层 hash 被重新计算。

## 8. 完整离线结果

| 程序模式 | 收到/计划 | 合法输出 | 全正确 checkpoint | 格式屏通过 | episode pass^2 |
| --- | ---: | ---: | ---: | ---: | ---: |
| correct | 2160/2160 | 2160 | 2160 | 36/36 | 全部 1 |
| invalid-control | 2160/2160 | 1728 | 1728 | 0/36 | 全部 0 |

invalid-control 在每条轨迹的 c2 注入无效 JSON，共 432 个失败。全部计入原分母，
并导致每个 family 屏只有 48/60 合法，低于 58/60 阈值。它用于证明错误不会被
静默丢弃；程序后端不执行 grammar 采样，不能把这 432 个失败看作实际模型失效率。

两份报告都保存逐来源/逐 repeat 的 36 个汇总格、432 条轨迹、1080 个配对结果、
首次曝光切片与完整 token 分解。correct 有 1080 对 both_correct；invalid-control
有 864 对 both_correct、216 对 both_wrong。没有人为过滤失败或替换分母。

上下文校验：10800 个程序请求机会、2373 个唯一提示的实际 tokenizer/adapter
检查，最大 prompt=7002；加完整输出预算后为 15194，低于 16384。
这不保证任意长模型 carrier 都能装下，因此超限停止测试也已实现。

## 9. 验证证据与复查入口

新增核心 65 项 pytest 测试最终全部通过，涵盖引用细类、MFT/INV/DIR、频率/replay、
Gold 不进入公开求解器、配对身份与 RNG、并发 claim、载体传播、部分返回、提取
异常、三个退出点、上下文超限、表面 hash 重算、报告重建和 pass^k。

旧测试首次使用轻量 `.venv` 时暴露 tokenizer/grammar 依赖缺失。对应的 71 项
constrained/stress 测试随后在现有安装环境通过，运行的是 CPU 验证而非模型生成。
全量旧测试的最终逐项对账、最终保全与迁移复查结果以 `VALIDATION_RESULTS.json`
和 `OFFLINE_ACCEPTANCE.json` 为准，不将重复测试次数与历史验收数字累加。

每个新步骤的实际 command、stdout/stderr、exit 和时间在 `validation/`。
第一次 posthoc hash 契约失配、故障回归的预期失败、第一次篡改 fixture 写法错误
及缺依赖的旧测试尝试均保留。处理过程见 `VALIDATION_NOTES.md`。

第四份方案另补 4 项测试且全部通过，其中1项 Hypothesis 性质测试使用固定 seed、
最多100个纯程序序列；序列数量不计作100项独立测试。独立的九个来源绑定探针全部
通过 private compiler/public oracle/手写常量预期的三方对照。按固定排序抽取8类
实际 P5 错误例子，保存在 `actual_examples/`，并附6480行原始来源元数据。
补充项的逐条映射见 `SUPPLEMENTAL_PLAN_RECONCILIATION.md`。

独立迁移只需 execution 内的冻结源码、tokenizer/config、原始 run 和 report。
复制后禁止访问原项目、模型权重与网络，使用没有 Torch/vLLM 的 CPU 环境，
重新生成评分并逐项比较。准备与复查命令见 `REPRODUCE.md`。

## 10. 尚未完成及下一步

当前状态应为 `offline_verified_live_pending`，不能写成模型评测完成或所有 live
条件就绪。具体待办按优先级为：

1. 实现新模型后端和一次性 ACP phase launcher，绑定单张完整 H100 的无生成预检，
   然后冻结并执行同一 2160 矩阵。已有 GPU 使用许可仍有效，最多四卡；本轮没有
   开启新的 live 调用或消费未来 claim。
2. 单独建立有界 NHC 官方 forecast 原文轨，优先同绝对 valid time 的多版本预报。
   分开 issue/init/lead/valid/获取时间，双解析器不一致自动 quarantine，保持无逐条
   人工标注和无 LLM judge 的主评分。
3. 在独立来源覆盖、任务/Gold/scorer 与上下文冻结后，做版本完全匹配的第二模型
   与正交方法干预；最后再执行 heldout。更多重复不能代替更多独立事件。

详细可执行步骤在 `NEXT_STEP_EXECUTION_PLAN.md`。本轮未下载新的上游框架、官方
天气正文或模型权重，未训练、未动 heldout、未发布 P6 到 GitHub。
