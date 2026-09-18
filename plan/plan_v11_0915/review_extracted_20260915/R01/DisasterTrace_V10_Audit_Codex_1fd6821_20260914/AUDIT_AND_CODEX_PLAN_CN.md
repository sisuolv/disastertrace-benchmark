# DisasterTrace v10 实现复查与 Codex 增量计划

## 0. 固定依据、审阅范围和结论

代码基线：`next-phase-v1@1fd6821fef15b26898a57c74d4715714f33ea779`。
提交时间：2026-09-14 23:30:56 UTC（纽约时间9月14日19:30:56）。父提交为 `6f71c8799ff69439a18f645e63b8c966ca21eec4`。

本文件延续现有 C1/C2/C3、P0–P3 与六组16类灾害，不另建执行引擎或研究版本。任务目录是对现有计划的增量拆解，不是已经实施的代码。执行代理必须检查本地最新状态，不能回退到本文提交覆盖之后的工作。

本次阅读最新进度、整体/后续计划、复查入口与有关源码。实际完成3份完整源码Git blob核验、21项合成CPU行为检查。`temperature_postprocess.py`和`regional_calibration_v2.py`原样执行；`feature_tasks.py`只按AST提取未修改的温度概率函数，未加载无关的解析依赖。没有重新运行720项仓库测试，没有全量重建实验，没有新增网络数据、模型/API或GPU运行。两个上游portable capsule没有在本环境成功取得并执行。所有实验规模与真实性能来自仓库报告，不冒称为本次独立重算。

结论：当前实现应继续复用；本次确认一个温度入口校验不一致，尚无证据证明已发布输入触发了它。其他重点是已披露的实验解释与性能优化，而非需要推翻旧结果的新漏洞。下一步的研究主瓶颈是季节/过程稳定性与强基线，不是模型调用规模。

## 1. 当前成果登记与不可混淆的分母

依据最新报告：720项不同monitoring测试通过，37项格式整理重跑是重叠分母。23个云作业全部结束且平台SUCCEEDED，H100峰值4卡；GPU分配区间总和约15.99GPU小时不等于实际利用率或账单。

本轮2812个benchmark回答：固定输入2016、27B提取/温度212、235B同题212、235B selector288、澄清提取84。另有15次兼容性调用/尝试，两次402导致424个登记任务未尝试；不将它们列为模型答错。

四季原始日历为2025年3月3日、6月2日、9月1日、12月1日开始的完整周，纽约/芝加哥/丹佛共12区域周，每区3站。每阈值6048机会、6008已结算、40缺失；1km29正例、5km307。它们是四个共同日历块，不是12个已证实独立天气过程。

首日预算控制为216个程序会话，每阈值864登记/861已结算。1km无正例，5km16正例全部位于12月。不得将完整周29/307正例移用到首日控制。

温度已有24个月连续版本流，2017拟合/2018开发EMOS+ECC。它不再是待首次连接；但仍为F-only：最终DWD归档729天可读，严格历史补证资格为0，没有逐版本公开时间证据。

已完成的小型重建交付为818成员与1162成员两种capsule。继续维护其限定范围，不再建立第三种同类包来重复记进度。

## 2. 哪些旧问题已经改好

正式入口 `FormalSession` 强制生产身份、来源/结果政策与`measurement.v3`；恢复时保留STOP，正式标记早于worker释放。它明确是受管理执行，不是任意Python对抗沙箱。

选择器重复JSON键已有严格拒绝；API不可变escrow保留未知费用与失败。无需把旧v9问题原样重做。

新H15后端从计数映射推进到三分类softmax：`p(vis<1000)=p0`、`p(vis<5000)=p0+p1`，原始概率具有嵌套一致性。旧FOLLOW的研究映射仍保留，不能称官方原生概率。

新校准敏感性实现把总先验质量固定为2，再按样本权重分配给概率单元。局部实验确认：100个零结果无论原始概率完全相同或相差1e-12，输出都约1/102，不再出现旧的每不同概率添加一对伪计数膨胀。

原生特征训练包含空证据及全部合法子集，每个信息单元权重总和为1，避免简单因多个视图增加样本量。后续还须验证部署时自适应缺证分布，但不能说当前完全没有缺证训练。

