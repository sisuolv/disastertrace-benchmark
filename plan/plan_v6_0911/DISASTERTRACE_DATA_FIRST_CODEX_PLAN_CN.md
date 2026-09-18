# DisasterTrace：数据优先的覆盖扩容与可用性核查计划

**交给 Codex 的执行规格｜2026-09-10｜v1.0**  
**当前目标：先确定数据，而不是先训练模型、扩写问题、追加 GPU 实验或重做整个 benchmark。**

> 对已有本地资料、开源 benchmark 的整理结果，以及官方原始数据进行统一核查，尽可能扩大实际可用的灾种、独立事件与多模态资产；最终交付可以追溯到清单、文件和程序输出的数据库存、任务适配矩阵与下一轮获取清单。
>
> 必须回答：“哪些可以直接用？哪些补少量信息可用？各有多少已经证实的资料？还差什么？扩大一批资料需要下载多少、处理什么、获得什么权限？”

本文件可以单独交给 Codex；末尾包含 54 项初始候选的入口。完整包另附 `specs/source_registry.seed.json`、16 类覆盖矩阵、未授权的执行范围模板及此前材料副本。**54 是合并旧清单后的登记项数，不是独立上游观测源数量，也不是扩容上限。**

本轮完成的是计划编制、前序文件读取、最新仓库入口与部分公开文档核对；没有批量下载数据、解码候选样例、执行认证 GEE 查询或运行模型。所有新资源的实测数量仍由 Codex 在实际环境中验证。附录继承的数量只能标为 `reported`，不能填入 `verified`。

---

## 0. 给 Codex 的首要指令

你正在为 `sisuolv/disastertrace-benchmark` 做**数据可行性审计与扩容准备**。请实际检查代码、来源目录、下载流程、最小样例和可重算计数；不要只把本文改写成另一份计划。

按以下优先顺序执行：

1. **广覆盖登记**：所有 16 类灾种和全部候选源先有记录；不要因为气旋、洪水容易，就不检查沙尘、冬季天气、干旱、浓雾和沿岸灾害。
2. **复用优先**：先盘点本地已经取得的资料，再复用开源 benchmark 的目录、加载器、配准和标签；仅在实际缺口上补官方原始资料。
3. **实证优先**：网页可读、目录可列举、文件取回、文件可解码、事件可识别、指定任务可构建，是不同验收层次。
4. **新增有效信息优先**：优先新增独立事件、缺失灾种、缺失地区/季节和缺失模态；不要仅增加已有场景的裁剪和问法。
5. **先数据后模型**：此阶段不训练、不调用 LLM/VLM、不生成大批 QA、不运行论文排行榜、不启动主动 Agent 实验。少量确定性查询仅用于验证数据能否支持后续任务。

遇到单个来源访问、许可、预算或网络阻塞，只标记并隔离该来源；继续其余数据和离线实现。不用未经核验的替代 URL、镜像或假定标签填补结果。

### 0.1 本轮必须返回的六项结果

- `SOURCE_FEASIBILITY.md`：逐来源的实证等级、真实入口、许可、版本、大小、解码和适配结论。
- `HAZARD_COVERAGE.md`：16 类分别有哪些主来源、备用来源、已验证资产、事件和缺口。
- `DATA_COUNTS.json`：公布量、枚举量、取回量、解码量、事件族与各任务合格量，全部带口径。
- `BENCHMARK_RAW_LINKS.jsonl`：开源 benchmark 样本与原始事件/产品的对齐及派生关系。
- `REUSE_AND_GAPS.md`：当前仓库可复用接口、真正需要增加的小模块、仍不支持的语义。
- `NEXT_ACQUISITION_MANIFEST.json`：下一轮具体文件/事件/切片、边际收益、实际或估算字节、解压空间、权限和成本边界。

这六份报告必须来自结构化清单和程序统计，而不是手工写一张看似完整的表。详情见第 14 节。

---

## 1. 先读最新工作区：不要沿用已经过期的工程判断

### 1.1 本计划的仓库锚点

本次读取远端：

```text
repository: sisuolv/disastertrace-benchmark
next-phase-v1: a8ea30d6fd35e5889f5f846ee9f49c87480cf96d
main: a23f73adadcbec077b9fcf2aecf8f45dfa4fe061
previous audit anchor: 36082c42a93e11f67d274d8000c87cd1dc098d74
```

**重要更新：**当前远端已有 `src/disastertrace/multimodal_v1/`。阶段文档记录了 Francine 图文种子、受控交付分支，以及 MM-3/MM-4 的真实模型诊断。旧报告“尚无真实多模态实现”的判断不再作为当前事实。[R1–R3]

本次读取的 `multimodal_v1/types.py` 已有 `FactKey`、`ArtifactMeta`、`DeliveryEvent`、`QuerySpec`、`TransitionObligation`，并允许 `historical_available_at=None`。但 `FactKey` 仍有 `threshold_kt` 等气旋种子语义，不能直接改名后装入所有灾种。[R4]

因此：**检查后复用，不机械新增一套 `data_v2`、`online` 或 `multimodal_v2`。**在新命名空间写审计/桥接代码，冻结源码不做原地变更。此前旧 scaffold 的问题是回归检查清单，不是对新 MM 模块仍有同样问题的结论。[A1]

### 1.2 DA00 必查文件与状态

先定位真实工作区，不假定当前目录；记录分支、HEAD、未提交改动、适用的全部 `AGENTS.md`。禁止为了匹配上述锚点而执行 reset/checkout 覆盖用户工作。

优先阅读实际存在的：

```text
AGENTS.md（从工作区上层至被修改目录）
disastertrace-starter/CURRENT_PHASE.md
disastertrace-starter/README_MULTIMODAL_V1.md
disastertrace-starter/README_MM4_ATOMIC_V1.md
src/disastertrace/multimodal_v1/types.py
src/disastertrace/multimodal_v1/acquire.py
src/disastertrace/multimodal_v1/build.py
src/disastertrace/multimodal_v1/geometry_reference.py
src/disastertrace/multimodal_v1/rendering.py
src/disastertrace/multimodal_v1/storage.py
src/disastertrace/forecast_source/
src/disastertrace/forecast_task/
configs/nhc_cohort_v1.json
相关 source manifest、admission、冻结清单及已有数据目录
```

如路径变化，先定位再记录映射；文件缺失不等于功能不存在。新的源数据检查不要启动 MM-5A、旧 GPU worker、作者训练入口或历史收集器。

输出 `REPO_DATA_BASELINE.json`：现有事件、快照、资产角色、接口、范围限制、复用方式、实际核查范围；不要只统计代码文件数。

### 1.3 不可变性、测试集与环境

- 原始文件、旧 Gold、评分器、回答、失败、冻结包和已消耗任务身份保持不变；不 push、不改仓库公开性。
- 从现有配置和保护清单取全部 heldout 标识的并集；也保护其关联原始影像、复合事件及派生标签。目录中能看到其 ID 不表示允许打开其隐藏答案用于开发。
- 下载前先按事件/产品 ID 过滤。无法判定是否关联旧 heldout 的条目进入 `PENDING_SPLIT_CHECK`，不得用来调解析器、阈值或任务设计。
- 外部数据原始 split 要保留；本项目未来 split 单独建立。优先用外部 train/development 样例测试读写，不把已检查过的例子重新叫隐藏测试集。
- 本计划不重新授权已经结束的 GPU/云任务窗口。新获取使用独立 scope；CPU 离线检查与有费用任务严格分开。
- 若使用 CCI，先确认真实持久卷与剩余空间。`/mnt/afs/260010168` 只是既有环境线索，不得未经检查就扫描/下载到该路径；不要递归扫描整个人工智能平台、HOME 凭据目录或其他用户目录。

---

## 2. “尽可能多”应如何执行

### 2.1 使用两层资料库，不用最严格条件淘汰全部数据

**Broad Data Bank：**许可允许、资产可解码、时空和来源可追踪的广域资料，保留静态、双时相、连续和单模态数据。

**Task-ready subsets：**从 Broad 中标记分别可支持地图阅读、多模态、真实演化、同目标修订、严格 as-of 和未来预测的子集。一个样本可以属于多个子集，不能把它们相加作为独立总量。

资料不能做同目标修订，不代表它没有价值；它可能适合感知、空间范围、物理演化或后期参考。没有标签也可作为背景或事件索引，不应伪装成可评分输入。

### 2.2 优先级规则

使用可解释的顺序，不造一个未经校准的“数据质量总分”：

