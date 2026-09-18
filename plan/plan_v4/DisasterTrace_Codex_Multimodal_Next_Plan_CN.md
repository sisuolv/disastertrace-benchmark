# DisasterTrace 多模态后续实施计划｜给 Codex 的执行说明

> **用途**：在现有 DisasterTrace 仓库上实现下一阶段的多模态任务，不重建整个项目，不改写已经冻结的文本实验。
>
> **计划状态**：待实施方案。本文给出新模块、接口、实验和验收要求；不表示这些模块已存在、数据已完整下载、外部方法已复现或模型实验已通过。
>
> **编制日期**：2026-09-08。外部资源以本文核查时可读的官方页面、作者仓库及数据卡为依据；执行时必须重新记录版本与实际下载结果。

## 0. Codex 先读：本轮到底做什么

请将多模态从附加实验提升为下一版的核心任务：

**当灾害文本、地图或影像异步更新时，模型能否依据相关视觉变化，只修订应该改变的状态，保留不受影响的判断与未知，并在后续查询中继续使用以前收到的视觉证据？**

推荐工作标题：

**DisasterTrace: Benchmarking Grounded State Revision over Asynchronous Multimodal Disaster Evidence**

### 0.1 必须遵守的实施顺序

1. **先保护旧资产**：检查实际仓库、`AGENTS.md`、本地改动、当前阶段和数据划分。
2. **先建立一条真实图文闭环**：官方来源 → 小样本下载 → 图文对齐 → 模型可见输入 → 自动参考 → 评分。
3. **再建立多模态修订任务**：异步到达、局部空间变化、旧图重放、后续新目标查询。
4. **先用一个 VLM 做诊断**：同一模型比较不同输入和历史，不先铺开大模型排行榜。
5. **最后增加一个原生遥感扩展**：SpaceNet 8 或 GEOID-Flood 二选一，不能同时开启多个大型数据工程。

首轮默认交付 **MM-P0 至 MM-P2 的代码与 CPU 验证**。真实模型生成、权重下载、大型影像下载及 GPU 作业，在对应预算和执行权限明确后进行。过去某个已结束的自主运行窗口不自动授权本轮计算。

### 0.2 不做什么

- 不把旧文本结果更名为多模态结果；不覆盖旧 Gold、评分器、原始响应、失败记录和冻结协议。
- 不把任务扩成开放式撤离建议、真实港口关闭决策、道路通行安全判断或数值天气预报。
- 不新增逐题 LLM judge 作为主评分，不让 LLM 生成的解释直接充当 Gold。
- 不训练新的遥感基础模型，不先搭建完整多 Agent 平台，不把 AutoResearch 放入首轮关键路径。
- 不通过不断加噪声、增加格式约束或筛掉高分样本来制造“novelty”。

### 0.3 每个里程碑结束时怎样汇报

提交一段简短的执行报告，包含：实际改动文件、实际执行命令与结果、验收项通过/失败、资源消耗、阻塞项、下一步。未运行的测试写 `NOT_RUN`，不可写“预计通过”。数据入口可访问、文件下载成功、解析通过、模型请求成功和科研结论成立是不同状态，分别报告。

---

## 1. 项目现状与新计划的边界

### 1.1 本计划依据

| 依据 | 本计划继承的内容 | 使用边界 |
|---|---|---|
| 原始 `DisasterTrace_Paper_Storyline_CN(3).md` | 内容、来源、持续可靠三层测量；自动评分；受控与原生任务分开 | 原文是历史证据快照，不当作执行时最新结果 |
| `DisasterTrace_Multimodal_Core_Plan_CN.md` | MM1 异步对齐、MM2 选择性修订、MM3 视觉历史使用 | 本文将其细化为工程任务，不将研究建议写成已实现功能 |
| 实际读取的 `forecast_task/protocol.py` | 模型自己的历史、固定机会、累计公开证据 | 不修改它来偷偷变成增量证据协议 |
| 本文末尾的官方资源与作者代码 | 数据入口、下载方式、可复用模块 | 代码和数据需要各自核验许可、版本、实际可用性 |

本次读取到的仓库：

- 仓库：<https://github.com/sisuolv/disastertrace-benchmark>
- 分支：`next-phase-v1`
- 观察到的提交：`36082c42a93e11f67d274d8000c87cd1dc098d74`
- 已读协议：<https://github.com/sisuolv/disastertrace-benchmark/blob/36082c42a93e11f67d274d8000c87cd1dc098d74/disastertrace-starter/src/disastertrace/forecast_task/protocol.py>

**该 SHA 只是复查基点，不是要求将用户工作区重置到这个版本。** 本地可能有更新提交、尚未推送的产物和正在运行的任务。先读取实际状态，再决定新增代码位置。

### 1.2 必须保留的事实

旧 `snapshot`、`structured_state` 和 `answer_history` 都从同一份 `visible_source_ids` 构造截至当前的累计原文输入。差异在于是否附加模型之前的回答载体。因此，新版必须明确区分：

- **累计证据条件**：模型可以重读完整历史，用作参照。
- **增量证据条件**：本轮新增证据 + 自身载体 + 该方法声明的检索权限。

不能将两者混成同一种记忆实验。也不能将旧的纯文本 `Qwen3-8B` 结果视为新 `Qwen3-VL` 的已有成绩。

### 1.3 启动时检查的文件

先查看当前目录及其父目录的 `AGENTS.md`。下列路径是检查入口，不存在时记录实际替代路径，不要创建空文件伪装原文件：

```text
AGENTS.md
README.md
RESULTS_20260909.md
disastertrace-starter/AGENTS.md
disastertrace-starter/CURRENT_PHASE.md
disastertrace-starter/REVIEW_FOR_CHATGPT_PRO_P6_PLUS.md
disastertrace-starter/REVIEW_FOR_CHATGPT_PRO_P5.md
disastertrace-starter/src/disastertrace/forecast_task/protocol.py
disastertrace-starter/src/disastertrace/forecast_task/contract.py
disastertrace-starter/src/disastertrace/forecast_task/compiler.py
disastertrace-starter/src/disastertrace/forecast_task/scoring.py
```

允许复用既有调度、哈希、原始响应保存和独立重建思想；是否能直接 import 某个实现，必须通过读取接口和回归测试决定。

---

## 2. 冻结研究问题与最小交付

### RQ-MM1：不同模态异步到达时，系统能否正确对齐证据？

区分发布时间、观测时间、目标有效时间和实验交付时间；识别“新但不相关”与“旧但仍支持当前目标”。不默认最后到达的材料最权威。

### RQ-MM2：视觉变化能否导致正确且局部的状态修订？

不仅问地图哪里变了，还问哪些事实、来源和派生判断应该变化，哪些应该保持，哪些仍应未知。

### RQ-MM3：先前视觉证据是否能够服务后续的新查询？

在模型已经保存历史后，再指定之前没有直接询问的地点。比较文字摘要、空间状态、保留图像和历史检索，检查信息保留与版本复查。

### 2.1 最小有效交付应是什么

首个试点至少应形成：一条真实来源图文轨迹、一个带自动 Gold 的局部修订样本、一组模态必要性诊断、一次旧图重放、一类后续新目标查询，以及能从原始输入和响应复算的评分。

`3–5 个开发事件`、`20–30 个关键转变候选`是后续试点的工作目标，不是已采集规模，不是统计充分性保证。若资料不足，报告实际覆盖；不得为了凑数量编造官方历史。

### 2.2 区分三种材料性质

| 类型 | 含义 | 允许怎样描述 |
|---|---|---|
| `native` | 原始官方图、公告或原生遥感影像 | 原始资料上的任务 |
| `official_data_rendered` | 用真实官方 GIS/数值数据确定性重绘地图 | 官方数据重渲染诊断，不称为官方原图 |
| `controlled_generated` | 人工设定规则、交付顺序、反事实组合或合成 fixture | 受控任务/干预，不称为真实历史发生 |

