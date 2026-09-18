# DisasterTrace：可交给 Codex 执行的实施计划

> 文档版本：v1.0 · 2026-09-05  
> 文档类型：工程执行规格，不是已经完成的代码或实验报告。  
> 主线：Release-time Replay → Model-owned Commit → Revision / Propagation Evaluation。  
> 首个真实候选：Ian 2022 × Tampa / Key West；是否纳入正式评测，由来源与时间审计决定。  
> 默认执行模式：CPU、离线测试、Mock Backend；真实模型调用必须单独授权并设置预算。

---

## 0. 交给 Codex 的任务指令

你是一名负责实现研究型 Benchmark 的工程师。请在当前工作目录实现 **DisasterTrace**，按本计划逐阶段写代码、测试、运行与交付，而不是再次输出一份宏观研究建议。

本计划是自包含的：不要求你能访问此前 ChatGPT 对话、Notion、用户邮箱、个人记忆或任何私有材料。研究背景来自前述讨论以及用户提供的《极端事件Benchmark 2026年9月3日(2).pdf》；公开资源见第 25 节。

### 0.1 执行规则

1. 先检查当前仓库、已有 `AGENTS.md`、项目配置、未提交修改和可用解释器；已有项目优先增量实现，禁止默认重建目录或覆盖代码。
2. 保持本文中的研究问题、状态提交和证据时间约束。此前回答的代码属于草图，**不能不经测试直接拼接**。第 2 节明确列出了工程澄清。
3. 按第 20 节 `M00–M11` 执行。先完成无需 API 的闭环，再接真实数据和模型。不为每个常规编程步骤重复请求许可。
4. 不把写出函数、通过 Mock、通过真实数据解析、完成模型实验、通过人工审核混为同一状态。分别记录。
5. 网络不可用时继续实现离线 Fixture、Parser、Replay、Commit Store、Evaluator；真实数据任务记为 `BLOCKED_EXTERNAL`，不得伪造下载成功。
6. 没有模型凭证或费用授权时使用 Mock，不得声称已经完成真实模型对比；已有凭证也不意味着获准跑完整实验矩阵。
7. 不修改已有 SSH、CCI、HOME、CODEX_HOME、代理、系统 Python、CUDA、驱动或其他项目配置。不得从历史聊天中复制任何密钥。
8. 不自动安装第三方 Agent 插件、执行上游安装脚本、发布数据、推送 GitHub、修改 Notion 或进行真实灾害响应操作。
9. 每完成一个里程碑，更新 `docs/IMPLEMENTATION_STATUS.md`，保存测试命令、退出码、输出摘要、实际产物与剩余阻塞。
10. 出现协议矛盾时，写入 `docs/DECISIONS.md`；优先遵循第 2 节和第 3 节，不静默改成更容易的任务。

### 0.2 开始时依次执行

```text
检查仓库和工作区
→ 阅读本计划第 0–7 节与第 20 节
→ 建立状态表和决策记录
→ 实现最小 Schema 与合成 Fixture
→ 跑通离线 Replay / Commit / Evaluation
→ 审计公开数据并构建真实候选事件
→ 通过验证后再进行有预算的模型实验
```

**所有 `dt ...` 命令都是本项目需要实现的目标 CLI，不是假设已经安装的现成工具。** 实现对应命令后才能运行验收。示例中的 Synthetic 数据只用于软件测试，不能计入真实 Benchmark 规模。

### 0.3 自动继续与必须暂停的边界

| 情况 | Codex 应如何处理 |
|---|---|
| 普通缺少函数、类型不一致、单元测试失败 | 自行修复并继续 |
| 公共数据下载失败 | 记录失败，继续不依赖网络的任务 |
| 上游目录与本文不同 | 读取真实文件树，建立显式适配与审计记录 |
| 真实来源发布时间、时区或港口范围不清 | 隔离记录，不猜测；生成人工审核清单 |
| 需要大规模下载、付费 API 或新模型权重 | 先列计划规模与预算，等待授权 |
| 需要判定真实业务行动是否合理 | 保留为待人工审核，不能让 Codex 冒充专家签字 |
| 真实强基线表现很好 | 忠实报告；不能改 Gold 或挑选失败样本制造困难 |

---

## 1. 研究目标与范围冻结

### 1.1 要实现什么

在已有气旋—港口材料上构建一层独立的评测协议：

```text
同一事件的多模态证据逐步到达
→ 同一模型维护自己的状态
→ 新证据可能要求保留、更新、新增或撤回断言
→ 检查变化是否影响正确的下游判断
→ 对证据到达时间或完整性做受控干预
→ 记录整条事件轨迹是否可靠
```

核心评价对象是**可审计的模型外部状态及其使用行为**。不声称仅凭 JSON 提交和 Probe 就证明模型的内部信念或参数发生了改变。

### 1.2 三条任务线

| 任务线 | 必须实现的能力 | 首版定位 |
|---|---|---|
| A. Natural Release-time Replay | 按可见时间释放证据，连续保存模型提交 | 主任务 |
| B. Evidence-arrival Interventions | 同一前缀状态下延迟、隐藏、旧版本继续可见、无关更新 | 主压力测试 |
| C. Commit-use Probes | 测试 Own / No / Oracle / Stale State 对后续回答的影响 | 状态使用诊断 |

保留 Model-conditioned Revision：修订义务由**该模型实际上一版状态**和当前分支的可断言参考状态共同决定，不是所有模型共享固定操作标签。

### 1.3 MVP 范围

| 项目 | 首轮目标 | 说明 |
|---|---|---|
| 真实候选 | 1 个 storm，最多 2 个 port episodes | 同一 storm 的两港不是两个独立灾害样本 |
| Checkpoints | 每 episode 3–4 个 | 不强行补造恢复阶段 |
| 状态 | 6 个事实字段 + 1 个行动对象 | 见第 7 节；可缺证但不可虚构 |
| 模态 | 官方文字 + 至少一类真实地图图像 | 纯文本先做工程调试，不能冒充多模态结果 |
| Baselines | Snapshot、Raw History、Structured State、RevisionGuard | 先完成前 3 个，再加 Guard |
| 干预 | Delay、Withhold、Stale-copy、Null | 先完成 Delay 与 Null |
| 模型 | Mock 必须；真实模型先 1 个，再扩到 2 个 | 不硬编码“最新模型” |
| 工具 | Manifest、按 ID 读取证据；GIS 仅可选 | 不引入任意 Shell / Python Agent |
| 训练 | 无 | 不训练 VLM、LLM 或 Verifier |

### 1.4 明确不做

首版不建设通用灾害知识图谱，不合并所有 Benchmark，不部署大型 MCP 工具库，不做原始雷达/SAR 流处理，不训练变化检测模型，不做 Memory RL/Agent RL，不估计“最优关闭港口时间”或真实经济收益。

Near-miss、多灾种、精细视觉区域监督和大型工具任务都属于扩展；它们不能阻塞首个可测的闭环。

---

## 2. 相对于此前示例代码的工程澄清

本节是**实施时明确补充的设计决定**，不是声称原论文已经给出这些结论。研究主线不变，但下列草图问题必须在编码前消除。

| 编号 | 此前草图中的风险或未定义点 | 本执行规格 |
|---|---|---|
| C01 | 把 `ConditionEffectiveTime` 当成发布时间 | `effective_at` 与 `issued_at` 分离；未知发布时间不能伪造精确 Release-time |
| C02 | 直接按 `12h/24h` 文件名定时间 | 文件名仅作检索；正文产品头、官方归档和审计决定时间 |
| C03 | 简单按产品类型连所有 `supersedes` | 使用明确的产品流、版本、范围、有效窗口与替代语义；部分公告不能覆盖所有港口 |
| C04 | corrected advisory 与新一次 forecast 混为一谈 | 区分 `REVISION`、`CORRECTION`、`DUPLICATE`、`CANCELLATION`；只改标题不算业务风险反转 |
| C05 | 用 cone 判断全部灾害风险 | Cone 只作为轨迹几何关系；不得将 cone 外等同无风雨、无风暴潮或无风险 [S05] |
| C06 | 所有 warning 放进单一等级链 | Wind watch、wind warning 分开；storm surge 另有字段，不能取任意“最高等级” |
| C07 | `UNKNOWN` 同时表示缺证和 Gold 缺失 | 模型应保持未知与评测方无法判断分开；后者为 `NOT_SCOREABLE` |
| C08 | Snapshot 只看增量，Ledger 看全部 active evidence | 主比较使用相同证据包；Delta-only 是单独的受限记忆 Track |
| C09 | 环境自动给“正确 active facts” | 环境只处理公开版本元数据，不给隐藏字段值；所有辅助能力单独标记 |
| C10 | 固定 `newly_released_ids` 不随 Delay 改变 | 先算分支可见时间，再算当前可见集与增量 |
| C11 | Withhold 可以擦掉模型先前已看过的材料 | 普通 Withhold 必须发生在首次暴露前；不能让已知证据凭空从历史中消失 |
| C12 | 干预共用自然轨迹 Gold | 每个分支按自己的可见证据重新编译可断言 Gold 与下游义务 |
| C13 | Guard 在线读取 `must_update` Gold 后纠错 | Runtime Guard 只读取公开证据、Schema 和公开规则；隐藏评测义务绝不能反馈模型 |
| C14 | `reset()` 删除已有状态日志 | 新 run / namespace，不删除历史；Resume 必须校验哈希和配置 |
| C15 | 任意未可见 ID 都叫 future leakage | 区分虚构 ID、已知但未释放 ID、当前未送入上下文 ID；分类报告 |
| C16 | Model-conditioned F1 可以直接比较模型 | 同时报当前状态分数、支持数、同难度分层和 Oracle-prev；禁止鼓励先犯错再赚修复分 |
| C17 | 写了 `rechecked_slots` 就算真正重新检查 | 自报 recheck 只是过程诊断；主分数看正确终态、有效支持和可执行派生结果 |
| C18 | 用单点后验结果否定此前概率预测 | 区分预测概率、读取官方概率、模型答题信心；三者使用不同指标 |
| C19 | `WRITE/NO_WRITE/ESCALATE` 含混地控制保存 | `write_mode` 与 `review_request` 正交，见第 11 节；不通过升级请求偷偷更新状态 |
| C20 | 复制多端接口代码，假设所有模型支持相同参数 | Backend Capability Profile；不支持的参数不可静默删除后继续正式实验 |
| C21 | 低分或排名反转作为必要成功条件 | 工程成功与研究假设分开；负结果也是合法实验结果 |

NHC 对 cone 的官方定义明确描述的是气旋**中心轨迹**，不能把它当作风暴大小或完整影响范围。该边界属于本次核查补充的科学约束 [S05]，应落实成负面测试。

---

## 3. 不可违反的评测约束

### 3.1 时间与证据

- 原始 Artifact 不覆盖；文件 bytes、来源 URL、SHA256 与归档获取时间均保留。
- 所有运行用时间必须带时区，规范化到 UTC。禁止用机器本地时区填补未知来源时区。
- 发布时间不明的记录不得进入 Strict Release-time 主测试；可保留在有标识的 Bootstrap 子集。
- 未来文件、未来文件名、最终气旋名、未来更正关系、事后 outcome 和完整隐藏目录清单均不能通过 metadata 泄漏。
- 模型只能通过公开 Manifest 和受限读取接口访问该分支当时允许的证据。
- 每次模型请求都保存实际发送的证据清单和内容哈希，不能只保存“理论上可访问”的清单。

### 3.2 状态与评分

- 环境只保存模型明确提交的合法结构，不为模型推断语义、补齐事实或写入 Gold。
- 格式/协议错误的尝试留档；按照固定规则保留上一版状态，不能伪装成成功 KEEP。
- 语义错误但格式有效的提交也必须真实保存，后续轮次继承它。
- Evaluator 是独立的离线评分程序；评分结果、Gold 和隐藏 Probe 不回流主轨迹。
- 删除、撤回、未知、无警报、无影响必须有不同表示。
- 不使用 LLM Judge 决定核心结构化分数。开放行动解释可另设人工/辅助评分，但不混入主指标。

### 3.3 实验与报告

- 同一 storm 的所有 ports、checkpoints、twins、图文重复文件必须在同一数据划分。
- Bootstrap 与置信区间以 storm 为聚类单位；不要把 slot 或 twin 当成独立自然事件。
- 版本、Prompt、解码、预算、重试、上下文裁剪必须冻结并可复算。
- Mock、程序 Oracle、真实模型运行和人工审核的产物标签不能互换。
- 决定样本去留的原则在正式模型结果之前冻结；不按“模型是否失败”筛正式测试集。
- 论文中的动作仅是历史情景下的研究输出，不能自动触发外部指令、邮件或控制系统。

---

## 4. 开源复用与版本审计

### 4.1 采用独立 Adapter，不 Fork 成一个大平台

CyPortQA 的公开仓库提供图文材料、场景/模板以及模型 Runner；CyPort 提供港口与气旋交互材料；EarthVerse 提供独立运行、验证与报告代码 [S01–S03]。本项目复用这些资源的**局部能力**，不继承它们的完整任务协议。

| 来源 | 优先检查的文件/目录 | 复用方式 | 不复制什么 |
|---|---|---|---|
| CyPortQA [S01] | `source_data/`、`dataset/MultiModalInput/`、`models/run_gpt4o.py`、`models/run_qwen2_5vl.py` | 数据索引、模态映射、文件加载、请求编码参考 | 原逐题循环、随机打乱、硬编码模型、无版本 `latest` |
| CyPortQA [S01] | `source_data/Encoded_senario.json`、`source_data/CyPortQA_template.json` | Bootstrap schema discovery、slot 候选与 Gold 草稿 | 把所有旧 answer 当成独立核验的真值 |
| CyPortQA [S01] | `source_data/Port_Condition_Bullitens/` | 公告候选和已有聚合 CSV | 未验证的发布时间、港口范围或业务解释 |
| CyPort [S02] | `Tropical_cyclone_interaction/interaction_data.csv` | 稳定港口 ID/坐标、候选筛选、隐藏 outcome | 最终中断/恢复字段进入早期 Prompt |
| EarthVerse [S03] | `scripts/validate_submission.py`、`scripts/report.py`、`scripts/run_direct.py` | 检查函数、运行记录、报告组织参考 | 整包 RAG 默认上下文、完整工具库、原 Judge 分数 |
| TGMS [S06] | 文档及小型 temporal / trace 例子 | 双时态与可验证依赖思想 | Rust 存储引擎成为必要依赖 |
| AutoSciRub [S07] | Criterion / Verification Schema | 离线数据审核表设计参考 | 在线随机生成评分标准或自动安装插件 |
| StateMemBench / STALE [S08–S09] | 论文中的状态更新与旧前提诊断 | 强状态基线、Probe taxonomy | 未取得作者代码却声称运行官方实现 |
| Criterion Revision [S10] | Trace 与迁移测量原则 | 提交归属、状态使用对照 | 将外部状态利用直接解释成内部信念改变 |
| EWB [S14] | 事件 registry 与配置 | 后期事件组织/边缘案例对照 | 首轮天气模型整套推理管线 |

