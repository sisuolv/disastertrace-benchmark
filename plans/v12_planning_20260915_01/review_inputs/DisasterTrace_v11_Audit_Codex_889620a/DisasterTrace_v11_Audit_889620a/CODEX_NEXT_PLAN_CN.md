# DisasterTrace：基于 v11 最新代码和进行中结果的 Codex 接续计划

审阅提交：`889620a4fc4ee6ad70757dd3e832a40c7509126a`。本计划是新增建议，不是已完成任务。沿用现有 v11 的 W00—W13；此前 P0—P3/N1—N5 保留为历史，不重建编号体系或引擎。

## 1. 先读什么

先读当前执行目录的 README、最新工作机状态和原始注册，再读本包 `AUDIT_REPORT_CN.md`。不要以规划文件开头的“尚未启动”覆盖后来的进行中状态。当前提交只是12:06 UTC快照，工作机可能已前进。隔离Git发布不要求开发工作树HEAD等于远端发布HEAD。

关键入口：

```text
LATEST_PROGRESS_V11_CN.md
publication/v11_inprogress_20260915/PROGRESS_SNAPSHOT.json
plans/v11_execution_20260915_01/README_CN.md
plans/v11_execution_20260915_01/fullweek_02/
plans/v11_execution_20260915_01/annual_catalog_01/
plans/v11_execution_20260915_01/annual_native_sample_01/
plans/v11_execution_20260915_01/c2_design_01/DESIGN.json
plans/v11_planning_20260915_01/OVERALL_PLAN_CN.md
```

## 2. 当前研究问题与完成状态

研究问题继续是：相同专业资料、合法时间和共享资源下，额外证据能带来多少预测增量；程序/模型能取得、理解并及时利用多少增量。E当前证据支持与F未来效果分开，D/MM不与核心成绩混合。

当前已完成：750项报告回归；旧指定输入影响扫描；正式v2来源绑定；温度旧边界修复；九日志19→9次重放；一个日案例五臂360行预检；年度目录阶段71/72；144个C2题构建。

进行中或未完成：840轨迹全量审计及新分层分数、年度原文和拟合、C2实际同状态分支、完整成员lineage和部分DWD政策、当前源capsule迁移与独立确认。v11新增被测模型调用0，不等于项目无实质进展，也不推断开发Codex token为0。

## 3. 首批执行的边界

首批只进行本地CPU、已有文件和已有依赖上的代码修复、回归、清单、只读派生审计。已有授权云任务先只读核身份和终态，不重复提交、不关闭原任务、不热改冻结源。

新增API/GPU/云任务/额外下载必须有明确的新范围或经核验仍有效的原授权；不能通过重开旧launcher、删claim或挪用未决费用获得额度。留存确认数据继续封闭。

本批优先交付：

1. W07.E_count：E状态统计修订，保留原ROWS和原分数。
2. W06.sample_summary：样例失败不再重复结果，并登记KORD精确缺片。
3. W01.temperature_scope：原始概率与ECC全产品资格分离。
4. W07.closeout：在已完成原轨迹上核全量roster与关键配对；未完成则只报告现状。

这四项不需要新被测模型。测试源码不应直接覆盖工作仓库；把反例转为实际生产模块测试再修复。

## 4. 必须保留的研究对照

| 比较 | 可以回答 | 不能混称 |
|---|---|---|
| FOLLOW → F_COMMON | 完整共同信息的另一数值后端表现 | 主动取证贡献 |
| F_BASE_ONLY → B11_BATCH | 同values后端中补证、获取时序的效果 | 所有后端的信息理论价值 |
| B11_BATCH → B11_COVERAGE | 登记预算与日程下两种选择策略差异 | 免费selector或全局最优策略 |
| 固定证据，原生/模型提取 | 读取字段和特征利用的差异 | 新运行的自适应效果 |
| 同前缀不同合法分支 | 指定档案/后端的路径效应 | 模型当时知道的最优动作或期望信息价值 |
| 同候选，两种采用规则 | 生效/到期/回退的作用 | 模型生成了新天气信息 |

