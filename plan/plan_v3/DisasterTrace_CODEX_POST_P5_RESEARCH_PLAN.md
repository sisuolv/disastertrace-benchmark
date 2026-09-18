# DisasterTrace：P5 之后的研究与代码增量计划

> 面向 Codex 的独立执行规格。先读当前仓库与适用 `AGENTS.md`，再按里程碑实施；不要把本文当成模型/GPU调用、历史作业重启或数据发布授权。

| 项目 | 本计划的绑定 |
|---|---|
| 文档日期 / 检索日期 | 2026-09-08 |
| 计划版本 | `post_p5_research_plan_v1` |
| 仓库 | `sisuolv/disastertrace-benchmark` |
| 已核对分支 | `next-phase-v1` |
| 已核对提交 | `dd5ee358f9708e2eb2f2032db9eaac14fa237adc` |
| 当前研究阶段 | P5 已完成；本文件中的 M00–M09 均为后续建议，不是已完成工作 |
| 默认首轮执行范围 | M00–M03：历史只读审计、错误分解、曝光分析、重复协议和离线验收；完成后停止 |
| 默认模型生成额度 | 0；不自动读取模型凭据、不启动 GPU、不下载权重 |
| 默认数据联网 | 关闭；M04 的有界官方资料获取需要明确启用 |
| 评分约束 | 自动 Gold、确定性评分；不新增逐题人工标注/专家裁决；不使用 LLM Judge 作为主评分器 |
| 修改策略 | 在现有项目上增量开发，保留历史 Gold、源码快照、回答、失败记录和已消耗的 launch claim |

**资料与执行边界。** 本文依据当前仓库记录、已读核心代码、上一版 P5 复查计划，以及重新检索的官方论文/仓库/文档形成。本文作者没有在本次工作中重跑 P5 模型、完整 capture 复验、GPU测试或全部 CPU 测试。文中结果属于仓库已记录结果或明确标注的算术汇总。外部项目“能访问 README”不等于已经安装或完成复现。来源见第 25 节。

---

## 0. 给 Codex 的执行摘要

### 0.1 现在最值得做什么

不要重做 T6 输出校准、U1–U3、基础 collector、XGrammar 接入和 P5 三因素运行。这些在绑定版本已经完成。[R01]

下一阶段围绕三个可检验问题推进：

1. **为什么值正确，当前证据绑定仍然错误？** 用已有回答区分旧版本、错实体/窗口、错字段/行、缺引用、混合引用和历史载体关联，先不新增模型调用。
2. **压力因素的影响能否在共同硬件、匹配随机化与完整失败分母下复现？** 先做同硬件重复的离线准备，再申请一个完整的新矩阵。
3. **同样的问题是否出现在真实官方预报的版本更新中？** 接入 NHC 同一绝对有效时刻的多个预报版本，分别提供原始表与等信息结构化表；不要只增加合成风暴名称。

推荐路线：

```text
冻结 P5 历史
  ├─ M01：230处引用类错误 + 实际曝光 + 语义捷径审计（零推理）
  ├─ M02–M03：匹配重复协议、状态隔离、程序演练和冻结执行包（零推理）
  └─ M04–M05：真实 NHC 预报版本资料和双表示任务（资料/CPU路径）
                          ↓
            M06：生成分布多样性与变形测试
                          ↓
       M07：批准后运行新矩阵；M08：第二模型与预算匹配的方法实验
                          ↓
             M09：冻结后 heldout / 可移植发布准备
```

### 0.2 首轮必须交付的六个文件/包

建议写入新目录 `work/post-p5-offline-v1/`，不得覆盖历史输出：

```text
repo_baseline.json
p5_citation_attribution.jsonl
p5_attribution_reconciliation.json
p5_exposure_manifest.jsonl
CLAIM_AUDIT_POST_P5.md
paired_execution_preparation/   # 未授权、未生成的执行规格与程序诊断
```

完成后写 `HANDOFF_POST_P5.md`：列出实际命令、实际退出码、已通过/失败/未执行测试、缺失资料、所选下一步。不要只有新的计划、没有产物；也不要为了“完成全部里程碑”越过授权停止点。

### 0.3 重要优先级

- **必须先做：**历史计数对账、曝光定义、随机种子与运行身份解耦。
- **可以并行：**真实预报资料可行性与生成器参数设计，不需要等 GPU实验结束。
- **稍后做：**第二模型、成本匹配的来源复查方法、框架导出。
- **明确延后：**level16、更大上下文、完整港口运营、原始雷达/SAR、训练、复杂记忆数据库、上百个工具。

---

## 1. 事实表：不要把旧阶段的待办重新当成当前缺口

### 1.1 已记录阶段

| 阶段 | 仓库已记录结果 | 不能据此声称 |
|---|---|---|
| P1 | 90响应/91尝试；中断及未知请求保留 | snapshot低分证明没有记忆 |
| T6 | 270个真实DeepSeek回答，选择共同8192输出上限 | 对任意模型与更长任务都足够 |
| P2初版 | 270回答；6无效、3处引用问题 | 可选择性重试并替换原结果 |
| P2契约v2 | 新270回答全正确 | 可以直接填入新版540回答矩阵 |
| P3自由输出 | Qwen3-8B，540回答，200契约合法，193完整正确 | 193/200可代替193/540 |
| P4结构约束 | 540契约全通过，490完整正确 | grammar解决语义和证据问题 |
| P5压力测试 | 三组各540，共1620；契约全通过，1360完整正确 | 108变体就是108独立天气事件 |

来源：[R01–R03]。旧结果不得因为新分析器、模板或显示格式改变而被覆盖。

### 1.2 当前 P5 设计

- 三个开发来源：`AL092021`、`AL062018`、`AL052019`。
- 基础矩阵：3来源 × 3任务族 × 2case × 2branch = 36episode / 18配对root。
- 每episode五个checkpoint；每方法180个回答机会；三方法540个回答/条件。
- 三种方法均看累计已交付证据；只在先前答案载体上不同。
- 状态四字段：最大持续风速、最低中心气压、中心纬度、中心经度。
- 初始数值有真实来源；实体编码、2040窗口、PATCH值、版本图与交付时间是受控生成。
- 模型：ModelScope来源的Qwen3-8B完整BF16；不能把已绑定文件身份改写成未核对的Hugging Face commit。
- 历史环境：Python3.10.12 / Torch2.8.0+cu128 / vLLM0.10.2 V1 / XGrammar0.1.23。
- thinking开启；temperature0.6、top_p0.95、top_k20；context16384，总生成8192，后者包含reasoning。
- P4使用H100 MIG，P5使用完整H100；P5条件身份也改变slot种子。下一轮不能沿用这些混杂后声称严格因果结论。

### 1.3 后续分析的硬对账锚点

| P5条件 | snapshot完整正确 | structured_state完整正确 | answer_history完整正确 |
|---|---:|---:|---:|
| revision_chain | 150/180 | 164/180 | 135/180 |
| irrelevant_scope | 155/180 | 154/180 | 135/180 |
| late_stale_replay | 163/180 | 172/180 | 132/180 |

从已保存表格相加得到：

```text
known_value_correct        4986 / 5076
known_grounded_correct     4756 / 5076
all_correct_checkpoints    1360 / 1620
value_or_status_errors       90
citation_only_field_errors  230
total_field_errors          320
incorrect_checkpoints       260
action_errors                29  # 与风速错误重叠，不另算29道错题
c0_all_correct              324 / 324
c1_to_c4_all_correct       1036 / 1296
```

这些是**对指定历史包的复核目标**，不得把计数写死进分类器。分类逻辑应适用于任意同协议run；历史回归测试才绑定上述计数。[R02–R03]

---

## 2. 文献检索后，对研究定位的调整

### 2.1 不应继续单独包装成 novelty 的部分

StateMemBench已经直接研究当前状态、被替代状态和状态式记忆；STALE研究过时前提及下游行为适配；LongMemEval-V2还覆盖动态状态、工作流知识和前提意识。因此，“动态状态”“过时记忆”“显式状态表”不能单独成为本项目的创新主张。[L02–L05]

**新的工作假设，而非已证实结论：**

> DisasterTrace 的价值在于把“值正确”与“值绑定到当前适用的证据版本”分开，在可自动核验的受控流和真实预报版本流中，测量这种联合可靠性如何受证据到达、作用域和先前模型答案影响。

支持该主张需要三个层次同时成立：

| 层次 | 需要建立的证据 | 不足以代替它的材料 |
|---|---|---|
| 测量正确 | 确定性Gold、公开oracle、失败分母、来源归因、可复算 | 大量单元测试数字或hash清单本身 |
| 实验可解释 | 新鲜共同基线、同硬件、预声明随机化、有效曝光与负控 | 历史P4与P5直接相减 |
| 领域有效 | 真实预报有效时刻对齐、原文读取、真实版本更新 | 把同一合成模板换成更多风暴名字 |

### 2.2 不预先保证论文结论

以下均是待检验假设：

- H1：在格式合法时，证据版本绑定仍然比数值读取脆弱。
- H2：携带全部答案历史可能增加陈旧来源干扰，但不保证所有模型均如此。
- H3：结构化状态对某些压力有效，却未必能抵抗作用域干扰。
- H4：上述现象在真实同有效时刻预报版本任务中仍可观察。
- H5：针对来源的复查比相同额外预算的普通再回答更有效。

不得用“必须看到rank inversion / 必须让强模型失败”作为数据准入或Go/No-Go条件。出现满分、无方法差异或假设被否定，同样是有效结果。

---

## 3. 可借鉴的开源项目：复用什么，明确不复用什么

下表是本轮资料核对结果。`README/code inspected`不表示运行过代码；所有实际导入都必须再固定commit、许可证与文件哈希。详见第25节完整URL。

