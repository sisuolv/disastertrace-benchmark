# v7 全部 16 类灾害的数据与任务合同

日期：2026-09-12。此表是 [整体计划](OVERALL_PLAN_CN.md) 的数据实施附件。来源状态继承当前 97 条目注册表；本轮未重新下载科学数据。全部新监测 E/F/D/MM 准入仍为 false；旧窄链可复用不等于新会话已建。

每个灾种最终至少形成一条明确未来目标、自动结算和合格 P/R 基线的任务链。时间尺度是候选，确认数据建设前冻结。分组 A 风暴、B 对流、C 水相关、D 温度/冬季、E 干旱/野火、F 能见度。

## H01 热带气旋（A 组）

**未来任务：** 总体最大持续风的未来数值/越阈，不替代地点风风险。

**候选尺度：** `6/12/24h; known storm at monitoring start`。**基线轨：** `P_conditional`。

| 用途 | 来源 ID 与名称 |
| --- | --- |
| 专业预报候选 | D01 NHC forecast advisories / GIS |
| 结果参考候选 | AW-HURDAT2 NHC HURDAT2 Atlantic；D02 IBTrACS v4r01 |
| 补充证据/已有 benchmark 候选 | D03 Digital Typhoon V2；D04 TCIR；AW-ABI GOES-19 ABI C01 / C13；D38 NOAA OISST v2.1；D50 CyPortQA |
| 目录索引 | D39 EM-DAT |
| 有额外门槛的结果参考 | D73 CMA Best Track |
| 空间门槛未通过的诊断来源 | D44 xBD |

**基线合同：** 最新同目标NHC点预报＋持续性；概率用同目标原生概率或分组开发拟合的误差分布，不冒称官方概率。

**E 支持任务：** 同气旋同有效时刻的强度/预报版本可比性和覆盖检查。

**跨目标共享设计：** 同洋盆预报公告、区域卫星和海温可服务多个有效时刻/相关目标。

处理要求：

- SID/机构别名与公告编号连接
- 风速平均时长、单位和分析机构分开
- TCIR等影像只使用合法观测时刻，检查裁剪中心是否来自事后轨迹
- HURDAT2/IBTrACS原始强度标签只在结果侧
- 使用发生前已知中心；不从 best track 裁剪；同一母气旋及洪水归同组

**负例与缺测：** 风暴后期缺少精确记录时unresolved，不用0代替；现有暴露风暴不进入盲测。

**现有证据范围：** 已有NHC窄F链；多模态增量和全球扩展未通过。

**下一道准入门槛：** 既有 NHC 窄链回归后，扩展未见风暴；CMA 字段核验与同洋盆业务预报为独立门槛。

**完整交付：** 同域连续输入—基线—结果链、E 规则与 F 自动结算、自然日历/极端诊断队列、独立过程分组及强 P/R 基线。D 只在 F 合格后使用固定研究损失表；原生多模态另验时间/配准/实际输入。一个子任务通过不代表该大类全部子灾种通过。

## H02 温带风暴/非对流大风（A 组）

**未来任务：** 指定站点平均风或阵风越阈；非对流成因单独验收。

**候选尺度：** `1-24h; matched wind averaging window`。**基线轨：** `P_conditional`。

| 用途 | 来源 ID 与名称 |
| --- | --- |
| 专业预报候选 | D28 NOAA GFS 0.25 degree operational forecasts；D67 NOAA HRRR operational forecasts；AW-GEFS NOAA GEFS ensemble |
| 结果参考候选 | AW-GHCNH NOAA GHCNh current hourly archive；AW-METAR AWC METAR observations；D05 NOAA Storm Events Database |
| 补充证据/已有 benchmark 候选 | D48 ExtremeWeatherBench；AW-ABI GOES-19 ABI C01 / C13 |
| 目录索引 | D39 EM-DAT |

**基线合同：** 同高度、同统计支持的业务风预报；点到概率的转换训练组隔离。

**E 支持任务：** 同高度/平均时段的风数值区间与相邻记录可比性。

**跨目标共享设计：** NWP 区域场和卫星能服务多站，独立站点观测可按需补充。

处理要求：

- 平均风与阵风分开
- 高度/时间平均窗口/站点迁移记录
- 区域格点到站点映射预先冻结
- 缺成因证据时只称强风，不能硬标非对流
- 平均风/阵风/阵风最大窗口不同；没有归因证据仅称强风

**负例与缺测：** 测站缺测不判无强风；匹配的负例来自预注册正常监测。

