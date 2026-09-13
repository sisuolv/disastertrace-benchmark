# DisasterTrace v7：基于开源 benchmark 与最新论文的定向优化

**基准提交：** `98f28a9a9f33c28ec2b0236c4aaf47a9173c813e`。本轮重新确认分支未变化。
**用途：** 对上一版 Q0–Q6 追加具体改动、来源与放行条件；不提出 v8，不重写 monitoring_v1。
**范围：** 文献/官方说明/定向源码核查和实施设计。没有下载新的科学数组、运行仓库测试、运行上游代码或提交模型/GPU作业。

## 1. 保持不变的研究目标

C1：共享资源与持续更新的共同基线下，选择性获取和预测修订是否值得。
C2：把可见事实支持、联合可达性、原生感知、预测融合与实际未来损失分开解释。
C3：六组十六类灾害分合同建设，独立过程验证、确定性结果、真实多模态和可复现在线/回放。

不新增逐题人工Gold，不用LLM judge决定主参考。已有人工标注和专家产品可以使用但需保留参考身份。现实应急动作不在本轮范围。所有旧概率、调用、失败和负收益原样保留；分析更充分不意味着旧实验证明了新结论。

## 2. 当前结果给出的优先级

已发布：monitoring_v1、109项实现/分析测试记录、33,944次调用，真实区域日历和图像处理记录。上述数字来自冻结报告，本轮未重跑。

当前最需要解释的并非缺少输出，而是：

1. TAF概率是此前湾区样本拟合的研究映射，并迁移到Front；2026区分能力弱，低Brier不能当强识别能力。
2. 实际紧约束是调用次数；selector占约一半调用，token和计算配额大量剩余。
3. E是较早的登记邻站报告存在性，不是所有最新信息，也不是未来可预测性。
4. 原生图已接入小型未来评分，但72调用对应18共同机会×4固定表示条件，零正例，未测主动视觉选择。
5. 旧报告重放支持原轨迹复现，不代表可以无条件评估所有未访问的替代资料或未生成的模型预测。

因此新增工作优先级为：**强基线与合法信息 → 可识别的动作/融合对照 → 真实视觉选择 → 跨过程与有限前瞻**。

## 3. 最重要的新来源：LAMP/GLMP专业基线候选

NOAA LAMP/GLMP提供滚动航空天气指导。官方产品列表包含能见度原生概率。它值得优先核验，因为当前TAF频率映射不应成为唯一专业对照。[R12]

### 3.1 绝不能静默改变既有目标

- 现有 `<1000m` 任务与 `<1 statute mile` 不同；1 statute mile精确等于1609.344m。
- 保留旧 `<1000m` 研究映射轨。若采用LAMP原生阈值，新增明确命名的子轨，预先登记，并重新生成对应结果。
- 某些产品给一个15分钟内最低能见度类别，不能对齐到任意单个routine METAR然后声称窗口完全一致。
- 网格点预报不自动等于机场站点测量。站点/网格映射、分辨率和预测对象需要记录。
- 原生概率的单位可能为百分数；字段、比例、比较符号必须从官方合同固定。

### 3.2 历史版本是首个准入门槛

官方变更记录显示，v2.6于2024-09-30加入15分钟最低类别产品；v2.7于2025-09-16加入/调整部分起止与概率文本产品。因此不能把新格式定义、发布时间或产品能力填到2024年1月旧开发任务中。[R12]

下一步按“官方说明 → 实际目录 → 固定版本小样例 → 解码 → 目标/参考配对”执行。找不到相应历史版本时，保持旧R轨并将新产品留作有界前瞻候选。不要把一个循环中的latest链接当作历史档案。

### 3.3 可执行访问模板（不是已下载文件）

官方入口：
`https://vlab.noaa.gov/web/mdl/lamp-nws-webservices`

