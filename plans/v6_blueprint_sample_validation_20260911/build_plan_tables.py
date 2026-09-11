"""Build the review tables from explicit source decisions and captured evidence."""

import csv
import io
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OLD = ROOT.parent / "v6_0911_dataset_selection"
AUDIT = "NEW_SAMPLE_AUDIT_05.json"


def dump(name, value):
    (ROOT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def cell(value):
    if isinstance(value, list):
        value = "; ".join(value)
    return str(value).replace("|", "\\|").replace("\n", " ")


def main():
    inherited = json.loads((OLD / "SOURCE_REGISTRY.json").read_text())["sources"]
    inventory = {}
    for item in inherited:
        ident = item["source_id"]
        evidence = item["content_evidence"]
        inventory[ident] = {
            "source_id": ident, "name": item["name"],
            "selection": "reserve_not_selected",
            "sample_status": "inherited_" + evidence,
            "sample_summary_cn": item["decision_cn"],
            "limitation_cn": "继承既有解析结论；本轮复核原文件哈希，未重跑所有旧解码器。",
            "urls": list(dict.fromkeys(item["registered_urls"] + item.get("observed_urls", []))), "capture_ids": [],
            "evidence_refs": ["INHERITED_SAMPLE_AUDIT.json", "../v6_0911_dataset_selection/SOURCE_REGISTRY.json"],
            "inherited_source_evidence": item.get("evidence", []),
            "new_formal_tasks": 0,
        }
    captures = {}
    for path in sorted(ROOT.glob("captures_*/MANIFEST.json")):
        for record in json.loads(path.read_text()):
            if record["id"] in captures:
                raise ValueError("duplicate capture ID")
            captures[record["id"]] = {**record, "receipt": str((path.parent / (record["id"] + ".json")).relative_to(ROOT))}
    audits = {r["capture_id"]: r for r in json.loads((ROOT / AUDIT).read_text())["reports"]}
    assemblies = {r["id"]: r for r in json.loads((ROOT / "ASSEMBLY_MANIFEST.json").read_text())}

    def source(ident, name, status, summary, limitation, ids=(), refs=(), urls=(), selection="selected_with_gates"):
        previous = inventory.get(ident, {})
        capture_ids = list(ids)
        for ident_assembled in ids:
            for part in assemblies.get(ident_assembled, {}).get("parts", []):
                capture_ids.append(json.loads((ROOT / part["receipt"]).read_text())["id"])
        capture_ids = list(dict.fromkeys(capture_ids))
        receipts = [captures[i]["receipt"] for i in capture_ids if i in captures]
        raw_paths = [audits[i]["raw_path"] for i in ids if i in audits]
        inventory[ident] = {
            **previous, "source_id": ident, "name": name, "selection": selection,
            "sample_status": status, "sample_summary_cn": summary, "limitation_cn": limitation,
            "capture_ids": capture_ids,
            "evidence_refs": list(dict.fromkeys(list(refs) + receipts + raw_paths + ([AUDIT] if any(i in audits for i in ids) else []))),
            "urls": list(dict.fromkeys(list(urls) + [captures[i]["url"] for i in capture_ids if i in captures] + previous.get("urls", []))),
            "new_formal_tasks": 0,
        }

    # Inherited samples remain useful; their scientific decoders were not rerun here.
    selected = {
        "D02": "已解码 21,923 条轨迹记录、378 个 SID；作分盆地事后分析参考。",
        "D05": "136,982 条实际灾害报告；作事件检索及独立定义的 R 结果。",
        "D06": "3 条完整 VIL 序列，每条 49 帧；用于雷达时序感知。",
        "D12": "3 组前后 SAR/标签/有效性配对；均为同一外部 test 激活下的洪水负瓦片。",
        "D19": "一个火场 3 天 TIFF；活动火像素 4/0/0，不能解释为后两天灭火。",
        "D23": "匿名 VIIRS CSV 有 2,606 条热点；尚未归并为火场。",
        "D26": "5 个站点窗口共 40 个站日，实际温度/降水/雪字段可读。",
        "D30": "CHIRPS v3 DAILY_SAT 两个完整日栅格；用于明确标注的降水产品结果/背景。",
        "D31": "3 个实际 USDM 周产品；采用既有专家分析等级，程序化提取。",
        "D37": "3 个潮位站共 720 对同基准观测/天文潮预报；不是完整风暴潮预报。",
        "D47": "ExEBench 寒潮子包完整：9 个来源案例、559 时间步；不是 9 个已确认独立过程。",
        "D48": "EWB 329 个案例定义及一个小时站点 parquet row group 的 122,880 行；未全部配对到案例。",
        "D55": "3 个 SNODAS SWE 日网格；SWE 与新降雪深度分开。",
        "D58": "3 个 NDBC 浮标的波浪记录；只作海岸风浪背景。",
        "D59": "MeteoNet 111,623 条站报、484 站和红外数组；雷达 NPZ 时间对象未启用 pickle。",
        "D60": "Caravan 三个美国流域，各 14,609 日；适合历史水文与属性辅助。",
        "D61": "HANZE 2,521 个欧洲洪水影响目录条目；仅用于事件索引。",
    }
    for ident, summary in selected.items():
        inventory[ident].update(selection="selected_with_gates", sample_summary_cn=summary)
    for ident in ("D12", "D47", "D48", "D58", "D59", "D60", "D61"):
        inventory[ident]["selection"] = "selected_auxiliary_or_diagnostic"
    inventory["D27"].update(selection="legacy_historical_only", limitation_cn="ISD 已被 GHCNh 替代；保留旧冻结资产兼容，不用于持续获取当前站点数据。")
    inventory["D15"].update(selection="conditional_rights", limitation_cn="已有真实配对样例；数据再分发条款歧义未解，先保留配方和引用。")
    inventory["D18"].update(selection="selected_event_bridge", limitation_cn="已取得产品目录与时空身份链；目录可读不等于所有原生地图已下载。")
    inventory["D21"].update(selection="conditional_target_semantics", limitation_cn="真实 19 波段数组可读；未来目标通道和有效掩膜语义未完成准入。")
    inventory["D50"].update(selection="selected_auxiliary_or_diagnostic", limitation_cn="3 组图文可读；公告精确时间和港口影响标签待核，不能自动作未来结果。")

    join_refs = ["INHERITED_JOIN_BINDINGS.json", "../v6_data_decision_20260911/nhc_audit_01/AUDIT.json"]
    source("D01", "NHC forecast advisories / GIS", "inherited_join_rehashed", "64 份公告、461 行数字预报；4 个已暴露风暴组，96 个唯一时刻有事后参考匹配。", "96 个匹配目标不是 96 场独立气旋；历史公开可用时间仍未证实。", refs=join_refs)
    source("AW-HURDAT2", "NHC HURDAT2 Atlantic", "inherited_join_rehashed", "已与四个风暴的数字预报精确匹配；原始结果文件本轮重新核验哈希。", "同机构事后分析 P；不用作独立原始传感器 O。", refs=join_refs, urls=["https://www.nhc.noaa.gov/data/#hurdat"])
    hydro_refs = ["INHERITED_JOIN_BINDINGS.json", "../v6_data_decision_20260911/hydro_audit_01/AUDIT.json"]
    source("D56", "USGS continuous observations", "inherited_join_rehashed", "两个正式站点映射，50 个水位样值；Scotia 另有 25 个同站流量样值。", "当前样例均为 Provisional；地点、变量、基准及冻结质量政策逐任务绑定。", refs=hydro_refs)
    source("D57", "NWPS stage forecasts", "inherited_join_rehashed", "SCOC1/GUEC1 两站各 119 个水位预报记录，已核官方 USGS 对应关系。", "普通 API 的滚动服务不证明历史业务版本；当前阈值不自动适用于历史。", refs=hydro_refs, urls=["https://api.water.noaa.gov/nwps/v1/gauges/SCOC1/stageflow", "https://api.water.noaa.gov/nwps/v1/gauges/GUEC1/stageflow"])
    source("AW-HEFS", "NOAA HEFS QINE ensemble", "inherited_join_rehashed", "Scotia 两轮完整集合产品，每轮 45 成员 × 721 时次。", "流量 CFS 不能直接套用水位洪水阈值；成员权重、flag 与概率合同待冻结。", refs=hydro_refs, urls=["https://api.water.noaa.gov/hefs/v1/ensembles/"])
    source("AW-NIMS", "USGS NIMS cameras", "inherited_image_stage_pair", "旧审计有一个站点三张真实影像与近时水位；本轮水文两站相机接口未找到。", "仅作条件性原生视觉证据；不把像素直接反演为精确水位 Gold。", refs=["../v6_active_warning_review_20260911/HYDRO_FEASIBILITY.json", "../v6_active_warning_review_20260911/NIMS_IMAGE_DECODE.json"], urls=["https://api.waterdata.usgs.gov/docs/nims"], selection="conditional_same_site_visual")

    source("AW-GHCNH", "NOAA GHCNh current hourly archive", "new_rows_decoded", "2026 Denver 单站文件首尾各 1 MiB，4,558 个完整稀疏行；476 行非空气温，涵盖 1 月及 9 月。", "不是整年下载；9 月气温 QC 为空不能当作通过 QC。温度已为摄氏度，能见度为 km，现象码含 TS:17 等字符串。", ids=["ghcnh-product", "isd-migration", "ghcnh-doc", "ghcnh-denver-prefix", "ghcnh-denver-tail"], refs=["GHCNH_DOCUMENTATION_TEXT.txt"])
    source("D28", "NOAA GFS 0.25 degree operational forecasts", "new_future_grib_decoded", "2026-09-10 00Z 起报、+6h：温度、10m U/V、0-6h 累计降水、能见度、阵风、冻雨分类，共 7 条完整 GRIB。", "同一次起报不构成修订序列；690 个冻雨非零格点属于预报，不是冻雨实测。", ids=["gfs-t2m", "gfs-u10", "gfs-v10", "gfs-apcp6h", "gfs-vis", "gfs-gust", "gfs-frzr"])
    source("AW-GEFS", "NOAA GEFS ensemble", "new_future_grib_decoded", "同一 00Z 起报 +6h，c00/p01 两成员各有气温与 0-6h 降水，720×361。", "仅抽样两个成员；不能用此宣称完整集合、官方概率或已校准概率。", ids=["gefs-c00-t2m", "gefs-c00-apcp6h", "gefs-p01-t2m", "gefs-p01-apcp6h"])
    source("D67", "NOAA HRRR operational forecasts", "new_future_grib_decoded", "同一 00Z 起报 +6h：气温、能见度、冻雨分类，1799×1059。", "冻雨样例全零；仅确认数值字段可读，尚无实际冬季正例链。", ids=["hrrr-t2m", "hrrr-vis", "hrrr-frzr"])
    source("AW-SPC", "SPC Day 1 convective outlook", "new_forecast_polygons_decoded", "2026-09-10 13Z outlook ZIP 完整 CRC 通过；7 类产品有 28 个 shapefile 表示层，含 cat/hail/torn/wind 及 CIG。", "28 层不是 28 个独立预报或灾害；DN、CIG 与区域/时间支持需按版本解释。", ids=["spc-day1-shapes"])
    source("D08", "NOAA NEXRAD Level II", "new_radar_arrays_decoded", "KTLX 2026-09-10 00:01:20.788 完整体扫，12 个 sweep，反射率/偏振矩可解析。", "MetPy 报 unknown message 32；并非所有报文或科学 QC 都已验证。", ids=["nexrad-sample"])
    inventory["D09"].update(selection="product_family_parent", limitation_cn="本轮 MESH 与 QPE 的实际样例分别见 AW-MESH/AW-QPE；父目录不重复计算为第三个来源。")
    source("AW-MESH", "MRMS MESH", "new_product_array_semantics_pending", "一个完整 gzip/GRIB，7000×3500；时间 2026-09-10 00:00:43，最大原值 24.9。", "本地 ecCodes 名称/单位为 unknown，含负代码；先补官方局地表/有效掩膜再设阈值，不能等同地面雹径。", ids=["mrms-mesh-sample", "mrms-grib-info", "mrms-product-guide"], selection="conditional_product_semantics")
    source("AW-QPE", "MRMS MultiSensor QPE 01H Pass2", "new_product_array_semantics_pending", "一个完整 gzip/GRIB，7000×3500；2026-09-10 00Z，1,676,667 个正原值，含 -3 代码。", "文件名为 1h QPE，但通用 GRIB 解码显示 instant/unknown units；产品累计窗、单位、Pass2 延迟与代码表须以产品规范绑定。", ids=["mrms-qpe-sample"], selection="conditional_product_semantics")
    inventory["D10"].update(name="GOES GLM (inherited sampled product)", selection="selected_with_gates", limitation_cn="本项实际继承 3 个 20 秒 GLM 产品；新 ABI 样例单列 AW-ABI，避免重复统计。")
    source("AW-ABI", "GOES-19 ABI C01 / C13", "new_netcdf_arrays_decoded", "2026-09-10 可见光 C01 与红外 C13 两个完整 NetCDF；C01 1000×1000，DQF 均为 0。", "两个通道/同一上游不是独立事件；原始变量、投影及 DQF 必须保留。", ids=["goes19-abi-sample", "goes19-abi-ir-sample"])
    source("AW-METAR", "AWC METAR observations", "new_aviation_rows_decoded", "KDEN/KJFK/KSFO 共 35 条实际站报。", "滚动接口不是长期历史档案；SM/kt 等原始单位及能见度上下界要解析。", ids=["metar-json"])
    source("AW-TAF", "AWC TAF forecasts", "new_aviation_forecasts_decoded", "KDEN/KJFK/KSFO 三站 TAF 原文和结构化预报组。", "FM/TEMPO/PROB 语义与机场范围必须保留；TAF 预报雾不能作未来观测标签。", ids=["taf-json"])
    source("AW-IEM", "IEM historical METAR archive", "new_positive_phenomena_rows_decoded", "OKC 2020 冰暴窗口 108 行：47 条 FZRA、8 条 FZDZ；PHX 2011 沙尘窗口 68 行：5 条 DS、10 条 BLDU。", "IEM 是历史站报再分发端，不是独立传感器；两次选择性历史过程均已暴露，仅作开发/可行性材料。", ids=["iem-freezing-rain", "iem-dust-storm"])
    source("AW-EDDI", "NOAA EDDI 01-month", "new_drought_array_decoded", "2026-01-01 ESRI ASCII，224×464；79,831 个非缺测有限值。", "文件没有显式 CRS；EDDI 不直接等于土壤水分、闪旱或已发布预报。", ids=["eddi-grid"])
    source("AW-CPC", "CPC Seasonal Drought Outlook", "new_forecast_shapes_decoded", "完整 15,714,252 字节 ZIP，19 个成员；2026-08-20 签发，目标 November30，两个形状层。", "季节性分类展望不对应下一周 USDM 概率；类别及空间范围保持原产品定义。", ids=["cpc-seasonal"], refs=["ASSEMBLY_MANIFEST.json"])
    source("AW-OFS", "NOAA CBOFS station forecast", "new_forecast_netcdf_decoded", "完整 50,650,138 字节 NetCDF；209 个模型位置、481 时次/48h，100,529 个有限 zeta 值，单位 m。", "模型位置尚无正式 CO-OPS 站号/垂直基准桥；不能直接和潮位站阈值比较。", ids=["ofs-forecast"], refs=["ASSEMBLY_MANIFEST.json"])
    source("AW-PETSS", "NOAA P-ETSS tide/surge station bulletins", "new_forecast_tables_decoded", "两份完整数值公告，各 290 个位置 × 102 值；210 个数字 ID、80 个 est ID，原单位 0.1 ft。", "明确 NOT VALID FOR TROPICAL STORM；e10 概率含义、时间对齐、基准及 -400 代码未准入。", ids=["petss-stormtide-sample", "petss-stormsurge-sample"])
    source("AW-WPC", "WPC QPF / winter products", "rendered_qpf_only", "实际 QPF GIF 可解码，冬季产品页面可读；数值网格候选请求未成功。", "只作产品读图候选；没有 QPF 或冬季概率数组，不冒充数字专业基线。", ids=["wpc-qpf-index", "wpc-winter-page", "wpc-grib-day1", "wpc-qpf-grib-local"], selection="conditional_numeric_forecast")
    source("AW-GWIS", "GWIS FWI map service", "rendered_fwi_only", "实际 256×192 FWI PNG 与 WMS 能力表；WCS 不暴露数值 FWI，点值查询为空。", "图层说明提及 ECMWF reanalysis，不能把该样例称为已验证业务火险预报；FWI 也不等于起火/扩展事实。", ids=["gwis-fwi-map", "gwis-wms-capabilities", "gwis-wcs-capabilities", "gwis-fwi-info-corrected"], selection="conditional_numeric_forecast")
    source("AW-EFFIS", "EFFIS fire danger service", "metadata_or_empty_response", "官方页面可读，WMS 能力请求返回空的 HTTP 200。", "不把 GWIS 地图替算为 EFFIS 数值取样成功；共用基础设施也不等于独立来源。", ids=["effis-page", "effis-wms-capabilities"], selection="reserve_not_selected")
    blocked = [
        ("AW-CAMS", "CAMS dust/composition forecast", ["cams-small-retrieval"], "小范围匿名实际提取 POST 返回 401 authentication required；无 dust 数组。"),
        ("AW-GLOFAS", "GloFAS operational forecast", ["glofas-small-retrieval"], "元数据可读；小范围实际提取 POST 返回 401，无流量数组。"),
        ("AW-EFAS", "EFAS operational forecast", ["efas-small-retrieval"], "过程模式可读；小范围实际提取 POST 返回 401，无流量数组。"),
        ("AW-SMAPL4", "SMAP L4 SPL4SMGP v008", ["smap-l4-granules", "smap-l4-header-range", "smap-l4-dds"], "已找到真实 granule；原始片段与 OPeNDAP 请求均为 401，无土壤水分数组。"),
        ("D29", "IMERG V07 Early / Late", ["imerg-early-list", "imerg-late-list"], "Early/Late GIS 归档请求均为 401；本轮没有实际 IMERG 数组。"),
    ]
    for ident, name, ids, summary in blocked:
        source(ident, name, "authentication_required_no_array", summary, "保留需账号/条款配置的扩展路线；本轮匿名尝试失败不证明数据科学上不可用。", ids=ids, selection="conditional_authentication")
    source("D53", "M4Fog", "repository_and_share_page_only", "README 与完整代码树可读；网盘停在提取/验证页面，未取得原生 cube。", "不能用仓库图片替代真实样本；主雾任务先采用 TAF/METAR。", ids=["m4fog-readme", "m4fog-tree", "m4fog-track-a-share"], selection="conditional_data_access")
    source("D07", "TorNet / v1.1 check", "inherited_negatives_new_archive_partial", "继承 3 个可解码 train 负例；本轮确认 v1.1 发布记录，新增归档前缀超时、无完整成员。", "新增前缀不是成功 NetCDF 样本；仍缺实际正例及其与预警窗口的桥接。", ids=["tornet-readme", "tornet-current-record", "tornet-prefix-positive-search", "tornet-catalog-prefix"], refs=["INHERITED_SAMPLE_AUDIT.json"], selection="conditional_positive_sample")

    hazards = []

    def hazard(ident, group, name, subtypes, target, kinds, forecasts, observations, auxiliaries, conditional, scale, rules, readiness):
        hazards.append({
            "hazard_id": ident, "group": group, "name_cn": name, "subtypes": subtypes,
            "fixed_future_target_cn": target, "outcome_kinds": kinds,
            "forecast_sources": forecasts, "outcome_and_observation_sources": observations,
            "auxiliary_or_benchmark_sources": auxiliaries, "conditional_extension_sources": conditional,
            "time_scale_cn": scale, "processing_rules_cn": rules, "current_readiness_cn": readiness,
            "E_status": "source_sample_supported_task_compilation_pending",
            "F_status": "designed_not_formally_admitted",
            "D_status": "requires_admitted_F_and_public_cost_contract",
            "new_formal_tasks": 0,
        })

    hazard("H01", "气旋与非对流风暴", "热带气旋", ["强度", "路径", "局地风影响另设"],
           "已监测气旋在固定未来 T 的最大持续风或位置；不得根据事后登陆结果选择监测时刻。", ["P"],
           ["D01"], ["AW-HURDAT2", "D02"], ["AW-ABI", "D50"], ["D03", "D04", "D73"], "6-72h；按公告合法有效时刻对齐",
           ["storm_id 与 UTC 时刻精确连接，不默认时间插值。", "风速平均时长/机构/盆地保留；最佳路径机构差异不平均成唯一真值。", "HURDAT2、事后 IBTrACS 只进私有结果层；同风暴洪水/潮位任务共享事件组。"],
           "既有数值预报—参考匹配最完整；四个风暴都是已暴露开发材料，正式历史 as-of 待证。")
    hazard("H02", "气旋与非对流风暴", "温带风暴/非对流大风", ["持续风", "阵风", "风暴系统"],
           "固定站点/区域未来窗口持续风或阵风越阈；非对流归因单列。", ["O", "R"],
           ["D28", "AW-GEFS", "D67"], ["AW-GHCNH", "AW-METAR"], ["D05", "D48"], ["D27"], "6-48h；点值与窗内最大分开",
           ["10m 持续风、阵风、测量高度和平均时长分别存储。", "冻结网格到站点方法；阵风预报的时间支持不能直接当持续风。", "非对流身份必须有过程/产品依据，否则仅名为大风任务。"],
           "站点与未来预报字段均实际可读；同窗匹配、QC、极端正例及非对流归因待完成。")
    hazard("H03", "强对流", "雷暴大风/下击暴流", ["对流阵风", "下击暴流专门子类"],
           "固定未来时空窗口的合格对流阵风 O 或雷暴大风报告 R；两种结果分开。", ["O", "R"],
           ["AW-SPC", "D67"], ["AW-GHCNH", "AW-METAR", "D05"], ["D08", "AW-ABI", "D06"], ["D49"], "分钟至小时；SPC 使用原有效窗",
           ["VIL、反射率、雷电和阵风保持各自语义。", "下击暴流不能只由强风或高 VIL 自动标注。", "报告无记录仅能作完备报告库下的 R 负例，不能作 O 的物理无灾标签。"],
           "SPC 多边形、NEXRAD 体扫与站报均可用；地面测量和过程归因需建立连接。")
    hazard("H04", "强对流", "龙卷风", ["未来事件报告", "雷达感知诊断"],
           "指定未来窗口内是否有按冻结数据库确认的龙卷报告 R；TorNet 现时标签只作独立诊断。", ["R"],
           ["AW-SPC"], ["D05"], ["D08", "AW-ABI", "D06"], ["D07", "D49", "D70"], "分钟至小时；区域 outlook 目标保留其时空支持",
           ["不把 TorNet 同时刻分类当成提前预测。", "选窗截止必须早于目标开始，轨迹及报告修订版本保留。", "同一母风暴多体扫跨县报告归组；原作者 split 与本项目暴露状态并存。"],
           "报告和雷达源成立；TorNet 仍只有三个已验证负例，v1.1 新正例未下载成功。")
    hazard("H05", "强对流", "冰雹", ["地面雹径报告", "雷达 MESH 代理"],
           "未来窗口地面报告雹径越阈 R；另设同支持的未来 MESH 产品越阈 P。", ["R", "P"],
           ["AW-SPC", "D67"], ["D05"], ["D08", "D06", "AW-ABI"], ["AW-MESH", "D70"], "分钟至小时",
           ["报告大小/测量估计属性及 inch-mm 转换保留。", "MESH 尚需局地 GRIB 单位与负代码表；数组可读不能直接准入阈值。", "SPC 25-mile 等概率定义不可原样赋给任意像元/站点小时。"],
           "报告路线可构建；MESH 已实际解码但科学语义准入未完成，P 子任务保留条件。")
    hazard("H06", "强对流", "强雷电", ["flash 数量", "有效覆盖面积密度"],
           "固定区域未来 10-60min 内 GLM flash 密度是否越过冻结阈值。", ["P"],
           [], ["D10"], ["AW-ABI", "D08", "D06"], [], "10-60min 为拟定合同，需连续文件覆盖",
           ["flash/group/event 不混算；跨文件/边界去重。", "按有效覆盖面积和时间归一，非观测区不能填零。", "气候极端阈值只由训练期同传感器/季节确定；专业概率未具备时用持续性及外推基线。"],
           "三个 GLM 产品可读且已有 ABI；连续极端窗口、跨文件 ID 与密度基准待完成。")
    hazard("H07", "降水与水灾", "极端降水", ["短时强降水", "日累计暴雨", "格点估计产品"],
           "站点/区域未来固定 1/3/6/24h 累计越阈；O 与降水分析产品 P 分榜。", ["O", "P"],
           ["D28", "AW-GEFS", "D67"], ["AW-GHCNH", "D26", "D30"], ["D59", "D48"], ["AW-QPE", "D29", "AW-WPC"], "1-24h；慢日产品单独支持",
           ["保留起止、降水率/累计量及累计重置，禁止重叠窗口相加。", "GHCNd 当地站日不可假作 UTC 日；GFS 0-6h 必须匹配同窗。", "MRMS Pass2 的处理滞后单列；CHIRPS DAILY_SAT 上游依赖不得当独立站雨量。"],
           "GFS/GEFS 未来累计和实际站雨量可读；新增 MRMS QPE 数组可读但单位/累计窗/代码表未准入；IMERG 401。")
    hazard("H08", "降水与水灾", "洪水/山洪/城市内涝", ["河洪", "山洪报告", "空间淹没/城市内涝"],
           "河站未来水位或流量越阈 O；山洪 R 与未来合格淹没图 P 各自固定目标。", ["O", "R", "P"],
           ["D57", "AW-HEFS"], ["D56", "D05"], ["D12", "D18", "D60", "D61"], ["AW-GLOFAS", "AW-EFAS", "AW-NIMS", "D15", "D13", "D14", "D51"], "河洪 6-72h；山洪短时；空间图按实际过境窗",
           ["用官方站号桥；水位/流量及垂直基准不互换。", "HEFS CFS 需要同变量阈值及成员权重，不直接生成洪水水位概率。", "SAR 标签保留永久水、无效/遮挡、地图制作时刻；城市子类须有城市证据，河洪不补其名额。"],
           "两站业务预报—观测连接已核；观测暂为 Provisional。GEOID 三个负瓦片已暴露；城市/山洪的完整 F 路线未通过。")
    hazard("H09", "降水与水灾", "风暴潮/沿岸淹没", ["沿岸总水位", "增水残差", "空间淹没"],
           "固定潮位站未来窗口总水位越同基准阈值 O；增水与淹没范围另设任务。", ["O"],
           [], ["D37"], ["D58", "D01"], ["AW-OFS", "AW-PETSS"], "1-48h；以合格模型和潮位覆盖为准",
           ["首选实际采集到的 CBOFS/P-ETSS 配对候选；站位/基准未核前不作正式专业基线。", "P-ETSS 当前公告明确不适用于热带风暴，气旋沿岸子类必须另验证 P-Surge 等产品。", "天文潮不是总水位预报；残差不唯一归因为风暴潮，波高不是潮位。"],
           "真实 OFS 数组、P-ETSS 数值表与潮位站样例俱在；正式站号、基准、产品适用范围是剩余核心门槛。")
    hazard("H10", "温度与冬季天气", "高温/热浪", ["点/日高温", "连续热浪"],
           "未来指定时刻/站日高温越阈，或固定多日窗满足气候相对阈值与持续规则。", ["O"],
           ["D28", "AW-GEFS", "D67"], ["AW-GHCNH", "D26"], ["D48"], ["D47", "D25", "D34"], "6h-7d，点值/日极值/持续过程分开",
           ["2m 气温、皮肤温度、体感指标不得互换。", "小时采样最大不是整日连续最大；热浪须完整持续窗与固定季节基准。", "基准期/地区阈值仅在开发侧确定，站点移动和 QC 纳入。"],
           "GHCNh 2026 记录与 +6h 预报实际可读；EWB 事件与观测未全连接，ExEBench 热浪包尚未取样。")
    hazard("H11", "温度与冬季天气", "寒潮/低温/霜冻", ["绝对低温", "快速降温", "空气霜冻条件"],
           "未来固定窗口低温越阈或满足降温幅度/持续规则；实际作物损害独立排除。", ["O"],
           ["D28", "AW-GEFS", "D67"], ["AW-GHCNH", "D26"], ["D47", "D48"], ["D25"], "6h-7d",
           ["温降必须有两个合格支持窗口；缺前值不可生成寒潮标签。", "空气 0 摄氏度附近条件不等于实际地表结霜或损害。", "ExEBench 事后案例只作检索/诊断，不暴露其极端结果给未来模型。"],
           "寒潮 benchmark 实包、站观测与通用预报均有样例；逐过程独立性、阈值和未来配对待完成。")
    hazard("H12", "温度与冬季天气", "暴雪/积雪/冰冻降水", ["新降雪", "积雪/SWE", "冻雨/冻毛毛雨", "暴风雪条件"],
           "未来固定窗的降雪/积雪越阈，或站点出现 FZRA/FZDZ；SWE 分列 P。", ["O", "P", "R"],
           ["D28", "D67"], ["D26", "AW-GHCNH", "AW-METAR", "AW-IEM", "D55"], ["D05"], ["AW-WPC", "D33"], "1-48h；积雪日尺度另列",
           ["雪深、SWE、新降雪及冻雨分别建 target。", "实际已取得 FZRA/FZDZ 正例站报；GFS/HRRR 分类是输入预报。", "暴风雪需要同时满足风、能见度、雪和持续规则；积雪正例不能替代。"],
           "已补冻雨真实正例，SNODAS 与站雪字段可用；WPC 冬季概率数组、暴风雪完整多变量样例仍缺。")
    hazard("H13", "干旱与火险", "干旱/闪旱", ["USDM 周等级", "独立定义的快速土壤干旱"],
           "未来指定 USDM 周版等级/面积越阈 P；闪旱以冻结快速下降、持续和恢复规则另建。", ["P"],
           [], ["D31"], ["AW-EDDI", "AW-CPC", "D30"], ["AW-SMAPL4", "D32", "D52", "D25"], "周到季；闪旱按五日/日产品可用支持另定",
           ["USDM 有效日与发布日分开；专家分析是既有 P，不新增逐题人工评审。", "CPC 季节 outlook 只在匹配季节目标时作基线，其余作背景。", "SMAP L4 根区水分需完整序列、质量/冻土掩膜与基准；EDDI 不单独充当闪旱真值。"],
           "USDM 周图、EDDI 数组、CPC 矢量均真实可读；持续性/转移基线可设计，闪旱数值源受 401 阻塞。")
    hazard("H14", "低能见度与沙尘", "沙尘暴", ["站点沙尘暴", "浮尘/扬沙对照", "沙尘成分产品"],
           "固定站点未来窗口出现 DS/SS 等规定现象并满足能见度条件；气溶胶产品另列 P 扩展。", ["O"],
           ["D28", "D67"], ["AW-GHCNH", "AW-METAR", "AW-IEM"], ["AW-ABI"], ["AW-CAMS", "D35", "D36"], "1-24h",
           ["DS 与 BLDU、BR、HZ 不混同；只统计主站报，排除 RMK/vicinity。", "通用能见度预报不是沙尘专属概率；基线需现象分类/校准。", "高 AOD 不自动作地面沙尘暴 Gold。"],
           "Phoenix 实际 5 条 DS 和 10 条 BLDU 已补；CAMS 没有匿名数值样例，当前先走站点现象路线。")
    hazard("H15", "低能见度与沙尘", "浓雾/极端低能见度", ["雾现象", "低能见度", "海雾扩展"],
           "站点未来窗口能见度低于阈值；浓雾额外要求 FG/FZFG 与持续性。", ["O"],
           ["AW-TAF", "D28", "D67"], ["AW-METAR", "AW-GHCNH"], ["AW-ABI", "D27"], ["D53"], "1-24h；以 TAF 变化组及站报支持为准",
           ["TAF 与 METAR 同机场身份，FM/TEMPO/PROB 分组明确解释。", "10+SM 等区间值不变成精确值；站点缺报不能标无雾。", "低能见度成因与浓雾标签分开，海雾需对应海域观测合同。"],
           "三站真实 TAF/METAR 与小时归档已可解析；M4Fog 未得到 cube，不让其阻断站点主线。")
    hazard("H16", "干旱与火险", "天气相关野火/火险", ["火险指数", "已知火场活动产品扩展"],
           "已知火场未来固定观测窗活动火产品面积/像素变化 P；火险指数越阈单独定义。", ["P"],
           [], ["D19", "D23"], ["D28", "AW-GEFS", "AW-ABI"], ["D21", "AW-GWIS", "AW-EFFIS", "D20", "D24", "D65"], "数小时至数日；固定合格观测窗",
           ["热点先按冻结时空规则归并火场，气象驱动不等于起火原因证明。", "下一次合格观测必须限制在预定窗口内，超窗仍为未结算，不能根据结果任意延后。", "FWI、活动火、烧毁面积分开；无热点与无覆盖/云遮不能直接解释为扑灭。"],
           "真实火场日栅格和 FIRMS 热点可用；多火场正扩展样例仍缺，FWI 目前只有渲染图，没有已验证数值业务预报。")

    for h in hazards:
        ids = sum((h[k] for k in ("forecast_sources", "outcome_and_observation_sources", "auxiliary_or_benchmark_sources", "conditional_extension_sources")), [])
        if set(ids) - inventory.keys():
            raise ValueError("unknown source reference")
    dump("SOURCE_SAMPLE_INVENTORY.json", {
        "schema": "disastertrace.blueprint_sample_inventory.v1", "date": "2026-09-11",
        "not_an_independent_source_count": True, "formal_new_tasks": 0,
        "status_counts": dict(Counter(v["sample_status"] for v in inventory.values())),
        "sources": list(inventory.values()),
    })
    dump("HAZARD_SOURCE_MATRIX.json", {
        "schema": "disastertrace.hazard_blueprint.v2", "family_count": 16,
        "group_count": 6, "reference_kinds": {"O": "observation", "P": "analysis_or_derived_product", "R": "confirmed_report"},
        "legacy_A_alias": "P", "formal_new_tasks": 0, "hazards": hazards,
    })
    for filename, rows, columns in [
        ("SOURCE_SAMPLE_INVENTORY.csv", list(inventory.values()), ["source_id", "name", "selection", "sample_status", "sample_summary_cn", "limitation_cn", "evidence_refs", "urls"]),
        ("HAZARD_SOURCE_MATRIX.csv", hazards, ["hazard_id", "group", "name_cn", "fixed_future_target_cn", "outcome_kinds", "forecast_sources", "outcome_and_observation_sources", "auxiliary_or_benchmark_sources", "conditional_extension_sources", "time_scale_cn", "current_readiness_cn"]),
    ]:
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: "; ".join(row[key]) if isinstance(row[key], list) else row[key] for key in columns})
        (ROOT / filename).write_text(output.getvalue())
    lines = ["# 数据源逐项样例与选择清单", "", "本表包含继承的 74 项登记及本轮拆分/新增产品；条目数不是独立传感器或数据集数量。主方案只采用下表明确选定的角色。样例可解析与正式任务准入分开；本轮新正式任务为 0。", "", "本轮新样例的最终科学审计为 [NEW_SAMPLE_AUDIT_05.json](NEW_SAMPLE_AUDIT_05.json)。旧数据只重核哈希并复用原解析结论，见 [INHERITED_SAMPLE_AUDIT.json](INHERITED_SAMPLE_AUDIT.json) 和 [INHERITED_JOIN_BINDINGS.json](INHERITED_JOIN_BINDINGS.json)。", "", "| ID / 数据源 | 选择 / 样例状态 | 实际证据 | 使用限制 |", "| --- | --- | --- | --- |"]
    for s in inventory.values():
        ref = s["evidence_refs"][0] if s["evidence_refs"] else "INHERITED_SAMPLE_AUDIT.json"
        label = f'[{s["source_id"]} {s["name"]}]({ref})'
        lines.append("| " + " | ".join([cell(label), cell(s["selection"] + " / " + s["sample_status"]), cell(s["sample_summary_cn"]), cell(s["limitation_cn"])]) + " |")
    lines += ["", "原始获取 URL、逐回执路径、继承的原始证据指针在 JSON 中；CSV 便于筛选。HTTP 200 的文档、空响应和地图均不算完成科学数组验证。未选替代项继续保留其真实状态，不为了扩源数量重复下载。", ""]
    (ROOT / "SOURCE_SAMPLE_INVENTORY.md").write_text("\n".join(lines))
    lines = ["# 16 类灾害的完整数据合同", "", "覆盖整个 benchmark；每类包含子类、固定未来目标、结果身份、数据源、自然时间尺度与剩余门槛。所有 E/F/D 正式任务编译与准入均待完成。本表为设计，不是 16 类已完成的数据集声明。", "", "O = 观测；P = 分析/遥感/融合/专家产品；R = 规定体系的确认报告。旧蓝图 A 统一别名为 P。", ""]
    for h in hazards:
        lines += [f'## {h["hazard_id"]} {h["name_cn"]}', "", f'组别：{h["group"]}。子类：{"；".join(h["subtypes"])}。', "", f'**固定目标：** {h["fixed_future_target_cn"]}', "", f'**结果：** {" / ".join(h["outcome_kinds"])}。**时间尺度：** {h["time_scale_cn"]}。', "", "| 数据角色 | 选定来源 |", "| --- | --- |"]
        for key, label in [("forecast_sources", "可用专业预报来源候选"), ("outcome_and_observation_sources", "观测/结果"), ("auxiliary_or_benchmark_sources", "辅助证据/已有 benchmark"), ("conditional_extension_sources", "条件扩展/不计当前完成")]:
            names = [f'{ident} {inventory[ident]["name"]}' for ident in h[key]]
            lines.append(f'| {label} | {cell(names) if names else "无已准入专用业务预报；先用持续性/气候态/产品演化基线"} |')
        lines += ["", "**处理规则：**", ""] + ["- " + v for v in h["processing_rules_cn"]]
        lines += ["", "**目前证据与缺口：** " + h["current_readiness_cn"], "", "逐来源真实样例与回执见 [数据源清单](SOURCE_SAMPLE_INVENTORY.md)。", ""]
    (ROOT / "HAZARD_SOURCE_MATRIX.md").write_text("\n".join(lines))
    rows = list(captures.values())
    scientific = [r for r in audits.values() if r["level"] not in {"rendered_product_only", "decode_failed"}]
    summary = {
        "http_requests": len(rows), "response_payload_bytes": sum(r.get("bytes", 0) for r in rows),
        "request_status_counts": dict(Counter(r["status"] for r in rows)),
        "http_status_counts": dict(Counter(str(r.get("http_status", "no_response")) for r in rows)),
        "empty_http_200_responses": [r["id"] for r in rows if r.get("http_status") == 200 and r.get("bytes") == 0],
        "verified_ranges": sum(r.get("range_verified") is True for r in rows),
        "response_cap_sum_bytes": sum(r["max_bytes"] for r in rows),
        "scientific_audit_records": len(scientific), "rendered_map_audit_records": sum(r["level"] == "rendered_product_only" for r in audits.values()),
        "decode_failures_in_final_audit": [r["capture_id"] for r in audits.values() if r["level"] == "decode_failed"],
        "final_audit": AUDIT, "new_formal_tasks": 0, "new_model_calls": 0, "gpu_jobs": 0,
        "counting_note": "HTTP bytes include documentation, errors, partials and repeated transport attempts; assembled files are not counted twice. Scientific audit records are not dataset/event counts. SDK/parser installs excluded.",
    }
    dump("CAPTURE_SUMMARY.json", summary)
    print(json.dumps({"sources": len(inventory), "hazards": len(hazards), **summary}, ensure_ascii=False))


if __name__ == "__main__":
    main()