**现有证据范围：** 已有源样例，完整非对流强风F链待准入。

**下一道准入门槛：** 站点高度与 NWP 支持、合格强风正例和普通监测块、成因及源时刻合同。

**完整交付：** 同域连续输入—基线—结果链、E 规则与 F 自动结算、自然日历/极端诊断队列、独立过程分组及强 P/R 基线。D 只在 F 合格后使用固定研究损失表；原生多模态另验时间/配准/实际输入。一个子任务通过不代表该大类全部子灾种通过。

## H03 雷暴大风/下击暴流（B 组）

**未来任务：** 与 SPC 半径/窗口匹配的确认对流风报告；局地站点短临另轨。

**候选尺度：** `SPC native valid window; local 0-3h in separate R track`。**基线轨：** `P_or_R_conditional`。

| 用途 | 来源 ID 与名称 |
| --- | --- |
| 专业预报候选 | AW-SPC SPC Day 1 convective outlook；D67 NOAA HRRR operational forecasts |
| 结果参考候选 | D05 NOAA Storm Events Database；AW-GHCNH NOAA GHCNh current hourly archive；AW-METAR AWC METAR observations |
| 补充证据/已有 benchmark 候选 | D06 SEVIR；D08 NOAA NEXRAD Level II；AW-ABI GOES-19 ABI C01 / C13；D49 WeatherQA |
| 目录索引 | D39 EM-DAT |

**基线合同：** SPC区域时窗匹配或另行冻结的局地研究预测器；不可将区域长窗概率复制为站点短窗概率。

**E 支持任务：** 风报告/雷达时刻与统计支持可比性；覆盖不充分维持未知。

**跨目标共享设计：** 一组雷达体扫可服务多个对流单体/区域，需各自合法映射。

处理要求：

- 实测/估计风报告分开
- 报告发生时间与发布时间分开
- 雷达体扫/天气过程关联
- 不得以强回波直接给下击暴流Gold
- SEVIR VIL 不是雨量或风 Gold；强回波不等于下击暴流

**负例与缺测：** 无报告不自动等于物理未发生；报告型队列与观测型队列分开。

**现有证据范围：** 来源候选已登记；需联合雷达—地面结果与专业基线映射。

**下一道准入门槛：** SPC 目标映射、实测/估计风区别、同一对流过程分组与报告制度。

**完整交付：** 同域连续输入—基线—结果链、E 规则与 F 自动结算、自然日历/极端诊断队列、独立过程分组及强 P/R 基线。D 只在 F 合格后使用固定研究损失表；原生多模态另验时间/配准/实际输入。一个子任务通过不代表该大类全部子灾种通过。

## H04 龙卷风（B 组）

**未来任务：** 指定点邻域和未来窗口的确认龙卷报告。

**候选尺度：** `SPC native valid window; local lead requires pre-onset radar`。**基线轨：** `P_or_R_conditional`。

| 用途 | 来源 ID 与名称 |
| --- | --- |
| 专业预报候选 | AW-SPC SPC Day 1 convective outlook |
| 结果参考候选 | D05 NOAA Storm Events Database |
| 补充证据/已有 benchmark 候选 | D07 TorNet / v1.1 check；D08 NOAA NEXRAD Level II；D06 SEVIR；D49 WeatherQA |
| 目录索引 | D39 EM-DAT |

**基线合同：** 匹配SPC概率；TorNet预测器须确认使用的帧早于目标，检测模型不直接冒充提前预测。

**E 支持任务：** 发生前雷达与区域有效覆盖、证据时间与报告时间的可比性。

**跨目标共享设计：** 同次雷达体扫服务相邻目标；目标必须在未来结果前生成。

处理要求：

- 锁TorNet v1.1/实际发布版本
- 事件起止与雷达帧对齐
- 同storm跨帧不可跨split
- 地点/裁剪中心来源核查
- TorNet 的发生期检测任务不可冒充提前预测；事后裁剪中心禁入 F

**负例与缺测：** 确认报告0/1与真实发生0/1分开；NUL样例不自动代表全域无龙卷。

**现有证据范围：** 当前报告列举的TorNet样例仍为负；不得称正负闭环已建。

**下一道准入门槛：** 锁定 TorNet 版本、真实正例/负例、确认报告参考；空报告不等于物理未发生。

**完整交付：** 同域连续输入—基线—结果链、E 规则与 F 自动结算、自然日历/极端诊断队列、独立过程分组及强 P/R 基线。D 只在 F 合格后使用固定研究损失表；原生多模态另验时间/配准/实际输入。一个子任务通过不代表该大类全部子灾种通过。

