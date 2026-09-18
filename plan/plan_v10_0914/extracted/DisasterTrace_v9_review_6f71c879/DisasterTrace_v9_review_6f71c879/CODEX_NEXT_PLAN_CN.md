# DisasterTrace v9：基于 6f71c879 的实现复查与后续 Codex 执行计划

**审查提交：**`6f71c8799ff69439a18f645e63b8c966ca21eec4`  
**父提交：**`5ed0fb94ae7bf235b37e7528e201b603271edffa`  
**审查日期：**2026-09-14  
**性质：**当前结果驱动的执行交接；不是新实验已完成声明，不自动授予付费调用、下载、远端计算或持续任务权限。

## 0. 给执行者的总约束

继续 v9、C1/C2/C3、E/F/D/MM、原 X00–X09 与现有 N1–N5 路线，不另起 v10，不要求主动方法或 LLM 必须取得正收益。以 `plans/v9_followup_execution_20260914_01/PAUSED_SUMMARY_CN.md`、根目录 `LATEST_PROGRESS_20260914_CN.md` 及实际冻结材料为当前状态；历史计划中的“尚未完成”须先核对，不能机械重做。

本轮已暂停。当前用户要求复查和规划，不是恢复原后台管线的授权。严禁从此计划自动重启旧 launcher、打开确认周、重新发送已消耗逻辑请求、下载大型数据或调用付费 API。下一次昂贵执行需要当次有效、明确的范围与新冻结；本地只读审计、受控测试及得到明确实施授权后的代码修复与数据重放，应按各自权限执行。

开始先记录 HEAD、分支、staged/unstaged/untracked 和实际执行源码。不能 reset、clean、覆盖旧 checkpoint、修改原始捕获或把未提交用户文件混入发布。若 HEAD 已前进，逐函数比较下面的发现是否已修正。新代码可沿用目录结构；旧结果使用其冻结源码重放，任何改变语义的派生成绩另存。

## 1. 当前状态：已经完成的工作不要重新安排

| 内容 | 当前证据 | 下一步真正的门槛 |
|---|---|---|
| 工程与恢复 | 仓库记录616项相关测试通过；累计等待、执行身份、串行恢复与AFS锁等待已处理 | 本地完整重放；补本次异常记录和审计完整性边界，不重建时钟 |
| 区域训练与校准 | 四区域3303次原生获取；purge后9678条拟合、2780条校准；独立2024年12月时期 | 校准不等于所有采样策略下仍校准；补条件归因和未见过程验证 |
| E02 | 1008次完整调用；42个底层问题×相依证据/表示/输出视图 | 离线分析模型槽位答案的确定性归约；不是再跑同一矩阵 |
| E结果 | Flash聚焦逐槽126/126；Pro聚焦逐槽全部槽位126/126正确，最终101/126，25个汇总错误 | 同模型输出的程序归约对照；与原模型成绩分开，不冒充新推理 |
| 普通F | 3区域×2日期×2阈值；120条程序臂、48条模型会话；2304次API请求 | 全臂解释、证据/校准分离、共同输入和资源对照；当前仅base-bound |
| Denver诊断 | 2025-01-09完整日；两阈值、384次API请求 | 已按暴露的正结果选日，仅探索性；不能并入自然总体或确认 |
| 温度连续程序 | 24个月、192条轨迹、11644个机会、3645个唯一目标 | 合法额外证据、冻结校准、温度模型与C1；不再从头接日极值 |
| COPY | 普通/诊断F已有COPY_CURRENT和COPY_BASELINE；温度已有两协议COPY和首次值保持 | 当前H15的base-bound结果不能证明persistent下同样成立 |
| 费用 | E01原938次尝试、876结算、62未知保留；E02/F新批完整结算 | 原请求只读对账；未知不视为0，不能免费重试 |
| 尚未完成 | 独立确认、全部16类、完整D反馈、MM和在线F | 各自准入；不作为核心E/F无限串行依赖 |

