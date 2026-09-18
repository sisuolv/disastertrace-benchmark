---
title: DisasterTrace v12 后续计划整合版
plan_id: v12-next-integrated-1eba36d
reference_commit: 1eba36dd272c72573d1309c78d45dbe97dd8af12
branch: next-phase-v1
status: proposed_not_executed
basis: eight_uploaded_zip_packages_plus_standalone_markdown_and_connected_GitHub_source_reads
production_modified_in_this_review: false
confirmation_opened_in_this_review: false
---

# DisasterTrace v12 后续计划整合版

## 0. 结论与使用方式

下一阶段不应是“修一下 JSON → 重跑 288 次 → 铺开 16 灾种”，而应是：

**保全已完成 v12 → 修真实执行与派生报告的资格缺口 → 用同后端、同日历区分时间、信息与策略作用 → 多状态 C2 → 小额真实接口资格 → 一次有界 selector 实验 → 双协议确认 → 分轨扩大 C3。**

沿用 C1/C2/C3、E/F/D/MM、A→B→C→D、X00—X09 和 16 类灾害总路线；本文 I00—I14、P01—P04 只是合并工单，不替换原贡献编号或已消费实验身份。

当前用户请求是审查和计划整合，不是运行授权。本文没有修改远端仓库、提交代码、运行真实天气实验、调用模型或打开确认集。BACKLOG.json 中所有工单均为 proposed；其中的上限不是额度授权，也不是已运行数量。

### 0.1 本次证据范围

- 实际读取 8 个 ZIP 中的计划、机器工单、关键源码副本与探针材料，以及独立 Markdown 计划。ZIP 解包条目及 SHA256 见 ATTACHMENT_MANIFEST.json；重复内容不视为独立证据。
- 通过连接的 GitHub 读取分支 HEAD，仍是上述完整 SHA；读取实际 worker、production、selection、residual query plan、C2/Stage C 分析器、年度拟合、温度后处理和当前结果入口等。路径见 SOURCES.json。
- 在本对话容器中，复制附件探针到隔离临时副本并重跑：28 个边界观察中 22 个正常/保护行为、6 个反例观察均复现；另运行恢复的正常/故障两案例，以及配对身份和三项缺失界算术控制。退出码为 0 表示预期观察复现，包括错误行为，并不表示缺陷已修复。
- 上述是源码函数级、替身依赖和合成数据测试。没有取得完整私有仓库安装与 AFS 运行资产，没有独立重跑 628/750 测试、840 轨迹、108 方法会话或 288 API 请求。恢复测试的基类 spool 仍是替身，配对测试使用函数摘录；必须转为真实生产模块集成回归。
- 此次审查有只读 GitHub/文档联网；隔离探针没有实际网络调用。未来“离线工作批次”需单独禁网络，不把仓库元数据读取伪记成总联网次数为零。

### 0.2 当前应保留的总体判断

没有据此整体撤销 v12 已发布结果的依据；也不能从已有测试通过推断全部故障路径正确。每个发现必须同时记录：源码行为、合成复现、原始运行是否触发、对应结果是否改变。后三者不能相互替代。

## 1. 当前基线：三条结果轨道分开保存

| 轨道 | 已完成内容 | 当前证据 | 不能推导的结论 |
|---|---|---|---|
| 原整周程序实验的 v12 派生分析 | 840 轨迹；12,096 方法无关机会；60,480 方法行；两阈值各 6,048 注册、6,008 可结算、40 缺失 | 1km 有 29 个正例机会；5km 有 307 个；5km 同 values 后端 coverage 优于 batch 和无补证 | 不是新年度 bank 的整周 LLM 实验；四个全球周不是已证明独立的天气过程 |
| 年度 bank / Stage C | 72/72 地区月；52,548 新原文；年度 common/values bank；12 日会话×9 条件=108 运行；288 selector 请求；24 评分组 | 每方法 864 注册、861 可结算、3 缺失；16 正例集中在 Chicago 2025-12-01；71 合法、217 非法回复；模型未超强程序 | 不是 16 独立事件；不能把无效回复全归于选择推理能力，也不能删除它们重排主榜 |
| C2 有限获取分支 | 6 父重建、6 原策略续跑、24 分支、36 两两比较 | 存在字段/特征/实际生效概率变化；同一全球日期且零正例 | 不是跨过程事件检出；不是 TAF 真实处理干预已经完成 |

来源：[S01–S04]；年度时点与角色见 [S10]。旧整周、C2 与年度 Stage C 的实际 bank、consumer、calendar 必须逐项从原 manifest 绑定，不凭名称推定相同。

