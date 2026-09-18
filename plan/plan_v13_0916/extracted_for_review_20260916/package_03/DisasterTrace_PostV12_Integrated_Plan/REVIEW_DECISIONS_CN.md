# 九份材料的取舍与合并记录

此表是整合者的裁决，不改写原材料。原审查者的探针结果仍属于其报告；本轮额外执行范围见LOCAL_CHECKS.json。原材料没有单一一致的“批准计划”，不能按P0标签数量投票。

## 输入身份

| ID | 本轮原始输入文件 | SHA256前缀（完整值见manifest） |
|---|---|---|
| A | `DisasterTrace_v12_Audit_Codex_1eba36d(4).zip` | `29ff095d329c1aed…` |
| B | `DisasterTrace_v12_Audit_Codex_1eba36d_20260916(4).zip` | `cfeffb5a42ab66a6…` |
| C | `DisasterTrace_v12_review_1eba36d(4).zip` | `c0a787f910a3b03a…` |
| D | `DisasterTrace_v12_1eba36dd_Review_and_Codex_Plan(4).zip` | `c4ef34e04c66df6e…` |
| E | `DisasterTrace_v12_1eba36d_Audit_Codex_Plan(4).zip` | `b3afabc4eb47ce75…` |
| F | `DisasterTrace_V12_Audit_and_Codex_Plan_1eba36d(4).zip` | `7f5ffd1f3135f5e9…` |
| G | `DisasterTrace_1eba36d_Audit_and_Codex_Plan_CN(5).zip` | `81238dac2a98f037…` |
| H | `DisasterTrace_1eba36d_Review_and_Codex_Package(4).zip` | `149a83ba7db4e5f1…` |
| I | `DisasterTrace_v12_Latest_Implementation_Audit_and_Codex_Plan_20260916_CN(4).md` | `60783fdbacafa564…` |

## 各输入的主要吸收点

| 来源 | 主要吸收 | 需要限制或另行选择 |
|---|---|---|
| A | schema不是预算器，query_order为排序；时点/信息前沿拆分；强程序与确认 | 24请求/23合法等门槛不能与其他包相加；统一为单独冻结的24例接口门槛 |
| B | raw max-only与ECC范围；两键query-only；公共动作合法与执行分开 | 48调用成对接口试验只在研究schema单因素时另立，不与默认24同时必跑 |
| C | 分支缺文件/trace仍passed；精确分母与调用级绑定；脱敏前截断判断 | 缺报告反例不等于已发布24个真实分支缺失；合成检查不当真实天气 |
| D | 现有生产路径最小修复、字段/预算一致、限定模型角色 | 温度问题只挡温度轨；兼容性24+额外probe不自动增加预算 |
| E | 原生视觉近期资格可并行；输入状态普查；资源和数据角色 | 24影像只是资格上限，有新HTTP需另批；不让VLM先于真实资产资格 |
| F | 格式/动作/执行/科学分四层；强程序一步/两步需训练支持；C1/C2单独证据 | 不建新RL/agent框架；预期VOI无合法支持则不适用，不用hindsight代替 |
| G | 实际worker最后门槛、capture hash、C2分析器；全年同条件对照与双确认 | 旧报告中的9/8局部测试不当本轮已执行或628全量回归 |
| H | 恢复response之后消费者仍拒绝；FOLLOW配对bank标签错误；生产消费者端验收 | 本轮重跑了隔离恢复/配对，底层spool是替身，尚需生产故障与历史影响扫描 |
| I | query-only语义、残余新获取、测试nodeid差异、时间/mask支持、温度谱系、双确认 | 首批过宽；单键与两键二选一；all/none与非零regret不得硬gate；D不新增核心 |

## 实质分歧的最终处理

