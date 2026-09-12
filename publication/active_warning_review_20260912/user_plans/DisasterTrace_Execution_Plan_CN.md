# DisasterTrace 下一阶段：从可证证据充分性到限时主动预警

研究与源码核对日期：2026-09-11。
核对基线：`sisuolv/disastertrace-benchmark`，`next-phase-v1`，提交 `a08486dca0cb08c481a44ebaf6d289520857f4fd`。

## 0. 使用边界

这是待实施、可供 Codex 拆分任务的计划，不是实现完成报告，也不是模型实验结果。本次读取远端关键源码、阶段报告及论文/官方接口说明；没有修改远端仓库、下载完整科学数组、独立重跑历史评测或启动模型/GPU/付费接口。仓库报告中的已有样本数和测试数属于其历史验收，不是本次新增结果。

执行者开始前必须重新读取工作区 HEAD、git status 和当前约束。本文件固定的是上述审查基线；不得将随后修改误认作本次已审查内容。不要覆盖用户未提交修改、历史 work/artifacts、失败记录和受保护 split。

当前阶段：数据与 CPU 协议验证。未来最多 4 张 H100 是资源上限，不等于本文件授权启动作业。不新增逐题人工 Gold，不用 LLM judge 决定主评分；允许继承明确署名的已有人工/专家标签。无法确定的匹配、质量或许可应拒绝/隔离，不能让 LLM 补造。

## 1. 决策摘要

主研究问题：在相同基础预报、合法信息权限、预算及准备要求下，系统能否选到有用证据，并将其转化为可验证的及时预警增益？

采用两条独立计分的轨道：

- **E：证据充分性与修订诊断。** 复用 active_forecast 的确定性参考及 multimodal_v1 的有序交付和分支参考。目标是资料在当时能支持什么，不是预测物理未来。
- **F：未来风险与及时决定。** 新增固定未来目标、独立事后结算、不可覆写预测提交、取证回执及时间/预算约束。这才允许评价预测质量、误报、漏报与准备时效。

16 灾种、74 来源登记作为数据储备，不能作为每一批研究的阻塞性配额。优先一个完整结果链，保留一个迁移场景。不要先训练天气基础模型、增加复杂 RL、自动改题或建设开放式应急世界模拟器。

## 2. 最新代码事实与复用位置

| 现有路径（相对 disastertrace-starter/src/disastertrace） | 核对到的内容 | 复用边界 |
|---|---|---|
| active_forecast/schema.py | 严格不可变 schema；RevisionTarget、CountTarget、AreaTarget；最多八卡；时空和版本兼容 | 不是 ForecastTarget；不应通过增加可选字段把两种 Gold 混合 |
| active_forecast/core.py | 有限池参考、充分性、最小充分集合、额外成本、预算评分 | 最小证据成本是私有完整池上的事后下界，不是在线最优策略 |
| active_forecast/public.py | exact_product_values 白名单；已读值/QC；完整合法候选目录 | 有限目录选择，不是无限制网络发现；字段投影不等于运行时隔离 |
| multimodal_v1/compiler.py | 有序/重复交付、按分支构建参考、值与来源分开的更新义务 | 不能重报为全部缺失；需要在新执行层实际强制权限 |
| multimodal_v1/build.py | Francine 官方 GIS 重绘、受控文本分区、研究 watch-list、六分支 | 不是原生卫星预测，不证明自然完整图文下视觉必要性；风半径不等于地点实测风 |
| V6 数据审计脚本与登记 | 原始捕获、有限下载、QC、来源/资产/事件相关记录 | 报告/瓦片/时步/分支不等于独立事件；准入仍需逐任务验收 |

已有 exact kernel 的 104 个开发 episode 为 NHC 24、GHCND 32、USDM 16、SEVIR 32；全部使用 archive_delivery，历史 availability 未证明时为 null。现有 MM 为一个 Francine 事件、一个 episode、六分支、30 检查点。V6 数据阶段没有新增正式 episode 或模型结果。[R01–R09]

## 3. 必须先冻结的科学契约

### 3.1 两种真值绝不合并