| 资源 | 已核对内容与启发 | 最小复用方式 | 本轮不采用 |
|---|---|---|---|
| **ALCE** [L01] | 正确性与citation quality分开；仓库有`eval.py` | 借鉴指标分层，构建我们的确定性版本/行引用诊断 | 不搬AutoAIS/NLI评分、首行截断或post-hoc加引用来改历史答案 |
| **StateMemBench / StateMem** [L02] | 2026-08论文；当前/过时状态分类，长度与成本匹配控制 | 定义旧版本错误标签、复查方法的等预算对照 | 本轮未核实官方实现仓库，不虚构clone地址，不宣称复现StateMem |
| **STALE / CUP-Mem** [L03] | 论文及官方`STALE/`、`cup_mem/`目录已核对 | 后续设计State Resolution / Premise Resistance / Policy Adaptation诊断 | 不导入其自动模型判分或新增主观标签；不复制普通生活场景当气象Gold |
| **LongMemEval** [L04] | 知识更新、时间推理、abstention及证据会话组织 | 分离“信息访问”和“读取后的更新”两个研究因素 | 不运行`evaluate_qa.py`的模型judge；不把全证据实验当记忆依赖 |
| **LongMemEval-V2** [L05] | 2026-05论文、2026-08仓库更新；context-gathering和多模态轨迹 | 借鉴memory输入/证据输出接口及检索与reader解耦 | 不接入巨量轨迹、coding-agent依赖或其默认LLM judge |
| **Microsoft STATE-Bench** [L06] | task-local状态，pass@1与所有重复成功的pass^5分开 | 新增trajectory级重复可靠性；接口上隔离任务状态 | 不引入企业工具/user simulator/UX judge；不改GPU环境满足其依赖 |
| **CheckList** [L07] | 能力×测试类型的行为测试设计 | 最小功能、应保持不变、应按方向变化的测试矩阵 | 不为本项目安装一整套旧NLP模型依赖 |
| **RULER** [L08] | 可配置长度与任务复杂度的合成测试 | 把token长度和有效证据复杂度分开设计 | 不照搬max-position修改、不静默截断、不复制旧runner；导入前确认分支迁移状态 |
| **ExtremeWeatherBench** [L09] | 官方`events.yaml`、事件优先的物理预测评测 | 借鉴事件注册和分层采样，保持forecast验证与LLM证据读取分开 | 不下载大规模reforecast/ERA5；当前README仍称论文in preparation，不把它当已核实正式论文 |
| **Tropycal** [D01] | NHC讨论/operational forecast获取接口；预报ID不等于讨论ID | 独立CPU资料适配或解析交叉检查 | 不把重建cone当官方原图；不把HURDAT事后best track当发布时预测 |
| **vLLM + XGrammar** [D02–D03] | 已在项目使用；可重复性和结构约束边界 | 保持既有版本，新增配对seed与调度验收 | 不为了“最新”升级正在做共同对照的后端；不动态mask正确答案 |
| **Hypothesis** [D04] | 状态机、规则序列与反例收缩 | 用于软件测试，不用作模型结果 | 不把自动测试数量当真实场景量 |
| **Inspect AI** [D05] | 自定义solver/scorer、TaskState与日志 | 最后做一个episode一个sample的可选导出/适配 | 不替换原生冻结执行链；不启用中间Gold评分来指导模型 |

**第一轮真实需要增加的依赖应很少。** 优先标准库、已有项目依赖；Hypothesis放CPU dev extra。Tropycal、Inspect等放独立可选环境，不与固定Torch/vLLM环境混装。

---

## 4. 源码复用地图：先用自己的已验证模块

所有下列路径相对于`disastertrace-starter/`，属于绑定版本中的已有路径。[R04]

| 已有模块 | 保留/复用 | 新增层处理的事情 |
|---|---|---|
| `controlled/schema.py` | 严格四字段协议、数值/引用验证 | 新真实预报轨使用独立三字段协议，不强行加入预测气压 |
| `controlled/compiler.py` | 历史自动Gold重算 | 新分析只读消费，不改过去Gold |
| `controlled/public_oracle.py` | 公开证据oracle、错误程序、per-key-latest-issued | 新资料轨独立parser/oracle；禁止用oracle填模型carrier |
| `controlled/renderer.py` | 公开字段白名单和model-owned carrier | 新表示保持所有已交付候选，不偷偷只展示目标Gold |
| `controlled/scorer.py` | P2–P5原指标与分母 | 新指标做overlay，明确update包含来源变化 |
| `local_eval/adapter.py` | chat template/token计数/reasoning分隔经验 | 新版本分离运行键和sampling键 |
| `local_eval/difficulty.py` | 旧三因素的准确变换定义 | 曝光分析、未来参数化变体，不编辑旧factor |
| `constrained_eval/contract.py` | structure-only限制原则 | 新schema仍需可生成语义错误的反例测试 |
| `stress_eval/{execution,runtime,audit}.py` | freeze、journal、采集、独立重建 | 新repeat协议包装；不绕过历史single-repeat验证 |
| P5的`analyze_p5.py`、`compare_stress.py` | 表格/映射/双向变化与历史路径说明 | 更细引用归因与实际曝光 |

**禁止全仓重构。** 优先新增`post_p5/`的少量模块，再按真实预报需要新增`real_forecast/`。出现相似实现时先核对可复用接口；不是每个指标都创建一个文件。

建议结构（均为拟新增，允许按现有风格微调并记录）：

```text
src/disastertrace/
  post_p5/
    inventory.py       # 审阅基线、路径与身份
    attribution.py     # 只读引用错误分类
    exposure.py        # 公开证据/载体差异与有效压力
    analysis.py        # overlay与计数对账
    paired.py          # repeat、sampling key、schedule
    audit.py           # 新分析/配对包独立验收
    cli.py             # inspect/analyze/prepare/verify，默认离线
  real_forecast/
    schema.py
    parsers.py         # 主表解析器；公开oracle独立实现核心读取逻辑
    public_oracle.py
    alignment.py
    dataset.py         # 资料获取/构建可再按复杂度拆开
    evaluation.py
    cli.py
configs/post_p5/
docs/post_p5/
tests/test_post_p5_*.py
tests/test_real_forecast_*.py
```

---

## 5. M00：接手、基线与历史保全

### 任务

- [ ] **T00.1** 读取根目录和子目录适用`AGENTS.md`、最新review/status/decisions/blockers；用`git status --short`、`git rev-parse HEAD`记录工作区。HEAD变化时先比对较晚进展，不checkout回旧提交、不覆盖未提交修改。
- [ ] **T00.2** 判断拿到的是完整repo、完整P5 review包还是轻量附件。列出缺失captures/冻结源码/tokenizer/日志；缺什么只限制什么，不一概停止全部开发。
- [ ] **T00.3** 记录历史输入只读根目录与本轮新输出目录，检查不得包含/覆盖关系。归档解压时拒绝绝对路径、`..`、越界symlink/hardlink。
- [ ] **T00.4** 选择与历史报告绑定的源码重建，而不是直接用新工作区源码解释旧run。记录核对范围和实际退出码。
- [ ] **T00.5** 建立`IMPLEMENTATION_STATUS_POST_P5.md`和`DECISIONS_POST_P5.md`，并在原状态文件追加一个入口，不覆写历史时间线。

### 可用的历史只读重算示例

下列接口由P5复查文档给出；仅在路径存在、依赖满足时执行，不能把“写在这里”当作已成功运行：[R01]

```bash
cd disastertrace-starter
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=artifacts/p5_stress_level4_v1/units/revision_chain/execution_live/implementation_source/src \
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
python -m disastertrace.stress_eval.cli report \
  --execution artifacts/p5_stress_level4_v1/units/revision_chain/execution_live \
  --run work/p5-qwen3-revision-chain-v1 \
  --output artifacts/p5_stress_level4_v1/units/revision_chain/model_report \
  --require-model --verify
```

这里`--verify`核对保存报告，不是重新采集。不要运行历史`launch_p5.py`、`acp_worker.py`、`collect`入口。只安装CPU重算所需依赖；网络安装与离线重算应分开记录。

### 验收

`repo_baseline.json`至少包含HEAD、dirty状态、可访问历史包、输入hash、Python版本、实际重算状态、缺失项。没有完整capture时可以完成fixture测试和报告级分析，但不能写`full_capture_verified=true`。

---

## 6. M01-A：把230处引用类错误解释清楚

### 6.1 输入与输出

输入：P5已保存响应、实际公共请求、该checkpoint的Gold、preceding accepted carrier、record/assertion映射。P4只作对照，不混入P5计数。

主键：

```text
(run_id, condition_id, method, source_group, episode_id, checkpoint_id, field)
```

输出：

```text
p5_citation_attribution.jsonl
p5_attribution_summary.json
p5_attribution_reconciliation.json
method_factor_field_breakdown.csv
```

CSV是普通机器可读研究产物，不需要生成Excel工作簿。

### 6.2 确定性分类

先依据历史scorer区分`value/status wrong`和`value right, citation wrong`，再分类后者。**不能改变历史scorer的正确性判定。**

建议互斥`primary_reason`：

1. `missing_evidence`：known值正确但没有引用。
2. `unresolvable_reference`：不存在的record、未交付record、越界/非ASSERT位置；具体原因进flags。
3. `wrong_entity`：所引ASSERT实体与目标不匹配。
4. `wrong_window_or_kind`：实体匹配，但有效时刻/窗口或measurement kind不同。
5. `wrong_variable_or_unit`：scope正确但对应其他变量/单位。
6. `stale_same_key_version`：同FactKey的非当前版本，值相同也仍是旧来源。
7. `other_unsupported_binding`：可定位但不能归于以上；保留原始证据，不调用模型补分类。

每一个citation分别产生checks；slot的primary按上述公开优先级选首个适用原因。新增非互斥flags：

```text
has_valid_and_invalid_citations
record_exists_but_wrong_line
same_numeric_value_in_wrong_field
matches_previous_carrier_reference
prior_carrier_was_wrong
reference_was_correct_at_earlier_checkpoint
multiple_bad_references
```

正确引用混入错误引用仍保持历史失败。`matches_previous_carrier_reference`只说明相同，不证明复制机制或因果关系。

### 6.3 数据接口草案

以下为拟新增JSONL结构，未要求模型输出这些标签：

```json
{
  "analysis_version": "p5_attribution_v1",
  "run_id": "bound-existing-run",
  "episode_id": "from-existing-capture",
  "checkpoint_id": "c3",
  "field": "maximum_wind_mph",
  "legacy_value_correct": true,
  "legacy_grounded_correct": false,
  "primary_reason": "stale_same_key_version",
  "flags": ["reference_was_correct_at_earlier_checkpoint"],
  "submitted_citations": [],
  "citation_checks": [],
  "input_capture_sha256": "computed-at-execution"
}
```

示例仅说明schema，不是现成错误样本。

### 6.4 任务与验收

