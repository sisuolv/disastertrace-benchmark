# DisasterTrace-MM｜交给 Codex 的下一阶段实施计划

> **类型：待执行研究与代码规格，不是已完成实验报告。**
>
> **目标：**保留现有 Text Core，在同一工程中增加“异步图文证据 → 局部状态修订 → 来源定位 → 下游条件更新”的可执行评测。
>
> **工作标题：**DisasterTrace-MM: Auditing Local Belief Revision under Asynchronous Multimodal Weather Evidence。
>
> **执行原则：**先检查现有仓库；先做一个真实资料支持、可自动评分的完整 episode；再做配对干预与基线；最后扩大事件和模型。不要继续用更多格式变体替代任务设计，也不要重建全部工程。
>
> **默认启动范围：S0–S1 的离线部分。**网络下载、模型权重下载、GPU/模型生成、付费 API、训练和 heldout 运行均不是本文件自动授予的权限。已有有效授权可按其范围执行；没有授权就完成离线工作、列出具体申请，不自行扩大资源范围。

---

## 0. 给 Codex 的第一条指令

你在维护既有 `sisuolv/disastertrace-benchmark`，不是从零实现新项目。

请先读取本文件及当前目录适用的 `AGENTS.md`，确认 Git HEAD、工作树、冻结科学产物、现有任务接口、当前执行记录和 protected heldout 元数据。不要 reset、清空目录、覆盖运行结果、结束他人进程、重复启动 controller，或把旧授权窗口当作本轮授权。

先完成下列工作：

1. 输出 `docs/mm_trace/REPO_AUDIT.md`：逐项列明“已有实现、可复用接口、待实现功能、阻塞项”，每项附文件路径。
2. 实现最小 `mm_trace` 数据契约、证据访问视图、下载计划生成器和一个离线 synthetic fixture；fixture 只验证代码，不计入真实 benchmark 数据。
3. 优先复用本地已合法取得的开发来源。缺数据时输出明确 URL、预计体量、保存位置与准入要求，不编造已下载或已配准记录。
4. 在许可范围内推进到 S1；任何网络、GPU或评测授权缺失都只阻塞对应步骤，不阻塞其余可完成的离线开发。
5. 结束时提交实际代码变更、测试输出、阻塞原因和下一步命令；不要只返回另一份计划。自动化运行日志与报告必须来自真实执行。

**本文件所有 `mm_trace` 模块名和 CLI 都是待实现接口规格，不表示仓库已经存在这些能力。**先查重再实现；已有等价接口时采用适配层，并在审计文档中记录映射。

---

## 1. 依据、当前基线与不能重复做的事情

### 1.1 依据优先级

本计划继承两份已有研究材料：

- `DisasterTrace_MM_Research_Roadmap_CN.md`：三部分结构、多模态必要性、Full-evidence/Streaming 分轨、S0–S5 路线。
- `DisasterTrace_Alignment_Novelty_NextPlan_CN.md`：选择性修订、依赖传播、证据到达与状态载体两类干预、故障隔离要求。