## H05 冰雹（B 组）

**未来任务：** 地面雹径报告越阈；未来 MESH 产品越阈为单独代理任务。

**候选尺度：** `SPC native valid window; radar proxy separately named`。**基线轨：** `P_or_R_conditional`。

| 用途 | 来源 ID 与名称 |
| --- | --- |
| 专业预报候选 | AW-SPC SPC Day 1 convective outlook；D67 NOAA HRRR operational forecasts |
| 结果参考候选 | D05 NOAA Storm Events Database |
| 补充证据/已有 benchmark 候选 | AW-MESH MRMS MESH；D08 NOAA NEXRAD Level II；D06 SEVIR |
| 目录索引 | D39 EM-DAT |

**基线合同：** 匹配SPC雹风险或冻结雷达研究基线；MESH本身不是地面真值。

**E 支持任务：** MESH 合法数值/QC/覆盖支持和地面报告量纲比较。

**跨目标共享设计：** 雷达/MESH 区域资产共享，未知/缺测负码不能计作无雹。

处理要求：

- GRIB局地参数表版本与负值代码
- 直径单位
- 报告/雷达目标域匹配
- 产品代理与地面标签隔离
- 地面参考与雷达估计分别结算；不能把 MESH 当实测雹径

**负例与缺测：** 缺报告按报告制度处理；负代码/缺雷达不能当0mm。

**现有证据范围：** MESH部分语义尚待准入。

**下一道准入门槛：** GRIB 局地参数表、负码、报告有效窗及区域/半径概率支持匹配。

**完整交付：** 同域连续输入—基线—结果链、E 规则与 F 自动结算、自然日历/极端诊断队列、独立过程分组及强 P/R 基线。D 只在 F 合格后使用固定研究损失表；原生多模态另验时间/配准/实际输入。一个子任务通过不代表该大类全部子灾种通过。

## H06 强雷电（B 组）

**未来任务：** 未来区域 GLM 检测 flash 密度越阈。

**候选尺度：** `15/30/60min; observation coverage explicitly bounded`。**基线轨：** `R_initial`。

| 用途 | 来源 ID 与名称 |
| --- | --- |
| 专业预报候选 | 尚无同目标已核验专业预报；初始采用明确的研究基线 |
| 结果参考候选 | D10 GOES GLM (inherited sampled product) |
| 补充证据/已有 benchmark 候选 | D06 SEVIR；D08 NOAA NEXRAD Level II；AW-ABI GOES-19 ABI C01 / C13 |

**基线合同：** 尚无已核验同目标专业雷电预报；先用持续性/外推等明确命名的研究基线；不声称超越官方雷电预报。

**E 支持任务：** 有效面积/时间下检测数量与覆盖上下界；flash/group/event 去重。

**跨目标共享设计：** ABI/雷达区域观测和 GLM 文件可共同服务多个区域目标。

处理要求：

- flash/group/event父子结构
- 跨文件标识和重复检查
- 有效足迹和时间覆盖
- 历史基准冻结极端密度阈值
- 传感器无覆盖不等于零；检测闪电不同于全部地面雷击

**负例与缺测：** 传感器无覆盖时unresolved；检测0与没有全部物理闪电不同。

**现有证据范围：** 短GLM观测可读，同目标专业预报未定。

**下一道准入门槛：** 多文件连续窗口、探测覆盖、历史阈值和外推/持续性强 R 基线；无已验证专业同目标预报。

**完整交付：** 同域连续输入—基线—结果链、E 规则与 F 自动结算、自然日历/极端诊断队列、独立过程分组及强 P/R 基线。D 只在 F 合格后使用固定研究损失表；原生多模态另验时间/配准/实际输入。一个子任务通过不代表该大类全部子灾种通过。

## H07 极端降水（C 组）

**未来任务：** 精确未来累计窗口降水越阈；站点实测与估计产品分轨。

**候选尺度：** `1/3/6/24h exact accumulation supports`。**基线轨：** `P_conditional`。

