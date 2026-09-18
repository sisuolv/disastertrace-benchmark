# DisasterTrace v9 最新实现复查与增量 Codex 计划

审阅基线：`next-phase-v1@6f71c8799ff69439a18f645e63b8c966ca21eec4`，父提交 `5ed0fb94ae7bf235b37e7528e201b603271edffa`。提交于2026-09-14 14:07:18 UTC。

性质：本文件是依据当前代码、已发布结果、用户补充idea形成的审查与实施计划。未改用户仓库，未调用模型/训练/GPU/天气数据采集，未打开确认集。保留v9、C1/C2/C3、16类与E/F/D/MM。

## 0. 结论与本轮证据范围

当前代码不是从零开始：规范结果与准入、共同预报、原请求恢复、廉价COPY、四区域校准、独立E/F与第二数值领域都已有实际产物。最新暂停状态应尊重，不能因本文件自动继续旧任务。

本轮发现一个局部可复现的解析边界：selector会接受重复JSON字段并采用最后一个值。没有检查到其在完整历史调用集合中的实际发生率，因此不能据此宣布现有真实成绩错误。

另外确认两项重要的设计/解释问题：补证路径采用单独后校准映射；LLM selector同时选择查询与预测调用对象。这两者都可以是合法的系统设计，但需要对照才能将变化归因于“新增证据”或“查询策略”。

E逐槽正确而汇总错误已经有仓库原始捕获分析；应评价新组合管线，不静默纠正旧答案。温度连续版本流已完成；下一步是补证/处理动作和模型能力，不是重复做COPY表。

本轮本地执行了4份源码Git blob哈希核对和17组局部CPU行为检查。直接运行三个完整标准库模块；`calibration.py`删除了未使用的证据导入，仅执行candidate=None路径，任何意外调用未加载辅助函数都会失败。所有输入均为合成数据。未取得二进制审查ZIP；发布说明本来也不包含所有F日志/检查点，因此未复跑616项测试、E02、API完整会话或温度192轨迹。详见`local_probes/PROBE_RESULTS.json`及SOURCE_INDEX。

## 1. 最新进度：应如何更新旧计划

| 部分 | v9实际完成 | 仍缺什么 |
|---|---|---|
| 实验不变量 | score_admitted从初始配置逐次验证intervention，再查最终状态 | 保持真实journal回归，不再把2→3→2当未修复 |
| 标准结果 | 目标+结果版本规范登记、跨提前量一致性与共同基线流检查 | 新provider仍需语义/质量资格 |
| API采集 | 原响应先落盘、AFS有界锁等待、未知费用保留、独立E02 | 用户实际账单/未知执行不能由研究估计替代 |
| 区域概率映射 | 四区域3303获取、9678拟合、2780校准；时间窗口和共享版本purge | 稀有事件支持、映射正则与异策略校准适用性 |
| E模型结果 | E02共1008调用、42底层问题相依视图 | 跨过程稳定性、与F的实际连接 |
| 航空F | 普通2304API调用、Denver诊断384调用；COPY和14类臂已有 | persistent实际模型轨、独立严重过程、选择/调度隔离 |
| 温度F | 24月192程序轨迹、11644机会、3645目标 | 补充证据、非平凡选择、温度LLM、多个独立站域 |
| 科学广度 | 16类总合同与多来源资产保留 | 各类E/F/D/MM/确认分别准入，不等于16类完成 |

[R01,R03,R05,R06,R12,R14]

E01保留938已登记尝试、876结算、62未知；E02是同问题/同提示整批独立再执行，不是只替换失败或错误题。费用为保存费率下的保守估计，不是账单。将“测试通过”“请求被成功保存”“科学结果成立”分开。

## 2. 已有结果的准确解释

### 2.1 E

Flash四条件114/126、125/126、109/126、126/126；Pro为85/126、106/126、84/126、101/126。Pro聚焦逐槽25个错误全部是槽位正确后的最终聚合错误。Flash完整逐槽的1份格式错误仍在分母。

