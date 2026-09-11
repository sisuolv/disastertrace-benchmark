# DisasterTrace V6: ChatGPT Pro 单文件复查材料

本文件汇集审查任务、主要报告和关键代码。当前为数据验证阶段，尚无新增模型实验。
请优先核对主张与证据，按严重性报告问题。完整文件清单和机器可读审计另在同目录 ZIP。


---

来源文件：`publication/v6_review_20260911/REVIEW_FOR_CHATGPT_PRO_CN.md`

# 请 ChatGPT Pro 复查 DisasterTrace V6 数据选择与研究设计

请对这份材料进行独立研究审查和代码审查，先列出问题，再给调整建议。不要把已有报告的结论当作正确答案；需要检查代码、统计口径和证据是否支持它们。

仓库：`sisuolv/disastertrace-benchmark`；分支：`next-phase-v1`。
本次主题是 **2026-09-11 的 V6 数据选择阶段**；上一发布父提交为 `a8ea30d6fd35e5889f5f846ee9f49c87480cf96d`。
请记录你实际读取的 commit。首页下方的 P5/P6 或旧 CURRENT_PHASE 属于历史阶段，不是本次数据工作的最新状态。

## 一、研究目标和用户要求

目标是建设评测 LLM/VLM 的极端天气 benchmark，尽可能覆盖热带气旋、大风、雷暴风、龙卷风、冰雹、雷电、极端降水、洪水、沿海灾害、热浪、寒潮、冬季天气、干旱、沙尘、浓雾和野火等 16 类方向。

用户要求先实际取样和验证数据来源，再决定最终数据集与任务。允许复用现有 benchmark、官方产品、已有标注和开源读取器；不新增逐题人工复核，不用 LLM judge 决定 Gold。可以继承已有专家或人工标注，但必须披露来源，不能宣称整个标签链没有人工。

没有硬截止日期。当前先做数据，不启动训练、LLM/VLM/API 评测或批量生成 QA。后续资源最多可用 4 张 H100；本次数据验证没有使用 GPU 或模型 API。

拟采用两层结构：Broad Data Bank 保留有价值的静态、时序和多模态资料；Task-ready subsets 按空间阅读、真实演化、同目标修订、受控证据回放、历史 as-of、未来结果配对等具体任务分别准入。

## 二、本轮已经实际做了什么

| 项目 | 实测结果 | 必须保留的限制 |
| --- | --- | --- |
| 来源清单 | 54 个原始候选 + 20 个互补登记项 | 含 benchmark 和派生产品，不是 74 个独立观测源，也不是全部已解码 |
| Storm Events | 2021/2023 两个完整年度文件，136,982 条报告 | EPISODE_ID 不等于独立天气系统，年度资料需保护事件过滤 |
| ExEBench coldwave | 固定 HF commit 的完整包；9 个源案例，559 时间步，8 国/地区 | 其他子包未下载；跨国案例可能共享物理过程；来源与再分发权利仍待查 |
| ExtremeWeatherBench | 329 条案例定义；一个 GHCN-hourly row group，122,880 行、24 站 | 尚未完成这些观测与具体 EWB 事件的配对；footer 的约 2.99 亿行不是已下载量 |
| GLM | 3 个连续 20 秒产品，flash/group/event 数与父子关系已检查 | 尚未建立极端密度基线或完成边界闪电去重 |
| GEOID/CEMS | 3 组完整前后 SAR/label/validity，连接到 EMSR712/AOI10 | 3 个瓦片洪水正像素均为 0；原 split 为 test，仅保留已观察审计身份 |
| TorNet | 从部分归档提取 3 个完整 train NetCDF | 均为 NUL 负例；龙卷正例和 v1.1 标签映射待验证 |
| DroughtED | 1 MiB 压缩前缀解析 26,666 完整行，3,809 非空分数 | 1,330 个分数为小数；train 实际含 2000–2016，与页面 2000–2009 描述冲突；无完整归档 CRC |
| WildfireSpreadTS | 同一火场 3 天；依作者读取器从探测时刻复算活动火像素为 4/0/0 | 无探测不能直接推断无火；需要独立覆盖质量与更多火场 |
| ISD | 北京与沙特两个站年；34 条雾码、276 条浮尘/扬沙码且有可用能见度 | 本批沙尘暴、冻雨、吹雪所检现象码正例为 0 |
| CO-OPS | 3 个站点共 720 对同基准面观测/预测潮 | 潮汐残差不等于单一风暴潮成因 |
| 交接核验 | VERIFY_REPORT 中 658 项断言通过 | 包括大量文件/hash/引用检查；不能称作 658 个独立科学测试或模型样本 |

本轮新正式任务数、新模型调用和新 GPU 作业均为 0。已有 Active Forecast 内核、104 个历史开发 episode 和 Francine 多模态种子属于此前工作，不计作本轮扩容成果。

## 三、建议阅读顺序

1. `plans/v6_0911_dataset_selection/DATA_READINESS_REVIEW_CN.md`：总体选择、验证结果和路线。
2. `SOURCE_FEASIBILITY.md`、`HAZARD_COVERAGE.md`、`RELATED_BENCHMARK_COMPARISON.md`：逐源、逐灾种和已有 benchmark 对照。
3. `DATA_COUNTS.json`、`SOURCE_REGISTRY.json`、`source_access_report.jsonl`：统计口径和五轴状态。
4. `analysis/SELECTION_AUDIT.json`、`analysis/DOWNLOADED_AUDIT.json`：本次和此前抽样的实际解码结果。后者保留早期失败状态，新审计中相应成功重试单列。
5. `audit_selection.py`、`audit_downloaded.py`、`build_reports.py`、`prepare_decisions.py`、`verify_selection.py`：检查算法、人工录入的科学判断和生成报告的一致性。
6. `plans/multihazard_source_validation_20260911/validate_samples.py`、`assemble_samples.py`、`sample_archives.py`、`probe_sources.py`：格式、QC、HTTP Range、归档和部分响应边界。
7. `BENCHMARK_RAW_LINKS.jsonl`、`SPLIT_AND_DEPENDENCY_RISKS.json`、`SOURCE_DEPENDENCIES.json`、`ASSET_REUSE_INDEX.json`：来源连接与泄漏风险。
8. `NEXT_ACQUISITION_MANIFEST.json`、`REUSE_AND_GAPS.md`：下一步可执行清单及现有接口复用。

上述缩写路径均相对 `plans/v6_0911_dataset_selection/`，除非已给出完整仓库相对路径。

如要检查任务接口，阅读 `disastertrace-starter/src/disastertrace/multimodal_v1/types.py` 和 `disastertrace-starter/src/disastertrace/active_forecast/`。已有模块是真实实现，不能重新建议从零搭框架；但 `FactKey.threshold_kt` 等气旋语义尚不能直接泛化为所有灾种。

## 四、请重点回答的审查问题

### 1. 数据选择是否充分、合理且可落实

- 哪些来源真正可以优先适配，哪些仍只是目录、负例、背景层或部分文件？五轴状态有没有互相冒充？
- 16 类覆盖表是否夸大细类：积雪与冻雨、扬沙与沙尘暴、雷达回波与冰雹/下击暴流、热点与天气相关野火、总水位与风暴潮？
- 当前便利抽样应该怎样改为正负、地区、季节和事件分层抽样？每个优先来源的最低证据单元应是什么？
- 哪些来源是同源派生或重复资产？如果要降低成本，最应该删减或合并哪些获取工作？
- 用已有 benchmark 补全球覆盖是否可靠？请给出明确的保留、补证、暂缓或替换建议，不只建议“多下数据”。

### 2. 数量、时间、标签及物理语义是否正确

- 所有计数是否分开 source case、真实事件族、报告、站日、时间步、瓦片、分支和任务？
- ExEBench t2m 场与序列的空间聚合定义是否被实际验证，还是仅日期匹配？
- DroughtED 小数 score 的聚合公式与训练年份冲突怎样处理？数据文件完整性和标签稀疏性还缺哪些核验？
- 读取器对 NaN、nodata、质量标记、缺失哨兵、温度/雨量/流量单位是否正确？地面日界是否被误称 UTC？
- GEOID 的 Gold-derived validity 是否充分隔离？已观察的外部 test 样例能否进入后续开发/隐藏测试？
- 是否把预报潜势当成已观测事件、把 issued_at/retrieved_at/Last-Modified 当成历史 available_at？

### 3. 来源链、去重与切分是否足够

- 物理事件图、资产重复图、来源依赖图是否被正确区分？共享 ERA5 是否错误导致所有事件合并？
- 同一气旋的 NHC/CyPortQA/IBTrACS、同一洪水的 CEMS/多个 benchmark，以及跨国寒潮该如何归并？
- 原始 split、现有保护风暴和关联派生标签有没有遗漏？unknown 的分组如何隔离？
- 公开已有 benchmark 可能进入 LLM 预训练，未来测试应该怎样减少污染并如实报告限制？

### 4. Novelty 是否站得住

请对照 ExEBench、ExtremeWeatherBench、WeatherQA、CyPortQA、CLLMate、洪水/野火时序 benchmark，以及其他相关动态证据或地学工具评测。

拟议核心是“跨灾种、可追溯证据下的 LLM/VLM 状态判断与信息更新”。请判断：哪些已有工作已覆盖，哪些只是应用迁移，哪些确有新测量价值？若创新不足，给出最小可行重定位，以及能够证实或否定该贡献的实验。不得仅以灾种/数据规模增加来宣告 novelty，也不要未经检索写“首次”。

有联网能力时请核验论文和作者仓库，给出链接与检索日期；如果无法检索，明确把新颖性结论标为暂定。

### 5. 后续计划应如何重排

对 NEXT_ACQUISITION_MANIFEST 的 12 项任务逐项判断：应马上做、依赖前置条件、延期或取消。优先修复会影响结论和数据准入的问题，不以新增模型调用掩盖数据缺口。

请给出一周数据阶段和两周试点阶段的顺序及停止条件。资源约束为无需新增逐题人工复核、当前先不调用模型、未来最多 4 张 H100；不要求凑旧的 3,050 episode 配额。

## 五、希望你返回的格式

1. **P0/P1/P2 问题列表**：文件/行号或 JSON Pointer、证据、触发条件、影响、最小修复方案。区分已证实问题、疑点和材料缺失；没有明确缺陷就如实说。
2. **逐来源决策表**：保留/补证/暂缓/替换、支持哪些灾种及任务、最关键的未满足条件。
3. **16 类覆盖修正版**：真实已验证证据、缺失细类和优先补样路线。
4. **Novelty 评估**：已有工作对照、应收缩的主张和推荐核心贡献。
5. **最多 5 项最高优先改动**，以及按依赖排序的一周/两周实施安排。

请不要只复述报告、简单肯定方案或泛泛建议增加数据和模型。不要把完整性断言数量当成实验强度。

## 六、材料与执行边界

