# DisasterTrace V6 数据集选择：研究、实测与执行路线

核查日期：2026-09-11。输入为用户提供的两份 V6 计划及 download_registry.json；原始字节副本和哈希已保存。结论建立在此前抽样与本轮新增验证上，不是仅阅读网页后的推荐。

## 1. 推荐决定

采用两层结构：先建设尽可能广的 Broad Data Bank，再从中按任务建立合格子集。以 16 类天气灾害为覆盖目标，保留所有 54 个原候选，并登记 20 个互补来源。74 是登记项数，含 benchmark、原始产品及派生集合；既不是独立数据源数，也不是全部已验证数。没有必要等待所有来源满足同目标修订才能扩容。

优先开发池围绕几条互补链组织：事件目录 Storm Events/HANZE/IBTrACS；地面与水文观测 GHCN/ISD/USGS/CO-OPS/Caravan；天气演化与空间证据 NHC/SEVIR/GLM/MeteoNet/SNODAS/CHIRPS；整理后的寒潮/热浪路线 ExEBench/EWB；干旱 USDM；野火 WildfireSpreadTS/FIRMS。这些是优先适配和完成准入的选择，并非已经批准重分发或形成新题集。

GEOID、TorNet、CyPortQA、DroughtED、TS-SatFire、WorldFloods、M4Fog 等保留为条件候选。已有证据很有价值，但缺正例、版本/切分冲突、时间对齐或数据权利时，需要补齐指定条件。EM-DAT/xBD 等访问门槛较高且不是当前覆盖瓶颈的资料暂缓。海洋热浪和降雨滑坡单列扩展，避免挤占主要 16 类的长尾补样。

## 2. 已经实际验证的关键证据

| 来源 | 本地实测 | 结论范围 |
| --- | --- | --- |
| NOAA Storm Events | 2021 年 61,389 + 2023 年 75,593 = 136,982 条报告 | 可作多灾种索引；非独立天气系统数，含应排除的非天气类型 |
| ExEBench coldwave | 4,385,936 字节完整包；固定 commit；9 源案例、559 时间步、8 国/地区 | NetCDF t2m(K)、坐标和序列表日期已对齐；其他子包未下载 |
| ExtremeWeatherBench | 329 条案例定义；GHCN-hourly 解码 122,880 行、24 站 | 仅读取一个 row group；整个 Parquet 的 298,948,393 行来自 footer，不是已下载量 |
| GHCN / ISD | 5 个日观测窗口共 40 站日；2 个逐时站年共 28,733 报告 | QC/缺测字段已解析；仍须独立定义极端阈值和事件窗口 |
| GLM | 3 个相邻 20 秒产品；489 flash / 6,904 group / 18,973 event 记录 | 父子 ID 一致；计数单位不同，未认定为强雷电过程 |
| GEOID + CEMS | 3 组前后 SAR/label/validity，12 资产；EMSR712/AOI10 可桥接 | 三瓦片洪水正像素均为 0；原数据 split 为 test，只作已观察审计材料 |
| TorNet | 从部分归档提取 3 个完整 train NetCDF | 全部 NUL 负例；龙卷风正例验证仍为 0 |
| WildfireSpreadTS | 同一火场 3 日 TIFF，按作者规则复算活动火像素 4/0/0 | 854 等值是 HHMM 探测时刻，NaN 依作者规则转无探测；不构成火场消失的充分证明 |
| DroughtED | 1 MiB 压缩前缀解析 26,666 个完整 CSV 行、5 县、3,809 非空分数 | 不是完整归档；无完整成员 CRC；其中 1,330 个分数为小数，不能直接当整数六分类 |
| CO-OPS | 3 站共 720 对观测/预测潮，同 MLLW/GMT/米 | 可重算残差；残差不等于单一风暴潮成因 |
| Caravan / MeteoNet | 3 流域各 14,609 日；111,623 站报/484 站及 IR 数组 | 可补水文和欧洲资料；三个 Caravan 样例仍全部在美国 |
| 补充资料 | SNODAS 3 日、CHIRPS 2 日、OISST 3 日；Landslide4Sense 3 对；HANZE 2,521 记录；Dheed 82,839 记录 | 栅格、事件目录和标签对分别计数；不求一个混合总样本量 |