Stage C 的代表性 Brier：F_COMMON 0.0072363，B11_COVERAGE 0.0077496，B11_BATCH 0.0080626，LLM_SELECTOR 0.0085666，F_BASE_ONLY 0.0085985，FOLLOW 0.0098354。LLM 对 F_BASE_ONLY 的平均改善约 0.0000319736，正例贡献为零；缺失结果敏感性界 [-0.0000576464, 0.0000339670] 跨零，它不是置信区间。[S02]

同样重要：FOLLOW 正例 Brier 约 0.2960，LLM 与 F_BASE_ONLY 约 0.4018。当前总体 Brier 的改善不能直接写成更强的极端事件发现能力；应同时解释自然日历总体分数、正负例贡献和过程支持，而不是改用仅正例主榜追求反转。[S02]

## 2. 对附件计划的合并裁决

### 2.1 保留且不重复建设

年度原文首次获取、两年度 bank、原整周引擎、正式 fork、六父有限分支、首轮 288 请求已经有交付。下一工单必须写“在新版本/新日历/新条件下补齐何种证据”，不能再次称“首次完成”。

v1 parser 已要求 query_order，已检查重复/未知 handle，并通过 strict_json 处理重复键；不能把“加上本来已有的检查”写作新修复。v1 对完整代码围栏的接受是现有版本行为，新 v2 可更严格，但旧回复按原版本判定。[S07]

### 2.2 将分散的 worker 建议合成一条生产链

最后发送许可、捕获长度/摘要、首次 reconcile 验证、持久化异常、失败后的恢复消费，应一次连通到 worker → ProductionSpoolBackend → coordinator → resource ledger。不能只修某个 batch-specific helper，却让真正的 API adapter 继续旁路。[S05,S06]

### 2.3 将接口输出格式统一为一个新版本

整合版推荐模型主输出使用一个字段：`{"query_order": [...]}`，版本 `selector_query_only.v2`。固定公共预测日程不再让模型生成不起作用的 forecast_handles。

若现有执行器必须接收两字段结构，由显式、冻结的 adapter 补 `forecast_handles=[]`，不交给模型、不改变预测槽/收费。另一种“模型保留两个字段且 forecast_handles 恒空”的方案可以成立，但只能作为另一个明确冻结的兼容版本，不能在同一次运行中自适应切换。选择此方案是减少无效输出维度的工程取舍，不是已验证的性能结论。

provider schema、提示说明、本地 parser、执行适配器来自同一合同源；动态 enum 只由该时刻可见目录产生。空目录不得生成空 enum 的非法 schema，应使用专门的空数组合同。query_order 表示有序意图，实际可执行前缀由预算、权限、缓存和截止控制，不能把“排名长度”混为“实际获取条数”。

### 2.4 合并而不累加预检额度

附件分别提出 12、24、48 请求及不同合法率阈值。整合版默认方案：**12 个真实天气形状的开发快照，一次冻结，一快照一请求，不重试；本地结构与 handle 合法性要求本批 12/12，安全/身份/捕获错误零容忍。** 这是严格的工程放行规则，不是总体可靠率的统计保证。

若论文确需识别“仅 response_format 的影响”，可在执行前改选“12 个相同输入 × text/schema 两条件 = 24 请求”的独立设计；同提示、同模型、同输入，仅输出模式不同。它替代上述默认预检，不是再加 24 或 48。接口整体同时改提示与 schema 时，应称组合接口修复，不声称纯 schema 因果效应。

发生安全/身份/泄漏问题立即停止；普通格式失败按预先冻结的完整预检计划记录，最终不放行大矩阵。不追加成功样本凑满合格数。

### 2.5 不把全部支线设为 H15 的前置条件

温度目标局部资格、动态 prompt、member lineage、DWD policy 属于温度出口的必要条件，不是 H15 CPU 对照的必要条件。原生 MM 的资产/时空/processor 资格可并行；新 VLM 运行另注册。内容寻址迁移先做到最小可复算切片，不先造一套大型分布式平台。

### 2.6 不把“模型必须选子集”“必须正增益”作为验收

空查、全查、固定排序都可能是合法策略。候选同费用不等于同信息，反之不同站名也不保证可利用的信息差。可区分性、可行性、实际信息效应、是否值得模型开销分别判断。若全读廉价且稳健，应保留为强基线，而不是涨价或隐藏信息制造主动性需求。

## 3. 必须进入下一次代码修复的具体问题

### 3.1 I01：发送边界、捕获与恢复是一条状态链

当前 `siliconflow_worker.deliver()` 仅入口检查 deadline，随后 claim、请求检查、intent 落盘，才调用 transport；transport 中还读凭据和准备请求。[S05] 合成时钟可使入口在截止前、实际假发送在截止后。历史 288 是否触发尚未证明。

