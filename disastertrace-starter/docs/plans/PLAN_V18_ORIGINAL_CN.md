# DisasterTrace v17：Benchmark 定位与后续优化建议

## 0. 当前判断

DisasterTrace 目前最大的风险，不是“不够严谨”，而是**为了避免与已有工作重叠、避免过度宣称，而把研究问题不断收缩，最终可能退化成一个过于局部的“当前哪份 TAF 有效”测试**。

这种方向不利于体现 benchmark 的独特性和整体价值。

更合理的原则应该是：

> **证据边界用于限制结论，不应该变成研究上限。**

DisasterTrace 不需要通过“和已有工作完全不重叠”来证明 novelty。更合理的做法是：

- 主动吸收已有工作的优秀设计；
- 将记忆、持续预测、工具使用、状态维护、干预实验等已有能力组合到一个真实、有业务约束的天气风险持续研判环境中；
- 通过新的任务组织方式、评价体系和实验发现来体现独特价值；
- 严格控制的是结论的证据范围，而不是研究本身的 ambition。

当前建议基于 `v17-batch-a-v1` 最新分支进行思考。当前核心方向已经从早期“LLM 是否能比官方公告更快”逐步转向：

> **真实天气证据持续变化时，智能体能否持续维护正确状态、吸收有效变化、避免被无效变化误导，并对同一未来天气风险目标持续修订判断。**

这是值得继续强化的主线。

---

# 1. 当前版本已经具备的基础

当前代码已经不再只是一个静态天气问答 benchmark，而是具备了持续研判任务的初始形态。

## 1.1 固定未来目标 + 多阶段证据更新

当前任务围绕一个固定的未来天气风险目标展开，例如：

- 固定机场；
- 固定未来一小时；
- 判断例行站报是否低于 5 km 能见度阈值；
- 在 T−60 / T−40 / T−20 三个时刻重复做判断。

因此，一个 episode 不再是：

> 给一堆资料 → 回答一次。

而是：

> 固定未来目标 → 新证据逐渐到达 → 模型更新事实状态和风险概率 → 继续等待新证据 → 再更新。

这已经非常接近老师所强调的 Live / Online：

> 新的信息不断进来，模型需要结合此前状态继续做判断，而不是单次调用。

## 1.2 当前已经实现的几个重要模块

| 模块 | 当前作用 | 后续定位 |
|---|---|---|
| `qualification.py` | 从真实 TAF 档案构建可追溯 episode | 继续作为真实 evidence stream 构建基础 |
| `agent_view.py` | 隔离模型可见证据与 scorer 私有参考 | 保留，并扩展模型可见的目标气象状态 |
| `runner.py` | 执行多 checkpoint 轨迹、状态延续、请求记录 | 扩展为统一历史 replay / prospective runner |
| FRESH / STATEFUL | 比较是否携带自写事实状态 | 保留为 memory / state 实验之一 |
| R / D / S | 原样重跑、重复证据、长度 sham | 保留为信息等价扰动诊断 |
| repair / sham | 修复错误状态并继续执行 | 保留为局部机制实验 |
| `analyze_v17_pilot.py` | 分析事实状态正确率、stale state、概率漂移 | 后续接入真实 Y 和预测质量 |

当前版本最大的缺口是：

> **过程评价已经开始形成，但预测结果质量尚未真正闭环。**

现阶段仍然主要是一个 Y-blind source-state pilot，因此它还不能回答：

- 概率到底准不准；
- 是否真的减少预测损失；
- 是否优于强专业预测基线；
- 状态错误是否真的导致风险预测变差。

这应该成为下一阶段最重要的补全方向。

---

# 2. 建议重新定义 DisasterTrace 的核心定位

## 2.1 推荐核心问题

建议将整个 benchmark 的核心问题明确为：

> **当真实天气证据持续到达、修订、重复、相互补充甚至发生冲突时，智能体能否持续形成可靠的风险判断：及时吸收有效变化、避免被无效变化带偏，并在必要时主动获取更多信息？**

推荐英文表述：

> **DisasterTrace: Evaluating Adaptive Weather-Risk Agents under Evolving Evidence**

中文可以概括为：

> **DisasterTrace：演化证据驱动的持续天气风险研判基准**

这里的核心研究对象是：

> **Adaptive Weather-Risk Agent**

而不是某个 ledger 标签，也不是某一种 memory 方法。

## 2.2 完整任务应包含什么

### 输入

持续变化的真实天气证据，例如：

- TAF；
- 观测；
- 专业预测产品；
- 图形或多模态气象资料；
- 可调用的天气工具；
- 历史公共判断；
- 当前已经维护的 agent state。