## 3. 本次实现发现与修改原则

### F01：温度两入口校验不一致（局部复现，P1）

`feature_tasks.temperature_ensemble_probability`只检查支持长度为整日倍数，没有检查UTC日界，重复日期会被字典覆盖，阈值未检查有限性。新`temperature_postprocess.event_probability`对这些条件严格拒绝。

合成反例：

| 输入 | 较早函数 | 新函数 |
|---|---|---|
| 中午到次日中午，读取日历日极值 | 返回0.5 | 拒绝非UTC完整日 |
| 同日重复两条互相矛盾产品 | 后项覆盖，返回1.0 | 拒绝重复日 |
| threshold=NaN | 返回0.0 | 拒绝非有限阈值 |

这些没有证明实际冻结记录违规。Codex首先读原始包和已存在上游校验，列出每个入口调用路径，再迁入正式回归、扫描既有记录。合法数据不变，旧捕获不修改；错误数据如存在先隔离并做版本化结果更正，不选择性保留。

共用准入规则可以集中，但数值参考保留独立实现，避免为了“一致”把两份本应独立的审计都调用同一个运算函数。

### F02：values是有损特征，不是完整信息的等价变换（静态）

代码验证开闭端点，但向F提供上下界log、infinite、missing等，没有`lower_closed/upper_closed`。同上下界不同开闭区间可能在E上支持不同结论，在F上却成为同一个向量。裁剪到20000米、温度±100以及TAF分类化同样属于明确压缩。

不是所有压缩都错误，也不能由此推出当前真实天气结果算错。先统计实际数据中的相关边界与碰撞，再决定是否新增小特征。新增须修改feature_version并重拟合新银行，不能把旧银行系数直接套新定义。相同原文、信息有损特征和专业解析工具分别命名。

### F03：EMOS/ECC修复是声明的设计，不是隐瞒的bug

原生成员按每一维秩重排，再对违反min≤max的成员投影为中点。局部测试确认原数组不被修改，修复次数有trace。该投影可能改变原本的Gaussian边际与秩关系；tie用原始成员顺序处理也属于确定的约定。

下一步只需分季节/时距统计投影和tie、受影响目标，再列修复前后诊断。不得将最终产物称为严格保持所有原边际的联合校准分布。首要目标不是增加更复杂copula，而是确认这项已有变换实际影响多大。

### F04：重复日志重放是已披露的性能问题

`score_formal`先载入第一个日志，再逐臂载入，最后`score_admitted`再次逐臂载入。九臂正常路径为19次完整from_journal。`FormalSession.step/persist`又对全部绑定文件重新读取校验；它的实际耗时占比本次没有测量。

优化必须先profile后修改。优先同次评分复用已验证、只读的引擎对象，依然执行结果/共同基线/比较/干预轨迹/事务校验。不要让调用者随意传一份伪造快照冒充verified engine，不按mtime缓存跨版本结果，不跳过原生来源验证来换速度。

实际运行中生成197秒，model-ready到完成110.6分钟，其他阶段未分段计时。不能把差额全部归因于AFS、CPU或本项重复读取，也不能预估19倍加速。模型释放GPU与CPU审计分离，并保存完整run状态。

## 4. 结果要求怎样更新研究重点

### 4.1 已有信息增益，不等于已有Agent优势

四季5km原始Brier：旧FOLLOW0.043130；去年周期后common0.036448；同values无证据0.038827；同values读全0.033218。

可精确区分：
- 共同信息换后端：0.043130→0.036448。
- 固定values后端加全部登记证据：0.038827→0.033218，改善0.005609。
- 后一项是固定资料条件，不受48信用约束；不能称主动策略成绩。
- 1km读全0.004738仍略差于common0.004667，不存在普遍“更多资料更好”。

去年周期特征是看过开发结果后的选择，虽然重新拟合没有使用季节标签，仍然不是独立确认。保留原银行及负结果。

### 4.2 完整日历与危险过程必须同时报告

首日5km coverage总体Brier0.00962590，略低于FOLLOW0.00983541、batch0.00975196；但全部16正例集中12月。coverage对FOLLOW在3/6/9/12月块的平均增益依次为+0.004947、+0.003043、+0.003722、-0.010882，12月对batch也为-0.001222。