```text
# YYYYMMDD 与 HH 必须从当日真实目录解析；下面均为模板
https://nomads.ncep.noaa.gov/pub/data/nccf/com/lmp/prod/lmp.YYYYMMDD/lmp.tHH30z.lavtxt.ascii
https://nomads.ncep.noaa.gov/pub/data/nccf/com/lmp/prod/lmp.YYYYMMDD/lmp.tHH30z.bufrmsg.xtrn.bufr
https://nomads.ncep.noaa.gov/pub/data/nccf/com/glmp/prod/glmp.YYYYMMDD/glmp.tHH30z.fcsts_visp2.g.co.grib2
https://nomads.ncep.noaa.gov/pub/data/nccf/com/glmp/prod/glmp.YYYYMMDD/glmp.tHH30z.fcsts_visp4.g.co.grib2
https://nomads.ncep.noaa.gov/pub/data/nccf/com/glmp/prod/glmp.YYYYMMDD/glmp.tHH30z.fcsts_visp5.g.co.grib2
```

`visp2`为低于1英里，`visp4`为低于3英里，`visp5`为不超过5英里。文件格式、实际有效窗和网格仍以取得的产品及对应版本说明核验，不仅根据文件名判断。

LAMP也有一小时雷电概率候选，但不能由此宣布H06的GLM flash-density阈值已经有同目标P基线；“是否发生”与“探测密度”仍是两种目标。

## 4. 改进研究映射，而不是等待全部专业概率到齐

当前 `monitoring_v1/calibration.py` 对TAF摘要类别、时距和少量邻站计数建立频率单元，稀疏时回退到较粗单元。这可复现，但高频回退可能压低区分能力，不能因为用了完整TAF文本就说数值映射也保留全部信息。

借鉴2026-09-07的空间后处理研究，将同地区未来月份、未见站点、跨地区迁移分别定义。该论文实验对象是德国温度和风，不把结论外推为机场雾的已证实规律。[R03]

首批不需要深度图模型。实现廉价且公平的对照即可：

- 旧频率映射原样保留；报告cell样本量、命中/回退率、概率直方图。
- 较充分历史上的正则化二分类映射，或预定义区域/站点层级收缩；只用可合法取得的TAF/背景特征。
- 同地区拟合与跨地区迁移使用不同试验ID；同一评测集不承担参数选择和确认。
- 完整TAF条件段、发布时间和目标窗独立审计；TEMPO不能固定为0.5。
- 如果目标附近无法取得足够历史正例，显式标数据不足，不用当前确认标签“修”概率。

基线变更后的输入集合要重新冻结。新增官方概率若已融合相同观测，仍允许研究原图/原观测的增量，但不能假设它们条件独立或预设一定有新价值。

## 5. 核心实现：selector / perceptor / predictor / gate分离

AFABench明确区分共享外部预测器与方法内部预测器；其代码提供act/predict接口，并为特权诊断保留label参数。正式DisasterTrace适配器必须禁止label进入策略。[R01]

建议保留运行内核，使用小型接口包装：

```text
selector(public_snapshot, budget) -> lawful action plan
perceptor(authorized_assets, representation_config) -> typed evidence view
predictor(common_baseline, evidence_view, missing_mask, age) -> proposal
revision_gate(proposal, current_state, baseline_version) -> FOLLOW/OVERRIDE/NO_CHANGE
```

不能给所有方法默认使用正确的E答案；可执行产品解析属于声明过的工具轨，原图感知仍是被测能力。对同一个实验固定predictor，对下一组实验再固定evidence/policy改变predictor。

### 5.1 最小矩阵

A：相同预测器、相同端到端预算，比较固定/批量/规则/模型selector。
B：固定实际证据包，比原文/合法结构化表示/原生图；有特权的提取另列。
C：固定证据和表示，比直接概率输出、简单条件融合、可复现的LEAP式候选。
D：固定已实际产生的候选提交，比FOLLOW、预声明门控和两种wrapper；不对未调用目标编造候选。

这些因素有交互，不能把所有差值相加成唯一因果贡献百分比。

### 5.2 LEAP具体可借用到哪里

已读到的公开仓库当前包含trace归一化和SKILL，要求另行安装`AGENTFUTURE_FINALIZER_BIN`。它不是本轮已经确认可一键复现的完整概率算法。先借“证据冻结/哈希锁定/禁止追加检索”的设计，后端无法核实就保留为待复现项。[R02]

