# 三份新材料的采纳与修正记录

本文件记录研究取舍，不是新功能完成清单。G/O/S分别指：

- G：[Research Grounded主文](inputs/research_grounded/DISASTERTRACE_V7_RESEARCH_GROUNDED_PLAN_CN.md)及Q0--Q6补丁。
- O：[Research Optimization主文](inputs/research_optimization/disastertrace_v7_research_optimization_98f28a9/V7_RESEARCH_OPTIMIZATION_CN.md)及OPT00--07。
- S：[Open Source主文](inputs/open_source/V7_OPEN_SOURCE_OPTIMIZATION_CN.md)及O1--O6。

## 1. 立即纳入近期计划

| 建议 | 依据 | 整合决定 |
| --- | --- | --- |
| 修订漏斗先行 | G第12节/Q0；S第6节 | W0复用旧输出，明确机会/调用/候选不同分母和分支；不补未产生输出 |
| 更强共同信息基线、回退诊断 | G第4节；O第4节 | W1A报告feature/cell/n/backoff；同一Front新日历比较本地与湾区映射 |
| 证据包×预测器 | G第5节；O第3节 | W2/W3固定目标、状态、base、原始资产/表示/费用；先小池两预测器 |
| E与F动作响应分开 | G第6节；O第6节 | 保留联合E参照，增加事后已测动作响应；不宣称可部署oracle |
| 成本三口径 | G第7节；O第7节 | 端到端等资源主表、匹配预测机会诊断、合理预算前沿分表 |
| 公开事件触发与短计划 | G第7节；O第7节；S第5节 | W4先廉价策略，全部方法享有合理批量与缓存，selector仍计费 |
| 现有开源评分交叉核验 | G第10节；S第7节 | 相同掩膜/权重先核Brier，后按合格类型扩展，不替换旧主分 |
| 全流程校准检查 | O第4节；S第6节 | 拟合、方法选择、完整系统校准、确认按分组隔离；不移植独立同分布保证 |

## 2. 有条件纳入的数据与组件

| 候选 | 条件 | 安排 |
| --- | --- | --- |
| LAMP/LAV/GLMP | 当期版本、阈值、窗口、条件/无条件概率、站点/网格、档案实际可用 | W1A候选；不改旧<1000m任务；受阻不阻塞R轨 |
| EUPPBench station forecast | 站点实测而非ERA5默认格点、forecast/reforecast身份、有效时刻、数据许可 | W1C并行候补；静态数值联调与主动机制分别验收 |
| SEEPS4ALL | 日界、观测/QC、气候统计与业务预报同窗；数据/代码许可独立 | H07日尺度支线，不代替小时链 |
| pysteps | 合格雨率/QPE序列、QC、时间/网格/halo、真实计算成本 | H07领域强对照，既有VIL不能直接输入冒充雨率 |
| GOES FLS | 当时可用的产品、云底/能见度联合定义、来源谱系 | 现状工具增强，非未来纯能见度Gold；不阻塞ABI |
| AFABench接口 | 策略不能收到label/full unobserved features；STOP/费用/时间须适配 | 借act/predict思想，保留自身环境和账本 |
| LEAP | 核心后端与许可证/运行配置能够复现后才比较算法 | 先仅借证据冻结/哈希；依赖未核验不作为必需对手 |
| ExtremeWeatherBench适配模式 | 官方时间/变量/机构映射及静态档案身份 | 借provider/惰性读取，不用inner join丢失机会，不称live数据 |

## 3. 必须修正的新材料边界

1. **O第10节的“更强基线消除增益，因此说明原差异来自后处理”过强。** 无增益与此
   解释相容，但不是唯一归因；固定证据/预测器、交互和不确定性必须共同支持判断。
2. **G/Q5的“连续流量先进入已有引擎”不是现成能力。** 当前target有有限阈值且要求
   非空区间，baseline/candidate/state/policy/scoring约束单概率。点支持和scalar/
   quantile/ensemble必须纵向扩展，不能只换provider或加CRPS。
3. **动作探针还需分固定快照与真实时间差。** 查询耗时会改变基线版本/修订寿命，
   输入响应差与会话最终损失差分别记录，不能统一称纯信息增量。
4. **多阈值删失掩膜不能随样本重归一权重。** 阈值分母、组合可评条件和缺失分析须
   预登记；不能因此声称保持了同一个proper总体评分。
5. **EUPPBench并不自动解决C1/C2。** 时间配对降低数值工程成本，但仍缺合法补证、
   当时输入版本、共享动作和极端过程合同；数值联调不算机制确认。
6. **依赖图不能要求全部新想法完成才能确认。** Q6与OPT07的广泛前置改为按资格
   分级：核心机制确认不等待全部主动MM、BRiG训练、日降水或长期在线同时完成。
7. **共同完整文本不等于数值基线已充分利用文本。** 当前calibration.py是粗特征
   与计数的平滑频率回退。完整TAF可见性、特征利用和最终校准分别验证。
8. **开源调用不自动给出真实独立证据。** FLS/ABI/NWP、LAMP/HRRR、NWPS/USGS及
   GEE/原生镜像保留谱系；独立性不能由接口名称推断。

## 4. 后置或不采用

- BRiG式风险训练、RL和多级模型路由后置；先一步/两步廉价基线，不能继承单位费用/
  固定步数假设下的理论保证。LEAP似然不是真值，同源证据不独立相乘。
- 不采用因偏离先验若干标准差就删除天气极端的默认规则；先看单位、缺失码、官方QC
  与有依据的物理范围，统计罕见性本身不作为剔除原因。
- potential CRPS/EasyUQ评估集内拟合只作事后潜力诊断，不充当正式概率或部署校准。
- Flip-Flop等稳定性为次要诊断，不能代替技能；AFDBench文字风格/数字集合重合不进F主分。
- RHITA为评估侧分组候选，不引入确认集调参、不声称算法簇就是物理独立过程。
- 不因新文献立即新增SFT/GRPO、逐题人工Gold或LLM judge；不以扩大来源数量证明novelty。

## 5. 本次核验范围

三个ZIP原字节不变；解压成员及CRC/哈希见`INPUT_BINDINGS.json`与
`PACKAGE_VALIDATION_LOCAL.json`。本轮定向读取的上游原文、Git blob与响应哈希见
`reference_checks_01/RECEIPTS.json`、`reference_checks_02/RECEIPTS.json`。
主要核实LAMP BUFR/LAV差异、IEM部分历史周期、EUPPBench数据入口/身份、SEEPS日雨量
与许可说明、AFA可选label及potential CRPS源码的评估标签拟合。

没有安装或执行上游算法，没有新增科学数据数组或模型推理。文献其余结论沿用用户
材料的明确阅读范围，不声称本轮重新全文复现或穷尽查新。当前97项已验证计数保持原义。