总体均值不是虚假的；如果研究总体就是这些登记机会，它回答了该总体上的问题。问题是它不足以证明高风险天气识别改善。不能删掉平静日求正例成绩，也不能将条件在事后Y上的分数当成完整概率评测替代物。

保留自然日历proper score为主；预注册过程分层、严重事件召回/虚警/及时性与风险排序辅助解释。主次指标和阈值在新确认载荷打开前固定。缺失结果补全界不是抽样置信区间。

### 4.3 提取改善要直接联到同一个预测器

普通样本235B能见度字段25/144→140/144，但固定流水线5km Brier0.070288→0.070545；原生程序提取为0.070546，FOLLOW0.065545。接近程序事实后F接近较差的程序后端，不能宣称正确提取无用或模型越聪明越差。

下一轮在一开始就写清报告标签/物理量、主报文/remarks与删失规则；错误后澄清轮继续作为开发证据。将合同解释、字段提取、逻辑归约、预测器利用和采纳分别配对，不在旧84任务无限修prompt。

### 4.4 强参考应为同信息强基线B*

现有FOLLOW保留为稳定历史比较，另预登记同信息强共同后端B*。主比较至少包括：B*、同values空证据、同values部分/全部证据、预算内策略。C1总体胜过较弱旧投影的差值不能全算取证收益。

可以添加一个轻量保守修订参考：廉价规则判断资料时效与缺口，冻结统计模块估计补证收益，必要时缩回B*；使用训练/校准数据设定门槛，而非在测试看到结果后选是否采纳。它不保证逐题改善，也不需要训练大型RL。

## 5. 接到当前P0–P3的实施规格

### P0：先完成有限正确性和运行成本工作

VT00–VT03是第一批：不启动任何新模型；既有数据只读。迁入F01反例、H15合同绑定、分阶段重放profile；对已有银行与EMOS结果做有界语义诊断。已有capsule可以由Codex在其机器按README重放一次，不重新造同类包。

### P1：完整历史年，而不是只扩大同一冬季频率表

现有计划提出2023拟合、2024校准、2025已暴露开发，可作为候选。先做源依赖/月份覆盖/失败和预算清单，核验与旧训练、提示材料的关系，再实际冻结角色。一次性全量请求前在一个已有或有界获准月份估计实际文件与接口成本；不根据结果替换月份。

周期特征在完整季节训练时可能合理，不能把“删year永远最佳”当结论。少量候选正则/表达选择只在训练内部按时间或过程切分，独立校准保持后置。common/mask-age/values支持相同目标和合法mask，但评估自适应选择造成的缺证分布差异，不暗示统计校准被自动保留。

### P2：自然过程与确认资格

四个全局日期块而非12独立过程。目标窗、证据回看、TAF原生版本、同场天气与跨站依赖都入分组；资源重置不改变物理独立性。自然背景与富集机制集单列，不用正例数临时选确认窗口。

Bay2025-02-17..23保持封闭，一个未看周只支持其自身范围；确认规模由开发过程差异与希望区分的效应/区间精度决定。历史回放的时间限制不消除模型预训练事件知识风险。新的前瞻影子运行需单独授权并先保存提交，不能在本聊天承诺后台执行。

### P3：同后端与同预测日程，先程序再模型

先用完整预登记日历复核预算控制，不仅首日。48查询信用保留为旧实验连续对照，再根据实际费用增加少量预定档位和不紧预算条件。所有策略具备相同批量/并发/专业工具，不人为提高廉价站报费用。

固定coverage做2x2是分配与共享研究，B11下再换selector才是策略研究。固定分额用不满全局上限需要单列解释。查询计划的机制重放与实际LLM耗时的端到端轨分开，前者不能当部署加速。

联合E可达性只评价同一合法路径上的事实覆盖，不能成为F优化的oracle。选择目标、查询、预测调度和采纳需要分别可记录，不能把方法所有差异都归为“证据更有价值”。

## 6. 跨领域工作保持边界

