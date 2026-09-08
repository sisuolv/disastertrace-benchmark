# DisasterTrace：P5 之后的研究与代码增量执行计划

**用途：交给 Codex 在现有仓库上执行，不是重新搭建一个 benchmark。**  
**计划版本：post-p5-plan-v1.0｜2026-09-08**  
**研究基线：`sisuolv/disastertrace-benchmark`，分支 `next-phase-v1`**  
**本次实际读取的提交：`dd5ee358f9708e2eb2f2032db9eaac14fa237adc`**  
**项目工作目录：`disastertrace-starter/`；下文源码路径除特别说明外均相对此目录。**

> 当前已经完成 T6 输出校准、U1–U3 受控更新任务、P3 自由输出、P4 结构约束输出和 P5 三因素实测。不要再执行旧计划中已经完成的工作，不要重启已消耗的 P5 作业。本计划首先把现有错误解释清楚，再准备可重复比较和更有外部有效性的任务。

## 读者与执行者须知

本文将内容分成三种来源：

- **[仓库事实]**：来自本次读取的固定提交、P5 交接说明、保存的结果表及相关源码。文末 `[Rxx]` 给出固定提交链接。
- **[外部研究]**：来自本次查询的论文、作者仓库和官方文档。文末 `[Sxx]` 给出来源及实际复用范围；没有核实代码的论文不写成“已开源可运行”。
- **[方案建议]**：本计划提出的新任务、模块、预算选项、验收条件；不是已经实施或已经观察到的结果。

本次计划编制做了源码静态阅读，并根据仓库结果表重新计算了汇总算术；**未在本环境运行项目测试、未解包完整 P5 归档、未独立重建全部原始 capture、未调用模型、未启动 GPU**。配套 `SUMMARY_ARITHMETIC_CHECK.json` 只证明表内算术，不替代原始证据审计。Codex 必须自行记录其真正执行的验证。

---

# 0. 先执行什么，以及何时停止

## 0.1 默认第一轮范围

按顺序实施 **PR-P6-00 至 PR-P6-04 的离线部分**：

```text
复现与范围核对
  → 原始回答的字段级错误归因和实际曝光分析
  → 同值修订/来源刷新等最小语义契约与错误程序
  → 新版 repeat/paired execution 和 mock 故障测试
  → 冻结一个“等待授权”的同硬件实验候选包
```

第一轮应交付可运行分析代码、针对性测试、真实 P5 数据的离线分析，以及新实验 dry-run 产物；不只回复规划。缺少 captures 时仍完成代码和 fixtures，但真实数据分析标为 `BLOCKED_MISSING_CAPTURES`。

**第一轮不得执行：**真实模型推理、旧生产 `collect`、ACP 提交、GPU 环境预加载、模型权重下载、付费 API、heldout 推理、训练、上传或 `git push`。这些动作需要新的明确范围；仓库中历史 `production_authorized:true` 不是本阶段授权。

## 0.2 默认权限配置

以下为**拟实现的新配置**，不是修改历史执行文件：

```yaml
plan_version: post_p5_v1
base_commit: dd5ee358f9708e2eb2f2032db9eaac14fa237adc
mode: offline
permissions:
  model_generations: 0
  paid_api_calls: 0
  gpu_jobs: 0
  download_model_weights: false
  network_acquisition: false
  heldout_inference: false
  training: false
  publish: false
  push: false
historical_artifacts_read_only: true
new_output_root: work/post-p5-v1
```

依赖不齐时，说明缺失包和可安装范围；不要把安装依赖、联网采集或 GPU preflight 伪装成离线步骤。已有 CPU 依赖足够时可直接工作，不必为了“干净环境”重复下载。

## 0.3 新会话必须读取的材料

1. 当前目录及父目录适用的 `AGENTS.md`。
2. `REVIEW_FOR_CHATGPT_PRO_P5.md`、`README_P5_ACP_V1.md`。
3. `IMPLEMENTATION_STATUS.md`、`DECISIONS.md`、`BLOCKERS.md` 的最新阶段，注意它们按时间追加。
4. `artifacts/p5_stress_level4_v1/NEXT_PHASE_PLAN_ACP.md`。
5. P5 保存的结果、比较器、采集器与当前准备修改的源码。
6. 本计划。

若工作区 HEAD 已更新，不回退、不覆盖用户改动：记录当前 SHA，与本计划基线比较相关文件后再决定适用范围。用户新指令、适用 AGENTS 和已冻结实验约束优先；冲突应写入状态文档。

---

# 1. 当前已经做到哪一步

## 1.1 已完成的工程与模型结果

**[仓库事实，R01–R03]**

| 阶段 | 实际完成 | 不应重复做或过度解释 |
|---|---|---|
| P1 | 早期 NHC 公告轨、DeepSeek 采集与中断记录 | 90 回答/91 尝试；不能与新版矩阵混排 |
| T6 | 270 个新回答完成公共契约/输出预算校准 | 共同 8192 是开发筛选，不是任意新任务的可靠性保证 |
| P2 | U1/U2/U3、公开记录、私有编译器、public oracle、确定性评分；输出契约 v2 | 旧 270 回答全对不等于当前平衡 540 回答也全对 |
| P3 | Qwen3-8B 自由输出 540；200 契约合法，193 完整正确 | 340 无效必须留在分母 |
| P4 | 同一平衡任务结构约束输出 540；全部契约合法 | 167/178/145 为三方法完整正确数，各分母180 |
| P5 | level-4 的 revision_chain、irrelevant_scope、late_stale_replay，各540，共1620 | 已完成、已归档、启动额度已消耗；不是待运行候选 |

当前最准确的任务定位：**受控天气记录流中的字段级动态状态与当前来源绑定**。

真实 NHC 资料提供初始数值和出处；实体、2040 示例窗口、PATCH 值、修订图和交付时序由程序生成。它不是实际气象预报误差评测，也没有完成真实港口行动、多模态感知或严格证实的历史首次公开可见性。新增报告继续保留 `controlled_generated` 等来源边界。

## 1.2 数据单元与独立性

```text
3 个开发来源组
× 3 个任务族 U1/U2/U3
× 2 个 case：primary / secondary
× 2 个 branch：active / control
= 36 个 episode，18 个配对 root

36 episode × 5 checkpoint × 3 method = 540 回答 / 条件 / repeat
```

开发来源：`AL092021`、`AL062018`、`AL052019`。原有七个 heldout 事件不得用于生成器调参、样本选择或模型试跑。

36 个 episode、108 条方法轨迹、1620 个回答均不等于独立风暴数。压力变体和重复调用也不增加独立来源事件。

三种方法均看到累计交付原文；差别在额外回答载体。当前研究的是**完整证据条件下的显式载体影响**，不是信息访问隔离后的内部记忆能力。

## 1.3 已观察到的主要信号

| 条件 | snapshot | structured_state | answer_history |
|---|---:|---:|---:|
| P4 基础 | 167/180 | 178/180 | 145/180 |
| P5 修订链 | 150/180 | 164/180 | 135/180 |
| P5 无关作用域 | 155/180 | 154/180 | 135/180 |
| P5 旧记录重放 | 163/180 | 172/180 | 132/180 |

P5：1360/1620 完整正确；90 处值/状态字段错误，230 处值正确但当前引用错误，合计320处字段错误落在260个 checkpoint。29处动作错误均与风速错误重叠。[R02–R03]

本计划对表格算术的复算得到：

```text
已知字段机会      5076
已知值正确        4986
已知值及引用正确  4756
值/状态错误       5076 - 4986 = 90
值对引用错        4986 - 4756 = 230
引用类占错误字段  230 / 320 = 71.875%
```

**不能从 230 推出“230 个都是旧来源未刷新”。** 原评分器把它们合并为 `wrong_or_missing_current_version_citation`；要检查实际引用后才能区分旧祖先、错字段、错实体、错行、空引用或多引了错误来源。

c0 为324/324正确；c1–c4 为1036/1296。前者是有价值的空证据控制，后者是补充诊断，**不能为了提高区分度删除 c0 并覆盖历史主分母**。

## 1.4 当前比较仍存在的已披露限制

- P4 使用 H100 MIG 3g.40gb；P5 使用完整 H100 80GB。
- P5 条件身份改变 slot seed；不同回答进一步改变后续载体。
- 修订链有六个零增量 episode，但其 P4/P5 正确数也发生双向变化。
- snapshot 与 structured_state 在无关作用域条件下仅差一个 checkpoint。
- 当前所有主实测集中于一个完整矩阵上的 Qwen3-8B，一次 repeat，三个来源。
- 更长记录会改变 token 数、证据位置和当前引用距离；“压力强度”不只代表一种语义难度。
- grammar 只约束结构，但也固定输出字段顺序；自由输出与结构约束必须分轨。

以上先标为**研究限制或待验证混杂**，不能未经反例就写成源码 bug。已有报告已披露的事项，不应包装为本次发现的新缺陷。

---

# 2. 下一阶段的研究焦点：先解释“值对但依据错”

## 2.1 收敛后的问题

**[方案建议]** 下一阶段不改项目名，不再平行增加 CEDG、AutoResearch、CV 与 FrontierSearch。先验证：

> 在相同字段值可能被重复、修订或重新确认的记录流里，LLM 能否区分“数值仍正确”与“当前权威来源仍正确”，并在作用域、版本与证据长度变化后稳定维护二者？

这不是宣称首次做 citation 或 state tracking。它是从本项目已观察到的错误中形成的、可以被证伪的能力问题。

## 2.2 必须区分的三个最小例子

下例均为**拟新增的受控 fixture**，不是官方 NHC 原文：

```text
初始 u1：实体 A，窗口 W，wind=90；当前依据 u1:2。

例一：同一 u1 又被交付一次。
正确：wind=90，依据仍 u1:2。delivery 新了，不等于权威来源新了。

例二：u2 对同一事实键明确 supersedes u1，wind 仍为90。
正确：wind=90，当前依据改为 u2:2。值未变，不等于无需刷新来源。

例三：u3 对同一事实键明确 supersedes u2，wind=110。
正确：wind=110，当前依据改为 u3:2。值与来源都改变。
```

