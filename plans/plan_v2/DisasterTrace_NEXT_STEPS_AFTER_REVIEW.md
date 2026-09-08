# DisasterTrace：仓库审阅后的增量实施计划

> 执行对象：Codex；本文件是下一阶段的工程与研究规格，不是已实现功能或新实验结果。
>
> 审阅基线：`sisuolv/disastertrace-benchmark@a23f73adadcbec077b9fcf2aecf8f45dfa4fe061`。
>
> 本计划依据该提交中的 review、当前状态、核心源码、P1 报告和交付验证记录制定。审阅方式为源码/文档/归档记录检查；本文编写过程未重新运行仓库的 684 项测试，未调用模型 API，未修改远程仓库。
>
> 默认执行范围：离线增量实现和测试。付费调用、模型下载、heldout 推理、远程推送和公开发布均不由本文件自动授权。

## 0. 给 Codex 的首要指令

先检查当前 checkout、未提交修改和所有适用的 `AGENTS.md`，然后读取本文件及下列当前入口：

1. `README.md`、`REFERENCE_BUNDLE.md`、`handoff_validation/README.md`。
2. `disastertrace-starter/REVIEW_FOR_CHATGPT_PRO.md`。
3. `disastertrace-starter/IMPLEMENTATION_STATUS.md`、`DECISIONS.md`、`BLOCKERS.md`。
4. `disastertrace-starter/docs/CALIBRATION_PROTOCOL_V1.md`、`docs/OUTPUT_CONTRACT_V1.md`、`docs/METRICS_V2.md`。
5. `disastertrace-starter/work/p1-deepseek-background-continuation-v1/report/REPORT.md`。
6. 与当前工作包相关的源码和测试。

如果 checkout 比本次审阅提交更新，先输出 `docs/REVIEW_BASELINE_DELTA.md`，区分已经完成的任务、仍适用的建议和发生冲突的协议。不要重置用户分支到旧提交，不要删除未提交修改。

**不要从头搭建 schema、parser、replay、provider 或 evaluator。** 当前项目已经有完整的自动化主线。沿现有 `src/disastertrace/automated/` 增量开发；不要用早期聊天中的示例代码替换当前实现。

第一轮默认完成 N0–N3 的离线部分，最后提交实际命令、测试结果、受保护历史文件校验结果和下一步授权清单。不得在离线验收后自动启动 N4 的真实请求。

---

## 1. 当前事实与研究边界

以下为仓库支持的事实，不是本计划的推测。[R1–R6]

| 项目 | 当前状态 | 对后续实施的含义 |
|---|---|---|
| 官方资料与准入 | 12 个候选风暴、36 份公告；32 份解析成功，10 个风暴各具完整三公告 | 不重新随机选事件，不改旧准入失败记录 |
| 划分 | 3 个开发风暴：Ida、Florence、Dorian；7 个 heldout 风暴尚无真实模型推理 | 新协议设计仅用开发事件/新合成 fixtures |
| 回放 | 每风暴 base、delay 两分支，每分支 c0–c4 五检查点 | 100 个检查点不是 100 个独立风暴 |
| 输入方法 | snapshot、structured_state、answer_history 全部看累计交付原文 | 当前研究回答载体差异，不隔离记忆依赖 |
| 输出 | 四个可抽取数值字段、一个始终未知的港口重开字段，加字符串 action | 不是多模态灾害推理或真实港口运营 |
| 规则 | 最大持续风速至少 100 mph → prepare；否则 monitor；未知 → request_evidence | 是公开研究规则，不是官方响应标准 |
| 时间 | 官方发行时刻 + controlled_release 交付计划 | 不等于已证明历史首次公开可用性；连续观测不等于同窗口纠正 |
| P0 | V2 等价证据支持和版本化离线重评已完成 | 不重做 scorer；旧 V1/V2 和原回答保持不变 |
| P1 | 90 个响应、91 次累计请求尝试；含一次授权的中断续跑 | 原请求 79 的未知费用仍独立保留；不能重启旧授权 |
| 新校准 | 三臂、270 个机会、54 条轨迹已离线准备 | 尚不是可启动的真实采集器 |
| 交付 | 根目录已带精简 references；交付记录有新环境 684 tests passed | 不把旧 review 的外部资料提醒误读成“当前包没有 references” |

P1 主结果：

| 方法 | 结构有效 | 已知字段 grounded correctness |
|---|---:|---:|
| snapshot | 14/30 | 39/96 |
| structured_state | 30/30 | 96/96 |
| answer_history | 24/30 | 76/96 |

90 个回答有 20 个输出上限失败、2 个其他结构错误。全部 68 个结构有效回答的字段值、状态与研究规则行动正确；另有一个 snapshot 引用落在不支持目标风速的行上。有效回答条件下的高分不能替换固定分母。[R2]

**当前可支持的定位：受控资料交付下，最新报告值的抽取、来源绑定及回答载体可靠性。**

**拟发展的定位：在可执行语义下，解析证据版本、局部更新和可回答性变化，并维护正确的值与来源。**

不要声称 structured_state 的 100% 已证明记忆机制优势、普遍灾害能力、真实调度能力或未来预测能力。

---

## 2. 四项优先决策

### D1. 停止重复扩建基础设施，完成真实采集的最后一段

优先补齐 explicit contract → exact wire request → raw provider response → carrier → 独立审计 → 离线评分的完整链路。

### D2. 校准优先于新的能力结论，但不阻塞离线 P2 设计

先消除明显的格式/输出预算混杂，再解释方法差异。与此同时可离线实现 P2 语义和程序负例；P2 模型调用必须等公共输出契约冻结。

### D3. 保留真实 NHC 轨道，另建 controlled semantics 轨道

真实文本提供来源与格式的现实性；受控轨道提供清晰的部分更新、同窗口纠正和可恢复缺失。两者分别报告，不用合成修订冒充真实 NHC 更正。

### D4. 首篇不新增专家逐题标注、LLM Judge、大型 GIS 或训练系统