本次 GitHub 快照和 ZIP 为研究/代码阅读包，包含代码、报告和结构化审计；不含数百 MB 原始 HTTP 字节、科学数组、权重和运行环境。FILE_MANIFEST/RUN_MANIFEST 中的一些路径保留原工作区的证据引用，路径不存在不等于原环境未做验证，但限制了你在阅读包内独立重放数组结果。

`python3 publication/v6_review_20260911/verify_review_snapshot.py` 可在仓库或解压后的阅读包运行，核验随包文件哈希与选定统计关系，不联网。完整 `audit_selection.py` 和 `verify_selection.py` 需要原始数据，不要把阅读包检查说成完整原始数据复算。

请不要自动启动抓取器、历史 GPU worker、付费 API 或更改受保护 split。本次让你分析并提出可审核的修改建议；实施工作另行执行。


---

来源文件：`plans/v6_0911_dataset_selection/DATA_READINESS_REVIEW_CN.md`

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


---

来源文件：`plans/v6_0911_dataset_selection/HAZARD_COVERAGE.md`

# 16 类灾种的实测覆盖与缺口

“有目录/有观测/有正例/有任务”分别判断。下表报告数是 2021、2023 两年美国 NOAA 报告类型的实测计数，不是去重天气事件，也不代表全球覆盖。三条相邻记录属于便利抽样，不能估计可用率。全部新资料尚未成为正式评测题。

| ID / 灾种 | 主路线；备选 | 目录报告条数 | 已经验证 | 仍需解决 |
| --- | --- | --- | --- | --- |
| H01 热带气旋 | D01,D02,D47,D50；D03,D04,D73 | 601 | NHC 已有种子/公告；全球 IBTrACS SID；CyPortQA 3 风暴图文 | 新增亚洲/南半球独立风暴；best-track/outcome 隔离；不复用受保护风暴 |
| H02 温带风暴/非对流大风 | D05,D27；D28,D48,D67 | 10054 | 强风报告及 ISD 风记录可读 | 需非对流分类证据；不能将全部雷达 storm 叫温带气旋；风速/阵风分开 |
| H03 雷暴大风/下击暴流 | D05,D06,D49；D08,D09,D48 | 36770 | 灾害报告、VIL 序列；SPC MD 原文 | 缺地面风与雷达联合窗口；下击暴流需特定证据 |
| H04 龙卷风 | D05,D07；D06,D08,D49 | 3067 | 龙卷报告；TorNet 3 个负例可读 | TorNet 正例 0；核对 v1.1 修订和同一风暴负例 |
| H05 冰雹 | D05,D06；D09,D48,D70 | 18033 | 真实冰雹目录标签；SEVIR 2 条 Hail VIL | 补地面直径/报告与雷达 MESH 时空匹配 |
| H06 强雷电 | D10；D06,D05 | 506 | 3 个 GLM 产品，flash/group/event 可读并检父子关系 | 尚未验证极端密度；需当地时间/面积基线及跨文件去重 |
| H07 极端降水 | D26,D30,D59；D09,D29,D47 | 2237 | 站点雨量、CHIRPS 2 日、MeteoNet 实测资料 | 日累计/分钟率不可混用；本轮栅格窗口未被认定极端 |
| H08 河洪/山洪/城市内涝 | D05,D15,D56,D60,D61；D12,D13,D14,D16,D17,D51 | 13299 | 站点流量、Caravan 时序、Sen1 标签及 HANZE | GEOID 新样本洪水正像素 0；城市内涝、道路状态、永久水体需独立验证 |
| H09 风暴潮/沿岸淹没 | D37,D05；D01,D18,D58,D69 | 513 | 3 站 720 对潮位/预测匹配 | 潮汐残差不是纯风暴潮；尚未取得独立沿海淹没掩膜及阈值 |
| H10 热浪 | D26,D48；D47,D25,D34 | 10550 | Heathrow 窗口、EWB 热浪定义和小时观测 | ExEBench heatwave 包未下载；本地气候态和持续时间待补，LST 单列 |
| H11 寒潮/极端低温/霜冻 | D47,D26,D27；D48,D28 | 3349 | ExEBench 9 案例/559 时间步，Houston 站温 | 寒潮骤降、绝对低温、霜冻分开定义；空间均值定义与跨国事件去重 |
| H12 暴雪/积雪/冰冻/冻雨 | D05,D26,D55；D27,D33,D49 | 18361 | 暴雪等灾害报告；Buffalo 站点雪量、SNODAS SWE | 冻雨和吹雪现象码样例为 0；雪盖/积雪不可填补全部冬季细类 |
| H13 干旱/闪旱 | D31,D52；D30,D32,D60,D62 | 9898 | 3 周 USDM；DroughtED 26,666 行前缀 | 周标签含连续小数；实际 split 与文档不一致；闪旱快速恶化定义待核 |
| H14 沙尘暴 | D05,D27；D35,D36,D63 | 195 | 有沙尘暴灾害报告；ISD 276 条浮尘/扬沙现象码 | ISD 本批沙尘暴码正例 0；必须补 dust-specific 栅格和地面暴尘窗口 |
| H15 浓雾/极端低能见度 | D27,D05；D53,D63 | 1105 | ISD 34 条带合格能见度的雾码报告 | 海雾 cube 未验证；极端低能见度阈值、持续时间及烟/沙尘排除待补 |
| H16 野火/天气相关火险 | D19,D23；D20,D21,D22,D24,D65 | 649 | WildfireSpreadTS 3 日、FIRMS 热点、TS-SatFire 3 日 | 每组仅 1 火场；火点/烧痕/火险分开；天气相关不等于自然或极端天气致火 |

扩展：海洋热浪使用 D38；降雨滑坡使用 D46，但降雨因果尚未建立。火山、地震、海啸不纳入主表。2023 Storm Events 中 7 条 Volcanic Ashfall 不计入这 16 类。

目前非美国证据包括 ExEBench 寒潮的 8 国/地区、北京与沙特站点、英国和澳大利亚站点、法国 MeteoNet、欧洲 HANZE、德国 GEOID/CEMS、印度与柬埔寨 Sen1Floods11。它们未形成全球均衡的事件分布；全球栅格覆盖也不能当作已验证全球极端事件。


---

来源文件：`plans/v6_0911_dataset_selection/SOURCE_FEASIBILITY.md`

# 数据源选择与实测可行性

本表保留用户 V6 的 D01–D54，并把此前实际调查中的互补来源登记为 D55–D74。共 74 个登记项，包含 benchmark、产品和派生资料；不是 74 个独立传感器，也不是全部已下载。判定来自 SOURCE_REGISTRY.json、CAPTURE_INDEX.jsonl、两份离线审计和继承复核文件。

五个独立轴为 access、content、provenance、license、task_eligibility。推荐进入开发池表示优先完成适配和准入，所有新正式任务数仍为 0。C0–C7 中 candidate 表示已有相关证据但尚未通过对应任务规则。