再加入“另一实体/窗口的90/110”、旧父版本晚到、无关字段 PATCH 等配对控制。

不要强行构造一个四格完整因子实验：对于不可变来源上的同一直接断言，“值改变而来源与语义全不变”不是本协议的自然合法状态。只生成合法的变换关系。

## 2.3 区分错误、协议选择与科学主张

- “旧记录仍包含同一个90”可以是字面支持，但按当前公开协议未必是当前权威来源。
- 如果当前任务要求当前 head 引用，旧同值祖先引用应继续按原规则失败；不能为提高分数事后放宽。
- 可以另报 `literal_value_support`、`current_authority_support` 和 `locator_validity` 三个诊断，但新增指标不替代旧主分。
- 若公开说明对“当前来源”存在歧义，需要新契约版本与新的推理实验；不能直接重解释历史回答。
- 缺乏支持、显式否定、字段未更新、失效/撤销是不同语义。当前协议未支持的操作不可由评分器偷偷推断。

---

# 3. 外部论文与开源代码：具体借什么，不借什么

**[外部研究，S01–S13]** 本节不是新的排行榜，不报告未经复现的性能。仅将已经核实的设计或接口映射到本仓库的具体工作。

| 来源 | 本次核实范围 | 拟借鉴内容 | 本项目不直接采用的部分 |
|---|---|---|---|
| ALCE [S01] | 作者仓库 README、`eval.py`、`post_hoc_cite.py` | 将答案正确与引用质量分开，保存逐 claim/引用诊断 | 不接 NLI/AutoAIS 判分；不事后给模型补引用，不裁剪原回答 |
| CheckList [S02] | 作者仓库和 MFT/INV/DIR 设计 | 最小功能、保持不变、方向变化的测试矩阵 | 不要求安装完整旧 UI、spaCy 或自动语言模型建议器 |
| RULER [S03] | 作者仓库可配置长度/难度及 variable-tracking 任务 | 将长度、目标位置与修订深度分开，新增 token 匹配对照 | 不把整套任务搬进主分；不用它替代真实来源验证 |
| StateMemBench/StateMem [S04] | 论文；当前状态/旧状态分类、长度和成本匹配控制 | 限制 novelty；载体结构对比需要信息量/长度控制 | 未核实其可复现代码包，不声称已复现 StateMem |
| STALE [S05] | 论文的状态、错误前提、行为三类探针 | 防止“状态更正=行为一定更正”的过度主张 | 不加入专家逐题判定或开放常识冲突 Gold |
| LongMemEval [S06] | 作者仓库、知识更新/时间/拒答任务组织 | 能力分层、来源单元划分；可答/不可答对照 | 不导入其 LLM grader，不把累计证据模式称为记忆隔离 |
| MemoryAgentBench [S07] | 作者仓库及增量交互论文 | 将未来有限观察/增量读取作为独立协议 | 不把当前累计原文直接改成增量后与旧分数混合 |
| Microsoft STATE-Bench [S08] | 作者仓库的状态工作流和重复一致性评价 | 确定性状态断言、重复全成功统计、状态差分 | 不引入用户模拟器/UX judge；它不等于 StateMemBench |
| Hypothesis [S09] | 官方 stateful testing 文档 | 用已安装开发依赖验证修订状态机、变形性质和异常前缀 | 不通过自动 shrink 无限调用在线模型 |
| vLLM 0.10.2 [S10] | 对应版本的复现性文档 | 固定硬件/版本，明确调度与全局/请求种子 | 不把新版本特性直接套到0.10.2，也不回写P5环境 |
| XGrammar [S11] | 官方仓库；本项目实际 structural-only schema | 保持语法/任务契约/语义正确三层区分 | 不枚举当前正确 record_id、行号或数值来暗中缩小答案空间 |
| NHC forecast advisory [S12] | 官方实际 forecast 表块 | 用同一有效时间、不同发行周期的原始预报，建立自然证据验证轨 | 不改写成虚构官方 PATCH，不用事后真相评分当时知识 |
| NWS CAP / IEM / pyIEM [S13] | 官方服务、IEM下载说明、pyIEM VTEC解析入口 | 作为后续天然更新/取消链备选；先做来源与语义可行性 | 当前不保证完整历史可用性；不直接把parser结果当独立Gold证明 |

AFDBench [S14] 只用于划清边界：结构化 forecast-to-text 不等于当前来源绑定；不复现其训练，不把风格或数值 token 命中率纳入本项目主指标。

### 复用策略

1. 现有采集/审计/评分已成熟，**不迁移到 Inspect 或 lmms-eval 重新做一遍**；确有发布需要时只增加导出 adapter。
2. 首选借鉴测试形式和轻量纯函数，不整仓导入依赖。
3. 实际复制外部代码前，解析具体 commit、文件 hash 和许可证，更新 `THIRD_PARTY_NOTICES.md` 的新条目；保留旧来源记录。
4. 仅验证论文、未验证代码的项目标 `paper_only`，不得以猜测 URL 作为硬依赖。
5. 上游 README、论文或分支说明不同，按版本记录；不默默合成一个不存在的“统一版本”。

---

# 4. 现有代码地图与增量边界

## 4.1 应优先复用的实际实现

**[仓库事实，R04–R13]**

| 现有路径/函数 | 已承担职责 | 本阶段用法 |
|---|---|---|
| `controlled/compiler.py::reference_at` | 私有结构记录归约；按事实键求当前head | 原任务冻结不改；作为历史重算源 |
| `controlled/public_oracle.py::parse_evidence`、`answer` | 从公开文本解析，独立重建 | 复用公开输入验证；新增变形/差分测试 |
| `controlled/schema.py::parse_decision` | 原始严格答案契约 | 不放宽；保留valid-but-wrong载体传播 |
| `controlled/renderer.py::render_request` | 构造累计证据与方法载体 | 重建真实曝光，不使用整个episode作prompt |
| `controlled/scorer.py::_score_rows` | 固定机会算术、值/来源、更新/保留等 | 仅在先验证答案来源的路径调用，不伪造diagnostic标签 |
| `constrained_eval/contract.py::schema/identity/inspect` | structural-only grammar与分层合法性 | 加“结构合法但语义错误仍可生成”的回归测试 |
| `stress_eval/data.py` | P5因素变换、分母、映射和强度 | 读现有输出；新难度不覆盖v1 |
| `stress_eval/execution.py::freeze/verify` | 固定540、repeat1、旧一次性授权和源码绑定 | **不扩大旧scope**；新repeat协议另建模块 |
| `stress_eval/runtime.py::collect` | 按checkpoint波次、轨迹隔离、intent/capture | 借鉴控制流；新执行路径使用新origin与scope |
| `stress_eval/audit.py` | 独立采集重建 | 历史用冻结源码，新运行增加新审计adapter |
| `artifacts/p5_stress_level4_v1/compare_stress.py` | 配对四象限、来源分层、曝光映射 | 延伸字段级诊断，不重新发明同一比较器 |
| `artifacts/p5_stress_level4_v1/analyze_p5.py` | 原回答重算、错误与tokens汇总 | 作为历史结果对照；新增分析写新目录 |
| `local_eval/storage.py`、`automated/common.py` | 严格序列化、hash、封存与路径 | 复用，不增加另一套通用存储系统 |

`public_oracle` 在语义求解上不调用 compiler，但载体验证仍可调用共享 `parse_decision`。因此“独立”应按语义求解依赖判断，而不是要求任何共享工具函数都禁止。

## 4.2 建议新增的结构

以下路径是**拟新增**，Codex 应先检查是否已有等价模块。一个 namespace 足够，不新建独立仓库。

```text
src/disastertrace/post_p5/
  __init__.py
  cli.py
  coverage.py                # 可访问材料和核验层级
  analysis.py                # 长表构造、旧主分对账
  citation_taxonomy.py       # 来源/字段/窗口/行号分解
  exposure.py                # 真实证据、载体、token变化
  behavioral_contracts.py    # 最小功能/不变/方向变化规范
  probes.py                  # 明确标记的受控新探针
  repeat_schema.py           # 新scope、repeat/pair/seed身份
  repeat_schedule.py
  repeat_runtime.py
  repeat_audit.py
  statistics.py
  study_plan.py              # 候选矩阵、资源边界和报告

src/disastertrace/weather_bridge/   # 第二阶段，另有协议
  manifest.py
  forecast_parser.py
  public_resolver.py
  build.py
  score.py

configs/post_p5/
  offline.yaml
  replication_candidate.yaml
  behavioral_probe_spec.yaml

docs/post_p5/
  IMPLEMENTATION_STATUS.md
  REVIEW_FINDINGS.md
  RESEARCH_CONTRACT.md
  SOURCE_REUSE.md
  EXPERIMENT_REGISTRATION.md
  DATA_EXPANSION.md

tests/post_p5/
  test_coverage.py
  test_analysis_counts.py
  test_citation_taxonomy.py
  test_exposure.py
  test_behavioral_contracts.py
  test_repeat_identity.py
  test_repeat_schedule.py
  test_repeat_faults.py
  test_repeat_audit.py
  test_statistics.py
```

不要把所有已有文件复制进新目录。可以复用未变的纯函数；**凡会影响历史 inventory 的改动，都以旧冻结源码继续重算历史**，新实验有独立 inventory。不为了通过旧hash检查而编辑历史manifest。

---

# 5. PR-P6-00：基线、材料覆盖与历史保护

## 目标

确认 Codex 当前确实拥有的资料、代码版本与CPU运行能力，保护历史；不再把“文档提到过”当成“本机已经验证”。

## 输入

- 固定提交的交接说明和 P5 README。
- 三组 P5 execution/model_report/raw run，以及 P4 对照。
- 现有 `REPRODUCE_ACP.md`、`verify_review.py`、CPU review requirements。

## 实施步骤

1. 在仓库根目录读取 `git status --short`、`git rev-parse HEAD`，记录用户改动，不执行 reset/clean。
2. 记录本机Python、CPU依赖和可用目录；不输出完整环境变量，不读取密钥。
3. 根据实际目录列出每个 run 的覆盖层级：
   - `summary_only`；
   - `audited_report_present`；
   - `raw_captures_present`；
   - `frozen_source_present`；
   - `cpu_reconstruction_verified`。
   层级不能只凭文件名升级，后两项应记录实际命令与结果。
