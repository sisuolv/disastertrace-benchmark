# 七份方案的取舍与当前代码核验

日期：2026-09-15。本文是整合依据；总体安排见 [整体计划](OVERALL_PLAN_CN.md)。

## 1. 输入来源与证据等级

原目录：`/mnt/afs/260010168/extreme_weather_benchmark/plan/plan_v11_0915`。
六个 ZIP 分别解压到 `review_extracted_20260915/R01` 至 `R06`，避免同名内部目录互相覆盖。
一份独立 Markdown 为 R07。原文件与解压成员哈希见 `REVIEW_BASELINE.json`。

| ID | 原始文件 | 主要补充 | 本计划去向 |
|---|---|---|---|
| R01 | DisasterTrace_V10_Audit_and_Codex_Plan_1fd6821.zip | 温度入口、特征有损表示、ECC 投影、强共同信息参照、有限保守修订 | W01/W04/W08/W11/T01；残差或门控只留一个有限候选 |
| R02 | DisasterTrace_v10_1fd6821_Review_Codex_Plan.zip | 机器数据卡、完整日历、真实分支，原生 MM 应近期有入口 | W02/W07/W11/T03；MM 元数据配对提前，核心确认不等 MM |
| R03 | DisasterTrace_v10_1fd6821f_Review_and_Codex_Plan.zip | 温度候选补丁、全周预算日界、成员轨迹、性能等价 | W01/W04/W07；不直接套附件 patch，先核当前入口 |
| R04 | DisasterTrace_v10_Audit_Codex_1fd6821.zip | 双端无穷能见度、先四个强对照再扩矩阵、采用与持续性 | W01/W07/W10/W11；初始四条件加 common 锚点为五条件 |
| R05 | DisasterTrace_v10_Audit_Codex_1fd6821_20260914.zip | 全周规模推导、common 锚定残差、同源提取/后端分离 | W07/W08/W10/W11；九策略分阶段补齐，不第一轮全乘 |
| R06 | DisasterTrace_v10_review_1fd6821.zip | claim 后 STOP/截止、超大整数概率、最小模型矩阵 | W01/W03/W12；发送许可边界单独测试 |
| R07 | DisasterTrace_v10_Latest_Implementation_Audit_and_Codex_Plan_20260914_CN.md | 正式来源闭合、claim 崩溃、DWD 绑定、行动/在线长路线 | W02/W03/T01/T04/T05；扩大工程建议分级处理 |

七份材料大都审阅同一个发布提交，并使用重叠源码和合成反例，不能视为七次独立天气验证。
其中六个 ZIP 保存的 31 份源副本对应当前 13 个模块，全部字节一致；这个校验只证明文件身份。
它不证明报告里的所有结论已经由本轮重新执行。

本次实际完成：读取七份主方案/审查与任务列表、定向检查当前模块和已有回执、执行 13 个
直接导入当前包的合成探针。API 使用临时目录、假时钟和离线运输替身，不读真实密钥、不发真实请求。
没有执行完整 720 项回归、两个 capsule、全部天气数据影响扫描或新的 GPU/模型实验。

首个探针脚本将模型 fixture 写成未列入当前费用表的名称，初始化被拒绝，退出 1。
修正测试 fixture 为当前登记的 `deepseek-flash` 后重新执行；原失败记录见
`checks/PROBE_ATTEMPT_01.json`。生产代码未变；13 情形的结果见 `checks/CURRENT_BOUNDARY_PROBES.json`。
`all_observed_as_expected=true` 表示复现预期的正常和异常行为，不是“13 项生产正确性全部通过”。

## 2. 当前已直接复现的四类边界