把自动评分限制在可执行、可独立检验的任务边界内。研究者仍需要制定协议和检查工程；这不同于逐题人工给模型判分。

---

## 3. 从当前代码直接复用什么

下列路径相对于 `disastertrace-starter/`。[R7–R13]

| 已有组件 | 已检查的行为 | 下一步用法 |
|---|---|---|
| `automated/dynamic.py` | public allowlist、累计交付、最新整份报告 reference、严格 parse_decision | NHC V1 原样保留；不用于隐式解释 P2 partial patch |
| `automated/output_contract.py` | legacy 原字节、explicit 公共 instruction/JSON Schema、contract identity | 新 collector 调用 `render_calibration_request` |
| `automated/provider.py` | prepare 精确 wire body、无隐式重试、凭据与 redirect 防护 | 优先沿用 transport；新增 deadline 必须另立执行配置 |
| `automated/collection.py` | 单方法顺序采集、逐请求持久记录、安全前缀恢复 | 复用实现模式；当前硬编码 legacy renderer，不直接当新 collector |
| `automated/collection_audit.py` | 旧采集审计和 provider envelope 检查 | 保留旧 verifier；新审计理解 contract/arm/全矩阵 |
| `automated/calibration.py` | 270 槽位调度、离线排练、计数筛选、评分投影 | 复用调度和配置；`score_rehearsal` 仍只接受程序诊断 |
| `automated/scoring_v2.py` | 固定分母、known-only、变化/保留/来源刷新、条件恢复 | NHC 正式分数继续使用冻结 V2 |
| `automated/evidence_support.py` | 受限 NHC 支持语法 | 不扩成通用文本蕴含，不因某模型答案改语法 |
| P1 外部 runner/continuation | 一次性启动、费用预留、未知请求保留 | 提取设计和已验证测试，不消耗/复用旧 launch claim |
| 根目录 references/ 与交付验证 | 精简来源包与新环境执行记录 | 增加标准离线 CI，不重新下载全部上游 benchmark |

### 外部开源资源的本阶段角色

- CyPortQA：保持已做的模板画像和来源核对；不把“可下载完整数据集”当成本阶段依赖。
- DisasterBench_Open：保留为独立计划一致性控制，不混进 NHC 主分数，不声称执行真实工具。
- EarthVerse：借鉴可执行答案单元与公开/私有边界；当前不导入整个 runner、工具库或事件包。
- STATE-Bench、STALE、时态 memory 框架：作为相邻工作和 P2 反例设计参考，不在没有正式适配与复现实验时列成已运行 baseline。

以上范围依据当前 review 的复用清单；本计划没有新增外部系统复现实验。[R1]

---

## 4. 新增代码边界与目录

以下均为**拟新增**，不是现有可运行命令或文件。尽量少加模块，不引入通用 Agent 平台。

```text
src/disastertrace/automated/
  calibration_collect.py           # 新契约/多 cell 的真实采集编排
  calibration_collection_audit.py  # 独立核验真实 exposure、carrier 和 wire body
  experiment_journal.py            # 全矩阵调度、启动归属、崩溃恢复
  budget_ledger.py                 # 单实验累计金额预留和结算
  calibration_report.py            # 审计后投影评分、paired report、预算推荐
  transport_deadline.py            # 仅在执行修订选择 total deadline 时新增

src/disastertrace/controlled/
  __init__.py
  schema.py
  generator.py
  reference.py                    # 每事实键权威版本/支持的参考编译
  renderer.py
  runtime.py                      # 只组织公共输入和保存模型响应
  scoring.py
  controls.py                     # 正确程序 + 针对性错误程序
  audit.py                        # 与参考编译不同算法的核验

specs/
  calibration_execution_v1.json
  p2_controlled_v1.json

docs/
  NEXT_STAGE_STATUS.md
  CALIBRATION_EXECUTION_PROTOCOL_V1.md
  P2_CONTROLLED_SEMANTICS_V1.md
  P2_AUTOMATIC_GOLD_VALIDATION.md
  CLAIMS_AND_LIMITATIONS.md
```

先完成 calibration 的五个核心模块。不要为了创建以上树而先写大量空文件；按工作包实际需要建立。

旧采集器仍支持历史协议；新采集器只服务当前校准矩阵。P2 独立命名是为了避免 source parser、输出 schema 和评分含义悄然改变。

---

## 5. N0：固定审阅基线并复核已有包

**目的：** 确认接手位置，避免重做已经完成的工作。

### 任务

- [ ] 记录 git commit、dirty status、Python、安装依赖与当前实现 identity。
- [ ] 阅读当前入口；发现比本审阅更新的内容时先生成差异表。
- [ ] 检查 `references/` 的实际文件、manifest 和已记录来源；不推定完整上游仓库已打包。
- [ ] 运行当前测试目录 `tests/`；不要递归混入历史 `artifacts/` 内的测试副本。
- [ ] 在全新输出路径执行 build → calibration prepare → verify。
- [ ] 记录实际 exit code、测试数、skip、失败日志；不要照抄 684 为本次结果。
- [ ] 固定受保护文件集合：历史 P1、原未知请求账、已有评分/采集原文、来源快照和旧 manifest。

当前已有的可执行入口示例：

```bash
cd disastertrace-starter
.venv/bin/python -m pytest tests -o addopts= -q

# 下面两个输出目录必须是本次全新的、不存在的路径。
.venv/bin/disastertrace-auto build \
  --references ../references \
  --nhc-snapshot ../references/nhc_cohort_v1 \
  --output work/next-review-build-001

.venv/bin/python -m disastertrace.automated.calibration prepare \
  --build work/next-review-build-001 \
  --provider-config artifacts/p1_deepseek_development/provider.json \
  --output work/next-review-calibration-001

.venv/bin/python -m disastertrace.automated.calibration verify \
  --output work/next-review-calibration-001
```

若没有 `.venv`，按根 README 建立环境；本文件不授权覆盖已存在的环境。禁止为通过 implementation identity 检查而修改历史 manifest。

### 验收

新运行可以解释与旧交付记录的相同和不同；当前新环境失败属于新发现，保留失败与原因，不能声称历史记录被本次重现。