- [ ] **T01.1** 实现逐citation定位与FactKey比较，使用私有Gold仅在离线分析进程中判断。
- [ ] **T01.2** 实现互斥primary + 重叠flags，保证一个失败slot只进入一个primary计数。
- [ ] **T01.3** 单独关联此前合法carrier，不以reference字符串相等推断模型机制。
- [ ] **T01.4** 与90/230/320/260/29对账；分开field、checkpoint、action三个层级。
- [ ] **T01.5** 输出所有未分类情况和全部失败实例，不挑“最有故事”的样本作为主分析。

成功标准：任意同协议run可执行，P5完整输入下恢复对账锚点，旧报告hash不变，零新增推理。若输入不全，输出`partial_analysis`及覆盖分母，不伪造剩余分类。

**来源到实现。** ALCE启发“答案与引用分层”，StateMemBench启发“current/stale/other拆分”；这里采用确定性结构比较，并没有复用它们的自然语言判分器。[L01–L02]

---

## 7. M01-B：把“有压力标签”改成“实际受到什么压力”

### 7.1 为什么必须新增曝光分析

当前旧任务族的stale/scope机会不等于P5所有新增压力的实际发生点：额外旧记录在c4到达，额外作用域从c2到达。不能把c0–c3中的变化归因为尚未到达的旧记录。[R06–R07]

同时，revision_chain会修改旧记录的`supersedes`，不只是增加新record。因此仅做record_id集合差集不足以证明输入只变化了预期因素。

### 7.2 每checkpoint记录四个层次

| 层次 | 比较对象 | 用途 |
|---|---|---|
| 身份映射 | base/stress episode、record、assertion映射 | 确认比的是同一基础机会 |
| 公共证据 | 文本、元数据、交付顺序、重复数与修改记录 | 确认实际干预何时可见 |
| carrier | 之前合法模型state/history | 区分早期回答传播造成的差异 |
| wire/token | 完整prompt、token IDs、采样参数、batch/硬件 | 记录运行混杂，不把语义相同当字节相同 |

拟输出字段：

```text
new_unique_records
modified_existing_records
extra_deliveries
out_of_scope_assertions
visible_target_chain_depth
added_factor_visible
evidence_byte_equal
evidence_semantic_equal_under_declared_mapping
carrier_equal
prompt_token_equal
sampling_seed_equal
```

`semantic_equal`必须有可审计的映射规则，不可让LLM判断“大概等价”。没有可靠映射则为`unknown`，不是自动true。

### 7.3 新的只读指标

- `factor_exposed_all_correct`：实际已经看见新增/被修改证据的机会上的完整正确率。
- `pre_exposure_disagreement`：新增因素尚未出现的匹配机会中，答案是否已不同。
- `no_op_flip_rate`：六个零增量chain控制中的双向变化。
- `base_correct_stress_wrong`、`base_wrong_stress_correct`：两个方向都报告。
- `first_error_checkpoint`、后续连续错误长度：描述错误传播，末尾未恢复记右删失/未恢复，不虚构恢复时间。

以上是**分析overlay**，不改变P5主分数。零机会返回`null`，不填0或1。

### 7.4 任务

- [ ] **T02.1** 构建从真实公共输入得出的曝光表，检查修改记录而不只新增记录。
- [ ] **T02.2** 分开证据相同、carrier相同、seed相同和token相同。
- [ ] **T02.3** 保留六个零增量episode及尚未曝光checkpoint。
- [ ] **T02.4** 输出全部双向pair变化和每来源/任务族/字段切片。
- [ ] **T02.5** 验证overlay计数与原始主表加总一致；不基于overlay自动删除题目。

---

## 8. M01-C：语义可识别性、模板捷径与测量主张审计

### 8.1 保留合法简单解法

当前公开语义限制单根、线性、父先到达、issue严格递增。对正确FactKey取最新issued记录已经可以解出全部题目；`per-key-latest-issued`是合法对照，不是需要“修掉”的漏洞。[R05]

输出`SOLVER_EQUIVALENCE.md`：给出适用前提、简短等价性论证、用fixture验证前提改变后的边界。不能将“解释版本图”写成当前任务唯一必要的算法。

### 8.2 区分引用推理与字符串复制

当前record_id较长。错误可能来自版本判断，也可能来自复制ID或行号的生成负担。先分析错误类型；后续可以另设**双射短ID诊断**：所有公开记录和回答引用统一双射，目标和证据不变，另立表示版本。

约束：不只缩短正确候选；不把当前Gold ID嵌入grammar；不改旧答案字符串后重打原分数；新表示需要新生成。

### 8.3 主张账本

每条主张记录：

```text
claim_id
statement
status: source_reported | code_derived | hypothesis | demonstrated_bug | proposed
support_paths
counterexample_or_limitation
allowed_wording
forbidden_overclaim
```

- [ ] **T03.1** 完成per-key等价性与版本边界审计。
- [ ] **T03.2** 统计数值、阈值距离、操作位置、行序、ID长度等先验；不要推断未执行模型结果。
- [ ] **T03.3** 审核grammar的结构/语义边界，列出仍可生成的错误值/错误引用反例。
- [ ] **T03.4** 明确目前没有真实forecast版本轨、多模态主轨或记忆机制证据；发现真正bug需最小反例和新版本修复。

---

## 9. M02：同硬件、匹配随机化的重复协议

### 9.1 两个互斥备选，不默认全部执行

| profile | 条件 | 计算 | 新回答数 |
|---|---|---|---:|
| `paired_scope_v1`，推荐最小版 | 新base + irrelevant_scope level4 | 2 × 540 × 3 repeats | 3,240 |
| `paired_all_factors_v1`，完整确认版 | 新base + 三种level4 | 4 × 540 × 3 repeats | 6,480 |

默认仅准备第一种，不自动准备/启动所有备选。选择scope来自P5探索，必须披露；该矩阵只能确认scope问题，不能替代三因素完整确认。[R08]

旧P4/P5只作历史背景，不填入新矩阵，不把旧run当第0个repeat。

### 9.2 两种身份必须分开

唯一运行键：

```text
experiment, model_digest, condition, repeat, method, base_episode, checkpoint
```

匹配随机化键：

```text
master_seed, model_digest, repeat, method, base_episode, checkpoint
```

后者**不含condition**；否则改变压力条件会同步改变种子。不同repeat独立，不同方法可采用独立seed；本轮主要配对目标是同方法的base/stress。

拟实现伪代码：

```python
def sampling_seed(master_seed, model_digest, repeat_id, method, base_episode, checkpoint):
    key = canonical({
        "master_seed": master_seed,
        "model_digest": model_digest,
        "repeat": repeat_id,
        "method": method,
        "base_episode": base_episode,
        "checkpoint": checkpoint,
    })
    return int(sha256(key.encode("utf-8")).hexdigest()[:8], 16)
```

实际实现复用仓库canonical/hash工具，检查计划内seed碰撞；不要使用进程随机化的Python内置`hash()`。数据生成RNG和模型采样RNG独立。

**同seed不保证不同prompt消耗同样的随机序列，更不保证跨硬件逐token一致。** 它只消除“条件身份必然改变seed”这一已知设计问题。

### 9.3 共同环境与调度

- 保持P5权重/tokenizer、BF16、模型采样、context、总生成上限、结构grammar不变。
- 使用相同完整H100规格和相同镜像/软件；记录实际GPU UUID、驱动、MIG状态和runtime inventory。
- 在repeat间轮换条件/worker或以平衡block调度，避免某因素始终只由一张物理卡承担。
- 按checkpoint波次执行，但同轨迹必须顺序，且跨condition/repeat不得复用carrier。
- 固定batch size、顺序、组成规则和prefix-cache设置；失败后不能通过重新组batch选择性重生成。
- vLLM0.10.2文档建议V1使用`VLLM_ENABLE_V1_MULTIPROCESSING=0`以固定调度；是否采用应写进新执行版本并先验证，不能改称旧P5设置。[D02]
- 不升级Torch/vLLM/XGrammar来“顺便优化”；升级性能应是另一个实验因素。

### 9.4 全轨迹总影响与单checkpoint直接影响分开

主矩阵是自然演化的整条轨迹：前一回答变了，后一carrier也可变，因此估计的是包含传播的总影响。

可选共同前缀诊断：在一个预声明fork点之前生成一次真实prefix，保存真实carrier，然后对两个证据条件分叉；每个分支独立生成suffix。只测当前证据时，两边carrier必须完全相同。

该诊断需要自己的实验ID、调用预算与源码路径；共享prefix只计一次真实生成，不是额外“独立样本”，也不得用oracle state冒充模型prefix。不要默认在主矩阵之外多跑这些请求。

### 9.5 任务

- [ ] **T04.1** 实现新repeat/运行键/sampling键，旧single-repeat路径保持原样。
- [ ] **T04.2** 从同一基础映射构建新完整schedule，断言3,240或6,480机会数且无重复。
- [ ] **T04.3** 保持完整prompt+8192输出预留；超过共同context即停止准备该profile，不截断。
- [ ] **T04.4** 冻结worker/condition顺序和batch规则，输出hardware requirements而非假称已匹配。
- [ ] **T04.5** 用程序诊断验证跨repeat和condition隔离、wrong-but-valid传播、invalid保持上一合法状态。

---

## 10. M03：可恢复执行、独立审计与冻结停止点

### 10.1 复用现有机制，不重新发明所有采集代码

先检查P5 execution/runtime/audit和已有launch流程可复用部分。新包装只增加repeat维度、匹配随机化、统一资源范围和新artifact身份。不要将旧claim复制后改名字启动。

状态至少区分：

```text
planned
→ intent_durable
→ generation_started
→ raw_capture_durable
→ parsed_and_committed
→ scored_and_audited
```

本地GPU生成不等于远程API计费，但也有“生成已完成但记录未完成”的不确定区间。没有完整capture不能声称生成次数为0；默认不自动重生成。

### 10.2 异常处理

| 异常 | 必须保存 | 处理 |
|---|---|---|
| 合法完整回答、值错误 | 原文/原token/usage/错误state | 原样进入自己的下一轮 |
| 无效任务回答 | 原文、失败位置、上一合法carrier | 本机会失败，不做修复重试 |
| 完整capture落盘后进程中断 | capture及其hash | 离线完成解析/报告，不重新生成 |
| generation intent已写但没有完整返回 | 未确定状态 | 停止并等待独立恢复决定 |
| token或上下文边界违规 | 实际输入、停止原因 | 不靠截断补齐 |
| 资源限额/worker中断 | 已完成前缀、未提交机会 | 部分结果，不选择性补成功格 |

