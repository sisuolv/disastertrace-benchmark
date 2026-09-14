# v8 数据源与任务准入对照

本表依据已保存的原始验证回执和合同生成。它不发出新下载请求，也不把历史样本可读升级为全版本可下载或完整 benchmark 已完成。

继承登记的 97 个产品/数据集项中，86 项有特定样本解码记录，7 项仅有目录/元数据，2 项尚无目标样本解码，2 项仍保留历史授权待办。镜像、产品别名、站点数和重复提前量不等于独立来源或天气过程。EUPP/DWD 点温度扩展单列，没有悄悄并入这 97 项。

## 本轮新增的实际任务证据

| 资料链 | 已实际完成 | 尚不能据此宣称 |
| --- | --- | --- |
| H15 TAF + METAR / IEM | 5 份自然日历、12,528 个 cutoff 机会；Bay 有 E/F 自动结算和模型开发评测；其余三区域完成原生获取解析 | 所有机会独立、所有低能见度都是浓雾、各地区都已有合格概率映射 |
| H10/H11 EUPPBench + DWD Berus | 2017-2018 两年、51 成员、14,600 个正时效点温度机会，14,430 可结算，170 缺测保留；960 次标量回放 | 热浪、寒潮、霜冻损失或独立极端过程验证 |
| H10/H11 DWD 官方日极值与 EUPP 六小时极值扩展 | 730 天 TXK/TNK；11,648 个 E 支持状态；新增原生 mx2t6/mn2t6 的2,920条未来日配对、2,920条三日事件及480个准入快照；见 TEMPERATURE_DAILY_FORECAST_CN.md | 只有声明可用时间下的离线候选与快照准入；连续主动会话、真实发布时效、最终热浪/寒潮定义、实际结霜/作物损伤和独立确认未完成 |
| H07 MRMS QPE Pass2 | 连续 12 小时网格解码；官方产品表证明 mm、1h 标称累计时长及 -1/-3 质量含义 | 累计区间端点和历史首发时间已证明，或匹配未来 F / 原生 MM 完成 |
| H08 CNRFC / HEFS | 两个预报循环，43 个 QINE 列，697 个共同有效时刻，2,788 个版本 E 状态 | 43 列成员身份、调蓄关系、流量/水位/空间淹没等价已证明；完整共同 HEFS 的事实不能额外收费 |
| AWC 当前来源采集 | 保存真实 HTTP 接收和原生 TAF/METAR 版本；具体完成范围见 shadow 独立报告 | 实时模型预测或未来结果结算已经完成 |

模型批次完成状态及分数以 [执行报告](RUN_REPORT_CN.md) 和 [执行状态](EXECUTION_STATUS.json) 为准。本表的来源可用性与模型胜负是两件事。

## 16 类灾害及其合同候选来源

以下是来源角色规划，不是 16 条全部准入的声明。各灾种优先完成一个定义严格的子目标；河洪、山洪和内涝也必须分别验证。

