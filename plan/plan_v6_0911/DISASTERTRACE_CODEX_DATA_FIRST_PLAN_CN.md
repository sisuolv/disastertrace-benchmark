# DisasterTrace：数据优先的下载、核验与多灾种扩容计划

**给 Codex 的执行规格｜2026-09-10｜仅数据阶段，不启动训练、模型推理或新的 GPU 作业**

## 0. 当前目标和读法

本轮先回答三个问题：哪些数据真正拿得到？其中有多少可区分的事件和有效资产？分别能支撑 DisasterTrace 的哪些任务？不要先扩大问答数量、跑模型排名或重写论文。继承原有 46 项来源的 ID，新增 D47–D54 八项开源 benchmark/数据资源，形成 **54 项来源核验表**；这个数字不是“54 项已经下载通过的独立数据集”。

**单独交付本 Markdown 即可使用。**全部来源的下载地址、集合 ID、限制和下一步都在第 9 节。配套 JSON 是机器可读副本；两个 Python 脚本仅帮助做有限元数据/文件探针，不是已经实现好的完整数据平台。

原来的约 16 类灾种、3,050 个 episode 是覆盖目标，不是已核实供给。最大化“不同物理过程、地区、年份、模态与有效事件”，而不是最大化重复帧、瓦片、问题模板或不同来源对同一事件的复述。海洋热浪与降雨滑坡为扩展；地震、海啸、火山不混入极端天气主集合。

### 已做与未做

本计划依据作者/官方 README、文件目录、公开数据卡、下载按钮和 API 文档，逐项补齐下载路线。直链、HF 文件路径、Zenodo record、云存储 prefix、GEE ID、共享盘、申请门户分别标注。**页面可读、作者列出链接，不等于已经取回二进制或在 CCI 解码通过。**本轮未批量下载数据、未认证 GEE、未运行模型，也未修改 GitHub。容器一次 Hugging Face HTTP 元数据探针遇 DNS 解析失败，不能外推为用户 CCI 不能下载。部分大文件链接由浏览工具因二进制类型或内部错误拒绝渲染，不据此判定源文件失效。

代码参考来自先前核对的 `next-phase-v1@36082c42a93e11f67d274d8000c87cd1dc098d74`，不是要求 reset 到这个提交；以当前工作区为准。旧 main 不能代替后续版本。

## 1. 给 Codex 的启动指令

```text
你在现有 DisasterTrace 工作区执行“数据优先核验”，不是再写一份泛泛计划。

先读取适用 AGENTS.md、当前 HEAD、git status、已有数据清单/采集脚本和本计划。
不要 reset、覆盖未提交修改、删除旧数据、push、重启旧作业或延长已经过期的算力授权。
不要运行外部 benchmark 的 train/eval/model 脚本，不下载模型权重，不调用 LLM 生成标签。

首先复用已有原始资料，完成 DF00–DF04；所有54项都必须有登记状态和下载路线。
使用实际网络和文件结果更新表格，不能用README样本数冒充本次已采集数量。
公共元数据与有限样例按 execution_scope.json 的预算执行；需要账户、许可、付费或超过
预算时记录阻塞，继续其他来源。不得绕登录、验证码、访问限制或使用未经核验的镜像。

输出 source_access_report、source_inventory、event_registry、hazard_coverage、
capability_matrix、admission_report 和 DATA_READINESS_REVIEW_CN.md。
只有经过实际获取与解码的资料才记 fetched/decoded；只能按证据支持的能力准入。
```

### 项目与存储边界

在 CPU/能访问数据源的工作环境执行。先检查已有 AFS 持久目录、剩余空间和用户配额，不因全局 `df` 有空间就假定自己无限可用。可设置：

```bash
# 是数据工作目录示例；先确认挂载和权限。不要移动现有 HOME 或重装全局环境。
export DISASTERTRACE_DATA_ROOT=/mnt/afs/260010168/disastertrace_data
```

检查当前仓库中的 heldout 配置。前序已知受保护 NHC ID 有 `AL142016, AL112017, AL152017, AL142018, AL132020, AL092022, AL102023, AL022024`，但必须以实际配置并集为准。公开大库可能包含这些事件：允许对已授权的归档做封存和元数据隔离；**不得把其标签/样例拿来调试选择提示词、阈值或正式规则**。跨 CyPortQA、xBD、CrisisMMD 等来源一并匹配。

## 2. 完成标准：七个层次分别记账

| 状态 | 必须有的证据 | 不能据此宣称 |
|---|---|---|
| registered | 本计划来源 ID、真实下载入口、用途 | 已能下载 |
| endpoint_observed | 目录/作者页面/文档快照，访问时间 | 文件完整或许可通过 |
| catalog_received | 实际文件清单、版本、大小、分页完整性 | 数据已取回 |
| fetched | 实际字节、URL来源、HTTP记录、SHA256 | 能解码或适合任务 |
| decoded | 实际读取格式/变量/shape/坐标/质量的日志 | 事件独立、标签无误 |
| event_linked | 真实事件ID、地区与时间、原始场景关联 | 每个切片都是独立事件 |
| admitted_for_track | 明确能力/任务的自动检查与参考依据 | 同时满足全部研究要求 |

失败或阻塞单列：`needs_account`、`needs_license_review`、`manual_access_required`、`rate_limited`、`provider_blocked`、`network_failed`、`large_single_archive`、`over_budget`、`catalog_partial`、`missing_labels`、`time_unresolved`、`no_valid_coverage`、`decode_failed`。这些不是“没有灾害”或“数据集不存在”。样例通过不能将整来源标为全部已准入。

### 数据能力不能强行统一

| 能力标记 | 最低材料要求 | 限制 |
|---|---|---|
| perception | 可读影像/图表与核验参考 | 只有单期可留在此轨 |
| spatial | 明确几何/网格、区域、变量与参考 | nodata/云不等于负例 |
| temporal_evolution | 真正不同观测时刻，可比较的空间支持 | 物理变化不是同目标修订 |
| native_revision | 相同目标时空/变量的明确后续版本 | 不能仅按“更晚下载”推导 supersedes |
| controlled_delivery | 已核验真实材料，显式规定延迟/重放 | 合成的是交付条件，须单列 |
| as_of_replay | 可证明可得时间或真实前瞻采集账本 | 未知历史 availability 不用现在时间补齐 |
| prediction_candidate | 独立未来观测目标、输入时间边界明确 | 本阶段不运行预测模型 |
| multimodal_native | 原生图/文/观测配对，不同必要信息 | 将同一栅格转PNG再生成一句话不等于独立来源 |

一个数据集不必同时具备所有能力；准入矩阵可以有空格和条件。尽量保留真实有用的数据，而不是为了动态核心拒绝所有静态资料。

## 3. 先广度，后深度：执行顺序

| 工作包 | Codex 实际做什么 | 交付与通过条件 |
|---|---|---|
| DF00 本地核对 | 读取代码/缓存/既有来源/磁盘；冻结旧产物边界 | REPO_BASELINE.json、LOCAL_DATA_INDEX.json、执行范围；不改历史 |
| DF01 全源入口核验 | 登记54项，解析可机器获取的清单；核对迁移/权限 | 每项有入口、版本、状态、证据或具体阻塞；不是只处理最容易的6项 |
| DF02 版本与文件清单 | HF锁SHA，Zenodo固定record，S3/GCS列对象，API跟分页 | resolved_sources.jsonl、file_manifest.jsonl；部分清单不伪装完整 |
| DF03 有界下载与解码 | 每源先1–3个独立候选/配套样例；单大包先评估 | 实际文件、校验和、解码日志；失败分开保留 |
| DF04 事件匹配与能力准入 | 统一事件/产品/版本，提取质量和时间，检查标签角色 | event_registry、capability_matrix、source_dependency_edges |
| DF05 按灾种补缺 | 每类最多先检查20个独立候选；复用成熟benchmark+原始资料 | 16类覆盖表；缺口说明；不为补配额编造类别 |
| DF06 扩容与冻结 | 根据有效事件增益/下载成本形成bulk计划，再按新范围执行 | 明确文件白名单、真实体积、准入漏斗、新版本dataset_manifest |
| DF07 数据验收汇报 | 输出实际可用数量/任务条件/许可/剩余障碍 | DATA_READINESS_REVIEW_CN.md，之后才进入模型实验 |

1–3和20是**适配抽查上限，不是最终数据量上限**。兼顾区域、季节、强度、缺测、负例、传感器及来源版本，不只抽最清楚、最早或最小的样本。样例抽样规则先固定；禁止依据待测模型分数决定保留哪些事件。

### 首轮建议：并行两条线

**开放 benchmark 线**：D47 ExEBench 小包 → D49 WeatherQA 原始文本/图组 → D12 GEOID 样例 → D07 TorNet 目录/2013 → D50 CyPortQA 当前缓存 → D19 WildfireSpreadTS 元数据。D13/D14/D51 等HF资料同步登记，不必等这一串全部完成。

**原始资料线**：D02 IBTrACS＋D05 Storm Events＋D26/D27站点索引＋D18 CEMS＋D40 EONET；并为冷热/干旱/雪/尘/雾准备D25/D30–D36。这样不会因为大图包下载慢而停掉全部多灾种核验。

### 预算建议（不是无上限授权）

默认 `probe`：总样例下载20 GiB，单文件上限4 GiB，元数据预算512 MiB，下载并发2；保存压缩/解压/缓存的实际额外开销。GEE 只在已有合法项目和允许额度内查询，默认不派发批量导出。禁止 requester-pays、新付费API和自动购置存储。

D19单ZIP48.4GB、D03大包、D22约6.3GB等不能“为了取一张图”直接突破上限。记录为大包候选；确认按需读取可行性或待 `bulk` 范围配置后获取。不得把全量下载门槛低误当资源质量高，也不只保留小文件。任务允许的更大预算应有独立配置与明确文件白名单；小脚本只约束单次，不替代全局账本。

## 4. 每类灾种怎么配源、如何防止假覆盖

| 灾种ID | 范围 | 优先数据编号（链接见第9节） | 准入重点 |
|---|---|---|---|
|H01|热带气旋|D01 D02 D03 D04 D47 D50|同一气旋多机构/港口/帧不得重复；best-track是事后参考。|
|H02|温带风暴／非对流大风|D05 D27 D28 D48|风暴身份及非对流性质需原始记录，不能用全部storm序列替代。|
|H03|雷暴大风／下击暴流|D05 D06 D08 D09 D49|雷达现象与地面风报告配对；下击暴流需特定证据。|
|H04|龙卷风|D07 D05 D08 D49|正负样本与event/episode IDs；采用TorNet v1.1。|
|H05|冰雹|D05 D09 D48 D49|冰雹报告与算法估计区别；不能从强回波直接判定。|
|H06|强雷电|D06 D10 D05|闪电检测/聚合与高影响事件区分，强度阈值先定义。|
|H07|极端降水|D47 D29 D26 D06 D09 D48|降水率/累计量、窗口和异常阈值；低频资料不冒充短时极值。|
|H08|河流洪水／山洪／城市内涝|D11 D12 D13 D14 D15 D16 D17 D18 D51|永久水体、云/覆盖、洪水标签分开；三个子类独立核验。|
|H09|风暴潮／沿海淹没|D37 D01 D18 D05|潮位基准面与天文潮一致；内陆洪水不是风暴潮配额。|
|H10|热浪|D47 D48 D25 D26 D34|2米气温与LST分开；固定季节/基准期/持续时间。|
|H11|寒潮／极端低温／霜冻|D47 D48 D25 D26 D27|寒潮、低温与霜冻不同定义；保存温度变量与表面/高度。|
|H12|暴雪／冰冻／冻雨|D05 D49 D26 D27 D33 D28|冬季细类需报告支持；雪盖不等于暴雪或冻雨。|
|H13|干旱／闪旱|D52 D31 D30 D32 D25|一般干旱有成熟数据；闪旱需预先定义变化速度与参考。|
|H14|沙尘暴|D35 D36 D27 D05|目前以原始资料联合为主；必须区分沙尘与烟，不承诺已成立闭环。|
|H15|浓雾／极端低能见度|D27 D53 D10|M4Fog海雾获取有条件；陆地雾和一般低能见度分开。|
|H16|野火及相关火险|D19 D20 D21 D22 D23 D24 D47|火点、火场、烧毁面积、受控状态不同；D20保留未来筛选偏差。|

D38海洋热浪和D46降雨滑坡单列扩展；D39/D40/D41为跨灾种目录，D44/D45/D54为跨灾种影响/图文/事件信息补充。目录、观测、标签、问题模板不能相互替代。

## 5. 最小数据契约：先做库存和审计，不重建整个评测框架

在现有项目旁新增只读数据核验工具；已存在同职责模块就复用。不要为了这轮下载先实现所有V2评分功能。至少保存下列账本：

```text
data_audit/<run_id>/
  execution_scope.json
  repo_baseline.json
  source_access_report.jsonl
  source_inventory.jsonl
  resolved_sources.jsonl
  file_manifest.jsonl
  acquisition_attempts.jsonl
  event_registry.jsonl
  source_dependency_edges.jsonl
  capability_matrix.jsonl
  hazard_coverage.csv
  admission_report.json
  DATA_READINESS_REVIEW_CN.md
  objects/<sha256>.<ext>
  source_metadata/<source_id>/
  private_reference/                 # 已有标签/事后参考，不能混入普通输入
```

本阶段表格可用CSV/JSONL，连续大表可用Parquet；实际数据保存GeoTIFF/NetCDF/HDF5/Zarr等原生格式，不能全部降为截图。原始内容不可覆盖，派生表示记录父对象与处理参数。

### file_manifest 最少字段

```json
{
  "source_id": "Dxx",
  "provider_version": null,
  "resolved_commit_or_record": null,
  "logical_product_id": null,
  "object_key_or_relative_path": null,
  "catalog_size_bytes": null,
  "fetched_size_bytes": null,
  "provider_checksum": null,
  "sha256": null,
  "content_type": null,
  "local_path": null,
  "observed_at_or_interval": null,
  "valid_at_or_interval": null,
  "issued_at": null,
  "historical_available_interval": null,
  "collector_seen_at": null,
  "fetched_at": null,
  "bbox_and_crs": null,
  "bands_units_scaling": null,
  "coverage_or_quality_assets": [],
  "role": "unclassified",
  "event_family_id": null,
  "parent_product_ids": [],
  "license_record": null,
  "access_status": "registered",
  "decode_status": "not_attempted",
  "track_admission": {}
}
```

`null`表示未知，不用当前时间、文件mtime或0填满。单个下载可能含多个产品和事件，必须允许一对多，不能强制一个ZIP只有一个event_id。event_family_id有不确定候选时保存匹配置信和理由，不强行归并。

### 必须检查的内容

**字节与格式**：HTTP 200不等于数据；识别HTML登录页、XML/JSON错误、Git LFS指针、截断流和错误Content-Length。SHA256自己算；ETag不是普遍意义的MD5。上游checksum原样记录并按算法验证，不能将MD5填入SHA256字段。

**安全读取**：先列ZIP/TAR成员和解压体积，拒绝绝对路径、`..`越界、设备节点及越界链接；不直接运行来源归档中的代码。NPZ使用`allow_pickle=False`。HDF5/NetCDF/GeoTIFF使用只读解析；pickle必要时先做版本与内容审查，在禁网、无凭据、资源受限的隔离环境处理，不从主HOME执行任意反序列化。