1. 先让每一灾种得到至少一条被检查的主路线和一条独立或互补的备用路线。
2. 优先新增尚未覆盖的灾种/地区/时间阶段/证据类型。
3. 在此基础上优先新增去重事件族和真实时间点，而非相同事件瓦片。
4. 同等增益下优先合法易取、小规模可读、已有精细元数据与标签的来源。
5. 大而重复的数据不删除，但降至批量扩容层，不抢占第一轮核查预算。

旧 3,050 配额仅保留为 `legacy_target`，不设置“必须凑够才通过”。不能用静态样本、空间瓦片或受控分支凑独立事件数。核查完成后用事实替换配额承诺。

### 2.3 覆盖矩阵：每类都必须有结论

| 灾种 | 优先借鉴的 benchmark / 整理数据 | 原始或官方补充路线 | 本轮必须确认 | 旧目标（仅参考） |
|---|---|---|---|---:|
| H01 热带气旋 | CyPortQA、ExEBench 气旋、Digital Typhoon V2、TCIR、EWB | NHC 公告/GIS、IBTrACS、相应卫星档案 | 独立风暴 ID、最佳路径与历史预报区别、图文时间与阶段 | 400 |
| H02 温带风暴/非对流大风 | EWB 相关案例及观测适配器 | Storm Events、ISD、GHCN、GFS/ERA5 | 风速指标、持续/阵风、非对流类别依据；缺少气旋追踪不得自动叫温带气旋 | 150 |
| H03 雷暴风/下击暴流 | WeatherQA、SEVIR、EWB-LSR | SPC/Storm Events、MRMS、NEXRAD | 风害报告与雷达配对；泛 storm 标签不能替代下击暴流确认 | 150 |
| H04 龙卷风 | TorNet、WeatherQA、EWB-LSR | SPC/Storm Events、NEXRAD | 修订后的事件 ID、起止时间、正例与困难负例 | 150 |
| H05 冰雹 | WeatherQA、EWB-LSR/PPH、SEVIR相关样本 | 冰雹报告、MRMS/NEXRAD | 地面冰雹大小/发生报告与雷达估计分开；PPH不是独立报告 | 100 |
| H06 强雷电 | SEVIR、可关联强对流图文 | GOES GLM、事件报告 | flash/group/event计数口径，空间时间密度的极端定义 | 100 |
| H07 极端降水 | ExEBench、SEVIR、EWB相关案例 | IMERG、GHCN、MRMS、CHIRPS | 降水率/累计量、时间窗、单位与极端标准 | 250 |
| H08 洪水/山洪/城市内涝 | GFD、GEOID、WorldFloods、UrbanSAR、KuroSiwo、Sen1Floods11、SpaceNet8、FloodNet | CEMS、S1/S2、降水、水文记录 | 事件族、有效覆盖、永久水体、现象与成因；淹水不自动等于道路关闭 | 400 |
| H09 风暴潮/沿海淹没 | EWB/NHC事件作为索引，不自动具备潮位标签 | CO-OPS 观测+预测潮、NHC、CEMS | 同基准面/站点/窗口；总水位与风暴增水不同 | 100 |
| H10 热浪 | ExEBench、EWB | GHCN、ERA5/ERA5-Land、GFS、MODIS LST | 连续过程、当地季节基准；LST不等于2米气温 | 250 |
| H11 寒潮/低温/霜冻 | ExEBench、EWB | GHCN、ISD、ERA5-Land、GFS | 低温、骤降、霜冻细类与标准，缺测规则 | 150 |
| H12 暴雪/冰冻/冻雨 | WeatherQA冬季入口须实查 | Storm Events、GHCN、ISD、MODIS Snow、GFS | 分开雪盖、降雪、冻雨和道路影响；不可用雪图包办全部细类 | 200 |
| H13 干旱/闪旱 | DroughtED、USDM | CHIRPS、SMAP、ERA5-Land、站点 | 周期/县域/过程区别；闪旱另有快速恶化定义 | 150 |
| H14 沙尘 | 先核查专项公开论文数据；无成熟包也要报告 | MERRA-2尘埃变量、S5P、ISD现象码/能见度 | 沙尘与烟尘区分、地面支持；只高AOD不足以确认沙尘暴 | 100 |
| H15 浓雾/极端低能见度 | M4Fog条件候选 | ISD现象码、能见度、湿度及相应卫星产品 | 海雾/陆雾/低能见度单列；不能仅用低能见度推断雾 | 100 |
| H16 野火及相关火险 | WildfireSpreadTS、Next Day、TS-SatFire、Sen2Fire、ExEBench火灾 | FIRMS、MTBS、CEMS、S1/S2 | 热点/活动火/火场边界/烧痕/火险分开，天气相关不等于自然起火 | 300 |

细类覆盖要单独列出，不能因为 H12 有雪盖数据就填“冻雨已满足”。海洋热浪、降雨滑坡另列扩展；大气河可作为极端降水成因标签。地震、火山和海啸不得计入极端天气覆盖。表中路线是待检查的候选，不是兼容性或配额保证。

### 2.4 补源不能无边界，也不能碰到困难就放弃

每类若缺少可行主路线，增加至少一轮有界补充检索：优先论文作者仓库、数据 DOI、官方目录和现有 benchmark 的上游来源；记录最多 3 个新增候选、选择理由与发现日期。没有合适结果就报告该轮缺口，不编造来源。

优先检索能提升非美国事件覆盖的全球/区域数据，保存国家、海域和季节分布；“16 类均有美国样本”不能称为全球均衡覆盖。可将新来源登记为 D55 起，不重编号旧来源，不重复登记同源镜像。

---

## 3. 开源 benchmark 与原始数据怎样组合

### 3.1 三条并行路线

- **B 路线：已整理 benchmark。**继承原始样本、事件目录、时空配准、读取器、已有标签；不运行作者训练/推理脚本，也不自动继承开放式评分。
- **R 路线：原始产品。**为 B 缺失的时间、模态、地面证据或新事件补资料；保存它与 B 的来源对应关系。
- **L 路线：本地已有资料。**优先核验 NHC 和新 MM 种子的实际 manifest；不重新获取覆盖旧文件，不重复下载已经拥有且哈希正确的资产。

首先建立 `benchmark sample → upstream event → upstream product/version → physical assets` 的映射。相同事件的多模态联合会提高资料完整性，但不增加独立事件数。

### 3.2 重点复用任务卡

下列事实仅来自文档/目录核查，不是下载验收。链接见 [S1–S10] 和完整来源表。各卡的“检查”是待 Codex 执行的工作。

#### D47 ExEBench / EarthExtreme-Bench

- 入口：作者仓库与 HF 数据页；按灾种拆分 ZIP，可参考其加载器。[S1]
- 检查 `coldwave / heatwave / expcp / tropicalCyclone / storm / fire / flood` 实际清单、变量和上游来源；子包作为 child resource，不重复算七个独立物理源。
- 列举与下载必须锁定同一个 HF commit。旧核查记录过目录使用 stable、下载未传同一 revision 的风险：本轮检查所用脚本是否仍如此，不直接复制旧结论。[A2]
- 先选择预算内的一个小包或独立文件。不能因 README 提供 `train_and_evaluate` 就运行它。
- 解析真实序列/事件 ID、时刻/坐标、输入与标签；7 类名称不代表 7 类都满足同样的动态任务。
- 输出：各子包数量口径与事件恢复率；缺原始事件 ID 时标未完成，不按帧数推算。

#### D48 ExtremeWeatherBench（EWB，与 ExEBench 分开）

- 借用事件配置、Zarr/Parquet/CSV 与数据适配器；其预测与参考分层值得复用。[S2]
- `ERA5`、`GHCN`、`LSR`、`PPH`、`IBTrACS` 分别登记产品；PPH 与 LSR 记录派生依赖。
- EWB 的 GHCN 小时数据与 D26 的 GHCN-Daily 不是同一个产品，单位转换也不能默认继承正确。
- 检查当前文档端点和实际代码版本；先变量、时间、空间子集，再触发有界读取；元数据请求也记实际流量。
- Zarr/Parquet 为 lazy 不等于零流量或永远只读几 KB；云 chunk 大小可能决定最低获取成本。
- 只用读取能力，不执行 `EvaluationObject` 的模型评测；冻存切片后离线复读。

#### D49 WeatherQA

- 作者页提供参数图与 SPC 讨论以及处理版入口。[S3]
- 读取一组真实讨论与匹配图；20 个参数图不当作 20 个观测时刻。
- 优先恢复原始 discussion ID、日期、图像时间、参数、来源 URL；自动模板问题与专家原文分开。
- 已有 MCQ 的答案、CoT、解释与预处理标注作为 reference，不能自动作为模型公开证据。
- 可寻找同一过程的相邻讨论，但没有实际关联依据就不拼成连续风暴；风险讨论不是灾害发生真值。
- 记录 GIF 的帧数/动画语义；不要把所有 GIF 动画帧都解释成物理时间序列。