对同一证据包比较两个finalizer时，必须共享`evidence_bundle_hash`；记录是否使用额外特征/图片，冻结后不得重新搜索。

LEAP论文的连续量分支还包含按先验标准差过滤异常的规则。极端天气不能直接继承“偏离先验很远就删除”：真实极端本来可能罕见。应先核验单位、缺失码、传感器QC和有科学依据的物理范围，不能以统计罕见性删除关键事件，也不能套用结果侧阈值筛输入。[R02]

LLM估计的likelihood/可靠性不是Gold。业务基线与某些观测共享信息时，不应直接把它们当独立likelihood相乘。同源文字、图表和产品也不能重复累计。可优先用训练/开发期固定的条件残差模型进行融合；没有新数学或学习结果就不宣称发明新贝叶斯算法。

## 6. E可判定之外，补一个有界动作价值试验

当前支持规则和联合参照保留不动。新实验回答：**在一个固定预测器下，一次合法查询到底改变了多少未来损失？**

固定同一前缀、同一目标、同一共同基线，预先规定一小组合法动作。获取真实响应后计算：

```text
d_i(a) = loss(f(b_i, E_i), y_i) - loss(f(b_i, E_i ∪ result_i(a)), y_i)
```

这是已测试系统的事后经验损失差，既不是信息论VOI，也不是可以事先知道的最优动作。允许d为负。对固定小开发池比较一阶动作和少量有真实地理依赖的两步路径，记录置信区间和费用；不要一上来做全部组合或训练RL。

需要三种界限：

1. E证书说明公开合同内哪些事实可断言；E不充分不强制F=0.5。
2. 联合E可达性说明共享资源下哪些事实可以同时补齐，不代表最大F收益。
3. 事后F最佳已测动作只是诊断；不能用来选择最终测试样本，也不能当可部署策略。

在开发阶段可以据此拟合廉价的预期收益/费用排序器，但其输入只能是当时公开元数据、已获事实和基线。标签及事后路径只能留在训练/评价侧。拟合这个小模型不等于要求训练LLM或新全球天气模型。

### 6.1 可用日志不等于可评估任意新策略

时间变化的主动获取研究明确提醒，获取政策改变会改变观察到的数据分布。[R04]

为每个预登记session建立独立有界候选归档；策略通过时间/授权/预算代理获取。只记录原Agent查过的资料，不足以重放另一个Agent的所有查询。未归档的响应标为不可评估；用LLM生成一个看似合理的雷达返回是禁止的。

旧输出可以重算wrapper、成本和评分，不能代替新输入条件下的新模型调用。不能在没有支持性和明确假设时，对确定性少量轨迹直接套用离线策略评估并声称无偏。

## 7. 成本优化：减轻无意义的每步大模型规划，而不是给Agent免费预算

现有结果表明调用数约束起主导作用。新冻结保留三种命名：

| 轨 | 固定条件 | 解释 |
|---|---|---|
| End-to-end | 总调用/token/compute等真实或声明费用相同 | 部署系统价值，selector全部收费 |
| Acquisition diagnostic | 预测器与预测机会固定，单独记录额外选源开销 | 辨别选源质量，不冒充等总成本主榜 |
| Cost frontier | 多个实测合理预算，含资源宽裕点 | 判断结论是否依赖硬调用上限 |

可增加公开事件触发或短计划：一次selector输出多个目标/查询的有界计划，在基线相关版本变化、计划到期或合法新证据到达时才重规划。规则和LLM均有同等批处理、缓存与计划权限；每次计算仍收费。

不同目标推理是否联合仍属于X09独立因素。即使一次选择多个查询，也不默认让联合预测器更强。新策略先是轻量对照，不能在看到确认集收益以后不断改调度器。

## 8. 让多模态从固定供图进入真实选择

### 8.1 增加明确但有限的动作空间

```text
READ_REPORT(product_revision)
READ_REGION_OVERVIEW(asset_revision)
READ_REGISTERED_ROI(asset_revision, roi_id, resolution)
READ_TEMPORAL_WINDOW(asset_ids)
READ_DOMAIN_PRODUCT(product_revision)
WAIT_UNTIL(public_time) / STOP（按当前协议逐步放开）
```

