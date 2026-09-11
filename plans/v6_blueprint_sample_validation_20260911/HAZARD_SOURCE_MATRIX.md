# 16 类灾害的完整数据合同

覆盖整个 benchmark；每类包含子类、固定未来目标、结果身份、数据源、自然时间尺度与剩余门槛。所有 E/F/D 正式任务编译与准入均待完成。本表为设计，不是 16 类已完成的数据集声明。

O = 观测；P = 分析/遥感/融合/专家产品；R = 规定体系的确认报告。旧蓝图 A 统一别名为 P。

## H01 热带气旋

组别：气旋与非对流风暴。子类：强度；路径；局地风影响另设。

**固定目标：** 已监测气旋在固定未来 T 的最大持续风或位置；不得根据事后登陆结果选择监测时刻。

**结果：** P。**时间尺度：** 6-72h；按公告合法有效时刻对齐。

| 数据角色 | 选定来源 |
| --- | --- |
| 可用专业预报来源候选 | D01 NHC forecast advisories / GIS |
| 观测/结果 | AW-HURDAT2 NHC HURDAT2 Atlantic; D02 IBTrACS v4r01 |
| 辅助证据/已有 benchmark | AW-ABI GOES-19 ABI C01 / C13; D50 CyPortQA |
| 条件扩展/不计当前完成 | D03 Digital Typhoon V2; D04 TCIR; D73 CMA Best Track |

**处理规则：**

- storm_id 与 UTC 时刻精确连接，不默认时间插值。
- 风速平均时长/机构/盆地保留；最佳路径机构差异不平均成唯一真值。
- HURDAT2、事后 IBTrACS 只进私有结果层；同风暴洪水/潮位任务共享事件组。

**目前证据与缺口：** 既有数值预报—参考匹配最完整；四个风暴都是已暴露开发材料，正式历史 as-of 待证。

逐来源真实样例与回执见 [数据源清单](SOURCE_SAMPLE_INVENTORY.md)。

## H02 温带风暴/非对流大风

组别：气旋与非对流风暴。子类：持续风；阵风；风暴系统。

**固定目标：** 固定站点/区域未来窗口持续风或阵风越阈；非对流归因单列。

**结果：** O / R。**时间尺度：** 6-48h；点值与窗内最大分开。

| 数据角色 | 选定来源 |
| --- | --- |
| 可用专业预报来源候选 | D28 NOAA GFS 0.25 degree operational forecasts; AW-GEFS NOAA GEFS ensemble; D67 NOAA HRRR operational forecasts |
| 观测/结果 | AW-GHCNH NOAA GHCNh current hourly archive; AW-METAR AWC METAR observations |
| 辅助证据/已有 benchmark | D05 NOAA Storm Events Database; D48 ExtremeWeatherBench |
| 条件扩展/不计当前完成 | D27 ISD / Global Hourly |

**处理规则：**

- 10m 持续风、阵风、测量高度和平均时长分别存储。
- 冻结网格到站点方法；阵风预报的时间支持不能直接当持续风。
- 非对流身份必须有过程/产品依据，否则仅名为大风任务。

**目前证据与缺口：** 站点与未来预报字段均实际可读；同窗匹配、QC、极端正例及非对流归因待完成。

逐来源真实样例与回执见 [数据源清单](SOURCE_SAMPLE_INVENTORY.md)。

## H03 雷暴大风/下击暴流

组别：强对流。子类：对流阵风；下击暴流专门子类。

**固定目标：** 固定未来时空窗口的合格对流阵风 O 或雷暴大风报告 R；两种结果分开。

**结果：** O / R。**时间尺度：** 分钟至小时；SPC 使用原有效窗。

| 数据角色 | 选定来源 |
| --- | --- |
| 可用专业预报来源候选 | AW-SPC SPC Day 1 convective outlook; D67 NOAA HRRR operational forecasts |
| 观测/结果 | AW-GHCNH NOAA GHCNh current hourly archive; AW-METAR AWC METAR observations; D05 NOAA Storm Events Database |
| 辅助证据/已有 benchmark | D08 NOAA NEXRAD Level II; AW-ABI GOES-19 ABI C01 / C13; D06 SEVIR |
| 条件扩展/不计当前完成 | D49 WeatherQA |