**数值与空间**：维度、坐标顺序、CRS、旋转/仿射、分辨率、单位、倍率/offset、NoData、QC、轨道和极化。经纬度转图片时保留裁剪/缩放转换；隐藏标签产生的有效域不能自动当传感器质量层公开。

**时间与引用**：观测、预报初始化、有效时间、发行、采集、实验交付分开。云端当前历史资产可能是事后修订版；未知历史可得时间只能进入明确的回溯/受控轨。预报的未来valid_at本身不违法；违法的是未来发行或未来观测被提前输入。平均/合成图的时间支持区间可能跨过截点，必须检查。

**来源角色**：原始观测、派生产品、官方声明、参考标签、背景层、自动问句分别标明。WorldFloods云/水标签、GEOID floodmask/permwater、ExEBench掩膜等不可当普通模型辅助输入。学习模型生成的掩膜并非独立人工真值。

**许可与受保护集合**：数据许可、代码许可、底图与新闻原文许可分开；共享盘可打开不等于允许再分发。保留作者原始split，但为DisasterTrace建立独立事件族隔离表；不越过旧heldout。受限来源只发布允许的元数据/获取脚本，不打包用户凭据或带令牌下载地址。

## 6. 如何统计“到底有多少数据”

每个来源及每个灾种均至少给出：上游公布数与原计数单位；清单可识别记录数；去重后的候选事件/事件族；真实原始产品和版本；已取回资产数与字节；解码成功数；静态/空间/真实多时相/同目标修订/严格as-of/原生多模态各自合格数。

数量必须带分母、时间范围、筛选条件和完整性状态。目录只翻了前几页时，写“已枚举N项，仍有next，当前下界”，不能输出全库总数或将未知写0。有效数据率必须基于实际检查样本；不能用3个样例推断全来源100%准入。

去重优先次序：原始权威事件ID（SID、EMSR、火灾ID等）→外部ID映射→地点/时间/路径匹配→人工不确定关系保留。不能只因“同一天同州”合并，也不能因不同县就认作独立风暴。

特别列出重叠：Digital Typhoon/TCIR/IBTrACS共享气旋；GEOID/KuroSiwo/UrbanSARFloods/WorldFloods可能共享CEMS事件或卫星场景；FIRMS/MTBS/WildfireSpreadTS/TS-SatFire可共享火灾；气旋与其洪水/风暴潮归同复合事件族；CHIRPS DAILY_SAT依赖IMERG；MRMS/SEVIR与雷达资料共享上游。记录“独立传感器、同传感器不同处理、同数据不同模态展示”三类关系。

### 扩容策略

全源元数据尽量完整，原始字节按事件需求获取。先用已有benchmark减少配准和标注工作，再用原始API补缺时刻、区域、站点和新事件。每一轮优先提升“已验证灾种覆盖”和“新独立事件增益”，避免全部预算消耗于洪水/气旋瓦片。

16类中当前数据不足的长尾（沙尘、陆地浓雾、闪旱、风暴潮及冬季细类）必须有独立核验报告。缺少专用benchmark时，登记原始观测+公开事件报告+预注册物理/统计定义；标记仍待语义审查，不用邻近类别冒充已完成覆盖。冻雨不能直接由雪盖图给标签；仅AOD不能确认沙尘；仅低能见度不能确认雾。

## 7. 网络与下载策略

每个来源先元数据再字节；支持Content-Length预检和流式字节上限，临时`.part`与最终对象分开。限额、限速、超时和访问限制分别报告。数据采集可对可重试的网络错误最多追加2次尝试，遵从Retry-After，保存每次记录；哈希不匹配、登录、许可不明不无限重试。模型重试规则与数据下载重试无关，本轮不调用模型。

对共享存储/多worker，用锁或原子创建避免两个worker下载同一文件；同一URL不同内容保存两个快照，不因文件名相同覆盖。支持断点续传前检查远端ETag/Last-Modified或版本ID，range响应必须是预期206；若服务器忽略range返回200，不能把完整正文接在旧.partial尾部。

限额和付款：匿名S3/GCS不需要新建云账户；但requester-pays、GEE项目、Earthdata/Kaggle登录和商业许可分别处理。不能因为有GEE认证就默认允许无限云计算或外部存储费用。FIRMS路径含MAP_KEY，所有日志/异常/清单需替换为占位符；不把临时签名URL长期作为数据身份。

## 8. 可复用的下载配方

以下命令是**针对已选公开资源的配方**。先创建隔离数据环境并审查依赖，只安装所需解析工具，不运行作者训练/评测入口。附带脚本默认dry-run；示例运行后不代表数据已准入。每次使用新的输出目录。

### 8.1 公开HTTP单文件：有字节上限的探针

```bash
# dry-run：完全不联网
python bounded_fetch.py \
  --url 'https://zenodo.org/records/12636522/files/catalog.csv?download=1' \
  --out "$DISASTERTRACE_DATA_ROOT/probe/tornet_catalog_plan" \
  --max-bytes 67108864

# 真正执行时换一个新目录；只取约38.2MB catalog，不下载3.2GB归档
python bounded_fetch.py \
  --url 'https://zenodo.org/records/12636522/files/catalog.csv?download=1' \
  --out "$DISASTERTRACE_DATA_ROOT/probe/tornet_catalog_get" \
  --max-bytes 67108864 --execute
```

输出`plan.json`、`receipt.json`和成功时的`payload.bin`，失败保留`.part`。`downloaded_not_decoded`不是“验收通过”。另按Content-Type和真实格式读取，不能只重命名后当作完成。脚本不管理全局预算、不支持登录/私有链接；Codex需在调度层维护总下载账本。

### 8.2 Hugging Face：同一完整提交用于列举和下载

```bash
# 需要huggingface_hub；dry-run无需安装或联网
python hf_file_manifest.py --repo zhaoshan/ee-bench_v1.0 --revision stable \
  --prefix data/weather/ --out "$DISASTERTRACE_DATA_ROOT/probe/exebench_plan"

# 正式元数据查询；仍不下载dataset ZIP
python hf_file_manifest.py --repo zhaoshan/ee-bench_v1.0 --revision stable \
  --prefix data/weather/ --out "$DISASTERTRACE_DATA_ROOT/probe/exebench_metadata" --execute
```

从`file_manifest.json`读取`resolved_commit`和文件名，**不得自行补全短SHA**。下面脚本取一个明确文件，执行前由全局预算检查所列文件大小：

```python
import json
from pathlib import Path
from huggingface_hub import hf_hub_download

manifest = json.loads(Path("/path/to/exebench_metadata/file_manifest.json").read_text())
assert manifest["status"] == "metadata_received"
sha = manifest["resolved_commit"]
file_name = "data/weather/coldwave.zip"
assert any(x["path"] == file_name for x in manifest["files"])
path = hf_hub_download(
    repo_id=manifest["repo_id"], repo_type="dataset", revision=sha,
    filename=file_name, local_dir="/path/to/new/exebench_coldwave",
    token=False,
)
print(path)
```

同法用于GEOID、KuroSiwo、UrbanSARFloods、WorldFloods、WeatherQA_SFT。目录有截断时先补齐相应prefix清单；不要把文件未出现在截断页解释为不存在。`hf_file_manifest.py`输出行数有上限，但SDK可能读取整个sibling元数据；首次大型repo仍需考虑元数据预算。

官方说明：https://huggingface.co/docs/huggingface_hub/guides/download

### 8.3 Zenodo：用记录API得到真实文件URL和checksum

```python
# 仅示例：实际请求加预算、超时、只读JSON和错误记录
import json
from urllib.request import urlopen
record_id = 12636522
with urlopen(f"https://zenodo.org/api/records/{record_id}", timeout=30) as r:
    meta = json.load(r)
for item in meta.get("files", []):
    print(item["key"], item.get("size"), item.get("checksum"), item["links"]["self"])
```

实际记录分别见D07、D19、D22、D51。采用记录页/API返回的文件链接，不猜archive名称，也不在不知道总量时运行下载整个record的工具。固定具体record而非不明确的latest DOI；自行算SHA256，同时验证作者MD5/SHA。

### 8.4 S3、GCS及云端分块数据

```bash
# AWS CLI：先列prefix，不递归sync整个桶
aws s3 ls --no-sign-request s3://sevir/
aws s3 ls --no-sign-request s3://unidata-nexrad-level2/
aws s3 ls --no-sign-request s3://spacenet-dataset/spacenet/SN8_floods/

# 真正下载时KEY必须从上一步取得，保留大小/ETag/版本
# aws s3 cp --no-sign-request 's3://BUCKET/RETURNED_KEY' /new/path/file

# GCS：只列正确bucket；gsutil需预先安装，匿名权限受实际服务控制
# gsutil ls gs://sen1floods11/
```

大目录应使用boto3/gcsfs官方分页接口并保存cursor；CLI只用于小探针。针对EWB的Zarr/Parquet，按作者loader或xarray/fsspec做有限选择，**先算chunk/row-group实际读取量**；小AOI不一定意味着小传输，某些chunk覆盖全球。不能执行整个Zarr目录rsync。

### 8.5 Drive / Dropbox / 百度网盘 / Nextcloud

```bash
# WeatherQA公开文件，使用作者README中的准确文件ID
# 先检查共享权限与大小；gdown本身不负责全局下载上限。
python -m gdown 'https://drive.google.com/uc?id=1GpEp6EFrCA6wqU6FEHsaMO7jwTckP_m4' \
  -O /new/path/weatherqa_raw_download
```

TCIR、FloodNet、M4Fog、Landslide4Sense使用第9节已定位的分享页。先列文件和配额；gdown folder整包、Dropbox folder打包和Nextcloud `/download`只能在确认返回真实文件后执行。网页需要交互、限流、验证码或授权时登记为manual_access_required，不绕过，不借不明镜像。M4Fog提取码是作者公开分享内容，可写入计划；用户密码、会话和OAuth token不可写入。

### 8.6 Kaggle

```bash
# 使用已有合法Kaggle认证（如服务要求），不在终端/仓库打印凭据
kaggle datasets files -d cdminix/us-drought-meteorological-data
kaggle datasets files -d fantineh/next-day-wildfire-spread
kaggle datasets files -d z789456sx/ts-satfire

# 对已列出的真实文件，按本地CLI --help确认版本参数：
# kaggle datasets download -d OWNER/SLUG -f RETURNED_FILENAME -p /new/path
```

先记录dataset version。CLI/API分页和文件过滤以当前安装版本为准，不能遇401/403时自动绕过。大归档由bulk范围批准后取。

### 8.7 GEE：集合ID明确，但必须先有项目权限

GEE不提供永久公共“整套数据ZIP”链接。第9节逐源给出准确`collection_id`和目录。先注册/初始化合法项目，然后按AOI/时间/波段查询，冻结实际asset IDs，再导出小范围GeoTIFF或GeoJSON。不要把目录页面当作下载文件。

```python
# 仅一个固定小AOI的目录探针，不自动下载或批量导出。
import os
import ee

ee.Initialize(project=os.environ["GEE_PROJECT"])
roi = ee.Geometry.Rectangle([-90.05, 29.95, -90.00, 30.00], proj="EPSG:4326", geodesic=False)
collection = (ee.ImageCollection("COPERNICUS/S1_GRD")
              .filterBounds(roi)
              .filterDate("2021-08-20", "2021-09-10")
              .sort("system:time_start")
              .limit(3))
metadata = collection.toList(3).map(lambda obj: ee.Image(obj).toDictionary()).getInfo()
# metadata可能为空，或无所需波段/覆盖；不是灾害证据验收。
print(metadata)
```

这个区域/日期仅说明参数，不承诺三景存在、VV/VH均可用或有灾。只验证一个集合后，将相同接口扩到其他数据；D24 MTBS应使用FeatureCollection。质量、波段、导出网格按产品独立指定；不做未知band自动猜测。正式资产下载记录getDownloadURL参数、实际波段和数值哈希，临时签名URL不进公开清单。小导出32MB/10000网格维度限制之外，改走另行批准的batch export。

官方：
- https://developers.google.com/earth-engine/guides/auth
- https://developers.google.com/earth-engine/apidocs/ee-imagecollection-filterdate
- https://developers.google.com/earth-engine/apidocs/ee-image-getdownloadurl

若需绕开GEE而取NASA原始卫星文件，使用官方Earthdata产品页/CMR：先查集合和版本，再用返回的collection concept ID查granule与下载links；**不虚构concept ID**。部分下载需要已有Earthdata授权。参考：https://cmr.earthdata.nasa.gov/search/site/docs/search/api.html 。这是一条备用获取路线，不声称所有GEE处理后产品在原生下载中完全等价。

### 8.8 FIRMS与CEMS等API

FIRMS的官方请求模板：

```text
https://firms.modaps.eosdis.nasa.gov/api/area/csv/{MAP_KEY}/{SOURCE}/{west,south,east,north}/{DAY_RANGE}/{YYYY-MM-DD}
```

从环境变量替换key，不打印成完整URL；先查产品有效期。当前文档一次DAY_RANGE为1..5。采集返回的NRT/SP要区分；无火点不证明无火或熄灭。模板依据：https://firms.modaps.eosdis.nasa.gov/api/area/

CEMS先列`public-activations-info/`，随后请求`public-activations/?code=返回的code`，跟随JSON真实`downloadPath`。NCEI/CHIRPS/OISST年度/月度目录先解析href，不猜最新创建时间后缀。CO-OPS、USDM使用第9节官方参数实例；成功JSON中仍可能有业务error，必须检查。

## 9. 逐项下载注册表

每条都保留下载路线的核验等级。移动的`main`、`stable`或动态URL仅供定位：正式获取前锁定完整commit、record或内容哈希。大文件体积用于预算，不能当实际解压占用；前序公布的样本规模要由本轮真实manifest复算。资料当前不可匿名下载的，明确登记访问流程而不是编造直链。

### 9.0 快速索引

