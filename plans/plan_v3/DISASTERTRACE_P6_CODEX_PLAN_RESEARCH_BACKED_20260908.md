# DisasterTrace P6：基于论文与开源实现的 Codex 增量执行计划

> 版本：`p6_research_backed_v1`  
> 编写及在线资料核查日期：2026-09-08  
> 项目：`sisuolv/disastertrace-benchmark`，分支 `next-phase-v1`  
> 已核对分支提交：`dd5ee358f9708e2eb2f2032db9eaac14fa237adc`  
> 本文件的性质：可执行工作说明与拟议实验协议；不是已实现代码、已通过测试或新模型实验结果。  
> 默认执行：CPU 离线分析、增量实现、测试、实验准备。不要启动 GPU/API、训练、下载权重、重启历史作业或发布资料。

## 给 Codex 的第一条指令

先读取本文件第 0–5 节，再按第 6 节的依赖实施任务。**不要只生成另一份计划，不要从最初 starter 重做项目。** 先完成 `T00–T07` 的离线交付；有可用资料时并行推进 `T10–T11`。每项任务先写可复现测试，再实现，再记录实际命令、结果和阻塞。没有新的 live scope 时，交付 `ready_not_launched`，继续完成其他离线任务。

本文件能独立使用；不需要把之前聊天复制给 Codex。文内 `[P…]` 对应当前项目资料；`[R…]` 对应第 12 节的在线原始论文、作者仓库与官方文档。文献支撑的是设计选择，不代表相关系统已经在本项目中复现。

---

## 0. 执行边界与历史保护

### 0.1 不得丢失的约束

1. 不新增逐题人工标注、专家逐题裁决或 LLM judge 主评分。主 Gold 和评分必须程序化；允许编写具有明确预期结果的软件测试夹具。
2. 不覆盖 P1–P5 的 raw responses、任务、Gold、原评分器、失败日志、授权、claim、历史源码副本或归档 manifest。
3. 本次已经消费的 P5 三个作业、P4 作业、T6/P2/P1 API scope 不得重启或复制后当作新授权。
4. 当前 `AGENTS.md` 含分阶段历史授权，按实际时间、适用范围和当前任务解析。过去允许私有 GitHub 上传或一定额度 GPU 使用，不等于本文件授权无限新增实验。
5. 模型只能收到已声明公开输入和该轨迹自身的合法 carrier。隐藏 Gold、未来交付计划、正确引用集合和私有错误标签不能进入模型输入或可访问工具。
6. 结构合法但事实错误的答案继续原样传播；无效答案保留失败，按冻结规则保持上一合法 carrier。禁止按 Gold 挑选“好的历史”。
7. 不把程序诊断、CPU 重算、模型重新采样、token-mask 复验混称为一种验证。
8. 不把生成 PATCH、2040 示例日期或受控交付称为 NHC 真实纠错或已证实的公众首次可见时刻。
9. 不提前运行原七个 heldout 的模型推理；不得用 heldout 结果选择模板、方法、预算或阈值。
10. 不顺便升级 P4/P5 的 vLLM/XGrammar、切换量化、增加 context 或接入完整 Agent 框架。
11. 本计划中的请求数只是候选范围，不是授权、费用上限保证或完成承诺。GPU 成本与付费 API 成本分开记录。
12. 本次只交付文件；没有重新跑项目完整测试、GPU 推理或全量 P5 归档复验。Codex 必须自行记录真正执行的检查。

### 0.2 当前工作区优先，审阅 SHA 不是回滚指令

从仓库根目录检查 `git status --short`、当前分支和 HEAD，读取所有适用 `AGENTS.md`。随后读取：

```text
disastertrace-starter/REVIEW_FOR_CHATGPT_PRO_P5.md
disastertrace-starter/README_P5_ACP_V1.md
disastertrace-starter/IMPLEMENTATION_STATUS.md
disastertrace-starter/DECISIONS.md
disastertrace-starter/BLOCKERS.md
disastertrace-starter/artifacts/p5_stress_level4_v1/REPRODUCE_ACP.md
disastertrace-starter/artifacts/p5_stress_level4_v1/NEXT_PHASE_PLAN_ACP.md
```

如果 HEAD 已更新，先生成差异清单，把已完成任务改为 `already_done_verified`，不要覆盖或重复实现。不要执行 `git reset --hard`，不要为贴合本计划而 checkout 掉用户修改。以下新增路径都只是建议；若已有等价模块，以最小改动接入并记录映射。

### 0.3 运行环境和网络

- CPU 审阅环境独立于原推理环境；离线测试禁止网络、模型凭据读取和隐式下载。
- 公开源码/官方资料获取属于单独 acquisition 步骤：只访问事先登记的公开 URL，保存来源、时间、字节和 hash。它不是模型调用。
- 资料未取得时写 `blocked_external_source`，不得造数据填补。可以用明确标为 synthetic 的测试夹具继续开发。
- 新模型运行必须有未消费且与冻结矩阵匹配的 scope；已有授权是否涵盖新矩阵不清楚时，只准备不启动。
- 不打印环境变量全集、不把 token 写入日志或下载链接，不修改仓库可见性。GitHub 上传/CI 另按有效权限执行。

---

## 1. 现在已经做成什么：后续任务的起点

以下是与审阅提交绑定的仓库报告事实，不是本文件新增的测试证据。[P01–P06]

| 项目 | 当前起点 | 后续不得误写为 |
|---|---|---|
| T6 | 270 个真实校准回答，选定共同 8192 输出上限 | 仍只有离线校准准备 |
| P2 | 自动 Gold、公有 oracle、U1/U2/U3；contract v2 在旧 270 版本上满分 | 新版 540/1620 矩阵的第二模型对照 |
| P3 | 540 个 Qwen3-8B 自由输出；200 合法、193 完整正确 | 仅报告 193/200 作为主成绩 |
| P4 | 540 个约束输出全部合法；490/540 完整正确 | 与 P5 同硬件同种子的因果对照 |
| P5 | 三因素各 540，共 1620；1360 完整正确；260 个错误 checkpoint | 1620 个独立天气事件 |
| 数据 | 三开发来源、36 episode、18 matched root、每条五 checkpoint | 广域多灾种、多模态预测 benchmark |
| 错误 | 90 值/状态字段错误；230 值正确但引用错误；动作错误29且与风速错误重叠 | 349 道独立错误题 |
| 信息访问 | 三方法都看到累计交付原文；carrier 不同 | 已隔离内部记忆因果优势 |
| 计算条件 | P4 H100 MIG；P5 full H100；factor-specific slot seed | 所有 P4→P5 降分均为压力因素效果 |

### 1.1 不变的 P5 计数核对点

```text
responses = 1620
contract_valid = 1620
all_correct = 1360
incorrect_checkpoints = 260
value_or_status_field_errors = 90
citation_only_field_errors = 230
all_field_errors = 320
known_field_opportunities = 5076
known_value_correct = 4986
known_grounded_correct = 4756
unknown_field_opportunities = 1404
unknown_correct = 1404
c0_all_correct = 324 / 324
post_c0_all_correct = 1036 / 1296
```

这些数值只用于**审阅 SHA 下冻结 P5**的回归核对，不允许硬编码为新数据评分器输出。发现不一致要停止发布诊断并调查，不修改旧回答来“对齐”。

### 1.2 当前最合理的研究定位

建议研究主线：**在受控记录流与真实天气预报资料中，LLM 能否保持事实值、作用域和当前权威证据的一致性？**

暂不声称：首个动态灾害 benchmark、天气预测能力、实际港口决策质量、内部记忆因果机制、不可简化的通用修订 DAG 推理，或已完成跨模态归因。[P01；R04–R08]

---

## 2. 文献怎样具体改变后续计划

### 2.1 三个主问题，而不是继续铺功能

- **RQ-A：数字正确但引用错误，究竟是哪类失败？** 用确定性后处理拆开错误记录、错误字段、作用域错配和过时同值来源，不改旧分数。依据 ALCE 对答案与引用维度的区分，但不采用其神经 NLI 判分。[R01]
- **RQ-B：显式状态载体的收益能否在匹配执行条件下复现？** 引入 repeat identity、成对采样、全过程失败分母与重复可靠性，参考 τ-bench/STATE-Bench；不能用更多重复冒充更多来源。[R03、R04、R12]
- **RQ-C：受控记录中的发现能否转移到真正的天气预报更新？** 从 NHC forecast advisory 的同绝对 valid time 入手，利用 EWB 的事件目录思路和 Tropycal 的 operational forecast 接口，而不是再拼很多静态 QA。[R08–R10]

次级问题：来源感知提示/公开验证工具是否改善引用维护；近作用域干扰是否仅是长度效应；已知记录的下游前提是否错误引用旧值。这些先在开发集单独验证，不全部做成首轮笛卡尔积。

### 2.2 复用矩阵

| 来源 | 已核查的参考入口 | 复用方式 | 明确不搬入 |
|---|---|---|---|
| ALCE [R01] | 作者仓库 `eval.py`，`compute_autoais`；ACL论文 | 答案正确性与引用质量分列、逐引用记录 | AutoAIS/NLI、整段自然语言 judge 作为主评分 |
| CheckList [R02] | README 的 MFT/INV/DIR 与 expectation 概念 | 最小功能、不变性、方向性三类测试规范；用现有 pytest 实现 | 整套历史依赖和自动改写导致的语义漂移 |
| τ-bench [R03] | 原始论文、作者 README 的重复可靠性 | pass^k 思想、每条任务独立重复和固定失败分母 | 用户模拟器、LLM错误归因器、旧领域任务 |
| STATE-Bench [R04] | Microsoft README、Main/Agent Learning tracks | 环境/任务/方法分离、重复与成本并列 | UX LLM judge、synthetic enterprise 标签到天气主表 |
| STALE/CUPMem [R05] | 论文 §3/§5、`cup_mem/README.md` | 当前状态裁决与历史归档分开；前提抗过时诊断；来源感知设计 | 人工隐式冲突标签、付费客户端、完整框架、声称已复现CUPMem |
| MemoryAgentBench [R06] | `agent.py`、`conversation_creator.py`入口和 `methods/` 目录说明 | 后置的增量观察/能力分层设计 | 当前就把全证据比较称为有限记忆实验；含judge的评测子集 |
| RULER [R07] | 作者 README、`scripts/` 生成流程 | 长度与任务复杂度分开、控制上下文预算、保留简单上界 | 把重复文本数直接当推理深度；把合成题替代真实验证 |
| ExtremeWeatherBench [R08] | 论文；README 所列 `src/extremeweatherbench/data/events.yaml` | 事件候选目录、分布记录、forecast/target 区分 | 大气模型重跑、ERA5全量下载、把RMSE移植成证据评分 |
| NHC [R09] | 产品说明、archive、Forecast/Advisory原文 | 原始资料、逐行引用、有效时刻和风速/阵风定义 | 把抓取时间当历史available；把best-track当当时预报 |
| Tropycal [R10] | `Storm.get_operational_forecasts()`、公开源码文档 | A-deck初始化/lead/aid 交叉核对与数据获取参考 | 默认下载全历史、把绘制的cone冒充原图、自动作为唯一Gold |
| XGrammar [R11] | 论文、作者仓库；本项目已冻结实现 | 保留结构约束与语义正确性的分层；schema可达错例 | 给grammar注入正确ID/数值/引用行范围；本轮升级依赖 |
| vLLM [R12] | v0.10.2 reproducibility文档 | 固定版本硬件调度、RNG隔离、共同profile | 相同seed必然相同结果或跨硬件一致性的承诺 |