### 10.3 不修改历史格式门槛

历史P5每方法/任务族有60个回答的格式screen。新重复包建议保留**每repeat单独的同结构screen**，不能把三个repeat合成180后临时放宽规则。任何门槛修改都必须先声明为新协议。

新报告同时输出：JSON合法、structure合法、task contract合法、值正确、有据正确、完整checkpoint正确。诊断程序不能标为`model`来源。

### 10.4 任务与验收

- [ ] **T05.1** 新执行包绑定代码、数据、模型来源、tokenizer、grammar、采样键、schedule与授权状态。
- [ ] **T05.2** 独立审计从capture重建真实prompt/carrier/seed，不只核对collector自产hash。
- [ ] **T05.3** 篡改后重算表面hash的负例仍被协议重建发现。
- [ ] **T05.4** 测试重复启动、跨输出目录绕过、跨repeat串状态和不确定生成恢复。
- [ ] **T05.5** 保存CPU重算入口、实际验收日志与未运行GPU检查；生成`AWAITING_AUTHORIZATION.md`后停止。

**首轮停止点：M00–M03。** 历史“最多四张H100”和以前的自动GPU许可属于已完成工作范围，本文不把它们转化为新3,240/6,480调用授权。

---

## 11. M04：真实 NHC 预报版本资料可行性

### 11.1 核心任务

从“不同观测时间的数值变化”推进到：

> 对同一场风暴、同一个绝对预报有效时刻、同一变量，不同已发布预报版本给出什么值？截至当前交付计划，应该采用哪一版及哪一处证据？

这仍不是LLM自行预测天气，也不是比较预测误差；它评价是否正确维护官方预报版本。

### 11.2 本轮核对到的资料与限制

NHC Ian 2022 Forecast/Advisory25的官方文本可读，包含发行时刻2022-09-28 21:00 UTC、目标2022-09-30 06:00 UTC的中心30.0N/80.6W及最大风速55kt。[D06]

上一版计划提出Discussion22/25的配对候选。本轮部分Discussion原页和Forecast/Advisory22直读返回403，因此**不得把两版完整资料已经取得写入数据交付**。先尝试合规地取得完整官方源；无原文件就保持`candidate_unverified`。不要把搜索片段、第三方转贴或手写数字转换成正式source fixture。

Ian及其具体例子已经被开发者查看，应归为开发/单元验证候选，不可称全新盲测事件。

### 11.3 两条资料路线

**路线A（优先）：NHC Forecast/Advisory原文。** 明确`FORECAST VALID`和`MAX WIND`，字段范围小，保存完整产品并定位对应行。先实现这个parser。[D06]

**路线B（补充）：Discussion中的预测表。** 用`FORECAST POSITIONS AND MAX WINDS`解析表格行，作为另一表示/交叉核查，不能认为与同版本Forecast/Advisory是独立天气来源。

Tropycal提供`get_nhc_discussion`和operational forecast接口，可以减少资料导航与ATCF解析工作。但其forecast索引与discussion编号不相同，重建cone不等于官方原图，事后HURDAT与operational资料也不能互换。[D01]

ATCF只作可选交叉核查：不要把`init_time`当作`issued_at`，不要用BEST/CARQ替代OFCL预报，不要因风圈半径重复行把一个scalar重复计数；同键数值冲突应报告，而非取最后一行掩盖。

### 11.4 首批规模与网络边界

设计目标为3–5个新开发风暴的可行性清单，不是承诺已有完整数据。事件先按来源完整性和固定年份/样本规则选择，不能看模型错题后挑选。

建议有界获取配置：

```yaml
source_acquisition:
  enabled: false
  allowed_hosts: [www.nhc.noaa.gov, nhc.noaa.gov]
  max_requests: 100
  max_total_bytes: 25000000
  max_file_bytes: 2000000
  request_timeout_seconds: 30
  max_retries: 1
  minimum_interval_seconds: 1
  allow_third_party_fallback: false
  preserve_failed_attempts: true
```

这是**数据下载**限额，不是模型调用限额。禁止通过规避访问控制解决403；记录失败或等待用户提供合法快照。不能因下载失败把模型题目Gold变成unknown。

### 11.5 任务

- [ ] **T06.1** 新建候选source manifest，新增开发来源选择显式排除现有七个heldout；Ian等已查看例子可作为parser回归fixture，但不计作新盲测或新增独立开发发现。
- [ ] **T06.2** 有界获取原文、HTML/提取文本hash、URL、时间、状态码；支持离线已下载快照。
- [ ] **T06.3** 实现Forecast/Advisory主parser及局部源行定位。
- [ ] **T06.4** 实现Discussion表parser或Tropycal/ATCF可选交叉核验；冲突不自动修复。
- [ ] **T06.5** 输出coverage/rejection/ambiguity报告；没有达到明确资料标准时不生成正式模型任务。

---

## 12. 真实预报轨的数据契约和难点

### 12.1 `ForecastEntry`草案

```text
source_product_id
source_url
raw_sha256
extracted_text_sha256
product_family                  # fstadv / discussion，不直接混成一个序列
storm_id
advisory_number
edition_id                      # 如能证实存在corrected edition则单独记录
issued_at_utc
observation_time_utc             # 可选，不等于预报初始化时刻
forecast_initial_time_utc        # 仅有源依据时填写
forecast_valid_at_utc
printed_lead_label              # 保留源文本，不用来替代绝对有效时间
lead_from_issue_hours            # 计算字段，命名不能混同 printed lead
forecast_max_wind_kt
forecast_latitude_deg
forecast_longitude_deg
forecast_stage                  # 如INLAND/OVER WATER/POST-TROP，首版辅助元数据
source_spans                    # 逐字段行范围，风速可能在位置下一行
parse_status / exclusion_reason
provenance_kind
```

禁止把`maximum_wind_mph`字段偷偷改装成knots。新轨字段用`forecast_max_wind_kt`，保持原始单位；主评分不引入任意容差，若需单位转换必须另定义舍入和误差协议。

### 12.2 时间恢复

`30/0600Z`缺月份和年份，恢复时必须用产品完整日期、允许的预报时域和时间递增性确定唯一候选，覆盖月末/年末/闰日。存在多个合法候选时拒收或显式标为ambiguous。

**特别注意：**Discussion中的`12H`标签不保证等于发行时刻+12小时；不同产品可能使用不同初始化参考。以明确打印的有效日期/时刻为主，记录差异，不为了满足等式改日期。

独立测试必须包括：同一个`24H`在两份产品中对应不同日期；同一绝对有效时刻在两份产品中使用不同lead标签；发行/观测/初始化的区别。

### 12.3 版本选择语义：首版先冻结一种

推荐真实预报v1采用**最新交付的完整产品快照**语义：

1. 在同storm和product_family内选择当前已交付且符合issue边界的最新产品；没有任何已交付产品时返回unknown，原因记为`no_delivered_product`。
2. 查询其中的目标有效时刻。
3. 有完整数值项则返回三字段；没有目标项则为`not_provided_in_latest_product`。
4. 不从旧产品默默补回缺失目标；这与受控PATCH轨“遗漏意味着不改”不同。

为了减少首版争议，主要模型样本先使用所选连续产品中**真实共同存在的目标有效时刻交集**，并把完整产品遗漏处理留作软件负例/独立诊断。

这是一项项目设计决定，不声称NHC为所有下游应用规定了唯一查询语义。若后续研究“每个目标保留最后可用预测”，必须另立`latest_available_per_target`协议并单独报告。

### 12.4 消散、未来目标与资料缺失

- `DISSIPATED`不能自动转换为风速0或经纬度0；首版数值任务排除不完整数值行，保留排除记录。
- 当前checkpoint过去了目标有效时刻，不自动使“曾发布的该目标预测”无效；必须先界定是在问历史预测还是当前未来预测。
- 解析失败、源损坏、未下载与“合法输入下缺少证据”是不同状态，不能混用unknown。
- 没有保存纠正前的完整版本，就不能仅凭Corrected标记构造真实纠错pair。
- 首版不插值、不将不同预报时刻凑成同一目标、不使用最终best track支持早期模型答案。

---

## 13. M05：真实轨的自动Gold、双表示与独立验证

### 13.1 两种输入条件

```text
RAW_PRODUCT_TEXT：完整的已选预报产品或预声明范围的完整预报段
NORMALIZED_TABLE：同样证据内容的结构化逐行表
```

两者必须保留该产品中相同范围的所有预报目标、版本及干扰信息，不能把NORMALIZED_TABLE变成只含正确目标答案的Gold摘要。相同字段预算与共同证据截止规则，差异是表示而非“谁看到更多答案”。

训练/评估实例保留source产品级分组；raw/normalized两种视图不能落入不同split。

### 13.2 两个独立参考实现

**私有compiler：**使用准入后的typed entries按声明的完整快照语义选择产品与目标行。

**public oracle：**从模型实际可见原文/规范化文本重新解析、恢复时间、选择目标。不得调用私有parser的核心选择逻辑。可以共享schema、日期基础库和hash工具，但要列出共享依赖。

Tropycal/ATCF可作为第三种cross-check，但共享NHC来源不意味着统计上独立真值；不一致时生成诊断，而不是投票决定。

### 13.3 输出协议

拟采用三个字段及支持关系：

```json
{
  "state": {
    "forecast_max_wind_kt": {"status": "known", "value": 55, "evidence": []},
    "forecast_latitude_deg": {"status": "known", "value": 30.0, "evidence": []},
    "forecast_longitude_deg": {"status": "known", "value": -80.6, "evidence": []}
  }
}
```

这是说明字段的schema示例，不是可发给模型的filled example，也不是一个有据正确提交。正式prompt只给空schema；known空evidence仍应在grounding上失败。

真实轨首版**不继承合成风速100mph动作阈值**，不要求表中不存在的预测气压。真实风险或港口动作需要额外可验证来源，不能为了凑四字段与action编造。

### 13.4 证据支持

证据至少绑定`product_id + locator`，locator对应原文行或结构化row。对位置和风速分开构建支持span；Forecast/Advisory中位置行不能单独支持下一行的数值风速。

同一父产品被raw和normalized展示时，它们是两个表示、不是两份独立支持。允许等价合法位置的集合应在模型推理前冻结；不按模型引用事后扩充规则。

### 13.5 任务