模型名称、thinking disabled、温度0、512输出token只描述该批设置。不把Flash/Pro的开发结果推广为模型一般排名；别沿用v8 Qwen的精确复制计数描述v9 DeepSeek。

## 2. 本次审查实际做过什么

本次通过GitHub连接读取代码和文档；容器下载26.6MB复查包遇到DNS失败，未得到完整包。未独立重跑616测试、所有原始E02回答、全部F事件日志、192条真实温度轨迹或原生数组。

实际运行26个离线定向情形：
- 五个完整源码文件逐字重建并通过Git blob哈希核对：`api_capture.py`、`lifecycle.py`、`calibration.py`、`regional_calibration.py`、`analyze_temperature_fullcalendar.py`。
- 20个正常/保护控制；4个情形复现两类实现边界；另2个为校准归因行为和未知费用对账限制的检查。
- API使用假HTTP、假spool发布、虚构凭据与局部故障注入；ApiBudget使用真实本地文件锁，不是AFS测试。
- 温度审计使用合成24月×8臂目录，运行真实审计main，不是对真实温度成绩重新审计。

原始记录见 `REVIEW_SCOPE.json`、`review_results.json`、`audit_completeness_results.json`、`source_verification.json`。反例断言通过表示成功复现问题，不是表示实现通过验收。

## 3. 高优先级发现

### R1 / P1：温度审计未验证完整登记分母

位置：`plans/v9_followup_execution_20260914_01/scripts/analyze_temperature_fullcalendar.py::main`。

审计遍历当前存在的`20??-??`目录和`*__*override`子目录，却直接写入`windows=24`、`sessions=192`、`passed=True`，未先比较冻结月份/臂集合。

合成反例：
- 完整24月×8臂时通过，故意改坏一项分数时能够拒绝，这是正向控制。
- 删除一个月份后，实际23月/184臂，仍生成24/192/passed。
- 删除一个方法目录后，实际24月/191臂，仍生成24/192/passed。

**影响边界：**证明审计器可能为不完整产物给出完整通过声明；不证明真实192条轨迹缺失，也不证明其已有数值错。

最小修复：
1. 从独立冻结的注册清单读取expected_month_ids、expected_arm_ids、expected_opportunity_ids和canonical target/result版本。不要从现存输出反推期望集合。
2. 检查月份、方法、机会ID精确集合、重复ID、缺失与意外项；完成回执必须与该集合逐项连接。
3. 分开`registered`、`present`、`completed`、`audited`、`scored`，计数从对象集合计算；不能写常量作为观测值。
4. 数学评分通过、数据完整、费用完整、阶段完成分开输出；所有必需条件成立才给总通过。
5. 正式验收不要只依靠Python assert；使用显式异常/验证结果，避免优化模式影响验证。
6. 日志/快照缺失属于artifact incomplete，不能改成天气结果missing；真正缺测仍保留原共同掩膜。
7. 新验证器先跑完整本地产物。若集合完全匹配且分数相同，记录`no_numerical_change`，无需重跑轨迹。
8. 对F/E相关审计做同类检查；F现有`all_registered_arms_finished`是有用的独立状态，不应让下游只读宽泛的`passed`。

最小回归：完整24×8、缺月、缺臂、重复机会、意外臂、错误分数、真正天气缺测、空输出、完成回执与产物冲突、python -O的等效拒绝。

### R2 / P2：API异常记录依赖正在失败的账本或错误正文读取

位置：`disastertrace-starter/src/disastertrace/monitoring_v1/api_capture.py::capture`。

当前except中先执行`HTTPError.read()`，随后读共享账本并可能再次调用`budget.transact(... outcome='unknown')`，最后才写局部`FAILURE.json`。

已复现：
- HTTP成功并已持久化RESPONSE.body/RESPONSE.json；费用结算锁失败，异常路径的unknown更新再次锁失败；最终FAILURE.json缺失，费用仍reserved。
- HTTPError发生后读取其错误正文又抛错；没有局部FAILURE.json，费用仍reserved，外层得到第二个异常。