---

## 6. N1：真实契约感知采集与独立曝光审计

### 6.1 为什么不能直接启动旧采集器

`collection.collect_model()` 目前使用 legacy `render_request()`。`calibration.score_rehearsal()` 只接受 `diagnostic_program` 且 `provider_requests=0` 的排练记录。不能改个 flag 就把排练当作真实结果。[R9–R11]

### 6.2 公共输入流程

```text
frozen schedule row
    + 此 trajectory 自己之前的有效真实回答
    → render_calibration_request(contract=...)
    → ProviderClient.prepare(...)
    → 保存 exact public request / exact wire body / hash
    → 一次 HTTP 请求
    → 保存 raw provider envelope 与返回元数据
    → 冻结的 parse_decision
    → 更新或保持本 trajectory 的 carrier
```

全部 cell 使用相同的 source、policy、evidence、parser 和 carrier 规则。只有预声明 contract/cap/执行修订字段可变。

轨迹键至少包含：

```text
(experiment_id, arm_id, method, event_id, branch, repeat_id)
```

请求机会键增加 `checkpoint_id`。不得用 output directory 作为唯一防重键。

### 6.3 每个请求的必要记录

```json
{
  "opportunity_id": "stable identifier",
  "trajectory_id": "stable identifier",
  "sequence_number": 1,
  "contract_id": "hash",
  "provider_config_id": "hash",
  "public_request_sha256": "hash",
  "wire_body_sha256": "hash",
  "carrier_before_sha256": "hash-or-null",
  "raw_provider_response_sha256": "hash-or-null",
  "acceptance": "accepted|invalid|not_received",
  "carrier_after_sha256": "hash-or-null",
  "transport_status": "received|error|unknown|not_sent",
  "usage_status": "verified|missing|invalid|not_applicable"
}
```

这是拟议的索引字段，具体命名可沿现有 journal。原始 bytes 保存在内容寻址文件中，索引指向它们，避免一份原文在多套 manifest 中重复存储。

### 6.4 独立 collection audit 必须验证

- [ ] 从原始 accepted/invalid 响应重建 carrier，不信任缓存的 `state_after`。
- [ ] 使用该 arm 的 contract 重建 actual public request。
- [ ] 检查公共 evidence 与交付 schedule，不能把未来 checkpoint、parsed fields 或 Gold 传给模型。
- [ ] 核对 prepare 的 body 与实际 transport 发送的 body 一致。
- [ ] 核对 response envelope、finish reason、model alias、usage 与对应请求。
- [ ] 把 schema-valid-but-wrong 原样保存为 carrier；schema-invalid 不进入 carrier。
- [ ] 失败与未发送机会保留在完整 270 槽位索引中。
- [ ] 确认不同 arm/method/branch/repeat 没有历史串用。
- [ ] 所有 output 原文保留；不得提取 reasoning_content 代替 content 作为“最终答案”。
- [ ] 日志不得包含 Authorization、API key 或代理凭据。

独立性不能仅是“调用 collector 自己的 verify()”。允许共享 canonical JSON/哈希函数，但审计的 schedule、carrier 与公共暴露重建逻辑应可单独测试，且必须有篡改后重新计算表面 hash 的负例。

### 6.5 投影评分的正确使用

```text
真实 actual trace
    → 独立 collection audit 通过
    → 创建新的 compatibility projection
       （仅把 instruction 换为 legacy）
    → 冻结 V1/V2 scorer
    → 报告同时绑定 actual/projection/audit/scorer/source hashes
```

不得修改 actual trace。不得把 projection 显示为模型真实看过的输入。不得给 `score_rehearsal` 的程序记录伪造真实请求数。

新 live-compatible scorer adapter 应只接受通过审计的 collection ID；审计不通过时不得产生“正式已验证模型结果”。既有诊断函数保留原限定。

### 验收

使用 fake transport 完成 54 条轨迹、270 个机会；每条后续请求来自自己的前缀。篡改 instruction、evidence、carrier、wire body 或接受状态中任一项，必须被独立审计发现。全程零模型请求。

---

## 7. N2：持久化调度、金额账本与故障恢复

### 7.1 一个实验、一套账本、一个启动归属

不要运行九个各自拥有 USD 3 的 cell runner。一个实验共享一个持久账本，全部 270 个机会都在同一调度中。沿现有 append-only journal，必要时使用 SQLite 事务；不要求重写旧存储系统。

### 7.2 建议状态机

```text
PLANNED
  → RESERVED
  → SEND_INTENT_DURABLE
  → RAW_RESPONSE_DURABLE
  → USAGE_VALIDATED_AND_SETTLED
  → DECISION_RECORDED
  → FINALIZED
```

异常状态：

```text
NOT_SENT_GUARD_STOP
UNKNOWN_IN_FLIGHT
RECEIVED_ENVELOPE_INVALID
RECEIVED_USAGE_INVALID
RECEIVED_TASK_SCHEMA_INVALID
```

注意 `RECEIVED_TASK_SCHEMA_INVALID` 是实际收到的模型失败；usage 有效时正常结算并按原 carrier 规则继续。provider envelope / usage 无法验证则停止进一步调用。

### 7.3 崩溃恢复决策

| 崩溃位置 | 恢复行为 |
|---|---|
| durable send intent 之前 | 在确认无发送可能时可恢复尚未发送槽位 |
| send intent 之后、没有完整 raw response | 视为可能已发送；保留金额预留，停止，不自动重发 |
| 完整 raw response 已落盘，但解析/载体尚未完成 | 离线重放解析、账本和 carrier，不进行网络重发 |
| 已结算和 finalization 之间 | 根据稳定记录幂等完成，不重复扣账 |
| 已完成机会 | 原样复用，包括格式失败，不重新抽样 |

本地可以保证幂等记账和禁止自动重复提交，不能宣称跨不确定网络具备服务端 exactly-once 计费。

### 7.4 金额守卫

沿现行保守规则，下一请求需满足：