新行为：完整 payload/请求/执行身份冻结后，在尽可能靠近网络调用的最终本地许可点，与 STOP 做可解释的原子排序；短锁不跨网络等待。记录 claim、permit、intent、收到、持久化，时间间隔使用单调钟，UTC 作锚。许可后的 STOP 不等于能撤回远端请求；未知远端执行不能承诺 exactly-once，更不能免费重发。

捕获问题不止字段命名：当前先读取最多 4,000,001 原始字节，再脱敏，最后按脱敏长度计算 complete。脱敏缩短时可把截断前缀错记完整；本次隔离探针已复现。[S05]

新 capture 至少记录 raw 捕获字节数/读取上限/截断或 EOF 证据、captured-prefix hash、完整时才允许存在的 full-body hash、脱敏存储字节 hash、解码状态。解析前校验可信 receipt 绑定的存储字节摘要；可读文本不能替代原字节身份。单纯在同一可修改 JSON 内保存 body 与其自算 hash 不等于防恶意篡改，还需绑定可信上层 receipt。旧 capture 无完整证据时保持 legacy/unavailable，不补造。

首次 reconcile 当前检查 request hash/status/complete，却不核保存 body 的预期摘要；要补齐首结算验证，而不是只靠后来已存在的 worker receipt 发现冲突。[S05]

恢复问题：response 落盘失败留下 failure；离线 reconcile 可重建 response；但 production.resolve 优先看到 failure 就抛错。[S06] 新状态允许增加不可变 recovery receipt，绑定原 failure/capture/request/execution 和新 response。实际消费者验证后只结算一次；旧 failure 不删，预算不重置。迟到恢复可以修账务，不回溯改写当时已经结算的预测采用状态。

**必须 red→green 的案例**：claim/凭据/持久化中到期、permit 前 STOP、重复 worker、发出前失败、发出后无捕获、正常/超长/脱敏缩短/非法 UTF-8、错模型和 usage、首次摘要不匹配、response 写失败后离线恢复、重复恢复、恢复后真实 consumer/ledger 无重复扣费、迟到恢复不回溯改变成绩。

### 3.2 I02：C2 报告不能靠现存文件倒推分母

`analyze_branches.py` 对缺 FORMAL_REPORT 使用 continue，passed 主要继承 execution 和 shared_wakeup。[S08] 隔离完整 6×4 树删除一份报告后，比较从 36 降到 33 仍 passed；删除全部报告后比较为 0 仍 passed。缺 trace 会缩小共享交集。此结果只证明派生分析器边界，不证明已绕过 score_formal 或历史实际缺文件。

新入口先从冻结 roster 得到 parent/rule/alias/实际尝试/终态/剩余机会集合，再核完整性。报告必须分 registered、attempted、completed、qualified、scored、comparison 数。别名计逻辑分支与唯一执行两种数，不能制造额外独立重复。

需要 trace 的集合由正式 calls 及其 head/调用类型定义；未产生 call 的合法 fallback 无需伪造 trace，但已产生 call 缺 trace 必须报缺口。避免以 opportunity_id 字典隐式覆盖多次调用，使用 call_id，并明确最后生效预测的 lineage。缺失、失败、不可行均留在注册分母，不宣告完整排名。

正常完整输入应数值等价；异常输入应明确 incomplete / qualified_partial / failed，不以空集合 all() 真值放行。formal-bound、legacy-replay、engineering-diagnostic 必须分标签；仅正式资格进入正式主表。

### 3.3 I02：相同 bank 文件不等于相同预测流程

Stage C paired() 只用“是否 F_COMMON”判断 bank_difference_involved，因而 FOLLOW 与 LLM 被标记为 false。[S09] 数字损失本身未因此算错，但解释标签不足。

每个方法绑定 `consumer_kind + consumer_code_hash + bank_hash/null + feature_schema + calibration_mode + baseline_mapping + schedule + admission_protocol`。未消费的 bank 文件不能充当同后端证据。pair 输出 changed_components、same_predictor、same_calendar、same_budget_policy、same_time_basis；报告不再用一个布尔值代替全部比较身份。

### 3.4 I04：remaining new acquisition 语义显式版本化

当前 residual plan 记录 already_cached/already_requested，但 eligible 仅使用 related/available。[S11] 因而 first/second 指的是第几个相关槽，不一定是新增获取；未来更多缓存的父状态会退化为 no-op。

保留 v1 重放；新增 v2 的 `none / first_new / second_new / all_new`，公开列出 all_related、remaining_new、excluded_cached/requested/unavailable。付款者、shared/private 权限、已失败但已消费 attempt 等继续遵守原合同，不能为获得“新增”而自动重试。第二条不存在要明确状态，不换第三个父样本补数。

`no_further_paid_query` 是停止后续付费查询，不是停止整会话，也不是原策略 no-op 续跑。继续共同预报更新、程序预测和完整剩余机会结算。[S11]