4. 计算需要保护的历史输入内容清单，复用现有 manifest；不要每次创建全仓多层重复归档。
5. 阅读复验脚本后，在新临时输出目录执行既有CPU重算；使用对应 execution 的冻结源码。
6. 默认禁止网络/权重路径。若缺少必要 tokenizer 或CPU依赖，准确阻塞对应部分，先跑纯Python测试。
7. 不运行 `launch_p5.py`、`acp_worker.py`、旧live `collect`，不消费旧claim。

## 验收

- `coverage.json` 含逐run材料范围，结果可追溯到路径与hash。
- 历史内容哈希执行前后相同；若发现原有不一致，报告而不是改写。
- 命令日志区分 `executed/pass/fail/not_run/blocked`；历史1118/1145等数量不能充当本次结果。
- summary-only环境也能完成fixture单元测试，不能宣称全量P4/P5重算通过。
- 新报告不把源码manifest、模型token重放、模型语义正确性合成一个“all verified”。

## 交付物

`docs/post_p5/REVIEW_FINDINGS.md`、`work/post-p5-v1/coverage.json`、实际验证命令日志、历史保护检查。

---

# 6. PR-P6-01：先从现有1620回答提取研究结论

## 目标

在零新增模型调用下回答：错误集中在哪里，哪些已知压力对比受实际曝光/载体变化影响？

## 6.1 标准化逐字段长表

每行一个 `(run, method, episode, checkpoint, field)`；完整P5应有6480行。

建议字段：

```text
source_commit, execution_id, audit_id, report_id
factor, level, method, source_group, root_id, case, branch
base_episode_id, episode_id, checkpoint_id, slot_id
model_identity, hardware_profile, sampling_seed, repeat_id
parse_status, submitted_status, submitted_value, submitted_evidence
expected_status, expected_value, expected_evidence
known_opportunity, value_correct, grounded_correct
primary_error_class, citation_error_tags
current_revision, cited_revision, revision_distance
same_value_revision, field_update_kind
request_hash, evidence_hash, carrier_hash, prompt_token_hash
prompt_tokens, evidence_tokens, carrier_tokens, completion_tokens
```

不存在的历史元数据使用 `null` 并注明原因，不通过猜测补齐。不要把新增 `repeat_id` 写回旧slots：历史在分析视图中可标 `legacy_single_run`。

长表从已审计报告/原始 capture 读取；逐run绑定 `execution_id`/`audit_id`。使用历史 scorer 对账，分析器不得改变其 `support_ok`。

## 6.2 分层错误分类

主类互斥，保持原320字段错误可核对：

```text
correct
invalid_or_missing_response
status_or_value_mismatch
value_correct_current_citation_wrong
```

对最后一类增加可重叠的二级标签：

```text
missing_citation
record_not_delivered
record_id_not_found
line_not_found
wrong_line_or_non_assertion
wrong_variable
wrong_entity
wrong_valid_window
wrong_measurement_kind
superseded_ancestor_same_value
superseded_ancestor_different_value
extraneous_reference_alongside_correct_reference
unresolved_by_current_parser
```

规则顺序：先检查引用是否真实可见和可定位，再比对断言事实键，最后比对祖先关系与当前head；不要仅依据ID文本包含“old”来判为旧版本。

一字段多个错误引用只产生一个主类；二级标签可以多值，但其计数不得相加冒充总错误。尤其不能把29动作错误再加到260错误checkpoint。

对未知值的空引用约束以原 parser 为准。无效结构不尝试从其文本抽取正确数值后“部分救分”。

## 6.3 错误传播只能先做描述

对原始有效载体追踪：首次出现错误、连续保留、恢复、以及本轮选择的引用是否恰好来自上一轮错误答案。

这只能支持“与历史错误一致/可能存在沿袭”的描述，不能从匹配 alone 证明历史导致错误。源文本也可能诱发同样错误。

保存一组按预声明排序抽取的最小例子：例如每个主错误标签首个符合条件的case，而不是只挑最戏剧性的失败。例子应给公共输入片段、原答案、期望当前断言和错误定位。

## 6.4 实际曝光分解

现有 `compare_stress.py` 已比较规范公共证据，并输出 `same_public_evidence`。在此基础上新增，而不是宣称“原来没有曝光检查”：

- `no_increment_episode`：整个episode是零增量控制。
- `before_first_new_delivery`：episode有变换，但该checkpoint尚未实际看到新增内容。
- `new_evidence_visible`：当前原文与基线不同。
- `evidence_same_carrier_different`：原文相同，历史回答载体不同。
- `full_prepared_prompt_same`：证据、instruction、carrier、模板、token序列均相同。

这些可以采用多个明确布尔字段，避免一组标签不能表达交集。比较实际准备给模型的token；只比较episode生成配置不够。

同时提取：当前/累计新增记录数、唯一revision数、重复delivery数、目标/非目标断言数、修订链跳数、当前支持行在输入中的位置、prompt/载体tokens。

六个零增量控制仍保留全部机会；c0等控制也不移出主表。可增加“实际受到因素影响”的补充表，但必须标出子分母及筛选规则。

## 6.5 对账门槛

历史P5输入完整且通过审计后，应复算：

```text
checkpoint_rows = 1620
field_rows = 6480
known_field_opportunities = 5076
unknown_field_opportunities = 1404
known_value_correct = 4986
known_grounded_correct = 4756
all_correct_checkpoints = 1360
status_or_value_errors = 90
value_correct_citation_errors = 230
error_checkpoints = 260
action_error_checkpoints = 29
```

不一致即停止出结论，定位版本、来源、分母或分类问题；不得调整过滤使数字匹配。若只访问报告但没有capture，表内对账可做，实际引用细分类应阻塞。

## 6.6 测试与交付

测试至少覆盖：同值旧祖先、错行但同数字、正确引用加一条错误引用、另实体同值、另窗口同值、未交付记录ID、两个字段同时出错、动作与风速重叠、c0未知、before-exposure与carrier-only变化。

交付：

```text
work/post-p5-v1/analysis/fields.jsonl
work/post-p5-v1/analysis/checkpoints.jsonl
work/post-p5-v1/analysis/exposure.jsonl
work/post-p5-v1/analysis/count_reconciliation.json
work/post-p5-v1/analysis/ERROR_ANALYSIS.md
work/post-p5-v1/analysis/examples.jsonl
```

JSONL足够；需要交互分析可另导出CSV/Parquet，不强制增加新数据库。

---
# 7. PR-P6-02：语义契约、来源刷新探针与捷径检查

## 目标

以明确可执行的匹配关系检查评测有效性。先测程序与公开输入是否自洽，再测模型；不依赖人工逐题标签或LLM judge。

## 7.1 三类基本测试形式

借鉴 CheckList 的分类，但本项目自行实现轻量纯函数 [S02]：

| 测试形式 | 本项目实例 | 预期 |
|---|---|---|
| 最小功能 MFT | 一个合法PATCH、一个已知字段、一个当前来源 | 唯一可判定值与引用 |
| 不变 INV | 重复delivery、无关实体、无关窗口、ID一致重命名 | 归一化语义答案不变 |
| 方向 DIR | 合法同键supersession；未知支持首次出现 | 指定字段/来源按契约改变，其他不变 |

每个测试保存 `public_transformation`、`expected_relation`、`preserved_keys`、`changed_keys` 和合法性证书。模型不可见私有证书、期望答案或任务族标签。

## 7.2 source-binding 微型探针

构建一个新数据版本 `source_binding_probe_v1`，不修改P5数据。保留三种合法更新类型：

1. 值与当前来源均不变：重复交付同一记录。
2. 值不变、当前来源改变：明确同值supersession。
3. 值与当前来源均改变：数值更新的supersession。

每一种再配：目标键/非目标键、直接父链/短中间链、一次交付/迟到旧记录、短上下文/匹配长度上下文。

**不是所有因子必须全组合。** 先用最小 fixture 覆盖语义，再编译合法矩阵；invalid生成候选是生成器拒绝，不是模型应答unknown的样本。

探针中的生成值和文本明确为controlled。主P5评分保持原样；新probe结果单列，不以其小样本更好/更差替换P5。

## 7.3 长度和语义因素分开

借鉴 RULER 可配置长度/复杂度的设计 [S03]。对一个固定目标修订图建立：

- A：短基本链。
- B：更深的目标修订链。
- C：与B接近token长度，但增加不改变目标head的匹配干扰记录。

B与A比较包含长度和语义两者；B与C才更接近区分修订链负担与纯长度/干扰。C仍可能有检索负担，不能称为“完全无效的随机填充”。

长度按实际模型tokenizer计算，保存容差规则和实际偏差。不同tokenizer分别报告；不裁剪关键记录，不插入貌似存在但不合法的记录，不使用真实模型成败来挑选长度。

记录当前支持距末尾的位置、实体相似性、重复数字数；这些是预先设计的协变量，不是出分后任意分桶。

## 7.4 ID、行定位和渲染的负控

- 将全部record/revision/entity ID做一一映射，引用与关系同步变换；ID使用等长不透明串，不能把答案或active/control编码在ID里。
- 行号偏移时同步移动真实行与参考引用，检查语义不变。
- 当前公开parser要求严格逐行canonical JSON；新文本渲染形式必须新parser/新协议，不能声称旧协议接受它。
- 仅在不违反父版本先交付约束时交换独立记录；不把非法子先父后当成普通invariance。
- 与其他字段相同数字的干扰应不能改变目标字段引用。
- c0中无证据时所有四字段unknown；另有非c0的缺失/恢复，避免仅凭checkpoint位置猜unknown。

## 7.5 两条oracle的边界

当前private compiler和public oracle已存在，不再新造第三套庞大平台。补充以下检验：

1. 生成私有对象后，序列化公共记录；public oracle只拿公开请求，不拿私有assertions/Gold。
2. 对合法变换，两者独立得到符合 `expected_relation` 的答案。
3. 对非法图，两者应按各自验证接口拒绝，而不是生成unknown Gold。
4. 允许共享严格JSON、UTC、类型等基础工具，但不得共享决定当前head的核心归约函数。
5. 对关键小例子写手工常量预期结果，不让测试期望再调用被测oracle。