#### D50 CyPortQA + D01 本地 NHC / MM

- 先检查本地已有索引和原始图文，再访问作者仓库；复用场景身份、NHC/USCG 来源索引。[A2]
- 气旋—港口组合、QA 数和风暴数分开；同一公告在不同场景复用时只计一个底层产品。
- 保留原文、官方 GIS、官方数据重渲染、benchmark 规则四种来源角色；港口核查规则不升级为真实关闭/撤离真值。
- 检查当前 MM `ArtifactMeta/FactKey/DeliveryEvent` 能承接哪些来源；不重新修复已经在新版本解决的旧 scaffold 问题。

#### D12 GEOID-Flood

- 作者支持目录预览、分模态获取与样例包；全量和样例都需独立预算，不能因名字为 sample 就默认小。[S4]
- 先读 tile/event/AOI catalog；区分原始 1024 瓦片、训练滑动小 chip、激活、物理事件和实际准入样本。
- 优先独立 COG 或最小合法分片。不存在单文件入口就如实报最小归档大小，不虚构单瓦片下载能力。
- `floodmask/permwater/label` 是参考/派生标签；由标签边界构成的 validity 不能自动当成公开传感器 QA。
- 灾前 S2 与灾前后 SAR 时间分开；GRD/RTC 记录同源处理，不能算作两个独立观测。
- 按冻结版 catalog 实查同激活/事件/AOI split；文档描述和旧样例观察不同则记录差异，不直接宣称原论文泄漏。[A2,S4]
- 不运行示例中的 `terratorch fit/test`；只解码资产、几何与标签。

#### D51 WorldFloods / ml4floods

- 选择并固定 v2 或指定版本；先查 HF/作者发布路线，再决定是否获取；旧 requester-pays 路线不得自动使用。[S5]
- 配对 S2、clear/cloud 与 land/water 标签，保留质量与标签的原始含义。
- 非商业条款、派生产品和允许再分发范围独立记录；研究可用不等于商业可用。
- 509 类似配对数不当事件数；按 CEMS/影像 ID 与其他洪水数据核对重叠。

#### D19 WildfireSpreadTS

- 作者记录提供逐日事件序列与公开 ZIP；完整归档较大。[S6]
- 先盘点本地是否已有完整/部分资料，查作者事件/日期 manifest；大单 ZIP 不默认整包取回。
- 若 HTTP Range 与 ZIP 结构允许，可在预算内读取中央目录和指定 member；否则生成整包方案，不边读边无限下载。
- 保存观测日期、通道、nodata、火情参考来源；避免未来日信息进入当前样本。
- 每日物理演化不自动成为官方修订；GeoTIFF→HDF5 转换可后置，不能为了读一张图复制整个库。

#### D06 SEVIR + D07 TorNet

- SEVIR：先 CATALOG、事件键、传感器、文件/内部索引，再决定需要哪个 HDF5 分片；整块文件中的记录和独立事件分开。[A2]
- TorNet：先 catalog、版本说明、event/episode ID、真实起止时间、正负样本；核对作者已发布修正，不盲用旧 v1。[S7]
- 只安装必要读取依赖，不下载模型或执行训练；不为了预览雷达样例自动安装整套深度学习栈。
- generic storm、不含龙卷的强对流、冰雹/风报告不互相替代；对不同标签对象分别核查。

#### D03 Digital Typhoon V2 + D04 TCIR

- 固定数据发布版，记录序列/帧数；优先从作者目录恢复风暴 ID，映射 IBTrACS/地区编号。[A3]
- 不把 V1 与 V2 计数相加；检查四通道维度、缺失、原始分辨率和可视化方式。
- 最佳路径/插值标签写入参考；不得声明等同历史实时业务预报。
- 对跨海盆、跨年份增加的独立事件另计净增益。

#### D52 DroughtED + D31 USDM

- DroughtED 作者论文与发布入口可作为对齐参考；先核验真实文件、认证、county/FIPS、日期、气象特征和目标字段。[S10,A2]
- 与原始 USDM 等级/地图配对时保存来源日期和发布/有效边界；县—周行和滑窗数不当独立干旱过程。
- 普通干旱与闪旱分开；无需有新样本就制造闪旱标签。
- 元数据/站点时间序列能起步不代表原生图文或历史修订链已具备。

#### D53 M4Fog + D27 ISD；D35/D36 沙尘路线

- M4Fog 保留条件候选；从论文/作者认可发布链确认入口，副本、网盘和许可证分别核验。不能因旧入口失败断言数据消失，也不能因有镜像断言可合法获取。[A2]
- ISD 检查能见度、现象码、温湿度与报告时刻；海雾、陆雾、烟尘低能见度分别标记。
- 沙尘使用 dust-specific 变量及地面现象支持，S5P 的高气溶胶指数不能单独确认沙尘暴。
- 两条长尾路线必须返回至少“已查什么、缺什么、可做哪个层级”的结论，不能在报告中省略。

#### D54 CLLMate（条件候选，不默认原文全开放）

- 先核验实际发布的数据卡、文件和原始新闻许可；此前论文资料涉及采购新闻，不将论文样本量写成免费可再分发库存。[A2]
- 可以借鉴时地对齐方法，不能把 LLM 生成标签自动升级为本项目 Gold。
- 无法取得原文时记录为方法参考/受限数据，不用生成新闻替代。

### 3.3 Benchmark—原始数据桥接的最小产物

每个优先 benchmark 至少生成一条实证关系（已取得权限和资料时）：

```text
benchmark_release + sample_id
  → upstream_event_id / candidate_event_family
  → product_id + version + observation/valid interval
  → acquired asset checksum
  → metadata/label/geometry checks
  → supported task capabilities + missing requirements
```

没有恢复出原始 ID 时，用可追溯的 local ID 保留样例并标 `upstream_link_unresolved`，不要用猜测链接补齐。

---

## 4. 官方原始数据专项检查

| 原始路线 | 借用入口 | 必查项与输出 |
|---|---|---|
| NOAA Storm Events | D05；官方年度 CSV [S8] | 固定文件版本；流式读 detail 表；location/fatality 只做关联，不相加为事件；逐类原始条目及事件组计数；过程去重规则另列 |
| 全球气旋 | D02 IBTrACS；D01 NHC | 多机构/多时刻按明确风暴键聚合；字段单位、最佳路径版本、资料可用时间；受保护风暴隔离 |
| 全球灾害目录 | D39/D40/D41/D18 | 目录条目不是精确灾情边界；灾种分类、分页、事件关联、CEMS激活/AOI/产品区别；缺收录不作为负例 |
| 气温与冬季天气 | D25/D26/D27/D28/D33/D34 | 站点/网格、QA、时区、气温/LST、雪盖/雪深/降雪、发行与有效时刻；保存可提取事件的变量清单 |
| 降水与干旱 | D29/D30/D31/D32 | precipitation rate/accumulation、窗口、产品修订、永久/临时标签、CHIRPS-IMERG等派生依赖；USDM周地图不硬称同周纠错 |
| 火情 | D23/D24，必要时CEMS/S1/S2 | 火点检测、事件聚类、烧毁范围、天气相关指标各自字段；晚期烧痕/MTBS不进入过去输入 |
| 沿海 | D37 | 观测与预测潮日期、同一基准面、站点/区域对应、verified/preliminary状态；total water与surge残差分开 |
| 遥感背景 | D42/D43及地形等 | 轨道/极化/波段/处理版本、CRS、质量、覆盖、真实重访；原始数据存在不等于 benchmark 标签存在 |

### 4.1 连续数据的事件提取只做小型可行性验证

当前不构建全球高分辨率灾害检测器。先挑选有地理/季节代表性的、范围可控的区域或站点，验证以下流程能否运行：

1. 固定观测变量、单位、空间支持和时间窗；明确是观测、再分析还是预报。
2. 引用公开定义，或显式命名“研究定义”；写明阈值、基准期、持续长度与缺测规则。
3. 使用预先固定的历史/开发基准；不能用待测事件之后的数据重新拟合它自己的阈值。
4. 计算尾随窗口，合并相邻时空片段；中心窗口只允许作为明确的事后参考。
5. 保存事件资格与原始产品关系；加入季节/地区匹配的正常、近阈值、缺测样本。
6. 报告实际窗口数、过程候选数、合并规则和有有效观测的比例；不外推为全国/全球事件总量。

热浪、寒潮、干旱/闪旱不能统一成一个未经定义的分位数任务；若定义待定，先只报告数据可用性，不执行正式事件归类。


## 5. 可用性不是一个开关：分别记录访问、解码和任务能力

### 5.1 五条独立状态轴