### 3.5 P01：温度缺口只阻塞对应路径

`event_probability` 在获取目标实际消费的变量后，仍调用验证 min/max 都完整的 validate_products；raw max-only/min-only 任务可能被无关变量拒绝。[S12] 应分 raw target-local validator 与 EMOS/ECC full-product validator，后者合理的完整性要求不放松。

动态目标必须生成一致 prompt；多日路径概率需原 issue/member IDs/ensemble/order/day support 证明 lineage，数组等长不够。缺原生身份时标 unavailable，不人工编序号冒充证明。上述未独立进行真实温度影响扫描，不声称旧温度成绩已错，更不把它算作 H15 错误。

## 4. 合并执行路线：有限批次，而不是循环写下一份计划

### 批次 A：工程闭环与有限历史影响核查（I00—I06）

默认本地 CPU、既有依赖/已暴露资料；不训练、不全量重跑、不新 API/GPU、不新增气象下载、不打开 Bay 或其他未读确认。

I00 记录真实 HEAD/dirty/index、结果三轨、保护清单、消费身份、暴露和权限。先读适用 AGENTS、LATEST_PROGRESS_V12、结果与下一门槛。若 HEAD 已前进先做精确差异，不 reset。

CURRENT_PHASE 当前仍以 v10 开头。[S13] 将其变成短导航入口，历史移链接。字段用 reviewed_baseline_sha / result_manifest，不要求文件包含自身所在提交的完整哈希而造成自指循环；实际 HEAD 由运行时 receipt 记录。旧授权窗口文字不能继承成新权限。

将 750 与 628 按唯一 nodeid 对账，不宣称减少 122，也不把多份探针计数相加。重复/重命名/删除原因/额外 test scope/未运行/缺 fixture 分别列明。

I01—I04 实施上节四组局部修复；每项先写当前版本失败的生产路径测试。I05 完成当前唯一测试范围、定向故障矩阵和最小真实复算切片。历史影响核查只读已有原物，不新生成回复；每项分 unchanged/affected/unavailable。受影响时新建更正派生表，不覆写原分数。缺 AFS 资产时精确列路径、ID、hash及受阻检查，其余离线工作继续。

I06 首轮时点审计按公开确定的有限子集执行；默认从原 12 个开发日会话各 hash-fixed 选 2 个机会，最多 24 目标，不按 Y/loss 取样。资料不足留缺口，不换优样本。全日历审计属于下一批。该 24 是新建议的计算上限，不是统计效力承诺。

**批次 A 输出**：BASELINE、保护清单、TEST_SCOPE_DIFF、实际 code diff、红绿回归、CAPTURE/RECOVERY 合同、QUERY_ONLY_V2 合同、残余查询 v2、ANALYSIS_ADMISSION、COMPARISON_PROVENANCE、历史 IMPACT、有限 CLOCK_AUDIT、后续精确 roster 草案和 STOP_RECEIPT。完成后停止；不自动触发批次 B/C。

### 批次 B：现有数据上的科学桥接（I06—I09）

#### I06：先保持权重，区分三种时间变化

年度 fit 确实使用 cutoff−600s，应用使用实际公共预测槽。[S10] 这首先是已声明的训练/部署分布差异，不自动等于泄漏或解释全部退化。

对同一未来目标、同一冻结 bank 建立：
1. 早时点合法且实际披露的信息；
2. 保持同一信息身份，在较晚合法时点更新 age/lead 的诊断视图；
3. 较晚时点实际可得且按权限实际披露的新资料、当前 TAF 与缓存。

分别量化版本变化、可见集合变化、age、feature、logit/probability、adoption 和损失。潜在可查询不等于已读取。不能把晚资料回填早时点；也不能在旧响应上改时间后称作原实验。

#### I07：必须补年度 bank 的完整自然日历程序表

保留原 3 地区×4 周×7 日×2 阈值，首层五臂：FOLLOW、F_COMMON、F_BASE_ONLY、B11_BATCH、B11_COVERAGE。新年度 raw bank 按新 run identity 执行；旧整周值保留为匹配参照，不重启旧 launcher。

若维持原 roster，程序工作量为 840 个方法轨迹、12,096 方法无关机会、60,480 方法行；以精确 ID 集合而不是预填计数验收。保持原 daily reset、48 查询/单阈值日、权限、公共槽、采纳协议、缓存跨日边界及 missing mask。变成长周不断缓存是另一个问题，不能随手混入。

缓存复用需 input+consumer+bank+schema+protocol+outcome+scorer 内容身份一致。不能只因路径或名称相同复用。运行五臂无需 LLM，也无需重取已完成年度原文。

这一步回答：旧整周较强的补证信号是否在年度后端、完整日历仍存在；Stage C 首日结果是否受日历/正例结构影响。不能将旧整周 .0339 与新首日 .00775 直接当训练改进。