这是42底层问题的相依视图，并采用thinking disabled/temperature0/512输出token。不是126独立事件，也不是模型一般性能排序。[R01,R07,R08]

### 2.2 F普通日历片段与富集诊断

普通试点为三个区域的2025-01-06、01-10全站逐时机会；每阈值432登记、431结算。1km无正例，5km47正例。FOLLOW的Brier为0.003527/0.064305；LLM批量预测器数值与其几乎一致；冻结补证程序和两种LLM selector+程序组合在普通试点总体更差。

DenverJan9是知道三条1km正例后选取的整日机制诊断。它显示部分程序和选择器组合降低损失，但不能与普通日历相加估计自然发生率、独立收益或严重事件总体召回。[R01,R03]

“新概率”只是同时离开两种可见概率超过0.005的数值；不是信息新颖性证明。selector_program的数值由程序生成，不是DeepSeek独立完成了新的天气概率推理。[R12,R13,R16]

### 2.3 温度

完整两年程序库有729个各事件目标；高温日22、霜冻113、冰日27，三日高温8和三日冰日10个可结算正例目标。相邻窗口与多次起报高度相关；24月是运行分片，不是24个独立天气系统。已取得完整四日51成员产品免费输入，零补证查询、零温度模型调用。[R01,R14]

## 3. 代码审查与具体修订

### 3.1 selector重复键：小修，不重写解析框架

`monitoring_v1/selection.py::parse_selection`调用默认json.loads。下列字符串会被接受并选q1：

```json
{"query_order":["q0"],"query_order":["q1"],"forecast_handles":["t0"]}
```

与同仓库E/head的唯一键解析口径不同。给selector增加唯一键检查；不“修复”内容，不重试模型。先扫描旧原始selector捕获，命中才做版本化影响分析。不能从合成反例推出旧成绩有错。[R13]

### 3.2 模型最终E不一致要作为语义错误保留

`evidence_diagnostic.parse`刻意允许“槽位合法但最终汇总不一致”，这是为了评分，不是验证器漏掉格式错误。不要在原parse中悄悄重写fact_truth。

新独立方法可输出：model_slots→deterministic_aggregate。它只使用模型预测的槽位，不使用正确参考槽。原始最终答案、模型槽、组合答案、原生合法事实参考四列都保存。组合方法增加的处理和调用计费，确定性原文解析对手同样可运行。后验组合正确率是诊断，前瞻新管线的结果另冻结。[R07,R08]

### 3.3 后校准分支是实际影响概率的组件

`predict()`先寻找带证据单元，再退到base/pooled；随后根据disclosed非空选择evidence或base校准器。两套校准器由独立历史校准段拟合，证据视图按每目标总权重1组织。没有证据表明测试标签参与拟合。[R09,R10,R11]

但在相同原始单元时，查询仍可通过切换映射改变p。合成无TAF路径中，同cell/n的输出可从0.1变成0.4。它只证明这条代码路径存在；缺报本身可能有信息，不规定空结果必然不改变预测。

后续逐条导出raw_p→family→post_p；分别比较单元信息、后处理和调度。固定family条件是机制诊断，原分支映射保留为完整合法系统，不被错误判为bug。

### 3.4 平滑按不同概率分桶，需报告先验占比

PAV实现每个不同原始概率都加1正/1负伪计数。100个相同0.1的负样本得到1/102；100个仅差1e-12的不同概率负样本得到1/3。单调性与数值范围仍然正确；这是已声明估计器的有限样本敏感性，不是计算错误。

真实银行要导出不同概率数、真实权重与伪计数比例，比较少量预冻结的收缩/正则方案。不能根据开发测试谁赢而选最终bank；不能自动round所有p后改写旧实验。W01仅支持校准的一般方法与局限，不直接证明该项目的某个估计器已经错误。

