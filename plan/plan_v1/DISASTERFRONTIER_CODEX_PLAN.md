# DisasterFrontier：可供 Codex 执行的端到端实施计划

> **文档角色：执行规格，不是已完成实现。** 以当前 `disasterfrontier_starter` 为起点，交付可复现的真实灾害证据压力测试系统。
>
> **版本：** 1.0 · **编写及 starter 核对日期：** 2026-09-05。
>
> **执行入口：** 先读第 0–3 节，再按第 13 节的 PR-00 → PR-11 推进。第 4–12 节是实现时必须遵守的数据、算法和评测契约。无需访问此前聊天或 Notion 才能理解本计划。
>
> **范围说明：** 本文保留前序讨论的 DisasterTrace 数据底座、DisasterFrontier 证据空间、Canonical Core、Adaptive Stress Track 和 FrontierSearch-Lite。第 2 节与第 15 节明确标出本次检查 starter 后新增的修复和语义澄清；它们不是已实现功能，也不是新的论文贡献。

---

## 0. 给 Codex 的执行指令

### 0.1 目标与工作方式

你是本项目的实施工程师。任务是**修改代码、运行测试、生成可复现产物**，而不是再次输出一份概念方案。优先在现有 starter 上增量改造；除非发现明确的接口障碍，不另起一个功能重复的项目。

开始时读取当前工作目录及其父目录适用的 `AGENTS.md`。若本计划配套的 `AGENTS.md` 与已有文件冲突，合并项目特定条款，不覆盖用户原来的指令。本计划不是提高任何执行权限的授权。

执行规则：

1. 先盘点仓库、工作区修改、Python 环境、现有测试和数据；不能把计划中出现的类、CLI 或目录误认为已经存在。
2. 在动代码前创建 `docs/IMPLEMENTATION_STATUS.md`，记录本次起点、阶段状态、已运行命令和下一步。
3. 对第 2 节的真实缺陷先加失败回归测试，再修复；不要通过删除断言、扩大容差或伪造预期结果让测试变绿。
4. 一次完成一个可验收里程碑。正常情况下验收通过后继续下一阶段，不反复询问“是否继续”。
5. 无 API key、GPU 或真实数据时，继续完成不依赖它们的离线代码、合成 fixture、FakeTransport 测试、数据解析器与 dry-run；把外部步骤标为 `BLOCKED`，不要假装运行。
6. 每次停止或上下文切换前更新 Progress、Surprises & Discoveries、Decision Log、Outcomes & Retrospective，方便下一次仅凭仓库恢复执行。
7. 所有完成声明附实际命令、退出码及产物路径。测试通过不等于真实实验成立，mock 曲线不等于论文结果。
8. 本计划中每个 PR 是工作切片，不是自动 push、开远程 PR 或发布数据的授权。

### 0.2 权限、预算与安全边界

默认运行模式为 `offline`：不调用付费模型，不下载大模型权重，不启动 GPU 服务，不发送真实业务通知。已有外部配置中的 API key 不能被打印、提交或复制到文档。

可在环境允许时安装项目虚拟环境内的依赖、获取公开文档和执行已明确限定范围的小型源数据下载；所有网络读取遵守平台权限。单次下载上限、总下载上限、允许域名和超时必须可配置。大规模数据或模型权重下载需要用户明确授权。

真实模型运行必须同时满足：

- 用户已经明确授权这次模型实验；
- 显式配置 provider/model，不使用代码中的 `latest` 默认模型；
- 有 `--allow-model-calls`；
- `BudgetConfig` 的逻辑查询、物理请求、token、时间和费用限制已经设置；
- 费用受限的运行已配置价格或保守成本估计；无法估算时 fail closed。

不要修改 SSH、Tailscale、全局 `CODEX_HOME`、系统 Node/Python、平台启停脚本、用户 Git 配置或云端账号。所有新增内容限制在用户指定工作区和获准缓存目录内。

### 0.3 启动时的最短行动清单

在 starter 解压后的项目根目录运行：

```bash
pwd
git status --short  # 仅当当前目录属于 Git 仓库；否则记录 not-a-git-repo
python --version
python -m pytest -q
```

若依赖缺失，在项目虚拟环境内安装，不修改系统环境：

```bash
python3.11 -m venv .venv  # 无 3.11 时使用可用的 >=3.11 解释器，并记录版本
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m pytest -q
```

以上是 starter 已有命令。后续 `disasterfrontier ...` 是本计划要求新增的 CLI；在实现前不能声称这些命令已经可运行。

默认下一步：**PR-00 复核 → PR-01 数据契约与基础缺陷 → PR-02 版本/Policy/合法性 → PR-03 防泄漏输入 → PR-04 离线运行时。** 先让一个合成样本正确运行，再接入真实数据。

---

## 1. Purpose / Big Picture：最终要交付什么

### 1.1 研究问题

给定同一场气旋与目标港口的一组真实文本、地图和业务公告，改变其中**允许改变的信息可见性、版本或呈现顺序**，观察模型何时从 `monitor` 变成 `prepare`，以及何时出现不应发生的决策变化。

不是再生成大量独立 QA，而是建立一个有限证据空间，寻找：

- 模型升级行动所依赖的最小证据组合；
- 旧版本、无关证据或缺失模态造成的可复现错误；
- 相同规范有效信息下的顺序敏感性和不合理行动残留；
- 在固定查询预算下，比随机测试更高效的反例发现策略。

**DisasterTrace** 是数据底座的名称；**DisasterFrontier** 是本仓库和研究系统的名称。不要继续改名或增加第四套研究框架。

这里的 decision frontier 是：合法探测图中，相邻探测的**模型行动发生变化**的边。行动发生变化本身不等于出错，必须另外通过 Policy Oracle 或有效的性质约束判断。

### 1.2 两条主评价线

| 评价线 | 输入是否对所有模型相同 | 用途 | 不能据此声称什么 |
|---|---|---|---|
| Canonical Core | 相同的冻结 probe/pair/sequence 集 | 公平比较模型与系统配置 | 不能因为模型专用难题少就判它更好 |
| Adaptive Stress Track | 按已观察输出选择下一次 probe | 比较搜索效率、压缩反例、分析模型失败条件 | 自适应发现比例不是自然场景总体错误率 |

### 1.3 最小可运行产物

仓库最终应支持：

```text
原始文件 + 来源清单
    → 带版本的证据单元
    → Episode + 公共 Policy Card + 私有标注
    → 合法 Probe / Pair / Sequence
    → 防答案泄漏的 ModelView
    → Mock 或真实多模态模型
    → 原始响应 + 结构化决策 + 预算日志
    → 独立 scorer
    → 固定评测报告 / 搜索发现曲线 / 最小反例包
```

在没有真实模型访问权限时，也应能够运行完整离线 E2E，输出带 `synthetic=true` 和 `model_kind=mock` 的报告，并可检测预先植入的错误。

### 1.4 冻结的 MVP 范围

**必须做：** 合法证据状态、Artifact/Atom 分离、版本解析、时间来源、显式 Policy、模型/Gold 隔离、固定探测、受预算约束的模型运行、缓存、性质评估、Random/BFS/FrontierSearch-Lite、配对反例压缩、序列测试、真实数据接入接口。

**真实数据试运行目标：** 先 2 个 episode；校准集扩至来自 4 个独立 storm 的 4 个 episode，每个约 6 个可操控单元；随后 8 个额外独立 storm 的主试验 episode，每个约 8–12 个单元。该规模是工程目标，不保证可从现成文件自动获得。

**暂不做：** 复现 AFDBench GRPO、训练视觉 backbone、所有 117k QA 全量迁移、多灾种大一统、图数据库、大型 Agent 编排平台、在线商业港口决策、复杂贝叶斯优化、自演化修改正式评测器。

### 1.5 术语

| 术语 | 在本项目中的可执行定义 |
|---|---|
| Artifact | 一份不可修改的原始 advisory、地图、表格或公告 |
| Evidence Unit / Atom | 可被提供或暂不提供给模型的输入单元；首版优先整份文件，后续才使用有精确 selector 的片段 |
| Episode | 一个 storm、一个港口/目标、一个决策问题和相应证据集合 |
| Probe | 在指定决策时刻，给模型的一次输入状态 |
| Pair | 两个由合法 transformation 关联的 probe |
| Sequence | 同一系统按步接收证据、产生响应并携带自身状态的轨迹 |
| Public View | 被测模型可见的输入；不包含 Gold、预期行动或性质标签 |
| Oracle | 只由评测器使用的规则/标注，用于确定可检验的预期结果 |
| Counterexample | 经合法性和统计复核后，违反指定性质的输入或输入对 |
| 1-minimal | 在当前允许的一步删除变换下，不能再缩小且保留同一失败；不等于全局最小 |

---

## 2. Context and Orientation：starter 实际状态与修复清单

### 2.1 本次已核验的基础事实

输入归档：`disasterfrontier_starter.zip` 与 `.tar.gz`。本次比较确认两种归档的 32 个文件内容一致。

ZIP SHA-256：

```text
a536368804a55cd06ccc6b3872103dedc504b89535febf48634d805c42e7e681
```

当前 package 为 `disasterfrontier`，`pyproject.toml` 要求 Python >=3.11，已有命令为 `disasterfrontier-demo`。主要模块如下：

| 已有路径 | 当前作用 | 使用方式 |
|---|---|---|
| `src/disasterfrontier/schemas.py` | Episode/Atom/Probe/Sequence/Decision/Policy 的 Pydantic 类型 | 增量迁移，不当作最终数据契约 |
| `lattice/validator.py` | 时间、依赖、直接版本冲突检查 | 必须先修正版本和严格校验 |
| `probes/canonical.py` | Anchor、穷举子集、一原子邻居 | 修正同版多原子、完整身份和约束邻居 |
| `search/frontier.py` | 同步边界扩展、单 probe greedy shrink | 仅 baseline 原型，不是完整搜索算法 |
| `policy.py` | 条件匹配和规则优先级 | 增加三值逻辑、状态有效性和显式缺失分支 |
| `eval/properties.py` | 简化的 pairwise 性质 | 必须增加适用条件和完整 pair 记录 |
| `eval/sequence_properties.py` | 简化最终状态比较 | 没有真实序列模型运行器 |
| `runtime/cache.py` | 最小 SQLite get/put | 未接入完整预算、请求、重复采样和恢复流程 |
| `runners/inspect_adapter.py` | 可选 Inspect API 调用 | 本次未安装 Inspect、未运行真实模型，不能标为已验收 |
| `runners/mock_model.py` | 手工 `claim_effects` 加总的 demo | 仅合成基础设施测试，禁止用于真实 Gold |
| `ingest/profile_json.py`、`tools/profile_cyportqa.py` | JSON 路径 profiler | 可复用，但尚无 CyPortQA 正式 importer |
| `data/episodes/demo_storm_alpha_port_blue.yaml` | 7 atoms 的合成示例 | 保留为 legacy fixture，不作为真实论文样本 |

本次实际执行：

```text
Python 3.13.5
python -m pytest -q
6 passed in 0.13s

PYTHONPATH=src python -m disasterfrontier.runners.local_demo \
  --episode data/episodes/demo_storm_alpha_port_blue.yaml --budget 24

输出：24 probes、16 frontier edges、0 violations。
```

**上述数字只证明 mock demo 可运行，不证明任何真实模型性质。** 本次没有运行真实模型 API、CyPortQA 迁移、NHC 下载或 GIS 管线。复核环境及源文件哈希见配套 `STARTER_AUDIT.json`；它不是目标服务器的环境锁。

### 2.2 本次新增的 P0 修复要求

下面是对现有实现的核对，不是前轮方案已经完成的功能。标为“复现”的问题已在未修改代码的本次环境中执行得到；“代码审阅”项仍需 Codex 写失败测试验证。

