# 七份审查意见的取舍与当前源码核对

状态：规划审阅；没有执行包内探针，没有修改生产实现，没有运行新的 benchmark。

来源基准均指向远端 `889620a4fc4ee6ad70757dd3e832a40c7509126a`。本地当前相关源码与其中 26 份副本字节一致，见 `SOURCE_MATCHES.json`。这说明所讨论代码仍适用，不等于本轮独立重跑了审查者测试或确认了全部历史影响。

## 1. 来源编号

解压输入、原路径、SHA256、成员表在 `REVIEW_INPUTS.json`；同名内部文件放在不同来源子目录中，未覆盖。

| ID | 原文件 | 主要采用的内容 |
|---|---|---|
| A | `DisasterTrace_v11_Latest_Implementation_Audit_and_Codex_Plan_20260915_CN.md` | 当前阶段入口、温度提示/精确合同、API claim、formal 资格、完整配对、行动扩展的边界 |
| B | `DisasterTrace_V11_Audit_and_Codex_Plan_889620a.zip` | 校准银行/温度入口、TAF 处理与 METAR 获取分开、共享状态机会成本、两条并行主线 |
| C | `DisasterTrace_v11_889620a4_Review_and_Codex_Plan.zip` | 区间开闭的表示损失、真实碰撞优先、parent 去重、有限模型与 MM 入口 |
| D | `DisasterTrace_v11_889620a_Review_Codex_Plan_20260915.zip` | E 枚举漏计、完整原生来源宇宙、不能先过滤覆盖、及时建立原生 MM 资格 |
| E | `DisasterTrace_v11_Audit_Codex_889620a.zip` | E/年度失败摘要的局部修复、整周配对、源角色/强后端、实际分支不等待全年拟合 |
| F | `DisasterTrace_v11_Audit_Codex_889620a_20260915.zip` | 最小温度与年度修复、完整周符号/分母、E 字段依赖、分路径放行 |
| G | `DisasterTrace_v11_review_889620a.zip` | bank 域规则与合法间隙、原生数据分层、跨阈值共享标签、三本资源账与短交接 |

七包重合意见合并处理；它们不是七批独立天气实验，多个包的合成探针也不能加到项目的真实样本数里。

## 2. 当前核对与裁决

下面的位置均相对于开发仓库根目录。行号是本轮读取时的位置。

| 编号 | 当前代码证据 | 判断、范围与处理 |
|---|---|---|
| R01 | `plans/v11_execution_20260915_01/fullweek.py:252`；`disastertrace-starter/src/disastertrace/monitoring_v1/evidence.py:49` | 生产者返回 supported，汇总计 entailed/refuted。源码路径确认。新派生报告修 E，不重跑 F；真实数量待完整审计。采用 D/E |
| R02 | `plans/v11_execution_20260915_01/prepare_c2.py:44`；`plans/v8_measurement_execution_20260913_01/scripts/build_native_v2.py:79` | C2 取已投影候选。builder 的完整索引仍保留，实际 F 用完整索引先选版本；不能称 F 整体版本规则已经错。新 C2 宇宙从原索引重建。采用 D |
| R03 | `plans/v11_execution_20260915_01/prepare_c2.py:54`、`:70`、`:79` | 题为 TAF coverage/revision，动作取 METAR，当前 F 不读最终 E。拆两类干预并保留不变性；尚无实际分支可判失败。采用 B/C/D/E/F/G |
| R04 | `plans/v11_execution_20260915_01/annual_catalogs.py:177` | sample 失败重复拼接，静态确认；真实闰月 sample 通过，因此不推翻当前 71/72。新入口回归、原失败保留。采用 A/E/F |
| R05 | `disastertrace-starter/src/disastertrace/monitoring_fixed_v1/native_feature.py:53` | previous=-1 允许首块负 value，缺跨块域顺序；下游仍可能拒绝。修实际消费入口，保留合法间隙/外推；raw 整周无已证明影响。采用 A/B/C/G |
| R06 | `disastertrace-starter/src/disastertrace/monitoring_v1/temperature_postprocess.py:29` | 目标校验之后又完整 min/max 校验；与 raw helper 资格不一致。raw 解耦，ECC 保留；是温度范围门槛。采用七份重合意见 |
| R07 | `disastertrace-starter/src/disastertrace/monitoring_v1/temperature_contract.py:43` | day_index 仅正整数、跨日仅等长；不提供真实 member/issue lineage。须核原坐标，不把合成重排反例写成真实错位。采用七份重合意见 |
| R08 | `disastertrace-starter/src/disastertrace/monitoring_v1/feature_tasks.py:9` | 温度提示写死 30/0，generic row 允许可配置目标。冻结事件目录和动态渲染；未证明旧固定 30/0 批次与原提示不一致。采用 A，限定影响 |
| R09 | `disastertrace-starter/src/disastertrace/monitoring_v1/api_ledger.py:119` | mkdir 在 reserve 之前。补 incomplete claim/原子发布/kill-point；共享锁不能证明远端 exactly-once。不影响本批 CPU 分析。采用 A，降为 API 前置 |
| R10 | `disastertrace-starter/src/disastertrace/monitoring_v1/formal_session.py:245`、`:278` | 原 data/bank/journal/report/STOP 检查已实现；返回结果没显式标 legacy 与 formal，终态可更清楚。补资格字段/合法失败，不重建引擎或删除失败。采用 A，保留其他审查对已有保护的认可 |
| R11 | `plans/v11_execution_20260915_01/fullweek.py:106`；`plans/v11_execution_20260915_01/analyze_fullweek.py:13` | same_values_bank 分组含 FOLLOW；当前少关键 BASE_ONLY→BATCH 配对。原比较身份合法保留，新分析注明实际消费者并补十个描述性配对。采用 A/D/E |
| R12 | `disastertrace-starter/src/disastertrace/monitoring_v1/native_feature_forecast.py:168` | F 编码区间数值和无穷标志，未编码闭端点。只说明表示碰撞；先扫描实际碰撞，必要时新特征版本/新拟合。采用 C/G |
| R13 | `disastertrace-starter/CURRENT_PHASE.md:1` | 当前入口仍 v10，旧文本不代表最新任务。获准执行后更新 pointer，保留历史与发布/实时区别。采用 A |
| R14 | `plans/v11_execution_20260915_01/finish_batch_02.py:85` | 总收尾 passed 依赖原 annual passed；其一月失败将保留总体未全通过。分组件报告，不能为了整页变绿改原 annual RESULT。当前状态核查增补 |