**状态声明：**上述位置来自前文仓库读取与本次公开资源核查；本文没有克隆、安装或运行这些项目。Codex 必须在 M02 中重新检查实际文件树、许可证与当前可取得的版本。README 的拼写或大小写可能与真实路径不同，不允许猜路径后批量忽略缺失文件。

### 4.2 Lock 文件

首次审计生成以下文件：

```text
upstream_lock.yaml
docs/UPSTREAM_AUDIT.md
licenses/THIRD_PARTY_NOTICES.md
artifacts/audit/upstream_files.csv
```

Lock 至少包含：

```yaml
schema_version: upstream-lock-v1
sources:
  cyportqa:
    repository: https://github.com/ChenchenMobility/MLLM-Bench-CyPortQA
    requested_ref: main
    resolved_commit: null
    checkout_status: NOT_FETCHED
    retrieved_at_utc: null
    license_status: NOT_REVIEWED
    imported_files: []
```

`null` 是初始待办状态，不能带着未解析 commit 宣布正式包已冻结。抓取后填真实 commit、许可证路径和所有导入文件哈希。不可凭记忆填写 SHA，不把分支名当版本。

### 4.3 获取策略

优先顺序：已有本地只读副本 → 小文件下载 → Git tree 清单 → 候选事件的 sparse checkout → 必要时扩大。

禁止为了读取一场 Ian 就默认下载整个图像库或完整 117K QA。先估计总量，超出下载预算则停止本次下载并列出待授权项目。符号链接和重复目录按内容哈希去重；原始路径保留在 provenance。

上游包含代码、任务标注和第三方证据时，逐类记录使用与再分发条件。不能因为根目录有 MIT/Apache 文件就推定所有地图、截图和第三方公告都可按同一许可重发。

---

## 5. 技术架构与信任边界

```text
                         构建阶段（允许读取全部候选数据）
  上游只读副本 → Inventory / Parser → 审核 → Dataset Build
                                              │
                      ┌───────────────────────┴───────────────────────┐
                      ▼                                               ▼
         public bundle（只含公开定义）                  private gold（仅 Evaluator）
         manifest / raw evidence / schema             reference / outcome / probes
                      │                                               │
                      ▼                                               │
          Replay View → Prompt Builder → Backend                     │
                      │                  │                            │
                      │                  ▼                            │
                      │             Raw Response                      │
                      │                  ▼                            │
                      └────────── Commit Store                        │
                                         │                            │
                                         └──── immutable logs ───────┤
                                                                      ▼
                                                          Offline Evaluator
                                                                      ▼
                                                        CSV / JSON / HTML Report
```

### 5.1 三个包边界

- `builder` 可以读取上游 annotations、公开材料和人工审核表，但必须输出严格区分的 public/private 数据。
- `runtime`、`models`、`baselines` **不得 import `evaluation` 或 private loader**。
- `evaluation` 可读取运行日志、冻结 Gold 和对应分支视图，不能调用模型修正其答案。

先用 Python import 边界 + 公开 DTO allowlist + 路径访问测试实现。MVP 不提供任意文件工具，不需要容器化科学执行环境；未来开放 Shell 时再增加 OS 级隔离。

### 5.2 小依赖原则

选择 Python 3.11 或 3.12 的一个版本并锁定；核心用标准库 SQLite/JSON/hashlib/datetime，加 Pydantic v2、PyYAML、Typer、Pillow 和 NetworkX。CSV 可先用标准库；确实需要 Parquet 时再增加 pandas/pyarrow。

开发依赖：pytest、Hypothesis、Ruff；类型检查选 mypy 或 pyright 之一。API SDK、GIS、模型推理环境分别作为可选 extra，不把 Torch/Transformers/CUDA 装入数据构建核心环境。

版本号在 M00 由实际环境解析并锁定，不复制此前草图的宽泛 `>=` 列表后宣称可复现。保留 `uv.lock` 或带精确版本的等价锁文件，二选一，不并行维护互相矛盾的依赖源。

Pydantic 的严格 Python 验证与严格 JSON 验证对 datetime 等类型处理不同 [S13]。请用真实 JSON 序列化往返测试检查时间、枚举、数值和 bool/int，不能只看到 `strict=True` 就认为 wire contract 完整。

---

## 6. 目标目录结构

```text
disastertrace/
├── DisasterTrace_CODEX_IMPLEMENTATION_PLAN.md
├── AGENTS.md                         # 短指令；已有则谨慎合并，不覆盖
├── pyproject.toml
├── uv.lock                           # 或一种等价精确锁文件
├── upstream_lock.yaml
├── README.md
├── .env.example                      # 仅环境变量名，无密钥
├── .gitignore
├── configs/
│   ├── mock.yaml
│   ├── real_smoke.example.yaml
│   ├── pilot.example.yaml
│   ├── sources.yaml                   # 上游位置、抓取权限与下载预算
│   ├── modalities.yaml                # 已审计的模态名到实际路径映射
│   ├── slots.yaml
│   ├── dependencies.yaml
│   ├── port_aliases.yaml
│   ├── source_streams.yaml
│   └── evaluation.yaml
├── docs/
│   ├── IMPLEMENTATION_STATUS.md
│   ├── DECISIONS.md
│   ├── UPSTREAM_AUDIT.md
│   ├── DATA_CARD.md
│   ├── EVALUATION_PROTOCOL.md
│   ├── KNOWN_LIMITATIONS.md
│   └── HANDOFF.md
├── licenses/
│   └── THIRD_PARTY_NOTICES.md
├── external/                         # 只读上游；默认不提交进本仓库
├── src/disastertrace/
│   ├── cli.py
│   ├── schemas.py
│   ├── canonical.py                  # JSON/hash/时间规范化
│   ├── adapters/
│   │   ├── cyportqa.py
│   │   ├── nhc.py
│   │   ├── uscg.py
│   │   └── cyport.py
│   ├── builder/
│   │   ├── inventory.py
│   │   ├── lineage.py
│   │   ├── episode.py
│   │   ├── reference.py
│   │   └── audit.py
│   ├── runtime/
│   │   ├── visibility.py
│   │   ├── replay.py
│   │   ├── store.py
│   │   ├── interventions.py
│   │   └── runner.py
│   ├── models/
│   │   ├── base.py
│   │   ├── mock.py
│   │   ├── openai_compatible.py
│   │   └── prompt.py
│   ├── baselines/
│   │   ├── snapshot.py
│   │   ├── history.py
│   │   ├── ledger.py
│   │   └── revision_guard.py
│   ├── evaluation/
│   │   ├── obligations.py
│   │   ├── state.py
│   │   ├── revision.py
│   │   ├── evidence.py
│   │   ├── propagation.py
│   │   ├── intervention.py
│   │   ├── probes.py
│   │   ├── aggregate.py
│   │   └── report.py
│   └── visual/
│       ├── render.py                 # optional geo extra
│       └── grid.py
├── tests/
│   ├── fixtures/synthetic/
│   ├── fixtures/official/            # 小型、有来源和许可记录的真实摘录
│   ├── unit/
│   ├── integration/
│   └── golden/
├── artifacts/
│   ├── audit/
│   └── builds/<build_id>/
│       ├── public/
│       └── private/
├── runs/<run_id>/
│   ├── run_manifest.json
│   ├── run.sqlite
│   ├── outputs/
│   └── exports/
└── reports/<run_id>/
```

这些目录是目标组织，不要求第一天全部创建空壳。先实现能通过 M01/M04/M05/M06 的必要路径，其余随里程碑增加。

---

## 7. 数据与提交契约

### 7.1 标识符

必须分开：

| 标识符 | 粒度 |
|---|---|
| `storm_id` | 官方气旋标识，或审核过的稳定替代 ID |
| `episode_id` | storm × target port |
| `artifact_id` | 一次特定产品发布/更正记录，不只是文件名 |
| `blob_sha256` | 原始 bytes 内容哈希；同 bytes 可有多个来源位置 |
| `stream_id` | source × product family × jurisdiction × scope × window policy |
| `checkpoint_id` | episode 内时间节点 |
| `variant_id` | base 或具体 intervention |
| `run_id` | 一次冻结配置的运行 |
| `trial_id` | 同一设置下的重复实验 |
| `state_hash` | 规范化持久状态的内容哈希 |

存储主键必须包含 `run_id/model_key/baseline/track/trial_id/episode_id/variant_id`。Tampa 与 Key West、两个模型、两个 baseline 不得互相覆盖状态。

### 7.2 Artifact

定义 Pydantic Model，并导出 JSON Schema。最低字段：

```text
artifact_id, storm_id, source, product_type, stream_id
blob_sha256, storage_relative_path, media_type, source_url
source_issue_time_raw, issued_at_utc, effective_start_utc, effective_end_utc
release_time_quality, release_time_evidence, retrieved_at_utc
version_number, revision_suffix, correction_kind
relation_edges[], geographic_scope, provenance_status
```

`issued_at_utc` 可以未知；但 Strict Track 的 `base_release_at` 必须由合格依据生成。Benchmark 可见时间放在 Replay Schedule 中，而不是改写 Artifact 本身。

`release_time_quality`：

- `VERIFIED_PUBLICATION`：有可核查发布记录。
- `PARSED_OFFICIAL_HEADER`：按官方头部恢复，且无未解决版本歧义。
- `BOUNDED`：只能获得发布时间区间。
- `ASSUMED`：使用明确声明的实验假设。
- `UNKNOWN`：无法确定。

Strict Release-time 默认只允许前两类。`BOUNDED` 可在预注册的保守上界协议中单列；没有任何上界依据时不能靠 effective time 构造上界。

### 7.3 Public Artifact DTO

Prompt Builder 不得直接 `artifact.model_dump()`。建立只允许以下字段的公开 DTO：

```text
public_evidence_id
source_label
product_type
已知且允许公开的 issued/effective time
该文件内容本身已经暴露的版本与来源范围
image/text payload 或受限 evidence handle
```

不允许暴露最终 outcome、Gold 标记、未来 sibling、私有本地路径、未发布 artifact ID、候选筛选得分、隐藏 reference span 或完整 `supersedes` 未来关系。

### 7.4 Checkpoint 与 Episode

```text
Episode:
  episode_id, storm_id, target_port_id, target_definition_version
  checkpoint_policy, checkpoint_ids
  public_task_instruction, input_track
  build_id, split, quality_tier

Checkpoint:
  checkpoint_id, episode_id, checkpoint_time_utc
  phase_label, cutoff_policy
  release_schedule_ref
```

`newly_released` 是运行时计算值，不作为干预后仍不变的唯一权威字段。

phase 只是描述，不保证一定有影响/恢复。只有 3 个可靠节点时记录 `partial_lifecycle=true`；不靠事后想象补第四轮。

### 7.5 MVP Slot Registry

原方案中的六组能力在 wire 层拆成下列 6 个事实字段与一个行动对象；把 watch/warning 拆开，是为了消除不可比较的混合等级，而不是扩大任务范围。

| 字段 | 类型/语义 | 主要来源 | 禁止混淆 |
|---|---|---|---|
| `storm_class` | 官方系统分类枚举 | NHC 正文 | 不仅凭单个 mph 推断所有气旋分类 |
| `cone_relation` | `INSIDE/OUTSIDE/BOUNDARY` 或未知 | 匹配版本的图/GIS | 不是“整体灾害暴露等级” |
| `wind_watch` | 已核实的 watch 类别集合 | NHC 正文/匹配区域 | 空集合与未知不同 |
| `wind_warning` | 已核实的 warning 类别集合 | NHC 正文/匹配区域 | 不把 surge warning 塞进此字段 |
| `wind_probability_34kt` | 官方概率值/区间 + 位置 + 有效窗 | Wind probability product | 不是模型自信度，也不是港口停运概率 |
| `official_port_condition` | 当时可确认的官方状态 | 带辖区与时效的公告 | 不是建议行动，不能由天气 warning 直接生成 |
| `action` | 可接受行动集合中的建议 + 依据 | 公开任务规则与可见材料 | 不声称真实最优政策或真实调度指令 |

Supporting fields：max wind、中心位置、运动、有效期、概率站点、公告权限等可以存储，但不默认等权计入核心状态分数。`storm_surge_*` 和 `observed_disruption` 留作扩展，不将信息不足的字段硬设成 `NONE`。

### 7.6 Slot Value

使用有标签类型而不是宽松 `str | int | float | bool`：

```text
kind: UNKNOWN | CATEGORY | NUMBER | INTERVAL | CATEGORY_SET
value: 类型对应的值；UNKNOWN 时必须为 null
unit: 可选，数字字段由 registry 约束
scope: entity_id / location_id / valid_start / valid_end / threshold 等
confidence: [0,1] 或 null，专指模型对该断言成立的自信度
support: [{evidence_id, role, locator?}]
```

- Pydantic 禁止多余字段，禁止 `true` 混入数值 1，禁止 NaN/Infinity。
- `CATEGORY_SET=[]` 表示经证据核实没有该警报；`UNKNOWN` 表示不够信息。
- 概率 0.8 与自信度 0.8 是不同字段。百分数与 0–1 形式只在 parser 规范化阶段显式转换并记 provenance。
- `locator` 可指原文行范围、图像网格或工具结果键；不是要求长篇思维链。

### 7.7 Reference State / Gold

冻结 Reference 的每个 slot 至少包含：

```text
score_mode: KNOWN | UNKNOWN_REQUIRED | ACCEPTABLE_SET | NOT_SCOREABLE
accepted_value 或 accepted_values
scope, tolerance_policy
support_requirements（多个可替代证据组合）
reference_generation_rule
review_status, review_record_id
```

`NOT_SCOREABLE` 必须排出该指标分母并报告比例；不是正确 UNKNOWN。模型猜对不可见的未来状态也不能获得 grounded-state 分数。

