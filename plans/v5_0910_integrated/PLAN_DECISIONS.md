# V5 整合取舍与待核对事项

日期：2026-09-10。这里记录规划建议；不覆盖历史 `DECISIONS.md` 或任何接受记录。

## 已确定的规划假设

用户确认没有硬投稿/交付截止，按首周 instrument、两周 pilot、约 12 周目标路线推进。既有最多四张 H100 授权继续有效；本轮任务是规划，新增模型/GPU/气象数据采集次数为零。

不新增逐题人工 Gold 或 LLM judge。可以复用已发布标签，保留其人工/算法/机构来源；来源规则与许可核查是工程准备，不能误称逐题人工标注。数据/模型错误保留，旧运行凭据与档案保持冻结。

## 关键取舍

| ID | 取舍 | 原因与依据 |
| --- | --- | --- |
| D01 | 采用 P58 的 Catalog/Broad/Trace，Active 和 Prospective 为交叉子集/模式 | 避免把互相重叠的数据产品加成更大样本量 |
| D02 | 用 P59 的分层分类骨架并保留全部原标签 | 22、34、17 等数字来自不同粒度；不做强行一对一映射 |
| D03 | P/C/R/F/A 资格逐样本判断，不设严格阶梯 | 静态标签、后续帧预测和自然版本修订的前提不同 |
| D04 | 采用 P45 的 goal/visible/sufficiency 三参考，另配 outcome | 防止对证据不足的正确认识与主动不作为混为同一种成功 |
| D05 | MM-5A 保留为 80 调用的测量支路 | 延续 MM-4 证据；它不再阻塞所有其他灾种接入 |
| D06 | 新阶段不设某个 VLM 必须全对的数据门槛 | 程序可解性、公共可见性与参考可信度才是数据准入条件；旧 MM-4 门槛仍失败 |
| D07 | 唯一新内核建议命名 active_forecast，provider 纳入其中 | 三套附件模块名表达重叠职责；减少重复 runner/scorer |
| D08 | 首轮只做六家族，后续分源族扩展 | 58/59 个目录条目不等于同样数量的简单采集器 |
| D09 | 自然队列和平衡诊断分开 | 概率、校准和预警精确率受发生率影响，平衡采样不代表自然发生率 |
| D10 | 有限主动读取先行，WAIT/研究决策后加 | 先建立可穷举的充分性与成本参考，再增加时间策略的复杂性 |
| D11 | NHC 固定未来目标先验证，水文和海浪另配观测 | 最佳路径、预报、站点水位和波高不能跨目标互换 |
| D12 | 不直接采用任何附件的大型全因子矩阵 | 初期先回答表示、读取、修订、取证四个问题；规划调用总上限为 1568 |
| D13 | 12 周是目标，允许 16–24 周单人完成 | 数据准入与前瞻发生率不受 GPU 吞吐完全控制 |
| D14 | 本轮不重新联网宣布来源可用、不以附件验证报告代替工程验收 | 原件可追溯与新环境实测是不同证据 |

## 第一批来源身份对照

下表是定位原记录的线索。逗号分隔的是同一“来源族/产品主题”的候选，不代表它们已经被判定为同一 release。完整 257 条记录见 [SOURCE_CANDIDATES.json](SOURCE_CANDIDATES.json)。

| 主题 | 原计划记录 | 实施时的身份处理 |
| --- | --- | --- |
| NHC | master43:nhc_operational; complete45:nhc; master52:D12; master58:DS06; master59:E05 | 拆分公告、GIS、HURDAT2 角色，锁具体产品与 release；不按 NHC 域名一并合并 |
| SEVIR | master43:sevir; complete45:sevir; master52:D13; master58:DS10; master59:D01 | 同源族候选；按 catalog release、split、实际样本 ID 确认重合 |
| GEOID-Flood | master58:DS15; master59:D10 | 检查图像、掩膜、时序和数据/代码许可，避免仅有文章即算接入 |
| GHCN-Daily | master43:ghcnd; complete45:ghcnd; master52:D26; master58:DS26; master59:O01 | 站点、日界、flags、文件版本匹配；重发的 QC 版本独立保留 |
| ISD/Global Hourly | master43:isd; master52:D27; master58:DS27 | 与 GHCNh 关联时需核查迁移/合并关系，不自动判完全相同 |
| GHCN-Hourly | complete45:ghcnh; master59:O02 | 接口、字段、历史时间质量与 ISD 的关系待核 |
| FIRMS | master43:firms; complete45:firms; master52:D25; master58:DS36; master59:O11 | MODIS/VIIRS、平台与近实时/标准产品分别标识；接口不是独立传感器 |
| FPA-FOD | master43:fpa_fod6; complete45:fpafod; master52:D22; master58:DS07; master59:D12 | P45 声称第七版，其他多为第六版；锁版本后再比较重复记录 |
| USDM | master43:usdm; complete45:usdm; master52:D32; master58:DS37; master59:O16 | 按发布期/有效期锁产品，普通周际变化与修订分别标记 |
| USGS | master43:usgs_water_nims; complete45:usgs_water; master59:O12; P58 附加 DEP01 | P43 组合接口需要拆分，P58 DEP01 不计入原 58；stage/flow 与站点 datum 另核 |
| NDBC | master59:O28; P58 附加 DEP02 | P58 的附加依赖不是第 59/60 个原记录；站点/变量与产品窗口需实测 |
| NWS | complete45:nws_api; master58:DS49; master59:E06 | alert/forecast 各产品与更新时间、可用性和分页行为分别核对 |

## 需要核对的外部事实

| 事项 | 本轮已知程度 | 工单如何处理 |
| --- | --- | --- |
| FPA-FOD 6/7、GESLA 3/4 | 输入方案不一致，本轮未验证最新发行 | V5-01 保存官方 release 证据，按版本和使用条件选择；已有历史资产不替换 |
| IMERG V07/V8 和不同入口的实时/最终产品 | 计划中有版本/可用范围变化提醒 | V5-01/V5-13 查实际 catalog 和最小响应，不把 GEE 状态泛化到所有入口 |
| CHIRPS 2/3、Daily SAT/其他版本 | 输入记录可能不同产品 | V5-01 锁实际文件、变量、版本和时间覆盖 |
| NWS/NWPS/HEFS/FIRMS 短保留窗口 | 来自附件文档核查，不是本轮实测 | V5-13 重新核对，再确定频率、过期策略和绝对截止 |
| Digital Typhoon 中心裁剪先验 | 对在线定位任务有实质影响 | V5-21 按实际产品生成流程判定，必要时只保留中心已知条件 |
| 中国数据、EM-DAT、GEE 权限 | 不预设当前账户已具备 | V5-01 仅对需要的来源验证；其他开放源照常进行 |
| 第二个 VLM revision/许可/显存 | 候选方向已推荐，未接入 | V5-24 先核验与 generation-disabled preflight，冻结后才正式生成 |
| 近期近邻论文的真正重叠 | P45 给出论文名及入口，未在本轮重读全文 | V5-23 建逐维度的原文证据表，不提前宣称独创性 |

这些核查是下一阶段可以执行的工作，不是要求用户替我们回答产品技术细节。只有实际缺少账户、预算或研究范围偏好时，才针对具体缺口提问。

## 交付口径

新计划文件、原件副本、输入哈希、候选记录、工单和资源草案已形成；新内核、真实六家族集、MM-5A 和主动环境仍待实施。规划验证只验证文件与算术/依赖的一致性，不作为模型成绩、来源在线性或科学有效性证明。