**读取深度说明：** 本次核查了上述原始论文页面/部分HTML、作者README和所列代码/官方文档入口；没有执行上游测试或完整复现方法。部分路径来自README而非逐文件审计，Codex固定SHA后须确认。不得把 `README已指明` 写成 `已验证该模块可直接运行`。

### 2.3 必须纠正的上游版本假设

- EWB 作者 README 仍有“论文准备中”的文字，但已检索到 2026-05-01 的论文 `2605.01126`。文献记录以论文页为准，代码能力以固定提交为准。[R08]
- τ-bench 当前 README 已提示旧任务未更新并指向后续系列。这里只借鉴原论文的重复可靠性定义，不把旧 retail/airline 集当最新实现。[R03]
- Microsoft `STATE-Bench`、`StateMemBench` 和其他名为 StateBench 的项目不是同一个资源，不得混写作者、任务数或实现。
- 本次确认 STALE 作者仓库是 `icedreamc/STALE`；其自动生成/评测命令可能读取 `.env`、调用模型。只读设计，不直接运行上游 runner。[R05]
- 复用代码前记录 SHA、文件hash、许可证和修改范围；只有方法启发时写 `design_only`，不要强行制造代码依赖。

---

## 3. 增量架构：只增加四个研究模块

以下均为**拟新增路径**，相对于 `disastertrace-starter/`；已经存在等价实现时合并，勿平行复制。

```text
src/disastertrace/
  posthoc_p5/                  # 旧P5只读重算、引用错误与暴露诊断
    cli.py
    capture_loader.py
    citation_taxonomy.py
    exposure_slices.py
    behavioral_checks.py
    report.py
  repeat_eval/                 # 新实验、重复与成对执行；不改旧P5 freeze
    cli.py
    protocol.py
    schedule.py
    runtime.py
    audit.py
    statistics.py
    report.py
  provenance_methods/          # 独立新方法；绝不偷偷改旧structured_state
    typed_prompt.py
    public_guard.py
    receipt.py
  forecast_revision/           # 原始NHC同valid-time新轨；独立schema
    cli.py
    schema.py
    acquisition.py
    parser_blocks.py
    parser_independent.py
    temporal_join.py
    renderer.py
    scorer.py
    source_split.py

tests/p6/
  fixtures/
  test_citation_taxonomy.py
  test_exposure_slices.py
  test_behavioral_invariants.py
  test_repeat_schedule.py
  test_repeat_runtime.py
  test_repeat_audit.py
  test_statistics.py
  test_public_guard.py
  test_forecast_parsers.py
  test_temporal_join.py
  test_source_split.py

plans/p6/
  protocol_repeat_scope_v1.yaml
  source_registry.json
  acquisition_catalogue.json
  method_registry.json
  status.json

docs/p6/
  MEASUREMENT_SPEC.md
  EVIDENCE_ACCESS.md
  EXPERIMENT_PROTOCOL.md
  REAL_FORECAST_TRACK.md
  UPSTREAM_REUSE.md
  DECISIONS.md
  BLOCKERS.md
```

### 3.1 现有实现的复用边界

| 现有文件/目录 | 后续用途 |
|---|---|
| `controlled/compiler.py` | 冻结P5 Gold重建；不复制进方法当隐藏答案 |
| `controlled/public_oracle.py` | 独立公开求解核对和诊断上界；新方法依赖时必须标明工具帮助 |
| `controlled/renderer.py` | 旧三方法输入的字节级基线；不得替换历史请求 |
| `controlled/scorer.py` | 旧分数重算、固定机会计数；新诊断另存 |
| `local_eval/difficulty.py` | 旧变换原样复用，计算有效added records/deliveries |
| `stress_eval/data.py` | equal-Gold/base_slot映射和机会守恒 |
| `constrained_eval/contract.py`、`adapter.py` | 冻结结构grammar；新方法不增加答案相关约束 |
| `stress_eval/runtime.py`及已有capture/audit代码 | 提取真正可复用的捕获、journal和审计逻辑；重复协议单独版本 |
| P5 `execution_live/implementation_source/` | 重算历史运行时的真实代码来源，优先于后续工作区代码 |

不要重建数据库服务、LangGraph、Neo4j、全量EarthVerse或lmms-eval。JSONL/JSON加现有分析工具足够；大型上游仅作读取与设计参考。

---

## 4. 先冻结测量契约

### 4.1 事实和证据的三个层次

为一个输出字段分别记录：

```text
value_status_correct       是否等于当前任务Gold的值/状态
cited_value_supported      引文按公开语法是否支持该变量/作用域/数值
current_authority_correct  引文是否指向当前权威版本
```

P5主分数仍要求当前权威引用；第二项仅为诊断，不能放宽旧主评分。引用正确也不证明模型内部推理真的依赖了它，不使用“faithfulness已证明”等表述。[R01；P04]

### 4.2 字段级主错误类型与引用级细项

- 字段值/状态错误：归入旧90，保留额外引用诊断但不重复计入旧230。
- 字段值正确但grounding失败：归入旧230；每字段选一个主类型，另保留所有引用细项。
- 每个错误checkpoint只计一次；action错误是附加标签。

拟议主类型及固定优先顺序：

```text
missing_citation
record_not_in_public_view
unknown_record_id
out_of_bounds_line
non_assertion_or_unparseable_line
wrong_entity
wrong_valid_window_or_measurement_kind
wrong_variable_or_unit
superseded_different_value
superseded_same_value
wrong_value_on_same_key
other_unverifiable
```

实现时先做record存在/交付/locator检查再解析，不能因为底层实现抛异常就随意归类。`record_not_in_public_view` 与 `unknown_record_id` 需要结合完整评测manifest区分：诊断器可以读私有目录以定位原因，但这些标签绝不暴露给模型。若两项触发条件或顺序调整，在首次输出分类前固定。

多引用时“一个正确引用＋一个错误引用”仍是字段级失败。`citation_details`按每个ref记录；`primary_error`按冻结优先级选取；重复引用单独标记，不能扩大字段分母。

### 4.3 不变的全量分母和补充切片

同时报告：

1. 所有预定checkpoint；
2. c1–c4；
3. 候选因素已实际进入公共证据的checkpoint；
4. 处理前checkpoint；
5. 零增量episode；
6. 数值变化、同值来源刷新、无关已知字段保留；
7. 每来源、任务族、case、branch、方法、repeat。

互斥切片才能相加；多标签切片必须注明重叠。不要把任何分数变化自动归因于最近加入的资料；逐因素效果仍有采样和历史中介。

### 4.4 语义限制必须成为测试

P5每FactKey为单根非分叉链、子版本issue严格晚于父版本、父版本先交付，因而 `per-key-latest-issued` 可以满分。保留并验证这一事实，不故意改程序让它失败来制造难度。[P03、P05]

不要暗中把“迟到父版本”“分叉冲突”“取消/过期”纳入旧协议；旧validator拒绝这些输入是明确边界。新语义必须另立schema和Gold。日后真的加入冲突，才定义允许集合或conflict状态，不塞入numeric/unknown协议。

---

## 5. 实验清单：先小而完整，不展开所有因素

### 5.1 默认首轮 E1：同硬件范围干扰重复

```text
2条件(base, irrelevant_scope level4)
× 36 episode
× 5 checkpoint
× 3方法(snapshot, structured_state, answer_history)
× 2独立repeats
= 2160个新回答机会
```

选择scope是由已看的P5开发数据启发，必须写成后续开发假设，不伪装成首次未见数据的发现。保留全部36 episode，不能只挑P5做错的题。

E1测的是**这项记录扩充的整体影响及其重复波动**，并不独立识别“长度效应”和“作用域近似度效应”。两次重复也不支持强总体显著性。

### 5.2 只有要作更强机制主张时，才选择 E1-L 取代 E1

在新推理之前可以选择三条件：base、near-scope distractor、长度/记录数匹配的far-scope distractor，共 `3×540×2=3240` 个回答。[R07]

- near/far都不得改变target Gold；仅改变干扰与target的相似程度。
- 记录数、每条断言数、数值分布、参考ID长度、呈现顺序尽量匹配。
- tokenizer级长度容差在推理前固定；报告实际token差。禁止根据模型分数挑匹配样本。
- 不承诺模型历史也等长，因为前序回答会分叉；E1-L仍包含历史中介。
- E1-L是替代方案，不是E1某格不显著后再加的选择性补充。

默认只准备E1；E1-L只生成离线设计和报价/资源表，不自动执行。

### 5.3 后续 E2：来源感知方法验证

先完成T08/T09离线。新方法与同版本 `structured_state` 比较，base+scope、两重复时完整矩阵为 `2方法×2条件×36×5×2=1440` 个新回答。

若希望复用E1中structured_state作为共同控制，必须在E1采集前登记共用控制关系、相同输入/设置和统计依赖；否则单独采集。不得看过E1结果后把旧控制当并发独立对照。工具验证和repair版本不混成一个新方法。

### 5.4 后续 E3：真实预报资料小型验证

候选目标为4–6个通过准入且不与旧heldout冲突的开发风暴，每风暴至少两个共同绝对valid time、至少三份相关原始产品。先做离线准入，不保证所有候选都有合适数据。

任务数由准入结果决定。冻结后用实际 `N_opportunities×N_methods×N_models×N_repeats` 计算，不提前写一个保证的请求总量。初期不用全量气候数组、AIS或高成本重分析。