```text
conservatively_settled
+ retained_unknown_reservations
+ reservation_for_next_request
<= newly_authorized_experiment_allowance
```

使用 Decimal 或整数最小单位。reasoning tokens 如属于 completion 的子集，不重复加价。actual-window/cache-aware estimate 与保守 guard 账分开；estimated cost 不是发票。

历史 P1 的未知请求及旧额度不转入新实验“可用余额”。未取得有效 usage 不释放预留。返回 usage 超过参数上界或模型 alias 异常时停止并保留原始响应。

保留当前 full-context reservation 策略，除非有单独验证且版本化的 provider token bound；不要按 bytes/4 或历史平均 token 偷换成安全上界。可另做描述性费用预测，但不得用于削弱 guard。

### 7.5 默认故障测试

- [ ] 两个进程同时 claim 同一实验，只能有一个实际执行者。
- [ ] 更换输出目录不能绕过 launch claim。
- [ ] 在每个 durable 状态边界强制中断并恢复。
- [ ] 接收到 JSON 失败后继续，旧有效 carrier 不变。
- [ ] 事实错误但结构有效后继续，错误 state 持续进入后续输入。
- [ ] raw response 存在而 state 不存在时，只离线恢复。
- [ ] uncertain in-flight 不释放预留、不重发。
- [ ] 边界金额恰好足够/差最小单位均正确。
- [ ] 缺 usage、usage 为负/溢出/不一致、model 不匹配立即停止。
- [ ] 追加日志尾部截断或 hash 断链时停止，不默认丢尾重试。
- [ ] 停止后的全部未发送机会仍在报告分母。

### 验收

270 个程序响应演练可完成并核验；在各崩溃点只能得到可证明恢复的前缀或明确中止，不得“恢复成功但重复请求”。旧 P1 checksum 不变。

---

## 8. N3：冻结执行协议、timeout 和报告

### 8.1 保留三臂，不立即扩为四臂

| arm | 公共 contract | 输出上限 | fresh opportunities |
|---|---|---:|---:|
| legacy_4096 | legacy_v1 | 4096 | 90 |
| explicit_4096 | explicit_v1 | 4096 | 90 |
| explicit_8192 | explicit_v1 | 8192 | 90 |

这是 270 个全新机会，不复用 P1 的旧 90 个回答作为本期 control。[R4]

两项对比：

```text
explicit_4096 - legacy_4096：固定 4096 时公共契约的影响
explicit_8192 - explicit_4096：显式契约下输出上限的影响
```

只有要估计 contract×budget interaction 时，才另立四臂完整设计。显式 schema 减少输出说明的不均衡，但不能单独排除“历史响应提供格式示例”的全部作用；本期不能据此证明记忆机制。

### 8.2 timeout 必须作为运行前决策，而非失败后临时调整

当前 `ProviderConfig.timeout=60`，`urllib_transport` 把它传给 `opener.open()`。Python 文档把该参数描述为阻塞操作的 timeout，而非整次请求墙钟时间保证。[R12,E1]

本计划建议在真实启动前完成一次明确的执行修订：

- 所有三臂使用相同的 socket timeout 和总体 deadline。
- 可将 240 秒作为待确认的共同工程上限；这不是已测量足够的结论。
- 记录连接/读取失败与总 deadline 超时为不同原因。
- 以本地慢响应、持续小块响应、连接不返回三类假服务测试总 deadline。
- 中止客户端不等于 provider 未生成或未收费；其预留仍保留。

**不得直接修改冻结 V1 的 60 秒参数。** 若接受上述建议，新增 `CALIBRATION_EXECUTION_PROTOCOL_V1.md` 和新的 execution identity，列出继承的三臂/数据/评分规则及唯一 transport 修订。新的 collector/prepare 派生配置，不伪装成原 V1 完全相同。

如果项目负责人决定完全照旧 V1 执行，则保持 60 秒并如实把结果解释为“共同 60 秒 socket timeout 约束下的预算校准”；不得观察 8192 失败后仅给该臂延长时间。

### 8.3 推理配置

保持当前 high + thinking enabled，不把 temperature=0 当作消除随机性的补丁。DeepSeek 官方文档说明 thinking 模式下 temperature 等参数不生效。[E2]

本期不同时加入 JSON mode、结构约束解码、non-thinking、修复重试或另一个模型，这些都会增加实验因素。需要时另立后续小型 ablation。

### 8.4 正式报告字段

每个 arm×method 报告：

- received/planned、schema success、empty content、partial JSON、length finish、结构错误。
- known value、known grounding、unknown correctness、action correctness。
- fixed-reference change/preservation/provenance refresh。
- conditional self-error recovery，独立列分母，不并入方法主排名。
- per-storm 和 base/delay；有效回答条件指标仅作诊断。
- prompt/completion/reasoning tokens、cache metadata、传输时延、timeout、费用估计与未知预留。
- actual exposure audit ID、projection ID、score/version IDs、schedule completeness。

长度失败、结构失败与空输出可能重叠，报告归因规则，不把重叠计数再求和作独立失败总数。

### 8.5 预算选择

继续保持已冻结的 >=29/30 schema-valid、<=1 length/method 的共同预算筛选规则。只有完整、独立审计通过且 usage 合法的 270 响应矩阵才作正式选择；计数函数 `screen_budget` 仍只能给非认证诊断结果。[R4,R10]

- 4096 全部满足 → 共同选 4096。
- 否则 8192 全部满足 → 共同选 8192。
- 否则 → no_selection；保留结果，另立下一协议。
- 矩阵不完整 → incomplete/no_selection；不只重跑失败 cell。

此门槛是开发筛选标准，不是 95% 总体可靠性置信保证。

### 验收

完整演练报告只能显示程序结果，`live_collection_verified` 不可伪置 true。真实调用授权模板可生成但必须是 `authorized=false`；不提供会自动消费旧凭据/额度的后台启动脚本。

---

## 9. N4：授权后执行一次新的完整校准

这是独立的真实执行阶段。本计划编写时尚未授权或执行。

### 启动前必须绑定