### 智能体行为

智能体需要：

1. 判断哪些证据当前有效；
2. 理解证据对目标时段真正表达了什么；
3. 区分新信息、重复信息、修订和冲突；
4. 维护历史状态；
5. 更新目标风险概率；
6. 在主动模式下选择是否继续获取信息；
7. 必要时 WAIT / RETRIEVE / UPDATE / STOP。

### 输出

至少包括：

- 风险概率；
- 当前关键证据；
- 目标相关事实状态；
- 下一步动作；
- 可选的自写 memory / carrier。

### 最终评价

不能只看一项分数，而应该同时看：

- 事实状态是否正确；
- 风险概率是否准确；
- 是否及时更新；
- 是否出现 stale state；
- 是否被重复资料干扰；
- 错误是否能够恢复；
- 主动检索是否值得；
- latency / token / tool cost；
- 最终风险预测的真实收益。

---

# 3. 不要把“事实维护”和“预测技能”变成两个互不相干的问题

此前方案中有一种潜在风险：

> 因为事实状态容易验证，所以不断强化事实状态评价；因为风险概率评价复杂，所以不断往后推。

这样最后很容易变成：

> 模型能不能找到最新的一份 TAF。

这个任务本身价值有限。

更合理的方向是：

> **事实维护和风险预测分别评分，但在同一个任务中研究它们之间的关系。**

可以形成如下四种情况：

| 事实状态 | 风险判断 | 含义 |
|---|---|---|
| 正确 | 正确 | 证据理解与预测均可靠 |
| 正确 | 错误 | 会维护资料，但不会把资料转化为预测 |
| 错误 | 暂时正确 | 最终答案可能掩盖脆弱过程 |
| 错误 | 错误 | 进一步判断是否可通过事实修复改善 |

真正值得研究的问题是：

> **过程错误什么时候只是格式错误，什么时候会真正污染后续风险判断？**

这会比单纯做 source-state benchmark 更有价值。

---

# 4. 建议将独特性集中在三个相互依赖的方面

## 4.1 真实天气证据具有复杂的版本和适用语义

天气证据不是普通的 append-only 文本流。

新资料可能意味着：

- 新版本替代旧版本；
- 目标时段发生变化；
- 只是格式重发；
- 是重复镜像；
- 是补充确认；
- 与此前来源发生冲突；
- 对目标无关；
- 旧产品不再“当前有效”，但仍包含历史预测信息。

因此任务不只是：

> 记住最新一句话。

而是：

> **当前什么信息有效？什么仍有参考价值？哪些变化真的与目标有关？**

这是 DisasterTrace 与一般 long-context / memory benchmark 相比非常值得强化的结构。

## 4.2 真正要评价的是 selective adaptation

一个系统如果永远不改概率：

- 会很稳定；
- 但无法吸收新信息。

一个系统如果每次看到新消息都大改概率：

- 会显得很敏感；
- 但也可能被重复和无关变化误导。

因此应该评价：

> **对有效变化敏感，对无信息变化稳定。**

也就是：

### Adaptation

遇到真正目标相关的新证据时：

- 能否及时更新状态；
- 能否更新风险判断。

### Stability

遇到：

- duplicate；
- mirror；
- reformat；
- length sham；
- semantic-equivalent reissue；

是否能保持合理稳定。

真正优秀的 agent 应当同时具备：

> **Sensitivity to useful evidence + Robustness to irrelevant change**

这是可以成为 benchmark 核心故事的一部分。

## 4.3 必须把过程错误连接到预测后果

最终不能只评价：

- source ID 对不对；
- 更新快不快；
- JSON 格式是否正确。

更重要的是：

> **这些过程差异会不会改变风险预测质量？**

因此后续一定要接入：

- 成熟 Y；
- 同期专业 baseline；
- 完整概率轨迹；
- outcome-side scoring。

这样才能回答：

- stale state 是否真的造成损失；
- duplicate-induced drift 是否真的有害；
- stateful memory 是否改善预测；
- repair 是否真的让后续判断变好。

---

# 5. Related Work 应该主动吸收，而不是主动回避

Novelty 不应该定义为：

> “已有工作做过的东西，我们都不能做。”

更合理的研究方式是：

> **已有好的组件直接借鉴；我们的贡献来自把它们放入新的真实问题结构中，并得到新的评价结论。**

## 5.1 FutureSim

可借鉴：

- 时间推进；
- 顺序预测；
- 持续状态；
- 可查询历史信息；
- 时间加权预测评价。

不需要因为 FutureSim 已经做 continuous forecasting 就删掉 DisasterTrace 的动态预测。