- [ ] **T07.1** 新建`real_forecast_v1`独立schema/renderer，不修改历史四字段controlled协议。
- [ ] **T07.2** 构建真实重合有效时刻和连续版本pair，保存版本选择证据。
- [ ] **T07.3** 实现私有compiler与独立public oracle，逐checkpoint交叉一致性检查。
- [ ] **T07.4** 实现raw/normalized信息等价检查、支持span和分支Gold独立重算。
- [ ] **T07.5** 构建晚到旧版本、首次支持延迟、无关目标时刻及null更新对照；缺失分支须在首次曝光前隐藏全部支持。
- [ ] **T07.6** 输出data card、拒收清单、任务机会表和未发送请求样例；此阶段不调用模型。

验收不能只要求oracle满分。还要让`last-arrival`、`same-lead-label`、`wrong-target-time`、`gust-as-sustained`等错误程序在预声明反例失败。正确的简单程序仍应得到满分。

---

## 14. M06：受控任务的新分布，而不是盲目拉长上下文

### 14.1 参数化范围

旧P5保持冻结，新增`controlled_diversity_v2`。可复用旧操作语义，但新dataset ID与生成器版本必须明确。

| 维度 | 最小取值/变化 |
|---|---|
| 更新变量 | 风、压、纬、经分别覆盖 |
| 更新方向 | 增加、减少、同值刷新 |
| 数值关系 | 正确值与干扰值相同/不同；阈值附近/远离阈值 |
| 支持状态 | 同字段known与首次支持前unknown的匹配条件 |
| 作用域 | 同实体不同目标、不同实体同目标、无关变量 |
| 操作位置 | 改变首次支持、PATCH和重放在序列中的位置 |
| 表示 | ASSERT行序、长度受控的ID、日期等价格式 |
| 复杂度 | 有效候选键数、当前来源分散度、修订链深度 |
| 冗余长度 | 语义不变的重复/无关记录数，单独记录token量 |

不要同时引入分叉冲突、撤回、过期和迟到父节点。需要新增时先写语义，不得把非法graph当成应回答unknown的题目。

### 14.2 CheckList式测试矩阵

本项目按以下三类自定义测试，不必安装完整CheckList：[L07]

- 最小功能：只有两个版本、一个更新字段时是否选择正确事实。
- 不变性：重复旧版本或增加其他scope时，目标状态应保持。
- 定向变化：合法目标PATCH跨过研究阈值，目标字段与派生研究动作应改变，其他字段不变。

**重要区别：**软件oracle必须满足精确不变量；随机模型的配对答案不保证相同，模型层面测的是通过率，不将随机波动误报软件bug。

### 14.3 RULER式长度—复杂度解耦

采用“小而可控”的2×2设计草案：

```text
低复杂度 / 短文本
低复杂度 / 长文本
高复杂度 / 短文本
高复杂度 / 长文本
```

长度用真实tokenizer实际计算；复杂度由有效FactKey数量、来源分散度等定义，而不是仅按字数。字数相同不等于token相同。padding必须有明确无关语义、所有方法相同规则；不得为某个模型删支持以满足长度。

这属于新实验，不混入P5 level4结果。RULER仓库可提供生成器组织参考，但具体分支/路径导入前需要核对；不要照搬其旧运行环境。[L08]

### 14.4 状态机测试

Hypothesis `RuleBasedStateMachine`用于生成SET、合法PATCH、重放、合法其他scope与延迟支持序列，检查：

```text
replay idempotence
untouched-field preservation
per-key authority
no future support
public/private reference agreement
renaming consistency
```

保留手算微型fixtures，避免两个实现只在同一种随机样本上共同通过。失败反例缩小后保存为固定回归；生产dataset seed与测试seed独立。[D04]

### 14.5 任务

- [ ] **T08.1** 抽出参数配置并固定覆盖比例，不基于P5错题筛选主数据。
- [ ] **T08.2** 编译coverage matrix、值分布、操作位置和source-root依赖清单。
- [ ] **T08.3** 实现不变性/定向变化/标识符双射测试。
- [ ] **T08.4** 完成Hypothesis状态机与独立oracle交叉测试，保存shrunk反例。
- [ ] **T08.5** 检查所有方法的完整上下文预留；不合格profile整体重设计而非静默截断。

---

## 15. 指标规范：主分数不改，新增解释性层

### 15.1 保留的主指标

- 四字段controlled或三字段real的value/status correctness。
- known-grounded correctness。
- unknown correctness，单列机会数。
- 完整checkpoint correctness。
- 历史既有update/preservation/refresh指标按原语义输出。
- action仅在拥有明确研究规则的controlled轨，不能解释为真实应急质量。

**所有率保存整数分子与分母；无机会为null。** 无效/缺失/未生成机会保留在声明的全计划分母；遇到基础设施中断同时报告完成覆盖率和模型结果，不把系统中断伪装成模型推理失败原因。

### 15.2 新增引用层诊断

```text
value_to_grounding_gap
current_version_binding_accuracy
source_localization_accuracy
stale_version_error_rate
wrong_scope_reference_rate
```

每个名称必须绑定精确定义。`source_localization_accuracy`若以“值正确”作条件，是次要诊断，不能用于替代固定机会主排名。

### 15.3 整轨迹与重复可靠性

从STATE-Bench借鉴“平均一次成功”和“所有重复成功”分开报告，但明确我们的评价单位是episode，而不是其企业任务。[L06]

设`P[e,r]`为episode e在repeat r的全部计划checkpoint均正确：

```text
episode_pass_mean = sum(P[e,r]) / (N_episode * K)
episode_all_repeats_success = sum(all_r P[e,r]) / N_episode
```

第二项建议明确命名`episode_all_repeats_success_K3`，避免与“至少一次成功”的pass@K混淆。K次必须是真实独立repeat，不由单次正确率乘方估计。缺失repeat时完整计划主指标视为未成功，并另给incomplete状态；不要称已测得稳定可靠性。

### 15.4 分组与统计单位

controlled轨同时报告source、root、episode、checkpoint、field；变体与repeat不是独立风暴。当前仅三个source时以描述性逐source差异、repeat范围为主，不输出伪精确总体显著性结论。

真实轨同一风暴的多个advisory、目标时刻、raw/normalized视图必须聚类。等权风暴macro与micro分数并列；bootstrap若后续使用，采样单元至少是实际storm而非字段，且小storm数下明确不稳健。

### 15.5 禁止的指标混用

- 引用230处、值错90处与动作29处不能简单相加为349道错题。
- P5 controlled的update含citation变化，不与旧automated纯semantic update直接合并。
- c1–c4补充切片不替换完整主分母。
- base与delay正确答案可能不同；要比较各自正确，不奖励跨分支答案一致。
- 低token/低时延不是更科学正确；GPU货币成本未知时不得填写0。

---

## 16. M07：批准后的实验执行与报告

### 16.1 实验矩阵

| 实验 | 默认地位 | 计划量 |
|---|---|---:|
| P5历史诊断 | 立即，CPU/零推理 | 0新回答 |
| 配对重复最小版 | M03后另行授权 | 3,240 |
| 配对重复完整版 | 替代最小版，非自动追加 | 6,480 |
| 新真实轨smoke | 数据准入、parser、oracle冻结后授权 | 从实际N_episode×N_cp×N_method×N_view×N_model×N_repeat计算 |
| 第二模型旧P5任务 | 独立绑定任务/输出轨后授权 | 按选定完整条件计算；不能复用旧DeepSeek填格 |
| 来源复查方法 | 需要额外调用预算 | 全部预声明机会的额外调用，不只复查已知错题 |

### 16.2 先确保“新问题值得调用”，不要求预先看到错误

Go门槛：源证据足够、oracle互相验证、错误程序在指定机会可区分、所有模型输入完整可见性可审计、预算和资源绑定、数据分布不按模型成绩筛选。

No-Go门槛：关键数据无法取回/解析、版本选择语义未定义、某一方法必须截断、历史capture不足却想宣称完整比较、授权范围不明确。

模型满分或方法等效不是软件No-Go；应记录结果并决定研究重心，而不是选择性加难题。

### 16.3 任务

- [ ] **T09.1** 使用用户实际授权记录绑定exact execution与条件/repeat/资源上限；模板必须保持`approved=false`直到真实批准。
- [ ] **T09.2** generation-disabled环境检查与真实生成分开，不把加载模型当运行样本。
- [ ] **T09.3** 执行完整批准矩阵，保留失败、停止前缀和全部计数；不重开旧P5 claim。
- [ ] **T09.4** 独立CPU重建、曝光切片和双向pair统计；旧结果和新结果分表。
- [ ] **T09.5** 输出假设支持/不支持/不确定结论，不按预期排序改数据或prompt。

---

## 17. M08：第二模型与轻量方法，只针对已定位问题

### 17.1 第二模型

不在本文凭排行榜猜测最适合的型号。先由现有资源和用户选择确定不同家族，固定权重/服务身份、tokenizer、许可证、模板、context和输出能力。

同样8192token不代表相同字符数或算力；采用共同内容、各自token实测与明确预算。模型不支持相同grammar时，建立另一个output track，不把普通JSON mode伪装成structure-only等价。

前缀/后缀包含thinking token的模型，需要独立分隔和EOS测试。不要沿用Qwen特殊token解析而不验证。

### 17.2 推荐的最小方法消融

在R0错误归因完成后，最多先比较：

```text
A：原始一次回答
B：一次回答 + 普通再次核对（相同额外调用数/输出预算）
C：一次回答 + 明确要求核对实体/有效时刻/版本/引用的复查
```

三者共用数据与score。B/C不允许读私有Gold或确定性oracle输出；第二轮仍由模型决定最终状态。是否保留第一轮进下一checkpoint应在协议中固定，推荐本方法只提交其最终一次回答。

不要只在scorer发现错误的checkpoint触发C，这会给方法隐藏的Gold帮助。首版对所有预声明checkpoint执行，或使用完全公开、冻结的触发条件，并匹配B的触发/预算。

StateMemBench的长度/成本匹配对照是这一设计的文献动机，不代表C是其官方StateMem实现。[L02]

### 17.3 可选STALE式probe

将来若需要前提抵抗诊断，可增加机器可验证的结构化probe：

```text
question premise: 旧风速仍是90吗？
required output: premise_valid + current_value + current_citation
```

模板中的真假前提及支持由已交付记录确定；不要依赖自然语言judge。加入probe之前必须扩展公开协议、分母、预算和parser，不能塞入旧state/action输出。[L03]

有限证据窗口、own/no/stale carrier需要独立信息访问协议；不能仅看某个方法输入少而低分，就声称测得内部记忆质量。[L04–L05]