本轮新增 V6 捕获 80 次 HTTP 尝试、22,888,813 字节；此前抽样 bundle 为 228 次、321,358,162 字节。尝试数包含重定向/失败，字节包含元数据和不完整响应。六类继承样例共绑定 26 个已有文件，没有重复当作新下载。

## 3. 对 V6 计划的重要修正

1. ExEBench 与 ExtremeWeatherBench 是两个不同项目；一个寒潮包的成功不能外推到所有天气/遥感子包。ExEBench 的国家案例可能属于同一跨境寒潮，9 个 case ID 尚不等于 9 个独立过程。
2. 数据集页面和真实数据会矛盾。DroughtED 页面说 train 2000–2009，本地 train 前缀实际含 2000–2016；下一阶段以冻结文件和实际日期计数为依据，并调查发布版本。周频缺失不等于无干旱，小数 score 的聚合公式需核验。
3. 简单取前三个文件会产生假覆盖。TorNet 三个负例、GEOID 三个无洪水瓦片、同一火场三天都证明了这一点。后续必须按正负/事件/地区/季节分层，失败和空样本保留在分母。
4. GEOID validity 与 label != 255 在本批完全一致，因此把它当公开独立传感器质量会泄漏 Gold。保留为私有评分有效区，另找真实云、轨道和传感器 QC。
5. ISD 本批实际有 34 条雾码以及 276 条浮尘/扬沙码；沙尘暴码 30–35、冻雨码 66–67、吹雪码 36–39 正例为 0。H14、H12 的特定细类仍是重点缺口，不能以“低能见度”或“SWE 有数据”替代。
6. CEMS 产品目录含“不生产/无变化”的版本。产品目录、发布版本、真实演化与同目标修订分别记录，不能仅按版本字段构造修订任务。
7. 公开访问、内容解码、来源链、数据权利、任务准入五轴分开。数据版权尚不明确的集合仍可登记其事实状态，不会因为网页打开就进入发布版。

## 4. 怎样兼顾覆盖与 novelty

多灾种数量是数据优势，单纯拼接公开 benchmark 本身不足以证明论文创新。建议将贡献收敛为“跨灾种、可追溯证据下的 LLM/VLM 状态判断与更新”，并保留三个相互可比、分别计分的层次。

- 覆盖层：16 类数据驱动阅读、阈值/持续时间判断、范围/受影响对象判定；与 ExEBench 的数值任务、EWB 的预报案例、WeatherQA/CyPortQA 的图文问答分别比较，不声称它们缺少全部相关能力。
- 演化层：同一真实过程多时刻证据，检查状态变化、未知区域与证据冲突；不同物理时刻和同一目标的预报修订分开。连续栅格可做 C3，不能因此叫 C4。
- 证据更新层：同一目标、不同发布/可见证据、时效冲突、可靠性和 abstention；Gold 来自明确的源记录及确定性规则。将受控交付 C5 与严格历史 as-of C6 分开，后者目前可以为空。

未来模型实验须加 text-only、image-only、完整证据、oracle structured evidence、时间打乱/过期证据、缺失证据和同源重复的诊断对照，分别报告感知错误与推理/更新错误。多模态必要性要有同文异图或同图异文等受控验证；不能用内容完全冗余的重绘图声称必须看图。

目前的 novelty 是有证据支撑的研究定位，不是已完成的首创性证明。还需要固定检索日期，对 ExEBench、EWB、WeatherQA、CyPortQA、CLLMate 及动态/工具型地学 benchmark 做方法维度对照；禁止未经系统检索写“首次”。本阶段不新增模型结果来代替该核查。

## 5. 后续执行顺序与完成条件