每个来源及抽样资产都要记录状态，不能一个 `available=true` 代表全部：

| 维度 | 建议状态 |
|---|---|
| access | `unprobed / docs_only / catalog_partial / catalog_complete / fetched / blocked_auth / blocked_network / blocked_budget / unavailable_endpoint` |
| content | `not_inspected / decoded / corrupt / unsupported_format / missing_component` |
| provenance | `unresolved / partial / linked / version_frozen` |
| license | `unknown / research_allowed / restricted / redistribution_allowed / redistribution_blocked`；具体条款另存 |
| task eligibility | 每个 capability 分别为 `verified / metadata_candidate / unsupported / blocked / not_checked` |

`catalog_complete` 只能针对固定的源版本、查询范围及截止时间成立。不能把所有可翻页目录都默认完整，也不能把 `not_checked` 写成 `unsupported`。

### 5.2 数据能力标签（不是互斥等级）

| 标签 | 数据满足什么 | 不能据此声称什么 |
|---|---|---|
| C0 discovery/background | 有可追溯的事件索引、背景或候选资料 | 不能当像素/精确时间真值 |
| C1 perception/spatial | 可读影像或地图，具备明确对象与可执行参考 | 不代表有多期或原生图文 |
| C2 multimodal | 至少两种信息表示/传感器可对齐，记录具体模态 | 多波段不自动等于原生图文；冗余转写不是新独立源 |
| C3 natural_temporal | 至少两次真实不同观测/有效时刻，知道区域与时间含义 | 物理演化不等于同目标纠错 |
| C4 same_target_revision | 同对象/变量/空间支持/有效目标的多个版本，可判权威关系 | 单纯发布日期晚不自动替代旧时刻 |
| C5 controlled_replay | 能用真实材料编制显式受控交付并生成分支参考 | 不宣称这是历史真实到达顺序 |
| C6 asof_reconstructable | 有可信可得边界或可靠前瞻日志，可审查信息截止 | 今天获取旧数据不证明历史可见 |
| C7 forecast_pair | 有合法前缀与未来独立结果、统一变量和时空目标 | 不声称本轮已运行预测模型 |

C2 至少继续分开 `native_text_image / numeric_image / multi_sensor / official_data_rendered / redundant_representation`。在数据阶段可以证实配对与潜在任务可解性；**没有结构性的反事实/成对可识别性或后续实验，不声称“已经证明视觉必需”。**

当前阶段对 C5/C7 只做数据资格和一两个确定性 witness，不启动完整回放模型或预测实验。C6 可以为空，不妨碍其他能力子集的建立。

### 5.3 输入、质量与参考的角色核查

每个字段/资产标记 `public_candidate / reference_only / quality / metadata / background / benchmark_rule`。

- 同一张发布的分类图可用于地图阅读；但其标签不能作为原始影像识别任务的辅助输入。
- 无效/云/观测空洞和没有灾害分开；由标签生成的有效范围不能伪装成独立传感器 QA。
- 观测、预报、再分析、最佳路径、算法估计、人工参考分别登记。
- 统计口径/阈值/空间支持不同时，不自动判为冲突或互相替代。
- 新闻事件未报道、站点无报告、遥感没有火点均不自动等于“无灾害”。

---

## 6. 数量怎么核实：让旧配额变成有证据的库存

### 6.1 每个数字必须有单位、范围与证据

每项 CountRecord 至少保存：

```json
{
  "source_id": "D47",
  "child_resource": "heatwave",
  "metric": "sequence_count",
  "value": null,
  "unit": "source_defined_sequence",
  "basis": "not_measured",
  "source_revision": null,
  "scope": {"time_start": null, "time_end": null, "region": null, "filters": {}},
  "enumeration_complete": false,
  "evidence_path": null,
  "counting_code_commit": null,
  "notes": "示意模板；null不是0；不得把此前论文数字自动放入实测计数"
}
```

`basis` 允许 `reported / catalog_measured / acquired_measured / decoded_measured / task_verified / estimated / not_measured`。

分别报告：

```text
source_reported_units             作者/目录原样声明及其单位
catalog_records                  实際枚举的记录
catalog_unique_source_events      源内事件ID去重
acquired_assets                  实际取回、校验的资产
decoded_assets                   通过指定读取器的资产
linked_event_families             按已公布规则关联的事件族
unresolved_event_candidates       仍无法可靠关联的候选
task_verified_event_families      某一指定能力下完整验证的事件族
task_verified_episode_candidates  按预定义构造规则通过的过程候选
frames / tiles / sites / timesteps 其他单位独立列
bytes_transferred / disk_peak     网络与本地成本
```

源自己的 `episode` 统一加前缀（如 `tornet_episode_id`），不与 DisasterTrace episode 混用。

### 6.2 不允许的统计

- 不把站点数、帧数、瓦片数、QA 数或不同产品数相加为事件数。
- 不把 54 项候选、ExEBench 的七个子包与其底层数据都计作彼此独立数据源。
- 不把“同一天”的所有灾害合成一个事件，也不把跨国同一气旋拆成多个独立风暴。
- 没有 event ID 不用 `len(files)` 代替；没有完整分页不报告 definitive total。
- 不能因为一个样例成功，就把论文全部样本写成 `task_verified`。
- 文件大小的 GB/GiB、压缩体积、解压体积、网络实际字节、工作空间和重复格式副本分开。

### 6.3 分层去重与不确定匹配

建立三个不同关系层，避免一个全球 ERA5 数据库把所有事件连成一团：

1. **物理事件关系图**：已知风暴/激活/报告身份、灾害因果或相同过程依据；关联依据和置信度可审计。
2. **资产复用索引**：文件 SHA、提供方 product/version、场景 ID、实际时空切片；同场景的多个裁剪记录共享父资产。
3. **来源依赖图**：重渲染、重采样、同源传感器、同一分析/标注产品的派生关系。只共享“ERA5产品家族”不等于同一物理事件或同一原始切片。

事件匹配分 `confirmed / probable / unresolved`。只按名称或大范围时空重合不能直接自动合并为 confirmed。报告匹配敏感性与未解决候选，不强迫造一个唯一精确总数。

优先检查：

- Digital Typhoon / TCIR / ExEBench / NHC / IBTrACS 的同气旋重叠；
- GEOID / WorldFloods / KuroSiwo / UrbanSAR / GFD 的同洪水及同 S1/S2 场景；
- 气旋及其洪水/风暴潮的复合事件关系；
- WildfireSpreadTS / TS-SatFire / FIRMS / MTBS 的同火情过程；
- ExEBench 与原始上游集合的包含关系；WeatherQA 的同讨论/同小时多个参数图。

未来数据划分至少以明确的事件族和实际共享资产为界。此阶段生成 `split_risk_report`，不要改写原数据集划分或宣称全世界不存在训练污染。

### 6.4 小样本审计不等于全集估计

每个来源先列元数据，按预先记录的 seed 和 strata 选择**最多 3 个非受保护事件族**做可解码烟雾测试；失败/不足三例如实报告。这是起步检查上限，不是最终数据规模上限。

至少对每个灾种尝试一条路线，不能让气旋/洪水把预算用完后仍把其余标成已核查。关键来源完成 smoke 后，再按地区、年份、阶段、质量/缺测、正负类型做最多 20 个事件族的适配性抽查，仍受共同预算约束。

- 样本选取不得使用待测 LLM/VLM 得分，也不挑图片最好看的若干例当代表性样本。
- 作者的小型演示包是便利样本，不能直接外推通过率。
- 若要估计总体任务可用量，先证明完整抽样框和抽样概率，按事件族做分层抽样并报告区间/未知覆盖；否则只给已验证下界和 catalog 候选量，不给拍脑袋通过率。
- 下载/解析失败样本保留在审计抽样分母中，但与气象资格不符分别分类。

---

## 7. Online、预算和下载安全

### 7.1 执行权限与推荐检查档位

**此计划不是新的收费服务授权。**先读取当前任务的实际 scope。没有授权记录时，可以完成本地审计、mock、脚本和 dry-run；公开文档/轻量目录读取依环境现有权限进行。真实资产获取、GEE、requester-pays、批量下载和常驻轮询不能自动开启。

本包的 `execution_scope.template.json` 默认不启用网络取回或云计算。建议以后授权时按下列档位逐级放行；数字只是建议上限，不是用户已经批准的额度：