| 发现 | 当前行为 | 证据范围 | 处置 |
|---|---|---|---|
| 温度 UTC 日窗口 | 较弱函数对中午至次日中午返回 0.5；严格入口拒绝 | 当前函数直接执行 | W01 共享准入，扫描真实输入 |
| 温度重复日期与类型 | 两份同日产品换序，输出 1.0/0.5；NaN/布尔阈值或 day_index 可被接受 | 6 个非法情形，含重复顺序对照 | 不用字典覆盖裁决版本；排除 bool/非有限量 |
| 能见度无有限下界 | `[+inf,+inf]` 双闭被 `parse_features` 接受 | 直接模型响应入口；合法 P6SM 对照保留 | W01 限定能见度域，不全局禁止通用无界 Interval |
| 超大整数概率 | 401 位整数在 `math.isfinite` 抛 OverflowError | 直接输出解析；没核所有上层捕获路径 | W01 统一无效输出，不剪裁成合法概率 |
| claim 后停止/截止 | claim 后读取假密钥时产生 STOP 或越过截止，仍调用离线运输替身 | 2 个实际 capture 路径探针，真实网络 0 | W03 明确 no-new-dispatch 许可点 |

温度源位置：`disastertrace-starter/src/disastertrace/monitoring_v1/feature_tasks.py` 的
`temperature_ensemble_probability`，对照 `temperature_postprocess.py::event_probability`。
模型响应位置：同文件 `parse_features/parse_temperature` 与 `native_feature_forecast.py::validate_claims`。
发送位置：`api_capture_v2.py::capture` 和 `api_ledger.py::claim`。

以上均没有扫描确认旧天气任务实际触发，不能宣布 v10 分数无效。只有扫描全部相关 ID 后才能写
“该范围无已知影响”；扫描不到的文件必须列出，不能计为未受影响。

## 3. 静态确认且需新集成反例的问题

### 正式成绩来源链

`formal_session.py::score_formal` 只接受 journal 路径，并检查 semantics、execution 和 provider-policy
配置字段；没有直接核对该 journal 对应的 FormalSession CONTRACT、checkpoint marker 和终态。
R07 的来源绑定建议有代码依据，但本次未制作完整伪装 journal 来跑穿生产入口。

`score_admitted` 内部用默认 legacy-compatible OutcomeRegistry，但 `score_formal` 在调用它之前
已经做过 formal provider 校验。因此不能写成“当前正式主路径完全没有 provider 检查”。
新增正式运行应走强绑定入口；generic 与 legacy 复算身份要明确，不能靠调用方自行加一个
`formal_required=false` 选项就解除资格。

`experiment_spec` 已经记录 `data_universe_sha256` 与 `bank_sha256`。完整输入角色 manifest 应补
source/raw/derived/target/query/policy/prompt 的来源链，而非重复复制同一数据四次。
新正式引用必须适配搬迁：身份依据相对内容寻址及哈希，不能只绑定绝对本机路径。

### API 不完整 claim 与 body 命名

`ApiLedger.claim` 先 mkdir 再写 reserve，存在未完成状态。当前 reducer 会保守计入未决预留，
原 contract 仍保存该调用的费用上限，因此不等同于“费用未知即归零”。
先 fault injection，再选择同文件系统无覆盖原子发布或明确的不完整状态协议；临时目录必须
不被 reducer 误认未登记调用，落盘与父目录持久化在实际 AFS 上验证。
仅恢复本地记账状态，不以看不到 HTTP 回执为理由免费重发。

`original_body_sha256` 在超长响应时只对应捕获前缀。新 schema 分清 captured/stored/full-body hash，
是否截断、捕获上限及脱敏；完整内容未获得时 full hash 为 null，旧 schema 留兼容解释。
HTTP 错误正文同样注明有界截取范围。

### DWD policy

当前 DWD 绑定验单位、时间、质量、provider/version，未像 H15 那样限定具体 target variable。
按允许的日最低/最高与三日事件构造增加条件检查是合理的，未必需要四套近乎相同类。
集合成员身份属于**预报输入**合同；DWD 观测结果应绑定原生日值和事件归约，不要求观测自己具有集合成员。
原成员坐标不能只凭数组等长认证，须从已有源 lineage 验证；缺坐标证明时声明资格不足，不补造 ID。

### 性能