| 阶段 | 建议节奏 | 工作 | 完成条件 |
| --- | --- | --- | --- |
| A：库存和元数据收口 | 1–2 天 | 现有 74 项登记；优先来源许可、版本、source/event/product/asset 身份；保护过滤 | 每项有五轴状态，文件计数可重算，未知数保留 null；不要求全部来源成功 |
| B：长尾与正负抽样 | 3–5 天 | 优先沙尘暴/冻雨/极端雾/强雷电；TorNet、GEOID 正例；ExEBench 热浪；火场和非美国增益 | 每条保留主路线和备选；至少 3 可识别单元目标并按正负/地区分层；不足则显式列缺口 |
| C：事件合并和数据合同 | 第 2 周 | 三种图分开；跨 benchmark/跨国事件归并；变量、单位、时间支撑区间、QC、权利和 Gold authority | 不跨 split 的事件/资产簇，原始 split 保留，至少一个可审计极端/正常对照窗；混合/不确定事件隔离 |
| D：小规模可评分试点 | 后续约 2 周 | 复用已有 MM/active_forecast 接口，确定性查询与独立数值参考，先不调用模型 | 每个进入主榜的灾种都有合格数据/Gold/负例；未合格灾种留 Broad，不伪造全面覆盖 |
| E：模型评测与论文线 | 之后按实测供给推进 | 冻结开发/测试，执行感知/推理/更新对照、污染和泛化分析 | 只有准入、隔离与评分检查通过后启动 LLM/VLM；按事件族统计，不按问法膨胀 |

下一批下载和元数据操作已写入 NEXT_ACQUISITION_MANIFEST.json，12 项依赖与捕获上限合计约 836 MiB。此数是各项上限之和，不是已启动预算、预测流量或预计净增事件数；实际事件增量和用户存储配额尚未知。优先执行 N11/N12 的离线工作，再执行 N01/N03/N04/N05 补关键证据，之后扩大其他数据。

## 6. 当前完成边界

DA00 工作区/冻结核查和 DA01 登记/16 类路线已完成本阶段要求。DA02/DA03 已对可达重点来源实际探测与解码，仍有未探测/阻塞项。DA04 有源案例和产品桥接记录，尚非所有样本的精确版本链。DA05 有能力候选矩阵，未完成正式任务准入。DA06 已重算本地数量、列出已知重复簇，但全量事件族/国家季节分布未完成。DA07 已交付下一轮具体获取清单。DA08 将以 VERIFY_REPORT.json 记录本次交接文件与哈希核查；它不宣告整个 V6 路线全部完成。

所有新增正式 episode = 0，新增 GPU 作业 = 0，新增 API/模型调用 = 0。历史 104 个开发 episode、现有 Francine MM 种子和历史模型成绩保持原冻结范围，不能与这次数据验证相加。所有历史 available_at 没有确证时仍为 null。

## 7. 阅读与复查入口

先看本文件，再看 SOURCE_FEASIBILITY.md 和 HAZARD_COVERAGE.md。详细数量在 DATA_COUNTS.json；逐样本核验在 analysis/SELECTION_AUDIT.json 和 analysis/DOWNLOADED_AUDIT.json；桥接事实在 BENCHMARK_RAW_LINKS.jsonl；现有接口复用在 REUSE_AND_GAPS.md；事件与依赖限制在 SPLIT_AND_DEPENDENCY_RISKS.json、SOURCE_DEPENDENCIES.json；后续执行依据为 NEXT_ACQUISITION_MANIFEST.json。

可离线运行：`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/mnt/afs/260010168/.venvs/disastertrace-multihazard-libs-20260911 python3 plans/v6_0911_dataset_selection/audit_selection.py`，随后 `python3 plans/v6_0911_dataset_selection/build_reports.py`。验证脚本和说明见 verify_selection.py/VERIFY_REPORT.json。源码读取器仅检查文本，没有执行作者模型、训练代码或不可信 pickle。