#### I08：候选可区分性与程序强对照

先 label-free census，再 evaluator-only 有限作用诊断。公开统计成本、延迟、覆盖、站点关系、age、可用性、缓存、公开可靠性；不把未来值或事后最优编码进目录、默认顺序或提示。

3 候选理论有 8 个无序子集、16 个无重复有序部分列表（含空）。不是都可行，也不是每父必须全部执行。先按预算/权限/截止剪枝，再判断真实终态等价。事后最优仅对这个有限可行路径集合成立，不能拼接各目标单独最优为一个不可行共享 oracle，不能称开放世界预测上界。

主程序基线先复用 no-query、batch、coverage；补固定站序/round-robin、公开 risk-age、固定种子随机。配额与共享 2×2 仍在同一个 selector 下比较；策略比较则固定 B11。source-query budget 与总成本向量分别匹配/报告。

one-step expected loss、two-step lookahead 只作条件性增强：必须有训练期条件分布或折外 value model，输入只能用当时公开信息，计算时间计费。直接枚举已知未来 Y 得到的是 evaluator oracle，不是 expected-value 在线程序。先不引入重模型/RL。

原 71 合法动作可做 posthoc schedule replay，分离生成开销与动作日程；冻结随机/risk/coverage 的 query-count 对照。它不是可部署方法，不以零时延重放冒充真实模型的实际端到端成绩。

#### I09：重拟合是条件任务，不是默认任务

先给 drift/evidence/positive-block 诊断和明确决策；实质问题成立才冻结新 bank。优先仅一个 slot-aligned values 方案；若同信息 values 持续劣于 common，再保留一个 common-anchored residual 候选。不要一次全扫四个银行×全部策略×全部阈值。

2023 内部分块训练/选择；2024 Jan–Nov 最终校准；2024 Dec 保持排除；2025 已暴露开发；未读确认仍封闭。每物理目标在时点/阈值/证据子集视图上的总权重规则明确。normalizer、clip、缺失编码也只在训练角色拟合。当前 raw 概率为 primary，calibration 独立 secondary；保证 P(vis<1km)≤P(vis<5km)。

若最终校准资料被用于选择 backend/hyperparameter，就记录其角色变化并设新未用校准/确认范围，不能沿用“最终独立校准”表述。新 bank 必须在相同完整 roster 的并列表中比较；旧 bank、分数和父状态绝不原位替换。

### 批次 C：C2 从六父工程链到跨状态机制（I10）

先用固定开发日历/公开来源状态 census，覆盖 full/partial/none TAF、当前/订正/撤回、缺报/删失/冲突、共享/私有、近截止和资源耗尽。索引缺覆盖叫 unknown，不自动叫无产品。未来 Y/loss/方法赢家不得参与新的代表性父选择。

默认建议上限：12 父、12 原策略续跑、48 个获取分支；TAF 处理子轨最多 12 个同原文配对。先冻结最终精确 roster；不足不替换，不把数字当独立过程数。合成故障测试不计真实样本。若另做已知事件富集诊断，明确 outcome-informed、非总体频率估计，不混进连续自然主轨和确认。

每父绑定整个 prefix：data/bank/consumer、clock、spent/reserved、cache与权限、pending、baseline版本、override、剩余机会 U_parent。新 bank 从会话起点重建自己的父，不能改旧 checkpoint bank。无干预原策略续跑必须匹配；它与 no_further_paid_query 分支不是同一对照。

三种量分开：
- **内容机制**：同时间、同共同基线、同合法证据，改变某字段处理，观察 feature/probability；诊断性等时视图不能冒充可执行免费获取。
- **获取总效应**：真实 GET 同时产生等待、age、免费 TAF 更新、费用与采纳变化，按真实时序结算。
- **整个残余会话效应**：初始干预后所有分支采用同一个冻结 continuation policy γ，统计对其他目标的预算挤占、共享收益与全部 U_parent 损失。原有限“以后不再付费”族继续单列；新 continuation 族使用新合同。

TAF 原文共同免费提供不变，固定同一原文，native parser/structured processor 等输出通过显式 adapter 成为 F 的实际输入，再比较处理效应与成本。模型处理须新授权、独立角色，不借 query-only 名额。仅改变最终 E 标签而 F 未消费时，F 不变是正确负控制。

输出逐边 source→receipt→native field→feature→candidate→admission→effective forecast→outcome→loss，带全部失败/no-op/迟到。有限最优、E 逻辑可达性与 F 未来预测优势不得混写；不画精确相加为100%的因果份额图，因为处理、时间和策略可能有交互。

### 批次 D：真实接口资格与一次有界模型比较（I11—I12）