### 17.4 任务

- [ ] **T10.1** 完成第二模型adapter一致性测试与新model manifest。
- [ ] **T10.2** 固定输出track、共同数据、资源/调用边界，再做完整小矩阵。
- [ ] **T10.3** 只有在错误归因有明确目标后实现B/C等预算方法；保留无额外调用A。
- [ ] **T10.4** 分析准确率、当前引用、错误持续、token、时延和资源，不只报最大提升。

---

## 18. M09：冻结、heldout与可移植交付

### 18.1 冻结顺序

先冻结任务语义、样本分布、generator seed、renderer、source parser、split、模型/输出track、重复数、分母、support policy和失败处理，再打开heldout模型结果。

分别命名：

```text
new_values
new_operation_compositions
new_real_storms
new_source_formats
new_models
```

“新初始数值”不能描述为“新气象过程泛化”。同一风暴的原文、结构化表、图像及所有pair属于同一个split；同一原始产品哈希也应检查跨split泄漏。

### 18.2 Inspect导出只放最后

可选导出规则：一个完整episode一个sample；solver在内部顺序执行checkpoint，并只传声明carrier；custom scorer读取冻结离线结果。目标Gold不得进入solver prompt或通过`TaskState.target`指导中间行动。[D05]

默认不开Inspect的自动重试、模型判分、自动压缩或隐式对话历史。兼容性验收要求导出后固定机会和原生评分一致；此步骤不是为了替换已经可重算的自有harness。

### 18.3 多模态延展的停止线

若后续保留multimodal论文主张，优先把同一真实预报表渲染为图像，与原文/结构化视图比较。需真实执行视觉模型后才能称为多模态评测。

必须保证图像alt text、文件名、metadata不泄漏答案；不同视图信息等价；基于渲染表的定位指标不是新遥感变化检测贡献。不要因为已有图表就声称完成SAR/雷达理解。

本阶段只提出接口，不默认生成图像、训练CV模型或下载大规模影像。

### 18.4 任务

- [ ] **T11.1** 按storm/原始source/root验证split和重复依赖，保持原七heldout不参与调参。
- [ ] **T11.2** 生成完整data/model/protocol cards，保留失败、来源边界和已知不可识别性。
- [ ] **T11.3** 独立CPU环境重建报告，不用GPU权重、不访问模型网络。
- [ ] **T11.4** 需要时再做Inspect导出和offline CI模板，不声称hosted CI已运行。
- [ ] **T11.5** 推送、发布数据、改变仓库可见性均等待本轮明确授权；不得复用旧一次性发布范围。

---

## 19. 软件测试清单：针对失效机制，不以数量为目标

以下为最低测试场景。可参数化组合，但报告实际执行测试数，不将表行数伪称真实样本数。

| ID | 测试情形 | 期望 |
|---|---|---|
| A01 | 正确值+正确当前ASSERT | 与旧scorer一致，支持成功 |
| A02 | 正确值+旧同键版本 | citation-only、stale标签 |
| A03 | 同值旧版本 vs 新版 | 不能因数值相同放过旧来源 |
| A04 | 正确record错变量行 | 不误判为值错误；wrong_variable标签 |
| A05 | 记录header/越界行 | unresolvable_reference细分 |
| A06 | 已知值空evidence | missing_evidence |
| A07 | 正确引用混入错误引用 | 主判定仍失败，mixed flag |
| A08 | 其他实体恰有相同数值 | 不能算合法支持 |
| A09 | 同实体不同有效窗口 | wrong_window标签 |
| A10 | 同citation多次出现 | slot计一次；逐ref统计另列 |
| A11 | 与此前carrier一致 | 只标关联，不生成因果结论 |
| A12 | P5完整计数 | 90/230/320/260/29均能对账 |
| E01 | late_stale c0–c3 | 新额外重放曝光为0 |
| E02 | late_stale c4 | 记录额外交付，不误算新独特源 |
| E03 | irrelevant c0–c1 | 新作用域曝光为0 |
| E04 | chain修改supersedes | modified_existing_records被识别 |
| E05 | 六个零增量控制 | 不删除，单独no-op统计 |
| E06 | 同evidence不同carrier | 不标完整prompt相同 |
| E07 | 字节不同但声明映射等价 | 两个相等标记分别保存 |
| E08 | 任一分母为0 | rate为null |
| P01 | 同base槽/同repeat两condition | sampling seed相同，run key不同 |
| P02 | 不同repeat | seed/载体隔离 |
| P03 | 方法/episode混写 | 审计拒绝 |
| P04 | wrong-but-valid | 原样进入后续carrier |
| P05 | invalid | 当前失败、不替换先前有效状态 |
| P06 | 完整capture后崩溃 | 离线恢复，不再生成 |
| P07 | intent后无capture | 不自动重试，保留未知状态 |
| P08 | 换输出目录重复启动 | 全局execution claim拒绝 |
| P09 | 3,240/6,480矩阵 | 唯一槽、完整顺序、精确机会数 |
| P10 | 超context | 不截断，准备失败/运行按冻结策略停止 |
| P11 | 程序diagnostic伪装model | 审计拒绝 |
| P12 | 修改input并重hash | 协议重建发现偏离 |
| G01 | 错值但合法结构 | grammar仍允许；scorer判错 |
| G02 | 不存在的record_id | grammar允许字符串；scorer判错 |
| G03 | unknown+数值等不一致 | structure与task contract区分 |
| G04 | 换field顺序 | identity变化明确，不伪称旧配置 |
| F01 | 直接UTC发行头 | 明确恢复时刻 |
| F02 | 月末/年末预报有效时间 | 唯一候选才准入 |
| F03 | 闰日/非法日期 | 正确解析或明确拒绝 |
| F04 | printed12H不等于issue+12h | 不误改绝对有效时刻 |
| F05 | 同lead不同valid time | 不能配为同一目标 |
| F06 | 同valid time不同lead | 正确配对 |
| F07 | W/S坐标 | 保留符号 |
| F08 | MAX WIND与GUSTS相邻 | 只读取持续风速 |
| F09 | KT与MPH同时存在 | 不混单位、不做未声明舍入 |
| F10 | DISSIPATED无数值 | 不填0、不伪造known |
| F11 | 下载/解析失败 | 数据拒收，不变成unknown题 |
| F12 | 最新完整产品无目标 | 按公开快照语义，不静默补旧预测 |
| F13 | 正常新版预报 | 不标成官方错误更正 |
| F14 | Corrected但无旧快照 | 不生成真实纠错pair |
| F15 | ATCF相同scalar重复风圈行 | 不重复计数；冲突显式报告 |
| F16 | 跨产品族或不同编号体系 | 不凭编号直接合并 |
| F17 | 原文/normalized视图 | 候选事实集合和源父身份一致 |
| F18 | 隐藏支持但正文仍有副本 | 缺失构造审核失败 |
| F19 | 已曝光后隐藏源 | 不自动要求遗忘成unknown |
| F20 | 私有/公开两实现 | 微型手算fixtures与完整准入数据一致 |
| D01 | SET+局部PATCH | 未更新字段和来源保持 |
| D02 | 旧record重复 | 幂等，不恢复旧权威 |
| D03 | per-key-latest合法域 | 与完整oracle一致，不强行判错 |
| D04 | 标识符全局双射 | Gold同步映射，语义一致 |
| D05 | 字段/ASSERT换序 | 新表示可读且引用随正确行变化 |
| D06 | 跨split原始源hash重复 | 拒绝泄漏或显式解释同一开发组 |
| D07 | generator RNG与model RNG | 改模型seed不改数据 |
| D08 | stateful缩小反例 | 保存稳定fixture，不在线改变生产题 |

---

## 20. 配置模板：未授权状态必须可机器检查

```yaml
plan_version: post_p5_research_plan_v1
base:
  repository: sisuolv/disastertrace-benchmark
  branch_observed: next-phase-v1
  commit_observed: dd5ee358f9708e2eb2f2032db9eaac14fa237adc

scope:
  mode: offline_prepare
  allowed_milestones: [M00, M01, M02, M03]
  model_generation_allowed: false
  gpu_allowed: false
  weight_download_allowed: false
  source_network_allowed: false
  paid_api_allowed: false
  heldout_inference_allowed: false
  training_allowed: false
  publish_allowed: false
  git_push_allowed: false

history:
  preserve_p1_to_p5: true
  forbid_consumed_claim_reuse: true
  score_mutation_allowed: false
  use_frozen_source_for_historical_replay: true

analysis:
  version: p5_attribution_exposure_v1
  classifier: deterministic
  unknown_reason_allowed: true
  fixed_denominators: true
  zero_opportunity_value: null
  include_no_op_controls: true

paired_experiment:
  profile: paired_scope_v1
  conditions: [base, irrelevant_scope_level4]
  methods: [snapshot, structured_state, answer_history]
  repeats: 3
  expected_new_responses: 3240
  seed_policy: paired_base_slot_repeat_v1
  context_tokens: 16384
  max_generated_tokens: 8192
  temperature: 0.6
  top_p: 0.95
  top_k: 20
  automatic_retry: false
  approved: false
  approved_gpu_limit: 0
  approved_new_model_responses: 0

output:
  root: work/post-p5-offline-v1
  refuse_existing_output: true
  save_input_hashes: true
  save_raw_failures: true
```

真实runtime/model manifest应复用已绑定字段，不仅凭这个简化YAML声称环境相同。GPU上限、网络资料下载、真实模型额度各自独立，不因某项批准自动打开其他权限。

---

## 21. 建议CLI与验收命令

**本节`disastertrace.post_p5.cli`和`real_forecast.cli`是待实现接口，不是当前仓库已有命令。** 实现后必须先验证`--help`及退出码，再写入README。

```bash
# M00：记录只读基线
python -m disastertrace.post_p5.cli inspect \
  --project-root . \
  --output work/post-p5-offline-v1/baseline

# M01：从指定P5历史包生成新分析；禁止改旧report
python -m disastertrace.post_p5.cli analyze \
  --p5-bundle artifacts/p5_stress_level4_v1 \
  --output work/post-p5-offline-v1/analysis

# M02/M03：只准备完整schedule与程序诊断
python -m disastertrace.post_p5.cli prepare-paired \
  --config configs/post_p5/paired_scope_v1.yaml \
  --output work/post-p5-offline-v1/paired_execution_preparation

python -m disastertrace.post_p5.cli verify \
  --package work/post-p5-offline-v1

# M04：无联网标志时仅消费本地已有官方快照
python -m disastertrace.real_forecast.cli audit-sources \
  --source-root references/real_forecast_candidates \
  --output work/real-forecast-audit-v1
```