**影响边界：**原始成功回答在第一个例子中仍保留；F的外层service还会写自己的`.failure.json`，因此不能声称整条管线丢掉所有失败证据。未证明E02/F已完成结果受到影响。

最小修复：
1. 外层错误观察先构造并尽可能写入每请求独立、脱敏、追加式的本地记录；不先等待共享账本。
2. 分别保护错误正文读取、局部记录落盘和费用结算；记录原异常以及次级异常，不能用次级异常掩盖原HTTP/解析错误。
3. 能取得可信usage但账本暂不可更新时，保留`response_received_billing_pending`及usage哈希，不默认丢弃合法回答，也不默认给截止前信用。
4. 只有原请求/原响应绑定成立时才做幂等费用对账。未知费用维持预留，不等于0；没有原响应的请求不猜账。
5. 设计追加式reconciliation记录，避免直接编辑冻结BUDGET。API类别、调用ID、请求/响应哈希、token、费率快照、原状态和新状态都绑定。
6. 不重发HTTP、不重试模型、不重复计费。单独区分`not_dispatched`、`response_received`、`response_invalid`、`billing_pending`和`unknown_remote_execution`。
7. 本地存储完全不可用时不能保证任何落盘成功，应fail closed并暴露该故障；本修复不承诺任意远端exactly-once。

最小回归：正常、局部锁重试成功、持续锁失败、HTTP错误、错误正文读取失败、收到回答后账本失败、usage非法、账本对账幂等、原请求不匹配、返回后超截止。只对局部锁/原回执查询进行有限重试，禁止模型结果重试。

### A1 / P1-科学归因：额外资料可能仅切换概率校准器

位置：`monitoring_v1/calibration.py::predict` 与执行脚本`fit_regional_baselines.py`。

当前选到一个原始频率cell后，按`disclosed`非空与否选择`post_calibration['evidence'/'base']`。即使证据专用cell未达到样本门槛、回退到同一个基础cell，或`no_taf`分支完全没有使用证据特征，也仍可能改用另一条校准映射。

合成银行中：相同cell、相同原始概率0.1，仅切换映射，就得到0.2与0.6。本次未统计真实捕获有多少这种路径。

**这不是自动判定算法错误。** 资料缺失、是否取得资料或选择机制可以含信息；两个校准器也可以是合法系统组成。但不能把所有新程序概率都归因于天气证据内容或LLM选择到了新信息。

新增诊断，不改旧分数：
- `feature_cell_requested`、`selected_cell`、`fallback_level`、`cell_n`、`raw_probability`。
- `calibration_family`、`base_map_probability`、`evidence_map_probability`。
- 已读source/slot集合、资料内容/缺失状态及其变化。
- dispatch最新基线/当前值、提议值、采纳原因、cutoff最终值、结果侧损失。

定义x_B/x_E为基础与证据输入选中的原始概率，g_B/g_E为冻结映射，逐条报告：
`g_E(x_E)-g_B(x_B)=[g_B(x_E)-g_B(x_B)]+[g_E(x_E)-g_B(x_E)]`。
这是选定次序的数值分解，不是天气因果或唯一交互分解。另给反序分解/2×2控制以揭示交互。

新增固定校准器对照：同一个g作用于B/BE、仅更换校准器但不增加资料内容、原完整f(B,E)。全部用分离拟合/校准期构建，不在评价标签上调映射。报告选择策略造成的校准分布变化，不声称PAV能保证任意自适应选择下校准。

## 4. 首批执行：只用已有文件和CPU

### N1.R0：保全与范围核验

- 记录实际HEAD、工作区和执行环境；若与审查提交不同，保存diff，不覆写原始工作。
- 读取所有最新pause/complete，区分脚本历史阶段文字与实际已完成状态。
- 验证本机完整原始包和省略清单。若只有review ZIP，报告其缺失，不能把省略F journal当作原实验未完成。
- 执行当前监测相关测试并给实际数量/失败/跳过；616是继承的报告数，不是这次预设通过数。
- 对五个审查模块做Git blob/sha核验并运行所附探针；R1/R2改成项目内生产模块测试，不仅测试片段。
- 使用未存在的新输出目录。所有原启动器已消耗，禁止运行。