`EvidenceReference(branch, time)`：该分支当时合法、已取得的产品能支持哪些事实。

`OutcomeReference(target)`：未来目标最终按哪个观测/分析产品、哪个版本及 QC 规则结算。

改变信息到达顺序可改变前者，不能改变后者。E 轨的 unknown 是可计算的证据状态；F 轨的概率没有每题唯一正确答案。不得用完整池产品结论替代实际结果，也不得因为某一次概率高而事件未发生就认定该概率不合法。

E 轨中“存在预算内充分集合”可由有限枚举确定；F 轨中“当时不可能预测好”一般不能由一次失败或完整输入基线失败证明。后者只作匹配实验支持的瓶颈诊断。

### 3.2 只设置截止时间并不足以研究何时预警

固定目标时间 T、固定截止 D、截止前行动成本和收益完全相同、信息可无损保留且没有提前行动额外收益时，等待至 D 的策略能够模仿任何早期决定。此时有意义的是查询/停止的资源分配，而非独立的最优报警时机。

第一版可先使用这个简单设置，但称为“限时取证和截止前决定”。要研究有效提前量，再采用下面的监测设置：

- 在不知道结果时固定站点、阈值 h、未来窗口 [T0,T1]、检查点和准备时长 ell。
- 事后从合格采样观测定义首次超阈时刻 tau；无事件则 tau 不存在。
- 系统可在 sigma 发出一次不可撤回的研究准备决定；sigma+ell<=tau 才算及时。
- 未发出、过晚发出和无事件误报分别记录。
- 不能先看到 tau，再为该题设置 `deadline=tau-ell`；这会把未来时间信息写入任务。
- 已经超阈的窗口不用于“首次发生预警”主轨，按预先条件隔离。

预测提交、发出研究准备决定、停止获取证据是三个不同动作。允许提交后继续获取，不能通过接口强迫“写答案就不能再看资料”。

### 3.3 三类时间有效性分榜

- `controlled_replay`：人为规定资料交付；可以评价受控条件，不能称真实历史可用性。
- `historical_asof_verified`：有可核查的历史可用性证据；issue/valid/retrieved 不能相互冒充。
- `prospective_first_seen`：记录本采集器第一次观察到某版本的时间；不称全球首次发布。

E 轨已有 archive_delivery 的记录保持原样。不要为兼容新接口伪造 available_at。GEE filterDate 按 system:time_start 筛选，不能提供历史 as-of 版本保证。[R17]

## 4. 建议新增接口（以下路径是建议，不是现有实现声明）

推荐使用独立的 `active_warning/` 包封装 F 轨，保持历史 active_forecast.v1 行为不变。

### contract.py

`ForecastTarget`：target_id、site/entity、variable、unit、空间支持、window_start/window_end、operator、threshold、observation_sampling、timezone/datum、time_policy。

`OutcomeSpec`：私有 resolver、authority、版本、观测 QC、缺失容忍、单位/基准转换证据、结算规则、无法结算时的原因。

`ForecastCommit`：target_id、p、receipt_time、checkpoint、evidence_receipt_ids、model/config hash、上一提交哈希。系统计时，不能相信模型自报时间。

`DecisionCommit`：研究情景 ID、target_id、action、服务端时间、所依据的最新预测提交。首版一次不可撤销决定，后续变更另设版本。

`ActionReceipt`：request_id、action、requested_at、completed_at、status、artifact_revision_ids、返回范围、charge、bytes/cache 标记、错误类型。请求、成功取得、交付和实际进入模型上下文分别保存。

### environment.py

动作限制为 `list_available`, `read`, `query`, `wait`, `submit_forecast`, `issue_research_alert`, `stop_acquisition`。数据工具只能访问服务端许可的版本和范围。

必须规定：串/并发上限；重复读取是否缓存及如何收费；失败请求收费和耗时；处理中跨越检查点时的提交规则；超时回退；空返回；无限 wait 防护；取消请求；相同时间的确定性排序。