| 用途 | 来源 ID 与名称 |
| --- | --- |
| 专业预报候选 | D28 NOAA GFS 0.25 degree operational forecasts；D67 NOAA HRRR operational forecasts；AW-GEFS NOAA GEFS ensemble；AW-WPC WPC QPF / winter products |
| 结果参考候选 | D26 GHCN-Daily；AW-GHCNH NOAA GHCNh current hourly archive；D29 IMERG V07 Early / Late；D30 CHIRPS v3 DAILY_SAT；AW-QPE MRMS MultiSensor QPE 01H Pass2 |
| 补充证据/已有 benchmark 候选 | D08 NOAA NEXRAD Level II；AW-ABI GOES-19 ABI C01 / C13；D59 MeteoNet |

**基线合同：** 同累计窗的专业QPF；有合格雷达雨率时可用pysteps短临基线；VIL不能直接作为毫米雨量。

**E 支持任务：** 累积支持区间、缺测/trace/QC；补齐窗口不能重复加整段与子段。

**跨目标共享设计：** 同一雷达雨场或 QPF 场服务多站/流域，各自映射冻结。

处理要求：

- startStep/endStep/stepType
- 累计重置与跨周期
- trace/缺测/QC分别编码
- 整段产品与子段累积不能重复相加
- 日降水不能切成小时真值；VIL 不能直接转换毫米；窗口缺失不就近拼接

**负例与缺测：** 间断累计不得补0；严格窗口结果拒收时保留unresolved，不靠最近记录凑完整。

**现有证据范围：** 已解码预报；历史严格雨量结果有拒收样例。

**下一道准入门槛：** 累计起止/重置、合格结果覆盖、同起报 QPF、真实雨量/代理身份。

**完整交付：** 同域连续输入—基线—结果链、E 规则与 F 自动结算、自然日历/极端诊断队列、独立过程分组及强 P/R 基线。D 只在 F 合格后使用固定研究损失表；原生多模态另验时间/配准/实际输入。一个子任务通过不代表该大类全部子灾种通过。

## H08 河洪/山洪/城市内涝（C 组）

**未来任务：** 同河站流量/水位越阈；山洪/内涝/空间扩张按不同结果子轨。

**候选尺度：** `6/12/24/48/72h; daily products have separate support`。**基线轨：** `P_conditional`。

| 用途 | 来源 ID 与名称 |
| --- | --- |
| 专业预报候选 | AW-HEFS NOAA HEFS QINE ensemble；D57 NWPS stage forecasts；AW-GLOFAS GloFAS operational forecast；AW-EFAS EFAS operational forecast |
| 结果参考候选 | D56 USGS continuous observations；D71 CAMELSH；D11 Global Flood Database v1；D18 CEMS Rapid Mapping |
| 补充证据/已有 benchmark 候选 | D14 UrbanSARFloods；D64 SenForFlood；D17 FloodNet；D16 SpaceNet 8；D12 GEOID-Flood；D13 KuroSiwo；D15 Sen1Floods11 v1.1；D51 WorldFloods v2 / ml4floods；AW-NIMS USGS NIMS cameras；D42 Sentinel-1 GRD；D43 Sentinel-2 SR Harmonized；D60 Caravan |
| 目录索引 | D39 EM-DAT |
| 空间门槛未通过的诊断来源 | D44 xBD |

**基线合同：** 最新同站同变量HEFS/NWPS或匹配日支持的GloFAS/EFAS；不同统计时间支持不混。

**E 支持任务：** 河站持续越阈证据支持；固定时刻空间洪水掩膜的覆盖面积界。

**跨目标共享设计：** 水网证实的上下游、多流域共享降雨/预报；SAR 区域资产需真实重合。

处理要求：

- 站号映射及数据证据
- 流量与水位分开、基准转换有来源和有效期
- 成员标识与轨迹保留
- 上游关系来自水网而非距离
- 图像与目标站/区域真实重合
- 洪水/永久水体/未知图例
- 流量和水位及基准不混；永久水体/洪水/未知分开；河站不代表所有洪水

**负例与缺测：** 固定时刻无合格观测unresolved；窗口无越阈但缺测可能藏越阈时不能判负；provisional与最终参考分榜。

**现有证据范围：** 连续流量窄链已通；部分水位前瞻试点；16灾种矩阵不等于洪水各子类完成。

**下一道准入门槛：** 归档发行版本、真实水网、阈值、成熟观测；空间子轨独立配准与标签；影像不要求 xBD 先通过。

**完整交付：** 同域连续输入—基线—结果链、E 规则与 F 自动结算、自然日历/极端诊断队列、独立过程分组及强 P/R 基线。D 只在 F 合格后使用固定研究损失表；原生多模态另验时间/配准/实际输入。一个子任务通过不代表该大类全部子灾种通过。

## H09 风暴潮/沿岸淹没（C 组）