**处理规则：**

- VIL、反射率、雷电和阵风保持各自语义。
- 下击暴流不能只由强风或高 VIL 自动标注。
- 报告无记录仅能作完备报告库下的 R 负例，不能作 O 的物理无灾标签。

**目前证据与缺口：** SPC 多边形、NEXRAD 体扫与站报均可用；地面测量和过程归因需建立连接。

逐来源真实样例与回执见 [数据源清单](SOURCE_SAMPLE_INVENTORY.md)。

## H04 龙卷风

组别：强对流。子类：未来事件报告；雷达感知诊断。

**固定目标：** 指定未来窗口内是否有按冻结数据库确认的龙卷报告 R；TorNet 现时标签只作独立诊断。

**结果：** R。**时间尺度：** 分钟至小时；区域 outlook 目标保留其时空支持。

| 数据角色 | 选定来源 |
| --- | --- |
| 可用专业预报来源候选 | AW-SPC SPC Day 1 convective outlook |
| 观测/结果 | D05 NOAA Storm Events Database |
| 辅助证据/已有 benchmark | D08 NOAA NEXRAD Level II; AW-ABI GOES-19 ABI C01 / C13; D06 SEVIR |
| 条件扩展/不计当前完成 | D07 TorNet / v1.1 check; D49 WeatherQA; D70 ESWD |

**处理规则：**

- 不把 TorNet 同时刻分类当成提前预测。
- 选窗截止必须早于目标开始，轨迹及报告修订版本保留。
- 同一母风暴多体扫跨县报告归组；原作者 split 与本项目暴露状态并存。

**目前证据与缺口：** 报告和雷达源成立；TorNet 仍只有三个已验证负例，v1.1 新正例未下载成功。

逐来源真实样例与回执见 [数据源清单](SOURCE_SAMPLE_INVENTORY.md)。

## H05 冰雹

组别：强对流。子类：地面雹径报告；雷达 MESH 代理。

**固定目标：** 未来窗口地面报告雹径越阈 R；另设同支持的未来 MESH 产品越阈 P。

**结果：** R / P。**时间尺度：** 分钟至小时。

| 数据角色 | 选定来源 |
| --- | --- |
| 可用专业预报来源候选 | AW-SPC SPC Day 1 convective outlook; D67 NOAA HRRR operational forecasts |
| 观测/结果 | D05 NOAA Storm Events Database |
| 辅助证据/已有 benchmark | D08 NOAA NEXRAD Level II; D06 SEVIR; AW-ABI GOES-19 ABI C01 / C13 |
| 条件扩展/不计当前完成 | AW-MESH MRMS MESH; D70 ESWD |

**处理规则：**

- 报告大小/测量估计属性及 inch-mm 转换保留。
- MESH 尚需局地 GRIB 单位与负代码表；数组可读不能直接准入阈值。
- SPC 25-mile 等概率定义不可原样赋给任意像元/站点小时。

**目前证据与缺口：** 报告路线可构建；MESH 已实际解码但科学语义准入未完成，P 子任务保留条件。

逐来源真实样例与回执见 [数据源清单](SOURCE_SAMPLE_INVENTORY.md)。

## H06 强雷电

组别：强对流。子类：flash 数量；有效覆盖面积密度。

**固定目标：** 固定区域未来 10-60min 内 GLM flash 密度是否越过冻结阈值。

**结果：** P。**时间尺度：** 10-60min 为拟定合同，需连续文件覆盖。

| 数据角色 | 选定来源 |
| --- | --- |
| 可用专业预报来源候选 | 无已准入专用业务预报；先用持续性/气候态/产品演化基线 |
| 观测/结果 | D10 GOES GLM (inherited sampled product) |
| 辅助证据/已有 benchmark | AW-ABI GOES-19 ABI C01 / C13; D08 NOAA NEXRAD Level II; D06 SEVIR |
| 条件扩展/不计当前完成 | 无已准入专用业务预报；先用持续性/气候态/产品演化基线 |