- [ ] 代码、build、execution protocol 和三臂 schedule identity。
- [ ] provider model/config、共同 timeout/deadline、返回 metadata 验证。
- [ ] 官方价格/上下文/输出上限的当期快照；旧价格不自动沿用。
- [ ] USD 上限、请求次数上限、重试为零、允许的开发事件和方法。
- [ ] 新的唯一实验启动归属，不复用已消费的 P1 claim。
- [ ] 实际授权证据，不能由 Codex 根据“计划建议 USD 3”自行生成批准。
- [ ] 持久目录和断电/重启后可恢复记录位置。

若执行选项改变了旧 calibration 的 transport/价格假设，必须先得到新 execution 方案的确认，不静默覆盖。

不要求额外付费 canary。若确需 canary，应另立最小范围和授权，并明确其不计入 fresh 270 对照；不将它混入重复次数或偷偷超出270请求上限。

### 运行后解读决策树

1. 显式契约后各方法都接近满分：把 NHC 轨道定位为正确性控制，重点进入 P2；不能临时挑错题维持分差。
2. 4096 仍截断而 8192 通过：冻结共同 8192；增加预算不等于证明推理能力增强。
3. 两种 cap 都有严重格式/截断：另立协议比较输出接口或推理预算；不直接跑 heldout。
4. schema 有效但事实/来源出现差异：按具体字段和证据失败归因，再决定 P2 和第二模型。
5. 发生 transport/usage/budget 中断：发布完整失败分母的部分报告，不选择共同预算，不把未知收费当零。

---

## 10. P2 的设计：三个能力族，而不是扩出很多任务

### 10.1 两条轨道分别报告

**NHC 原文轨道**保留现有 `latest_available_report_not_same_valid_time_forecast_revision` 语义。

**Controlled Semantics V1** 明示使用生成的事实/修订/交付计划，研究公开协议下的版本解析与状态维护。来源可引用 NHC 模板风格，但生成的值和 correction 不伪装成官方历史记录。

P2 的程序、fixtures 和审计可在校准期间离线开发；真实推理使用校准后冻结的公共输出契约。

### 10.2 最小事实键与 schema

事实键：

```text
(entity_id, variable, valid_start, valid_end)
```

为降低实现成本，P2 V1 每条轨迹先固定一个 entity 和一个 valid window，仅 variable 不同。后续才扩多实体/多窗口。

使用四个数值字段：wind、latitude、longitude、pressure；不把永远未知的 port_reopening_time 作为 P2 主不足证据测试。

公共输入事件必须明确以下信息：

```json
{
  "protocol": "disastertrace_controlled_v1",
  "source_origin": "synthetic_record",
  "record_id": "r2",
  "entity_id": "E1",
  "issued_at": "2020-01-01T06:00:00Z",
  "delivered_at": "2020-01-01T06:01:00Z",
  "valid_window": {"start": "2020-01-02T00:00:00Z", "end": "2020-01-02T06:00:00Z"},
  "record_kind": "patch",
  "updates": [
    {"variable": "maximum_wind_mph", "value": 110, "unit": "mph", "supersedes": "r1:maximum_wind_mph"}
  ]
}
```

示例数值完全为协议演示生成，不能标成真实天气观测。

**先让输入支持 patch，模型输出仍提交完整 state。** 不要同时要求模型输出 JSON Patch 并让 harness 替模型补齐剩余状态；这样能避免把自动合并误当模型保持能力。

P2 单独的 parser/scorer 可以复用 `strict_json`、finite-number、hash 工具，但不能通过修改 V1 `FIELDS` 或 `reference_at()` 来偷换旧任务。

### 10.3 Family A：Partial Update & Provenance Preservation

示例：

```text
r1: wind=80, pressure=990, lat=20, lon=-70
r2: only wind=110; explicitly supersedes r1's wind fact
r3: only pressure=980; explicitly supersedes r1's pressure fact
```

r3 后参考：wind来自r2、pressure来自r3、坐标仍来自r1。遗漏表示不更新，不表示 unknown、清零或撤销。

必须覆盖：只改一个字段、改两个字段、no-op、迟到旧 patch、数值相同但来源升级。每个字段的来源独立维护，不能“所有字段统一引用最新 record”。

反例：latest-whole-record、clear-omitted、broadcast-one-source、overwrite-all-values。

### 10.4 Family B：Same-Window Correction & Stale Replay Resistance

同一事实键和同一 valid window：

```text
r1: wind=80
r2: wind=110; explicitly corrects r1
then r1 is delivered again
```

参考仍为 r2 的 110。交付时间较晚不使旧版本恢复权威。

包含一个值保持110但新的 correction version 成为权威的对照，用于区分值正确与来源正确；包含仅重复同一 record、不需要 provenance refresh 的对照。

V1 先限定单根、无分叉、无环的 correction chain。分叉优先级/无解冲突属于后续新协议，不能在 known/unknown 中随意编码。

### 10.5 Family C：Recoverable Missing Evidence

同一字段在匹配轨迹中分别有充分支持或暂时没有支持，之后再交付完整支持。

```text
branch A: wind evidence delivered at c1
branch B: all wind support withheld before first exposure, delivered at c3
```

c1–c2 两分支该字段参考不同；c3 后均可回答。pressure/coordinates 等不相关事实应保持。

必须隐藏全部支持：摘要、正文重复、表格、其他版本、metadata 与派生字段。不只是删一行。

**已经给模型看过的事实不能因后来文件暂时隐藏，就自动变成“应当未知”。** 这种设置测删除/检索，不是未获得证据；需要另外公开有效期/撤销语义。P2 V1 缺失从首次曝光前实施。

不允许把下载失败、parser failure 或 Gold 不确定改造成 unknown 题。那些是数据准入失败。

### 10.6 暂不加入

无优先级的真实来源冲突、自由文本因果解释、真实港口重开时刻、自然灾害损失预测、多实体多窗口组合、大量工具、长期记忆压缩、图像模型训练。

这些不是“不重要”，而是当前自动 Gold 不能可靠覆盖，且不是最快形成清晰研究贡献的路径。