输出：`BASELINE_REVIEW.json`、`TEST_COMMANDS.json`、实际测试日志、`SOURCE_DIFF.json`、`REVIEW_SCOPE.json`。

### N1.R1：修复验收链并做历史影响核查

先修温度分母验收，再修API异常/费用对账。无需模型。

对原24月/192臂清单、快照、canonical scores、原响应和费用状态重检。产出每项：
`unchanged` / `affected` / `not_evaluable_from_available_artifacts`。

发现受影响产物时，仅在冻结捕获上重算允许重算的统计，保留原结果并报告diff。不要因验证器修复而重发模型请求。

输出：`AUDIT_COVERAGE.json`、`SOURCE_AND_CALL_DISPOSITIONS.json`、`HISTORICAL_IMPACT.json`、`RED_GREEN_TESTS.json`。

### N3.A1：完成校准与预测值路径归因

复用普通和Denver两套独立F记录。优先对已有程序预测及dispatch证据进行数值重算，不重跑API。

区分六种情况：
1. 数值精确等于最新基线；
2. 数值精确等于当前状态；
3. 与二者仅有数值/舍入差；
4. 原始频率cell改变；
5. 原始cell未变但校准映射改变；
6. 候选改变但未采纳或未影响cutoff。

当前“新提议”阈值为与两可见值均相差>0.005。它不是精确复制计数，不应与v8精确相等统计混用。保留exact、1e-6、0.005三种统计，不用阈值优化结论。

按ordinary/Denver、阈值、区域、日期、selector、predictor分开输出。差值符号统一为`loss_method-loss_follow`（负值改善），也可以另提供`gain=loss_follow-loss_method`但严禁混列。

输出：`PREDICTION_PATHS.parquet/jsonl`、`CALIBRATION_ABLATIONS.json`、`HELP_HARM_EFFECTIVE.json`、`ATTRIBUTION_REPORT_CN.md`。

### N3.E1：对已有逐槽回答做确定性归约

不再重复E02的1008次矩阵。保留原始模型最终E和逐槽输出，用原登记aggregate对模型已输出槽位归约，另算混合管线成绩。

至少并列：
- 原始直接输出；
- 原始逐槽+模型最终汇总；
- 模型逐槽+确定性汇总（派生对照，不是新的模型调用）；
- 原生合法产品确定性reducer；
- 恒unknown。

不得将评估侧正确slots塞入混合管线；程序只能读模型实际输出。格式无效、漏slot、未知/冲突保留，不“修补”非法回答。完整输入124/126槽全对不必然意味着混合结果恰好124/126，应逐条计算而不是从汇总数猜。

按42个底层问题聚簇，证据条件与两表示是相依重复；报告每slot错误、存在量词归约错误、无依据确定性、可判定但unknown、格式失败及全部成本。

输出：`E_REDUCER_CONTROL.jsonl`、`E_ERROR_TRANSITIONS.json`、原/派生对照表、未改原回答的hash证明。

### N4.C1：现有F全臂的完整分析

原连续F不仅有主摘要的8臂，还有risk、coverage及同selector的分配×授权2×2。先使用所有已完成臂，避免以增加模型替代缺失分析。

- 固定predictor与selector：分额/全局 × 私有/共享。
- 固定predictor与global/shared：batch/risk/coverage/LLM selector。
- 固定获取规则和信息：程序与LLM predictor。
- 逐臂保留费用、token、客户等待、采纳状态、资源预留、所有机会与结果缺失。
- 不把API HTTP时长当服务端计算；不把声明1ms程序与真实网络延迟称作真实部署成本相等。
- 只在共同输入/资源/时钟合同可比的分组内比较；普通集与Denver不合并作总体。
- 当前只使用base_bound时，COPY跟随一致是协议条件下的结果，不外推persistent。