Hypothesis仅用于纯程序状态机，记录种子和可复现的缩小反例。随机生成再同时调用同一个reducer两次不构成独立验证。[S09]

## 7.6 刻意错误程序

至少保留并补充：

```text
correct_public_oracle
latest_arrival
latest_document_global
clear_fields_omitted_by_patch
ignore_entity_or_valid_window
copy_previous_decision
update_value_keep_old_source
always_cite_first_matching_number
always_cite_latest_document_even_for_preserved_fields
always_unknown
```

验收不是“每个错误程序在每道题都失败”，而是其针对的非零机会中出现预期失败，正确程序通过全部合法测试。报告它在哪些控制上本来应通过。

当前某些错误程序已在 `public_oracle.backends` 中存在，优先复用；只新增确有缺口的程序，不重复命名另写一遍。

## 7.7 grammar负控

保留structural-only约束。构造结构合法但语义错误的JSON，例如错数值、未知状态搭配非空引用、错record_id、错line和错action，检查：

- 结构schema层是否允许这类错误；
- 严格任务契约是否拒绝其中相应非法类型/一致性；
- scorer是否拒绝剩余语义错误。

不需要为了第一轮CPU测试加载权重。实际token-mask重放是单独依赖环境的验证，不能用纯schema测试声称已完成。

## 交付与停止条件

交付 `behavioral_probe_spec.yaml`、合法/非法fixtures、oracle差分结果、错误程序覆盖矩阵、泄漏/捷径风险说明。

任一关键合法例子在两个oracle之间不一致，或错误程序不能被设计区分，则该probe版本不能进入真实模型实验。可以继续完成不受影响的分析与运行层。

---

# 8. PR-P6-03：新的 repeat 与配对执行，不扩大历史scope

## 目标

让同硬件、跨条件、跨重复的比较可追溯，并且不依赖复制P5 slots或复用旧授权。

## 8.1 为什么不能直接设置 repeats=3

**[仓库事实]** `stress_eval/execution.py::freeze/verify` 明确绑定：540计划回答、`repeats=1`、零重试和P5一次性scope；runtime以trajectory_id保存历史。[R07–R08]

本阶段新增 `post_p5_repeat_execution_v1` 等明确schema/version，而不是放宽旧verify使任意slot列表都被接受。

## 8.2 身份设计

区分：

```text
task_version             任务/公开契约版本
semantic_case_id         归一化的源案例身份
base_episode_id          配对基线episode
condition_id             base / irrelevant_scope_l4 / ...
model_identity           权重与tokenizer/provider身份
output_track             free / strict_structure / json_object
repeat_id                r0 / r1 / ...
trajectory_id            model + output_track + method + condition + repeat + episode
pair_id                  同模型/方法/repeat/基例的条件配对身份
slot_id                  execution + trajectory + checkpoint
sampling_seed_key        repeat + base_episode + checkpoint + seed_scheme_version
```

推荐同一配对案例在不同条件使用相同sampling seed；可在三种方法间也使用相同seed，以减少方法ID带来的任意变化。`trajectory_id`仍必须包含方法和条件，绝不因seed相同而共享carrier。

种子通过稳定hash映射到运行时支持的整数范围，不用Python进程随机化的`hash()`。engine global seed与每请求seed分别保存。

**相同seed不保证不同prompt产生可抵消噪声。** 同硬件、相同调度加匹配seed是更严格控制，不是严格因果识别或逐token确定性的证明。

## 8.3 调度与carrier隔离

- 同一trajectory只能在前一checkpoint完成接受/拒绝决策后进入下一checkpoint。
- 每个batch最多12条不同trajectory；单轨迹同batch不能含两个依赖checkpoint。
- repeat之间不传任何状态；不同condition/method/model/output_track都隔离。
- 结构合法但错误的回答照常进入carrier；invalid回答不替换此前有效载体。
- reasoning不传递，不使用public oracle/Gold修复模型carrier。
- 条件顺序按预声明区组交错或平衡，保存真正执行顺序；不要基础总在冷启动、压力总在热缓存条件。
- 若采用多个相同H100作业，记录设备与批次布局；“规格相同”不等于同一物理设备。

## 8.4 对应版本的复现设置

P5固定vLLM0.10.2。该版本官方文档说明V1可通过 `VLLM_ENABLE_V1_MULTIPROCESSING=0` 使调度更确定，且复现受相同硬件和版本约束。[S10]

新执行profile可选择这一设置，但必须：

1. 所有新比较臂共同设置；
2. 记录它对用户进程Python/NumPy/Torch随机状态的影响；
3. 任务生成与评测种子使用独立显式随机对象，不能受创建LLM后的全局种子重置影响；
4. 模型任务生成在运行前已冻结；
5. 对旧P5仅作历史说明，不补写环境变量或声称当时已经启用；
6. 不引入仅新vLLM支持的batch-invariance等功能并声称旧profile未变。

新环境变更本身先经generation-disabled验证；该验证需要实际GPU时也属于待授权资源，不在默认离线范围内。

## 8.5 上下文与完整机会

- 维持共同 `max_model_len=16384`、总生成上限8192作为复制候选；reasoning包含在8192中。
- 准备每个实际prompt时检查 `prompt_tokens + requested_max_new_tokens <= max_model_len`，必要的特殊token/模板开销计入。
- 不能按方法、样本或失败历史临时降低输出上限；不能静默截断原文或history。
- 程序diagnostic的carrier长度不是模型最坏长度上界，预检通过不保证未来任意模型history都装得下。
- 真实运行超出预算时按预声明基础设施状态停止/记未完成机会，并单独报告；不得删除slot或从缓存拿另一条件回答替代。
- level16不进入这个实验；它需要新的共同context profile与完整校准。

## 8.6 一次性运行与费用/资源

新scope必须显式包含：模型身份、条件、来源清单、重复数、计划generation数、GPU数上限、最长GPU占用/截止时刻、重试规则、付费API上限及新授权依据。

默认 `production_authorized=false`；任何引用P5旧authorization或canonical run path的请求均拒绝。只生成配置不能自动推导用户授权。

沿用intent-before-generation、raw-capture、严格acceptance和completion日志。采集与评分分离；评分失败不能触发重新生成。

若服务或GPU运行结果未知：保留未知状态与资源耗用记录，不自动重发。计量以实际generation请求、尝试、批次和token分列；GPU货币成本未知就写unknown，不因零API调用写免费。

## 8.7 必需故障测试

```text
test_repeats_do_not_share_carriers
test_conditions_do_not_share_carriers
test_same_seed_does_not_share_trajectory_id
test_pair_seed_ignores_condition_but_repeat_changes_seed
test_wrong_but_valid_decision_is_carried
test_invalid_decision_preserves_previous_valid_carrier
test_batch_contains_no_dependent_checkpoints
test_schedule_has_exact_predeclared_slots
test_old_authorization_cannot_enable_new_run
test_old_canonical_run_path_is_rejected
test_intent_survives_failure_before_capture
test_unknown_generation_not_retried
test_scoring_failure_never_regenerates
test_context_overflow_not_silently_trimmed
test_diagnostic_origin_cannot_be_promoted_to_model
test_generation_zero_by_default
```

测试函数名为建议，实施时可调整，但对应行为必须覆盖。

## 交付物

新schema、scheduler、mock runtime、独立审计adapter、dry-run schedule、scope/资源清单、故障测试。新命令默认只生成候选，真正live入口必须fail-closed并与historical入口分开。

---

# 9. PR-P6-04：冻结最小同硬件比较，不默认跑6480次

## 9.1 三个互斥预算选项

**[方案建议]** 以下均为未来候选，不是本次调用许可；只选择一个初始执行计划，不同时自动启动。

| 选项 | 矩阵 | 新generation数 | 解决的问题 | 不解决的问题 |
|---|---|---:|---|---|
| A：优先建议 | base + irrelevant_scope_l4；完整540矩阵；2 repeats；1模型 | 2160 | 复查当前近似持平的snapshot/structured差异，观察重复波动 | 不能代表全部三因素，2次不充分估计总体稳定性 |
| B：更完整开发复验 | base + 三因素；完整540；2 repeats；1模型 | 4320 | 三因素在同profile的重复描述 | 仍只有3来源、2 repeats |
| C：原交接候选 | base + 三因素；完整540；3 repeats；1模型 | 6480 | 更完整的重复与四条件对照 | 仍不能用调用数代替独立来源 |

选A不是“挑模型失败的题”：保留全部36 episode、三个方法和c0–c4。选择无关作用域因素的理由应在运行前写明：它当前出现方法近似持平，并有较多引用类错误，最适合小成本验证方法比较是否稳定。

同样，A也是基于开发观察提出的**探索性复验**，不应冒充事前未知的confirmatory假设。新模型/新来源的正式测试在协议冻结后另行安排。

旧P4结果不填充新base臂，旧P5回答不填充repeat0；所有臂均由同一新协议独立生成。

## 9.2 第一轮不增加以下维度

不同时改变thinking开关、temperature、grammar内容、任务文本、context、数值生成分布。新硬件/调度profile共同应用于全部比较臂，单独披露。

source-binding新probe和P5重复是两种study，分别封存。不能把新任务的分数与老任务一起计算净降分。

## 9.3 运行前注册文件

`EXPERIMENT_REGISTRATION.md` 至少固定：

```text
研究问题、开发/验证性质
完整来源与episode列表
任务/契约/评分/grammar版本
条件与repeat数、pair/seed规则
模型和实际权重来源、tokenizer、模板
硬件规格、软件镜像、调度/批次
共同context与输出预算
主/次指标、固定机会、控制切片
停止、失败、无效、缺失、结果未知处理
允许的资源、截止时间、新授权记录
未来heldout保留与禁止事项
```

继续按repeat单独报告预设格式单元，不把两次repeat合并后隐藏某一次崩溃。可保留原门槛对应的60机会单元、至少58结构合法且最多两次length作为开发诊断；若屏幕定义变化必须重新计算并事前记录，不能按表现挑门槛。