原计划导航：[DisasterTrace Notion](https://app.notion.com/p/3ceff220ec69818693f8e30889bc7c1f)。

研究审查使用过的仓库基准是 `36082c42a93e11f67d274d8000c87cd1dc098d74`。**这是历史参考，不是要求 checkout 或回退到它。**本次读取的 `CURRENT_PHASE.md` 仍是标注 2026-09-08 20:31 UTC 的进展指针；它不能证明相应作业此刻仍在运行。实际实施以本地最新代码、冻结清单和终态记录为准。[P1–P3]

遇到冲突时按以下方式处理：最新可核查记录决定“已做了什么”；冻结版本决定旧实验的语义；本计划决定新增研究目标；不能为了适配本计划而改写历史事实或旧评分。

### 1.2 已有进展检查表

| 资产 | 历史审查记录 | Codex 应做什么 |
|---|---|---|
| Text Core 的受控实验 | P6：1,861/2,160 严格正确 | 保留为基础诊断；不重新命名成多模态成绩 |
| 官方原文模型实验 | P7：Qwen3-8B 527/1,542 严格正确，全部回答收齐 | 不再安排“首次 P7 实测”；检查现有验收记录 |
| 同前缀表示对照 | P8：422 对；JSON 118 正确，文本 143 正确 | 保留其长度混杂；不要误称等 token 纯表示实验 |
| 第二模型与扩展来源 | P9 有部分未尝试；P10 已扩六场开发风暴 | 不删失败，不把已有扩展当作新贡献重复做 |
| P11–P14 | 历史指针存在运行中或预检记录 | 读取真实终态；禁止根据旧文字启动重复任务 |
| 当前输入协议 | 三方法均可读取累计原文 | 新增访问条件，而不是声称现有任务已强制依靠记忆 |

表内数字来自项目报告，不是本计划重新运行所得。[P2–P4]

### 1.3 保留、新增、暂缓

**保留：**原始资料保存、明确目标键、独立编译与评分、模型自己的实际历史、固定机会分母、失败记录和可复算结果。

**新增：**地图与文本的对齐、自动空间参考、局部依赖、分支独立 Gold、图文必要性测试、流式证据预算、固定前缀载体审计。

**暂缓：**真实最优停港/撤离行动、全灾种平台、遥感基础模型训练、通用知识图谱、开放式 LLM judge、自动搜索测试集、为了扩展而迁移整个 runner。

---

## 2. 研究契约：实现必须服务于什么问题

### 2.1 三个研究问题

| 编号 | 研究问题 | 对应实验 |
|---|---|---|
| RQ-A | 地图中的局部变化能否被正确转换为状态与相关结论？ | 原子读图、原始图文、oracle 感知诊断 |
| RQ-B | 模型是否只对当前已交付且与目标相关的变化作出反应？ | 延迟、缺模态、旧版重放、无关更新的配对轨迹 |
| RQ-C | 模型保存的状态及视觉依据是否真正影响后续表现，且影响是否可靠？ | Streaming 条件、固定前缀 Actual/Masked/Oracle/Edited 审计 |

**不预设答案。**强基线解决任务、加入状态没有提升、主要瓶颈只在感知，均应如实报告。不得按被测模型是否失败筛选正式数据。

### 2.2 必须分开的三层变化

```text
证据变化：来源换版、到达顺序变化、某区域图形变化
    ↓ 不一定改变事实值
事实变化：某地点的空间关系或数值档位变化
    ↓ 需要复核依赖，但不一定改变结论
派生条件变化：某个公开研究条件的结果变化
```

每次转换区分：`must_change_value`、`must_refresh_support`、`must_recheck`、`must_preserve`。它们可以重叠但不能混为同一标签。例如来源刷新可能要求重新验证支持链，却不要求改动下游布尔值。

`must_recheck` 的输出只表示模型**声明完成复核**，不是观察到内部思维过程。实际可靠性仍由提交结果和干预表现检验。

### 2.3 自动评分的边界

主流程不新增逐题人工文本 span、手画 polygon 或主观行动标签，不用 LLM judge 生产主 Gold。采用官方可解析信息、已有可追溯结构化数据、公开研究规则和程序生成定位。

这不等于禁止研究者审查规则或抽查渲染。若一个样本必须由专家逐题解释才能获得唯一语义，先隔离，不让 Codex 以常识或另一个 LLM 补齐后纳入主分。

---

## 3. 首版数据路线：下载什么、先做哪一种任务

### 3.1 推荐优先顺序

**P0：NHC Forecast/Advisory + forecast wind radii GIS。**优先寻找相同绝对有效时刻的预报层，制作地点进入/退出/保持某风圈的图文任务。必须先从下载的实际文件检查 layer、字段、CRS 和时间含义，不能凭文件名假定每个包都具备目标层。[D1][D2]

**P1：NHC 原始地图或 CyPortQA 的图文素材。**核对原图对应的产品、发行版本、有效时段及地图范围。有匹配结构数据时进入 native-map；没有可靠配准就不作为精确区域主评分样本。[D3][D6]

**P2：风速概率地图。**只在有效窗口和概率阈值语义核查后加入。滚动 120 小时产品不能伪装成同一个绝对时间目标的自然修订；全海盆概率产品也不能无依据归因给单一风暴。[D4]

**开发选点：**先用程序按固定种子生成的中性点 `P01/P02`；位置在公开地图中明确可见，记录 `point_origin=generated_probe`，不称其为真实港口。复用 CyPortQA 港口坐标时另外核查坐标字段和来源。不得使用私有 Gold 给模型标出正确地点关系。

### 3.2 真实修订与产品快照的语义不能混淆

定义两个独立查询模式：

- `fixed_valid_target`：固定变量、地点、测量类型、有效时间/区间，只有同键证据能更新该事实。主打“同目标修订”。
- `latest_product_snapshot`：回答最近合法可见产品所覆盖的状态，并显式返回其 cycle 和有效区间。可用于 cone 或滚动概率产品，但不宣称不同窗口的差值是同一目标预测的修订。

首版主表优先 `fixed_valid_target`。`latest_product_snapshot` 单列，不能强行将时间窗改写成相同值来凑配对。不同模式下同一个地点的记录也必须有不同事实键。

如果 P0 样本量不足：完成少量明确标注的渲染/合成仪器验证，并输出数据缺口；不可从自然主轨无声切换为合成主轨。

### 3.3 本轮核查到的下载入口

下面区分**目录/元数据已确认**与**下载后还需验收**。网页可访问、文件在目录存在，不等于压缩包已成功下载，更不等于图文已经配准。

| ID | 资源与链接 | 首版用途与核查状态 |
|---|---|---|
| D1 | [NHC GIS 总入口](https://www.nhc.noaa.gov/gis/)；[本次可读的官方同站入口](https://prod-east-nhc.woc.noaa.gov/gis/) | 官方列出 track/cone、wind radii、WSP 等产品。主域部分页面本次返回 403，已保留为访问限制 |
| D2 | [Forecast wind radii ZIP 目录](https://ftp.nhc.noaa.gov/atcf/gis/fst/) | 目录可读；适合先定位带明确编号的历史文件 |
| D3 | [Track/cone/watch-warning ZIP 目录](https://ftp.nhc.noaa.gov/atcf/gis/5day/) | 目录可读；不要把 5day 包当作风速概率包 |
| D4 | [NHC 风速概率历史入口](https://www.nhc.noaa.gov/gis/archive_wsp.php) | 原方案已列的官方入口；本轮抓取受限，具体年份文件需重新从页面确认，禁止猜下载文件名 |
| D5 | [Francine 原始图形档案](https://www.nhc.noaa.gov/archive/2024/FRANCINE_graphics.php) | 候选原图入口；本轮主域抓取受限。下载时解析实际图片链接，不臆造 PNG URL |
| D6 | [CyPortQA 固定版本数据目录](https://github.com/ChenchenMobility/MLLM-Bench-CyPortQA/tree/1c38abf339d1471d710f6cb719a5e3874b547077/dataset) | GitHub Contents 元数据已核查；可按文件白名单下载 |
| D7 | [CyPortQA 固定版本来源目录](https://github.com/ChenchenMobility/MLLM-Bench-CyPortQA/tree/1c38abf339d1471d710f6cb719a5e3874b547077/source_data) | 模板、场景和原始材料候选；不直接继承旧 QA 为新任务 Gold |

**直接 GIS 样本链接，已在官方目录确认存在：**

| 文件 | 直接下载链接 | 官方目录显示的约大小 |
|---|---|---:|
| Francine 005 forecast wind radii | https://ftp.nhc.noaa.gov/atcf/gis/fst/al062024_fcst_005.zip | 66K |
| Francine 007 forecast wind radii | https://ftp.nhc.noaa.gov/atcf/gis/fst/al062024_fcst_007.zip | 65K |
| Francine 005 track/cone 等 | https://ftp.nhc.noaa.gov/atcf/gis/5day/al062024_5day_005.zip | 36K |
| Francine 007 track/cone 等 | https://ftp.nhc.noaa.gov/atcf/gis/5day/al062024_5day_007.zip | 33K |

这些是数据获取/层结构检查候选，不是已验收 episode。不保证 005/007 的每个 GIS 层具有同一有效时间；需读取内容后选择匹配层。本轮未取得这些 ZIP 字节，**SHA-256 留空，不能伪造**。目录更新时间不是历史首次公开时间。

**文字来源优先复用本地已保存的 Francine 开发资料。**以下为原方案中的对应官方地址；本轮抓取受限，Codex 应核对本地 manifest 或重新验证：

- https://www.nhc.noaa.gov/archive/2024/al06/al062024.fstadv.005.shtml
- https://www.nhc.noaa.gov/archive/2024/al06/al062024.fstadv.007.shtml

原来的 Francine 005/007 同目标风速示例不能直接证明 GIS 配准成功。也不得因为 Francine 曾是开发来源，就跳过当前 split 清单检查。

### 3.4 CyPortQA 的真实路径与固定版本下载

本轮核查到的仓库 commit：

```text
1c38abf339d1471d710f6cb719a5e3874b547077
```

下列为固定 commit 的 raw 下载地址。大小来自 GitHub 元数据，并非本轮实际下载测量。[D6][D7]

| 资源 | 字节数 | 直接链接 |
|---|---:|---|
| 题型模板 | 40,313 | https://raw.githubusercontent.com/ChenchenMobility/MLLM-Bench-CyPortQA/1c38abf339d1471d710f6cb719a5e3874b547077/source_data/CyPortQA_template.json |
| 编码场景 | 9,409,152 | https://raw.githubusercontent.com/ChenchenMobility/MLLM-Bench-CyPortQA/1c38abf339d1471d710f6cb719a5e3874b547077/source_data/Encoded_senario.json |
| 完整 QA JSON | 98,747,532 | https://raw.githubusercontent.com/ChenchenMobility/MLLM-Bench-CyPortQA/1c38abf339d1471d710f6cb719a5e3874b547077/dataset/CyPortQA.json |

**不要照抄 README 中的大小写：实际是 `CyPortQA_template.json` 与 `Encoded_senario.json`，不是大写 `.JSON`。**保留上游 `senario` 的实际拼写。

实际图文目录为：

```text
dataset/MultiModalInput/
  Cyclone Graphics Archive Uncertainty Cone/
  Cyclone Graphics Archive Wind/
  Cyclone Text Archive Advisory/
  Cyclone Text Archive Wind/
```

[浏览已核查的图文目录](https://github.com/ChenchenMobility/MLLM-Bench-CyPortQA/tree/1c38abf339d1471d710f6cb719a5e3874b547077/dataset/MultiModalInput)

构建显式 `modality_path_map`，不要假设 runner 中的简称恰好就是磁盘目录名。先用 Contents API 列文件，再按已批准的事件和字节预算下载。`dataset/MultiModalInput` 与 `source_data/NOAA NHC Cyclone Products` 本轮元数据指向相同 tree SHA，可优先内容去重，避免下载两份相同素材。

完整 QA 和场景可能含未来结果、标签或业务信息。它们只供离线来源选择与分析，不得自动放进模型输入、RAG索引或历史载体。若包含 protected heldout，先做记录级过滤；未经许可不读取那些标签。

---

## 4. 现成代码、论文和模型：复用范围

### 4.1 代码资源

| ID | 项目 | 入口 | 建议用途 | 不能照搬的部分 |
|---|---|---|---|---|
| K1 | CyPortQA | https://github.com/ChenchenMobility/MLLM-Bench-CyPortQA | 图文消息打包、素材组织；检查 `models/run_qwen2_5vl.py` | QA 打乱顺序、`latest` 模型名、默认付费模型列表，不适合冻结回放 |
| K2 | STALE / CUP-Mem | https://github.com/icedreamc/STALE | 更新、失效、前提验证；优先看 `cup_mem/pipeline.py` 和 `cup_mem/write/` | 不启动生成新 QA 的流程，不将其 judge 当天气真值；内部模型调用计费/预算单独统计 |
| K3 | VersionRAG | https://github.com/danielhuwiler/versionrag | 版本检索及查询解析；`src/retrieval/` | 自建轻量过滤器不能冒称完整官方复现；不能读取未来版本元数据后才过滤正文 |
| K4 | lmms-eval | https://github.com/EvolvingLMMs-Lab/lmms-eval | 需要时复用模型适配，不必替换现有 runner | 不能假设框架自动提供本项目时间政策、状态隔离与固定分母 |
| K5 | GeoPandas | https://github.com/geopandas/geopandas | GIS 读取与空间连接 | 核对 CRS、几何有效性和坐标顺序 |
| K6 | Shapely | https://github.com/shapely/shapely | intersection/difference/covers 等几何运算 | 不能把几何关系解释为真实最优行动 |
| K7 | Qwen3-VL | https://github.com/QwenLM/Qwen3-VL | 原生 processor、图像输入与模型适配说明 | 不用浮动分支或默认无限图像预算 |
| K8 | InternVL | https://github.com/OpenGVLab/InternVL | 第二语言骨干的视觉模型适配 | 审核所需 remote code，固定 commit 与动态切图策略 |

**复用顺序：**现有 DisasterTrace > 小型自建必要适配 > 上游单模块 > 整框架迁移。`version_filter`、`state_rechecker`、`visual_cache` 先做明确可测的最小基线；原作者系统适配成功后另命名、另锁定。

对每个外部依赖记录 `repo_url / commit / files_used / local_changes / license_path / data_license / upstream_reference`。仓库公开不等于所有数据可以再分发；代码许可、模型许可与来源图片许可分别检查。许可不清时保留下载入口与适配代码，不发布对应字节。

### 4.2 论文只提供设计依据，不自动成为已复现方法

| 论文 | 直接链接 | 本计划借鉴点 |
|---|---|---|
| StateMemBench / StateMem | https://arxiv.org/abs/2608.19652 | supersession 与依赖重查的强近邻；需要基线比较，不当新概念 |
| STALE | https://arxiv.org/abs/2605.06527 | 过期前提识别、状态更新后用于后续任务 |
| VersionRAG | https://arxiv.org/abs/2510.08109 | 版本敏感检索，检验“过滤版本就足够”的解释 |
| SpaMEM | https://arxiv.org/abs/2604.22409 | 原子感知、oracle 状态和端到端维护的分层诊断 |
| When History Is Multimodal / VERA | https://arxiv.org/abs/2608.29897 | 保留原生视觉证据，而不是默认全部转为文本 |
| CyPortQA | https://arxiv.org/abs/2508.15846 | 领域图文材料和已有任务边界 |

本计划的 oracle 感知实验是针对 DisasterTrace 的适配，不声称逐项复现 SpaMEM 的实验。`visual_cache` 也不直接命名为 VERA，除非按原方法完成适配和核验。

### 4.3 模型下载入口与预检

首轮推荐可启动模型，而非宣称最新最强：

- [Qwen3-VL-8B-Instruct](https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct)
- [InternVL3-9B](https://huggingface.co/OpenGVLab/InternVL3-9B)

InternVL3-9B 官方表列出的语言部分是 `internlm3-8b-instruct`。不要误换成 Qwen 语言骨干的其他同系列型号后声称独立骨干验证；也不要把 `InternVL3-9B` 和 `InternVL3-9B-Instruct` 当同一 checkpoint。[M1][M2]

下载前检查本地缓存，记录精确 revision。权重、tokenizer、processor、chat template、图片缩放、tile 上限、precision、推理开关和停止规则全部锁定。若后端不支持该模型，先用官方 Transformers 路径验证一个开发请求，再选择是否适配加速后端；不升级或破坏旧实验环境。

官方 CLI 支持指定 revision 和本地目录：[Hugging Face 下载说明](https://huggingface.co/docs/huggingface_hub/guides/cli)。以下是**取得权重下载授权并填好固定 SHA 后**的实际命令，不属于默认执行步骤：

```bash
test "${WEIGHTS_DOWNLOAD_APPROVED:-0}" = 1 || { echo "权重下载未获批准"; exit 1; }
: "${MODEL_ROOT:?指定已有持久存储下的模型目录}"
: "${QWEN_REV:?填写已核查的模型 commit SHA}"
: "${INTERNVL_REV:?填写已核查的模型 commit SHA}"

hf download Qwen/Qwen3-VL-8B-Instruct \
  --revision "$QWEN_REV" \
  --local-dir "$MODEL_ROOT/Qwen3-VL-8B-Instruct"

hf download OpenGVLab/InternVL3-9B \
  --revision "$INTERNVL_REV" \
  --local-dir "$MODEL_ROOT/InternVL3-9B"
```

环境变量仅作误执行防护，不等于外部授权。不得在脚本中硬编码账号 token。不要猜固定包版本：在独立环境通过预检后输出 lock 文件，并保留后端源码/版本依据。

---

## 5. 下载器与来源 manifest 的实施要求

### 5.1 四个权限门槛

| 门槛 | 可以做什么 | 不能自动扩展为什么 |
|---|---|---|
| G0 / offline | 本地审计、已有开发数据、fixture、单元测试、下载 dry-run | 不联网装依赖、不取权重、不加载 GPU 模型 |
| G1 / source-download | 按明确白名单取得免费官方资料和允许的开源代码 | 不等于下载全部数据、模型权重或调用模型 |
| G2 / model-run | 固定实验协议、模型、资源、时间和机会数后的开发实测 | 不等于付费 API、训练或 heldout |
| G3 / heldout | 冻结后一次正式测试，按单独许可 | 不等于依据测试分数反复调参再报同一测试集 |

如果当前用户已明确授予某一门槛内的操作，核实后执行，不重复询问已知事项。旧任务的带截止时间授权不能自动续期。

### 5.2 来源记录格式

实现 `SourceCandidate` 与 `DownloadedArtifact` 两种状态，不能混用。下面是候选 schema 示例，不是假装已下载的数据：

```json
{
  "resource_id": "nhc_francine_fcst_005",
  "url": "https://ftp.nhc.noaa.gov/atcf/gis/fst/al062024_fcst_005.zip",
  "source_index_url": "https://ftp.nhc.noaa.gov/atcf/gis/fst/",
  "resource_kind": "official_gis_zip",
  "event_context": "AL062024",
  "declared_product_family": "forecast_wind_radii",
  "verification_level": "index_confirmed_not_downloaded",
  "expected_bytes": null,
  "max_bytes": 10485760,
  "expected_sha256": null,
  "download_enabled": false,
  "split_check_required": true
}
```

下载后新增：最终 URL、请求时间、HTTP 状态、MIME、真实字节数、SHA-256、ZIP 内成员、解压尺寸、许可证/来源说明和失败记录。`expected_sha256=null` 表示只能建立首次获取的哈希，不能声称通过了上游给定 checksum 校验。

### 5.3 必须实现的行为

- `plan` 默认只列候选与预计体量；正式下载只读已批准 manifest，不爬整个 NHC 或 GitHub 仓库。
- 先检查本地源与哈希，缺什么取什么。网络失败可有限重试下载，但不能用模型多次生成类比为允许的“下载重试”。
- 流式下载设单文件和总字节上限，临时文件使用 `.part`，验收后原子重命名；已有路径内容不同时另存冲突而非覆盖。
- 防止 HTTP 200 的 HTML 错误页被当成 ZIP/PNG/JSON。ZIP 检查 magic、CRC、成员路径、解压总量、压缩炸弹和 symlink/path traversal。
- GIF/PNG/JPEG 图片检查可解码、尺寸上限；JSON 保持原始 bytes 并另存解析产物。
- HTTP 403/404/429、DNS 失败、内容不符分别记录；不使用来历不明镜像悄悄替换。重定向到新域名先检查许可白名单。
- 原始文件名/来源号放私有来源表；模型侧可用稳定不含答案的公开 ID。保存映射以便审计。
- 文件时间戳、HTTP `Last-Modified` 和目录时间都不能直接变成 historical `available_at`。

**启动体量建议：**首次仅下载已批准的 4 个 Francine ZIP 与必要文本；模板可单独批准。先不下载约 99 MB 的完整 QA JSON，更不拉全部图片。这个上限是节约开发成本的建议，不是用户已经授予的下载授权。

### 5.4 取得代码的示例

以下命令只用于 G1 已批准且目的目录不存在的情况。它创建外部只读参考副本，不动用户主仓库：

```bash
test "${SOURCE_DOWNLOAD_APPROVED:-0}" = 1 || { echo "来源与代码下载未获批准"; exit 1; }
: "${THIRD_PARTY_ROOT:?设定外部参考代码目录}"
CYPORT_COMMIT=1c38abf339d1471d710f6cb719a5e3874b547077
DEST="$THIRD_PARTY_ROOT/cyportqa"
test ! -e "$DEST" || { echo "目录已存在：先审查并复用，不覆盖"; exit 1; }

git clone --single-branch --branch main --no-tags --filter=blob:none --no-checkout \
  https://github.com/ChenchenMobility/MLLM-Bench-CyPortQA.git "$DEST"

git -C "$DEST" sparse-checkout init --no-cone
git -C "$DEST" sparse-checkout set \
  '/README.md' '/LICENSE' '/models/' '/source_data/CyPortQA_template.json'
git -C "$DEST" checkout --detach "$CYPORT_COMMIT"
git -C "$DEST" rev-parse HEAD
```

第一次不把 `/dataset/` 加入 sparse 列表。需要图文文件时从批准 manifest 逐文件下载，保护 heldout。无法 partial clone 时报告，不自动回退到可能很大的全量 ZIP。

---

## 6. 数据契约与类型设计

在新命名空间 `src/disastertrace/mm_trace/` 定义；旧任务定义与旧评分器不修改。类型实现可用项目已有验证库，不引入与旧环境冲突的依赖。

### 6.1 必需对象

| 对象 | 最小内容 | 使用侧 |
|---|---|---|
| `ArtifactMeta` | 身份、产品范围、issue/valid/available/retrieved、多模态、哈希、来源与渲染信息 | 安全投影后公开 |
| `FactKey` | 实体/地点、变量、测量类型、阈值、产品范围、有效时间 | 公开 |
| `QuerySpec` | 查询模式、目标键/选择器、公开解析政策、期望字段 | 公开 |
| `DeliveryEvent` | `delivery_id`、`artifact_id`、`branch_id`、交付步与时间 | 只公开当前允许部分 |
| `Episode` | 基础来源组、多个目标、查询、交付序列、split | 私有完整目录；公开前缀 |
| `ModelCommit` | 原样最终文本、解析状态、支持位置、更新操作、自选缓存 | 模型/运行器 |
| `TransitionObligation` | 值变化、支持刷新、复核与保持集合、可接受支持集合 | 仅评测侧 |
| `InterventionSpec` | 只改哪个交付/载体因素、前缀标识、预期分支关系 | 私有实验配置 |

**同一旧 artifact 可以被重放两次，故 delivery ID 与 artifact ID 必须分开。**重复交付不创造新版本，也不能靠改变 ID 让旧内容看起来更新。

### 6.2 多时间与版本规则

保存 `issued_at`、`valid_at` 或 `valid_from/valid_to`、可选 `effective_at`、`retrieved_at`、`available_lower/upper`、`availability_basis`。交付发生在 `DeliveryEvent.delivered_at`，不是修改 artifact 的发行日期。

默认采用 `controlled_issue_order`：已在该分支交付的资料才可使用。只有 historical availability 有可核查证据时才开启 `verified_as_of_time`。已知可用区间横跨 checkpoint 时，不能当成精确已可见。

版本选择流程：

```text
先筛当前分支已经交付的资料
→ 再匹配产品范围、对象、变量、测量类型和有效时间
→ 在同语义键内按公开 version policy 选择
→ 应用明确替代/撤回/有效期规则
→ 返回支持状态与允许的来源集合
```

不使用全局“最后读到的材料胜出”。也不把更新的其他变量文本当作撤销旧地图。

### 6.3 事实状态与缺失

首版可采用 `supported / unknown / withdrawn / terminal`。只有任务确实涉及、且来源与规则支持时才启用后两者；无法裁决的同级冲突若不纳入单独 conflict 任务，应隔离而非任意选新值。

- `unknown` 表示当前没有充分证据，不表示世界中事实为假。
- 布尔值 `false` 必须有判断依据；不得用它代替 `unknown`。
- `withdrawn` 需要明确撤回或公开规则的失效事件，不能由“新文没提”推导。
- `terminal` 如消散，需要引用明确来源，不能转成数值零。
- 对 fixed-target 的旧明确覆盖是否继续保留，必须用该任务版本的公开规则；不要称它为 NHC 的通用业务规则。

### 6.4 模型输出示例

以下为**待实现的演示 schema 与合成样例**，不是官方资料，也不是实际模型回答。公开编号 `Q-P01` 已通过查询定义映射到完整 FactKey；未显示的 query fields 不由模型猜。

```json
{
  "schema_version": "mm_trace_v1",
  "checkpoint_id": "c3",
  "states": [
    {
      "query_id": "Q-P01",
      "status": "supported",
      "value": "band_40_60",
      "support": [
        {"artifact_id": "IMG-02", "locator_type": "grid", "locator_ids": ["G07"]}
      ]
    },
    {
      "query_id": "Q-P01-condition",
      "status": "supported",
      "value": true,
      "support": [
        {"artifact_id": "IMG-02", "locator_type": "grid", "locator_ids": ["G07"]},
        {"artifact_id": "TXT-R", "locator_type": "sentence", "locator_ids": ["S03"]}
      ]
    }
  ],
  "operations": [
    {"query_id": "Q-P01", "operation": "UPDATE"},
    {"query_id": "Q-P01-condition", "operation": "UPDATE"}
  ],
  "declared_rechecks": ["Q-P01-condition"],
  "retain_evidence": [
    {"artifact_id": "IMG-02", "locator_ids": ["G07"]}
  ]
}
```

**选择一个主状态契约并冻结：首版推荐完整状态提交。**模型每轮提交全部目标状态，运行器只机械保存和解析。若改为 patch 模式，必须显式定义未提及项保持、事务失败和操作应用顺序；patch/full 模式不可无标注混跑。

无效输出保存原文并传递 `invalid_commit` 标记；不得自动恢复成最近正确 Gold。若选择“保留上次合法自有状态”作为恢复政策，要单独声明并与失败标记共存，不用静默回退改变实验。

---

## 7. Gold、可视化和局部依赖的实现

### 7.1 公私数据隔离

```text
data/mm_trace/raw/                # 离线来源，可能含所有未来版本
build/mm_trace/private/           # GIS、Gold、support masks、全部分支与split
build/mm_trace/public/            # 可发布数据资产；不是在线自动可见的全集
runs/mm_trace/<run_id>/views/     # 每条实际请求的可见证据快照
```

路径是建议，实际遵守项目目录习惯。**不能仅靠名字叫 private 就算隔离。**模型服务工作目录不挂载私有目录；政策函数只接受 `PublicEvidenceView` 和自有历史；工具端必须按当前 episode/branch/checkpoint 校验可见性。全文检索、向量索引、文件列表和元数据也不能暴露未来版本。

服务的主执行流程不得导入 `geometry_gold`、读取 `TransitionObligation` 或以参考答案选图。评测可在模型输出写入之后由独立进程运行。调试日志不能被下一轮自动拼入 prompt。

### 7.2 GIS 准入与图像生成

1. 在实际下载 ZIP 上列 layer 与字段，输出 `LAYER_CATALOG.json`，记录原始 schema，不提前硬编码猜测字段。
2. 验证 CRS、经纬度轴序、距离/角度单位、经度跨日界线、多面体/洞、缺失几何和无效几何。
3. 选取满足查询模式的 layers。缺确切有效时间时不插值拼 Gold。
4. 几何推导：进入=`new\old`，退出=`old\new`，稳定按公开定义分解。只能比较语义兼容的两层。
5. 构造公开地图：边界、图例、比例/坐标信息、目标中性点、固定网格。保存 `render_spec`、图片 hash 与地理到像素变换。
6. 对 native-map 额外检查原图/GIS的对应关系和配准证据；不能直接套重绘图的精确像素映射。
7. 空间标签按图中可辨类别生成。概率区间 `[a,b)` 跨过研究阈值时，图像可能不足以唯一判断；返回按规则定义的不可确定状态或进入歧义诊断，不用私有精确概率强判。
8. 选点与边界排除基于冻结的几何/像素距离规则，而不是基于某个 VLM 是否做对。披露被排除的困难边界样本比例。

不要求训练视觉变化模型；也不使用图像生成模型制造“官方天气地图”。

### 7.3 不新增逐题人工定位标签

文本使用自动编号的句子/行，保留原文 offset；图片使用固定网格 ID，或与答案无关的程序生成候选区域。区域 ID 在模型可见图片上可定位。

Gold 支持集合由几何映射和文本解析产生；允许多个等价充分支持集合，而不是只认一个任意 locator。单纯选整张图不能总算成功：预先设每字段定位数量/覆盖面积上限，并在地理边界诊断中明确容差。

若采用网格，注意一个格可能跨越多种值：**网格是证据定位，不是把整格都标为同一概率**。答案针对公开目标点，图例解释与点周边关系必须仍可见。

### 7.4 依赖和更新义务

实现公开 `RuleSpec`，首版仅支持可审查的类型：阈值比较、集合成员、AND/OR、明确有效期约束。未知按冻结的三值逻辑传播，不用 Python 的 `None` 隐式转换为 false。

```text
Artifact / span / region → base fact → derived condition
```

每个转换同时保存：

- Gold 前后完整状态。
- 值改变集合与来源改变集合，二者分开。
- 公开依赖关系下的 affected frontier。
- 应复核但结果不变的集合。
- 不受影响的状态集合。

**公开 RuleSpec 不是私有正确答案图。**方法基线可读取公开依赖规则；无法从题意直接确定的依赖边需由模型/方法提出，不能向方法提供 Gold 变化集合。

### 7.5 独立验证的含义

参考 compiler、参考求解和 scorer 分工；避免 compiler 与核查器直接调用同一个 `resolve()` 后“全通过”。可以共享无语义的 JSON/时间基础库，但关键版本匹配、几何关系和未知传播应有独立对照/手算单元 fixture。

使用私有 GIS 的核查器属于 **oracle/instrument validation**，不能称为与 image-only VLM 同输入的公开求解器。重绘 fixture 可有独立像素检查；官方原图仍需配准与可读性证据。程序彼此一致不等于完全排除了同源语义错误。

---

## 8. 任务构造与信息干预

### 8.1 最小教学轨迹

用合成概率区间解释接口，真实自然数据不强行复制这些值：

| 检查点 | 新交付证据 | P 的正确行为 | Q 的正确行为 |
|---|---|---|---|
| c0 | 研究规则 R，未提供地图 | `unknown` | `unknown` |
| c1 | M1，P 在较低档位、Q 在更低档位 | 建立值与支持，计算条件 | 建立独立状态 |
| c2 | 文本更新另一变量 | 相关概率保持，不凭新日期清空 | 只改被明确更新的槽位 |
| c3 | 同键 M2，P 越过研究条件门槛、Q 的值不变 | 更新 P 值与派生条件 | 值保持；若新图提供当前支持，则引用相应刷新 |
| c4 | 旧 M1 重放 | 不回退 | 不回退 |

注意 c3：**Q 值不变不保证 Q 的支持引用也不变。**若 M2 是 Q 的新有效覆盖，Q 可以属于 `must_preserve_value` 与 `must_refresh_support` 的交集。这一细节必须写入测试。

### 8.2 四类任务

- `spatial_revision`：同地点同目标的区域进入、退出、稳定；包含同值来源刷新。
- `cross_modal_conjunction`：图像提供空间关系，文本提供独立必要条件，或反向组合；避免简单读图任务冒称联合推理。
- `scope_version`：同键新版、不同有效期、其他对象、旧版迟到与不同产品混合。
- `withholding_recovery`：缺少必要证据时保留未知，补齐后恢复支持，允许明确撤回/过期的独立子型。

### 8.3 四种干预与参考关系

| 干预 | 可改变项 | 不得改变项 | 必验关系 |
|---|---|---|---|
| `delay` | 指定图/文的交付步 | 原正文、issued/valid、其他交付 | 延迟期间按本分支证据回答，不能提前用未来材料 |
| `withhold` | 指定必要模态/证据是否交付 | 其他资料与研究规则 | 参考应按可断言性重算，合理未知不能被判为胡猜失败 |
| `stale_replay` | 旧 artifact 的再次交付事件 | artifact 内容与版本时间 | 最新有效覆盖不能被旧副本覆盖 |
| `null_update` | 无关/重复资料是否出现 | 目标支持集与政策 | 相关目标值、有效来源应满足冻结的不变关系 |

图文错配需分清：真正矛盾、时间不一致、不同测量类型或只是版本号不同。不能把“号不一样”全部算 conflict。

分支构造时先求出 `visible_artifacts(branch,t)`，再独立编译参考。除经过证明的 null 条件外，不复用 base 的 Gold 文件。

### 8.4 前缀与闭环

同前缀单步实验共享已经保存的真实前缀；干预后的闭环继续使用各自实际输出。两个实验族分别报告。

相同种子不保证不同请求产生相同文本。干预前若输入相同，优先共享已保存的前缀而非重新生成；所有克隆前缀计为共享，不重复当作新增独立模型回答。

---

## 9. 证据访问轨道、模型方法与诊断必须分开

### 9.1 访问轨道

| 轨道 | 允许证据 | 主要问题 |
|---|---|---|
| `full_evidence` | 截至当前全部已交付原始图文；方法可附加自身状态 | 从头重算与历史配置能达到什么水平 |
| `streaming` | 本轮新证据 + 预算内自有状态/缓存；不另回查原始旧资产 | 保存和更新是否必要、视觉信息是否丢失 |
| `budgeted_archive`（后续可选） | streaming + 有限回查当前已交付档案 | 重读成本与准确性的权衡 |

`streaming` 的容量限制必须有部署动机并做预算敏感性；不只是为制造低分而随意删除证据。端到端 Gold 仍描述截至当前已交付的完整证据所支持的答案；方法自己遗忘并不能让 Gold 自动变成 unknown。由实验主动 withholding 某必要模态则不同，必须更改可断言参考。

`full_evidence` 塞不下时不能偷偷删图后仍称完整证据轨。先在冻结前约束数据规模；运行时真实超限则保留失败。

### 9.2 首轮四个系统

固定同一访问轨道内比较：

- `direct`：在许可输入上直接回答；streaming 版本携带原样的预算内历史，不虚称无历史 snapshot。
- `version_filter`：只按公开元数据与当前可见资料做作用域/有效时间/版本过滤，再由同一模型作答。
- `state_rechecker`：模型提取状态单元，维护被替代关系和依赖复核标记；如借鉴 StateMem/CUPMem，明确标记为适配基线。
- `state_rechecker_visual_cache`：与前者同方法，额外使用明确预算内、由模型或冻结策略选择保留的原生视觉片段。

第四项相对于第三项改变了记忆内容/模态及可能的容量。预算要固定或增加匹配对照，不能默认把额外信息带来的差额全称为算法效应。

VersionRAG 完整适配、CUPMem 完整适配可列增强基线，但首个 episode 不应等待这些重依赖。基线的每次更新、检索解析、复核、修复调用都纳入总预算。

### 9.3 三组诊断

1. **原子感知：**单张图，明确目标，去掉版本干扰。只测图像里的可辨信息。
2. **感知 oracle：**用该步已交付图片可支持的正确视觉事实替换读图，不提供未来或正确后续修订；只用于隔离视觉误差，单列特权条件。
3. **模态对照：**text-only、vision-only、full-modal 和 wrong-version-map；按各条件的信息集计算可断言状态，并补报对 full-modal 目标的正确作答覆盖率。

不以单模态低分证明信息必要性。每个 cross-modal-required 样本额外记录两种合法输入变化导致不同答案的“必要性见证”，以及冗余证据扫描结果。

### 9.4 输出与后端公平性

同一语义契约允许各模型原生 chat template；模板与 role 映射记录在案。选定自由输出或 structure-only 主轨后冻结，不对测试失败模型单独补例子/扩大预算。

结构约束允许所有语义候选，不把正确来源 ID、正确值或正确区域集合注入动态 grammar。可限制字段类型和合法公开 ID 范围，但“合法ID”只能来自当前允许输入，不能是 Gold 支持集。

图像 resize/crop/tiling 后实际送入的图片与 processor 参数必须保存。尽量统一可见分辨率和输入预算，并报告各模型视觉 token 的实现差异；不能假装不同 tokenizer 的 token 是完全可比的信息单位。

---

## 10. Streaming 的状态与证据缓存

- 每条 `(episode, branch, method, model, repeat)` 拥有独立状态、视觉缓存、工具记录，不跨策略共享。
- 模型选择 `retain_evidence`；缓存只能从本条轨迹已交付的资产创建。候选 crop 网格由公开规则提供，不由 Gold 生成。
- 网格 crop 需要可见图例/坐标上下文时，将它们纳入缓存预算；不能在缓存外隐形补一张完整旧图。
- 固定文本容量、图片总像素/张数/视觉 token上限、档案读取额度，以及超额政策。
- 超额时执行冻结的、与 Gold 无关的拒绝/淘汰规则，并记录实际删除什么。不能为某个失败样本临时保留更多证据。
- 图像 caption 由模型生成时，记录它的成本和错误；它不是无损 oracle 事实。
- 所有工具调用都带服务端 checkpoint 权限检查；猜中未来文件名也不得读取未来图片。

预算参数可在独立开发小集上选择，然后冻结。不得用本计划中的示例数字替代实际 processor 长度预检。

---

## 11. 状态载体四臂审计

仅在已有真实模型前缀或明确标注的程序 fixture 上执行；二者不能混报。

| 臂 | 输入改动 | 解释 |
|---|---|---|
| Actual | 真实提交的状态 | 正常条件 |
| Masked | 去除目标状态；另设等长度/同结构的无信息 sham | 比较载体信息的作用，披露不可避免的长度差 |
| Oracle | 正确的历史状态 | 特权诊断，不能混入方法排行榜 |
| Edited | 只改相关字段或不相关字段 | 测定向敏感性、错误传播及抵抗当前证据反驳的能力 |

**必须隔离状态与视觉缓存。**若要测文本状态本身，四臂固定同一视觉缓存；若测整体记忆，应另建 `mask_all_memory` 条件并清除相关图片、缓存摘要和检索副本。不能删除一个 JSON 字段却从另一个载体重新给回同样信息。

选择 probe 前检查：本轮新证据是否可直接回答、缓存是否重复保存、有没有低分/满分地板天花板。数据的依赖性由内容分析支持，模型是否表现出差异则是实验结果。

Edited 至少包含：

- 相关编辑，且当前没有纠正依据：检测下游错误传播，不把盲从加分。
- 相关编辑，且当前证据明确反驳：正确行为是修复/拒绝错误状态。
- 无关编辑：相关目标应保持不变。

`commit_used` 不作为每题可直接读取的布尔标签。报告 Actual–Masked 成对效应、Oracle 差距、相关/无关编辑的方向性影响和正确修复比例；不由这些行为推断模型内部神经机制。

---

## 12. 评分与统计

### 12.1 主表结构

| 指标 | 分母与含义 |
|---|---|
| Semantic state accuracy | 全部预注册目标字段的值/状态正确率 |
| Current support accuracy | 同一字段上同时满足当前产品/目标/版本要求；另报字面支持 |
| Grounding sufficiency | span/region 定位是否构成充分支持；拒绝不存在与过宽定位 |
| Required update recall | 应改变值的目标中正确完成改变的比例 |
| Support refresh accuracy | 值可不变但应换依据时是否更新支持 |
| Stable preservation | 应保持的值/来源维度是否没有错误改写；与更新率一起报告 |
| Unsupported assertion rate | 参考为未知的字段中仍作确定断言的比例 |
| Supported answer coverage | 有充分证据字段中实际给出可用答案的比例，防止一律拒答 |
| End-to-end trajectory success | 预定轨迹全部检查点满足契约的比例；按长度分组 |
| Recovery opportunities | 从信息已足够且有修正机会起计算恢复步数；未恢复按右删失/未恢复数量单列 |

可以另外报告 `grounded_revision_pass` 联合分，但必须伴随分项，不能让一个乘积分数遮蔽图像不可读、格式失败或基础设施停止。

更新率与稳定率不允许单独排序：总是 KEEP 会有虚高稳定率，总是 UPDATE 可能有虚高变化覆盖。按转换类型给出联合表现。

对于上一轮模型本就错误的状态：同时报告绝对当前正确性与从模型实际前缀出发的纠错表现，不能仅用 Gold-to-Gold 不变就扣掉合理纠错。条件于前缀正确的指标另报样本数，不替代全分母主表。

### 12.2 固定机会与故障分类

主分母包含所有已冻结最终作答槽位。`not_attempted`、`context_blocked`、`invalid_output`、`timeout`、`backend_error` 与语义失败分开呈现；不能只对收到的答案计算主准确率。

按 trajectory 隔离上下文超限，不使同 worker 的其他独立轨迹一起停掉。遇到 GPU 进程级错误可以依据冻结政策恢复进程继续未提交槽位，但未知是否提交的请求不得自动重复生成；不得用新的随机回答替换旧失败。

结构错误原样保存。语义归一化（单位、别名、等价定位）若采用，必须在新数据版本中预先声明，并保留原始契约评分；不更改旧实验分数。

### 12.3 分组与泄漏

- 首先按自然风暴/来源组划分，所有地点、目标、时间版本、render variants、twins 跟随组。
- 共享同一官方产品或其派生图像的事件，按共享 artifact 关联构造 split-connected component。不要把全海盆同一 WSP 图分到两个集合。
- protected heldout 只读取划分/ID元数据以防误用，不读标签进行开发。
- 源数据许可允许后，可做名称屏蔽/样式变化的诊断，但不能据此宣称消除预训练污染。
- 小 pilot 给逐组结果与宏平均；扩大后做组级成对 bootstrap，公开组数。不能将上千 checkpoint 当独立风暴计算显著性。

---

## 13. 代码结构与拟实现 CLI

### 13.1 新增一个稳定语义内核

建议目录如下。已有同职能模块优先复用。不是每个实验创建一套复制源码。

```text
disastertrace-starter/
  src/disastertrace/mm_trace/
    contract.py                 # Query/FactKey/Commit；未知与版本语义
    artifacts.py                # 来源与多时间元数据
    source_registry.py          # 可批准下载候选/路径映射/锁定版本
    download.py                 # dry-run、有限下载、安全校验
    alignment.py                # 产品、绝对有效时刻与图文配准
    rendering.py                # 可公开地图、网格、地理像素变换
    geometry_gold.py            # 私有几何参考，模型侧不可访问
    dependencies.py             # 公开研究规则与私有义务计算分离
    compiler.py                 # episode及分支独立Gold
    interventions.py            # delay/withhold/stale/null
    evidence_views.py           # full/streaming；工具权限边界
    state_protocol.py           # 模型原样状态与冻结恢复政策
    visual_cache.py             # 非oracle证据选择/容量与访问日志
    baselines/                  # direct/version_filter/rechecker/cache
    model_adapter.py            # 明确版本与processor记录
    collector.py                # 复用旧日志体系；单轨故障隔离
    carrier_audit.py            # 固定前缀四臂，与主轨分开
    scoring.py                  # 内容、支持、定位、修订、未知
    analysis.py                 # 分母、分组、配对、恢复和成本
    cli.py
  configs/mm_trace/
    source_candidates.json
    scope.yaml
    fixture.yaml
    pilot_full.yaml
    pilot_streaming.yaml
    budgets.yaml
  tests/mm_trace/
  docs/mm_trace/
  artifacts/mm_trace/            # 新设计/验收，不覆盖旧阶段
```

若项目已有公用 collector，可以在新 wrapper 中补轨迹隔离，不修改冻结旧 collectors；抽取共享代码前用旧版本回归证明输出不变。

### 13.2 CLI 规格（不是现在已经存在的命令）

要求 Codex 实现或映射下列接口，`--help` 必须列出默认权限和输出文件：

```bash
# 默认完全离线：以下接口需先实现
python -m disastertrace.mm_trace.cli audit --offline
python -m disastertrace.mm_trace.cli sources plan --manifest configs/mm_trace/source_candidates.json
python -m disastertrace.mm_trace.cli build --config configs/mm_trace/fixture.yaml --offline
python -m disastertrace.mm_trace.cli validate --bundle artifacts/mm_trace/fixture

# 只有 G1 权限和已批准 manifest 才可执行
python -m disastertrace.mm_trace.cli sources fetch --approved-manifest artifacts/mm_trace/download_approval.json

# 实际下载/准入通过后的离线构建
python -m disastertrace.mm_trace.cli build --config configs/mm_trace/pilot_full.yaml --offline
python -m disastertrace.mm_trace.cli validate --bundle artifacts/mm_trace/pilot_full

# 以下需要单独 G2 授权；preflight本身占GPU时也需授权
python -m disastertrace.mm_trace.cli preflight --profile artifacts/mm_trace/model_lock.json
python -m disastertrace.mm_trace.cli run --freeze artifacts/mm_trace/live_freeze.json
python -m disastertrace.mm_trace.cli score --run artifacts/mm_trace/runs/approved_run
python -m disastertrace.mm_trace.cli report --run artifacts/mm_trace/runs/approved_run
```

报错时非零退出；不将“跳过全部实测”写成模型测试成功。CLI 命名调整可接受，但必须给出对应表，避免文档命令与实现不一致。

---

## 14. 分阶段任务、交付物与验收

### S0｜仓库审计与最小故障隔离

**目的：**不重复旧研究，不让新工作破坏旧科学证据。

- [ ] 读取 AGENTS、HEAD、dirty diff、冻结清单、进展指针与受保护划分。
- [ ] 梳理现有 compiler、public view、collector、scorer 可复用接口。
- [ ] 核查三种历史配置是否仍为累计原文；如已改变，记录实际差异。
- [ ] 在新运行器或适配层上实现 trajectory 级故障隔离。
- [ ] 用模拟后端验证一条超限/失败后，另一条独立轨迹仍完成。

**交付：**`REPO_AUDIT.md`、`SCOPE_CONTRACT.md`、最小回归测试、未修改的历史文件校验结果。

**通过条件：**没有修改冻结字节或隐藏新权限；未提交的机会、已提交未知状态与已经返回的回答可区分。

### S1｜10–20 组候选的图文可行性检查

**目的：**确认存在可做的题，而非先搭巨大框架。

- [ ] 生成来源下载 dry-run。批准后取得最少的开发样本，否则使用本地已有资料。
- [ ] 实现 `ArtifactMeta`、`FactKey`、time policy 与来源准入。
- [ ] 对实际 ZIP 列 layer、字段和时间；native图/GIS配对另有证据。
- [ ] 先完成一个渲染图 episode：公开图文 → 程序参考 → mock提交 → 确定性评分。
- [ ] 完成一个真实资料驱动候选的可读性、时间配准与模态必要性报告。
- [ ] 若真实样本不存在/不足，隔离并提交具体失败原因，不能拿 synthetic fixture代替验收。

**交付：**`SOURCE_MANIFEST.jsonl`、`LAYER_CATALOG.json`、`ALIGNMENT_REPORT.json`、`ADMISSION_REPORT.md`、可追溯样例。

**通过条件：**至少有清晰支持的完整候选；分别报告代码 fixture 通过与真实资料准入状态。只有前者时状态为 `NEEDS_REAL_SOURCE_VALIDATION`。

### S2｜构建局部修订 pilot 与配对分支

**目的：**从单个读图题推进为可解释的动态 benchmark。

- [ ] 实现四类任务、三值研究规则、自动定位与局部义务。
- [ ] 编译 base/delay/withhold/stale/null 的分支参考。
- [ ] 增加至少“来源变值不变”“值变条件不变”“值/条件都变”“缺证恢复”四类转换。
- [ ] 完成必要性见证、无泄漏公共投影、共享artifact分组和split审计。
- [ ] 输出 mock/program/oracle 的独立对照，不声称为 LLM 成绩。

**pilot 目标，而非已满足数据量：**约12 episodes、至少8个开发风暴候选、约60个基础检查点；≥20个非KEEP转换，≥一半关键转换真正依赖视觉或图文联合。共享产品会减少独立组数，必须据实记录。不要为了凑8个名字拆分同一事件。

**交付：**`TASK_CARD.md`、public/private bundles、`OBLIGATIONS.jsonl`、`TWIN_RELATIONS.jsonl`、`SPLIT_AUDIT.json`、完整离线验收。

### S3｜Full-evidence 的分层诊断与开发实测

**目的：**分清图像感知、目标对齐、来源选择和状态修订。

- [ ] 在独立开发样例完成模型/processor/输出契约预检。
- [ ] 先冻结原子感知、oracle感知、全图文三个小诊断，获得有效性证据。
- [ ] 接入四个系统，在同一访问轨道内公平比较，记录全部内部调用。
- [ ] G2获批后执行预注册矩阵，保存原始输出与实际图像输入。
- [ ] 输出分项、逐组、逐转换类型结果，而不只一个总分。

**交付：**`MODEL_LOCK.json`、`LIVE_FREEZE.json`、原始请求/回复日志、分项与成本报告。

**通过条件：**运行可重建且主要失败原因可解释。若仅感知困难，结论降为感知瓶颈，不伪装成记忆失败。

### S4｜Streaming、缓存及载体审计

**目的：**真正测试有限历史条件下的状态维护和视觉依据使用。

- [ ] 冻结旧资产访问、文本状态与视觉缓存预算。
- [ ] 检查所有可能回读旧证据的路径，含工具、缓存、摘要和自动日志。
- [ ] 分开 mask-text-state 与 mask-all-memory，不让其他载体补回被移除信息。
- [ ] 选择真实保存前缀，进行 Actual/Masked/Oracle/Edited 与相关/无关编辑。
- [ ] 同前缀单步及闭环恢复分别报告，保留 null effect、反向变化和未恢复情况。

**交付：**`STREAMING_CONTRACT.md`、缓存日志、prefix forks、`CARRIER_AUDIT_REPORT.md`。

### S5｜独立事件扩展与冻结测试

**目的：**检验跨事件、生命周期和模型的适用性，不以重复题量代替外推。

- [ ] 按预定事件/生命周期规则增广，不只每个风暴前六份公告。
- [ ] 保留增强/衰减、区域进入/退出、支持缺口/恢复等可核查转换。
- [ ] 选择新的未用于调参的来源组；所有派生样本随共享artifact组划分。
- [ ] 在开发完成后冻结方法与预算，G3获批再运行heldout。
- [ ] 发布结果时区分自然原图、官方数据重绘、受控交付与合成fixture。

**交付：**最终数据卡、版本化 evaluator、可复现运行说明、完整结果/负结果与限制。

**AutoResearch仅后续可选：**冻结 dev evaluator 后限定修改 prompt、selection、state rendering/recheck policy。禁止改 raw、Gold、split或测试难度；全部候选成本与失败保留。它不是本阶段必做，也不默认启动模型训练。

---

## 15. 计算预算与运行政策

### 15.1 基础矩阵示例

单一 `full_evidence` 轨、仅 base 条件：

```text
12 episodes × 5 checkpoints × 4 systems × 2 models × 2 repeats
= 960 次最终作答机会
```

这个例子不包含 twins、单模态/感知 oracle、Streaming、载体审计或系统内部调用。**不是完整研究总预算，也不是已经获批的960次调用。**变长轨迹用 `sum(checkpoints)` 重新计算。

先用小型开发样例估计峰值显存、视觉 token、实际吞吐和内部调用成本；在总矩阵冻结前输出每块单独预算。不要一次性运行所有维度笛卡尔积。

### 15.2 默认配置示例（待Codex实现）

```yaml
experiment:
  task_version: mm_trace_v1
  split: development
  access_track: full_evidence
  conditions: [base]
  methods: [direct, version_filter, state_rechecker, state_rechecker_visual_cache]
  repeats: 2

permissions:
  allow_source_download: false
  allow_weight_download: false
  allow_gpu_preflight: false
  allow_model_generation: false
  allow_paid_api: false
  allow_training: false
  allow_heldout: false

runtime:
  max_concurrent_gpus: 0
  max_final_answer_slots: 0
  max_total_model_calls: 0
  max_total_generated_tokens: 0
  deadline_utc: null
  model_retry_policy: no_resampling
  isolate_failure_by: trajectory

reference:
  branch_specific_gold: true
  main_score_llm_judge: false
  inject_gold_into_requests: false
  preserve_all_scheduled_slots: true
```

所有 `0/null` 是默认关闭，不是建议正式运行额度。获批的 `LIVE_FREEZE` 才写入真实值。若用户后续同意最多四张 H100，也要合计预检、排队/保留和正式作业，不把“每方法四卡”误作全局四卡。

---

## 16. 必做测试清单

以下测试采用fixture/mock优先，核心逻辑无需GPU。对真实数据另报准入，不能把这些测试数当事件数量。

| 类别 | 测试 | 必须满足的性质 |
|---|---|---|
| 时间 | 较新公告属于另一有效时刻 | 固定目标不被错误更新 |
| 时间 | 相同lead但不同绝对时间 | 不匹配成同一目标 |
| 时间 | 滚动120小时窗口变化 | 不计为 fixed-target 数值修订 |
| 时间 | 历史available未知 | 不自动填issued/retrieved；严格轨拒收 |
| 版本 | 已知新版本后旧版迟到 | 不回退 |
| 版本 | 同值新覆盖 | 值保持、支持刷新分别正确 |
| 版本 | 重复交付同artifact | 增加delivery事件，不创造新版本 |
| 局部性 | P变化、Q值不变但支持换版 | P更新；Q保持值且按需换支持 |
| 依赖 | 上游变化但阈值结果不变 | 标记需复核，不强制改变布尔结果 |
| 依赖 | 任一必要前提unknown | 按三值逻辑传播，不转false |
| 缺证 | withholding关键图 | 分支Gold转未知或旧支持状态，符合查询政策 |
| 分支 | 同一终端合法证据集合 | 内容型结论一致；到达延迟指标可不同 |
| 图像 | 图例只有概率区间 | 不按私有小数值要求精确输出 |
| 图像 | bbox/grid跨概率区 | 定位与点值分开，避免整格单值假设 |
| 图像 | 目标在边界/地图范围外 | 按冻结可读性/边界政策处理 |
| 几何 | CRS、经度符号、日界线、洞 | 不发生简单平面误判或轴序错配 |
| 泄漏 | policy读取private目录 | 被隔离并留下访问记录 |
| 泄漏 | 查询未来文件ID/检索未来版本名 | 工具拒绝，正文和元数据均不可见 |
| 泄漏 | filename/caption透露label | 必要性/公开视图扫描发现并阻断 |
| 划分 | 两个storm共享同一WSP源图 | 派生样本在同一split component |
| 状态 | 合法但错误commit | 不被Gold改正，后续错误如实传递 |
| 状态 | invalid/missing commit | 固定政策与明确标记，不静默oracle恢复 |
| 缓存 | 未交付图或超额crop被请求 | 拒绝/淘汰符合预定政策，不按Gold选择 |
| 载体 | mask后视觉缓存含同一事实 | 标记重建路径，不能称纯状态必需测试 |
| 载体 | 当前证据反驳edited字段 | 修复算可靠，盲从不算高因果能力 |
| 运行 | 某轨context超限 | 其他独立轨继续，全计划分母保留 |
| 运行 | 提交后响应未知 | 不自动生成第二条替代答案 |
| 评分 | Gold locator有多个等价解 | 按预先允许集合接受，不临时放宽 |
| 安全 | ZIP路径穿越/HTML伪装/超额下载 | 非零退出，无写出白名单外文件 |
| 回归 | 新工作前后冻结旧文件哈希 | 保持一致 |

增加性质测试：对不改变语义的输入展示顺序/公开 ID 重命名，参考不变；对 delay/withhold，参考变化符合独立分支求解；对纯null，不允许参考发生无根据变化。

---

## 17. 每阶段汇报格式与最终交付

每次提交一个小而完整的变更包，不把日志/原始图片全塞进Git。未经明确授权不 push、创建远程PR或发布私有数据。

阶段报告格式固定为：

```text
Stage / Run ID:
Parent code commit:
New code paths:
Research question addressed:
Data actually read/downloaded:
Files actually changed:
Commands actually run:
Tests passed / failed / not run:
Real-source admission status:
Actual model calls / GPU-hours / bytes downloaded:
Frozen artifacts unchanged:
Remaining blockers:
Next executable command:
Permission needed for that command:
```

没有进行模型生成时明确写 `model_calls=0`，不得把mock/oracle或程序solver输出算作模型成绩。工具执行失败也不表示原实验自动成功。

**S2离线包至少包含：**任务卡、类型/schema、来源manifest、来源许可记录、实际样例、渲染与配准记录、分支Gold、独立对账、必要性见证、split审计、测试输出。

**S3/S4实测包额外包含：**权重/processor锁、运行权限与预算、槽位manifest、实际prompt和图像hash、所有模型回复/可得token信息、状态缓存谱系、错误与未尝试、逐组/逐类型分数、完整成本。

**面向投稿的结论只写已有证据支持的内容。**不因为“没有新人工标注”“程序可以满分”“模型分数很低”就宣布无标签误差、业务安全、普遍记忆机制或首创。

---

## 18. 立即可交给 Codex 的启动文本

```text
请在当前 disastertrace-benchmark 仓库中执行
DisasterTrace_MM_Codex_Next_Plan_CN.md。

先遵守现有 AGENTS.md，检查 HEAD、工作树、冻结产物、最新终态记录
和 protected heldout 元数据。不要回退到文中历史 commit。

第一轮只完成 S0–S1 中已有权限允许的离线实现：仓库审计、复用接口映射、
mm_trace 数据契约、公开/私有证据视图、来源下载 dry-run、一个端到端
合成fixture和测试。真实开发资料本地已存在时继续完成对应准入检查。

这是一项代码实施任务，不要只再写一份方案。也不要把fixture当作真实数据。
每个新增功能说明它对应哪个RQ，以及怎样验证。

没有新的明确授权时，不联网批量下载，不下载模型权重，不提交GPU作业，
不进行模型生成、付费API、训练、LLM judge、heldout运行或远程发布。
缺少数据/依赖时说明精确URL、路径、体量和阻塞点，继续做其余离线工作。

保留全部既有数据、分数和失败；新任务用独立版本，不改旧评分。
结束时返回实际代码变更、实际测试结果、验收状态和下一步命令。
```

---

## 19. 来源、核查范围与链接使用说明

### 项目来源

- [P1] 原计划：[Notion 导航](https://app.notion.com/p/3ceff220ec69818693f8e30889bc7c1f)；[13.3A 完整研究方案](https://app.notion.com/p/3cfff220ec6981fc83c6f48cad66a035)。
- [P2] [历史固定提交结果入口](https://github.com/sisuolv/disastertrace-benchmark/blob/36082c42a93e11f67d274d8000c87cd1dc098d74/RESULTS_20260909.md)。
- [P3] [当前分支进展指针](https://github.com/sisuolv/disastertrace-benchmark/blob/next-phase-v1/disastertrace-starter/CURRENT_PHASE.md)；[复查说明](https://github.com/sisuolv/disastertrace-benchmark/blob/36082c42a93e11f67d274d8000c87cd1dc098d74/disastertrace-starter/REVIEW_FOR_CHATGPT_PRO_P6_PLUS.md)。
- [P4] [原文输入协议](https://github.com/sisuolv/disastertrace-benchmark/blob/36082c42a93e11f67d274d8000c87cd1dc098d74/disastertrace-starter/src/disastertrace/forecast_task/protocol.py)；[P7完成报告](https://github.com/sisuolv/disastertrace-benchmark/blob/36082c42a93e11f67d274d8000c87cd1dc098d74/disastertrace-starter/artifacts/p7_forecast_live_v1/FINDINGS.md)。

这些私有仓库链接需要已有访问权限。本文件不包含访问token，也不要求将私有资料上传到第三方系统。

### 开源与数据核查

本轮实际读取：两份上轮Markdown完整内容、用户仓库 `CURRENT_PHASE.md`；CyPortQA分支commit、dataset/source_data/MultiModalInput的GitHub Contents元数据；NHC官方GIS说明与两个FTP-over-HTTPS目录；STALE、VersionRAG、lmms-eval项目页；两份模型卡、HF下载CLI和近邻论文页面。

配套 `resources.seed.json` 只记录候选资源与核查级别，所有 `download_enabled` 默认为 false；它不是已验收下载清单，不能直接替代未来 CLI 要求的已批准 manifest。主计划也包含全部关键链接，可单独交给 Codex。

数据链接见第3节；代码/论文链接见第4节。GIS操作说明：[GeoPandas overlay](https://geopandas.org/en/stable/docs/user_guide/set_operations.html)。模型来源：[M1 Qwen3-VL-8B-Instruct](https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct)、[M2 InternVL3-9B](https://huggingface.co/OpenGVLab/InternVL3-9B)。

**本轮没有取得并校验GIS压缩包、完整CyPortQA或模型权重，没有运行新benchmark。**工作容器网络请求发生DNS解析失败，NHC主域部分网页访问也受限；因此本文件只将目录确认和元数据确认写为已核查，字节校验与图文配准仍是S1任务。链接失效时依据官方目录/原仓库重新解析，不猜镜像或补造文件。

相对上轮研究稿，本计划新增的实施细化包括：事实键与查询模式分离、artifact/delivery身份分离、支持刷新与值保持并存、缓存影响下的carrier审计、真实下载路径修正和分阶段权限。它们是待实现规格，不是额外已完成研究结果。