### 3.5 selector当前是两种决策的组合

它同时输出query_order和forecast_handles。查询可以变化，哪些目标会调用程序也变化，保留旧值的机会随之变化。普通日历中补证程序总体有害时，一个少调用的选择器可能仅通过避免部分有害改写改善相对batch表现。

因此分三张表：固定预测日程改变查询；固定证据改变预测日程；两个同时变化的完整策略。少更新不自动是投机；允许有效地避免坏改写，但应正确归因。[R12,R13]

### 3.6 动态比较旧问题已修复

score_admitted现在逐次comparison.validate中途状态，且检查初始与最终一致。不要再创建一个竞争性的动态验证模块。继续保留真实日志的2→3→2拒绝测试及合法动态值测试。[R06]

### 3.7 API失败与身份边界

当前采集先保存原始响应，再另行结算费用；AFS锁只做本地等待，不自动重发HTTP，这是正确改进。E01未知费用不能因为E02成功就消失。能够从已持久化原始usage对账时，采用有来源、幂等且单独记录的对账入口；不能重新发请求获得“替代usage”。[R15]

后续报告客户端总耗时、排队、提交/持久化与服务端未知计算。旧peak费率不套用到新日期；请求模型名与实际返回模型名都保存。外部官方文档当前可能变化，不能据此否认当时已捕获的兼容性结果。[W02]

## 4. 后续研究主线：不要扩大同类调用，先修复可识别性

### 4.1 一个证据×预测器矩阵

共同预报B→只看共同信息f(B)→加入指定合法资料f(B,E)。固定证据比较冻结程序与LLM；固定预测器比较补证；固定预测轨迹比较采纳。完整原始TAF始终保留给公平对手。

新增报告不仅有最终Brier，还包含cell、参考基线、候选、采纳动作、完成时间、最终生效、损失。概率等于基线不能证明模型内部复制；也不能证明它已作出持续FOLLOW动作。0.005仅是诊断容差。

### 4.2 E-F连接不是把true变成0.9、unknown变成0.5

E是过去合法证据命题，F是未来固定目标。保留每槽地点、时间、区间、覆盖和版本，不只把一个existential结果交给预测器。该预测器必须冻结训练与缺测适配；由已有规范数据或程序可确定的事实对所有方法开放。用评估器私有事实替换感知时必须另标特权诊断。

同一前缀下，只有改变一个明确环节才能解释局部效果；多个修复的损失变化不能相加成互斥“错误原因百分比”。事后最佳分支不作为被测策略可见信息。

### 4.3 必须有状态区分见证

当前航空新API批只有base-bound，且以1h目标为主；不同COPY/FOLLOW往往无机会分叉。不是缺少COPY代码，而是缺少能区分协议行为的轨迹。

先用合成短见证验证：旧覆盖仍有效时新基线到达、相同值重新提交刷新寿命、KEEP不刷新、预测完成与基线到达同刻、迟到不能回填。再按公开时间/版本结构选择真实档案配对，不按最终得分挑前缀。持久协议已存在于引擎和温度程序，不用重写。

### 4.4 校准与极端结果分开评价

普通1km队列无正例时只能分析负例概率与误报负担，不能估计该队列的严重事件召回或正例校准。5km不是统一的极端浓雾。保留Brier、各阈值与提前量、AP/ROC在有两类时的适用范围、全正例分母中的及时检出。

不把所有新阈值、视图和seed加成独立N。自然采样与诊断富集分表；抽样概率不明时不简单逆频率加权冒充部署分布。共同结果mask保证方法比较同一可结算集合，不保证总体缺测无偏。

## 5. 温度和其他灾种的接入

温度F程序版本流已经成立。下一项产物应是一个真正有补充信息/处理选择的固定未来任务，而不是再跑一遍192条COPY。单站完整四日预报已经免费，不能将同一产品拆片伪装为新独立证据。候选可来自合法早期站点状态、相关气象变量或空间信息，但必须证明实际存在并与目标相关，不能假设有用。