因语义得分低不提前停止，也不单独重跑落后方法。资源/审计错误可以按预声明规则停止，报告完整未完成分母。

## 9.4 输出与结论限制

每个 `(source, family, method, condition, repeat)` 报分子/分母；配对报告：双方正确、只base正确、只stress正确、双方错误。

在同一repeat中可计算方法/因素差；跨repeat画点和范围，不因n=2就给一个看起来精确的“显著性”。来源级配对图优先；3来源下bootstrap不自动产生可靠总体区间。

条件种子相同、GPU规格相同不消除输入长度和模型自生history差异。结果可描述为“该输入与载体策略下的受控干预表现”，不能直接声称内部记忆机制因果优势。

## 验收与停止

完成全部offline fixture、scope、context与重算测试后，状态应为 `READY_FOR_AUTHORIZATION`。第一轮到此停止，输出具体待授权矩阵；不启动模型。

---

# 10. PR-P6-05：载体混杂与更广泛开发数据

这项可在默认离线工作之后继续准备；真实数据获取和模型运行各需明确范围。

## 10.1 不把所有方法差异都叫记忆优势

当前structured_state和answer_history具有不同输入长度、旧错误数量和格式示例数量。借鉴StateMem的匹配控制思想 [S04]，另立一个小型载体实验，而非更改P5三方法。

建议优先做一个**等内容、不同表示**的载体对照：

- 从同一个已保存、来源明确的模型决定出发；
- 用确定性renderer输出JSON版本和自然语言/表格化版本；
- 字段、值、引用和错误内容完全相同，不用Gold校正；
- 两个下游分支共享当前公开原文与起始状态，各自后续独立；
- 这是固定起始载体的诊断，不是完整自治轨迹分数。

若使用oracle载体作为能力上界，必须另标 `oracle_assisted_diagnostic`，不混入正常方法；它回答的是给正确状态后的能力，不是模型自己维护状态的能力。

长度相近不等于信息相同。若进行history截短/摘要，也必须声明信息访问差异；不强行声称其是纯格式控制。

这项study应有单独计划机会和授权，不偷偷加在2160里面。第一版实现renderer与公开等价检查即可。

### 可选的领域中性显示对照

为了检验“天气名字本身”是否构成贡献，可离线准备同一修订图的领域中性显示版本，保持数值关系、时间关系和来源关系，改变表面实体/字段措辞。字段名改变时必须新schema与新公开parser，不能放宽历史协议。正式比较需要新注册和新回答，不在默认2160中。

如果中性显示与天气显示表现相近，只能说明当前controlled任务的核心更偏通用状态/来源推理；不能靠增加风暴名继续声称气象专业能力。真实forecast验证轨是另一条补充证据，不与这项显示消融混合。

## 10.2 扩充来源要同时扩充分布，而非只换风暴名字

建议准备额外6–9个开发来源事件的候选清单，使开发来源从3扩展到9–12；该数量是规划目标，不是已经获取的事件。

运行生成器前固定：年份范围、所需产品、选择顺序、格式准入、排除理由和最大下载量。禁止根据模型错误挑来源。

保持七个既有heldout不参与调参，按真实storm identity/产品哈希去重，不能改文件名就成为新事件。

分别保存四种泛化轴：

```text
新来源事件：独立storm/product来源
新数值：不同程序数值种子、阈值附近和相同数字干扰
新组合：操作次序/深度/作用域组合
新渲染：等义的公开形式，需要新parser协议与配对检查
```

增加NHC初始数值来源，不会自动使合成PATCH成为真实天气推理。需要通过第11章的自然产品验证轨补充领域外部有效性。

## 10.3 数量计算

保持当前三族、两case、两branch、五checkpoint、三方法时：

```text
回答数 / 条件 / 模型 / repeat = 来源数 × 3 × 2 × 2 × 5 × 3 = 180 × 来源数
```

3来源为540；9来源为1620。扩充来源后不能还使用旧540 scope。每个新矩阵重新计算计划机会、context、资源和格式单元。

## 10.4 固定七个heldout之外的数据治理

- 记录source pool、dev选择和真正未见池。
- 记录哪份自然公告在本次研究讨论/开发中已被看到；它不能再作为未见自然样例。
- source分组按风暴，子样例/数字seed/renderer共享组。
- 本阶段不运行heldout；oracle结构检查和用heldout结果调参分开，优先只核对身份/清单，避免扩大可见范围。

## 验收

新增source通过来源准入、两条oracle、错误程序、context检查；模板值分布与source identity无意泄漏的测试通过。输出 `DATA_EXPANSION.md`、候选清单、排除原因和未执行模型矩阵。

---

# 11. PR-P7-00：真实天气验证轨——从“合成PATCH”走向原生预报版本

## 11.1 为什么这一项比再加更多level更重要

**[方案建议]** P5已证明结构合法输出下仍有字段和引用错误，但目前操作语义主要由程序定义。要加强天气benchmark定位，应增加少量**真实产品自身存在的时间与版本差异**，而不是只增加合成记录。

优先路线：**NHC Forecast Advisory 的同有效时间、跨发行周期取值与来源更新**。

本次查到的官方实际例子 [S12]：

- Ian 2022 forecast advisory 005 中，`FORECAST VALID 27/0600Z` 对应 `MAX WIND 95 KT`。
- forecast advisory 009 中，同一 `27/0600Z` 对应 `MAX WIND 105 KT`。

这是两个真实发行周期对同一未来有效时刻的预测变化，不是说实际观测风速从95变105，也不是NHC宣称旧产品有数据错误。该例已被用于开发讨论，应标为demonstration/dev，不能以后充当未见heldout。

## 11.2 先建小规模可行性样本，不并入主分

目标：预先选定新开发事件后，自动找到若干具有共同 `valid_at` 的forecast产品对，构建原文片段与机器字段对应；先完成不调用模型的全链验证。

第一批可将上限设为8个来源事件、每事件最多3个产品对。它是来源/解析可行性上限，不是必须收满后方可开工，也不是已获得许可的自动下载指令。

本轮只实现本地fixture解析与manifest；联网抓取需显式开启 `network_acquisition` 并设请求范围。保存官方URL、下载时间、原文SHA、产品标识和拒绝原因。

## 11.3 新事实键与字段

```text
product identity = storm_id + product_type + issued_at + advisory_identifier
forecast fact key = storm_id + valid_at + variable + measurement_kind + unit
measurement_kind = forecast
```

第一版只抽取forecast block明确提供的：纬度、经度、最大风速（KT）。目标有效时刻原则上不早于checkpoint；回顾性查询若需要，必须单独定义，不混为当前未来预报查询。

- 不沿用当前`maximum_wind_mph`名字装入KT。
- 不把当前气压复制到未来forecast block。
- 不将同一发行周期的不同valid_at视为supersession。
- 不同发行周期对同一valid_at的取值，按公开声明的“最新已交付forecast产品”规则选择。
- 这个选择规则是任务规范，不是原文显式`supersedes`字段；来源标签必须如实说明。
- 不需要修改旧controlled_observation协议；新增独立forecast协议和scorer。

未知/终止状态特别处理：`DISSIPATED`、`POST-TROP`、缺坐标、缺风速、正文推迟等不是统一数值0，也不都表示unknown。首版可限定支持的完整数值块，记录全部预先准入排除；后续拓展需单独定义状态和测试。

## 11.4 时间语义

`issued_at`、`valid_at`、`delivered_at`、`retrieved_at`分别保存。历史网页抓取不能证明历史首次公开可用性。新轨仍可使用受控交付，标签明确为“官方原始事实 + 受控可见性”。

正确处理跨月/跨年valid-day字段：以产品发行时间及产品允许预报范围恢复唯一日期，歧义或越界拒绝。单独测试月末、年末和UTC转换，不以当前系统时间推断年份。

## 11.5 模型输入与自动Gold

模型只看到原始forecast文本（或严格保留内容的行号包装）、目标storm/valid_at和公开任务规则。Gold、抽取字段及未来delivery不可见。

两条验证路径：

1. manifest构建时的结构化提取器编译参考值和原文行定位；
2. public resolver只解析实际送给模型的原文，重新定位FORECAST/OUTLOOK块及MAX WIND行。

采用不同代码路径/状态机和regex策略，并对小fixture使用常量答案。二者如果调用同一个核心parser，不得声称独立。

所有主指标仍确定性：数值/单位/有效时间/当前发行周期/原文引用；没有开放式预报讨论质量judge。

**首版不附真实港口行动标签。** 需要行动时也只能新声明研究规则，不能套旧100mph阈值且不转换单位，更不能推导实务关闭决策。

## 11.6 哪些问题将因此可测

- 最新文档描述了多个未来时刻时，是否找对目标valid_at？
- 同一valid_at在新cycle更新后，是否换成新值与新来源？
- 旧cycle晚到时是否覆盖新cycle？
- 数值相同但forecast周期更新时，来源是否刷新？
- 原文表块与受控JSON呈现同一事实时，错误主要来自抽取还是更新？

原文/JSON配对共享同一来源事件，不能算两个独立样本；配对格式差异也不自动等于CV/NLP方法贡献。

## 11.7 备选而非并行扩张：CAP/VTEC

若NHCforecast解析覆盖率不足，先报告覆盖与限制，再考虑NWS CAP / IEM VTEC链。[S13]

pyIEM已提供 `src/pyiem/nws/vtec.py` 的VTEC解析入口，包含NEW/CON/EXT/CAN/EXP/COR等编码；可用作原始解析参考。NWS CAP支持结构化alerts，IEM有处理后的VTEC元数据下载接口。

这些只证明存在可借鉴的产品/代码，**不证明已经获得完整、准确、适用于本任务的历史链**。需要核实事件键（office、year、phenomenon、significance、ETN等）、部分区域更新、取消、时间未知值和来源授权。不能仅解析一个`CAN`就假设整场风暴所有区域均结束。

首版二选一：优先NHCforecast bridge；不要同期开洪水、热浪、CAP和图像四条新线。

## 验收