| ID | 路径/符号 | 实际问题 | 要求 |
|---|---|---|---|
| B01 | `Probe.validate_order()` | **复现：** `visible=[a,b]`、`order=[a,b,b]` 被接受，因为只比较 set | 检查长度、重复和一一对应 |
| B02 | 各时间 validator | **复现：** 无时区 datetime 被静默当作 UTC | 真实数据禁止静默补时区；转换时记录来源时区和转换依据 |
| B03 | `policy._condition_matches()` | **复现：** `status=retracted,value=true` 仍可通过 `eq` 并触发 restrict | 除专门历史查询外，仅 active 且有效的 claim 可参与业务条件 |
| B04 | `canonical_active_atoms()` | **复现：** v1→v2→v3 链中只显示 v1、v3，v1 仍被当作 active | 通过完整 manifest 的传递版本关系判定，不能只找直接父版本 |
| B05 | `_latest_versions()` | **复现：** 同一 artifact 版本含多个 atoms 时只保留一个 | 先解析 artifact 版本，再保留该版本全部被选中 atoms |
| B06 | `ACTION_RANK` | request_evidence 被赋 -1，混入行动轻重比较 | abstention 没有 severity rank；单独报告 |
| B07 | `InspectModelAdapter.decide()` | 代码审阅：没有发送 Policy Card；逐 atom 读取整个文件；可能重复注入未选择片段；缺文件时静默空文本回退 | 改为允许字段的 ModelView + 唯一 RenderedInput；缺文件 fail closed |
| B08 | `FrontierSearch.state_key()` | 代码审阅：只按排序后的 atom IDs 去重，丢掉顺序/呈现/状态条件 | 静态语义身份、实际输入身份、序列身份分开 |
| B09 | `_Candidate` 有界队列 | 代码审阅：负优先级 min-heap 超限时 `heappop` 删除的是最优项 | 编写容量=1 的回归测试；保留最高 acquisition 候选 |
| B10 | `shrink_visible_set()` | 代码审阅：无预算且只缩单 probe，不能保持 pair 的性质前提 | 所有请求走 BudgetedQuery；pair-preserving shrink |
| B11 | `stale_version_override()` | 代码审阅：只要引用旧版就判失败 | 区分历史对比引用与旧版作为当前支持；后者才可能构成污染 |
| B12 | `compare_neighbor_pair()` | 代码审阅：靠 atom polarity 推导单调性，未核实版本、变量、有效时段和政策 | 引入 PropertySpec 与 applicability certificate |
| B13 | `order_dependence()` | 代码审阅：只验证最终可见 ID set 相同 | 还要匹配最终时间、规范有效 claim、政策状态、资源条件与任务 |
| B14 | `probe_hash()` / cache | 代码审阅：未建立完整模型请求指纹和独立重复采样身份 | 模型/配置/schema/字节/历史/replicate_id 全部入请求键 |
| B15 | `mock_model.py` | demo 将作者写的 effect 相加得到风险 | 明确隔离为 synthetic-only；真实 Gold 不能沿用 |

优先修 B01/B03/B04/B05/B06/B07，然后做搜索和统计。不能把“现有 6 个测试全部通过”当作这些问题不存在的证据。

### 2.3 兼容与迁移

保留原 demo 原始文件和一份原始测试运行记录。新 schema 加 `schema_version: '2.0'`；提供迁移器，把旧样本转成明确标记的 synthetic-only fixture。不要让旧样本通过补默认值变成“真实、已审核”样本。

`schemas.py` 可以作为过渡 re-export facade；新类型放入 `contracts/`。不要同时创建冲突的 `schemas.py` 与同名 `schemas/` package。旧 imports 的退役需有迁移测试和 README 说明。

---

## 3. 开源复用策略与来源边界

### 3.1 资源选择

| 来源 | 复用内容 | 不复用/不假定 | 优先级 |
|---|---|---|---|
| CyPortQA [S01] | 原始文件、storm–port 索引、template 与模态读入思路 | 不继承独立 QA runner 作为正式实验；不把所有生成答案当 Gold | 必选 |
| NHC 官方 archive / GIS [S02] | 原始产品、版本、产品说明、GIS 校验 | 不把事后 best track 当早期输入；不猜真实公开时刻 | 必选 |
| Inspect AI [S03–S04] | 多模态模型适配、structured output、可选任务日志 | 不依赖未经验证的开发版 API；不假定 provider 全支持 strict | 必选适配，延后真实调用 |
| Hypothesis [S05] | 纯程序 property-based tests、有限离线表上的生成/缩减 | 不允许它绕过预算无限调用云模型 | 必选开发依赖 |
| STATE-Bench [S06] | StateDiff、任务/规则/结果隔离的设计 | 与 StateMemBench 是不同项目；不混用引用和 baseline 名称 | 参考，不作为硬依赖 |
| WorldMemArena [S07] | 选择性参考 memory adapter | 不整合全部系统、不自动下载完整数据 | P2 |
| Tropycal [S08] | storm ID 对齐、候选事件浏览 | 不把便利绘图或近似产品当官方视觉 Gold | P2 |
| AFDBench [S09] | narrative-first 对照的任务启发 | 未复现训练/权重不得称 AFDBench 官方 baseline | P2 |
| Codex 官方指南 [S10–S11] | 项目级 AGENTS 指令与持续更新的执行计划组织 | 不自动改变用户全局 agent 配置 | 文档参考 |

CyPortQA 仓库公开列出原始产品、scenario metadata、templates 和模型脚本 [S01]。以下路径沿用已经看到的仓库结构，但 PR-00/PR-08 仍须在固定 commit 上检查大小写与存在性：

```text
source_data/Encoded_senario.json
source_data/CyPortQA_template.json
source_data/NOAA NHC Cyclone Products/
source_data/Port_Condition_Bullitens/
dataset/CyPortQA.json
dataset/MultiModalInput/
models/run_qwen2_5vl.py
run.py
Requirements.txt
```

仓库 README 的命令或路径不一定与实际文件一致，执行时以 checkout 的文件为准。仅阅读需要的 importer/输入组装部分，不运行上游未审查的脚本。

### 3.2 来源锁定

新增 `configs/sources.lock.yaml`：

```yaml
schema_version: '1.0'
sources:
  cyportqa:
    repository: 'https://github.com/ChenchenMobility/MLLM-Bench-CyPortQA.git'
    commit: null
    local_root: null
    verified_at: null
    license_record: null
    status: unverified
```

`null` 是待执行状态，不是可用于正式运行的默认。获得完整 commit SHA、文件清单、许可证记录之后才置 `verified`。不要把网页上的单个 blob SHA 冒充 repository commit。

每次 vendoring 保留 LICENSE 和来源说明。代码许可证不能自动代替每类第三方数据的再分发授权；`THIRD_PARTY_NOTICES.md` 与 `docs/DATA_LICENSES.md` 分开维护。

### 3.3 依赖管理

第一步保留 starter 已有依赖，只增加当前阶段确实使用的包。核心不导入 Inspect/GIS，保证离线测试在无这些可选包时可运行。

建议 optional groups：

```text
core：pydantic / PyYAML / orjson / typer / rich / networkx
io：httpx / pyarrow / duckdb（在实际使用时添加）
eval：inspect-ai
geo：geopandas / shapely / pyproj / rasterio / pillow
dev：pytest / pytest-cov / ruff / mypy / hypothesis
```

PR-00 记录当前版本；PR-04 对 Inspect 做独立 compatibility smoke；固定通过测试的版本到仓库锁文件。不得仅因前文写过 `inspect-ai>=0.3.70` 就假定其支持 `materialize_media` 等 API。官方文档目前展示 structured schema 与运行期 media materialization，但仍需核对实际安装版本 [S03–S04]。

---

## 4. 目标目录与依赖方向

```text
DisasterFrontier/
├── AGENTS.md
├── DISASTERFRONTIER_CODEX_PLAN.md
├── pyproject.toml
├── README.md
├── configs/
│   ├── sources.lock.yaml
│   ├── models.example.yaml
│   ├── budgets/offline.yaml
│   ├── budgets/live.example.yaml
│   ├── policies/
│   ├── splits.synthetic.yaml
│   ├── splits.real.yaml
│   └── runs/
├── docs/
│   ├── IMPLEMENTATION_STATUS.md
│   ├── STARTER_AUDIT.md
│   ├── DATA_CONTRACT.md
│   ├── PROPERTY_DEFINITIONS.md
│   ├── DATA_LICENSES.md
│   ├── REAL_DATA_REVIEW.md
│   ├── RUNBOOK.md
│   └── DECISIONS.md
├── data/
│   ├── raw/                 # 不可变；默认不提交大文件
│   ├── manifests/
│   ├── rendered/
│   ├── episodes/public/
│   ├── annotations/private/
│   └── probes/
├── src/disasterfrontier/
│   ├── cli.py
│   ├── schemas.py          # 兼容 facade
│   ├── contracts/          # 公共模型契约；不得 import private annotations
│   ├── annotations/        # 私有 Gold 类型及 resolver
│   ├── ingest/
│   ├── geo/
│   ├── lattice/
│   ├── probes/
│   ├── policy.py
│   ├── rendering/
│   ├── runners/
│   ├── runtime/
│   ├── eval/
│   ├── search/
│   └── analysis/
├── tests/
│   ├── fixtures/synthetic/
│   ├── fixtures/source_samples/
│   ├── unit/
│   ├── integration/
│   ├── regression/
│   └── e2e/
└── outputs/                # ignored；不作为下一轮模型输入
```

**硬边界：** `runners/` 只能接收 `ModelView`，不能接收完整 EpisodeAnnotations。`search/` 可以使用公开的变换约束和训练/开发时允许的性质定义，但不能读取未查询模型输出或正式测试的私有最小答案集。

Gold 解析器、mock oracle 和被测模型适配器分开，不共享“从 effect 加总答案”的函数作为现实正确性证明。

---

## 5. 数据契约：先实现，再写 importer

所有新对象使用 Pydantic，`extra='forbid'`；真实数据采用严格类型验证。JSON/YAML 往返、稳定序列化和哈希必须有测试。字段名以下述约定为基准，调整须记录到 `docs/DECISIONS.md` 并提供迁移。

### 5.1 ArtifactRecord

代表原始材料，不携带模型预期行动。

| 字段 | 类型/要求 |
|---|---|
| `artifact_id` | 稳定内部 ID |
| `source`, `product_type` | 枚举/受控字符串，区分 advisory/cone/wind_probability/bulletin/observation |
| `source_uri`, `source_revision` | 原始来源；不自动发送给模型 |
| `storm_id`, `target_ids` | 身份信息；多 storm 产品允许空/多值，不能强行唯一 |
| `path`, `media_type`, `sha256`, `size_bytes` | 相对数据根路径、真实 MIME 和校验值 |
| `issued_at` | 官方声明时间，可为 null，必须 aware datetime |
| `availability_lower`, `availability_upper` | 可验证的公开可见时间边界，可为空；单点时相等 |
| `availability_basis` | `public_archive_evidence / issuer_timestamp_proxy / inferred / unknown` |
| `availability_evidence_ref` | 证明时间边界的源文件或记录 |
| `valid_from`, `valid_to`, `effective_at` | 描述的物理时间区间与业务生效时刻 |
| `retrieved_at` | 本项目抓取时间，不能替代历史可见时刻 |
| `series_id`, `revision_id` | 一条产品版本链与此版本 ID |
| `supersedes_artifact_ids` | 可多值的明确版本边；不得形成环 |
| `review_status` | `unreviewed / auto_checked / human_reviewed / rejected` |
| `synthetic`, `license_id` | 合成标记和授权信息 |

时间语义：`valid_from > as_of` 对预报是合法的；禁止用有效时间过滤掉真正已发布的未来预测。若声明发布时间与实际可见证据冲突，记录并隔离，不静默修正为想要的顺序。

`public_verified` 运行使用 `availability_upper <= as_of` 的保守准入；只有 issuance 时间的样本使用明确标注的 `issuer_timestamp_proxy` 模式，不能称精确复原公众可见性。由某个发布时间推定另一张图同时发布，不够作为 Grade A 证据。

### 5.2 EvidenceUnit 与私有 EvidenceAnnotation

公共单元：

```yaml
unit_id: u_002
artifact_id: a_002
modality: image
source_kind: forecast
selector:
  kind: full_file
required_context_unit_ids: []
public_metadata:
  product_label: 'Forecast map'
```

`modality` 只描述输入形式：`text / image / table / structured`。`observation / forecast / operational` 是来源语义，放 `source_kind`，不继续混进模态 enum。

selector 类型：

- `full_file`：MVP 默认，一个输入单元就是一份完整文件；
- `text_span`：以 UTF-8 解码后的 Unicode 字符 offsets `[start,end)` 选择，记录规范化文本哈希；
- `image_region`：明确 bbox 或 polygon、像素/规范坐标系、图像尺寸与渲染规则；
- `table_cells`、`json_pointer`：仅在有明确 extractor 时启用。

私有标注另存：

```yaml
unit_id: u_002
supported_claim_keys: []
refuted_claim_keys: []
redundancy_groups: []
expected_region_geometry_ref: null
support_role: null
review_status: unreviewed
```

**绝不能发送给模型：** `claim_effects`、polarity/strength、预期 action、oracle_minimal_set、property failure type、人工答案、未选择单元的文字或图像。模型前的 ID 使用无语义 opaque ID，不使用 `warning_expansion_high_risk` 这类泄漏结论的名字。

MVP 优先整文件单元，避免虚假的 atom withholding：如果隐藏一句话但 renderer 又把含该句的完整文档发送给模型，这个 probe 无效。

### 5.3 ClaimKey、ClaimResult 与证据关系

一个 claim 需要明确其对象、属性、单位和有效时段，避免把不同地方/时间的数值互相比较。

```text
ClaimKey = (subject_id, attribute, valid_from, valid_to, unit)
```

`ClaimResult` 至少含：`claim_key`、`value`、`status`、`confidence`、`evidence_refs`。`status` 取 `active / unknown / retracted / superseded`。`unknown` 必须 `value=null`；撤回/旧版 claim 可保留历史值，但禁止直接作为当前 Policy 条件。

每条 `EvidenceRef` 含 `display_unit_id`、可选 selector，以及 `role=current_support / historical_comparison / refutation`。允许引用旧版本解释“发生了什么变化”；不能仅因旧 ID 出现在引用列表里就判 stale override。

`confidence` 是模型自报信心，不是自动校准概率。`risk_score` 若保留，必须有 `risk_target`，明确事件、地点、时间窗；未定义时为 null，不与其他模型的任意风险数值直接排名。