| 编号 | 源材料意见 | 本次决定 | 理由/当前代码证据 | 对应工作 |
|---|---|---|---|---|
| D01 | 九份P0全部首批做完 | 不采纳并集；按消费者门槛拆分 | 温度、API、H15与搬迁不是同一依赖链 | R0与支线 |
| D02 | 单键query_order vs两键 | 首批保留两键，forecast_handles=[] | 仓库SELECTOR_INTERFACE_V2_PROPOSAL明确保留两键；少改接口面积 | R04 |
| D03 | 12/24/48接口次数与95%/全过 | 默认≤24真实形状请求，先冻结全过合同；48只为单因素对照 | 不把不同建议累加；小样本不证明总体高可靠率 | R20 |
| D04 | 必须出现subset/reorder | 不采纳 | none/all可以是合理策略；公开费用同形不等于信息相同 | R07/R21 |
| D05 | 最好动作不能恒为all/none、强程序regret非零才Go | 删除硬条件，保留描述诊断 | 根据Y选非平凡性容易制造有利任务；真实合法空间及消费可检查才是先决条件 | R07/R12 |
| D06 | GET24分支完成=处理干预完成 | 明确仅GET完成，PROCESS单列 | 现行报告的treatment文字不等于TAF processing | R13 |
| D07 | 修capture或发送门槛即可恢复 | 扩为发送—capture—reconcile—消费者一条链 | production.resolve先检查failure，reconcile只写response不足 | R03 |
| D08 | 缺报告继续算其余配对 | 可部分诊断但不能complete=true | analyze_branches以已存在报告集合比较并沿用execution.passed | R01 |
| D09 | F_COMMON之外都是同bank | 改按actualconsumer/bank/feature/calibration身份 | analyze_stage_c以名称异或判bank_difference；FOLLOW不消费native values | R02 |
| D10 | first/second/all是错误必须改旧结果 | v1保持，v2定义new-acquisition | residual源码记录cache/request但eligible仅related/available；不同语义须版本化 | R05 |
| D11 | 有请求历史就全局排除qid | 不采纳全局排除 | 私有权限/付款目标、未知reserve与合法cache是不同状态 | R05 |
| D12 | 再建全年bank作为默认下一步 | 先审计时点与同条件结果；有依据才newbank | fit已完成，StageC只用raw；新首日/旧全周不可直接相减 | R06/R10/R11 |
| D13 | 下一bank使用2024全年校准 | 保持2024-01..11，Dec继续排除 | 当前fit_annual冻结registration明确；旧月不可凭新计划变未读 | R06/R10 |
| D14 | 在2024做策略感知选择并校准 | 策略/超参在2023训练内选择；2024只对选定系统校准 | finalcal与调参职责必须分开，既有暴露记录保留 | R06 |
| D15 | 直接复用原parent换新bank | 不允许 | bank是父状态身份的一部分；新bank重建新父前缀 | R10/R12 |
| D16 | 内容寻址manifest与所有capsule搬迁为首批硬门槛 | 显式资格标签先行，完整搬迁按目标范围后置 | 不删现有formal绑定，不把legacy评分当正式资格 | R08/支线 |
| D17 | 温度/DWD/成员/动态prompt全部首批 | 按温度路径前置；不阻塞H15 | 形状检查不足，但无证据全部历史成员错误 | T01 |
| D18 | MM永远最后 vs现在即做VLM | 近期已有资产资格并行；新影像/模型另批准 | 真实processor与时空/来源资格先行 | M01 |
| D19 | 行动层后续作为新增核心 | 不采纳升级；保留既有D支线 | 稳定C1/C2与第二主动链之前不改论文中心问题 | D01 |
| D20 | 模型不显著就可称没有价值 | 不采纳 | 非显著不等于等价；需要实用差异界与过程精度 | R30/R31 |
| D21 | 任一支线未完成则总协调器持续等候 | 分轨终态，失败阻塞相关后继 | 执行终止、工程通过、科学完整性不同 | R08 |
| D22 | CURRENT_PHASE必须等于包含它的未来HEAD | 用已观察publishedSHA+独立上传回执 | 避免自引用；不要求用git reset消除独立发布工作树差别 | R00 |

## 新补充的执行约束

新HTTP/API/GPU/拟合/确认均需对应新scope；工程gate通过不是授权。旧 failure/raw回复/费用/STOP/分母不可覆盖。恢复可以恢复消费或对账，不能倒填旧截止。统计要区分方法机会、目标、会话、公开输入状态、来源依赖与独立天气过程。所有“首批完成”必须由实际回执证明。