**未来任务：** 同站总水位越阈；纯风暴潮残差和沿岸淹没独立子轨。

**候选尺度：** `6/12/24/48h; fixed datum and epoch`。**基线轨：** `P_conditional`。

| 用途 | 来源 ID 与名称 |
| --- | --- |
| 专业预报候选 | AW-OFS NOAA CBOFS station forecast；AW-PETSS NOAA P-ETSS tide/surge station bulletins |
| 结果参考候选 | D37 NOAA CO-OPS water levels；D69 GESLA current / GESLA-3 candidate |
| 补充证据/已有 benchmark 候选 | D58 NDBC Buoys；D01 NHC forecast advisories / GIS |
| 目录索引 | D39 EM-DAT |

**基线合同：** 适用区域和天气类型的业务总水位/潮汐残差产品；P-ETSS已取得样例注明的热带风暴不适用限制必须继承。

**E 支持任务：** 潮位基准/支持窗可比性、观测覆盖与阈值。

**跨目标共享设计：** 沿岸预报场、浮标与风压资料可服务多个站点。

处理要求：

- 潮位基准和epoch
- 模型位置—站号桥接
- 天文潮与总水位分开
- 残差不自动命名纯风暴潮
- P-ETSS 样例的热带风暴不适用限制继承；潮汐残差不自动等于纯风暴潮

**负例与缺测：** 质量标记剔除保留原因；缺测不证明无沿岸高水位。

**现有证据范围：** 已有潮位样例，模型—站点完整映射待做。

**下一道准入门槛：** 站点映射、垂直基准与 epoch、预报适用天气类型；实际淹没需额外标签。

**完整交付：** 同域连续输入—基线—结果链、E 规则与 F 自动结算、自然日历/极端诊断队列、独立过程分组及强 P/R 基线。D 只在 F 合格后使用固定研究损失表；原生多模态另验时间/配准/实际输入。一个子任务通过不代表该大类全部子灾种通过。

## H10 高温/热浪（D 组）

**未来任务：** 2m 气温越阈；热浪持续天数/气候阈值子轨。

**候选尺度：** `1-24h instantaneous; multiday heatwave separately specified`。**基线轨：** `P_conditional`。

| 用途 | 来源 ID 与名称 |
| --- | --- |
| 专业预报候选 | D28 NOAA GFS 0.25 degree operational forecasts；D67 NOAA HRRR operational forecasts；AW-GEFS NOAA GEFS ensemble |
| 结果参考候选 | D26 GHCN-Daily；AW-GHCNH NOAA GHCNh current hourly archive |
| 补充证据/已有 benchmark 候选 | D25 ERA5-Land Hourly；D34 MODIS LST MOD11A1.061；D47 ExEBench / EarthExtreme-Bench；D48 ExtremeWeatherBench；D62 Dheed；D66 WeatherBench2 ERA5 |
| 目录索引 | D39 EM-DAT |

**基线合同：** 最新GFS/GEFS或其他同支持预报；校准器用独立训练组。

**E 支持任务：** 单位/缩放/QC、日界和持续时间缺口的可计算支持。

**跨目标共享设计：** 区域 NWP/卫星供多站复用，站点观测按需更新。

处理要求：

- 源单位与缩放标记
- 2m气温/LST不同
- 格点到站点规则冻结
- 气候态基准仅历史训练期
- 数据源时区/日界/QC
- LST 不等于 2m 温度；ERA5/MODIS 可为结果/背景不自动 as-of 输入

**负例与缺测：** 被拒的温度QC保留，不能因极端离群就删除；热浪缺日不能自动打断或补齐。

**现有证据范围：** 已有历史高温瞬时窄链；不等于多日热浪完成。

**下一道准入门槛：** 先完成瞬时温度迁移；再核定历史气候态、当地日界、持续性与未见热浪。

**完整交付：** 同域连续输入—基线—结果链、E 规则与 F 自动结算、自然日历/极端诊断队列、独立过程分组及强 P/R 基线。D 只在 F 合格后使用固定研究损失表；原生多模态另验时间/配准/实际输入。一个子任务通过不代表该大类全部子灾种通过。

## H11 寒潮/极端低温/霜冻（D 组）

**未来任务：** 负温度越阈或固定窗口降温；专用霜冻/损伤目标另建。

**候选尺度：** `1-24h; fixed cooling interval; multiday cold event separate`。**基线轨：** `P_conditional`。