I11 的小额真实预检只依赖工程闭环和已冻结开发输入，可以与程序科学分析并行；不必等待温度/16灾种。反之，小额预检通过不自动启动大矩阵。

默认 12 请求方案见 2.4。具体 endpoint/model、generation、schema、完整消息、call IDs、每次与整批 token/费用上限、deadline、停止规则、失败回退均冻结。模型 ID 返回一致不等于掌握提供方底层权重版本；未知即记录。

SiliconFlow 官方文档区分 json_object 和 json_schema，并要求处理截断和支持变化。[E01,E02] 文档不能替代具体路由、空目录、枚举、长输入的实际资格；本地 validator 始终有效。任何供应方 SDK 自动重试必须显式关闭或被单次 dispatch 合同控制。

I12 开启条件：可靠接口、冻结后端及 calendar、实际非退化的合法动作空间、强程序参照、C2 基本消费证据、预算和完整分母。这里不要求 LLM 必须赢或最优动作必须随样本切换；但若所有动作完全等价且大矩阵不会回答新问题，记录 No-Go 并收口，而不是付费重复。

建议最多 12 日×24 calls=288 个新 selector 请求、一个模型、一个 query-only 角色。是否沿用原 12 日或使用新的元数据固定日历须执行前选定；沿用原日历只算接口开发比较。所有程序 arms 同 backend、权限、source universe、forecast slots、adoption、outcome。

完整漏斗：registered→attempted→HTTP/capture→schema→legal handles→planned query→actual acquisition→qualified product→feature→probability→timely adoption→loss。合法空选与非法 fallback 分开；无效仍消耗调用与时间，主表不删。真实费用未知保留 unknown，token 不直接充当金额，HTTP wall time 不称 provider compute。

接口通过但仍 all/none，是有效行为结果；模型无收益，也是允许的实验出口。不能换模型、增样本或改 prompt 直到赢。安全/合同失效按登记停止并保留所有未尝试机会，不做成功补样。

### 批次 E：双确认与可发布证据（I13—I14）

确认草案可提前做，最终方法/比较/统计冻结必须在任何未读确认资料暴露前。协议 A 检验同后端策略/模型增量；协议 B 检验 C2 字段到会话损失机制是否在新过程复现。共用 calendar 时同时冻结；不同时冻结则用隔离资料。

冻结 primary comparison、阈值族、process/dependency block、missing/failure规则、最大连续日历、停止/支持不足处理、多重比较与区间方法。单个 Bay 2025-02-17—23 周只承担窄确认，不能保证正例、多季节或地区效力。

正式样本量由开发期过程间变异、最低有意义效应和预定精度预算决定；小时、两阈值、分支、重复请求都不增加独立过程数。有限块下报告宽区间或无法可靠估计；缺失标签敏感性与抽样不确定性分开。共享/嵌套标签可行值有约束时，独立逐项最坏界至多是保守界，不称 sharp joint bound。

raw natural-calendar Brier 保持主分，正负贡献、尾部命中/虚警/提前量在预定阈值下作解释。零正例时不编召回/AUC；按原连续日历规则结束，不追加到显著。方法可以取得负结果，工程/benchmark依然可按准确限定结论发布。

可重放切片至少覆盖：一个原非法回复、一个合法 none、一个合法查询、一个 C2 生效概率变化、一个失败恢复。raw资产（许可允许时）/输入/consumer/bank/schema/journal/ledger/outcome/scorer/独立算术齐全。原 source replay 与当前迁移 replay 分报告；缺依赖/再分发许可明确。文件可移动不自动获得原 formal qualification，迁移清单采用角色+内容hash+relocation mapping，不改旧绝对路径或 STOP。

## 5. C3 / E/F/D/MM 与 X09 支线的具体出口

### P01 温度 F-only

先完成 target-local raw 与完整 ECC 分离、动态 prompt 与 evaluator 同 contract、原 issue/member lineage、UTC day support、细分 DWD outcome policy。旧 UTC/EMOS/ECC 已有部分不重做。无历史合法补充证据时明确 F-only，不靠最终 DWD 档案加固定延迟改成历史收费补证。温度 lineage 受阻不阻塞 H15。

### P02 第二条主动物理链

H07 降水与 H08 水文先做 readiness 对照，按数据合同成熟度而非结果选择一条。H07 核累计窗/网格空间支持/单位/QC/issue-valid-available/outcome；H08 核流量与水位、瞬时/均值、断面、调控、成员身份、阈值与同期来源可得性。完成一个同目标 baseline+supplementary+outcome+cost+as-of 主动链比十六类浅接口更重要。

### P03 原生多模态