同一资产放大或换图是表示/处理变化，不是新物理观测；新的拍摄时刻才是新观测。一次下载可共享，额外ROI、解码、视觉token和模型调用照计。ROI从预登记站点/水网/合法已知目标确定，不使用未来事件中心或标签去找热点。

### 8.2 GOES FLS的正确位置

GOES Fog and Low Stratus可作为强领域产品对照：其IFR/LIFR等定义包含能见度**或**云底高，且主要描述当前条件。因此：

- 不是未来纯能见度<1000m的结果；
- 不是地面雾的无误差mask；
- 不能忽略它与原ABI和数值模式的共享上游；
- 可以按实际发行时间作为工具增强证据或相匹配现状产品任务。

官方说明给出日夜预测变量不同、厚度产品适用云层有限等约束；主图文任务应保留日夜、上层云遮挡、覆盖和质量分层。[R13]

先核验官方产品样例和历史版本，不让FLS缺口阻塞原生ABI机制试验。图像辅助要允许失败，不能先假设VLM一定优于领域产品。

### 8.3 至少四个可解释条件

1. 完整合法文字/数值，含强专业基线；
2. 同基线+策略可选择的原生图像或真实时序；
3. 同基线+合法领域产品/同源计算特征，计算与来源明确；
4. 特权视觉事实诊断，只有能确认信息匹配时才称纯表示对照。

新的集合应按预登记过程构建，保留正例、近阈值、无事件、缺测与表示困难。自然监测队列不能按未来正例筛；另设富集机制子集并明确不代表自然发生率。

## 9. 第二灾种：保持H08主迁移，H07可作多模态领域控制

H08最接近已有数据基础，先复用连续HEFS流量→USGS合同；水位越阈另验datum、epoch、历史阈值和预报版本。当前水位阈值不能套给cfs/kcfs，不用当下跨接口一致证明历史一致。[R05及现有Q5]

若已有雷达QPE得到准确时窗、单位、投影和QC，H07可以用pysteps的持续/平流/集合短临对照，验证图像中的时空信息是否能被专业方法利用。[R11]

这不是新增全球天气模型研发。SEVIR VIL不能未经科学映射当毫米降雨；弱标签或未知雨强不能拿来跑pysteps后生成伪Gold。领域模型预测也不是参考真值。

两条路线并行按真实数据门槛推进，哪一条先形成第二物理过程的合格多模态链由证据决定。16类仍保持原合同，不能因为引入新库就在资格表打勾。

## 10. 指标：技能、稳定性、成本与机制分开

保留Brier/数值误差、AP/ROC、可靠性、G+/G-、全机会分母、改写率、失败和迟交。罕见事件不能仅凭低Brier说识别好，也不能为提升召回而事后选阈值。

用`scores`建立独立的度量交叉核验，而不是立即替换已有评分器。Flip-Flop Index可以作为同一固定目标的修订稳定性诊断；它本身不用真实结果，稳定不等于正确，不变常数可能非常稳定。[R10]

```python
# 引用官方接口名称；本轮未安装或运行该库
from scores.continuous import flip_flop_index
```

分别统计模型proposal序列与协议最终生效序列，以免把自动FOLLOW/回退当模型稳定性。相同目标、相同机会网格和缺失政策下比较；不跨单位直接求均值。

## 11. 在线：保留实证目标，不把观察器当在线预测

可复用FutureSim/ForecastBench的提前登记、滚动提交和延迟结果思路；它们已有持续预测能力，不能单独主张首次online。[R08/R14]

本项目必须绑定气象特有的时间与质量：provider发行→本地捕获→处理→模型看到→提交→结果成熟。真实模型回复持久化时间须早于cutoff。空档案、删失观测、临时结果、最终结果分开。

候选采集器与策略访问费用分账。前瞻不是对历史网络延迟的模拟，也不能把实时观察器记录反填旧样例。普通报告能依法进入后续任务，私有奖励/成熟Gold不自动反馈给模型。

在线范围有限且预登记，留足结果尾窗；本计划不授权启动常驻服务或承诺后台长期工作。使用已有授权时仍要确认其窗口/资源范围是否覆盖新运行。