### 5.4 PublicEpisode / EpisodeAnnotations

公共：`schema_version`、`episode_id`、`storm_id`、`target`、`decision_question`、`claim_schema`、`units`、`policy_card`、`task_time_window`、`synthetic`。

私有：`artifact_annotations`、`claim_evidence_rules`、`expected_actions`、`property_specs`、`split`、`review_records`、`outcome_reference`。

模型只能收到公共内容中的**当前被选中部分**。即使完整公共 unit catalog 不含答案，也不能把未提供材料的描述列表泄漏到 `missing_evidence` 提示中。

### 5.5 PolicyCard

包含 `policy_id`、`policy_version`、`description`、`rules`、`default_on_unknown`、`stateful`、`review_status`、`policy_origin=benchmark_defined / source_derived`。

规则用枚举操作符和类型化表达式，不执行任意 Python `eval()`。支持 `all / any / not / eq / gte / lte / known / unknown`；对 unknown 实现三值逻辑，不把 unknown 当 false 后自动给 monitor。

**规则应公开给模型**；依据证据得到的真实状态值只留给 evaluator。Policy 正确执行和证据正确理解是两个不同分数。

### 5.6 Probe、ProbePair 与规范身份

`Probe` 字段：

```text
probe_id、episode_id、as_of、visible_unit_ids、presentation_order、
view_mode、transform_spec、policy_version、render_version、
public_context、previous_commit_ref（仅序列/状态审计）
```

- `presentation_order` 严格是 visible IDs 的一个排列，没有重复、没有遗漏。
- `visible` 可以包含旧版与新版；`canonical_active` 由评测器推导，不能默认告诉模型哪份有效。
- `view_mode=static_snapshot / full_history / latest_filtered / stateful_delta` 必须记录，不能混合统计。
- 相同 evidence set、不同顺序或不同历史，不是同一个模型输入。

`ProbePair` 字段：`pair_id`、`left_probe_id`、`right_probe_id`、`transformation`、`protected_unit_ids`、`applicability_certificate`。

三种 key：

```text
semantic_state_key：相同规范当前信息的聚类，用于分析，不用于直接缓存模型请求。
input_fingerprint：实际输入字节、顺序、schema、政策、历史、模型配置的哈希。
query_key：input_fingerprint + replicate_id + sample_nonce/seed + provider/model revision。
```

`probe_id`、parent ID、搜索优先级等非语义元数据不应无谓破坏缓存复用；但 transform 影响到实际像素/文本时必须反映到字节指纹。

### 5.7 SequenceProbe

每步明确定义：`step_id`、`decision_time`、`new_delivery_ids`、`retirement_events`、`public_context`、`max_output_tokens`。保持一个 append-only delivery log 和规范有效信息视图。

同一序列内按真实步骤串行，不跨步并发；不同序列可以并发。

必须区分三种操作：

| 操作 | 含义 | 可否假定模型忘记以前看到的内容 |
|---|---|---|
| withheld_before_delivery | 从未给过 | 可以不掌握这条信息 |
| source_retraction / supersession | 已给过，但后来正式撤回/替换 | 旧事实不应继续作为当前有效事实；历史仍可保留 |
| context_eviction | 从当前上下文移出 | 不能等同于事实被反驳，属于 memory stress |

### 5.8 ModelView / RenderedInput / ModelDecision

`ModelView` 只能包含：问题、当前时间、目标信息、公共 Policy、选中 evidence 的显式内容块、允许的上一轮模型 commit、输出 schema。它是 runner 的唯一数据入口。

`RenderedInput` 含最终消息结构、media bytes/hash、输入指纹、token 估计和构建日志。构建日志中 Gold 信息不可出现在发送字段。

`ModelDecision` 保留四个 action 值以便兼容：

```text
monitor / prepare / restrict / request_evidence
```

但 ordinal rank 仅适用于前三者：`0/1/2`。`request_evidence` 用单独的 abstention 指标与政策分支检查；任何涉及 rank 的函数遇到它应返回不适用或进入专门分支，而不是 -1。

建议字段：`action`、`claims`、`evidence_refs`、`missing_information`、可选 `risk_score/risk_target`、简短 `explanation`。不要求暴露模型私有 chain-of-thought。

### 5.9 QueryResult / PropertyResult / Counterexample

`QueryResult`：`query_key`、原始响应、parsed decision、`status=ok/schema_invalid/refusal/timeout/provider_error`、usage、latency、cache mode、尝试记录、模型实际版本、replicate ID。

`PropertyResult`：`property_id`、`status=pass/fail/inapplicable/indeterminate`、pair/sequence refs、可比较量、差值、适用前提、跳过原因、复核状态。

`Counterexample`：失败性质、原始 pair/sequence、压缩后 pair/sequence、保留条件、实际查询数、独立确认结果、`minimality=unverified/greedy_reduced/1_minimal/global_minimum_in_enumerated_space`、证据及响应哈希。

---
## 6. Gold 与 Policy：真实判断不能从 demo effect 推出来

### 6.1 三个互相分离的计算层

```text
私有证据标注 + 当前真正可见内容
    → GoldClaimResolver
    → evidence-conditioned Gold claims

Gold claims + 公开 Policy Card
    → PolicyEngine
    → 预期/可接受行动

模型 claims + 同一 Policy Card
    → PolicyEngine
    → 根据模型自己状态应采取的行动
```

三者用于分别计算：证据理解错误、规则执行错误、以及端到端行动错误。不要让一个模型在证据理解错误但恰巧输出正确 action 时拿到完整通过。

真实 claim 的依据来自文档中明确事实、GIS 空间运算或经过审核的组合规则，不是模型自由编写的概率加和。`claim_effects` 仅允许存在于 `tests/fixtures/synthetic/legacy/`。

### 6.2 最小合成 fixture：一个可穷举的跨模态边界

创建 `tests/fixtures/synthetic/multimodal_boundary/`，含一份公开 episode、私有 annotations、两份文本、两个 PNG、Policy Card。所有文件标注 synthetic。

本 fixture 的决策问题：是否进入“准备”状态；不是实际港口关闭建议。

- `u_001`：文本给出某有效时段的 warning 适用于区域 R；
- `u_002`：地图给出 Port Blue 与区域 R 的空间关系；
- `u_003`：明确的同方向补充事实，不改变上述逻辑；
- `u_004`：不同目标的无关材料；
- `u_005`：同系列旧版地图；
- `u_006`：明确替代旧图的新图。

不要让文本直接写出“Port Blue 在区域 R 内”，否则视觉不是必需。PNG 含固定尺寸、图例、目标点和区域，私有 GeoJSON 提供几何真值。

该 fixture 使用的 Policy 仅取三种结果：

```text
两个前提均为 true                → prepare
至少一个前提有明确 false 证据      → monitor
其余情况                         → request_evidence
```

其中两个前提是 `warning_active_for_R` 与 `target_inside_R`。缺少一个前提时为 unknown，不推断 false。`restrict` 在另一个明确有生效公告的 fixture 中测试，不强塞进本例。

Golden truth table：

| warning | inside | 预期行动 |
|---|---|---|
| true | true | prepare |
| true | false | monitor |
| false | true/false/unknown | monitor |
| true | unknown | request_evidence |
| unknown | true/unknown | request_evidence |
| unknown | false | monitor |

这些是**本项目合成测试约定**，不是 NHC/USCG 的业务规则。

### 6.3 Policy 解释器约束

给每条规则明确优先级和冲突处理；同优先级给出互斥行动且可同时满足时，Policy 编译失败，而非依赖 YAML 顺序选择。

`not unknown = unknown`。数值类型与单位在编译时校验，不用 `float(True)` 当概率，不让字符串转换失败在模型调用后才崩溃。对已撤回、已被替换或不在有效时间范围的 claim 返回 unknown/历史状态，不参与当前阈值条件。

若一个高优先级规则为 unknown，不允许自动跳到一个隐式低风险默认；必须有明确的缺失信息策略。复杂样本允许返回 `admissible_actions` 集，并单独提供已审核的单一 `expected_action` 子集用于确定性校准。

保存 `RuleTrace`：每个前提的 true/false/unknown、最终命中规则、使用 claim。它供 scorer 审查，不发送给被测模型。

### 6.4 历史行动与未来结果

历史港口公告作为 `observed_official_action`，不冒充普遍最优策略。`benchmark_defined` Policy 的正确性仅表示“按公开规则执行正确”，不能表述为“现实中唯一安全动作”。

预报与事后观察分开：对同一地点/有效时段的预报 claim，后续 observation 可以验证结果；新版对**另一个时段**的低风险预测不能自动反驳之前的概率预测。一次未发生事件也不意味着原先非零概率预测不合理。

MVP 不强制实现全套 forecast-to-observation 子任务；保留字段和精确时间窗，后续经真实数据审核再启用。

---

## 7. 版本解析、时间门控与合法探测空间

### 7.1 版本层在 Artifact，不在单个 Atom

新增 `lattice/versioning.py`：

```python
def resolve_active_artifacts(
    delivered_artifact_ids: frozenset[str],
    manifest: ArtifactIndex,
    claim_scope: ClaimScope,
    as_of: datetime,
) -> VersionResolution:
    ...
```

实现要求：

- 构建 `supersedes` DAG，拒绝环、自引用、不存在引用和不合法跨系列覆盖。
- 利用完整链判断传递替代：v3 可使已提供的 v1 过期，即使 v2 没有提供。
- 不凭“manifest 中存在未来/未交付新版”自动将模型只看到的旧版判错；解析当前可断言状态必须条件化于实际输入。
- 同一最新版文件里的多个选中单元全部保留。
- 不同产品、变量、空间范围或有效区间不能凭较新时间戳相互覆盖。
- 两份无明确取代关系的冲突证据可作为有意构造的 conflict probe 保留；resolution 标记 conflict，不按最后呈现顺序偷偷决定真值。
- `version_index` 可作为校验线索，不能代替显式关系。特殊 advisory 或编号字符串必须保留原值。

不要向普通模型输入自动附 `active=true` 标签；`latest_filtered` baseline 明确是外部版本过滤系统，必须单独标注。

### 7.2 时间门控

静态 probe 只包含其模式允许的当时可见 artifact。序列分别保存 `issued_at`、可信可见边界与 `delivered_at`。一次通信延迟改变 `delivered_at`，不改原始产品发布时间。

所有核心时间须 aware datetime 并规范化成 UTC；原始字符串和来源时区留在 manifest。无时区且没有来源解释的记录进入 quarantine，不硬填 UTC。

对 availability 区间，保守选择 upper bound；区间跨越 checkpoint 的证据不进严格核心。来源仅提供日期时，可以表达区间，不伪造到分钟精度。

### 7.3 transformation 的精确定义

| Transformation | 修改内容 | 必须保持 | 主要限制 |
|---|---|---|---|
| add | 加入一个已可见输入单元/依赖 bundle | 原材料、时间、政策、其他内容 | 不自动将更多信息等同更高风险 |
| withhold | 在初始提供前省略一个单元 | 其他内容与初始状态 | 冗余通道仍透露信息时，不宣称“移除了该事实” |
| stale_replay | 新版已在输入中，再加旧版 | 新版、目标时间、政策 | 保留旧版原时间戳，不伪装成新版本 |
| version_swap | 将一个系列当前可用版本换成同事件获准旧版本 | 其他系列和上下文 | 属于合成通信/版本压力测试，不是假称自然回放 |
| order_swap | 调换合法独立输入顺序 | 最终决策时间、证据字节集合、政策、资源条件 | 单轮呈现顺序与多轮到达顺序分开报告 |
| source_retraction | 发送真实/明确标记的撤回或替代事件 | 历史日志 | 不能仅删除模型已看过的文件就当作撤回 |
| modality_ablation | 保留规定形式的证据 | 问题、政策、时刻 | 报告信息变化，不保证与 full 具有同样 Gold |
| span/region mask | 按指定 selector 生成掩蔽派生物 | 非目标区域、图例/坐标按协议保持 | P2；边界模式不能泄漏目标位置；保留原始字节 |

### 7.4 三层 validator

1. **SchemaValidator：** ID、类型、UTC、selector、哈希、数组唯一性。
2. **ProbeValidator：** 时间、版本关系、依赖、路径权限、渲染可用性。
3. **PairApplicabilityValidator：** 这个 pair 是否真的只修改宣称的因素，是否满足待测性质前提。

标准错误码：

```text
UNKNOWN_UNIT / DUPLICATE_ORDER / MISSING_ORDER_ITEM / NAIVE_TIMESTAMP
FUTURE_DELIVERY / UNVERIFIED_AVAILABILITY / MISSING_DEPENDENCY
VERSION_CYCLE / VERSION_SCOPE_MISMATCH / UNRESOLVED_CONFLICT
SELECTOR_OUT_OF_RANGE / MISSING_MEDIA / CHECKSUM_MISMATCH
PATH_OUTSIDE_DATA_ROOT / REDUNDANCY_LEAK / PROPERTY_NOT_APPLICABLE
SYNTHETIC_IN_REAL_SPLIT / GOLD_LEAKAGE / BUDGET_EXCEEDED
```