| 来源 | 建议 | 实测内容层 | 访问层 | 选择依据与缺口 |
| --- | --- | --- | --- | --- |
| D01 NHC Public / Forecast Advisories + GIS | 优先数据开发池 | inherited | inherited_local_sample | 复用已有 NHC 公告/GIS 和 Francine 种子；新增风暴独立分组；issued_at 不等于历史 available_at。 |
| D02 IBTrACS v4r01 | 定向桥接 | numeric | response_captured | 已解码 21,923 条轨迹、378 个 SID；属于事后参考，隔离 outcome；跨机构及跨盆地去重。 |
| D03 Digital Typhoon V2 | 条件候选 | partial | response_captured | Digital Typhoon ZIP Range 获取未完成；保留亚洲气旋扩容路线，不把目录计为帧。 |
| D04 TCIR | 暂缓 | reference | response_captured | TCIR 仅入口/读取器候选；尚未完成真实影像解码，需确认版本和切分。 |
| D05 NOAA Storm Events Database | 优先数据开发池 | catalog | response_captured | 136,982 条灾害报告仅作检索索引；EPISODE_ID 不等于独立天气系统；需要气象事件跨县合并。 |
| D06 SEVIR | 优先数据开发池 | inherited | inherited_local_sample | 复核 3 条 VIL 序列，每条 49 帧；不能据此声称已验证闪电/光学多模态；补地面报告桥接。 |
| D07 TorNet | 条件候选 | numeric | response_captured | 3 个 TorNet train NetCDF 均为 NUL 负例；核对 v1.1 修订并获取正例和匹配困难负例。 |
| D08 NOAA NEXRAD | 定向桥接 | unverified | not_runtime_probed | NEXRAD 原始体扫尚无本轮解码样本；优先按 TorNet/SEVIR 具体雷达时刻补取。 |
| D09 NOAA MRMS | 定向桥接 | metadata | response_captured | MRMS 桶目录可列，尚无实际 MESH/降水文件；不能将 MESH 估计直接等同地面冰雹报告。 |
| D10 GOES-R ABI / GLM archives | 优先数据开发池 | numeric | response_captured | 3 个 GLM 20 秒文件及父子 ID 已校验；须构建空间密度基线并补极端窗口；ABI 尚未取样。 |
| D11 Global Flood Database v1 | 条件候选 | reference | requests_failed_or_incomplete | GFD 入口明确但没有实际事件栅格；GEE 项目访问与公开替代产品分开记录。 |
| D12 GEOID-Flood | 条件候选 | paired | response_captured | 3 组前后 SAR/标签/有效性完整匹配同一发布清单，但洪水正像素均为 0；同一 EMSR712/AOI10 且原 split 为 test，仅作已观察审计材料。 |
| D13 KuroSiwo | 条件候选 | unverified | requests_failed_or_incomplete | KuroSiwo 的 HF 连接失败；下一轮锁定版本后仅取 train 正负样例，不承诺整个数据不可用。 |
| D14 UrbanSARFloods | 条件候选 | unverified | requests_failed_or_incomplete | UrbanSARFloods 的 HF 连接失败；保留城市内涝候选，必须验证城市标签/事件身份。 |
| D15 Sen1Floods11 v1.1 | 条件候选 | inherited | inherited_local_sample | 已复核 3 个 Sen1Floods11 图像标签对、2 个事件地区；许可字段存在歧义，先澄清数据再分发条款。 |
| D16 SpaceNet 8 | 条件候选 | reference | response_captured | SpaceNet8 读取文档可得；本轮未获取成对影像/道路标签，需保留原 split 并分开洪水与道路状态语义。 |
| D17 FloodNet | 条件候选 | reference | response_captured | FloodNet 文档可得，真实图像/标签未取样；无人机图像多样性不等于多个风暴。 |
| D18 CEMS Rapid Mapping | 定向桥接 | catalog | response_captured | CEMS EMSR712/AOI10 产品与影像时刻已列举；部分版本状态 N、无产品，不能当成成功下载或同目标修订。 |
| D19 WildfireSpreadTS | 优先数据开发池 | numeric | response_captured | 3 天同一火场 TIFF；按作者读取器复算活动火像素 4/0/0；需新增独立火场、正例与火灭/缺测区别。 |
| D20 Next Day Wildfire Spread | 条件候选 | partial | response_captured | Next Day Wildfire ZIP 前缀已取得，TFRecord 尚未解码；需字段、CRC 和标签时距核验。 |
| D21 TS-SatFire | 条件候选 | numeric | response_captured | TS-SatFire 3 天同一火场 19 波段栅格可解码；最终标签通道和未来标签切片仍需读取器验证。 |
| D22 Sen2Fire | 条件候选 | unverified | not_runtime_probed | Sen2Fire 尚未获取实际图像；只在需要独立火场/新地区时补源，不与同源火点重复计数。 |
| D23 NASA FIRMS | 优先数据开发池 | numeric | response_captured | 公开 FIRMS VIIRS CSV 可匿名取得；2,606 条为热点，不是 2,606 场野火；归因与事件分组待完成。 |
| D24 MTBS burned-area boundaries | 定向桥接 | unverified | requests_failed_or_incomplete | MTBS 公开直链尝试失败；不必把 GEE 作为唯一入口，后续检查官方周界产品和许可。 |
| D25 ERA5-Land Hourly | 条件候选 | unverified | not_runtime_probed | ERA5-Land 未实际验证；已有 WeatherBench2 ERA5 chunk 不能代替 ERA5-Land 认证与变量验证。 |
| D26 GHCN-Daily | 优先数据开发池 | numeric | response_captured | 5 个站点窗口 40 站日已解析；Toronto 查询为空；需季节基准、日界、质量标记和缺测规则。 |
| D27 ISD / Global Hourly | 优先数据开发池 | numeric | response_captured | 北京和沙特两个站年 28,733 报告；实有雾及浮/扬尘码，未发现本批沙尘暴/冻雨码正例。 |
| D28 NOAA GFS0P25 | 定向桥接 | numeric | response_captured | 已从公开 S3 读 GFS 3 个变量 GRIB；仅同一次初始化 f000，不是多轮修订或 3 场极端。 |
| D29 GPM IMERG V07 | 条件候选 | unverified | not_runtime_probed | IMERG V07 尚无实测切片；CHIRPS DAILY_SAT 对 IMERG 的依赖不代表独立 IMERG 取样成功。 |
| D30 CHIRPS v3 DAILY_SAT | 优先数据开发池 | numeric | response_captured | CHIRPS v3 DAILY_SAT 完成 2 个日栅格，第三日未完成；补站点、有效值编码与产品版本说明。 |
| D31 US Drought Monitor | 优先数据开发池 | inherited | inherited_local_sample | USDM 3 个周次已复核；采用已有专家标注，不新增逐题人工复核；不能把周次算独立干旱过程。 |
| D32 SMAP Enhanced L3 Soil Moisture | 条件候选 | unverified | not_runtime_probed | SMAP 无实测土壤湿度切片；干旱/闪旱升级时再补，先确认冻土/植被与质量标记。 |
| D33 MODIS Snow MOD10A1.061 | 条件候选 | unverified | not_runtime_probed | MODIS Snow 未实测；雪盖与降雪/暴雪/冻雨分开，当前 SNODAS 可作为积雪补源。 |
| D34 MODIS LST MOD11A1.061 | 条件候选 | unverified | not_runtime_probed | MODIS LST 未实测；地表温度不能替代 2 米气温热浪标签。 |
| D35 MERRA-2 aerosol diagnostics | 定向桥接 | reference | response_captured | MERRA-2 气溶胶仅文档与入口；优先补 dust 专属变量并与现象码配对，不能以高 AOD 单独判沙尘暴。 |
| D36 Sentinel-5P OFFL Aerosol Index | 条件候选 | unverified | not_runtime_probed | S5P Aerosol Index 尚无实际切片；需将沙尘、烟羽、云和缺测区分。 |
| D37 NOAA CO-OPS water levels | 优先数据开发池 | numeric | response_captured | 3 个潮位站各 240 对同基准面观测/潮汐预报已匹配；残差含多种作用，不能单独称纯风暴潮。 |
| D38 NOAA OISST v2.1 | 扩展灾种 | numeric | response_captured | OISST 3 个日 NetCDF 可读；海洋热浪为扩展方向，需长期气候态与持续性定义。 |
| D39 EM-DAT | 暂缓 | unverified | not_runtime_probed | EM-DAT 注册和许可入口；不绕过访问条件；ExEBench 的案例 ID 也需检查派生使用条款。 |
| D40 NASA EONET v3 | 定向桥接 | unverified | not_runtime_probed | EONET 为事件检索备选，尚未有本轮解码事件；不能将事件目录当像素 Gold。 |
| D41 GDACS | 定向桥接 | unverified | not_runtime_probed | GDACS 仅候选入口，当前未验证实际 feed；如已有 CEMS GDACS ID 再定向桥接。 |
| D42 Sentinel-1 GRD | 定向桥接 | inherited_component | derived_component_only_raw_access_not_tested | S1 派生资产已在洪水数据中验证；独立原始 GRD/GEE 访问未验证，不重复算独立来源增量。 |
| D43 Sentinel-2 SR Harmonized | 定向桥接 | unverified | not_runtime_probed | S2 原始 SR 访问尚未验证；现有 SAR/背景切片不代表其可用，按事件补光学和云质量层。 |
| D44 xBD | 暂缓 | unverified | response_captured | xBD 有注册/许可门槛；建筑损伤属于下游影响，且需排除地震等非天气灾种。 |
| D45 CrisisMMD v2.0 | 暂缓 | reference | response_captured | CrisisMMD 仅入口候选；社交图像版权和文本真实性尚未落实，不作为因果真值。 |
| D46 Landslide4Sense | 扩展灾种 | paired | response_captured | Landslide4Sense 已验证 3 个 train 图像掩膜对；HDF5 缺时空/事件属性，降雨诱发成因仍未确认。 |
| D47 ExEBench / EarthExtreme-Bench | 优先数据开发池 | numeric | response_captured | 固定 commit 的寒潮 ZIP 完整校验：9 案例、559 时间步、8 国家/地区；其他六个子包未下载，ERA5/EM-DAT 来源与极端定义待核。 |
| D48 ExtremeWeatherBench | 优先数据开发池 | numeric | response_captured | EWB 解码 329 案例定义及 GHCN-hourly 一个 row group 122,880 行；尚未把该观测组匹配到 EWB 极端案例。 |
| D49 WeatherQA | 定向桥接 | reference | response_captured | WeatherQA 的 Drive 下载失败；SPC 2018/md0398 原文可取回；README 的 20 幅图是变量组，不是 20 个时刻。 |
| D50 CyPortQA | 条件候选 | multiformat | response_captured | CyPortQA 已取得 Dorian/Harvey/Florence 各 1 图 1 文；精确公告时刻对齐及港口标签规则尚未验证。 |
| D51 WorldFloods v2 / ml4floods | 条件候选 | unverified | requests_failed_or_incomplete | WorldFloods v2 的 HF 数据连接未完成；保留为全球光学洪水备选，核验每类源产品的许可。 |
| D52 DroughtED | 条件候选 | prefix_records | response_captured | DroughtED train ZIP 前缀解析 26,666 行，含 3,809 非空周标签；实际至 2016 与文档 train 2000-2009 冲突；需固定原文件切分。 |
| D53 M4Fog | 条件候选 | reference | response_captured | M4Fog 仓库和网盘页可读，未取到真实 cube；镜像身份/条款和海雾正例均未完成验证。 |
| D54 CLLMate | 辅助背景 | catalog | response_captured | CLLMate 公共 JSON 7,747 节点已解析；包括非天气事件；新闻/原图与因果边未验证，不作因果 Gold。 |
| D55 SNODAS SWE | 优先数据开发池 | numeric | response_captured | SNODAS 3 日 SWE 网格已解码；积雪不是暴雪/冻雨，32767 编码上限须结合产品说明。 |
| D56 USGS Water Data | 优先数据开发池 | numeric | response_captured | USGS 3 站各 3 条流量记录，9 条真实记录；返回日期不连续且不代表最新；需按洪水窗口重取。 |
| D57 NWPS Stageflow | 定向桥接 | numeric | response_captured | NWPS 3 站阶段水位可解析，流量字段 -999；BTRL1 未提供 usgsId，不能自动接到附近 USGS 站。 |
| D58 NDBC Buoys | 定向桥接 | numeric | response_captured | NDBC 3 个浮标波高可解析；多条报告仍需按风暴/站点配对，波高不等于风暴潮。 |
| D59 MeteoNet | 优先数据开发池 | numeric | response_captured | MeteoNet 111,623 站报/484 站及 IR108 数组可读；雷达 NPZ object 时间不启用 pickle，时间桥接未完成。 |
| D60 Caravan | 优先数据开发池 | numeric | response_captured | Caravan 3 个 CAMELS 美国流域各 14,609 日；流域属性/单位/极端阈值待补，ERA5-Land 驱动不是独立真值。 |
| D61 HANZE v2.1 | 优先数据开发池 | catalog | response_captured | HANZE 2,521 欧洲洪水影响记录、40 国；用于非美国检索与类型校验，事件族去重另做。 |
| D62 Dheed | 定向桥接 | catalog | response_captured | Dheed 82,839 派生干热事件记录可读；先查上游依赖和定义，不能作为另一份独立观测真值。 |
| D63 DAWN | 辅助背景 | metadata | response_captured | DAWN 官方 API 枚举 Fog/Rain/Sand/Snow 四包；未抽取图片，时间/地点不足时仅作视觉条件辅助集。 |
| D64 SenForFlood | 条件候选 | background | response_captured | SenForFlood TAR 前缀取得 3 个 LULC TIFF；目前仅背景层，不是三组洪水图像标签对。 |
| D65 FPA-FOD6 | 定向桥接 | inherited | inherited_local_sample | FPA-FOD6 已复核 3 条火灾记录；与 FIRMS、火烧迹地按事件合并，起火原因不能默认极端天气。 |
| D66 WeatherBench2 ERA5 | 定向桥接 | inherited | inherited_local_sample | WeatherBench2 一个 ERA5 温度 chunk 已复核；记录为 ERA5 衍生产品，不冒充 D25 ERA5-Land。 |
| D67 HRRR | 定向桥接 | numeric | response_captured | HRRR 已读同一次初始化 3 个 GRIB 变量；若做修订需同 valid_time 的多 init_time，当前未证实。 |
| D68 HKO-7 | 条件候选 | catalog | response_captured | HKO-7 仓库日天气统计 2,556 行可读；实际雷达序列尚未取样。 |
| D69 GESLA current / GESLA-3 candidate | 定向桥接 | metadata | response_captured | GESLA 站点目录可读；现端点报告 format 5.0/2026，不能标作 GESLA-3；潮位实际切片未取回。 |
| D70 ESWD | 暂缓 | unverified | not_runtime_probed | ESWD 适合补欧洲龙卷/冰雹，但本轮未获得许可明确的批量样本。 |
| D71 CAMELSH | 条件候选 | metadata | response_captured | CAMELSH 发布元数据候选；未解码水文时序，需确认与 Caravan/CAMELS 的派生重叠。 |
| D72 MSETCD / MSCAR | 条件候选 | reference | response_captured | MSETCD/MSCAR 读取器或目录候选；未验证实际图像，用于后续亚洲气旋补源。 |
| D73 CMA Best Track | 条件候选 | reference | requests_failed_or_incomplete | CMA 最佳路径入口已登记；尚无完整样例解码，仅作未来多机构事后对照。 |
| D74 NOAA Billion-Dollar Disasters | 辅助背景 | reference | response_captured | NOAA Billion-Dollar 仅影响事件索引候选；经济损失阈值造成地区偏差，不定义全球气象极端。 |