| 档位 | 建议上限 | 允许做什么 |
|---|---|---|
| metadata | 总网络 100 MiB、单响应 10 MiB、最多 1000 请求、每主机并发≤2 | 文档、许可、版本、catalog/API分页；较大catalog申请独立条目 |
| sample | 单文件 1 GiB、单源 3 GiB、总 10 GiB、解压/派生输出 20 GiB | 小包/COG切片/少量表格，CPU解码与标准化；全局预算原子计费 |
| approved_shard | 按已列出的包/事件/分片逐项授权 | GEOID样例、TorNet年度包或其他超过sample的最低有效单元 |
| cloud_slice | 单独列 project、集合、AOI、变量、日期与服务额度 | GEE受限查询/导出；免费额度也计使用，不运行全球批任务 |

`authorized=false` 不能因为写了建议预算就被脚本自动改为 true。预算不足生成下一轮候选清单并继续其他来源，而不是反复询问使全部工作停住。

### 7.2 下载与解码必须真实可验证

- HTTP 200 可能是登录页/错误 HTML；校验响应头、文件 magic、实际格式和长度。HEAD 失败不等于 GET 不可用，记录各自证据。
- 范围下载必须检查 `206` 和 `Content-Range`；服务器忽略 Range 时立即受限停止，不自动拉全量归档。
- S3/GCS/HF/Zenodo 使用官方客户端或受限 HTTP；冻结 commit/record/object version 与查询截止。`stable/main/latest` 解析后保存具体版本，不只保存别名。
- ZIP/TAR 解包防路径穿越、symlink越界、解压炸弹及超出磁盘额度；单一归档无随机读取能力时承认需要整包。
- `.npy/.npz` 默认禁用 pickle；不执行不受信任数据中的 Python、pickle、shell 或 notebook；不因加载器要求就启用 `trust_remote_code`。
- NetCDF/HDF5/Zarr/GeoTIFF 只用固定的读取路径做只读检查，不隐式运行训练或全量 materialize。
- 保存原始字节哈希与解码/规范化哈希；跨运行允许相同原始blob去重，但每次获取的时间/失败/响应记录保留。
- ETag 不一定是内容哈希；临时签名 URL 不用于公开复现，也不保存其中的凭据。
- 如已授权下载允许重试，次数与原因明确记录，且每次传输计预算；不能隐蔽自动重试到成功。默认至多一次网络重试，不改变抽样事件。

### 7.3 GEE 与非 GEE 两条在线路径

GEE 检查注册项目和权限，仅选择预定集合、AOI、时窗、波段。`filterDate()` 筛 `system:time_start`，不是历史可获得时间。[S9]

IMERG 等源存在替换版本，保存实际取回内容和质量信息；同样的查询脚本之后执行不保证同一字节。[S11]

并行尝试 EWB 的公共 Zarr/Parquet、公开 S3、HF 单文件及官方 API。GEE 认证阻塞不阻塞这些路线；匿名公共 GCS 读取也不能写成“GEE已认证”。在线目录候选和可交付证据是两种对象。

元数据探针完成应得到：固定查询、完整/部分页、最新实际返回时间、目标区域有效覆盖、返回数、失败原因和实际字节。若没有权限执行，只产生 `not_executed` 计划，不能填写模拟成功结果。

本轮不部署 daemon/cron，不承诺未来自动收集。可实现单次增量采集命令和状态持久化测试，实际持续运行另行安排。

---

## 8. 最小数据契约：适配现有代码，不先重写全系统

先读当前 MM 类型与旧 source manifests，编写 `REUSE_AND_GAPS.md`。新 audit record 可以轻量化，不要求现在重写 `ModelCommit`、runner 或 scorer。

### 8.1 至少保留的对象

| 对象 | 必要字段 |
|---|---|
| SourceRecord | id、别名、类型、灾种映射、入口、版本、许可、来源家族、所用加载代码版本 |
| AcquisitionReceipt | scope、真实请求/响应、时间、状态、实际字节、原始hash、错误、重试、完整性 |
| EventCandidate | local/source IDs、event_family候选、hazard及资格依据、区域/时间、原始split、保护状态 |
| AssetRecord | raw/render/quality/reference角色、hash/媒体类型、波段/单位、CRS/grid、nodata/覆盖、派生父资产 |
| SampleQualification | 数据样本ID、检查项结果、各C0–C7状态、证据路径、缺口、来源与代码版本 |
| CountRecord | 数值、单位、basis、scope、冻结版本、完整性和统计脚本 |
| JoinRecord | benchmark_sample、upstream产品/事件、link type、依据、置信度及待定原因 |

### 8.2 时间与角色是不可丢失字段

分别保存观测/有效区间、预报初始化与lead、明确发行时间、有证据的历史availability、本采集器first-seen、获取时间、处理完成时间和未来可用的交付事件。字段不存在可以为 null，不能用相邻时间替代。

同一 source URL 被更新时创建新的 snapshot。`supersedes`、`new_observation`、`derived_from`、`same_underlying_observation` 是不同关系；不能仅用时间先后决定。

原始区域可能是圆锥、风圈、概率阈值、积水图或质量掩膜，记录各自变量和空间支持；不同图形不直接求并集当一个“灾害区”。

### 8.3 数据级标准化检查

- 经纬度与 CRS、坐标轴/经度范围、正负号、单位及 scale/offset 可恢复。
- 栅格网格/分辨率/时间轴可读；分类掩膜重采样与连续变量重采样分开。
- 历史基准、累计窗、阈值/百分位定义可追溯。
- 渲染图保存原始资产、显示参数、投影、裁剪和像素—地理映射；不因生成 PNG 就丢掉数值场。
- 图中缺少可读日期/图例/目标区域会影响对应任务资格，不能用评测侧精确数值要求模型读出图中不存在的精度。
- 公共证据字段不包含答案、标签选区、未来目标值和由私有标注生成的捷径。

---

## 9. 可交付的工作包（仅数据，不包含模型实验）

| 编号 | 依赖 | 主要动作 | 实际交付与验收 |
|---|---|---|---|
| DA00 工作区与权限 | 无 | 核对新HEAD/MM、已有资产/接口、保护清单、预算和持久目录 | REPO_DATA_BASELINE + scope记录；不修改冻结文件 |
| DA01 统一注册与全灾种覆盖 | DA00 | 导入54候选和别名，填16类主备路线；检查重复/新来源 | source_registry + hazard_matrix；每类有路线或明确缺口 |
| DA02 实际目录与许可探针 | DA01 | 版本、文件清单、分页、大小、许可、最小获取单位 | docs/catalog receipts；完整性和权限不混为一谈 |
| DA03 本地只读与小样例读取 | DA00–02 | 复用NHC/MM；有scope时取样、解码不同格式 | acquired/decoded manifests、实际错误日志；mock不算下载成功 |
| DA04 benchmark—原始来源连接 | DA03 | 事件、产品、观测、参考与派生关系对齐 | join records；每条链接有证据/置信度 |
| DA05 16类适配性与长尾补源 | DA02–04 | 主路线抽样；验证可评分能力；必要时最多3候选补源/类 | C0–C7能力矩阵、具体缺口；非核心资料仍保留 |
| DA06 去重、计数、覆盖分布 | DA01–05 | 源内/跨源去重；事件/资产/任务量分开；生成分布 | 可重跑统计；partial/unresolved显式，旧配额不当库存 |
| DA07 扩容与成本清单 | DA02、DA05–06 | 依净增事件/灾种/模态与成本选择下一批 | NEXT_ACQUISITION_MANIFEST；文件级预算和收益依据 |
| DA08 冻结审计与交接 | 所有已执行步骤 | 符合范围的原始日志、样例、代码、报告与hash打包 | 断网可重算已取得内容；无新增模型调用；明确未完成边界 |

DA02 的公开目录工作和 DA03 的本地解码可以并行；GEE阻塞不阻塞其他来源。每完成一个来源立即写结构化结果，不等54项全部完成才交付首张覆盖表。

### 9.1 阶段停止点

- **第一轮**：54项登记完成，16类都有路线/缺口；当前MM/NHC本地盘点；关键公开目录与许可结果；样例任务按实际授权执行。
- **第二轮**：核心来源跨格式解码与事件恢复，长尾逐类最小验证；形成实测量与未知量。
- **第三轮**：按冻结策略抽样估计可用性、检查跨源重叠并生成批量获取清单。

不要把“只写注册表”称为全部验收，也不要因仍有受限来源而否定已经完成的实证结果。

---

## 10. 目录与命令接口建议

以下路径和命令是**待实现/对接接口**，不是声称当前仓库已存在。若已有等价模块，用等价命令并在文档中映射。优先新增轻量审计层，不复制MM研究内核。