## 12. 对Q0–Q6的修改和最小执行顺序

| 工作包 | 本轮新增重点 | 首个出口 |
|---|---|---|
| Q0 | 已有日志漏斗、proposal与effective状态、scores独立核验与稳定性 | 无新模型调用即可解释哪里没有形成修改 |
| Q1 | LAMP版本与原生阈值候选；当地/迁移校准分离 | 一条语义完整基线或明确blocked，不改旧任务 |
| Q2 | 有界动作探针、真实候选归档、E与F价值分开 | 输入与结果可复算且无oracle/未来泄漏 |
| Q3 | AFABench式固定预测器，LEAP式证据锁定；多种成本口径 | 不混获取/融合/门控收益，缺后端不虚构复现 |
| Q4 | 多过程主动图片和领域产品对照 | 真图可选择，原生/工具/特权轨明确 |
| Q5 | H08迁移；有条件H07+pysteps | 第二过程先CPU闭环，未来目标与参考真实匹配 |
| Q6 | 新过程确认与有限前瞻模型结算 | 全机会、公平成本、真实提前提交和结果尾窗 |

建议首先做Q0；并行开始Q1的文档/小样例审计和Q2的数据设计。不等待LAMP/FLS所有门槛完成才优化R轨。Q3先小模型/程序，Q4只在配对与数据质量过关后执行。未经可识别性检查，不重复上轮整套33k调用矩阵。

确认阶段仍需独立父天气过程/保守时空块、purge、固定主要比较、多重比较政策和采样范围。旧三个日历与96个E案例是已暴露开发材料，不通过换一个图例或映射重命名为确认集。

## 13. 保留的最终定位与失败判据

**DisasterTrace在持续更新的专业基线和共享预算下，测量智能体如何获取、理解和使用多模态证据来选择性修订固定未来风险，并用可执行支持参照、配对信息实验与真实结果识别增益或失效发生在哪个环节。**

这不是对“首次”或发表结果的保证。只有在强专业/程序对照、真实时间与独立过程中建立结果，才能兑现C1/C2/C3。

- LAMP或强融合已经足够：保留其优势，不人为弱化基线。
- 图像无法提供可利用信息：先检查传感器/目标适用性，不靠模态名称宣称价值。
- E变充分但F不变：如实记录，不强行将E充分性升级为预测最优。
- 选择代价大于收益：允许停止或批量程序获胜。
- 所有差异来自当前数据/解析错误：先修通用规则并新冻结，再做研究解释。
- 新方法仅在开发集有效：保留范围，不能扩推16类。

## 14. Codex首轮启动指令

```text
保持v7、C1/C2/C3、Q0–Q6和monitoring_v1，不提出新框架。
先读本文件、Q0_Q6_AMENDMENTS.json和REFERENCE_AND_REUSE_REGISTER.json，
再检查实际HEAD、适用AGENTS.md、未提交修改、旧冻结结果和现有授权范围。

先交付Q0的已有日志分析；并行做Q1/Q2的离线合同和限定元数据核验。
新增LAMP/FLS先以candidate登记，实际文件/版本/目标未验不要标admitted。
当前<1000m保留；新原生阈值独立建轨，不能修改旧结果。
保留所有负收益和失败。不调用LLM生成Gold，不新增逐题人工标签。
不要仅再返回计划：交付代码/数据清单/真实检查输出/阻塞原因。
本轮实施由用户另行明确范围，本文本身不启动模型、GPU、大下载、常驻服务或git push。
```

## 15. 证据与访问边界

本轮确认了用户分支，读取现有概率映射源码、AFABench Protocol、EWB inputs.py和LEAP实际适配说明；并定向阅读论文、官方API及产品文档。上游代码未执行，科学样例未下载，各来源可用性尚需用户环境的有限实测。

一部分NOAA VLab说明通过官方页面的搜索索引读取，直接打开存在失败；因此这里是产品说明核验，不是端点连通、授权、历史完整性或科学文件解码证明。

本交付包只检查自身JSON、依赖、引用ID和哈希，没有重新执行109项测试或新模型实验。引用注册表记录阅读范围与未复现限制。工作包拟产生的输出文件当前不存在，名称是实施目标。

