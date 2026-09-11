# 整体灾种—数据源—处理矩阵

这是整个 benchmark 的设计范围。来源被选为主路线或候选，不代表已形成相应正式任务。D01–D74沿用既有登记；AW前缀为本方案单列的补充来源。

## H01 热带气旋

子类：强度；路径；局地风影响另设任务。

未来目标：已在监测系统的固定未来时刻最大持续风/位置；局地风风险单独定义。

| 角色 | 来源 |
| --- | --- |
| 观测/标签 | [AW-HURDAT2 NHC HURDAT2 Atlantic](https://www.nhc.noaa.gov/data/hurdat/hurdat2-1851-2025-02272026.txt)；[D02 IBTrACS v4r01](https://www.ncei.noaa.gov/data/international-best-track-archive-for-climate-stewardship-ibtracs/v04r01/access/csv/) |
| 预报/专业基线候选 | [D01 NHC Public / Forecast Advisories + GIS](https://www.nhc.noaa.gov/archive/) |
| 现成benchmark/背景/辅助 | [D03 Digital Typhoon V2](https://agora.ex.nii.ac.jp/digital-typhoon/dataset/V2/)；[D04 TCIR](https://www.csie.ntu.edu.tw/~htlin/program/TCIR/)；[D50 CyPortQA](https://github.com/ChenchenMobility/MLLM-Bench-CyPortQA)；[D73 CMA Best Track](https://tcdata.typhoon.org.cn/en/zjljsjj.html) |

处理规则：

- 按storm_id与绝对UTC有效时刻精确匹配。
- 多机构最佳路径保留权威差异，不平均当唯一真值。
- 风速统一kt；风暴最大风与地点风暴露分开。
- 无数字预报与无结果均保留缺失，不补零。

当前证据：本轮重核64公告、461数字预报行、96可结算唯一时刻；四个已暴露开发组；历史availability未证。

自然时间尺度：小时至数日。

## H02 温带风暴/非对流大风

子类：非对流持续风；阵风；风暴系统身份。

未来目标：固定站点未来风速或阵风越阈。

| 角色 | 来源 |
| --- | --- |
| 观测/标签 | [D27 ISD / Global Hourly](https://www.ncei.noaa.gov/data/global-hourly/access/) |
| 预报/专业基线候选 | [D28 NOAA GFS0P25](https://developers.google.com/earth-engine/datasets/catalog/NOAA_GFS0P25)；D67 HRRR |
| 现成benchmark/背景/辅助 | [D05 NOAA Storm Events Database](https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/)；[D48 ExtremeWeatherBench](https://extremeweatherbench.readthedocs.io/en/latest/data/) |

处理规则：

- 持续风与阵风分开。
- 核对10m高度、平均时长和瞬时/区间最大语义。
- 按源事件标签或可验证过程区分非对流与雷暴风。
- 网格到站点的取样规则预先固定。

当前证据：ISD风和报告可读；GFS/HRRR仅有同一初始化少量变量，尚无完整未来预报配对。

自然时间尺度：小时至数日。

## H03 雷暴大风/下击暴流

子类：雷暴阵风；下击暴流需专门依据。

未来目标：固定站点/区域未来雷暴大风；无合格实测时只评价报告或产品目标。

| 角色 | 来源 |
| --- | --- |
| 观测/标签 | [D27 ISD / Global Hourly](https://www.ncei.noaa.gov/data/global-hourly/access/)；[D05 NOAA Storm Events Database](https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/) |
| 预报/专业基线候选 | D67 HRRR；[AW-SPC NOAA SPC convective outlooks / mesoscale discussions](https://www.spc.noaa.gov/products/outlook/archive/) |
| 现成benchmark/背景/辅助 | [D06 SEVIR](https://registry.opendata.aws/sevir/)；[D08 NOAA NEXRAD](https://registry.opendata.aws/noaa-nexrad/)；[D09 NOAA MRMS](s3://noaa-mrms-pds/)；[D49 WeatherQA](https://github.com/chengqianma/WeatherQA) |

处理规则：

- 雷达/VIL与地面阵风不是同一变量。
- 按雷暴过程链接雷达、测站和报告。
- 报告空白不标成无灾害。
- 下击暴流不由强风或高VIL自动推断。

当前证据：SEVIR和报告已抽样；地面风—雷达—合法预报链待配对。

自然时间尺度：分钟至小时。

## H04 龙卷风

子类：龙卷风险；带龙卷标签的雷达窗口。

未来目标：固定时空窗口的龙卷报告/作者定义标签；直接物理发生须额外可核验覆盖。

| 角色 | 来源 |
| --- | --- |
| 观测/标签 | [D07 TorNet](https://github.com/mit-ll/tornet)；[D05 NOAA Storm Events Database](https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/) |
| 预报/专业基线候选 | [AW-SPC NOAA SPC convective outlooks / mesoscale discussions](https://www.spc.noaa.gov/products/outlook/archive/) |
| 现成benchmark/背景/辅助 | [D08 NOAA NEXRAD](https://registry.opendata.aws/noaa-nexrad/)；[D06 SEVIR](https://registry.opendata.aws/sevir/)；[D49 WeatherQA](https://github.com/chengqianma/WeatherQA) |

处理规则：

- TorNet保留作者标签、质量和原split。
- 先补真实正例；同一风暴多个体扫归组。
- SPC概率窗口与目标范围精确对齐。
- 无报告不是可证负例；不从测试标签选输入时刻。

当前证据：TorNet三个train样例均负例；报告正例存在；未完成未来任务链。

自然时间尺度：分钟至小时。

## H05 冰雹

子类：地面大冰雹；雷达估计冰雹。

未来目标：固定窗口报告冰雹直径越阈，或明确标注的未来MESH产品越阈。

| 角色 | 来源 |
| --- | --- |
| 观测/标签 | [D05 NOAA Storm Events Database](https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/)；[D09 NOAA MRMS](s3://noaa-mrms-pds/) |
| 预报/专业基线候选 | [AW-SPC NOAA SPC convective outlooks / mesoscale discussions](https://www.spc.noaa.gov/products/outlook/archive/)；D67 HRRR |
| 现成benchmark/背景/辅助 | [D08 NOAA NEXRAD](https://registry.opendata.aws/noaa-nexrad/)；[D06 SEVIR](https://registry.opendata.aws/sevir/)；[D48 ExtremeWeatherBench](https://extremeweatherbench.readthedocs.io/en/latest/data/)；[D70 ESWD](https://www.essl.org/cms/author/tomas/) |

处理规则：

- 英寸/mm转换并保留报告测量或估计属性。
- MESH与地面直径分表。
- 时空匹配及缺测遮罩独立处理。
- 无报告与雷达无有效覆盖均不直接作物理负例。

当前证据：冰雹目录和SEVIR样例可读；MESH实际数组与配对预报未核验。

自然时间尺度：分钟至小时。

## H06 强雷电

子类：闪电频度；闪电密度极端。

未来目标：固定区域未来窗口的GLM有效观测flash数量或密度。

| 角色 | 来源 |
| --- | --- |
| 观测/标签 | [D10 GOES-R ABI / GLM archives](https://registry.opendata.aws/noaa-goes/) |
| 预报/专业基线候选 | 持续性、气候态或简单数值基线；匹配专业预报未确定 |
| 现成benchmark/背景/辅助 | [D06 SEVIR](https://registry.opendata.aws/sevir/)；[D05 NOAA Storm Events Database](https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/) |

处理规则：

- flash/group/event三层不混计。
- 空间面积与时间窗口固定，跨文件边界去重。
- 极端密度阈值来自独立气候基线。
- 视场和传感器缺测显式保留；默认持续性/气候态基线。

当前证据：三个20秒GLM产品已解析；尚无极端密度判定和匹配专业概率预报。

自然时间尺度：分钟至小时。

## H07 极端降水

子类：短时强降水；日累计暴雨。

未来目标：固定站点/区域未来指定时段累计降水越阈。

| 角色 | 来源 |
| --- | --- |
| 观测/标签 | [D26 GHCN-Daily](https://www.ncei.noaa.gov/pub/data/ghcn/daily/)；[D27 ISD / Global Hourly](https://www.ncei.noaa.gov/data/global-hourly/access/)；[D59 MeteoNet](https://meteofrance.github.io/meteonet/english/data/summary/) |
| 预报/专业基线候选 | [D28 NOAA GFS0P25](https://developers.google.com/earth-engine/datasets/catalog/NOAA_GFS0P25)；D67 HRRR |
| 现成benchmark/背景/辅助 | [D09 NOAA MRMS](s3://noaa-mrms-pds/)；[D29 GPM IMERG V07](https://developers.google.com/earth-engine/datasets/catalog/NASA_GPM_L3_IMERG_V07)；[D30 CHIRPS v3 DAILY_SAT](https://developers.google.com/earth-engine/datasets/catalog/UCSB-CHC_CHIRPS_V3_DAILY_SAT)；[D47 ExEBench / EarthExtreme-Bench](https://github.com/zhaoshan2/EarthExtreme-Bench)；[D48 ExtremeWeatherBench](https://extremeweatherbench.readthedocs.io/en/latest/data/) |

处理规则：

- 累计量与降水率分开。
- 处理累计起止、重置和重叠报告。
- 站点日界不冒充UTC日界。
- 雷达/卫星估计与雨量计结果分层；不随意插值Gold。

当前证据：雨量站、CHIRPS、MeteoNet已有样例；未来QPF与同窗结果链待验证。

自然时间尺度：分钟、小时或日。

## H08 洪水

子类：河流洪水；山洪；城市内涝。

未来目标：河站未来水位/流量越阈；空间淹没与城市道路另设目标。

| 角色 | 来源 |
| --- | --- |
| 观测/标签 | [D56 USGS Water Data](https://api.waterdata.usgs.gov/) |
| 预报/专业基线候选 | D57 NWPS Stageflow；[AW-HEFS NOAA/NWS HEFS](https://api.water.noaa.gov/hefs/v1/headers/) |
| 现成benchmark/背景/辅助 | [D12 GEOID-Flood](https://github.com/links-ads/geoid-flood)；[D18 CEMS Rapid Mapping](https://mapping.emergency.copernicus.eu/about/how-to-harvest-cems-mapping-data/emergency-response-data/)；[D60 Caravan](https://www.nature.com/articles/s41597-023-01975-w)；[D61 HANZE v2.1](https://essd.copernicus.org/articles/16/5145/2024/)；[AW-NIMS USGS NIMS](https://api.waterdata.usgs.gov/docs/nims)；[D13 KuroSiwo](https://github.com/Orion-AI-Lab/KuroSiwo)；[D14 UrbanSARFloods](https://github.com/jie666-6/UrbanSARFloods)；[D16 SpaceNet 8](https://spacenet.ai/sn8-challenge/)；[D51 WorldFloods v2 / ml4floods](https://spaceml-org.github.io/ml4floods/content/worldfloods_dataset.html) |

处理规则：

- 官方站点映射，水位基准/单位与阈值版本匹配。
- 水位与流量分轨，无有效评级曲线不转换。
- 单时刻优先，时间窗负例要求完整注册网格。
- 空间洪水标签与河站结果不强行拼同一事件。

当前证据：本轮两站两流域、50水位和25流量观测；两个HEFS起报完整数组；全为Provisional，四个水位点预览均未越阈。

自然时间尺度：小时至数日。

## H09 风暴潮/沿岸淹没

子类：总水位越阈；潮汐残差；沿岸淹没。

未来目标：固定潮位站未来总水位越阈；气象成因和陆地淹没单独验证。

| 角色 | 来源 |
| --- | --- |
| 观测/标签 | [D37 NOAA CO-OPS water levels](https://api.tidesandcurrents.noaa.gov/api/prod/) |
| 预报/专业基线候选 | [AW-SURGE NOAA operational total-water-level / storm-surge guidance (ESTOFS / ETSS candidates)](https://polar.ncep.noaa.gov/estofs/) |
| 现成benchmark/背景/辅助 | D58 NDBC Buoys；[D69 GESLA current / GESLA-3 candidate](https://rmets.onlinelibrary.wiley.com/doi/10.1002/gdj3.174)；[D01 NHC Public / Forecast Advisories + GIS](https://www.nhc.noaa.gov/archive/)；[D18 CEMS Rapid Mapping](https://mapping.emergency.copernicus.eu/about/how-to-harvest-cems-mapping-data/emergency-response-data/) |

处理规则：

- 统一潮位基准面、单位和时区。
- 天文潮预测与风暴潮/总水位预报区分。
- 残差不当作单一风暴潮成因。
- 波高不是水位；淹没面积需要独立地形和空间标签。

当前证据：三站720对水位/天文潮已验证；业务总水位预报尚未取样，不能把潮汐预测充当完整强基线。

自然时间尺度：小时至数日。

## H10 热浪/极端高温

子类：单时刻或单日高温；持续热浪。

未来目标：未来日最高温越阈或预注册连续多日热浪。

| 角色 | 来源 |
| --- | --- |
| 观测/标签 | [D26 GHCN-Daily](https://www.ncei.noaa.gov/pub/data/ghcn/daily/)；[D27 ISD / Global Hourly](https://www.ncei.noaa.gov/data/global-hourly/access/) |
| 预报/专业基线候选 | [D28 NOAA GFS0P25](https://developers.google.com/earth-engine/datasets/catalog/NOAA_GFS0P25)；D67 HRRR |
| 现成benchmark/背景/辅助 | [D48 ExtremeWeatherBench](https://extremeweatherbench.readthedocs.io/en/latest/data/)；[D47 ExEBench / EarthExtreme-Bench](https://github.com/zhaoshan2/EarthExtreme-Bench)；[D25 ERA5-Land Hourly](https://developers.google.com/earth-engine/datasets/catalog/ECMWF_ERA5_LAND_HOURLY)；[D34 MODIS LST MOD11A1.061](https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MOD11A1)；[D66 WeatherBench2 ERA5](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels-timeseries) |

处理规则：

- 2m气温与地表温度分开。
- 冻结当地季节阈值/气候基准期。
- 热浪明确持续天数，单点高温不直接叫热浪。
- 检查观测日界、QC与预报统计支持。

当前证据：温度站、EWB案例可读；ExEBench高温包未取样，尚无完整未来预报配对。

自然时间尺度：日及数日。

## H11 寒潮/极端低温/霜冻

子类：极端低温；快速降温；霜冻需现象依据。

未来目标：未来低温或降温幅度/持续性越阈。

| 角色 | 来源 |
| --- | --- |
| 观测/标签 | [D26 GHCN-Daily](https://www.ncei.noaa.gov/pub/data/ghcn/daily/)；[D27 ISD / Global Hourly](https://www.ncei.noaa.gov/data/global-hourly/access/) |
| 预报/专业基线候选 | [D28 NOAA GFS0P25](https://developers.google.com/earth-engine/datasets/catalog/NOAA_GFS0P25)；D67 HRRR |
| 现成benchmark/背景/辅助 | [D47 ExEBench / EarthExtreme-Bench](https://github.com/zhaoshan2/EarthExtreme-Bench)；[D48 ExtremeWeatherBench](https://extremeweatherbench.readthedocs.io/en/latest/data/)；[D25 ERA5-Land Hourly](https://developers.google.com/earth-engine/datasets/catalog/ECMWF_ERA5_LAND_HOURLY)；[D66 WeatherBench2 ERA5](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels-timeseries) |

处理规则：

- 绝对低温与温度下降分开。
- 2m温度低于0度不自动等于地表霜冻。
- 跨国同一次寒潮归并，阈值按当地基准。
- ERA5为回溯参考，不当业务初始可用输入。

当前证据：ExEBench寒潮包9案例559时步已解码，另有站温；九案例不等于九独立寒潮。

自然时间尺度：小时至数日。

## H12 冬季灾害

子类：大雪；暴雪/吹雪；积雪；冻雨/结冰。

未来目标：分别定义未来降雪量、雪深/SWE、吹雪条件或冻雨现象。

| 角色 | 来源 |
| --- | --- |
| 观测/标签 | [D26 GHCN-Daily](https://www.ncei.noaa.gov/pub/data/ghcn/daily/)；[D27 ISD / Global Hourly](https://www.ncei.noaa.gov/data/global-hourly/access/)；[D55 SNODAS SWE](https://nsidc.org/data/g02158/versions/1) |
| 预报/专业基线候选 | D67 HRRR；[D28 NOAA GFS0P25](https://developers.google.com/earth-engine/datasets/catalog/NOAA_GFS0P25) |
| 现成benchmark/背景/辅助 | [D05 NOAA Storm Events Database](https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/)；[D33 MODIS Snow MOD10A1.061](https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MOD10A1)；[D49 WeatherQA](https://github.com/chengqianma/WeatherQA) |

处理规则：

- 降雪量、雪深和SWE不混用。
- 暴雪需雪、风、能见度和持续性联合证据。
- 冻雨使用对应现象码/标签，不能由雪盖替代。
- 缺测与产品编码上限保留；各子类单独覆盖统计。

当前证据：积雪和灾害报告已有样例；ISD冻雨/吹雪码正例仍缺。

自然时间尺度：小时至数日。

## H13 干旱/闪旱

子类：持续干旱；快速恶化/闪旱。

未来目标：固定地区未来USDM等级/面积变化；物理干旱指数另定义。

| 角色 | 来源 |
| --- | --- |
| 观测/标签 | [D31 US Drought Monitor](https://droughtmonitor.unl.edu/DmData/DataDownload/WebServiceInfo.aspx) |
| 预报/专业基线候选 | [AW-CPC NOAA CPC drought outlooks](https://www.cpc.ncep.noaa.gov/products/Drought/) |
| 现成benchmark/背景/辅助 | [D26 GHCN-Daily](https://www.ncei.noaa.gov/pub/data/ghcn/daily/)；[D30 CHIRPS v3 DAILY_SAT](https://developers.google.com/earth-engine/datasets/catalog/UCSB-CHC_CHIRPS_V3_DAILY_SAT)；[D32 SMAP Enhanced L3 Soil Moisture](https://developers.google.com/earth-engine/datasets/catalog/NASA_SMAP_SPL3SMP_E_006)；[D52 DroughtED](https://www.kaggle.com/datasets/cdminix/us-drought-meteorological-data)；[D60 Caravan](https://www.nature.com/articles/s41597-023-01975-w)；[D62 Dheed](https://essd.copernicus.org/articles/17/6621/2025/index.html) |

处理规则：

- 周次有效状态不当同一目标订正。
- 先固定USDM产品标签，披露已有专家参与。
- 季节展望不能直接作为下一周等级概率。
- DroughtED小数标签和split冲突解决前隔离；闪旱需独立快速恶化规则。

当前证据：USDM周图可用；DroughtED仅部分归档且语义/年份待修；未来概率链未完成。

自然时间尺度：周至月。

## H14 沙尘暴

子类：沙尘暴；浮尘/扬沙另列。

未来目标：未来具有沙尘现象依据的低能见度/沙尘指标越阈。

| 角色 | 来源 |
| --- | --- |
| 观测/标签 | [D27 ISD / Global Hourly](https://www.ncei.noaa.gov/data/global-hourly/access/) |
| 预报/专业基线候选 | [AW-CAMS Copernicus CAMS atmospheric composition forecasts](https://ads.atmosphere.copernicus.eu/) |
| 现成benchmark/背景/辅助 | [D05 NOAA Storm Events Database](https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/)；[D35 MERRA-2 aerosol diagnostics](https://developers.google.com/earth-engine/datasets/catalog/NASA_GSFC_MERRA_aer_2)；[D36 Sentinel-5P OFFL Aerosol Index](https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S5P_OFFL_L3_AER_AI) |

处理规则：

- 核查现象码及能见度，浮尘不自动升格为沙尘暴。
- AOD/气溶胶指数不单独证明沙尘来源。
- MERRA-2为回溯分析，CAMS业务预报另存版本。
- 缺失天气码不当无沙尘；需补明确正例。

当前证据：有沙尘报告与浮尘/扬沙码；当前ISD样例沙尘暴码正例为零，dust专属数组待取样。

自然时间尺度：小时至数日。

## H15 浓雾/极端低能见度

子类：浓雾；海雾；其他低能见度另列。

未来目标：未来站点能见度越阈，并在有依据时判断雾现象。

| 角色 | 来源 |
| --- | --- |
| 观测/标签 | [D27 ISD / Global Hourly](https://www.ncei.noaa.gov/data/global-hourly/access/) |
| 预报/专业基线候选 | D67 HRRR |
| 现成benchmark/背景/辅助 | [D53 M4Fog](https://github.com/Clynie/M4Fog)；[D05 NOAA Storm Events Database](https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/) |

处理规则：

- 能见度单位/QC/上限或截断编码保留。
- 用现象码区分雾、烟、沙尘，模糊时只评低能见度。
- 雾的持续性按完整时间网格判定。
- M4Fog未验证影像不能计入已建海雾子集。

当前证据：ISD已有34条合格雾码记录；极端程度与持续性需构建，M4Fog真实cube未取得。

自然时间尺度：分钟至小时。

## H16 天气相关野火/火险

子类：活动火扩展；烧毁范围；天气火险三者分开。

未来目标：未来活动火探测范围进入固定区域，或独立定义的未来火险。

| 角色 | 来源 |
| --- | --- |
| 观测/标签 | [D19 WildfireSpreadTS](https://zenodo.org/records/8006177)；[D23 NASA FIRMS](https://firms.modaps.eosdis.nasa.gov/api/area/) |
| 预报/专业基线候选 | 持续性、气候态或简单数值基线；匹配专业预报未确定 |
| 现成benchmark/背景/辅助 | [D20 Next Day Wildfire Spread](https://www.kaggle.com/datasets/fantineh/next-day-wildfire-spread)；[D21 TS-SatFire](https://www.kaggle.com/datasets/z789456sx/ts-satfire)；[D24 MTBS burned-area boundaries](https://developers.google.com/earth-engine/datasets/catalog/USFS_GTAC_MTBS_burned_area_boundaries_v1)；[D65 FPA-FOD6](https://doi.org/10.2737/RDS-2013-0009.6)；[D28 NOAA GFS0P25](https://developers.google.com/earth-engine/datasets/catalog/NOAA_GFS0P25)；D67 HRRR |

处理规则：

- FIRMS热点不等于独立火场。
- 按作者规则解析HHMM探测时刻、云和未探测状态。
- 火点消失不当火已扑灭；烧痕不当实时活动火。
- 天气条件可作输入，不默认极端天气导致起火；先用持续性/简单扩展强基线。

当前证据：WildfireSpreadTS与TS-SatFire仅少量同火场时序；未来标签、QC和更多独立火场仍需准入。

自然时间尺度：小时至日。