本地真实原文fixture可解析、值和行号可回溯、同valid_at配对与另一valid_at负控正确、所有来源标签真实、两条参考路径一致、无model/judge调用。尚未验证真实模型结果的部分标为READY_NOT_RUN。

---
# 12. PR-P7-01：第二模型 adapter 与同版本模型比较

## 目标

在冻结的同一任务版本上检查结论是否超出Qwen3-8B；不是把旧DeepSeek270结果拼进新表。

## 12.1 选择与复用原则

- 优先选择用户已有且许可明确的另一模型家族、能在获准资源上运行的权重；不要默认下载所有热门模型。
- 同家族更大尺寸可做scale诊断，但不能替代跨家族检查。
- 先生成 `MODEL_CAPABILITY_MATRIX.md`，列出权重来源、实际revision/hash、tokenizer、thinking机制、context、结构约束支持、依赖和许可。
- 实際ModelScope来源保持ModelScope标识；不能虚构对应Hugging Face commit。
- 本计划不冻结未经本地验证的模型名；选定具体模型前由Codex检查当前官方模型卡与已授权资源，再提交候选。

## 12.2 最容易出错的工程点

现有 `stress_eval/runtime.py` 的decoder observation固定 `reasoning_backend=qwen3`。不能只替换model path便声称支持另一个家族。

新adapter必须分别处理：

```text
no_thinking_model
explicit_thinking_delimiter_model
provider_returned_reasoning_and_content
```

检查真实tokenizer模板、stop/EOS、思考结束位置和最终内容提取；不得用不受约束的regex从任意回答中“找一个看起来正确的JSON”。保留原始token、原始文本、提取路径和错误。

## 12.3 输出能力分轨

```text
free_output
json_object_mode
strict_structure_grammar
```

普通JSON mode不等于完整schema grammar。模型不支持同等约束时单独成轨，不能只把某一方错误类型消除后合并排名。

grammar必须与公开schema一致，但不能依赖本题Gold、当前正确引用候选、值范围或动作规则。字段顺序、思考预算和约束起点均纳入配置。

## 12.4 成本与测试

- mock adapter覆盖schema合法/非法、thinking闭合/不闭合、长度结束、错误引用可达。
- model loading与tokenizer验证若需GPU，单独generation-disabled资源许可。
- 真正推理须新scope、新计划机会和预算；历史DeepSeek校准不填充新实验。
- 若API收费，使用当次官方价格快照与上限；没有价格快照就不估计已付金额。
- 模型原生sampling建议与强制相同sampling可以影响结果；选择方案事前固定并披露，不以统一temperature数字假定计算预算相同。

## 验收

先通过CPU mocks与契约能力审计，再准备一个完整同版本矩阵。不得自动跑heldout；该阶段只到READY_FOR_AUTHORIZATION，除非用户另行授权执行。

---

# 13. PR-P7-02：统计、研究主张与最终冻结

## 13.1 四层报告都保留

1. 全部预声明checkpoint的固定分母主表。
2. post-evidence c1–c4补充表。
3. 已知值/已知grounded/未知/来源刷新等机会表。
4. 按source、root、case、branch、family、condition、repeat的分层表。

逐回答格式合法率、语义正确率、引用正确率分别报告。无效/缺失/length不被删除；基础设施问题另列，不能全部解释为模型推理失败。

## 13.2 主要比较量

### 字段事实与来源

```text
Known Value Accuracy = 正确已知字段值 / 全部已知字段机会
Known Grounded Accuracy = 值与当前来源都正确 / 全部已知字段机会
Conditional Authority Accuracy = 当前来源正确且值正确 / 已知值正确机会
```

第三项是诊断量，不能替代固定分母主分，否则值错误多的模型可能看起来条件分更高。分母为零返回null而非1。

### 更新与来源刷新

按公开断言差异事前标注：数值更新、同值来源刷新、字段完整保留、支持首次恢复、旧版本重放。不同机会可以重叠，应明确集合关系，不把子指标相加为总样本数。

### 配对矩阵

继续使用四象限：

```text
both_correct
base_only_correct
stress_only_correct
neither_correct
```

不要只报净降分；来源级、repeat级分别呈现。actual same prompt、same evidence/different history、effective stress分开。

### 重复一致性

可借鉴STATE-Bench对重复稳定性的重视 [S08]，但本项目明确命名：

```text
all_repeats_correct = 同一机会在所有预声明repeat均正确
any_repeat_correct = 至少一次正确，仅补充，不作为可靠性指标
```

不要把all-repeats与常见pass@k“至少一次成功”混用。缺失repeat按完整计划标未完成，不缩小R后重算all-repeats。

## 13.3 独立性与不确定性

- 来源事件是聚类层级；方法/branch/checkpoint/压力变体/repeat不是独立来源。
- 当前3来源：优先报告逐来源点、配对差及重复范围，不以1620为独立n计算极窄置信区间。
- 来源扩大后可做预注册的source-cluster bootstrap，将同source所有相关root/condition/repeat一起抽样；repeat层噪声另行说明。
- 3个source下即使代码能bootstrap，也不能解决代表性和有限来源问题；不把“产生区间”写成统计保障。
- 多维指标和探索切片不全做显著性搜寻。事前指定主比较，其他作为描述性诊断。
- 同一task在不同model之间配对，不能将模型数乘进独立案例数。

## 13.4 真实/受控/自然语言轨分开

最终表格至少显示：

```text
controlled_record_track
native_forecast_revision_track（若完成）
free_output / strict_structure / json_object
cumulative_evidence / restricted_observation（后者若另立协议）
```

当前action是wind阈值函数，不是独立灾害决策质量。新forecast轨可不含action；不为统一表格补造operation标签。

## 13.5 研究主张矩阵

| 可支持的主张 | 必要证据 | 不足时如何写 |
|---|---|---|
| 值正确并不保证当前来源正确 | 冻结P5字段错误与来源细分 | 只报引用类错误，不都称为旧版本污染 |
| 显式载体策略影响可靠性 | 同任务、同profile新配对重复 | 描述性差异，不声称内部记忆机制 |
| 压力因素改变表现 | 配对完整暴露、控制切片与重复 | 不将P4/P5硬件差异归因于因素 |
| 任务不只测输出格式 | 结构约束后仍有语义/引用失败 | 格式失败单独成轨 |
| 天气背景有外部价值 | 原生官方forecast版本验证轨 | 仅称天气背景的受控证据任务 |
| 来源绑定是可区分能力 | 同值修订与重复delivery等最小对照 | 作为工作假设，不声称已证明新能力 |
| 跨模型/来源成立 | 新模型与独立source，冻结heldout | 不从三个源和一个矩阵外推 |

ALCE、StateMemBench、STALE等已覆盖引用、当前状态、过期状态和行为适应的相关问题；不要声称首次做其中任一单点。[S01,S04,S05]

## 13.6 heldout的最后闸门

在查看七个保留事件的模型输出前，冻结：任务版本、分布、生成种子、renderers、因素、模型、预算、输出模式、主指标、失败处理和统计方法。

如看过heldout后修改生成器、prompt、scorer或选择标准，必须标为探索性，并另设真正未见测试。不能删除旧结果后继续使用“heldout”名称。

原540协议扩到七来源，一条件/一模型/一repeat的数量为1260；若实际选择不同任务族/机会，按新的schedule重新计算，不能沿用旧NHC轨70checkpoint的数量。

## 交付

可复算的结果表、研究主张矩阵、每种验证的覆盖范围、许可证/来源文件、CPU复现说明和最小CI测试。CI只有实际运行后才标通过；不默认把私有raw captures、模型权重或凭据上传公开。

---

# 14. 各PR的依赖与优先级总表

| PR | 优先级 | 关键交付 | 前置依赖 | 默认资源 | 通过后能消除的不确定性 |
|---|---|---|---|---|---|
| P6-00 | P0 | 材料覆盖、基线复现、历史保护 | 当前仓库 | CPU/offline | 确切知道哪些证据可验证 |
| P6-01 | P0 | 字段错误、引用分类、曝光/载体表 | P6-00 | CPU/offline | 230处引用类错误究竟是什么 |
| P6-02 | P0 | 来源刷新probe、变形/负控、oracle测试 | P6-00；可并行P6-01 | CPU/offline | 协议是否区分数值与权威来源，是否有捷径 |
| P6-03 | P1 | 新repeat运行/审计、fault tests | P6-00 | CPU mocks | 新重复矩阵能否不污染历史、安全执行 |
| P6-04 | P1 | 注册矩阵、资源scope、dry-run | P6-01/02/03 | CPU；推理另授权 | 同硬件复验是否具备可解释设计 |
| P6-05 | P1 | 匹配载体、来源/数值/组合泛化候选 | P6-02 | 离线；采集另许可 | 方法差是否只是表示/长度，来源是否过窄 |
| P7-00 | P1 | 原生forecast bridge解析/参考/fixture | P6-02 | 离线；来源获取另许可 | 天气领域外部有效性是否可自动验证 |
| P7-01 | P2 | 第二家族adapter与同版本候选 | P6-03/04 | CPU mocks；GPU另授权 | 结论是否只属于一个模型 |
| P7-02 | P2 | source级统计、主张矩阵、heldout冻结 | 前述已完成部分 | CPU；heldout另授权 | 论文结论边界与复现是否完整 |

不必串行等待所有运行层完成再研究自然产品：P6-01/02与P7-00本地parser可以并行，使用独立worktree/新输出目录；正在执行的实验使用冻结代码，不热修改。

---

# 15. 接口与命令合同：Codex要实现什么

以下全是**拟新增接口**。不是当前仓库已存在命令，不能在实现前记录为执行成功。

## 15.1 Python模块接口建议

```python
# 签名示意；根据现有类型适配，所有函数禁止隐式模型/网络调用。
def inspect_coverage(repo_root, run_specs, output_dir): ...
def build_field_table(audited_runs, output_dir): ...
def classify_citations(public_request, decision, expected, lineage): ...
def compare_exposure(base_prepared, stress_prepared, slot_mapping): ...
def compile_behavioral_suite(spec, output_dir): ...
def validate_behavioral_suite(dataset_dir): ...
def make_repeat_schedule(dataset, conditions, methods, repeat_ids, seed_scheme): ...
def freeze_study(spec, output_dir, *, production_authorized=False): ...
def simulate_study(execution_dir, output_dir, fixture_backend): ...
def audit_repeat_run(execution_dir, run_dir): ...
def summarize_source_clustered(audited_reports, registration): ...
```