## 16. 官方与作者入口

### R01 — AFABench

- `paper`: https://arxiv.org/html/2508.14734v3
- `repository`: https://github.com/Linusaronsson/AFA-Benchmark
- 已读源码：`afabench/core/types.py`；文件blob：`8245bf49c8e41f358dfcce5a35a713c40dffeecf`。这不是整个仓库commit锁。
- 核查范围：论文固定/内部预测器比较；核心 Protocol 定向阅读。
- 用途：act/predict 分离、固定预测器与共同预算；图片/变量组的合法动作映射。
- 限制：不照搬 i.i.d. 随机切分、均匀特征费用；正式 adapter 不得传 label；本轮未执行上游框架。

### R02 — LEAP

- `paper`: https://arxiv.org/html/2609.01337v1
- `repository`: https://github.com/layingfish/LEAP
- 已读源码：`SKILL.md`；文件blob：`a3dc453b89f0c4f1c7c2023d9dec90a2c0d50687`。这不是整个仓库commit锁。
- 核查范围：论文相关章节、README、SKILL、scripts 列表。
- 用途：冻结证据 snapshot、哈希绑定、相同证据上的融合对照。
- 限制：当前公开适配器要求另装 AGENTFUTURE_FINALIZER_BIN；未确认全算法可独立复现；LLM likelihood 不是真值；依赖来源不能独立相乘。

### R03 — Statistical versus machine learning-based spatial interpolation of post-processed ensemble weather forecasts

- `paper`: https://arxiv.org/html/2609.07512v1
- 核查范围：摘要、数据、方法与讨论定向阅读。
- 用途：把同地区时间迁移、未见站点/跨地区迁移分开；局地/区域/半局地后处理对照。
- 限制：原实验为德国 ECMWF 温度/风；不将其结果直接外推到低能见度，也未复现作者模型。

### R04 — Evaluation of Active Feature Acquisition Methods for Time-varying Feature Settings

- `paper`: https://www.jmlr.org/beta/papers/v26/23-1635.html
- `supplementary_html`: https://arxiv.org/html/2312.01530v3
- 核查范围：JMLR 最终摘要及较早公开正文相关论述。
- 用途：策略改变会改变已观测数据；独立候选归档、支持条件和离线策略评估边界。
- 限制：不假定当前确定性日志满足 positivity 或无混杂；没有真实替代响应不得编造重放；不强制实现离线策略估计器。

### R05 — ExtremeWeatherBench

- `paper`: https://arxiv.org/abs/2605.01126
- `repository`: https://github.com/brightbandtech/ExtremeWeatherBench
- `documentation`: https://extremeweatherbench.readthedocs.io/en/latest/data/
- 已读源码：`src/extremeweatherbench/inputs.py`；文件blob：`968861779e548b80545e61ed1bf2cc63d2d5d4bc`。这不是整个仓库commit锁。
- 核查范围：数据文档和 inputs.py 开头、变量映射、固定云端入口。
- 用途：forecast/target 适配器、init/lead/valid 时间、变量及机构级映射、惰性读取。
- 限制：固定 2020–2024 站点文件不是 live；不得 inner-join 删除失败；本轮未运行该库。

### R06 — EarthVerse

- `paper`: https://arxiv.org/html/2608.23525v1
- 核查范围：正文任务/评分/干预相关章节。
- 用途：可执行事实与空间子任务、证据定位和过程瓶颈诊断。
- 限制：其证据地图与缺失干预已经存在；只借确定性部分，不引入逐题新增人工或主观 judge。

### R07 — SIREN

- `paper`: https://arxiv.org/html/2607.24588v1
- 核查范围：公开正文任务、工具、局限相关章节。
- 用途：跨预警环节的领域工具基线与流程覆盖。
- 限制：不能以端到端预警首次性作为贡献；本轮未核验可独立运行的完整公开实现。

### R08 — FutureSim