温度：继续F-only，并完成2017/18分季节、时效、事件、连续量和后处理稳定性。已有729天最终DWD结果不能借助固定lag成为真实历史证据。可以另列受控最终档案诊断，但必须显式说明使用非vintage资料；严格C1另找真正历史版本/可用性证据。

H07：先完成精确降水率/累计起止、质量、预报与未来参考，再用已有专业短临作为等权工具。VIL、彩色图、日累计不能直接替代分钟毫米降水。H08：继续QINE支持、调控、成员、断面/站点、阈值与参考配对，不为了叙事把不同来源强拼。

两者只需一条先成立即可推进新证据机制，另一条保留阻塞。其余16类分项准入继续，不同步扩成16套复杂Agent。D/MM/联合风险/online具有独立出口，不作为全部F发布的统一前置。

## 7. 有限参考方法、实验与novelty

主实验链：强共同信息B* → 合法补证与处理 → 固定预测器 → 可撤回/过期的预测覆盖 → 独立未来结果。

建议少量互相正交实验：
1. 固定资料比较程序、模型和结构化处理。
2. 固定预测器比较查询、共享、预算和简单一/两步策略。
3. 固定同一前缀更换一个实际存在的资料/处理环节，保持继承资源与在途状态。
4. 固定候选和完成时刻研究采用规则，完整重跑另列。
5. 固定方法后做独立过程与小规模前瞻记录。

所有替代资料必须真实存在；分支不重置费用、缓存与权限。事后最低损失只能是有限诊断，不成为测试时的“已知最优”动作。E事实充分不认证未来概率，多个机制改善不相加成互斥原因百分比。

仍以C1/C2/C3描述贡献：C1测信息、处理与时间的增量，C2用真实重放区分误解和无预测价值，C3验证跨过程与明确资料资格。校准、softmax、ECC、缓存、日志均不是独有创新；不能通过更复杂的环境名称保证novelty。最终可以保留LLM没有净增益，但任务与强对手必须有解释力。

## 8. 运行与报告要求

执行包不自动恢复已完成的自治窗口。第一批仅本地实现和CPU验证；已存在有效授权可按其范围执行，不能由本文扩大。新数据/API/GPU/拟合/确认/推送分别查验范围。模型权重、凭据、临时签名链接不得进入输出。

运行报告按以下栏目给证据：已改源码；合成回归；真实数据检查；模型实际请求/收到回答/未尝试；失败和未知费用；科学支持；未完成门槛。不要按测试数、调用数、日历数宣称独立样本或全部完成。

保持历史银行、prompt、源、回答与分数不可变。若修复改变结果，生成新的版本与影响清单；若只加强校验而真实输入均合法，声明零已知影响，避免无必要重跑。

## 9. 本包复查方式与来源

运行局部检查：

```bash
python3 -B checks/run_checks.py
```

需要Python3.10+、只用标准库，输入全为脚本生成的合成资料。3项源哈希与21项行为检查分母分开。`observed_as_asserted`包括正确拒绝和复现旧入口接受非法输入，不代表生产代码“21项全部正确”。

`SOURCE_INDEX.json`列出本次读取的固定提交路径、范围和原论文/官方文档；`FINDINGS.json`分清局部复现、静态压缩限制、已披露设计与科学门槛。`CODEX_BACKLOG.json`包含12项增量任务及依赖。

本次未重跑两种上游capsule、完整模型或全原生ETL。它们在仓库的搬迁回执是项目已有证据，不是本审查独立运行证据。

### 固定源码与报告入口