联网获取另设`fetch-sources --allow-source-network --manifest ...`，必须读取显式有界配置，不从无关网页自动扩大范围。

建议开发检查（安装环境与具体版本以仓库为准）：

```bash
python -m pytest tests -o addopts= -q
python -m ruff check src/disastertrace/post_p5 tests/test_post_p5_*.py
python -m ruff format --check src/disastertrace/post_p5 tests/test_post_p5_*.py
```

没有Ruff/可选依赖时记录blocked，不自动修改整个历史代码风格；只对新增范围修正。shell glob未匹配时不得误称测试通过。

---

## 22. 里程碑、依赖与停止门槛

| 里程碑 | 主要任务ID | 依赖 | 核心产物 | 验收/停止 |
|---|---|---|---|---|
| M00 | T00 | 当前repo/附件 | 基线、可访问性、历史保全 | 缺失范围明确；不回退工作区 |
| M01 | T01–T03 | M00 | 错误归因、曝光、主张账本 | 指定历史完整包能对账；overlay不改旧分数 |
| M02 | T04 | M01测量定义 | 新paired/repeat/seed计划 | 槽位唯一、配对规则清楚、context完整 |
| M03 | T05 | M02 | 独立审计、程序演练、未授权执行包 | **默认本轮到此停止** |
| M04 | T06 | M00；资料访问权限 | 官方源清单、parser、拒收报告 | 不用搜索片段造source；真实获取质量合格 |
| M05 | T07 | M04 | 真实同目标版本、双表示、自动Gold | public/private独立重建；错误程序可区分 |
| M06 | T08 | M01语义审计 | 参数化v2与变形测试 | 覆盖预注册、不追逐已知模型错题 |
| M07 | T09 | 对应数据与执行包+批准 | 新模型capture、完整报告 | 完整或明确停止，不挑失败重跑 |
| M08 | T10 | M01/M05及新增批准 | 第二模型/等预算方法 | 同数据同轨；方法不读Gold |
| M09 | T11 | 开发选择冻结 | heldout计划、data card、迁移包 | 新授权后执行/发布，历史可重算 |

**依赖不是强制全串行。** M04资料审计、M06配置设计可以与M02–M03并行；新模型调用必须等待对应协议冻结。M09不是默认完成全文后自动推送。

工程工作量仅作分配参考：M00–M01约2–3个开发工作日，M02–M03约2–4日，M04–M05约3–5日且受官方资料访问影响；不作为保证，也不作为跳过验证的截止命令。

---

## 23. 分支与依赖管理：降低后续维护成本

1. 新开发分支由用户现有工作流决定；不要自动force checkout/reset。若需建分支，只在工作区干净且用户范围允许时建立普通新分支。
2. 不批量复制P1–P5源码到新名字下再维护多套几乎相同逻辑。运行时以冻结包保持历史，新增层通过明确接口复用；重构公共核心需要独立回归与新identity。
3. CPU分析、资料获取、GPU推理使用独立环境。Tropycal/Inspect/STATE-Bench/LME-V2依赖不作为核心安装先决条件。
4. 外部代码只在许可证核验后导入，记录具体文件、commit、修改摘要和NOTICE；论文可访问不等于代码可复制。
5. 不保存密钥、带临时token的下载URL、访问凭据或账户cookie到source registry和Markdown。
6. 历史文件绝对路径不能通过手改旧manifest“修成新机器”；新包记录迁移路径映射，保留旧provenance。
7. 输出文件生成采用原子写与不可覆盖目录，计划/执行/诊断/模型结果使用明确不同origin。

建议`upstream_reuse_manifest.json`（未导入前各项为空，不编造commit）：

```json
{
  "manifest_version": "post_p5_upstream_v1",
  "review_date": "2026-09-08",
  "entries": [
    {
      "name": "Tropycal",
      "repository": "https://github.com/tropycal/tropycal",
      "observed_ref": "master",
      "pinned_commit": null,
      "license_verified_at_commit": false,
      "imported_paths": [],
      "reuse_mode": "optional_adapter_or_reference",
      "runtime_required": false
    },
    {
      "name": "StateMemBench",
      "paper": "https://arxiv.org/abs/2608.19652v1",
      "repository": null,
      "implementation_status": "not_verified_in_this_review",
      "imported_paths": [],
      "reuse_mode": "paper_informed_design",
      "runtime_required": false
    }
  ]
}
```

---

## 24. 可以直接复制给 Codex 的首轮任务

```text
请完整阅读 DisasterTrace_CODEX_POST_P5_RESEARCH_PLAN.md，并在当前
sisuolv/disastertrace-benchmark 项目上增量执行，不要只再写一份计划。

本计划依据 next-phase-v1 的 dd5ee358f9708e2eb2f2032db9eaac14fa237adc。
先检查当前HEAD、未提交修改、根及子目录AGENTS.md、最新IMPLEMENTATION_STATUS、
DECISIONS、BLOCKERS和REVIEW_FOR_CHATGPT_PRO_P5.md。
如果已有更晚实现，先核对，不回退、不重复开发、不覆盖用户改动。

本轮默认只完成M00–M03：
1. 核对历史P5可访问产物和冻结源码，建立新只读分析输出目录。
2. 对已有P5回答实现逐citation确定性归因，分开90处值/状态错误与230处引用类错误；
   对账320字段错误、260失败checkpoint、29重叠动作错误；缺capture时明确partial。
3. 实现按实际公开证据而非factor名称定义的曝光、共同前缀和六个零增量控制分析。
   新指标为overlay，不修改旧Gold、scorer、回答或主分母。
4. 明确per-key-latest-issued在当前合法域中可以正确解题，不能把合法简单解法当bug。
5. 新增运行身份与sampling身份分离的repeat协议；准备base+irrelevant_scope的
   3240请求候选矩阵，三个repeat；仅用程序诊断，不真实生成。
6. 验证跨condition/repeat/method载体隔离、完整context预留、崩溃前缀、防重复启动、
   独立prompt/seed重建和CPU评分；不将相同seed写成确定性保证。

优先复用现有controlled/local_eval/constrained_eval/stress_eval模块。
不重建collector、U1-U3和XGrammar；不升级历史GPU环境。
外部论文/代码只按来源表作最小复用，StateMem实现未核实，不编造仓库路径。
不用LLM Judge、不新增逐题人工标注、不用Gold纠正模型carrier。

不调用付费API、不启动GPU生成、不下载权重、不训练、不访问heldout模型结果、
不重开P1-P5 consumed claim、不推送、不发布数据。
官方资料下载也默认关闭；可在等待时编写M04/M05的离线fixtures和接口，
但不要声称已取得此前403的完整NHC版本。

每个里程碑记录实际命令、退出码、实际测试结果和失败日志。交付：
repo_baseline、引用归因、计数对账、曝光表、CLAIM_AUDIT、paired执行准备包、
独立验收与HANDOFF_POST_P5.md。
缺失产物写明确阻塞并继续不依赖它的任务；未运行测试不得写passed。
M03完成后停止，提供真实实验和资料联网所需的精确待授权范围。
```

---

## 25. 来源登记与复用边界

下面URL是人工/工具核对用的资料入口，不是可跳过上游commit固定的依赖锁文件。网页/README在未来可能变化；Codex导入前应固定实际版本，不能编造SHA。除明确列出的P5绑定外，本轮未运行这些外部项目。

### 25.1 本项目、历史计划与用户综述