图像来源、文字来源、任务规则来源和交付时序来源分别标记。一个 episode 可以使用真实图像和受控规则，但不能因此整体标为“原生业务任务”。

---

## 3. 第一条主线：NHC 图文修订任务

### 3.1 优先选择的空间任务

先做指定地点相对某个明确预报风圈或地图分区的关系：`inside / outside / boundary_ambiguous`。再将关系与文字中的关注名单、时间条件或公开核查规则组合。

后续才扩展到路径与区域相交、多个空间关系的组合。不要首轮就引入道路可通行性、撤离路线最优性或高成本行动效用。

**任务中的风圈覆盖仅表示指定产品与目标时刻的覆盖关系，不表示实际地面风速已经达到阈值，也不自动表示损害或设施关闭。**

### 3.2 一个可实现的五轮教学轨迹

以下只是解释协议的示例，不应写入 `natural_case.json` 冒充真实风暴。固定目标为同一个绝对有效时刻。任务规则：关注名单内、处于指定预报风圈中的地点进入核查名单。

| 轮次 | 新证据 | 应有行为 |
|---|---|---|
| c0 | V1 地图中 A/B 在圈内；文字关注 A/B | 记录 A/B 空间关系和核查名单 |
| c1 | 文字更新中心强度，未明确更新 A/B 覆盖 | 不把中心强度变化直接等同于所有地点覆盖变化 |
| c2 | 同目标有效时刻的 V2：A 圈外、B 圈内 | 修订 A；保留 B 的值，但分别判断其来源是否应更新 |
| c3 | 旧图 V1 重放 | 记录交付事件，不用旧图覆盖 V2 |
| c4 | 文字关注改为 B/C，查询此前图中尚未问过的 C | 使用仍适用的 V2 空间信息，不只复制旧答案 |

实际自然资料不必恰好具有以上顺序。自然轨迹按照资料本身编译；延迟、重放、规则更新与反事实组合放在独立的受控轨道。

### 3.3 必须先检查“文字已经把图像答案说完了”

NHC 文字产品中可能存在足以重建某张图的坐标、风圈半径或其他数值。Codex 必须检查实际配对资料，不得因为输入里出现图片就判定任务需要视觉。

按以下方式处理：

1. **完整原文确实足以解题**：保留为 `redundant_modalities` 对照，不计入“视觉必要”子集。
2. **另一个完整、适用的文字产品不含所需空间事实**：可以作为真实图文任务，但保存该产品的完整来源与选择规则。
3. **为诊断而移除文字中的重复空间字段**：允许单独建 `controlled_modality_partition`，必须保留原文和公开投影差异；不得继续称作完整原文条件。
4. **使用自定义关注名单/核查规则**：标为 `benchmark_rule`，不伪装成官方历史公告。

图文双模态的“必要性”只针对具体输入条件。空间事实原则上可以编码成文字，不能声称它天然不可符号化。

### 3.4 固定绝对时间，不混淆地图产品

查询键建议为：

```text
(event_id, target_id, product_family, variable, measurement_kind,
 threshold, absolute_valid_time_or_interval, spatial_scope)
```

必须遵守：

- 发布相隔六小时、都标“24H”的两份图，不一定针对同一绝对有效时刻。
- 风圈、路径不确定性锥、风速概率不是同一产品，不相互代替。
- 累计概率、首次开始概率、某时段发生概率不能混用；首版非必要时不进入概率产品。
- 不使用“中心在圈外”或“中心强度下降”替代目标地点的空间判断。
- 缺图、目标在显示范围外、产品无覆盖、存在遮挡，不自动推出 `outside`。
- 不将未来归档、更正或最终最佳路径资料加入当前检查点输入。
- 只知道 `issued_at` 时，使用明确标注的受控 issued-order replay；`historical_available_at` 保持 `null`。

---

## 4. 数据与代码资源登记表

### 4.1 数据：先 NHC，再选择一个原生遥感扩展