```text
src/disastertrace/data_audit/           # 或工作区已有同职责模块
  registry.py
  catalog_probe.py
  sample_readers.py
  event_links.py
  qualification.py
  counts.py
  reporting.py
  cli.py
tests/data_audit/
configs/data_audit/
  sources.json
  hazards.json
  scope.json
work/data_audit/<run_id>/
  run_manifest.json
  repo_baseline.json
  source_registry.json
  receipts/                           # 追加式，失败也记录
  catalogs/                           # 冻结的元数据页/清单
  objects/<sha256>                     # 原始内容，按许可保留
  decoded/                            # 小型标准化样例
  private_reference/                  # 仅评估/核验用途
  qualifications/
  reports/
```

```bash
# 接口示例：实际实现后才执行；--scope/--out 必须显式提供。
python -m disastertrace.data_audit inventory --scope SCOPE.json --out RUN_DIR
python -m disastertrace.data_audit register --seed specs/source_registry.seed.json --out RUN_DIR
python -m disastertrace.data_audit probe --sources all --scope SCOPE.json --out RUN_DIR
python -m disastertrace.data_audit sample --source D47 --scope SCOPE.json --out RUN_DIR
python -m disastertrace.data_audit qualify --source D47 --out RUN_DIR
python -m disastertrace.data_audit link --out RUN_DIR
python -m disastertrace.data_audit count --out RUN_DIR
python -m disastertrace.data_audit report --out RUN_DIR
python -m disastertrace.data_audit verify --offline --out RUN_DIR
```

requirements只增加确实需要的小型读取/统计依赖，固定实际版本；不自动升级用户基础环境。使用本地隔离环境。下载器在网络关闭时必须可运行 mock 测试，`verify --offline` 不偷偷访问云缓存缺项。

### 10.1 下载策略须可选择，不写“全部下载”默认值

```text
mode = local_only | metadata | sampled_assets | approved_shards
source_selection = explicit source IDs
revision = resolved immutable version
filters = event/time/region/variables
max_bytes / max_requests / max_disk_bytes = explicit
allow_paid / allow_requester_pays / allow_gee = explicit false by default
```

各worker共享预算账本；不能每个worker都把总10GiB当成自己的10GiB。未知大小使用受限流式读取并在上限前停止；不能调用无界的 response.read()。

---

## 11. 最低测试清单

本节是待 Codex 执行的测试要求，不是本轮已经通过的项目测试。

| 测试 | 应有结果 |
|---|---|
| DNS/403/429/timeout、GEE鉴权失败 | 分类并记录，不变成无事件或空成功 |
| HTTP 200返回HTML登录页 | 不标为已下载数据包 |
| 有next_cursor但只读取第一页 | partial，不报告全集 |
| metadata成功、payload未下载 | catalog成功，fetched/decoded仍未执行 |
| 不支持Range | 受限停止，不获取完整大归档 |
| Range有效但对象版本变化 | 拒绝跨版本拼接，生成新的获取记录 |
| 恶意ZIP路径/过大解压 | 拒绝越界及超预算 |
| .npy包含需pickle对象 | 默认拒绝，不执行反序列化代码 |
| 同URL内容变化 | 新snapshot；旧哈希仍可验证 |
| 不同URL同blob | 内容可去重，来源和获取记录不丢失 |
| 多瓦片同event、多个灾种同复合event | 事件族不重复累加，标签覆盖仍保留 |
| 相同产品家族但不同时间地点 | 不因此把所有事件强连为一个组 |
| event身份不确定 | unresolved，不强填独立事件数 |
| null availability、观测晚于查询 | 不伪造历史可得时间，不把事后资料放入过去输入 |
| 云/nodata/无覆盖 | unknown/invalid，不改成负灾害标签 |
| private标签、CoT、未来参考混入公开资产 | 准入失败或拆分角色 |
| 配准/CRS/单位错误 | 具体错误或边界，不静默更正而不留痕 |
| 3个样例通过、全集10000 | 只报告3个已验证，不报告10000合格 |
| 旧heldout匹配/可能关联 | 阻止开发性内容打开，保留审计原因 |
| 离线重算 | 与已冻结catalog/资产范围内计数一致；不访问网络 |
| 源码或数据记录含秘密/签名URL | 输出脱敏，原始凭据不进入公开包 |
| 模型调用/GPU进程入口 | 此阶段计数必须为0；fixture不算真实资料 |

小型fixture可以合成，但 `is_synthetic_fixture=true`，不得计入天气事件、成功下载或真实样例数量。


## 12. 下一批资料如何选择：先看边际收益，再看体积

对每个来源输出三个彼此独立的建议：

- `USE_NOW`：在当前资料和许可条件下，已经有实际可解码、可关联并满足至少一种任务的样例；推荐复用其哪部分。
- `ADD_WITH_BRIDGE`：主体可用，缺少可定位的原始时间/图文/标签/事件ID；列出具体补源和实现工作。
- `CONDITIONAL_OR_DEFER`：需要新授权、研究许可、作者认可入口、大归档预算或难以恢复的语义；不作为已落实核心供给。

以上建议与实际verified数量分开。一个来源可以只对 C1 为 USE_NOW，对 C6 为 unsupported。

### 12.1 批量获取清单的字段

```text
source_id / pinned_release / object_id_or_query
requested_event_ids / proposed_hazard_ids
asset_roles / variables / time_interval / AOI
known_bytes / estimated_bytes / estimation_method
estimated_unpacked_bytes / cache_and_temp_overhead
marginal_confirmed_event_ids / marginal_candidate_event_ids
new_hazard_subtypes / new_regions / new_modalities
same_target_revision_potential / asof_evidence_available
existing_overlap / uncertain_overlap
license_evidence / auth_needed / paid_service / budget_scope
acquisition_method / expected_outputs / admission_checks
reason_to_prioritize / conditions_to_stop
```

不能用“新增百万条”替代净新增事件/模态的解释。`marginal_confirmed_event_ids` 必须基于实际去重；未知时只填候选，不给伪精确的节省比例。

### 12.2 三种数据规模方案，结果由事实决定

最终报告给出三个**基于本轮证据**的方案，而不是再次机械引用3,050：

| 方案 | 选择逻辑 | 必须报告 |
|---|---|---|
| 可立即构建版 | 已持有或预算内已实际核验，优先覆盖缺失灾种 | 已验证灾种/事件族/资产/能力，无法满足的细类 |
| 广覆盖扩容版 | 增加明确有目录和访问路径的源、补关键原始资料 | 净增候选、费用/流量/磁盘、桥接工作、估计不确定性 |
| 高质量动态核心版 | 仅取具备真实时空关系、合适参考与对应能力的子集 | 各C2/C3/C4/C6的实际下界与缺口，不混为同一种任务 |

如果一个新来源只能补更多已覆盖的洪水图，而另一个小型站点集合可补低温/能见度，应说明后者为何可能更有助于用户当前广覆盖目标。不是无限追求下载GB，也不是强求每个灾种一定有原生图文。

---

## 13. 最终报告模板

### 13.1 面向用户的总表

| 灾种/细类 | 已检查主源+备用源 | 公布量及单位 | 已枚举候选事件 | 已验证事件族 | 已解码资产 | C1/C2/C3/C4/C6/C7合格量 | 许可/访问 | 主要缺口 | 下一批动作 |
|---|---|---|---:|---:|---:|---|---|---|---|
| Hxx | 待程序填充 | reported | null/实测 | null/实测 | null/实测 | 分任务，非合计 | 证据路径 | 具体原因 | 文件/查询级 |

`0` 表示在明确范围内真实检查后计得0；`null` 表示未测或未知。正文不能将它们混写成“没有数据”。

### 13.2 每来源至少回答十个问题

1. 原始来源和发布者是什么，是否是作者认可发布？具体版本是什么？
2. 它到底包含哪些灾种和细类，灾害资格是否由资料支持？
3. 如何获取：本地、公开HTTP、HF、S3/GCS、GEE、Kaggle、网盘还是需申请？
4. 目录是否完整，文件/事件/帧/标签分别有多少，实际验证了多少？
5. 最小有效获取单元有多大；真实传输、解压、缓存与处理成本多少？
6. 是否能恢复事件ID、观测/有效/发行时间、区域、单位、质量和原始产品？
7. 实际拥有哪几种模态，来自独立传感器还是同源重渲染/转写？
8. 能支持哪些C0–C7能力，各自依据和不足是什么？
9. 与已有来源/本地资产/受保护事件有什么重叠和风险？
10. 现在应直接复用、补哪种原始资料，还是暂缓？推荐的下一批具体是什么？

### 13.3 失败也应可采取行动

`BLOCKED_NETWORK` 要区分具体环境DNS/代理/域名限制，不推广到源站永久不可用。`BLOCKED_AUTH` 说明需要哪种已有产品流程，不索要或打印凭据。`BLOCKED_BUDGET` 列最小获取单元和所缺额度。`UNSUPPORTED_TASK` 说明资料还能支持什么任务，而不是删掉该源。