Private 中分开保存：

```text
world_reference        # 事后/观测参考；可缺省
assertable_reference   # 当时可见证据下允许断言什么；核心评分
outcome_reference      # 最终影响/恢复，仅用于明确的后验任务
```

不需要构建完整物理世界数字孪生。

---

## 8. 数据接入：Inventory → Parser → 人工审核

### 8.1 Inventory 必须先于大批量下载

实现 `inventory`：递归枚举实际文件树，输出文件路径、大小、media type、hash、来源目录、候选 storm/year/product、重复组和解析状态。

需要检测：UTF-8 BOM、错误编码、空文件、HTML 错误页伪装 TXT、Git LFS 指针、图片打不开、目录命名差异、大小写差异、同名异内容、异名同内容、原始文件截断。

`modalities.yaml` 或显式映射表连接 upstream 标签与实际目录；不能假设 `Graphic_Uncertainty_cone` 一定就是物理目录名。

产物：

```text
artifacts/audit/file_inventory.csv
artifacts/audit/duplicate_blobs.csv
artifacts/audit/modality_mapping.csv
artifacts/audit/coverage_matrix.csv
artifacts/audit/quarantine.csv
```

每条 quarantine 必须带 `reason_code` 和原始证据路径。缺失文件不允许被 `except: continue` 隐藏。

### 8.2 NHC Parser

优先从文字产品抽取以下可复核字段：

```text
official_storm_id
原始系统名称与分类
advisory_number（支持 1A 等 intermediate）
correction 标记与明确更正范围
本地 issue time + timezone abbreviation + UTC 摘要
中心位置、持续风速、气压、移动（包括 stationary）
完整 Watch/Warning 段与 Changes 段
未来预报/概率的有效时间窗
```

实现约束：

- 先识别产品种类，再应用该种类的 Parser；公共 advisory、forecast/advisory、概率表不能用同一正则硬读。
- 同时保留正文原文和每个解析字段的 evidence span：行范围或字符范围、原字符串、标准化值、规则 ID。
- 日期跨 UTC 午夜、12 AM/PM、行首空白、大小写、CRLF、BOM、intermediate、corrected、stationary 都有测试。
- `TTAA00 KNHC DDHHMM` 这类模板字段不是一个可直接使用的完整时间。
- 固定缩写的 offset 必须有来源记录；正文时区与 UTC 摘要不一致时隔离，不静默择一。
- `...Corrected` 的头部可能仍引用原 advisory 时刻。没有实际更正公开时间时不能假定更正在原发布时间已经可见。
- 气旋分类优先保留官方术语；热带/副热带/潜在气旋/后热带不能仅通过风速阈值合并。
- 不把“Changes with this advisory: None”误读成“当前没有任何警报”。必须读取 active watches/warnings 段。
- 复杂沿海区间与港口归属无法确定时进入审核，不用简单字符串包含关系给全部港口贴标签。

首轮 Parser 输出 `ParsedArtifact`，不直接写 Gold。Gold 由第 10 节编译器消费已审核的解析结果。

### 8.3 NHC 风概率

概率字段必须附上阈值、概率类别、累计/分时段、有效时间窗和具体站点/位置。正式比较只在相同语义窗口上进行。

最近站点数据不能无标识地称为精确港口概率；使用 `location_binding=NEAREST_STATION_PROXY`、距离和审核记录。对 trace/小于某阈值等非点值，保存区间或限定值，不伪造小数。

图形和文本文件可能并非相同 issue time。不能因为文件名 leadtime 相同就给它们共同发布时间。

### 8.4 USCG 公告与港口映射

`uscg_port_conditions_agg.csv` 用于候选和 Bootstrap，不自动等同于直接官方公告。至少核验：

```text
source publication time
condition effective time
issuing authority / jurisdiction
covered ports / waterways
condition label
operational permissions and exceptions
source URL / screenshot reference
```

- 只有 `ConditionEffectiveTime`、没有 publication 证据的记录，不进入 Strict Release-time 主测试。
- 只有聚合 CSV 的情形，可以保留为 `BOOTSTRAP_EFFECTIVE_TIME` 轨迹，报告名称不得伪装成发布时点回放。
- `['TAMPA', 'BAY']` 不一定是两个港口；不得直接按逗号拆分并丢掉无法识别的 token。
- `Tampa Bay` 可能是覆盖多个港口/水道的区域，不应永久映射为单一 Tampa Port。使用经审核的 scope-to-target 多对多映射。
- 对 `NINE` 等早期系统名使用官方 storm ID、时间和来源联合消歧；禁止把同名/同编号的所有记录自动并入 Ian。
- 空 `FacilityOps` 不意味着允许操作，也不允许复制另一条公告的指导补全。
- reopening、restricted reopening、modified condition、local exception 保留原始类别或子状态；禁止一律回退到 `NORMAL`。

输出 alias 表必须有 `raw_name / canonical_id / scope_type / source / review_status`。未知 alias 使相关记录隔离，而不是默默丢弃。

### 8.5 CyPort / CyPortQA 场景字段

若场景 JSON 太大，使用流式读取或只读取已经下载的元数据。初次先输出实际 schema profile，再写 Adapter，禁止臆造 `senario` 根层或时间字段结构。

将字段分为三组：

| 组 | 示例 | 用途 |
|---|---|---|
| 静态候选信息 | 稳定 port ID、位置 | Entity resolution；过时或事后属性仍要审计 |
| 当时产品内容 | 已发布概率、watch/warning | 经核验后进入当时参考状态 |
| 事后结果 | 最终中断、恢复天数、最近距离、全事件最大风速 | Private outcome / 筛选审计，不能进入早期输入 |

即使是“静态属性”，如果字段来自未来年份的港口设施或网络统计，也不能无条件加入严格历史输入。

### 8.6 首个真实候选

先检查 Ian 2022 的现有 advisory 图文文件与 Tampa / Key West 公告。前文确认过的文件名仅作为候选定位线索，不当作本次真实运行产物：

```text
IAN_2022_48h.txt
IAN_2022_36h.txt
IAN_2022_24h.txt
IAN_2022_12h.txt
uscg_port_conditions_agg.csv 中 Ian 2022 相关记录
```

不得预设这些节点就覆盖了登陆、解除或恢复。恢复材料不完整时仅发布早期演变的开发示例，或继续从官方档案补齐；不能拼接另一事件的恢复公告。

Advisory 13 → Advisory 15 的正常预报升级，与 Advisory 15 本身标题/下一公告时间的 correction 是两个不同变化。只有真实语义变化才能作为对应风险更新案例；不能仅凭 `Corrected` 标签计入 RETRACT。

---

## 9. 时间线、产品版本与可见性

### 9.1 产品版本关系

定义边类型：

```text
REVISES_FULL       完整替代同范围的前版产品
CORRECTS_FIELDS    只更正声明字段
CANCELS_CLAIMS     明确取消一组断言或区域警报
DUPLICATE_OF      同一发布的复制件
SUPPLEMENTS       补充产品，不默认取消前版
```

每条边有 `from/to、scope、field_set、effective_window、evidence`。

MVP 可以先完整支持 `REVISES_FULL`、`DUPLICATE_OF` 和有限的显式 cancellation；其他关系出现时可隔离，但不能将其粗暴改写为完整替代。

完整替代只在同一核实的 `stream_id` 内成立。公告覆盖 Tampa 与 Key West 的不同子集时，不能把一条 Key West 新公告当作 Tampa 旧公告失效的依据。

### 9.2 可见性函数必须是纯函数

建议接口：

```python
def materialize_view(
    episode,
    cutoff_utc,
    release_schedule,
    intervention,
    previous_view,
):
    """Return an immutable ReplayView; no Gold reads, no network, no state writes."""
```

逻辑顺序固定为：

```text
1. 读取该 episode 的候选公开 Artifact 与冻结 schedule
2. 应用 variant 的发布时间/首次暴露变换
3. 计算截至 cutoff 已经向此分支释放的 evidence
4. 计算当前 live scope / 版本元数据（只使用已可见关系）
5. new_ids = visible_ids(t) - visible_ids(t-1)
6. 单列因时钟推进发生的有效期变化
7. 构建 Public DTO 与 manifest_hash
```

`Clock tick` 即使没有新文件，也可能使预报窗口过期；需要有这一类 Fixture。不会因为预期存在新 advisory 却没看到它，就自动判定所有旧港口状态失效。

### 9.3 已可见、当前有效、实际发送三类集合

- `visible_ids`：截至当时已经可访问的全部历史证据。
- `live_scope`：公开版本与有效期规则下可用于当前哪些 claim 的证据范围。
- `delivered_ids`：本次真正发送给模型的证据，以及本次已实际读取的工具结果。

历史证据可以用于解释过去或版本差异；不能只因它非最新就判为违规。新材料被延迟后，base 分支中被替代的旧版在 twin 中可能仍是最新已知版。

任何辅助“active product filtering”都要在运行配置中记录。不能悄悄给某个 baseline 正确的 active state，再称为模型自身能力提升。

### 9.4 时间质量与可接受发布

源 issue time、effective time、retrieval time 与 benchmark release time 的转换规则分别记录。

```text
严格来源时间 → base release time
分支干预 → effective branch release time
checkpoint cutoff → visible set
```

`retrieved_at` 只说明本次构建获取了档案，不说明当年用户何时知道。文件系统 mtime、Git commit time、CSV 行顺序也不能替代业务发布时间。

---

## 10. Reference Compiler 与动态修订义务

### 10.1 编译器输出

输入：已核验产品内容、来源角色、目标范围、当前分支可见集合、公开 derivation policy。

输出：

```text
assertable_reference.jsonl
obligation_base.jsonl
support_alternatives.jsonl
reference_audit.csv
```

函数签名建议：

```python
def compile_assertable_reference(public_view, reviewed_facts, frozen_rules):
    """Build branch-specific reference and support alternatives offline."""


def derive_model_obligations(previous_model_state, current_reference, slot_registry):
    """Pure scoring function; no model invocation or state modification."""
```

为了隔离 Gold，`public_view` 仅是用于离线评价的同一视图副本；不要把 `reviewed_facts` 传给 Runtime。

### 10.2 Gold 构建流程

```text
上游已有字段生成草稿
→ 官方文本解析或 GIS 确定性计算
→ 字段类型/时间/位置/来源角色对齐
→ 独立 spot check 与争议审核
→ 冻结 accepted values + support alternatives
→ 对各 variant 重编译 assertable reference
```

Parser 与 Gold 若共享代码，其一致性不能当作独立验证。核心样例应有人工核对、独立表达的断言或第二条计算路径。

### 10.3 未知与“保持旧值”

缺少新证据时，不总是应当 UNKNOWN：

- 仍有效的旧公告可支持当前港口状态，就应保留旧值并注明来源。
- 唯一支持已经到期，且无法确定新状态，才要求撤回或保持未知。
- 模型没在证据库中找到某条文件，不等于该领域事实在现实中不存在。
- 评测方缺少可靠 Gold 时标 `NOT_SCOREABLE`，不能惩罚模型没有写成未知。

### 10.4 操作语义

对同一 `slot_id + target scope`：

| 之前实际状态 | 本轮允许的参考 | 主要语义操作 |
|---|---|---|
| 未知 | 已知并有支持 | ADD |
| 已知且仍落在可接受集合内 | 同一语义值 | KEEP |
| 已知 | 不同的已知可接受值 | UPDATE |
| 已知断言已不能继续支持 | 必须未知 | RETRACT |
| 未知 | 必须未知 | KEEP |
| 任意 | Gold 无法评分 | 不生成该字段操作评分 |

取消警报后可确认“无该警报”，固定槽位的结果是 `UPDATE → empty set`，不强行把它算成 RETRACT。RETRACT 主要表示旧断言退出 active state且没有可支持的替代事实。

值未变但支持来源刷新：语义操作可为 KEEP，提交仍可 WRITE 更新 provenance。概率窗口或目标 scope 变了时，即使数值相同也不能直接当作相同预测；由 registry 的 scope comparator 确定并单列 `SCOPE_CHANGE`。

### 10.5 不是一个简单的单值 Diff

Reference 可含多个合理值、多个证据组合或数值容忍区间。上一版只要仍可接受，就不能为了匹配唯一字符串强迫 UPDATE。

除 `value_operation` 外，另生成：

```text
support_refresh_required
scope_validation_required
unknown_preservation_required
required_recheck_candidates
```

不要把“值正确但只引用失效支持”计为完整修订成功，也不要把合法证据替换当成无关改写。

### 10.6 Model-conditioned 公平性

这类指标的分母依赖模型之前的错误，不能单独排序。必须同时报告：

```text
当前状态 correctness / completeness
每类操作的支持数与 Non-KEEP F1
按上一轮正确/错误分层的 preservation / repair
Oracle-previous-state 的一次更新对照
完整 rollout 的错误占用时间与 EpisodePass
```

首轮主要是初始化，不纳入跨轮修订 Macro-F1。不得把先犯大量错误再修复的模型评为比始终正确的模型更好。

---

## 11. Model-owned Commit 与持久化

### 11.1 提交协议

为消除此前 `ESCALATE` 与状态写入的歧义，采用两个正交字段：

```text
write_mode: WRITE | NO_WRITE
review_request: NONE | REQUEST_EVIDENCE | REQUEST_HUMAN_REVIEW
```

这是对原 proposal 的工程拆分：保留其保留/写入/升级处理三类意图，但“升级请求”本身不再决定是否写状态。

每次完整提交包含：

```text
schema_version
run_context: episode_id / variant_id / checkpoint_id
parent_state_hash
write_mode
current_state（所有 required slots，未知也显式输出）
revisions（每个 required slot 的显式操作）
action
rechecked_slots
review_request / requested_evidence_roles
```

- MVP 采用全量 snapshot，避免半途引入复杂 Patch DSL。
- Slot 输出 key 必须与内部 `slot_id` 一致，不能重复 key。
- WRITE：保存模型提供的完整结构；不得从 Gold 补字段。
- NO_WRITE：事实与行动 snapshot 必须和上一版一致；请求审核可以作为本轮消息留档，不修改状态。
- 仅变更 provenance/confidence 也可 WRITE，但不因此算作语义 UPDATE。
- Escalation request 不是“选择最高危险等级”；它是请求新证据或人工确认。