## 权利与来源的独立检查

| 来源 | 当前状态 | 范围 |
| --- | --- | --- |
| D01 | official_public_data_terms_to_document | Official public endpoint reachable or registered; per-product attribution and third-party exceptions remain to document |
| D02 | not_fully_verified | Planning links/README do not establish rights to redistribute every upstream asset |
| D03 | not_fully_verified | Planning links/README do not establish rights to redistribute every upstream asset |
| D04 | not_fully_verified | Planning links/README do not establish rights to redistribute every upstream asset |
| D05 | official_public_data_terms_to_document | Official public endpoint reachable or registered; per-product attribution and third-party exceptions remain to document |
| D06 | not_fully_verified | Planning links/README do not establish rights to redistribute every upstream asset |
| D07 | not_fully_verified | Planning links/README do not establish rights to redistribute every upstream asset |
| D08 | official_public_data_terms_to_document | Official public endpoint reachable or registered; per-product attribution and third-party exceptions remain to document |
| D09 | official_public_data_terms_to_document | Official public endpoint reachable or registered; per-product attribution and third-party exceptions remain to document |
| D10 | official_public_data_terms_to_document | Official public endpoint reachable or registered; per-product attribution and third-party exceptions remain to document |
| D11 | not_fully_verified | Planning links/README do not establish rights to redistribute every upstream asset |
| D12 | provider_license_captured | CC-BY-4.0 in pinned dataset README; inherited manual labels; upstream/product conditions still checked per asset |
| D13 | not_fully_verified | Planning links/README do not establish rights to redistribute every upstream asset |
| D14 | not_fully_verified | Planning links/README do not establish rights to redistribute every upstream asset |
| D15 | unresolved | Repository/STAC dataset license ambiguity; do not equate code license with data license |
| D16 | not_fully_verified | Planning links/README do not establish rights to redistribute every upstream asset |
| D17 | not_fully_verified | Planning links/README do not establish rights to redistribute every upstream asset |
| D18 | not_fully_verified | Planning links/README do not establish rights to redistribute every upstream asset |
| D19 | data_terms_pending | Author reader verified; data publication terms still to be pinned |
| D20 | not_fully_verified | Planning links/README do not establish rights to redistribute every upstream asset |
| D21 | not_fully_verified | Planning links/README do not establish rights to redistribute every upstream asset |
| D22 | not_fully_verified | Planning links/README do not establish rights to redistribute every upstream asset |
| D23 | not_fully_verified | Planning links/README do not establish rights to redistribute every upstream asset |
| D24 | not_fully_verified | Planning links/README do not establish rights to redistribute every upstream asset |
| D25 | not_fully_verified | Planning links/README do not establish rights to redistribute every upstream asset |
| D26 | official_public_data_terms_to_document | Official public endpoint reachable or registered; per-product attribution and third-party exceptions remain to document |
| D27 | official_public_data_terms_to_document | Official public endpoint reachable or registered; per-product attribution and third-party exceptions remain to document |
| D28 | official_public_data_terms_to_document | Official public endpoint reachable or registered; per-product attribution and third-party exceptions remain to document |
| D29 | not_fully_verified | Planning links/README do not establish rights to redistribute every upstream asset |
| D30 | not_fully_verified | Planning links/README do not establish rights to redistribute every upstream asset |
| D31 | not_fully_verified | Planning links/README do not establish rights to redistribute every upstream asset |
| D32 | not_fully_verified | Planning links/README do not establish rights to redistribute every upstream asset |
| D33 | not_fully_verified | Planning links/README do not establish rights to redistribute every upstream asset |
| D34 | not_fully_verified | Planning links/README do not establish rights to redistribute every upstream asset |
| D35 | not_fully_verified | Planning links/README do not establish rights to redistribute every upstream asset |
| D36 | not_fully_verified | Planning links/README do not establish rights to redistribute every upstream asset |
| D37 | official_public_data_terms_to_document | Official public endpoint reachable or registered; per-product attribution and third-party exceptions remain to document |
| D38 | official_public_data_terms_to_document | Official public endpoint reachable or registered; per-product attribution and third-party exceptions remain to document |
| D39 | registration_and_terms_required | No authenticated dataset access attempted |
| D40 | not_fully_verified | Planning links/README do not establish rights to redistribute every upstream asset |
| D41 | not_fully_verified | Planning links/README do not establish rights to redistribute every upstream asset |
| D42 | not_fully_verified | Planning links/README do not establish rights to redistribute every upstream asset |
| D43 | not_fully_verified | Planning links/README do not establish rights to redistribute every upstream asset |
| D44 | registration_and_terms_required | xBD terms and release conditions pending |
| D45 | not_fully_verified | Planning links/README do not establish rights to redistribute every upstream asset |
| D46 | not_fully_verified | Planning links/README do not establish rights to redistribute every upstream asset |
| D47 | upstream_rights_pending | HF package downloaded; ERA5 and EM-DAT derivative conditions not yet cleared |
| D48 | not_fully_verified | Planning links/README do not establish rights to redistribute every upstream asset |
| D49 | not_fully_verified | Planning links/README do not establish rights to redistribute every upstream asset |
| D50 | repository_license_only | GitHub LICENSE captured; individual NHC products and derived QA rights separate |
| D51 | not_fully_verified | Planning links/README do not establish rights to redistribute every upstream asset |
| D52 | provider_license_captured | Kaggle metadata CC0; attribution/terms of NASA POWER, USDM and soil inputs retained |
| D53 | not_fully_verified | Planning links/README do not establish rights to redistribute every upstream asset |
| D54 | not_fully_verified | Planning links/README do not establish rights to redistribute every upstream asset |
| D55 | official_public_data_terms_to_document | Official public endpoint reachable or registered; per-product attribution and third-party exceptions remain to document |
| D56 | official_public_data_terms_to_document | Official public endpoint reachable or registered; per-product attribution and third-party exceptions remain to document |
| D57 | official_public_data_terms_to_document | Official public endpoint reachable or registered; per-product attribution and third-party exceptions remain to document |
| D58 | official_public_data_terms_to_document | Official public endpoint reachable or registered; per-product attribution and third-party exceptions remain to document |
| D59 | not_fully_verified | Planning links/README do not establish rights to redistribute every upstream asset |
| D60 | not_fully_verified | Planning links/README do not establish rights to redistribute every upstream asset |
| D61 | not_fully_verified | Planning links/README do not establish rights to redistribute every upstream asset |
| D62 | not_fully_verified | Planning links/README do not establish rights to redistribute every upstream asset |
| D63 | not_fully_verified | Planning links/README do not establish rights to redistribute every upstream asset |
| D64 | provider_license_captured | Dataverse CC-BY-SA-4.0 metadata; current assets are LULC only |
| D65 | not_fully_verified | Planning links/README do not establish rights to redistribute every upstream asset |
| D66 | not_fully_verified | Planning links/README do not establish rights to redistribute every upstream asset |
| D67 | official_public_data_terms_to_document | Official public endpoint reachable or registered; per-product attribution and third-party exceptions remain to document |
| D68 | not_fully_verified | Planning links/README do not establish rights to redistribute every upstream asset |
| D69 | not_fully_verified | Planning links/README do not establish rights to redistribute every upstream asset |
| D70 | not_fully_verified | Planning links/README do not establish rights to redistribute every upstream asset |
| D71 | not_fully_verified | Planning links/README do not establish rights to redistribute every upstream asset |
| D72 | not_fully_verified | Planning links/README do not establish rights to redistribute every upstream asset |
| D73 | not_fully_verified | Planning links/README do not establish rights to redistribute every upstream asset |
| D74 | not_fully_verified | Planning links/README do not establish rights to redistribute every upstream asset |

## 可重放证据

- 原始入口和失败/重试记录：CAPTURE_INDEX.jsonl；逐次 HTTP 回执在两个 bundle 的 attempts/。
- 数组、字段、日期和计数：analysis/DOWNLOADED_AUDIT.json、analysis/SELECTION_AUDIT.json。
- 每个本地资产及哈希：FILE_MANIFEST.jsonl。返回 206 完整 Range 不表示完整归档。
- 不能自动外推成功率：本轮是目录开头或已知事件的便利抽样，未做随机抽样。
- 许可不明确的来源保持候选；公开可下载不等于可以直接重新分发。


---

来源文件：`plans/v6_0911_dataset_selection/RELATED_BENCHMARK_COMPARISON.md`

# 已有 benchmark 的复用与研究差异

本表依据已捕获的作者文档、目录、读取器和样例，服务于数据选择。只声明核验到的能力；没有把“本次未发现”写成“原项目完全不支持”。独立首创性/发表新颖性仍需完整文献检索。