相反，可以把问题改成：

> FutureSim 类持续预测机制，在带有明确来源、有效期和版本修订语义的真实天气证据中，会表现如何？

## 5.2 StateMem / StateMemBench / BLF

可借鉴：

- evolving fact state；
- structured memory；
- belief / evidence state；
- 预测状态的持续更新。

可以直接把这些方法改造成 baseline。

然后测试：

> 在天气证据不断 revision、重复和冲突的情况下，这些 memory/state 方法是否仍然可靠？

这比“为了不重叠所以不用 memory”更合理。

## 5.3 EarthVerse

可以借鉴：

- 地球系统异构证据；
- 工具使用；
- 来源追踪；
- 过程与最终结果的共同评价。

DisasterTrace 不需要重新发明“工具评价”和“过程评价”。

更重要的是：

> 把这些机制应用在真正持续变化、具有 operational revision semantics 的天气风险目标上。

## 5.4 AgentCaster

可以借鉴其角色设定：

> LLM / Agent 使用专业天气资料和工具做风险推理，而不是要求 LLM 自己裸做 NWP。

这正好回应老师们之前担心：

> LLM 本身不适合直接替代专业天气模型。

DisasterTrace 应该明确：

> 专业模型是工具和证据，Agent 的任务是综合、维护、获取和判断。

## 5.5 LiveHouse-TS / Living Benchmarks

可以借鉴：

- prospective evaluation；
- 真实未来数据；
- 在线持续评价；
- 时间跨度上的模型稳定性。

DisasterTrace 的 Living 应保留，但不要将：

> “有 live”

本身当 novelty。

真正要证明的是：

> **真实时间运行会暴露 replay 静态 benchmark 看不到的什么问题？**

---

# 6. 五个优先级最高的优化方向

## 6.1 优化一：从“当前来源是谁”升级到“当前资料对目标说了什么”

当前模型主要维护：

- `active_source_ids`
- `valid_start`
- `valid_end`
- `relation_status`

下一阶段应该进一步加入：

> **Target-relevant Weather State**

例如对于低能见度任务：

- 目标时段的能见度描述；
- 是否有 BR / FG；
- 是否存在 TEMPO / PROB；
- 是否有目标相关的云底、降水、天气现象；
- 哪些变化真正改变了目标风险相关内容。

建议形成三层状态：

### Layer 1 — Source State

哪份资料当前有效？

### Layer 2 — Target Content State

当前资料对目标时段表达了什么？

### Layer 3 — Risk Belief

agent 对未来事件的概率判断是什么？

于是：

> **Source Change ≠ Content Change ≠ Probability Change**

这三个层次应该明确分开。

## 6.2 优化二：接入真实 Y，让过程评价和预测价值闭环

当前 Y-blind pilot 的作用是：

- 测试仪器；
- 测试状态行为；
- 测试重复敏感性；
- 测试 memory。

但它不能成为最终 benchmark 的主体。

下一阶段应在开发集上完成：

> **Evidence Stream → Agent Probability Trajectory → Mature Outcome → Score**

并且接入：

- 专业基线；
- 简单统计基线；
- 当前 agent；
- memory 方法；
- tool-assisted 方法。

这样才能回答：

> Agent 是否真的改善风险判断，而不是只更会维护 source ID。

## 6.3 优化三：从 3-checkpoint pilot 走向更长持续过程

T−60 / T−40 / T−20 是很好的第一版。

但长期而言，它太短，不能充分测试：

- 长期 memory；
- state decay；
- recovery；
- 多次 update；
- 很长时间没有变化后突然出现关键变化；
- agent 是否知道什么时候不应该更新。

建议下一版增加：

> **Long-Horizon Evidence Stream**

例如：

- T−6h；
- T−4h；
- T−2h；
- T−1h；
- T−40；
- T−20。

不一定每个点都有新证据，但这正好能研究：

> 无变化期间的稳定性 + 关键更新时刻的适应能力。

## 6.4 优化四：同时保留 Controlled 与 Natural 两个主 Track

不要在“公平控制”和“真实智能体能力”之间二选一。

建议统一成两个 track。

### Controlled Track

所有模型看到完全相同的 evidence prefix。

主要测：

- 理解；
- memory；
- state maintenance；
- probability revision；
- duplicate robustness；
- repair。

适合做机制对照。

### Natural / Active Track

所有模型拥有相同：

- 可访问来源；
- 工具；
- 时间；
- 权限。

但允许自己决定：

- 查什么；
- 什么时候查；
- 是否等待；
- 是否停止；
- 使用哪个天气工具。

主要测：

- tool use；
- retrieval；
- active observation；
- adaptive reasoning；
- cost-quality frontier。