当前五组正式评分分组不能为方便合表而取消银行身份检查。跨组可以在相同目标与结果掩膜上做显式配对，需标注银行不同。增加 F_BASE_ONLY→B11_BATCH 和 F_COMMON→B11_BATCH/COVERAGE，防止只比较较弱FOLLOW。

完整周是七个每日重置会话，不是跨日缓存持续的一周agent。首轮沿用每日48查询、不结转；整周信用和缓存设计另作版本，不能在同表中暗改。

## 5. C2 如何从“题构建成功”走向“可辨别的研究结果”

当前72个覆盖题全部full，首先是构建与参考健全性检查。先跑always_full和免费程序解析基线；普查整个固定日历的状态，核对是否构建器先筛完整投影导致恒真。自然分布保留，状态分层诊断另表，不为了模型分数选择未来事件。

TAF本来就是共同免费产品。检查其版本/覆盖有助于区分产品理解，但不是付费补证的新增信息。新报告必须将共同资料解释、实际取到的站报、模型提取、后端利用和修订生效分开。

同状态分支执行器可以在全年数据尚未全部完成时先用已有冻结后端实现和调试。主要科学结论再由完成资格的新后端验证，不必让所有CPU工作等待两年原文下载。

## 6. 两条并行线与最终门槛

```text
当前状态对账
  ├─ E汇总/失败摘要/温度资格修复 → 现有完整周收尾 → 程序机制比较
  ├─ 年度目录精确补缺 → 去重原文 → 任务/角色准入 → 全季节强后端
  ├─ C2全日历状态普查 → 同前缀分支工程验证 ───────┘
  └─ 未暴露来源/过程/精度设计草案

强后端 + 实际分支 + 非平凡任务 → 一次有限模型角色实验
最后冻结方法 + 过程/样本设计 → 一次性未读历史确认
```

模型获胜不是任何科学出口的前提。反之，若全部分支得到同样资料、selector没有实际选择，先说明任务局限；不以继续增加模型规模代替任务设计。

## 7. 逐任务实施清单

### W00.refresh：先对账当前工作机和正在运行的批次

实现依赖：无。

已有入口：

```text
LATEST_PROGRESS_V11_CN.md
publication/v11_inprogress_20260915/PROGRESS_SNAPSHOT.json
plans/v11_execution_20260915_01/README_CN.md
plans/v11_execution_20260915_01/finish_batch_02.py
```

操作：

1. 核实际远端提交、开发工作树、未提交修改和冻结源；隔离发布导致HEAD不同不等于代码回退。
2. 只读检查fullweek_02、annual_catalog_01、annual_native_sample_01、STATUS/DASHBOARD/分片回执和作业ID。将过时README状态与新回执分开。
3. 每个任务记录owner、注册范围、心跳、已完成ID、进程与平台终态；无法访问平台就标unknown，不据空目录推断尚未运行。
4. 建立每项改动影响的运行、源版本和派生报告清单；当前已授权作业不重复启动，不因本报告强制终止。

交付（建议新文件名，不是已有完成证据）：`CURRENT_STATE_DELTA.json`、`ACTIVE_RUN_OWNERSHIP.json`、`CHANGE_SCOPE.json`。

验收：

- 840轨迹是注册数还是已完成数明确分开；没有使用部分结果写整批胜出。
- 年度目录、TAF原文、解析、任务、角色和拟合至少六个状态分别表示。
- 旧模型实验、失败、未尝试任务和未知费用保留；新增benchmark调用0不解释为Codex token0。
- 未修改运行中的冻结源码或已消费launcher；未打开Bay确认载荷。

执行范围：`local_cpu_existing_materials`。

### W07.E_count：修正完整周E汇总，不重跑预测

实现依赖：W00.refresh。

已有入口：