| ID | 来源 | 获取方式 | 先行批次 |
|---|---|---|---|
|D01|NHC Public / Forecast Advisories + GIS|`PUBLIC_HTTP_WITH_PROVIDER_FAILURES`|A|
|D02|IBTrACS v4r01|`PUBLIC_HTTP`|A|
|D03|Digital Typhoon V2|`PUBLIC_DOWNLOAD_INDEX_LARGE_FILES`|B|
|D04|TCIR|`PUBLIC_SHARED_FOLDER_ACCESS_TO_VERIFY`|B|
|D05|NOAA Storm Events Database|`PUBLIC_HTTP_DIRECTORY`|A|
|D06|SEVIR|`PUBLIC_S3`|A|
|D07|TorNet|`PUBLIC_ZENODO`|A|
|D08|NOAA NEXRAD|`PUBLIC_S3`|C|
|D09|NOAA MRMS|`PUBLIC_S3`|C|
|D10|GOES-R ABI / GLM archives|`PUBLIC_S3`|C|
|D11|Global Flood Database v1|`GEE_PROJECT_REQUIRED`|A|
|D12|GEOID-Flood|`PUBLIC_HUGGINGFACE`|A|
|D13|KuroSiwo|`PUBLIC_HUGGINGFACE`|B|
|D14|UrbanSARFloods|`PUBLIC_HUGGINGFACE`|B|
|D15|Sen1Floods11 v1.1|`PUBLIC_GCS`|B|
|D16|SpaceNet 8|`PUBLIC_S3`|B|
|D17|FloodNet|`PUBLIC_SHARED_FOLDER_ACCESS_TO_VERIFY`|B|
|D18|CEMS Rapid Mapping|`PUBLIC_JSON_API`|A|
|D19|WildfireSpreadTS|`PUBLIC_ZENODO_LARGE_ARCHIVE`|A|
|D20|Next Day Wildfire Spread|`KAGGLE_ACCESS_TO_VERIFY`|B|
|D21|TS-SatFire|`KAGGLE_ACCESS_TO_VERIFY`|B|
|D22|Sen2Fire|`PUBLIC_ZENODO`|B|
|D23|NASA FIRMS|`FREE_MAP_KEY_REQUIRED`|A|
|D24|MTBS burned-area boundaries|`GEE_PROJECT_REQUIRED`|B|
|D25|ERA5-Land Hourly|`GEE_PROJECT_REQUIRED`|A|
|D26|GHCN-Daily|`PUBLIC_HTTP_DIRECTORY`|A|
|D27|ISD / Global Hourly|`PUBLIC_HTTP_DIRECTORY`|A|
|D28|NOAA GFS0P25|`GEE_PROJECT_REQUIRED`|B|
|D29|GPM IMERG V07|`GEE_PROJECT_REQUIRED`|A|
|D30|CHIRPS v3 DAILY_SAT|`GEE_PROJECT_REQUIRED`|A|
|D31|US Drought Monitor|`PUBLIC_API_AND_GIS_INDEX`|A|
|D32|SMAP Enhanced L3 Soil Moisture|`GEE_PROJECT_REQUIRED`|B|
|D33|MODIS Snow MOD10A1.061|`GEE_PROJECT_REQUIRED`|B|
|D34|MODIS LST MOD11A1.061|`GEE_PROJECT_REQUIRED`|B|
|D35|MERRA-2 aerosol diagnostics|`GEE_PROJECT_REQUIRED`|B|
|D36|Sentinel-5P OFFL Aerosol Index|`GEE_PROJECT_REQUIRED`|B|
|D37|NOAA CO-OPS water levels|`PUBLIC_JSON_CSV_API`|B|
|D38|NOAA OISST v2.1|`PUBLIC_HTTP_DIRECTORY`|B|
|D39|EM-DAT|`REGISTRATION_AND_LICENSE_GATE`|C|
|D40|NASA EONET v3|`PUBLIC_JSON_API`|A|
|D41|GDACS|`PUBLIC_FEED_NEEDS_RUNTIME_RECHECK`|C|
|D42|Sentinel-1 GRD|`GEE_PROJECT_REQUIRED`|A|
|D43|Sentinel-2 SR Harmonized|`GEE_PROJECT_REQUIRED`|A|
|D44|xBD|`REGISTRATION_AND_LICENSE_GATE`|C|
|D45|CrisisMMD v2.0|`PUBLIC_HTTP`|B|
|D46|Landslide4Sense|`PUBLIC_SHARE_ACCESS_TO_VERIFY`|C|
|D47|ExEBench / EarthExtreme-Bench|`PUBLIC_HUGGINGFACE`|A|
|D48|ExtremeWeatherBench|`PUBLIC_CLOUD_LAZY_ACCESS`|A|
|D49|WeatherQA|`PUBLIC_GDRIVE_AND_HF`|A|
|D50|CyPortQA|`PUBLIC_GITHUB_DATA`|A|
|D51|WorldFloods v2 / ml4floods|`PUBLIC_HF_LICENSE_CONDITIONED`|B|
|D52|DroughtED|`KAGGLE_ACCESS_TO_VERIFY`|B|
|D53|M4Fog|`PUBLIC_SHARE_MANUAL_ACCESS_AND_PROVENANCE_GATE`|C|
|D54|CLLMate|`PUBLIC_STRUCTURED_JSON_RAW_NEWS_UNRESOLVED`|A|

A/B/C表示建议取样顺序，不是能否使用或学术价值评级；所有来源先做DF01登记。

### D01｜NHC Public / Forecast Advisories + GIS

**覆盖与角色：** 热带气旋；风暴潮；强风；公告与空间产品。

**规模口径：** 随风暴、年份和公告编号变化；本次未统计全档案

**下载入口（类型不能混同）：**