| ID / 灾害 | 主要预报来源 | 结果参考 | 目标定义 | 后续准入门槛 |
| --- | --- | --- | --- | --- |
| H01 热带气旋 | D01: NHC forecast advisories / GIS | AW-HURDAT2: NHC HURDAT2 Atlantic; D02: IBTrACS v4r01 | 起始时已经进入监测的气旋，在固定未来绝对时刻的总体最大持续风；地点风风险必须另建子任务。 | 既有 NHC 窄链回归后，扩展未见风暴；CMA 字段核验与同洋盆业务预报为独立门槛 |
| H02 温带风暴/非对流大风 | D28: NOAA GFS 0.25 degree operational forecasts; D67: NOAA HRRR operational forecasts; AW-GEFS: NOAA GEFS ensemble | AW-GHCNH: NOAA GHCNh current hourly archive; AW-METAR: AWC METAR observations; D05: NOAA Storm Events Database | 固定站点未来瞬时或窗口平均风/阵风越阈；非对流成因要求额外依据。 | 站点高度与 NWP 支持、合格强风正例和普通监测块、成因及源时刻合同 |
| H03 雷暴大风/下击暴流 | AW-SPC: SPC Day 1 convective outlook; D67: NOAA HRRR operational forecasts | D05: NOAA Storm Events Database; AW-GHCNH: NOAA GHCNh current hourly archive; AW-METAR: AWC METAR observations | 固定区域/站点未来对流阵风越阈；确认下击暴流为独立子类。 | SPC 目标映射、实测/估计风区别、同一对流过程分组与报告制度 |
| H04 龙卷风 | AW-SPC: SPC Day 1 convective outlook | D05: NOAA Storm Events Database | 固定区域和未来窗口内的确认龙卷报告；物理发生声明另需覆盖依据。 | 锁定 TorNet 版本、真实正例/负例、确认报告参考；空报告不等于物理未发生 |
| H05 冰雹 | AW-SPC: SPC Day 1 convective outlook; D67: NOAA HRRR operational forecasts | D05: NOAA Storm Events Database | 未来地面报告雹径越阈；MRMS MESH产品越阈为另一个有名称的代理任务。 | GRIB 局地参数表、负码、报告有效窗及区域/半径概率支持匹配 |
| H06 强雷电 |  | D10: GOES GLM (inherited sampled product) | 未来区域内单位有效观测时间和面积的GLM检测flash密度；不是全部地面雷击。 | 多文件连续窗口、探测覆盖、历史阈值和外推/持续性强 R 基线；无已验证专业同目标预报 |
| H07 极端降水 | D28: NOAA GFS 0.25 degree operational forecasts; D67: NOAA HRRR operational forecasts; AW-GEFS: NOAA GEFS ensemble; AW-WPC: WPC QPF / winter products | D26: GHCN-Daily; AW-GHCNH: NOAA GHCNh current hourly archive; D29: IMERG V07 Early / Late; D30: CHIRPS v3 DAILY_SAT; AW-QPE: MRMS MultiSensor QPE 01H Pass2 | 固定时段累计降水或规定时刻降水率越阈；参考类型分实测和产品估计。 | 累计起止/重置、合格结果覆盖、同起报 QPF、真实雨量/代理身份 |
| H08 河洪/山洪/城市内涝 | AW-HEFS: NOAA HEFS QINE ensemble; D57: NWPS stage forecasts; AW-GLOFAS: GloFAS operational forecast; AW-EFAS: EFAS operational forecast | D56: USGS continuous observations; D71: CAMELSH; D11: Global Flood Database v1; D18: CEMS Rapid Mapping | 河洪流量/水位越阈；山洪与城市内涝以独立结果合同建子轨；不能用河站代理所有子类。 | 归档发行版本、真实水网、阈值、成熟观测；空间子轨独立配准与标签；影像不要求 xBD 先通过 |
| H09 风暴潮/沿岸淹没 | AW-OFS: NOAA CBOFS station forecast; AW-PETSS: NOAA P-ETSS tide/surge station bulletins | D37: NOAA CO-OPS water levels; D69: GESLA current / GESLA-3 candidate | 先做固定站点极端总水位；天气成因与实际沿岸淹没为另外的子目标。 | 站点映射、垂直基准与 epoch、预报适用天气类型；实际淹没需额外标签 |
| H10 高温/热浪 | D28: NOAA GFS 0.25 degree operational forecasts; D67: NOAA HRRR operational forecasts; AW-GEFS: NOAA GEFS ensemble | D26: GHCN-Daily; AW-GHCNH: NOAA GHCNh current hourly archive | 固定时刻2m气温越阈；热浪子轨需要固定当地日界、阈值与连续天数。 | 先完成瞬时温度迁移；再核定历史气候态、当地日界、持续性与未见热浪 |
| H11 寒潮/极端低温/霜冻 | D28: NOAA GFS 0.25 degree operational forecasts; D67: NOAA HRRR operational forecasts; AW-GEFS: NOAA GEFS ensemble | D26: GHCN-Daily; AW-GHCNH: NOAA GHCNh current hourly archive | 负温度越阈/快速降温分别定义；霜冻或作物损伤需专用观测，不由2m温度直接推出。 | 新负值 schema、温度/降温/霜冻定义分离、独立气候基准与过程 |
| H12 冬季灾害 | D28: NOAA GFS 0.25 degree operational forecasts; D67: NOAA HRRR operational forecasts | D26: GHCN-Daily; AW-GHCNH: NOAA GHCNh current hourly archive; AW-IEM: IEM historical METAR archive; D55: SNODAS SWE; D33: MODIS Snow MOD10A1.061 | 新雪、雪深、SWE、冻雨/冰冻毛毛雨、吹雪分别建子类，使用匹配结果。 | 匹配冬季发行预报与真值；每个子类单独命名；无概率产品时明确 R 基线 |
| H13 干旱/闪旱 | AW-CPC: CPC Seasonal Drought Outlook | D31: US Drought Monitor; D32: SMAP Enhanced L3 Soil Moisture; AW-SMAPL4: SMAP L4 SPL4SMGP v008 | 未来USDM等级/面积为评估产品预测；物理土壤水分或快速恶化另建目标。 | 长期基准、历史发布版本、完整周窗；周级采用强持续性/统计 R 轨并保留产品身份 |
| H14 沙尘暴 | AW-CAMS: CAMS dust/composition forecast; D28: NOAA GFS 0.25 degree operational forecasts; D67: NOAA HRRR operational forecasts | AW-IEM: IEM historical METAR archive; AW-METAR: AWC METAR observations; AW-GHCNH: NOAA GHCNh current hourly archive | 未来沙尘相关天气码与低能见度；AOD/AI产品预测只能作为代理子轨。 | 同期起报版本与地面报告、 dust 变量语义、独立概率校准或明确研究融合基线 |
| H15 浓雾/极端低能见度 | AW-TAF: AWC TAF forecasts; D28: NOAA GFS 0.25 degree operational forecasts; D67: NOAA HRRR operational forecasts | AW-METAR: AWC METAR observations; AW-GHCNH: NOAA GHCNh current hourly archive; D27: ISD / Global Hourly | 未来机场报告的能见度低于阈值；雾子类需FG等合法证据；海雾未来mask需真实标签。 | 完整 INITIAL/FM/BECMG/TEMPO/PROB/COR、原生阈值、连续多站、真实同期平台；TEMPO 不赋 0.5 |
| H16 天气相关野火/火险 | AW-GWIS: GWIS FWI map service; AW-EFFIS: EFFIS fire danger service | D23: NASA FIRMS; D24: MTBS burned-area boundaries; D18: CEMS Rapid Mapping; D65: FPA-FOD6 | 未来火险指数产品与已知火场活动/蔓延分轨；不统一为天气导致的点火。 | 真实时间序列和未见火场、天气合法版本、覆盖与标签图例；同目标蔓延强 R 模型；不把 FWI 当点火概率 |