可先 CPU 建原生 image asset→issue/available→时空 ROI→processor输入→payload/token→输出角色→F消费者路径。结构化数值、专业派生产品与原图各自信息范围/成本公开；等预算不必假装等信息。已有图片/旧 MM 实验不能重新列“从未开始”，但新的气象原图任务仍需自己的资格。VLM 是否真消费像素和是否带来增量是两道门，不以“能发送图片”替代科学证据。

### P04 行动、X09、前瞻

行动 D 先 Scenario Card 与强程序 optimizer，固定天气与证据改变准备耗时/容量/可逆性/错失代价。硬不变量：同 weather+evidence+predictor，改变 DecisionSpec 时 F 请求与概率不变；acquisition 可以依行动可行性变化。结果只称研究场景准备收益，不称真实减灾效果。

X09 保留同信息单目标/联合目标推理问题，分别按每请求上限和每目标组总预算匹配；它不是 query selector 的改名。

前瞻 first_seen 可独立做采集资格；只有事前持久化预测、后取得未来结果才能计 prospective 成绩。历史发行/有效时刻、声明档案延迟、可证明历史发布、实测 first_seen 四类分别标注。未执行前瞻也能推进冻结的未读历史确认，不必等待真实未来灾害。

## 6. 统一指标、对照与贡献表

记损失改善为 Δ=Loss(reference)−Loss(method)，正表示改善。至少拆三类对照：

| 问题 | 推荐对照 | 必须固定 | 注意 |
|---|---|---|---|
| 后端能力 | FOLLOW→F_COMMON；同信息 common→values-empty | 目标、共同信息、日历、outcome | consumer 可能不同，不是纯 acquisition |
| 补充获取总价值 | 同 values 的 F_BASE_ONLY→B11_BATCH | 后端、目标、预算协议、预测/采纳规则 | 自然时间下含等待与版本更新；纯内容另做同时间诊断 |
| 选择/分配价值 | B11_BATCH→B11_COVERAGE/LLM | 同后端、预算与共享规则、source universe | 模型总成本另计，不能只配 query 数 |
| C1 共享机制 | 固定 selector 的 B00/B01/B10/B11 | backend、calendar、动作来源与总预算定义 | 共享收益、权限差异、预算分配分别解释 |
| C2 机制 | 同父合法 GET/PROCESS/WAIT 对照 | 父状态、后续策略、全 U_parent | 共享挤占与失败也进分母 |

分开报告 Forecast、Evidence、Acquisition、Action、Runtime，不默认压成单一总分。多输出阈值保证一致性。缓存共享、费用、实际读到和实际消费均有可核记录；supported/refuted/undetermined/inconsistent 不等于预测正确。

当前最稳妥的论文方向是：**在动态共同专业信息之上，以可追溯、时间受限、共享预算的多目标环境，检验追加取证与处理何时产生值得成本且可归因的增量价值；基准允许并揭示强程序胜过模型、信息到达过迟、处理改善不转化为预测改善等负结果。**

贡献证据递进：C1=共享资源下真实可行的分配问题与强对照；C2=同父状态、可执行反事实和字段到全会话损失链；C3=同一评测原则在第二物理过程/原生模态上的重复与差异。不是“数据集多”“测试多”“API多”本身，也不预先保证相对所有已有论文的独创性；本次没有重新做完整相关工作检索。

## 7. 全局执行与收尾合同

每个工单输出：status（proposed/running/completed/failed/blocked/not_needed）、范围、实际命令/退出码/唯一nodeid、输入与源码hash、产生的实际diff、red/green与未运行原因、cost/failure、历史impact、下一道条件。科学资格另设，代码 completed 不等于独立确认 passed。

资料缺失时不补造，网络受限时不自动打开下载；缺确认资料不去读确认索引挑样本。仅当前明确授权范围可以执行；旧 288+2 请求、旧云任务和 STOP 均消费完毕，不复用。

新代码测试在当前源码运行；冻结历史 source/results 不可覆盖。正常输入损失等价，必要更正新建版本并给 lineage。修复一个问题后不重复生成同一份长计划；只更新 BACKLOG 状态、IMPACT 和一页 NEXT_ACTION。

拟合、模型调用、云作业、线上采集、推送、确认暴露分别需要对应授权和 gate。主线中 API blocked 不应使离线 census、代码测试、原始算术、第二链合同草案全部停摆。

首批完成即停止，输出按类别的资源统计：repository_reads、weather_network_requests、model_requests、GPU、training、confirmation_payload_reads；不能执行过仓库联网却宣称全部 network=0。

## 8. 最小可发布切片与停止规则

不必等全 16 类、所有模态和所有行动都做完才能得到有效交付。可发布切片应至少拥有一个成熟 H15 主轨、同后端强基线、多状态 C2、清晰接口/成本失败表、可重放证据和与结论相称的确认支持。第二链增加的是广度；如未完成，明确范围而不把目录当成果。