| 对照项目 | 已实查的资料 | 值得复用 | DisasterTrace 需要补的研究层 |
| --- | --- | --- | --- |
| [ExEBench / EarthExtreme-Bench](https://github.com/zhaoshan2/EarthExtreme-Bench) | 固定 HF commit 的寒潮包、数值序列读取器、配置；9 个病例 NetCDF/CSV | 多灾种变量与数值资料组织；非美国病例；空间温度场 | 面向 LLM/VLM 的证据阅读、时效状态、冲突/未知处理；同一案例不增加来源独立性 |
| [ExtremeWeatherBench](https://github.com/brightbandtech/ExtremeWeatherBench) | 329 个事件定义、数据适配代码、小时地面观测 row group | 独立事件配置、观测/预报/参考产品分层、真实极端定义 | 把案例与具体证据包配对；区分模型天气预报成绩与 LLM 读取/推理成绩 |
| [WeatherQA](https://github.com/chengqianma/WeatherQA) | 文档中的 20 参数地图组织；SPC MD0398 原文；Drive 数据失败 | 地图和气象业务文本关联方式、上游产品入口 | 同一地图分析时间 17:00Z 与正文发行 17:56Z 必须分开；图文任务需要确定性可评分标签，开放解释不作 Gold |
| [CyPortQA](https://github.com/ChenchenMobility/MLLM-Bench-CyPortQA) | Dorian/Harvey/Florence 各一图一文、模板、LICENSE | 气旋图文格式、港口情境与业务问题模板 | 先逐产品核对时刻，再考虑行动问题；港口关闭/开放要有显式政策及外部状态依据 |
| [GEOID-Flood](https://github.com/links-ads/geoid-flood) | 3 组 12 个对齐资产、发布清单哈希、CEMS activation/AOI | 三类标签、前后 SAR、有效区域和事件来源链 | 像素标签转为确定性空间/状态问题；私有 Gold-derived validity 隔离；补真正正例及新事件 |
| [CLLMate](https://github.com/hobolee/CLLMate) | 公共 JSON 中的节点、日期、坐标与新闻/图像路径字段 | 事件检索和跨媒体关联候选 | 新闻/图像未取回、因果边未核验，不能继承为 causal Gold；优先做证据支持程度判断 |
| [TorNet](https://github.com/mit-ll/tornet) | 作者读取器/发布说明及 3 个完整负例雷达文件 | 雷达序列、事件身份与难负例 | 先核正例与 v1.1，再建立地面确认/雷达表现/LLM 答案的分层评估 |
| [WildfireSpreadTS](https://github.com/SebastianGer/WildfireSpreadTS) | 作者读取器及 3 个相邻日 TIFF | 同一事件的真实演化、活动火探测时刻解释 | 分开探测/无探测/覆盖缺失；审计输入预报的 as-of 信息；避免将火灾成因默认标为天气 |

推荐论文主问题：同一极端天气事件中，当图像、观测和官方产品具有不同时间、空间支撑范围与可靠性时，LLM/VLM 能否给出有依据的状态结论，随有效证据更新，并在证据不足时正确保留未知？

该问题需要用以下方法落实，才能超过现有资料拼接：

1. 将物理过程演化、同目标预报修订、受控证据交付分别建集与计分。
2. 固定事件与答案，控制过期证据、矛盾证据、重复来源、缺失模态，形成可解释的成对诊断。
3. 保留 oracle structured evidence 与原始影像输入对照，分离感知错误和推理/更新错误。
4. 用独立事件族、跨地区和跨灾种留出测试衡量泛化，避免按帧/瓦片/问题重写扩大有效样本数。
5. 以来源和确定性规则产生 Gold；允许披露来源的已有专家/人工数据集标注，不新增逐题人工复核。

当前证据支持以上研究定位；其优势大小、必要的任务规模和相对于所有相关工作的创新范围，仍要由后续系统文献检索及冻结实验确定。


---

来源文件：`plans/v6_0911_dataset_selection/REUSE_AND_GAPS.md`

# 复用现有实现与需要增加的接口

现有仓库已经有真实多模态实现，不能再沿用“尚无 MM 框架”的旧结论。已读取 `disastertrace-starter/README_MULTIMODAL_V1.md`、`CURRENT_PHASE.md`、`multimodal_v1/types.py` 和实际 admission；本轮未修改这些冻结模块。

| 现有部分 | 可以复用 | 还要补什么 |
| --- | --- | --- |
| multimodal_v1: ArtifactMeta、FactKey、DeliveryEvent、QuerySpec | 源资产、语义键、交付、确定性查询的已有协议 | 通用变量/单位/时间支撑区间；FactKey.threshold_kt 不能直接用于温度/雨量/土壤湿度 |
| NHC/MM 原始获取、存储、空间参考 | 哈希、官方产品、矢量参考及受控投递分支 | 扩展 source adapter；原生图像解读单列，不将数据重绘误标为原始卫星 |
| active_forecast exact kernel | 确定性计数、面积、修订运算及已有评分约束 | 各灾种 source admission；状态、输入、私有标签的运行时隔离；新增预算规则另行验收 |
| 现有受保护配置和源 manifest | 冻结样例/保护 ID 的继承 | 同一物理事件、重叠瓦片/时窗、跨 benchmark 资产重复的完整图 |
| 当前匿名有界下载、Range、解码脚本 | 捕获回执、失败、断点拼接、局部读、哈希及已有标签检查 | 重复运行的增量注册、provider schema 漂移检查、正负样例策略及测试覆盖 |

建议只增加数据准入/桥接层，不重写 benchmark 框架。最小数据记录应包含 source/version、artifact SHA256、变量和单位、valid time/issue time/retrieved time、空间范围/CRS、缺测/QC、原始 split、event ID、label authority、rights、parent products。historical_available_at 没有证据就保留 null。

三种图分开：physical-event graph 用于跨源事件切分；asset-reuse graph 用于重复影像、裁剪和派生资产防泄漏；source-dependency graph 用于独立证据声明。共享 ERA5 不会把所有天气事件连接成一个簇。

Gold 采用确定性记录读取、阈值/持续时间算法、空间运算及已有官方/公开数据集标签。允许已有专家标签并标注来源，例如 USDM、洪水人工掩膜；不新增逐题人工复核，也不使用 LLM judge 决定事实。数据发生冲突、时空或许可不能确定时，自动拒绝该题或显式输出 unknown，不能用模型补造真值。

未完成：多灾种通用 adapter、概率/分层抽样、全量事件去重、正式 train/dev/test、严格 as-of、原生影像必要性检查、跨灾种 Gold 一致性测试，以及新增模型实验。本轮的资产可解码不代表上述能力已实现。


---

## 代码：plans/v6_0911_dataset_selection/audit_selection.py

```python
"""Reproduce V6 sample checks using captured bytes only, without external code execution."""

import base64
import csv
import hashlib
import io
import json
import re
import struct
import sys
import zipfile
import zlib
from collections import Counter
from datetime import datetime
from pathlib import Path

import netCDF4
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import rasterio
from PIL import Image

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
PRIOR = ROOT.parent / "multihazard_source_validation_20260911"
V5 = ROOT.parent / "v5_0910_source_probe_20260910"
sys.path.insert(0, str(PRIOR))
from validate_samples import captures, geotiff_sample, netcdf_sample, require


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(path.read_text())


def collect(root):
    specs = {s["id"]: s for p in root.glob("specs/*.json") for s in read(p).get("probes", [])}
    result = {}
    for path in sorted(root.glob("batches/*/*.json")):
        r = read(path)
        if "final" not in r:
            continue
        spec = specs.get(r["id"], {"id": r["id"], "kind": r["kind"], "url": r["requested_url"]})
        response = r["final"]
        body = (root / response["attempt_path"] / "body.bin").read_bytes()
        require(sha(body) == response["body_sha256"], "capture hash mismatch")
        require(len(body) == response["captured_bytes"], "capture size mismatch")
        result[r["id"]] = spec, response, body
    return result


class CapturedRanges(io.RawIOBase):
    """A local sparse reader that refuses access to bytes never downloaded."""

    def __init__(self, length, blocks):
        self.length, self.blocks, self.pos = length, blocks, 0

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=0):
        self.pos = offset if whence == 0 else self.pos + offset if whence == 1 else self.length + offset
        require(0 <= self.pos <= self.length, "seek outside object")
        return self.pos

    def read(self, size=-1):
        size = min(size if size >= 0 else self.length - self.pos, self.length - self.pos)
        for start, data in self.blocks:
            if start <= self.pos and self.pos + size <= start + len(data):
                result = data[self.pos - start:self.pos - start + size]
                self.pos += size
                return result
        raise ValueError("read of uncaptured bytes")


def main():
    rows = collect(ROOT)
    old = captures()
    refs = ROOT / "references"
    refs.mkdir(exist_ok=True)
    reports = []

    def checked(ident):
        spec, response, body = rows[ident]
        require(response["complete"] and response["http_status"] in (200, 206) and body, "incomplete HTTP asset: " + ident)
        return body

    def check(ident, source, func):
        result = {"id": ident, "source": source, "level": "not_validated"}
        try:
            result["details"] = func()
            result["level"] = "verified"
        except Exception as exc:
            result.update(error_type=type(exc).__name__, error=str(exc))
        reports.append(result)

    for ident, (spec, response, body) in rows.items():
        if spec["kind"] == "github_blob" and response["complete"] and response["http_status"] == 200:
            obj = json.loads(body)
            raw = base64.b64decode(obj["content"])
            blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
            require(blob == obj["sha"] == spec["url"].rsplit("/", 1)[-1], "Git blob verification")
            (refs / (ident + ".bin")).write_bytes(raw)

    def lightning():
        samples = []
        for i in range(3):
            ident = f"D10-glm-{i}"
            data = checked(ident)
            with netCDF4.Dataset("glm", memory=data) as ds:
                entry = {"capture_id": ident, "sha256": sha(data), "start": ds.time_coverage_start,
                         "end": ds.time_coverage_end, "counts": {}, "quality_flags": {}}
                for unit in ["flash", "group", "event"]:
                    values = ds[unit + "_id"][:]
                    entry["counts"][unit] = len(values)
                    require(len(np.unique(values)) == len(values), "duplicate GLM ID within product")
                for child, parent in [("event", "group"), ("group", "flash")]:
                    require(np.isin(ds[f"{child}_parent_{parent}_id"][:], ds[parent + "_id"][:]).all(), "GLM parent missing")
                for unit in ["flash", "group"]:
                    values, counts = np.unique(ds[unit + "_quality_flag"][:], return_counts=True)
                    entry["quality_flags"][unit] = {str(int(v)): int(c) for v, c in zip(values, counts)}
                samples.append(entry)
        return {"samples": samples, "unit": "three consecutive 20-second GLM files", "extreme_lightning_confirmed": False,
                "limits": "Density baseline, spatial grouping, duplicate boundary flashes and extreme thresholds remain to be defined."}

    check("glm-three-products", "D10", lightning)

    def coldwave():
        data = checked("D47-coldwave-pinned")
        require(sha(data) == rows["D47-coldwave-pinned"][0]["expected_sha256"], "HF linked checksum mismatch")
        samples = []
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            require(sum(m.file_size for m in z.infolist()) < 16 * 1024**2, "archive expansion cap")
            require(z.testzip() is None, "ZIP CRC")
            for name in sorted(n for n in z.namelist() if n.endswith(".nc")):
                raw = z.read(name)
                with netCDF4.Dataset("coldwave", memory=raw) as ds:
                    require(ds["t2m"].units == "K", "t2m units")
                    arr = ds["t2m"][:]
                    dates = netCDF4.num2date(ds["time"][:], ds["time"].units)
                    times = [d.strftime("%Y-%m-%d") for d in dates]
                    seq_name = name[:-3] + "_sequence.csv"
                    seq = list(csv.DictReader(io.StringIO(z.read(seq_name).decode())))
                    require([r["date"] for r in seq] == times, "sequence date mismatch")
                    require(np.isfinite(arr).all(), "nonfinite coldwave array")
                    samples.append({"case_id": name.split("/")[1], "member": name, "sha256": sha(raw),
                                    "shape": list(arr.shape), "time_steps": len(times), "start": times[0], "end": times[-1],
                                    "units": "K", "min": float(arr.min()), "max": float(arr.max()),
                                    "bbox": [float(ds["longitude"][:].min()), float(ds["latitude"][:].min()),
                                             float(ds["longitude"][:].max()), float(ds["latitude"][:].max())],
                                    "sequence_rows": len(seq)})
            return {"sha256": sha(data), "hf_commit": rows["D47-coldwave-pinned"][0]["revision"],
                    "members": len(z.infolist()), "file_members": sum(not m.is_dir() for m in z.infolist()),
                    "uncompressed_bytes": sum(m.file_size for m in z.infolist()), "samples": samples,
                    "source_case_ids": len(samples), "deduplicated_event_families": None,
                    "time_steps": sum(s["time_steps"] for s in samples), "countries_by_case_suffix": sorted({s["case_id"].split("-")[-1] for s in samples}),
                    "limits": "Country-disaster IDs are source cases, not independently verified synoptic systems. ERA5 field lineage, event extrema definitions and EM-DAT derivative rights need checking."}

    check("exebench-coldwave", "D47", coldwave)

    def drought():
        data = checked("D52-train-prefix-encoded")
        require(data[:4] == b"PK\x03\x04" and struct.unpack_from("<H", data, 8)[0] == 8, "ZIP deflate local header")
        n, e = struct.unpack_from("<HH", data, 26)
        name = data[30:30 + n].decode()
        dec = zlib.decompressobj(-15)
        raw = dec.decompress(data[30 + n + e:], 16 * 1024**2)
        raw = raw[:raw.rfind(b"\n") + 1]
        rs = list(csv.DictReader(io.StringIO(raw.decode())))
        require({"fips", "date", "T2M", "PRECTOT", "score"} <= rs[0].keys(), "DroughtED schema")
        for r in rs:
            datetime.fromisoformat(r["date"])
            require(np.isfinite(float(r["T2M"])), "temperature")
        labeled = [r for r in rs if r["score"]]
        require(len(labeled) >= 3, "DroughtED labeled sample")
        out = ROOT / "samples/droughted_train_prefix.csv"
        out.write_bytes(raw)
        return {"member": name, "prefix_rows": len(rs), "counties": sorted({r["fips"] for r in rs}),
                "observed_date_min": min(r["date"] for r in rs), "observed_date_max": max(r["date"] for r in rs),
                "score_min": min(float(r["score"]) for r in labeled), "score_max": max(float(r["score"]) for r in labeled),
                "fractional_score_rows": sum(not float(r["score"]).is_integer() for r in labeled),
                "nonmissing_score_rows": len(labeled), "examples": labeled[:3], "archive_complete": False,
                "full_member_crc_checked": False, "prefix_sha256": sha(raw), "asset_path": str(out.relative_to(REPO)),
                "license_provider": "CC0: Public Domain (captured Kaggle metadata)",
                "limits": "Partial compressed member; whole-member CRC unavailable. Actual train prefix includes 2016, conflicting with metadata description of 2000-2009 train. Weekly USDM-derived scores are not daily labels or a new independent gold source."}

    check("droughted-prefix", "D52", drought)

    def hourly():
        footer = checked("D48-ghcnh-full-footer")
        prefix = checked("D48-ghcnh-rg0")
        rf, rp = rows["D48-ghcnh-full-footer"][1], rows["D48-ghcnh-rg0"][1]
        require(rf["headers"]["etag"] == rp["headers"]["etag"], "Parquet object changed")
        start, end, total = map(int, re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)", rf["headers"]["content-range"]).groups())
        require(len(footer) == end - start + 1 and end + 1 == total, "footer range")
        require(rp["headers"]["content-range"] == f"bytes 0-{len(prefix)-1}/{total}", "prefix range")
        reader = CapturedRanges(total, [(0, prefix), (start, footer)])
        pf = pq.ParquetFile(reader)
        table = pf.read_row_group(0)
        require(table.num_rows == pf.metadata.row_group(0).num_rows, "row group count")
        df = table.to_pandas()
        good = df[df.surface_air_temperature.notna() & (df.valid_time < "2024-01-03")]
        require(len(good) >= 3, "sample rows")
        ex = good.groupby("station", sort=True).head(1).head(3).to_dict("records")
        return {"object_declared_rows": pf.metadata.num_rows, "metadata_row_groups": pf.metadata.num_row_groups,
                "decoded_row_groups": 1, "decoded_rows": len(df), "stations": int(df.station.nunique()),
                "examples": [{k: str(v) if k == "valid_time" else None if isinstance(v, float) and not np.isfinite(v) else v
                              for k, v in r.items()} for r in ex],
                "columns": list(df.columns), "object_bytes": total,
                "limits": "Only row group 0 downloaded, not 298 million rows. GHCN-hourly is distinct from GHCN-Daily; temperature conventions and missing wind codes require source documentation. No EWB event alignment admitted."}

    check("ewb-hourly-rowgroup", "D48", hourly)

    def geoid():
        v5rows = collect(V5)
        checksum_text = v5rows["geoid-mirror-checksums"][2].decode()
        checksums = {line.split(maxsplit=1)[1].strip(): line.split()[0] for line in checksum_text.splitlines() if line.strip()}
        tiles = []
        for i in range(3):
            parts, arrays = {}, {}
            for role in ["pre", "post", "label", "validity"]:
                ident = f"geoid-{role}-{i}"
                retry = f"D12-{ident}-retry"
                spec, response, data = rows[retry] if retry in rows else old[ident]
                require(response["complete"] and response["http_status"] == 200, "incomplete GEOID role")
                name = spec["url"].split("/868407460bf3db492f50730a57585916baa71dc6/", 1)[1]
                require(checksums[name] == sha(data), "GEOID pinned manifest checksum")
                parts[role] = {"sha256": sha(data), "member": name, **geotiff_sample(data)}
                with rasterio.io.MemoryFile(data) as mem:
                    with mem.open() as ds:
                        arrays[role] = ds.read()
            ref = parts["post"]
            require(all(p["crs"] == ref["crs"] and np.allclose(p["transform"], ref["transform"], rtol=0, atol=1e-8)
                        and p["array"]["shape"][-2:] == ref["array"]["shape"][-2:] for p in parts.values()), "GEOID grid mismatch")
            label, validity = arrays["label"][0], arrays["validity"][0]
            require(set(np.unique(label)) <= {0, 1, 2, 255}, "GEOID label classes")
            tiles.append({"tile_id": f"EMSR712-10-{i}", "parts": parts,
                          "flood_pixels": int((label == 2).sum()),
                          "validity_equals_label_not255": bool(np.array_equal(validity > 0, label != 255))})
        cems = json.loads(checked("D18-EMSR712"))["results"][0]
        aoi = next(a for a in cems["aois"] if a["number"] == 10)
        products = [{"product_id": p["id"], "type": p["type"], "monitoring_number": p["monitoringNumber"],
                     "version": p["version"], "images": p["images"]} for p in aoi["products"]]
        return {"tiles": tiles, "tile_pairs": len(tiles), "activation_count": 1, "activation": "EMSR712", "aoi": 10,
                "cems_name": cems["name"], "aoi_name": aoi["name"], "event_time": cems["eventTime"], "products": products,
                "external_split": "test (EMSR712 sample catalogue)", "new_disastertrace_split": "AUDIT_ONLY_ALREADY_OBSERVED",
                "limits": "Audit samples cannot become unseen tests. Activation/AOI bridge established; exact original scene and annotation revision links still require matching. Gold-derived validity is private QA, not independent sensor quality evidence."}

    check("geoid-complete-pairs-and-cems", "D12", geoid)

    def fire():
        reader = (refs / "D19-reader-blob.bin").read_text()
        require("y = (y > 0).long()" in reader and "torch.nan_to_num(y, nan=0.0)" in reader, "author mask semantics changed")
        run = read(PRIOR / "archive_runs/wildfirespreadts_01/RESULT.json")
        samples = []
        for m in run["members"]:
            data = (PRIOR / m["path"]).read_bytes()
            require(sha(data) == m["sha256"], "fire member hash")
            with rasterio.io.MemoryFile(data) as mem:
                with mem.open() as ds:
                    last = ds.read(ds.count)
            mask = np.nan_to_num(last, nan=0) > 0
            samples.append({"name": m["name"], "nan_pixels": int(np.isnan(last).sum()), "positive_pixels": int(mask.sum()),
                            "total_pixels": int(mask.size), "mask_sha256": sha(mask.astype(np.uint8).tobytes())})
        return {"samples": samples, "source_events": 1, "reader_git_blob": "a7422287ea43725a6deaa27e2af548626ea15629",
                "rule": "NaN to zero; detection HHMM > 0 becomes active-fire label, per author reader",
                "limits": "Reader semantics verified; detecting fire is not proof of weather causation, valid sensor coverage, or forecast-as-of provenance."}

    check("wildfire-label-semantics", "D19", fire)

    def coastal():
        samples = []
        for station in ["8761724", "8518750", "9414290"]:
            s1, _, b1 = old[f"coops-{station}-water_level"]
            s2, _, b2 = old[f"coops-{station}-predictions"]
            require(all(x in s1["url"] and x in s2["url"] for x in ["datum=MLLW", "units=metric", "time_zone=gmt"]), "datum/time/units mismatch")
            water = json.loads(b1)["data"]
            pred = {r["t"]: float(r["v"]) for r in json.loads(b2)["predictions"]}
            values = [float(r["v"]) - pred[r["t"]] for r in water if r["q"] == "v" and r["v"] and r["t"] in pred]
            require(len(values) == 240, "coastal pairing count")
            samples.append({"station": station, "matched_times": len(values), "residual_min_m": min(values), "residual_max_m": max(values)})
        return {"samples": samples, "datum": "MLLW", "timezone": "GMT", "residual_is_pure_storm_surge": False}

    check("coops-time-pairing", "D37", coastal)

    def isd_codes():
        results = []
        for station in ["54511099999", "40416099999"]:
            rs = list(csv.DictReader(io.StringIO(old["isd-" + station][2].decode())))
            kinds = {"dust_storm_codes_30_35": {str(v) for v in range(30, 36)}, "fog_codes_40_49": {str(v) for v in range(40, 50)},
                     "dust_presence_codes_06_07_not_storm": {"06", "07"},
                     "freezing_rain_codes_66_67": {"66", "67"}, "blowing_snow_codes_36_39": {str(v) for v in range(36, 40)}}
            for kind, codes in kinds.items():
                selected = []
                for r in rs:
                    parts = r.get("MW1", "").split(",")
                    vis = r["VIS"].split(",")
                    if len(parts) >= 2 and parts[0] in codes and parts[1] in {"0", "1", "4", "5"} and vis[1] in {"0", "1", "4", "5"} and int(vis[0]) != 999999:
                        selected.append({k: r.get(k) for k in ["STATION", "DATE", "LATITUDE", "LONGITUDE", "MW1", "VIS", "WND"]})
                results.append({"station": station, "phenomenon_code_group": kind, "qc_accepted_reports": len(selected), "examples": selected[:3]})
        return {"groups": results, "limits": "Code-specific presence probes; WMO/ISD code definitions are required for final subtype admission. No independent event or local-extreme threshold inferred."}

    check("isd-phenomenon-samples", "D27", isd_codes)

    def cyport():
        result = []
        for storm in ["DORIAN_2019", "HARVEY_2017", "FLORENCE_2018"]:
            parts = {}
            for ext in ["png", "txt"]:
                ident = f"D50-{storm}-{ext}"
                blob = refs / (ident + "-blob.bin")
                data = blob.read_bytes() if blob.exists() else checked(ident)
                if ext == "png":
                    with Image.open(io.BytesIO(data)) as im:
                        im.load()
                        parts[ext] = {"size": list(im.size), "format": im.format, "sha256": sha(data)}
                else:
                    text = data.decode()
                    ids = sorted(set(re.findall(r"AL\d{6}", text)))
                    require(ids, "missing NHC storm ID")
                    parts[ext] = {"storm_ids": ids, "sha256": sha(data), "prefix": text[:800]}
            result.append({"source_storm_name": storm, "parts": parts})
        return {"samples": result, "storms_by_filename": len(result), "limits": "Filename-level text/graphic bundle checked. Exact matching advisory issue and image-printed timestamp still pending; no port decision labels adopted."}

    check("cyport-three-storm-bundles", "D50", cyport)

    def weatherqa_upstream():
        html = checked("D49-spc-md0398").decode()
        text = re.search(r"<pre>(.*?)</pre>", html, re.S).group(1)
        require("Mesoscale Discussion 0398" in text and "May 13 2018" in text, "SPC product identity")
        require("Valid 131756Z - 132000Z" in text, "SPC valid interval")
        require("Mesoanalysis at 17Z" in text, "SPC analysis time")
        return {"product": "SPC MD 2018/0398", "issue_time": "2018-05-13T17:56:00Z",
                "valid_end": "2018-05-13T20:00:00Z", "analysis_time_referenced": "2018-05-13T17:00:00Z",
                "weatherqa_raw_group_downloaded": False, "document_sha256": sha(html.encode()),
                "limits": "Forecast potential, not observed hail/wind truth. 17Z maps and 17:56Z discussion have distinct timestamps."}

    check("weatherqa-spc-product", "D49", weatherqa_upstream)
    output = {"schema": "v6_offline_supplement_audit_v1", "reports": reports, "model_calls": 0, "gpu_jobs": 0,
              "new_formal_episodes": 0, "checked_capture_ids": sorted(rows)}
    path = ROOT / "analysis/SELECTION_AUDIT.json"
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2, default=str, allow_nan=False) + "\n")
    print(json.dumps({r["id"]: r["level"] + (": " + r["error"] if "error" in r else "") for r in reports}, indent=2))


if __name__ == "__main__":
    main()

```


---

## 代码：plans/v6_0911_dataset_selection/audit_downloaded.py

```python
"""Offline sample verification spanning the earlier captures and V6 decisions."""

import csv
import hashlib
import io
import json
import re
import sys
import tarfile
import zlib
from pathlib import Path

import h5py
import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parent
PRIOR = ROOT.parent / "multihazard_source_validation_20260911"
sys.path.insert(0, str(PRIOR))
from validate_samples import captures, validate, require, array_summary, geotiff_sample, netcdf_sample
from assemble_samples import assemble


def digest(data):
    return hashlib.sha256(data).hexdigest()


def record_file(path, expected=None):
    data = path.read_bytes()
    require(expected is None or digest(data) == expected, "asset hash mismatch")
    return data


def main():
    output = ROOT / "analysis/DOWNLOADED_AUDIT.json"
    require(not output.exists(), "new output required")
    rows = captures()
    reports, failures = [], []
    for ident, (spec, response, body) in rows.items():
        r = {"id": ident, "source": spec.get("source"), "capture_bundle": str(PRIOR.name), "capture_path": response.get("attempt_path"), "sha256": digest(body), "bytes": len(body), "is_new_in_v6": False}
        try:
            r["level"], r["details"] = validate(spec, response, body)
        except Exception as exc:
            r.update(level="not_validated", error_type=type(exc).__name__, error=str(exc))
        reports.append(r)

    for ident in sorted({s["completes"] for s, _, _ in rows.values() if "completes" in s}):
        r = {"id": ident + "-assembled", "source": rows[ident][0]["source"], "is_new_in_v6": False}
        try:
            spec, body, inputs = assemble(rows, ident)
            level, details = validate(spec, {"complete": True, "http_status": 200}, body)
            existing = PRIOR / "assemblies/completion_01" / (ident + ".bin")
            if existing.exists():
                require(digest(existing.read_bytes()) == digest(body), "earlier assembly differs")
                path = str(existing.relative_to(ROOT.parent.parent))
            else:
                target = ROOT / "samples" / (ident + ".bin")
                target.write_bytes(body)
                path = str(target.relative_to(ROOT.parent.parent))
            r.update(level=level, details=details, inputs=inputs, asset_path=path, sha256=digest(body), bytes=len(body), new_http_response=False)
        except Exception as exc:
            r.update(level="not_validated", error_type=type(exc).__name__, error=str(exc))
        reports.append(r)

    archive_members = {}
    for f in sorted((PRIOR / "archive_runs").glob("*/RESULT.json")):
        result = json.loads(f.read_text())
        for member in result["members"]:
            data = record_file(PRIOR / member["path"], member["sha256"])
            require(zlib.crc32(data) == member["crc32"], "ZIP member CRC mismatch")
            archive_members[member["name"]] = member, data

    pairs = []
    for ident in ("1", "10", "100"):
        image, ib = archive_members[f"TrainData/img/image_{ident}.h5"]
        mask, mb = archive_members[f"TrainData/mask/mask_{ident}.h5"]
        with h5py.File(io.BytesIO(ib)) as f:
            im = f["img"][:]
        with h5py.File(io.BytesIO(mb)) as f:
            labels = f["mask"][:]
        require(im.shape == (128, 128, 14) and labels.shape == (128, 128), "Landslide4Sense shape")
        values, counts = np.unique(labels, return_counts=True)
        require(set(values) <= {0, 1}, "Landslide4Sense classes")
        pairs.append({"sample_id": ident, "image": image, "mask": mask, "image_array": array_summary(im), "label_counts": {str(int(v)): int(n) for v, n in zip(values, counts)}})
    reports.append({"id": "landslide-three-pairs", "source": "landslide4sense", "level": "paired_arrays_decoded", "details": {"samples": pairs, "limits": "No geospatial/time metadata inside these HDF5 chips; upstream event linkage and rainfall cause unresolved."}})

    caravan, wildfire = [], []
    for name, (member, data) in archive_members.items():
        if name.startswith("Caravan/timeseries/"):
            rs = list(csv.DictReader(io.StringIO(data.decode())))
            require(len(rs) >= 3 and "date" in rs[0] and "streamflow" in rs[0], "Caravan daily timeseries")
            good = [r for r in rs if r["streamflow"] and r["streamflow"].lower() != "nan"]
            require(len(good) >= 3, "Caravan flow values")
            for r in good[:3]:
                require(np.isfinite(float(r["streamflow"])), "Caravan finite flow")
            caravan.append({"name": name, "member": member, "rows": len(rs), "flow_rows": len(good), "columns": list(rs[0]), "examples": good[:3]})
        if re.match(r"\d{4}/fire_\d+/.*\.tif$", name):
            d = geotiff_sample(data)
            with rasterio.io.MemoryFile(data) as mem:
                with mem.open() as ds:
                    last = ds.read(ds.count)
                    values, counts = np.unique(last, return_counts=True)
                    d["last_band_raw_values"] = {str(float(v)): int(n) for v, n in zip(values, counts)} if len(values) < 100 else {"unique_values": len(values)}
            wildfire.append({"name": name, "member": member, **d})
    reports.append({"id": "caravan-three-basins", "source": "caravan", "level": "sample_decoded", "details": {"samples": caravan, "basins": len(caravan), "limits": "Daily basin records; original conventions and catchment metadata must be linked before flood thresholds."}})
    reports.append({"id": "wildfire-three-days", "source": "wildfirespreadts", "level": "arrays_decoded_label_semantics_pending", "details": {"samples": wildfire, "source_event_ids": sorted({r["name"].split('/')[1] for r in wildfire}), "limits": "Same-event daily files; numerical nodata/fire-mask interpretation must follow the author reader."}})

    for ident, source in [("tornet-three-prefix", "tornet"), ("senforflood-tar-prefix", "senforflood")]:
        spec, response, body = rows[ident]
        result = {"id": ident + "-members", "source": source, "level": "not_validated", "details": {"archive_complete": False, "members": []}}
        try:
            require(body and response["http_status"] == 206, "archive prefix not received")
            with tarfile.open(fileobj=io.BytesIO(body), mode="r|*") as tar:
                for m in tar:
                    if not m.isfile() or not m.name.endswith((".nc", ".tif")):
                        continue
                    require(m.size <= 48 * 1024**2, "archive member too large")
                    data = tar.extractfile(m).read(m.size + 1)
                    require(len(data) == m.size, "incomplete archive member")
                    details = netcdf_sample(data) if m.name.endswith(".nc") else geotiff_sample(data)
                    item = {"name": m.name, "bytes": len(data), "sha256": digest(data), "details": details}
                    if source == "tornet":
                        import netCDF4
                        with netCDF4.Dataset("sample", memory=data) as ds:
                            item["attributes"] = {k: str(ds.getncattr(k)) for k in ds.ncattrs()}
                    out = ROOT / "samples" / (source + "-" + str(len(result["details"]["members"])) + (".nc" if source == "tornet" else ".tif"))
                    out.write_bytes(data)
                    item["asset_path"] = str(out.relative_to(ROOT))
                    result["details"]["members"].append(item)
                    if len(result["details"]["members"]) == 3:
                        break
            require(len(result["details"]["members"]) == 3, "fewer than three complete members")
            result["level"] = "radar_samples_decoded" if source == "tornet" else "background_only_decoded"
        except Exception as exc:
            result.update(error_type=type(exc).__name__, error=str(exc))
        reports.append(result)

    geoid = []
    for index in range(3):
        parts = {}
        try:
            for role in ("pre", "post", "label", "validity"):
                ident = f"geoid-{role}-{index}"
                spec, response, body = rows[ident]
                require(response["complete"] and response["http_status"] == 200, "incomplete GEOID " + ident)
                parts[role] = geotiff_sample(body)
            ref = parts["post"]
            require(all(v["crs"] == ref["crs"] and v["transform"] == ref["transform"] and v["array"]["shape"][-2:] == ref["array"]["shape"][-2:] for v in parts.values()), "GEOID grids disagree")
            geoid.append({"tile_id": f"EMSR712-10-{index}", "status": "aligned", "parts": parts})
        except Exception as exc:
            geoid.append({"tile_id": f"EMSR712-10-{index}", "status": "incomplete", "error": str(exc), "parts": parts})
    reports.append({"id": "geoid-paired-check", "source": "geoid", "level": "paired_rasters_checked", "details": {"tiles": geoid, "parent_activation": "EMSR712", "limits": "One parent activation/AOI, not three independent floods; mirror payload provenance and validity derivation require separate checks."}})

    for ident in ["ts-satfire-sample-0", "ts-satfire-sample-1", "ts-satfire-sample-2"]:
        spec, response, body = rows[ident]
        r = {"id": ident + "-decoded", "source": "ts_satfire"}
        try:
            require(response["complete"] and response["http_status"] == 200, "TS-SatFire asset incomplete")
            r.update(level="sample_decoded", details=geotiff_sample(body))
        except Exception as exc:
            r.update(level="not_validated", error_type=type(exc).__name__, error=str(exc))
        reports.append(r)

    summary = {"schema": "offline_downloaded_validation_v1", "reports": reports,
               "new_model_calls": 0, "new_gpu_jobs": 0, "new_formal_benchmark_episodes": 0,
               "limits": "No global event-family count or whole-source admission is inferred from these checks."}
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    from collections import Counter
    print(json.dumps(dict(Counter(r["level"] for r in reports)), sort_keys=True))


if __name__ == "__main__":
    main()

```


---

## 代码：plans/v6_0911_dataset_selection/verify_selection.py

```python
"""Verify the handoff against captured bytes, measured counts and protected baselines."""
import ast
import hashlib
import importlib.util
import json
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parent.parent
PRIOR=ROOT.parent/'multihazard_source_validation_20260911'
checks=[]
def read(path):
 return json.loads(path.read_text(),parse_constant=lambda x:(_ for _ in ()).throw(ValueError('invalid JSON constant '+x)))
def require(condition,message):
 if not condition:raise AssertionError(message)
 checks.append(message)
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def jsonl(path):return [json.loads(x) for x in path.read_text().splitlines() if x]

seed=read(ROOT/'inputs/download_registry.json')
registry=read(ROOT/'SOURCE_REGISTRY.json')['sources']; byid={r['source_id']:r for r in registry}
require(len(registry)==len(byid)==74,'74 unique registry entries, 54 original plus 20 supplements')
require({r['id'] for r in seed['resources']}=={r['source_id'] for r in registry if r['seed_id_preserved']},'original D01-D54 IDs preserved')
require(all(byid[r['id']]['name']==r['name'] for r in seed['resources']),'original source names preserved')
require(all(set(r['axes'])=={'access','content','provenance','license','task_eligibility'} for r in registry),'five independent status axes on every source')
require(all(not r['new_task_admitted'] and r['new_qualified_episode_count']==0 for r in registry),'no new formal task admission inferred from decoding')
require(all(r['capabilities']['C6']=='not_established_historical_availability_null' for r in registry),'strict historical availability remains unestablished')
for r in registry:
 for e in r['evidence']:
  require((ROOT/e['file']).exists(),'evidence file exists: '+r['source_id']+' '+e['file'])

counts=read(ROOT/'DATA_COUNTS.json')
require(counts['event_family_total'] is None,'uncomputed global event count remains null')
require(counts['new_model_calls']==counts['new_gpu_jobs']==0,'no new model or GPU jobs')
require(counts['content_class_counts']==dict(Counter(r['content_evidence'] for r in registry)),'content class totals match source registry')
for m in counts['counts']:
 require(all(k in m for k in ['value','unit','basis','scope','evidence']),'count unit/basis/scope present: '+str(m['source_id'])+' '+m['metric'])
 require(m['value'] is None or isinstance(m['value'],int),'counts are integer or explicitly unknown')

files=jsonl(ROOT/'FILE_MANIFEST.jsonl')
require(len(files)==len({r['path'] for r in files})==counts['file_manifest_entries'],'file manifest paths unique and counted')
for r in files:
 path=REPO/r['path']
 require(path.is_file() and path.stat().st_size==r['bytes'] and digest(path)==r['sha256'],'file bytes and SHA256: '+r['path'])

for root in [PRIOR,ROOT]:
 rs=[read(p) for p in root.glob('attempts/*/response.json')]
 require(len(rs)==counts['network'][root.name]['http_attempts'],'HTTP attempt denominator: '+root.name)
 require(sum(r['captured_bytes'] for r in rs)==counts['network'][root.name]['captured_bytes'],'HTTP captured-byte total: '+root.name)
 scope=read(root/'SCOPE.json')
 require(len(rs)<=scope['max_http_attempts'] and sum(r['captured_bytes'] for r in rs)<=scope['max_captured_response_body_bytes'],'independent request and byte budgets respected: '+root.name)
 require(len(list(root.glob('attempts/*/intent.json')))==len(rs),'all request intents have terminal receipts: '+root.name)

old={r['id']:r for r in read(ROOT/'analysis/DOWNLOADED_AUDIT.json')['reports']}
new={r['id']:r for r in read(ROOT/'analysis/SELECTION_AUDIT.json')['reports']}
require(len(new)==10 and all(r['level']=='verified' for r in new.values()),'10 supplementary content/relationship checks verified')
require(sum(old[k]['details']['records'] for k in ['storm-events-2021-assembled','storm-events-2023-assembled'])==136982,'complete Storm Events annual rows total 136982')
require(new['exebench-coldwave']['details']['source_case_ids']==9 and new['exebench-coldwave']['details']['time_steps']==559,'ExEBench case/time-step units separated')
require(new['ewb-hourly-rowgroup']['details']['decoded_rows']==122880 and new['ewb-hourly-rowgroup']['details']['decoded_rows']<new['ewb-hourly-rowgroup']['details']['object_declared_rows'],'decoded Parquet rows distinguished from footer-declared supply')
require(all(t['flood_pixels']==0 for t in new['geoid-complete-pairs-and-cems']['details']['tiles']),'GEOID sampled bundles do not establish flood-positive coverage')
require(all(t['validity_equals_label_not255'] for t in new['geoid-complete-pairs-and-cems']['details']['tiles']),'GEOID validity dependence on label explicitly identified')
require(all('/NUL_' in x['name'] for x in old['tornet-three-prefix-members']['details']['members']),'TorNet sampled radar files are negative examples')
require(new['droughted-prefix']['details']['fractional_score_rows']==1330,'DroughtED fractional scores are not silently rounded to classes')
require(new['droughted-prefix']['details']['observed_date_max']=='2016-12-31','DroughtED actual train dates checked against metadata conflict')
require(new['weatherqa-spc-product']['details']['issue_time']!=new['weatherqa-spc-product']['details']['analysis_time_referenced'],'SPC analysis and discussion issuance times distinguished')

protected=set(read(ROOT/'REPO_DATA_BASELINE.json')['protected_ids'])
for s in new['cyport-three-storm-bundles']['details']['samples']:
 require(not protected.intersection(s['parts']['txt']['storm_ids']),'new CyPort sample outside protected explicit storm IDs: '+s['source_storm_name'])
risks=read(ROOT/'SPLIT_AND_DEPENDENCY_RISKS.json')
require(set(risks['protected_storm_ids'])==protected,'protected storm union propagated to split-risk registry')
require(new['geoid-complete-pairs-and-cems']['details']['new_disastertrace_split']=='AUDIT_ONLY_ALREADY_OBSERVED','externally heldout GEOID samples remain observed audit material')
require(risks['event_family_count'] is None,'global cross-source event deduplication not falsely declared complete')

hazards=read(ROOT/'HAZARD_COVERAGE.json')
require({r['hazard_id'] for r in hazards}=={f'H{i:02d}' for i in range(1,17)},'all 16 hazard directions recorded')
require(all(r['primary_source_ids'] and r['backup_source_ids'] and r['gaps_cn'] for r in hazards),'each hazard has primary/backup routes and an explicit gap')
require(all(set(r['primary_source_ids']+r['backup_source_ids'])<=byid.keys() for r in hazards),'hazard source references resolve')
st=Counter()
for k in ['storm-events-2021-assembled','storm-events-2023-assembled']:st.update(old[k]['details']['type_counts'])
require(all(r['catalog_report_count']==sum(st[t] for t in r['storm_events_types']) for r in hazards),'hazard report counts recompute from decoded annual files')
require(all('Volcanic Ashfall' not in r['storm_events_types'] for r in hazards),'volcanic ash excluded from weather taxonomy')

manifest=read(ROOT/'NEXT_ACQUISITION_MANIFEST.json')
require(len(manifest['items'])==12,'12 concrete next-acquisition work items')
require(manifest['sum_item_capture_caps_bytes']==sum(r['max_captured_bytes'] for r in manifest['items']),'next-acquisition byte caps recompute')
require(all(r['net_new_event_families'] is None and r['status']=='planned_not_launched' for r in manifest['items']),'future event yield unpromised; next-stage jobs not launched')
for r in manifest['items']:require(set(r['source_ids'])<=byid.keys(),'next-stage source IDs resolve: '+r['id'])
for r in jsonl(ROOT/'BENCHMARK_RAW_LINKS.jsonl'):require(r['benchmark_source_id'] in byid and r['historical_available_at'] is None,'benchmark linkage preserves uncertainty: '+r['link_id'])

baseline=read(PRIOR/'BASELINE.json')
for r in baseline['old_files']:require(digest(REPO/r['path'])==r['sha256'],'protected baseline unchanged: '+r['path'])
for r in read(ROOT/'REPO_DATA_BASELINE.json')['inputs']:
 require(digest(Path(r['path']))==r['sha256'],'user input unchanged: '+Path(r['path']).name)
 require(digest(ROOT/'inputs'/Path(r['path']).name)==r['sha256'],'input snapshot matches original: '+Path(r['path']).name)
correction=read(ROOT/'analysis/SCOPE_METADATA_CORRECTION_01.json')
require(correction['actual_sha256']==digest(ROOT/'inputs/download_registry.json'),'incorrect initial scope digest corrected by preserved amendment')

for p in ROOT.glob('*.py'):ast.parse(p.read_text())
require(True,'all new top-level Python sources parse without executing author code')
required=['DATA_READINESS_REVIEW_CN.md','SOURCE_FEASIBILITY.md','HAZARD_COVERAGE.md','DATA_COUNTS.json','BENCHMARK_RAW_LINKS.jsonl','REUSE_AND_GAPS.md','NEXT_ACQUISITION_MANIFEST.json','CAPABILITY_MATRIX.md','SOURCE_DEPENDENCIES.json','ASSET_REUSE_INDEX.json']
for name in required:require((ROOT/name).stat().st_size>0,'required deliverable present: '+name)
for p in ROOT.glob('*.json'):read(p)
for p in ROOT.glob('*.jsonl'):jsonl(p)
report={'schema':'disastertrace_v6_selection_verification_v1','status':'passed','check_count':len(checks),'checks':checks,
 'required_deliverables':[{'path':name,'sha256':digest(ROOT/name),'bytes':(ROOT/name).stat().st_size} for name in required],
 'limitations':['This verifies the bounded acquisition/selection handoff, not full V6 completion.','Probability sampling, full rights review, event-family deduplication, native image timestamp OCR and task admission remain open.','No inferred representative source success rate or global event count.'],
 'new_gpu_jobs':0,'new_model_calls':0,'new_formal_episodes':0}
(ROOT/'VERIFY_REPORT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ['checks','required_deliverables']},ensure_ascii=False,indent=2))

```