### 5.5 扩大到6480的条件

只有研究目标在采集前明确要求base+三因素的共同硬件重复，才执行 `4×540×3=6480`。更多重复仅补采样稳定性，不补独立来源和天气语义；不能用它替代E3。不得因显著性不足自动追加repeat。

---

## 6. Codex任务单：T00–T16

所有任务状态初始为 `planned`。每任务交付必须包含代码/文档差异、实际测试命令、退出码、输出路径与已知边界。任务数量不是代码或测试已经完成的声明。

### T00｜确认基线并建立只读证据索引

**依赖：** 无。 **优先级：** P0。 **模型调用：** 0。

- 核对HEAD、工作树、适用AGENTS和P5归档路径。读取源review与原始结果入口，不只用本文件摘要。
- 生成 `work/p6-baseline-<id>/baseline_inventory.json`，记录source commit、冻结执行ID、真实捕获位置、文件hash、可重算范围、缺失成员。
- 在独立CPU环境运行项目允许的现有测试；完整套件和新增suite分开记录。仅有轻量review包时不得声称完成全量capture复验。
- 按P5 REPRODUCE说明用冻结源码、新输出路径重建能访问的报告，不调用collect、launch或worker。
- 当前旧数值不一致时记录 `baseline_mismatch`，允许继续写纯夹具测试，但阻止发布以错误基线为起点的实测诊断。

**验收：** 原始历史文件hash不变；真实模型回答与diagnostic路径分清；缺失项有明确状态；没有新模型请求。

### T01｜固定论文与开源复用清单

**依赖：** T00。 **优先级：** P0。 **模型调用：** 0。

- 从第12节建立 `plans/p6/source_registry.json` 与 `docs/p6/UPSTREAM_REUSE.md`。
- 每个采用的代码片段记录 repository、resolved_commit、upstream_path、file_sha256、license、reuse_mode、local_destination、test。
- 本文件的资料登记不是完整vendor lock；尚未解析SHA的项必须为null并写 `pin_before_copy=true`。
- 除确实需要复制的解析/小工具外，以 `design_only` 为主。不安装STATE-Bench/CUPMem/MemoryAgentBench全套依赖。
- README和论文不一致时分开登记，不自动以“最近修改README”覆盖已存在论文。

**验收：** 复制的每个文件都有许可和固定版本；design-only项没有引入隐藏runtime依赖；没有自动执行上游示例命令。

### T02｜实现P5引用错误确定性分类

**依赖：** T00，规格第4.2节。 **优先级：** P0。 **模型调用：** 0。

**新增：** `posthoc_p5/capture_loader.py`、`citation_taxonomy.py`及对应测试。

- 加载每slot的真实public request、严格parsed output、冻结reference、旧字段评分。不得重新生成答案。
- 按原输出定位所有ref；所有检查只作posthoc，不输出“修正后的模型回答”。
- 输入缺失/invalid状态与引用错误区分。先复算旧分母，再细分旧230，不把旧90值错也计入230。
- 保存逐引用细项、字段级主类型、来源片段的locator/hash和支持判断理由。
- 对未知ID、未交付ID、行号越界、header行、错字段/单位、错scope、旧版本同值/异值、空引用、混合引用分别设最小fixture。

**交付：** `field_diagnostics.jsonl`、`citation_details.jsonl`、`conservation.json`、`CITATION_FINDINGS.md`。

**验收：** `90+230=320`、错误checkpoint=260；citation-only主分类和=230；旧得分逐项不变。不一致是失败，不自动“修复”历史。

### T03｜增加暴露、来源刷新和上下文诊断

**依赖：** T02。 **优先级：** P0。 **模型调用：** 0。

**新增：** `posthoc_p5/exposure_slices.py`、`report.py`。

- 复用旧base_slot映射，计算实际added records/deliveries、因素首次曝光checkpoint和零增量episode。
- 不仅用episode后缀或level判断作用；按实际delivered manifest判定。
- 将数值变化与同值证据刷新拆开；保留旧updates汇总及分解映射。
- 从实际token记录读取输入长度；tokenizer缺失时token字段为null，不把bytes/4当测量。
- 报告good→bad、bad→good、both-good、both-bad。P4/P5差异继续标为描述性。
- 来源级表、任务族表和checkpoint表均携带分子分母。相互重叠切片不能相加作总量。

**验收：** c0与post-c0回加到1620；互斥暴露切片完整覆盖；处理前片段不被解释成已受因素作用；六个chain零增量episode保留。

### T04｜按CheckList强化语义与防泄漏测试

**依赖：** T00/T01。 **优先级：** P0。 **模型调用：** 0。[R02、R07]

**新增：** `posthoc_p5/behavioral_checks.py`、程序化fixture生成器；不改旧数据。

- MFT：PATCH保留未变字段与原来源、同值revision必须刷新来源、scope隔离、unknown→known。
- INV：精确重放、无关记录、统一ID改名、等量时间平移、保持父先子后的无依赖交换。
- DIR：延迟全部首次支持时首次known不得提前；恢复支持后应重新可回答。
- 负例：非法parent未交付、分叉、cycle必须由旧validator拒绝；不能偷换为unknown Gold。
- 明确验证 `per-key-latest-issued` 当前全域/采样域的成功，不将简单满分上界隐藏。
- sentinel测试：私有Gold字段、未来ID、评分标签、source_group/episode元数据不得进入任何public请求或工具返回。
- Grammar可达错例：随机record_id、错值、负line等在结构层可能通过，但原任务/语义评分必须失败；正确答案不能被schema限定。

**验收：** 夹具与变形关系全过；程序错误控制在指定关系上失败；compiler与public oracle不共享核心resolver；测试报告说明覆盖域而不作形式证明承诺。

### T05｜冻结新重复协议与统计口径

**依赖：** T03/T04。 **优先级：** P0。 **模型调用：** 0。

**新增：** `repeat_eval/protocol.py`、`schedule.py`，`docs/p6/EXPERIMENT_PROTOCOL.md`。

- 默认选择E1=2160；E1-L或6480需要在任何新模型结果前替换配置并重新冻结。
- 新protocol记录model content identity、tokenizer、hardware profile、版本、grammar hash、context、输出cap、batch规则、RNG、重复数和分母。
- 区分 `trajectory_id`、`slot_id`、`attempt_id`、`pair_id` 和 `repeat_id`。
- 采样seed与运行身份分离，规则见第7节；禁止Python内置hash作跨进程稳定seed。
- 记录closed-loop总效应；不称为固定carrier的直接效应。
- 预定主指标仍为all-correct和known-grounded，另报repeat可靠性；不要按本次最高分选输出预算。
- 先做确定性profile可行性检查；如更改执行环境选项，所有新条件统一更改且不覆盖P5。

**验收：** 完整2160唯一slots、432条轨迹；每轨五顺序checkpoint；成对条件除显式因素外一致；未发送的后续请求只保存构造规范，不伪造未来真实carrier。

### T06｜实现repeat-aware采集、恢复和独立审计

**依赖：** T05。 **优先级：** P0。 **模型调用：** 0（mock/程序响应）。

**新增：** `repeat_eval/runtime.py`、`audit.py`；复用现有捕获基础。

- 只有不同轨迹可批处理；同轨下一checkpoint必须等当前响应接受处理后构造。
- 每repeat、condition、method有独立carrier。不得跨repeat复用答案cache，媒体/tokenization缓存必须不影响语义。
- 请求capture包含实际prompt hash、token IDs或可重建内容、输入receipt、carrier hash、model/grammar/settings、batch ID和seed。
- 每批先durably保存意图，之后dispatch；未知批次不自动重启。保存响应后再接受、记账/状态更新。
- 同一工作目录或claim重复启动必须失败。恢复已确认完整前缀可以不重发地重建状态；未确认远端结果不能猜测为未发送。
- 独立审计从冻结任务、交付计划和原始回答重建每轮请求，不相信collector预先写的state_after或success标记。
- 被测方法进程/对象只接收public request；Gold只能在独立评分/审计路径可用。不要把整份episode含Gold传给可自由调用工具的模型代理。

**验收：** 第9节恢复/篡改测试通过；错误合法状态被保留；invalid不晋升；未发送机会计数保留且错误来源标记为infrastructure；审计篡改一字节就失败。

### T07｜零模型调用完整排演与可移植报告

**依赖：** T06。 **优先级：** P0。 **模型调用：** 0。

- 对完整2160槽位至少用correct与invalid-control跑排演；报告实际program响应数，不能简称为“模型2160完成”。
- 用新统计模块重建来源×repeat×condition×method表及pass^k诊断。
- 进行CPU异地复制测试：屏蔽原路径、网络和权重，使用新输出目录重建报告。
- 首轮offline包包含任务映射、scope未授权状态、实际命令/日志、测试摘要、所有失败、manifest和下一命令。
- 实际tokenizer未取得时，结构/状态排演可完成，context-fit gate保持blocked；不可假装mock分词证明可运行。

**验收：** `offline_verified=true`；`model_calls=0`；满足全部live前置条件才标 `ready_not_launched`；缺哪项就准确标blocker，不虚构验收。

### T08｜最小来源感知Prompt方法

**依赖：** T02/T04；可与T05–T07并行。 **优先级：** P1。 **模型调用：** 0。

**新增：** `provenance_methods/typed_prompt.py`。

- 新方法ID `provenance_prompt_v1`，保留旧structured_state名称和实现。
- 公开instruction要求按实体/变量/窗口识别当前依据，并提醒同值修订也刷新来源；最终输出仍是原冻结schema。
- 不给出已填充状态，不给正确current-record名单，不改变grammar为动态enum。
- 不要求输出私有chain-of-thought；只要求可审计的最终值、状态和来源。额外解释不是主分。
- 存储上一模型提交时，value与其原始citation成对保存；不由程序替模型补上当前revision。
- 以实际请求diff证明本方法只改变公开提示或声明carrier呈现，记录新增token。

**验收：** 相同公开资料、旧评分器可评；没有Gold数据流；新方法不修改旧历史；correct/invalid fixture均可运行。

### T09｜公开来源验证工具的独立辅助方法

**依赖：** T08。 **优先级：** P1。 **模型调用：** 0。

**新增：** `provenance_methods/public_guard.py`、`receipt.py`。

