# 下一批执行规格：阶段 A（待复核，未启动）

版本：2026-09-15。关联整体计划：`OVERALL_PLAN_CN.md`。

本文件是供用户审阅的具体范围，不是已消费的 launcher。`execution_authorized=false`；没有新 claim、云任务、下载或模型请求。原 v11 批次按原注册继续，核查时不得重复启动。

## 1. 这一批必须回答什么

1. 原整周实验在完整七天上，后端、补证和策略各自表现如何，是否有事件期退化？
2. E 汇总和年度失败摘要哪些是派生计数问题，实际影响哪些记录，哪些 F 数值保持不变？
3. C2 使用完整当前产品目录后，任务状态是否仍全 full，哪些候选动作真正改变 F 消费字段？
4. 现有冻结后端能否从同一个真实父状态恢复并执行合法分支？
5. 全年数据下一次准确还需获取哪些唯一原文/缺片，其范围和角色能否冻结？

本批不要求模型获胜，也不以“750 个测试再次通过”代替上述答案。

## 2. 范围与资源

| 项目 | 推荐首批范围 |
|---|---|
| 实验资料 | 既有 12 个已暴露区域周、原 v11 回执；原生月样例只作获取/构建质量核查 |
| 生产代码 | 受影响的汇总、来源编译、最小校验与现有 checkpoint 接线；新输出目录 |
| 整周推理重跑 | 0；原 840 条继续原流程，完成后消费日志 |
| 新来源 HTTP | 0；只登记缺片与年度唯一原文清单 |
| 新被测模型/API | 0；不调用余额探针，不执行审查包中的启动指令 |
| GPU | 0；首批不需要推理 |
| 新拟合/校准 | 0；使用已经冻结的后端作工程验证 |
| 确认数据 | 不打开 Bay 2025-02-17..23 或其他未读确认载荷 |
| 新 CPU 资源 | CCI 控制；需要时最多额外 1 个 16 CPU/64 GiB ACP 任务，实际进程数 6—12，根据峰值内存确定 |
| 并行约束 | 算入仍运行的 v11 作业，不超过实测配额；一个会话一个 owner |
| 时间安排 | 约 1—2 个工作日；单次后台范围上限建议 12h，超时保留前缀和原因，不自动扩展 |

第一阶段可先提交不依赖整周终态的代码/来源交付；整周末片或审计未完成时保留 pending。不要为等一张总表让全部工作停等，也不要用部分结果提前选方法。

## 3. 任务顺序、产物与验收

### W00.refresh：建立执行基线与当前入口

依赖：用户批准本批。预计 20—40 分钟，不新增实验。

读取：真实远端分支、开发源/索引哈希、原 `DASHBOARD_02.json`、`STATUS_03.json`、COMPLETE/EXIT、平台任务状态，以及可能新出现的 fullweek/analysis/BATCH 终态。

交付：

- `EXECUTION_BASELINE.json`：published / development / live 三种身份与实际观察时间。
- `PROTECTED_INPUTS.json`、`CONTINUATION_ROSTER.json`：原任务和冻结文件，不用文件 glob 定义科学分母。
- 更新当前入口指向 v11 的真实终态/进行中状态，再链接本次执行目录；历史内容保留。

验收：不 reset Git，不修改冻结输入，不重复提交；明确区分 worker 完成、正式审计、科学报告和来源阶段失败。原 annual `passed=false` 不能被解释成 fullweek 一定失败，也不能被总看板吞掉。

### W07.e_summary：修订 E 枚举与真实影响

依赖：W00。预计 1—2 小时；不要求所有整周记录已齐。

相关位置：`fullweek.py::audit`、`monitoring_v1/evidence.py`、`policies.py`。在新开发/派生路径实现，不热改 `fullweek_02/source` 或原自动审计。

先写生产路径回归：supported/refuted/undetermined/inconsistent 各一条，可判定为 2；未知状态显式报错/隔离；缺 frame 单列。不要全仓库替换 entailed，因为旧 schema 可能有不同合法词表。