函数返回结构数据；Markdown/CSV是从结构数据生成的派生物。输入无效时明确错误码，不悄悄删除行或自动纠正来源。

## 15.2 CLI合同

```bash
# 拟实现：先仅生成可用材料清单
python -m disastertrace.post_p5.cli inspect \
  --config configs/post_p5/offline.yaml \
  --output work/post-p5-v1/coverage

# 拟实现：只读已审计回答，生成离线错误与曝光分析
python -m disastertrace.post_p5.cli analyze \
  --config configs/post_p5/offline.yaml \
  --output work/post-p5-v1/analysis

# 拟实现：生成并校验controlled probes，无模型
python -m disastertrace.post_p5.cli build-probes \
  --spec configs/post_p5/behavioral_probe_spec.yaml \
  --output work/post-p5-v1/probes
python -m disastertrace.post_p5.cli verify-probes \
  --dataset work/post-p5-v1/probes

# 拟实现：冻结未授权的新实验候选
python -m disastertrace.post_p5.cli plan \
  --spec configs/post_p5/replication_candidate.yaml \
  --output work/post-p5-v1/replication_candidate

# 拟实现：mock/diagnostic模拟，不生成真实模型答案
python -m disastertrace.post_p5.cli simulate \
  --execution work/post-p5-v1/replication_candidate \
  --output work/post-p5-v1/rehearsal
```

以上命令均不应自动创建production authorization。生产命令放单独入口，缺新授权或资源上限直接拒绝；本计划故意不提供“一键启动所有GPU任务”命令。

## 15.3 当前可用的历史CPU验证方式

按照仓库 `REPRODUCE_ACP.md` 和 `REVIEW_FOR_CHATGPT_PRO_P5.md` 的实际说明，在独立复制/解压目录运行；确保所用解释器和冻结源码存在。[R01,R02]

其中report的 `--verify`/`--require-model` 路径用于对照保存报告，不等于live采集。首次使用前读CLI定义；新分析优先写新目录，避免误触非verify覆盖路径。

不要求Codex照抄一个不存在的review虚拟环境路径；记录本机实际路径即可。

## 15.4 状态记录模板

```markdown
# Post-P5 Implementation Status

## Baseline
- repository_commit:
- working_tree_state:
- source_coverage:
- historical_reconstruction_scope:

## Current PR
- id:
- status: TODO / IN_PROGRESS / DONE_OFFLINE / READY_FOR_AUTHORIZATION / BLOCKED
- changed_files:
- completed_behavior:

## Executed verification
- command:
- exit_code:
- result:
- artifact_path:
- limitations:

## Resource use
- actual_model_generations: 0
- gpu_jobs: 0
- paid_api_calls: 0
- network_acquisition:

## Remaining questions
- confirmed_defects:
- hypotheses_not_yet_tested:
- disclosed_limitations:
- next_step:
```

不要在“completed”里放下一步计划。测试数量以实际命令本次结果为准，历史各轮重复测试次数不得相加。

---

# 16. 测试与验收的最小清单

## 16.1 分析纯函数

- P5摘要与逐回答重算一致；summary-only时不谎称raw核验。
- 一个checkpoint多个字段错误不增加checkpoint数。
- 值正确但旧引用的样本归引用主类；引用多标签不重复主分母。
- 动作与风速重叠保持可查询，不新加错误题。
- unknown/known分母为零返回null。
- report行乱序/重复slot/不匹配execid/auditid拒绝。

## 16.2 语义与来源

- 同值supersession刷新来源；duplicate delivery不刷新来源。
- partial PATCH保留未修改字段原来源。
- 不同entity/window不能互相覆盖；相同数字不构成同一事实。
- 原公开约束下非法revision图被拒绝，不转成unknown。
- 缺失首次支持与“已经看过但本轮没再次提供”不混淆。
- 原数据的已知/未知来源标记不因模型结果改变。
- public view没有future/private gold/任务答案元数据。

## 16.3 运行与schema

- 结构合法错误答案保持可达且进入carrier。
- invalid不替换previous，且保留失败文本。
- repeat/method/condition隔离；scope不接受旧production授权。
- 稳定pairseed与唯一trajectory并存。
- 截断、fallback decoder、动态答案候选enum均被检测。
- 默认模式不import/instantiate GPU引擎，不访问模型服务。

## 16.4 新自然forecast轨

- 005与009同valid_at原文fixture分别解析95KT与105KT。
- 其他valid_at数值不覆盖目标；current observed maxwind不当forecast maxwind。
- 月末/年末日期恢复、坐标方向、KT与mph标签严格处理。
- 后来产品有terminal/unsupported block时，不能静默跳过该产品并宣称旧数值仍是当前参考；按新准入规则拒绝或显式建模。
- 原文行号/产品版本与引用可复算。
- 上游缺失/无法验证≠自动生成unknown模型题。

## 16.5 完成定义

每个PR至少包含：可审阅diff、针对性测试、真实执行日志、产物路径、已知限制、无历史变更检查、资源消耗记录。没有性能改进也可以是有效研究结果；不得为得到正结果修改固定分母或筛掉失败。

---

# 17. 节奏安排与决策闸门

以下是开发工作量规划，不是运行时或研究成功保证。

| 时间窗口 | 优先工作 | 本阶段结束时应拿到 |
|---|---|---|
| 第一轮1–2个开发日 | P6-00/01 | 真实错误明细、曝光混杂表、可核查最小例子 |
| 接下来2–3个开发日 | P6-02与P6-03 mock | 来源刷新契约、负控、可隔离repeat调度 |
| 之后1–2个开发日 | P6-04 | 注册候选与明确待授权范围 |
| 并行后续 | P6-05、P7-00本地fixture | 广泛来源计划与真实forecast桥接原型 |
| 获新授权后 | 小型同硬件复验、第二模型 | 不再混合硬件/任务版本的比较 |
| 最后 | P7-02 | 冻结任务后才执行heldout |

## Gate A：是否需要先修代码？

有影响分数/输入/接受状态的可执行反例：先修新版本并建立回归测试，旧分数保留。只是已披露的种子/硬件限制：改新实验设计，不修改历史分数。

## Gate B：是否立刻做6480？

默认否。先做离线错误/曝光/语义检查，确定是否有必要跑完整三因素重复。若最重要问题是方法近似持平且资源紧，2160候选更直接；若需要完整因素重复再选择6480。无论多少repeat，3来源的限制仍在。

## Gate C：是否加更多level？

只有长度/目标位置/语义因素分解后仍需要更长context，才另立context profile。不能用增加context掩盖来源引用错误，也不能裁原文让level16“跑起来”。

## Gate D：是否继续宣称天气benchmark？

若自然forecast bridge通过来源、parser、oracle与模型验证，可加强原生天气证据任务定位。若只有程序PATCH与风暴名字，则保留“weather-grounded controlled evidence updates”的有限表述；不要用更多名字补足领域novelty。

## Gate E：是否回到FrontierSearch或AutoResearch？

只有可执行性质、稳定模型失败和固定测试预算都已建立，才把自动测试生成作为单独方法研究。先与random/固定行为测试比较，不默认升级为本论文主要贡献。当前默认不训练、不改Gold、不让agent修改scorer来提分。

---

# 18. 来源与复用记录

所有外部来源本次查询日期为2026-09-08。GitHub默认分支是可变页面；**实际借代码前必须另行pin提交**。本计划没有把文献检索等同于已安装或已复现实验。

## 18.1 项目固定提交来源

固定根：`https://github.com/sisuolv/disastertrace-benchmark/blob/dd5ee358f9708e2eb2f2032db9eaac14fa237adc/`