- 新方法ID `public_guard_v1`，不能悄悄合并进旧Prompt baseline。
- 工具只检查已交付公开记录：ID/line存在、字段/单位、scope、版本权威性；返回规则错误码和被检查ref。
- 默认不返回Gold正确数值或正确引用，不自动改写答案。能够靠公开解析直接算对的完整方法，明确记为 `program_assisted`，不是模型自主能力。
- `repair_budget=0`作为首版。一次repair若后续开启，另立方法ID/预算/实验scope，保存初稿、反馈、最终稿和额外调用。
- 对“已合法错误答案是否被外部修复”保留前后分数；实验主表按预定算法端到端成本比较。

**验收：** public工具无法打开private或future；所有输出可由公开bytes独立核验；Gold路径替换为sentinel后工具结果不变。

### T10｜真实预报轨资料登记和小型快照

**依赖：** T01；与重复开发并行。 **优先级：** P1。 **模型调用：** 0。[R08–R10]

**新增：** `forecast_revision/acquisition.py`、`source_split.py`。

- 首先读取旧split实际storm IDs，预登记候选事件、年份/海盆/生命周期覆盖和替补顺序。不根据模型错误选事件。
- 第12节给出的NHC样例只是已阅读的开发示例；纳入前仍须排除旧heldout冲突，不宣称它们是未见测试来源。
- 优先少量Forecast/Advisory原文；从官方事件索引解析真实链接，不猜完整文件清单。
- 每份保存原始HTML、规范化文本、原文字节hash、canonical文本hash、line mapping、URL、HTTP结果、retrieved_at、issued_at和availability证据等级。
- 采集失败/格式不支持属于拒收或quarantine，不伪造“应答unknown”的模型样本。
- Tropycal仅作A-deck参考/交叉核对适配；默认不运行其会全量下载的接口。不把best-track/reanalysis加载给模型。

**验收：** 资料清单先于模型运行冻结；每文件可追源；不与旧heldout共用事件；没有用本次抓取时刻替代历史available_at。

### T11｜两个独立NHC解析器与时间对齐

**依赖：** T10资料；无资料时先做synthetic fixtures。 **优先级：** P1。

**新增：** `schema.py`、`parser_blocks.py`、`parser_independent.py`、`temporal_join.py`。

- A实现按段状态机读取 `FORECAST VALID/OUTLOOK VALID`及随后MAX WIND/GUSTS/坐标。
- B实现从原文独立提取块并解析日期、单位和字段，不调用A的日期解析/状态选择函数；可以共享文件读取和hash。
- 单独表示issued_at、forecast_reference_at/init_time、valid_at和delivered_at；不得假设ATCF tau等于valid_at减产品发布时间。
- 同一valid_at比较可以跨不相邻advisory；找真实共同绝对时刻，不能强行把两个+24h视为相同target。
- 跨月/跨年/闰日、`DD/HHMMZ`恢复必须有唯一合法日历解释和冻结最大产品时域约束；不唯一就quarantine。
- 分开持续风、阵风、移动速度；KT与mph不混用。先使用原生KT任务，不为了沿用100mph规则做隐式换算。
- 同文本的当前观测、过去定位、未来预报分别typed；两解析器都保留引用位置与原文片段hash。
- A-deck为辅助来源，不作为唯一第二Gold；aid、reference time、tau、raw product配对均需验证，避免混用插值产品。

**验收：** 共享输入但独立解析，按全部准入事实一致；任何不一致记录到quarantine；至少覆盖第9节天气时间/变量测试。不得为凑事件数放松解析。

### T12｜同有效时刻的真实资料Benchmark桥接轨

**依赖：** T11。 **优先级：** P1。 **模型调用：** 0。

**新增：** `forecast_revision/renderer.py`、`scorer.py`、`docs/p6/REAL_FORECAST_TRACK.md`。

- 新协议 `forecast_revision_v1`，不修改旧受控四字段schema。
- 初版目标是指定风暴、产品语义、绝对valid_at下的最新已交付预报；字段可为 `max_sustained_wind_kt`、`gust_kt`、`latitude_deg`、`longitude_deg`。
- Forecast Advisory通常没有相同形式的未来最低气压，不能把当前pressure填作未来forecast pressure。新轨不强行继承旧pressure字段。
- 本轨不评旧100mph action，不声称应急建议；动作/风险计算留待独立且可执行的研究规则。
- `latest_for_key`从已交付且明确覆盖key的事实中选取。新产品遗漏目标valid_at不自动撤销旧预测；本规则在prompt中明示且不冒充官方取消规定。
- 同一时刻的特殊更正/同号版本没有确定优先级时隔离；不要靠字母排序瞎猜权威版本。
- 冻结Raw与Typed两种输入：Raw保留原文；Typed由程序提取全部准入事实，不只给目标答案。Typed是程序辅助的信息投影，不声称等价保留原文所有语义。
- 真实raw轨原文不改数值；反事实/重命名/延迟另标 `controlled_variant`。
- 同值版本引用、同valid time变化、不同valid time不覆盖、缺失/恢复有对应程序验证。

**验收：** 原始证据可确定性支持每个Gold；任务是“读预报、追更新”而不是“预测天气”；全体候选/准入/拒收有账；新数据不混入旧P5主分。

### T13｜第二模型能力清单与适配，暂不调用

**依赖：** T07，至少一个冻结任务版本。 **优先级：** P1。

- 复用当前ModelAdapter入口，不把新的供应商参数散落进runner。
- 记录权重/服务身份、tokenizer、license、context、output cap、thinking策略、grammar支持、调用成本口径。
- 第二家族必须真的不同；同Qwen家族大小变体只能称规模对照。
- 本文件不虚构可用模型或推荐未核验价格。先从用户已有且许可匹配的模型清单解析选择；缺失就 `blocked_model_selection`，继续CPU准备。
- 普通JSON mode与strict grammar不等价；分别保存 `free/json/grammar` 条件，不能把较强结构帮助藏进模型比较。
- 第二模型使用完全相同的任务内容和独立响应，旧DeepSeek270不填进新版矩阵。

**验收：** mock能力与解析测试通过；没有读key、下载权重或生成回答；若需要不同推理环境，隔离并冻结，而非破坏历史环境。

### T14｜版本化报告、CI与发布前审计

**依赖：** T02/T07；真实轨部分依赖T12。 **优先级：** P1。

- 新表始终标明task_content_id、scorer_id、method_id、model_id、output_track、runtime profile和repeat范围。
- CI默认仅CPU无网fixtures；模型实测验证为单独可选job，不能让PR触发GPU或API。
- 现有权限缺workflow时交付CI模板与本地执行记录，不能声称hosted CI通过。
- 代码、任务标注、模型和第三方资料分别登记许可；可再分发不明确时发布manifest/下载器而非直接打包原文。
- 新文档/实现引用旧归档路径，但不改写旧manifest。旧全仓库export清单不代表新P6包。
- 明确测试数、自动检查数、程序输出数、真实模型响应数和独立来源数，不能相加。

**验收：** 新CPU环境能按README重建可用部分；包里无凭据/权重/未来泄漏；manifest与实际成员一致；有未运行范围说明。

### T15｜执行新live矩阵：只在匹配scope下

**依赖：** T00–T07全部gate与实际新scope；E2/E3还需各自gate。 **优先级：** gated。

- 先绑定新的run path、最大机会/attempt、资源上限、截止条件、失败处理、数据/模型/环境身份。
- 旧授权和旧consumed claim不能重用。generation-disabled GPU preflight也消耗资源，须在scope内。
- E1默认单full-H100 profile、TP1、batch不超过12，不再拿旧MIG基础表充作并发对照。扩并发时每worker必须有条件轮换，不能让因素永久绑定某张卡。
- 同一模型完整执行冻结方法/条件/repeats；不只重跑失败cell。没有足够资源完成时保留未提交机会并报告不完整。
- 所有repeats新采样，不使用历史输出缓存。未知请求/批次不自动重试。
- 运行后独立audit、report和迁移重算；只有通过这些检查才标 `completed_audited`。

**验收：** 实际机会覆盖、错误、usage/resource日志和停止状态可审计；没有结果驱动的增补；不完整矩阵不据此挑共同方法/预算或做正式排名。

### T16｜可选有限证据与前提抗过时诊断，不进入首轮

**依赖：** 引用错误已理解、重复设计可用、独立小协议冻结。 **优先级：** P2。[R05、R06]

- 前提探针：给一个公开记录已能判定过时的明确候选状态，让模型输出结构化判断与支持；用自动规则判定，不复制STALE需常识/人工裁决的场景。
- 有限窗口轨另定义什么是“曾曝光证据”及历史citation receipt；过去合法看过的有效事实不因当前raw不可见就自动unknown。
- 因果载体诊断从同一真实prefix分叉 actual/reset/delete/edited，当前证据保持一致，增加不相关字段控制。
- 编辑载体的值只是干预，不是权威事实；新公开证据足够时应纠正错误carrier。禁止用“跟随错误carrier越多越好”作可靠性指标。
- 共前缀fork用于机制实验，不当独立repeat；多个repeat必须有各自重新采样prefix。
- Snapshot被剥夺历史后信息更少，其低分不能直接解释为记忆质量差。保留全证据参考。

**验收：** 新信息访问协议可执行、无私有Gold输入、正确行为有程序Oracle、所有诊断单独计费和报告。没有这些条件时延后，不阻塞主线。


---

## 7. 给实现者的接口、身份与配置契约

以下是**目标接口，不是已经存在的可执行 API**。复用现有类型时保留同等约束，并在 `DECISIONS.md` 记录映射；不要同时维护两套意思相同的类型。

### 7.1 只读分析与模型工具必须分开

```text
PosthocAuditInput:
  frozen_execution_ref
  public_request
  raw_response
  recorded_score
  private_reference          # 仅离线评分侧可有
  source_hashes

PublicGuardInput:
  public_request             # 实际交付证据及公开任务说明
  submitted_decision
  exposure_receipt
  # 禁止 private_reference / future_schedule / gold_citation_set
```

`posthoc_p5` 可以为研究分析读取隐藏参考；`provenance_methods/public_guard.py` 不能。测试使用私有 canary，确保它不会通过异常、工具返回、检索索引、缓存键的可读说明或日志回传给模型。不要把“同一 evaluator 进程持有 Gold”误当成自动泄漏，也不能仅靠 prompt 的一句禁止访问证明隔离有效。

字段级诊断记录至少具有：