---

## 11. P2 自动 Gold 的独立验证

### 11.1 双实现，而非生成器自证

- **Reference compiler A**：按可见版本关系维护每事实键的有效 value/source，计算 checkpoint state。
- **Audit oracle B**：在小规模输入上从所有已交付节点枚举该键的合法权威链终点，独立重算 value/source。
- **Runtime**：只维护可见输入和模型 carrier，不调用 compiler 的 Gold 来更正模型。

A 与 B 可共享数据 schema，但不能复用同一个 resolve_latest_fact 函数后宣称独立。让两端通过固定语义、手工写定的小型测试期待值及变形关系检查一致；这些是程序单元测试，不是新增逐题人工 benchmark 标注。

### 11.2 必要 metamorphic tests

- [ ] 重放旧版本不改变权威事实。
- [ ] 只改变到达时间且顺序/可见集合不变，不改变最终权威解析。
- [ ] 调整某支持的首次交付时间，仅影响它到达前需要该支持的 checkpoint。
- [ ] null update 不改语义状态；是否改 provenance 由显式版本语义决定。
- [ ] 改 wind 不应改变 pressure/coordinates。
- [ ] 改别的 entity/window 不影响目标键（先在单元测试覆盖，为后续版本做准备）。
- [ ] 同值新版本正确刷新来源；旧同值证据不能自动拿当前事实 credit。
- [ ] 移动文本与其 locator 一起移动，支持关系保持。
- [ ] 丢失所有支持前应 unknown；保留任意明确合法支持时不可错误标 unknown。
- [ ] 支持从未暴露与先暴露后隐藏的结果区别符合公开规则。
- [ ] correction cycle、未知 supersedes target、重复 ID 不同内容被拒绝。

### 11.3 程序控制矩阵

| 程序 | 用途 | 应在哪些机会失败 |
|---|---|---|
| specification-following | 正确性基准 | 不应失败；失败先查 benchmark |
| last-arrival-wins | 检测交付/权威混淆 | correction 后旧版本重放 |
| latest-whole-record | 检测字段级合并缺失 | partial patch 的未更新字段 |
| clear-omitted-fields | 检测错误 unknown | partial preservation |
| always-unknown | 检测固定拒答捷径 | 有支持及恢复后的字段 |
| always-known | 检测无支持猜答 | 缺失阶段 |
| correct-value-wrong-source | 检测只看数值的评分漏洞 | 来源刷新/同值新版本 |
| indiscriminate-update | 检测无关状态破坏 | 无关字段与 null controls |

每个能力族至少有一个定向 mutant 在预先指定的机会稳定失败，并保留 easy controls。不要为了让某模型低分删除其答对题目。

---

## 12. 实验规模、分母与停止条件

### 12.1 第一阶段校准

```text
3 arms × 3 methods × 3 dev storms × 2 branches × 5 checkpoints
= 270 fresh opportunities
```

一个 repeat、一个模型；描述性校准，不做总体显著性声明。

### 12.2 最小 P2 模型 smoke（建议值，待冻结与授权）

```text
3 capability families × 2 root scenarios
= 6 root scenario groups

6 roots × 2 matched branches × 6 checkpoints
= 72 checkpoint opportunities

72 × 3 methods × 1 model × 1 repeat = 216 requests
添加第二模型家族：再216，总计432 requests
```

这是 6 个受控 root groups，不是72独立事件，也不是足够证明广泛泛化的样本量。先用程序批量生成与测试更多候选；按预声明 seed、family、value ranges 和能力配额确定模型 smoke 子集。

第二模型具体名称、服务、推理选项和费用需要明确选择，不能使用未经确认的 placeholder 启动。不要把模型别名相同等同于底层版本永久不变。

### 12.3 现有 NHC heldout 的可选一次性评估

冻结契约、scorer、parser、模型与重复后：

```text
7 storms × 2 branches × 5 checkpoints = 70 opportunities / model / method

2 model families × 3 methods × 1 repeat = 420 requests
2 repeats = 840 requests
```

420/840 是请求数量，不是 independent n。7 个风暴的结果主要按事件展示；需要总体结论时先计划更多独立事件，不靠增加同事件 checkpoint 制造精度。

不能按模型或方法分别选“效果最好的 cap”。若不同模型使用不同 provider 限制，区分共同条件与适配条件，记录全部有效配置；不要声称 token 在跨 tokenizer 下代表相同计算量。

### 12.4 拆分与防泄漏

NHC 按 storm 分组，branch/checkpoint 不跨 split。Controlled 按 root/template lineage 分组，base/twin 不跨 split；仅换数字的模板派生不能算完全独立泛化。

已查看的 heldout 模型结果不可再参与协议优化后继续叫 confirmatory heldout。需要更改时保留旧结论为探索性，并另选未用测试组。

### 12.5 不用“必须看到失败”作为准入标准

优先 Gate：协议可验证、反例有效、分母清楚、执行完成与审计可信。模型全对也是有效结果。只有按预先定义的能力缺口升级任务，不按某模型失败来筛主评分题。

---

## 13. 指标与论文图表

### 保留的主指标

NHC 使用冻结 V2 known_grounded_accuracy 和固定分母。P2 对每事实键分别报告 value correctness 与 provenance correctness，并报告全分母联合正确率。

unknown 正确率、schema validity、action rule accuracy 独立呈现。不要把更高 unknown 占比变成总分优势。条件恢复率只诊断，不作为不同方法机会不等的主排名。

### P2 新指标（先写定义再实现）

- Partial-preservation success：Gold 未改且应继续可回答的字段，当前值及合法来源是否仍正确。
- Correction uptake：同事实键被更正后，当前答案是否采用合法新版本。
- Stale replay resistance：旧版本再到达后是否仍采用权威版本。
- Provenance refresh：数值不变但权威来源更新时是否正确引用。
- Answerability balanced accuracy：known 与 unknown 两条件分别计算后等权平均，保留原始分母。
- Recovery-after-delivery：原先不可回答、现在支持到达的固定机会是否恢复可回答。
- Unaffected-state stability：真正不受干预的键保持正确；不能奖励保留原错误。
- Paired-both-correct：base/twin 各自对其参考都正确，而非两答案相同。