**确定性初态（Genesis）：**每个连续 execution 从统一的全 `UNKNOWN` required slots 和 `UNKNOWN` action 开始，support 为空；初态只由公开 Schema / registry 生成，不含任何事件 Gold。初态具有固定编码规则和可计算的 `state_hash`。首轮提交以它为 parent；首轮失败时仍保留这一初态并记录失败。初态不是模型已完成一次正确回答，不能进入模型正确率或成功 KEEP 分子。

### 11.2 三类校验分开

| 校验类型 | 示例 | 是否阻止写入 |
|---|---|---|
| JSON / Schema | 无效 JSON、缺 required slot、值类型错误、重复 key | 是，保留上一状态；记录失败 |
| 协议 | episode/checkpoint 错、parent hash 不匹配、NO_WRITE 却改变 state | 是；记录协议失败 |
| 语义与事实 | 错误 warning、错误 evidence、遗漏必要修订、错误行动 | 否；真实保存，交给离线评分 |

不能因为隐藏 Gold 判断一个提交“错了”就拒绝保存并留下较正确的旧状态，那也是一种隐藏纠错。

`revisions` 和最终 snapshot 矛盾的情况：保留格式有效 snapshot作为实际模型状态，同时标记 `operation_state_inconsistency`；过程得分失败。此规则固定，不按是否碰巧提高终态分数更换。

### 11.3 Canonical Hash

保留两份：

```text
raw response bytes / raw_response_sha256
normalized state JSON / state_sha256
```

规范化只负责对象键顺序、约定的 UTF-8 JSON 编码、确定性的时间格式；不负责语义纠错。禁止浮点 NaN/Infinity，定义 `-0.0` 等策略并测试。

数组若语义为 set，应在数据契约中明确“顺序无意义”，哈希规范化可以排序，但原始提交仍保留。其他数组不得随意重排。

### 11.4 SQLite Store

建议每 run 一个 `run.sqlite`，至少有：

```text
runs                冻结配置与源码/数据/Prompt 版本
executions          model/baseline/track/trial/episode/variant namespace
requests            请求签名、payload hash、预算预留、attempt
responses           原始返回、状态、token/latency/provider ID
checkpoints         checkpoint result、validation、accepted flag
states              snapshot、hash、parent、accepted checkpoint
branches            干预共同前缀与分支关系
```

使用事务保存 checkpoint 与 state；对执行 namespace/checkpoint 建唯一约束。导出的 JSON/CSV 是可重建视图，不是第二个权威状态源。

### 11.5 失败、恢复和重试

- 新运行生成新 namespace，禁止 `reset()` 删除已有日志。
- `--resume` 先比较 code/build/prompt/config/hash；不一致则拒绝恢复到同一次执行。
- API 返回已写盘、尚未 commit 时，恢复应重用该返回并继续处理，不再重复调用。
- 429/5xx/连接失败按固定限次重试；输出不是 JSON 属于模型结果，不无限重试到成功。
- 超时可能发生在远端已计费之后；标记 `billing_status=UNKNOWN`，不要承诺跨服务 exactly-once。
- Schema/协议无效时 `accepted=false`，state_hash 仍为上一状态；该 checkpoint 尝试不得算作成功 KEEP。
- 原始答题失败与服务故障分别计数。严格系统指标保留失败，模型质量诊断可单列已完成请求的分数和覆盖率。

### 11.6 默认不收集长思维链

需要的是 evidence IDs、短的来源/派生依据、操作、状态和工具结果，不是私有内部推理。`trajectory.json` 记录可观察的调用与提交，不伪造模型未提供的中间思考。

---

## 12. Intervention Engine：只改变证据到达，不改物理世界

### 12.1 Patch Manifest

```yaml
schema_version: intervention-v1
variant_id: delay_warning_bundle
base_episode_id: synthetic_storm_port_a
branch_before_checkpoint: C2
operations:
  - kind: DELAY_RELEASE
    target_bundle_id: warning_update_bundle
    release_at_utc: '2020-01-01T12:00:00Z'
expected_scope:
  manipulation_type: information_arrival
  alters_world_reference: false
```

以上是合成 Fixture，不是 Ian 的真实时间。

Manifest 只声明输入变换，不把 expected affected Gold 送入 Prompt。真实原文件不复制、不改 bytes；变更的是分支 schedule。

### 12.2 四类 MVP 干预

| 类型 | 实现语义 | 必要检查 |
|---|---|---|
| `DELAY_RELEASE` | 第一次对模型可见时间推迟 | 新时间不早于真实发布；到期后在增量中出现 |
| `WITHHOLD` | 整条轨迹不释放指定首次未见材料 | 不删除过去已经见过的知识 |
| `STALE_COPY` | 不开放新版本，旧版以原时间/版本继续存在 | 绝不把旧产品伪装成新发布 |
| `NULL_UPDATE` | 增加目标语义不变的材料 | 经固定投影检验，Gold 相关值不变 |

普通 missing-modality ablation可以只隐藏图或文，但它不自动构成“关键事实不可见”干预：同一事实可能仍在另一模态中。

### 12.3 冗余证据与 Bundle

对同一事实，如果文字 advisory、地图、摘要和公告中都有相关信息，延迟单文件不一定改变可断言状态。

因此记录两类干预：

- `file_level`：测冗余/模态利用，不预设输出必须变。
- `information_bundle_level`：所有等价支持路径都被考虑，才能声称改变了相应信息可得性。

受影响集合由重新编译后的 Gold 得到，不根据“我们删掉了一张图，所以 action 必须变”人工指定。

### 12.4 共同前缀分叉

Base / Twin 在首次输入差异前复用同一模型实际前缀：

```text
共同 C1 提交（冻结 hash）
            ├── C2 Base → C3 Base → C4 Base
            └── C2 Twin → C3 Twin → C4 Twin
```

对应分支必须使用同一 `parent_state_hash`、模型配置、Prompt 模板与非干预上下文。不能独立跑两个不同随机前缀，再把差异都归因于干预。

可重建的无服务端隐式会话调用最容易复现。若 Backend 使用 opaque server session，不能假装可复制其内部状态；应显式重建相同可观察上下文，并记录这一限制。

### 12.5 干预后的 Gold

对每个 checkpoint 分支重新生成：

```text
assertable_reference
must_change / must_preserve / candidate_recheck
allowed support alternatives
admissible actions
```

`world_reference` 和后验 outcome 不因信息延迟改变。更少证据允许的行动可能是更保守的集合，而不一定是“推迟所有准备”。官方状态是否已知与合理的预防性建议必须分开。

### 12.6 合流不是强制回到 Base 内存

关键材料最终到达后，base/twin 可以有相同当前 Gold，但实际模型状态可能因早期错误不同。应该测恢复过程，而不是强制将 twin state 替换成 base state。

只有显式的状态干预实验才能替换 state；这种实验必须和普通证据到达干预分开标注。

---

## 13. Model Backend、Prompt 与调用预算

### 13.1 统一接口

```python
class ModelBackend:
    def capabilities(self):
        """Return tested protocol, image, schema, seed and sampling capabilities."""

    async def generate(self, request):
        """Return raw output, provider metadata, usage and timing; never read Gold."""
```

先实现 `MockBackend` 和一种兼容用户现有 endpoint 的 API Backend；Ollama/vLLM/Gemini 等仅在需要时加独立 adapter。不要把三套 Agent Framework 同时引入。

协议选择明确为 `chat_completions`、`responses` 或指定本地协议。不能在一次正式 run 中遇到错误就自动切另一协议。

### 13.2 Capability Profile

每个真实 Backend smoke test 验证：

```text
model identifier / resolved version（若可取得）
text support
single/multiple image support
JSON / strict schema support
response usage fields
accepted sampling parameters
request timeout / retry behavior
maximum requested output
provider-specific refusal / truncation response
```

Structured Outputs 可约束输出结构，但不能保证事实正确 [S12]。不支持严格 Schema 的模型仍可参与，使用固定 JSON 指令并报告格式成功率；不允许通过一个更强模型偷偷修复输出。

不支持 temperature/seed 的模型将配置字段设为 `null` 并在 run 中记录。temperature=0 也不能作为结果完全确定的保证；对代表性事件做重复运行诊断。

### 13.3 凭证与 Endpoint

示例环境变量：

```text
DT_MODEL_API_KEY
DT_MODEL_BASE_URL
DT_MODEL_NAME
```

仅记录这些变量是否存在，不记录值。不扫描用户历史聊天、HOME、共享 Codex 凭证或不相关 .env 来猜 token。远端 endpoint 默认要求 HTTPS；localhost 可允许 HTTP。

第三方 relay 是否支持图像、JSON Schema 或 token usage，由 Capability Profile 实测，不能因为它“OpenAI-compatible”就预设全部支持。

### 13.4 Prompt Builder

输入仅来自 Public DTO 和该 baseline 被允许的模型状态：

```text
统一任务定义与 Slot Schema
当前 checkpoint 与目标范围
该分支实际可见/读取的 evidence
该 baseline 的 own state 或历史输出
所需输出 Schema
```

保存：

```text
request.json             # 可重建的实际消息；敏感认证不包含
request_manifest.json    # 顺序、文本/图像 hash、角色、裁剪记录
prompt_version.json
raw_response.txt
provider_response.json   # 经密钥/敏感 header 清理
usage.json
```

对于原始图像，不要默认附加从私有 GIS Gold 导出的 caption；那等于用文字泄露视觉答案。经过公开工具得到的解析结果必须标记为 `assisted_perception` 并对所有对照开放。

### 13.5 上下文预算

- MVP 优先选择能完整放入上下文的 3–4 checkpoint 事件，减少截断混杂。
- 不同模型使用相同证据 byte/image 集合；同时记录实际 token usage。
- 超长时执行冻结且不依赖 Gold 的裁剪规则，逐文件记录 `included/truncated/skipped`。
- 关键证据因预算被裁掉时单列诊断，不能把 unavailable-in-prompt 直接认作修订能力差。
- 不以隐藏义务挑“最相关文件”；Oracle-relevant-evidence 只能是单独上界实验。

### 13.6 并行、缓存与预算

同一 episode 的 checkpoints 必须顺序执行；不同 episode/model/trial 可限流并行。

Cache key 至少包含：

```text
resolved model / provider / endpoint identity（不含凭证）
request bytes hash + image hashes + order
sampling and output constraints
prompt/schema versions
parent state hash
variant + checkpoint + input track
trial_id 或显式 cache policy
```

对独立随机 trials 默认不共享回答 cache。允许复用已经声明的共同前缀，但不能把同一个回答伪装成多个独立重复实验。

预算同时限制外部请求数、预计/实际 token 和费用；guard repair、格式修复、Probe、API 重试都占预算。定价未知时，不得把费用写成 0；先以调用/token 限额控制，并报告 `cost_status=UNKNOWN`。

---

## 14. Baseline 设计：避免把信息不公平当成记忆提升

### 14.1 主对照：Evidence-matched Track

对同一 checkpoint，各 baseline 接收**同一份截至当时可见的证据包**。差别只在有没有此前模型输出，以及这些输出如何组织。

| ID | 实现 | 额外模型上下文 | 主要用途 |
|---|---|---|---|
| B0 `snapshot` | 每轮独立回答相同的当前任务 | 无旧模型输出 | 状态正确率参照，不参与模型自身跨轮操作 F1 排名 |
| B1 `raw_history` | 可见证据 + 此前模型原始回答 | 原始历史回答 | 观察旧断言是否污染新回答 |
| B2 `structured_state` | 可见证据 + 上一版完整 own state | 结构化外部状态 | 测试结构化状态表达 |
| B3 `revision_guard` | B2 + 公开规则驱动的检查提示 | 候选重查信息；最多一次修复 | 方法参考，额外调用成本单列 |

MVP 保证全部证据在各模型预算内；不能一边给 B0 增量、一边给 B2 全部当前资料，却将差异称为 memory benefit。

B0 可以独立从全部可见证据重建正确状态，这不是评测失败，而是重要基线。是否需要状态持久化以及能否节省成本，要靠次级受限轨迹回答。

**B0 的执行隔离：**每个 checkpoint 使用独立的 snapshot child execution，其 `parent_state_hash` 指向上述 Genesis，而不是上一 checkpoint 的模型输出。日志仍记录原 episode 与 checkpoint，方便将独立状态/行动分数汇总成 snapshot episode 参照；但不声称这些独立输出形成了模型持续维护的 own-state 轨迹。B0 的 `ADD/KEEP` 等首轮操作不进入跨轮 revision F1，`validate-run` 按 snapshot 模式验证 parent。B1–B3 则必须继承其自身最近一次实际接受的状态。

### 14.2 次级对照：Delta-only / Memory-budget Track

仅在主协议跑通后实现：每轮只发送新增证据；可携带有限持久状态，旧原始证据不可重新读取，所有方法预算规则相同。

比较自由文本 Summary、结构化 State、有限 Raw-history Buffer。记录 memory token/byte cap 与被丢弃内容。无限历史是额外参考上界，不混为相同预算方法。

不要称这就是完全真实业务系统；它是显式的记忆压缩压力测试。主表和本 Track 分开报告。

### 14.3 Oracle 诊断

- `oracle_prev_state`：一次更新用已审核上一版参考状态，隔离累积错误。
- `oracle_extraction`：使用确定性公开工具可得到的结构化感知结果，隔离视觉/解析困难。
- `oracle_relevant_evidence`：隐藏参考辅助的证据选择上界，必须标 Oracle。
- `stale_prev_state`：明确的状态扰动，只作为鲁棒性测试。

这些 Oracle 不应出现在“无需额外信息”的常规方法排名中。

### 14.4 模型结果判读

原假设包括 Full History 污染、结构化 State 改善和传播遗漏。它们是**待检验假设**，不是代码必须产生的输出。不要增加人为坏 Prompt、删正常证据或改 Gold 以保证排名反转。

---

## 15. RevisionGuard：只使用公开信息的轻量参考方法

### 15.1 流程

```text
本轮已可见的新产品与公开版本元数据
→ artifact type / scope 映射到候选 slots
→ 公共依赖图产生 candidate_recheck
→ 模型自己提交完整 snapshot
→ 公开 Schema / 时效 / 引用 / 操作一致性检查
→ 在授权预算内最多一次定向修复
→ 保存初稿、反馈、修订稿；模型选定最终提交
```

### 15.2 依赖图语义

这是一张**推理依赖与重查图**，不是经过识别的灾害物理因果图。

建议边：