```json
{
  "diagnostic_version": "citation_taxonomy_v1",
  "execution_id": "bound-at-runtime",
  "slot_id": "bound-at-runtime",
  "field": "maximum_wind_mph",
  "legacy_value_correct": true,
  "legacy_grounded_correct": false,
  "primary_error": "superseded_same_value",
  "citation_details": [],
  "request_sha256": "bound-at-runtime",
  "raw_response_sha256": "bound-at-runtime",
  "scorer_id": "frozen-original-scorer",
  "changes_original_score": false
}
```

这里展示的是 schema 形状，不是新增真实错误记录。每条分类必须能回溯到一个原始 slot/field；主标签采用第4节固定规则，多引用细项可多标签，但字段错误计数不重复。

### 7.2 新重复协议示例

建议写入 `plans/p6/protocol_repeat_scope_v1.yaml`。`null` 表示必须由本机只读检查绑定，不能用字符串占位值通过 live 校验。

```yaml
protocol_version: p6_repeat_scope_v1
experiment_id: p6-e1-base-scope-r2
status: draft_offline
research_question: scope_interference_under_matched_execution
review_base_commit: dd5ee358f9708e2eb2f2032db9eaac14fa237adc

matrix:
  conditions: [base, irrelevant_scope_level4]
  methods: [snapshot, structured_state, answer_history]
  repeats: [0, 1]
  source_groups: [AL092021, AL062018, AL052019]
  base_episode_count: 36
  checkpoints_per_episode: 5
  planned_trajectories: 432
  planned_responses: 2160
  task_content_id: null
  treatment_selection: all_base_episodes_no_model_failure_filter

randomness:
  seed_version: paired_seed_v1
  experiment_seed: 60719
  schedule_seed: 60720
  paired_seed_fields: [base_episode_id, method, repeat, checkpoint_id]
  condition_in_sampling_seed: false
  condition_in_trajectory_id: true
  engine_seed: 60721
  generation_result_cache: disabled

runtime:
  hardware_profile: full_H100_80GB_single_gpu
  gpu_profile_verified: false
  model_snapshot_sha256: null
  tokenizer_snapshot_sha256: null
  python: "3.10.12"
  torch: "2.8.0+cu128"
  vllm: "0.10.2"
  xgrammar: "0.1.23"
  precision: bf16
  tensor_parallel_size: 1
  max_independent_trajectories_per_batch: 12
  context_tokens: 16384
  max_total_generation_tokens: 8192
  full_output_reservation_required: true
  truncation: forbidden
  temperature: 0.6
  top_p: 0.95
  top_k: 20
  min_p: 0
  repetition_penalty: 1
  thinking: enabled
  output_track: inherited_structure_only_grammar
  v1_multiprocessing_policy: null
  condition_order: preregistered_rotation

failure_policy:
  automatic_retry: false
  response_repair: false
  propagate_schema_valid_wrong_answers: true
  invalid_answer_carrier: retain_last_schema_valid
  uncertain_inflight: stop_and_preserve
  omitted_opportunities: retain_in_full_denominator

authorization:
  model_generation_authorized: false
  gpu_preflight_authorized: false
  paid_api_authorized: false
  scope_record: null
  max_attempts: null
  max_parallel_gpus: null
  deadline_utc: null
```

`2160` 是 E1 的矩阵验证断言，不应成为通用 runtime 的魔法常数；其他实验使用同一计算器核对自己的矩阵。当前旧执行器的 `540/repeats=1` 固定合同不改变。

`max_total_generation_tokens=8192` 同时包含 reasoning 与 final。输出预留总额为 **17,694,720 tokens**，不是预期实际消耗，更不是 GPU 费用。其他预设矩阵分别为：E1-L 的 3240 → 26,542,080；E2 的 1440 → 11,796,480；完整四条件三重复的 6480 → 53,084,160。每种矩阵都需要自己的 scope，不能相加当默认授权。

### 7.3 稳定种子不等于可复现保证

推荐的纯函数接口：

```python
# 设计示意；实现时为输入约束、跨进程稳定性及碰撞检查补测试。
from hashlib import sha256
import json


def paired_seed(experiment_seed: int, *, base_episode_id: str,
                method: str, repeat: int, checkpoint_id: str) -> int:
    payload = {
        "seed_version": "paired_seed_v1",
        "experiment_seed": experiment_seed,
        "base_episode_id": base_episode_id,
        "method": method,
        "repeat": repeat,
        "checkpoint_id": checkpoint_id,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return int.from_bytes(sha256(raw).digest()[:8], "big") % (2**31 - 1)
```

同一配对 slot 跨条件种子相同；不同 repeat 的 key 不同。有限位种子理论上可能碰撞，所以冻结 schedule 时要检查不同独立采样 key 的冲突；检测到冲突应修改并重新冻结整个 seed 协议，不能运行中只改某个失败样本。不要使用受进程影响的 Python `hash()`。

生成器 seed、schedule seed、engine seed、每请求 sampling seed 分开存储。生成 schedule 使用独立 `random.Random(schedule_seed)`，不要让 vLLM 初始化改变全局 RNG 后悄悄改变实验顺序。[R12]

vLLM v0.10.2 的文档指出，同硬件同版本及调度配置是可复现性的必要背景，在线调度不能任意假定可复现。若采用 `VLLM_ENABLE_V1_MULTIPROCESSING=0`，必须将它作为**新共同 runtime profile**记录，所有新条件相同；不能声称历史 P4/P5 已经使用该设置。[R12]

### 7.4 调度与缓存

- 同一轨迹只能按 c0→c4 串行；同 checkpoint 波次可并行不同轨迹。
- 每个 repeat 重新采样完整 prefix，不复用旧答案。共前缀 fork 是另一种机制实验，不能与独立重复混写。
- 配对条件在处理前应有相同任务证据与提示；实际 carrier 是否一致由采集记录验证，不强行替换模型历史以制造一致。
- 记录 `batch_id`、成员、顺序、GPU UUID/配置、实际时间、输入/输出 tokens。条件顺序按来源/repeat预设轮换，不能永久由卡号决定条件。
- 输入图像编码/资料解析等纯函数缓存可以保留；真实模型 response cache 关闭。Provider 的内部前缀缓存可能不可控制，记录可见信息，不伪称完全消除。
- 使用真实 tokenizer 和 chat template 检查每次请求的 token 数，保留完整8192生成空间；含真实 carrier 的后续请求无法提前全部冻结，必须在运行时检查。
- `prompt_tokens + 8192 > 16384` 时按冻结规则记为 context 失败/停止；不得按样本删证据、削减输出或丢最旧历史。

### 7.5 意图、响应和接受状态

```text
PLANNED
  → PREPARED_AND_HASHED
  → DISPATCH_INTENT_DURABLE
  → RAW_RESPONSE_DURABLE
  → ACCEPTED_SCHEMA_VALID / RECEIVED_INVALID
  → SCORED_OFFLINE

DISPATCH_INTENT_DURABLE 后没有确定响应
  → OUTCOME_UNKNOWN
  → STOPPED_PENDING_REVIEW
```

无效回答与未知远端结果不同：前者是收到的模型失败；后者可能已使用计算资源而缺少可确认输出。所有机会保留；不自动重试。批次部分成功时逐slot记录，不把整个批次误标为成功或全部未发。

恢复只能使用独立 audit 验证的已保存前缀，原 capture 只读。Hash 验证提供一致性和篡改检测，不是对模型服务或第三方真实性的密码学认证。

### 7.6 真实天气新轨的核心类型

```text
ForecastFactKey:
  storm_id
  product_type
  measurement_kind             # forecast，不与observation混用
  variable                     # max_sustained_wind_kt/gust_kt/latitude_deg/longitude_deg
  valid_at_utc                 # 单时刻，不复用controlled半开窗口的全部语义

ForecastEvidence:
  artifact_id
  issued_at_utc
  initialization_at_utc        # 可空，但不可静默设为issued_at
  available_at_min/max         # 证据支持不了就空并降低claim grade
  source_sha256
  raw_line_start/end
  raw_excerpt
  fact_key
  canonical_value
  canonical_unit
  parser_version

ForecastQuery:
  target_key
  checkpoint_time
  exposure_policy_id
  selection_semantics_id       # 最新已交付且明确覆盖该key的产品
```

已在线查看的两份 2024 AL06 forecast advisory 可用作开发 parser 夹具：对 `2024-09-10T06:00:00Z`，001 的最大风预报是45KT，003为55KT。[R09] 这不是未见事件，应在 `source_split` 标 `already_inspected_development_candidate`；先与既有七个heldout核对。若冲突，不将它加入新模型dev或用它调整主parser，仅登记冲突并另选来源。

针对两份资料的检查应通过原行定位与原始hash产生，不把45/55写成通用Gold逻辑。其预报初始化/有效时间和发布时刻分别解析。真实数据中只有相同绝对valid time才能组成修订对，不靠插值凑齐。

---

## 8. 指标与统计：实现前必须写进协议

### 8.1 三种单位分别保留

1. **Checkpoint 成功**：冻结 scorer 的 `all_correct`；P5和E1的主指标保持不变。
2. **Episode 成功**：该条五检查点轨迹全部正确；这是新增严格诊断，分母为episode。
3. **跨重复可靠性**：同一任务在多个独立采样重复中均成功；分母仍是预定义任务，而非把重复当新风暴。[R03、R04]

对每个方法/条件报告完整计数、来源macro、family、case、branch、checkpoint和repeat。结构成功、已知值、已知当前引用、未知状态、语义更新、同值来源刷新、无关保留、动作和成本分别列出，不只给一个总分。

### 8.2 `pass^k` 不是 `pass@k`

令一个固定episode在R个独立重复中有c个完整成功。若R≥k，可报告对应全部k次成功的组合估计：

```text
pass^k_episode = C(c, k) / C(R, k)
```

然后对预先规定的episode集合聚合。R=2、k=2时，只有两次都成功才取1。不能把平均checkpoint正确率平方，冒充episode级 `pass^2`。

`pass@k` 是至少一次成功的另一指标，不应当作“重复稳定性”。R<k时记null，不外推不存在的重复。推理结果缓存返回旧答案不是独立重复。[R03]

基础设施导致未完成时，完整分母的端到端成功率可以把未交付机会保留为失败；但必须同时标 `incomplete_infrastructure`。不能将其中的语义可靠性估计当作完整、可比的模型排名，不能用只剩完整pair的子集悄悄替换主集合。

### 8.3 双向配对变化

对于同方法、base_episode、checkpoint、repeat的一对Base/Stress，保存四格：

