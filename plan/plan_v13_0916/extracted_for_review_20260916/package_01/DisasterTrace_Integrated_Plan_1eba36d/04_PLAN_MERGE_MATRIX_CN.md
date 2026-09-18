# 八份 ZIP 与主 Markdown 的合并矩阵

本表保留来源编号，避免把多份审查提出的同一个问题统计成多个独立缺陷。文件名与原始 SHA256 见 INPUT_MANIFEST.json。所有“工单”均为新提案，不是已执行结果。

| 输入 | 主要应保留的建议 | 本方案去向 | 修正/限制 |
|---|---|---|---|
| P01：DisasterTrace_1eba36d_Audit_and_Codex_Plan_CN(2).zip | C2 缺报告仍通过；最终发送许可；capture 哈希；整周与年度桥接；GET/PROCESS；支线不阻塞 H15 | A01/A02/B00/B01/M00 | 合成反例不能当旧运行实际故障数；既有 probe 在本次复制目录重新执行 |
| P02：DisasterTrace_1eba36d_Review_and_Codex_Package(1).zip | 原 capture 恢复后仍被 failure 阻断；FOLLOW 消费者差异；年度 bank 完整日历；双确认 | A02/A04/B00/D00 | 不删除失败解决恢复；把消费者身份从单一布尔标记改为完整因子指纹 |
| P03：DisasterTrace_V12_Audit_and_Codex_Plan_1eba36d(1).zip | 接口结构/语义/可执行性/科学价值分层；轻量选择器；C2 多样前缀；分级成果 | A03/B02/B01/D02 | 不要求动作必须复杂；oracle 非零不等于公开可学，不先做大型 RL |
| P04：DisasterTrace_v12_1eba36d_Audit_Codex_Plan(1).zip | CPU、C2/多模态、有界模型三条线；后端与日期分离 | B00/B01/M00/C00/C01 | 保留并行，但共享核心接口由单一负责人冻结；不能并行改坏同一账本 |
| P05：DisasterTrace_v12_1eba36dd_Review_and_Codex_Plan(1).zip | 温度 raw/完整产品资格不一致；有界 query-only；过程与确认角色；X09/D 分轨 | T00/A03/D00/V00 | 温度问题只阻塞温度，不变成下一次 H15 的总 P0 |
| P06：DisasterTrace_v12_Audit_Codex_1eba36d(1).zip | 首次结算 capture 完整性；格式、时点、证据支持三类混淆；保留 A→B→C→D | A02/B00/B02/总体 DAG | 不立即归因为模型推理差，不因 clock 风险直接训练 |
| P07：DisasterTrace_v12_Audit_Codex_1eba36d_20260916(1).zip | 目标局部温度校验与 member lineage；训练多时点/子集权重；最多48次接口小试 | T00/B03/C00 | 48 与主 MD 的12不是可相加额度；本方案默认提议12，任何改变须新冻结 |
| P08：DisasterTrace_v12_review_1eba36d(1).zip | 脱敏后长度导致截断误判；C2缺trace交集弱化；时点桥接及新信息/消费者/调度三增量 | A02/A01/A04/B00 | 不仅重命名 hash 字段，要修真实完整性判断；本次另在隔离目录复现 |
| U09：DisasterTrace_v12_Latest_Implementation_Audit_and_Codex_Plan_20260916_CN(1).md | 状态入口、node IDs 对账、strict schema、residual新增语义、formal资格、clock、action census、温度、双确认、行动价值 | 全方案的基础骨架 | 把过长串行清单改成路径依赖；補 P01/P02/P08 独有恢复/分析缺陷；第一批不囊括所有灾种 |

## 共识：保留而不重复实现

v12 已完成其登记的年度来源、有限 C2 分支和首轮 selector 比较；旧回复、旧失败和 unknown fee 保留；不用更大模型代替信息价值分析；父状态选择不读取未来标签；确认集先冻结协议再开启；温度 F-only 不升级为主动链；原生多模态必须实际进入请求；16 类按资格分阶段推进。

## 不采用简单并集的六处原因

1. 不同作者的“P0”对应不同路径，合在一起会人为阻塞所有工作。
2. 12/48/288 是不同用途与范围的提案，不能相加，也不形成已经批准的预算。
3. 旧 fullweek 与新年度 Stage C 并非后端升级的成对比较，先补桥接再解释。
4. 严格子集/重排不是普遍优于全取/不取；非平凡信息价值不等于动作形式多样。
5. 各 ZIP 中 probe 通过代表审查观察复现，可能正是在复现漏洞；不是仓库通过全部测试。
6. 新增图像、ActionSpec、portable manifest、全16类扩展不应全部挤入首个修复批次。

## 本轮新增整合判断

- 给 C2 加“有限 E 可达性”和“全残余会话效应”两个出口，避免只证明 feature hash 变化。
- 给强程序加入有界预期最终损失选择器，优先适配 AFABench 的策略思想，而不复制新运行框架。
- 单独保留后续模型 E/F 角色，避免 query-only 因子实验永久缩减原 benchmark。
- 将 ScenarioCard/程序行动原型、first_seen recorder 设计提前为旁路；实际联网/模型行为仍需独立授权。
- 以内容身份区分自然日历、来源状态诊断、已暴露开发、密封确认与 prospective。
- 对截止许可强调本地线性化边界，不承诺网络世界不可验证的严格 exactly-once。