```text
wind_probability_34kt ── may_require_recheck ──> action
wind_watch           ── may_require_recheck ──> action
wind_warning         ── may_require_recheck ──> action
official_port_condition ── constrains ────────> action
cone_relation        ── review_geometry ──────> exposure_review
exposure_review      ── may_require_recheck ──> action
```

`exposure_review` 是内部候选检查节点，不是隐藏 Gold 风险等级。第一版可以不把它暴露为核心评分 slot。

禁止硬编码：

```text
storm_class 改变 ⇒ wind probability 一定改变
outside_cone ⇒ no risk
hurricane_warning ⇒ official_port_condition=ZULU
new file ⇒ 所有下游字段必须 UPDATE
```

### 15.3 Runtime Check 能检查什么

可检查：JSON 类型、必需键、当前是否有该 evidence、所引时间窗是否冲突、公开版本下是否引用了被替代的当前支持、操作与模型自己的前后值是否一致。

不可检查：隐藏 Gold 值、当前样本真正的 must_change 集合、私有审核的唯一正确行动、未发布来源、隐藏 Probe 答案。

如 Guard 使用规则 Parser 直接抽取了关键答案，需标记 `uses_public_extraction_tool=true`，为对照开放相同工具，或单列 assisted Track，不能把提取器贡献归给记忆。

### 15.4 修复预算与指标

设置 `max_repairs_per_checkpoint=1`；原始提交和修复后提交都记录。分别报告 first-pass、final-pass、额外 requests/token/latency。

修复反馈只指出当前公开可检验问题，例如“声明 KEEP 但值发生变化”，不能说“正确答案应为 Hurricane Warning”。

---

## 16. Commit-use Probe：验证外部状态是否被使用

### 16.1 构建三类 Probe

| 类别 | 测什么 | 构建要求 |
|---|---|---|
| State Resolution | 是否读出当前有效状态 | 不重新附带能直接还原答案的原始证据 |
| Premise Resistance | 是否拒绝已失效的旧前提 | 旧前提必须在真实/synthetic 时间线中有依据 |
| Policy Adaptation | 是否把状态用于下游约束 | 任务规则公开，不能靠常识猜隐藏政策 |

题目、答案和 scoring contract 在模型主运行前冻结；Probe 不提前出现在主 Prompt，不写回主事件状态。

### 16.2 四种输入条件

```text
OWN     该模型本次实际保存的当前状态
NONE    不提供状态；保持其他题目信息一致
ORACLE  当前可断言参考状态；不是未来 World/Outcome
STALE   同一事件的前一版或指定旧状态
```

每个 Probe 从隔离会话开始，不能让 NONE 分支继承其他条件的聊天历史。Probe 输出本身也不进入后续主轨迹。

### 16.3 两种评分分开

- `factual_probe_score`：相对于当时可断言 Reference 是否正确。
- `state_fidelity_score`：是否忠实使用所给 state；忠实复述错误状态不等于事实正确。

报告：

```text
Own-State Benefit = Score(OWN) - Score(NONE)
State Quality Gap = Score(ORACLE) - Score(OWN)
Stale Sensitivity = Score(OWN) - Score(STALE)
```

同时提供各条件绝对分数、有效样本数与多次运行波动。

这些差异说明输入的外部状态对输出有可观察影响，不足以证明模型形成了稳定内部信念或实现了通用跨事件学习。

### 16.4 防止从题目泄漏答案

- 不在题目中提供最新 warning 名称，再询问它是不是最新。
- 对 Premise Resistance 平衡正确与过时前提，避免模型学到“一律否定用户前提”。
- 先用合成实体无外部知识版本验证，再做真实命名版本；两种结果分开。
- 隐去最终事件名/精确日期可以减弱记忆污染，但地图地理和文本仍可能暴露身份，不能宣称完全消除预训练污染。
- 若 NONE 也很高，审查题目是否可由常识重建，或承认该 Probe 不强依赖状态；不能直接删掉所有此类结果。

---

## 17. Evaluator：主分数、诊断分数和分母

### 17.1 评分单元

最小原子单元：

```text
episode × variant × checkpoint × slot × scope
```

首先在 checkpoint 内聚合，再在 episode 内聚合，最后按 storm 聚类。每张表必须报告分子、分母、不可评分数与失败数，不只给百分数。

### 17.2 当前状态

Registry 为每个字段指定：exact categorical、set equality/F1、number tolerance、interval compatibility 或 scope-aware matcher。

主指标：

```text
state_accuracy             # 固定公开类型/范围下的正确值
state_completeness         # required slots 是否提交
support_validity           # 证据是否可见、时效/角色/范围是否支持
fully_grounded_state_rate  # 值正确 + 支持成立 + scope 正确
unknown_preservation      # UNKNOWN_REQUIRED 上的正确保持未知
unsupported_assertion_rate
```

数值容忍必须是明确正数；误差在容忍内的 pass 与连续 soft score 分开命名。不能把“容忍=1”的线性分数在误差=1 时为 0，却描述成“误差在1以内都正确”。

`storm_class` 和 warning 默认分类，不使用未经论证的全类别线性等级距离。Port condition 的有序子集可做 ordinal diagnostic，但本地例外和 reopen 不强行塞进统一序号。

### 17.3 修订

报告两层：

- `operation_macro_f1`：模型声明的 KEEP/ADD/UPDATE/RETRACT 与可接受操作是否相符。
- `transition_success`：操作可接受、终态可接受、当前支持成立且 scope 一致。

每类支持数与 `Non-KEEP Macro-F1` 必须同时输出；support=0 时标 `NA`，不能填 100%。缺省操作不是 KEEP，而是 `MISSING_OPERATION`。

### 17.4 状态保护与恢复

`preservation` 的分母只包括：模型上一轮正确、且本轮仍应该保持其语义值的字段。原先错误但本轮被修好，不得算过度修改。

`correct_to_wrong_regression` 排除真实参考状态变化导致的正常更新需求；需要比较同一支持范围。

`stale_claim_rate` 判断的是当前断言仍依赖已经不适用的状态/来源，不只是“引用了旧文件”。旧文件用于历史说明不应计错。

`recovery_latency` 从某次可观测错误开始，到该字段再次满足 reference 的第一时刻；轨迹结束仍未恢复则 right-censored，不能直接当作最后一轮已恢复。主表同时给未恢复比例。

`error_occupancy_time` 用相邻 checkpoint 时间差加权，避免把 3 小时与 24 小时的陈旧状态当成同样严重。

### 17.5 证据合法性

逐条区分：

```text
FABRICATED_ID              数据包根本不存在该 ID
KNOWN_NOT_YET_RELEASED     该分支尚未释放
KNOWN_WITHHELD             该分支明确未开放
VISIBLE_NOT_DELIVERED      已可访问但本调用无实际读取记录
INVALID_CURRENT_SUPPORT    可读的历史证据不支持当前值/窗口
INVALID_SCOPE              不是当前港口/区域/变量
VALID_HISTORICAL_REFERENCE 合法历史比较引用，不惩罚
```

只有对应语义的条目才进入 `future_evidence_use`。在纯 Prompt Track 中，非 delivered 的未读材料不能算有效 grounding；在工具 Track 中，要检查工具读取日志。

### 17.6 传播

分开三个集合：

```text
must_change              Reference 语义确实要求变
candidate_recheck        上游变化可能影响，需要核验
must_preserve            应保持且上一状态正确
```

- `change_recall`：must_change 中被正确改到允许终态的比例。
- `change_precision`：实际语义改变中有依据的比例；合法纠正早先错误单独计入 justified change。
- `unaffected_state_stability`：must_preserve 的正确保持率。
- `declared_recheck_coverage`：自报过程覆盖，明确标为辅助统计。

仅列出所有 descendants 不等于正确 propagation；列出了 recheck 但终态仍错误，不能获得 propagation 成功。

### 17.7 干预对

对于 base/twin 同一时刻，先由私有 Reference 定义：

```text
required_divergence: 两分支可接受状态不相容，必须不同
required_invariance: 目标语义明确相同，应保持相容
ambiguous_overlap: 两分支都允许某些相同答案，不能强迫输出不同
```

当有多个允许值时，比较接受集合/约束，不单纯比较一个字符串。`pair_success` 要求 base 和 twin 都正确，并满足 divergence/invariance；两个错误答案彼此不同不能算成功。

无可评价的 divergence 时，其 Recall 为 `NA`；无实际编辑时 precision 为 `NA`，另报 missed-change。不能靠对空分母都填 1 制造高分。

### 17.8 行动与时机

分开：

```text
official_status_tracking   事实：当时可确认的官方状态
recommended_action        在公开约束下的建议
```

主评分看 admissible set、未违反明确约束及证据支持。行动升级延迟从**相关依据在本分支可见且要求行动变化的时刻**计算，不从事后已知的风暴发生时刻反推。

发布时间只知区间时，延迟也只给区间或不评分。未知尚未解除，不意味着应自动 NORMAL；高风险天气也不自动意味着官方港口关闭。

在没有有效的损失函数、状态转移和专家校验时，不报告 policy regret、真实经济节省或“最优行动”。

### 17.9 概率

- 读取 NHC 概率：评价数值/窗口/站点匹配。
- 模型对一个二元事件的预测：只有定义清楚的 outcome 与抽样协议才用 Brier/log score。
- 模型对自身断言的信心：做 selective risk/accuracy-confidence 诊断，不与 NHC 风概率混在一起。

### 17.10 EpisodePass 与聚合

至少输出：

```text
checkpoint_core_score
worst_checkpoint_score
critical_constraint_pass
EpisodePass@0.6 / @0.7 / @0.8
storm_macro_average
run_completion_rate
```

`EpisodePass@τ` 定义为：所有必需 checkpoint 的 core score ≥ τ，且预注册的关键约束全部通过。τ 是报告阈值，不是重新调整 Gold 的开关。

失败不能直接从分母删除。因数据/Gold 本身无法评分的单元单列；模型缺输出计失败。聚合脚本输出 manifest of exclusions。

多港口的 CI 按 storm cluster bootstrap；base/twin 与所有 ports 随 storm 一起重采样。只有一个 storm 的 Demo 不给跨事件泛化置信区间或稳定排名声明。

---

## 18. 视觉诊断：可选，但不能被文字答案替代

### 18.1 MVP

使用现有真实图像作为模型输入，人工核验它们与文字/GIS 的产品版本、范围和 issue time 一致。没有有效匹配时，图像可做调试但不计入严格多模态测试。

### 18.2 Vector-to-image 扩展

需要时实现：

```text
官方对应版本矢量
→ 明确 CRS 与范围
→ 相邻版本 added / removed / stable geometry
→ 统一渲染和 8×8 网格
→ changed-cell / evidence-to-slot 诊断
```

GIS 要处理：CRS、边界点、地理经纬度与米制距离、跨日界线、无效几何、点 vs 港区范围。不能对经纬度直接调用 planar `.distance()` 并称单位为米。

边界容忍独立标记 `BOUNDARY`；不能因浮点误差强制 INSIDE/OUTSIDE。Coastal warning 若是沿海线段，不能默认把它当闭合 polygon 做 contains。

### 18.3 防止把视觉答案泄漏给模型

私有 polygon difference、changed-cell Gold、GIS inside/outside 结果不进入图像轨迹 Prompt。文本消融、图像消融和公开工具辅助分开。

要证明图像有独立价值，至少保留经过人工确认的 image-required 子集；若文字已经完整回答所有关键问题，不能把性能变化包装为视觉推理突破。

---

## 19. 必须实现的合成 Fixture 与 Golden 测试

合成 Fixture 的来源字段为 `SYNTHETIC_TEST`，使用虚构实体，不能伪造为 NHC/USCG 文件。合成图像仅用于验证图片载荷与视觉接口，不伪装真实天气产品。

### 19.1 四节点最小 Fixture

| 节点 | 合成信息变化 | 应测试的语义 |
|---|---|---|
| C1 / 00:00Z | 一个风 watch；已知港口处于 X-RAY 类测试状态 | 初始建立状态 |
| C2 / 06:00Z | 风 warning 新到达；港口公告未变且仍有效 | 更新天气、保持官方港口状态，重查 action |
| C3 / 12:00Z | 明确限制性港口公告到达 | 更新官方状态与受约束行动 |
| C4 / 18:00Z | 天气 warning 解除，但港口限制尚未解除 | 不得仅因天气改善就声称港口已开放 |

以上只是软件验证情景，不主张真实港口条件规则由这张表定义。真实任务 action rubric 必须另行审核。

### 19.2 干预 Fixture

- Delay C2 warning 的全部等价信息至 C3：C2 不能声称见过该更新；C3 必须将它列入 newly released。
- 只延迟 warning 图像但保留等价文字：Gold 可不变，不强迫 divergence。
- Withhold 在首次见到之前发生：不能擦掉前缀已见的事实。
- Null 插入另一目标材料：相关 Gold 不变。
- Header-only correction：provenance 更新，风险值不变。
- 版本链 v1→v2→v3，v2 未可见但 v3 可见：已知完整替代链正确处理，不让 v1错误重新活跃。
- Partial-scope 更新：Port B 公告不能取消 Port A 状态。
- 没有新文件、仅时间推进导致 forecast 有效窗过期：时效检查仍触发。

### 19.3 Mock Response Fixture

至少提供 5 种模型行为脚本：

```text
correct_script          正确参考行为，仅用于测试系统
stale_script            保留旧 warning
over_revision_script    错改不相关 official status
invalid_json_script     在指定节点返回无效 JSON
recovery_script         先错，再在可见新证据下修复
```

Mock response fixtures 是测试输入，不是实际测得模型行为。不要让生产 `MockBackend` 通过 private Gold 动态生成“完美回答”；测试脚本应独立且可检查。

### 19.4 小型 Golden 结果

为固定 synthetic run 保存手工可验证的 expected counts：

```text
checkpoint_count
accepted_commit_count
invalid_attempt_count
must_change support
wrongly_changed preserved slots
future/fabricated evidence count
expected retained state hashes at invalid checkpoint
pair pass/fail flags
```

优先断言原始计数，再断言聚合分数。只断言“report 文件生成了”不足以验收评分器。

---

## 20. 分阶段任务清单与验收

任务状态仅允许 `TODO / IN_PROGRESS / IMPLEMENTED / TESTED / BLOCKED_EXTERNAL / NEEDS_HUMAN_REVIEW / DONE`。`IMPLEMENTED` 不等于 `DONE`；每个 DONE 必须有对应测试与产物。

### M00｜仓库勘察与执行环境