合法输入但性质不适用时返回 `inapplicable`，不要报成模型失败。所有被过滤候选要统计原因，不能静默丢弃以美化结果。

### 7.5 “Lattice”只作为工程简称

依赖、版本冲突、时间限制会使子集空间不满足数学格的并/交封闭性。实现采用 **legal probe graph**；不得假定所有子集合法或使用未经证明的单调剪枝。

首版穷举对 <=6 个单元的组合生成候选，再过滤，记录候选数、合法数和拒绝原因。实际 formal denominator 为合法集大小，不默认等于 64。

邻居以合法 transformation 定义。需要共同出现的地图与图例可以是一个 bundle；删除任意组成会违法时，不要一边自动加回一边称“只改一个 atom”。报告编辑单元数和编辑 bundle 数。

---

## 8. 模型输入、运行时、缓存与预算

### 8.1 PromptRenderer：先解决“真正提供了什么”

新增 `rendering/model_view.py` 和 `rendering/renderer.py`。严格构造以下顺序：

```text
固定任务说明
目标与决策时刻
公开 Policy Card（版本与文字规则）
允许的上一轮模型 commit（若为 stateful）
按 presentation_order 提供的证据内容块
输出 JSON schema 及缺失信息约定
```

内容块只含 opaque evidence ID、必要来源/发布时间/有效时间及可见内容。不发完整 Episode JSON，不发内部绝对路径、Gold 标签、support/refute 标签或 expected claim value。

整文件模式对同一 artifact 去重；片段模式只发送获准 selector 的内容及协议规定的上下文。图像必须有真实可读取文件；无文件时报 `MISSING_MEDIA`，禁止回退为“本应有一张图”的文本并仍标记 vision run。

读取路径使用 data root 下的相对路径并 resolve，阻止 `..` 与 symlink 逃逸。运行期远程媒体关闭；所有文件先由 downloader 白名单获取，再本地校验、物化。Inspect 官方文档说明运行期动态媒体须为 inline data URL，并明确媒体物化是权限行为 [S04]；因此 renderer 只对已经授权的本地 media 使用 `materialize_media`，不得对模型返回的路径/URL调用它。

### 8.2 防答案泄漏测试

创建包含以下 sentinel 的私有 annotation：

```text
PRIVATE_GOLD_SENTINEL
oracle_action_restrict
hidden_support_strength_0_93
```

渲染 prompt、结构化 schema、日志发送字段、图片 metadata 后扫描：这些字符串不得出现在模型请求中。还要测试没有 selected 的文本 span 不会因读取原始整文件而泄漏。

视觉 overlay 中只能画目标点、区域、legend、时间；禁止根据 Gold 将目标区域标成“正确答案区”或在文件名中编码 yes/no。对模型可见图片去除带答案的 EXIF/metadata。

### 8.3 统一 adapter 与 provider 能力检测

目标接口：

```python
class ModelAdapter(Protocol):
    async def generate(
        self,
        request: RenderedInput,
        generation: GenerationConfig,
    ) -> RawModelResponse:
        ...
```

实现 `FakeTransportAdapter` 和 `InspectAdapter`。所有业务路径通过 `QueryService` 统一做解析、预算、缓存和日志。adapter 本身不偷偷重试、不替模型补 Gold、不调用 policy oracle。

Inspect structured output 可使用 `GenerateConfig(response_schema=ResponseSchema(...))` 与 Pydantic JSON schema；官方同时提醒 provider 支持及 strict 行为不同，仍需校验响应 [S03]。加入启动能力检查：text、image、structured output、seed、max tokens。能力不足时报不支持或执行明确标记的 JSON-prompt fallback，不偷偷降成 text-only。

MVP 不依赖 `SampleSource` 等动态评测 API。外层 Python 搜索循环调用已测试的 Inspect model 接口；完整 Inspect Task/log 集成是可选薄封装。

### 8.4 原始响应与失败状态

保存 raw response、completion、模型返回标识、usage、解析状态。JSON 无法解析时记录 `schema_invalid`；它不等于 `request_evidence`。拒答、超时和 provider 失败也不能自动映射为低风险行动。

默认不做语义 repair。允许一个纯格式抽取选项（例如严格去掉单一 JSON code fence）时，保存原文和 `parse_mode`，不能改变值、补字段或重新询问模型后冒充一次调用。

请求连接/限流失败可重试，但每次物理请求登记在预算日志；模型给出合法但不喜欢的答案不是重试理由。

### 8.5 三种缓存模式

- `live`：未命中时实际查询，所有尝试受预算限制。
- `replay_only`：只能读取已有锁定实验表，未命中报错；用于搜索算法公平比较。
- `off`：独立随机性确认所需；仍写原始响应与预算日志。

cache key 至少包括：provider、实际 model/revision、生成配置、完整 prompt/schema、所有媒体字节哈希、Policy、as_of、顺序、历史 commit 字节、工具权限/版本（若有）、`replicate_id`。

**同一个缓存答案不是新的独立采样。** 新 replicate 必须产生新的 key 并发起独立生成，除非是在重放已独立采集的那个 replicate。

SQLite 最少拆成：

```text
requests(query_key, input_hash, model_config_hash, replicate_id, status, ...)
responses(query_key, raw_response_path, decision_json, usage_json, ...)
attempts(attempt_id, query_key, status, estimated_cost, actual_usage, ...)
experiments(experiment_id, config_hash, source_lock_hash, code_revision, ...)
search_steps(experiment_id, step_no, candidate_id, query_key, acquisition, ...)
```

使用参数化 SQL、WAL/合理 busy_timeout、单写者或短事务并发策略，支持中断恢复。无效输出可缓存其错误状态，但不得覆盖一条成功的独立采样。

### 8.6 预算是物理执行约束，不只是 for 循环长度

所有模型调用，包括 anchors、邻居查询、replicates、shrinking、LLM planner，都必须经过同一个 `BudgetedQuery`。

`BudgetConfig`：

```yaml
mode: offline
allow_model_calls: false
max_logical_queries: 128
max_provider_requests: 0
max_input_tokens: 0
max_output_tokens: 0
max_cost_usd: 0
max_wall_seconds: 120
max_concurrency: 1
max_transport_retries: 0
```

上面是默认离线配置。Mock/FakeTransport 不占 provider/token/费用预算，只计逻辑查询与墙钟；其用量不得伪装为真实 provider usage。live 示例默认仍关闭；由用户授权后写非零边界，不能在文档中填一个金额就视为授权。

预算记账区分：

| 计数 | 含义 |
|---|---|
| logical queries | 搜索算法获得多少个独立配置/replicate 输出；重放数据仍消耗该算法预算 |
| provider requests | 实际网络请求数，含重试 |
| model generations | 两阶段 narrative baseline 的两次生成均计入 |
| input/output tokens | 含图像 token 和 provider 返回的相关用量；未知不能记作零 |
| planner usage | AutoResearch planner 自身费用 |
| wall time | 包含渲染、模型等待和缩减开销 |

并发时先原子 reserve 最坏允许用量，完成后 settle。不能让并发请求同时看到余额充足而超额。未知计费/无法保守估计时停止付费路径；无损保存已完成部分。

cache hit 在真实费用上为 0，但在算法回放预算中仍消耗一次新观察。不能用共享 warm cache 给某个 search baseline 免费看完所有结果。

---

## 9. 性质定义：每一项都需要适用条件

新增 `eval/applicability.py`、`eval/single_probe.py`、`eval/pairwise.py`、`eval/sequence.py`。评估输出保留 numerator、eligible denominator、excluded count 和原因。

### 9.1 单 Probe 指标

| 指标 | 判定依据 |
|---|---|
| SchemaValidity | 原始响应能否按锁定 schema 解析 |
| CitationValidity | 引用是否实际提供，selector 是否存在 |
| EvidenceTimeLegality | renderer/输入/引用是否违反约定时间门控 |
| ClaimGrounding | 当前 value 是否由当前可用证据及标注规则支持 |
| UnknownPreservation | 未被证据解决的任务相关 claim 是否保持 unknown |
| PolicyCompliance | 模型 action 是否与其自身 claims 和公开 Policy 一致 |
| EndToEndAction | 模型 action 是否在 Gold claims 导出的允许集合内 |
| UnsupportedClosure | unknown 被不受支持地变成 true/false/具体数值 |

不能从模型“碰巧知道未来结局”直接证明训练污染；区分实际未来材料输入、非法引用、与未来结局吻合的无证据断言三种现象。

### 9.2 P01：Irrelevant-Evidence Invariance

输入对只新增一个经任务依赖检查确认不影响当前问题的单元。as_of、Policy、目标、资源、有效期不变。判断 action/任务相关 claims 是否发生不受支持变化。

新增材料含更正说明、可信度变化、全局资源约束或目标有关信息时，不适用。仅凭 `polarity=irrelevant` 标签不足以自动通过证书。

### 9.3 P02：Conditional Monotonicity

只有当同一 claim、单位、地点、有效区间、版本语义及 Policy 构成明确同向关系时才检查。Oracle 必须证明这个 edit 不应降低对应响应等级；不能假定“更多证据 → 更高风险”。

当任一响应为 `request_evidence` 时，跳过 ordinal 违规判断，另评信息充分性/abstention。Policy 有资源竞争、条件反转或合法迟滞时，不使用简单排序。

对于风险数值，只比较相同 `risk_target`；该指标为次级诊断，不把不同模型自报 risk 的差异包装成真实风险校准。

### 9.4 P03：Version Dominance

比较 `latest` 与 `latest + old`，要求同一问题所需的新版完整替代旧版，且加入旧版不会恢复新版没有覆盖的历史时段信息。

失败条件为旧版造成**错误的当前 claim/action**或作为当前唯一支持覆盖了新版；允许旧版以 `historical_comparison` 解释变更。只有输出引用字段而没有判断语义时，最多标记待审核，不能直接判错。

### 9.5 P04：Multimodal Necessity / Information Sufficiency

在同一 target/time/Policy 下比较 text-only、image-only、full、经批准的错配版本条件。Gold 由各自输入重新计算，不能沿用 full evidence 的 action 惩罚合理 unknown。

至少区分：

```text
model_minimal_trigger：什么输入让模型自己采取动作。
oracle_minimal_sufficient：什么输入在任务规则下足以支持动作。
```

前者更小不代表更好，可能是过早触发。报告二者的差异、多模态必要集覆盖与 unsupported trigger，而非单看证据数量。

若文本已经描述完整空间关系，full 与 text 无差异可能是正确的模态冗余，不是模型忽略视觉。需要使用私有 redundancy 标注检查这一点。

### 9.6 P05：Order Dependence

分为 `single_prompt_order` 与 `multi_turn_arrival` 两类，分开汇报。

严格对照要求最终目标时间、决策问题、Policy、资源状态、规范有效证据与各自版本完全相同。测试输入可以具有不同顺序，但不能让后到证据来自未来、改变了截止时刻，或者让一条路径合法地累计了不同政策状态。

报告跨顺序差异相对于“同一输入重复生成”的噪声基线。动作不变但数值略变，不一定是稳定顺序失败。

### 9.7 P06：Retraction / History Residual

`WITHHOLD` 不是 `WITHDRAW`。模型已经见过的信息，除非后来收到有效更正、撤回或版本替代，不应被要求因为当前 prompt 不再重复它就主动忘记。

在相同最终有效信息下比较有高风险历史与无该历史的路径，先计算 Policy 自己的预期迟滞。如果 Policy 规定“连续两个周期确认才降级”，模型继续准备不是立即错误。

MVP 的 matched-history 实验使用 `stateful=false` Policy 或显式匹配其必要状态。主指标是**超过 Policy 预期的残留/延迟**，不是所有 hysteresis 都有害。

`RetractionDelay` 报告真实小时和 checkpoint 数，并对截至轨迹末尾仍未降级的案例记录 right-censored，不强填一个假定延迟。

### 9.8 可选：Carrier-Isolated Commit Audit

仅作为后续诊断，不阻塞 Frontier MVP。在形成状态后的 transfer checkpoint，不重新提供可完全重建目标状态的当前证据；分别使用 Actual/Masked/Oracle/Edited commit。

如果当前证据已经足以覆盖旧状态，Edited 后 action 不变并不能证明模型没用 memory。不要把这类不适用 probe 计入失败。Oracle 干预仅供测试，不能写回主自然轨迹。

### 9.9 反例与因果表述边界

这些实验识别的是**指定输入/状态载体干预对系统可观察行为的影响**。不能仅凭输出变化声称证明神经网络内部 belief 的真实因果机制。

只有经过适用性验证的违反才称 `confirmed_counterexample`；不适用、噪声太大和 schema invalid 分别记录。作用于实际物理灾害的因果结论不在本任务范围内。

---

## 10. FrontierSearch：先建立可检验 baseline，再优化

### 10.1 搜索接口

```python
class SearchPlanner(Protocol):
    def propose(self, observation: SearchObservation) -> ProbeRequest | None:
        ...
    def observe(self, result: QueryResult, feedback: SearchFeedback) -> None:
        ...
    def dump_state(self) -> bytes:
        ...
```