- **R01** [REVIEW_FOR_CHATGPT_PRO_P5.md](https://github.com/sisuolv/disastertrace-benchmark/blob/dd5ee358f9708e2eb2f2032db9eaac14fa237adc/disastertrace-starter/REVIEW_FOR_CHATGPT_PRO_P5.md)：读取全文分段；当前任务、规模、历史、限制和复查范围。
- **R02** [README_P5_ACP_V1.md](https://github.com/sisuolv/disastertrace-benchmark/blob/dd5ee358f9708e2eb2f2032db9eaac14fa237adc/disastertrace-starter/README_P5_ACP_V1.md)：已完成P5、旧scope消耗、真实结果与验证入口。
- **R03** [RESULT_TABLES.md](https://github.com/sisuolv/disastertrace-benchmark/blob/dd5ee358f9708e2eb2f2032db9eaac14fa237adc/disastertrace-starter/artifacts/p5_stress_level4_v1/analysis/RESULT_TABLES.md)：实际九个方法/因素单元分子分母；本次只对其算术独立复算。
- **R04** [controlled/compiler.py](https://github.com/sisuolv/disastertrace-benchmark/blob/dd5ee358f9708e2eb2f2032db9eaac14fa237adc/disastertrace-starter/src/disastertrace/controlled/compiler.py)：完整读取的私有参考归约实现。
- **R05** [controlled/public_oracle.py](https://github.com/sisuolv/disastertrace-benchmark/blob/dd5ee358f9708e2eb2f2032db9eaac14fa237adc/disastertrace-starter/src/disastertrace/controlled/public_oracle.py)：本次读取1–220行；未据此声称全文件无缺陷。
- **R06** [controlled/scorer.py](https://github.com/sisuolv/disastertrace-benchmark/blob/dd5ee358f9708e2eb2f2032db9eaac14fa237adc/disastertrace-starter/src/disastertrace/controlled/scorer.py)：本次读取1–230行；固定分母和support_ok算术。
- **R07** [stress_eval/execution.py](https://github.com/sisuolv/disastertrace-benchmark/blob/dd5ee358f9708e2eb2f2032db9eaac14fa237adc/disastertrace-starter/src/disastertrace/stress_eval/execution.py)：本次读取1–220行；固定540/repeat1和旧授权边界。
- **R08** [stress_eval/runtime.py](https://github.com/sisuolv/disastertrace-benchmark/blob/dd5ee358f9708e2eb2f2032db9eaac14fa237adc/disastertrace-starter/src/disastertrace/stress_eval/runtime.py)：读取采集主体，包括backend、carrier、intent与capture。
- **R09** [constrained_eval/contract.py](https://github.com/sisuolv/disastertrace-benchmark/blob/dd5ee358f9708e2eb2f2032db9eaac14fa237adc/disastertrace-starter/src/disastertrace/constrained_eval/contract.py)：structural-only schema与固定property order。
- **R10** [analyze_p5.py](https://github.com/sisuolv/disastertrace-benchmark/blob/dd5ee358f9708e2eb2f2032db9eaac14fa237adc/disastertrace-starter/artifacts/p5_stress_level4_v1/analyze_p5.py)：历史分析重算与verify路径。
- **R11** [compare_stress.py](https://github.com/sisuolv/disastertrace-benchmark/blob/dd5ee358f9708e2eb2f2032db9eaac14fa237adc/disastertrace-starter/artifacts/p5_stress_level4_v1/compare_stress.py)：本次读取1–230行；配对、映射、机会与公共曝光。
- **R12** [NEXT_PHASE_PLAN_ACP.md](https://github.com/sisuolv/disastertrace-benchmark/blob/dd5ee358f9708e2eb2f2032db9eaac14fa237adc/disastertrace-starter/artifacts/p5_stress_level4_v1/NEXT_PHASE_PLAN_ACP.md)：原候选6480与来源/模型/heldout后续路线。
- **R13** [pyproject.toml](https://github.com/sisuolv/disastertrace-benchmark/blob/dd5ee358f9708e2eb2f2032db9eaac14fa237adc/disastertrace-starter/pyproject.toml)：已存在Hypothesis/pytest等开发依赖。

本次未完整核验：全部原始captures、完整tar.gz、每个冻结源码文件、所有tests、当前分支完整CI。相关陈述来自R01/R02的仓库记录；不是本次重执行的结论。

## 18.2 在线论文、开源与官方文档

- **S01 ALCE** — [作者仓库](https://github.com/princeton-nlp/ALCE)、[论文](https://arxiv.org/abs/2305.14627)、[`eval.py`](https://github.com/princeton-nlp/ALCE/blob/main/eval.py)、[`post_hoc_cite.py`](https://github.com/princeton-nlp/ALCE/blob/main/post_hoc_cite.py)。借鉴答案/引用评价分离；注意其自动NLI评价和post-hoc citation不符合本项目主评分约束，不直接导入。
- **S02 CheckList** — [作者仓库](https://github.com/marcotcr/checklist)、[论文](https://arxiv.org/abs/2005.04118)。借鉴MFT/INV/DIR和期望关系，使用本项目已有测试依赖轻量实现；不声称复现其原始自然语言任务。
- **S03 RULER** — [作者仓库](https://github.com/NVIDIA/RULER)、[论文](https://arxiv.org/abs/2404.06654)。借鉴独立配置长度/复杂度与variable tracking；读取具体代码前核对分支，当前README中的旧评估流程/更新分支说明不可混用。候选阅读 `scripts/data/synthetic/`、`scripts/data/template.py`、`scripts/synthetic.yaml`，以pin后的真实目录为准。
- **S04 StateMemBench / StateMem** — [Can Agent Memory Systems Track Evolving State?](https://arxiv.org/abs/2608.19652)、[v1全文](https://arxiv.org/html/2608.19652v1)。关注当前/旧状态分类、supersession和长度/成本控制。本次未确认可供直接复现的官方代码包，状态为 `paper_verified_code_not_verified`。不要与Microsoft STATE-Bench混淆。
- **S05 STALE** — [论文](https://arxiv.org/abs/2605.06527)。关注状态解析、错误前提抵抗和行为适应的区别。本次核实论文，未将代码作为依赖。
- **S06 LongMemEval** — [作者仓库](https://github.com/xiaowu0162/LongMemEval)、[论文](https://arxiv.org/abs/2410.10813)。借鉴知识更新、时间推理与拒答能力组织；其公开用法通过模型grader评估答案，本项目不启用该路径。本次借鉴基础协议，不声称已经核查LongMemEval-V2等所有新变体。
- **S07 MemoryAgentBench** — [作者仓库](https://github.com/HUST-AI-HYZ/MemoryAgentBench)、[论文](https://arxiv.org/abs/2507.05257)。借鉴增量交互设置。README和论文版本对能力类别有命名差异，保存各自版本，不把不同类别名合成新定义。
- **S08 Microsoft STATE-Bench** — [作者仓库](https://github.com/microsoft/STATE-Bench)。借鉴状态断言与重复可靠性组织；其企业任务、模拟器或判断器不属于当前实际运行框架，也不是StateMemBench的代码。
- **S09 Hypothesis** — [Stateful tests官方文档](https://hypothesis.readthedocs.io/en/latest/stateful.html)。用于纯程序状态机和最小反例；安装版本需pin，本计划未运行其测试。
- **S10 vLLM** — [v0.10.2 reproducibility](https://docs.vllm.ai/en/v0.10.2/usage/reproducibility.html)。采用对应P5版本的调度/随机状态说明；不以新版文档替代旧行为。
- **S11 XGrammar** — [官方仓库](https://github.com/mlc-ai/xgrammar)。保留P5固定0.1.23与schema身份；实际依赖按原锁定清单，不升级“latest”。
- **S12 NHC原始forecast产品** — [Ian forecast advisory 005](https://www.nhc.noaa.gov/archive/2022/al09/al092022.fstadv.005.shtml)、[Ian forecast advisory 009](https://www.nhc.noaa.gov/archive/2022/al09/al092022.fstadv.009.shtml)。本次直接核对其同有效时间forecast块；仅作为开发示例，未下载完整来源池或证明历史首次公开时刻。
- **S13 原生alert链备选** — [NWS Alerts Web Service](https://www.weather.gov/documentation/services-web-alerts)、[IEM VTEC下载](https://mesonet.agron.iastate.edu/request/gis/watchwarn.phtml)、[pyIEM](https://github.com/akrherz/pyIEM)、[`src/pyiem/nws/vtec.py`](https://github.com/akrherz/pyIEM/blob/main/src/pyiem/nws/vtec.py)。只核实服务/代码入口，不等于已验证全量历史覆盖或引用语义。
- **S14 AFDBench** — 用户提供的 `AFDBench.pdf`，任务定义第2页、指标第3页、限制第5–6页；[arXiv记录](https://arxiv.org/abs/2608.24954)。仅用于forecast-to-text任务边界，不因其标题自行认定自主科研能力或已核实会议录用。

### 外部源码纳入项目时的记录格式

```yaml
resource_id: S02
url: https://github.com/marcotcr/checklist
use_type: design_reference
resolved_commit: null
license_verified: false
files_copied: []
notes: No upstream code copied yet; resolve commit and license before copying.
```

本计划不伪造外部commit；未复制代码时可以保持design_reference。仓库许可不能覆盖其提及的所有第三方数据、模型和服务。

---

# 19. 可以直接交给Codex的启动提示

```text
请基于当前 disastertrace-benchmark 的 next-phase-v1 工作区执行，
先读取适用 AGENTS.md、REVIEW_FOR_CHATGPT_PRO_P5.md、README_P5_ACP_V1.md、
IMPLEMENTATION_STATUS.md、DECISIONS.md、BLOCKERS.md 和本计划。

计划审阅基线是 dd5ee358f9708e2eb2f2032db9eaac14fa237adc。
若当前HEAD不同，先比较相关改动，不回退、不覆盖用户文件。

本轮只完成 PR-P6-00～PR-P6-04 的离线实现和验收。
重点不是重做已完成的T6/P2/P3/P4/P5，也不是立刻启动6480次实验：
先重建P5字段错误与实际曝光，解释230处“值对引用错”，
补充同值来源刷新/重复delivery/作用域负控，再实现新repeat身份与mock调度审计，
最后生成等待授权的同硬件实验候选。

默认：零真实模型调用、零GPU作业、零付费API、零权重下载、
不运行heldout、不训练、不联网采集、不push、不发布。
P5已消耗的授权和run目录不可复用；新矩阵数字不是用户授权。

必须先补针对性测试，再实现；保持原parser/scorer和历史原始回答不变。
valid-but-wrong照常进入模型carrier，invalid保留失败且不替换上次valid。
不能引入Gold修复、事后引用补写、LLM judge或静默context截断。

缺少全量capture时，继续完成fixtures与代码，把真实归因标为BLOCKED，
不得用摘要表对账冒充完整CPU重算，不得把程序diagnostic标成真实模型结果。

每个PR更新 docs/post_p5/IMPLEMENTATION_STATUS.md：实际改动、命令、退出码、
测试结果、产物路径、资源消耗、未验证范围和下一步。
完成P6-04后停止在READY_FOR_AUTHORIZATION，不自行启动生产实验。
```

## 会话恢复提示

```text
请先读适用AGENTS与 docs/post_p5/IMPLEMENTATION_STATUS.md，
核对工作区、最新commit及上次实际产物，再继续尚未完成的离线PR。
不要重新执行已完成或已消耗的模型任务；不要把旧对话的预算视为新授权。
若报告与capture/源码身份不符，先定位差异并保留证据，不改历史文件来过校验。
```

---

# 20. 最终交付标准

第一阶段的成功不是“又多了一大批测试与hash”，而是能用代码和原始证据回答：

1. P5引用类错误究竟有多少是旧祖先、错作用域、错字段、错行或多余引用？
2. 哪些P4/P5变化在真正新证据出现前就发生，哪些仅由不同载体历史伴随？
3. 同值修订与重复交付能否被oracle、负控和模型分别区分？
4. 新repeat执行是否在同硬件profile下保持独立轨迹、固定分母和可复算原始记录？
5. 原生forecast产品能否提供无需逐题人工标签的时间/版本验证轨？

如果这些问题得到可靠回答，再扩大来源、模型和正式测试；如果没有，就明确收缩主张。**不要通过换标题、加更多灾种或启动更多GPU代替这一步。**