**前置：**无。  
**目标：**确定工作位置，保护现有修改，建立可续跑工作记录。

- [ ] M00.1 检查当前路径、Git root、已有源码、`AGENTS.md` 和未提交修改。
- [ ] M00.2 写 `docs/IMPLEMENTATION_STATUS.md` 与 `docs/DECISIONS.md`。
- [ ] M00.3 选择并记录 Python 小版本、依赖锁方式、测试/格式/类型工具。
- [ ] M00.4 建 `.env.example` 和忽略规则，不读取或写入真实凭证。
- [ ] M00.5 在不覆盖已有指令的前提下添加短 `AGENTS.md` 路由，指向本文。
- [ ] M00.6 记录是否允许联网、下载预算、API 授权；默认 Mock-only。

**验收：**仓库原有用户修改完整保留；依赖可安装；测试入口可运行；真实网络测试默认关闭。不要要求此时已经有 `dt build`。

**产物：**初始化配置、锁文件、工作状态表、初始环境报告。

### M01｜Schema、严格序列化与最小 Fixture

**前置：**M00。  
**目标：**冻结跨模块接口，先让数据契约可测试。

- [ ] M01.1 实现 Artifact、Public DTO、Episode、Checkpoint、ReplayView、Slot Registry。
- [ ] M01.2 实现 ModelCommit、ReferenceSlot、Intervention、BackendResult。
- [ ] M01.3 导出 JSON Schema；拒绝多余字段、重复 key、NaN、未知 enum、无时区运行时间。
- [ ] M01.4 定义 canonical state hash，验证 JSON round trip。
- [ ] M01.5 构建第 19 节基础 synthetic episode、文本、最小图片与脚本回答。
- [ ] M01.6 实现 `dt schema export`、`dt fixture build`。

**验收：**Fixture 通过 Schema；坏类型按预期失败；同语义规范化 state 的 hash 稳定；原始 bytes 单独保存。

**命令：**

```bash
python -m pytest tests/unit/test_schemas.py tests/unit/test_canonical.py -q
dt schema export --out artifacts/schemas
dt fixture build --name minimal --out artifacts/builds/synthetic-v1
```

### M02｜上游审计与 Adapter

**前置：**M00；可与 M01 部分并行。  
**目标：**把“仓库应该有”变成可核验的实际资源。

- [ ] M02.1 优先发现已有本地上游副本，否则在网络许可内获取树和小文件。
- [ ] M02.2 锁实际 commit 与文件哈希，生成许可和再分发审计表。
- [ ] M02.3 Inventory 检测 BOM、LFS、截断、错误页、图片损坏和重复文件。
- [ ] M02.4 读取真实模板/场景结构，生成 schema profile，不凭旧示例猜字段。
- [ ] M02.5 实现 NHC 产品分类与 Parser；保留字段 spans 和原时间字符串。
- [ ] M02.6 实现 USCG Bootstrap Adapter、港口 scope 映射与时间质量标记。
- [ ] M02.7 实现 CyPort 静态/当时/事后字段隔离。
- [ ] M02.8 为 Ian 候选生成覆盖矩阵和人工审核 CSV。

**验收：**支持的格式通过 fixtures；无法处理的格式可追溯进入 quarantine；无 silent skip；源文件未修改。

**命令：**

```bash
dt upstream audit --config configs/sources.yaml --out artifacts/audit
dt inventory --sources external --out artifacts/audit
python -m pytest tests/unit/test_nhc.py tests/unit/test_uscg.py tests/unit/test_inventory.py -q
```

**外部阻塞处理：**真实下载/许可不明确不阻塞 M04–M10 的 synthetic 实现；写明真实状态为 BLOCKED。

### M03｜Episode Builder 与 Reference Compiler

**前置：**M01；真实包还需要 M02。  
**目标：**同一次构建输出 public/private 分离、可复算的事件包。

- [ ] M03.1 实现 episode/storm/port 标识；固定 checkpoint policy 与 target scope。
- [ ] M03.2 构建产品版本关系；完整替代、部分更正、取消、复制件分开。
- [ ] M03.3 编译 assertable reference、多个支持组合、不可评分掩码。
- [ ] M03.4 生成 Bootstrap / Strict 两级质量标记。
- [ ] M03.5 输出 private outcome，测试其字段不进入 public DTO。
- [ ] M03.6 实现 `dt build-episode` 与 `dt validate-event`。
- [ ] M03.7 生成人工 review packet：时间线、原文 spans、图像版本、冲突条目。

**验收：**相同输入与规则生成相同 build hash；每个 scoreable Gold 有 provenance；Strict 包拒绝未解决时间/范围问题。

**命令：**

```bash
dt build-episode --source-config configs/sources.yaml --storm IAN --year 2022 --port TAMPA --quality bootstrap --out artifacts/builds/ian-tampa-draft
dt validate-event --build artifacts/builds/ian-tampa-draft --quality bootstrap
python -m pytest tests/unit/test_reference.py tests/unit/test_lineage.py tests/integration/test_public_private_boundary.py -q
```

**注意：**上例是待实现 CLI 的调用形状；数据不足时必须返回明确质量失败，不能构造假的“完整 Ian”。

### M04｜纯函数 Replay 与可见性

**前置：**M01；Synthetic 不依赖 M02/M03。  
**目标：**同一 cutoff 与 variant 总能生成相同 public view。

- [ ] M04.1 实现 schedule override 后再过滤时间的算法。
- [ ] M04.2 分开 visible/live/delivered/newly released。
- [ ] M04.3 修正跨版本和范围的活跃支持解析。
- [ ] M04.4 禁止未来关系/目录/标注 metadata 泄漏。
- [ ] M04.5 时钟推进、重复 cutoff、空增量均有稳定行为。
- [ ] M04.6 实现 `dt inspect-view`，默认只输出 Public DTO。

**验收：**第 19 节时序和分支 Fixture 全部通过；无 Gold import/read；Delayed 文件在实际释放时进入增量。

```bash
python -m pytest tests/unit/test_visibility.py tests/unit/test_replay.py -q
dt inspect-view --build artifacts/builds/synthetic-v1 --episode synthetic_storm_port_a --checkpoint C2 --variant base
```

### M05｜Commit Store、哈希链与 Resume

**前置：**M01、M04。  
**目标：**逐字留存模型原答，可靠保存模型自己的有效结构。

- [ ] M05.1 实现 SQLite namespace 与唯一键。
- [ ] M05.2 分开 raw、schema validation、protocol validation、accepted snapshot。
- [ ] M05.3 实现 WRITE / NO_WRITE 与独立 review_request。
- [ ] M05.4 invalid 保留前态但记录失败；semantic wrong 正常写入。
- [ ] M05.5 实现事务写入、state parent hash、导出重建。
- [ ] M05.6 实现新 run 和 resume，禁止默认删除旧状态。
- [ ] M05.7 模拟崩溃位置并验证不重复使用或错覆盖已完成 checkpoint。

**验收：**模型/港口/baseline/variant 隔离；Evaluator 无写权限；非法状态不能串改下一执行。

```bash
python -m pytest tests/unit/test_store.py tests/integration/test_resume.py tests/integration/test_namespace_isolation.py -q
```

### M06｜离线评分核心

**前置：**M01、M05；Reference 使用 M03 或测试 Fixture。  
**目标：**先证明指标正确，再调用真实模型。

- [ ] M06.1 实现当前状态、类型/范围/容忍、支持替代路径评分。
- [ ] M06.2 实现 model-conditioned obligations 与操作/终态分层评分。
- [ ] M06.3 实现 UNKNOWN_REQUIRED / NOT_SCOREABLE 区别。
- [ ] M06.4 实现 preservation、regression、stale、recovery 的分母与 censoring。
- [ ] M06.5 实现证据违规分类、缺字段/无效尝试处理。
- [ ] M06.6 实现 EpisodePass 和 storm-level aggregate。
- [ ] M06.7 为小 Fixture 人工计算 expected counts，生成 Golden 测试。
- [ ] M06.8 实现 `dt evaluate` 与 CSV/JSON 报告。

**验收：**Golden 计数与评分完全一致；0 分母输出 NA；不修改 run.sqlite 中的模型状态；不依赖网络/LLM Judge。

```bash
python -m pytest tests/unit/test_obligations.py tests/unit/test_metrics.py tests/golden -q
```

### M07｜Backend、Prompt、Runner 与前三个 Baseline

**前置：**M04、M05；真实 smoke 前要求 M06。  
**目标：**从 build 到一条完整可评分轨迹。

- [ ] M07.1 MockBackend 支持正确、陈旧、过度改写、无效 JSON 和恢复脚本。
- [ ] M07.2 实现公开 Prompt Builder，保存实际消息/证据哈希。
- [ ] M07.3 实现一个 API Backend 与 capabilities 检查，不把所有端点视为同一协议。
- [ ] M07.4 实现 Snapshot / Raw History / Structured State，同一证据包主对照。
- [ ] M07.5 实现 request budget、超时、固定重试、缓存与 run manifest。
- [ ] M07.6 checkpoints 串行，episodes 可限流并发；实现 dry-run 调用估算。
- [ ] M07.7 完成离线 `dt run → dt evaluate → dt report`。

**验收：**Mock E2E 无网络通过；API tests 默认 skip；无凭证不妨碍核心工作；secret 不进入日志。

```bash
dt run --config configs/mock.yaml --build artifacts/builds/synthetic-v1 --run-id smoke-offline
dt evaluate --run runs/smoke-offline --gold-root artifacts/builds/synthetic-v1/private --out reports/smoke-offline
dt report --scores reports/smoke-offline --format html
python -m pytest tests/integration/test_offline_e2e.py tests/unit/test_prompt.py tests/unit/test_budget.py -q
```

### M08｜干预、共同前缀分叉与成对评分

**前置：**M06、M07。  
**目标：**确保观测到的差异来自声明的输入干预。

- [ ] M08.1 实现 Delay、Withhold、Stale-copy、Null Manifest。
- [ ] M08.2 支持 information bundle，并检查其他模态仍存在的等价支持。
- [ ] M08.3 分叉时复制同一 accepted prefix state，不重跑两个不同前缀。
- [ ] M08.4 编译分支-specific Reference 与必须不同/相同/可重叠目标。
- [ ] M08.5 实现 PairPass、变化正确率、无关状态稳定性与恢复。
- [ ] M08.6 输出 prompt diff / manifest diff / changed scope report。

**验收：**不同分支前缀 hash 相同；只有声明输入变更；不会删除已经暴露的知识；两个错误但不同的答案无法获得 PairPass。

```bash
python -m pytest tests/unit/test_interventions.py tests/integration/test_branching.py tests/golden/test_pairs.py -q
dt run --config configs/mock.yaml --build artifacts/builds/synthetic-v1 --variants base,delay_warning_bundle,null_update --run-id smoke-pairs
```

### M09｜Hidden Probes 与状态使用诊断

**前置：**M06、M07；配对诊断使用 M08。  
**目标：**独立测量外部状态输入对下游回答的影响。

- [ ] M09.1 生成三类 Probe 和独立评分 contract。
- [ ] M09.2 OWN/NONE/ORACLE/STALE 会话隔离。
- [ ] M09.3 Probe 不写回主 State Store；输出另存 namespace。
- [ ] M09.4 分开 factual correctness 与 state fidelity。
- [ ] M09.5 支持正确/陈旧前提平衡和 synthetic entity 对照。
- [ ] M09.6 输出绝对分数、条件差值、调用成本和泄漏诊断。

**验收：**运行 Probe 前后主 state hash 完全一致；NONE 没有其他条件历史；ORACLE 不使用未来 outcome。

```bash
dt probes run --config configs/mock.yaml --run runs/smoke-offline --conditions own,none,oracle,stale --out runs/smoke-offline/probes
python -m pytest tests/unit/test_probes.py tests/integration/test_probe_isolation.py -q
```

### M10｜RevisionGuard 与可选视觉诊断

**前置：**M06、M07；可以与 M09 并行。  
**目标：**形成轻量参考方法，不引入训练工程。

- [ ] M10.1 实现 public artifact-type → candidate slots → dependency frontier。
- [ ] M10.2 实现不访问隐藏 Gold 的 Runtime Check。
- [ ] M10.3 最多一次定向 repair，保存 before/feedback/after 与额外预算。
- [ ] M10.4 first-pass / final-pass 成绩和效率分开。
- [ ] M10.5 optional：匹配 NHC GIS、统一地图/网格、视觉 Gold 私有化。
- [ ] M10.6 optional：图文消融与 image-required subset 审核。

**验收：**Guard 无 private data access；不自动填写正确值；没有 geo extra 仍可运行所有核心测试。视觉扩展失败不阻塞核心验收。

```bash
python -m pytest tests/unit/test_guard.py tests/integration/test_guard_no_gold.py -q
```

### M11｜真实 Pilot、数据卡与交付

**前置：**M00–M10 核心已通过；真实数据需人工审核；真实 API 需预算许可。  
**目标：**可复现的真实小规模实验，而不是承诺一定得到某种研究结论。

- [ ] M11.1 真实候选通过发布时间/范围/许可证 review，冻结 build 与 split。
- [ ] M11.2 先做 1 模型 × 1 episode × 3 baseline 小规模 smoke，再扩大。
- [ ] M11.3 执行预先批准的调用预算；首次超过请求/成本/token cap 即停止。
- [ ] M11.4 逐例核验关键错误是否来自 parser/Gold，而非直接归咎模型。
- [ ] M11.5 扩大到目标 12 episodes 前先统计独立 storms、修改操作与不可评分比例。
- [ ] M11.6 输出 Bootstrap 与 Strict 结果、失败覆盖率、配置与数据版本。
- [ ] M11.7 写 DATA_CARD、EVALUATION_PROTOCOL、KNOWN_LIMITATIONS、HANDOFF。
- [ ] M11.8 发布前运行去泄漏、许可与 secret scan；没有明确发布授权则只产出本地包。

**验收：**读者可从 README 重跑离线 Demo；获授权者可从锁定源与配置重跑真实 Pilot；任何未完成人工审核、未运行实验和外部依赖均明确记录。

### 20.1 推荐关键路径

```text
M00
 ├── M01 → M04 → M05 → M06 → M07 → M08 → M09
 └── M02 → M03 ────────┘         └────────→ M10
                                             ↓
                                            M11
```

M02/M03 的真实数据可能因来源时间审核阻塞，但不妨碍 synthetic software path。不能把“Mock 全通过”误写成“真实数据已通过”。