`SearchObservation` 只含该算法已查询结果、允许的探测目录/约束、剩余预算和合法性反馈。禁止获得完整模型查找表、test Gold 最小集合或尚未查询的 action。

所有算法共享同一候选变换空间、同一响应表或真实模型接口、同一预算口径和同一确认标准。

### 10.2 Stage A：Exhaustive Calibration

对 4 个小 episode 枚举合法静态 probe，固定 prompt/order/model 配置。确定性 mock 可得到精确参照；真实模型是**固定采样协议下的经验参照图**，不是永恒精确边界。

保留全部查询表用于 replay-only 比较，search planner 不得直接读取表文件；由独立 `ReplayQueryService` 逐次揭示请求结果并记账。调整 acquisition 权重只能用开发 episode，不能用最终评估 episode。

### 10.3 必须实现的搜索基线

| 算法 | 具体行为 |
|---|---|
| UniformRandom | 从合法候选中不放回随机采样，固定 seed |
| CanonicalSuite | 固定序列的 anchors / leave-one-out / modality / version 对照 |
| BFS | 按声明的合法图邻居广度优先，不使用未查 action |
| FrontierSearchLite | 基于已观察局部行动分歧和性质覆盖排序 |
| Greedy/Hypothesis reduction | 对已发现失败做预算内压缩；不是可以免费看模型的独立算法 |

禁止把相同算法换名当成不同 baseline。Hypothesis 首先用于纯程序测试；作为搜索 baseline 时只通过 BudgetedQuery 或冻结响应表。

### 10.4 FrontierSearch-Lite 具体过程

**初始化。** 建立候选目录、validator、状态指纹索引、已查询集合和有界队列。anchors 包括 empty、full、合法 singleton、leave-one-out、模态子集和最新/旧版对照。通过去重与合法性检查后按固定顺序入队，记录 anchor 成本。

**查询。** 对最高 acquisition 的未观察输入调用 QueryService。错误结果保持为错误，不生成伪 action。记录 planner 状态和查询日志，保证中断可恢复。

**邻域扩展。** 根据合法 add/remove/version 对照和已观察 pair 产生候选。单纯加/删无法连接某些依赖 bundle 时，使用明确登记的 bundle edit，不偷偷跳过整块空间。

**优先级。** 初版使用固定可解释 heuristic：已观察邻居行动分歧、尚未覆盖的合法性质/模态关系、候选多样性和预估请求成本。权重仅在开发集锁定，不按每个测试模型调参。每项分值保存到 `search_steps`。

**评估。** pair 的两个端点都有输出且适用证书通过后再评价。action-change edge 与 violation edge 分开存储。低置信或噪声案例进入 confirmation queue。

**预算分配。** 一个可配置的开发默认是 60% 探索、20% 配对补齐/确认、20% 反例缩减；比例是待验证 heuristic，不是论文最优设置。所有方法总预算相同，报告实际消耗。

**停止。** 无合法未查候选、达到任一预算、墙钟超时或外部取消时停止并输出 `stop_reason` 和 partial result。不得为了凑满预算重复查相同 replicate。

### 10.5 必修的数据结构问题

- 用 `input_fingerprint → observed_result` 的索引避免逐节点线性查找。
- 语义 set key 可以用于聚类，但不能覆盖实际 presentation/history 身份。
- 队列可先使用有界有序字典/列表，别为追求 heap 复杂性保留 B09。若用负分 min-heap，容量裁剪必须移除最低价值项。
- 新观测可能改变旧候选 priority：使用 generation/version 标记惰性更新或重建队列，不能永远保留过期 acquisition。
- 排序 tie-break 使用稳定候选 hash 与本地 RNG，避免 Python set 遍历随机性。
- pair ID 规范化；有方向性质同时保存 `base → changed`，不能随字母排序逆转意义。

### 10.6 Pair-preserving Shrinker

输入不是单个失败 probe，而是 `CounterexampleCandidate`：性质、两端输入、固定 edit、适用前提。

以“加一个无关单元导致错误”为例：该新增单元必须受保护，左右两侧共同删除背景单元；否则压缩可能改变成另一个问题。

```text
候选共同背景删除
    → 重建两端（保护声明的差异）
    → schema + probe + pair applicability 验证
    → 两端输出查询（按各自 replicate 与预算）
    → 检查同一个失败谓词
    → 成功则接受并重新开始
```

对存在依赖的背景，优先删除可移除 bundle。预算不足、随机性无法确定、或必要条件破坏时停止；保存 best-so-far 并标记未完成。

最终再遍历一遍所有获准单步缩减，才能标 `1_minimal`。仅在穷举小集检验过所有更小合法候选时标 `global_minimum_in_enumerated_space`。不存在全局最小证明时禁止使用“保证最小”。

### 10.7 P2：Active Test Scientist / AutoResearch

首版先完成非 LLM search baselines。P2 planner 只能提出获准 transform DSL：`operator + unit IDs + pairing + testable hypothesis`，不能生成任意代码执行、改 Gold、修改原始材料或绕过 validator。

LLM planner 与被测模型的调用成本分别记录，同时报告总成本。比较时包含 LLM-only、heuristic-only、hybrid；只有新策略在未见 storm/episode 上稳定优于简单基线，才支持方法贡献。

不要在 MVP 引入 BoTorch、Optuna、RL 或 prompt 自演化，除非先记录一个具体瓶颈并通过另一个隔离 PR 验证收益。

---

## 11. 随机性、搜索公平性与报告

### 11.1 查询与确认协议

普通探索可单次采样；候选边界/失败先 3 次重复做筛选，但 **2/3 一致不等于统计证明**。重要论文反例使用预先配置的额外独立确认次数，并报告次数、行动频率与区间。

provider 不支持 seed 时如实记录；temperature=0 不自动等于完全可重复。复核不能命中同一 replicate cache。失败确认规则在看测试结果前锁定，不为单个好看的案例改阈值。

将 `stable / unstable / unresolved` 与 `pass/fail` 分开；对不稳定输入报告行动分布。序列每次 replicate 从干净初始状态开始，不继承上次会话。

### 11.2 搜索方法评价

在已冻结校准响应表上重放每种算法及多个 search seeds，每一次新观察均消耗逻辑预算。

| 指标 | 计算约定 |
|---|---|
| FrontierEdgeRecall@B | 在预算 B 内两端均查询到的 action-change edges / 参照图中的有效 frontier edges |
| ViolationRecall@B | 已确认唯一失败 / 参照图中同一定义的失败 |
| DiscoveryAUC | 按逻辑预算轴积分；同时提供按物理请求/token/费用轴结果 |
| QueriesToFirstFailure | 未发现则 right-censored，不记为 0 |
| CounterexampleSize | 共同背景单元数、编辑单元数和 bundle 数分开 |
| MinimalityGap | 仅有穷举最小参照时计算；否则 null |
| CrossModelTransfer | 在 A 上发现、冻结后在 B 上独立确认的反例比例 |

分母为 0 时报告 N/A，不填 100%。正式自适应主集没有完整参照，不报告“召回率 80%”，只能报告固定预算内发现数、确认率和覆盖。

去重失败至少按 episode/property/核心 edit/规范证据集合，而非按输出措辞。不同代码版本、Policy、视图模式下的结果不合并。

### 11.3 模型 Decision Fingerprint

主报告不强制一个总分，保留：政策行动正确率、unsupported trigger、任务相关 unknown、模态必要性、版本污染、顺序敏感性、超出政策预期的历史残留、撤回延迟和运行错误率。

风险标量与模型自报置信度是辅助指标。不要把“较少证据就行动”默认算优点；必须与 oracle sufficient set 比较。

### 11.4 分割与统计

按 storm 分组划分开发/校准/正式评估，不能让同 storm 的不同 port 或复制文件跨 split。用 SHA-256 检查共享 artifact；跨年份等泛化只是后续扩展，不在小 pilot 强做所有划分。

置信区间以 storm 为 cluster bootstrap；搜索 seed、重复采样和同 storm 的多个 probe 不是独立事件样本。小规模 pilot 如实报告样本量，不承诺显著性或排名变化。

选择“变化特别明显”的事件可以用于工具验证，但需要记录筛选规则；正式自然错误率不能从自适应或人工困难样本的错误比例推定。

### 11.5 输出文件契约

每个 `outputs/<experiment_id>/` 至少包含：

```text
manifest.json              # code/source/config/split/model/prompt/render hashes
resolved_config.yaml       # 密钥已删除
requests.jsonl             # 发出请求的授权字段与指纹
responses.jsonl            # 原始输出引用和解析结果
attempts.jsonl             # 物理请求与预算
property_results.parquet   # 含 eligible、status、reason
frontier_edges.parquet
counterexamples.jsonl
search_steps.jsonl
fingerprint.json
discovery_curve.csv
summary.md
budget_report.json
```

`manifest.json` 必须含 `synthetic`、`real_data_review_status`、`model_kind`、`evaluation_mode`、`complete/partial`、`stop_reason`。任何含 synthetic/mock/unreviewed 的实验不能导出为正式 leaderboard。

可用 matplotlib 生成每张独立图；图表同时输出底层 CSV。禁止先画理想曲线填入虚构分数。相同配置重跑的结果若因随机性不同，记录原因而不是修改旧文件。

---

## 12. 真实数据接入：尽量复用，但先证明来源与信息边界

### 12.1 CyPortQA importer

先 profiler 再 parser。读取 `Encoded_senario.json`、templates 和文件目录的真实结构，报告字段分布、空值、BOM、大小写不一致、缺图、相对路径等。不能仅照 README 猜数据 schema。

生成：

```text
artifacts.parquet
source_file_index.jsonl
candidate_episodes.parquet
import_report.json
quarantine.jsonl
```

一个候选必须能回溯到 storm、target、具体原始文件、issue cycle 和有效时间。lead-time 桶如 `24h/48h` 不自动等于实际发布时间；不把“登陆前 24h”标签当作精确可见时刻。

原 QA answers 可用于候选筛选，但 Gold 必须有自己的可追溯依据与审核记录。`senario` 这样的上游拼写在兼容 importer 中处理，内部使用规范字段并保存映射。

### 12.2 下载器

`ingest/fetch.py` 使用白名单域名、HTTPS、超时、连接限制、字节上限、重试退避和原子 rename。缓存 key 为来源 URI/版本，保存响应 metadata 和 sha256；重定向也检查目标域与地址策略。

先 `--dry-run` 展示文件清单和预计大小，再显式下载。数据中的任意 URL 不直接送入通用媒体读取器，不运行下载包里的脚本。archive 解包检查路径穿越、链接、文件数和解压后总大小。

404/403、网络失败与格式变化进入 quarantine；不能用相邻日期文件代替而不记录。

### 12.3 NHC 时间与空间核验

以原始产品自身及官方归档作为核验来源；本计划不要求下载全部历史。

官方 wind-speed-probability GIS archive 明确说明其文件覆盖所有 basins，并非每个文件仅对应一个 storm [S02-WSP]。因此 importer 必须使用产品时间、目标位置和事件上下文关联，不能从该文件名直接推断唯一 storm ID。

NHC cone、风场、概率图、watch/warning 是不同产品，不混用语义。cone containment 只是空间关系，不直接解释为港口灾损概率 [S02]。GIS 产品缺失时，可以保留原图人工核验子集，但不得伪造官方 polygon。

### 12.4 GIS 管线

新增 `geo/readers.py`、`geometry.py`、`render.py`：

```text
原始 GIS / 栅格
    → 明确 CRS、变量、单位、有效时间和 nodata
    → 目标点/港口几何
    → 空间关系与误差容差
    → 私有空间 Gold
    → 公共 PNG 派生物
```

要求：

- 距离/面积使用合适投影或 geodesic 计算，不能在经纬度直接把度数称作 km。
- 明确 `covers` 与 `contains` 的边界差异；在边界附近的点按已锁定容差处理或标 ambiguous。
- 栅格先检查 nodata、单位和概率编码；不要将 0–100 与 0–1 混淆。
- 固定 extent、尺寸、字体/legend 布局和目标 marker；保存 render config/hash。
- 圆锥等派生可视化不等于原官方产品；标出 `official_original / controlled_render` 两种视图并分开评估。
- 生成 Gold 用真实几何，不从 PNG 反推；对生成图像做人工抽样检查配准。

### 12.5 真实 episode 的人工交付包

Codex 为每个候选生成 `review_packet.md`：原始材料路径/来源、时间证据、对齐图、claim 标注、Policy、适用性质、缺失项。人的审核状态不可由 Codex 自动填为 approved。

MVP 的真数据选择标准：来自不同 storm、每例约 6 个可操控单元、至少一项可验证版本关系、至少一个真正的文本/图像互补判断、至少一个合法 fixed pair。无法满足则记录障碍，不强拼。

人工未审核时，可以运行标记为 `unreviewed_data_exploration` 的授权探索；不能进入正式报告。不能为了凑“4 个真实 episode”把 synthetic fixture 改名字。

---
## 13. Plan of Work：逐 PR 实施与验收

以下命令除 PR-00 外均为**应新增的目标接口**。Codex 实现相应模块和 CLI 后再运行；测试路径不存在不能用空目录或 `--ignore` 伪造验收。