至少保留真实成员轨迹上的多日概率、原生日界、初始时刻和声明可用时间；当前单站、重叠目标仍属于有限范围。没有额外有意义的资料时，温度可作为连续F控制/迁移轨发布，不强行称为主动取证成功。

16类总范围不变。H15负责稳定开发；温度承担已完成版本流之上的真实补证；H07负责合格连续定量降水与处理工具；H08核准变量、断面、调蓄、时域支持后连接。D、MM、live都有各自条件，不变成全部核心发布的串行前置。

## 6. 执行工作包

具体字段、依赖、文件、产物与验收见CODEX_BACKLOG.json。下面为顺序摘要：

| ID | 主要工作 | 先后 |
|---|---|---|
| VX00 | 锁定v9和实际授权/暂停 | 第一批 |
| VX01 | 严格selector解析与旧发生率扫描 | 第一批 |
| VX02 | 最小端到端复放包和独立算术 | 第一批 |
| VX03 | E逐槽→确定性组合的独立协议 | 第一批 |
| VX04 | 校准单元与映射归因 | 第一批 |
| VX05 | 查询与预测日程因素隔离 | 第二批 |
| VX06 | 状态区分见证与persistent规格 | 第二批 |
| VX07 | 真正任务相关的补证目录和固定F | 第二批 |
| VX08 | 温度真实主动会话 | 与第二批并行 |
| VX09 | 有限实际模型管线实验 | 对应有效授权、前置冻结后 |
| VX10 | 完整日历/独立组/确认锁 | 第二批开始设计，冻结后运行 |
| VX11 | 分级发布与D/MM扩展 | 依资格逐项 |

第一批CPU为主，不新增请求。一次变更尽量不同时改数据、prompt、概率映射、采纳协议和评分。完成报告写实际路径、函数、命令与结果，不写“测试数增加所以novelty增加”。

## 7. 明确验收和停止规则

工程：相同未来目标不换结果；同角色比较不换共同预报；失败不删除机会；原始响应与费用不丢失；未读/未来数据不会进入模型；重复键不得静默产生动作。

科学：能区分资料/校准/预测/调度/采纳；自然与富集集不混合；现有API别名和配置范围如实披露；模块正确不等于所有领域的物理合同成立。

研究：接到至少一条同前缀真实E—补证—F链，并在新的独立过程检验。允许程序优于LLM、全读优于主动、少调用更优以及零增益。只有协议与数据可测性是准入门槛，不将正收益设为门槛。

以下情况应停止扩相同模型矩阵并交付诊断：全部合法证据被强程序利用后仍无增量；模型输出恒等于可见值且廉价程序复制可解释；采集/物理支持不合格；独立正例不足以支持主张。停止对应的是扩大当前实验，不是放弃整个研究。

## 8. Novelty应怎样得到证明

C1不是“读得多”或“数字变了”，而是同工具、同更新专业基线下的有限信息/处理/预测日程选择。
C2不是模型解释，也不是聚合公式原创，而是合法支持集合、联合可达性、结构化理解和实际未来效果的可验证关系。当前Pro槽位正确但汇总错误是一个开发现象；确定性组合是强方法对照，不自动保证未来收益。
C3不是16这个数字，而是同样的测量问题可以在不同物理过程、不同来源与独立时间块复现，并公开不成立的范围。

用户补充idea强调完整状态重跑、预测主线与研究准备分层。本计划保持这些重点；复杂D或更大模型不替代当前E/F可识别性与真实独立证据。

## 9. 来源与复查方式

本包SOURCE_INDEX.json列出固定提交的逐文件读取范围与URL。编号R01—R18在本文引用；W01/W02为仅做定向核验的官方文档。事实以对应冻结捕获为准，不将后来动态网页视作当时运行配置。