**处理规则：**

- flash/group/event 不混算；跨文件/边界去重。
- 按有效覆盖面积和时间归一，非观测区不能填零。
- 气候极端阈值只由训练期同传感器/季节确定；专业概率未具备时用持续性及外推基线。

**目前证据与缺口：** 三个 GLM 产品可读且已有 ABI；连续极端窗口、跨文件 ID 与密度基准待完成。

逐来源真实样例与回执见 [数据源清单](SOURCE_SAMPLE_INVENTORY.md)。

## H07 极端降水

组别：降水与水灾。子类：短时强降水；日累计暴雨；格点估计产品。

**固定目标：** 站点/区域未来固定 1/3/6/24h 累计越阈；O 与降水分析产品 P 分榜。

**结果：** O / P。**时间尺度：** 1-24h；慢日产品单独支持。

| 数据角色 | 选定来源 |
| --- | --- |
| 可用专业预报来源候选 | D28 NOAA GFS 0.25 degree operational forecasts; AW-GEFS NOAA GEFS ensemble; D67 NOAA HRRR operational forecasts |
| 观测/结果 | AW-GHCNH NOAA GHCNh current hourly archive; D26 GHCN-Daily; D30 CHIRPS v3 DAILY_SAT |
| 辅助证据/已有 benchmark | D59 MeteoNet; D48 ExtremeWeatherBench |
| 条件扩展/不计当前完成 | AW-QPE MRMS MultiSensor QPE 01H Pass2; D29 IMERG V07 Early / Late; AW-WPC WPC QPF / winter products |

**处理规则：**

- 保留起止、降水率/累计量及累计重置，禁止重叠窗口相加。
- GHCNd 当地站日不可假作 UTC 日；GFS 0-6h 必须匹配同窗。
- MRMS Pass2 的处理滞后单列；CHIRPS DAILY_SAT 上游依赖不得当独立站雨量。

**目前证据与缺口：** GFS/GEFS 未来累计和实际站雨量可读；新增 MRMS QPE 数组可读但单位/累计窗/代码表未准入；IMERG 401。

逐来源真实样例与回执见 [数据源清单](SOURCE_SAMPLE_INVENTORY.md)。

## H08 洪水/山洪/城市内涝

组别：降水与水灾。子类：河洪；山洪报告；空间淹没/城市内涝。

**固定目标：** 河站未来水位或流量越阈 O；山洪 R 与未来合格淹没图 P 各自固定目标。

**结果：** O / R / P。**时间尺度：** 河洪 6-72h；山洪短时；空间图按实际过境窗。

| 数据角色 | 选定来源 |
| --- | --- |
| 可用专业预报来源候选 | D57 NWPS stage forecasts; AW-HEFS NOAA HEFS QINE ensemble |
| 观测/结果 | D56 USGS continuous observations; D05 NOAA Storm Events Database |
| 辅助证据/已有 benchmark | D12 GEOID-Flood; D18 CEMS Rapid Mapping; D60 Caravan; D61 HANZE v2.1 |
| 条件扩展/不计当前完成 | AW-GLOFAS GloFAS operational forecast; AW-EFAS EFAS operational forecast; AW-NIMS USGS NIMS cameras; D15 Sen1Floods11 v1.1; D13 KuroSiwo; D14 UrbanSARFloods; D51 WorldFloods v2 / ml4floods |

**处理规则：**

- 用官方站号桥；水位/流量及垂直基准不互换。
- HEFS CFS 需要同变量阈值及成员权重，不直接生成洪水水位概率。
- SAR 标签保留永久水、无效/遮挡、地图制作时刻；城市子类须有城市证据，河洪不补其名额。

**目前证据与缺口：** 两站业务预报—观测连接已核；观测暂为 Provisional。GEOID 三个负瓦片已暴露；城市/山洪的完整 F 路线未通过。

逐来源真实样例与回执见 [数据源清单](SOURCE_SAMPLE_INVENTORY.md)。

## H09 风暴潮/沿岸淹没

组别：降水与水灾。子类：沿岸总水位；增水残差；空间淹没。