基准事件时钟与真实 GPU/API 延迟分别记录。主协议不得把一次普通 HTTP 读取随意放大为几十分钟。真实服务延迟、生产发布等待和实验压力条件分开出表。

### representation.py / lineage.py

将同一科学事实、其呈现方式及重复交付分成不同身份：

`FactRevision -> RepresentationAsset -> DeliveryReceipt`

关系至少区分 `derived_from`, `supersedes`, `summarizes`, `overlapping_support`, `shared_assimilation_input`, `dependency_unknown`。多个 NOAA 产品不能只因同属 NOAA 就丢弃至一份；同一产品的地图/摘要又不能被视为独立观测。未知依赖保持未知。

LEAP 已有依赖聚类；新增方法不能声称首次做同源去重。更具体的贡献候选是有可核查资产谱系和时空范围的配对实验，区分版本替换、互补观测、表示辅助与重复计数。[R12]

### resolution.py / metrics.py

结果只在离线评价进程加载。运行器的可见文件系统、检索索引、Python 工具不能访问私有结果、证书、完整未读数组及隐藏测试记录。哈希白名单和 DTO 验证是必要而非充分条件。

保留原始传输响应后才解析；失败输出不删除、不自动修复成成功；重试耗时与预算如实记账。定期生成独立可复算的提交清单。

## 5. 数据路线和准入表

### 5.1 第一条闭环：NHC 协议桥接

使用已熟悉的 NHC 历史产品构建一个同绝对有效时刻的未来最大持续风阈值目标，结算资料可以调查 NHC best-track/HURDAT2。该产品是事后分析，不称逐点直接实测。严格匹配最大持续风语义和时间，不将风半径包含关系变成地点风速结果。概率基线若从确定性预报生成，误差模型/校准器只能在开发集拟合。[R18]

目的：快速验证提交早于目标、结果独立、输入隔离、正常/超阈窗口和预算规则。不把气旋数量少的桥接样本当正式早期预警结论。

### 5.2 主候选：洪水站点预警

优先 N08，必须交付实际 join 后的覆盖表，而不是数据源推荐表：

`site_id mapping | datum/unit | target_window | forecast_cycle/version | usable observation history | source availability evidence | independent result | positive/negative/near miss | image overlap | rejection_reason`

必须核验 USGS 与 NWPS 站点对应、单位/水位基准、原始采样间隔、缺失和预报可用版本。当前 NWPS 主 API 不提供完整历史序列，HEFS 约 10 天，NWM 主服务也是短滚动历史；不能假设 API 存在就能拼多年回顾性预报。[R15]

观测相机 NIMS 可以按相机和时间取文件清单，但尚不能证明所需样本具有影像、站点、预报三者重合，或影像提供独立预测增益。[R16]

硬准入：合法基础预报、未来参考、目标语义、负例、时间有效性、许可/分组都能确定。任一核心条件长期阻塞则不把该来源送入正式 F 轨；切换 NHC 桥接或调查 EWB 温度/站点路线。影像不足时保留强数值主轨，不通过删除数值输入制造多模态优势。

### 5.3 E 轨空间辅助

GEOID/CEMS 可以用于标签定义下的覆盖/面积界限，但当前三瓦片全负、来自外部 test，不能当新隐藏测试或代表性洪水数据。N04 从合法 train activation 补独立正负样本；label-derived validity 私有，公共 QC 必须来自真实传感器/产品元数据。水体面积不自动等于新增淹没面积，像素比例不自动等于地理面积。[R07]

WorldFloods/GEOID 的事件不保证能与 USGS/NWPS 对齐；E 和 F 可以共用协议而不强行伪造同一事件链。

### 5.4 代表性与切分

先固定监测站点、时窗和阈值规则，再观察结果。区分富集困难案例的诊断集和可解释事件率的监测集。目录未报告不等于可证负例；缺失观测不填 0。未来最大值或持续时间规则必须明确离散采样语义。

分别维护物理事件图、资产复用图、来源依赖图。对物理事件/重叠时窗及同源资产做 split 防泄漏；共享 ERA5 不让所有事件合并。已读的外部 test 样例记录开发暴露身份。按事件/流域或时间块估计不确定性，问法、检查点、重复种子不作为独立事件。