没有机会的 rate 为 null，不能填0或1。不能把互相重叠的诊断分子相加作“总成功数”。

### 优先制作五张图/表

1. P1 → 新校准的失败分解：schema / length / fact / evidence 分别计数。
2. 三臂三方法的共同契约与预算对比，按三个风暴分面或分表，不附伪精确 p 值。
3. P2 能力族 × 方法/模型矩阵，程序控制单独区域。
4. 一对完整 base/twin 时序：到达、权威来源、模型答案、评分原因。
5. 质量–调用成本/实际输出 tokens 的描述性对比，未知费用单列。

NHC 当前的100mph rule action可能对数值错误不敏感，因此只作辅助任务，不能代表真实行动价值。[R5]

---

## 14. 可选载体机制实验：不列为首轮必做

当前 full-evidence 三方法不能证明 memory dependence。若后续确需机制结论，另立 finite-evidence 协议，并区分信息量变化与 carrier 质量。[R1,R5]

在同模型、同方法、同一已保存前缀处 fork：

```text
actual own carrier
carrier reset
target fact removed
target fact changed to a controlled wrong value
```

下一 checkpoint 的新 evidence、公共契约、预算保持一致，加入不相关字段控制。只记录外部载体干预的行为影响，不声称观察到模型内部记忆机制。

Oracle state 可作为单独标记的上界诊断，但不得混入普通模型轨迹；是否允许作为输入须单独预声明。无需为了本轮主论文上线复杂 hidden-transfer 平台。

---

## 15. 复现与交付：补足而不重新搭建

当前审查包已经有 `references/`、新环境验证和完整失败记录；下一步是规范化重复执行，不是从零修复“完全不可复现”。[R3,R6]

### 最小新增交付

- [ ] 一个不会访问模型网络的 CI/smoke 入口：安装 → tests → fresh build → prepare → verify。
- [ ] source content identity 与 execution location identity 分开记录；旧绝对路径不改写。
- [ ] 输出 root/index/manifest 明确哪些是当前、哪些历史、哪些 diagnostic、哪些 model results。
- [ ] 无凭据验证；扫描 Authorization/API key，不把 provider HTTP headers 原样入库。
- [ ] 新产生大文件用 manifest 索引，不无限复制整个历史代码和全部旧档案。
- [ ] 记录所有失败，避免清理时删掉对解释结果重要的 interrupted/invalid 原文。
- [ ] 对来源许可保持已有声明；当前私有审查不等于可公开再分发所有资料。

本阶段不需要上线 leaderboard、做前端、容器编排集群或导入170个工具。

---

## 16. 建议工作包与工期

以下为单开发者配合 Codex、现有环境可用时的粗略估算；不是完成承诺。数据/服务权限与授权等待不计入开发天数。

| 工作包 | 目标 | 预计工作量 | 停止点 |
|---|---|---:|---|
| N0 | 确认基线与离线复现 | 半天–1天 | 实际复核记录 |
| N1 | 契约感知 collector + 独立 audit | 1–2天 | fake transport完整270机会 |
| N2 | journal + 共享预算 + crash tests | 1–2天 | 可审计恢复/停止 |
| N3 | 统一执行协议 + 报告 + 预算认证 | 1天左右 | offline-live-ready，未授权不调用 |
| N4 | 新鲜校准 | 依响应时延与授权 | 完整结果或明确部分停止 |
| N5 | P2 schema、generator、双实现与mutants | 2–4天，可与N1–N3离线错峰 | 三能力族程序验证通过 |
| N6 | P2 smoke + 第二模型 | 另定调用额度 | 任务区分度与错误类型报告 |
| N7 | 一次性heldout、复现与论文表 | 1–3天工程工作，研究分析另计 | 冻结报告 |

不要在一次巨大改动中同时修改 source parser、live runner、scorer、dataset 和模型参数。每包完成后记录改动的层次和旧结果不变证据。

---

## 17. 下一轮默认必须停止的边界

完成以下五项即停止，输出可审阅包：

1. 新 collector 能通过 fake transport 执行完整三臂矩阵。
2. 独立 audit 验证 actual exposure 与自身真实风格的程序前缀（明确不是模型成绩）。
3. 共享账本与故障恢复测试完成，所有 uncertain requests 安全停留。
4. 报告与预算选择只接受可验证输入；projection 不冒充 exposure。
5. execution protocol、拟议启动范围、价格待刷新项与授权模板已生成。

本轮不自动：调用 DeepSeek、重跑原P1、补发未知请求79、跑heldout、下载权重、改原V2语法或推送远程。

P2 可输出离线规范或无网络 fixtures，但不因为 N1 完成而自动进入模型实验。

---

## 18. 对 review 八个问题的建议答案

| review 问题 | 建议 |
|---|---|
| 研究定位 | 现阶段是最新报告抽取/来源绑定与输出可靠性；P2 后可谈可执行动态证据更新。不要直接用多模态/真实行动定位 |
| 校准是否优先、三臂够不够 | 先校准；三臂足够识别指定简单对比，不识别交互。timeout运行前统一决定 |
| 固定分母是否合理 | 保留known-only主指标和失败分母；unknown/schema/有效回答条件分数单列 |
| 自动Gold可信边界 | 有限公开语义、双实现、负例和变形测试可支撑；不覆盖任意真实文本推理 |
| 投影评分 | 可作兼容层，但必须先独立认证actual wire/trace；永远保留两份身份 |
| 最小P2 | partial patch、same-window correction、recoverable missing；模型仍提交完整state |
| 实验与heldout | 先开发冻结再一次性heldout；第二模型比继续堆同模型近重复案例更值得优先；以storm/rootgroup统计 |
| 发布还缺什么 | 现有资料与新环境记录已在；补标准离线CI、身份/路径区分、运行索引和许可范围，不重建整个包 |

---

## 19. 可直接粘贴给 Codex 的执行提示