**固定目标：** 固定潮位站未来窗口总水位越同基准阈值 O；增水与淹没范围另设任务。

**结果：** O。**时间尺度：** 1-48h；以合格模型和潮位覆盖为准。

| 数据角色 | 选定来源 |
| --- | --- |
| 可用专业预报来源候选 | 无已准入专用业务预报；先用持续性/气候态/产品演化基线 |
| 观测/结果 | D37 NOAA CO-OPS water levels |
| 辅助证据/已有 benchmark | D58 NDBC Buoys; D01 NHC forecast advisories / GIS |
| 条件扩展/不计当前完成 | AW-OFS NOAA CBOFS station forecast; AW-PETSS NOAA P-ETSS tide/surge station bulletins |

**处理规则：**

- 首选实际采集到的 CBOFS/P-ETSS 配对候选；站位/基准未核前不作正式专业基线。
- P-ETSS 当前公告明确不适用于热带风暴，气旋沿岸子类必须另验证 P-Surge 等产品。
- 天文潮不是总水位预报；残差不唯一归因为风暴潮，波高不是潮位。

**目前证据与缺口：** 真实 OFS 数组、P-ETSS 数值表与潮位站样例俱在；正式站号、基准、产品适用范围是剩余核心门槛。

逐来源真实样例与回执见 [数据源清单](SOURCE_SAMPLE_INVENTORY.md)。

## H10 高温/热浪

组别：温度与冬季天气。子类：点/日高温；连续热浪。

**固定目标：** 未来指定时刻/站日高温越阈，或固定多日窗满足气候相对阈值与持续规则。

**结果：** O。**时间尺度：** 6h-7d，点值/日极值/持续过程分开。

| 数据角色 | 选定来源 |
| --- | --- |
| 可用专业预报来源候选 | D28 NOAA GFS 0.25 degree operational forecasts; AW-GEFS NOAA GEFS ensemble; D67 NOAA HRRR operational forecasts |
| 观测/结果 | AW-GHCNH NOAA GHCNh current hourly archive; D26 GHCN-Daily |
| 辅助证据/已有 benchmark | D48 ExtremeWeatherBench |
| 条件扩展/不计当前完成 | D47 ExEBench / EarthExtreme-Bench; D25 ERA5-Land Hourly; D34 MODIS LST MOD11A1.061 |

**处理规则：**

- 2m 气温、皮肤温度、体感指标不得互换。
- 小时采样最大不是整日连续最大；热浪须完整持续窗与固定季节基准。
- 基准期/地区阈值仅在开发侧确定，站点移动和 QC 纳入。

**目前证据与缺口：** GHCNh 2026 记录与 +6h 预报实际可读；EWB 事件与观测未全连接，ExEBench 热浪包尚未取样。

逐来源真实样例与回执见 [数据源清单](SOURCE_SAMPLE_INVENTORY.md)。

## H11 寒潮/低温/霜冻

组别：温度与冬季天气。子类：绝对低温；快速降温；空气霜冻条件。

**固定目标：** 未来固定窗口低温越阈或满足降温幅度/持续规则；实际作物损害独立排除。

**结果：** O。**时间尺度：** 6h-7d。

| 数据角色 | 选定来源 |
| --- | --- |
| 可用专业预报来源候选 | D28 NOAA GFS 0.25 degree operational forecasts; AW-GEFS NOAA GEFS ensemble; D67 NOAA HRRR operational forecasts |
| 观测/结果 | AW-GHCNH NOAA GHCNh current hourly archive; D26 GHCN-Daily |
| 辅助证据/已有 benchmark | D47 ExEBench / EarthExtreme-Bench; D48 ExtremeWeatherBench |
| 条件扩展/不计当前完成 | D25 ERA5-Land Hourly |

**处理规则：**

- 温降必须有两个合格支持窗口；缺前值不可生成寒潮标签。
- 空气 0 摄氏度附近条件不等于实际地表结霜或损害。
- ExEBench 事后案例只作检索/诊断，不暴露其极端结果给未来模型。