所有 CLI 支持 `--help`，错误输出包含稳定错误码。所有写出命令支持中断恢复；已有不同 hash 产物默认拒绝覆盖，使用新的 experiment ID。

### PR-00 · audit-and-bootstrap

**目标：** 建立实际起点，不改科研逻辑。

**工作：** 读取 starter 全部相关源码及现有 AGENTS，记录 Git 状态与归档 SHA。运行现有测试和 mock demo。写 `docs/STARTER_AUDIT.md`、`docs/IMPLEMENTATION_STATUS.md`、`.gitignore`、`.env.example`（无 key）与项目虚拟环境/锁定方式。

若当前没有 starter 代码，检查用户指定目录或归档；没有可找到的文件时记录，按本计划的新契约创建基础框架，但不得声称修复了未读取的源码。

**实际已有命令：**

```bash
python -m pytest -q
PYTHONPATH=src python -m disasterfrontier.runners.local_demo \
  --episode data/episodes/demo_storm_alpha_port_blue.yaml \
  --budget 24 --output outputs/bootstrap/mock_demo.json
```

**验收：** 记录实际通过/失败数量；产物明确 synthetic/mock；没有网络模型请求；代码与旧数据未被覆盖。已有 6 个测试在本次编写环境通过，但目标环境仍需重跑。

**停止条件：** 缺依赖且环境不允许安装时标 `BLOCKED_ENV`，仍完成源码审阅和测试补写，不伪造执行记录。

### PR-01 · contracts-v2-and-regressions

**前置：** PR-00。

**目标：** 第 5 节的公共/私有类型与 v1→v2 迁移可执行。

**主要文件：** `contracts/{artifacts,evidence,episodes,probes,decisions,results}.py`、`annotations/schemas.py`、`ingest/migrate.py`、`schemas.py` 兼容 facade。

**工作：** 修 B01/B02/B06；拆分 modality/source_kind；给真实样本加严格时间/审核状态；序列化 set 前稳定排序；所有 model_copy/update 路径最后重新 schema validate，不能借 `model_copy` 绕过新约束。增加 opaque public ID。

**回归测试：**

```text
test_order_rejects_duplicate_element
test_order_rejects_missing_element
test_real_artifact_rejects_naive_time
test_forecast_valid_time_can_be_future
test_request_evidence_has_no_ordinal_rank
test_roundtrip_stable_across_hash_seeds
test_legacy_migration_stays_synthetic
test_unknown_requires_null_value
```

**目标命令：**

```bash
python -m pytest -q tests/unit/test_contracts.py tests/regression/test_starter_contracts.py
python -m disasterfrontier.cli migrate \
  --input data/episodes/demo_storm_alpha_port_blue.yaml \
  --output outputs/migration/demo_v2
```

**验收：** 公共类型中无 Gold 字段；旧 demo 可明确迁移；无时区真实记录失败而非默认 UTC；重复 order 失败；schema 与 JSON/YAML 往返稳定。

### PR-02 · version-policy-and-validity

**前置：** PR-01。

**目标：** 不靠模型的纯程序语义先正确。

**主要文件：** `lattice/versioning.py`、`lattice/validator.py`、`policy.py`、`annotations/resolver.py`、`probes/transforms.py`。

**工作：** 修 B03/B04/B05；版本 DAG 和完整传递替代；同版本多 atom；三值 Policy；严格 transform 定义；可见性与语义 active 分离；公共 Policy 单独编译；合理 conflict/inapplicable 处理。

**回归测试：**

```text
test_v1_v3_resolves_without_delivering_v2
test_latest_artifact_keeps_all_selected_units
test_hidden_new_version_does_not_change_visible_gold
test_cross_product_version_does_not_supersede
test_version_cycle_rejected
test_retracted_claim_cannot_trigger_policy
test_unknown_is_not_false
test_conflicting_same_priority_policy_rejected
test_withholding_does_not_mean_refutation
test_pair_certificate_preserves_time_and_policy
```

**目标命令：**

```bash
python -m pytest -q tests/unit/test_versioning.py tests/unit/test_policy.py tests/unit/test_validity.py
python -m disasterfrontier.cli episode validate \
  --path tests/fixtures/synthetic/multimodal_boundary/episode.yaml --mode synthetic
```

**验收：** 第 6.2 节 truth table 精确通过；所有版本环拒绝；相互独立产品不被误删；gold 不随没提供的未来 artifact 变化。

### PR-03 · leak-free-rendering-and-fixtures

**前置：** PR-01/02。

**目标：** 能看见实际将送入模型的内容，而且绝不偷偷提供答案。

**主要文件：** `rendering/{model_view,renderer,media}.py`、`tests/fixtures/synthetic/`、`cli.py` 的 doctor/render/demo 基础入口。

**工作：** 实现第 6.2 节真实 PNG 的 synthetic fixture；修 B07；模板必须包含 Public Policy；fragment selector 真正裁切；整文件去重；媒体路径/哈希验证；Gold sentinel 测试。

**回归测试：**

```text
test_renderer_never_serializes_annotations
test_renderer_sends_policy_card
test_withheld_span_absent_from_rendered_prompt
test_missing_image_fails_instead_of_text_fallback
test_artifact_path_cannot_escape_data_root
test_public_ids_do_not_encode_gold
test_same_artifact_not_repeated_for_each_atom
test_media_bytes_change_input_fingerprint
```

**目标命令：**

```bash
python -m pytest -q tests/unit/test_rendering.py tests/integration/test_model_view_isolation.py
python -m disasterfrontier.cli render \
  --episode tests/fixtures/synthetic/multimodal_boundary/episode.yaml \
  --probe tests/fixtures/synthetic/multimodal_boundary/probe_full.json \
  --out outputs/render_check
```

**验收：** 输出可审阅的 `prompt.txt`、`messages.public.json`、媒体缩略预览和 `input_manifest.json`；无 private sentinel、未选片段或答案标签；image 必须实际是 PNG bytes。

### PR-04 · budgeted-runtime-cache-and-inspect-spike

**前置：** PR-03。

**目标：** 同一个 QueryService 可驱动 fake 和可选真实 adapter，并可安全恢复。

**主要文件：** `runtime/{query,budget,cache,experiment}.py`、`runners/{base,fake,inspect_adapter}.py`、`configs/budgets/`。

**工作：** 修 B14；原子预算 reserve/settle；logical/physical 区分；raw response + parse status；cache modes；replicate 隔离；transport retries；按来源 capability 配置；provider/model 必填；log redaction。可选环境安装并锁定 Inspect 只做 import/接口 fake smoke，不默认调用真实模型。

**回归测试：**

```text
test_no_api_request_without_explicit_permission
test_budget_prevents_concurrent_overspend
test_retry_consumes_physical_request_budget
test_cache_hit_not_new_independent_sample
test_new_replicate_requires_distinct_query_key
test_history_changes_cache_key
test_resume_does_not_repeat_completed_logical_queries
test_provider_error_not_replaced_with_monitor
test_inspect_adapter_sends_real_image_and_policy
test_secrets_removed_from_resolved_config_and_logs
```

**目标命令：**

```bash
python -m pytest -q tests/unit/test_budget.py tests/unit/test_cache_v2.py tests/integration/test_fake_runtime.py
python -m disasterfrontier.cli doctor --offline
python -m disasterfrontier.cli run --config configs/runs/offline_smoke.yaml --out outputs/offline_smoke
```

**验收：** `provider_requests=0`；FakeTransport 的错误路径经过真实 QueryService；相同 replicate replay 不重发；独立 replicate 不能复用同一答案；预算失败之前不发生请求。

### PR-05 · property-oracles-and-fixed-evaluation

**前置：** PR-02/04。

**目标：** 能区分正确行动变化与真正违规。

**主要文件：** `eval/{applicability,single_probe,pairwise,sequence}.py`、`probes/{canonical,exhaustive}.py`、`runners/fixture_models.py`。

**工作：** 修 B11/B12；实现 P01–P04，先为 P05/P06 建明确不适用路径；引入正确 mock 与可控错误 mock：忽略视觉、旧版覆盖、无关警报词触发、总是 unknown。各错误 mock 是测试夹具，不伪装真实模型。

**目标命令：**

```bash
python -m pytest -q tests/unit/test_properties.py tests/integration/test_fault_injection.py
python -m disasterfrontier.cli probe build \
  --episodes tests/fixtures/synthetic/multimodal_boundary \
  --suite exhaustive --max-units 6 --out outputs/exhaustive/probes
python -m disasterfrontier.cli run \
  --config configs/runs/offline_calibration.yaml --out outputs/offline_calibration
```

**验收：** 正确 mock 不因“引用历史旧版本”或合法 unknown 被误报；故障 mock 被对应性质捕获；所有 inapplicable 带原因；不足信息组合不沿用 full evidence Gold。

### PR-06 · search-baselines-and-pair-shrinking

**前置：** PR-05。

**目标：** 在离线响应表上真实比较搜索方法，不泄漏未查标签。

**主要文件：** `search/{base,random,bfs,canonical,frontier,shrink}.py`、`runtime/replay.py`、`analysis/discovery.py`。

**工作：** 修 B08/B09/B10；有界候选队列、完整输入去重、priority 更新、逻辑预算、anchors 记账、pair-preserving shrink、dump/load planner state。生成一个已知最小反例的小型响应表。

**回归测试：**

```text
test_capacity_one_preserves_highest_priority_candidate
test_order_variant_not_deduplicated_as_same_input
test_search_cannot_read_unqueried_action_table
test_anchor_and_shrink_queries_count_toward_budget
test_pair_shrink_preserves_protected_edit
test_shrink_cannot_change_property_identity
test_invalid_candidate_never_calls_model
test_resume_has_same_logical_trace_for_deterministic_replay
test_one_minimal_not_claimed_when_budget_exhausted
test_zero_frontier_denominator_is_na
```

**目标命令：**

```bash
python -m pytest -q tests/unit/test_search_v2.py tests/unit/test_shrink_pairs.py tests/integration/test_replay_fairness.py
python -m disasterfrontier.cli search \
  --config configs/runs/offline_search_comparison.yaml --out outputs/search_comparison
python -m disasterfrontier.cli analyze \
  --run outputs/search_comparison --out outputs/search_comparison/report
```

**验收：** Random/BFS/Canonical/FrontierSearch-Lite 使用同一预算；重放 lookup 消耗逻辑预算；至少一个植入失败能被压缩并经终检；保存各算法原始发现序列，不要求 Lite 必须优于 Random 才算工程通过。

### PR-07 · stateful-sequences-and-noise-controls

**前置：** PR-04/05。

**目标：** 真正执行多轮序列，而不只是比较两个手工构造的最终 JSON。

**主要文件：** `runners/sequence_runner.py`、`probes/sequences.py`、`eval/sequence.py`、序列 synthetic fixtures。

**工作：** 修 B13；step 串行、序列间隔离、append-only delivery、model-authored commit 原样保存、retirement event 语义、single-prompt-order vs multi-turn-arrival 分开、合法政策迟滞测试、replicate 噪声基线。Context eviction 不当成 source retraction。

**回归测试：**

```text
test_sequence_step_uses_previous_model_commit_not_gold
test_two_sequences_do_not_share_state
test_order_pair_requires_same_final_time_and_policy_state
test_old_fact_not_forgotten_just_because_prompt_omits_it
test_source_correction_retires_current_claim
test_policy_required_hysteresis_not_flagged_as_failure
test_noise_only_mock_not_called_confirmed_order_failure
test_non_downgrade_at_end_is_censored
```

**目标命令：**

```bash
python -m pytest -q tests/unit/test_sequences_v2.py tests/integration/test_sequence_runner.py
python -m disasterfrontier.cli sequence run \
  --config configs/runs/offline_sequences.yaml --out outputs/sequence_smoke
```

**验收：** 顺序、状态、政策/资源匹配都有可审计日志；正确 mock 在合法迟滞例上不误报；mutant 历史残留可检测；最终步缺失不能当作完整轨迹。

### PR-08 · real-source-import-and-gis

**前置：** PR-01/02/03；可与 PR-05–07 在独立模块并行。

**目标：** 真实公开文件可变成可审核候选，不要求这一步已有正式 Gold。

**主要文件：** `ingest/{cyportqa,nhc,manifest,fetch}.py`、`geo/`、`configs/sources.lock.yaml`、`docs/REAL_DATA_REVIEW.md`。

**工作：** 按第 12 节 profiler/importer、下载器、GIS、时间来源审查实现。先对小型本地 source fixture 验证，再对获准真实目录跑。源数据断网时仍需完成 parser fixtures 和 HTTP mock 测试。

**目标命令：**

```bash
python -m pytest -q tests/unit/test_ingest.py tests/unit/test_downloader.py tests/unit/test_geo.py
python -m disasterfrontier.cli dataset profile \
  --source cyportqa --root "$CYPORTQA_ROOT" --out outputs/cyportqa_profile
python -m disasterfrontier.cli dataset ingest \
  --source cyportqa --root "$CYPORTQA_ROOT" --limit-episodes 2 --out data/manifests/pilot
python -m disasterfrontier.cli review \
  --episode data/episodes/public/pilot_001.yaml --out outputs/review/pilot_001
```

