"""Structured scientific decisions; reports are generated from this input plus audits."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
# id | recommendation | evidence class | observed capability candidates | remaining work
rows='''D01|core|inherited|C0,C1,C2,C3,C4,C5|复用已有 NHC 公告/GIS 和 Francine 种子；新增风暴独立分组；issued_at 不等于历史 available_at。
D02|bridge|numeric|C0,C3,C7|已解码 21,923 条轨迹、378 个 SID；属于事后参考，隔离 outcome；跨机构及跨盆地去重。
D03|conditional|partial|C0|Digital Typhoon ZIP Range 获取未完成；保留亚洲气旋扩容路线，不把目录计为帧。
D04|defer|reference|C0|TCIR 仅入口/读取器候选；尚未完成真实影像解码，需确认版本和切分。
D05|core|catalog|C0|136,982 条灾害报告仅作检索索引；EPISODE_ID 不等于独立天气系统；需要气象事件跨县合并。
D06|core|inherited|C0,C1,C3|复核 3 条 VIL 序列，每条 49 帧；不能据此声称已验证闪电/光学多模态；补地面报告桥接。
D07|conditional|numeric|C0,C1,C3|3 个 TorNet train NetCDF 均为 NUL 负例；核对 v1.1 修订并获取正例和匹配困难负例。
D08|bridge|unverified||NEXRAD 原始体扫尚无本轮解码样本；优先按 TorNet/SEVIR 具体雷达时刻补取。
D09|bridge|metadata|C0|MRMS 桶目录可列，尚无实际 MESH/降水文件；不能将 MESH 估计直接等同地面冰雹报告。
D10|core|numeric|C0,C1,C3|3 个 GLM 20 秒文件及父子 ID 已校验；须构建空间密度基线并补极端窗口；ABI 尚未取样。
D11|conditional|reference|C0|GFD 入口明确但没有实际事件栅格；GEE 项目访问与公开替代产品分开记录。
D12|conditional|paired|C0,C1,C3|3 组前后 SAR/标签/有效性完整匹配同一发布清单，但洪水正像素均为 0；同一 EMSR712/AOI10 且原 split 为 test，仅作已观察审计材料。
D13|conditional|unverified||KuroSiwo 的 HF 连接失败；下一轮锁定版本后仅取 train 正负样例，不承诺整个数据不可用。
D14|conditional|unverified||UrbanSARFloods 的 HF 连接失败；保留城市内涝候选，必须验证城市标签/事件身份。
D15|conditional|inherited|C0,C1|已复核 3 个 Sen1Floods11 图像标签对、2 个事件地区；许可字段存在歧义，先澄清数据再分发条款。
D16|conditional|reference|C0|SpaceNet8 读取文档可得；本轮未获取成对影像/道路标签，需保留原 split 并分开洪水与道路状态语义。
D17|conditional|reference|C0|FloodNet 文档可得，真实图像/标签未取样；无人机图像多样性不等于多个风暴。
D18|bridge|catalog|C0|CEMS EMSR712/AOI10 产品与影像时刻已列举；部分版本状态 N、无产品，不能当成成功下载或同目标修订。
D19|core|numeric|C0,C1,C3|3 天同一火场 TIFF；按作者读取器复算活动火像素 4/0/0；需新增独立火场、正例与火灭/缺测区别。
D20|conditional|partial||Next Day Wildfire ZIP 前缀已取得，TFRecord 尚未解码；需字段、CRC 和标签时距核验。
D21|conditional|numeric|C0,C1,C3|TS-SatFire 3 天同一火场 19 波段栅格可解码；最终标签通道和未来标签切片仍需读取器验证。
D22|conditional|unverified||Sen2Fire 尚未获取实际图像；只在需要独立火场/新地区时补源，不与同源火点重复计数。
D23|core|numeric|C0,C1|公开 FIRMS VIIRS CSV 可匿名取得；2,606 条为热点，不是 2,606 场野火；归因与事件分组待完成。
D24|bridge|unverified||MTBS 公开直链尝试失败；不必把 GEE 作为唯一入口，后续检查官方周界产品和许可。
D25|conditional|unverified||ERA5-Land 未实际验证；已有 WeatherBench2 ERA5 chunk 不能代替 ERA5-Land 认证与变量验证。
D26|core|numeric|C0,C3|5 个站点窗口 40 站日已解析；Toronto 查询为空；需季节基准、日界、质量标记和缺测规则。
D27|core|numeric|C0,C3|北京和沙特两个站年 28,733 报告；实有雾及浮/扬尘码，未发现本批沙尘暴/冻雨码正例。
D28|bridge|numeric|C0,C1|已从公开 S3 读 GFS 3 个变量 GRIB；仅同一次初始化 f000，不是多轮修订或 3 场极端。
D29|conditional|unverified||IMERG V07 尚无实测切片；CHIRPS DAILY_SAT 对 IMERG 的依赖不代表独立 IMERG 取样成功。
D30|core|numeric|C0,C1,C3|CHIRPS v3 DAILY_SAT 完成 2 个日栅格，第三日未完成；补站点、有效值编码与产品版本说明。
D31|core|inherited|C0,C1,C3|USDM 3 个周次已复核；采用已有专家标注，不新增逐题人工复核；不能把周次算独立干旱过程。
D32|conditional|unverified||SMAP 无实测土壤湿度切片；干旱/闪旱升级时再补，先确认冻土/植被与质量标记。
D33|conditional|unverified||MODIS Snow 未实测；雪盖与降雪/暴雪/冻雨分开，当前 SNODAS 可作为积雪补源。
D34|conditional|unverified||MODIS LST 未实测；地表温度不能替代 2 米气温热浪标签。
D35|bridge|reference|C0|MERRA-2 气溶胶仅文档与入口；优先补 dust 专属变量并与现象码配对，不能以高 AOD 单独判沙尘暴。
D36|conditional|unverified||S5P Aerosol Index 尚无实际切片；需将沙尘、烟羽、云和缺测区分。
D37|core|numeric|C0,C3|3 个潮位站各 240 对同基准面观测/潮汐预报已匹配；残差含多种作用，不能单独称纯风暴潮。
D38|extension|numeric|C0,C1,C3|OISST 3 个日 NetCDF 可读；海洋热浪为扩展方向，需长期气候态与持续性定义。
D39|defer|unverified||EM-DAT 注册和许可入口；不绕过访问条件；ExEBench 的案例 ID 也需检查派生使用条款。
D40|bridge|unverified||EONET 为事件检索备选，尚未有本轮解码事件；不能将事件目录当像素 Gold。
D41|bridge|unverified||GDACS 仅候选入口，当前未验证实际 feed；如已有 CEMS GDACS ID 再定向桥接。
D42|bridge|inherited_component|C1|S1 派生资产已在洪水数据中验证；独立原始 GRD/GEE 访问未验证，不重复算独立来源增量。
D43|bridge|unverified||S2 原始 SR 访问尚未验证；现有 SAR/背景切片不代表其可用，按事件补光学和云质量层。
D44|defer|unverified||xBD 有注册/许可门槛；建筑损伤属于下游影响，且需排除地震等非天气灾种。
D45|defer|reference|C0|CrisisMMD 仅入口候选；社交图像版权和文本真实性尚未落实，不作为因果真值。
D46|extension|paired|C1|Landslide4Sense 已验证 3 个 train 图像掩膜对；HDF5 缺时空/事件属性，降雨诱发成因仍未确认。
D47|core|numeric|C0,C1,C3|固定 commit 的寒潮 ZIP 完整校验：9 案例、559 时间步、8 国家/地区；其他六个子包未下载，ERA5/EM-DAT 来源与极端定义待核。
D48|core|numeric|C0,C3|EWB 解码 329 案例定义及 GHCN-hourly 一个 row group 122,880 行；尚未把该观测组匹配到 EWB 极端案例。
D49|bridge|reference|C0|WeatherQA 的 Drive 下载失败；SPC 2018/md0398 原文可取回；README 的 20 幅图是变量组，不是 20 个时刻。
D50|conditional|multiformat|C0,C1,C2|CyPortQA 已取得 Dorian/Harvey/Florence 各 1 图 1 文；精确公告时刻对齐及港口标签规则尚未验证。
D51|conditional|unverified||WorldFloods v2 的 HF 数据连接未完成；保留为全球光学洪水备选，核验每类源产品的许可。
D52|conditional|prefix_records|C0,C3|DroughtED train ZIP 前缀解析 26,666 行，含 3,809 非空周标签；实际至 2016 与文档 train 2000-2009 冲突；需固定原文件切分。
D53|conditional|reference|C0|M4Fog 仓库和网盘页可读，未取到真实 cube；镜像身份/条款和海雾正例均未完成验证。
D54|auxiliary|catalog|C0|CLLMate 公共 JSON 7,747 节点已解析；包括非天气事件；新闻/原图与因果边未验证，不作因果 Gold。
D55|core|numeric|C0,C1,C3|SNODAS 3 日 SWE 网格已解码；积雪不是暴雪/冻雨，32767 编码上限须结合产品说明。
D56|core|numeric|C0,C3|USGS 3 站各 3 条流量记录，9 条真实记录；返回日期不连续且不代表最新；需按洪水窗口重取。
D57|bridge|numeric|C0,C3|NWPS 3 站阶段水位可解析，流量字段 -999；BTRL1 未提供 usgsId，不能自动接到附近 USGS 站。
D58|bridge|numeric|C0,C3|NDBC 3 个浮标波高可解析；多条报告仍需按风暴/站点配对，波高不等于风暴潮。
D59|core|numeric|C0,C1,C3|MeteoNet 111,623 站报/484 站及 IR108 数组可读；雷达 NPZ object 时间不启用 pickle，时间桥接未完成。
D60|core|numeric|C0,C3|Caravan 3 个 CAMELS 美国流域各 14,609 日；流域属性/单位/极端阈值待补，ERA5-Land 驱动不是独立真值。
D61|core|catalog|C0|HANZE 2,521 欧洲洪水影响记录、40 国；用于非美国检索与类型校验，事件族去重另做。
D62|bridge|catalog|C0|Dheed 82,839 派生干热事件记录可读；先查上游依赖和定义，不能作为另一份独立观测真值。
D63|auxiliary|metadata|C0|DAWN 官方 API 枚举 Fog/Rain/Sand/Snow 四包；未抽取图片，时间/地点不足时仅作视觉条件辅助集。
D64|conditional|background|C0,C1|SenForFlood TAR 前缀取得 3 个 LULC TIFF；目前仅背景层，不是三组洪水图像标签对。
D65|bridge|inherited|C0|FPA-FOD6 已复核 3 条火灾记录；与 FIRMS、火烧迹地按事件合并，起火原因不能默认极端天气。
D66|bridge|inherited|C0,C1,C3|WeatherBench2 一个 ERA5 温度 chunk 已复核；记录为 ERA5 衍生产品，不冒充 D25 ERA5-Land。
D67|bridge|numeric|C0,C1|HRRR 已读同一次初始化 3 个 GRIB 变量；若做修订需同 valid_time 的多 init_time，当前未证实。
D68|conditional|catalog|C0|HKO-7 仓库日天气统计 2,556 行可读；实际雷达序列尚未取样。
D69|bridge|metadata|C0|GESLA 站点目录可读；现端点报告 format 5.0/2026，不能标作 GESLA-3；潮位实际切片未取回。
D70|defer|unverified||ESWD 适合补欧洲龙卷/冰雹，但本轮未获得许可明确的批量样本。
D71|conditional|metadata|C0|CAMELSH 发布元数据候选；未解码水文时序，需确认与 Caravan/CAMELS 的派生重叠。
D72|conditional|reference|C0|MSETCD/MSCAR 读取器或目录候选；未验证实际图像，用于后续亚洲气旋补源。
D73|conditional|reference|C0|CMA 最佳路径入口已登记；尚无完整样例解码，仅作未来多机构事后对照。
D74|auxiliary|reference|C0|NOAA Billion-Dollar 仅影响事件索引候选；经济损失阈值造成地区偏差，不定义全球气象极端。'''
items=[]
for line in rows.splitlines():
 ident,rec,level,caps,note=line.split('|',4)
 items.append(dict(source_id=ident,recommendation=rec,content_evidence=level,capability_candidates=caps.split(',') if caps else [],decision_cn=note,new_task_admitted=False,new_qualified_episode_count=0))
(ROOT/'SOURCE_DECISIONS.json').write_text(json.dumps(items,ensure_ascii=False,indent=2)+'\n')