---

## 21. 强制测试矩阵

下表是验收标准，不是仅供参考的测试名称。允许合并测试文件，但不能省略对应语义。所有核心测试默认离线执行。

### 21.1 Schema / Parser / 数据质量

| ID | 测试 | 预期 |
|---|---|---|
| T01 | JSON 重复 key | 拒绝，不取最后一个值掩盖矛盾 |
| T02 | 数字字段传 true / NaN / Infinity | 拒绝 |
| T03 | 无时区时间进入 Runtime | 拒绝 |
| T04 | UTC 午夜换日、12 AM/PM、CRLF、BOM | 正确解析并保留原文 |
| T05 | Header 与 UTC 摘要不一致 | Quarantine，不静默修正 |
| T06 | Intermediate advisory 1A、常规 2 | 正确的版本表示，不按字符串数值误排 |
| T07 | Corrected 产品仍带原 issue time | 不推断更正在原时点已可见 |
| T08 | `Changes: None` 但已有 active warning | 不解析成无警报 |
| T09 | 概率累计窗与分时段概率 | 分开；不把二者当同一数值 |
| T10 | 最近站点与港口不是同一点 | 必须保留 proxy/location binding |
| T11 | 只有 USCG effective time | Strict release-time 验收不通过 |
| T12 | `['TAMPA','BAY']`、区域 alias、多港公告 | 不盲目分裂/合并目标 |
| T13 | 同名早期系统 NINE 跨事件 | 无充分标识则隔离 |
| T14 | 空 guidance / 缺模板字段 | 不补造事实；有完整缺失统计 |
| T15 | 图像损坏、HTML 错误页、LFS pointer | 拒绝进入模型证据 |
| T16 | 重复原始文件 | 复用 blob，保持各自 provenance |

### 21.2 可见性 / 干预 / 安全

| ID | 测试 | 预期 |
|---|---|---|
| T17 | cutoff 边界前后 | `release_at <= cutoff` 规则稳定 |
| T18 | 延迟材料到下个 checkpoint | 届时进入 newly_released |
| T19 | 旧版在 base 被替代、twin 新版未到 | twin 旧版可继续是最新已知支持 |
| T20 | v1→v2→v3，v2不可见 | 完整替代语义正确；无错误复活 |
| T21 | 仅 Port B 新公告 | 不覆盖 Port A 状态 |
| T22 | Null update | 相关 Reference 不变 |
| T23 | 延迟图片但正文已有同义事实 | 不强制 Reference 改变 |
| T24 | Withhold 已在前缀暴露的证据 | 拒绝该普通干预或标记为另类操作 |
| T25 | 时钟推进无新文件、有效期变化 | 更新时效视图，不伪造新证据 |
| T26 | 模型查看 `../private` 或任意路径 | 受限读取拒绝 |
| T27 | Public DTO 含 outcome / private path | Schema/allowlist 验证失败 |
| T28 | 尚未发布产品通过完整 inventory 泄漏 | 测试失败，必须移除 |
| T29 | 最终系统名在早期来源尚未出现 | 不由私有规范化 metadata 提前暴露 |
| T30 | Base/Twin 共同前缀 | 请求和 state hash 相同 |

### 21.3 Commit / Resume / 预算

| ID | 测试 | 预期 |
|---|---|---|
| T31 | 两模型/两港/两 baseline 同时运行；Snapshot 独立节点 | namespace 完全隔离；B0 各节点指向 Genesis，连续基线指向实际前态 |
| T32 | 语义错误、格式正确的提交 | 保存错误并进入下一轮 |
| T33 | 无效 JSON | 尝试留档，保留前态，非成功 KEEP |
| T34 | NO_WRITE 却更改行动/事实 | 协议失败 |
| T35 | 操作 KEEP 但 snapshot 值变化 | 保存有效 snapshot，过程一致性失败 |
| T36 | Parent hash 不匹配 | 拒绝 commit，不悄悄换 parent |
| T37 | 新 run | 不删除旧 run |
| T38 | 相同配置 Resume | 重用已完成请求与提交 |
| T39 | 变更 Prompt/build 后 Resume | 拒绝合并到原执行 |
| T40 | 写 Raw 后进程崩溃 | 可恢复，不默认重发已完成请求 |
| T41 | API timeout 后费用未知 | 不填零成本，不无限重试 |
| T42 | 无凭证 | Mock 完整运行；真实 Backend 明确报配置阻塞 |
| T43 | 达请求上限 | 下个外部请求前停止 |
| T44 | Guard repair / Probe / retry | 计入预算 |
| T45 | 缓存跨独立随机 trial | 默认不复用作为独立样本 |
| T46 | Endpoint 不支持 Schema/seed/temperature | 预检查记录，不静默改协议 |
| T47 | 日志包含 API key / Authorization | Secret scan 失败 |

### 21.4 Gold / 指标 / Probe / 视觉

| ID | 测试 | 预期 |
|---|---|---|
| T48 | UNKNOWN_REQUIRED vs NOT_SCOREABLE | 不同分母和得分行为 |
| T49 | 多个允许值 | 旧值仍可接受时无需强迫 UPDATE |
| T50 | 相同值但有效窗不同 | scope-aware 判定，不误当相同预测 |
| T51 | 当前值正确但无合法支持 | value 分可得，grounded 分不可得 |
| T52 | 历史证据用于历史比较 | 不算 current-support 违规 |
| T53 | 不存在 ID vs未来 ID | 分别统计 |
| T54 | 以前错误、本轮主动修好 | 不算 over-revision |
| T55 | 声称 rechecked 但终态错误 | 不算传播成功 |
| T56 | base/twin 两个不同的错误答案 | PairPass 失败 |
| T57 | 无 divergence / 无该类操作 | NA + support 0，不填 100% |
| T58 | 无效提交导致 retained state 碰巧正确 | 单独报 retained quality；本轮提交不算成功 |
| T59 | 恢复未发生 | Censored，不假设最后一刻恢复 |
| T60 | 只有一个 storm 的多港 Demo | 不声称独立 N=2，不做稳定泛化 CI |
| T61 | Evaluator 运行前后 | 模型 state hash / accepted log 不变 |
| T62 | Guard 读取私有 Gold 或实际 must_change | 测试失败 |
| T63 | Probe OWN/NONE/ORACLE/STALE | 不共享隐式会话，不写回主状态 |
| T64 | 错误 OWN state 被忠实复述 | fidelity 可高，factual score 仍低 |
| T65 | 所有过时前提都被否定 | 正确前提对照检测该投机策略 |
| T66 | Cone 外但有独立 wind warning | 不能推断 NO_RISK [S05] |
| T67 | 经度纬度 `.distance()` 当米 | 测试失败或禁止路径 |
| T68 | Coastal line 当闭合 polygon | 拒绝不匹配几何方法 |
| T69 | 私有视觉 Gold 被转成 caption 输入 | 去泄漏测试失败 |
| T70 | 图文版本 issue time 不同 | 不自动绑定同一版本 |

### 21.5 标准验收命令

项目实现后统一支持：

```bash
python -m pytest tests/unit tests/integration tests/golden -q
python -m ruff check src tests
python -m ruff format --check src tests
```

类型检查使用 M00 选定的工具；真实联网测试标记 `network`，真实模型测试标记 `live_model`，默认禁用。CI 默认无密钥、无真实模型请求、无大文件下载。

增加 pytest 或等价配置，在核心测试中阻止未声明的 socket 请求，防止“离线测试”实际消耗 API。

---

## 22. CLI、配置与运行产物

### 22.1 必须实现的 CLI

| 命令 | 作用 | 默认联网 |
|---|---|---|
| `dt doctor` | 环境、路径、配置、依赖检查，不输出凭证 | 否 |
| `dt schema export` | 导出 JSON Schema | 否 |
| `dt fixture build` | 构建软件测试包 | 否 |
| `dt upstream audit` | 检查本地/授权获取的上游版本与许可 | 仅显式允许时 |
| `dt inventory` | 构建文件清单、重复组、隔离清单 | 否 |
| `dt build-episode` | 从审核结果生成 public/private 包 | 否；抓取另走独立步骤 |
| `dt validate-event` | 质量层级、时间、版本、支持、split 审计 | 否 |
| `dt inspect-view` | 查看指定 checkpoint/variant 的公开视图 | 否 |
| `dt backend check` | 能力检查，真实请求仍需预算授权 | 仅显式允许时 |
| `dt run --dry-run` | 输出执行矩阵、请求数估计、预算检查 | 否 |
| `dt run` | 执行 baseline 轨迹 | 由 Backend 与许可决定 |
| `dt probes run` | 独立 Probe 条件实验 | 由 Backend 与许可决定 |
| `dt validate-run` | 校验日志、hash、请求/输出与状态连续性 | 否 |
| `dt evaluate` | 离线评分，不修改状态日志 | 否 |
| `dt report` | 生成静态 HTML / Markdown / CSV / JSON | 否 |
| `dt export` | 生成有许可和泄漏清单的本地交付包 | 否，不自动上传 |

所有危险或昂贵操作有 dry-run；`--resume` 不接受配置漂移；已有 run_id 默认报冲突而不是覆盖。

### 22.2 Offline 配置示例

```yaml
schema_version: run-config-v1
run_id: smoke-offline
build_id: synthetic-v1
execution_mode: mock
input_track: evidence_matched
allow_network: false
allow_paid_api: false

episodes:
  - synthetic_storm_port_a

variants:
  - base
  - delay_warning_bundle
  - null_update

models:
  - key: mock_stale_then_recover
    backend: mock
    response_script: tests/fixtures/synthetic/responses/stale_then_recover.jsonl

baselines:
  - snapshot
  - raw_history
  - structured_state
  - revision_guard

budget:
  max_external_requests: 0
  max_download_bytes: 0
  max_estimated_cost_usd: 0
  max_output_tokens_per_request: 2048
  max_repairs_per_checkpoint: 1
  max_transport_retries: 0

runtime:
  episode_workers: 1
  checkpoint_order: sequential
  context_overflow_policy: fail
  invalid_commit_policy: retain_previous_and_mark_failed
  store_backend: sqlite
  overwrite_existing_run: false

evaluation:
  first_checkpoint_in_revision_metrics: false
  missing_prediction: fail
  gold_unscoreable: exclude_and_report
  bootstrap_unit: storm
  episode_pass_thresholds: [0.6, 0.7, 0.8]
```

Mock response script 需要按 baseline/variant/checkpoint/attempt 有明确记录；缺一项就显式报错，不能回退为“最后一个正确回答”。

### 22.3 真实 Smoke 配置模板

```yaml
schema_version: run-config-v1
run_id: real-smoke-pending
execution_mode: real
input_track: evidence_matched
allow_network: false
allow_paid_api: false
build_id: null

episodes: []
variants: [base]
baselines: [snapshot, raw_history, structured_state]

models:
  - key: user_selected_model
    backend: openai_compatible
    protocol: chat_completions
    model_env: DT_MODEL_NAME
    api_key_env: DT_MODEL_API_KEY
    base_url_env: DT_MODEL_BASE_URL
    capability_profile: null
    sampling:
      temperature: null
      seed: null

budget:
  max_external_requests: 0
  max_estimated_cost_usd: 0
  max_output_tokens_per_request: 2048
  max_transport_retries: 2
  max_repairs_per_checkpoint: 0

runtime:
  episode_workers: 1
  context_overflow_policy: fail
  invalid_commit_policy: retain_previous_and_mark_failed
```

该模板故意未启用真实调用。只有在用户选定模型、端点、事件与明确预算后，才改成可运行配置。不要自动把开关设为 true。

### 22.4 预算计算

先估算，不把以下数值当已发生实验：

```text
自然轨迹逻辑调用 = episodes × checkpoints × models × baselines
干预逻辑调用 = 每个分支实际需要新执行的 checkpoints 之和
Probe 逻辑调用 = probes × conditions × models × selected_methods
总外部请求 = 逻辑调用 + repair + transport retries
```

示例：2 episodes × 4 checkpoints × 1 model × 3 baselines = 24 次**逻辑调用**，不包括重试或 Probe。Guard 的额外调用不得从预算中遗漏。

12 episodes × 4 checkpoints × 2 models × 4 baselines = 384 次自然轨迹逻辑调用。这是扩大阶段的上限估算之一，不是默认首次执行规模。

共同前缀复用可以减少实际请求，但需要保存 parent execution reference；统计不能把复用当新的独立模型样本。

### 22.5 结果文件

每个 run 至少输出：

```text
runs/<run_id>/
├── run_manifest.json
├── run.sqlite
├── execution_plan.json
├── budget_ledger.jsonl
├── outputs/<model>/<baseline>/<track>/<trial>/<episode>/<variant>/<checkpoint>/
│   ├── request_manifest.json
│   ├── request.json
│   ├── raw_response.txt
│   ├── protocol_validation.json
│   ├── parsed_commit.json             # 格式无效则不存在，不伪造空成功对象
│   ├── accepted_state_snapshot.json   # 可从 SQLite 重建
│   ├── checkpoint_receipt.json
│   └── usage.json
└── exports/
    ├── checkpoints.jsonl
    ├── states.jsonl
    └── errors.jsonl

reports/<run_id>/
├── validation_summary.json
├── score_definitions.json
├── per_slot.csv
├── per_checkpoint.csv
├── per_episode.csv
├── per_storm.csv
├── revision_support.csv
├── intervention_pairs.csv
├── probe_conditions.csv
├── exclusions.csv
├── cost_and_coverage.csv
├── failure_cases.md
└── index.html
```

HTML 使用本地静态资源，不依赖外部 CDN。展示 side-by-side 的 evidence release、模型前态/后态、Reference、真实变更和评分说明；这是开发审计页，不是主研究 Pre，也不混入口播稿。

---

## 23. 数据审核、研究判断与范围扩展

### 23.1 人工审核表

`review_packet.csv` 至少包含：

```text
record_id / artifact_id / episode_id
字段/范围/时间疑点
source snippet 或图像定位
parser 输出
待判断事项
review_status
reviewer_id
reviewed_at_utc
decision
supporting_reference
```

Codex 生成待审核项目和建议，但不得自填人类 reviewer、签字、已审核时间或专家认可。代码可检查审核结构和覆盖率，不能替代真实审核。

### 23.2 三层成功