输出：`ALL_ARM_SCORECARD_CN.md`、`FACTOR_2X2.json`、`SELECTOR_PREDICTOR_PAIRS.json`、`COST_TIMING_QUALIFICATION.json`。

## 5. 下一次有限模型试验：E到F接口，而非更多同类矩阵

只有N1和N3离线分析完成、问题与预算冻结后才申请新的API/GPU批次。当前请求本身不启动这些动作。

### 5.1 科学问题

在相同合法证据与完整共同TAF下，F不变来自什么：证据无用、模型没理解、模型理解后不会转为概率，还是保留基线确实更好？不得根据不修订直接认定模型失败。

### 5.2 最小分层对照

先固定获取轨迹，以隔离预测/理解：
A. 当前F输入与头；
B. 同一证据，加模型逐槽结果经确定性归约的结构（不添加新外部事实）；
C. 同证据的已核验程序特征/归约输入，作为合法工具辅助条件；
D. 冻结统计f(B,E)与校准器对照；
E. B-only/COPY/FOLLOW。

C不得传评估器隐藏标签，也不能把“E支持集合已确定”写成未来F应为0/1；原生解析是一个处理工具，需报告额外计算/上下文成本。

若B增加一次模型调用，主比较给其他方法相同总预算或报告真实质量—成本曲线，不能只按每次512输出限制声称等预算。先小规模冻结信息与请求形状验证，之后才运行。

之后才固定predictor比较获取策略，不同时改变selector、预测器、校准器、语义表示和时间协议。程序提议与LLM selector组合产生的新数值，不归因于LLM predictor。

### 5.3 预先定义结果分支

- E改善、F不变：保留结果；检查在独立时期拟合的f(B,E)是否有增量，不强迫概率变化。
- 只需程序聚合即可解决E：把它作为强工具基线；这不削弱benchmark，而是排除纯语言归约瓶颈。
- F改善来自校准器切换：归为映射/融合贡献，另验内容增量。
- 只有persistent改善且COPY可解释：归为状态/时点效应，不称新增预测信息。
- LLM selector不如risk/coverage/batch：保留，无需弱化对照。

## 6. N2：独立过程和确认数据

已完成2024年12月拟合/校准及purge，不重新从零下载同一批。审查输入足迹是否包含TAF有效窗、观察回看、目标支持、来源订正、状态延续、区域空间关联和统计拟合时期。共享hash能够证明重叠，未共享hash不自动证明独立天气过程。

普通试点是纽约/芝加哥/丹佛的2025-01-06与01-10；1km零正例，5km47个正机会。Denver01-09是按已知3个1km正例选定的完整日，明确为outcome-selected exploratory diagnostic；模型没看到未来标签不等于数据选择没有后见条件。

下一步从预注册的连续天气窗口/外部定义选择独立过程，保留近阈值和普通时段；固定事件/日历块选择、缺测、模型、提示、校准、预算、协议及停止规则后才打开确认材料。

Bay2025-02-17—23继续保持未打开。数据暴露本身要入账：看过标签、用于调提示、用于选择校准器或决定扩样的任何材料归为开发。N2预留周未暴露不自动满足所有过程独立条件。

不承诺20个过程一定够。按开发块间方差和预先指定的精度/效应目标确定规模，报告保守块级配对不确定性。相关块不是已经验证独立的天气系统。自然集与富集诊断分表，不用模型胜负决定继续加哪个日期。

输出：`EXPOSURE_LEDGER_DELTA.json`、`EVIDENCE_FOOTPRINTS.json`、`PROCESS_SPLITS.json`、`CONFIRMATION_PREREGISTRATION.json`。

## 7. N4：persistent协议与C2联合可达性

只在新的冻结中启用persistent，保留当前base-bound成绩。先CPU运行已完成的COPY/FOLLOW/首次值保持，明确新基线到达、旧override期限、同值续期、显式保持与自动提议的区别。

模型返回probability而系统自动OVERRIDE时，不称模型自主选择OVERRIDE。确需FOLLOW/OVERRIDE/NO_CHANGE显式动作，单独给输出协议版本；旧回答不能事后猜动作。