```text
plans/v11_execution_20260915_01/fullweek.py
plans/v11_execution_20260915_01/fullweek_02/source/fullweek.py
disastertrace-starter/src/disastertrace/monitoring_v1/policies.py
disastertrace-starter/src/disastertrace/monitoring_v1/evidence.py
```

操作：

1. 先将本包E反例移到实际模块测试：两个可判定状态supported/refuted都应计入；undetermined/inconsistent不计入。
2. 对frame E字段使用明确schema/枚举映射；遇未知拼写报错，不做全仓库entailed替换。
3. 修开发审计器；已经冻结的执行/原审计保留。新增只读派生审计，对原ROWS和journal作状态直方图与逐组对账。
4. 输出原E计数、修订E计数、差值、受影响机会ID与引用源哈希；Brier及原概率文件不得改变。

交付（建议新文件名，不是已有完成证据）：`reports/fullweek_E_audit_v2/RESULT.json`、`reports/fullweek_E_audit_v2/IMPACT.json`、`tests/test_fullweek_e_status_contract.py`。

验收：

- supported/refuted/undetermined/inconsistent四状态反例得到2而非1。
- 真实各组修订值等于supported_count+refuted_count；原所有状态数之和等于相应完整E分母。
- E截止时统计与模型dispatch时E正确率分开；F结果缺失不自动删除可观测E机会。
- 源概率、loss、机会/结果掩膜和Brier哈希或数值完全不变；仅E汇总及派生版本变化。
- 完整ROWS尚未取得时只交付代码回归和pending影响清单，不伪造真实修订数量。

执行范围：`local_cpu_existing_materials`。

### W06.sample_summary：修复样例失败摘要并登记精确缺片

实现依赖：W00.refresh。

已有入口：

```text
plans/v11_execution_20260915_01/annual_catalogs.py
plans/v11_execution_20260915_01/annual_catalog_01/
```

操作：

1. 失败分支改为sample+[]；按注册unit拒绝重复、未知ID、样例与后续重叠。
2. 保留3样例全成功、样例失败、后续月失败三个实际入口测试；分清实际调用数和结果条数。
3. 对Chicago2023-01失败的KORD切片记录原429、后续超时、已消耗重试和同月5个可复用切片。
4. 仅生成一份有次数/字节/限速/终止条件的缺片修复计划。无新下载授权时不执行额外HTTP。

交付（建议新文件名，不是已有完成证据）：`tests/test_annual_sample_gate.py`、`ANNUAL_MISSING_SLICES.json`、`CATALOG_REPAIR_SCOPE.json`。

验收：

- 2成功1失败只输出3条结果、completed_units2；没有执行其余69月。
- 样例全成功后某月失败保留72条唯一结果、71成功；证明该反例不否定当前71月记录。
- logical_slice、HTTP_attempt、retry、region_month各自计数，失败不变成缺测天气。
- 不覆盖原RESULT，不清理claim或重新下载全部成功月份。

执行范围：`local_cpu_existing_materials`。

### W01.temperature_scope：区分原始目标概率与完整ECC产品资格

实现依赖：W00.refresh。

已有入口：

```text
disastertrace-starter/src/disastertrace/monitoring_v1/temperature_contract.py
disastertrace-starter/src/disastertrace/monitoring_v1/feature_tasks.py
disastertrace-starter/src/disastertrace/monitoring_v1/temperature_postprocess.py
```

操作：

1. 为原始事件概率只验证目标所需字段和UTC支持，统一两个入口的资格；保留两种独立概率计算。
2. 为EMOS/ECC保留完整min/max产品校验，给出稳定的ValueError及原因码而不是无上下文KeyError。
3. member_id、initialization、日期与day_index按上游提供方合同绑定；不得仅以等长数组宣称真实lineage。
4. 对旧已登记POLICY和模型输入做只读对账；修复影响仅另表列出，不重新生成旧回答。

交付（建议新文件名，不是已有完成证据）：`TEMPERATURE_INPUT_SCOPE.json`、`tests/test_temperature_scope_v2.py`、`TEMPERATURE_IMPACT.json`。

验收：