**[R01] P5当前审阅入口（已读，2026-09-08）。**
- [REVIEW_FOR_CHATGPT_PRO_P5.md](https://github.com/sisuolv/disastertrace-benchmark/blob/dd5ee358f9708e2eb2f2032db9eaac14fa237adc/disastertrace-starter/REVIEW_FOR_CHATGPT_PRO_P5.md)
- [AGENTS.md](https://github.com/sisuolv/disastertrace-benchmark/blob/dd5ee358f9708e2eb2f2032db9eaac14fa237adc/disastertrace-starter/AGENTS.md)
- 证据等级：仓库记录；不是本次新的GPU验证。

**[R02] 已保存P5实测说明。**
- [MODEL_FINDINGS.md](https://github.com/sisuolv/disastertrace-benchmark/blob/dd5ee358f9708e2eb2f2032db9eaac14fa237adc/disastertrace-starter/artifacts/p5_stress_level4_v1/MODEL_FINDINGS.md)
- 作用：历史错误数、硬件与采样差异、实际执行边界。

**[R03] P5逐方法/因素结果表。**
- [RESULT_TABLES.md](https://github.com/sisuolv/disastertrace-benchmark/blob/dd5ee358f9708e2eb2f2032db9eaac14fa237adc/disastertrace-starter/artifacts/p5_stress_level4_v1/analysis/RESULT_TABLES.md)
- 作用：第1节数值汇总；文件级重算仍由M00执行。

**[R04] 已有源码目录。**
- [controlled](https://github.com/sisuolv/disastertrace-benchmark/tree/dd5ee358f9708e2eb2f2032db9eaac14fa237adc/disastertrace-starter/src/disastertrace/controlled)
- [local_eval](https://github.com/sisuolv/disastertrace-benchmark/tree/dd5ee358f9708e2eb2f2032db9eaac14fa237adc/disastertrace-starter/src/disastertrace/local_eval)
- [constrained_eval](https://github.com/sisuolv/disastertrace-benchmark/tree/dd5ee358f9708e2eb2f2032db9eaac14fa237adc/disastertrace-starter/src/disastertrace/constrained_eval)
- [stress_eval](https://github.com/sisuolv/disastertrace-benchmark/tree/dd5ee358f9708e2eb2f2032db9eaac14fa237adc/disastertrace-starter/src/disastertrace/stress_eval)
- 作用：增量复用；历史运行以execution绑定源码为准。

**[R05] 版本语义与公开oracle。**
- [schema.py](https://github.com/sisuolv/disastertrace-benchmark/blob/dd5ee358f9708e2eb2f2032db9eaac14fa237adc/disastertrace-starter/src/disastertrace/controlled/schema.py)
- [public_oracle.py](https://github.com/sisuolv/disastertrace-benchmark/blob/dd5ee358f9708e2eb2f2032db9eaac14fa237adc/disastertrace-starter/src/disastertrace/controlled/public_oracle.py)
- [stress data诊断](https://github.com/sisuolv/disastertrace-benchmark/blob/dd5ee358f9708e2eb2f2032db9eaac14fa237adc/disastertrace-starter/src/disastertrace/stress_eval/data.py)
- 作用：per-key-latest-issued合法域与oracle边界。

**[R06] 压力变换。**
- [difficulty.py](https://github.com/sisuolv/disastertrace-benchmark/blob/dd5ee358f9708e2eb2f2032db9eaac14fa237adc/disastertrace-starter/src/disastertrace/local_eval/difficulty.py)

**[R07] 原评分与采样。**
- [scorer.py](https://github.com/sisuolv/disastertrace-benchmark/blob/dd5ee358f9708e2eb2f2032db9eaac14fa237adc/disastertrace-starter/src/disastertrace/controlled/scorer.py)
- [adapter.py](https://github.com/sisuolv/disastertrace-benchmark/blob/dd5ee358f9708e2eb2f2032db9eaac14fa237adc/disastertrace-starter/src/disastertrace/local_eval/adapter.py)
- 作用：机会定义、同值来源更新、条件ID/seed关系。

**[R08] 已有下一阶段计划。**
- [NEXT_PHASE_PLAN_ACP.md](https://github.com/sisuolv/disastertrace-benchmark/blob/dd5ee358f9708e2eb2f2032db9eaac14fa237adc/disastertrace-starter/artifacts/p5_stress_level4_v1/NEXT_PHASE_PLAN_ACP.md)
- 当前会话文件`DisasterTrace_P5_REVIEW_AND_NEXT_PLAN.md`（上一版R0–R5），作为执行连续性来源。
- 本文保留其主线，新增文献复用、来源错误细则、真实轨语义、测试/接口和分阶段停止点。

**[U01] 用户提供的《极端事件Benchmark 2026年9月3日》综述PDF。**
- 第1页区分Physical Prediction、Multimodal Understanding、Operational Agent和Scientific Agent。
- 第43页讨论可执行Ground Truth与可见任务/隐藏目标的一致性。
- 用途：保留研究问题层级与可验证性原则；其对各论文的全部数值/first主张未在本轮逐项重新验证，不能作为本轮已核实上游实现的替代。

### 25.2 论文与开放benchmark

**[L01] ALCE — Enabling Large Language Models to Generate Text with Citations，EMNLP2023。**
- [论文](https://aclanthology.org/2023.emnlp-main.398/)
- [官方仓库](https://github.com/princeton-nlp/ALCE)
- [eval.py](https://github.com/princeton-nlp/ALCE/blob/main/eval.py)
- 已核对：README及citation评分代码片段；评分包含模型NLI，不导入本项目主评分。只借鉴指标分层。

**[L02] StateMemBench / StateMem — Can Agent Memory Systems Track Evolving State?，2026-08-20。**
- [论文v1](https://arxiv.org/abs/2608.19652v1)
- [HTML](https://arxiv.org/html/2608.19652v1)
- 已核对：论文；本轮未核实官方代码位置。借鉴current/stale区分和长度/成本匹配实验，不宣称复现。

**[L03] STALE — Can LLM Agents Know When Their Memories Are No Longer Valid?，2026-05-07。**
- [论文v1](https://arxiv.org/abs/2605.06527v1)
- [官方仓库](https://github.com/icedreamc/STALE)
- 已核对：论文与README，`STALE/`和`cup_mem/`组件；借鉴三类probe，不采用其模型判分路径。

**[L04] LongMemEval — Benchmarking Chat Assistants on Long-Term Interactive Memory，ICLR2025。**
- [论文](https://arxiv.org/abs/2410.10813)
- [官方仓库](https://github.com/xiaowu0162/LongMemEval)
- 已核对：README、`src/evaluation`/`src/retrieval`/`src/generation`组织说明；其judge不进入我们的CPU确定性评分。

**[L05] LongMemEval-V2: Evaluating Long-Term Agent Memory Toward Experienced Colleagues，2026-05-12。**
- [论文v1](https://arxiv.org/abs/2605.12493v1)
- [官方仓库](https://github.com/xiaowu0162/LongMemEval-V2)
- 已核对：论文与README，2026-08更新说明、`memory_modules/`、`evaluation/`、`leaderboard/`布局。论文标记Work in Progress；其人工策划问题和默认LLM judge不复制为无人工协议。

**[L06] Microsoft STATE-Bench，开放enterprise workflow benchmark。**
- [官方仓库](https://github.com/microsoft/STATE-Bench)
- [官方介绍](https://opensource.microsoft.com/blog/2026/05/19/introducing-state-bench-a-benchmark-for-ai-agent-memory/)
- 已核对：README，MIT声明，pass@1/pass^5、task-local sandbox以及UX judge的区分。只借鉴状态隔离与重复可靠性，不运行企业工作流。
- 注意：STATE-Bench与StateMemBench不是同一个项目，不能混称或混引。

**[L07] CheckList — Beyond Accuracy: Behavioral Testing of NLP Models with CheckList，ACL2020。**
- [论文](https://aclanthology.org/2020.acl-main.442/)
- [项目仓库入口](https://github.com/marcotcr/checklist)
- 已核对：论文页面；本轮没有安装完整库。采取behavioral test matrix原则，执行由项目自身测试完成。

**[L08] RULER: What’s the Real Context Size of Your Long-Context Language Models?，2024。**
- [论文](https://arxiv.org/abs/2404.06654)
- [官方仓库](https://github.com/NVIDIA/RULER)
- 已核对：README中的可配置长度/复杂度设计；不采用其排行榜比较或旧环境安装。实际导入前核对主分支/迁移分支与路径。

**[L09] ExtremeWeatherBench，官方代码与事件注册。**
- [仓库](https://github.com/brightbandtech/ExtremeWeatherBench)
- [事件注册入口](https://github.com/brightbandtech/ExtremeWeatherBench/blob/main/src/extremeweatherbench/data/events.yaml)
- [文档](https://extremeweatherbench.readthedocs.io/)
- 已核对：README、事件路径与评价接口；该README仍写论文in preparation，与用户已有PDF的来源状态分别记录，不擅自统一。借事件组织，不把物理forecast metrics冒充LLM证据评分。

**[L10] Calibrating Criterion Revision in LLM Agents: Failure Modes and a Trace-Anchored Protocol，2026。**
- [论文](https://arxiv.org/abs/2608.20729)
- 已核对：论文入口与HTML；仅作model-owned commit、隐式harness帮助与matched intervention的相关研究。未核实代码位置，不增加实现依赖。

### 25.3 官方资料与工程实现

**[D01] Tropycal。**
- [官方仓库](https://github.com/tropycal/tropycal)
- [文档](https://tropycal.github.io/tropycal/)
- [operational forecast接口](https://tropycal.github.io/tropycal/api/generated/tropycal.realtime.RealtimeStorm.get_operational_forecasts.html)
- 已核对：README的`get_nhc_discussion`与forecast编号/重建cone/事后资料警告。未运行下载和解析；许可证需绑定实际导入commit复核。

**[D02] vLLM0.10.2 reproducibility。**
- [固定版本官方文档](https://docs.vllm.ai/en/v0.10.2/usage/reproducibility.html)
- 已核对：默认不保证reproducibility、V1 multiprocessing设置及同硬件同版本限制。本文不保证仅凭seed即可逐token复现。

**[D03] XGrammar。**
- [论文](https://arxiv.org/abs/2411.15100)
- [官方仓库](https://github.com/mlc-ai/xgrammar)
- [文档](https://xgrammar.mlc.ai/docs/)
- 作用：解释structure约束，不推断语义正确。项目当前真正运行的grammar以P5冻结`constrained_eval`和版本0.1.23为准；未在本轮重放432,742token。

**[D04] Hypothesis stateful testing。**
- [官方文档](https://hypothesis.readthedocs.io/en/latest/stateful.html)
- 已核对：RuleBasedStateMachine、invariants与反例收缩；导入前核对Python兼容版本，不改变固定GPU环境。

**[D05] Inspect AI。**
- [Solvers](https://inspect.aisi.org.uk/solvers.html)
- [Scorers](https://inspect.aisi.org.uk/scorers.html)
- [官方仓库](https://github.com/UKGovernmentBEIS/inspect_ai)
- 已核对：自定义solver/scorer、TaskState字段与评分路径；本轮只建议最后做可选适配，不能开启中间target评分指导模型。

**[D06] NHC官方预报档案。**
- [Ian Forecast/Advisory25，可读官方文本](https://www.nhc.noaa.gov/archive/2022/al09/al092022.fstadv.025.shtml?text=)
- [Ian Forecast/Advisory22，候选、直读受限](https://www.nhc.noaa.gov/archive/2022/al09/al092022.fstadv.022.shtml?text=)
- [Ian Discussion22，候选、直读受限](https://www.nhc.noaa.gov/archive/2022/al09/al092022.discus.022.shtml)
- [Ian Discussion25，候选、直读受限](https://www.nhc.noaa.gov/archive/2022/al09/al092022.discus.025.shtml)
- 已核对：25号产品中的发行头、FORECAST VALID与MAX WIND。其余需完整官方原文件；不能以本文件中的候选链接/数值代替正式数据包。

---

## 26. 最后一次执行边界检查

在任何新模型/GPU实验前，逐项确认：

```text
[ ] 我运行的是新execution，不是consumed P5任务。
[ ] 我没有改写历史Gold、scorer、capture或manifest。
[ ] 数据源和生成成分明确分开；真实资料没有被虚构PATCH替代。
[ ] 私有Gold/当前正确引用集合不在prompt或grammar中。
[ ] 三方法的信息条件与输出track被准确披露。
[ ] 运行ID与配对sampling ID不同；repeat之间carrier隔离。
[ ] seed相同不被误写成确定性/因果证明。
[ ] 实际压力曝光而非factor名称用于解释切片。
[ ] 所有失败/未生成机会与基础设施停止都得到记录。
[ ] 预算、资源并发和后续恢复范围是本轮明确授权。
[ ] 没有通过删题、截断、挑seed、单独修复失败格维持预期结论。
[ ] 所有“passed / completed / reproduced”均有本轮真实执行证据。
```

**最小成功交付不是更大的平台，而是：一份能解释P5错误的报告、一套可解释的新重复协议，以及一条真正能从官方预报版本自动重建答案的数据路径。**