## 97 项逐来源实际证据

“样本检查”来自继承记录；“本轮补充”链接到新增结果。历史门槛仍保留原文供追溯，若本轮已有更细资格，以新增回执的具体字段为准。未填写新增回执的来源，本轮没有重新宣称其全部端点可用。

| ID / 来源 | 已有获取级别 | 已实际检查的内容 | 本轮补充 | 继承的未完成门槛 |
| --- | --- | --- | --- | --- |
| D01 NHC forecast advisories / GIS | 已有特定样本解码 | 64 份公告、461 行数字预报；4 个已暴露风暴组，96 个唯一时刻有事后参考匹配。 | 继承已有记录 | 96 个匹配目标不是 96 场独立气旋；历史公开可用时间仍未证实。 |
| D02 IBTrACS v4r01 | 已有特定样本解码 | 已解码 21,923 条轨迹记录、378 个 SID；作分盆地事后分析参考。 | 继承已有记录 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| D03 Digital Typhoon V2 | 已有特定样本解码 | ZIP 前缀中取出并 CRC 校验 3 帧完整 HDF5，原生数组可读。 | 继承已有记录 | 同一台风的连续帧；强度标签、版本和原始切分待连接。 |
| D04 TCIR | 已有特定样本解码 | 完整 2017 压缩包 868,340,269 字节，gzip CRC 通过；HDF5 含 4,580 帧、94 个气旋 ID，已解析全部元数据及 6 帧原生数组，连接一个 +6h 强度参考。 | 继承已有记录 | 只对 6 帧做数组检查；已暴露开发资料；需业务预报、历史可用时点及独立事件切分，不能把 4,580 帧当独立气旋。 |
| D05 NOAA Storm Events Database | 已有特定样本解码 | 136,982 条实际灾害报告；作事件检索及独立定义的 R 结果。 | 继承已有记录 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| D06 SEVIR | 已有特定样本解码 | 3 条完整 VIL 序列，每条 49 帧；用于雷达时序感知。 | 继承已有记录 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| D07 TorNet / v1.1 check | 已有特定样本解码 | 继承 3 个可解码 train 负例；本轮确认 v1.1 发布记录，新增归档前缀超时、无完整成员。 | 继承已有记录 | 新增前缀不是成功 NetCDF 样本；仍缺实际正例及其与预警窗口的桥接。 |
| D08 NOAA NEXRAD Level II | 已有特定样本解码 | KTLX 2026-09-10 00:01:20.788 完整体扫，12 个 sweep，反射率/偏振矩可解析。 | 继承已有记录 | MetPy 报 unknown message 32；并非所有报文或科学 QC 都已验证。 |
| D09 NOAA MRMS | 已有特定样本解码 | MRMS 的完整 MESH、1 小时 QPE GRIB 数组已有下载和解析证据，关联 AW-MESH/AW-QPE。 | [h07_extension_01/decoded_01/REPORT.json](h07_extension_01/decoded_01/REPORT.json); [h07_extension_01/semantic_contract_01/QUALIFICATION.json](h07_extension_01/semantic_contract_01/QUALIFICATION.json) | 产品别名不增加独立来源数；局地 GRIB 参数、负代码和时间支持待严格绑定。 |
| D10 GOES GLM (inherited sampled product) | 已有特定样本解码 | 3 个 GLM 20 秒文件及父子 ID 已校验；须构建空间密度基线并补极端窗口；ABI 尚未取样。 | 继承已有记录 | 本项实际继承 3 个 20 秒 GLM 产品；新 ABI 样例单列 AW-ABI，避免重复统计。 |
| D11 Global Flood Database v1 | 已有特定样本解码 | GEE 项目认证成功，GFD 事件栅格取到 3 组 flooded/duration/clear_views 像元及可解码 GeoTIFF。 | 继承已有记录 | 当前 3 点均非洪水；需事件内正例与质量有效区。回顾性洪水范围不等于未来流量真值。 |
| D12 GEOID-Flood | 已有特定样本解码 | 3 组前后 SAR/标签/有效性配对；均为同一外部 test 激活下的洪水负瓦片。 | 继承已有记录 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| D13 KuroSiwo | 已有特定样本解码 | HF 镜像取到 TAR 前缀，解析 3 组完整 SAR/掩膜/info 共 24 个成员。 | 继承已有记录 | 同一激活中的 3 组瓦片；标签图例、原始 train/test 身份、事件独立性需连接。 |
| D14 UrbanSARFloods | 已有特定样本解码 | 8×256×256 SAR 与完整 GT 文件的同网格窗口精确配对；0 类 50,726、开阔地洪水 14,755、城市洪水 55 像素，原负瓦片保留。 | 继承已有记录 | GT 为经校验的窗口而非全文件下载；正瓦片按标签探查后选择，仅作开发可行性；需独立事件与任务时间链。 |
| D15 Sen1Floods11 v1.1 | 已有特定样本解码 | 已复核 3 个 Sen1Floods11 图像标签对、2 个事件地区；许可字段存在歧义，先澄清数据再分发条款。 | 继承已有记录 | 已有真实配对样例；数据再分发条款歧义未解，先保留配方和引用。 |
| D16 SpaceNet 8 | 已有特定样本解码 | SpaceNet 8 原生灾前、灾后 TIFF 与映射对应 GeoJSON 标签均已完整下载解析。 | 继承已有记录 | 原生网格不同；重投影配准、标签栅格化、覆盖和道路/建筑语义需单独核验。 |
| D17 FloodNet | 已有特定样本解码 | 作者原始 Google Drive 取得 3 组 4000×3000 RGB—标签对，10 类编码可读。 | 继承已有记录 | 这 3 组没有建筑受淹/道路受淹像素，保留负例；需补正例、事件拆分及拍摄时点，灾后图像不自动支持预警。 |
| D18 CEMS Rapid Mapping | 已有特定样本解码 | 完整 EMSR842/AOI01 野火分级 ZIP，7 个 GeoJSON 层、604 条记录；602 有几何，2 条空几何保留，0 个无效几何。 | 继承已有记录 | 实际取样是 Zamora 野火，不是原计划洪水 AOI；烧毁范围是事后参考；原始卫星影像与事件时点链须补齐。 |
| D19 WildfireSpreadTS | 已有特定样本解码 | 一个火场 3 天 TIFF；活动火像素 4/0/0，不能解释为后两天灭火。 | 继承已有记录 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| D20 Next Day Wildfire Spread | 已有特定样本解码 | 从已有 ZIP 前缀解析 3 个完整 TFRecord，长度和数据 CRC32C 均通过；13 字段包含前日/次日火掩膜。 | 继承已有记录 | 整个 ZIP 未下载，未校验全包 CRC；原始时空事件身份和切分仍需核验。 |
| D21 TS-SatFire | 已有特定样本解码 | TS-SatFire 3 天同一火场 19 波段栅格可解码；最终标签通道和未来标签切片仍需读取器验证。 | 继承已有记录 | 真实 19 波段数组可读；未来目标通道和有效掩膜语义未完成准入。 |
| D22 Sen2Fire | 已有特定样本解码 | Sen2Fire 大 ZIP 通过 HTTP Range 取出 3 个完整 NPZ并通过成员 CRC，12 波段/气溶胶/掩膜均可读。 | 继承已有记录 | 当前 3 个掩膜全为负例；还需火灾正例、时序标签和独立火场身份。 |
| D23 NASA FIRMS | 已有特定样本解码 | 匿名 VIIRS CSV 有 2,606 条热点；尚未归并为火场。 | 继承已有记录 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| D24 MTBS burned-area boundaries | 已有特定样本解码 | GEE 实取 3 个 MTBS 周界矢量，并读取火烧严重度产品的有效像元。 | 继承已有记录 | 历史周界/严重度属于事后产品；不提供原生次日火势或起火归因真值。 |
| D25 ERA5-Land Hourly | 已有特定样本解码 | CDS ERA5-Land 原生温度切片已验证；GEE 日聚合和小时集合也返回真实温度/降水值。 | 继承已有记录 | 再分析不能冒充当时预报；小时总降水与累积变量的定义需按各产品单独绑定。 |
| D26 GHCN-Daily | 已有特定样本解码 | 5 个站点窗口共 40 个站日，实际温度/降水/雪字段可读。 | 继承已有记录 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| D27 ISD / Global Hourly | 已有特定样本解码 | 北京和沙特两个站年 28,733 报告；实有雾及浮/扬尘码，未发现本批沙尘暴/冻雨码正例。 | 继承已有记录 | ISD 已被 GHCNh 替代；保留旧冻结资产兼容，不用于持续获取当前站点数据。 |
| D28 NOAA GFS 0.25 degree operational forecasts | 已有特定样本解码 | 2026-09-10 00Z 起报、+6h：温度、10m U/V、0-6h 累计降水、能见度、阵风、冻雨分类，共 7 条完整 GRIB。 | 继承已有记录 | 同一次起报不构成修订序列；690 个冻雨非零格点属于预报，不是冻雨实测。 |
| D29 IMERG V07 Early / Late | 已有特定样本解码 | NASA 原生 IMERG Early、Late V07B 各下载并解码 5×5 降水和质量切片；此前 Final 也已验证。 | 继承已有记录 | 当前 E/L 样例降水均为 0；需要降水正例、累计时窗换算和版本延迟。GEE IMERG 接口不是 E/L 身份的替代证明。 |
| D30 CHIRPS v3 DAILY_SAT | 已有特定样本解码 | CHIRPS v3 DAILY_SAT 两个完整日栅格；用于明确标注的降水产品结果/背景。 | 继承已有记录 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| D31 US Drought Monitor | 已有特定样本解码 | 3 个实际 USDM 周产品；采用既有专家分析等级，程序化提取。 | 继承已有记录 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| D32 SMAP Enhanced L3 Soil Moisture | 已有特定样本解码 | SMAP L3 原生 DAP4 切片取得 437 个有效湿度值及坐标/质量字段；GEE 也有数值样本。 | 继承已有记录 | 最初小窗全缺测，保留失败；GEE 3 点推荐质量位未通过。必须联合冻土/植被/质量位，不能直接作骤旱标签。 |
| D33 MODIS Snow MOD10A1.061 | 已有特定样本解码 | MOD10A1.061 完整 HDF4已下载，2400×2400 雪盖及 QA 数组已解码并筛出有效像元。 | 继承已有记录 | 区分 0–100 雪盖值与云/水体/缺测代码；雪盖不等于新降雪、暴雪或冻雨。 |
| D34 MODIS LST MOD11A1.061 | 已有特定样本解码 | MOD11A1.061 完整 HDF4已下载，1200×1200 日间 LST 与 QC 已解析，应用 0.02 K 缩放。 | 继承已有记录 | 地表温度不能替代 2m 气温；完整 QC、日夜条件与热浪持续性待规定。 |
| D35 MERRA-2 aerosol diagnostics | 已有特定样本解码 | MERRA-2 实际取得并解析 DUEXTTAU、DUSMASS 各 27 个 dust 数值，附原生变量属性。 | 继承已有记录 | 再分析尘 AOD/近地面质量浓度不能单独作观测沙尘暴标签；需天气现象码等外部结果。 |
| D36 Sentinel-5P OFFL Aerosol Index | 已有特定样本解码 | Sentinel-5P OFFL 原生 DAP4 数值切片有 532 个有效气溶胶指数及坐标/QA。 | 继承已有记录 | 低纬/极夜窗口可全缺测；L2 原生与 GEE L3 栅格身份不同，气溶胶指数不能单独区分烟尘或确定沙尘暴。 |
| D37 NOAA CO-OPS water levels | 已有特定样本解码 | 3 个潮位站共 720 对同基准观测/天文潮预报；不是完整风暴潮预报。 | 继承已有记录 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| D38 NOAA OISST v2.1 | 已有特定样本解码 | OISST 3 个日 NetCDF 可读；海洋热浪为扩展方向，需长期气候态与持续性定义。 | 继承已有记录 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| D39 EM-DAT | 仅目录/元数据 | 用户授权 XLSX 已完整解析：17,022 条、47 列；核心天气灾害 8,584 条国家记录、6,863 个事件编号组。 | 继承已有记录 | 只作事件目录；7,463 条核心记录缺经纬度，日期粒度不一；灾害报告阈值与漏报偏差、2026 年未完结、事件归并和再分发条件需遵循。缺记录不能作负例。 |
| D40 NASA EONET v3 | 仅目录/元数据 | EONET v3 取得并解析 5 个带几何/日期的真实事件条目。 | 继承已有记录 | 仅事件检索；含非天气灾害，不能当像元或未来预警真值。 |
| D41 GDACS | 仅目录/元数据 | GDACS 实际 RSS/XML 事件 feed 已下载解析。 | 继承已有记录 | 目录/告警条目不等同独立观测结果；需灾种过滤与版本/时间保存。 |
| D42 Sentinel-1 GRD | 已有特定样本解码 | AWS 原始 GRD 路径收到文件前缀；GEE Sentinel-1 VV/VH/angle 有真实像元与可解码 GeoTIFF。 | 继承已有记录 | GEE 是经处理的 GRD 产品；不等于原始 SAFE 全处理链已验证，也不增加独立 SAR 来源数。 |
| D43 Sentinel-2 SR Harmonized | 已有特定样本解码 | AWS L2A 反射率波段和 SCL 完整可读；GEE SR_HARMONIZED 也下载到真实像元和 TIFF。 | 继承已有记录 | 当前 GEE 3 点为高概率云，不能纳入清晰地表任务；缩放/offset/重采样和云质量需严格处理。 |
| D44 xBD | 已有特定样本解码 | 真实取得 3 组 Florence 灾前/后 GeoTIFF 与标签，6 个 TIFF + 6 个 JSON；官方 geotransforms 22,068 项且 SHA1 通过。灾后 286 无损、176 未分类。 | 继承已有记录 | 三组来自同一 Florence 过程、原 hold split，现为开发样例。像素/经纬度标签转换与 native affine 不一致，空间评分阻断；样例无损伤正类；完整分卷未下载校验，原始 PNG 与 TIFF 像素配准未证实。 |
| D45 CrisisMMD v2.0 | 已有特定样本解码 | 原始完整标注 ZIP 与 QCRI 官方托管图像精确路径连接 3 组图文标签，覆盖野火/Harvey/Irma。 | 继承已有记录 | 社交相关性与影响标签不是天气真值；需转发去重、素材使用条款与真实拍摄/发布时点，过滤非天气事件。 |
| D46 Landslide4Sense | 已有特定样本解码 | Landslide4Sense 已验证 3 个 train 图像掩膜对；HDF5 缺时空/事件属性，降雨诱发成因仍未确认。 | 继承已有记录 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| D47 ExEBench / EarthExtreme-Bench | 已有特定样本解码 | ExEBench 寒潮子包完整：9 个来源案例、559 时间步；不是 9 个已确认独立过程。 | 继承已有记录 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| D48 ExtremeWeatherBench | 已有特定样本解码 | EWB 329 个案例定义及一个小时站点 parquet row group 的 122,880 行；未全部配对到案例。 | 继承已有记录 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| D49 WeatherQA | 已有特定样本解码 | 官方 12,803,203 字节 JSON 分片完整重建，共 8,511 条标注；3 张完整 GIF 与标注内配图路径精确匹配并解码。 | 继承已有记录 | 这里只验证官方图文内容；图为不同天气变量，不能按时刻计数；预报讨论文字不是独立灾害结果真值。 |
| D50 CyPortQA | 已有特定样本解码 | CyPortQA 已取得 Dorian/Harvey/Florence 各 1 图 1 文；精确公告时刻对齐及港口标签规则尚未验证。 | 继承已有记录 | 3 组图文可读；公告精确时间和港口影响标签待核，不能自动作未来结果。 |
| D51 WorldFloods v2 / ml4floods | 已有特定样本解码 | WorldFloods v2 完整 train S2 图像、gt 栅格和事件元数据已下载并通过网格一致性检查。 | 继承已有记录 | 一组图像不是独立事件覆盖；混合来源许可和标签/时序定义需核验。 |
| D52 DroughtED | 已有特定样本解码 | DroughtED train ZIP 前缀解析 26,666 行，含 3,809 非空周标签；实际至 2016 与文档 train 2000-2009 冲突；需固定原文件切分。 | 继承已有记录 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| D53 M4Fog | 尚无目标样本解码 | M4Fog 作者仓库与公开网盘分享页可访问。 | 继承已有记录 | 尚未取得原生多模态 cube；需要可直接下载的作者分包或已登录网盘访问。 |
| D54 CLLMate | 仅目录/元数据 | CLLMate 公共 JSON 7,747 节点已解析；包括非天气事件；新闻/原图与因果边未验证，不作因果 Gold。 | 继承已有记录 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| D55 SNODAS SWE | 已有特定样本解码 | 3 个 SNODAS SWE 日网格；SWE 与新降雪深度分开。 | 继承已有记录 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| D56 USGS continuous observations | 已有特定样本解码 | 两个正式站点映射，50 个水位样值；Scotia 另有 25 个同站流量样值。 | 继承已有记录 | 当前样例均为 Provisional；地点、变量、基准及冻结质量政策逐任务绑定。 |
| D57 NWPS stage forecasts | 已有特定样本解码 | SCOC1/GUEC1 两站各 119 个水位预报记录，已核官方 USGS 对应关系。 | 继承已有记录 | 普通 API 的滚动服务不证明历史业务版本；当前阈值不自动适用于历史。 |
| D58 NDBC Buoys | 已有特定样本解码 | 3 个 NDBC 浮标的波浪记录；只作海岸风浪背景。 | 继承已有记录 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| D59 MeteoNet | 已有特定样本解码 | MeteoNet 111,623 条站报、484 站和红外数组；雷达 NPZ 时间对象未启用 pickle。 | 继承已有记录 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| D60 Caravan | 已有特定样本解码 | Caravan 三个美国流域，各 14,609 日；适合历史水文与属性辅助。 | 继承已有记录 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| D61 HANZE v2.1 | 仅目录/元数据 | HANZE 2,521 个欧洲洪水影响目录条目；仅用于事件索引。 | 继承已有记录 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| D62 Dheed | 仅目录/元数据 | Dheed 82,839 派生干热事件记录可读；先查上游依赖和定义，不能作为另一份独立观测真值。 | 继承已有记录 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| D63 DAWN | 已有特定样本解码 | DAWN Fog/Rain/Sand/Snow 四个子包各取 3 张原始图片，共 12 张，ZIP 成员 CRC 和图片解码均通过。 | 继承已有记录 | 视觉条件数据缺乏可验证时空/天气严重度，Fog 样例文件名含 haze；只能先作视觉辅助集。 |
| D64 SenForFlood | 已有特定样本解码 | 官方镜像取得 EMSR339 的 7 个完整 TIFF：S1/S2 灾前与灾中、地形、LULC、掩膜；512×512 同 EPSG:3857 网格。 | 继承已有记录 | 掩膜 0/1/2 的准确图例、波段定义及精确观测 UTC 尚未确认；不得把非零统一当洪水，暂不评分二值洪水/未来预警。 |
| D65 FPA-FOD6 | 已有特定样本解码 | FPA-FOD6 已复核 3 条火灾记录；与 FIRMS、火烧迹地按事件合并，起火原因不能默认极端天气。 | 继承已有记录 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| D66 WeatherBench2 ERA5 | 已有特定样本解码 | WeatherBench2 一个 ERA5 温度 chunk 已复核；记录为 ERA5 衍生产品，不冒充 D25 ERA5-Land。 | 继承已有记录 | 继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。 |
| D67 NOAA HRRR operational forecasts | 已有特定样本解码 | 同一 00Z 起报 +6h：气温、能见度、冻雨分类，1799×1059。 | 继承已有记录 | 冻雨样例全零；仅确认数值字段可读，尚无实际冬季正例链。 |
| D68 HKO-7 | 历史记录仍待授权 | 公开日天气统计和时间索引可得；已核对作者原始雷达数据申请说明。 | 继承已有记录 | 雷达影像和掩膜须由高校/研究机构成员签署承诺书，并用机构邮箱申请；本机没有这部分样本。 |
| D69 GESLA current / GESLA-3 candidate | 已有特定样本解码 | 当前 GESLA 端点实取一个站点 4 条完整小时海平面记录，单位 m，包含双质量标记。 | 继承已有记录 | 不是已锁定的 GESLA-3 版本；站点基准、flag1/flag2和天文潮/风暴潮区分仍需核验。 |
| D70 ESWD | 历史记录仍待授权 | ESWD 公共页面可访问，尚无许可明确的批量事件样本。 | 继承已有记录 | 需要确认研究用途的数据访问许可和批量提供方式。 |
| D71 CAMELSH | 已有特定样本解码 | 官方公开版本 16729675 的 Hourly2.zip 经 9 次 Range 取得 3 个完整 NetCDF；各 394,488 个名义小时格，1980—2024，流量/水位含单位和缺测。 | 继承已有记录 | 流量 m3/s、水位 m 分开；缺测格不是有效观测；需水位基准、质量成熟度和专业预报匹配，所取成员不含完整气象驱动。 |
| D72 MSETCD / MSCAR | 尚无目标样本解码 | MSCAR 仓库明确对应 MSETCD 数据集；作者网盘分享入口已访问。 | 继承已有记录 | MSCAR 是代码/模型而非另一独立数据集；原生 MSETCD 影像尚未取回。 |
| D73 CMA Best Track | 已有特定样本解码 | 用户提供 CMA RAR 的 77 个年度文件均通过 CRC；1949—2025 年，2,549 个气旋段、74,370 个时次，保留 734 行可选第七列。 | 继承已有记录 | 官方格式页仍返回 468。经纬度比例、风速单位/平均时段、缺失码及 UTC 定义待原始文档绑定；最佳路径是事后分析，历史预报配对和发布时间另验。 |
| D74 NOAA Billion-Dollar Disasters | 仅目录/元数据 | NOAA Billion-Dollar Disasters 完整事件 CSV 已获取并解析。 | 继承已有记录 | 经济损失阈值决定入选，地区偏差明显；只作影响事件索引。 |
| AW-HURDAT2 NHC HURDAT2 Atlantic | 已有特定样本解码 | 已与四个风暴的数字预报精确匹配；原始结果文件本轮重新核验哈希。 | 继承已有记录 | 同机构事后分析 P；不用作独立原始传感器 O。 |
| AW-HEFS NOAA HEFS QINE ensemble | 已有特定样本解码 | Scotia 两轮完整集合产品，每轮 45 成员 × 721 时次。 | [hydro_e_extension_01/FREE_COMMON_BASELINE_CONTROL.json](hydro_e_extension_01/FREE_COMMON_BASELINE_CONTROL.json) | 流量 CFS 不能直接套用水位洪水阈值；成员权重、flag 与概率合同待冻结。 |
| AW-NIMS USGS NIMS cameras | 已有特定样本解码 | 旧审计有一个站点三张真实影像与近时水位；本轮水文两站相机接口未找到。 | 继承已有记录 | 仅作条件性原生视觉证据；不把像素直接反演为精确水位 Gold。 |
| AW-GHCNH NOAA GHCNh current hourly archive | 已有特定样本解码 | 2026 Denver 单站文件首尾各 1 MiB，4,558 个完整稀疏行；476 行非空气温，涵盖 1 月及 9 月。 | 继承已有记录 | 不是整年下载；9 月气温 QC 为空不能当作通过 QC。温度已为摄氏度，能见度为 km，现象码含 TS:17 等字符串。 |
| AW-GEFS NOAA GEFS ensemble | 已有特定样本解码 | 同一 00Z 起报 +6h，c00/p01 两成员各有气温与 0-6h 降水，720×361。 | 继承已有记录 | 仅抽样两个成员；不能用此宣称完整集合、官方概率或已校准概率。 |
| AW-SPC SPC Day 1 convective outlook | 已有特定样本解码 | 2026-09-10 13Z outlook ZIP 完整 CRC 通过；7 类产品有 28 个 shapefile 表示层，含 cat/hail/torn/wind 及 CIG。 | 继承已有记录 | 28 层不是 28 个独立预报或灾害；DN、CIG 与区域/时间支持需按版本解释。 |
| AW-MESH MRMS MESH | 已有特定样本解码 | 一个完整 gzip/GRIB，7000×3500；时间 2026-09-10 00:00:43，最大原值 24.9。 | 继承已有记录 | 本地 ecCodes 名称/单位为 unknown，含负代码；先补官方局地表/有效掩膜再设阈值，不能等同地面雹径。 |
| AW-QPE MRMS MultiSensor QPE 01H Pass2 | 已有特定样本解码 | 一个完整 gzip/GRIB，7000×3500；2026-09-10 00Z，1,676,667 个正原值，含 -3 代码。 | [h07_extension_01/decoded_01/REPORT.json](h07_extension_01/decoded_01/REPORT.json); [h07_extension_01/semantic_contract_01/QUALIFICATION.json](h07_extension_01/semantic_contract_01/QUALIFICATION.json) | 文件名为 1h QPE，但通用 GRIB 解码显示 instant/unknown units；产品累计窗、单位、Pass2 延迟与代码表须以产品规范绑定。 |
| AW-ABI GOES-19 ABI C01 / C13 | 已有特定样本解码 | 2026-09-10 可见光 C01 与红外 C13 两个完整 NetCDF；C01 1000×1000，DQF 均为 0。 | 继承已有记录 | 两个通道/同一上游不是独立事件；原始变量、投影及 DQF 必须保留。 |
| AW-METAR AWC METAR observations | 已有特定样本解码 | KDEN/KJFK/KSFO 共 35 条实际站报。 | [shadow_capture_01/poll_00/metar.receipt.json](shadow_capture_01/poll_00/metar.receipt.json) | 滚动接口不是长期历史档案；SM/kt 等原始单位及能见度上下界要解析。 |
| AW-TAF AWC TAF forecasts | 已有特定样本解码 | KDEN/KJFK/KSFO 三站 TAF 原文和结构化预报组。 | [development_dataset_v2/BUILD.json](development_dataset_v2/BUILD.json); [shadow_capture_01/poll_00/taf.receipt.json](shadow_capture_01/poll_00/taf.receipt.json) | FM/TEMPO/PROB 语义与机场范围必须保留；TAF 预报雾不能作未来观测标签。 |
| AW-IEM IEM historical METAR archive | 已有特定样本解码 | OKC 2020 冰暴窗口 108 行：47 条 FZRA、8 条 FZDZ；PHX 2011 沙尘窗口 68 行：5 条 DS、10 条 BLDU。 | [development_dataset_v2/BUILD.json](development_dataset_v2/BUILD.json); [regional_calendar_extension_01/BATCH_COMPLETE.json](regional_calendar_extension_01/BATCH_COMPLETE.json); [reports/large_model_diagnostic_01/VALIDATION.json](reports/large_model_diagnostic_01/VALIDATION.json) | IEM 是历史站报再分发端，不是独立传感器；两次选择性历史过程均已暴露，仅作开发/可行性材料。 |
| AW-EDDI NOAA EDDI 01-month | 已有特定样本解码 | 2026-01-01 ESRI ASCII，224×464；79,831 个非缺测有限值。 | 继承已有记录 | 文件没有显式 CRS；EDDI 不直接等于土壤水分、闪旱或已发布预报。 |
| AW-CPC CPC Seasonal Drought Outlook | 已有特定样本解码 | 完整 15,714,252 字节 ZIP，19 个成员；2026-08-20 签发，目标 November30，两个形状层。 | 继承已有记录 | 季节性分类展望不对应下一周 USDM 概率；类别及空间范围保持原产品定义。 |
| AW-OFS NOAA CBOFS station forecast | 已有特定样本解码 | 完整 50,650,138 字节 NetCDF；209 个模型位置、481 时次/48h，100,529 个有限 zeta 值，单位 m。 | 继承已有记录 | 模型位置尚无正式 CO-OPS 站号/垂直基准桥；不能直接和潮位站阈值比较。 |
| AW-PETSS NOAA P-ETSS tide/surge station bulletins | 已有特定样本解码 | 两份完整数值公告，各 290 个位置 × 102 值；210 个数字 ID、80 个 est ID，原单位 0.1 ft。 | 继承已有记录 | 明确 NOT VALID FOR TROPICAL STORM；e10 概率含义、时间对齐、基准及 -400 代码未准入。 |
| AW-WPC WPC QPF / winter products | 已有特定样本解码 | 从实际 2p5km_qpf 目录取回完整 GRIB 数值降水预报并解析。 | 继承已有记录 | 当前只验证 QPF；冬季雪/冰概率及厚度产品仍须独立抽样。 |
| AW-GWIS GWIS FWI map service | 已有特定样本解码 | 从官方前端定位数值接口，实取 (-4,40) 五天、八项火险指数，含 FWI/FFMC/ISI。 | 继承已有记录 | FWI 不是起火概率；缺原始签发版本与历史发布证明；完整原生格点导出另核。 |
| AW-EFFIS EFFIS fire danger service | 已有特定样本解码 | 旧版停用后验证新版专属配置绑定数值接口，实取 (-7,42) 五天、八项指数。 | 继承已有记录 | 与 GWIS 共享 ECMWF 后端，不能作为另一独立模型；缺签发版本、历史发布时间和格点导出验证。 |
| AW-CAMS CAMS dust/composition forecast | 已有特定样本解码 | 此前 ADS 授权后已实取并解码 dust AOD 数值预报，旧 401 状态已失效。 | 继承已有记录 | 光学厚度不等于地面沙尘暴；未来有效窗、现象观测和延迟需配对。 |
| AW-GLOFAS GloFAS operational forecast | 已有特定样本解码 | 此前 EWDS 授权后已实取并解码流量数值预报，旧 401 状态已失效。 | 继承已有记录 | 网格与河网/站点匹配、平均时窗及阈值不能默认兼容。 |
| AW-EFAS EFAS operational forecast | 已有特定样本解码 | EWDS 历史 forecast 数值已下载解码；公开历史路径不再受旧 403 许可阻断。 | 继承已有记录 | 公共下载约有 30 天延迟；实时合作伙伴权限未验证，不宣称实时 EFAS 可用。 |
| AW-SMAPL4 SMAP L4 SPL4SMGP v008 | 已有特定样本解码 | NASA 原生 rootzone/surface 3×3 数值和 GEE 样例均已取回。 | 继承已有记录 | 同化产品不是独立实测真值；时制、冻结/积雪和质量支持仍需细化。 |

## 这些数据怎样支撑 novelty

C1 需要同一个共同专业基线、合法资料菜单、共享预算和时间限制，比较补充取证的分配方式。仅下载更多数据或共享缓存不能单独证明 LLM 的贡献。

C2 需要可计算的证据支持、原生缺测/删失/版本规则，以及同预算下单目标与联合可达性参照。评估器有隐藏标签不代表模型已读懂影像；事实充分不等于未来预测有收益。

C3 需要上述机制在不同、独立的真实过程和资料类型中复现。当前数据基础足够继续开发，但样本下载清单不能替代同目标预报配对、独立过程实验和强对照。

后续顺序见 [v8 后续计划](NEXT_PHASE_PLAN_CN.md)：先完成冻结的大模型自适应结算，再补 H15 独立过程与区域概率映射，以及第二灾种的原生物理时间合同。