- max-only完整UTC日的合法原始事件在两个入口都得到0.75；ECC仍拒绝缺少其所需min数组。
- 非午夜、重复日期、NaN/bool/巨大整数、day0及所需成员维度错配继续被拒绝。
- 完整旧EUPP输入的原始概率不变；例外列出具体ID和前后理由。
- lineage缺失属于资格未知，不把同一排列不变性单测当成历史成员身份验证。

执行范围：`local_cpu_existing_materials`。

### W07.closeout：收口完整周并补齐关键配对

实现依赖：W07.E_count。

已有入口：

```text
plans/v11_execution_20260915_01/fullweek.py
plans/v11_execution_20260915_01/analyze_fullweek.py
plans/v11_execution_20260915_01/fullweek_02/
```

操作：

1. 完成当前注册840臂终态对账；没有可信完整日志的臂保留incomplete，不静默删掉也不伪造回退。
2. 以原PLAN、输入/评估资产哈希和源码快照核验全量roster；优先复用原已完成日志，不重跑成功臂。
3. 保留同后端四组正式合同与F_COMMON单独合同，再用同目标/同结果掩膜的配对算术比较五组。
4. 现有PAIRS之外补F_BASE_ONLY→B11_BATCH，以及F_COMMON→B11_BATCH/COVERAGE；跨银行者明确标总系统比较。
5. 按全年开发周、地区、地区周、日、正负标签贡献、缺失与费用展开。累计/每日重置、1ms情景均原样保留。

交付（建议新文件名，不是已有完成证据）：`FULLWEEK_FINAL_ROSTER.json`、`FULLWEEK_PAIRED_EFFECTS.json`、`FULLWEEK_EVENT_BACKGROUND_REPORT_CN.md`。

验收：

- 168日条件、840臂、12096方法无关机会、60480方法行分别核验，不把注册数当完成数。
- 普通预检360行不与全量60480行相加；没有新LLM分数。
- F_COMMON不是与values同银行的纯取证对照；共同TAF和结算掩膜相同。
- 含事件块和背景块对总损失的贡献可相加复算；不只突出平均收益。
- 四个全局周的描述性结果不配逐小时bootstrap；缺失敏感性界不写成置信区间。
- E计数使用修订审计并保留原版；所有合法失败都能在注册清单中找到。

执行范围：`local_cpu_existing_materials`。

### W06.native_inventory：从年度目录走到可用原文与角色

实现依赖：W06.sample_summary。

已有入口：

```text
plans/v11_execution_20260915_01/annual_catalogs.py
plans/v11_execution_20260915_01/annual_native_sample.py
plans/v11_execution_20260915_01/annual_catalog_01/
plans/v11_execution_20260915_01/annual_native_sample_01/
```

操作：

1. 先接续已登记三个闰月样例的原文与构建审计；0完成地区不能写成样例已通过。
2. 根据实际目录按原生product_id/版本/内容去重全年TAF下载清单，保留站点、多月padding及源请求关联；不要用月份数估算已下载原文数。
3. 新下载前固定逻辑清单、次数、字节、提供方共享限速与重试终止；已有相同哈希原文复用，403/429/超时和语法不支持分开。
4. 构建后按字段、时间支持、站点、版本、结果政策及完整依赖足迹准入。源码可解析不等于所有天气目标可结算。
5. 2023用于拟合和训练内选择，2024保留为冻结后最终校准，2025已暴露数据继续标开发。按角色边界剔除捕获padding跨界依赖。

交付（建议新文件名，不是已有完成证据）：`ANNUAL_PRODUCT_OBJECTS.json`、`ANNUAL_TASK_QUALIFICATION.json`、`ANNUAL_ROLE_MANIFEST.json`、`ANNUAL_DATA_STATUS_CN.md`。

验收：

