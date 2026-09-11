# 数据源逐项样例与选择清单

本表包含继承的 74 项登记及本轮拆分/新增产品；条目数不是独立传感器或数据集数量。主方案只采用下表明确选定的角色。样例可解析与正式任务准入分开；本轮新正式任务为 0。

本轮新样例的最终科学审计为 [NEW_SAMPLE_AUDIT_05.json](NEW_SAMPLE_AUDIT_05.json)。旧数据只重核哈希并复用原解析结论，见 [INHERITED_SAMPLE_AUDIT.json](INHERITED_SAMPLE_AUDIT.json) 和 [INHERITED_JOIN_BINDINGS.json](INHERITED_JOIN_BINDINGS.json)。

| ID / 数据源 | 选择 / 样例状态 | 实际证据 | 使用限制 |
| --- | --- | --- | --- |
| [D01 NHC forecast advisories / GIS](INHERITED_JOIN_BINDINGS.json) | selected_with_gates / inherited_join_rehashed | 64 份公告、461 行数字预报；4 个已暴露风暴组，96 个唯一时刻有事后参考匹配。 | 96 个匹配目标不是 96 场独立气旋；历史公开可用时间仍未证实。 |
| [D02 IBTrACS v4r01](INHERITED_SAMPLE_AUDIT.json) | selected_with_gates / inherited_numeric | 已解码 21,923 条轨迹记录、378 个 SID；作分盆地事后分析参考。 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| [D03 Digital Typhoon V2](INHERITED_SAMPLE_AUDIT.json) | reserve_not_selected / inherited_partial | Digital Typhoon ZIP Range 获取未完成；保留亚洲气旋扩容路线，不把目录计为帧。 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| [D04 TCIR](INHERITED_SAMPLE_AUDIT.json) | reserve_not_selected / inherited_reference | TCIR 仅入口/读取器候选；尚未完成真实影像解码，需确认版本和切分。 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| [D05 NOAA Storm Events Database](INHERITED_SAMPLE_AUDIT.json) | selected_with_gates / inherited_catalog | 136,982 条实际灾害报告；作事件检索及独立定义的 R 结果。 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| [D06 SEVIR](INHERITED_SAMPLE_AUDIT.json) | selected_with_gates / inherited_inherited | 3 条完整 VIL 序列，每条 49 帧；用于雷达时序感知。 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| [D07 TorNet / v1.1 check](INHERITED_SAMPLE_AUDIT.json) | conditional_positive_sample / inherited_negatives_new_archive_partial | 继承 3 个可解码 train 负例；本轮确认 v1.1 发布记录，新增归档前缀超时、无完整成员。 | 新增前缀不是成功 NetCDF 样本；仍缺实际正例及其与预警窗口的桥接。 |
| [D08 NOAA NEXRAD Level II](captures_02/nexrad-sample.json) | selected_with_gates / new_radar_arrays_decoded | KTLX 2026-09-10 00:01:20.788 完整体扫，12 个 sweep，反射率/偏振矩可解析。 | MetPy 报 unknown message 32；并非所有报文或科学 QC 都已验证。 |
| [D09 NOAA MRMS](INHERITED_SAMPLE_AUDIT.json) | product_family_parent / inherited_metadata | MRMS 桶目录可列，尚无实际 MESH/降水文件；不能将 MESH 估计直接等同地面冰雹报告。 | 本轮 MESH 与 QPE 的实际样例分别见 AW-MESH/AW-QPE；父目录不重复计算为第三个来源。 |
| [D10 GOES GLM (inherited sampled product)](INHERITED_SAMPLE_AUDIT.json) | selected_with_gates / inherited_numeric | 3 个 GLM 20 秒文件及父子 ID 已校验；须构建空间密度基线并补极端窗口；ABI 尚未取样。 | 本项实际继承 3 个 20 秒 GLM 产品；新 ABI 样例单列 AW-ABI，避免重复统计。 |
| [D11 Global Flood Database v1](INHERITED_SAMPLE_AUDIT.json) | reserve_not_selected / inherited_reference | GFD 入口明确但没有实际事件栅格；GEE 项目访问与公开替代产品分开记录。 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| [D12 GEOID-Flood](INHERITED_SAMPLE_AUDIT.json) | selected_auxiliary_or_diagnostic / inherited_paired | 3 组前后 SAR/标签/有效性配对；均为同一外部 test 激活下的洪水负瓦片。 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| [D13 KuroSiwo](INHERITED_SAMPLE_AUDIT.json) | reserve_not_selected / inherited_unverified | KuroSiwo 的 HF 连接失败；下一轮锁定版本后仅取 train 正负样例，不承诺整个数据不可用。 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| [D14 UrbanSARFloods](INHERITED_SAMPLE_AUDIT.json) | reserve_not_selected / inherited_unverified | UrbanSARFloods 的 HF 连接失败；保留城市内涝候选，必须验证城市标签/事件身份。 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| [D15 Sen1Floods11 v1.1](INHERITED_SAMPLE_AUDIT.json) | conditional_rights / inherited_inherited | 已复核 3 个 Sen1Floods11 图像标签对、2 个事件地区；许可字段存在歧义，先澄清数据再分发条款。 | 已有真实配对样例；数据再分发条款歧义未解，先保留配方和引用。 |
| [D16 SpaceNet 8](INHERITED_SAMPLE_AUDIT.json) | reserve_not_selected / inherited_reference | SpaceNet8 读取文档可得；本轮未获取成对影像/道路标签，需保留原 split 并分开洪水与道路状态语义。 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| [D17 FloodNet](INHERITED_SAMPLE_AUDIT.json) | reserve_not_selected / inherited_reference | FloodNet 文档可得，真实图像/标签未取样；无人机图像多样性不等于多个风暴。 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| [D18 CEMS Rapid Mapping](INHERITED_SAMPLE_AUDIT.json) | selected_event_bridge / inherited_catalog | CEMS EMSR712/AOI10 产品与影像时刻已列举；部分版本状态 N、无产品，不能当成成功下载或同目标修订。 | 已取得产品目录与时空身份链；目录可读不等于所有原生地图已下载。 |
| [D19 WildfireSpreadTS](INHERITED_SAMPLE_AUDIT.json) | selected_with_gates / inherited_numeric | 一个火场 3 天 TIFF；活动火像素 4/0/0，不能解释为后两天灭火。 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| [D20 Next Day Wildfire Spread](INHERITED_SAMPLE_AUDIT.json) | reserve_not_selected / inherited_partial | Next Day Wildfire ZIP 前缀已取得，TFRecord 尚未解码；需字段、CRC 和标签时距核验。 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| [D21 TS-SatFire](INHERITED_SAMPLE_AUDIT.json) | conditional_target_semantics / inherited_numeric | TS-SatFire 3 天同一火场 19 波段栅格可解码；最终标签通道和未来标签切片仍需读取器验证。 | 真实 19 波段数组可读；未来目标通道和有效掩膜语义未完成准入。 |
| [D22 Sen2Fire](INHERITED_SAMPLE_AUDIT.json) | reserve_not_selected / inherited_unverified | Sen2Fire 尚未获取实际图像；只在需要独立火场/新地区时补源，不与同源火点重复计数。 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| [D23 NASA FIRMS](INHERITED_SAMPLE_AUDIT.json) | selected_with_gates / inherited_numeric | 匿名 VIIRS CSV 有 2,606 条热点；尚未归并为火场。 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| [D24 MTBS burned-area boundaries](INHERITED_SAMPLE_AUDIT.json) | reserve_not_selected / inherited_unverified | MTBS 公开直链尝试失败；不必把 GEE 作为唯一入口，后续检查官方周界产品和许可。 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| [D25 ERA5-Land Hourly](INHERITED_SAMPLE_AUDIT.json) | reserve_not_selected / inherited_unverified | ERA5-Land 未实际验证；已有 WeatherBench2 ERA5 chunk 不能代替 ERA5-Land 认证与变量验证。 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| [D26 GHCN-Daily](INHERITED_SAMPLE_AUDIT.json) | selected_with_gates / inherited_numeric | 5 个站点窗口共 40 个站日，实际温度/降水/雪字段可读。 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| [D27 ISD / Global Hourly](INHERITED_SAMPLE_AUDIT.json) | legacy_historical_only / inherited_numeric | 北京和沙特两个站年 28,733 报告；实有雾及浮/扬尘码，未发现本批沙尘暴/冻雨码正例。 | ISD 已被 GHCNh 替代；保留旧冻结资产兼容，不用于持续获取当前站点数据。 |
| [D28 NOAA GFS 0.25 degree operational forecasts](captures_02/gfs-t2m.json) | selected_with_gates / new_future_grib_decoded | 2026-09-10 00Z 起报、+6h：温度、10m U/V、0-6h 累计降水、能见度、阵风、冻雨分类，共 7 条完整 GRIB。 | 同一次起报不构成修订序列；690 个冻雨非零格点属于预报，不是冻雨实测。 |
| [D29 IMERG V07 Early / Late](captures_03/imerg-early-list.json) | conditional_authentication / authentication_required_no_array | Early/Late GIS 归档请求均为 401；本轮没有实际 IMERG 数组。 | 保留需账号/条款配置的扩展路线；本轮匿名尝试失败不证明数据科学上不可用。 |
| [D30 CHIRPS v3 DAILY_SAT](INHERITED_SAMPLE_AUDIT.json) | selected_with_gates / inherited_numeric | CHIRPS v3 DAILY_SAT 两个完整日栅格；用于明确标注的降水产品结果/背景。 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| [D31 US Drought Monitor](INHERITED_SAMPLE_AUDIT.json) | selected_with_gates / inherited_inherited | 3 个实际 USDM 周产品；采用既有专家分析等级，程序化提取。 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| [D32 SMAP Enhanced L3 Soil Moisture](INHERITED_SAMPLE_AUDIT.json) | reserve_not_selected / inherited_unverified | SMAP 无实测土壤湿度切片；干旱/闪旱升级时再补，先确认冻土/植被与质量标记。 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| [D33 MODIS Snow MOD10A1.061](INHERITED_SAMPLE_AUDIT.json) | reserve_not_selected / inherited_unverified | MODIS Snow 未实测；雪盖与降雪/暴雪/冻雨分开，当前 SNODAS 可作为积雪补源。 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| [D34 MODIS LST MOD11A1.061](INHERITED_SAMPLE_AUDIT.json) | reserve_not_selected / inherited_unverified | MODIS LST 未实测；地表温度不能替代 2 米气温热浪标签。 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| [D35 MERRA-2 aerosol diagnostics](INHERITED_SAMPLE_AUDIT.json) | reserve_not_selected / inherited_reference | MERRA-2 气溶胶仅文档与入口；优先补 dust 专属变量并与现象码配对，不能以高 AOD 单独判沙尘暴。 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| [D36 Sentinel-5P OFFL Aerosol Index](INHERITED_SAMPLE_AUDIT.json) | reserve_not_selected / inherited_unverified | S5P Aerosol Index 尚无实际切片；需将沙尘、烟羽、云和缺测区分。 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| [D37 NOAA CO-OPS water levels](INHERITED_SAMPLE_AUDIT.json) | selected_with_gates / inherited_numeric | 3 个潮位站共 720 对同基准观测/天文潮预报；不是完整风暴潮预报。 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| [D38 NOAA OISST v2.1](INHERITED_SAMPLE_AUDIT.json) | reserve_not_selected / inherited_numeric | OISST 3 个日 NetCDF 可读；海洋热浪为扩展方向，需长期气候态与持续性定义。 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| [D39 EM-DAT](INHERITED_SAMPLE_AUDIT.json) | reserve_not_selected / inherited_unverified | EM-DAT 注册和许可入口；不绕过访问条件；ExEBench 的案例 ID 也需检查派生使用条款。 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| [D40 NASA EONET v3](INHERITED_SAMPLE_AUDIT.json) | reserve_not_selected / inherited_unverified | EONET 为事件检索备选，尚未有本轮解码事件；不能将事件目录当像素 Gold。 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| [D41 GDACS](INHERITED_SAMPLE_AUDIT.json) | reserve_not_selected / inherited_unverified | GDACS 仅候选入口，当前未验证实际 feed；如已有 CEMS GDACS ID 再定向桥接。 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| [D42 Sentinel-1 GRD](INHERITED_SAMPLE_AUDIT.json) | reserve_not_selected / inherited_inherited_component | S1 派生资产已在洪水数据中验证；独立原始 GRD/GEE 访问未验证，不重复算独立来源增量。 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| [D43 Sentinel-2 SR Harmonized](INHERITED_SAMPLE_AUDIT.json) | reserve_not_selected / inherited_unverified | S2 原始 SR 访问尚未验证；现有 SAR/背景切片不代表其可用，按事件补光学和云质量层。 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| [D44 xBD](INHERITED_SAMPLE_AUDIT.json) | reserve_not_selected / inherited_unverified | xBD 有注册/许可门槛；建筑损伤属于下游影响，且需排除地震等非天气灾种。 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| [D45 CrisisMMD v2.0](INHERITED_SAMPLE_AUDIT.json) | reserve_not_selected / inherited_reference | CrisisMMD 仅入口候选；社交图像版权和文本真实性尚未落实，不作为因果真值。 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| [D46 Landslide4Sense](INHERITED_SAMPLE_AUDIT.json) | reserve_not_selected / inherited_paired | Landslide4Sense 已验证 3 个 train 图像掩膜对；HDF5 缺时空/事件属性，降雨诱发成因仍未确认。 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| [D47 ExEBench / EarthExtreme-Bench](INHERITED_SAMPLE_AUDIT.json) | selected_auxiliary_or_diagnostic / inherited_numeric | ExEBench 寒潮子包完整：9 个来源案例、559 时间步；不是 9 个已确认独立过程。 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| [D48 ExtremeWeatherBench](INHERITED_SAMPLE_AUDIT.json) | selected_auxiliary_or_diagnostic / inherited_numeric | EWB 329 个案例定义及一个小时站点 parquet row group 的 122,880 行；未全部配对到案例。 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| [D49 WeatherQA](INHERITED_SAMPLE_AUDIT.json) | reserve_not_selected / inherited_reference | WeatherQA 的 Drive 下载失败；SPC 2018/md0398 原文可取回；README 的 20 幅图是变量组，不是 20 个时刻。 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| [D50 CyPortQA](INHERITED_SAMPLE_AUDIT.json) | selected_auxiliary_or_diagnostic / inherited_multiformat | CyPortQA 已取得 Dorian/Harvey/Florence 各 1 图 1 文；精确公告时刻对齐及港口标签规则尚未验证。 | 3 组图文可读；公告精确时间和港口影响标签待核，不能自动作未来结果。 |
| [D51 WorldFloods v2 / ml4floods](INHERITED_SAMPLE_AUDIT.json) | reserve_not_selected / inherited_unverified | WorldFloods v2 的 HF 数据连接未完成；保留为全球光学洪水备选，核验每类源产品的许可。 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| [D52 DroughtED](INHERITED_SAMPLE_AUDIT.json) | reserve_not_selected / inherited_prefix_records | DroughtED train ZIP 前缀解析 26,666 行，含 3,809 非空周标签；实际至 2016 与文档 train 2000-2009 冲突；需固定原文件切分。 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| [D53 M4Fog](captures_01/m4fog-readme.json) | conditional_data_access / repository_and_share_page_only | README 与完整代码树可读；网盘停在提取/验证页面，未取得原生 cube。 | 不能用仓库图片替代真实样本；主雾任务先采用 TAF/METAR。 |
| [D54 CLLMate](INHERITED_SAMPLE_AUDIT.json) | reserve_not_selected / inherited_catalog | CLLMate 公共 JSON 7,747 节点已解析；包括非天气事件；新闻/原图与因果边未验证，不作因果 Gold。 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| [D55 SNODAS SWE](INHERITED_SAMPLE_AUDIT.json) | selected_with_gates / inherited_numeric | 3 个 SNODAS SWE 日网格；SWE 与新降雪深度分开。 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| [D56 USGS continuous observations](INHERITED_JOIN_BINDINGS.json) | selected_with_gates / inherited_join_rehashed | 两个正式站点映射，50 个水位样值；Scotia 另有 25 个同站流量样值。 | 当前样例均为 Provisional；地点、变量、基准及冻结质量政策逐任务绑定。 |
| [D57 NWPS stage forecasts](INHERITED_JOIN_BINDINGS.json) | selected_with_gates / inherited_join_rehashed | SCOC1/GUEC1 两站各 119 个水位预报记录，已核官方 USGS 对应关系。 | 普通 API 的滚动服务不证明历史业务版本；当前阈值不自动适用于历史。 |
| [D58 NDBC Buoys](INHERITED_SAMPLE_AUDIT.json) | selected_auxiliary_or_diagnostic / inherited_numeric | 3 个 NDBC 浮标的波浪记录；只作海岸风浪背景。 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| [D59 MeteoNet](INHERITED_SAMPLE_AUDIT.json) | selected_auxiliary_or_diagnostic / inherited_numeric | MeteoNet 111,623 条站报、484 站和红外数组；雷达 NPZ 时间对象未启用 pickle。 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| [D60 Caravan](INHERITED_SAMPLE_AUDIT.json) | selected_auxiliary_or_diagnostic / inherited_numeric | Caravan 三个美国流域，各 14,609 日；适合历史水文与属性辅助。 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| [D61 HANZE v2.1](INHERITED_SAMPLE_AUDIT.json) | selected_auxiliary_or_diagnostic / inherited_catalog | HANZE 2,521 个欧洲洪水影响目录条目；仅用于事件索引。 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| [D62 Dheed](INHERITED_SAMPLE_AUDIT.json) | reserve_not_selected / inherited_catalog | Dheed 82,839 派生干热事件记录可读；先查上游依赖和定义，不能作为另一份独立观测真值。 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| [D63 DAWN](INHERITED_SAMPLE_AUDIT.json) | reserve_not_selected / inherited_metadata | DAWN 官方 API 枚举 Fog/Rain/Sand/Snow 四包；未抽取图片，时间/地点不足时仅作视觉条件辅助集。 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| [D64 SenForFlood](INHERITED_SAMPLE_AUDIT.json) | reserve_not_selected / inherited_background | SenForFlood TAR 前缀取得 3 个 LULC TIFF；目前仅背景层，不是三组洪水图像标签对。 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| [D65 FPA-FOD6](INHERITED_SAMPLE_AUDIT.json) | reserve_not_selected / inherited_inherited | FPA-FOD6 已复核 3 条火灾记录；与 FIRMS、火烧迹地按事件合并，起火原因不能默认极端天气。 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| [D66 WeatherBench2 ERA5](INHERITED_SAMPLE_AUDIT.json) | reserve_not_selected / inherited_inherited | WeatherBench2 一个 ERA5 温度 chunk 已复核；记录为 ERA5 衍生产品，不冒充 D25 ERA5-Land。 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| [D67 NOAA HRRR operational forecasts](captures_02/hrrr-t2m.json) | selected_with_gates / new_future_grib_decoded | 同一 00Z 起报 +6h：气温、能见度、冻雨分类，1799×1059。 | 冻雨样例全零；仅确认数值字段可读，尚无实际冬季正例链。 |
| [D68 HKO-7](INHERITED_SAMPLE_AUDIT.json) | reserve_not_selected / inherited_catalog | HKO-7 仓库日天气统计 2,556 行可读；实际雷达序列尚未取样。 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| [D69 GESLA current / GESLA-3 candidate](INHERITED_SAMPLE_AUDIT.json) | reserve_not_selected / inherited_metadata | GESLA 站点目录可读；现端点报告 format 5.0/2026，不能标作 GESLA-3；潮位实际切片未取回。 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| [D70 ESWD](INHERITED_SAMPLE_AUDIT.json) | reserve_not_selected / inherited_unverified | ESWD 适合补欧洲龙卷/冰雹，但本轮未获得许可明确的批量样本。 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| [D71 CAMELSH](INHERITED_SAMPLE_AUDIT.json) | reserve_not_selected / inherited_metadata | CAMELSH 发布元数据候选；未解码水文时序，需确认与 Caravan/CAMELS 的派生重叠。 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| [D72 MSETCD / MSCAR](INHERITED_SAMPLE_AUDIT.json) | reserve_not_selected / inherited_reference | MSETCD/MSCAR 读取器或目录候选；未验证实际图像，用于后续亚洲气旋补源。 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| [D73 CMA Best Track](INHERITED_SAMPLE_AUDIT.json) | reserve_not_selected / inherited_reference | CMA 最佳路径入口已登记；尚无完整样例解码，仅作未来多机构事后对照。 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| [D74 NOAA Billion-Dollar Disasters](INHERITED_SAMPLE_AUDIT.json) | reserve_not_selected / inherited_reference | NOAA Billion-Dollar 仅影响事件索引候选；经济损失阈值造成地区偏差，不定义全球气象极端。 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| [AW-HURDAT2 NHC HURDAT2 Atlantic](INHERITED_JOIN_BINDINGS.json) | selected_with_gates / inherited_join_rehashed | 已与四个风暴的数字预报精确匹配；原始结果文件本轮重新核验哈希。 | 同机构事后分析 P；不用作独立原始传感器 O。 |
| [AW-HEFS NOAA HEFS QINE ensemble](INHERITED_JOIN_BINDINGS.json) | selected_with_gates / inherited_join_rehashed | Scotia 两轮完整集合产品，每轮 45 成员 × 721 时次。 | 流量 CFS 不能直接套用水位洪水阈值；成员权重、flag 与概率合同待冻结。 |
| [AW-NIMS USGS NIMS cameras](../v6_active_warning_review_20260911/HYDRO_FEASIBILITY.json) | conditional_same_site_visual / inherited_image_stage_pair | 旧审计有一个站点三张真实影像与近时水位；本轮水文两站相机接口未找到。 | 仅作条件性原生视觉证据；不把像素直接反演为精确水位 Gold。 |
| [AW-GHCNH NOAA GHCNh current hourly archive](GHCNH_DOCUMENTATION_TEXT.txt) | selected_with_gates / new_rows_decoded | 2026 Denver 单站文件首尾各 1 MiB，4,558 个完整稀疏行；476 行非空气温，涵盖 1 月及 9 月。 | 不是整年下载；9 月气温 QC 为空不能当作通过 QC。温度已为摄氏度，能见度为 km，现象码含 TS:17 等字符串。 |
| [AW-GEFS NOAA GEFS ensemble](captures_02/gefs-c00-t2m.json) | selected_with_gates / new_future_grib_decoded | 同一 00Z 起报 +6h，c00/p01 两成员各有气温与 0-6h 降水，720×361。 | 仅抽样两个成员；不能用此宣称完整集合、官方概率或已校准概率。 |
| [AW-SPC SPC Day 1 convective outlook](captures_01/spc-day1-shapes.json) | selected_with_gates / new_forecast_polygons_decoded | 2026-09-10 13Z outlook ZIP 完整 CRC 通过；7 类产品有 28 个 shapefile 表示层，含 cat/hail/torn/wind 及 CIG。 | 28 层不是 28 个独立预报或灾害；DN、CIG 与区域/时间支持需按版本解释。 |
| [AW-MESH MRMS MESH](captures_02/mrms-mesh-sample.json) | conditional_product_semantics / new_product_array_semantics_pending | 一个完整 gzip/GRIB，7000×3500；时间 2026-09-10 00:00:43，最大原值 24.9。 | 本地 ecCodes 名称/单位为 unknown，含负代码；先补官方局地表/有效掩膜再设阈值，不能等同地面雹径。 |
| [AW-QPE MRMS MultiSensor QPE 01H Pass2](captures_10/mrms-qpe-sample.json) | conditional_product_semantics / new_product_array_semantics_pending | 一个完整 gzip/GRIB，7000×3500；2026-09-10 00Z，1,676,667 个正原值，含 -3 代码。 | 文件名为 1h QPE，但通用 GRIB 解码显示 instant/unknown units；产品累计窗、单位、Pass2 延迟与代码表须以产品规范绑定。 |
| [AW-ABI GOES-19 ABI C01 / C13](captures_04/goes19-abi-sample.json) | selected_with_gates / new_netcdf_arrays_decoded | 2026-09-10 可见光 C01 与红外 C13 两个完整 NetCDF；C01 1000×1000，DQF 均为 0。 | 两个通道/同一上游不是独立事件；原始变量、投影及 DQF 必须保留。 |
| [AW-METAR AWC METAR observations](captures_01/metar-json.json) | selected_with_gates / new_aviation_rows_decoded | KDEN/KJFK/KSFO 共 35 条实际站报。 | 滚动接口不是长期历史档案；SM/kt 等原始单位及能见度上下界要解析。 |
| [AW-TAF AWC TAF forecasts](captures_01/taf-json.json) | selected_with_gates / new_aviation_forecasts_decoded | KDEN/KJFK/KSFO 三站 TAF 原文和结构化预报组。 | FM/TEMPO/PROB 语义与机场范围必须保留；TAF 预报雾不能作未来观测标签。 |
| [AW-IEM IEM historical METAR archive](captures_07/iem-freezing-rain.json) | selected_with_gates / new_positive_phenomena_rows_decoded | OKC 2020 冰暴窗口 108 行：47 条 FZRA、8 条 FZDZ；PHX 2011 沙尘窗口 68 行：5 条 DS、10 条 BLDU。 | IEM 是历史站报再分发端，不是独立传感器；两次选择性历史过程均已暴露，仅作开发/可行性材料。 |
| [AW-EDDI NOAA EDDI 01-month](captures_02/eddi-grid.json) | selected_with_gates / new_drought_array_decoded | 2026-01-01 ESRI ASCII，224×464；79,831 个非缺测有限值。 | 文件没有显式 CRS；EDDI 不直接等于土壤水分、闪旱或已发布预报。 |
| [AW-CPC CPC Seasonal Drought Outlook](ASSEMBLY_MANIFEST.json) | selected_with_gates / new_forecast_shapes_decoded | 完整 15,714,252 字节 ZIP，19 个成员；2026-08-20 签发，目标 November30，两个形状层。 | 季节性分类展望不对应下一周 USDM 概率；类别及空间范围保持原产品定义。 |
| [AW-OFS NOAA CBOFS station forecast](ASSEMBLY_MANIFEST.json) | selected_with_gates / new_forecast_netcdf_decoded | 完整 50,650,138 字节 NetCDF；209 个模型位置、481 时次/48h，100,529 个有限 zeta 值，单位 m。 | 模型位置尚无正式 CO-OPS 站号/垂直基准桥；不能直接和潮位站阈值比较。 |
| [AW-PETSS NOAA P-ETSS tide/surge station bulletins](captures_04/petss-stormtide-sample.json) | selected_with_gates / new_forecast_tables_decoded | 两份完整数值公告，各 290 个位置 × 102 值；210 个数字 ID、80 个 est ID，原单位 0.1 ft。 | 明确 NOT VALID FOR TROPICAL STORM；e10 概率含义、时间对齐、基准及 -400 代码未准入。 |
| [AW-WPC WPC QPF / winter products](captures_02/wpc-qpf-index.json) | conditional_numeric_forecast / rendered_qpf_only | 实际 QPF GIF 可解码，冬季产品页面可读；数值网格候选请求未成功。 | 只作产品读图候选；没有 QPF 或冬季概率数组，不冒充数字专业基线。 |
| [AW-GWIS GWIS FWI map service](captures_04/gwis-fwi-map.json) | conditional_numeric_forecast / rendered_fwi_only | 实际 256×192 FWI PNG 与 WMS 能力表；WCS 不暴露数值 FWI，点值查询为空。 | 图层说明提及 ECMWF reanalysis，不能把该样例称为已验证业务火险预报；FWI 也不等于起火/扩展事实。 |
| [AW-EFFIS EFFIS fire danger service](captures_01/effis-page.json) | reserve_not_selected / metadata_or_empty_response | 官方页面可读，WMS 能力请求返回空的 HTTP 200。 | 不把 GWIS 地图替算为 EFFIS 数值取样成功；共用基础设施也不等于独立来源。 |
| [AW-CAMS CAMS dust/composition forecast](captures_06/cams-small-retrieval.json) | conditional_authentication / authentication_required_no_array | 小范围匿名实际提取 POST 返回 401 authentication required；无 dust 数组。 | 保留需账号/条款配置的扩展路线；本轮匿名尝试失败不证明数据科学上不可用。 |
| [AW-GLOFAS GloFAS operational forecast](captures_06/glofas-small-retrieval.json) | conditional_authentication / authentication_required_no_array | 元数据可读；小范围实际提取 POST 返回 401，无流量数组。 | 保留需账号/条款配置的扩展路线；本轮匿名尝试失败不证明数据科学上不可用。 |
| [AW-EFAS EFAS operational forecast](captures_06/efas-small-retrieval.json) | conditional_authentication / authentication_required_no_array | 过程模式可读；小范围实际提取 POST 返回 401，无流量数组。 | 保留需账号/条款配置的扩展路线；本轮匿名尝试失败不证明数据科学上不可用。 |
| [AW-SMAPL4 SMAP L4 SPL4SMGP v008](captures_01/smap-l4-granules.json) | conditional_authentication / authentication_required_no_array | 已找到真实 granule；原始片段与 OPeNDAP 请求均为 401，无土壤水分数组。 | 保留需账号/条款配置的扩展路线；本轮匿名尝试失败不证明数据科学上不可用。 |

原始获取 URL、逐回执路径、继承的原始证据指针在 JSON 中；CSV 便于筛选。HTTP 200 的文档、空响应和地图均不算完成科学数组验证。未选替代项继续保留其真实状态，不为了扩源数量重复下载。