C2继续连接实际已花/预留资源、source与计算成本、缓存权限、版本、在途任务和截止。小图给有限精确解及见证，大图给界和可行解；不把各目标独占预算的解相加。

当前E可达性优化的是产品事实，不是未来F最优；选择器被奖励减少unknown也不能直接推导F收益。相同状态分支的后见最好路径只作评估侧诊断，不能当在线oracle策略或单个样本期望信息价值。

X09仍是同信息单目标/多目标输出，不是E/F双头。需要新调用时同时冻结按请求上限与按组总输出预算的对照，区分上下文复用、质量和批处理耗时；不以X09阻塞核心F。

## 8. N5：温度与其他物理过程

### 温度下一步

24个月192条程序轨迹已完成，不再规划“先跑完整日历”。先修审计完整性并在真实清单上重验。

新增`DENOMINATOR_BRIDGE.json`连接v8静态11680机会/3661目标与v9连续11644机会/3645目标。逐条说明缺36机会、16目标的原因：会话支持、边界、重复身份或其他合同规则。没有逐行证据前，不推测为错误，也不默认为合理。保留未结算与已发生day0政策。

然后接入完整共同的未来四日成员极值产品，新增预先定义的合法补充资料（例如同站此前DWD日值）。DWD观测日结束时间不自动等于公开时间；无法证明则继续声明归档释放场景。

补B、f(B)、f(B,E)的独立校准，按同成员连续三日构造事件，不能乘边际概率。两年仅一个站点，不称地区泛化；113个frost_day是2m日最低温越阈，不等于实际地面霜冻/作物受损。三日绝对阈值不自动称通用热浪/寒潮。

同基线免费、辅助资料计费，先数值程序和同输入诊断，之后才安排少量真实模型。新温度模型实验按实际数据资格择路，不因在某灾种更容易赢而改变主实验。

### 其他线路

- H07：当前已验证单位与代码的结论保留；实际积累端点、连续窗口和同目标基线通过后再做原生图/特征/工具实验。
- H08：免费共同HEFS里已包含的版本E不能重新收费来制造取证收益；断面、成员、调蓄、瞬时/平均、流量/水位分别准入。
- MM：原生图像不等于隐藏mask；合法工具处理与特权事实分开。
- D：先固定F的准备场景，再接闭环；不得用准备偏好污染固定信息条件下的天气概率；不宣称真实减灾收益。
- 前瞻：当前source-only成功不等于在线F。新任务必须有开始前固定目标、合法收到记录、deadline提交和后来结算；前瞻不阻塞历史核心。
- 16类：保持来源/许可/解码/语义/配对/时间/E/F/MM/D/确认分级，不要求全部候选都进入主榜。

## 9. 运行与资源控制

先前CCI为2核8GiB、ACP程序任务用64核/256GiB或16核/64GiB，只是已完成环境记录，不是新任务的默认授权。

先用已有本地材料估计CPU重放瓶颈。已合格原轨迹只读复用；验证器修复优先重验，非必要不重算或重跑。新的CPU迁移要记录源码、配置、数据、程序延迟情景和实际硬件，不把程序声明1ms改成节点实测后混合旧对照。

模型调用前：新任务清单、模型/返回model身份、thinking模式、token上限、总费用、请求数、并发、超时/未知/停机规则与已授权截止全部冻结。费率从获准的当次官方快照核对，不把本文/旧代码中的2026-09-14费率当永久价格。估算上界不是账单。

只允许有限、本地锁或原回执轮询；任何新模型尝试必须有新的授权记录，不能选择性重试失败题。若重建整批采集修复实验，记录与原批提示/题目/参考一致性，像E01/E02一样明确两批，不能悄悄替换。

保留暂停状态，禁止后台自动追加研究阶段。完成一个获准批次后提交材料，不自动打开确认或下一轮扩样。

## 10. 工作包与依赖