- catalog/native_bytes/decoded/task_join/role_admitted/fit六级证据分别有ID和哈希。
- 完整月4176双阈值机会×3是预期，实际缺测和不支持案例仍完整登记。
- 同一原生文件跨站点/月份复用不重复算独立样本；原生版本与来源脚印不跨训练/确认用途。
- 2024尚未做模型选择；若已经使用，改登记用途并另设最终校准，不隐瞒暴露。
- 最终参考可用于评分不自动可作历史输入；情景时延与真实first-seen资格分开。

执行范围：`inventory_cpu_now; network_only_under_new_or_still_valid_exact_authorization`。

### W08.year_backend：以完整季节训练建立强同信息后端

实现依赖：W06.native_inventory。

已有入口：

```text
plans/v11_planning_20260915_01/OVERALL_PLAN_CN.md
disastertrace-starter/src/disastertrace/monitoring_v1/native_feature_forecast.py
disastertrace-starter/src/disastertrace/monitoring_fixed_v1/native_feature.py
plans/v10_execution_20260914_01/scripts/fit_native_feature_bank.py
```

操作：

1. 只用已通过资格的冻结资料拟合，保留common/mask_age/values、原始概率及单独校准/CDF结果。
2. 2023训练内按时间/过程选择有限配置，2024只按预先固定方式校准；均值缩放、先验、缺证模式、阈值和特征版本一并锁定。
3. 报告每季节/站点的样本和正例、回退、缺测模式、分布外特征、校准变化；不得因为极端值远离均值就删除。
4. 旧冬季和去year消融全部保留；新银行跑新注册。必要时只加一个训练内折外common锚定残差参照，不把零补证回退优化包装成novelty。

交付（建议新文件名，不是已有完成证据）：`BACKEND_REGISTRATION.json`、`YEAR_BANKS/`、`BACKEND_GENERALIZATION_CN.md`。

验收：

- 拟合、内部选择、最终校准、开发、确认角色明示；没有使用新评价标签重新选银行。
- 合法空证据和子集训练已有实现被复用；每个物理单元的视图总权重保持合同。
- 同信息下1km概率不超过5km；不同信息包不能强行做同CDF投影。
- 主要报告不要求新方法优于旧方法；失败优化器、支持不足和不可结算均保留。

执行范围：`CPU_fit_after_input_role_and_compute_scope_admission`。

### W11.census：先确认C2题目不是筛选过程中的恒真题

实现依赖：W00.refresh。

已有入口：

```text
plans/v11_execution_20260915_01/c2_design_01/DESIGN.json
plans/v11_execution_20260915_01/c2_design_01/public/TASKS.json
disastertrace-starter/src/disastertrace/monitoring_fixed_v1/taf_tasks.py
```

操作：

1. 保留现有72前缀/144题，明确覆盖全full；加入always_full和合法程序解析对照。
2. 按固定完整日历普查full/partial/none/unavailable/冲突/订正/删失/未读等各自合同允许的状态；检查构建器是否先过滤完整投影才问覆盖。
3. 自然分布和状态分层诊断分表。只按公开产品状态分层而非模型输赢；看过结果后形成的规则进入新开发版本。
4. 标注TAF是共同免费产品：理解其适用性是C2，不把再次读取免费TAF记成C1补证。

交付（建议新文件名，不是已有完成证据）：`C2_STATE_CENSUS.json`、`C2_TASK_ROUTING.json`、`C2_BASELINE_REPORT_CN.md`。

验收：

- 72个full的旧样本保留，不用新困难集重命名旧分母。
- 各任务答案空间、常数预测准确率、不可用数量、源版本和分层规则可以复核。
- 评估参考和未来结果不进入模型view；全状态普查结果不当成在线获知的未来事件边界。
- 缺少真实冲突时明确0个，不把合成冲突算成真实灾害。

执行范围：`local_cpu_existing_materials`。

### W11.branch_runtime：真正执行同状态四分支

实现依赖：W11.census。 主要科学结论另需：W07.closeout、W08.year_backend。

已有入口：

```text
plans/v11_execution_20260915_01/c2_design_01/DESIGN.json
disastertrace-starter/src/disastertrace/monitoring_v1/session_checkpoint.py
disastertrace-starter/src/disastertrace/monitoring_v1/residual_reachability.py
```