- [LATEST_PROGRESS_V10_CN.md](https://github.com/sisuolv/disastertrace-benchmark/blob/1fd6821fef15b26898a57c74d4715714f33ea779/LATEST_PROGRESS_V10_CN.md)：全篇分段读取；最后计划部分以独立NEXT文件为准
- [plans/v10_execution_20260914_01/OVERALL_PLAN_UPDATED_CN.md](https://github.com/sisuolv/disastertrace-benchmark/blob/1fd6821fef15b26898a57c74d4715714f33ea779/plans/v10_execution_20260914_01/OVERALL_PLAN_UPDATED_CN.md)：前180行
- [plans/v10_execution_20260914_01/NEXT_PHASE_PLAN_CN.md](https://github.com/sisuolv/disastertrace-benchmark/blob/1fd6821fef15b26898a57c74d4715714f33ea779/plans/v10_execution_20260914_01/NEXT_PHASE_PLAN_CN.md)：主要P0–P3、第二主链及模型资源部分；响应后段截断
- [publication/v10_execution_20260914/README_CN.md](https://github.com/sisuolv/disastertrace-benchmark/blob/1fd6821fef15b26898a57c74d4715714f33ea779/publication/v10_execution_20260914/README_CN.md)：全部
- [publication/v10_execution_20260914/REVIEW_FOR_CHATGPT_PRO_CN.md](https://github.com/sisuolv/disastertrace-benchmark/blob/1fd6821fef15b26898a57c74d4715714f33ea779/publication/v10_execution_20260914/REVIEW_FOR_CHATGPT_PRO_CN.md)：全部
- [disastertrace-starter/src/disastertrace/monitoring_v1/native_feature_forecast.py](https://github.com/sisuolv/disastertrace-benchmark/blob/1fd6821fef15b26898a57c74d4715714f33ea779/disastertrace-starter/src/disastertrace/monitoring_v1/native_feature_forecast.py)：全部；静态审阅，未加载此模块
- [disastertrace-starter/src/disastertrace/monitoring_v1/formal_session.py](https://github.com/sisuolv/disastertrace-benchmark/blob/1fd6821fef15b26898a57c74d4715714f33ea779/disastertrace-starter/src/disastertrace/monitoring_v1/formal_session.py)：全部；静态审阅，未运行真实journal
- [disastertrace-starter/src/disastertrace/monitoring_v1/temperature_postprocess.py](https://github.com/sisuolv/disastertrace-benchmark/blob/1fd6821fef15b26898a57c74d4715714f33ea779/disastertrace-starter/src/disastertrace/monitoring_v1/temperature_postprocess.py)：全部；原样标准库执行；Git blob核对
- [disastertrace-starter/src/disastertrace/monitoring_v1/feature_tasks.py](https://github.com/sisuolv/disastertrace-benchmark/blob/1fd6821fef15b26898a57c74d4715714f33ea779/disastertrace-starter/src/disastertrace/monitoring_v1/feature_tasks.py)：全部；仅temperature_ensemble_probability函数AST隔离执行；Git blob核对
- [disastertrace-starter/src/disastertrace/monitoring_v1/regional_calibration_v2.py](https://github.com/sisuolv/disastertrace-benchmark/blob/1fd6821fef15b26898a57c74d4715714f33ea779/disastertrace-starter/src/disastertrace/monitoring_v1/regional_calibration_v2.py)：全部；原样标准库执行；Git blob核对
- [plans/v10_execution_20260914_01/scripts/fit_native_feature_bank.py](https://github.com/sisuolv/disastertrace-benchmark/blob/1fd6821fef15b26898a57c74d4715714f33ea779/plans/v10_execution_20260914_01/scripts/fit_native_feature_bank.py)：前255行；未运行拟合
- [plans/v10_execution_20260914_01/scripts/fit_temperature_postprocess.py](https://github.com/sisuolv/disastertrace-benchmark/blob/1fd6821fef15b26898a57c74d4715714f33ea779/plans/v10_execution_20260914_01/scripts/fit_temperature_postprocess.py)：前230行；未运行拟合
- [disastertrace-starter/tests/test_monitoring_temperature_postprocess.py](https://github.com/sisuolv/disastertrace-benchmark/blob/1fd6821fef15b26898a57c74d4715714f33ea779/disastertrace-starter/tests/test_monitoring_temperature_postprocess.py)：全部；阅读，未执行仓库pytest

### 定向外部资料（本次已读取，不表示完整方法复现）

- https://scikit-learn.org/stable/modules/calibration.html：概率校准与区分、独立校准数据；不要求更换现有库版本
- https://arxiv.org/abs/1302.7149：ECC原论文摘要中的边际后处理与原始秩重排；非新颖性独有组件
- https://hypothesis.readthedocs.io/en/latest/stateful.html：状态序列差分测试思想；可先用有限枚举