```text
请读取仓库根目录的 DisasterTrace_NEXT_STEPS_AFTER_REVIEW.md，执行其中
N0–N3 的离线增量工作，不要重新实现已有 starter，也不要只重复生成计划。

先读取所有适用 AGENTS.md、根README、REVIEW_FOR_CHATGPT_PRO.md、
IMPLEMENTATION_STATUS.md、DECISIONS.md、BLOCKERS.md、
CALIBRATION_PROTOCOL_V1.md 和 METRICS_V2.md。

本次审阅基线为 a23f73adadcbec077b9fcf2aecf8f45dfa4fe061。
若当前仓库更新，先列增量差异，跳过已经实现的部分，保护已有修改。

重点完成：
1. 使用 render_calibration_request 的契约感知 collector；
2. 独立 actual-exposure / wire-body / carrier 审计；
3. 单实验270机会的持久调度、单一累计费用账本、唯一launch claim；
4. 崩溃恢复、未知in-flight、安全停止和不自动重试的故障测试；
5. 审计后的独立scoring projection、完整分母report和可认证预算选择。

优先复用现有 provider.prepare/transport、动态解析、评分V2和调度实现。
禁止给 score_rehearsal 的程序轨迹伪造live标记。
禁止修改历史P1、原请求79的未知预留、原始回答或历史manifest。
保持旧V1/V2 parser/scorer与历史复现能力；新协议另立版本。

timeout/deadline改动必须写入新的execution协议；不得静默改旧冻结配置。
用fake transport和本地故障服务测试。默认不读取模型凭据、不调用付费API、
不重跑旧P1、不做heldout推理、不下载模型权重、不推送仓库或公开数据。

每个工作包记录实际命令、exit code、测试数、skip、失败原因和改动范围。
完成离线验收后停止，交付：新代码、测试、历史完整性检查、execution manifest、
授权待确认清单、实际未完成项。不要自行把 proposed allowance 写成授权。
```

---

## 20. 来源与审阅定位

所有仓库链接固定到本次审阅提交，不包含临时下载凭据。下列是本计划使用的主要依据；测试通过等数据属于仓库记录，而非本文编写者重新运行的结果。

- [R1 Review](https://github.com/sisuolv/disastertrace-benchmark/blob/a23f73adadcbec077b9fcf2aecf8f45dfa4fe061/disastertrace-starter/REVIEW_FOR_CHATGPT_PRO.md)
- [R2 P1 report](https://github.com/sisuolv/disastertrace-benchmark/blob/a23f73adadcbec077b9fcf2aecf8f45dfa4fe061/disastertrace-starter/work/p1-deepseek-background-continuation-v1/report/REPORT.md)
- [R3 Root README](https://github.com/sisuolv/disastertrace-benchmark/blob/a23f73adadcbec077b9fcf2aecf8f45dfa4fe061/README.md)
- [R4 Calibration protocol](https://github.com/sisuolv/disastertrace-benchmark/blob/a23f73adadcbec077b9fcf2aecf8f45dfa4fe061/disastertrace-starter/docs/CALIBRATION_PROTOCOL_V1.md)
- [R5 Metrics V2](https://github.com/sisuolv/disastertrace-benchmark/blob/a23f73adadcbec077b9fcf2aecf8f45dfa4fe061/disastertrace-starter/docs/METRICS_V2.md)
- [R6 Fresh-environment validation](https://github.com/sisuolv/disastertrace-benchmark/blob/a23f73adadcbec077b9fcf2aecf8f45dfa4fe061/handoff_validation/README.md)
- [R7 Dynamic task code](https://github.com/sisuolv/disastertrace-benchmark/blob/a23f73adadcbec077b9fcf2aecf8f45dfa4fe061/disastertrace-starter/src/disastertrace/automated/dynamic.py)
- [R8 Output contract](https://github.com/sisuolv/disastertrace-benchmark/blob/a23f73adadcbec077b9fcf2aecf8f45dfa4fe061/disastertrace-starter/src/disastertrace/automated/output_contract.py)
- [R9 Collection](https://github.com/sisuolv/disastertrace-benchmark/blob/a23f73adadcbec077b9fcf2aecf8f45dfa4fe061/disastertrace-starter/src/disastertrace/automated/collection.py)
- [R10 Calibration preparation](https://github.com/sisuolv/disastertrace-benchmark/blob/a23f73adadcbec077b9fcf2aecf8f45dfa4fe061/disastertrace-starter/src/disastertrace/automated/calibration.py)
- [R11 Current implementation status](https://github.com/sisuolv/disastertrace-benchmark/blob/a23f73adadcbec077b9fcf2aecf8f45dfa4fe061/disastertrace-starter/IMPLEMENTATION_STATUS.md)
- [R12 Provider transport](https://github.com/sisuolv/disastertrace-benchmark/blob/a23f73adadcbec077b9fcf2aecf8f45dfa4fe061/disastertrace-starter/src/disastertrace/automated/provider.py)
- [R13 Current blockers](https://github.com/sisuolv/disastertrace-benchmark/blob/a23f73adadcbec077b9fcf2aecf8f45dfa4fe061/disastertrace-starter/BLOCKERS.md)
- [R14 Incremental repository instructions](https://github.com/sisuolv/disastertrace-benchmark/blob/a23f73adadcbec077b9fcf2aecf8f45dfa4fe061/disastertrace-starter/AGENTS.md)
- [R15 Earlier optimization roadmap; status superseded by current review](https://github.com/sisuolv/disastertrace-benchmark/blob/a23f73adadcbec077b9fcf2aecf8f45dfa4fe061/disastertrace-starter/OPTIMIZATION_ROADMAP.md)
- [E1 Python urllib timeout semantics](https://docs.python.org/3.11/library/urllib.request.html)
- [E2 DeepSeek thinking-mode parameters](https://api-docs.deepseek.com/guides/thinking_mode/)

本文不声称穷尽最新相关研究，也没有对本仓库作安全认证。新增功能、工期、P2规模与240秒共同deadline均为审阅后的建议，需按明确的版本和执行范围落实。