| 用途 | 来源 ID 与名称 |
| --- | --- |
| 专业预报候选 | D28 NOAA GFS 0.25 degree operational forecasts；D67 NOAA HRRR operational forecasts；AW-GEFS NOAA GEFS ensemble |
| 结果参考候选 | D26 GHCN-Daily；AW-GHCNH NOAA GHCNh current hourly archive |
| 补充证据/已有 benchmark 候选 | D25 ERA5-Land Hourly；D47 ExEBench / EarthExtreme-Bench；D48 ExtremeWeatherBench；D66 WeatherBench2 ERA5 |
| 目录索引 | D39 EM-DAT |

**基线合同：** 同高度同支持温度业务预报＋持续性，后处理训练隔离。

**E 支持任务：** 负值、冷却方向、持续时间和缺测区间。

**跨目标共享设计：** 区域温度预报/邻站共享，一个冷空气过程形成跨站目标。

处理要求：

- 允许合法负值
- 冷却幅度方向明确
- 基准期和气候区
- 跨国同一冷空气过程归组
- 2m 低温不直接给出作物损失；跨国同冷空气事件不可跨 split

**负例与缺测：** 前后端任一温度缺失，快速降温目标unresolved。

**现有证据范围：** 已有负温度历史配对；旧active_warning.v1不可直接加载。

**下一道准入门槛：** 新负值 schema、温度/降温/霜冻定义分离、独立气候基准与过程。

**完整交付：** 同域连续输入—基线—结果链、E 规则与 F 自动结算、自然日历/极端诊断队列、独立过程分组及强 P/R 基线。D 只在 F 合格后使用固定研究损失表；原生多模态另验时间/配准/实际输入。一个子任务通过不代表该大类全部子灾种通过。

## H12 冬季灾害（D 组）

**未来任务：** 未来 FZRA/FZDZ 报告或新雪/雪深/SWE 各自变量。

**候选尺度：** `1-24h; phase/report and snow accumulation separately`。**基线轨：** `P_or_R_conditional`。

| 用途 | 来源 ID 与名称 |
| --- | --- |
| 专业预报候选 | D28 NOAA GFS 0.25 degree operational forecasts；D67 NOAA HRRR operational forecasts |
| 结果参考候选 | D26 GHCN-Daily；AW-GHCNH NOAA GHCNh current hourly archive；AW-IEM IEM historical METAR archive；D55 SNODAS SWE；D33 MODIS Snow MOD10A1.061 |
| 补充证据/已有 benchmark 候选 | AW-ABI GOES-19 ABI C01 / C13；D63 DAWN |
| 目录索引 | D39 EM-DAT |

**基线合同：** 匹配变量与相态的业务预报；没有冬季概率产品的子类明确研究基线。

**E 支持任务：** 天气码/积累周期/当地日界/覆盖支持；相态可比性。

**跨目标共享设计：** 区域相态 NWP、卫星和站报服务多站/子目标。

处理要求：

- SNOW/SNWD/SWE不同变量
- FZRA/FZDZ代码与发生时间
- 雪盖不能当冻雨
- 缺测/积累周期/日界
- DAWN 是视觉辅助且缺时空时不入监测；雪盖不等于冻雨

**负例与缺测：** 雪盖无变化不证明没有冻雨或新雪；不相容子类不替代完成。

**现有证据范围：** 已有冰冻降水现象码样例；完整预报连接待做。

**下一道准入门槛：** 匹配冬季发行预报与真值；每个子类单独命名；无概率产品时明确 R 基线。

**完整交付：** 同域连续输入—基线—结果链、E 规则与 F 自动结算、自然日历/极端诊断队列、独立过程分组及强 P/R 基线。D 只在 F 合格后使用固定研究损失表；原生多模态另验时间/配准/实际输入。一个子任务通过不代表该大类全部子灾种通过。

## H13 干旱/闪旱（E 组）

**未来任务：** 下期 USDM 等级/面积产品；土壤水分恶化/闪旱速率另轨。

**候选尺度：** `weekly next-product; 2-4 week change; seasonal separate`。**基线轨：** `R_weekly_P_seasonal_conditional`。

| 用途 | 来源 ID 与名称 |
| --- | --- |
| 专业预报候选 | AW-CPC CPC Seasonal Drought Outlook |
| 结果参考候选 | D31 US Drought Monitor；D32 SMAP Enhanced L3 Soil Moisture；AW-SMAPL4 SMAP L4 SPL4SMGP v008 |
| 补充证据/已有 benchmark 候选 | AW-EDDI NOAA EDDI 01-month；D25 ERA5-Land Hourly；D30 CHIRPS v3 DAILY_SAT；D52 DroughtED；D62 Dheed |
| 目录索引 | D39 EM-DAT |