`CYPORTQA_ROOT` 必须是实际存在的用户目录或本次获准 checkout；`pilot_001.yaml` 仅在 importer 真实生成后使用，不允许用一个空模板冒充。

**验收：** 两个候选的每个文件可回溯原路径与 sha256；缺失项进入 quarantine；没有把日期/lead-time 猜成精确 available_at；真实 GIS 与 PNG 配准经过 review packet；审核人字段仍由人工填写。

### PR-09 · authorized-real-calibration

**前置：** PR-04/05/06/08 + 用户授权模型预算 + 足够的真实数据审核。

**目标：** 从 2 个样本 smoke 到 4 个独立 storm 的小型经验参照图。

**工作：** 锁定 source/model/prompt/Policy/splits；运行 fixed probes 和合法穷举子集；对边界/候选失败预先分配重复采样；记录 provider errors 与截断。先单模型少量请求验媒体和 schema，再扩大。

**目标命令（默认先 dry-run）：**

```bash
python -m disasterfrontier.cli run \
  --config configs/runs/real_calibration.yaml --dry-run --out outputs/calibration_dry_run

# 只有用户已明确批准配置中的预算后：
python -m disasterfrontier.cli run \
  --config configs/runs/real_calibration.yaml \
  --allow-model-calls --out outputs/real_calibration
```

**验收：** 所有实际模型名称/版本/输入字节与预算可追溯；真实输入不包含 Gold；参照图注明采样次数；无“调用失败被填成 monitor”；没有使用 mock 替代缺失结果。

**阻塞规则：** 缺 key/预算/审核时标 `BLOCKED_LIVE` 或 `BLOCKED_REVIEW`；提交完整 dry-run 与待审核材料后继续其他离线阶段，不能随意换用别人的端点。

### PR-10 · adaptive-main-set-and-generalization

**前置：** PR-09 得到有意义的实证基础，用户批准扩大范围。

**目标：** 在未参与调参的 episode 上比较搜索方法，并生成模型失败特征。

**工作：** 按 storm 扩至计划的额外 8 个 episode；每例约 8–12 单元，每模型每例先 40–60 逻辑查询的候选预算，再加明确确认配额。所有数字须经过费用 dry-run，不能沿用文本自动开跑。

Canonical Core 在所有模型相同；Adaptive 使用相同预算而非相同专用题。固定反例跨模型迁移，报告选择偏差。LLM-based planner 仅以独立 P2 配置增加，成本单列。

**目标命令：**

```bash
python -m disasterfrontier.cli search \
  --config configs/runs/adaptive_main.yaml --dry-run --out outputs/adaptive_dry_run
python -m disasterfrontier.cli analyze \
  --run outputs/adaptive_main --out outputs/adaptive_main/report
```

**验收：** 开发/测试 storm 无重叠；方法在相同预算下比较；不存在所有 test Gold 已提前发送给 planner；有各性质分母、噪声控制、失败包与数据文件。不要求预定排名或显著性。

### PR-11 · release-readiness-and-handoff

**前置：** 离线阶段可先完成；正式数据 release 额外要求 PR-09/10 与授权。

**目标：** 新用户只靠 README、配置和小 fixture 能复现系统行为。

**工作：** 维护 CLI/help、最小依赖、公开/私有隔离、LICENSE/NOTICE、复现实验配置、数据清单、失败包导出、API/GPU 成本说明、测试矩阵和清晰限制。输出 `docs/GO_NO_GO.md`，结论依据实际观察而非原先设想。

**目标命令：**

```bash
python -m pytest -q -m 'not live and not network'
python -m ruff check src tests
python -m mypy src/disasterfrontier
python -m disasterfrontier.cli demo --suite synthetic --model mock_oracle --out outputs/final_smoke
python -m disasterfrontier.cli export --run outputs/final_smoke --destination outputs/handoff_demo
```

在 PR-00/01 注册 pytest `live/network/geo` markers；若 ruff/mypy 有原有问题，先记录并增量修复，不用忽略整个 package 的方式假通过。

**验收：** 干净环境离线 E2E 可重复；文档命令实际执行过；demo 导出显著 synthetic/mock；正式导出拒绝混入未审核数据、秘密或未完成实验；完整 handoff 写明仍未运行的真实步骤。

---

## 14. 接口与 CLI 总表

### 14.1 模块接口

这是目标签名形态，具体类型来自第 5 节；不得用 `dict[str, Any]` 贯穿全部核心逻辑。

```python
load_public_episode(path: Path) -> PublicEpisode
load_annotations(path: Path) -> EpisodeAnnotations
validate_episode(episode: PublicEpisode, manifest: ArtifactIndex) -> ValidationReport

compile_policy(card: PolicyCard) -> CompiledPolicy
resolve_gold_claims(view: EvidenceVisibility, annotations: EpisodeAnnotations) -> GoldClaims
evaluate_policy(claims: ClaimSet, policy: CompiledPolicy, context: PolicyContext) -> PolicyDecision

build_model_view(episode: PublicEpisode, probe: Probe, media: MediaStore) -> ModelView
render_input(view: ModelView, config: RenderConfig) -> RenderedInput

validate_probe(probe: Probe, episode: PublicEpisode, manifest: ArtifactIndex) -> ValidationReport
validate_pair(pair: ProbePair, context: ValidationContext) -> ApplicabilityCertificate

async query_service.query(request: RenderedInput, replicate_id: int) -> QueryResult
async sequence_runner.run(sequence: SequenceProbe, adapter: ModelAdapter) -> SequenceResult

build_canonical_probes(episode: PublicEpisode, constraints: ProbeConstraints) -> ProbeCatalog
build_exhaustive_probes(episode: PublicEpisode, max_units: int) -> ProbeCatalog
run_search(planner: SearchPlanner, query_service: QueryService, config: SearchConfig) -> SearchResult
shrink_counterexample(case: CounterexampleCandidate, query_service: QueryService) -> Counterexample

score_probe(result: QueryResult, oracle: GoldContext) -> ProbeScores
score_pair(pair: ProbePair, results: QueryResultPair, certificate: ApplicabilityCertificate) -> PropertyResult
build_report(experiment_dir: Path) -> ReportBundle
```

### 14.2 CLI 最小集合

| 命令 | 默认是否联网 | 主要输出 |
|---|---|---|
| `doctor --offline` | 否 | 环境/依赖/路径/配置检查 |
| `migrate` | 否 | 兼容样本与迁移报告 |
| `episode validate` | 否 | schema/来源/版本/规则错误 |
| `dataset profile` | 否，本地目录 | schema profile |
| `dataset ingest` | 否，本地目录 | manifest、候选、quarantine |
| `dataset fetch --dry-run` | dry-run 不下载 | 来源文件计划 |
| `probe build` | 否 | canonical 或 exhaustive catalog |
| `render` | 否 | 公共实际模型输入和媒体清单 |
| `run --dry-run` | 否 | 可运行性/授权/预算预估 |
| `run` | 依据 config；默认 offline | QueryResult 表 |
| `search` | 依据 config；默认 replay/mock | 搜索轨迹、反例 |
| `shrink` | 同一授权 QueryService | 缩减与确认记录 |
| `sequence run` | 依据 config；默认 offline | 多轮提交记录 |
| `analyze` | 否 | fingerprint、曲线、summary |
| `review` | 否 | 人工审核包 |
| `demo` | 否 | 一键 synthetic E2E |
| `export` | 否 | 可分发的去秘密结果包 |

退出码建议：`0=完成`，`2=配置/数据校验失败`，`3=预算不足或未授权`，`4=上游资源阻塞`，`5=运行不完整`。最终以 `docs/RUNBOOK.md` 的实际实现为准，不能只写表不实现。

---

## 15. 对前序讨论的必要澄清（禁止静默回退）

这一节明确区分“沿用已有方案”与“本次新增修正”，避免 Codex 从旧聊天复制已被否定的简化实现。

| 先前简化说法 | 本计划的执行规则 | 原因 |
|---|---|---|
| REQUEST_EVIDENCE=-1 | 不进入行动强度排序 | 获取信息不等于比监测更低的业务行动 |
| 同一版本组只保留一个 atom | Artifact 版本选中后保留该版本的全部可见单元 | 一份公告可含多个独立事实 |
| 读取 atom.artifact_path 全文 | 整文件 unit 或精确 selector，不能两者混用 | 防止 withheld 信息重新注入 |
| 相同 evidence set 就同一 probe | 输入 bytes/order/history/Policy 都参与身份 | 否则顺序实验与缓存互相污染 |
| 没显示旧证据就应忘记 | 区分未交付、上下文移除、正式撤回 | 不能把已有知识当作从未见过 |
| 多证据不得降低风险 | 只有经过 oracle 证明的同向、同语义 edit 检查单调性 | 新证据可能正确地降低风险 |
| 旧版本被引用就是失败 | 历史解释引用合法；旧版错误支持当前状态才是污染 | 否则无法正确描述变更 |
| Edited 后不变证明 memory 无效 | 先隔离可重建途径和政策无差异的情况 | 不变可能是正确覆盖或动作集合重叠 |
| 2/3 重复就确认 | 作为筛选，重要反例需要独立复核与不确定性报告 | 不能把少量采样包装成统计保证 |
| greedy shrink 得到最小证据 | 默认 reduced/1-minimal；全局最小需穷举证明 | 非单调空间没有全局保证 |
| cache hit 免费提高查询召回 | 物理费可为零，但算法新观察仍计逻辑预算 | 保证 replay 比较公平 |
| issued_at=available_at | 只有证据支持时才合并；否则明确 issuance proxy | 发布时间声明不等于已验证分发时刻 |
| 双重干预证明内部因果链 | 限定为受控输入/状态载体的外部行为效应 | 不过度解释黑箱实验 |

上述澄清必须体现在代码、测试、报告和 README，不能只出现在本计划里。

---

## 16. Validation and Acceptance：整体完成标准

### 16.1 工程验收与研究结论分开

**工程完成**不以 FrontierSearch 击败 Random 或模型有错误为条件。工程完成要求数据、预算、输入隔离、性质适用性、重放、公平性和导出行为正确。

**研究继续/收缩判断**依据真实模型实验：是否发现值得分析的非平凡边界、是否有真正多模态依赖、搜索是否有效、反例能否复现与迁移。若没有优势，如实报告负结果，不调测试集到出现预设结论。

### 16.2 最低测试矩阵

| 类别 | 必须包含的正/反案例 |
|---|---|
| 时间 | aware/naive、availability 区间、未来有效预测、延迟交付 |
| 版本 | 完整链、跳中间版、同版多个单元、跨产品不覆盖、环 |
| 输入 | Gold sentinel、片段泄漏、缺图、路径逃逸、Policy 已发送 |
| 政策 | true/false/unknown、retracted/superseded、优先级冲突、合法迟滞 |
| 缓存 | 相同请求、换模型、换媒体、换顺序、换历史、换 replicate |
| 预算 | anchors、retries、shrink、并发 reserve、重放计数、取消 |
| 性质 | pass、fail、inapplicable、indeterminate 都有测试 |
| 搜索 | 队列截断、恢复、无候选、无失败、重复候选、未查标签不可见 |
| 缩减 | 保护 edit、依赖 bundle、预算用尽、1-minimal 终检 |
| 序列 | 独立会话、同终态不同路径、政策依赖、未降级右删失 |
| 数据 | BOM/大小写/缺图、官方时间缺失、多 storm 产品、GIS nodata |
| 报告 | 零分母、partial、synthetic 隔离、secret redaction、split 泄漏 |

不要用“测试数量达到某值”代替行为覆盖。可对核心纯程序模块设置覆盖率门槛，但本计划不预设未经执行的最终通过数量。

### 16.3 最终复现链

一个只安装 core+dev 的干净环境应能够：

```bash
python -m pytest -q -m 'not live and not network'
python -m disasterfrontier.cli demo --suite synthetic --model mock_oracle --out outputs/repro_oracle
python -m disasterfrontier.cli demo --suite synthetic --model mock_stale_override --out outputs/repro_mutant
python -m disasterfrontier.cli search --config configs/runs/offline_search_comparison.yaml --out outputs/repro_search
python -m disasterfrontier.cli analyze --run outputs/repro_search --out outputs/repro_search/report
```

可核验结果：正确 mock 按 fixture 定义通过，故障 mock 出现预置类型的违规；报告含真实执行的逻辑查询数和 zero provider requests；反例包含左右实际输入、性质证书与独立确认状态。这里不规定 frontier 边数，避免语义修复后被旧 demo 数字束缚。

真实实验额外要求 source、data review、provider/model、预算授权和所有媒体齐全。没有这些条件时，系统应安全阻止真实执行并提供具体阻塞原因。

---

## 17. Idempotence and Recovery：可恢复与不破坏已有工作

原始数据只写一次，以 checksum 判断是否一致；派生输出使用内容哈希目录或新 experiment ID。生成失败写临时文件，完成后原子 rename。

每个查询先落 request/attempt 记录，完成后提交 response。恢复时只补缺失逻辑结果；状态不明确的付费超时请求不能假定“没有计费”，应保守计账并记录。

序列中断从最近完整 step 的原始模型 commit 恢复，前置输入/模型配置发生变化则另开实验，不续写原 ID。