**核心停止规则**：工程缺口未闭合则禁新付费运行；动作无可区分作用则不扩大 selector；存在分布问题则先定位而非堆模型；确认支持不足则报告不足，不补样到赢；负结果可以完成实验，但不能伪造为正结论。

交付包还包含 START_HERE_CODEX_CN.md、BACKLOG.json、SOURCE_CROSSWALK.md/json、SOURCES.json、ATTACHMENT_MANIFEST.json、验证回执和本包自检。它是后续执行规格，不是已实施补丁。

## 来源索引

- [S01] LATEST_PROGRESS_V12_CN.md：https://github.com/sisuolv/disastertrace-benchmark/blob/1eba36dd272c72573d1309c78d45dbe97dd8af12/LATEST_PROGRESS_V12_CN.md
- [S02] plans/v12_execution_20260915_01/FINDINGS_AND_NEXT_GATES_CN.md：https://github.com/sisuolv/disastertrace-benchmark/blob/1eba36dd272c72573d1309c78d45dbe97dd8af12/plans/v12_execution_20260915_01/FINDINGS_AND_NEXT_GATES_CN.md
- [S03] plans/v12_execution_20260915_01/FULLWEEK_FINDINGS_CN.md：https://github.com/sisuolv/disastertrace-benchmark/blob/1eba36dd272c72573d1309c78d45dbe97dd8af12/plans/v12_execution_20260915_01/FULLWEEK_FINDINGS_CN.md
- [S04] plans/v12_execution_20260915_01/C2_ENGINEERING_REPORT_CN.md：https://github.com/sisuolv/disastertrace-benchmark/blob/1eba36dd272c72573d1309c78d45dbe97dd8af12/plans/v12_execution_20260915_01/C2_ENGINEERING_REPORT_CN.md
- [S05] plans/v12_execution_20260915_01/siliconflow_worker.py：https://github.com/sisuolv/disastertrace-benchmark/blob/1eba36dd272c72573d1309c78d45dbe97dd8af12/plans/v12_execution_20260915_01/siliconflow_worker.py
- [S06] disastertrace-starter/src/disastertrace/monitoring_v1/production.py：https://github.com/sisuolv/disastertrace-benchmark/blob/1eba36dd272c72573d1309c78d45dbe97dd8af12/disastertrace-starter/src/disastertrace/monitoring_v1/production.py
- [S07] disastertrace-starter/src/disastertrace/monitoring_v1/selection.py：https://github.com/sisuolv/disastertrace-benchmark/blob/1eba36dd272c72573d1309c78d45dbe97dd8af12/disastertrace-starter/src/disastertrace/monitoring_v1/selection.py
- [S08] plans/v12_execution_20260915_01/analyze_branches.py：https://github.com/sisuolv/disastertrace-benchmark/blob/1eba36dd272c72573d1309c78d45dbe97dd8af12/plans/v12_execution_20260915_01/analyze_branches.py
- [S09] plans/v12_execution_20260915_01/analyze_stage_c.py：https://github.com/sisuolv/disastertrace-benchmark/blob/1eba36dd272c72573d1309c78d45dbe97dd8af12/plans/v12_execution_20260915_01/analyze_stage_c.py
- [S10] plans/v12_execution_20260915_01/fit_annual.py：https://github.com/sisuolv/disastertrace-benchmark/blob/1eba36dd272c72573d1309c78d45dbe97dd8af12/plans/v12_execution_20260915_01/fit_annual.py
- [S11] disastertrace-starter/src/disastertrace/monitoring_v1/residual_query_plan.py：https://github.com/sisuolv/disastertrace-benchmark/blob/1eba36dd272c72573d1309c78d45dbe97dd8af12/disastertrace-starter/src/disastertrace/monitoring_v1/residual_query_plan.py
- [S12] disastertrace-starter/src/disastertrace/monitoring_v1/temperature_postprocess.py：https://github.com/sisuolv/disastertrace-benchmark/blob/1eba36dd272c72573d1309c78d45dbe97dd8af12/disastertrace-starter/src/disastertrace/monitoring_v1/temperature_postprocess.py
- [S13] disastertrace-starter/CURRENT_PHASE.md：https://github.com/sisuolv/disastertrace-benchmark/blob/1eba36dd272c72573d1309c78d45dbe97dd8af12/disastertrace-starter/CURRENT_PHASE.md
- [S14] connected_GitHub_branch_read：https://api.github.com/repos/sisuolv/disastertrace-benchmark/branches/next-phase-v1
- [E01] official_docs_read_not_live_provider_qualification：https://docs.siliconflow.com/cn/userguide/guides/structured_outputs
- [E02] official_docs_read_not_live_provider_qualification：https://docs.siliconflow.com/cn/userguide/guides/json-mode_struct