从原 frames/ROWS 生成新报告：状态直方图、旧计数、新计数、差值及受影响机会 ID。E 截止状态与模型答题正确率分开，缺未来 Y 不删除可观测 E。

验收：`determined=supported+refuted`；全状态加缺 frame 等于登记 E 分母；F 概率、Y、roster、结果掩膜、loss/Brier 数值及原文件哈希不变。尚缺行标 not_evaluated，不能填 0 影响。

产物：`E_STATUS_SUMMARY_IMPACT.json`、`E_STATUS_RECOUNT.json`、定向回归回执。

### W06.sample_summary：修复失败分支，登记精确缺口

依赖：W00。预计 1 小时；只用 mock 或已有字节。

相关位置：`annual_catalogs.py::execute`。修 sample 失败时重复拼接，增加唯一 unit 与注册集合检查。

验收例：

- 三个 sample 中 2 成功、1 失败：仅 3 条结果、2 complete、1 failed、69 not_attempted；实际只调用三个样例。
- 三个 sample 全通过、后续 1 月失败：72 个唯一结果、71 complete；不误判为前一项 bug。
- completed + failed + not_attempted 等于完整注册集合，HTTP attempts 与逻辑片/月份分别统计。

只读核对 KORD/2023-01 原 429 和 timeout，保留同月五片；生成 `MISSING_SLICE_RECOVERY_PROPOSAL.json`。有界建议为最多两个新 HTTP attempts、尊重 Retry-After、单请求超时与字节上限，具体参数引用原请求；这是下一采集批的提案，本批不发送。

月样例已完成，不重跑。按原产品 ID/版本与已有缓存生成 `ANNUAL_NATIVE_INVENTORY.json`；没有字节的对象只按原身份去重，获取后再做内容去重，不能凭未知 hash 宣称同内容。

产物必须保留实际 catalog/native/decoded/join/role/fit 各层；原失败 RESULT 不变。

### W01.bank_guard：校准银行最小准入修复

依赖：W00。可与 W07/W06 并行准备，合并后统一回归。

相关位置：`monitoring_fixed_v1/native_feature.py::validate_feature_bank`、现有 `apply_monotone` 消费者。

增加严格有限非布尔数值、`0<=value<=1`、输入域顺序/重叠和边界规则。保留合法稀疏间隙及原外推语义；不通过重排、裁剪或强迫覆盖整个 [0,1] 偷改旧映射。

在实际 `NativeFeaturePredictor` 入口验证，不能仅运行审查者 AST 探针。扫描实际使用 calibrated 模式的银行；raw 轨不因这一问题重跑。列 unchanged/affected/not_evaluated。

温度 raw/ECC 的小修可作为相同批次的独立可选项；精确温度目标、成员谱系、DWD 扩展与 API 原子恢复不进入本批主线完成条件。

### W07.closeout：完整周结果与配对解释

依赖：W07.e_summary、原 fullweek 全量审计实际完成。预计 CPU 复算耗时以原回执为准；不二次执行预测器。

原五臂：FOLLOW、F_COMMON、F_BASE_ONLY、B11_BATCH、B11_COVERAGE。保留 48 queries/每单阈值日会话、day reset、lead 1h、base-bound、1ms 程序/持久化情景。它不是跨日一周持续 agent。

先核 exact IDs：168 日条件、840 轨迹、12,096 方法无关机会、60,480 方法行；未完成/失败和天气结果缺失分开。不把预检 360 行累加进去。

保持原正式比较合同和原分数。在新派生报告中把消费者分为 FOLLOW、common、values 三类；原 FOLLOW 所携带的 invariant bank 不解释成真实 values 消费。

五个方法的十个唯一配对均可由已审核原行计算，重点呈现：