- `paper`: https://arxiv.org/html/2605.15188v1
- `repository`: https://github.com/OpenForecaster/futuresim
- 核查范围：公开正文连续预测、按日期可见信息和恢复思路；未复跑整个仓库。
- 用途：滚动预测、冻结历史、动作恢复、研究与提交分离。
- 限制：它已有多问题选择和更新；日期门控不替代气象产品细粒度发行时间；主分不引入文字匹配 judge。

### R09 — RealBench

- `paper`: https://arxiv.org/html/2605.24945v1
- 核查范围：公开正文数据/业务条件相关内容。
- 用途：区分业务低延迟输入与回顾分析；真实参考与成熟度。
- 限制：历史年份不能保证 LLM 无预训练污染；不是直接可替换本站任务的配置。

### R10 — scores

- `documentation`: https://scores.readthedocs.io/en/stable/
- `brier`: https://scores.readthedocs.io/en/stable/tutorials/Brier_Score.html
- `flip_flop`: https://scores.readthedocs.io/en/stable/tutorials/Flip_Flop_Index.html
- 核查范围：官方 API/tutorial 页面。
- 用途：独立评分实现交叉核对；flip_flop_index 用于固定目标的修订稳定性诊断。
- 限制：稳定性不用结果标签，不代表预测技能；不得奖励不变常数；先锁版本并检验缺失和权重策略。

### R11 — pysteps

- `documentation`: https://pysteps.readthedocs.io/en/latest/
- `deterministic`: https://pysteps.readthedocs.io/en/latest/generated/pysteps.nowcasts.extrapolation.forecast.html
- `ensemble`: https://pysteps.readthedocs.io/en/latest/generated/pysteps.nowcasts.steps.forecast.html
- 核查范围：官方接口说明。
- 用途：H07 雷达降水持续/平流/集合短临领域对照。
- 限制：必须用有单位/质量/时间间隔的雨率或累计输入；SEVIR VIL 不能当 mm；不保证适用其他灾害。

### R12 — NOAA LAMP / GLMP

- `documentation`: https://vlab.noaa.gov/web/mdl/lamp
- `download_documentation`: https://vlab.noaa.gov/web/mdl/lamp-nws-webservices
- `change_log`: https://vlab.noaa.gov/web/mdl/lamp-change-log
- `data_availability`: https://vlab.noaa.gov/web/mdl/lamp-data-availability
- 核查范围：官方页面的索引文本/检索内容；若干直接页面访问失败；未取科学文件。
- 用途：增加业务能见度原生概率/类别基线候选；站点与网格分开准入。
- 限制：1 statute mile = 1609.344 m，不等于1000m；15min最差类别与routine槽位不同；历史版本/档案待验；2024-09-30后v2.6、2025-09-16后v2.7不能反填2024年1月。

### R13 — GOES Fog and Low Stratus

- `documentation`: https://vlab.noaa.gov/web/towr-s/goes-16-fog-and-low-stratus
- `archive_catalog`: https://www.ncei.noaa.gov/metadata/geoportal/rest/metadata/item/gov.noaa.ncdc%3AC01572/html
- `archive_search`: https://www.class.noaa.gov/search/GRABINDE
- 核查范围：官方产品说明/目录；未取原生文件。
- 用途：原生ABI之外的合法工具增强/现状概率产品对照。
- 限制：MVFR/IFR/LIFR涉及能见度或云底高，不是单独未来<1000m或地面雾真值；与ABI及模型背景共享上游；日夜算法有差别。

### R14 — ForecastBench

- `paper`: https://arxiv.org/html/2409.19839v2
- 核查范围：公开正文动态问题与结果评价相关内容。
- 用途：结果未知时登记预测与延迟结算的设计。
- 限制：online本身不是首创；天气的原生窗口/QC/删失仍由本项目定义。

### R15 — Satpy / Py-ART

- `satpy`: https://satpy.readthedocs.io/en/stable/
- `pyart`: https://arm-doe.github.io/pyart/
- 核查范围：此前实现计划中的已有工具路线，本轮不声称重新审计全部代码。
- 用途：复用解码、校准、重投影和雷达绘图，尽量不自己写原始格式读取器。
- 限制：读取/渲染不是地面真值；锁依赖、变换和实际模型图像；不复制未经验证的默认设置。