**基线合同：** CPC展望只用于相匹配季节尺度；下周USDM不能直接拿季节概率；必要时冻结持久性/统计研究模型。

**E 支持任务：** 固定版产品的等级面积支持；土壤深度/QC/时段可比性。

**跨目标共享设计：** 流域/区域 SMAP、EDDI、降水记录在周级更新周期共享。

处理要求：

- USDM既有专家参考身份
- DroughtED小数聚合不取整
- 土壤深度/植被/冻土QC
- 闪旱速率和历史基准
- ERA5等回顾数据不可伪造实时
- USDM 是已有专家评估产品；CPC 季节展望不能作下周概率；DroughtED 聚合不取整

**负例与缺测：** 周产品缺失不算干旱消失；时间修订生成新版本。

**现有证据范围：** 有周级产品样例，完整闪旱或下周专业预测匹配未定。

**下一道准入门槛：** 长期基准、历史发布版本、完整周窗；周级采用强持续性/统计 R 轨并保留产品身份。

**完整交付：** 同域连续输入—基线—结果链、E 规则与 F 自动结算、自然日历/极端诊断队列、独立过程分组及强 P/R 基线。D 只在 F 合格后使用固定研究损失表；原生多模态另验时间/配准/实际输入。一个子任务通过不代表该大类全部子灾种通过。

## H14 沙尘暴（F 组）

**未来任务：** 未来沙尘相关报告与低能见度；AOD/AI 产品代理另轨。

**候选尺度：** `1/3/6/24h; forecast run and report time matched`。**基线轨：** `P_or_R_conditional`。

| 用途 | 来源 ID 与名称 |
| --- | --- |
| 专业预报候选 | AW-CAMS CAMS dust/composition forecast；D28 NOAA GFS 0.25 degree operational forecasts；D67 NOAA HRRR operational forecasts |
| 结果参考候选 | AW-IEM IEM historical METAR archive；AW-METAR AWC METAR observations；AW-GHCNH NOAA GHCNh current hourly archive |
| 补充证据/已有 benchmark 候选 | D35 MERRA-2 aerosol diagnostics；D36 Sentinel-5P OFFL Aerosol Index；AW-ABI GOES-19 ABI C01 / C13；D63 DAWN |
| 目录索引 | D39 EM-DAT |

**基线合同：** 同发行时刻/支持范围的CAMS dust相关预报＋天气；不把AOD直接映射起沙尘暴概率。

**E 支持任务：** DS/BLDU/浮尘与烟雾/云区别；能见度删失支持。

**跨目标共享设计：** 同起报 CAMS 区域尘埃场、天气与卫星共享多站。

处理要求：

- DS/BLDU/浮尘区分
- 烟/沙尘/云质量区分
- 站点能见度删失与单位
- 尘埃专属变量和产品版本
- 尘埃 AOD 不能直接定义地面沙尘暴；OFFL/MERRA-2 不能伪造实时输入

**负例与缺测：** 低能见度无沙尘码时只做低能见度结果；未报告归因不强贴标签。

**现有证据范围：** 已有DS/BLDU历史样例，连接同期预报待做。

**下一道准入门槛：** 同期起报版本与地面报告、 dust 变量语义、独立概率校准或明确研究融合基线。

**完整交付：** 同域连续输入—基线—结果链、E 规则与 F 自动结算、自然日历/极端诊断队列、独立过程分组及强 P/R 基线。D 只在 F 合格后使用固定研究损失表；原生多模态另验时间/配准/实际输入。一个子任务通过不代表该大类全部子灾种通过。

## H15 浓雾/极端低能见度（F 组）

**未来任务：** 未来 routine METAR 支持窗能见度低于 1000m；FG 子类单独确认。

**候选尺度：** `1/3/6h report slots; fog subtype separate`。**基线轨：** `P_conditional_after_TAF_and_calibration`。

| 用途 | 来源 ID 与名称 |
| --- | --- |
| 专业预报候选 | AW-TAF AWC TAF forecasts；D28 NOAA GFS 0.25 degree operational forecasts；D67 NOAA HRRR operational forecasts |
| 结果参考候选 | AW-METAR AWC METAR observations；AW-GHCNH NOAA GHCNh current hourly archive；D27 ISD / Global Hourly |
| 补充证据/已有 benchmark 候选 | AW-ABI GOES-19 ABI C01 / C13；D63 DAWN；D53 M4Fog |