| 入口 | 类型 | 核查边界 |
|---|---|---|
|[NHC原始公告档案](https://www.nhc.noaa.gov/archive/)|`http_directory`|官方入口已知；本轮访问失败，需CCI重试|
|[NHC GIS产品入口](https://prod-east-nhc.woc.noaa.gov/gis/)|`http_directory`|官方/作者页面已列出；本次未下载文件|
|[NHC预报风圈文件目录](https://ftp.nhc.noaa.gov/atcf/gis/fst/)|`http_directory`|前序官方入口；本轮未枚举|
|[已有Dorian公告样例](https://www.nhc.noaa.gov/archive/2019/al05/al052019.fstadv.001.shtml)|`http_file`|前序已定位；本轮不重复下载|

**Codex最小动作：**

1. 优先复用本地封存公告。新采集先下载年份/风暴索引，解析其真实href；只选development事件。
2. 保留HTML和PRE原文；GIS先取得目录清单，再按返回的ZIP文件名获取一个版本。
3. 遇403记录为provider_blocked；不得改写旧原文或生成假公告。

**可复用与适配边界：** 预报理解、同目标修订、风圈空间关系。风圈、路径锥、概率图不同；issued_at不等于历史available_at

**当前验收状态：** 下载路线已登记；本轮未取回数据归档、未解码、未验证CCI连通性、未准入benchmark。

### D02｜IBTrACS v4r01

**覆盖与角色：** 热带气旋；全球轨迹与事件索引。

**规模口径：** 本轮目录：since1980约144MB，ALL约331MB，last3years约10.4MB；文件会更新，下载时重新记录字节哈希。

前序数量备注（需实际清点，不能视为本次通过）：全球长期轨迹；按冻结版本去重storm ID后统计

**下载入口（类型不能混同）：**

| 入口 | 类型 | 核查边界 |
|---|---|---|
|[当前官方CSV目录](https://www.ncei.noaa.gov/data/international-best-track-archive-for-climate-stewardship-ibtracs/v04r01/access/csv/)|`http_directory`|本轮目录可读|
|[1980年以来轨迹CSV](https://www.ncei.noaa.gov/data/international-best-track-archive-for-climate-stewardship-ibtracs/v04r01/access/csv/ibtracs.since1980.list.v04r01.csv)|`http_file`|文件名与大小在本轮目录中可见；未下载|
|[全部轨迹CSV](https://www.ncei.noaa.gov/data/international-best-track-archive-for-climate-stewardship-ibtracs/v04r01/access/csv/ibtracs.ALL.list.v04r01.csv)|`http_file`|官方/作者页面已列出；本次未下载文件|
|[近三年CSV](https://www.ncei.noaa.gov/data/international-best-track-archive-for-climate-stewardship-ibtracs/v04r01/access/csv/ibtracs.last3years.list.v04r01.csv)|`http_file`|官方/作者页面已列出；本次未下载文件|

**Codex最小动作：**

1. 先取近三年或1980以来CSV，读取单位行、SID、ISO_TIME、海盆和机构风速定义。
2. 按SID/别名映射建立事件索引，不按机构或时刻重复计事件。

**可复用与适配边界：** 全球事件统一ID、强度和路径参考。最终best track不是历史实时预报；同一风暴多机构重复与口径差异；本轮有效目录是 /data/international-best-track-archive-for-climate-stewardship-ibtracs/，不要盲用旧 /pub/data/ibtracs 路径。

**当前验收状态：** 下载路线已登记；本轮未取回数据归档、未解码、未验证CCI连通性、未准入benchmark。

### D03｜Digital Typhoon V2

**覆盖与角色：** 热带气旋；时序遥感数据。

**规模口径：** 官方V2下载页：WP约56GB；AU约21GB。

前序数量备注（需实际清点，不能视为本次通过）：WP 1,116 / 192,956；AU 480 / 70,087；合计1,596 / 263,043

**下载入口（类型不能混同）：**

| 入口 | 类型 | 核查边界 |
|---|---|---|
|[V2官方实际下载页](https://agora.ex.nii.ac.jp/digital-typhoon/dataset/V2/)|`download_index`|本轮页面有WP/AU归档及SHA256；归档跳转未成功获取|
|[总项目说明](https://agora.ex.nii.ac.jp/digital-typhoon/dataset/)|`documentation`|官方/作者页面已列出；本次未下载文件|

**作者页面公布的SHA256（必须核对匹配版本）：**
```text
WP: d90ae06d06c3f9247a5970fd3768e5f40bafcffbd0514906e2d3cbb3b3d2edfc
AU: 229151465cc1e2fbbf5a0ece9150b429cf58921ff40ff80f902c2de4cf6dcdb5
```

**Codex最小动作：**

1. 解析V2页中西北太平洋/澳大利亚Download链接href，不猜ZIP/TAR文件名；保存该页快照及两个URL。
2. 校验作者SHA256；第一轮只做清单/体积评估，单个大包超过上限则标large_single_archive。
3. 取得后按真实气旋序列和年份登记，不运行pyphoon训练，不把V1/V2相加。

**可复用与适配边界：** 图像时序、强度变化、跨海盆外推。不要与V1累加；部分元数据由best-track插值；帧数不是事件数；V2旧样本参考与新发行时间分开；不要按作者迁移建议删除项目已冻结的V1证据。

**当前验收状态：** 下载路线已登记；本轮未取回数据归档、未解码、未验证CCI连通性、未准入benchmark。

### D04｜TCIR

**覆盖与角色：** 热带气旋；四通道遥感数据。

**规模口径：** 1,285场；70,501帧

**下载入口（类型不能混同）：**

| 入口 | 类型 | 核查边界 |
|---|---|---|
|[作者数据说明及原始下载按钮](https://www.csie.ntu.edu.tw/~htlin/program/TCIR/)|`documentation`|本轮作者页面可读|
|[作者Data短链接](https://tinyurl.com/ntuTCIR)|`download_redirect`|官方/作者页面已列出；本次未下载文件|
|[短链接解析到的Google Drive目录](https://drive.google.com/drive/folders/10tGM8DA-zWJRSYlW5OJyH15KtaKKYHAN?usp=drive_link)|`shared_folder`|本轮只确认跳转目标；没有枚举权限或下载文件|

**Codex最小动作：**

1. 先枚举目录，保存HDF5真实文件名、大小和访问状态；gdown只针对已选单文件。
2. h5py只读检查info/matrix、201×201×4、时间/SID和NaN；统计唯一气旋而非帧。

**可复用与适配边界：** IR/WV/VIS/PMW跨通道理解与强度估计。作者数据为201×201×4；缺失NaN；best-track事后估计，非当时已知事实；四个通道及其时间对齐按作者说明；缺测不能补0；标签是事后best-track。

**当前验收状态：** 下载路线已登记；本轮未取回数据归档、未解码、未验证CCI连通性、未准入benchmark。

### D05｜NOAA Storm Events Database

**覆盖与角色：** 暴雨；洪水；龙卷风；冰雹；雷暴风；热浪；寒潮；冬季天气等；多灾种事件记录。

**规模口径：** 1950–2026年度文件可查；本次未合并计数

**下载入口（类型不能混同）：**

| 入口 | 类型 | 核查边界 |
|---|---|---|
|[Storm Events年度CSV目录](https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/)|`http_directory`|本轮真实文件目录可读|

**Codex最小动作：**

1. 解析目录，按同一年和同一创建批次选择 StormEvents_details-*.csv.gz；不要猜 cYYYYMMDD 后缀。
2. locations/fatalities只做辅助关联。先一年，再分年份增量扩展；保留每个更新版。
3. 用EVENT_ID/EPISODE_ID/州县和时间建立候选，审查合并关系；地图之外负样本不能由无记录推断。

**可复用与适配边界：** 大规模事件索引、文字叙述、灾种平衡。详情/位置/伤亡表不能相加；局地记录需按事件组去重

**当前验收状态：** 下载路线已登记；本轮未取回数据归档、未解码、未验证CCI连通性、未准入benchmark。

### D06｜SEVIR

**覆盖与角色：** 强对流；降水；雷电；部分龙卷风/冰雹关联；配准多模态时序。

**规模口径：** 超过10,000组序列；完整下载约TB级

**下载入口（类型不能混同）：**

| 入口 | 类型 | 核查边界 |
|---|---|---|
|[官方开放数据登记](https://registry.opendata.aws/sevir/)|`documentation`|本轮登记页确认bucket与匿名访问|
|[公开对象目录](s3://sevir/)|`s3_prefix`|官方/作者页面已列出；本次未下载文件|
|[作者数据加载器](https://github.com/MIT-AI-Accelerator/eie-sevir)|`code`|官方/作者页面已列出；本次未下载文件|

**Codex最小动作：**

1. aws s3 ls --no-sign-request s3://sevir/；从实际结果定位CATALOG.csv再下载。
2. 按catalog选择少量id和同一id的传感器；用file_name/file_index定位HDF5。
3. 若一个容器过大，先登记size，不能为一个样本默认下载全库；必要时验证远程range支持。

**可复用与适配边界：** 雷达-卫星-闪电时序、降水演化。包含采样背景；序列数不是独立极端天气系统数；实际目录需冻结；不能把全部storm片段标成龙卷风或冰雹；传感器缺失须逐事件报告。

**当前验收状态：** 下载路线已登记；本轮未取回数据归档、未解码、未验证CCI连通性、未准入benchmark。

### D07｜TorNet

**覆盖与角色：** 龙卷风；强对流；带标签雷达时序。

**规模口径：** catalog约38.2MB；2013约3.2GB，其余每年约12–19GB。

前序数量备注（需实际清点，不能视为本次通过）：约20万样本；v1论文203,133；6.8%龙卷风正样本

**下载入口（类型不能混同）：**

| 入口 | 类型 | 核查边界 |
|---|---|---|
|[作者v1.1下载说明](https://github.com/mit-ll/tornet)|`code`|本轮README列出所有年度记录|
|[2013年度记录](https://zenodo.org/records/12636522)|`zenodo_record`|官方/作者页面已列出；本次未下载文件|
|[2014年度记录](https://zenodo.org/records/12637032)|`zenodo_record`|官方/作者页面已列出；本次未下载文件|
|[2015年度记录](https://zenodo.org/records/12655151)|`zenodo_record`|官方/作者页面已列出；本次未下载文件|
|[2016年度记录](https://zenodo.org/records/12655179)|`zenodo_record`|官方/作者页面已列出；本次未下载文件|
|[2017年度记录](https://zenodo.org/records/12655183)|`zenodo_record`|官方/作者页面已列出；本次未下载文件|
|[2018年度记录](https://zenodo.org/records/12655187)|`zenodo_record`|官方/作者页面已列出；本次未下载文件|
|[2019年度记录](https://zenodo.org/records/12655716)|`zenodo_record`|官方/作者页面已列出；本次未下载文件|
|[2020年度记录](https://zenodo.org/records/12655717)|`zenodo_record`|官方/作者页面已列出；本次未下载文件|
|[2021年度记录](https://zenodo.org/records/12655718)|`zenodo_record`|官方/作者页面已列出；本次未下载文件|
|[2022年度记录](https://zenodo.org/records/12655719)|`zenodo_record`|官方/作者页面已列出；本次未下载文件|
|[catalog.csv直链](https://zenodo.org/records/12636522/files/catalog.csv?download=1)|`http_file`|本轮记录页有此文件，38.2MB；未下载|
|[2013年压缩包](https://zenodo.org/records/12636522/files/tornet_2013.tar.gz?download=1)|`http_file`|官方/作者页面已列出；本次未下载文件|

**Codex最小动作：**

1. 先取2013记录JSON /api/records/12636522 和catalog.csv；核对1.1。
2. 按记录files[].links.self和checksum下载2013样例包，再按event/episode分组读取NetCDF。
3. 其余九年分批登记下载；不要运行作者带模型权重的evaluation脚本。

**可复用与适配边界：** 龙卷风识别、时间变化、困难负样本。不能写20万场龙卷风；使用发布版事件ID划分；修订版数量另核验；必须使用1.1：作者修复了部分标签、event/episode IDs并补了龙卷风起止时间。

**当前验收状态：** 下载路线已登记；本轮未取回数据归档、未解码、未验证CCI连通性、未准入benchmark。

### D08｜NOAA NEXRAD

**覆盖与角色：** 强对流；降水；龙卷风相关；连续雷达观测。

**规模口径：** 连续大规模档案；按站点、扫描、时段筛选

**下载入口（类型不能混同）：**

| 入口 | 类型 | 核查边界 |
|---|---|---|
|[官方bucket迁移说明](https://registry.opendata.aws/noaa-nexrad/)|`documentation`|本轮确认旧bucket停用日期和新bucket|
|[LevelII归档](s3://unidata-nexrad-level2/)|`s3_prefix`|官方/作者页面已列出；本次未下载文件|
|[LevelIII派生产品](s3://unidata-nexrad-level3/)|`s3_prefix`|官方/作者页面已列出；本次未下载文件|

**Codex最小动作：**

1. 只列目标日期/雷达站前缀，按列表key下载一体扫；解析专业雷达格式和扫描时间。
2. 使用aws --no-sign-request；禁止全bucket sync。

**可复用与适配边界：** 按事件补全雷达证据与序列。需做雷达专业处理；反射率不是直接灾损标签；旧noaa-nexrad-level2桶已弃用；采用当前登记的unidata-nexrad-level2。反射率不是直接灾损真值。

**当前验收状态：** 下载路线已登记；本轮未取回数据归档、未解码、未验证CCI连通性、未准入benchmark。

### D09｜NOAA MRMS

**覆盖与角色：** 暴雨；强对流；冰雹相关；多雷达/多传感器派生产品。

**规模口径：** 连续产品；按变量和时段统计

**下载入口（类型不能混同）：**

| 入口 | 类型 | 核查边界 |
|---|---|---|
|[公开目录](s3://noaa-mrms-pds/)|`s3_prefix`|官方/作者页面已列出；本次未下载文件|
|[官方登记](https://registry.opendata.aws/noaa-mrms-pds/)|`documentation`|本轮页面可读|

**Codex最小动作：**

1. 先列产品目录，再锁定QPE/所需变量、日期和少量GRIB2文件；记录软件读取方式和单位。
2. 不同产品/版本分别登记；与NEXRAD/SEVIR共享上游不可当独立验证。

**可复用与适配边界：** 降水、强对流多源证据。派生算法产品，不是独立人工灾害真值

**当前验收状态：** 下载路线已登记；本轮未取回数据归档、未解码、未验证CCI连通性、未准入benchmark。

### D10｜GOES-R ABI / GLM archives

**覆盖与角色：** 气旋；强对流；雷电；烟尘；连续卫星观测。

**规模口径：** 高频连续影像和闪电产品；无统一事件数

**下载入口（类型不能混同）：**

| 入口 | 类型 | 核查边界 |
|---|---|---|
|[官方卫星历史与bucket](https://registry.opendata.aws/noaa-goes/)|`documentation`|本轮登记页可读|
|[GOES-16资料桶](s3://noaa-goes16/)|`s3_prefix`|官方/作者页面已列出；本次未下载文件|
|[GOES-17资料桶](s3://noaa-goes17/)|`s3_prefix`|官方/作者页面已列出；本次未下载文件|
|[GOES-18资料桶](s3://noaa-goes18/)|`s3_prefix`|官方/作者页面已列出；本次未下载文件|
|[GOES-19资料桶](s3://noaa-goes19/)|`s3_prefix`|官方/作者页面已列出；本次未下载文件|

**Codex最小动作：**

1. 按事件日期、卫星、ABI/GLM产品列目录，选择真实存在的key；先少量NetCDF。
2. 跨卫星/重处理版本保留身份，不凭GOES-16/17旧教程认定当前实时产品。

**可复用与适配边界：** 高频多模态证据补齐。GOES16/17/18/19职责和时段不同；不用旧卫星名称假定当前实时

**当前验收状态：** 下载路线已登记；本轮未取回数据归档、未解码、未验证CCI连通性、未准入benchmark。

### D11｜Global Flood Database v1

**覆盖与角色：** 洪水；事件级淹水与持续时间产品。

**规模口径：** 913场

**下载入口（类型不能混同）：**

| 入口 | 类型 | 核查边界 |
|---|---|---|
|[GEE目录／波段与许可](https://developers.google.com/earth-engine/datasets/catalog/GLOBAL_FLOOD_DB_MODIS_EVENTS_V1)|`gee_catalog`|本轮目录页面可读；未认证查询|

**GEE精确ID：** `GLOBAL_FLOOD_DB/MODIS_EVENTS/V1`。

**Codex最小动作：**

1. 按第8节 GEE 配方，以 collection_id=GLOBAL_FLOOD_DB/MODIS_EVENTS/V1、固定AOI/日期/所需波段检索；先导出元数据，再小区域数值+有效性信息。
2. 先导出事件属性和已有ID；按事件边界导出一份flooded/duration及clear观测相关波段。
3. 保留永久水体处理和参考不确定性；记录913是目录事件产品口径，不是本次已准入数。

**可复用与适配边界：** 事件范围、持续时间、与设施空间关系。历史静态库；不是持续更新的实时洪水；保留云覆盖和永久水体

**当前验收状态：** 下载路线已登记；本轮未取回数据归档、未解码、未验证CCI连通性、未准入benchmark。

### D12｜GEOID-Flood

**覆盖与角色：** 洪水；配准多传感器带标签数据。

**规模口径：** 本轮HF根目录约588GB、sample约3.09GB；这是动态目录展示值，不覆盖旧发布的584/586GB记录。

前序数量备注（需实际清点，不能视为本次通过）：219事件；65国；超过14,000切片

**下载入口（类型不能混同）：**

| 入口 | 类型 | 核查边界 |
|---|---|---|
|[作者代码/下载器](https://github.com/links-ads/geoid-flood)|`code`|官方/作者页面已列出；本次未下载文件|
|[固定版本前先读取HF目录](https://huggingface.co/datasets/links-ads/geoid-flood/tree/main)|`hf_tree`|本轮目录可读，显示约588GB|
|[样例目录](https://huggingface.co/datasets/links-ads/geoid-flood/tree/main/sample)|`hf_tree`|本轮约3.09GB|
|[分片索引](https://huggingface.co/datasets/links-ads/geoid-flood/resolve/main/shard_index.json.gz)|`http_file`|本轮根目录有该文件|
|[SHA256清单](https://huggingface.co/datasets/links-ads/geoid-flood/resolve/main/SHA256SUMS)|`http_file`|官方/作者页面已列出；本次未下载文件|

**HF定位：** `links-ads/geoid-flood`；初始分支 `main`，下载前解析为完整SHA。

**Codex最小动作：**

1. 先解析main→完整SHA，使用同SHA读取shard_index.json.gz与SHA256SUMS；列sample目录。
2. 优先sample中的单个配套COG/标签；若需sample整体则预留约3.09GB。
3. 按父CEMS激活及原始场景分组；只读借鉴get_data.py，不直接全量运行。

**可复用与适配边界：** 灾前后SAR、灾前光学、DEM联合。与CEMS其他数据可能重合；双时相不等于多轮历史；标签来源分层；floodmask/permwater/部分validity可能来自Gold构造；不能作为普通传感器质量输入。GRD与RTC不是独立观测。

**当前验收状态：** 下载路线已登记；本轮未取回数据归档、未解码、未验证CCI连通性、未准入benchmark。

### D13｜KuroSiwo

**覆盖与角色：** 洪水；多时相SAR及参考。

**规模口径：** 43场；覆盖约338,000平方公里陆地

**下载入口（类型不能混同）：**

| 入口 | 类型 | 核查边界 |
|---|---|---|
|[作者README](https://github.com/Orion-AI-Lab/KuroSiwo)|`code`|本轮确认v2及以下公开数据|
|[GeoTIFF数据](https://huggingface.co/datasets/orion-ai-lab/Kuro-Siwo-GeoTIFFs)|`hf_dataset`|官方/作者页面已列出；本次未下载文件|
|[WebDataset分片](https://huggingface.co/datasets/orion-ai-lab/Kuro-Siwo-Webdataset)|`hf_dataset`|官方/作者页面已列出；本次未下载文件|
|[原始标注多边形](https://github.com/Orion-AI-Lab/KuroSiwo-annotations)|`code_data`|官方/作者页面已列出；本次未下载文件|

**HF定位：** `orion-ai-lab/Kuro-Siwo-GeoTIFFs`；初始分支 `main`，下载前解析为完整SHA。

**Codex最小动作：**

1. 优先GeoTIFF目录锁定SHA并列事件，挑一个完整灾前/后组合；WebDataset为替代序列化，不重复计数。
2. 标签多边形按版本与事件关联；优先HF而非旧Dropbox批量脚本。

**可复用与适配边界：** SAR变化、洪水迁移验证。面积不是图像数；不凭通用描述给出未核实切片总量；作者当前README已写v2；旧论文43事件不能自动当当前下载总数。

**当前验收状态：** 下载路线已登记；本轮未取回数据归档、未解码、未验证CCI连通性、未准入benchmark。

### D14｜UrbanSARFloods

**覆盖与角色：** 城市洪水；开放区域洪水；SAR强度/相干性数据。

**规模口径：** 18场；8,879切片

**下载入口（类型不能混同）：**

| 入口 | 类型 | 核查边界 |
|---|---|---|
|[作者README和订正表](https://github.com/jie666-6/UrbanSARFloods)|`code`|本轮作者README可读|
|[实际数据目录](https://huggingface.co/datasets/S1Floodbenchmark/UrbanSARFloods_v1/tree/main)|`hf_tree`|官方/作者页面已列出；本次未下载文件|
|[训练验证打包文件](https://huggingface.co/datasets/S1Floodbenchmark/UrbanSARFloods_v1/resolve/main/urban_sar_floods.tar.gz)|`http_file`|文件名由作者README明确列出，未取回|
|[原始SLC目录](https://huggingface.co/datasets/S1Floodbenchmark/UrbanSARFloods_v1/tree/main/Sentinel-1_SLC_data)|`hf_tree`|官方/作者页面已列出；本次未下载文件|

**HF定位：** `S1Floodbenchmark/UrbanSARFloods_v1`；初始分支 `main`，下载前解析为完整SHA。

**Codex最小动作：**

1. 锁定SHA后列testing_case_orig/testing_case_256及training包；先一个完整事件的SAR/GT。
2. 按README修正表核对事件日期与原始SLC文件名；不要只查原论文缺项表。

**可复用与适配边界：** 城市与非城市洪水对照、困难空间推理。类别严重不平衡；相干性与普通GRD不是同一输入；相干性依赖SLC，不以GEE GRD替代；保持NF/FO/FU类别口径。

**当前验收状态：** 下载路线已登记；本轮未取回数据归档、未解码、未验证CCI连通性、未准入benchmark。

### D15｜Sen1Floods11 v1.1

**覆盖与角色：** 洪水；S1/S2影像与标签。

**规模口径：** 完整发布约14GB；事件/切片数需以manifest重算

**下载入口（类型不能混同）：**

| 入口 | 类型 | 核查边界 |
|---|---|---|
|[正确GCS桶](gs://sen1floods11/)|`gcs_prefix`|官方/作者页面已列出；本次未下载文件|
|[作者README与样例](https://github.com/cloudtostreet/Sen1Floods11)|`code`|本轮README可读，正文有一处bucket拼写错误|
|[仓库内样例](https://github.com/cloudtostreet/Sen1Floods11/tree/master/sample)|`code_data`|官方/作者页面已列出；本次未下载文件|
|[事件元信息](https://raw.githubusercontent.com/cloudtostreet/Sen1Floods11/master/Sen1Floods11_Metadata.geojson)|`http_file`|文件名来自作者README；下载前核对当前树|

**Codex最小动作：**

1. 以gs://sen1floods11/为准，先gsutil ls，再选样例S1/S2/Label配套文件；不得用正文误写的senfloods11。
2. 匿名GCS读取优先；如需要凭据则记录原因，不开启付费工程。
3. S2为L1C TOA，不与S2 SR混同；保持-1无效与0非水、1水的区别。

**可复用与适配边界：** 感知基线、标签与无效像素处理。区分手工标签与自动/弱标签；README bucket拼写以实际可访问清单为准

**当前验收状态：** 下载路线已登记；本轮未取回数据归档、未解码、未验证CCI连通性、未准入benchmark。

### D16｜SpaceNet 8

**覆盖与角色：** 洪水；气旋次生淹水；高分辨率设施标签。

**规模口径：** 德国、Louisiana East、Louisiana West三个AOI

**下载入口（类型不能混同）：**

| 入口 | 类型 | 核查边界 |
|---|---|---|
|[官方资源页](https://spacenet.ai/sn8-challenge/)|`documentation`|本轮页面列出以下tarball|
|[SN8目录](s3://spacenet-dataset/spacenet/SN8_floods/)|`s3_prefix`|官方/作者页面已列出；本次未下载文件|
|[Germany_Training_Public](s3://spacenet-dataset/spacenet/SN8_floods/tarballs/Germany_Training_Public.tar.gz)|`s3_object`|官方/作者页面已列出；本次未下载文件|
|[Louisiana-East_Training_Public](s3://spacenet-dataset/spacenet/SN8_floods/tarballs/Louisiana-East_Training_Public.tar.gz)|`s3_object`|官方/作者页面已列出；本次未下载文件|
|[Louisiana-West_Test_Public](s3://spacenet-dataset/spacenet/SN8_floods/tarballs/Louisiana-West_Test_Public.tar.gz)|`s3_object`|官方/作者页面已列出；本次未下载文件|

**Codex最小动作：**

1. 匿名列SN8目录，优先按单独原图/标签/CSV取一个AOI；若仅大tar包可取则先记录大小并申请bulk档。
2. 同一次Ida相关AOI联成同事件族；公共test不代表你的新开发集。

**可复用与适配边界：** 建筑/道路淹水空间关系。道路淹水不等于业务上的不可通行；同场事件的不同AOI不跨split；CC BY-SA条款逐层核对；设施淹水不直接表示关闭或可通行。

**当前验收状态：** 下载路线已登记；本轮未取回数据归档、未解码、未验证CCI连通性、未准入benchmark。

### D17｜FloodNet

**覆盖与角色：** 洪水；气旋次生灾害；无人机语义分割。

**规模口径：** 2,343张；Harvey灾后

**下载入口（类型不能混同）：**

| 入口 | 类型 | 核查边界 |
|---|---|---|
|[作者当前Dropbox下载](https://www.dropbox.com/scl/fo/k33qdif15ns2qv2jdxvhx/ANGaa8iPRhvlrvcKXjnmNRc?rlkey=ao2493wzl1cltonowjdbrnp7f&e=2&dl=0)|`shared_folder`|本轮作者README列出；未枚举文件|
|[作者说明](https://github.com/BinaLab/FloodNet-Supervised_v1.0)|`code`|官方/作者页面已列出；本次未下载文件|

**Codex最小动作：**

1. 先按公开目录取得文件清单；选train图和对应mask检查尺寸、类别及拍摄信息。
2. 不要把README注释掉的旧Drive链接当首选；如果需要交互授权，标manual_access_required。

**可复用与适配边界：** 道路/建筑与淹水场景、低空多模态。2,343图像不是2,343事件；不能伪造灾前后序列；2343图主要来自Harvey；像片量不能代替跨事件覆盖。

**当前验收状态：** 下载路线已登记；本轮未取回数据归档、未解码、未验证CCI连通性、未准入benchmark。

### D18｜CEMS Rapid Mapping

**覆盖与角色：** 洪水；野火；风暴；其他自然灾害；事件激活/官方地图与矢量。

**规模口径：** 滚动激活与产品目录；需按灾种、区域去重

**下载入口（类型不能混同）：**

| 入口 | 类型 | 核查边界 |
|---|---|---|
|[官方API与返回字段](https://mapping.emergency.copernicus.eu/about/how-to-harvest-cems-mapping-data/emergency-response-data/)|`documentation`|本轮官方文档可读，明确downloadPath/version.deliveryTime|
|[激活分页目录](https://rapidmapping.emergency.copernicus.eu/backend/dashboard-api/public-activations-info/)|`api`|官方/作者页面已列出；本次未下载文件|
|[文档样例激活详情](https://rapidmapping.emergency.copernicus.eu/backend/dashboard-api/public-activations/?code=EMSR842)|`api_example`|参数示例由官方文档支持；本轮未请求JSON|
|[文档所列单产品下载示例](https://rapidmapping.emergency.copernicus.eu/backend/EMSR842/AOI01/GRA_PRODUCT/EMSR842_AOI01_GRA_PRODUCT_v1.zip)|`http_file`|仅文档样例URL，不等于本次已获取|

**Codex最小动作：**

1. 先limit=10记录results/count/next，再依next分页；批次有截断时保留游标。
2. 选公开激活后读取public-activations/?code=返回code，跟随aois[].products[].downloadPath下载单产品，不默认整事件zip。
3. 记录acquisitionTime、version.number/reason/deliveryTime、monitoring字段；资料敏感标记必须遵守。

**可复用与适配边界：** 图文配对、产品交付链、空间参考。activation≠独立物理事件；观测/制图/发行时间不同；与GEOID等共享来源；expectedDelivery不是实际交付；有字段不证明所有旧版本均可取回。不要拿未来成图作为过去输入。

**当前验收状态：** 下载路线已登记；本轮未取回数据归档、未解码、未验证CCI连通性、未准入benchmark。

### D19｜WildfireSpreadTS

**覆盖与角色：** 野火；逐日多模态序列。

**规模口径：** 48.4GB压缩包；作者md5 dc1a04e63ccc70037b277d585b8fe761。

前序数量备注（需实际清点，不能视为本次通过）：607场；13,607日图像；压缩包48.4GB

**下载入口（类型不能混同）：**

| 入口 | 类型 | 核查边界 |
|---|---|---|
|[官方Zenodo记录](https://zenodo.org/records/8006177)|`zenodo_record`|本轮记录页列出48.4GB ZIP及checksum|
|[数据直链](https://zenodo.org/records/8006177/files/WildfireSpreadTS.zip?download=1)|`http_file`|官方/作者页面已列出；本次未下载文件|
|[作者加载器与GEE构建代码](https://github.com/SebastianGer/WildfireSpreadTS)|`code`|官方/作者页面已列出；本次未下载文件|

**Codex最小动作：**

1. 先GET /api/records/8006177读取文件大小/checksum，不运行任何训练。
2. 该发布是约48.4GB单ZIP，超初轮cap；先完成元数据审查，待bulk批准后下载或确认HTTP range+ZIP目录支持后取指定文件。
3. 不得宣称单个ZIP可以天然按事件独立下载。

**可复用与适配边界：** 连续状态/火势扩展/下一日预测。不是13,607场火灾；原作者代码有已披露修复与角度特征注意事项；逐日演化不是同目标产品修订；火掩膜派生标签与原始观测区分。

**当前验收状态：** 下载路线已登记；本轮未取回数据归档、未解码、未验证CCI连通性、未准入benchmark。

### D20｜Next Day Wildfire Spread

**覆盖与角色：** 野火；多变量翌日配对样本。

**规模口径：** 18,545个t→t+1日样本

**下载入口（类型不能混同）：**

| 入口 | 类型 | 核查边界 |
|---|---|---|
|[作者指定Kaggle数据](https://www.kaggle.com/datasets/fantineh/next-day-wildfire-spread)|`kaggle_dataset`|Google Research README列出的同一slug|
|[作者原始数据导出/读取器](https://github.com/google-research/google-research/tree/master/simulation_research/next_day_wildfire_spread)|`code`|本轮README可读|

**Kaggle精确slug：** `fantineh/next-day-wildfire-spread`。

**Codex最小动作：**

1. kaggle datasets files -d fantineh/next-day-wildfire-spread；列出真实文件名再选小分片。
2. 仅解析TFRecord，不运行导出到Cloud Storage或训练；云导出需单列预算。

**可复用与适配边界：** 预测、当前证据与未来参考隔离。文中部分称fire events，但不能当18,545场独立火灾；MODIS火掩膜为派生产品；作者默认筛选当前和下一日都有火的ongoing样本，未来结果参与样本选择；不能据此直接估计完整场景虚警。

**当前验收状态：** 下载路线已登记；本轮未取回数据归档、未解码、未验证CCI连通性、未准入benchmark。

### D21｜TS-SatFire

**覆盖与角色：** 野火；多任务多时相遥感数据。

**规模口径：** 3,552景地表反射率影像；约71GB

**下载入口（类型不能混同）：**

| 入口 | 类型 | 核查边界 |
|---|---|---|
|[作者指定Kaggle数据](https://www.kaggle.com/datasets/z789456sx/ts-satfire)|`kaggle_dataset`|官方/作者页面已列出；本次未下载文件|
|[作者源码](https://github.com/zhaoyutim/TS-SatFire)|`code`|本轮README明确179事件、3552影像及Kaggle地址|

**Kaggle精确slug：** `z789456sx/ts-satfire`。

**Codex最小动作：**

1. 先kaggle datasets files -d z789456sx/ts-satfire，检查版本、大小、文件结构。
2. 按火灾和日期检查GeoTIFF/AF/BA标签；不要运行run_*model或自动装CUDA。

**可复用与适配边界：** 活动火、过火范围、扩展预测。必须按事件分组；与其他美国火灾数据可能重叠；179事件/3552影像是当前作者说明；不得与WildfireSpreadTS重合火灾重复计。

**当前验收状态：** 下载路线已登记；本轮未取回数据归档、未解码、未验证CCI连通性、未准入benchmark。

### D22｜Sen2Fire

**覆盖与角色：** 野火；多传感器影像切片。

**规模口径：** 6.3GB ZIP；2466切片/13bands；作者md5 135be2af2a8577c6deb12cbd7cc76c1a。

前序数量备注（需实际清点，不能视为本次通过）：2,466个512×512切片；13波段

**下载入口（类型不能混同）：**

| 入口 | 类型 | 核查边界 |
|---|---|---|
|[官方Zenodo数据](https://zenodo.org/records/10881058)|`zenodo_record`|本轮页面列出Sen2Fire.zip|
|[Sen2Fire ZIP直链](https://zenodo.org/records/10881058/files/Sen2Fire.zip?download=1)|`http_file`|官方/作者页面已列出；本次未下载文件|

**Codex最小动作：**

1. 先/api/records/10881058读取文件清单和license；Sen2Fire.zip约6.3GB，超初轮单文件cap时等待配置扩额。
2. np.load(..., allow_pickle=False)检查NPZ形状和波段；按四个场景分组，不按重叠patch切分。

**可复用与适配边界：** 烟羽/火情识别、模态对照。切片不是独立火灾；气溶胶高值不必然是火灾；作者标签来自MOD14A1派生火产品，不是逐像素新增人工Gold；相邻patch有重叠。

**当前验收状态：** 下载路线已登记；本轮未取回数据归档、未解码、未验证CCI连通性、未准入benchmark。

### D23｜NASA FIRMS

**覆盖与角色：** 野火；热异常；近实时火点/检测产品。

**规模口径：** 随日期/卫星/区域变化；需聚合为事件

**下载入口（类型不能混同）：**

| 入口 | 类型 | 核查边界 |
|---|---|---|
|[FIRMS Area API及申请MAP_KEY](https://firms.modaps.eosdis.nasa.gov/api/area/)|`api_documentation`|本轮官方文档可读|
|[可用时间查询入口](https://firms.modaps.eosdis.nasa.gov/api/data_availability/)|`api_documentation`|官方/作者页面已列出；本次未下载文件|

**Codex最小动作：**

1. 只从环境变量读FIRMS_MAP_KEY；模板见第8节，先查询产品可用日期。
2. 单次固定bbox和1天，当前文档DAY_RANGE为1..5；真实响应保留版本/产品，逐次保存。

**可复用与适配边界：** 滚动事件发现、新热点和空间变化。无火点不证明熄灭；重复过境/传感器去重；密钥不写入数据包；URL路径含key，日志必须脱敏；RT/URT会随NRT处理被移除/替换；空结果不证明熄灭。

**当前验收状态：** 下载路线已登记；本轮未取回数据归档、未解码、未验证CCI连通性、未准入benchmark。

### D24｜MTBS burned-area boundaries

**覆盖与角色：** 野火；大型火场与烧毁程度参考。

**规模口径：** 1984年以来；数量按冻结边界ID统计

**下载入口（类型不能混同）：**

| 入口 | 类型 | 核查边界 |
|---|---|---|
|[GEE目录／波段与许可](https://developers.google.com/earth-engine/datasets/catalog/USFS_GTAC_MTBS_burned_area_boundaries_v1)|`gee_catalog`|本轮目录页面可读；未认证查询|
|[当前USGS下载入口](https://burnseverity.cr.usgs.gov/direct-download)|`download_index`|MTBS旧站本轮明确迁移到此页面|

**GEE精确ID：** `USFS/GTAC/MTBS/burned_area_boundaries/v1`。

**Codex最小动作：**

1. 按第8节 GEE 配方，以 collection_id=USFS/GTAC/MTBS/burned_area_boundaries/v1、固定AOI/日期/所需波段检索；先导出元数据，再小区域数值+有效性信息。
2. 这是ee.FeatureCollection，不是ImageCollection；按火灾ID/年份筛少量矢量导出GeoJSON。
3. 替代入口只从USGS门户实际返回URL获取，避免旧站失效。

**可复用与适配边界：** 火场范围与后期参考。非全部火灾；事后产品不得提前给模型

**当前验收状态：** 下载路线已登记；本轮未取回数据归档、未解码、未验证CCI连通性、未准入benchmark。

### D25｜ERA5-Land Hourly

**覆盖与角色：** 热浪；寒潮；干旱；暴雨；积雪；强风等；连续重分析。

**规模口径：** 1950年以来逐小时；50变量；理论20年175,320时次

**下载入口（类型不能混同）：**

| 入口 | 类型 | 核查边界 |
|---|---|---|
|[GEE目录／波段与许可](https://developers.google.com/earth-engine/datasets/catalog/ECMWF_ERA5_LAND_HOURLY)|`gee_catalog`|本轮目录页面可读；未认证查询|
|[CDS原始产品目录](https://cds.climate.copernicus.eu/)|`account_portal`|原始备选门户；具体请求参数从产品页面API示例获取|

**GEE精确ID：** `ECMWF/ERA5_LAND/HOURLY`。

**Codex最小动作：**

1. 按第8节 GEE 配方，以 collection_id=ECMWF/ERA5_LAND/HOURLY、固定AOI/日期/所需波段检索；先导出元数据，再小区域数值+有效性信息。
2. 先少量区域/日期/变量temperature_2m等，读取变量单位、累计量重置规则；不要一次导出全部50变量。
3. ERA5与ERA5-Land是不同产品；重分析生成时间不同于观测有效时间，不声称实时可得。

**可复用与适配边界：** 连续场阈值筛选、过程检测与背景。重分析不是历史实时预测；参数和极端阈值必须先固定

**当前验收状态：** 下载路线已登记；本轮未取回数据归档、未解码、未验证CCI连通性、未准入benchmark。

### D26｜GHCN-Daily

**覆盖与角色：** 热浪；寒潮；暴雨；大雪；站点观测。

**规模口径：** 超过100,000站点；180国家/地区；温度站超过25,000

**下载入口（类型不能混同）：**

| 入口 | 类型 | 核查边界 |
|---|---|---|
|[GHCN原始下载目录](https://www.ncei.noaa.gov/pub/data/ghcn/daily/)|`http_directory`|本轮目录可读|
|[站点目录](https://www.ncei.noaa.gov/pub/data/ghcn/daily/ghcnd-stations.txt)|`http_file`|官方/作者页面已列出；本次未下载文件|
|[变量/站点覆盖清单](https://www.ncei.noaa.gov/pub/data/ghcn/daily/ghcnd-inventory.txt)|`http_file`|官方/作者页面已列出；本次未下载文件|
|[单站资料目录](https://www.ncei.noaa.gov/pub/data/ghcn/daily/all/)|`http_directory`|官方/作者页面已列出；本次未下载文件|
|[按年汇总目录](https://www.ncei.noaa.gov/pub/data/ghcn/daily/by_year/)|`http_directory`|官方/作者页面已列出；本次未下载文件|

**Codex最小动作：**

1. 先stations/inventory及readme；按地域/元素/时间覆盖选少量站点，再从all/目录获取实际ID.dly。
2. 解码TMAX/TMIN/PRCP/SNOW等元素、倍率与质量标志；缺测保持null，不把所有10万站点当同时有效。
3. 按固定阈值/持续时间构建冷热/降水事件；定义基准期与区域，不利用模型分数。

**可复用与适配边界：** 站点核验、极值与持续时间。站点记录长度不同；缺测不能变零；公开产品存在更新

**当前验收状态：** 下载路线已登记；本轮未取回数据归档、未解码、未验证CCI连通性、未准入benchmark。

### D27｜ISD / Global Hourly

**覆盖与角色：** 低能见度/浓雾；大风；热冷极端；降水；站点观测。

**规模口径：** 汇集超过35,000站点

**下载入口（类型不能混同）：**

| 入口 | 类型 | 核查边界 |
|---|---|---|
|[Global Hourly按年CSV目录](https://www.ncei.noaa.gov/data/global-hourly/access/)|`http_directory`|本轮目录可读|
|[ISD原始年度压缩资料](https://www.ncei.noaa.gov/pub/data/noaa/)|`http_directory`|官方/作者页面已列出；本次未下载文件|
|[ISD站点历史清单](https://www.ncei.noaa.gov/pub/data/noaa/isd-history.txt)|`http_file`|官方/作者页面已列出；本次未下载文件|

**Codex最小动作：**

1. 先取isd-history.txt，再在目标年份目录中按返回的站号文件下载；并行上限2。
2. 解析能见度、现象码、风和温湿度，保留报告时间、QC及站点移动。
3. 雾候选需现象码/可解释规则支持，低能见度可能为尘、烟或降水；不得全部贴fog。

**可复用与适配边界：** 能见度、风、温湿压与天气现象。不能仅以低能见度推断雾；不同报告时间和质量控制要保留

**当前验收状态：** 下载路线已登记；本轮未取回数据归档、未解码、未验证CCI连通性、未准入benchmark。

### D28｜NOAA GFS0P25

**覆盖与角色：** 多类天气极端的预测；模式预报。

**规模口径：** 滚动预报周期；具体可用初始化与时效由目录统计

**下载入口（类型不能混同）：**

| 入口 | 类型 | 核查边界 |
|---|---|---|
|[GEE目录／波段与许可](https://developers.google.com/earth-engine/datasets/catalog/NOAA_GFS0P25)|`gee_catalog`|本轮目录页面可读；未认证查询|

**GEE精确ID：** `NOAA/GFS0P25`。

**Codex最小动作：**

1. 按第8节 GEE 配方，以 collection_id=NOAA/GFS0P25、固定AOI/日期/所需波段检索；先导出元数据，再小区域数值+有效性信息。
2. 先列实际资产属性forecast_time、creation_time等，按当前目录定义映射issue/init/valid；不要把固定字段名推断作已验证。
3. 固定初始化和目标时刻；未来有效时刻的已发布预报可以输入，未来初始化产生的产品不能提前输入。

**可复用与适配边界：** 真正未来预测与预报修订。初始化与有效时间分开；未来预报可合法输入但未来初始化不可

**当前验收状态：** 下载路线已登记；本轮未取回数据归档、未解码、未验证CCI连通性、未准入benchmark。

### D29｜GPM IMERG V07

**覆盖与角色：** 暴雨；洪水；气旋降水；连续降水估计。

**规模口径：** 2000年以来半小时；理论20年350,640时次

**下载入口（类型不能混同）：**

| 入口 | 类型 | 核查边界 |
|---|---|---|
|[GEE目录／波段与许可](https://developers.google.com/earth-engine/datasets/catalog/NASA_GPM_L3_IMERG_V07)|`gee_catalog`|本轮目录页面可读；未认证查询|

**GEE精确ID：** `NASA/GPM_L3/IMERG_V07`。

**Codex最小动作：**

1. 按第8节 GEE 配方，以 collection_id=NASA/GPM_L3/IMERG_V07、固定AOI/日期/所需波段检索；先导出元数据，再小区域数值+有效性信息。
2. 先检查provisional/permanent状态和版本覆盖；保留半小时rate到累计量的转换。
3. V07永久产品和V08迁移范围以当次目录/源公告为准；同日期后续产品可能替换。

**可复用与适配边界：** 高频降水证据、累计量和极值。临时/最终产品会替换；V07永久产品2025-09-30后受V08迁移限制

**当前验收状态：** 下载路线已登记；本轮未取回数据归档、未解码、未验证CCI连通性、未准入benchmark。

### D30｜CHIRPS v3 DAILY_SAT

**覆盖与角色：** 干旱；降水极端；连续降水产品。

**规模口径：** 1981年以来日尺度；理论20年7,305日期

**下载入口（类型不能混同）：**

| 入口 | 类型 | 核查边界 |
|---|---|---|
|[GEE目录／波段与许可](https://developers.google.com/earth-engine/datasets/catalog/UCSB-CHC_CHIRPS_V3_DAILY_SAT)|`gee_catalog`|本轮目录页面可读；未认证查询|
|[CHIRPS v3原始可下载目录](https://data.chc.ucsb.edu/products/CHIRPS/v3.0/)|`http_directory`|本轮目录可读|
|[CHIRPS v3说明](https://data.chc.ucsb.edu/products/CHIRPS/v3.0/README-CHIRPSv3.0.txt)|`http_file`|官方/作者页面已列出；本次未下载文件|
|[日产品目录](https://data.chc.ucsb.edu/products/CHIRPS/v3.0/daily/)|`http_directory`|官方/作者页面已列出；本次未下载文件|

**GEE精确ID：** `UCSB-CHC/CHIRPS/V3/DAILY_SAT`。

**Codex最小动作：**

1. 按第8节 GEE 配方，以 collection_id=UCSB-CHC/CHIRPS/V3/DAILY_SAT、固定AOI/日期/所需波段检索；先导出元数据，再小区域数值+有效性信息。
2. 原始HTTP路线先下载README再沿daily/目录列具体SAT版本与文件，勿将ERA5分配日版本与SAT混用。
3. 固定累计窗口、时间边界；记录CHIRPS日产品依赖IMERG，不能当独立证据。

**可复用与适配边界：** 干旱累计窗口、降水异常。以IMERG分配pentad至daily，两者并非完全独立；最新AOI可用性需实查

**当前验收状态：** 下载路线已登记；本轮未取回数据归档、未解码、未验证CCI连通性、未准入benchmark。

### D31｜US Drought Monitor

**覆盖与角色：** 干旱；周地图/矢量与叙述。

**规模口径：** 1999年以来每周；约1,400期量级（估算，未枚举）

**下载入口（类型不能混同）：**

| 入口 | 类型 | 核查边界 |
|---|---|---|
|[官方REST下载说明](https://droughtmonitor.unl.edu/DmData/DataDownload/WebServiceInfo.aspx)|`api_documentation`|本轮页面明确URL和参数|
|[官方完整API下载示例](https://usdmdataservices.unl.edu/api/USStatistics/GetDroughtSeverityStatisticsByArea?aoi=us&startdate=1/1/2012&enddate=1/1/2013&statisticsType=1)|`api_example`|来自官方文档；非本次已请求|
|[GIS/周地图下载](https://droughtmonitor.unl.edu/DmData/GISData.aspx)|`download_index`|官方/作者页面已列出；本次未下载文件|
|[地图归档](https://droughtmonitor.unl.edu/Maps/MapArchive.aspx)|`download_index`|前序已知入口；执行时核对实际href|

**Codex最小动作：**

1. 统计先按StateStatistics/CountyStatistics等官方参数查询有限FIPS和时间区间；csv/json Accept显式声明。
2. GIS页需提交日期选择时记录参数与响应，只取返回的真实shapefile/GeoJSON链接；不猜USDM_日期.zip。
3. 记录有效周、周二资料截止与周四发行；同周不追溯修订不强造修订轨。

**可复用与适配边界：** 干旱等级、周际演化、跨证据推断。周四发布基于周二截止资料；不是预报；同周公布后不追溯修改；官方说明2004以前部分矢量由图像数字化，位置精度较差；空间边界任务需精度分层。

**当前验收状态：** 下载路线已登记；本轮未取回数据归档、未解码、未验证CCI连通性、未准入benchmark。

### D32｜SMAP Enhanced L3 Soil Moisture

**覆盖与角色：** 干旱；洪水前湿度；冻融；连续遥感土壤湿度。

**规模口径：** 006在GEE从2023-12-04开始；更早数据查005

**下载入口（类型不能混同）：**

| 入口 | 类型 | 核查边界 |
|---|---|---|
|[GEE目录／波段与许可](https://developers.google.com/earth-engine/datasets/catalog/NASA_SMAP_SPL3SMP_E_006)|`gee_catalog`|本轮目录页面可读；未认证查询|

**GEE精确ID：** `NASA/SMAP/SPL3SMP_E/006`。

**Codex最小动作：**

1. 按第8节 GEE 配方，以 collection_id=NASA/SMAP/SPL3SMP_E/006、固定AOI/日期/所需波段检索；先导出元数据，再小区域数值+有效性信息。
2. 先检查006实际开始时间和AOI有效检索；更早日期改查经验证的旧版本，不能静默拼接。
3. 保留土壤湿度QA、冻结/水体等限制；同一窗口的未来数据不能参与历史异常指标。

**可复用与适配边界：** 湿度状态和质量覆盖。不能把任务2015开始等同006含完整2015历史；中心窗异常可能含未来资料

**当前验收状态：** 下载路线已登记；本轮未取回数据归档、未解码、未验证CCI连通性、未准入benchmark。

### D33｜MODIS Snow MOD10A1.061

**覆盖与角色：** 积雪；冬季天气；连续遥感积雪覆盖。

**规模口径：** 2000年以来日尺度500m

**下载入口（类型不能混同）：**

| 入口 | 类型 | 核查边界 |
|---|---|---|
|[GEE目录／波段与许可](https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MOD10A1)|`gee_catalog`|本轮目录页面可读；未认证查询|

**GEE精确ID：** `MODIS/061/MOD10A1`。

**Codex最小动作：**

1. 按第8节 GEE 配方，以 collection_id=MODIS/061/MOD10A1、固定AOI/日期/所需波段检索；先导出元数据，再小区域数值+有效性信息。
2. 包含NDSI_Snow_Cover及相应QA/类别层，取一个地点数日；保存cloud/no decision/night等不同状态。
3. 雪盖图不是雪深、降雪量或冻雨标签；冬季灾种需与站点/事件资料联合。

**可复用与适配边界：** 积雪出现消退、空间范围。雪盖不等于雪深/降雪量；云/无效不等于无雪

**当前验收状态：** 下载路线已登记；本轮未取回数据归档、未解码、未验证CCI连通性、未准入benchmark。

### D34｜MODIS LST MOD11A1.061

**覆盖与角色：** 热浪；地表高温；连续遥感地表温度。

**规模口径：** 2000年以来日尺度1km

**下载入口（类型不能混同）：**

| 入口 | 类型 | 核查边界 |
|---|---|---|
|[GEE目录／波段与许可](https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MOD11A1)|`gee_catalog`|本轮目录页面可读；未认证查询|

**GEE精确ID：** `MODIS/061/MOD11A1`。

**Codex最小动作：**

1. 按第8节 GEE 配方，以 collection_id=MODIS/061/MOD11A1、固定AOI/日期/所需波段检索；先导出元数据，再小区域数值+有效性信息。
2. 读取LST_Day_1km/LST_Night_1km及QC与倍率；选两三个日期比较。
3. 地表温度不是2米气温；与GHCN/ERA5温度任务保持不同variable。

**可复用与适配边界：** 地表热异常与空间分布。地表温度不等于2米气温，不能直接替代热浪标准

**当前验收状态：** 下载路线已登记；本轮未取回数据归档、未解码、未验证CCI连通性、未准入benchmark。

### D35｜MERRA-2 aerosol diagnostics

**覆盖与角色：** 沙尘；烟尘；连续再分析气溶胶。

**规模口径：** 1980年以来小时数据

**下载入口（类型不能混同）：**

| 入口 | 类型 | 核查边界 |
|---|---|---|
|[GEE目录／波段与许可](https://developers.google.com/earth-engine/datasets/catalog/NASA_GSFC_MERRA_aer_2)|`gee_catalog`|本轮目录页面可读；未认证查询|

**GEE精确ID：** `NASA/GSFC/MERRA/aer/2`。

**Codex最小动作：**

1. 按第8节 GEE 配方，以 collection_id=NASA/GSFC/MERRA/aer/2、固定AOI/日期/所需波段检索；先导出元数据，再小区域数值+有效性信息。
2. 目录中选择明确dust相关变量而非总AOD；固定bbox/time/单位和垂直含义。
3. 将该层用于沙尘候选/输送背景；只有强度代理而无现象或观测支持时，不认定已验证沙尘灾害。

**可复用与适配边界：** 尘埃输送、沙尘事件筛选。总气溶胶≠沙尘；重分析非当时实时；结合站点天气现象

**当前验收状态：** 下载路线已登记；本轮未取回数据归档、未解码、未验证CCI连通性、未准入benchmark。

### D36｜Sentinel-5P OFFL Aerosol Index

**覆盖与角色：** 沙尘；烟羽；遥感气溶胶指数。

**规模口径：** 2018年以来卫星产品；数量随AOI筛选

**下载入口（类型不能混同）：**

| 入口 | 类型 | 核查边界 |
|---|---|---|
|[GEE目录／波段与许可](https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S5P_OFFL_L3_AER_AI)|`gee_catalog`|本轮目录页面可读；未认证查询|

**GEE精确ID：** `COPERNICUS/S5P/OFFL/L3_AER_AI`。

**Codex最小动作：**

1. 按第8节 GEE 配方，以 collection_id=COPERNICUS/S5P/OFFL/L3_AER_AI、固定AOI/日期/所需波段检索；先导出元数据，再小区域数值+有效性信息。
2. 先查询absorbing_aerosol_index及可用质量/覆盖，保存过境时刻、OFFL产品版本。
3. 结合ISD现象码/原始报告区分烟、尘；仅AER_AI高不构成duststorm Gold。

**可复用与适配边界：** 跨模态烟尘空间证据。吸收气溶胶不能单独区分尘/烟；OFFL非即时观测时间可用

**当前验收状态：** 下载路线已登记；本轮未取回数据归档、未解码、未验证CCI连通性、未准入benchmark。

### D37｜NOAA CO-OPS water levels

**覆盖与角色：** 风暴潮；沿海洪水；潮位站观测/潮汐预测。

**规模口径：** 可按站点与时段提取6分钟水位等

**下载入口（类型不能混同）：**

| 入口 | 类型 | 核查边界 |
|---|---|---|
|[官方API与参数](https://api.tidesandcurrents.noaa.gov/api/prod/)|`api_documentation`|本轮官方文档可读|
|[站点元数据API](https://api.tidesandcurrents.noaa.gov/mdapi/prod/)|`api_documentation`|官方/作者页面已列出；本次未下载文件|
|[有限历史下载示例](https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?begin_date=20200101&end_date=20200102&station=8518750&product=hourly_height&datum=MLLW&time_zone=gmt&units=metric&application=DisasterTrace&format=json)|`api_example`|参数依官方规范构造；本轮未请求，不保证指定窗口完整|

**Codex最小动作：**

1. 先确认站点/基准面可用，再取固定一天hourly_height或一个月以内6min water_level。
2. 潮汐predictions单独调用，同基准面、同时间网格配对；记录preliminary/verified。
3. 观测减天文潮是非潮汐余量，不能不加条件叫纯风暴增水；不要把官方返回error JSON当数据。

**可复用与适配边界：** 潮位异常和风暴潮过程。潮位≠纯风暴增水；基准面、预测潮与观测需一致

**当前验收状态：** 下载路线已登记；本轮未取回数据归档、未解码、未验证CCI连通性、未准入benchmark。

### D38｜NOAA OISST v2.1

**覆盖与角色：** 海洋热浪（气候扩展）；连续海表温度。

**规模口径：** 1981-09以来逐日0.25°；理论20年7,305日期

**下载入口（类型不能混同）：**

| 入口 | 类型 | 核查边界 |
|---|---|---|
|[OISST NetCDF原始月目录](https://www.ncei.noaa.gov/data/sea-surface-temperature-optimum-interpolation/v2.1/access/avhrr/)|`http_directory`|本轮目录可读|

**Codex最小动作：**

1. 沿月份目录列文件，选择一个真实日NetCDF，保存时间、纬经网格、单位及缺测定义。
2. 海洋热浪需固定季节基准和连续阈值；作为扩展单列，不强塞16主类。

**可复用与适配边界：** 海洋热浪阈值与持续时间。海洋热浪应明确单列；融合插值产品非原始独立传感器

**当前验收状态：** 下载路线已登记；本轮未取回数据归档、未解码、未验证CCI连通性、未准入benchmark。

### D39｜EM-DAT

**覆盖与角色：** 多灾种；含非天气灾害；灾害记录目录。

**规模口径：** 超过27,000条

**下载入口（类型不能混同）：**

| 入口 | 类型 | 核查边界 |
|---|---|---|
|[EM-DAT公共下载平台](https://public.emdat.be/)|`account_portal`|本轮页面可达；未登录/导出|
|[官方数据文档](https://doc.emdat.be/)|`documentation`|官方/作者页面已列出；本次未下载文件|

**Codex最小动作：**

1. 仅使用用户已有合法访问；未授权时记录needs_account_or_terms，不填写登录表也不绕过。
2. 导出后区分国家行/灾害事件/事件族，过滤非天气灾害；受限原文不自动发布。

**可复用与适配边界：** 全球候选发现、事件影响元信息。包含非天气灾害；跨国/多源记录需匹配；非精细时空Gold；不是全量匿名下载URL；不能用聚合HDX表冒充完整EM-DAT记录。

**当前验收状态：** 下载路线已登记；本轮未取回数据归档、未解码、未验证CCI连通性、未准入benchmark。

### D40｜NASA EONET v3

**覆盖与角色：** 火灾；风暴；洪水；干旱等及非天气灾害；事件发现目录。

**规模口径：** 滚动；按类别与日期查询

**下载入口（类型不能混同）：**

| 入口 | 类型 | 核查边界 |
|---|---|---|
|[EONET v3事件API](https://eonet.gsfc.nasa.gov/api/v3/events)|`api`|官方/作者页面已列出；本次未下载文件|
|[类别API](https://eonet.gsfc.nasa.gov/api/v3/categories)|`api`|官方/作者页面已列出；本次未下载文件|
|[官方参数说明](https://eonet.gsfc.nasa.gov/docs/v3)|`api_documentation`|本轮文档可读|

**Codex最小动作：**

1. 先类别表，再固定start/end/status=all/limit=10查询；按官方返回状态判断是否完整，不任意当limit10是总量。
2. 来源字段用于导航；event geometry/closed时间不作精细洪水界或精确结束时刻。

**可复用与适配边界：** 新事件导航、空间时间锚点。目录几何不是灾害边界；closed/time未必精确；无收录≠无灾

**当前验收状态：** 下载路线已登记；本轮未取回数据归档、未解码、未验证CCI连通性、未准入benchmark。

### D41｜GDACS

**覆盖与角色：** 多自然灾害；告警与事件导航。

**规模口径：** 滚动；数量需定期快照统计

**下载入口（类型不能混同）：**

| 入口 | 类型 | 核查边界 |
|---|---|---|
|[GDACS RSS](https://www.gdacs.org/xml/rss.xml)|`rss`|官方常用公开feed；本轮web读取失败，执行时重验|
|[GDACS官方说明](https://www.gdacs.org/About/overview.aspx)|`documentation`|官方/作者页面已列出；本次未下载文件|

**Codex最小动作：**

1. 限一次RSS获取，保存HTTP/XML异常；使用XML安全解析，不解析外部实体。
2. 按eventid/type/date关联EONET/CEMS，RSS滚动窗口不是完整历史档案。

**可复用与适配边界：** 跨灾种在线发现与风险资料。风险估计不等于最终损失标签；包含地质灾害

**当前验收状态：** 下载路线已登记；本轮未取回数据归档、未解码、未验证CCI连通性、未准入benchmark。

### D42｜Sentinel-1 GRD

**覆盖与角色：** 洪水；野火后变化；滑坡等；通用原始遥感底座。

**规模口径：** 2014年以来；目标AOI数量动态

**下载入口（类型不能混同）：**

| 入口 | 类型 | 核查边界 |
|---|---|---|
|[GEE目录／波段与许可](https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S1_GRD)|`gee_catalog`|本轮目录页面可读；未认证查询|

**GEE精确ID：** `COPERNICUS/S1_GRD`。

**Codex最小动作：**

1. 按第8节 GEE 配方，以 collection_id=COPERNICUS/S1_GRD、固定AOI/日期/所需波段检索；先导出元数据，再小区域数值+有效性信息。
2. 明确同轨向、相对轨道、模式与极化，再取灾前后真正可比较的场景；先metadata后小AOI导出。
3. 保持dB/线性功率、DEM处理和无效区域，不把同一场景多种处理当不同事件。

**可复用与适配边界：** 补充真实多期SAR证据。不是现成灾害标签；同轨道极化等条件匹配；入库时间不等于观测时间

**当前验收状态：** 下载路线已登记；本轮未取回数据归档、未解码、未验证CCI连通性、未准入benchmark。

### D43｜Sentinel-2 SR Harmonized

**覆盖与角色：** 洪水；野火；旱情；积雪；灾后变化；通用原始遥感底座。

**规模口径：** GEE SR自2017年以来；目标AOI可用图像数需查

**下载入口（类型不能混同）：**

| 入口 | 类型 | 核查边界 |
|---|---|---|
|[GEE目录／波段与许可](https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2_SR_HARMONIZED)|`gee_catalog`|本轮目录页面可读；未认证查询|

**GEE精确ID：** `COPERNICUS/S2_SR_HARMONIZED`。

**Codex最小动作：**

1. 按第8节 GEE 配方，以 collection_id=COPERNICUS/S2_SR_HARMONIZED、固定AOI/日期/所需波段检索；先导出元数据，再小区域数值+有效性信息。
2. 按目标区域、时段和质量找实际可用场景；保存SCL/QA选择和缩放。
3. 用SR影像替换作者原L1C/TOA时属于新协议；不得悄悄改变原benchmark输入。

**可复用与适配边界：** 多光谱与可见光输入。底层S2存在不代表论文标签也在GEE；不能把云遮挡当无灾

**当前验收状态：** 下载路线已登记；本轮未取回数据归档、未解码、未验证CCI连通性、未准入benchmark。

### D44｜xBD

**覆盖与角色：** 洪水；气旋；野火；含地震等；灾前后建筑损毁标签。

**规模口径：** 850,736建筑标注；45,362平方公里影像

**下载入口（类型不能混同）：**

| 入口 | 类型 | 核查边界 |
|---|---|---|
|[xView2数据申请/登录入口](https://xview2.org/dataset)|`account_portal`|页面JS渲染；本轮未登录、未确认实际资产URL|
|[官方基线与注册说明](https://github.com/DIUx-xView/xView2_baseline)|`code`|本轮README明确数据需注册/login下载|

**Codex最小动作：**

1. 读取官方访问与许可条件；用户已有授权文件先只读建立目录，否则needs_account。
2. 不得下载未知镜像或用代码LICENSE替代影像许可；收到正式下载URL后写私有获取清单。
3. 按disaster_name、影像前后时间和建筑ID索引，保留非天气灾害为单列扩展。

**可复用与适配边界：** 建筑级影响、多灾种感知对照。标签包含非天气事件；高分影像许可需单核；事件数不能用建筑数替代

**当前验收状态：** 下载路线已登记；本轮未取回数据归档、未解码、未验证CCI连通性、未准入benchmark。

### D45｜CrisisMMD v2.0

**覆盖与角色：** 气旋；洪水；野火；含地震；社交媒体图文。

**规模口径：** 7场灾害；16,058文本；18,082图像；约1.8GB

**下载入口（类型不能混同）：**

| 入口 | 类型 | 核查边界 |
|---|---|---|
|[作者v2说明](https://crisisnlp.qcri.org/crisismmd)|`documentation`|本轮页面明确v2包与图文数|
|[v2图文包直链](https://crisisnlp.qcri.org/data/crisismmd/CrisisMMD_v2.0.tar.gz)|`http_file`|本轮从作者下载按钮解析；web因gzip类型不渲染，未下载|
|[使用条款入口](https://crisisnlp.qcri.org/crisismmd)|`license_entry`|官方/作者页面已列出；本次未下载文件|

**Codex最小动作：**

1. 先将v2约1.8GB归档放新路径并校验完整性；按许可只读解包，选择weather事件与样例。
2. 排除地震；事件涉及旧NHC heldout的记录进入隔离区，不用于开发prompt。
3. 图文标签可能不同，不能只因同一推文就认为空间/语义完全一致；不输出个人身份资料。

**可复用与适配边界：** 真实图文、信息相关性和粗粒度影响。全量抓取14M推文不是发布标注量；图文标签可能不同；不是精确几何Gold

**当前验收状态：** 下载路线已登记；本轮未取回数据归档、未解码、未验证CCI连通性、未准入benchmark。

### D46｜Landslide4Sense

**覆盖与角色：** 降雨诱发滑坡（扩展）；含地震诱发滑坡；多源滑坡标签。

**规模口径：** 原论文摘要3,799切片；四地区/时段

**下载入口（类型不能混同）：**

| 入口 | 类型 | 核查边界 |
|---|---|---|
|[作者竞赛数据说明](https://github.com/iarai/Landslide4Sense-2022)|`code`|本轮README明确训练/验证下载|
|[训练数据（带标签）](https://cloud.iarai.ac.at/index.php/s/KrwKngeXN7KjkFm)|`shared_folder`|官方/作者页面已列出；本次未下载文件|
|[验证影像](https://cloud.iarai.ac.at/index.php/s/N6TacGsfr5nRNWr)|`shared_folder`|官方/作者页面已列出；本次未下载文件|

**Codex最小动作：**

1. 先解析公开分享页面中的Download，不猜归档名；训练集含img/mask，验证/测试未必有公开标签。
2. 只读h5检查14通道、128×128和mask；按地区/灾害诱因筛降雨滑坡。

**可复用与适配边界：** 地形+光学的次生灾害迁移。必须筛除地震诱发部分后才称天气相关；版本/划分需重核；本轮竞赛README列训练3799、验证245、测试800；3799不是全套总数。只有训练标签明确公开。

**当前验收状态：** 下载路线已登记；本轮未取回数据归档、未解码、未验证CCI连通性、未准入benchmark。

### D47｜ExEBench / EarthExtreme-Bench

**覆盖与角色：** 热浪；寒潮；气旋；极端降水；雷达风暴；火烧迹地；洪水；整理后数值/遥感任务集合。

**规模口径：** 本轮目录：coldwave 4.39MB；heatwave 65.3MB；expcp 545MB；tropicalCyclone 5.06GB；storm 17.3GB；fire 2.65GB；flood 4.69GB。

前序数量备注（需实际清点，不能视为本次通过）：作者论文55热浪序列、9寒潮序列、95气旋、1092降水序列、931雷达风暴序列；需按冻结发布复算。

**下载入口（类型不能混同）：**

| 入口 | 类型 | 核查边界 |
|---|---|---|
|[作者仓库](https://github.com/zhaoshan2/EarthExtreme-Bench)|`code`|官方/作者页面已列出；本次未下载文件|
|[发布目录](https://huggingface.co/datasets/zhaoshan/ee-bench_v1.0/tree/stable/data)|`hf_tree`|本轮目录可读|
|[data/weather/coldwave.zip](https://huggingface.co/datasets/zhaoshan/ee-bench_v1.0/resolve/stable/data/weather/coldwave.zip)|`http_file`|本轮HF目录确认精确相对路径；链接仍为移动分支，执行前锁SHA|
|[data/weather/heatwave.zip](https://huggingface.co/datasets/zhaoshan/ee-bench_v1.0/resolve/stable/data/weather/heatwave.zip)|`http_file`|本轮HF目录确认精确相对路径；链接仍为移动分支，执行前锁SHA|
|[data/weather/expcp.zip](https://huggingface.co/datasets/zhaoshan/ee-bench_v1.0/resolve/stable/data/weather/expcp.zip)|`http_file`|本轮HF目录确认精确相对路径；链接仍为移动分支，执行前锁SHA|
|[data/weather/tropicalCyclone.zip](https://huggingface.co/datasets/zhaoshan/ee-bench_v1.0/resolve/stable/data/weather/tropicalCyclone.zip)|`http_file`|本轮HF目录确认精确相对路径；链接仍为移动分支，执行前锁SHA|
|[data/weather/storm.zip](https://huggingface.co/datasets/zhaoshan/ee-bench_v1.0/resolve/stable/data/weather/storm.zip)|`http_file`|本轮HF目录确认精确相对路径；链接仍为移动分支，执行前锁SHA|
|[data/eo/fire.zip](https://huggingface.co/datasets/zhaoshan/ee-bench_v1.0/resolve/stable/data/eo/fire.zip)|`http_file`|本轮HF目录确认精确相对路径；链接仍为移动分支，执行前锁SHA|
|[data/eo/flood.zip](https://huggingface.co/datasets/zhaoshan/ee-bench_v1.0/resolve/stable/data/eo/flood.zip)|`http_file`|本轮HF目录确认精确相对路径；链接仍为移动分支，执行前锁SHA|

**HF定位：** `zhaoshan/ee-bench_v1.0`；初始分支 `stable`，下载前解析为完整SHA。

**Codex最小动作：**

1. 必须通过HF API把stable解析为完整SHA，列目录/文件下载均使用同SHA。
2. 首轮coldwave→heatwave→expcp，之后按预算取EO火/洪水和大气旋/雷达包；不运行原全量下载器。
3. 检查ZIP内格式及metadata；pickle/torch pickle不得在有凭据的主环境直接反序列化。

**可复用与适配边界：** 直接复用数据包、变量元信息、加载器和标签，优先降低多灾种准备工作。。不是原生异步图文；再分析/best track/最终掩膜不得提前作为历史证据。；旧下载器列目录stable、下载默认分支的问题不得照搬；不要把天气雷达storm等同全部强对流细类。

**当前验收状态：** 下载路线已登记；本轮未取回数据归档、未解码、未验证CCI连通性、未准入benchmark。

### D48｜ExtremeWeatherBench

**覆盖与角色：** 热浪；寒潮；强对流；气旋；降水等；云端事件配置与观测/预测适配器。

**规模口径：** 不按整库体积估算；按实际Zarr/Parquet读取量登记。

**下载入口（类型不能混同）：**

| 入口 | 类型 | 核查边界 |
|---|---|---|
|[官方数据访问文档](https://extremeweatherbench.readthedocs.io/en/latest/data/)|`documentation`|本轮文档列出以下精确URI|
|[作者代码](https://github.com/brightbandtech/extremeweatherbench)|`code`|官方/作者页面已列出；本次未下载文件|
|[ERA5云端Zarr](gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3)|`gcs_cloud_dataset`|官方/作者页面已列出；本次未下载文件|
|[GHCN小时2020–2024](gs://extremeweatherbench/datasets/ghcnh_all_2020_2024.parq)|`gcs_cloud_dataset`|官方/作者页面已列出；本次未下载文件|
|[局地风暴报告](gs://extremeweatherbench/datasets/combined_canada_australia_us_lsr_01012020_09272025.parq)|`gcs_cloud_dataset`|官方/作者页面已列出；本次未下载文件|
|[从报告派生的PPH](gs://extremeweatherbench/datasets/practically_perfect_hindcast_20200104_20250927.zarr)|`gcs_cloud_dataset`|官方/作者页面已列出；本次未下载文件|

**Codex最小动作：**

1. 先锁作者代码版本和具体case配置；只读一个case所需时间、区域、变量。
2. 读取chunk/row-group元数据估算传输量，必要时在其上重写有预算loader；不得整个Zarr clone或全表转CSV。
3. 从云端得到的确切切片保存原生维度/单位和来源，不只保存xarray repr。

**可复用与适配边界：** 复用事件范围、ERA5/GHCN/LSR/IBTrACS数据访问和init/lead/valid划分。。与ExEBench不同工作；PPH来自LSR；lazy不等于不产生网络或全零费用。

**当前验收状态：** 下载路线已登记；本轮未取回数据归档、未解码、未验证CCI连通性、未准入benchmark。

### D49｜WeatherQA

**覆盖与角色：** 强对流；部分冬季天气；原生SPC参数图+业务讨论。

**规模口径：** 作者图像包2014–2019约10GB；2020约1.5GB。

**下载入口（类型不能混同）：**

| 入口 | 类型 | 核查边界 |
|---|---|---|
|[作者说明](https://github.com/chengqianma/WeatherQA)|`code`|本轮README列出下面三个准确Drive文件ID|
|[原始Mesoscale Discussion文本](https://drive.google.com/file/d/1GpEp6EFrCA6wqU6FEHsaMO7jwTckP_m4/view?usp=sharing)|`gdrive_file`|官方/作者页面已列出；本次未下载文件|
|[2014–2019图像](https://drive.google.com/file/d/1mViaf1f-sWB1DyfCrw-NwmZp4gj96mYr/view?usp=drive_link)|`gdrive_file`|官方/作者页面已列出；本次未下载文件|
|[2020图像](https://drive.google.com/file/d/17Hfv2NOLpy6rJBUrghaZmU_7r6WDCuDs/view?usp=sharing)|`gdrive_file`|官方/作者页面已列出；本次未下载文件|
|[加工SFT版本](https://huggingface.co/datasets/ZhanxiangHua/WeatherQA_SFT)|`hf_dataset`|官方/作者页面已列出；本次未下载文件|
|[SPC原始分析图档案](https://www.spc.noaa.gov/exper/ma_archive/)|`download_index`|官方/作者页面已列出；本次未下载文件|
|[SPC原始讨论入口](https://www.spc.noaa.gov/products/md/)|`download_index`|官方/作者页面已列出；本次未下载文件|

**Codex最小动作：**

1. 先原始文本与一个完整20参数图组，记录md_id/year/time/parameter映射；gdown文件ID用第8节配方。
2. 优先2014–2019开发样例；2020原test可下载隔离以验格式，不用于优化后仍声称原test独立。
3. HF加工SFT的正确选项和CoT进入私有标签，不当真实原始公告；找到同天气过程的连续讨论才构建自然时序。

**可复用与适配边界：** 复用讨论ID、图文配对与参数地图，不从零配图。。20图主要为同一时刻不同参数，非20时刻；风险讨论不是最终天气发生标签。

**当前验收状态：** 下载路线已登记；本轮未取回数据归档、未解码、未验证CCI连通性、未准入benchmark。

### D50｜CyPortQA

**覆盖与角色：** 气旋；港口相关影响；NHC图形/公告/USCG资料及场景索引。

**规模口径：** 117k+QA、2900+气旋–港口场景，非独立气旋计数。

**下载入口（类型不能混同）：**

| 入口 | 类型 | 核查边界 |
|---|---|---|
|[作者仓库](https://github.com/ChenchenMobility/MLLM-Bench-CyPortQA)|`code`|本轮README确认目录|
|[原始资料目录API](https://api.github.com/repos/ChenchenMobility/MLLM-Bench-CyPortQA/contents/source_data)|`github_contents`|官方/作者页面已列出；本次未下载文件|
|[问题与多模态输入目录API](https://api.github.com/repos/ChenchenMobility/MLLM-Bench-CyPortQA/contents/dataset)|`github_contents`|官方/作者页面已列出；本次未下载文件|

**Codex最小动作：**

1. 优先本地已有副本；否则contents/tree API列实际大小写文件名（Encoded_senario.JSON等可能与旧文档不同）。
2. 锁定commit，选择source_data原始小文件和一个图件；发现LFS pointer需按正式LFS取得实际字节并计费/配额检查。
3. 不要运行models/run.py、安装全模型依赖或推理；按风暴而不是港口场景分组。

**可复用与适配边界：** 沿用当前NHC基础，复用source_data和场景映射。。业务开放式答案不直接作自动安全决策Gold；AIS/第三方图层许可另核查。

**当前验收状态：** 下载路线已登记；本轮未取回数据归档、未解码、未验证CCI连通性、未准入benchmark。

### D51｜WorldFloods v2 / ml4floods

**覆盖与角色：** 洪水；云与水体标签、配准影像及处理代码。

**规模口径：** 作者约509对影像/掩膜；HF文档约76GB，需按版本清点。

**下载入口（类型不能混同）：**

| 入口 | 类型 | 核查边界 |
|---|---|---|
|[作者数据说明](https://spaceml-org.github.io/ml4floods/content/worldfloods_dataset.html)|`documentation`|本轮官方文档列HF v2与许可|
|[WorldFloods v2公开HF](https://huggingface.co/datasets/isp-uv-es/WorldFloodsv2)|`hf_dataset`|官方/作者页面已列出；本次未下载文件|
|[额外整理地图与标签记录](https://zenodo.org/records/8153514)|`zenodo_record`|官方/作者页面已列出；本次未下载文件|
|[处理代码](https://github.com/spaceml-org/ml4floods)|`code`|官方/作者页面已列出；本次未下载文件|

**HF定位：** `isp-uv-es/WorldFloodsv2`；初始分支 `main`，下载前解析为完整SHA。

**Codex最小动作：**

1. 先HF锁SHA列元数据，按一个事件选图和两通道参考；图/云/标签分角色。
2. 先读并记录非商业条件，旧GCS付费路线默认禁用；Zarr/整库不自动镜像。

**可复用与适配边界：** 复用图像/掩膜以及cloud-versus-water显式处理。。原v1 GCS可为requester-pays，代码与数据/模型许可不同。

**当前验收状态：** 下载路线已登记；本轮未取回数据归档、未解码、未验证CCI连通性、未准入benchmark。

### D52｜DroughtED

**覆盖与角色：** 干旱（闪旱需另定义）；气象/土壤/县域与USDM等级配对。

**规模口径：** 记录、县域和滑动时间窗，尚未复算独立事件数。

**下载入口（类型不能混同）：**

| 入口 | 类型 | 核查边界 |
|---|---|---|
|[作者数据发布slug](https://www.kaggle.com/datasets/cdminix/us-drought-meteorological-data)|`kaggle_dataset`|前序作者论文定位；本轮网页可达但客户端渲染未列文件|
|[作者论文说明](https://www.climatechange.ai/papers/icml2021/22)|`paper`|官方/作者页面已列出；本次未下载文件|

**Kaggle精确slug：** `cdminix/us-drought-meteorological-data`。

**Codex最小动作：**

1. kaggle datasets files -d cdminix/us-drought-meteorological-data，锁dataset版本，获取一个有日期/FIPS/目标的分片。
2. 检查时间窗是否含未来、标签发布时间、县域重叠；不要直接把所有窗口当独立极端事件。

**可复用与适配边界：** 复用FIPS、时间和气象特征配对，配合D31地图。。一般干旱不等于闪旱；多个县可能共享同一干旱过程。

**当前验收状态：** 下载路线已登记；本轮未取回数据归档、未解码、未验证CCI连通性、未准入benchmark。

### D53｜M4Fog

**覆盖与角色：** 海雾；海洋低能见度；卫星/海温/稀疏观测和雾标签。

**规模口径：** 论文68000 data cubes/15海区；实际各公开子集范围独立核验。

**下载入口（类型不能混同）：**

| 入口 | 类型 | 核查边界 |
|---|---|---|
|[本轮取得下载列表的README](https://github.com/Clynie/M4Fog)|`code`|公开副本README可读；未验证网盘文件/许可|
|[TrackA H8/H9黄渤海（公开提取码 6vm7）](https://pan.baidu.com/s/1aOw3TqzkS7E0ymLG0k2BhA?pwd=6vm7)|`baidu_shared_file`|README公开分享链接；不是用户密钥；本轮未通过网盘认证|
|[TrackA FY4A黄渤海（公开提取码 wp9k）](https://pan.baidu.com/s/1FSNdZoZCZ4mdu9_ehMRLIA?pwd=wp9k)|`baidu_shared_file`|README公开分享链接；不是用户密钥；本轮未通过网盘认证|
|[TrackA GOES多海区（公开提取码 jv7g）](https://pan.baidu.com/s/16RCgHSbdbNDgV8HMwKojPw?pwd=jv7g)|`baidu_shared_file`|README公开分享链接；不是用户密钥；本轮未通过网盘认证|
|[TrackB H8/H9（公开提取码 8q75）](https://pan.baidu.com/s/1q0s9eqAlydmyX6lu0znd3w?pwd=8q75)|`baidu_shared_file`|README公开分享链接；不是用户密钥；本轮未通过网盘认证|
|[TrackC H8/H9多区域（公开提取码 99ci）](https://pan.baidu.com/s/1it_gK_v_RDLXRoxMX-X4Ow?pwd=99ci)|`baidu_shared_file`|README公开分享链接；不是用户密钥；本轮未通过网盘认证|
|[ICOADS 2015–2024（公开提取码 yfat）](https://pan.baidu.com/s/1_8hTqhCS5ZyrkCqvTrT7KQ?pwd=yfat)|`baidu_shared_file`|README公开分享链接；不是用户密钥；本轮未通过网盘认证|
|[中文海洋天气综述2017–2022（公开提取码 amwc）](https://pan.baidu.com/s/1QE5QicyA1tFalcguP_fY_Q?pwd=amwc)|`baidu_shared_file`|README公开分享链接；不是用户密钥；本轮未通过网盘认证|

**Codex最小动作：**

1. 先验证公开分享是否有效、作者发布归属与许可；需要交互则登记manual_access_required，不绕验证码/登录。
2. 公共提取码可保留，用户账户token绝不写入；没有自动获取能力不阻塞其他53项。
3. 成功取得一份后核验时间、dense/sparse配准和标签；云图预测不等于雾发生预测。

**可复用与适配边界：** 作为雾类别的多模态与真实时序候选，保留原始观测和站点信息。。本轮读取Clynie公开副本README，原kaka0910入口前序404；作者认可发布与完整许可尚需确认。

**当前验收状态：** 下载路线已登记；本轮未取回数据归档、未解码、未验证CCI连通性、未准入benchmark。

### D54｜CLLMate

**覆盖与角色：** 多类天气与气候事件；结构化事件JSON；气象栅格需另取。

**规模口径：** 本轮data/dataset_cllmate.json为1,825,400 bytes；新闻原文/完整栅格不等于包含在此文件。

**下载入口（类型不能混同）：**

| 入口 | 类型 | 核查边界 |
|---|---|---|
|[作者说明](https://github.com/hobolee/CLLMate)|`code`|本轮README明确结构化文件及ERA5另取|
|[公开JSON直链](https://raw.githubusercontent.com/hobolee/CLLMate/main/data/dataset_cllmate.json)|`http_file`|本轮contents API确认文件名、大小和blobSHA|
|[当前目录元信息](https://api.github.com/repos/hobolee/CLLMate/contents/data)|`github_contents`|官方/作者页面已列出；本次未下载文件|

**Codex最小动作：**

1. 先解析main→commit，再下载固定commit的数据JSON；json.load统计真实事件键和缺少字段。
2. 原始新闻和ERA5并非一起打包：按JSON对应时空取ERA5只作受控/回溯资料，新闻权限单列。
3. 不要沿用“完全没有公开数据”的旧结论，也不要升级成“原文和全部模态均已开放”。

**可复用与适配边界：** 核验event/time/location/coordinate/news_id/image_path，作为跨灾种事件候选和对齐参考。。新闻原始获取/再分发仍需许可；自动提取caused by/cause等不是已验证因果Gold。

**当前验收状态：** 下载路线已登记；本轮未取回数据归档、未解码、未验证CCI连通性、未准入benchmark。

## 10. 必交报告与验收测试

最终报告必须能直接回答：“每一类有哪些资源、哪几个能在本机获得、真正有多少去重事件、哪些材料还缺、下载多少字节才能弥补缺口”。不要只贴README列表和总下载容量。

### source_access_report.jsonl

每项保存主路线及备用路线、实际HTTP/API状态、解析到的完整版本、需要账户/许可与否、样例下载/解码状态、失败证据路径、下一条可执行动作。对xBD/EM-DAT/M4Fog等需要额外访问步骤的资源明确阻塞点，不给假直链。CLLMate公开JSON已定位，原新闻仍另记unknown_access；两个结论同时保留。

### hazard_coverage.csv

至少含hazard_id、细类、来源、候选事件族数、已取回事件族数、样例检查数、各能力准入数、实际观测时间步、文本/图像/栅格/矢量量、准入规则版本、拒收原因和清单是否完整。3050配额可另列target，但不能填充verified列。

### DATA_READINESS_REVIEW_CN.md

正文按16类输出“已确认、条件可用、未落实”三层；同时给来源层、事件层、模态层和任务层矩阵。用真实证据区分原生资料与派生产品/标签。列出最大的重复来源簇、许可限制、地理偏差、历史可见性缺口、包体积与解压体积。最后给出下一批明确文件/事件白名单及字节预算，而不是再提出一个没有链接的泛化计划。

### 最低自动验收

| 测试 | 应有结果 |
|---|---|
| HTML登录页伪装成ZIP、API返回error | fetched_valid=false，不能解包或记为样例成功 |
| 下载中断、Content-Length不符、checksum不符 | 失败/部分保留，不进入正式对象和样本数 |
| 同URL内容更新 | 新快照，旧哈希和文件保持原样 |
| 目录还有next、达到样例上限 | catalog_partial，数字是当前下界而非全库总量 |
| 累计下载达到额度 | 后续转over_budget；不自动增额或删除其他文件 |
| 同一事件不同瓦片/港口/传感器/派生产品 | 各资产可计数，独立事件不重复 |
| 空结果/无效像素/云遮挡 | 不转换成“无灾害” |
| 只有两个真实观测时刻 | 只登记两时相，不造五轮自然序列 |
| 观测时刻不同但内容不同 | 标physical_evolution，不能自动标same_target_revision |
| history_available为空 | strict_as_of不可准入，controlled/retrospective可单列 |
| 标签带答案，或渲染标题/文件名暴露答案 | 私有隔离/公共投影去除；保留真实原始文件作为私有来源 |
| 读取旧heldout样本进行调参 | split_guard阻止并记录；不得重新命名冒充开发集 |
| ZIP/TAR包含越界路径、符号链接或pickle执行 | 拒绝/隔离，不在主环境运行 |
| GEE/论文集合列表有ID但AOI无有效观测 | 记录局部不可用，不能声称有一份最新观测 |

## 11. 数据阶段完成后的选择，不在本轮提前执行

若某来源样例可解码但事件身份缺失，先保留为感知资料，不进入跨事件统计。若时间可用性不明，保留为回溯或受控轨。若原生图文已包含全部答案，后续应做文字消融，但本轮不借此调用模型筛数据。若一个灾种只有弱标签代理，明确参考类型，不承诺动态核心达到配额。

当DF07报告完成，再决定正式数据规模、核心任务和模型实验。应优先选“新独立事件增益大、参考可靠、时空语义完整”的来源；不是一味选最大归档或追求最低模型分数。来源目录可以继续增加，但新条目必须提供同等详细的真实下载路径、版本和访问状态。

## 12. 本次文件本身的验证边界

配套脚本的dry-run、参数拒绝和模拟响应测试在本地执行；不代表云服务真实联通。网页、README、文件清单的核验与数据包下载是两种不同证据。`validation_report.json`记录本次实际检查的范围；没有在用户CCI、GEE项目或完整DisasterTrace代码上运行这些数据任务。

本计划只新增交付文件，不修改之前任何计划、冻结结果和GitHub仓库。它首先要解决的是数据库存与适配性，后续方案以实际验收报告为准。