| ID | 原路线 | 优先级 | 依赖 | 不新增模型的出口 |
|---|---|---|---|---|
| N1.R0 | N1 | P0门禁 | 无 | 真实checkout/范围/测试基线 |
| N1.R1 | N1 | P1 | N1.R0 | 温度完整性红绿回归和旧产物重验 |
| N1.R2 | N1 | P2 | N1.R0 | API嵌套失败与幂等只读费用对账 |
| N3.A1 | N3 | P1科学 | N1.R0 | 程序cell/校准/采纳路径归因 |
| N3.E1 | N3 | P1科学 | N1.R0 | E02模型槽位确定性汇总派生对照 |
| N4.C1 | N4 | P1科学 | N1.R1,N3.A1 | 已完成全臂2×2与selector/predictor报告 |
| N2.D1 | N2 | P1科学 | N1.R0 | 完整输入足迹与独立确认设计，确认未打开 |
| N5.T1 | N5 | P1 | N1.R1 | 36机会/16目标差异清单、温度下一输入合同 |
| N4.F1 | N4 | 条件模型 | N1.R1,N1.R2,N3.A1,N3.E1,N4.C1 | 新的小规模同信息E→F冻结，得到新授权才调用 |
| N4.P1 | N4 | 条件 | N4.C1 | persistent与COPY CPU对照；新模型动作协议单列 |
| N4.C2 | N4 | 条件 | N1.R1,N4.C1 | 实际账本联合可达见证与支持规则 |
| N5.T2 | N5 | 条件模型 | N5.T1,N2.D1 | 温度真正补证与有限模型冻结 |
| N2.CONFIRM | N2/N4 | 后置 | 固定主要方法、N2.D1及数据资格 | 不按正收益门槛决定是否确认，按可解释性/数据/功效门槛 |

N4.F1不等待D/MM/全部16类。N1防御性小修不应无限阻塞N3的已有捕获离线分析。修复或科学结论为零/负都可完成任务；仅发布有证据支持的层级。

## 11. 每批最少交付

- `STATUS.json`：沿用上述ID，状态为done/partial/blocked/skipped/not_started，明确理由。
- 实际命令、时间、退出码、环境、源码/数据/协议/评估器hash。
- 原始与派生结果并列；语义变化、数值变化和未变项清单。
- 所有机会、方法、失败/缺测/未知费用的共同分母；不靠删除失败获得通过。
- C1/C2/C3现有证据与不能声称的内容；不把工程测试数当novelty证据。
- 下一项最小未回答问题，而非新的大而全路线图。

## 12. 审查引用入口（全部固定于同一提交）

仓库：`sisuolv/disastertrace-benchmark`；分支`next-phase-v1`；提交`6f71c8799ff69439a18f645e63b8c966ca21eec4`。

1. `LATEST_PROGRESS_20260914_CN.md`。
2. `publication/v9_followup_20260914/README_CN.md`、`REVIEW_FOR_CHATGPT_PRO_CN.md`。
3. `plans/v9_followup_execution_20260914_01/README_CN.md`、`RUN_REPORT_CN.md`。
4. `plans/v9_followup_roadmap_20260914_01/RESEARCH_ROADMAP_CN.md`。
5. `plans/v9_followup_execution_20260914_01/scripts/analyze_api_followup.py`、`fit_regional_baselines.py`、`run_api_pilot.py`、`analyze_temperature_fullcalendar.py`。
6. `plans/v9_followup_execution_20260914_01/reports/e_error_mechanisms_01/REPORT_CN.md`、`reports/temperature_fullcalendar_audit_01/REPORT_CN.md`。
7. `disastertrace-starter/src/disastertrace/monitoring_v1/{api_capture,lifecycle,calibration,regional_calibration,production}.py`。
8. `disastertrace-starter/src/disastertrace/monitoring_fixed_v1/{adaptive,joint_targets}.py`。

**最后提醒：本计划不是要求再证明一遍“模型可以调用API”。最小下一成果应当是：当前得失有可信分母、每次概率改变能定位到输入/映射/协议路径、E归约瓶颈能在不额外取得信息的情况下被验证，以及下一轮模型实验确实只回答一个尚未解决的问题。**