这很好地回应老师之前提出：

> 信息检索本身也是模型能力，不应该全部人为固定。

## 6.5 优化五：尽早加入多模态和第二领域的小规模验证

不要等 H15 所有细节都完全完成才开始第二领域。

但也不要立刻铺开 16 种灾种。

推荐：

### 第一领域

机场低能见度：

- TAF；
- METAR；
- 专业 guidance；
- 必要图形产品。

### 第二领域

热带气旋：

- forecast advisory；
- track / intensity；
- satellite / map；
- observation updates。

研究：

> 相同的 evidence evolution / state / update benchmark 设计是否可以迁移？

这样可以回答：

> 当前结果到底是在测一般的持续天气研判能力，还是只是在测“会不会读 TAF”。

---

# 7. 最值得做的四组论文级实验

## 7.1 实验 1：Endpoint vs Trajectory

核心问题：

> **只看最终答案，会不会误判一个持续运行 agent 的可靠性？**

同时报告：

- Final Brier / final accuracy；
- Trajectory Brier；
- Fact-state accuracy；
- stale-state duration；
- recovery；
- invalid state / fallback。

重点展示：

> 最终表现类似的模型，中间轨迹是否存在明显差异。

如果有：

说明 process-aware benchmark 有额外价值。

如果没有：

也可以说明在哪些任务上 endpoint 已经足够。

## 7.2 实验 2：Adaptation vs Stability

同时设置：

### 真变化

- 新目标相关证据；
- revision；
- content change；
- independent confirmation。

### 无信息变化

- duplicate；
- mirror；
- reformat；
- length sham；
- semantic-equivalent reissue。

比较：

- 应该更新的时候是否更新；
- 不应该更新的时候是否稳定。

最后画：

> **Adaptation–Stability Tradeoff**

而不是只画 accuracy。

## 7.3 实验 3：Repair → Downstream Forecast

已有 repair / sham 非常适合作为真正有研究价值的实验。

核心问题：

> **一个错误 evidence state 是否真的会污染后续风险判断？**

步骤：

1. 找到真实错误 parent state；
2. fork；
3. repair 仅修复事实；
4. sham 做等范围非实质改动；
5. 保持之后所有证据相同；
6. 让 agent 继续运行；
7. 比较后续：
   - source state；
   - probability；
   - action；
   - 最终损失。

定义：

\[
\Delta_{\mathrm{repair}}
=
\mathbb{E}
[
Q_{\mathrm{original}}
-
Q_{\mathrm{repair}}
].
\]

这比只证明：

> repair 后 fact accuracy 更高

有价值得多。

## 7.4 实验 4：强 Baseline 对比

建议至少保留四类：

### Professional / Statistical Baseline

回答：

> Agent 是否真的提供额外预测价值？

### Fresh Recompute

回答：

> 直接每次重读全部资料是否已经足够？

### Stateful / Structured Memory

回答：

> 持续状态到底在什么时候有帮助？

### Tool-assisted Agent

回答：

> 普通解析工具能解决多少问题？剩下哪些才是真正 reasoning / planning 难点？

然后可以加入 BLF / StateMem 风格方法。

重点不是一定让自己的方法赢。

而是回答：

> **什么时候复杂 agent 有价值，什么时候简单方法已经足够？**

这本身就是 benchmark 的价值。

---

# 8. 工程层面建议

## 8.1 第一优先：完成真实 outcome 闭环

下一阶段最重要的是：

> target → legal evidence → agent probability → mature Y → score

而不是继续新增几十个 contract 字段。

具体包括：

- 对锁定开发 episode 接入 outcome；
- 保留已有预测；
- 不根据 Y 改样本；
- 对齐专业 baseline；
- 输出 trajectory score。

优先完成：

> **一条完整、可对账的真实 episode + 一张主表**

比继续新增很多 gate 文档更有价值。

## 8.2 第二优先：扩展目标相关内容状态

在现有 source state 上增加：

- visibility；
- relevant weather；
- condition blocks；
- target applicability；
- uncertainty。

不要一步做完整天气语义。

先把一个任务做深。

## 8.3 第三优先：扩展 Natural Track

允许模型：

- RETRIEVE；
- READ；
- WAIT；
- STOP；
- CALL WEATHER TOOL。

固定：

- source catalogue；
- deadline；
- tools；
- safety cap。

报告：

- prediction quality；
- latency；
- tokens；
- tool calls；
- failures。

资源上限是安全边界，不再是核心 novelty。

## 8.4 第四优先：Living Prospective Pilot

建立一个真正未来运行的小闭环：