报告不能说“所有类别都能下载”除非每类都已取回并解码至少一份对应合格资料；即使如此，也不能保证该类全部目录都可用或满足旧配额。

---

## 14. 文件交付与验收

Codex 应在一个新run目录中交付：

```text
START_REPORT.md                       工作区与本轮实际权限
REPO_DATA_BASELINE.json               现有资料/模块与冻结边界
SOURCE_FEASIBILITY.md                逐源结论，含未执行和阻塞
HAZARD_COVERAGE.md                   全部16类/细类覆盖矩阵
DATA_COUNTS.json                     可重算的单位/范围/实测数字
BENCHMARK_RAW_LINKS.jsonl            事件与产品的可核验链接
REUSE_AND_GAPS.md                    同现有MM/forecast接口的适配差距
NEXT_ACQUISITION_MANIFEST.json       下一批具体资产/查询与预算建议
LIMITATIONS.md                      未知量、偏差和适用边界
source_registry.json
acquisition_receipts.jsonl
asset_manifest.jsonl
sample_qualifications.jsonl
count_evidence.jsonl
split_risk_report.json
source_dependency_graph.json
tests_results.json                  实际命令、退出状态；不伪造passed
RUN_MANIFEST.json                   代码、配置、源版本、成本与输出hash
```

首次完成应满足：

- 原始54候选均保留或有显式合并映射；16类均有检查状态，长尾不被跳过。
- 实际看到的新来源可扩充，镜像/版本/子包不能无理由膨胀source总数。
- 至少一个本地已持有来源通过只读数据核验；如果本地未挂载，则明确说明并使用已授权替代样例，不假装仓库说明等于本地内容。
- 已获下载权限的优先来源有真实receipts/解码结果；没有权限则完整输出not_executed与阻塞，不称全部成功。
- 所有“可用”结论指向具体task与样本；所有数量有basis/单位/范围。
- 广域、模态、时序、修订、as-of、预测能力各自统计；不要求全部重叠才保留资料。
- 至少对实际获取资料执行去重和角色/时间/覆盖检查；离线重算在已取得范围内一致。
- 新代码/文件不覆盖旧实验；真实模型调用、GPU作业和训练次数均为0。
- 有一份基于边际收益和成本的下一批获取清单，而不是泛称“继续扩数据”。

完成部分工作也要交付已验证部分和完整缺口表。不要为了“完成”而创造文件、伪造成功日志，或把未执行步骤标记为已通过。

---

## 15. 可直接粘贴给 Codex 的启动提示

```text
请完整阅读 DISASTERTRACE_DATA_FIRST_CODEX_PLAN_CN.md。
当前目标只做 DisasterTrace 的数据可行性核查和扩容准备，不跑模型、GPU、训练或排行榜。
优先在现有工作区检查最新 AGENTS.md、HEAD、已持有数据和 multimodal_v1 的真实接口；
本计划锚点为 a8ea30d6fd35e5889f5f846ee9f49c87480cf96d，不要reset或覆盖未提交修改。

结合开源benchmark已整理数据和官方原始数据，完整登记54项初始候选、覆盖16类灾种，
可以继续补充新来源。旧3050是目标，不是现成数据量。
先执行DA00–DA02，同时准备DA03的本地解码和mock；随后按实际已有权限/预算执行小样例。
没有网络、GEE或大下载权限时，隔离对应步骤并继续可执行部分，不停止所有来源的核查。

不要只复述计划。交付实际检查代码、来源清单、真实日志、解码/配对检查、去重计数与报告。
分别统计公布量、目录量、获取量、可解码量、事件族，以及静态/多模态/时序/同目标修订/as-of合格量。
不因不能做修订而删除静态资料，不以瓦片/帧/问题数冒充独立灾害数。
保护旧heldout、原始快照、Gold、失败和冻结结果，不push，不启动旧作业。
最终回答每类灾害现在能用什么、证实多少、缺什么、补什么原始资料，以及下一批如何获取。
```

---

## 16. 本次依据、证据等级与访问入口

### 16.1 最新仓库依据（本次实际读取，未复跑其测试）

- [R1] 分支清单：`https://api.github.com/repos/sisuolv/disastertrace-benchmark/branches?per_page=100`
- [R2] 当前阶段：`https://github.com/sisuolv/disastertrace-benchmark/blob/a8ea30d6fd35e5889f5f846ee9f49c87480cf96d/disastertrace-starter/CURRENT_PHASE.md`
- [R3] MM种子文档：`https://github.com/sisuolv/disastertrace-benchmark/blob/a8ea30d6fd35e5889f5f846ee9f49c87480cf96d/disastertrace-starter/README_MULTIMODAL_V1.md`
- [R4] MM数据类型：`https://github.com/sisuolv/disastertrace-benchmark/blob/a8ea30d6fd35e5889f5f846ee9f49c87480cf96d/disastertrace-starter/src/disastertrace/multimodal_v1/types.py`
- [R5] MM构建逻辑（本次读取前130行）：`https://github.com/sisuolv/disastertrace-benchmark/blob/a8ea30d6fd35e5889f5f846ee9f49c87480cf96d/disastertrace-starter/src/disastertrace/multimodal_v1/build.py`

### 16.2 前序文件（随包附带，旧状态不自动代表新代码）

- [A1] `inputs/DisasterTrace_Data_Format_Online_Audit_CN.md`：旧提交上的局部源码审查，不代表新MM模块仍有同样缺陷。
- [A2] `inputs/DisasterTrace_Reusable_Data_Feasibility_20260910.md` / `.json`：12项来源的前序公开资料核查，没有完整下载。
- [A3] `inputs/DisasterTrace_Dataset_Registry_20260910.md` / `.json`：原46项候选和16类旧配额；数量保留原文，不升级为当前实测。

### 16.3 本次复查的公开入口（仅文档/目录读取）

- [S1] ExEBench 作者仓库：`https://github.com/zhaoshan2/EarthExtreme-Bench`；数据文件页：`https://huggingface.co/datasets/zhaoshan/ee-bench_v1.0/tree/stable/data/weather`
- [S2] EWB 数据文档：`https://extremeweatherbench.readthedocs.io/en/latest/data/`；由文档给出的代码仓库：`https://github.com/brightbandtech/extremeweatherbench`
- [S3] WeatherQA 作者仓库：`https://github.com/chengqianma/WeatherQA`
- [S4] GEOID-Flood 作者仓库：`https://github.com/links-ads/geoid-flood`
- [S5] WorldFloods 官方项目文档：`https://spaceml-org.github.io/ml4floods/content/worldfloods_dataset.html`
- [S6] WildfireSpreadTS 固定发布记录：`https://zenodo.org/records/8006177`
- [S7] TorNet 作者仓库：`https://github.com/mit-ll/tornet`
- [S8] NOAA Storm Events 年度目录：`https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/`
- [S9] GEE filterDate：`https://developers.google.com/earth-engine/apidocs/ee-imagecollection-filterdate`
- [S10] DroughtED 作者论文介绍：`https://www.climatechange.ai/papers/icml2021/22`
- [S11] GEE IMERG V07 产品说明：`https://developers.google.com/earth-engine/datasets/catalog/NASA_GPM_L3_IMERG_V07`

以上入口可读仅证明相应页面被读取，不是认证、数据下载、格式解码或全部历史版本可用的证明。其他来源入口继承[A2/A3]，执行时逐项核验。

---

## 附录 A. 完整初始来源表（54项，不是全部已验证供给）

原D01–D46不改编号。前序补充中的 GEOID、WildfireSpreadTS、SEVIR、TorNet 合并到既有条目；8个新增条目为D47–D54。代码包、云数据、论文数据集、事件目录和背景产品的“登记项”不是统一的独立观测源单位。

每个来源都要执行“目录/许可核查→预算内取样→解码与来源检查→事件计数与任务标签”；第一轮尚未执行的字段保持空值。表内入口有的是论文或目录而非直链，必须沿发布者给出的实际文件链接获取，不根据文件命名规则猜URL。