本包local_probes中的测试无需网络或模型。它们的输出不是616项仓库测试的复现。selection的重复键反例、PAV的数值敏感性以及无TAF后处理分支均明确标注作用域，不自动外推历史影响。

### 固定仓库文件

- R01：`LATEST_PROGRESS_20260914_CN.md`；读取 `full`；blob `bd2e30cb6f0ee8afa7d0a1fef479379970e649e2`。
  来源：`https://github.com/sisuolv/disastertrace-benchmark/blob/6f71c8799ff69439a18f645e63b8c966ca21eec4/LATEST_PROGRESS_20260914_CN.md`
- R02：`publication/v9_followup_20260914/README_CN.md`；读取 `full`；blob `未在本包单独绑定`。
  来源：`https://github.com/sisuolv/disastertrace-benchmark/blob/6f71c8799ff69439a18f645e63b8c966ca21eec4/publication/v9_followup_20260914/README_CN.md`
- R03：`plans/v9_followup_execution_20260914_01/README_CN.md`；读取 `1-210`；blob `53b0a9d7bfb72d98a98f426c727a23e9b198c6b0`。
  来源：`https://github.com/sisuolv/disastertrace-benchmark/blob/6f71c8799ff69439a18f645e63b8c966ca21eec4/plans/v9_followup_execution_20260914_01/README_CN.md`
- R04：`plans/v9_followup_roadmap_20260914_01/RESEARCH_ROADMAP_CN.md`；读取 `1-230`；blob `未在本包单独绑定`。
  来源：`https://github.com/sisuolv/disastertrace-benchmark/blob/6f71c8799ff69439a18f645e63b8c966ca21eec4/plans/v9_followup_roadmap_20260914_01/RESEARCH_ROADMAP_CN.md`
- R05：`disastertrace-starter/src/disastertrace/monitoring_fixed_v1/outcomes.py`；读取 `full`；blob `6fb58ce11b64af8cd6ab64ec1207d62f8119d82c`。
  来源：`https://github.com/sisuolv/disastertrace-benchmark/blob/6f71c8799ff69439a18f645e63b8c966ca21eec4/disastertrace-starter/src/disastertrace/monitoring_fixed_v1/outcomes.py`
- R06：`disastertrace-starter/src/disastertrace/monitoring_fixed_v1/admission.py`；读取 `650-990`；blob `0211ec048a2787e7f703c3c31be310f89a05d392`。
  来源：`https://github.com/sisuolv/disastertrace-benchmark/blob/6f71c8799ff69439a18f645e63b8c966ca21eec4/disastertrace-starter/src/disastertrace/monitoring_fixed_v1/admission.py`
- R07：`plans/v9_followup_execution_20260914_01/scripts/evidence_diagnostic.py`；读取 `full`；blob `40e7668e76862b4b3f61f31d5c77f6fde6d34578`。
  来源：`https://github.com/sisuolv/disastertrace-benchmark/blob/6f71c8799ff69439a18f645e63b8c966ca21eec4/plans/v9_followup_execution_20260914_01/scripts/evidence_diagnostic.py`
- R08：`plans/v9_followup_execution_20260914_01/reports/e_error_mechanisms_01/REPORT_CN.md`；读取 `full`；blob `2d9d8c3f2aa3a8b1c87f020d78969822c66cae32`。
  来源：`https://github.com/sisuolv/disastertrace-benchmark/blob/6f71c8799ff69439a18f645e63b8c966ca21eec4/plans/v9_followup_execution_20260914_01/reports/e_error_mechanisms_01/REPORT_CN.md`
- R09：`disastertrace-starter/src/disastertrace/monitoring_v1/regional_calibration.py`；读取 `full`；blob `6236493c86c31e0f3b7c605692601146e716bbbf`。
  来源：`https://github.com/sisuolv/disastertrace-benchmark/blob/6f71c8799ff69439a18f645e63b8c966ca21eec4/disastertrace-starter/src/disastertrace/monitoring_v1/regional_calibration.py`