## 3. 不照搬的部分

### 不把所有 P0 排成一个很长的串行前置

A 的首批同时包含完整温度合同/lineage、API 两节点事务、formal 可搬迁和多类测试。其它材料强调受影响路径隔离。采用后者的调度：首批先关闭 H15 的 E 汇总与 C2 来源问题；温度、API、MM、D 的升级分别有自己的门槛。

这不是取消校验，而是让每项校验服务实际即将执行的功能。API 暂不调用，就无需等它的两节点试验才能回答旧整周结果。

### 不热改原 fullweek PLAN 或自动审计

即使发现 group label 与 E 汇总问题，也不能改正在运行的冻结 source/PLAN。由原程序产生原回执，再在新目录用相同原行计算修订 E、分组与配对；新增派生报告身份。旧 F 数值是否不变必须核对，不靠承诺。

### 不把 generic 温度 helper 限死为唯一阈值

通用函数允许合同指定阈值并不天然错误。问题是任务注册、模型提示、专业产品、事件定义和结果政策必须一致。事件白名单在 benchmark 层约束；raw/helper 层保留正确的可配置语义。只在新正式目标要求真实可得性和成员谱系时升级资格，不给旧档案补造历史时间。

### 不把严格 STOP.completed 当所有合法评分的必要条件

完整正常运行、预登记失败续行/回退、无法恢复的真正不完整要分开。哈希绑定不代替科学终态；但只接受 success 也会删除困难失败。新报告同时给完整性、来源资格与失败分母。

### 不把“已证明信息有正收益”当作模型实验门槛

先要求任务有真实不同的合法选择、后端消费链可检查、强对照齐备。正收益不是准入条件。若真实可选空间退化，先如实记录；不能改弱基线直到 LLM 看起来有用。

### 不把全年下载变成 C2、MM 的串行阻塞

用现有冻结资料/后端验证工程路径；新后端科学实验另注册。MM 先做最多 24 个真实资产配对；不等全部年度拟合，也不凭文本模型运行记录称视觉链已通过。

### 不把 D 再升级成新的核心概念

行动条件信息价值沿既有 D 支线保留，先公开场景假设和程序基线。当前最缺的是 C1/C2 的真实鉴别力与独立过程证据；再加概念会推迟这个出口。

## 4. 状态更新对旧方案的影响

六包和 standalone 多处引用 12:06:47 快照中的“月度原生样例 0/3”。本轮观察已是 **3/3 构建完成**，不把“完成三个样例”继续当首次建设任务；下一步是质量/角色核对和年度去重清单。

本轮已见 3 个整周分片 COMPLETE，各 210 轨迹；第 4 片仍运行。该数量不含最后分片可能已完成但尚未汇总的轨迹，也不等于已做全量正式审计。最新状态需重读回执，不能按经过时间推断。

月样例出现 8 个 conflict、4 个 unparsed 机会状态，是 source builder 的结果，不是 12 个独立事件。3 份未解析 TAF 被保留，不应把 2,470 份已获原文写成全部成功解析。

## 5. 研究新颖性的评估方式

本轮没有重做完整文献检索，不对全球首创或录用作保证。沿用既有近邻比较，再以实际任务做一次最终差异核对：

| 近邻类型 | 本计划需要额外证明的差异 | 会削弱主张的结果 |
|---|---|---|
| 气象预报/后处理 benchmark | 持续多目标合法信息、预算、版本、修订与模型角色分离 | 收益全部来自更强静态映射，未体现查询/时机 |
| 工具使用/主动取证 benchmark | 严格来源支持、物理/产品时间、独立未来参考与强专业流程 | 人为隐藏公共资料或只比弱工具基线 |
| 证据 QA / 溯源 benchmark | 从同一真实状态执行路径，测字段是否进入 F 以及及时采用 | 只有 E 正确率，或者干预的 E 根本不被 F 消费 |
| 多灾种/多模态数据合集 | 同一机制问题跨合格过程与真实模态可复算 | 只有源列表、样例截图或依赖的小时数量 |

最终主张可以是模型在哪些条件下有用，也可以是强程序更好、收益只来自某一环节。必须有真实不同路径、合理对照、固定分母和独立过程支持，不能仅因得到负结果就宣称 benchmark 已有独特贡献。

## 6. 本轮验证边界

实际进行了：七份输入阅读、135 个 ZIP 成员安全解压与 CRC 检查、输入 hash 清单、26 个相关源码副本比对、关键生产调用路径静态核查、当前回执与精确任务的只读平台观察、远端分支只读核验。

未进行：新缺陷 red/green、全部 750 回归重跑、原 fullweek 全量审计重跑、年度新下载/拟合、C2 实际分支、新模型/API/GPU、确认集、推送。审查者测试结果只作为其报告的证据，不冒充本轮生产验证。