| ID | 数据集/资源 | 灾种或角色 | 首个核查入口 |
|---|---|---|---|
| D01 | NHC Public / Forecast Advisories + GIS | 热带气旋；风暴潮；强风 | `https://prod-east-nhc.woc.noaa.gov/gis/` |
| D02 | IBTrACS v4r01 | 热带气旋 | `https://www.ncei.noaa.gov/products/international-best-track-archive` |
| D03 | Digital Typhoon V2 | 热带气旋 | `https://arxiv.org/html/2411.16421v1` |
| D04 | TCIR | 热带气旋 | `https://www.csie.ntu.edu.tw/~htlin/program/TCIR/` |
| D05 | NOAA Storm Events Database | 暴雨；洪水；龙卷风；冰雹；雷暴风；热浪；寒潮；冬季天气等 | `https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/` |
| D06 | SEVIR | 强对流；降水；雷电；部分龙卷风/冰雹关联 | `https://raw.githubusercontent.com/MIT-AI-Accelerator/eie-sevir/refs/heads/master/examples/SEVIR_Tutorial.ipynb` |
| D07 | TorNet | 龙卷风；强对流 | `https://arxiv.org/html/2401.16437v1` |
| D08 | NOAA NEXRAD | 强对流；降水；龙卷风相关 | `https://registry.opendata.aws/noaa-nexrad/` |
| D09 | NOAA MRMS | 暴雨；强对流；冰雹相关 | `https://registry.opendata.aws/noaa-mrms-pds/` |
| D10 | GOES-R ABI / GLM archives | 气旋；强对流；雷电；烟尘 | `https://registry.opendata.aws/noaa-goes/` |
| D11 | Global Flood Database v1 | 洪水 | `https://developers.google.com/earth-engine/datasets/catalog/GLOBAL_FLOOD_DB_MODIS_EVENTS_V1` |
| D12 | GEOID-Flood | 洪水 | `https://arxiv.org/abs/2608.02315` |
| D13 | KuroSiwo | 洪水 | `https://arxiv.org/abs/2311.12056` |
| D14 | UrbanSARFloods | 城市洪水；开放区域洪水 | `https://arxiv.org/abs/2406.04111` |
| D15 | Sen1Floods11 v1.1 | 洪水 | `https://github.com/cloudtostreet/Sen1Floods11` |
| D16 | SpaceNet 8 | 洪水；气旋次生淹水 | `https://spacenet.ai/sn8-challenge/` |
| D17 | FloodNet | 洪水；气旋次生灾害 | `https://github.com/BinaLab/FloodNet-Supervised_v1.0` |
| D18 | CEMS Rapid Mapping | 洪水；野火；风暴；其他自然灾害 | `https://mapping.emergency.copernicus.eu/about/how-to-harvest-cems-mapping-data/emergency-response-data/` |
| D19 | WildfireSpreadTS | 野火 | `https://zenodo.org/records/8006177` |
| D20 | Next Day Wildfire Spread | 野火 | `https://arxiv.org/html/2112.02447v2` |
| D21 | TS-SatFire | 野火 | `https://arxiv.org/abs/2412.11555` |
| D22 | Sen2Fire | 野火 | `https://arxiv.org/abs/2403.17884` |
| D23 | NASA FIRMS | 野火；热异常 | `https://firms.modaps.eosdis.nasa.gov/api/` |
| D24 | MTBS burned-area boundaries | 野火 | `https://developers.google.com/earth-engine/datasets/catalog/USFS_GTAC_MTBS_burned_area_boundaries_v1` |
| D25 | ERA5-Land Hourly | 热浪；寒潮；干旱；暴雨；积雪；强风等 | `https://developers.google.com/earth-engine/datasets/catalog/ECMWF_ERA5_LAND_HOURLY` |
| D26 | GHCN-Daily | 热浪；寒潮；暴雨；大雪 | `https://www.ncei.noaa.gov/products/land-based-station/global-historical-climatology-network-daily` |
| D27 | ISD / Global Hourly | 低能见度/浓雾；大风；热冷极端；降水 | `https://www.ncei.noaa.gov/products/land-based-station/integrated-surface-database` |
| D28 | NOAA GFS0P25 | 多类天气极端的预测 | `https://developers.google.com/earth-engine/datasets/catalog/NOAA_GFS0P25` |
| D29 | GPM IMERG V07 | 暴雨；洪水；气旋降水 | `https://developers.google.com/earth-engine/datasets/catalog/NASA_GPM_L3_IMERG_V07` |
| D30 | CHIRPS v3 DAILY_SAT | 干旱；降水极端 | `https://developers.google.com/earth-engine/datasets/catalog/UCSB-CHC_CHIRPS_V3_DAILY_SAT` |
| D31 | US Drought Monitor | 干旱 | `https://droughtmonitor.unl.edu/About/WhatistheUSDM.aspx` |
| D32 | SMAP Enhanced L3 Soil Moisture | 干旱；洪水前湿度；冻融 | `https://developers.google.com/earth-engine/datasets/catalog/NASA_SMAP_SPL3SMP_E_006` |
| D33 | MODIS Snow MOD10A1.061 | 积雪；冬季天气 | `https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MOD10A1` |
| D34 | MODIS LST MOD11A1.061 | 热浪；地表高温 | `https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MOD11A1` |
| D35 | MERRA-2 aerosol diagnostics | 沙尘；烟尘 | `https://developers.google.com/earth-engine/datasets/catalog/NASA_GSFC_MERRA_aer_2` |
| D36 | Sentinel-5P OFFL Aerosol Index | 沙尘；烟羽 | `https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S5P_OFFL_L3_AER_AI` |
| D37 | NOAA CO-OPS water levels | 风暴潮；沿海洪水 | `https://api.tidesandcurrents.noaa.gov/api/prod/` |
| D38 | NOAA OISST v2.1 | 海洋热浪（气候扩展） | `https://www.ncei.noaa.gov/products/optimum-interpolation-sst` |
| D39 | EM-DAT | 多灾种；含非天气灾害 | `https://doc.emdat.be/` |
| D40 | NASA EONET v3 | 火灾；风暴；洪水；干旱等及非天气灾害 | `https://eonet.gsfc.nasa.gov/docs/v3` |
| D41 | GDACS | 多自然灾害 | `https://www.gdacs.org/About/overview.aspx` |
| D42 | Sentinel-1 GRD | 洪水；野火后变化；滑坡等 | `https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S1_GRD` |
| D43 | Sentinel-2 SR Harmonized | 洪水；野火；旱情；积雪；灾后变化 | `https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2_SR_HARMONIZED` |
| D44 | xBD | 洪水；气旋；野火；含地震等 | `https://arxiv.org/abs/1911.09296` |
| D45 | CrisisMMD v2.0 | 气旋；洪水；野火；含地震 | `https://crisisnlp.qcri.org/crisismmd` |
| D46 | Landslide4Sense | 降雨诱发滑坡（扩展）；含地震诱发滑坡 | `https://arxiv.org/abs/2206.00515` |
| D47 | ExEBench / EarthExtreme-Bench | heatwave / coldwave / tropical_cyclone / extreme_precipitation / radar_storm / wildfire_burn_scar / flood | `https://github.com/zhaoshan2/EarthExtreme-Bench` |
| D48 | ExtremeWeatherBench (EWB) | heatwave / freeze / tropical_cyclone / severe_convection / atmospheric_river | `https://extremeweatherbench.readthedocs.io/en/latest/data/` |
| D49 | WeatherQA | severe_convection / winter_storm | `https://github.com/chengqianma/WeatherQA` |
| D50 | CyPortQA | tropical_cyclone / port_related_scenario | `https://github.com/ChenchenMobility/MLLM-Bench-CyPortQA` |
| D51 | WorldFloods v2 / ml4floods | flood | `https://github.com/spaceml-org/ml4floods` |
| D52 | DroughtED | drought | `https://www.climatechange.ai/papers/icml2021/22` |
| D53 | M4Fog | marine_fog | `https://arxiv.org/abs/2406.13317` |
| D54 | CLLMate | multi_weather_climate_events | `https://arxiv.org/html/2409.19058v2` |

### 附录 B. 不要遗漏的别名与版本

| 前序ID | 本包ID | 合并说明 |
|---|---|---|
| F01 | D47 | ExEBench / EarthExtreme-Bench；保留前序证据，不重复计数 |
| F02 | D48 | ExtremeWeatherBench (EWB)；保留前序证据，不重复计数 |
| F03 | D49 | WeatherQA；保留前序证据，不重复计数 |
| F04 | D50 | CyPortQA；保留前序证据，不重复计数 |
| F05 | D12 | GEOID-Flood；保留前序证据，不重复计数 |
| F06 | D51 | WorldFloods v2 / ml4floods；保留前序证据，不重复计数 |
| F07 | D19 | WildfireSpreadTS；保留前序证据，不重复计数 |
| F08 | D06 | SEVIR；保留前序证据，不重复计数 |
| F09 | D07 | TorNet v1.1；保留前序证据，不重复计数 |
| F10 | D52 | DroughtED；保留前序证据，不重复计数 |
| F11 | D53 | M4Fog；保留前序证据，不重复计数 |
| F12 | D54 | CLLMate；保留前序证据，不重复计数 |

**终点：形成有真实证据的广覆盖数据决策，而不是用一个固定目标倒推并伪造可用库存。**