操作：

1. 复用同一session checkpoint；先以工程输入检验分支恢复，再以已完成真实前缀检验。
2. 沿用登记四分支：停止新增付费查询、第一/第二合法邻站、其余全部；第一/第二以同一前缀冻结排序，不能按未来值排序。
3. 继承时钟、spent/reserved、来源额度释放、授权、缓存及完成时间、baseline/override、查询与推理pending、失败政策。按原设计先解决原串行pending且只保留同一回执，不为分支复制发出实际请求。
4. 不同名字得到相同后续输入/预测则记录等价分支；记录无查询可做、预算不足、迟到、缺档案和失败。no_further_paid_query不等于终止整个会话或冻结共同预报。
5. 逐层输出字段→特征→概率→候选完成/生效→固定未来结果。事后最佳分支只是指定有限动作和后端下的诊断。

交付（建议新文件名，不是已有完成证据）：`C2_PREFIX_CHECKS.json`、`C2_BRANCH_TRACES/`、`C2_FIELD_TO_LOSS.json`、`C2_BRANCH_EFFECTS_CN.md`。

验收：

- 原恢复路径与不中断路径科学状态相同；任何未来payload只在合法完成时可见。
- 不重置已花与预留，不把每日48额度在中午一次发满，不将目标私有证据共享。
- 停止查询分支仍能接收共同基线更新、执行后续合法预测和完整评分。
- 四个标签不自动等于四种信息；报告独特后续状态数和空操作比例。
- 缺少替代真实响应则not_evaluable；没有用LLM生成假资料补分支。
- E若不是F输入，单独改E标签不称F干预；字段替换/Gold修复仅作评估侧敏感性。

执行范围：`local_cpu_existing_materials`。

### W10.component_comparison：用强后端重测信息、选择与时机

实现依赖：W07.closeout、W08.year_backend。

已有入口：

```text
plans/v11_execution_20260915_01/fullweek.py
plans/v11_execution_20260915_01/analyze_fullweek.py
disastertrace-starter/src/disastertrace/monitoring_v1/forecast_schedule.py
```

操作：

1. 新注册五组完整日历比较；先固定选择器再补预算分配×授权四格，避免同时改变模型/后端/预算/日程。
2. 明确三个问题：旧FOLLOW到common是后端；同values空证据到batch是补证；batch到coverage是策略及其时序。差值不强制做无交互因果百分比。
3. 保留每日重置原轨；若新增整周336额度、缓存结转等，单独命名和注册。
4. 同原生证据固定包比较原生提取/模型提取/同一后端，完整自适应另算；需要隔离等待时用固定查询计划的声明时延诊断，不冒充新模型运行。

交付（建议新文件名，不是已有完成证据）：`MECHANISM_COMPARISONS.json`、`FULL_CALENDAR_EFFECTS_CN.md`、`COST_AND_SCHEDULE.json`。

验收：

- 总体、含事件/无事件过程和正负结果贡献齐全，没有只看平静天气的平均获益。
- 共同预算上限与实际使用都报告；48次来源查询不等于同总成本。
- 固定证据和新会话分别统计；输入改变后不复用旧响应冒充新推理。
- 覆盖率、未来预测质量和预算效率分表；不以E覆盖作为F奖励的无条件替代。

执行范围：`local_cpu_existing_materials`。

### W12.bounded_selector：只运行一个有明确问题的新模型角色

实现依赖：W10.component_comparison、W11.branch_runtime。

已有入口：

```text
plans/v11_planning_20260915_01/OVERALL_PLAN_CN.md
plans/v11_execution_20260915_01/README_CN.md
```

操作：

