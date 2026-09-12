# 候选数据实际取样与验证说明

日期：2026-09-12。当前用途：为 [导师讨论稿](../advisor_review_20260912/PROPOSAL_FOR_ADVISOR_CN.md) 提供实际数据证据。这里只证明指定样本、字段或入口达到记录中的验证程度，不能推定全部数据、完整历史时序或正式预测任务均已合格。

## 1. 当前结论

[逐项登记](CANDIDATE_REGISTRY_CN.md) 共 97 个来源/产品入口：75 项实际样本已解析，3 项目标内容不完整，6 项仅事件/派生目录，8 项尚无目标样本，4 项账号/许可流程未完成，1 项仅渲染产品。这不是 97 个独立数据集，也不是 75 类已建成任务。

登记 JSON 的快照时间为 2026-09-12 09:07:55 UTC。`decoded_content_entries=84` 包含 75 项样本、3 项部分内容和6项目录；不能把 84 当作完整数据集通过数。所有候选正式准入仍为 false，本批新增正式 benchmark 任务、模型调用和 GPU 作业均为零。

GEE 的 `disastertrace-gee` 项目已经通过真实认证和数值读取，见 [GEE_CHECK.json](gee_02/GEE_CHECK.json)。NASA/Copernicus 中已授权并解码的产品沿用最新授权证据，旧 401/403 或 GEE 未登录记录保留为历史失败。

## 2. 证据层次与文件

| 证据 | 文件 | 能证明什么 |
| --- | --- | --- |
| 来源、用途、失败与条件 | [CANDIDATE_REGISTRY.json](CANDIDATE_REGISTRY.json)、[CSV](CANDIDATE_REGISTRY.csv) | 97 项逐条判断，包含引用和哈希；该判断仍有任务准入条件 |
| 旧资产完整性 | [INHERITED_INTEGRITY.json](INHERITED_INTEGRITY.json) | 857 个文件、690,671,607 字节的既有哈希/大小核对通过；并非所有科学解析器重新运行 |
| 新解析记录 | [NEW_AUDIT_02.json](NEW_AUDIT_02.json) | 16 条实际数字/图像/配对/目录解析记录 |
| 扩展解析记录 | [EXTENDED_AUDIT_03.json](EXTENDED_AUDIT_03.json) | 23 条原生/GEE 数组、站点或矢量解析记录 |
| TCIR/WeatherQA 补充 | [SUPPLEMENTAL_AUDIT.json](SUPPLEMENTAL_AUDIT.json) | 2 条实际解析记录，保留前缀与配对的范围限制 |
| NEXRAD 环境补齐后复解码 | [NEXRAD_REDECODE_03.json](NEXRAD_REDECODE_03.json) | 12 sweep 及若干雷达矩实际可读；所有报文与科学 QC 未整体认证 |
| GEE 多集合样本 | `gee_collections_01/`、`gee_collections_02/`、`gee_collections_03/`、`gee_mtbs_boundaries_01/` | 指定产品真实像元/导出/矢量，不证明历史入库时间 |
| HTTP/ZIP 样本与失败 | `captures_01/` 至 `captures_11/`、`zip_*` | 实收字节和请求回执；文件前缀是否足以解析完整成员另行判断 |

三个新解析报告共 41 条记录，涉及 30 个来源 ID，均没有 `decode_failed`；它们是解析检查记录，不是 41 个独立实验或正式任务认证。完整报告保留数值、QA、缺测、网格与标签限制。

登记生成后的 `captures_11/` 还收到 CEMS 的 1,219,736 字节部分 ZIP 和 CrisisMMD 的 4,194,304 字节 TAR.GZ 前缀。这两项未完成科学内容解析，没有上调登记状态。网页成功、HTTP 200/206 或收到字节均不足以替代完整目标样本。

## 3. 对选择最有影响的发现

- **GEE 可用了。** 已有 GFD、Sentinel-1/2 等真实像元和 TIFF；部分初始集合查询、几何或波段请求失败后使用有界调整成功，失败记录均保留。直接 CHIRPS v3 样本可读，但此次 GEE v3 路径未找到。
- **原生多模态样本可读。** KuroSiwo、WorldFloods、SpaceNet8、Sen2Fire、WeatherQA、DAWN 等已有实际内容，分别仍有事件/标签/网格/质量限制。
- **NASA 产品有科学数组。** IMERG E/L、SMAP L3/L4、MODIS Snow/LST、MERRA-2 和 S5P 已取得相应数值；DAP4 解决了部分 DAP2 类型兼容问题，不代表所有空间窗都有效。
- **来源间不能替代验证。** GEE 与直接下载可能是不同处理级别或版本；CAMS AOD 不是地面沙尘暴，SMAP 不是骤旱标签，MODIS 雪盖不是冻雨，ERA5-Land 不是当时业务预报。
- **少量样本不保证有极端正例。** GFD/Sen2Fire 等样例为负，部分 S2 为云；SMAP 推荐质量位需要筛选。完整事件链需另行选取合格场景。
- **剩余缺口有明确角色。** 部分账号/许可、作者网盘原包、配对标签和数值产品尚未获得；它们可以保留候选，但当前不能作为主实验必要依赖。

## 4. 复现与边界

`fetch_samples.py`、`sample_zip.py`、`check_gee.py`、`sample_gee_collections.py` 记录了有界获取方法；审计脚本为 `audit_samples.py`、`audit_extended.py`、`audit_supplemental.py`，来源汇总由 `build_registry.py` 生成。不要为了读讨论稿重跑下载或覆盖历史输出。

部分科学解析依赖本地隔离环境和 `parser_libs/`；此目录不纳入 Git。报告记录的是实际使用的已安装环境，不宣称在任意全新机器上无依赖可运行。下载凭据和 GEE 私有认证配置不属于本包。

本次导师稿的离线核验脚本为 [verify_review.py](../advisor_review_20260912/verify_review.py)：它复核状态计数、来源 ID、本文及讨论稿的本地引用、41 条新解析所绑定的实际文件哈希，以及记录中的 GEE 成功状态。它不重新请求服务或认证科学定义，不修改既有样本。

真正的数据选择需要回到完整任务：同一目标的专业预报、截止前资料、来源关系和未来结果是否匹配，以及能否构造公平的 N1—N3 对照。具体建议见 [候选处理明细](../advisor_review_20260912/CANDIDATE_SELECTION_CN.md)。