**基线合同：** 完整TAF条件段和修订，不止prevailing；TEMPO不能任意转0.5；PROB需保留原时空/时间范围。

**E 支持任务：** 原生 SM/米、P6SM/9999 区间、报告覆盖与 TAF 条件段可比性。

**跨目标共享设计：** 同域同刻 ABI 服务机场群，邻站 METAR 产生不同证据选择。

处理要求：

- 原生米/SM精确转换而非舍入衍生列
- P6SM/9999删失区间
- INITIAL/FM/BECMG/TEMPO/PROB和跨月
- SN/FZRA/烟/尘与FG不同
- M4Fog未来云图不当未来雾mask
- SN/FZRA/烟/尘不能当纯雾；M4Fog 未来云图不是未来雾 mask

**负例与缺测：** 阈值恰等于1000m与严格<1000不同；不使用特殊报告时间本身给模型泄露未来风险。

**现有证据范围：** 美国低能见度窄链已通，正例含降雪；M4Fog原生包仍是缺口。

**下一道准入门槛：** 完整 INITIAL/FM/BECMG/TEMPO/PROB/COR、原生阈值、连续多站、真实同期平台；TEMPO 不赋 0.5。

**完整交付：** 同域连续输入—基线—结果链、E 规则与 F 自动结算、自然日历/极端诊断队列、独立过程分组及强 P/R 基线。D 只在 F 合格后使用固定研究损失表；原生多模态另验时间/配准/实际输入。一个子任务通过不代表该大类全部子灾种通过。

## H16 天气相关野火/火险（E 组）

**未来任务：** 已知火场的未来检测/扩张；未来火险指数产品为独立子轨。

**候选尺度：** `24/48h known-fire activity/spread; index forecast separate`。**基线轨：** `R_spread_P_index_conditional`。

| 用途 | 来源 ID 与名称 |
| --- | --- |
| 专业预报候选 | AW-GWIS GWIS FWI map service；AW-EFFIS EFFIS fire danger service |
| 结果参考候选 | D23 NASA FIRMS；D24 MTBS burned-area boundaries；D18 CEMS Rapid Mapping；D65 FPA-FOD6 |
| 补充证据/已有 benchmark 候选 | D19 WildfireSpreadTS；D20 Next Day Wildfire Spread；D21 TS-SatFire；D22 Sen2Fire；AW-ABI GOES-19 ABI C01 / C13；D43 Sentinel-2 SR Harmonized；D45 CrisisMMD v2.0；D28 NOAA GFS 0.25 degree operational forecasts；AW-GEFS NOAA GEFS ensemble |
| 目录索引 | D39 EM-DAT |

**基线合同：** GWIS/EFFIS FWI作为指数预报且共享上游；蔓延任务需匹配的研究/专业基线，不能把FWI当点火概率。

**E 支持任务：** 有效卫星覆盖下活动/周界面积支持，版本与时间差可比性。

**跨目标共享设计：** 天气场/卫星瓦片服务多个火场；GWIS/EFFIS 共享上游须识别。

处理要求：

- 热异常/活动火/烧痕/周界不同
- 未来天气特征as-of
- 卫星覆盖/云/探测时间
- GWIS/EFFIS同源不计两个模型
- 确认标注图例
- 火点/活动/烧痕/周界/火险不同；不从相关天气推断点火因果；未来天气特征须 as-of

**负例与缺测：** 无热点不证明熄灭；未知覆盖保留；人类点火与灭火未建模限制独立说明。

**现有证据范围：** 数值火险样例已取得，共享上游和历史签发版本仍有缺口。

**下一道准入门槛：** 真实时间序列和未见火场、天气合法版本、覆盖与标签图例；同目标蔓延强 R 模型；不把 FWI 当点火概率。

**完整交付：** 同域连续输入—基线—结果链、E 规则与 F 自动结算、自然日历/极端诊断队列、独立过程分组及强 P/R 基线。D 只在 F 合格后使用固定研究损失表；原生多模态另验时间/配准/实际输入。一个子任务通过不代表该大类全部子灾种通过。

## 来源状态索引

97 个条目的名称、继承状态、计划用途和仍需通过的门槛见 [SOURCE_USAGE_MAP.json](SOURCE_USAGE_MAP.json)。其中未分配核心目标的候选继续保留，不为了“使用全部数据集”强塞入任务。