**目前证据与缺口：** 寒潮 benchmark 实包、站观测与通用预报均有样例；逐过程独立性、阈值和未来配对待完成。

逐来源真实样例与回执见 [数据源清单](SOURCE_SAMPLE_INVENTORY.md)。

## H12 暴雪/积雪/冰冻降水

组别：温度与冬季天气。子类：新降雪；积雪/SWE；冻雨/冻毛毛雨；暴风雪条件。

**固定目标：** 未来固定窗的降雪/积雪越阈，或站点出现 FZRA/FZDZ；SWE 分列 P。

**结果：** O / P / R。**时间尺度：** 1-48h；积雪日尺度另列。

| 数据角色 | 选定来源 |
| --- | --- |
| 可用专业预报来源候选 | D28 NOAA GFS 0.25 degree operational forecasts; D67 NOAA HRRR operational forecasts |
| 观测/结果 | D26 GHCN-Daily; AW-GHCNH NOAA GHCNh current hourly archive; AW-METAR AWC METAR observations; AW-IEM IEM historical METAR archive; D55 SNODAS SWE |
| 辅助证据/已有 benchmark | D05 NOAA Storm Events Database |
| 条件扩展/不计当前完成 | AW-WPC WPC QPF / winter products; D33 MODIS Snow MOD10A1.061 |

**处理规则：**

- 雪深、SWE、新降雪及冻雨分别建 target。
- 实际已取得 FZRA/FZDZ 正例站报；GFS/HRRR 分类是输入预报。
- 暴风雪需要同时满足风、能见度、雪和持续规则；积雪正例不能替代。

**目前证据与缺口：** 已补冻雨真实正例，SNODAS 与站雪字段可用；WPC 冬季概率数组、暴风雪完整多变量样例仍缺。

逐来源真实样例与回执见 [数据源清单](SOURCE_SAMPLE_INVENTORY.md)。

## H13 干旱/闪旱

组别：干旱与火险。子类：USDM 周等级；独立定义的快速土壤干旱。

**固定目标：** 未来指定 USDM 周版等级/面积越阈 P；闪旱以冻结快速下降、持续和恢复规则另建。

**结果：** P。**时间尺度：** 周到季；闪旱按五日/日产品可用支持另定。

| 数据角色 | 选定来源 |
| --- | --- |
| 可用专业预报来源候选 | 无已准入专用业务预报；先用持续性/气候态/产品演化基线 |
| 观测/结果 | D31 US Drought Monitor |
| 辅助证据/已有 benchmark | AW-EDDI NOAA EDDI 01-month; AW-CPC CPC Seasonal Drought Outlook; D30 CHIRPS v3 DAILY_SAT |
| 条件扩展/不计当前完成 | AW-SMAPL4 SMAP L4 SPL4SMGP v008; D32 SMAP Enhanced L3 Soil Moisture; D52 DroughtED; D25 ERA5-Land Hourly |

**处理规则：**

- USDM 有效日与发布日分开；专家分析是既有 P，不新增逐题人工评审。
- CPC 季节 outlook 只在匹配季节目标时作基线，其余作背景。
- SMAP L4 根区水分需完整序列、质量/冻土掩膜与基准；EDDI 不单独充当闪旱真值。

**目前证据与缺口：** USDM 周图、EDDI 数组、CPC 矢量均真实可读；持续性/转移基线可设计，闪旱数值源受 401 阻塞。

逐来源真实样例与回执见 [数据源清单](SOURCE_SAMPLE_INVENTORY.md)。

## H14 沙尘暴

组别：低能见度与沙尘。子类：站点沙尘暴；浮尘/扬沙对照；沙尘成分产品。

**固定目标：** 固定站点未来窗口出现 DS/SS 等规定现象并满足能见度条件；气溶胶产品另列 P 扩展。

**结果：** O。**时间尺度：** 1-24h。