## 6. 强基线和可识别实验

### 6.1 获取策略隔离

所有策略共用一个已冻结、可以处理缺测掩码和证据年龄的概率更新器：

`p_t = g_theta(base_forecast_t, acquired_evidence_t, missing_mask_t, age_t)`。

不能只冻结天气底座、同时让各 Agent 用不同融合算法，然后把全部收益归因于获取策略。g_theta 的拟合、校准及缺测模拟只使用开发集。

获取策略：固定顺序、最近优先、随机/最便宜优先、贪心、有限两步前瞻、LLM 选择。AFABench 的 grouped acquisition、硬/软预算及部分基线可以适配；不用照搬其完整大规模调度。[R11]

### 6.2 系统总价值比较

至少包括：气候/持久性；初始预报；最新合法业务预报持续更新加规则；简单数值后处理；固定流程；标准概率 Agent；候选方法。

区分“相对旧初始预报”的增益和“相对最新业务预报”的增益。公平提供公共资料及成本，不故意让官方基线错过后续更新。若所有证据都能低成本并行取得，全部合法读取是正常竞争基线；超预算完整输入才是单独的诊断条件。

BLF 可作概率状态方法参照；其 v4 的信息价值停止仅为未实测的讨论，不能假装存在已验收官方实现。LEAP 可作聚合/依赖处理参照，不能忽略其已有去重机制。[R12–R13]

### 6.3 最小有解释力的实验序列

1. CPU 确定性策略与独立结果结算：证明任务、时钟、预算和强基线工作，而不是先看 LLM 分数。
2. 同事件、同预算、共享 g_theta：获取策略效果。
3. 同事件/未来结果：准时/延迟/重复/旧版本/无关范围分支；只改变信息条件。
4. 两层表示：精确源事实与原生/重绘图文；同时披露两者给出的信息是否完全等价。
5. 固定预测轨迹、替换行动规则；固定策略、替换模型。分离预测、获取、感知和时机。
6. 在未见事件/流域/信息条件验证；最后做冻结后的前瞻影子提交。

不要一开始运行所有灾种×模态×预算×时限×模型×状态干预的笛卡尔积。先一个主任务、三个预算、少数策略；扩展由置信区间、有效独立事件和真实覆盖决定。

## 7. 评分

### E 轨

分别报告 visible_decision_correct、grounded_success、read_sufficient、spent、minimum_extra_cost、充分/不充分匹配对通过率。goal_correct 不能单独作为主分，因为未读证据猜中不代表有依据。

minimum certificate 是私有事后诊断，绝不返回给交互 Agent。当前 max8cards 是枚举算法边界，不应仅把上限改成几百而不更换证书算法。

### F 轨预测

每个预先固定检查点计算 Brier，并按目标/事件聚合，不能只评分模型愿意提交的时刻。尚未更新使用最近一次合法概率；没有任何提交使用统一预登记基线。保留 invalid/missing/timeout 比例。

每个提前量及事件层计算校准、Brier/相对基线差，不把自然单次结果当唯一正确概率。

### F 轨准备时效

主 V1：截止前准备与否，报告不同成本比例和最低提前量下误报、漏报、情景损失。

随机首次越阈扩展：及时检出率的分母包含全部合格正例；漏报不从提前量图中消失。无事件窗口报告误报率和每监测时长误报负担。阈值在开发集选择后冻结，不在测试集为每个模型重调以强行相同误报率。

一个研究代理损失可为：

`cost = rho * has_alert + 1[event AND (no_alert OR alert_time + preparation_time > onset_time)]`。

只表示公开假设下的漏失罚分和准备成本，不是真实经济损失。查询预算可先作硬约束，查询/秒/token 单列；若合并，使用预声明无量纲权重并做敏感性分析。

报告相对强固定流程的配对 `Delta J = J_baseline - J_policy`，按事件/时间块给不确定区间。预测质量、情景价值、资源、合法性不合成不透明总分。

## 8. 12 项既有获取任务重排

