---
title: DisasterTrace — Codex 可执行实施计划
plan_version: "1.0"
planning_date: "2026-09-05"
language: zh-CN
starting_point: disastertrace-starter.zip
starting_archive_sha256: "823ffa9fcbea8f114565fba36ee9e3fc9bd94f7a1618b45724e790c8bedae6c6"
implementation_status: "plan_only; starter inspected and baseline tests executed"
default_execution_target: "M1_offline_end_to_end"
default_allow_paid_api: false
default_allow_model_training: false
---

# DisasterTrace：从现有 starter 到可验证 Benchmark 的实施计划

> **给 Codex 的任务：在已有 starter 上增量开发，不从零重写。先修复测量协议与评分，再实现无 API 的完整回放，随后接入真实数据和模型。**
>
> 本文是实施规格，不代表其中的新命令、新模块或正式数据已经存在。第 2 节明确列出现有能力；第 12 节以独立任务定义待实现能力。没有联网、密钥或人工审核时，完成不依赖这些条件的工程，并将真实数据、付费模型运行或人工审核标为 BLOCKED，禁止伪造完成。

## 导航

- [0. 开始执行](#s0)
- [1. 固定目标与边界](#s1)
- [2. starter 实际审计与优先修复](#s2)
- [3. 开源复用策略](#s3)
- [4. 工程布局与环境](#s4)
- [5. 数据、时间与状态契约](#s5)
- [6. Replay Engine 与隔离](#s6)
- [7. 数据构建、文本和 GIS Gold](#s7)
- [8. 干预与因果审计](#s8)
- [9. 评分契约](#s9)
- [10. baseline 与模型接口](#s10)
- [11. CLI、配置与产物](#s11)
- [12. 分阶段任务单](#s12)
- [13. 测试矩阵与验收](#s13)
- [14. 并行开发、阻塞与续接](#s14)
- [15. 数据扩展、统计与冻结](#s15)
- [16. 延后扩展](#s16)
- [17. 完成定义与交付模板](#s17)
- [18. 参考资源](#s18)

<a id="s0"></a>
## 0. 开始执行

### 0.1 可以直接交给 Codex 的启动指令

```text
读取仓库根目录 DISASTERTRACE_CODEX_PLAN.md 和已有 AGENTS.md。
基于已有 disastertrace starter 增量实现，不整体重写、不重新做一轮研究规划。
先执行 DT-00，核实文件、依赖、现有 6 个测试与已记录的缺陷。
随后按依赖完成 M1：严格 schema、状态 reducer、证据可见性、独立请求、
可靠 trace、确定性评分、fixture agents，以及离线 demo → run → score → report 闭环。
先写针对缺陷的回归测试，再修复代码；不要仅增加空类、占位返回或未执行的命令。

默认不调用付费 API、不训练模型、不修改用户其他仓库、不上传或发布资料。
网络、密钥、真实发布时间证明或人工审核缺失时，记录 BLOCKERS.md，继续可离线任务。
不得用 synthetic episode 替代真实数据并标为 real，不得将 issued_at 直接写成 available_at。
每完成一个任务更新 IMPLEMENTATION_STATUS.md，记录改动、真实执行命令和测试结果。
阶段结束给出可复现命令、通过/失败/未运行的测试、未解决问题和下一任务 ID。
```

### 0.2 工作目录

已有仓库：在该仓库内执行，保留未提交修改。没有仓库：解压 starter 后，以包含 `pyproject.toml` 的 `disastertrace-starter/` 为根目录。

不要把本环境的 `/mnt/data/...` 写进项目代码。本文所有项目路径均相对于仓库根目录。用户的 Windows、WSL、Linux/CCI 路径由配置传入。

### 0.3 执行规则

1. 每次开始先读 `IMPLEMENTATION_STATUS.md`、`DECISIONS.md`、`BLOCKERS.md`；没有则创建。
2. 有既有实现时先检查再复用。文档与代码冲突，以实际检查为起点，以本计划的协议契约为修改目标。
3. 每个任务必须有：实现、非平凡测试、CLI/接口说明、实际运行记录。仅“写完代码”不算 DONE。
4. 不删除失败测试来提高通过率；允许修订旧测试，但必须说明旧测试违反哪项新协议，并保留回归覆盖。
5. 不执行 `git reset --hard`、`git clean -fd` 或覆盖用户修改；不自动 push、创建公开 release 或上传数据。
6. 原始 artifact、历史 trace 不覆盖；新 schema、新规则、新 scorer 生成新版本和 hash。
7. 本计划不授权真实港口操作、外部业务写入或实际灾害调度。行动是离线 benchmark 输出。

<a id="s1"></a>
## 1. 固定目标与边界

### 1.1 研究任务

逐 checkpoint 提供当时允许使用的灾害文本、地图和公告，让模型维护**自己提交的显式状态**，再审计证据、更新、状态传递与行动。

```text
原始证据 → 时间/来源账本 → 分轮可见证据 → 模型状态提交
                                           ↓
                              自然回放 / 证据干预 / carrier 干预
                                           ↓
                           确定性评分 + 可追踪失败原因
```

首个真实场景只做 storm–port；不同时接入洪水、野火、地震和数值天气预报模型。

### 1.2 里程碑

| 阶段 | 必须交付 | 不能据此宣称 |
|---|---|---|
| M0 | starter 审计、回归测试、协议契约 | 已有正式 benchmark |
| M1 | 无网络、无密钥的 synthetic demo 闭环 | 已验证真实灾害表现 |
| M2 | 1 个 provenance 完整的真实 episode；缺失条件明确列出 | 所有发布时间均精确可知 |
| M3 | 4 个真实 episode；Core B / Core C 诊断；受控模型 smoke run | 可靠的广域 leaderboard |
| M4 | 12-episode instrument pilot、人工复核、统计与冻结材料 | 自动等同于正式测试集或已证明 novelty |
| E1/E2 | lmms-eval 集成、冻结 evaluator 后的策略搜索 | 首版核心依赖 |

### 1.3 暂时不做

不训练视觉模型；不部署 Neo4j、复杂多 Agent 框架或微服务；不恢复全部 CyPortQA；不批量下载 TB 级天气数据；不启动 AutoResearch；不以 LLM judge 替代时间、状态或 GIS 确定性判断。

**优先复用“有边界的功能”，不把多个完整 benchmark 强行拼成一个系统。**

<a id="s2"></a>
## 2. starter 实际审计与优先修复

### 2.1 本次已核实的起点

附件 `disastertrace-starter.zip` 内含约 55 KB 原始文件；包名 `disastertrace`，版本 `0.1.0`。已直接检查源代码并执行：

```bash
PYTHONPATH=src python -m pytest -q
PYTHONPATH=src python -m disastertrace.cli validate-episode examples/episode.json
python -m compileall -q src
```

结果：**6 个现有测试通过**；demo 为 **2 个文本 artifact、2 个 checkpoint**；编译检查通过。审计环境为 Python 3.13.5、Pydantic 2.13.4、pytest 9.0.2。没有执行真实模型 API、完整上游数据构建、GIS 集成或新建空环境安装测试。

这些结果仅说明小型 starter smoke tests 通过，**不证明下列缺陷不存在**。如带有执行包，详细记录位于 `docs/STARTER_AUDIT.md` 和 `audit_artifacts/`。

### 2.2 已有文件与真实能力

| 当前文件 | 已有能力 | 尚未具备 |
|---|---|---|
| `models.py` | 基础模型、时间区间、简易 StateLedger | 严格类型/额外字段拒绝、完整版本约束、行动 carrier |
| `evidence.py` | strict/optimistic 时间 gate | 来源证明、真实可见性分级、实际输入 exposure 审计 |
| `interventions.py` | withhold、stale、组合干预 | 分支 Gold、重复 arrival 事件、完整语义校验 |
| `runner.py` | fresh request、carrier transform、最终 trajectory | 增量落盘、恢复、分支唯一输出目录、同前缀 fork |
| `adapters.py` | scripted 和基础 API adapter | 完整 capability contract、错误分类、可验证缓存 |
| `policies.py` | new/all evidence、version filter、简易 state | 真正检索、dependency rechecker、B4 verifier |
| `scoring.py` | 基础 transition score | claim–artifact–locator 绑定、时间序列行动评分、强协议检测 |
| `importers/cyportqa.py` | 场景索引 | artifact resolver、来源恢复、稳健数字序列化 |
| `importers/nhc_time.py` | 一种完整 UTC 日期行 | 常见 public advisory 本地日期+UTC摘要格式 |
| `gold/` | 文本/GIS delta 原型 | 可靠 layer filter、投影映射、reviewed Gold |
| `cli.py` | 3 个命令，见下 | `run`、`score`、`report`、配置加载、resume |

当前真正存在的命令只有：

```bash
python -m disastertrace.cli validate-episode examples/episode.json
python -m disastertrace.cli index-cyportqa INPUT_JSON OUTPUT_JSONL
python -m disastertrace.cli parse-nhc-time INPUT_TEXT
```

`configs/pilot.yaml` 当前是示例配置，不是已接通的实验调度器。B3 也只是带状态的简易 policy，**不是已复现的 StateMem rechecker**。

### 2.3 必须优先处理的缺陷

下表“已复现”表示本次运行了专门的探针；“代码确认”表示从实现直接确认，仍需补回归测试。

| ID | 问题 | 状态 | 对应任务 |
|---|---|---|---|
| F01 | scorer 将行动时间窗口无条件施加到 HOLD；允许 monitor 的样例仍被罚 timing | 已复现 | DT-08 |
| F02 | `must_preserve` 比较整个 SlotState，重复 KEEP_UNKNOWN 仅更新 `updated_at` 也失败 | 已复现 | DT-02/08 |
| F03 | span 仅集合匹配；将 A 的 span 名写到 B 上仍可通过 grounding | 已复现 | DT-08/15 |
| F04 | reducer 接受同一 slot 两次更新，最后一个覆盖前一个 | 已复现 | DT-01/02 |
| F05 | NHC parser 无法读取常见“本地日期行+无日期 UTC 摘要” | 已复现 | DT-12 |
| F06 | Pydantic 默认忽略未知字段，拼错键可能悄悄消失 | 已复现 | DT-01 |
| F07 | 输出路径缺少 evidence arm、carrier arm、repeat，同名运行可能互相覆盖 | 代码确认 | DT-05 |
| F08 | request hash 不含最终附加 schema、模型、解码参数等完整请求因素 | 代码确认 | DT-05/06 |
| F09 | 只在整个 episode 结束时写文件，崩溃丢失中间结果 | 代码确认 | DT-05 |
| F10 | scorer 只接收 delivered IDs，无法判断证据是否真正出现在模型请求中 | 代码确认 | DT-03/08 |
| F11 | StateLedger 不保留上一轮 action，无法完整审计行动升级/降级 | 代码确认 | DT-02 |
| F12 | GIS 无条件 union 全部要素并 `.buffer(0)`；混合阈值、线要素会产生错误 | 代码确认 | DT-14 |
| F13 | “新证据”仅 set difference，已见旧版本再次送达的 arrival 无法表达 | 代码确认 | DT-04/16 |
| F14 | API adapter 捕获所有异常重试，可能重复请求永久性错误；格式 repair 未实现 | 代码确认 | DT-06 |
| F15 | 原有 delay 测试未真正检查后续 checkpoint 的释放；名称比覆盖范围更强 | 代码确认 | DT-09 |
| F16 | hash 可空、版本 parent/DAG/适用期/跨 episode 引用未完整校验 | 代码确认 | DT-01/03 |

另检查 `ijson` 返回 Decimal 的序列化、UTF-8 BOM、非数字 lead-time key、重复 JSON key 等；不要未验证就将这些潜在问题写成已复现缺陷。

<a id="s3"></a>
## 3. 开源复用策略

### 3.1 固定优先级

| 资源 | 具体复用点 | 不直接搬入的部分 | 优先级 |
|---|---|---|---|
| CyPortQA [S01] | `source_data/Encoded_senario.json`、NHC 原始材料、港口索引、`models/run_gpt4o.py` 的图像消息思路 | 静态 QA 主循环、QA Gold、事后 impact 字段 | P0 |
| EarthVerse [S02] | `scripts/validate_submission.py` 的检查模式；`run_agent.py` 中日志/包路径校验思路 | 完整多轮会话、通用 shell 执行器、原 benchmark judge | P1 |
| NHC [S03/S04] | 原始 advisory 与 GIS 产品、版本号、正式格式说明 | 将后分析数据当当时输入 | P0 |
| lmms-eval [S05] | 模型后端、媒体编码、task/export、评测接口 | 原 simulator 的真实 current-state 重述 | E1 |
| OpenAI SDK/文档 [S06] | capability-aware 请求、structured output、明确错误处理 | 假设所有兼容网关具有相同 API 能力 | P1 |
| Shapely/GeoPandas [S07] | 确定性几何计算与投影 | 不区分图层的 union / buffer | P1 |
| autoresearch [S08] | 固定评测、原子变更、保留/回退的实验协议 | 训练脚本、修改 Gold 或测试集的自由权限 | E2 |

`VersionRAG`、`StateMem-style` 在首版只作为设计参照。没有核验原实现、参数和协议前，不把自己的简化 baseline 命名为“官方复现”。

### 3.2 上游锁定

以下 SHA 是前序仓库读取记录中的参考版本，不声称是未来执行时的最新版本。Codex 必须在下载时验证 commit 存在并记录实际采用版本；验证失败不静默切到 `main`。

```yaml
schema_version: upstream_lock_v1
sources:
  cyportqa:
    repository: https://github.com/ChenchenMobility/MLLM-Bench-CyPortQA
    requested_commit: 1c38abf339d1471d710f6cb719a5e3874b547077
    resolved_commit: null
    verification_status: pending
    code_license: MIT
  earthverse:
    repository: https://github.com/CuiZHIQ/Earth-Verse
    requested_commit: 6ee72d4094c23306660f503789e8f82b4431ecc6
    resolved_commit: null
    verification_status: pending
    code_license: Apache-2.0
```

只借鉴实现模式时，不建立上游运行时依赖。确实复制代码时保留许可、原路径、commit、改动说明。EarthVerse 的脚本许可与其任务标注许可不同；第三方证据不得因为进入某仓库而被默认重新授权。[S01/S02]

不要为取得几个 metadata 文件完整克隆含大量历史数据的仓库。优先指定 commit 的文件下载或 sparse checkout；下载器有超时、重试上限、缓存和 SHA-256。

<a id="s4"></a>
## 4. 工程布局与环境

### 4.1 最小侵入式布局

**M1 保留现有平铺模块名。** 不要一次把 `models.py` 改为 `models/`、把 `adapters.py` 改为同名包，否则容易产生 import 冲突。功能稳定且确有规模需要后，再独立迁移。

```text
.
├── DISASTERTRACE_CODEX_PLAN.md
├── AGENTS.md                         # 已有则合并，不覆盖
├── IMPLEMENTATION_STATUS.md
├── DECISIONS.md
├── BLOCKERS.md
├── UPSTREAM_LOCK.yaml
├── THIRD_PARTY_NOTICES.md
├── pyproject.toml
├── src/disastertrace/
│   ├── models.py                     # v2 内部 schema、DTO、枚举
│   ├── evidence.py                   # availability gate、exposure
│   ├── interventions.py              # evidence view 和 delivery schedule
│   ├── runner.py                     # checkpoint replay / fork
│   ├── adapters.py                   # provider 请求/响应
│   ├── policies.py                   # baseline policy
│   ├── scoring.py                    # 确定性规则入口
│   ├── cli.py
│   ├── provenance.py                 # 新增：hash、来源与许可
│   ├── persistence.py                # 新增：原子落盘、cache、resume
│   ├── contracts.py                  # 新增：模块接口/协议
│   ├── compiler.py                   # 新增：episode/obligation 编译
│   ├── experiment.py                 # 新增：运行组合与预算
│   ├── reporting.py                  # 新增：聚合、区间与报告
│   ├── fixtures.py                   # 新增：专用 synthetic agents
│   ├── importers/                    # 保留并扩充
│   └── gold/                         # 离线构建；model runtime 禁止读取 Gold
├── configs/
├── examples/                         # 明确标记 synthetic
├── tests/{unit,integration,fixtures}/
├── docs/{data_protocol,scoring_protocol,STARTER_AUDIT}.md
├── scripts/
├── data/{raw,public,manifests}/
├── private_gold/                     # 不进入模型进程的可读目录
├── outputs/                          # 不跟踪大文件/密钥
└── reports/
```

### 4.2 环境选择

开发建议 Python 3.11；这是项目选择，不是声称 starter 已在 3.11 验证。保留合理的跨平台路径支持，至少在选定 Python 版本上执行完整 offline suite。

基础依赖沿用 Pydantic、Typer、PyYAML、ijson；API、GIS、检索分别用 optional extras。M1 不导入 torch、transformers、GeoPandas 或 OpenAI SDK。需要分析表格时再增加 Parquet/DuckDB 依赖。

先选一种 lockfile 方案并记录，不能同时维护互相矛盾的 pip/uv/conda 锁。安装仅在项目虚拟环境内进行，不全局修改 CUDA 或 Python。

```bash
# 若机器已有可用 python3.11：
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m pytest -q
```

无网络且依赖已存在时，可用 `PYTHONPATH=src` 执行测试，但报告必须写“未做新环境安装验证”。依赖缺失不能简单跳过核心测试后标 DONE。

默认 CI 离线测试无密钥；在线下载、GIS、真实 API 分别标记测试组。锁定之后保存 Python、包版本、OS 和 git commit。

<a id="s5"></a>
## 5. 数据、时间与状态契约

### 5.1 三种数据对象必须分开

| 对象 | 允许为空的字段 | 使用者 |
|---|---|---|
| `SourceArtifactCandidate` | availability、hash、未恢复 metadata | 离线 importer / reviewer |
| `ValidatedArtifact` | 非适用的 valid/effective time | episode compiler / runtime |
| `PublicArtifactView` | 仅模型需要的可见字段 | ModelAdapter |

候选资料无法确定 availability 时保存 `null` 和 `missing_reason`，不要构造虚假的精确区间。进入 strict episode 前必须验证合格。`metadata: dict` 不可直接整体拼接到 prompt；采用字段白名单 DTO。

### 5.2 时间字段

```text
issued_at                 发布机构声明的产品发布时间
valid_from / valid_to     该事实、预报或警报适用的时间区间
effective_at              公告中业务状态开始生效的时间
availability_interval    最早公开可见时间的可信区间 [lower, upper]
retrieved_at              本研究获取原文件的时间
scheduled_delivery_at    某实验臂中资料交给 Agent 的时间
```


全部内部时间为 timezone-aware UTC；保留原始时间字符串、时区与解析证据。禁止 naive datetime；拒绝无穷数、NaN、反向区间、同一 episode 内重复 checkpoint ID。checkpoint 时间严格递增；同一时刻的一批资料先合并。

**关键纠正：准确解析 `issued_at` 不等于证明精确 `available_at`。** 仅有 NHC 标题时间的记录不能自动升为 Grade A。需要额外的发布/传输/存档证据，或将实验明确标记为 `issued_time_replay`。

### 5.3 availability 分级与轨道

| Grade | 允许的含义 | 默认用途 |
|---|---|---|
| A | 原文件与可审计公开发布/分发证据匹配；精度足以决定 checkpoint 前后 | strict historical subset |
| B | 公开可见时间能界定为区间；保留不确定性 | interval robustness |
| C | 仅由 issued/effective/上下文推断 | issued-time / assumption-based replay |
| D | 不可恢复 | 候选清单，不进入时间因果评估 |

synthetic fixture 的 availability 由模拟器定义，必须标 `availability_basis=synthetic_schedule`；即使使用 A 枚举，也不得计入真实公开时间证明的统计。

A 的时间也可以是有已知分辨率的短区间，而非伪造到秒的点时间。必须保存 `availability_basis`、`evidence_url`、`evidence_hash`、`review_status`。

```text
strict visible(a, t) = qualified_grade(a) AND availability_upper(a) <= t
optimistic visible(a, t) = qualified_grade(a) AND availability_lower(a) <= t
```

默认 strict config 只接受 A。B 运行单独出表，conservative/optimistic 同时报告。只能证明 issued time 的真实 episode 仍有价值，但不得标成 strict historical availability 或使用“精确历史到达”主张。

未来有效的预报，只要当时已经发布且可见，可以合法输入；未来发布的事实，即使描述过去，也不能提前输入。不得用 `valid_time <= checkpoint` 作为所有证据的通用 gate。

### 5.4 artifact 最低字段

```text
artifact_id, storm_id, subject_scope, product_family, source_provider
source_url, raw_relative_path, sha256, mime_type, byte_size
issued_at, valid_from, valid_to, effective_at
availability_interval, availability_grade, availability_basis
retrieved_at, product_version, version_parent_ids
provenance_record_id, license_record_id
representation: original | standardized_render | normalized_text
```

`artifact_id` 全局唯一，尽量按来源、产品版本和内容哈希构成，不包含 Gold 答案。多个港口可引用同一 NHC artifact，避免按港口重复存储大图。

检查 parent 存在、无环、storm/product/scope 可比、有效期关系有意义。新文件不必然全局替代旧文件：不同有效期、不同灾害变量、不同产品族不能直接 supersede。只有本臂已交付的版本信息才能影响该臂 version filter；不得通过未来 parent/child 元数据泄漏“后面还有更正版”。

### 5.5 Episode 与 delivery schedule

```text
Episode:
  schema_version, episode_id, storm_id, subject_id, subject_location
  source_manifest_id, artifact_ids, checkpoints, replay_track, data_origin

Checkpoint:
  checkpoint_id, at, decision_task_id

DeliveryEvent:
  delivery_event_id, checkpoint_id, artifact_id, representation_id, event_order
```

`data_origin` 必须是 `synthetic` 或 `real`；synthetic source 不使用 NHC/USCG 官方身份伪装。

`DeliveryEvent` 是实际到达的唯一权威来源。旧 `released_artifact_ids` 仅作为迁移输入或派生摘要，不能与 gate/JSON 中另一套时间线并存而相互矛盾。

同一个 artifact 可重复送达，以独立 event ID 表达。`new_content_ids` 与 `arrival_events` 分开：重复文件可以不是新内容，但仍是一次新到达。

### 5.6 固定状态槽位

M1 synthetic 和首个真实域使用少量、明确定义的槽位，不开放任意 `Any`：

```text
warning_status
wind_risk_band
exposure_relation
port_condition
operational_restriction
unresolved_conflict
```

每个 slot 具有自己的值域和空间/时间适用定义。`wind_risk_band` 的概率阈值由公开 rule card 定义，不能从模型结果反向调参。域扩展在 schema 版本化后增加。

`SlotState` 至少包含 `value`、`epistemic_status`、`source_refs`、`validity`、`last_changed_at`。`epistemic_status` 区分 `asserted/unknown/conflict/expired`，不能把 unknown 编码成业务枚举里的 `none`。

### 5.7 显式 carrier

```text
CarrierSnapshot:
  schema_version
  slots
  last_action_commit
  parent_commit_hash
  source_receipt_refs
```

carrier 的语义只能来自模型提交。框架可以按公开通用 reducer 执行模型的 `KEEP/UPDATE`，不能根据 Gold、GIS 或隐藏规则补全 state。保存原始提交 bytes 和 hash；canonical carrier 的派生规则可复现。

公开初始化只允许“所有任务槽位未知、尚未提交行动”等与样本答案无关的模板。

### 5.8 reducer 操作语义

| 操作 | 结构性前提 | 结果 |
|---|---|---|
| ADD | 原槽位不存在或尚未 asserted；值满足类型 | 写入模型提供的新断言 |
| UPDATE | 有可更新状态；显式 old value 与 carrier 一致 | 替换指定 slot |
| KEEP | 不提供相矛盾的新 value | 保留原 semantic state 和 last_changed_at |
| KEEP_UNKNOWN | 该槽位当前未知；不能借此清除既有 asserted 值 | 保持 unknown |
| RETRACT | 显式撤回现有断言并提交引用/理由 | 转为 unknown 或 conflict；保留撤回历史 |

一次 commit 对一个 slot 最多一条操作。整份提交先校验再原子应用。非法提交不得部分写入。框架可以拒绝结构错误，但**不能用隐藏 Gold 判断新值是否正确后再决定接不接受**；错误但结构合法的 belief 要真实保留并评分。

保持语义比较不包括纯审计时间戳；evidence/provenance 的变化单独评分。`last_action_commit` 是 carrier 一部分，支持 HOLD 和 DOWNGRADE 的跨轮判断。

### 5.9 输出和定位引用

状态型模型输出 `CheckpointCommitV2`；无 carrier 的 snapshot 基线输出 `StateAnswerV2`。两者共享当前状态/行动评分，但 snapshot 不强制回答 ADD/UPDATE 的历史区别。

每条 evidence reference 绑定：

```text
claim_or_slot_id + artifact_id + representation_id + locator + role
```

文本 locator 为规范化可见文本中的 `[start_char, end_char)` 和 `text_view_hash`；图像 locator 为归一化点/框或与整张图一致的中性 grid ID，加 `image_view_hash`。

不要要求模型猜隐藏的 `warning_change_gold_01`。可显示统一行号或网格，但不把隐藏 Gold span/region 的位置、名称或支持关系放进 prompt。

### 5.10 Gold obligation

将旧 `required_evidence_any_of` 迁移为不含歧义的**多组充分支持集合**：

```yaml
support_options:
  - all_of:
      - artifact_id: text_02
        locator_requirement: text_claim_01
      - artifact_id: map_02
        locator_requirement: spatial_claim_01
  - all_of:
      - artifact_id: explicit_port_notice_02
        locator_requirement: explicit_statement_01
```

上例含义：第一组必须同时具备文本和地图，或第二组单独提供同一结论的充分明确公告。评分不能把 AND 弄成 OR；存在第二组时，该问题不应被标为“必需跨模态”。

Gold 还包含：可断言值或允许集合、must-update/recheck/preserve/unknown、action-specific 规则、grounding 容差、审核记录、支持来源。允许多个有效 span/region，不要求复刻唯一人工推理路径。

<a id="s6"></a>
## 6. Replay Engine 与隔离

### 6.1 必须区分四种证据集合

```text
L_t = 截至 t 已证明公开可见的 artifact
D_t = 此实验臂截至 t 已交付的 artifact
P_t = 此次请求/本 checkpoint 工具实际返回给模型的 representations
R_t = 本臂 carrier 明确携带、且此前真实展示过的引用来源
```

满足 `P_t ⊆ D_t ⊆ L_t`。`R_t` 必须有本分支历史 presentation receipts；Masked arm 不因 supervisor 还保存旧状态而自动获得 R_t。

scorer 区分：

```text
future citation:            不在 L_t
withheld citation:          在 L_t 但本臂未交付
unseen-current citation:    已交付但既未展示也不在 carrier 合法历史来源
historical-carried citation: 有明确历史来源，可按记忆证据规则使用
```

历史引用存在不等于当前看见旧图原像。把“保留历史结论”与“重新完成视觉定位”分别评估；要求定位时允许通过合法 replay retrieval 重新取图，且记录额外成本。

### 6.2 Fresh request 的边界

每个 checkpoint 建立新的 model messages。可以复用网络连接和模型服务，但不能携带上一轮 assistant 自由文本、provider conversation ID 或 Responses 的 `previous_response_id`。

单个 checkpoint 内工具循环可保留其临时消息；跨 checkpoint 仅显式 carrier 传递状态。trace 留在 supervisor/evaluator，不暴露给模型。

### 6.3 运行接口目标

以下是待实现接口契约，不是声称现有类已具有这些方法：

```python
class ReplayEnvironment:
    def view(self, checkpoint_id: str, arm_id: str) -> "EvidenceView": ...
    def read_public(self, artifact_id: str, checkpoint_id: str, arm_id: str) -> "PublicView": ...

class PromptPolicy:
    def build_request(self, observation: "Observation", carrier: "CarrierSnapshot | None") -> "ModelRequest": ...

class ModelAdapter:
    async def generate(self, request: "ModelRequest", sample_id: str) -> "ModelResponse": ...

class CommitReducer:
    def apply(self, carrier: "CarrierSnapshot", commit: "CheckpointCommitV2") -> "ApplyResult": ...

class TransitionEvaluator:
    def evaluate(self, trace: "CheckpointTrace", gold: "TransitionObligation") -> "TransitionScore": ...
```

`ModelRequest` 不持有 Gold、完整 Episode Python 对象或文件根目录任意读权限。建 dataset/gold 的代码不应在 model runtime 中自动执行。

### 6.4 主循环

```text
验证 manifest 和 hash
→ 获取当前 checkpoint 的公开可见 L_t
→ 根据固定 arm schedule 产生 delivery events / D_t
→ policy 选择资料；生成 P_t 与真实 presentation receipts
→ 从本臂明确 carrier 构造独立请求
→ 先原子保存最终请求清单及 hash
→ 调用 adapter，保存原始响应/usage/error
→ 严格解析并校验结构；不读 Gold
→ 合法则原子 apply，不合法则记录协议失败
→ 原子保存 commit、carrier_after、checkpoint_status
→ 继续下一轮
```

无 Gold 的运行与有 Gold 的评分拆成命令/进程。Oracle arm 是显式 supervisor 注入的诊断例外，日志不得标为普通 model-owned carrier。

### 6.5 失败处理

- 网络暂时错误：限次重试，遵守超时和 Retry-After；取消任务不能被吞掉。
- 401/403、确定的配置/Schema 400：不指数重试；记录配置失败。
- 截断、空响应、拒答、无效 JSON：保留原文与 finish reason；不伪造合法回答。
- baseline 默认 format repair 预算为 0。研究一次 repair 时用独立配置/结果列，保留修复前后及全部成本。
- 模型结构无效：该 checkpoint 标 `invalid_output`，不得跳过分母。继续回放时沿用未被修改的上一 carrier，并加 `carry_forward_after_invalid` 审计标志；不把它算作模型成功 KEEP。
- 数据集/schema/hash 失效：终止该 episode 并报告 dataset failure，不能记成模型失败。
- provider 持续不可用：记录 infrastructure failure；主表单列覆盖率，并报告保守的全计划任务口径，不通过丢弃失败样本抬分。

### 6.6 文件与权限

输出路径至少含以下维度，所有 slug 需净化防路径穿越：

```text
outputs/<run_id>/<model_slug>/<policy_id>/<episode_id>/
  evidence-<evidence_arm>/carrier-<carrier_arm>/repeat-<repeat_id>/
    run_manifest.json
    CP_001/
      request_manifest.json
      request_payload.redacted.json
      response.raw.json
      commit.raw.json
      carrier_before.json
      carrier_after.json
      exposures.json
      status.json
    trajectory.json
```

Gold 不放在被测 Agent 的可读目录。仅字符串 denylist 不是安全沙箱；M1 不提供任意 Python/shell 工具。将来需要执行工具时使用只读公开目录、独立工作目录、网络/进程隔离；同样阻止 symlink 和 `../` 逃逸。

### 6.7 hash、缓存与恢复

`request_hash` 基于最终发送的 payload、输出 Schema、图像实际 bytes/变换参数、provider endpoint identity（不含密钥）、模型版本、全部有效生成参数、工具定义。SDK 添加的 Schema 指令也必须包含。

实验身份另存 `run_key`，含 dataset/rule/policy/replay/scorer 版本、arm、repeat 和前缀 hash。`sample_cache_key = hash(request_hash, repeat_id, sample_index)`；独立重复不得默认复用同一采样结果。

允许同一已完成样本为 resume 命中缓存，不允许把 1 个实际回答复制 3 次称为 3 次重复。确定性和随机模型都遵循此规则。

先写临时文件再 `os.replace`；checkpoint 完成有独立 marker。中断后只恢复输入、前序 carrier、数据和 policy hash 全部一致的 checkpoint。scorer 改变可离线重新评分，但不能悄悄覆盖旧 score 文件。

<a id="s7"></a>
## 7. 数据构建、文本和 GIS Gold

### 7.1 CyPortQA 导入

先只处理 `Encoded_senario.json` 和源文件清单，不加载全部 117k QA 来重建 episode。[S01]

保留上游 `senario` 拼写作为兼容输入，内部统一为 `scenario`。验证 BOM、Decimal/浮点序列化、非数值 key、空 operation、非唯一 storm 名、港口别名和坐标有效性。

读取实际目录名建立 `artifact_resolver.jsonl`，不要假定 modality 枚举与文件夹同名。使用 storm/year/advisory identity 和文件头信息对齐；`12h/24h` 只是候选检索线索，不是正式顺序或发布时间。

禁止把 `impact_prediction`、最终恢复期、最终影响量、事后修改的 best track 放入 `PublicArtifactView`。这些资料可另放 world-reference，访问隔离。

### 7.2 NHC 时间解析

按产品类型选择 parser，不使用单条泛化正则扫描全文的第一个 UTC：

1. 有完整 UTC 日期标题的产品：解析标题区域。
2. 常见 public advisory：解析本地发布时间标题，并用文内 UTC 摘要交叉验证。
3. 已知 NHC 时区缩写按产品规则显式映射；跨日、跨月、跨年换算后核对。
4. WMO header 只有日时分钟时，需要同一产品其他日期字段定位月份；出现占位 `DDHHMM` 不当真实时间。
5. 无法唯一判定时返回候选或错误，不猜。

真实格式回归依据 NHC Ian Advisory 34 [S09]：

```text
1100 PM EDT Fri Sep 30 2022
→ issued_at = 2022-10-01T03:00:00Z
```

其 UTC 信息出现在摘要中，而不一定有完整“UTC + 星期 + 月日年”单行；这正是 starter parser 的缺口。测试还覆盖 12 AM/PM、午夜、日期边界、special/intermediate advisory、`05A` 和 correction。

`issued_at` 解析成功后仍进入 availability 审核，不能自动 Grade A。

### 7.3 USCG 恢复

读取 condition CSV 仅生成候选。原 `ConditionEffectiveTime` 不足以证明首次公开时间。为每条采用记录补原公告链接、发布证据、时区、适用港口、原文引用和哈希。

在 source registry 保存：

```text
condition / effective_at / public_release_evidence
available_lower / available_upper / availability_grade
source_url / content_sha256 / reviewer / review_status
```

第一版允许只采用少量高质量公告；其余行明确缺失。解析到港口别名须人工核实存在歧义的映射；不把通用区域名称直接当港口点。

### 7.4 checkpoint 构建

默认沿全部合格 arrival sequence 回放，再标 critical transition；不可为了提高变化密度跳过关键上下文。若因成本采样 checkpoint，保存选择规则、未选 arrival 以及这些资料何时在后续被送达。

合并窗口是显式配置，合并后 checkpoint 时间不得早于组内最后实际到达的证据。release-delay 诊断使用未被合并抹平的时间粒度。

至少保留升级、撤回/降级、未知、稳定几类；稳定窗口不要全部删掉，否则过度反应 agent 会被错误鼓励。

### 7.5 文本 Gold

固定 `normalized_text` 和 transformation hash；定位 offset 针对模型看见的版本，而非另一份清洗文本。

解析已知 section，包括“摘要”“本次变更”“watch/warning”“hazards”；区分产品头、分隔线和全大写正文，不能把任意全大写句子都当 section。

sentence alignment 只生成候选，不决定真假。识别数值、单位、实体、否定、更正和范围变化；保存原文 offset。改动不必然改变 Gold，必须按 slot 的含义和有效期确定。

人工审核所有关键 transition 的支持关系；非关键机械解析可抽查。没有审核的 candidate 不进入 frozen Gold。

### 7.6 GIS Gold：逐产品实现，不通用 union

NHC GIS 提供多种产品，不保证每种都是面要素或使用同一时间/空间语义。[S03]

实施前必须按文件实际字段选择：storm、advisory、产品族、风速阈值（34/50/64 kt 等）、概率阈值、预报时效、适用区域。不同层不合并。

```text
读图层 → 检查 CRS/geometry type/属性 → 选择同一语义产品
→ 验证修复与异常日志 → 对齐有效期/阈值
→ 分别计算空间关系与 added/removed/stable
→ 生成隐藏 Gold + 标准渲染映射
```

明确要求：

- 经纬度明确为 lon/lat；计算距离、面积和缓冲用适当投影，不能把经纬度当米。
- coastal warning 可能为线；不能 `.buffer(0)` 后按 polygon.contains 检查。
- `make_valid` 可能产生 GeometryCollection/线/空几何，需要显式处理，不能静默丢要素。[S07]
- WSP 嵌套概率等值区域逐阈值选择；不能 union 所有概率面后声称读取了港口风险概率。
- 临界边界给出容差或 ambiguous/boundary 标签，不人为强制 inside/outside。
- 原始 cone 只用于其正确空间含义；不得把进入 cone 当作港口关闭或受灾概率的充分依据。
- “未来 120 小时”随产品发布时间移动；两个不相同有效窗口的变化标 `horizon_shift`，不能一律解释为同一命题被修订。

### 7.7 图像展示与定位

M2 优先从已经合法可见的 GIS 构建**标准化地图**：固定域、图例、港口标记、投影和分辨率，保存像素↔坐标转换。标注 `representation=standardized_render`，不冒充 NHC 当时发布的原 PNG。

原始 PNG 若无法可靠 georeference，可用于答案任务，不进入精细区域定位 strict metric。不要直接把 GIS 坐标当原始 PNG 像素。

所有地图上以同一算法标港口，不能只在有 Gold 变化的样本上加醒目标记。地图 extent 不根据未来风暴轨迹自适应选取；使用预先冻结的地区范围或当时已知信息。

### 7.8 最小 CEDG 与公开规则

隐藏 CEDG 用 JSONL/Parquet：`source_ref, relation, target_slot_or_action, checkpoint_id, rule_id, review_status`。

初版关系仅 `SUPPORTS/SUPERSEDES/REQUIRES_RECHECK/MUST_PRESERVE/LICENSES_ACTION`。

两种图分开：

```text
Gold CEDG：由离线程序和人工确定，不供普通 baseline 读取。
Predicted evidence graph：由模型/公开算法从当前合法输入生成，可作为方法输出。
```

B4 可以读公开的通用 slot dependency / rule card，不能读逐样本 Gold frontier。GIS oracle 和 Gold-scaffold 只能作为清晰命名的诊断上界。

<a id="s8"></a>
## 8. 干预与因果审计

### 8.1 Core B：修改交付，不修改历史世界

同一不可变 raw archive、world reference、checkpoint time grid 生成多个 delivery schedules。默认只延迟/隐藏，不提供早于公开时间的材料。

| 干预 | 改什么 | 验证什么 |
|---|---|---|
| release delay | 指定资料推迟若干 checkpoint 交付 | 不能提前使用；到达后能更新 |
| stale replay | 暂不交付新版本，并明确再次送达旧版本 | 识别当前可证状态与 stale/expired |
| null update | 重复/无关证据事件存在与否 | 与决策无关的信息不造成无关状态变化 |
| modality withholding | 在必要模态诊断子集中移除一类输入 | 降低断言或请求必要证据 |

stale arm 不能只删除 V2 却不给 stateful agent任何 arrival，然后称“模型看了旧版”。到达流需要显示 V1 的 replay event。也要明确隐藏持续到哪个 checkpoint，后续 V3/correction 是否解除。

### 8.2 每个 arm 都有自己的 epistemic Gold

```text
WorldReference(base) = WorldReference(twin)
VisibleEvidence(base, t) 可能不等于 VisibleEvidence(twin, t)
AssertableBeliefGold(base, t) 因此可能不等于 AssertableBeliefGold(twin, t)
```

不能只改变输入、继续用 base obligation 评分 twin。对每个 arm 重算支持闭包、未知、stable frontier 和 action admissibility；所有 Gold 在评测前冻结。

延迟到达后要求旧值还是 UNKNOWN，取决于旧断言适用期/持续性，并非统一答案。没有重新发布新图不表示旧图仍描述当前世界。

Null 控制两臂的时钟与基础 arrival 必须相同；正常时间流逝本身造成的失效在两臂都应发生。无关材料应来自合法范围，不含伪造官方内容。

### 8.3 Core C：从同一个真实 prefix 分叉

**不能把 Actual/Masked/Oracle/Edited 各自从头随机跑一遍再称单变量干预。**

```text
运行到 checkpoint t-1
→ 冻结唯一 prefix snapshot（carrier、exposure、delivery cursor、request/response hashes）
→ 在 t 创建四个独立分支
→ 当前证据、prompt wording、图像次序、工具权限等一致
→ 只替换 carrier 内容
```

输出 trace 中保存 `prefix_snapshot_hash`、`pair_id`、`probe_id`、`carrier_transform_spec`。arm 名只在 supervisor metadata，不直接写入 prompt 提示模型它被 edited/masked。

初版 probe 是单 checkpoint continuation；多步后续传播在独立配置中扩展，保证各分支只使用自己的新提交。

### 8.4 四臂和解释边界

| arm | carrier | 主解释 |
|---|---|---|
| Actual | 模型原提交的状态 | 正常使用情况 |
| Masked | 无 carrier，也无可恢复旧信息的隐藏通道 | 依赖显式历史的程度 |
| Oracle | 独立正确 carrier，格式预算与其他臂匹配 | 记忆错误与当轮推理瓶颈 |
| Edited | 只修改预注册 slot/语义字段 | 是否选择性影响后续依赖项 |

Edited 后“答案变了”并不自动正确，也不证明真实世界因果机制。它测的是**显式输入 carrier 的行为作用**。

区分两个子集：

- `carrier_dependence`：当前证据未覆盖目标旧事实，任务在给定 carrier 条件下定义。评估预定义 downstream frontier 的选择性响应。
- `carrier_corruption_robustness`：carrier 与当前可见证据矛盾。正确行为可能是拒绝坏 carrier 并纠正，不应强制奖励盲目跟随。

增加 sham edit / 无关 slot edit 控制。编辑 source_refs 等多个字段才使 carrier 自洽时，明确它是一个语义变量变更而非声称“只有一个 JSON key”。保留修改 diff。

### 8.5 probe 设计

6–8 个 probe 是首版计划目标，不是已具备的样本。每个 probe 需要：历史支持事实、当前资料不直接重述该事实、预定义依赖前沿、合法历史来源、静态重建对照和人工审核。

若 Masked≈Actual，检查重建捷径，也允许结论为“该任务无需 carrier”；不能以必须证明 memory 有用为理由，只保留让模型失败的测试样本。

独立重复至少 3 次作为 pilot 可选配置；重复是新的模型采样，不是缓存重用。不承诺小样本得到显著性。

<a id="s9"></a>
## 9. 评分契约

### 9.1 不以单一严格乘积分数掩盖测量缺陷

全体适用 transition 报告 `GroundedTransitionPass`；只有完成预注册 carrier audit 的子集再报告 `CausalGCTP`。没有测 `commit_used` 时为 `null/not_evaluated`，绝不默认为通过。

```text
GroundedTransitionPass = protocol_valid
                        × evidence_legal
                        × evidence_exposed
                        × grounding_correct
                        × state_correct
                        × preservation_correct
                        × unknown_preservation
                        × action_admissible
                        × action_timing_correct

CausalGCTP = audited_subset 的 GroundedTransitionPass
            × 预注册且实际测得的 carrier-use criterion
```

不是所有样本都具备精细 locator 或 action window。Gold 必须显式列 `required_components`；缺少所需标注则不能进入对应 strict subset。每张表报告适用样本数和 coverage，避免通过跳过难项抬分。

`model_owned_commit` 的判据是来源与通用 reducer 审计，不是函数参数默认为 True。Oracle arm 明确不计普通 model-owned 成绩。

### 9.2 Grounding

检查每个 claim 与具体 artifact/representation/locator 绑定。locator 必须真实存在、在当前模型能见的 text/image view 范围内，并符合 Gold 的支持关系。

必须拒绝以下捷径：

```text
A 的 span 标到 B 上
只列对的 evidence ID 但 slot 的值与证据无关
把所有 artifact 都引用一遍碰中 required ID
只在顶层 evidence_used 列表提及 Gold，而实际 action 引用错误证据
隐藏更正版的 Gold span 出现在旧版本 locator 上
```

支持 correctness 与证据 precision 分开。广泛错误引用和过大的整图 bbox 不能仅凭覆盖到目标就满分；使用预注册的定位容差/最大面积/支持关系，不能按模型表现调阈值。

### 9.3 State、revision 与 preservation

`state_correct` 对允许值集合和类型评分；不得把“气象风险增大”视为“港口已经关闭”。

`revision_correct` 对状态型 baseline 单列。期待操作根据**该模型实际上一 carrier**与当前 assertable Gold 比较：上一轮已经错了，本轮允许通过正确修复恢复，不强迫其假装上一轮等于 Gold。

`must_preserve` 用语义投影比较：value、epistemic status 和有业务意义的 validity；`updated_at` 或 JSON 键顺序变化不算状态破坏。合法 provenance refresh 单独审计。

缺失 required slot 不自动算正确 unknown。每次任务必须规定输出的必需槽位或允许的稀疏 KEEP 规则；通过公开初始化+通用 reducer得到的 unknown 与未按协议提交明确区分。

### 9.4 Action 与时间

先定义研究输出是建议、风险响应还是官方 condition 摘录。不能将模型建议“准备”写成它有权发布官方关闭命令。

`ActionRule` 以 action 为单位，包括：规则版本、证据前提、适用范围、允许集合、earliest/latest 窗口和依据。没有经审核的安全截止时间，使用 `protocol_target_time` 或只评 admissibility，不虚构 `latest_safe_time`。

时间从 action sequence 计算，而非每一轮直接做“checkpoint 是否在窗口内”：

```text
首次达到目标响应级别的 checkpoint
持续不必要高响应的时长
明确解除证据到达后的 downgrade delay
因证据未到造成的机会缺失，与证据到达后不响应的延迟
```

反例验收：准备窗口从 10:00 开始，08:00 正确 HOLD/monitor 不应因早于 10:00 被罚；11:00 已准备，13:00 继续保持也不能因为超过 12:00 截止而被判“首次准备过晚”。

主时间指标是 replay-clock，不混入 API 网络延迟；wall-clock latency 单列。如成本矩阵未经领域验证，称 benchmark utility/cost，而非真实经济损失。

### 9.5 因果与统计指标

至少包含：

```text
CommitUtility = score(actual) - score(masked)
OracleRecovery = score(oracle) - score(actual)
TargetResponse = 目标依赖项是否按该 probe 定义响应
StableFrontierViolation = 不相关项是否被错误改变
PairConsistency = base/twin 的两边是否都符合各自 obligation
NullStability = 同时钟的 null 对照之间是否保持无关语义
```

分母包含全部预注册 pair/probe；缺失一臂单独标 incomplete，不以仅成功返回的 pair 得出完整结论。

采用 storm-level 配对聚合/cluster bootstrap，不能把同一 storm 的 ports、checkpoints、twins 当独立大样本。8 个 storm 的 pilot 区间可能很宽，要报告样本规模和这种限制。

### 9.6 Judge 的受限职责

M1 主评分全部 deterministic。后续 LLM judge 只用于难以枚举的自由文本解释，输入脱敏模型身份，保存 rubric、版本、原始 verdict，与人工分歧抽查。

Judge 不决定发布时间、几何覆盖、版本排序、deadline 或 JSON 操作合法性；judge 结果不反馈给主模型来改写同次已冻结的答案。

<a id="s10"></a>
## 10. baseline 与模型接口

### 10.1 baseline 共用一个 runtime

| ID | 正式命名 | 输入 | 输出 | 说明 |
|---|---|---|---|---|
| B0 | NewEvidenceSnapshot | 当前 arrival 内容，无 carrier | 完整 StateAnswer | 对当前信息任务评分，memory-only probe 只作重建诊断 |
| B1 | FullLegalHistory | 本臂全部历史可见材料，无 carrier | 完整 StateAnswer | 不含未来，也不得看到被 withheld 的资料 |
| B2 | AsOfVersionFiltered | 本臂已见且当前适用的版本，无 carrier | 完整 StateAnswer | 初版未检索时不叫 RAG |
| B3 | StructuredStateRechecker | 新到达 + 自有 carrier + 公开 dependency rules | Commit | 必须真正实现 recheck，而不只是改 prompt 名 |
| B4 | EvidenceGroundedRevision | 新到达 + carrier + 模型预测 grounding + 公开 verifier | Commit | 不读 Gold CEDG；增加工具/模型调用计入预算 |

可添加 `B2_RAG` 作为单独任务：先 metadata filter 再 BM25；只在 dev 选择 top-k。训练 embedding 或 Neo4j 不在首版依赖。

比较共用相同 backbone、输入分辨率、已定义的 token/tool/repair 预算。Full History 超过 context 时使用预先冻结截断策略并报告截断，不能从 Gold 选择要保留的段落。

oracle relevant-evidence、oracle GIS、oracle carrier 独立命名为上界诊断；不与普通 agent 混排名。

### 10.2 Adapter capability contract

```text
provider / endpoint / model_requested / model_resolved
supports_images / supports_multiple_images
supports_structured_outputs / supported_output_schema_mode
supports_temperature / supports_seed / max_token_parameter
request_timeout / transport_retry_limit / tool_support
```

真实能力通过配置与小型 smoke test 核验。模型 ID、base URL、API key 从配置/环境变量读取，禁止把此前聊天中的凭据写入任何文件。

OpenAI 官方 strict structured output 对 JSON Schema 有要求，且 refusal/truncation 仍需处理。[S06] 内部 schema 与 provider 输出 schema 分离：输出对象关闭 extra keys；可空字段用 nullable required；避免直接把 `Any`、开放 dict 或所有复杂内部状态转换成 strict schema。

Chat Completions 和 Responses 是不同 wire format。先完成一个可用 adapter；另一个用独立 serializer，不混用 `image_url`/`input_image` 字段。兼容网关不自动等同官方端点；unsupported 参数按能力配置处理，不静默降级后仍声称同条件。

多图请求每幅图都带中性 artifact 标识并保持固定排列；记录原图 hash、发送图 hash、裁剪/压缩/分辨率。文件缺失/坏图/不支持图片属于明确错误，不能改为只送文字继续报告 full-modal。

### 10.3 Request 与 response

```text
ModelRequest:
  fixed_protocol, checkpoint_task, visible_evidence_parts, carrier
  response_schema_id, generation_config, public_rulecard_ids

ModelResponse:
  raw_provider_response, raw_model_text, parsed_output_or_null
  refusal, finish_reason, error_class, effective_parameters
  usage, wall_latency, provider_request_id, repair_records
```

普通 prompt 中不包含 evaluator score、arm 名、hidden Gold、未送达文件清单或 probe 的 expected outcome。

### 10.4 网络与付费开关

配置 `allow_paid_api: false` 是默认值。有环境密钥不等于已授权无限批量调用。`run --dry-run` 必须输出模型调用上限、图像/token估算、重试/repair预算。

真实模型执行要求用户设定 `allow_paid_api: true` 并给出最大调用数/最大 token 数；模型价格无法核验时费用字段为 unknown，不自动填 0。

上游公开资料下载与模型推理联网分开控制。被测 agent 不允许访问实时网络来绕过 as-of archive。

<a id="s11"></a>
## 11. CLI、配置与产物

### 11.1 目标命令：均需实现与测试后才可执行

下面不是 starter 现有命令。保留现有 `validate-episode/index-cyportqa/parse-nhc-time`，新增：

```bash
python -m disastertrace.cli doctor --offline
python -m disastertrace.cli demo --output work/demo
python -m disastertrace.cli validate-data --bundle work/demo/public --strict
python -m disastertrace.cli run --config configs/offline_demo.yaml --dry-run
python -m disastertrace.cli run --config configs/offline_demo.yaml
python -m disastertrace.cli score --run-dir outputs/offline_demo --gold-root work/demo/private_gold
python -m disastertrace.cli report --scores outputs/offline_demo/scores --out-dir reports/offline_demo
python -m disastertrace.cli verify-run --run-dir outputs/offline_demo
```

后续新增：

```bash
python -m disastertrace.cli fetch-sources --config configs/sources.yaml
python -m disastertrace.cli audit-sources --manifest data/manifests/source_manifest.jsonl
python -m disastertrace.cli compile-episode --spec configs/episodes/real_001.yaml
python -m disastertrace.cli compile-twins --episode data/public/episodes/real_001.json
python -m disastertrace.cli prepare-review --episode data/public/episodes/real_001.json
python -m disastertrace.cli causal-audit --config configs/causal_pilot.yaml --dry-run
python -m disastertrace.cli freeze --config configs/freeze.yaml
```

CLI exit codes 统一：0 成功、2 配置/验证失败、3 外部依赖阻塞、4 运行失败。除 `doctor` 外不以吞异常并返回 0 来“通过”。

### 11.2 目标运行配置示例

```yaml
schema_version: disastertrace_run_v2
run_id: offline_demo
mode: offline
allow_paid_api: false

paths:
  public_bundle: work/demo/public
  output_root: outputs
  # 普通 run 无 gold_root；只有 score/明确 Oracle supervisor 接受 Gold。

replay:
  track: synthetic_protocol
  gate_mode: strict
  allowed_grades: [A]
  fresh_session_per_checkpoint: true
  carry_raw_conversation: false
  unsupported_source_policy: fail

models:
  - id: fixture_rule_reader
    adapter: fixture_rule_reader
    response_cache: resume_only

policies: [B0, B1, B2, B3]

evidence_arms: [natural, delay_one, stale_one, null_control]
carrier_arms: [actual]

budgets:
  max_concurrent_episodes: 2
  transport_attempt_limit: 1
  max_paid_model_calls: 0
  max_output_tokens_per_call: 1800
  format_repair_calls: 0
  semantic_repair_calls: 0

execution:
  repeats: 1
  fail_on_hash_mismatch: true
  persist_each_checkpoint: true
  resume: true
```

为减少笛卡尔积浪费，experiment compiler 产生明确 `run_matrix.jsonl`，只调度可适用组合；不能把全部 Core B arms × 全部 Core C arms × 全部模态消融自动相乘。

### 11.3 运行产物

每次运行含：最终配置、dataset/upstream/rule/policy/schema hashes、模型能力记录、请求/响应/commit、presentation receipts、action序列、失败状态、真实调用统计。

每次评分含：每 checkpoint 的 audit vector、每 transition 的 reason codes、每 pair/probe 指标、样本纳入/排除理由、评分器版本、各项 coverage。

每次报告含：

```text
summary.md
per_checkpoint.jsonl
per_transition.csv
per_pair.csv
per_probe.csv
error_taxonomy.csv
coverage.json
cost_and_latency.json
figures/       # 至少 score breakdown、paired effects 等适用图
```

完整原文保存在受控位置；API key、authorization header、网关 token 必须从日志与报告清除。不要把完整私有 Gold 混入可发布报告。

<a id="s12"></a>
## 12. 分阶段任务单

**执行依赖，不按数字机械顺序。** 特别是 DT-07 的完整 CLI 验收依赖 DT-08/09。所有任务初始状态 TODO；本文件没有把计划任务预勾成完成。

### 12.1 任务依赖总表

| ID | 任务 | 前置依赖 | 阶段 |
|---|---|---|---|
| DT-00 | 基线审计、工作区与状态文档 | 无 | M0 |
| DT-01 | Schema V2、验证、迁移 | DT-00 | M0/M1 |
| DT-02 | 事务 reducer 与完整 carrier | DT-01 | M1 |
| DT-03 | provenance / gate / exposure | DT-01 | M1 |
| DT-04 | delivery schedule / replay | DT-02/03 | M1 |
| DT-05 | trace、fingerprint、cache、resume | DT-04 | M1 |
| DT-06 | adapter 能力与请求序列化 | DT-01/03/05 | M1 |
| DT-08 | deterministic scorer 修复 | DT-01/02/03/05 | M1 |
| DT-09 | fixtures 与负面对照 | DT-04/05/08 | M1 |
| DT-07 | CLI 离线闭环、基础报告 | DT-05/06/08/09 | M1 |
| DT-10 | 上游 lock / downloader | DT-00 | M2，可并行 |
| DT-11 | CyPortQA 索引和 artifact resolver | DT-01/10 | M2 |
| DT-12 | NHC 产品 parser / 时间审计 | DT-01/10 | M2，可并行 |
| DT-13 | USCG 来源与港口映射 | DT-11/12 | M2 |
| DT-14 | GIS、标准渲染与定位 | DT-03/11/12 | M2 |
| DT-15 | Gold/obligation/review compiler | DT-08/11/12/13/14 | M2 |
| DT-16 | matched twins 与分支 Gold | DT-04/08/15 | M3 |
| DT-17 | 同 prefix Core C 因果审计 | DT-05/08/15 | M3 |
| DT-18 | 强 baseline 和公开 verifier | DT-06/08/14/15 | M3 |
| DT-19 | 实验预算、批量调度、统计报告 | DT-07/16/17/18 | M3/M4 |
| DT-20 | 12-episode pilot 与冻结 | DT-19 + 人工审核 | M4 |

### DT-00：基线审计与工作区

**文件：** `IMPLEMENTATION_STATUS.md`、`DECISIONS.md`、`BLOCKERS.md`、`docs/STARTER_AUDIT.md`。

- [ ] 检查 git status、目录、现有 AGENTS.md、Python 和依赖；记录用户未提交修改。
- [ ] 复跑第 2 节真实存在的三个验证命令；保存 stdout、stderr、exit code。
- [ ] 检查 starter archive/hash 是否匹配；不匹配则按当前文件重新审计，不覆盖。
- [ ] 复核 F01–F16，建立“已复现/代码确认/待验证”的状态。
- [ ] 创建任务表和决策记录，标明 M1 为默认目标，API 关闭。

**验收：** 能指出现有三个 CLI 命令、两轮 demo、6 项 baseline tests 及其覆盖不足；不会称现有 config 已可运行完整 pilot。

### DT-01：Schema V2 与迁移

**文件：** `models.py`、`contracts.py`、`tests/unit/test_schema_v2.py`、迁移脚本。

- [ ] 定义 Candidate / ValidatedArtifact / PublicArtifactView；统一可选值与错误类型。
- [ ] 模型输出拒绝额外字段；定义 slot 枚举和值域，禁止开放 Any 穿入 provider Schema。
- [ ] 检查唯一 ID、timestamp、validity、episode引用、版本 DAG、hash格式。
- [ ] 定义 CarrierSnapshot、DeliveryEvent、ExposureReceipt、ActionRule、支持集合语义。
- [ ] 将原 `episode.json` 迁移成明确 synthetic v2；保留原 fixture用于兼容迁移测试。
- [ ] 导出 JSON Schema，并测试无隐式丢字段、字符串布尔值/NaN不被误接受。

**验收：** F04/F06/F16 相关反例被拒绝；旧示例可显式迁移，旧数据不会静默当新版读取。

### DT-02：事务 reducer

**文件：** `models.py` 或新增 `state.py`，`tests/unit/test_reducer.py`。

- [ ] 按 §5.8 定义操作；一次 slot 一条更新。
- [ ] 校验整份提交后原子应用；失败前后 carrier hash 相同。
- [ ] KEEP/KEEP_UNKNOWN 不因“过了一小时”改变语义更新时间；审计访问另记录。
- [ ] 保留上一轮 action、状态 lineage 和来源；不读 Gold。
- [ ] 接受结构合法但事实错误的状态，确保错误能传播并被测出，而非 harness偷偷修正。
- [ ] 实现 invalid-output 保持上一 carrier 的显式策略，不把它算成功。

**验收：** F02/F04/F11 修复；错误 old_value、重复slot、部分有效提交有回归测试；示例 carrier 前后可逐字/逐字段追踪。

### DT-03：来源、可见性与 exposure

**文件：** `provenance.py`、`evidence.py`、`tests/unit/test_visibility.py`。

- [ ] 验证文件 SHA-256、size、MIME 与数据根目录；拒绝逃逸、坏图和缺失文件。
- [ ] strict 默认 A；B 明确作为单独 interval 轨道；unknown availability fail closed。
- [ ] 区分 L/D/P/R；public DTO 不含 future index、Gold metadata 或隐藏支持关系。
- [ ] 为真实送入模型的文字、图像、工具结果生成 ExposureReceipt。
- [ ] 历史 carrier citation 与当轮原始图文 exposure 分开。
- [ ] 验证未到达版本不得影响 supersession过滤。

**验收：** 未来、withheld、未展示、历史carry四种引用可被区分；修改文件一个字节必须使validate/run失败。

### DT-04：到达事件与 replay

**文件：** `interventions.py`、`runner.py`、`tests/unit/test_delivery.py`。

- [ ] 使用 DeliveryEvent 替代仅 set difference 表达 arrival。
- [ ] 实现自然时间线、暂时withhold、延迟释放和旧版本再次到达。
- [ ] 每个 checkpoint 独立请求；跨轮只传 carrier，不传旧原文聊天。
- [ ] 将 clock、availability gate、arrival schedule、policy selection四层分开。
- [ ] 接收重复到达但new-content为空；仍能进行null/stale对照。
- [ ] 组合干预有固定优先序；冲突规格在编译时拒绝。

**验收：** 延迟样例至少3个checkpoint，先隐藏后真正释放；stale样例确认旧资料确实呈现在目标请求中。

### DT-05：trace、cache、resume

**文件：** `persistence.py`、`runner.py`、`tests/integration/test_resume.py`。

- [ ] 输出目录包含model/policy/episode/evidence_arm/carrier_arm/repeat；净化slug。
- [ ] 请求发送前保存manifest；每轮原子保存响应、commit、状态和完成marker。
- [ ] 保存carrier_before/after和实际applied transform，非目标checkpoint不得误记为edited。
- [ ] 实现最终wire payload fingerprint、sample cache identity、版本化评分路径。
- [ ] 模拟CP2后崩溃；恢复时从CP3继续，并验证历史 hash。
- [ ] 初始化prefix snapshot保存接口，后续DT-17使用。

**验收：** F07/F08/F09修复；同run_id跑两个arm两个repeat无覆盖；一个模型/参数/schema变化不能误命中旧请求缓存。

### DT-06：Adapter 与 provider 边界

**文件：** `adapters.py`、`tests/unit/test_adapter_payload.py`、可选provider模块。

- [ ] ScriptedAdapter保留；增加记录最终payload的FakeProvider，测试无实际网络。
- [ ] 定义统一Response envelope、capabilities、超时、usage和错误分类。
- [ ] 一个可靠的多图API serializer；图片身份、hash、分辨率与文本保持对应。
- [ ] strict Schema与prompt-only JSON mode分别配置；处理refusal/截断/空响应。
- [ ] 仅暂时错误限次重试，区分format repair与semantic repair。
- [ ] 不把SDK默认重试与自己的重试无控制叠加；总请求数和重试计入预算。
- [ ] 禁用跨checkpoint provider conversation；关闭客户端资源。

**验收：** FakeProvider覆盖200、429、5xx、401/403、Schema400、timeout、invalid JSON、取消；无密钥仍可运行M1。

### DT-08：确定性评分器

**文件：** `scoring.py`、`tests/unit/test_scoring_v2.py`、`docs/scoring_protocol.md`。

- [ ] 按 §9拆分protocol、legality、exposure、grounding、state、preservation和action。
- [ ] support_options实现OR-of-AND，不退化为“碰到任意artifact就通过”。
- [ ] claim–artifact–view–locator绑定；从所有实际使用位置收集引用。
- [ ] preserve用语义投影，missing slot和unknown有明确规则。
- [ ] action-specific deadline由序列计算；HOLD不被别的action窗口误罚。
- [ ] 普通GTP与causal subset分开；未测component=null，附coverage。
- [ ] 定义reason_codes，失败不抛异常直接让整批评分中断；数据错误另行拒绝。

**验收：** F01/F02/F03/F10有明确失败→通过回归；gold-only错误绑定、空白输出、全引用刷分都不能过关。

### DT-09：Fixture agents 与测量验证

**文件：** `fixtures.py`、`tests/fixtures/`、`tests/integration/test_instrument.py`。

- [ ] 构建4个明确synthetic episode：升级、撤回、版本冲突、null稳定。
- [ ] 至少3个checkpoint用于delay验证；增加一组带中性几何图像的offline fixture。
- [ ] 实现rule-reader、no-op、stale、overreact、future-citing、misattributed、invalid-output。
- [ ] Oracle fixture只能在专门评测器测试中读取Gold，标为test oracle；普通rule-reader不读Gold。
- [ ] 模拟坏carrier、无关slot edit、缺少必要模态、重复到达。
- [ ] 断言具体reason_code，不仅断言总体score范围。

**验收：** Oracle ceiling与每类负面对照有预期差异；不是靠if agent_name赋分；把agent输出文件改名不改变分数。

### DT-07：完整离线 CLI

**文件：** `cli.py`、配置模型、`reporting.py`基础实现、`tests/integration/test_cli.py`。

- [ ] 实现doctor/demo/validate-data/run/score/report/verify-run及help。
- [ ] 所有配置走严格Pydantic validation；删除或迁移未使用的旧config键。
- [ ] run普通入口无Gold权限；score单独接收Gold。
- [ ] dry-run输出精确run matrix与最大调用预算，不真正调用模型。
- [ ] demo创建public/private分离目录与一份可运行配置；报告显著标synthetic。
- [ ] README复制命令可从干净目录运行，不依赖审计容器路径。

**M1验收：** §11.1第一组命令完整执行，产物存在且内容非空，offline无需网络/GPU/API。

### DT-10：上游获取与锁定

**文件：** `UPSTREAM_LOCK.yaml`、`scripts/fetch_sources.py`、`provenance.py`。

- [ ] 验证参考commit，记录resolved SHA，不使用漂移main作为正式来源。
- [ ] 根据manifest按文件获取，缓存、重试上限、下载大小预算、hash和来源记录。
- [ ] 下载失败记录真实HTTP/权限错误；不生成同名假数据。
- [ ] 确认复制代码与原材料许可，更新THIRD_PARTY_NOTICES。
- [ ] 离线可读取已下载缓存；CI用本地HTTP/fake transport测试，不依赖外网。

**验收：** 同manifest重复运行幂等；上游hash变化fail closed；缺网络只阻塞数据获取，不阻塞M1。

### DT-11：CyPortQA 候选与 resolver

**文件：** `importers/cyportqa.py`、`importers/port_aliases.py`、resolver脚本。

- [ ] 流式解析大JSON，支持BOM与Decimal；fallback设明确大小上限。
- [ ] 规范storm ID与port ID；保留原始别名、坐标及映射来源。
- [ ] 读取实际文件树生成modality→path映射；检查runner示例与实际路径差异。
- [ ] 候选输出包含版本数、图文覆盖、operation候选、时间缺失率。
- [ ] 不把生成的场景描述/operation future entries冒充当时官方证据。
- [ ] 生成20个以内的首轮候选清单，选择基于资料质量而非目标模型失败率。

**验收：** 输入源文件hash可追踪；未知字段不丢；至少一个候选能映射到原始advisory和图像。

### DT-12：NHC 产品与时间恢复

**文件：** `importers/nhc_time.py`、`importers/nhc_products.py`、真实格式fixture。

- [ ] 实现完整UTC标题、本地标题+UTC摘要、advisory编号与storm ID提取。
- [ ] 覆盖跨日、跨年、12AM/PM、intermediate/special/correction。
- [ ] 当前issued/valid/forecast horizon分别解析并保存支持offset。
- [ ] 解析多结果冲突时报ambiguity，不挑最容易通过的时间。
- [ ] availability proof独立流程；header仅支持issued-time轨道。
- [ ] 保存来自[S09]等公开格式的最小回归fixture及原始URL/获取记录。

**验收：** F05修复；2022-09-30 23:00 EDT正确归为2022-10-01 03:00 UTC，且不因此自动A级。

### DT-13：USCG与行动依据

**文件：** `importers/uscg.py`、`data/manifests/uscg_source_recovery.*`。

- [ ] condition CSV只当索引；恢复采用记录的原公告和public-release证据。
- [ ] 区分effective与published；时间精度不足保存区间，不编秒数。
- [ ] 核对公告适用港口、区域、例外权限，保留文本offset。
- [ ] 梳理官方condition描述与模型建议动作的区别。
- [ ] 生成审核表，未审核标pending；无原文/发布时间证据为BLOCKED。

**验收：** 至少一条拟采用公告有完整证据链；没有则真实action子集不冻结，NHC-only开发仍继续。

### DT-14：GIS 与地图表示

**文件：** `gold/gis_delta.py`、`gold/render_map.py`、GIS配置与测试。

- [ ] 按产品schema过滤类型、阈值、时效；不能对全部图层无条件union。
- [ ] 加CRS/单位/geometry type检查、修复日志、边界容差。
- [ ] polygon、coastal line分支；未知几何类型拒绝而不是变空集。
- [ ] 比较相同valid window，否则显式horizon_shift。
- [ ] 标准化渲染与像素坐标转换，保存原始/渲染/transform hash。
- [ ] 发布给模型的图片与隐藏GIS标签严格对应；不暴露答案提示区域。

**验收：** 已知投影的synthetic geometry给出精确inside/outside/boundary；真实一个产品能复算；坏CRS和混合阈值被拒绝。

### DT-15：Gold、CEDG与人工审核

**文件：** `gold/text_delta.py`、`gold/dependency_rules.py`、`compiler.py`、review exporter。

- [ ] normalized text有offset映射，句子diff仅生成candidate。
- [ ] 构建支持集合、可断言值、未知、stable/recheck frontier和action-specific规则。
- [ ] 每条Gold关联source hash、rule version、review记录；区分derived与human-adjudicated。
- [ ] 生成HTML/JSON审核材料，显示每checkpoint材料、候选变化、理由；不需复杂web服务。
- [ ] reviewer输入采用独立结构；禁止Codex自行填写虚构的两位审核者。
- [ ] 数据compiler输出public episode和private obligation，不将Gold注入普通输入。

**M2验收：** 1个真实episode具备可浏览证据链。人工未完成时工程标DONE但`real_gold_release`仍BLOCKED，不能混称整个M2已完成。

### DT-16：Matched evidence twins

**文件：** `interventions.py`、`compiler.py`、`tests/integration/test_twins.py`。

- [ ] 从immutable base manifest编译delay/stale/null，再扩展withholding。
- [ ] 各arm重新计算assertable Gold、support sets与时窗，保持物理world-reference不变。
- [ ] paired diff仅含预注册delivery改动；检查是否有其他文件内容/metadata变化。
- [ ] 冻结affected/unchanged frontier和最早允许分化时间。
- [ ] 处理无效旧资料expiry、后继版本解除隐藏、重复arrival。

**验收：** Oracle fixture在两边都能通过；同一base Gold直接用于twin的错误被测试发现；delay不能产生公开时间前的输入。

### DT-17：Carrier causal audit

**文件：** `runner.py`、`experiment.py`、`scoring.py`因果聚合。

- [ ] 保存t-1单一prefix snapshot并fork，而不是重新独立采样四份历史。
- [ ] actual/masked/oracle/edited拥有相同current request body，除carrier外不得有arm提示。
- [ ] probe配置包含target slot、expected dependency frontier、sham control和实验解释类型。
- [ ] masked不能借previous_messages、日志、工具、缓存或旧receipt自动恢复状态。
- [ ] 每repeat有独立采样标识；记录request equality检查。
- [ ] 区分“依赖carrier”与“抵抗损坏carrier”，输出不强求单方向变化。

**验收：** prefix hash全相同；only-carrier-diff验证通过；secret历史token在masked payload中不出现；无关slot改动不被当目标因果成功。

### DT-18：强baseline与RevisionGuard

**文件：** `policies.py`、公开rulecard、verifier模块。

- [ ] B0/B1/B2用完整StateAnswer，B3/B4用Commit；统一当前状态/行动评分。
- [ ] B2区分version-filtered与真正BM25 RAG；后者另命名、参数只在dev选择。
- [ ] B3按公开依赖图要求重新检查受影响项，不能读取Gold affected frontier。
- [ ] B4生成claim-grounding并检查已见ID、Schema、版本适用、显式冲突；最多一次修复为独立预算。
- [ ] runtime verifier不访问逐样本正确答案、不调用隐藏GIS oracle；修复前后均保存。
- [ ] 增加text-only/vision-only/full/mismatch输入条件，重新审核是否真的需要跨模态。

**验收：** code路径可证明普通baseline不读Gold；方法额外调用和token报告完整；不把提示词名字变化冒充完整新算法。

### DT-19：实验编译、预算与统计

**文件：** `experiment.py`、`reporting.py`、run matrix配置。

- [ ] episode内串行；episode/model/arm之间受Semaphore与provider限额控制。
- [ ] 预生成run_matrix；causal子集不与所有消融做无意义笛卡尔积。
- [ ] dry-run列出调用上限和授权状态；max_paid_calls=0时不能访问模型API。
- [ ] report区分synthetic/real、A/B/issued、模型/基础设施/数据失败。
- [ ] storm-level聚合、paired effects、cluster bootstrap、coverage和成本。
- [ ] 增加selector-scorer-version审计，避免只输出最佳seed或删失失败。

**验收：** 同一raw trace换scorer可独立重算；小型手算fixture与统计结果一致；并行运行不改变合法时间线。

### DT-20：12-episode instrument pilot 与冻结

**文件：** dataset card、freeze manifest、splits、pilot_report、release checklist。

- [ ] 目标12 episodes、至少8 storms、48–72 checkpoints、20+ meaningful transitions；不足就报告实际数量。
- [ ] 确保稳定/未知/撤回/跨模态/冲突覆盖；不能通过复制同storm扩大独立样本数。
- [ ] 两名审核者的行动/关键Gold review与分歧裁决；缺人则release blocked。
- [ ] storm-level划分，全部ports/checkpoints/twins/identity variants同split；文件hash重复另做检查。
- [ ] 所有已反复debug的pilot数据视为开发数据，不能改名叫hidden test。
- [ ] 冻结raw、parser、schema、rules、Gold、splits、evaluator及输入表示配置；生成checksum清单。
- [ ] 完成限制、许可、样本质量与模型失败分析，不自动上传公开仓库。

**M4验收：** release validator无硬错误，报告可复算；未满足的数据覆盖或审核条件明确呈现，不能通过降低Gate并保留原宣传词过关。

<a id="s13"></a>
## 13. 测试矩阵与验收

下面是最低**行为覆盖**，不是要求为了凑数量写空测试。每一组必须有正例与反例；关键错误应断言reason_code和状态不被污染。

| 测试 ID | 场景 | 预期 |
|---|---|---|
| T01 | naive time、反向区间、重复checkpoint | schema拒绝 |
| T02 | 未知输出字段、拼错slot、不合法值 | 不静默忽略/类型强转 |
| T03 | parent缺失、循环、跨产品错误supersession | 编译失败 |
| T04 | 文件改1字节、路径穿越、symlink逃逸 | hash/权限校验失败 |
| T05 | availability只知道区间 | strict用upper、optimistic用lower |
| T06 | accurate issued但无availability proof | 不自动Grade A |
| T07 | 未来valid forecast已发布 | 允许；未来发布的过去事实仍禁止 |
| T08 | 新版本尚未公开/未交付 | 不可通过metadata删除当前已见旧版 |
| T09 | 同slot两次UPDATE、old_value不匹配 | 原子拒绝，carrier不部分修改 |
| T10 | KEEP_UNKNOWN跨时刻但语义不变 | preservation通过 |
| T11 | asserted被KEEP_UNKNOWN擦掉 | 协议拒绝，需显式RETRACT |
| T12 | source ID在delivered但没展示 | 不算当前可见证据 |
| T13 | source ID由明确历史carrier保留 | 按历史引用规则识别，不误罚未来泄漏 |
| T14 | Masked仍能从previous_response_id/历史对话恢复 | 测试必须发现该隐藏通道 |
| T15 | A的span写到B、伪造offset/hash | grounding失败 |
| T16 | 同一个充分支持组需要文本+图 | 缺任一项不能通过 |
| T17 | 引用所有材料或整图框碰巧含答案 | precision/定位约束阻止刷分 |
| T18 | 输出值与自己的evidence不相符 | state/grounding对应项失败 |
| T19 | 08:00 HOLD、10:00才允许prepare | HOLD不因prepare窗口被罚 |
| T20 | 11:00已prepare、13:00仍维持 | 不被误罚首次行动延迟 |
| T21 | action没有可审核安全时窗 | timing不硬编，coverage明确 |
| T22 | delay有3轮，第二轮隐藏第三轮释放 | 第三轮真实arrival被展示 |
| T23 | 旧版再次送达但内容已见 | arrival保留，new_content可为空 |
| T24 | base与twin时钟/世界相同，信息不同 | 分别使用各自epistemic Gold |
| T25 | null两臂经过同样时间 | 与时间本身有关的expiry处理相同 |
| T26 | Actual/Masked/Oracle/Edited | 同prefix，除carrier以外payload一致 |
| T27 | 无关slot编辑、sham编辑 | 不产生目标错误传播奖励 |
| T28 | 坏carrier与当前证据冲突 | 纠正可能正确，不奖励盲信 |
| T29 | 两arm两repeat同run_id | 目录、cache、usage无互相覆盖 |
| T30 | 仅模型/schema/温度/图像bytes改变 | request fingerprint改变 |
| T31 | 同payload独立repeat | 不复用同一个采样作为多次结果 |
| T32 | CP2后中断、恢复 | 仅继续未完成；旧hash不匹配拒绝resume |
| T33 | 401/403/400与429/5xx | 前者立即失败，后者限次重试 |
| T34 | refusal、truncated、invalid JSON | 保留原文，正确错误状态和成本 |
| T35 | bad image/不支持multi-image | 不静默降级text-only |
| T36 | 真实NHC public header跨日期 | UTC正确，issued与availability分离 |
| T37 | ijson Decimal/BOM/不规则lead-time | 序列化稳定或明确报错 |
| T38 | coastal line、混合WSP层、坏CRS | 不能被误当普通polygon union |
| T39 | fixed render像素↔地理坐标 | 可逆到规定容差 |
| T40 | 相同风阈值、不同forecast valid window | 标horizon_shift，不假装同命题revision |
| T41 | Snapshot没有旧状态 | 不用历史operation精度不公平排名 |
| T42 | 修改agent/model显示名称 | deterministic分数不变 |
| T43 | Oracle fixture vs no-op/stale/overreact | 分数和失败原因符合规则 |
| T44 | dataset hash失败 vs model错误 | 错误类型和分母处理不同 |
| T45 | score重跑相同trace | deterministic指标相同 |
| T46 | same storm多port/twin | split与bootstrap按storm聚类 |
| T47 | config paid=false或调用预算耗尽 | 不发起新的付费调用 |
| T48 | public导出含private_gold、API token | release validator拒绝 |

### 13.1 测试命令约定

为 pytest 注册 `network/api/geo` 等 marker；default offline suite不依赖网络或密钥。下面命令在DT-07建立相应组后必须实际验证：

```bash
python -m pytest -q -m 'not network and not api and not geo'
python -m pytest -q -m geo
python -m ruff check src tests
python -m compileall -q src
```

类型检查采用选定的一致配置，逐步覆盖核心schema/replay/scorer。不要把现有代码所有typing错误用ignore注释掩盖。

跨环境CI至少一套无API的Linux环境；有条件增加Windows路径测试。真实API test跳过时必须报告SKIPPED及原因；不得与offline tests合并宣称“全链路已验证”。

### 13.2 M1 smoke场景

M1应该可以从empty work目录连续运行：

```text
demo → validate-data → run --dry-run → run → score → report → verify-run
```

报告显著写`synthetic fixture results`。至少一个负面对照出现预期失败，至少一项评分定位到明确的`reason_code`。只有全部fixture满分的系统不满足验收。

<a id="s14"></a>
## 14. 并行开发、阻塞与续接

### 14.1 可并行边界

在DT-01接口冻结前，不让多个coding agent同时大改models/runner/scoring。

可分工：

| 工作流 | 主要任务 | 独占文件 |
|---|---|---|
| A：核心回放 | DT-01至DT-07相关工程 | models/evidence/runner/persistence/cli |
| B：资料导入 | DT-10/11/12/13 | importers、source manifest |
| C：评测与Gold | DT-08/09/14/15 | scoring、gold、review输出 |
| D：实验分析 | DT-16/17/18/19 | 接口冻结后按独立PR拆分 |

同一个文件只有一个任务owner；接口改变先写DECISIONS并同步测试。不要由多个agent分别实现不兼容的Artifact类。

### 14.2 BLOCKERS 分类

```text
BLOCKED_NETWORK             原资料/依赖无法下载
BLOCKED_CREDENTIALS         模型密钥或访问权限缺失
BLOCKED_BUDGET              未授权/耗尽付费模型调用
BLOCKED_SOURCE_PROVENANCE   无法证明公开时间或原文归属
BLOCKED_DOMAIN_REVIEW       action/Gold没有人工审核
BLOCKED_DATA_LICENSE        采用/分发条款未明确
BLOCKED_ENVIRONMENT         必需Python/系统库不可用
```

处理方式：保存具体任务ID、实际错误、已完成工作、可继续部分、解除条件。外部条件不能用猜测或造数据绕过；也不应阻塞与其无关的离线工作。

### 14.3 IMPLEMENTATION_STATUS.md模板

```markdown
# Implementation status

Target milestone: M1
Current schema version: ...
Current git commit / working tree status: ...
Paid API enabled: false

| Task | Status | Implementation evidence | Tests executed | Blocker |
|---|---|---|---|---|
| DT-00 | TODO | | | |

## Last completed task
...

## Next executable task
...

## Exact commands and results
...
```

Status仅允许`TODO/IN_PROGRESS/DONE/BLOCKED/FAILED`。存在待审核真实Gold时，可把代码任务与数据交付分别记录，不能把整个里程碑提前DONE。

### 14.4 AGENTS.md最小指令

合并到根目录已有指令，不覆盖用户内容。Codex支持读取仓库层级的AGENTS.md指令，具体行为参见官方说明。[S10]

```text
Read DISASTERTRACE_CODEX_PLAN.md and IMPLEMENTATION_STATUS.md before editing.
Implement incrementally on the starter; do not rewrite the entire repository.
Keep Gold and future evidence out of model requests and tools.
Use fresh messages per checkpoint; carry only the declared model-authored carrier.
Add regression tests before fixing the documented scorer/runtime defects.
Run offline tests first. Paid APIs are disabled by default.
Do not fake source timestamps, human reviews, model runs, or test results.
Do not push, publish data, delete user changes, or alter frozen evidence.
At each task boundary record actual commands, results, blockers, and next task ID.
```

### 14.5 续接指令

```text
读取DISASTERTRACE_CODEX_PLAN.md、IMPLEMENTATION_STATUS.md、DECISIONS.md、BLOCKERS.md。
先确认上次运行结果与当前文件一致，再从Next executable task继续。
不要重新生成研究方案，不要重复已DONE且仍通过验收的任务。
禁止把上次未执行的API/真实数据步骤写成成功；保留原始失败记录。
```

<a id="s15"></a>
## 15. 数据扩展、统计与冻结

### 15.1 选择顺序

```text
synthetic fixtures
→ 1个原始证据可检查的真实episode
→ 4个类型互补的真实episode
→ 12-episode instrument pilot
→ 经独立采样和冻结后的正式benchmark
```

不要预填某个storm“必然包含降级/冲突”。由source audit确认；找不到满足条件的数据，就列actual coverage，不虚构案例。

候选排序主要考虑：时间证明质量、版本完整性、图文可对齐性、状态转移类型、官方公告可得性和审核成本。最终测试选择规则在测试模型运行前冻结。

### 15.2 多模态必要性

每个声称visual-required/conjunction的transition都需证明文本alone不包含同等充分答案，图像也不是仅装饰。公开rulecard不预写该港口的风险结论。

设置text-only、vision-only、full-modal、mismatched-modal条件；比较时可用的时间/版本meta一致，只有目标模态改变。mismatch必须有版本可解释性，不能随机换无关图片后夸大因果结论。

若大部分题可由文字解答，保留数据但调整任务标签/论文主张，不强行声称跨模态推理。

### 15.3 小样本统计

12 episodes不是12个独立storm。报告storms/ports/checkpoints/transitions/pairs/probes各自数量。

单模型三次重复不足以精确描述分布，但可以用于pilot检查采样不稳定；不把API temperature=0称为绝对确定。使用配对差值与storm级区间，不以同storm几十个checkpoint制造很小的p值。

最好同时输出每storm结果，避免总体平均掩盖某一storm占据大部分样本。

### 15.4 冻结前硬Gate

- 原始文件hash全部验证；strict样本没有未经证明的availability假设。
- prompt与tool payload不含Gold、未来文件索引或秘密测试label。
- Base/twin和Core C变更规格可复现，分支差异审计通过。
- 明确action依据与适用范围，不把气象风险自动等同官方关闭。
- 人工review完整，无法仲裁的样本标ambiguous并按预注册规则处理。
- same-storm所有变体同split，重复artifact跨split检查完成。
- 失败/缺失/拒答处理规则固定，不能看到测试结果后更改分母。

### 15.5 停止扩大主张而非停止工程

| 观察 | 应采取的动作 |
|---|---|
| 发布时间无法证明 | 保留issued-time轨道，缩小strict subset |
| action Gold分歧大 | 改为明确admissible/forbidden，不硬标唯一最优动作 |
| Masked无显著影响 | 检查当前证据重述和其他通道；如无问题，诚实报告任务不依赖carrier |
| B3足够强 | 报告该结果，重新定位残余失败，不删掉强baseline |
| 图像非必要 | 修订模态依赖标签，不靠名称维持视觉贡献 |
| scorer各项全为0 | 先检查协议和标注粒度，保留分解指标 |
| 发现Gold错误 | 版本化修订并重算全部受影响模型，不能只修某模型失败样例 |

<a id="s16"></a>
## 16. 延后扩展

### E1：lmms-eval集成

前置：M3协议稳定。优先adapter/exporter，不迁移核心ReplayEngine。

复用[S05]的模型/媒体I/O与任务接口；episode外层仍由DisasterTrace调度。原agentic示例可能把simulator state直接重述给模型，不可移植到carrier审计。

每一个导出任务都需验证request与原生runner等价、Gold不在doc_to_text中、相同input budget、cache包含arm/repeat语义。通过small smoke再扩大模型覆盖。

### E2：AutoResearch策略搜索

前置：M4的dataset/evaluator冻结，独立dev存在，用户授权模型预算。

```text
可改：editable/revision_policy.py、editable/prompt.md、已声明的选择参数
不可改：raw artifacts、时间、Gold、split、evaluator、hidden test、评分口径
```

借鉴[S08]的原子实验思想，每次一个假设和一个策略改动。实现file allowlist、进程权限、受控评测接口、预算限制、keep/revert日志；单纯目录命名为frozen不构成隔离。

对比manual/random/agent search使用相同开发预算，最佳选择只依据dev。未见storm与未见intervention测试只在策略冻结后运行；不能把反复调参过的pilot称hidden test。

本计划不要求复制autoresearch训练部分，也不要求训练任何灾害模型。

### E3：身份屏蔽与新灾种

优先在已有稳定协议上加identity-shielded辅助子集。改名、日期平移、地理表示变化必须保持相对时序/空间关系，且评估难度变化不能自动解释为训练污染。

新灾种应复用EvidenceGate、Carrier、Intervention、Scorer接口，但重新审核数据时间、状态定义和action规则。不要直接把不同benchmark静态QA拼在一起称动态轨迹。

<a id="s17"></a>
## 17. 完成定义与交付模板

### 17.1 M1完成定义

- [ ] 原6个测试保持或经说明迁移；F01–F16中M1范围问题有回归测试。
- [ ] 离线demo闭环实际运行，文档命令可复制。
- [ ] 输出不互相覆盖、可恢复、final request hash完整。
- [ ] Gold与模型输入隔离；checkpoint fresh request测试有效。
- [ ] 正负fixture行为有可解释分数，不只是JSON parsing成功。
- [ ] 新API/GIS接口即使未在线运行，也明确标为未验证，不混报全链路成功。

### 17.2 真实数据里程碑完成定义

- [ ] 每个采用artifact有原文、source与content hash。
- [ ] issued/valid/effective/available区分，无法证明的时间显式降级。
- [ ] 标准化render与官方原图身份明确。
- [ ] 每个采用Gold有支持链与review记录。
- [ ] 没有fake reviewer、fake API response或synthetic冒充real。

### 17.3 每个阶段给用户的报告模板

```markdown
## 已完成
任务ID、模块、对应commit或文件。

## 实际验证
| 命令 | 结果 | 范围 |
|---|---|---|
| ... | PASS/FAIL/SKIPPED | offline/geo/network/api |

## 产物
真实存在的目录和文件。

## 未完成或阻塞
明确区分代码未实现、真实数据缺失、人工审核、API未授权。

## 下一步
下一可执行任务ID及其输入条件。
```

不能把“下载成功”写成“数据正确”，不能把“6 tests通过”写成“测量成立”，不能把“论文写了代码链接”写成“官方实现已复现”。

### 17.4 最终交付清单

```text
可安装Python包和锁定依赖
完整离线fixtures与测试
实际接通的CLI和示例config
可审计真实资料manifest（如已获得）
公开输入/私有Gold分离
自然回放与matched twins
同prefix四臂carrier audit
baseline与provider adapter
确定性scorer和失败原因
预算、trace、cache、resume与统计报告
dataset card、license/provenance、freeze checksums
IMPLEMENTATION_STATUS / DECISIONS / BLOCKERS
```

首要完成条件是**一个真实、可追溯的测量流程**，而不是文件很多、baseline名称很多或模型调用很多。

<a id="s18"></a>
## 18. 参考资源

以下为实施所需的一手资源。链接用于核查源代码、数据格式和API契约；执行时应锁commit/版本。除starter本地审计外，不将外部资料的描述当作本项目已经实现的能力。

### S01 — CyPortQA

- 仓库：https://github.com/ChenchenMobility/MLLM-Bench-CyPortQA
- 模型输入参考：https://github.com/ChenchenMobility/MLLM-Bench-CyPortQA/blob/main/models/run_gpt4o.py
- 数据入口：`source_data/Encoded_senario.json`、`source_data/Port_Condition_Bullitens/uscg_port_conditions_agg.csv`；以锁定版本实际文件树为准。
- 复用范围：索引、原始证据候选、图像消息构造；不直接采用静态QA标签作为动态Gold。

### S02 — EarthVerse

- 仓库：https://github.com/CuiZHIQ/Earth-Verse
- Runner参考：https://github.com/CuiZHIQ/Earth-Verse/blob/main/scripts/run_agent.py
- 提交检查：https://github.com/CuiZHIQ/Earth-Verse/blob/main/scripts/validate_submission.py
- 许可：https://github.com/CuiZHIQ/Earth-Verse/blob/main/LICENSE.md
- 复用范围：有限的包隔离、日志和校验模式；不整体继承会话与评分。

### S03 — NHC GIS

- 官方产品与归档：https://www.nhc.noaa.gov/gis/
- 必须逐产品检查类型、字段、阈值、valid time和档案覆盖；不是所有storm都具有所有产品。

### S04 — NHC archives / data

- https://www.nhc.noaa.gov/data/
- https://www.nhc.noaa.gov/archive/
- 使用实际发布档案构造候选输入；后分析报告与最终best track隔离为world reference。

### S05 — lmms-eval

- https://github.com/EvolvingLMMs-Lab/lmms-eval
- https://github.com/EvolvingLMMs-Lab/lmms-eval/blob/main/docs/releases/lmms-eval-0.7.md
- https://github.com/EvolvingLMMs-Lab/lmms-eval/blob/main/lmms_eval/tasks/tau2_bench/README.md
- 参考agentic接口不等于移植官方完整τ2-Bench；不将seed simulator当DisasterTrace环境。

### S06 — OpenAI structured outputs / SDK

- https://developers.openai.com/api/docs/guides/structured-outputs
- https://github.com/openai/openai-python
- 核查当前模型和endpoint支持的Schema与请求格式；处理额外字段、nullable、refusal、截断和usage。

### S07 — Shapely / GeoPandas

- https://shapely.readthedocs.io/en/stable/reference/shapely.make_valid.html
- https://geopandas.org/en/stable/docs/user_guide/projections.html
- `make_valid`可产生不同几何类型；CRS设置与坐标转换必须明确区分。

### S08 — autoresearch

- https://github.com/karpathy/autoresearch
- 只借鉴原子实验与固定评测协议；不作为当前runtime依赖。

### S09 — 真实NHC时间格式回归样例

- https://www.nhc.noaa.gov/archive/2022/al09/al092022.public.034.shtml
- 采用最少必要片段验证本地标题日期与UTC摘要；完整文件按source manifest获取。

### S10 — Codex仓库指令

- https://developers.openai.com/codex/guides/agents-md
- 官方入口可能重定向；使用仓库AGENTS.md保留不可违反的开发边界和续接协议。

### S11 — 本项目方案来源

- 用户提供的DisasterTrace Notion导航：https://app.notion.com/p/13-1-DisasterTrace-Notion-3ceff220ec69818693f8e30889bc7c1f
- 用户前序研究方案、实现讨论及已上传starter；本文对其工程约束做了显式校正，特别是available time、Gold隔离、carrier fork和评分契约。
- 编码代理无需拥有Notion权限即可执行本文件的M1；本文件包含必要接口与验收条件。