- R10：`plans/v9_followup_execution_20260914_01/scripts/fit_regional_baselines.py`；读取 `full`；blob `9e4c734517a4e1492e6a3790405cbbaf331498f6`。
  来源：`https://github.com/sisuolv/disastertrace-benchmark/blob/6f71c8799ff69439a18f645e63b8c966ca21eec4/plans/v9_followup_execution_20260914_01/scripts/fit_regional_baselines.py`
- R11：`disastertrace-starter/src/disastertrace/monitoring_v1/calibration.py`；读取 `full`；blob `6c5cf91e7513bd7674f558ea1f474c58168db6b4`。
  来源：`https://github.com/sisuolv/disastertrace-benchmark/blob/6f71c8799ff69439a18f645e63b8c966ca21eec4/disastertrace-starter/src/disastertrace/monitoring_v1/calibration.py`
- R12：`plans/v9_followup_execution_20260914_01/scripts/run_api_pilot.py`；读取 `1-240`；blob `6c14f6a05c6c177778701e3c28f25618e6c09942`。
  来源：`https://github.com/sisuolv/disastertrace-benchmark/blob/6f71c8799ff69439a18f645e63b8c966ca21eec4/plans/v9_followup_execution_20260914_01/scripts/run_api_pilot.py`
- R13：`disastertrace-starter/src/disastertrace/monitoring_v1/selection.py`；读取 `full`；blob `c79decdbee12db2e2e4ae70dfb2a70d3174c37dd`。
  来源：`https://github.com/sisuolv/disastertrace-benchmark/blob/6f71c8799ff69439a18f645e63b8c966ca21eec4/disastertrace-starter/src/disastertrace/monitoring_v1/selection.py`
- R14：`plans/v9_followup_execution_20260914_01/scripts/run_temperature_fullcalendar.py`；读取 `full`；blob `29eb1dc71a1021484d822990aa0bbfc66892984a`。
  来源：`https://github.com/sisuolv/disastertrace-benchmark/blob/6f71c8799ff69439a18f645e63b8c966ca21eec4/plans/v9_followup_execution_20260914_01/scripts/run_temperature_fullcalendar.py`
- R15：`disastertrace-starter/src/disastertrace/monitoring_v1/api_capture.py`；读取 `full`；blob `9dead639a11b7d4f1f9de6c6e2a253a5665be93c`。
  来源：`https://github.com/sisuolv/disastertrace-benchmark/blob/6f71c8799ff69439a18f645e63b8c966ca21eec4/disastertrace-starter/src/disastertrace/monitoring_v1/api_capture.py`
- R16：`plans/v9_followup_execution_20260914_01/scripts/analyze_api_followup.py`；读取 `180-340`；blob `b0a046af7b6231f56bc0dc39793b6c8d2f6443ee`。
  来源：`https://github.com/sisuolv/disastertrace-benchmark/blob/6f71c8799ff69439a18f645e63b8c966ca21eec4/plans/v9_followup_execution_20260914_01/scripts/analyze_api_followup.py`
- R17：`disastertrace-starter/src/disastertrace/monitoring_v1/evidence.py`；读取 `full`；blob `d921c845ac6689131944271c34a1f462deb5fb9b`。
  来源：`https://github.com/sisuolv/disastertrace-benchmark/blob/6f71c8799ff69439a18f645e63b8c966ca21eec4/disastertrace-starter/src/disastertrace/monitoring_v1/evidence.py`
- R18：`disastertrace-starter/src/disastertrace/monitoring_v1/support.py`；读取 `full`；blob `d43b56c98aa3e59c4c1d17f72a503941b604698d`。
  来源：`https://github.com/sisuolv/disastertrace-benchmark/blob/6f71c8799ff69439a18f645e63b8c966ca21eec4/disastertrace-starter/src/disastertrace/monitoring_v1/support.py`