| ID | 新安排 | 与主问题的关系 |
|---|---|---|
| N12 | 立即，最高 | 合同、三种图、标签隔离；增加未来目标/结果、回执和时间契约，不平均摊至16灾种 |
| N11 | 与 N12 同步，离线 | 防泄漏及事件分层；新增物理事件以真实证据为准 |
| N08 | 提升为数据主路径 | 验证站点—预报版本—未来观测的闭环；先元数据与有限样本，不批量 |
| N04 | 条件推进，E 轨 | train 正负洪水样本、来源桥接、QC 隔离；不是站点未来结果替代品 |
| N02 | 备用路线 | 仅在温度预报—站点结算对齐可行时扩；ERA5 资料不冒充历史实时预报 |
| N05 | 修复状态/隔离，暂不扩样 | 解决小数 score、年份和不完整归档，不让错误标签进入未来主轨 |
| N01 | 延后 | 长尾灾种覆盖不阻塞主链 |
| N03 | 延后 | 保留正例验证待办，不做独立龙卷主项目 |
| N06 | 延后 | GLM 专用极端阈值/边界去重需要额外工作 |
| N07 | 延后 | 野火观测/QC/未来天气条件尚需独立准入 |
| N09 | 定向复用，暂不扩大 | 可借已有气旋图文；不增加港口动作真值 |
| N10 | 延后 | 无可靠时间地点的视觉数据仅作辅助感知 |

原计划的总捕获上限不是建议一次用完的预算，也不构成启动下载的授权。[R08]

## 9. 按依赖提交的实施包

### P0 — 研究契约与准入决策

输出：协议 ADR、代码资产地图、当前数据准入表、E/F 双轨命名、旧版本保留策略。

验收：任一输出能识别为资料事实或未来预测；说明时间模式；排除按未来 onset 倒推 deadline；列出可部署与特权诊断条件。

停止：结果来源/目标语义无法确定时，不生成 F 轨题目；可以继续 E 轨。

### P1 — 最小执行环境

依赖 P0。
输出：少量合成契约测试、只追加日志、查询回执、服务端时钟、预算执行、外部工具权限白名单、原始响应记录。

必测：未来/未读/私有 Gold 不可读取；跨截止请求；重复/失败/缓存收费；等待与预测提交解耦；重启重放一致；随机化未读值/QC不改变当前公开输入；同内容换表示不创建第二份独立事实。

停止：任何权限绕过、预算绕过或旧提交可覆写，禁止模型批量运行。

### P2 — 一个真实未来目标闭环

依赖 P0，可与 P1 的底层实现并行。
输出：NHC 小规模桥接与洪水 N08 覆盖审计；每条任务的 forecast/outcome/clock/datum/QC/negative 证据。

验收：不读未来；结算规则可独立复算；合法正负和不可结算样本分开；不能将实验受控到达写成历史实时。

停止：无法可靠匹配 forecast 与 observation，换路线而不是插值制造标签。

### P3 — 无模型基线和实验有效性

依赖 P1、P2。
输出：最新业务基线、固定/随机/贪心/两步前瞻、共享 g_theta；全读合法基线与特权条件分开。

验收：评分与独立计算一致，策略成本差异可解释；同一目标各信息分支共用一个 outcome；不要求候选策略一定获胜。

停止：所有卡片既便宜又相同、查询动作不影响可用信息、或时限设计无区分时，收缩主动取证主张；不通过造假成本挽救故事。

### P4 — 小规模模型试点（需要新的明确授权）

依赖 P3 全部通过。
输出：少量开发事件、一个基础后端、少数策略、三个预算；随后加入强概率 Agent 和表示对照。

验收：原始调用完整、失败保留、协议冻结、成本可复算。4 H100 为上限，不是必须占满。

停止：若格式问题主导先改开发协议并提升版本，不用测试集调；若增益仅来自弱官方基线或不公平模态删除，修复后重验。

### P5 — 确认性结果与前瞻影子验证

依赖 P4。
输出：冻结模型/策略/成本/阈值，未见事件评估、事件级不确定性、漂移压力测试、前瞻 first-seen 日志与预先提交。