| 层级 | 成功标准 | 不代表什么 |
|---|---|---|
| Software Ready | Synthetic E2E、Golden 指标、隔离/恢复测试通过 | 不代表真实数据可靠 |
| Data Ready | 真实产品时间、范围、版本、许可与 Gold 审核通过 | 不代表模型实验已有结论 |
| Research Ready | 冻结协议下完成有覆盖报告的真实对照实验 | 不保证某个 novelty claim 或论文录用 |

### 23.3 Pilot 候选规模

Software Demo：1 synthetic storm + 至少 2 variants。  
Real Vertical Slice：1 真实 storm × 最多 2 ports × 3–4 checkpoints。  
Pilot 目标：约 12 episodes，优先增加独立 storms，而不是重复同一 storm 的很多港口。

这些数量是计划上限/目标，不是已核实存在的合格数据。M02/M03 的覆盖审计决定最终能支持多少。

### 23.4 样本选择

开发集可优先选择 revision-rich 候选，以测试所有路径；正式集应冻结覆盖与分层规则，报告常见 KEEP 与稀有变化的真实比例。

统计：

```text
独立 storm 数
port episodes 数
有可靠 release time 的比例
图文匹配比例
各操作支持数（不硬造 RETRACT）
升级 / 降级 / 仅支持变化 / 未知保留
scoreable / not-scoreable 比例
每类干预数量及实际改变可断言状态的比例
```

不要为了达到“至少4个 RETRACT”而把所有 warning cancellation 改标签；固定槽位下“已确认没有警报”是一个新的已知值。

### 23.5 Go / No-Go

**工程继续条件：**没有关键时间/泄漏/状态保存错误，指标可由 Golden 复算。  
**数据继续条件：**有足够独立、可审计事件，不可评分项和来源缺口可接受。  
**研究判断：**报告静态与轨迹、历史与结构化状态、自然与干预、Own 与 No State 的差异及不确定性。

观察不到预期现象时：先审查实现与数据，再忠实记录负结果。不能将“结果未支持初始假设”当作隐藏调参指令。

允许的范围调整：

| 问题 | 可接受处理 |
|---|---|
| 港口公告发布时间无法恢复 | 严格轨迹只评价可核验 NHC 来源；港口部分单列 Bootstrap |
| 业务 action Gold 争议大 | 以官方状态跟踪和公开约束为主，行动解释为次级结果 |
| 完整生命周期不足 | 发布部分生命周期子集，明确缺恢复阶段 |
| 结构化状态基线很强 | 强化成本、时间干预和跨模态诊断，不人为削弱该 baseline |
| 视觉贡献不明显 | 报告文字充分性，开发真正 image-required 子集后再声称视觉价值 |
| 可用独立 storms 少 | 缩小泛化主张，报告探索性结果，不把 ports/twins 当独立事件 |

### 23.6 后续扩展优先级

优先增加独立 storms 与审核过的时序证据；其次补足几类自然变化、有效 Null/Delay pairs；再加近失事件、视觉网格子集和小型工具任务。

TGMS、AutoSciRub、外部 StateMem-style 方法和变化检测网络只能通过可选 Adapter 引入。没有可运行作者代码时，标记 `inspired reimplementation`，不能用论文名字冒充官方 baseline。

---

## 24. Codex 分工、续跑与最终交接

### 24.1 可并行与不可并行

可以分工：

```text
Agent A：上游 audit、NHC Parser、真实来源回查
Agent B：Schema、Replay、Store
Agent C：Evaluator 与独立 Golden 计数
Agent D：Backend、Prompt、Report
```

前提是先冻结 schemas。一次只有一位负责人修改同一契约/lock 文件；其他模块通过接口协作。合并后必须跑完整离线测试。

不能并行：同一执行 namespace 中连续 checkpoints 的模型状态写入。不能让多个 Agent 共用同一个 SQLite state stream 后依赖“最后写入者”获胜。

### 24.2 状态文件模板

```markdown
# Implementation Status

## 当前范围
- plan_version:
- code_commit:
- build_id:
- execution_mode:
- last_completed_milestone:
- current_milestone:

## 已完成
| Task | Code/Artifact | Validation command | Result |
|---|---|---|---|

## 阻塞
| Task | Blocker | Evidence | Next action |
|---|---|---|---|

## 最近测试
- command:
- exit_code:
- output_summary:
- log_path:

## 接下来执行
下一里程碑与需要读取的章节。
```

每次恢复会话，先读本文件、`DECISIONS.md` 和对应任务，不重新推翻已冻结协议。

### 24.3 短 AGENTS.md 模板

官方文档将 `AGENTS.md` 作为持久项目指令来源 [S11]。完整计划放在独立 Markdown，短指令只负责路由和关键约束，不依赖自动加载整份长文。

```markdown
# DisasterTrace project guidance

Read `DisasterTrace_CODEX_IMPLEMENTATION_PLAN.md` before implementing a milestone.
Start with sections 0–3, 7, and the current milestone in section 20.
Use `docs/IMPLEMENTATION_STATUS.md` and `docs/DECISIONS.md` for continuation.

- Preserve existing user changes and upstream source bytes.
- Default to offline fixtures and MockBackend.
- Do not call paid APIs, download model weights, or publish artifacts without explicit approval and caps.
- Keep publication time, effective time, visibility, and outcome time separate.
- Runtime and baselines must not read private Gold or hidden probes.
- Store model-owned state; do not silently repair semantic errors.
- Never delete prior runs on reset. Resume only with matching configuration and hashes.
- Run relevant unit/integration/golden tests after each milestone.
- Report mock success, source audit, real model execution, and human review separately.
- Do not change test labels, splits, or scoring rules to make a hypothesis look successful.
```

如已有 `AGENTS.md`，应审查后添加本项目段落，不覆盖全文件，也不更改用户全局 Codex 配置。

### 24.4 最终交付必须包含

- [ ] 实际可运行的源码，而非只有函数占位符。
- [ ] 精确依赖与上游 lock；全部导入文件 provenance。
- [ ] 无网络、无 API key 的端到端 Synthetic Demo。
- [ ] 覆盖时间、scope、状态归属、干预分叉、评分边界的单元/Golden 测试。
- [ ] 真实候选审计包；人工未审核项明确标记。
- [ ] 实际执行过的模型配置、请求日志与结果；未执行不能伪造。
- [ ] README 从干净环境复现的步骤。
- [ ] 数据卡、评分定义、已知限制、许可清单和预算报告。
- [ ] `docs/HANDOFF.md`：已实现/已测试/未完成/外部阻塞/下一步，全部对应实际文件。

### 24.5 不合格交付

```text
只写 README，没有端到端路径
只让 Mock 根据 Gold 输出完美答案
时间不明仍宣称 Strict Release-time
用有效时间或文件名代替已核查发布时间
运行环境读 Gold 并修正模型状态
干预后仍使用 base Gold
模型调用失败就把结果删出分母
以重复港口/干预样本冒充独立 storm
把文章中的示例模型得分写成本项目实验结果
把最初方案的伪代码当成已测试生产代码
```

---

## 25. 来源与边界说明

### 25.1 用户材料

**[F01]《极端事件Benchmark 2026年9月3日(2).pdf》**，51 页，用户上传的综述展示材料。用于继承研究问题与评测原则，不把其中所有具体数值直接作为本项目实验结果。

与本执行计划直接相关的位置：

- 第 21 页：Obshazard 的独立时间点 VQA 与持续状态维护之间的区别。
- 第 35–36 页：DORA 的长异构工具链错误、数据 manifest 和 as-of-time 边界。
- 第 43 页：EarthVerse 的可执行 Ground Truth、审核与来源/时间/空间匹配。
- 第 46 页：固定历史事件包与逐步发布时间之间的区别。
- 第 49–51 页：ResearchClawBench 强调完成科学核心、可审计产物，而非报告外观。

这些内容指导本计划采用“小型可审计协议层”，而不是在首轮复现完整大型工具平台。F01 是用户综述材料，不替代论文原文与真实代码版本。

### 25.2 公开资源

本次公开资料核查日期：2026-09-05。网页存在、README 描述能力与在目标环境成功运行是不同状态。Codex 在 M02/M07 中必须完成安装/路径/能力层面的实际验证。

| 编号 | 资源 | 本计划使用范围 |
|---|---|---|
| S01 | [CyPortQA 仓库](https://github.com/ChenchenMobility/MLLM-Bench-CyPortQA)；[论文](https://arxiv.org/abs/2508.15846) | 核心候选图文数据、场景/模板、模型请求编码参考 |
| S02 | [Maritime-Data-CyPort](https://github.com/ChenchenMobility/Maritime-Data-CyPort) | 港口/气旋交互、稳定实体、Private outcome 候选 |
| S03 | [EarthVerse 仓库](https://github.com/CuiZHIQ/Earth-Verse)；[LICENSE](https://github.com/CuiZHIQ/Earth-Verse/blob/main/LICENSE.md) | validator/report/run logging 的设计参考；实施前核查每类许可 |
| S04 | [NHC 数据档案入口](https://www.nhc.noaa.gov/data/)；[NHC 历年归档入口](https://www.nhc.noaa.gov/archive/) | 回查官方原始产品；具体事件页面和下载可用性仍须执行时审计 |
| S05 | [NHC Cone 定义](https://www.nhc.noaa.gov/aboutcone.shtml)；[NWS Hurricane Preparedness](https://www.weather.gov/mhx/hurricaneprep) | Cone 不是完整风暴大小或全部影响范围 |
| S06 | [TGMS 仓库](https://github.com/zxf-work/tgms) | 双时态、trace 和依赖检查；首轮不引入完整后端 |
| S07 | [AutoSciRub 仓库](https://github.com/zjunlp/AutoSciRub) | 离线标准草拟与逐项审核思想；不自动安装 |
| S08 | [Can Agent Memory Systems Track Evolving State?](https://arxiv.org/abs/2608.19652) | 强状态维护 baseline 与 novelty 边界 |
| S09 | [STALE](https://arxiv.org/abs/2605.06527) | State resolution、旧前提抵抗与下游使用诊断 |
| S10 | [Calibrating Criterion Revision in LLM Agents](https://arxiv.org/abs/2608.20729) | 状态提交归属和 trace-anchored 测量原则 |
| S11 | [Codex：Custom instructions with AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md) | 短项目指令与详细执行文档分离 |
| S12 | [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs) | 后端能力检查、Schema 输出与结构/事实正确性区分 |
| S13 | [Pydantic Strict Mode](https://docs.pydantic.dev/latest/concepts/strict_mode/) | JSON/Python 严格验证的差异及测试 |
| S14 | [ExtremeWeatherBench](https://github.com/brightbandtech/ExtremeWeatherBench) | 后期事件 registry 与边缘案例组织参考；非 MVP 必需依赖 |

说明：本次读取部分 NHC 事件/GIS 页面未成功，因此本文不宣称已取得 Ian 的完整官方版本链、所有 GIS 或港口公告。具体可用性和精确发布时间是 M02/M03 的交付项。此前对仓库小文件的读取也不能替代这一步。

### 25.3 研究贡献表述

本计划实现的贡献候选是：

```text
Release-time multimodal event replay
+ Model-conditioned state revision evaluation
+ Evidence-arrival intervention with grounded downstream checks
```

Model-owned commit、Hidden Probes、RevisionGuard 和视觉子集服务于这一主线。它们并不自动分别构成全新研究贡献，也不自动证明物理因果识别、内部信念改变、实时部署安全或最优灾害决策。

不声称 first dynamic benchmark、first memory benchmark 或 first revision benchmark。最终 novelty 要依据真实实现、实验与投稿时相关工作核验，而不是依靠计划中的命名。

---

## 附录 A：可直接粘贴给 Codex 的启动指令

```text
请读取仓库根目录的 DisasterTrace_CODEX_IMPLEMENTATION_PLAN.md，
按第 20 节的 M00–M11 执行，不要只重新生成研究计划。

先检查现有仓库、AGENTS.md 和未提交修改，再建立 IMPLEMENTATION_STATUS.md。
优先完成 Schema、Synthetic Fixture、Replay、Commit Store、离线 Evaluator
和 Mock 端到端闭环。随后在许可范围内审计上游真实数据。

严格执行第 2–3 节的评测边界：
发布时间不等于生效时间；Runtime 不读私有 Gold；
模型语义错误应真实保存；干预分支重新生成可断言参考；
相同证据主对照；不同模型/港口/分支隔离；Resume 不删除历史。

默认不调用真实付费模型、不下载模型权重、不发布文件或推送仓库。
遇到真实发布时间、港口范围或人工审核不明确的记录，隔离并列出待确认项，
但继续完成可独立进行的离线工程。

每完成一个里程碑运行对应测试，保存实际命令与结果，更新状态文档。
不得把 Mock 结果当真实实验；不得为制造模型失败修改 Gold 或正式测试集。
结束时交付可运行文件、测试结果、实际产物路径、阻塞项和下一里程碑。
```

## 附录 B：第一轮推荐停止点

第一轮不是必须一口气跑完整真实 Benchmark。推荐先得到：

```text
Schema + Synthetic Fixture
Replay + SQLite Commit Store
可复算的状态/修订/证据评分
3 个基础 Baseline 的 Mock E2E
Delay / Null 两种干预和相同前缀分支
最少一个 Own/No/Oracle/Stale Probe
Ian 真实数据审计清单
```

在这个停止点，应能区分“协议已经正确实现”和“真实数据/模型实验还未完成”。只有在真实数据审核与费用授权就绪后，才进入 M11 的真实模型实验。

<!-- Portable source reference definitions -->
[S01]: https://github.com/ChenchenMobility/MLLM-Bench-CyPortQA
[S02]: https://github.com/ChenchenMobility/Maritime-Data-CyPort
[S03]: https://github.com/CuiZHIQ/Earth-Verse
[S04]: https://www.nhc.noaa.gov/data/
[S05]: https://www.nhc.noaa.gov/aboutcone.shtml
[S06]: https://github.com/zxf-work/tgms
[S07]: https://github.com/zjunlp/AutoSciRub
[S08]: https://arxiv.org/abs/2608.19652
[S09]: https://arxiv.org/abs/2605.06527
[S10]: https://arxiv.org/abs/2608.20729
[S11]: https://learn.chatgpt.com/docs/agent-configuration/agents-md
[S12]: https://developers.openai.com/api/docs/guides/structured-outputs
[S13]: https://docs.pydantic.dev/latest/concepts/strict_mode/
[S14]: https://github.com/brightbandtech/ExtremeWeatherBench