1. FOLLOW→F_COMMON；
2. F_COMMON→F_BASE_ONLY；
3. F_BASE_ONLY→B11_BATCH；
4. F_BASE_ONLY→B11_COVERAGE；
5. B11_BATCH→B11_COVERAGE；
6. F_COMMON→B11_BATCH/COVERAGE。

这十个配对是已暴露开发数据上的描述性补充，不伪装成原预注册或确认性多重检验。

报每阈值总体、global week、region、region-week、region-day、正/负例条件损失和可加贡献、最差块、变化预测数、查询/等待/失败/回退。缺失补全界与置信区间分开。四个 global weeks 不进行逐小时“独立” bootstrap。

验收：新旧 F 算术一致，E 修订差值可追到原行；所有配对的目标/参考/掩膜一致；同后端和跨后端明确。若原审计失败，只在新范围定位和修复相应派生层；不清除原失败或重启原 launcher。

产物：`FULLWEEK_FINAL_ROSTER.json`、`FULLWEEK_PAIRED_EFFECTS.json`、`FULLWEEK_FINDINGS_CN.md`。

### W11.universe：完整来源与 C2 两类任务

依赖：W00。使用原 12 个已暴露区域周，独立于全年原文和拟合。

从 `NATIVE_PRODUCT_INDEX`、原始回执及会话披露规则重建 as_of 宇宙。先确定可见版本，再选择当前版本，再判断覆盖。原 `baseline_candidates` 只作差异比较，不能当唯一来源。

固定完整日历，不按 F 标签/模型失败挑时间。普查 active/full、partial/no-coverage、CNL/NIL、unparsed、conflict、no-product、订正/替代和等价别名。保留全部普通 full 和不可用机会；2024 月样例只提供已完成质量证据，不将其未来标签用于新 C2 难度设计。

将原 144 题标为 supplied-packet sanity。新 current-product E 另建 task ID，记录原/新资料集合、可见版本、答案变化和影响原因。不能直接重命名原题并宣称旧参考全错。

建立 `E_FIELD_DEPENDENCY.json`：每题的公开资产、参考种类、支持假设、可见范围、归约版本、干预字段、F 特征键与无传播情形。明确 TAF 处理与 METAR 获取两组。

验收例：旧覆盖产品 + 新不覆盖产品、新 CNL、同刻异义冲突、等义镜像、缺报/删失；这些工程反例单列，不计真实样本。完整生产编译器需要通过，不能只测 provider helper。

产物：`SOURCE_UNIVERSE_MANIFEST.json`、`C2_UNIVERSE_IMPACT.json`、`C2_STATE_CENSUS.json`、`E_FIELD_DEPENDENCY.json`。

### W11.branch_engineering：最多六个真实父状态的恢复/分支

依赖：W11.universe、对应原 parent 日会话完成；不要求年度强后端已拟合。

选择规则在看分支结果前冻结：在原 72 个 noon 目标引用中，每个区域×阈值按原 week/date/opportunity_id 升序取第一个引用，最多六个；按真实 checkpoint 去重。不因某个前缀不可行而换一个更有利前缀，保留失败/不适用原因。原后端/银行与原来源情景保持。

先做不干预恢复：科学状态、公开输入、预算与后续预测相同。然后最多四条原规则分支，合计不超过 24 个工程分支；别名分支只记别名，不重复算独立实验。

首个工程合同明确为有限残余查询计划：

- 冻结该引用对应的 eligible query 集合和公开排序；记录已取/不可取者，不按隐藏响应或未来 Y 排序。
- 四规则是 no further paid query、first、second、all remaining（均相对于同一冻结集合）。
- first/second/all 按注册顺序完成该计划后也停止新付费查询。所有分支继续共同预报、原公共预测日程和日会话剩余目标。
- pending 按既有串行规则共享地完成一次，再记录实际 fork 时刻；无法证实恢复时不免费重发。
- 不给新 48 次预算、不跨分支共享新缓存、不免费忽略等待。搜索/分支参数不是线上最优策略。