1. 首先评估现有强程序是否已将登记小候选池读完或多数分支等价，确认新selector有非平凡选择。
2. 沿用已验证235B优先做选择器；提取轨单独实验。新注册精确会话ID、提示/模型/后端哈希、资源、失败和停止规则。
3. 现有计划建议最多12会话×24选择=288正式请求及最多2兼容性探测，可按新roster收缩，不自动扩大。所有真实请求必须有新或明确仍有效的运行授权。
4. 若结果无增益或有效分支不足，保留结论，不通过强迫概率变化、削弱batch或加入模型追逐收益。

交付（建议新文件名，不是已有完成证据）：`MODEL_TRIAL_PREREGISTRATION.json`、`MODEL_TRIAL_RESULTS_CN.md`。

验收：

- 本轮只改变一个模型角色，所有基线有相同廉价解析/批处理工具。
- 来源费用、selector tokens/批次/排队/交付、漏交时刻和结果完整记录。
- 未尝试、传输失败、格式错误与科学预测错误分开；未知费用不回收为新预算。
- 模型失败/无收益也可完成注册，不按显著性追加日期或重试错误答案。

执行范围：`explicit_new_model_compute_authorization_required`。

### W09.confirmation_design：预先定义过程、样本精度与最终确认

实现依赖：W00.refresh。

已有入口：

```text
plans/v11_planning_20260915_01/OVERALL_PLAN_CN.md
disastertrace-starter/src/disastertrace/monitoring_v1/process_split.py
plans/v11_execution_20260915_01/c2_design_01/DESIGN.json
```

操作：

1. 设计完整来源/目标足迹依赖块与自动外部规则的天气过程组，不等同于日会话、区域周或小时。
2. 用开发数据的过程间变化制定区间精度、最大连续日历和不足时规则；不得先看确认效果。
3. Bay2025-02-17至23继续封闭；将其与新跨季节确认的作用明确，不让一个周承担所有结论。
4. 保留1km/5km，预先确定主要假设、多重比较与辅助指标；不可识别ROC/AP时标不适用。

交付（建议新文件名，不是已有完成证据）：`CONFIRMATION_DESIGN_DRAFT.json`、`SOURCE_DEPENDENCY_SPLITS.json`。

验收：

- 现有四季开发资料及提示澄清涉及的样本全部登记为暴露，不重新叫测试集。
- 新确认开始前才最终冻结方法与哈希；设计草案不触发读取确认载荷。
- 按天气过程/保守块估计不确定性，缺失补全界独立命名。
- 研究未暴露与模型预训练未见分开说明；历史回放不自动成为前瞻证据。

执行范围：`local_cpu_existing_materials`。

### W05.current_replay：只对变更范围做当前源可移植检查

实现依赖：W07.E_count。

已有入口：

```text
publication/v10_execution_20260914/README_CN.md
disastertrace-starter/src/disastertrace/monitoring_v1/formal_session.py
```

操作：

1. 用有明确任务范围的小型真实子集验证修复前后科学字段和派生E差异；没有当前源可搬迁字节就明确未完成。
2. 读取旧有限capsule说明和清单，区分旧源码复算与当前源迁移；不每次都无目的全重跑。
3. 测试新正式引用拒绝错目录、错合同、错STOP/journal/report、错data/bank；legacy只能显式只读，不能产生正式新资格。
4. 同次评分加载复用继续保留检查；记录耗时/内存及冷暖缓存条件，不承诺2.26倍普遍加速。

交付（建议新文件名，不是已有完成证据）：`CURRENT_SOURCE_REPLAY_SCOPE.json`、`COMPATIBILITY_AND_IMPACT.json`。

验收：

- 没有以本包6个源副本覆盖生产模块；只用来理解和构造测试。
- 新schema和旧schema分别校验，不要求不同格式所有字节相同；科学字段等价必须证明。
- 已验证source/manifests未被热修改；未知影响标unavailable_to_review而非0。

执行范围：`local_cpu_existing_materials`。

### W13.confirmation_release：一次性确认并按能力层级发布

实现依赖：W09.confirmation_design、W12.bounded_selector、W05.current_replay。

已有入口：