验收：所有科学主张均对应独立实验；近邻对照只写核实的差异；没有保证排名反转或 Agent 一定胜出。真实响应行动不自动执行。

## 10. 论文可能支持与不能支持的结论

可争取：相同预算和预报底座下的增量预警收益；哪些信息条件使得来源/版本处理重要；完整输入能力与限时能力是否不同；感知、获取、状态、决策的匹配诊断；在哪些场景简单流程已经足够。

不能仅由该协议宣称：首个主动信息获取/异步 Agent/证据去重；真实最优信息价值；自动证明物理未来不可预测；真实减灾经济收益；所有原始数据无人工；仅凭前瞻小样本证明全无训练污染；74独立源/104独立灾害/全部16灾种已可预警。

建议当前定位：**DisasterTrace 将可追溯证据获取、修订与未来风险结算放入同一受限时间协议，检验 AI 在既有预报之上的增量预警价值，并以独立证据诊断解释它何时有效、何时无效。**

## 11. 已核对来源与复用入口

仓库固定前缀：`https://github.com/sisuolv/disastertrace-benchmark/blob/a08486dca0cb08c481a44ebaf6d289520857f4fd/`。以下仓库路径均相对根目录。

- [R01] `publication/v6_review_20260911/REVIEW_FOR_CHATGPT_PRO_CN.md`
- [R02] `disastertrace-starter/src/disastertrace/active_forecast/README.md`
- [R03] `disastertrace-starter/src/disastertrace/active_forecast/schema.py`
- [R04] `disastertrace-starter/src/disastertrace/active_forecast/core.py`
- [R05] `disastertrace-starter/src/disastertrace/active_forecast/public.py`
- [R06] `disastertrace-starter/src/disastertrace/multimodal_v1/compiler.py` 与 `build.py`
- [R07] `plans/v6_0911_dataset_selection/DATA_READINESS_REVIEW_CN.md`、`REUSE_AND_GAPS.md`
- [R08] `plans/v6_0911_dataset_selection/NEXT_ACQUISITION_MANIFEST.json`
- [R09] `disastertrace-starter/artifacts/active_forecast_core_v1/README_CN.md`、`disastertrace-starter/README_MULTIMODAL_V1.md`
- [R10] Extreme Weather Bench：`https://arxiv.org/html/2605.01126v1`；代码 `https://github.com/brightbandtech/ExtremeWeatherBench`。复用 events.yaml、cases/inputs/metrics，不把其回算预报默认认定为历史实时可用。
- [R11] AFABench：`https://arxiv.org/abs/2508.14734`；代码 `https://github.com/Linusaronsson/AFA-Benchmark`。已核对 README 的方法与分类任务边界，适配需要独立验证。
- [R12] LEAP：`https://arxiv.org/html/2609.01337`；代码 `https://github.com/layingfish/LEAP`。论文已有 dependency clustering；本次没有复现其完整方法。
- [R13] BLF：`https://arxiv.org/abs/2604.18576`、`https://arxiv.org/html/2604.18576v4`。v4 将信息价值停止标为尚未尝试的设想。
- [R14] EarthVerse：`https://arxiv.org/html/2608.23525v1`；SIREN：`https://arxiv.org/abs/2607.24588`；Gaia2：`https://arxiv.org/html/2602.11964`。分别覆盖主动调查、预警链及异步时限；不要将它们概括成静态 QA。
- [R15] NOAA NWPS：`https://api.water.noaa.gov/about/api`。历史覆盖与业务产品类别以该次服务说明为边界。
- [R16] USGS NIMS：`https://api.waterdata.usgs.gov/docs/nims`。只证明接口能力，不证明事件级配对已完成。
- [R17] GEE filterDate：`https://developers.google.com/earth-engine/apidocs/ee-filter-date`。
- [R18] NHC 数据目录：`https://www.nhc.noaa.gov/data/`。本次搜索检索到官方目录说明，直接打开受到 403 限制；最终适配前需再核验具体文件、产品说明和版本。