| 数据角色 | 选定来源 |
| --- | --- |
| 可用专业预报来源候选 | D28 NOAA GFS 0.25 degree operational forecasts; D67 NOAA HRRR operational forecasts |
| 观测/结果 | AW-GHCNH NOAA GHCNh current hourly archive; AW-METAR AWC METAR observations; AW-IEM IEM historical METAR archive |
| 辅助证据/已有 benchmark | AW-ABI GOES-19 ABI C01 / C13 |
| 条件扩展/不计当前完成 | AW-CAMS CAMS dust/composition forecast; D35 MERRA-2 aerosol diagnostics; D36 Sentinel-5P OFFL Aerosol Index |

**处理规则：**

- DS 与 BLDU、BR、HZ 不混同；只统计主站报，排除 RMK/vicinity。
- 通用能见度预报不是沙尘专属概率；基线需现象分类/校准。
- 高 AOD 不自动作地面沙尘暴 Gold。

**目前证据与缺口：** Phoenix 实际 5 条 DS 和 10 条 BLDU 已补；CAMS 没有匿名数值样例，当前先走站点现象路线。

逐来源真实样例与回执见 [数据源清单](SOURCE_SAMPLE_INVENTORY.md)。

## H15 浓雾/极端低能见度

组别：低能见度与沙尘。子类：雾现象；低能见度；海雾扩展。

**固定目标：** 站点未来窗口能见度低于阈值；浓雾额外要求 FG/FZFG 与持续性。

**结果：** O。**时间尺度：** 1-24h；以 TAF 变化组及站报支持为准。

| 数据角色 | 选定来源 |
| --- | --- |
| 可用专业预报来源候选 | AW-TAF AWC TAF forecasts; D28 NOAA GFS 0.25 degree operational forecasts; D67 NOAA HRRR operational forecasts |
| 观测/结果 | AW-METAR AWC METAR observations; AW-GHCNH NOAA GHCNh current hourly archive |
| 辅助证据/已有 benchmark | AW-ABI GOES-19 ABI C01 / C13; D27 ISD / Global Hourly |
| 条件扩展/不计当前完成 | D53 M4Fog |

**处理规则：**

- TAF 与 METAR 同机场身份，FM/TEMPO/PROB 分组明确解释。
- 10+SM 等区间值不变成精确值；站点缺报不能标无雾。
- 低能见度成因与浓雾标签分开，海雾需对应海域观测合同。

**目前证据与缺口：** 三站真实 TAF/METAR 与小时归档已可解析；M4Fog 未得到 cube，不让其阻断站点主线。

逐来源真实样例与回执见 [数据源清单](SOURCE_SAMPLE_INVENTORY.md)。

## H16 天气相关野火/火险

组别：干旱与火险。子类：火险指数；已知火场活动产品扩展。

**固定目标：** 已知火场未来固定观测窗活动火产品面积/像素变化 P；火险指数越阈单独定义。

**结果：** P。**时间尺度：** 数小时至数日；固定合格观测窗。

| 数据角色 | 选定来源 |
| --- | --- |
| 可用专业预报来源候选 | 无已准入专用业务预报；先用持续性/气候态/产品演化基线 |
| 观测/结果 | D19 WildfireSpreadTS; D23 NASA FIRMS |
| 辅助证据/已有 benchmark | D28 NOAA GFS 0.25 degree operational forecasts; AW-GEFS NOAA GEFS ensemble; AW-ABI GOES-19 ABI C01 / C13 |
| 条件扩展/不计当前完成 | D21 TS-SatFire; AW-GWIS GWIS FWI map service; AW-EFFIS EFFIS fire danger service; D20 Next Day Wildfire Spread; D24 MTBS burned-area boundaries; D65 FPA-FOD6 |

**处理规则：**

- 热点先按冻结时空规则归并火场，气象驱动不等于起火原因证明。
- 下一次合格观测必须限制在预定窗口内，超窗仍为未结算，不能根据结果任意延后。
- FWI、活动火、烧毁面积分开；无热点与无覆盖/云遮不能直接解释为扑灭。

**目前证据与缺口：** 真实火场日栅格和 FIRMS 热点可用；多火场正扩展样例仍缺，FWI 目前只有渲染图，没有已验证数值业务预报。

逐来源真实样例与回执见 [数据源清单](SOURCE_SAMPLE_INVENTORY.md)。