| 优先级 | 资源与链接 | 用途 | 本次核查与执行边界 |
|---|---|---|---|
| P0 | [NHC GIS 官方入口](https://www.nhc.noaa.gov/gis/)；[本次可读官方节点](https://prod-east-nhc.woc.noaa.gov/gis/) | 公告配套地图、风场及预报风圈候选 | 产品索引可核查；部分 `www` 页面本次返回 403，未完成图像/GIS 二进制下载验证 |
| P0 | [NHC GIS forecast archive](https://www.nhc.noaa.gov/gis/forecast/archive/)；[历史索引示例](https://www.nhc.noaa.gov/gis/archive_forecast_info_results.php?id=al09&name=Hurricane+IAN&year=2022) | 从实际索引枚举版本文件 | 索引示例不是指定开发事件；先查仓库 heldout，不能直接把 Ian 加入开发集 |
| P0 | [NHC 历史公告入口](https://www.nhc.noaa.gov/archive/) | 找到与图层相容的完整文字产品 | 优先复用仓库已保存原字节；新获取结果另建版本，不覆盖旧下载 |
| P1，二选一 | [SpaceNet 8 官方数据页](https://spacenet.ai/sn8-challenge/)；[作者代码](https://github.com/SpaceNetChallenge/SpaceNet8) | 原生灾前/灾后影像与道路/建筑相关标签 | 官方列出公开 S3 下载对象；本次未下载完整归档。优先公开训练标签，不假定测试包有可用 Gold |
| P1，二选一 | [GEOID-Flood 数据卡](https://huggingface.co/datasets/links-ads/geoid-flood)；[sample 目录](https://huggingface.co/datasets/links-ads/geoid-flood/tree/main/sample)；[作者代码](https://github.com/links-ads/geoid-flood) | 已配准 SAR、灾前光学影像及已有洪水标签 | 不下载全量。示例约 3 GB，先按文件大小筛小型完整样本；标签/派生掩膜必须与模型输入隔离 |

NHC 的历史版本是否足够、目标时间是否可对齐，必须以实际文件验证。某个请求 403/404 是一次访问结果，不等于全部官方数据不存在；也不能跳过验证宣称来源已打通。[D1–D3]

### 4.2 开源代码：复用什么，不复用什么

| 资源 | 具体复用点 | 不能默认成立的事 |
|---|---|---|
| [Qwen3-VL](https://github.com/QwenLM/Qwen3-VL)；[8B-Instruct 权重](https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct) | 官方多图消息、processor、推理接口；一个本地 VLM 起点 | 未在用户机器验证显存/依赖，不承诺直接沿用旧纯文本运行环境 |
| [Qwen3-VL-Embedding](https://github.com/QwenLM/Qwen3-VL-Embedding) | 后续图文检索适配，建立自己的时间/版本合法性过滤 | 向量相似度不等于适用版本；不直接用向量搜索替代证据门控 |
| [MMA](https://github.com/AIGeeksGroup/MMA) | 阅读记忆更新、检索与可信度处理，适配近邻 baseline | 不将其模型生成数据或模型评分流程移作本项目 Gold |
| [SpaceNet 8](https://github.com/SpaceNetChallenge/SpaceNet8) | 数据读取、已有影像处理和专业工具 baseline 参考 | 不要求先训练优胜模型；专业分割结果与参考标签必须分离 |
| [GEOID-Flood](https://github.com/links-ads/geoid-flood) | 文件索引、数据布局与配准元数据；读取下载脚本作参考 | 官方快捷下载命令不自动满足本项目版本固定与大小限制 |
| 已有 DisasterTrace 代码 | 调度、状态隔离、响应记录、失败保留、CPU 重建 | 不修改旧科学文件来“顺手修复”新旧所有任务 |

第三方只读放在独立 `third_party/` 或外部缓存，记录远端、完整 commit、许可证和修改补丁。未核实到直接可用实现的论文方法，可以做明确标注的 `paper_inspired_reimplementation`，不称为作者代码复现。[C1–C5]

### 4.3 两个实际下载陷阱

**GEOID-Flood 的 `--sample` 不是“任意小样本”。** 本次读取的 `scripts/get_data.py` 在处理 `--list` 和层选择之前就进入 sample 分支。因此，`--sample --list` 不能当作只预览；`--sample --layer ...` 也不能当作会按层缩小 sample。新适配器应直接使用固定 revision 的文件清单和字节预算。[C5]

**GEOID 的 sample 不构成独立事件泛化测试。** 数据卡列出的两个 sample AoI 都来自 `EMSR712`，分别带 train/test 标记。这里用于验证读入流程可以，但本项目若要求事件级拆分，必须将它们视为同一事件组，而不是照抄 sample split 得出跨事件结论。[D5]

另外，SpaceNet 8 的 Louisiana 数据与 Hurricane Ida 有关；若 NHC 轨也用了 Ida，必须共用同一 `global_event_id`，避免跨数据集把同一事件一边用于开发、一边用于“独立测试”。[D4]

### 4.4 许可账本

代码许可和数据许可分别保存。SpaceNet 数据页标注 CC BY-SA 4.0；GEOID 数据卡标注 CC BY 4.0，并需保留上游来源及 DEM 等组件条款。不能用仓库的 MIT/Apache 代码许可代替影像再发布许可。[D4–D5]

对外发布前再逐项审查 `redistribute_raw / redistribute_derived / metadata_only / unresolved`。许可未明确时可以只发布下载清单与任务生成代码，不默认上传原始图像。

---

## 5. 下载与版本固定：先列目录，再下小样本

本节有两类命令：**官方工具的真实入口命令**，以及后文要求 Codex 实现的**新项目 CLI**。不要将后者误认为现有命令。

### 5.1 默认下载护栏

建议首轮配置如下；这是本计划建议的执行上限，不是声称用户此前已经授权该预算：

```yaml
mode: offline_build
allow_paid_api: false
allow_gpu_job_submission: false
allow_model_weight_download: false
allow_full_dataset_download: false
max_single_data_file_bytes: 268435456       # 256 MiB
max_new_data_download_bytes: 536870912      # 512 MiB，总量含重试
max_download_workers: 2
max_attempts_per_file: 3
```

已有本地文件优先；检查内容哈希后复用。需要超过上限的完整训练包、GEOID 全 sample 或模型权重时，先输出下载计划和磁盘峰值，再取得该阶段预算。不要通过分片并发绕过总量上限。

下载器必须做到：HTTPS/S3/HF 来源白名单、超时、有限重试、字节计数、`.part` 文件、内容类型/压缩格式检查、SHA-256、大小核对、安全解包和下载收据。防止将 HTML 错误页保存为 `.zip`；拒绝路径穿越、符号链接逃逸和异常解压膨胀。日志中不得保存 token 或签名 URL 的敏感参数。

### 5.2 NHC：从官方索引获取真实文件 URL

入口：

```text
https://www.nhc.noaa.gov/gis/
https://prod-east-nhc.woc.noaa.gov/gis/
https://www.nhc.noaa.gov/gis/forecast/archive/
https://www.nhc.noaa.gov/archive/
```

实现一个索引发现器，先保存页面原文和最终 URL，再解析实际 `href`。记录每个候选对象的事件、产品、版本、文件名、发现页与 HTTP 状态。**不根据一个示例文件名拼出整场风暴“应该存在”的所有文件并把它们记为已发现。**

历史索引示例：

```text
https://www.nhc.noaa.gov/gis/archive_forecast_info_results.php?id=al09&name=Hurricane+IAN&year=2022
```

该链接仅展示索引形式。事件选择必须服从既有开发/保留划分。优先寻找一个已有开发事件的两份可对齐产品，再增加事件。

检查点：ZIP 内是否真有预期图层；`.prj`/CRS、单位、属性名、绝对有效时间是否可解析；同一图层和公告是否真实匹配。不要猜测所有年份的字段名一致。

### 5.3 SpaceNet 8：官方公开 S3 对象

以下地址来自官方数据页，不是推测文件名：[D4]

```text
s3://spacenet-dataset/spacenet/SN8_floods/tarballs/Germany_Training_Public.tar.gz
s3://spacenet-dataset/spacenet/SN8_floods/tarballs/Louisiana-East_Training_Public.tar.gz
s3://spacenet-dataset/spacenet/SN8_floods/tarballs/Louisiana-West_Test_Public.tar.gz
```

先查看目录和对象大小，不直接下载所有包：

```bash
aws s3 ls s3://spacenet-dataset/spacenet/SN8_floods/ --no-sign-request

aws s3api head-object \
  --bucket spacenet-dataset \
  --key spacenet/SN8_floods/tarballs/Germany_Training_Public.tar.gz \
  --no-sign-request \
  --query '{Bytes:ContentLength,LastModified:LastModified,ETag:ETag}'
```

确认完整包大小、许可与磁盘预算后，才执行选择的下载，例如：

```bash
# 本命令会下载完整训练包，不属于默认小样本预算；取得预算后再执行。
: "${APPROVED_DATA_DIR:?请设置已批准的数据目录}"
mkdir -p "$APPROVED_DATA_DIR/spacenet8"
aws s3 cp \
  s3://spacenet-dataset/spacenet/SN8_floods/tarballs/Germany_Training_Public.tar.gz \
  "$APPROVED_DATA_DIR/spacenet8/Germany_Training_Public.tar.gz" \
  --no-sign-request
```

S3 ETag 不一律等于文件内容 MD5，更不等于 SHA-256；下载后仍计算本地 SHA-256。若目录存在更细粒度公开对象，先确认实际键，再按完整样本组下载；不能假定这种布局存在。

### 5.4 GEOID-Flood：固定 HF revision，只下载明确选定的文件

官方入口：

```text
https://huggingface.co/datasets/links-ads/geoid-flood
https://huggingface.co/datasets/links-ads/geoid-flood/tree/main/sample
https://github.com/links-ads/geoid-flood
https://raw.githubusercontent.com/links-ads/geoid-flood/main/scripts/get_data.py
```

先在新环境中使用 `huggingface_hub` 读取元数据。以下代码只列目录和大小，不下载影像文件；执行时有网络请求，本次编写计划并未运行它：

```python
from __future__ import annotations

import json
from pathlib import Path

from huggingface_hub import HfApi

repo_id = "links-ads/geoid-flood"
api = HfApi()
revision = api.dataset_info(repo_id).sha
if not revision:
    raise RuntimeError("Dataset revision is unavailable; do not fall back to unpinned main.")

files = []
for item in api.list_repo_tree(
    repo_id=repo_id,
    repo_type="dataset",
    revision=revision,
    path_in_repo="sample",
    recursive=True,
):
    size = getattr(item, "size", None)
    if size is not None:
        files.append({"path": item.path, "bytes": int(size)})

manifest = {
    "repo_id": repo_id,
    "repo_type": "dataset",
    "revision": revision,
    "purpose": "listing_only_not_a_download_selection",
    "total_listed_bytes": sum(row["bytes"] for row in files),
    "files": sorted(files, key=lambda row: row["path"]),
}
out = Path("geoid_sample_listing.json")
if out.exists():
    raise FileExistsError(f"Refusing to overwrite {out}; use a new audit directory.")
out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"revision={revision}; files={len(files)}; bytes={manifest['total_listed_bytes']}")
```

从生成清单中选择一个完整样本需要的 pre/post 影像及评测侧标签，保存为另一份 `download_selection.json`。不得将“全目录清单”自动当作“全部已获准下载”。

HF 官方工具支持固定 revision 的 dry run；先从清单读取完整 SHA：[T1]

```bash
export GEOID_REVISION="$(python -c 'import json; print(json.load(open("geoid_sample_listing.json"))["revision"])')"
: "${GEOID_REVISION:?未获取数据集 revision}"

# 先核查小型元数据请求；--dry-run 不下载请求的文件内容。
hf download links-ads/geoid-flood README.md SHA256SUMS shard_index.json.gz \
  --repo-type dataset --revision "$GEOID_REVISION" --dry-run

# 必须把 GEOID_FILE 设为已经列出并通过预算核对的真实文件路径。
: "${GEOID_FILE:?从清单选择一个真实文件，不能使用通配符全库下载}"
hf download links-ads/geoid-flood "$GEOID_FILE" \
  --repo-type dataset --revision "$GEOID_REVISION" --dry-run
```

通过预算后，下载器调用 `hf_hub_download(repo_id, filename, repo_type="dataset", revision=..., local_dir=...)`。每次只传清单内路径，保留 revision 和来源。不要直接复制作者的无参数全量下载命令，也不要使用 `--sample --list` 进行所谓预检。

### 5.5 模型下载与依赖

模型入口：

```text
https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct
https://github.com/QwenLM/Qwen3-VL
https://github.com/QwenLM/Qwen3-VL-Embedding
```

先检查是否已有本地模型。下载时通过 `HfApi.model_info(...).sha` 固定模型完整 revision，并使用 `hf download ... --revision ... --dry-run` 查看请求大小。模型权重不计入“小型资料”的默认许可范围。

不要直接在旧运行环境执行 `pip install -U transformers vllm`。创建独立环境，核对官方模型类、processor、图像 token 处理和 backend 支持后固定版本；CPU 数据构建环境与 GPU 推理环境可以分开。

---

## 6. 新模块结构与依赖边界

下列是**建议新增结构**，不是已存在路径。若实际仓库已有同功能的新阶段，优先适配，避免再复制一个平行工程。

```text
disastertrace-starter/
  plans/multimodal_v1/
    PLAN.md
    SCOPE.md
    REUSE_MAP.md
    DATA_POLICY.md
    EXPERIMENT_PROTOCOL.md
    EXECUTION_LOG.md
  configs/multimodal_v1/
    sources.yaml
    pilot.yaml
    protocol.yaml              # 机器可读协议，与 Markdown 对应
    budgets.yaml
  src/disastertrace/multimodal_v1/
    models.py                  # 证据、交付、查询、答案、载体类型
    ledger.py                  # 原始内容与来源登记
    temporal.py                # 时间、目标与产品作用域
    evidence_gate.py           # 只开放合法证据；检索也必须调用
    adapters/
      nhc.py
      spacenet8.py              # 后续选中才实现
      geoid.py                  # 后续选中才实现
    downloads.py               # 固定版本、下载预算、收据、安全解包
    rendering.py               # 官方数据确定性重绘；不依赖答案选样式
    geometry_reference.py      # 评测侧空间参考
    visual_validation.py       # 实际图像可读性/边界/覆盖检查
    public_projection.py       # 向模型开放什么，唯一出口
    rules.py                   # 公开规则与三值逻辑
    compiler.py                # 状态与修订参考编译
    interventions.py           # 到达干预、语义相容配对、载体干预
    protocol.py                # 累计/增量协议与自身历史
    memory.py                  # summary/spatial/image/retrieval 适配
    vlm_backend.py             # 真正的多图请求与用量捕获
    scoring.py
    runner.py
    audit.py
    cli.py
  tests/multimodal_v1/
    test_temporal.py
    test_rules.py
    test_geometry.py
    test_public_isolation.py
    test_interventions.py
    test_memory.py
    test_scoring.py
    test_downloads.py
    test_runner.py
  artifacts/multimodal_v1/
    raw/                       # 原始下载与收据，不直接对模型暴露目录
    public/                    # 正常模型进程只读取此视图
    private_reference/         # 评测侧参考、标签、必要模态证书
    manifests/
    runs/
    reports/
```

优先用已有工程依赖与常见 GIS 库完成小闭环；不要首轮引入图数据库。依赖关系可以先用 JSON 邻接表和确定性拓扑求值。只有确实出现性能瓶颈才换复杂组件。

新包不得在 import 时读取模型权重、访问网络或启动 GPU。下载、编译、运行和评分应是显式独立命令。

---

## 7. 数据契约：证据与交付事件必须分开

### 7.1 不可变证据对象

证据主对象至少包含：

```yaml
artifact_id: a_opaque_0001
source_product: nhc_forecast_wind_radii
modality: image
origin_kind: official_data_rendered
source_event_id: null              # 下载/解析后填写，不编造事件
issued_at: null
observed_at: null
valid_at: null                     # 点时间产品填写
valid_interval: null               # 区间产品填 start/end；不用相对 lead 代替
historical_available_at: null
historical_availability_basis: unknown
version_id: null
supersedes_artifact_ids: []
variable: forecast_wind_footprint
measurement_kind: forecast
threshold: {value: 34, unit: KT}    # 只是本任务的拟定例子，实际按产品字段核验
spatial_scope_id: region_01
crs: null
source_url: null
content_sha256: null
parent_artifact_ids: []            # 重绘必须追到原始 GIS
render_spec_id: null
license_record_id: null
```

此处 `null` 表示待解析/未知，不是可直接用于正式任务的有效记录。编译器必须拒绝缺少必需目标时间和坐标语义的样本。

原始 URL、内容哈希、磁盘路径、标签路径和渲染父数据可存在审计账本中，**不要求全部进入模型提示**。公开投影必须显式白名单，防止文件名/标签目录/哈希成为答案线索。

### 7.2 交付事件

同一旧图重放应是新的 delivery event，而不是“新的图像版本”：

```yaml
delivery_id: d_0007
artifact_id: a_opaque_0001
checkpoint_id: c3
delivered_at: null                 # 真实实验调度确定后填写
schedule_kind: controlled
is_replay: true
```

`is_replay` 是私有诊断字段，正常输入是否公开由任务协议决定；不能直接把“这是错误旧图”作为答案提示。模型可见的发布时间/版本元数据应足以依公开规则处理。

### 7.3 查询与公开规则

查询包含地点或区域的公开位置、指定产品、变量/阈值、绝对有效时间和需要回答的状态槽位。规则需独立存档，例如：

```text
inspection_required(site) = watched(site) AND forecast_inside(site)
```

`inspection_required` 仅为演习核查规则。采用三值逻辑：

| A | B | A AND B |
|---|---|---|
| true | true | true |
| false | 任意 | false |
| 任意 | false | false |
| true | unknown | unknown |
| unknown | true | unknown |
| unknown | unknown | unknown |

真实冲突先保存来源间的冲突状态，不能未经规则定义就当作 false。派生求值是否将冲突保守映射为 unknown，必须写入公开契约。

### 7.4 模型输出与自身载体

建议正常输出仅包含以下内容：

```json
{
  "checkpoint_id": "c2",
  "states": [
    {
      "slot_id": "site_A.forecast_inside",
      "status": "known",
      "value": false,
      "evidence": [
        {
          "artifact_id": "image_2",
          "locator": {"kind": "image_point", "x": 0.42, "y": 0.58}
        }
      ]
    }
  ],
  "rule_outputs": [],
  "memory_commit": {
    "text": "",
    "spatial_records": [],
    "retained_images": []
  }
}
```

上述坐标是格式示例，不是任何实际图像的参考答案。图像定位使用最终提供给模型的图像坐标系，左上为原点，x/y 归一化到 [0,1]。裁剪和重采样要保留可逆映射或明确转换记录。

`unknown`、`conflict` 的 value/null 和引用要求在新协议固定；不能自动将模型输出的任意字符串归一化为正确答案。

历史处理建议沿用“原始最终文本永久保存、合法解析结果作为 typed carrier、非法/缺失设置显式标志”的原则。选择 last-answer 或 last-valid-answer 必须在 MM-P2 冻结，两者不能中途切换；默认采用 **last-answer + invalid/missing 标志**。错误但结构合法的值原样延续，不由 Gold 修复。

模型输出中的自述变化不是主评分依据。评分器应比较实际提交状态与参考状态，也比较相邻实际输出，独立判断改了什么。

---

## 8. 自动参考、视觉可解性与 Gold 隔离

### 8.1 三层参考

1. **资料事实参考**：官方 GIS/数值字段，或继承影像标签及其来源等级。
2. **当时可支持参考**：只从已合法交付资料和公开选择规则计算，允许 unknown/conflict。
3. **修订参考**：比较相邻状态和配对条件，得到值变化、来源变化、保持、未知和依赖重查集合。

比较的目标是“证据当前支持什么”，不是事后世界真值。预报图和灾后观测不得混成相同语义的 Gold。

### 8.2 不要求所有多模态任务都伪造一个满分 public oracle

对标准化重绘图，可以分别用 GIS 几何路径与实际公开渲染图的像素/图例路径检查一致性。两条路径不能共同 import 同一个最终 Gold；边界、投影和分辨率差异需明确容差。

但对任意原生遥感影像，已有标签并不意味着存在一个“仅看相同公开像素即可确定性满分”的程序。必须区分：

- `reference_from_private_geometry_or_inherited_labels`：参考可复算，但依赖评测侧资料。
- `public_visual_resolver_verified`：确实存在从模型可见材料解题的独立程序，并已实际验证。
- `visual_observability_checked`：有可读性检查，不能等价写成公开求解器满分。

不能把使用私有分割掩膜的程序输出报告成“公开视觉 oracle”。这一点与旧文本任务的独立公开解析器不完全相同，要诚实保留区别。

### 8.3 视觉可解性准入

在看待测模型分数之前固定准入规则：目标在图内、图例可读、产品时间明确、坐标系正确、目标与边界距离足够、关键像素没有被缩放/裁剪删除。

边界容差以最终输入像素和相应地理尺度共同定义。底层数据有精确小数，不代表图片也支持精确输出。不可读/边界不确定样本可以单独标为有明确契约的歧义子集，不能混进清晰二分类后让模型猜。

原生遥感的云、无效像素、SAR 显示变换和继承标签噪声分别记录。不得把 `ignore=255` 自动当作背景或“未淹水”。

### 8.4 四类修订集合应按“槽位 × 方面”定义

同一槽位可能值不变、来源改变，所以集合不应粗暴按整槽位互斥：

```text
must_change_value
must_change_provenance
must_preserve_value
must_preserve_provenance
must_remain_unknown
must_recheck_dependencies
```

`must_recheck_dependencies` 由上游变化及公开依赖关系得出；它不是模型内部推理标签。不能因模型写“已重查”就得分。

### 8.5 模型进程不可见的内容

私有掩膜、原始 GIS 参考几何、Gold 状态、正确图像裁剪框、答案候选集、未来查询、配对分支答案、受影响集合，均不得进入普通模型输入或可检索目录。

例外只能是预注册的 **Oracle/结构化事实诊断条件**，并单独记录 `assistance_level`。公开分级地图解释轨可以把分级地图当输入，但它不是原生影像理解轨。

---

## 9. 多模态必要性与外部证据干预

### 9.1 必要性证书

对受控诊断子集，构造两类配对：

- 非视觉输入完全相同，图片的相关空间事实不同，正确答案不同。
- 图片及图像元数据相同，文字关注条件不同，派生答案不同。

“非视觉输入相同”应核对完整请求投影，不只是公告正文；文件名、artifact alias、alt text、版本提示和附加摘要也可能泄漏差异。私有内容哈希不用于模型提示。

若为了保持相同文字元数据而对真实图片进行反事实替换，该组合必须标为 `controlled_counterfactual`，不声称历史上真的发布了这个组合。自然异步回放不必强行满足字节级相同，可用另一类配对证据解释。

必要模态证书记录输入投影哈希、不同的参考答案、可见证据差异、逻辑上无法由剩余输入唯一确定的原因。它证明特定条件下的信息需求，不证明模型内部关注了某个像素。

### 9.2 首轮外部干预

| 干预 | 固定什么 | 改变什么 | 预先确定的期望 |
|---|---|---|---|
| 图像延迟 | 图像内容和文字 | 图像交付检查点 | 未收到时按剩余证据回答；到达后更新 |
| 旧图重放 | 已收到的新版本 | 再交付旧图 | 当前相关状态不回退 |
| 无关图像更新 | 目标有效时间/地区的相关证据 | 另一对象/时段图片 | 当前目标保持 |
| 同目标视觉修订 | 公开规则、查询作用域 | 合法的新图版本 | 只修改相应事实和依赖结论 |
| 文字关注条件变化 | 地图 | 关注名单/演习规则 | 空间事实保持，相关派生输出变化 |

改变观测的物理时刻，与改变证据交付时刻，是两种实验。不把两时相影像重排成不存在的五时相世界演化。

### 9.3 “从未给图”与“收到后忘图”分开

- **从未交付必要图像**：参考按剩余证据重算；只有逻辑仍不充分时才是 unknown。
- **交付过但记忆方法丢掉图像**：参考仍按合法历史计算；不能为模型遗忘降低 Gold 要求。
- **模型本来没有权限重新检索图像**：这是公开的信息访问条件，不在运行中临时给它开后门。

---

## 10. 视觉历史与内部载体干预

### 10.1 正常方法的最小集合

| 方法 ID | 输入/记忆 | 角色 |
|---|---|---|
| `full_history_vlm` | 全部合法图文历史 | 累计证据参照；超预算不能静默截断后仍称 full history |
| `incremental_summary` | 新证据 + 模型文字摘要 | 基础增量记忆 |
| `incremental_spatial_state` | 新证据 + 模型自己提取的空间状态 | 更强符号记忆，不由参考几何自动填充 |
| `incremental_image_memory` | 新证据 + 自选旧图/裁剪 + 来源元数据 | 视觉载体；裁剪不能偷看 Gold 或未来查询 |
| `version_filtered_retrieval` | 新证据 + 有预算的合法历史检索 | 后续强 baseline，不作为首个闭环阻塞项 |

初期无需五个方法同时跑满。先 full history、summary、spatial state 跑通，再增加图像载体和检索。

公共任务范围必须提前说明可能继续询问哪些区域类型，但具体后续地点和答案不提前暴露给压缩方法。把完整多边形/空间结构保存好的方法允许获胜，不人为限制它来制造图像优势。

### 10.2 诊断条件

- `vlm_extracted_facts`：由真实 VLM 抽取视觉事实，错误原样流入后续更新。
- `oracle_visual_facts`：提供当前图片可支持的正确结构化事实，检查排除感知错误后的剩余失败。
- `oracle_carrier`：提供正确上一轮状态，诊断状态构造与后续使用。
- `text_only_evidence`：去掉视觉信息后重算可支持参考，不与未重算的正常完整任务混同。

Oracle 条件属于诊断参照，不列为普通可部署方法，不用它的分数证明新方法优越。

### 10.3 同前缀载体干预

保存一个真实模型前缀，冻结本轮新增证据，分别测试：`Actual / Masked / Oracle / Edited / IrrelevantEdit`。

- Actual：模型真实提交的载体。
- Masked：屏蔽相关记忆；另有匹配格式/近似长度的无关替换控制。
- Oracle：正确参考载体，仅诊断。
- Edited：改变一个相关槽位或其来源。
- IrrelevantEdit：只改变无关槽位或呈现形式。

Edited 需要分两种目的：

1. **载体敏感性诊断**：记录下游是否随相关槽位改变；这本身不一定是正确行为。
2. **错误载体恢复**：当前新证据已经足以推翻错误记忆时，检查模型是否修复，而不是盲从。

不得把“跟随一个被篡改的错误状态”统一算作成功。Masked 不掉分也不能直接证明“没有记忆”，还要检查当前资料是否已足以重建答案、探针是否真的依赖历史。

同前缀单步干预与自身历史持续分化的闭环轨迹分别出表。长度、信息量和裁剪策略的差异显式报告，不越界宣称模型内部神经记忆机制。

---

## 11. 模型接口、预算与可复现运行

### 11.1 图像必须真正进入模型

`vlm_backend.py` 使用已固定版本的官方多模态接口。图片应作为 image content/PIL/后端支持的图像对象进入 processor；不能把文件路径字符串塞进普通文本就说“已提供图片”。[C1,T2]

每个请求捕获：公开消息、图像顺序、原始内容哈希、解码后尺寸、最终缩放/裁剪参数、processor 配置、可用的 `image_grid_thw` 或等价特征、文本 token、视觉用量、上下文预算、输出预算、采样设置和模型 revision。

按后端实际接口避免重复 resize；变更像素预算会改变输入条件，必须登记。不能假定纯文本 tokenizer 的 token 数已经包含视觉开销。

### 11.2 两套环境

- CPU 环境：来源读取、GIS、编译、测试、评分、重建；不需要下载 VLM 权重。
- 推理环境：模型、processor、后端、GPU 库完整锁定。先用少量非测试样本校准格式和最大图像数量，再冻结共同设置。

优先用已有可用环境的兼容版本，但不得污染旧已验收环境。固定 `requirements`/lockfile、Python 版本和 CUDA/后端信息；不要用 README 中未固定的 `main` 依赖作为最终科研环境。

### 11.3 预算不是只算最终回答

报告文字摘要、视觉抽取、检索路由、重排、状态更新和最终生成的全部调用。图像保留不能免费获得无限像素；符号记忆也不能获得无限 token。

首个小规模矩阵先估算：

```text
主生成次数 = sum(各 episode 检查点数) × 正常方法数 × 重复数
额外次数 = 同前缀探针数 × 干预臂数 + 抽取/摘要/检索模型调用
总次数 = 主生成次数 + 额外次数
```

根据实际 preflight 的用量给出 GPU 时长/内存估计，不编造固定“一张卡多少分钟”。跨模态 token 不强行换成未经验证的统一成本；报告实际 token、像素、调用数和运行资源。

### 11.4 失败隔离与机会保留

一个轨迹上下文超限，只标记该轨迹或该请求的失败，不能使同 worker 中无关轨迹全部无声消失。所有计划槽位保留，区分 `invalid_output / context_budget / provider_error / missing / unattempted`。

不因为答错选择性补跑。网络请求是否允许重试、何时认定首次尝试未产生回答、如何记录不确定结果，必须预先冻结。运行恢复只跳过有完整收据的已完成槽位，不能覆盖原始响应。

无授权时不得创建付费调用或新 GPU 作业；已有旧作业不能为本计划被自动取消。

---

## 12. 评分：主指标少而清楚，分母必须固定

### 12.1 主结果四组

| 组别 | 核心指标 | 解释 |
|---|---|---|
| 当前状态 | 值/状态正确率、派生规则输出正确率 | 模型目前的判断是否符合可见证据 |
| 当前依据 | 合法来源、适用版本、文字/图像定位 | 支持是否对准目标与版本 |
| 修订质量 | 必要更新、稳定状态退化、未知破坏 | 是否只修改应该修改的部分 |
| 持续可靠 | 整段全对、旧图回退、错误恢复延迟 | 能否维持和修复状态 |

普通条件的主表保留全部计划机会；Oracle、模态移除后重算任务、不同数据来源分别报告，不合成一个“总体多模态能力分”。

### 12.2 推荐实现定义

```text
strict_checkpoint_accuracy
  = 完整满足状态、规则和证据契约的检查点 / 全部计划检查点

required_update_success
  = 在 must_change_value/provenance 上提交了当前正确结果的槽位方面数
    / 全部要求变化的槽位方面数

stable_regression_rate（条件诊断）
  = 参考应保持、上一轮模型正确、本轮变错的槽位方面数
    / 参考应保持且上一轮模型正确的槽位方面数

unknown_violation_rate
  = 应仍未知但模型提交确定值的槽位数 / 应仍未知的槽位数

whole_episode_success
  = 该 episode 全部计划检查点均严格正确
```

注意事项：

- “该更新集合”和“稳定集合”应按值/来源等方面分别定义；同值换引用不等于值更新。
- `required_update_success` 不证明模型进行了内部修订，它也可能重读后答对；历史必要性另由输入协议与干预检查。
- 模型上一轮错、本轮修正成对，即便 Gold 前后未变，也不能被算作“过度更新”。
- 空集合指标写 `null` 并报告分母 0，不记作 100%；汇总同时报告 eligible 数和固定主分母。
- 条件化分析不能替代完整矩阵：例如只看“上一轮读图正确”的子集要明确选择条件。
- 图像定位只对需要且存在合格定位的槽位计算；整图框不算精确区域定位。只证明定位契约满足，不直接证明推理忠实。

### 12.3 时间与统计

恢复延迟从首次有足够合法更正证据的检查点算起；未恢复事件按删失单独报告，不从平均值中静默删除。受控检查点延迟不直接转换成真实世界的安全时间。

同一事件的地点、图块、检查点和配对变体不是独立事件。小试点提供描述性结果；扩大后使用以 `global_event_id` 为单位的聚类分析/重采样。若事件数不足，不用海量检查点制造显著性。

若采用“重复两次均整段成功”，必须明确不是 pass@2。只做一次重复的阶段不借用旧字段名宣称两次可靠性。

---

## 13. 分阶段执行工单

### MM-P0｜仓库识别、保护边界与可复用接口

**依赖**：无。

**操作**：读取实际 HEAD、AGENTS、本地修改和当前运行状态；检查已有开发/保留事件；列出可复用代码与新旧差异；定义新目录与默认资源预算。

**交付**：

```text
plans/multimodal_v1/SCOPE.md
plans/multimodal_v1/REUSE_MAP.md
plans/multimodal_v1/DATA_POLICY.md
artifacts/multimodal_v1/manifests/BASELINE_SNAPSHOT.json
configs/multimodal_v1/sources.yaml
configs/multimodal_v1/budgets.yaml
```

**验收**：旧受保护文件列表与哈希已记录；未回滚未提交改动；没有启动模型/数据全量下载；任务明确哪些是新建、哪些是复用。当前已有新阶段时优先合并计划而不是重复命名。

**停止条件**：工作区位置不明、AGENTS 有冲突、待修改范围与旧冻结产物重叠。保留报告，换独立目录或请求必要澄清。

### MM-P1｜真实来源适配与最小可读图文包

**依赖**：P0。

**操作**：先下载/复用一个已允许开发事件的真实资料，保存原始字节、来源、许可、元数据和失败收据；确定至少两个可对齐产品。无法获得官方原图时，可做显式标注的官方数据重绘，不伪称原图已打通。

**交付**：`ledger.py`、`downloads.py`、`adapters/nhc.py`、`temporal.py`、`rendering.py` 的最小实现；一份真实种子清单；浏览用案例页；图文重复信息检查报告。

**验收**：

- 原始文件不是错误 HTML；下载、解析、渲染三个状态分别记录。
- 事件、产品、阈值、单位、CRS、绝对目标时间可解释。
- 至少一个真实图文包能形成公开输入，且读图位置可见。
- 没有将未知历史可用时间补成 issued/download time。
- 全文足以解答的样本被标为冗余模态，不冒充视觉必要。

**停止条件**：所有真实数据入口失败、时间无法对齐、图中无法读出参考要求。可以继续合成 fixture 的软件测试，但 P1 科研验收必须标 `BLOCKED`，不能用 fixture 替代真实样本通过。

### MM-P2｜自动任务、修订参考、评分与泄漏检查

**依赖**：P1 的真实种子；软件部分可先用明确合成 fixture 并行开发。

**操作**：实现公开规则、三值逻辑、作用域/版本选择、参考编译、模型公开投影、修订集合和确定性评分。增加受控图文配对与必要模态证书。

**交付**：`models.py`、`rules.py`、`evidence_gate.py`、`geometry_reference.py`、`visual_validation.py`、`public_projection.py`、`compiler.py`、`scoring.py`；冻结 `EXPERIMENT_PROTOCOL.md` 与机器可读 `configs/multimodal_v1/protocol.yaml` 初版，并检查二者一致。

**验收**：正常模型视图不含私有标签/未来查询；同一目标和异目标修订区分正确；值不变来源变化单独评分；空集合、边界、未知/false、无效输出和缺失输出均有测试；真实数据与合成测试的计数不混合。

**阶段终点**：到这里应已经有一套不需要 GPU 的可检查任务。不要仅交文档，不交代码和真实输入；也不要因模型暂未配置就让 CPU 任务全部停滞。

### MM-P3｜多模态请求与一个 VLM 的小型预检

**依赖**：P2；模型/计算授权与兼容环境明确。

**操作**：实现真正多图输入、最终 processor 日志、原始响应捕获、上下文预检、轨迹级失败隔离。先用极小预检，不启动完整矩阵。

**交付**：`vlm_backend.py`、`protocol.py`、`runner.py`、`audit.py`；环境锁、模型 revision、请求样例、预检报告。

**验收**：更换图片像素会改变捕获的视觉输入，而非仅改变路径文本；Gold 和正确裁剪未进入请求；无效但结构合法的错误答案仍能表达；无模型生成时可跑 mock/CPU 测试；原始失败不被覆盖。

**停止条件**：图片实际未进入模型、图像被二次缩放导致信息丢失、预算不够、不能隔离私有参考。先修接口，不继续获取一批不可解释分数。

### MM-P4｜小型闭环矩阵、双干预与视觉记忆

**依赖**：P3 预检通过；P2 数据/规则/评分已冻结。

**操作**：先 full history、summary、spatial state，再加 image memory；运行图像延迟、旧图重放、无关更新和保存前缀的载体探针。对后续新地点查询检查 future-query leakage。

**交付**：`memory.py`、`interventions.py`、试点计划槽位清单、真实响应、四组主指标、成本表和案例页。

**验收**：同前缀与闭环分别报告；自身错误不会被 Gold 修复；缺图重算参考与收到后遗忘不混同；强空间状态可以保存充分信息，不被人为弱化；条件分数不替代固定主分母。

**继续条件**：确实能定位感知/版本/修订/保留中的不同失败，或发现专业工具/结构化方法可靠解决的有意义结果。不是必须低于某个准确率才能“过关”。

### MM-P5｜强近邻 baseline 与一个原生遥感扩展

**依赖**：P4；数据与模型预算重新核准。

**操作**：优先补版本过滤检索，再评估适配 MMA/论文方法的成本。SpaceNet 8 与 GEOID-Flood 选择一个小型扩展，沿用接口但单独定义参考与输入可见性。

**交付**：第三方版本和许可账本、适配补丁、选定遥感 adapter、数据卡、方法偏离说明、独立报告。

**验收**：未把官方 sample 的 train/test 当作本项目事件级保留划分；未将 SAR/多光谱张量未经说明当作 RGB；图像、模型预测掩膜、参考标签三个层次隔离；两时相未伪装长自然序列；淹水未被升级为真实不可通行。

### MM-P6｜冻结验证与论文证据整理

**依赖**：P4/P5 形成稳定任务，额外事件/模型预算明确。

**操作**：冻结开发选择，增加独立事件与必要的第二 VLM；保留 event/AoI/tile/pair 的层级关系；独立 CPU 重建报告；整理与近邻工作的协议差异。

**交付**：可恢复发布包、来源/许可/拆分清单、数据卡、方法卡、完整计划分母、论文表图所需机器可读统计和局限性。

**验收**：测试集不参与 prompt/阈值/渲染风格选择；没有跨数据集同事件泄漏；多个轨道不随意混总分；无“首次”“安全行动”“内部记忆机制”等超出现有证据的结论。

---

## 14. 必须覆盖的测试清单

以下是验收需求，测试名可随代码风格调整；不是声称测试已经存在或通过。

| 类别 | 最小测试 |
|---|---|
| 时间 | 同相对 lead 不同绝对目标；跨日/月/年；issued/observed/delivered 分离；未知 availability 保持 null |
| 版本 | 同目标新版覆盖；异实体/异时段不得覆盖；旧图重放不成新版本；不同产品无隐式全局权威 |
| 几何 | 经纬轴顺序、投影转换、边界点、多边形洞、图外目标、无覆盖和无效像素；不支持的几何明确拒收 |
| 规则 | true/false/unknown 的 AND/OR；缺模态不必未知；无业务公告不能推出开放 |
| 图像 | 实际 resize 后可见；坐标转换；图像顺序；裁剪不泄漏未来目标；禁止私有 Gold 区域选择 |
| 公开隔离 | 模型视图不含标签路径、标准状态、未来图像、必要变化集合；普通检索无法读私有目录 |
| 历史 | 模型错误原样延续；invalid/missing 明确；不同方法/事件不共用答案；恢复运行不会拼错前缀 |
| 干预 | 延迟前相同曝光前缀；基于同一保存载体；无关编辑控制；从未收到与收到后遗忘分开 |
| 评分 | 值变化与来源变化分开；修正旧错误不误算过更新；空集合 null；无效/未尝试保留固定主分母 |
| 下载 | 错误 HTML、超预算、缺长度、哈希不符、路径穿越、解压膨胀、超时重试和收据恢复 |
| 运行 | 单轨迹上下文失败不终止其他轨迹；未授权 GPU/API 被拒绝；重复 slot 不覆盖；未知请求结果不被静默补答 |
| 拆分 | 同事件及相邻瓦片/配对不跨开发测试；NHC 与 SpaceNet 同名/同事件统一映射；GEOID sample 不伪装跨事件 |

新增确定性错误程序对照：最后到达者优先、所有中心强度变化都覆盖地点状态、永不更新、只更新值不更新来源、所有更新都改全图、缺证据一律 false。它们是诊断程序，不是模型 baseline 成绩。

保留独立 CPU 重建：从公开输入、冻结协议、原始响应和私有参考重新计算结果，不依赖原推理机器路径，不重新调用模型。

---

## 15. 建议的新 CLI 合约

**本节所有 `disastertrace.multimodal_v1.cli` 子命令都要求 Codex 新实现，不能直接声称现有仓库已经支持。** 每个命令应支持 `--help`、清楚的非零退出码和机器可读报告。

```bash
# 1. 检查资源入口与本地复用情况；默认仅元数据和下载计划。
python -m disastertrace.multimodal_v1.cli discover \
  --config configs/multimodal_v1/sources.yaml \
  --output artifacts/multimodal_v1/manifests/source_candidates.json

# 2. 严格按经过批准的选择清单下载；下载器自己执行预算检查。
python -m disastertrace.multimodal_v1.cli fetch \
  --selection artifacts/multimodal_v1/manifests/download_selection.json \
  --budget configs/multimodal_v1/budgets.yaml

# 3. 编译样本，分别写公开输入与私有参考，不运行模型。
python -m disastertrace.multimodal_v1.cli build \
  --config configs/multimodal_v1/pilot.yaml \
  --output artifacts/multimodal_v1

# 4. 检查时间、视觉可读性、参考一致性与输入隔离。
python -m disastertrace.multimodal_v1.cli validate \
  --manifest artifacts/multimodal_v1/manifests/benchmark.json

# 5. 固定机会和预算，生成运行计划；仍不调用模型。
python -m disastertrace.multimodal_v1.cli plan-run \
  --protocol configs/multimodal_v1/protocol.yaml \
  --budget configs/multimodal_v1/budgets.yaml

# 6. 真正运行仅在批准的 run-plan 下进行，不接受隐式扩大矩阵。
python -m disastertrace.multimodal_v1.cli run \
  --run-plan artifacts/multimodal_v1/manifests/approved_run_plan.json

# 7. 评分、重建与导出均为离线动作。
python -m disastertrace.multimodal_v1.cli score --run-dir RUN_DIR
python -m disastertrace.multimodal_v1.cli audit --run-dir RUN_DIR
python -m disastertrace.multimodal_v1.cli report --run-dir RUN_DIR
```

`protocol.yaml` 是 `plan-run` 的权威输入，Markdown 是人读说明，两者生成/校验一致。若调整命令名，同步修改文档，不留不可执行的旧示例。

建议 `sources.yaml` 至少包含：官方入口、可接受源域名、来源等级、当前验证状态、数据许可链接、代码链接、冻结 revision、单文件/总量上限；不能只是一串网址。

---

## 16. 何时继续，何时调整研究定位

### 继续扩大前必须满足

- 有真实来源图文样本，不只是漂亮的合成案例。
- 视觉事实对部分任务确实必要，冗余文字样本已分开。
- 图像最终输入与参考精度匹配，不让模型猜不可见内容。
- 应更新、应保持和应未知有独立可核对参考。
- 简单专业工具/结构化方法与 VLM 都有诚实、公平的位置。
- 小试点已经能产生可解释的正确和错误轨迹，而不是只产生格式失败。

### 暂停扩量、先修任务

图文不属于同一目标时间，风圈被误当成概率图，参考侧知道但图片看不出，下载错误页被当数据，所需答案已在 alt text，或所谓记忆任务每轮依然给出全部必要旧证据。

### 应重新定位而不是制造难度

如果专业工具加简单规则已经高可靠解决任务，应报告混合系统/结构化方案的优势。若 VLM 弱点主要是感知，论文就重点讨论感知与证据表征，而不是强行说成状态记忆失败。

多模态、记忆、变化理解都有近邻工作。本项目候选增量在于：灾害时间与空间语义下，可核验的选择性修订、配对输入和历史使用诊断。低准确率本身不是 novelty 证据。

---

## 17. 最终需要交付的文件

```text
1. SCOPE.md / REUSE_MAP.md / DATA_POLICY.md
2. 来源与许可账本、固定版本、下载选择与实际收据
3. 可读真实案例 + 明确标识的受控/合成测试案例
4. 新多模态数据类型、适配、编译、协议、评分、运行与审计代码
5. 自动测试及实际运行记录
6. 模态必要性诊断与双干预清单
7. 预注册运行矩阵、预算、模型与处理器版本
8. 原始响应、失败、计划分母与独立重建报告
9. 四组主指标、成本、案例和局限性
10. 下一阶段尚未完成的事项；不把计划写成结果
```

首轮达到 P2 即可交付有价值代码。模型阶段未授权不妨碍完成数据/协议/CPU 测试；真实来源尚未成功则必须保留 P1 阻塞状态。

---

## 18. 可直接复制给 Codex 的首轮指令

```text
请在当前 DisasterTrace 仓库执行《DisasterTrace 多模态后续实施计划》。

先读取当前和父目录 AGENTS.md、实际 HEAD、未提交改动、当前阶段、已有数据拆分及
本计划。不要 reset 工作区，不要覆盖任何旧 Gold、评分器、响应、失败或冻结产物。
计划中提到的 36082c42... 只是复查基点，不要求回滚到它。

本轮先完成 MM-P0、MM-P1、MM-P2：
1. 保护旧资产，明确复用接口和新的 multimodal_v1 目录。
2. 从已允许的开发事件寻找一个真实 NHC 图文种子，保存原始内容和来源收据。
3. 实现时间/产品作用域、公开图文输入、自动参考、选择性修订集合、确定性评分。
4. 做视觉必要性与文字泄漏检查。完整原文已包含图像答案的样本只能进入冗余模态轨。
5. 完成 CPU 单元测试、错误程序对照和可检查的真实样例报告。

下载先列清单、固定 revision、核对大小；小样本不超过计划默认预算。不能下载整个
遥感数据集或模型权重，不能使用 --sample --list 作为 GEOID 的只预览命令。
GPU、付费 API、大规模模型生成、训练和大型下载均不属于本轮默认动作。

不要只返回另一份计划，应该实际实现本轮代码和测试。真实数据入口失败时，保留
失败记录并标 BLOCKED；可继续明显标为 synthetic fixture 的软件测试，但不得用
fixture 冒充真实数据验收通过。不要靠猜测数据 URL、语义或成绩补齐缺口。

最后报告：改了哪些文件，实际执行了哪些命令及结果，哪些验收通过/失败，已下载
多少字节，剩余阻塞是什么，下一条建议命令是什么。未运行的项目明确写 NOT_RUN。
```

---

## 19. 参考入口、核查级别与引用说明

这些链接用于执行时复查。本文没有运行外部模型、完整下载遥感数据或验证全部二进制链接。论文条目用于延续上一版的相关工作边界，不等于本轮重新完成所有论文全文与代码复现。

### 官方数据

- **[D1] NHC GIS**：<https://www.nhc.noaa.gov/gis/>；本次可读官方节点 <https://prod-east-nhc.woc.noaa.gov/gis/>。核查到产品入口；历史文件实际可用性待 P1 下载验证。
- **[D2] NHC 历史 GIS/公告**：<https://www.nhc.noaa.gov/gis/forecast/archive/>；<https://www.nhc.noaa.gov/archive/>；索引示例 <https://www.nhc.noaa.gov/gis/archive_forecast_info_results.php?id=al09&name=Hurricane+IAN&year=2022>。部分页面在本次浏览环境返回 403；不声称下载成功。
- **[D3] NHC 产品语义**：<https://www.nhc.noaa.gov/aboutnhcprod.shtml>；<https://www.nhc.noaa.gov/templates/graphics_wsp_inc.shtml>。具体产品字段与目标时间仍按实际文件核查。
- **[D4] SpaceNet 8 官方下载与数据许可**：<https://spacenet.ai/sn8-challenge/>。页面提供本文列出的公开 S3 路径；二进制完整下载未执行。
- **[D5] GEOID-Flood 数据卡与文件**：<https://huggingface.co/datasets/links-ads/geoid-flood>；<https://huggingface.co/datasets/links-ads/geoid-flood/tree/main/sample>。核查了来源、数据布局、sample 与许可说明；具体下载固定完整 revision。

### 作者代码与模型

- **[C1] Qwen3-VL**：<https://github.com/QwenLM/Qwen3-VL>；<https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct>。
- **[C2] Qwen3-VL-Embedding**：<https://github.com/QwenLM/Qwen3-VL-Embedding>。
- **[C3] MMA**：<https://github.com/AIGeeksGroup/MMA>。适配方法，不继承其模型评分作为本项目主评分。
- **[C4] SpaceNet 8**：<https://github.com/SpaceNetChallenge/SpaceNet8>；baseline 说明 <https://github.com/SpaceNetChallenge/SpaceNet8/blob/main/baseline/README.md>。
- **[C5] GEOID-Flood**：<https://github.com/links-ads/geoid-flood>；本次实际读取的下载脚本 <https://raw.githubusercontent.com/links-ads/geoid-flood/main/scripts/get_data.py>。执行前记录实际 commit，避免 main 漂移。

### 官方工具文档

- **[T1] Hugging Face Hub 下载、revision 与 dry run**：<https://huggingface.co/docs/huggingface_hub/guides/download>；API <https://huggingface.co/docs/huggingface_hub/package_reference/hf_api>。
- **[T2] vLLM 多模态输入**：<https://docs.vllm.ai/en/latest/features/multimodal_inputs/>。只有采用该后端时才进入依赖；不能用 latest 文档替代实际锁定版本测试。

### 近邻论文：用于协议比较，不作为新增大工程清单

- **SpaMEM**：<https://arxiv.org/abs/2604.22409>。检查感知与视觉历史状态维护的比较条件。
- **MMA: Multimodal Memory Agent**：<https://arxiv.org/abs/2602.16493>。检查多模态记忆可信度、冲突和修订近邻。
- **When History Is Multimodal / VERA**：<https://arxiv.org/abs/2608.29897>。检查原生视觉历史保留的近邻。
- **LongEarth-R1**：<https://arxiv.org/abs/2608.13344>。检查长时序地球观测与变化定位近邻。
- **GEOID-Flood**：<https://arxiv.org/abs/2608.02315>。核对数据时间、模态和标签来源。

**计划终点不是“代码越来越多”，而是一套真实可核查、视觉确有作用、修订关系清楚、能解释错误来源的小型 benchmark；通过后才扩事件、扩模型和扩遥感任务。**