```text
both_correct
base_correct_stress_wrong
base_wrong_stress_correct
both_wrong
```

净差 `stress - base` 之外，必须报告两个反向变化数。处理前、有效处理后和零增量控制分别展示；还需展示哪些case因前序模型答案不同而出现carrier分叉。

当前端到端比较估计的是整条策略在处理条件下的总变化，包含历史载体中介路径；它不是固定同一历史下的单checkpoint直接效应。后者必须用另立的共同prefix干预。

### 8.4 三个来源不能制造精确总体结论

E1的三个源组优先报告逐来源、逐repeat计数和差值，附均值与范围；不默认附人口级p值或“统计显著”。同一源组派生的root、branch、stress variant和repeat不能当独立storm。

以后扩充来源，按预登记的独立来源组做paired cluster bootstrap；所有该组variant随组一起重采样，采样seed固定。模板/生成器仍共享时，需要把“来源数增加”与“语义多样性增加”分开说明。置信区间实现通过确定性toy数组测试，不用本次三组结果调统计方案。[R04、R08]

### 8.5 性能、费用和帮助层级

- 保存真实 `prompt_tokens`、`reasoning_tokens`、`final_tokens`、`total_generation_tokens`；reasoning已含在generation时不重复加。
- GPU批次墙钟、整个采集进程耗时、单请求服务时延分开；共享batch时间不能平均后伪称单请求纯推理时延。
- 无付费API不等于无计算费用；未知GPU货币成本写unknown。
- 提示增强、公开确定性工具、一次repair、strict grammar分别标记。额外工具/repair调用全部纳入预算，不能仅对最终成功答案报成本。
- 若公共工具直接执行当前任务的精确resolver并给出完整答案，这是有效的工具/程序上界，而不是新的LLM推理能力证据。

### 8.6 主表与附表的建议输出

```text
Table A: 冻结P5错误守恒与细分类（不改旧分数）
Table B: E1各来源/方法/条件/repeat的固定分母成绩
Table C: 双向pair变化、pre-exposure/treated/zero-effect切片
Table D: episode-level success与pass^2，包含不完整状态
Table E: 方法帮助层级、token、工具调用、硬件profile
Table F: 真实forecast轨的源覆盖、拒收、same-valid-time对数
```

每张表带 `content_id/scorer_id/model_id/output_track/runtime_id`。事实数值错误、引用错误和动作错误不相加成独立错题。结果中不存在的条件不得从历史不同版本补表。

---

## 9. 最低行为验收清单：60 个场景

这些是**需要实现并实际运行的验收场景**，不是已通过测试。可以参数化为更多pytest用例，但不得把下表数量直接写为测试通过数。

### 9.1 版本、权限与数据边界（A01–A08）

| ID | 场景 | 必须观察到的结果 |
|---|---|---|
| A01 | HEAD比审阅SHA更新且有本地修改 | 报告差异，不回滚、不覆盖 |
| A02 | 请求旧已消费P5 claim作为新任务 | 拒绝启动；保留旧目录 |
| A03 | 无授权调用live入口 | 明确拒绝；CPU prepare仍可用 |
| A04 | 只读posthoc运行前后对旧文件hash | 完全不变；新产物在新目录 |
| A05 | 私有Gold canary置入评分目录 | 模型请求/工具结果/可读缓存中没有canary |
| A06 | 故意加入未来delivery metadata | 公共投影拒绝或排除，审计可识别 |
| A07 | 原始捕获缺文件或digest不匹配 | 不生成verified报告；给出缺失项 |
| A08 | 离线测试环境有key和网络可用 | 测试仍禁止读key/网络，无隐式下载 |

### 9.2 引用与计数（C01–C12）

| ID | 场景 | 必须观察到的结果 |
|---|---|---|
| C01 | 值正确、当前ASSERT正确 | 与旧scorer一致通过 |
| C02 | 值正确、evidence为空 | missing_citation，保持旧grounding失败 |
| C03 | 同record的header行被引用 | 不是字段支持；明确标签 |
| C04 | 同数值但引用其他变量 | wrong_variable_or_unit，不因数值巧合通过 |
| C05 | 同数值但另一实体 | wrong_entity |
| C06 | 同实体但另一有效窗口 | wrong_valid_window_or_measurement_kind；不依据字段名直接匹配 |
| C07 | superseded旧版本与当前同值 | 当前authority失败；同值支持诊断可另记 |
| C08 | superseded旧版本与当前异值 | 记录过时异值；不写成未知ID |
| C09 | 已知record但未在该请求交付 | record_not_in_public_view，不靠全量数据绕过 |
| C10 | 不存在record或行越界 | unknown_record_id与out_of_bounds_line分别记录 |
| C11 | 一个正确引用混一个无效引用 | 字段主分仍失败，多引用细项完整保留 |
| C12 | 值也错误且引用也错误 | 算入90类而非再算入230；320字段/260cp守恒 |

### 9.3 身份、采样、调度与恢复（RT01–RT14）

此处 `RTxx` 是测试前缀，与第12节的文献索引 `Rxx` 区分。

| ID | 场景 | 必须观察到的结果 |
|---|---|---|
| RT01 | 展开E1矩阵 | 2160唯一slots、432唯一trajectories、各自5cp |
| RT02 | 同配对slot跨condition | seed相同，trajectory/slot ID不同 |
| RT03 | 不同repeat相同其他字段 | 独立身份和重新采样；禁止response cache命中 |
| RT04 | 不同进程重建schedule | 字节/digest一致；不依赖Python hash随机化 |
| RT05 | vLLM初始化改变全局RNG | 冻结schedule不变；专用RNG隔离 |
| RT06 | 任意提前提交同轨迹c2 | 拒绝，必须先处理c1接受状态 |
| RT07 | other method/condition/repeat的carrier注入 | audit失败；不允许仅同episode就复用 |
| RT08 | schema合法但答案错误 | 原样进入后续carrier |
| RT09 | 无效JSON答案 | 机会失败、raw保留、上一合法carrier保留 |
| RT10 | 发送意图后进程崩溃，无响应 | unknown并停，不自动重发 |
| RT11 | raw已落盘但接受状态未写完 | 独立解析恢复，不再次生成 |
| RT12 | 两个launcher竞争一个run | 仅一个成功claim，其他拒绝 |
| RT13 | batch中部分slot有响应 | 按slot记录成功/未知，不整批抹除或补跑 |
| RT14 | 实际carrier导致context超限 | 不截断/削减cap；固定分母记录失败或停止 |

### 9.4 Gold、公开Oracle和grammar（G01–G08）

| ID | 场景 | 必须观察到的结果 |
|---|---|---|
| G01 | PATCH只改一个字段 | 未修改字段的值与来源都保留 |
| G02 | 同值PATCH | 数值不变，但provenance refresh机会正确 |
| G03 | 旧记录精确重复交付 | authority不回滚 |
| G04 | 当前协议中父版本未先交付 | 作为非法数据拒收，不虚构unknown Gold |
| G05 | fork/cycle/跨FactKey父指针 | 当前协议拒收，两个Oracle都被独立反例覆盖 |
| G06 | per-key-latest-issued正确程序 | 当前合法数据仍满分，公开承认任务边界 |
| G07 | grammar生成错误数字/ID/动作 | 结构可能合法，语义必须仍可失败 |
| G08 | 文本与引用locator一起平移 | 值与支持评分不变；仅移动一方应失败 |

### 9.5 真实天气资料和时间（W01–W12）

| ID | 场景 | 必须观察到的结果 |
|---|---|---|
| W01 | observation行与forecast行都含风速 | 目标forecast只匹配forecast块 |
| W02 | MAX WIND与GUSTS并列 | 不交换持续风和阵风 |
| W03 | 移动速度数值与风速相同 | 不能作为风速支持 |
| W04 | 两公告都有+24h但起报不同 | 不误认为同valid time |
| W05 | 两公告不同lead却同绝对valid time | 能正确对齐修订对 |
| W06 | 月末/年末DD/HHMMZ跨界 | 按原文时间上下文唯一解析；歧义隔离 |
| W07 | issued与初始化相差数小时 | 分开保存，不静默相等 |
| W08 | KT与MPH混合来源 | 保留原单位或使用预注册转换；不任意误差容忍 |
| W09 | N/S/E/W符号 | 坐标符号正确，wrong hemisphere失败 |
| W10 | 新公告没覆盖目标时刻 | 按公开latest-covering-key规则处理，不自动取消 |
| W11 | 当前压力被当成未来压力预测 | 拒绝该fact映射；新轨不生成无来源字段 |
| W12 | 两parser不一致/实际来源撞heldout | quarantine；不按有利结果选择一个parser |

### 9.6 汇总、统计与帮助层级（S01–S06）

| ID | 场景 | 必须观察到的结果 |
|---|---|---|
| S01 | 3来源很多派生分支 | 独立来源数仍为3 |
| S02 | 两repeat一成功一失败 | episode pass^2=0，不是“至少一次成功” |
| S03 | 双向pair变化相抵 | 保留good→bad和bad→good两方向 |
| S04 | 无机会/缺repeat | rate=null或incomplete，不记100% |
| S05 | 公开工具直接给答案 | 标tool-assisted/upper-bound；不声称LLM独立推理 |
| S06 | 所有报告重建与迁移 | 分母、模型origin、身份和旧hash核对一致；无法验证部分显式列出 |

---

## 10. 命令、工作状态与首轮交付

### 10.1 当前已经存在的安全入口

先检测仓库位置和解释器；以下不是无条件“都可执行成功”的保证。

```bash
# 从仓库根目录运行。仅读，不回滚工作区。
git status --short
git branch --show-current
git rev-parse HEAD

cd disastertrace-starter
# 在独立CPU环境且依赖已安装、所需资料可用后：
python -m pytest tests -o addopts= -q
```

完整测试如果依赖缺失，应报告缺失，运行可用的无网子集；不得把skip或旧日志当新全量成功。历史capture报告复核优先使用 `REVIEW_FOR_CHATGPT_PRO_P5.md` / `REPRODUCE_ACP.md` 给出的冻结源码和 `--require-model --verify` 路径，而非拿当前改过的模块解释旧结果。

不要运行历史 `launch_p5.py`、`acp_worker.py`、P4/P5 `collect` 或已消费API launcher。新CPU复核输出放在新的审阅目录，不覆盖旧 `verification_result.json`。

### 10.2 要由 T00–T12 实现的 CLI 合同