本地 Git commit 可按 PR 小步提交，前提是用户已允许；不得自动 push 或 force reset。工作区已有未提交修改时不覆盖，明确记录与你的修改范围。

缓存数据库迁移先备份或使用新 schema version；不能以清空旧结果为默认修复。测试产生的文件放 temp/output 目录，不污染真实源清单。

---

## 18. 进度、意外发现与决策日志模板

以下四个小节是持续执行状态，不是一次性写完的装饰。也可在 `docs/IMPLEMENTATION_STATUS.md` 维护同结构，并在本计划记录其路径。

### Progress

- [x] 2026-09-05：计划编写阶段已核对当前 starter 归档与 32 个文件，重跑 6 个既有测试和 mock demo。
- [x] 2026-09-05：计划编写阶段已复现 B01/B02/B03/B04/B05，并将代码审阅风险列入 P0。
- [ ] PR-00：目标执行环境重新审计与 bootstrap。
- [ ] PR-01：v2 契约、回归测试与迁移。
- [ ] PR-02：版本、Policy、合法性。
- [ ] PR-03：防泄漏 renderer 与真实 PNG fixture。
- [ ] PR-04：预算、缓存、FakeTransport、Inspect spike。
- [ ] PR-05：性质 oracle 与固定评价。
- [ ] PR-06：搜索基线、配对压缩、重放公平性。
- [ ] PR-07：序列运行与噪声控制。
- [ ] PR-08：CyPortQA/NHC/GIS importer 与人工审核包。
- [ ] PR-09：获授权的真实校准；无权限则 BLOCKED。
- [ ] PR-10：主集自适应实验；根据校准结果决定是否执行。
- [ ] PR-11：离线可复现交付、文档与正式发布准备。

### Surprises & Discoveries

```text
日期：2026-09-05
观察：既有 6 个测试全通过，但重复 arrival_order 和 retracted claim 参与 Policy 均可复现。
证据：第 2.2 节，STARTER_AUDIT.json。
影响：先补语义回归测试，再增加真实数据/模型规模。
```

后续按“日期—观察—证据—影响”追加。这里只记录可公开验证的技术理由，不要求输出私有思维链。

### Decision Log

```text
D001 · 2026-09-05
决定：保留 DisasterFrontier 主线，不再次改研究题目。
理由：用户当前任务是把已讨论方案转成可执行代码计划。

D002 · 2026-09-05
决定：MVP 先整文件 Evidence Unit，再考虑 span/region 级缩减。
理由：避免原始整文件渲染绕过 withholding，先确保实验有效。

D003 · 2026-09-05
决定：先完成离线正确性和预算层，再运行真实模型。
理由：starter 尚有会改变科学结论的语义缺陷，且真实 API 未验收。

D004 · 2026-09-05
决定：严格区分公共模型输入、私有标注、搜索可见信息。
理由：禁止通过 prompt、媒体或 acquisition 偷看预期答案。
```

### Outcomes & Retrospective

当前只完成计划与 starter 审阅，**尚未实施 PR-00–11 的新增代码**。当前原型可跑 mock，不是完整真实 Benchmark。下一行动是目标环境 PR-00 与 P0 回归测试；外部依赖只阻塞对应步骤，不阻塞离线实现。

每阶段结束写：完成行为、实际命令、通过/失败、产物、残留风险、下次入口。

---

## 19. 六周排期与并行边界

下面是实施顺序估计，不是完成时间保证；真实数据审核和模型访问可能成为主要瓶颈。

| 阶段 | 推荐工作 | 可以并行的内容 |
|---|---|---|
| 前 72 小时 | PR-00/01/02 的核心缺陷与 truth table | 源文件盘点、许可证和 metadata profile |
| 第 1 周 | PR-03/04，离线真实消息管线 | source importer fixtures |
| 第 2 周 | PR-05，固定探测与 oracle | GIS fixture 与审核包模板 |
| 第 3 周 | PR-06，replay 搜索与缩减 | PR-08 的小规模源数据接入 |
| 第 4 周 | PR-07，序列与噪声控制 | 人工数据/Policy 审核 |
| 第 5 周 | PR-09，获授权真实校准 | 报告代码与复现文档 |
| 第 6 周 | 视结果执行 PR-10；完成 PR-11 | 负结果分析或范围收缩 |

多 agent 并行时，先冻结 contracts；分别负责 `ingest/geo`、`runtime`、`eval/search`。同一分支不要让多个 agent 同时重写 schema/CLI。每条支线先有合约测试再合并，主代理做端到端复核。

不要为了并行建立三套类型或三套缓存；最费时间的不是代码量，而是后期对不一致实验语义进行补救。

---

## 20. Go / No-Go：怎样决定值得继续

### 工程 Gate（必须满足）

ModelView 无 Gold 泄漏；配对适用前提可自动核验；版本/时间语义正确；BudgetedQuery 不能被绕过；缓存与重复采样分离；真实数据与 synthetic 清晰隔离；报告可追溯。

任何一项失败，停止真实规模扩张，先修工程。

### 科研 Gate（待实验验证）

判断是否存在值得研究的失效/边界差异，是否真的有跨模态必要性，FrontierSearch 是否在合理预算内比简单方法更有效，是否出现可迁移和可解释的小反例。

不把“40% 查询找到 80% 反例”这类先前管理目标写成必须达到的测试预期。它们最多作为开发目标；真实曲线怎么得出就怎么报告。

| 观察 | 后续行动 |
|---|---|
| FrontierSearch 不优于 Random/BFS | 保留 benchmark/性质分析，降低或放弃搜索方法 novelty claim |
| Text-only 足够完成全部任务 | 核查信息冗余，不能强行宣称 CV 必需 |
| 大量时间只有 issuance proxy | 主张改为 issuance-conditioned replay，严格公开可见子集另列 |
| Action Gold 主观分歧大 | 保留可计算 Policy-controlled 任务，现实行动仅做描述性对照 |
| 大部分“失败”只来自噪声 | 增加预注册重复与噪声模型，不继续报确定性边界 |
| 几乎没有非平凡反例 | 检查问题与单元选择，记录负结果，停止盲目扩大模型调用 |

不能在看到正式测试结果后删除困难病例、改 Policy、增加容差而仍沿用相同 benchmark version。

---

## 21. Artifacts and Notes：最终 handoff 应交付的东西

**代码：** 通过离线测试的 package、CLI、回归/性质/集成/E2E tests、可选 Inspect/GIS 适配。

**数据：** 小型合成 fixture、真实源 manifest、候选/审核/隔离记录；只有有权公开的文件才加入 release。

**实验：** 固定 Canonical 配置、Random/BFS/FrontierSearch 配置、replay-only 流程、原始响应与反例导出；授权不足时给 dry-run，不伪造结果。

**文档：** README、RUNBOOK、DATA_CONTRACT、PROPERTY_DEFINITIONS、预算与恢复说明、许可证、已知限制、GO_NO_GO。

**每次给用户的状态汇报采用：**

```text
本轮完成：具体 PR 与用户可运行行为。
实际验证：命令 + 退出码 + 通过/失败 + 产物路径。
尚未验证：真实 API / GIS / 人工审核等，分别列明。
阻塞条件：缺什么，影响哪一步，不影响哪些离线步骤。
下一步：一个明确的下个 PR，而不是另一份泛化方案。
```

不得在终端/报告中显示 API key，不把真实业务行动输出给外部机构，不自动发布网页或向远程仓库推送。

---

## 22. 来源与核验记录

本文的设计规格主要来自本次对话已选定路线；P0 列表来自本次实际 starter 检查。外部资源只用于代码复用与 API/数据契约核对，不作为“这些研究贡献已经证明新颖”的证据。

### [L00] 本地 starter

```text
文件：disasterfrontier_starter.zip / disasterfrontier_starter.tar.gz
核验：2026-09-05
ZIP SHA-256：a536368804a55cd06ccc6b3872103dedc504b89535febf48634d805c42e7e681
附件：STARTER_AUDIT.json
```

### [S01] CyPortQA 作者代码仓库

```text
https://github.com/ChenchenMobility/MLLM-Bench-CyPortQA
```

用于原始产品/场景索引/templates 和输入适配参考。仓库根目录与 README 本次可访问；具体数据下载完整性和运行兼容性仍由 PR-08 核验。

### [S02] NHC 官方 GIS / archive

```text
https://www.nhc.noaa.gov/gis/
https://www.nhc.noaa.gov/data/
https://www.nhc.noaa.gov/aboutnhcgraphics.shtml
```

本次 GIS 首页直接抓取曾失败，但官方搜索结果提供产品列表；执行时再次核验。产品说明区分 cone、wind field、warning 等，不能互换语义。

[S02-WSP] 官方 WSP 归档：

```text
https://www.nhc.noaa.gov/gis/archive_wsp.php
```

该页明确说明 WSP 数据覆盖所有 basins，非单 storm 文件。另一个实际归档例表明 advisory 编号可含 `003A` 等后缀，禁止只按 int 解析：

```text
https://www.nhc.noaa.gov/gis/archive_forecast_info_results.php?id=al09&name=Hurricane+IAN&year=2022
```

### [S03] Inspect structured output

```text
https://inspect.aisi.org.uk/structured.html
https://inspect.aisi.org.uk/reference/inspect_ai.model.html
```

用于 ResponseSchema/GenerateConfig 与 provider 兼容性核验。本次读取文档，不代表已在 starter 中安装或运行通过。

### [S04] Inspect 多模态与媒体授权

```text
https://inspect.aisi.org.uk/multimodal.html
```

用于运行期 media 必须 inline、可信本地路径 materialize 和媒体权限边界。

### [S05] Hypothesis

```text
https://hypothesis.readthedocs.io/en/latest/reference/api.html
https://github.com/HypothesisWorks/hypothesis
```

用于纯程序性质测试和可控 shrinking；不是默认付费模型探索器。

### [S06] STATE-Bench

```text
https://github.com/microsoft/STATE-Bench
```

参考任务/状态差分架构，复制具体代码前核验文件与许可证。**此项目不是 StateMemBench。**

### [S07] WorldMemArena

```text
https://github.com/UCSB-AI/WorldMemArena
```

可选 memory baseline adapter 来源，不是 MVP 必需依赖；接入前固定具体实现与版本。

### [S08] Tropycal

```text
https://github.com/tropycal/tropycal
```

仅用于候选检索与事件对齐。本计划未验证具体历史数据方法，不复制未经当前版本验证的函数名。

### [S09] AFDBench 用户提供论文

```text
AFDBench.pdf
题名：AFDBench: A Reasoning-First AI Scientist for National Weather Service Forecast Discussions
依据：Section 3.1（PDF 第 2 页）、Section 4.1（PDF 第 3 页）
```

论文任务是结构化天气预报到专业 AFD；本文只借鉴 narrative-first 对照形式，不声称已获得官方训练代码或模型权重。不是要求先复现其训练。

### [S10] Codex 项目指令

```text
https://developers.openai.com/codex/guides/agents-md
```

官方文档说明 Codex 会读取项目指令，并存在项目指令体积限制。因此配套 AGENTS 保持短小，完整实施规格存本文件，由入口要求显式阅读，不把全文塞入自动加载指令。

### [S11] Codex 长任务执行计划

```text
https://developers.openai.com/cookbook/articles/codex_exec_plans
```

参考其自包含任务定义、验收命令及 Progress/Discovery/Decision/Outcome 持续记录形式。本文是本项目自己的执行规格，不要求安装额外计划工具。

---

## 23. 第一次交给 Codex 的完整启动提示

将本文件放到 starter 解压后的项目根目录；配套 AGENTS 先与已有指令合并。随后把以下内容交给 Codex：

```text
请阅读当前仓库适用的 AGENTS.md，并完整读取 DISASTERFRONTIER_CODEX_PLAN.md。

以现有 disasterfrontier_starter 为起点实施计划，不要重新设计研究题目，也不要只回复方案。
先执行 PR-00，在目标环境复核 starter、测试和工作区状态；然后优先完成 PR-01～PR-04。
对计划中的 B01～B15 先写或补足回归测试，再修复。每个 PR 完成后运行验收命令并记录实际输出。

默认 offline：不得调用付费模型、下载模型权重、启动 GPU 服务、push 仓库或修改 SSH/平台配置。
无 API key 或真实数据时继续完成合成 fixture、Mock/FakeTransport、数据解析器和 dry-run，
只将依赖外部权限或人工审核的部分标记 BLOCKED，不能把它们伪装为已通过。

核心约束：公共模型输入与私有 Gold 完全隔离；Policy Card 必须发送给模型；
版本在 artifact 层解析；REQUEST_EVIDENCE 不参与强度排序；
withholding、context eviction、source retraction 三种语义不能混淆；
搜索、重试、确认和反例缩减都必须经过统一预算/缓存服务。

每次停止前更新 docs/IMPLEMENTATION_STATUS.md，明确已实施、已验收、未验证和下一步。
如果本次能继续，就按计划推进后续不受外部依赖阻塞的里程碑，不必反复询问是否继续。
最终只报告真实修改、真实命令、测试结果、产物路径和阻塞条件。
```

**文档结束。下一步不是再次规划，而是在目标仓库执行 PR-00。**