九方法 `score_formal` 的 1+N 重放，加 `score_admitted` 的 N 重放，合计 19 次。
后者还在每个结果机会创建全 target registry。源码支持存在重复计算；本次没量化各部分占比。
首项优化为一次评分每个 journal 一次完整验证，复用只读对象及 canonical outcomes。
所有共同基线轨迹、结果跨提前量冲突、干预历史、snapshot 完整性校验继续保留。

## 4. 需要修改或降级的建议

| 原建议/潜在解释 | 整合决定 | 原因 |
|---|---|---|
| 要求正式 STOP reason 只能 completed | 改为有验证的终态 + 预登记失败处理 | 防止删除失败和超时造成幸存者偏差；缺可信快照时阻止完整排名 |
| 所有 P0 工程、D/MM、多 pending 都先完成 | 只将相应路径必需项设为门槛 | API 修复不阻塞 CPU，行动并发不阻塞文本 F |
| 每轮再跑 720 项、两 capsule、全部旧模型 | 按改动范围回归；核心接口完成后一次集成 | 不把重复验证当新成果，避免编排和 CPU 开销 |
| 立即跑 9 策略 × 两协议 × 多模型 × 所有预算 | 先五条件全日历，再补四格和强 selector | 完整时间覆盖优先，保留关键归因并限制组合数 |
| 等全年资料完备再做任何程序实验 | 现有完整周开发与年度获取并行 | 已有数据足以检查首日选择偏差和程序路径 |
| 立即推出 common 残差为新主方法 | 只留一个可选训练内候选 | 防止基线建设膨胀成新方法论文；不要求候选赢 |
| 年周期特征永远删除 | 全年训练内部有限比较 | v10 删特征是冬季外推开发诊断，不是通用结论 |
| 没有缺证训练，必须重建 | 保留已实现的合法子集和单位权重，补部署分布审计 | 源码已包含空证据/子集训练 |
| 无法识别自然过程时 region-week 就独立 | 保守块为主，区域周描述性及多尺度敏感性 | 资源/日历单元不认证天气独立性 |
| all-read 是 F 上界，regret 可加成原因比例 | 改称条件信息对照/配对损失；交互单列 | 更多信息可能被后端误用；不保证单调或因果可加 |
| E composition 提升自动应带来 F 提升 | 先验该输出是否实际被后端消费 | 当前后端可能只使用字段，不消费最终布尔归约 |
| MM 等所有文本研究后再考虑 | 近期做 24 目标元数据配对，后续小闭环 | 给原生视觉明确出口，同时不阻塞 H15 核心 |
| 新工作每一步重问 CPU/GPU/私有推送授权 | 沿用用户已有授权，使用新的登记身份与任务边界 | 不增加无意义审批；本轮先规划符合用户当前意图 |

## 5. 科学结果如何约束下一步

- 同 values 后端的 5km 全信息改善约 0.005609，是继续研究信息价值的依据。
  common 自身已较旧 FOLLOW 改善，不能将所有差值归于 C1。
- 首日总体小收益同时伴随 12 月事件块退化，需要完整日历和过程分层；不能通过只留下正例小时修正。
- 澄清后 140/144 能见度正确但 F 未改善，提供 C2 开发证据；不意味着提取无用或允许保留错误提取。
- 235B selector 尚不如同后端空证据及 FOLLOW。先锁合理后端，再测选择；当前负结果保留。
- 四季只有四个全局块，不能从大量小时观测生成过窄置信区间。
- 温度 F-only 可以独立交付；DWD 最终档案仍缺历史逐版本可得性，不能强行承担温度 C1。

## 6. 有意不做的重复工作

本轮不改研究名、不建新引擎、不重新下载已完成的 12 区域周、不重新生成 v10 模型回答、
不再做一次同题提示优化，也不把七个审查包的重叠合成测试数累加。
未对七份材料引用的所有论文重新做系统检索；计划采纳的是与代码和结果相符的设计，
不据这些材料承诺同行认可或保证首创性。确认前更新邻近工作对照只针对最终冻结的贡献。