```text
plans/v11_planning_20260915_01/OVERALL_PLAN_CN.md
publication/v11_inprogress_20260915/README_CN.md
```

操作：

1. 在最后冻结后按精确授权打开未暴露历史确认；负结果照常保留，不追加有利日期。
2. 发布核心E/F的程序、模型、完整分母和复算范围，区分implemented/runtime/development/confirmation。
3. 温度F-only与历史补证、原生MM、D、X09、在线分别给资格；不作为核心确认整体前置。
4. 生成一页论文主张→实验→证据→限制表；未来资料/结果仅评估侧。

交付（建议新文件名，不是已有完成证据）：`CONFIRMATION_RESULTS_CN.md`、`CLAIM_EVIDENCE_MATRIX.json`、`REPRODUCTION_SCOPE.json`。

验收：

- 没有把有限E可达参照写成未来预测上界，也不将相关配对差异写成精确因果百分比。
- 有用信息、模型利用、及时生效和费用各自有对照；结论不要求模型胜出。
- 完整16类仍是总体目标，实际完成各自分项准确列出。
- 运行结束与资源终态有证据；进行中快照不包装成最终结果。

执行范围：`explicit_confirmatory_data_access_and_execution_scope_required`。

## 8. 并行支线：不能消失，也不作为核心确认的统一前置

**温度**：已有F-only模型及EMOS/ECC，不重新做同一128题来计进度。继续分季节/时距稳定性、hot-day退化、ECC的min/max修复次数和概率影响；真实成员lineage与DWD提供方语义单独准入。最终历史DWD可以是结果参考，不因有数值就成为收费历史证据。无历史发布证据时严格C1继续未验证；明确假设的情景轨另命名，不冒充真实部署。

**原生MM**：沿用v11规划中最多24个元数据预定资产配对的入口，不以模型胜负挑ROI或天气过程。报告实际可得、覆盖、时间、处理器图像接收及成本；原生Gold不进入策略。GOES/降水/气旋路线各自核资格，无法取得则记录阻塞，不能生成图像当真实观测。

**D准备任务**：先固定天气与F，改变准备时长、容量和取消成本，比较已有简单程序；再研究查询与准备的有限并行。前一层要求F不受行动偏好影响；后一层查询不同导致F不同是允许的。预测失效不退还实际准备成本，等待模型不暂停准备进程；只称情景收益，不称真实社会减灾。

**X09和在线**：联合目标要同时有按请求和按组总预算控制。在线需要提前保存预测、真实first-seen、后续结果成熟，不只收集来源。当前聊天不承诺后台唤醒；可执行的预登记调度器由工作机在明确授权范围运行。

## 9. 输出与异常处理

每个子任务交付简短`STATUS.json`（planned/running/implemented/runtime_validated/development_validated/blocked/failed），对应证据路径和哈希。不要只写passed，必须说明通过哪条合同，未测哪条。

正常运行进度由已有脚本汇总，Codex只读取变化和错误所指向的最小日志；不为节省编排token更改被评测模型的提示或输出预算。

对已有运行：优先精确续跑/只读重评分，不重复成功轨迹。未知远端执行不自动重发。参数/输入改变时旧模型响应不能冒充新推理。所有负结果、字段错误、格式错误、失败和未尝试保持独立分母。

对外汇报固定四类：当前实现；本地实际测试；真实开发结果；独立确认。修订派生E汇总与旧F分数分开。目录、原文、解析、任务、拟合和独立灾害过程的计数不得相互代替。

## 10. 本包的执行与来源限制

本包只运行32项有限本地检查，29通过、3失败，无完整750项回归、无新的真实天气评分。测试包含合成输入、AST提取函数和模拟执行器，不能包装成实际正式会话。

所有任务是本次建议；依据为审阅提交中的最新快照、执行README、OVERALL_PLAN及代码。具体读取与本地源范围见AUDIT_REPORT和SOURCE_INDEX。旧用户材料的“证据包×预测器”和“有界合法动作探针”继续采用；不把这些思想另起框架或声称首次发现。