```text
REGISTER
    ↓
OPEN
    ↓
Evidence Arrives
    ↓
Agent Updates
    ↓
SEALED
    ↓
PENDING_RESULT
    ↓
SETTLED
    ↓
Next Batch
```

先跑 baseline-only，再跑有限 agent。

真正的 Living 价值来自：

- real arrival latency；
- failures；
- outages；
- corrections；
- prospective commitment。

而不是仅仅：

> “历史数据按照时间顺序 replay”。

## 8.5 简化模型侧输出协议

当前 commit contract 偏复杂。

模型不应该承担过多纯 bookkeeping 字段。

推荐模型只需要输出：

```json
{
  "risk_probability": 0.35,
  "active_evidence": ["source_A"],
  "target_state": {},
  "next_action": "WAIT"
}
```

系统内部负责：

- hash；
- parent commit；
- timestamps；
- version；
- validation；
- transaction log。

这样任务难度更集中在：

> 天气证据理解与持续风险研判，

而不是：

> JSON 填表能力。

---

# 9. 如何回应老师们的核心问题

| 老师的问题 | 当前是否解决 | 推荐最终回答 |
|---|---|---|
| Benchmark 到底测什么？ | 部分解决 | 测持续天气风险研判，而不是单次报告生成 |
| LLM 是不是在替代天气模型？ | 基本解决 | 不替代 NWP；专业模型是证据和工具 |
| Live 是不是只是“更快”？ | 基本解决 | Live 是新信息持续到达后的状态与风险修订 |
| 为什么限制 search 次数？ | 需要调整 | Natural Track 不强制紧 budget，cost 作为指标 |
| 公告是不是 ground truth？ | 当前已开始澄清 | 专业公告是 evidence / baseline，成熟观测才是 Y |
| 更快 / 更省够不够重要？ | 不够 | 核心价值是持续判断是否可靠，以及过程错误是否影响预测 |
| Related work gap 在哪里？ | 正在形成 | 不是说别人都没有动态，而是现有方法缺少版本化真实天气证据下的持续研判评价 |
| Benchmark 有没有整体价值？ | 尚需实验验证 | 用 endpoint-vs-trajectory、adaptation-vs-stability、repair、strong baseline 四组实验来证明 |

---

# 10. 推荐最终论文结构

## Contribution 1 — Evolving Weather Evidence Benchmark

构建：

> 真实、版本化、带来源和时效语义的天气证据持续流。

不是静态 QA。

## Contribution 2 — Process × Outcome Evaluation

同时评价：

- evidence state；
- target content；
- risk belief；
- update timing；
- recovery；
- final outcome。

## Contribution 3 — Controlled Diagnostics

使用：

- duplicate；
- identity repeat；
- sham；
- repair；
- withhold；
- delay。

解释：

> 模型为什么成功 / 失败。

## Contribution 4 — Replay + Prospective Living Evaluation

同一合同支持：

- historical replay；
- active replay；
- prospective live evaluation。

---

# 11. 推荐向导师解释的一段话

> **DisasterTrace 研究的是智能体在真实天气证据持续变化时，能否一直做出可靠的风险判断。我们允许它使用专业预报、观测和工具，不要求 LLM 替代数值天气模型；但要求它正确处理资料的更新、重复和冲突，并持续修订同一未来目标的判断。评价既看最终预测，也看整个过程是否及时、稳定、能够从错误中恢复，再通过配对实验判断证据处理究竟怎样影响预测。现有记忆、持续预测与工具方法都是我们的重要参照，而不是需要回避的重叠。**

---

# 12. 最终建议

下一阶段不建议继续主要投入在：

- 再增加很多 contract 项；
- 再增加很多 defensive disclaimer；
- 再继续细化“哪些结论不能说”；
- 再为了避免重叠而主动删除已有研究做过的组件。

应该把精力集中到：

1. **真实成熟 Y 与风险预测闭环；**
2. **Target-content state；**
3. **Endpoint vs Trajectory；**
4. **Adaptation vs Stability；**
5. **Repair → Downstream Forecast；**
6. **Strong Baselines；**
7. **Natural Active Track；**
8. **Prospective Living Pilot；**
9. **小规模多模态 / 第二领域验证。**

最后需要坚持的原则是：

> **研究问题可以完整、有 ambition；需要严格限制的是最终结论的证据范围，而不是研究本身的上限。**

DisasterTrace 最有潜力的价值，不是证明自己和所有已有工作都不同，而是：

> **把真实演化天气证据、持续智能体行为、过程诊断和最终风险预测放进同一个可执行评价体系，并证明这种评价能够揭示静态终点评测看不到的系统差异。**