以下命令是**拟实现接口**。只有模块实现、`--help` 与相关测试都通过后才能使用；不得仅创建一个空命令然后报告功能完成。

```bash
# 新增：冻结P5只读诊断；输出目录必须不存在。
python -m disastertrace.posthoc_p5.cli audit \
  --capture-index plans/p6/p5_capture_index.json \
  --output work/p6-posthoc-001

# 新增：预设2160槽位执行包，仅CPU/未授权。
python -m disastertrace.repeat_eval.cli prepare \
  --protocol plans/p6/protocol_repeat_scope_v1.yaml \
  --output work/p6-repeat-prepared-001

# 新增：程序夹具演练，不读取模型权重、不调用generate。
python -m disastertrace.repeat_eval.cli rehearse \
  --execution work/p6-repeat-prepared-001 \
  --backend correct \
  --output work/p6-repeat-diagnostic-correct-001

python -m disastertrace.repeat_eval.cli verify \
  --execution work/p6-repeat-prepared-001 \
  --run work/p6-repeat-diagnostic-correct-001 \
  --expected-origin diagnostic_program

# 新增：只解析已经获取的真实资料快照。
python -m disastertrace.forecast_revision.cli build \
  --snapshot plans/p6/forecast_snapshot_manifest.json \
  --catalogue plans/p6/acquisition_catalogue.json \
  --output work/p6-forecast-dev-001
```

示例路径下的JSON/YAML由相应任务生成。缺失就报错，不自动下载其他数据替代，不创建虚假manifest。live命令不在首轮启动指令中；T15按新scope单独设计。

### 10.3 实施分组：避免一个巨大PR

| 提交组 | 任务 | 退出条件 |
|---|---|---|
| A | T00、T01 | 状态/来源/历史保护清楚，没有重做已完成模块 |
| B | T02、T03、T04 | P5细分类和行为测试可重建，计数守恒 |
| C | T05、T06、T07 | 新repeat包与故障演练通过，`ready_not_launched` |
| D | T08、T09 | 方法增强和程序帮助层级明确，不改旧基线 |
| E | T10、T11、T12 | 真实预报parser与同valid-time任务可自动核验 |
| F | T13、T14 | 第二模型adapter准备和CPU复现/发布包审计 |
| G | T15 | 有效新scope下的真实运行及独立复核 |
| H | T16 | 可选新机制协议；不阻塞前述任务 |

依赖图：

```text
T00 → T01
T00 → T02 → T03
T00,T01 → T04
T03,T04 → T05 → T06 → T07
T02,T04 → T08 → T09
T01 → T10 → T11 → T12
T07 → T13
T02,T07,(T12若已做) → T14
T00..T07 + 新scope → T15(E1)
T08/T09或T12/T13 + 各自新scope → T15(其他独立实验)
T02,T07 → T16（可选）
```

默认首轮不执行live，不等待所有可选方法或真实资料才能交付A–C。T10获取受阻时，T11用synthetic parser fixtures继续开发，但不能标真实轨完成。

### 10.4 机器可读状态模板

```json
{
  "plan_version": "p6_research_backed_v1",
  "review_base_commit": "dd5ee358f9708e2eb2f2032db9eaac14fa237adc",
  "actual_head": null,
  "task_id": "T00",
  "status": "not_started",
  "changed_files": [],
  "commands_executed": [],
  "test_results": [],
  "artifacts": [],
  "blockers": [],
  "paid_model_requests": 0,
  "local_model_generations": 0,
  "gpu_jobs": 0,
  "historical_files_changed": false,
  "next_task": "T01"
}
```

允许状态：`not_started/in_progress/completed_verified/already_done_verified/blocked_external_source/blocked_environment/blocked_scope/failed_validation/ready_not_launched`。`completed_verified` 要有当前执行证据；一个文档或上游README声称完成不足以使用这个状态。

每项 DECISION 记录：问题、备选、选项、理由、影响的协议/数据/方法身份、是否改变历史可比性。每项 BLOCKER 记录：缺失对象、已尝试动作、具体错误、仍可并行任务，避免把整个项目因单个可选项停住。

---

## 11. Gate、论文产物与主动延后事项

### Gate A：测量解释成立

P5计数重建一致；引用分类覆盖且守恒；不变性/方向性夹具能区分正确与错误程序；每一项“bug”有最小反例。没有反例时写研究局限或待检验假设，不写成已修复缺陷。

### Gate B：新执行可信

重复身份、carrier隔离、配对seed、批次与完整分母通过离线验收；能够对中断前缀独立审计。程序诊断只证明管线，不证明模型会通过格式或8192足够。

### Gate C：有意义的新模型证据

只有绑定scope并真实执行的新矩阵才进入表格。新模型失败都保留；基于P5选择的研究问题明确标为开发发现，不宣称预见。无显著变化也是结果，不按结果临时加深任务或选失败子集作为主benchmark。

### Gate D：天气外部价值

至少有可追溯原始官方资料、同绝对valid time的预报更新对、独立解析器和错误负控；源事件/模板/单位/时间覆盖透明。生成记录与真实文字轨分别报告。新资料只改变数值时，不能据此声称新的气象推理机制。

### 可形成的论文贡献（待实验支持，非现阶段宣称）

1. 一个联合测量数值、作用域和当前来源的动态证据协议，清楚区分格式成功与语义成功。
2. 一组保持checkpoint Gold不变、同时保留零增量控制的干扰测量及重复验证。
3. 数值正确但当前引用错误的结构化失败分析，以及透明的来源感知基线。
4. 在同有效时间真实天气预报资料上的外部验证，而非仅增加合成风暴名称。

这些不是“第一个”主张。STATE-Bench、STALE、MemoryAgentBench等已经覆盖状态/记忆评价；DisasterTrace需要通过来源权威性、局部更新与真实天气资料的联合证据建立差异，而不能靠persistent state这个词本身构成novelty。[R04–R06]

### 明确延后

- Level16、大context、更多checkpoint：先设计独立长度/决策跨度因素，不能直接推断更强记忆压力。
- 多模态GIS：待文本真实轨稳定，再定义图像必需样本、独立隐藏GIS标签与模态消融；当前不声称已实现。
- 第二灾种：优先可执行官方表格/alert修订，开放建议不进入自动主评分。
- 训练、RL、自动prompt搜索、AutoResearch：只有开发/heldout和scorer冻结后单独研究，搜索成本全部计入。
- 通用Agent/数据库大重构：无证据表明能解决当前230处引用错误，暂不做。
- 人工或LLM替代主评分：不在本计划范围内。

---

## 12. 在线原始资料登记与项目证据

核查日期统一为 **2026-09-08**。URL在本文中以代码形式保留，便于编码代理直接取用。除明确的项目SHA/文档版本外，外部仓库本次没有全部解析到不可变commit；不能说它们都已锁版本。下载/拷贝前由T01补充 `resolved_commit/file_hash/license`。

每个来源区分：论文内容、仓库可见实现、文档声称，以及本项目拟借鉴。**阅读README不是复现结果。** 本次不依赖不存在的第三方评测成绩，也不因作者提供代码就默认整套依赖可以在项目Python3.10环境运行。

### R01｜ALCE：答案与引用质量分离

- 论文：Tianyu Gao, Howard Yen, Jiatong Yu, Danqi Chen. *Enabling Large Language Models to Generate Text with Citations*. EMNLP 2023。
- 原文页：`https://aclanthology.org/2023.emnlp-main.398/`
- 作者代码：`https://github.com/princeton-nlp/ALCE`
- 代码入口：`https://github.com/princeton-nlp/ALCE/blob/main/eval.py`，`compute_autoais`。
- 核查：论文页/摘要、README、评分入口。借鉴维度与逐引用记录，不运行NLI神经判分。
- 对应任务：T02/T03/T08/T09；复用模式 `design_only`。不要将自有确定性引用评分命名为“完整ALCE复现”。

### R02｜CheckList：行为测试而非仅平均准确率

- 论文：Marco Tulio Ribeiro, Tongshuang Wu, Carlos Guestrin, Sameer Singh. *Beyond Accuracy: Behavioral Testing of NLP Models with CheckList*. ACL 2020。
- 原文页：`https://aclanthology.org/2020.acl-main.442/`
- 作者代码：`https://github.com/marcotcr/checklist`
- 核查：论文页、README中的MFT/INV/DIR和expectation概念。
- 对应任务：T04/T11；以pytest实现任务自己的最小行为/不变性/方向性测试，`design_only`，不复制整个生成器。

### R03｜τ-bench：重复可靠性

- 论文：*τ-bench: A Benchmark for Tool-Agent-User Interaction in Real-World Domains*. 2024，arXiv:2406.12045。
- 原文页：`https://arxiv.org/abs/2406.12045`
- 作者代码：`https://github.com/sierra-research/tau-bench`
- 核查：原论文摘要/重复可靠性定义、仓库README。当前README已提示旧任务不再更新并指向后续系列。
- 对应任务：T05/T07/T14；借鉴重复与成功定义，使用第8节明确的episode级适配。旧用户模拟、retail/airline数据和自动LLM错误归因器不搬入。

### R04｜Microsoft STATE-Bench：状态、环境与方法隔离

- 作者项目：`https://github.com/microsoft/STATE-Bench`
- 官方介绍：`https://opensource.microsoft.com/blog/2026/05/19/introducing-state-bench-a-benchmark-for-ai-agent-memory/`
- 核查：README、Main/Agent Learning分轨、运行与依赖说明。包含程序验证和不同评价维度，不能把其UX判分当成我们的自动主评分。
- 对应任务：T05/T06/T13/T14；只借鉴环境隔离、重复/成本报告。当前项目不是StateMemBench，禁止引用混名。
- 复用模式 `design_only`；外部Python要求与本项目不同，不能直接整包替换。

### R05｜STALE 与 CUP-Mem：当前状态与历史主张的区别

- 论文：*STALE: Can LLM Agents Know When Their Memories Are No Longer Valid?* 2026，arXiv:2605.06527。
- 原文：`https://arxiv.org/abs/2605.06527`；HTML：`https://arxiv.org/html/2605.06527v1`
- 作者仓库：`https://github.com/icedreamc/STALE`
- 已读取入口：`https://github.com/icedreamc/STALE/blob/main/cup_mem/README.md`
- 核查：状态解析、前提抗过时与策略调整设计；CUP-Mem公开runner说明。上游runner会自动读取`.env`并依赖模型/embedding，不能盲跑。
- 对应任务：T08/T09/T16；只在明确公开规则下构建自动可裁决测试，不复制需要人工隐式冲突裁决的标签。方法应称“受其启发”，不是已复现CUP-Mem。