这一工程实验比较有限查询计划，不声称已经衡量自适应策略的全部机会成本。阶段 C 如需单步动作效应，另冻结同一个后续策略 γ，定义“跳过本决策”与“余下全停止”的区别，并计入其他目标预算竞争；不能暗改这次 stop 语义。

主产物记录整个余下会话的状态/损失，另列选中目标。明确 no legal query、already cached、alias、budget exhausted、late、missing native、failed、completed。原 registered target 分母保持；没有真实替代响应的路径 not_evaluable。

每条有效路径保存字段→特征→概率→采用→损失与成本。只改最终 E label 的负控制应 F 不变。没有传播不算工程失败，但必须定位；没有任何有效不同路径意味着任务选择空间不足，不触发新大模型。

产物：`C2_PARENT_STATES.json`、`C2_NOOP_EQUIVALENCE.json`、`C2_BRANCH_ROSTER.json`、`C2_FIELD_TO_LOSS.json`、`C2_ENGINEERING_REPORT_CN.md`。

### W05.acceptance：一次相关回归与收尾

依赖：本批已实施的修复。不要等未启动的支线。

顺序：定向失败回归 → 最小修复 → 定向通过 → 合并后一次当前 monitoring 回归 → 有界真实输入复算与正式引用负向校验。既有 750 是历史节点数，新数字从 JUnit/nodeid 自动去重统计。

formal 标签要求：managed bound 与显式 legacy 区分；合法预登记失败/回退可按原合同评分，真正不完整不可自动宣称完整比较。不得用只要求 `STOP.reason=completed` 的规则删除合理失败。

可携带的小型当前源验证仅覆盖适用输入；旧 capsule 冻结源复算与新代码迁移分开。无需为了本次 E 汇总重跑所有大型历史原始数据或模型。

检查本批所有输出未修改冻结原预测/费用/失败/分母；Git 开发索引保持原样，除非用户另有提交操作要求。

## 4. 自动执行与停止方式

本批获准后才产生 `EXECUTION_AUTHORIZATION.json`、新的输出目录和一次性运行身份。不要把本文件的 proposed 状态改成一个虚假的已批准收据。

薄协调器只按明确依赖推进：

```text
W00
  +-- W07.e_summary -- 原 fullweek final audit -- W07.closeout
  +-- W06.sample_summary -- 年度缺口/原文清单（到登记为止）
  +-- W01.bank_guard
  +-- W11.universe -- W11.branch_engineering
                         |
               已完成更改 -- W05.acceptance -- 本批报告/停止
```

每项写短状态：task_id、input/roster hash、expected/completed/failed/not_attempted、资源 ID、heartbeat、首次失败签名、是否需人工判断、下一条依赖。完整日志另存；机器可以周期检查，Codex 不为每个心跳重复读取。

发生以下情况停止受影响节点：哈希/合同变化、意外分母、未知提交/执行身份、未决费用异常、需新来源/模型才能继续、未读确认载荷被请求。其它独立节点仍可完成原批准范围。

源码边界修复若影响科学输入，只新增修订结果和影响表；不会自动获得重生成模型回答的授权。数据缺片恢复与模型逻辑重试是不同合同，不能互相借用。

## 5. 首批交付与下一批交界

用户最终应看到三份短报告：

1. **整周结果**：完整分母、各方法/季节/正负例效果，修订 E 及不变 F 的证据；未完成则列精确缺口。
2. **C2 可行性**：来源全集差异、自然状态分布、最多六个真实父状态的恢复/分支及实际传播链。
3. **数据下一批范围**：KORD 精确缺片、年度唯一原文清单、角色/purge 规则、吞吐估计、预算和停止条件。

同时交付代码差异、定向/合并回归、原始证据清单与资源终态。下一批的唯一推荐入口是按已核实清单补数据并构建全年后端；C2 科学矩阵等后端冻结，温度/API/MM 按各自资格并行。

没有本批的实际通过回执，就不能把阶段 B—D 的建议写成“自动下一任务已获准”。本轮是正式执行前的复核材料。