### R06｜MemoryAgentBench：增量观察应另设协议

- 论文：*Evaluating Memory in LLM Agents via Incremental Multi-Turn Interactions*. 2025，arXiv:2507.05257。
- 原文：`https://arxiv.org/abs/2507.05257`
- 作者代码：`https://github.com/HUST-AI-HYZ/MemoryAgentBench`
- 核查：论文页和作者README；`agent.py`、`conversation_creator.py`及`methods/`为进一步阅读入口，未完整审计其全部实现。
- 对应任务：T16；借鉴增量呈现与能力分层，保留全证据对照。不引入其带LLM judge的子任务作为主Gold。

### R07｜RULER：长度与复杂度分别控制

- 论文：*RULER: What's the Real Context Size of Your Long-Context Language Models?* 2024，arXiv:2404.06654。
- 原文：`https://arxiv.org/abs/2404.06654`
- 作者代码：`https://github.com/NVIDIA/RULER`
- 核查：论文页、README和`scripts/`生成/评估入口。进一步复用前定位具体脚本并固定SHA，不猜文件名。
- 对应任务：T03/T04/T05的可选长度控制；合成诊断不能替代真实资料外部验证。

### R08｜ExtremeWeatherBench：事件组织与预报评测边界

- 论文：Amy McGovern et al. *Extreme Weather Bench: A framework and benchmark for evaluation of high-impact weather*. 2026，arXiv:2605.01126，论文页提交日期2026-05-01。
- 原文：`https://arxiv.org/abs/2605.01126`
- 作者代码：`https://github.com/brightbandtech/ExtremeWeatherBench`
- README指明目录：`src/extremeweatherbench/data/events.yaml`，T01固定提交后确认。
- 核查：论文页、作者README。论文已经出现，README“准备中”文字不能当作没有论文的证据。
- 对应任务：T10/T12/T14；借鉴事件目录、来源覆盖、预报/目标区分。不运行天气基础模型或下载庞大再分析数据，不把其forecast误差等同LLM资料理解分数。

### R09｜NHC 官方产品说明与同有效时刻资料

- 产品说明：`https://www.nhc.noaa.gov/aboutnhcprod.shtml`
- 官方资料入口：`https://www.nhc.noaa.gov/data/`
- 本次打开的两个原始资料页面：
  - `https://www.nhc.noaa.gov/archive/2024/al06/al062024.fstadv.001.shtml`
  - `https://www.nhc.noaa.gov/archive/2024/al06/al062024.fstadv.003.shtml`
- 核查：上述HTML原文中的预报时刻、位置、最大持续风/阵风。对2024-09-10 06Z，两份资料分别给出45KT与55KT的最大风预报，为真实资料revision示例，不是模型结果。
- 对应任务：T10–T12；以不可变抓取字节、逐行引用和显式时间语义构建。当前已看过的资料不是新heldout。现有heldout冲突检查优先。
- 官方来源不自动证明历史首次可见时间；归档抓取时间单独登记。禁止用best-track后分析填当时模型输入。

### R10｜Tropycal：Operational Forecast 的交叉核对入口

- 作者项目：`https://github.com/tropycal/tropycal`
- API文档：`https://tropycal.github.io/tropycal/api/generated/tropycal.tracks.Storm.get_operational_forecasts.html`
- 公开源码文档：`https://tropycal.github.io/tropycal/_modules/tropycal/tracks/storm.html`
- 核查：API与源码文档中的operational forecast/A-deck访问方式。没有调用该函数下载资料，文档版本不等于已经锁定最新代码。
- 对应任务：T10/T11；可选交叉核对init、forecast hour、aid及官方预报。OFCL与插值/其他aid不可混用；来源不一致时保留争议，不强行选择有利值。不是唯一Gold。

### R11｜XGrammar：结构约束与任务正确性分离

- 论文：*XGrammar: Flexible and Efficient Structured Generation Engine for Large Language Models*. 2024，arXiv:2411.15100。
- 原文：`https://arxiv.org/abs/2411.15100`
- 作者实现：`https://github.com/mlc-ai/xgrammar`
- 核查：论文页、作者项目说明，以及本项目已经读取的结构schema/adapter。实际P6对照沿用项目冻结的0.1.23实现，不自动升级。
- 对应任务：T05/T06/T13；grammar应允许错误值/错误引用成为可达输出，任务评分独立完成。不同输出轨分开报告。

### R12｜vLLM v0.10.2 的可复现性说明

- 与项目版本对应的官方文档：`https://docs.vllm.ai/en/v0.10.2/usage/reproducibility.html`
- 核查：同硬件/版本的限制、V1多进程设置、调度与全局RNG的说明。
- 对应任务：T05/T06/T07；固定profile、明确seed类别、独立schedule RNG、控制批次。不能承诺跨硬件一致或相同seed足以隔离所有处理效应。

### P01–P06｜本项目只读证据入口

统一不可变URL前缀：

```text
https://github.com/sisuolv/disastertrace-benchmark/blob/dd5ee358f9708e2eb2f2032db9eaac14fa237adc/
```

| ID | 前缀后的文件路径 | 支撑内容 |
|---|---|---|
| P01 | `disastertrace-starter/REVIEW_FOR_CHATGPT_PRO_P5.md`；`disastertrace-starter/AGENTS.md` | 当前研究定义、阶段结果、限制和已消费运行范围 |
| P02 | `disastertrace-starter/README_P5_ACP_V1.md`；`disastertrace-starter/artifacts/p5_stress_level4_v1/analysis/RESULT_TABLES.md` | P5真实结果计数与层级 |
| P03 | `disastertrace-starter/src/disastertrace/controlled/compiler.py`；`.../controlled/public_oracle.py` | 私有compiler与公开resolver、当前单链语义 |
| P04 | `disastertrace-starter/src/disastertrace/controlled/scorer.py`；`.../controlled/renderer.py` | 当前引用评分、固定分母、公开输入与carrier |
| P05 | `disastertrace-starter/src/disastertrace/local_eval/difficulty.py`；`.../stress_eval/data.py`；`.../stress_eval/execution.py` | stress变换、equal-Gold、单repeat旧执行契约 |
| P06 | `disastertrace-starter/src/disastertrace/constrained_eval/contract.py`；`.../constrained_eval/adapter.py`；`disastertrace-starter/artifacts/p5_stress_level4_v1/REPRODUCE_ACP.md` | 结构约束、推理设置与CPU重算入口 |

表中 `.../` 仅为阅读缩写，机器登记文件必须展开为完整路径。随交接包的 `SOURCE_REGISTRY.json` 提供完整URL；单独使用本Markdown也可以按目录结构展开。

### 来源登记对象要求

```json
{
  "id": "R01",
  "primary_urls": ["https://aclanthology.org/2023.emnlp-main.398/"],
  "repository": "princeton-nlp/ALCE",
  "reviewed_at": "2026-09-08",
  "review_scope": ["paper_metadata_abstract", "readme", "selected_eval_function"],
  "reuse_mode": "design_only",
  "target_tasks": ["T02", "T03", "T08", "T09"],
  "resolved_commit": null,
  "license_verified_for_copy": false,
  "runtime_reproduced": false,
  "pin_required_before_copy": true
}
```

上面的空SHA和许可状态是有意的诚实边界；`null`不阻塞方法启发，但阻塞未审阅许可的代码复制。不要为了让validator通过伪造SHA或宣称运行测试。

---

## 13. 可直接复制给 Codex 的启动与续接指令

### 13.1 首轮：完成离线可交付包

```text
请读取 DISASTERTRACE_P6_CODEX_PLAN_RESEARCH_BACKED_20260908.md，
以及仓库所有适用AGENTS.md、P5 review、IMPLEMENTATION_STATUS、DECISIONS和BLOCKERS。
基准提交是dd5ee358f9708e2eb2f2032db9eaac14fa237adc；若HEAD更晚，先核对差异。

在现有DisasterTrace上增量实现，不整体重写，不回到最初starter，
也不要只生成另一份计划。首轮目标是T00–T07的离线交付；
有已经获取的资料时并行T10–T11，否则用明确synthetic夹具完成parser测试。

先建立回归测试，再实现引用错误细分类、处理暴露切片和行为验收，
保持P5原分数与原始文件不变。实现新的repeat身份、配对seed、
调度、carrier隔离、journal、独立audit和程序rehearsal。
E1候选矩阵是Base/Scope × 36episode × 5checkpoint × 3方法 × 2repeat = 2160。

不要启动GPU、模型API、generation-disabled GPU preflight、训练、权重下载、
历史作业或GitHub发布；不读取密钥。没有对应新scope时交付ready_not_launched。
不新增逐题人工判分，不使用LLM judge或AutoAIS作为主评分。
外部代码先锁SHA和许可；当前以设计借鉴和已有代码复用为主，避免安装整个上游框架。

禁止把诊断输出当模型结果、把旧DeepSeek结果填新版矩阵、
把当前累计证据比较称为内部记忆因果证明。
每完成一个任务，更新plans/p6/status.json和IMPLEMENTATION_STATUS，
记录实际命令、exit code、测试结果、产物路径/hash、未执行项和下一任务。
若某个外部资料或环境阻塞，明确记录并继续可独立完成的离线任务。
结束时提供已完成/未完成任务、实际检查结果、可复现命令和live前尚缺条件。
```

### 13.2 续接：避免把上一次摘要当完成证据

```text
请先核对当前HEAD、工作区修改、plans/p6/status.json及最新执行日志。
逐项确认上次标completed_verified的任务仍有对应测试和产物；不要重跑历史模型。
从第一个尚未完成且依赖满足的任务继续，保留所有失败和旧产物。
仍只执行本轮明确允许的离线范围；没有新scope不启动任何模型/GPU工作。
不要重复写同一计划或重新实现已有模块。
```

### 13.3 完成的定义

交付的核心不是“模块文件都存在”，而是：

**能从冻结P5回答解释错误；能在独立条件/重复下生成和核验正确请求；能用公开真实预报资料构造可复算任务；每个主张都有相匹配的证据层级。**

本文件及交接包生成只验证了文档结构、引用登记和计划计数，不构成对上述代码功能、模型结果或GPU执行的验收。后续所有完成状态以Codex实际执行记录为准。
