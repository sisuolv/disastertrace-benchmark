# v10 复查意见的落实与保留门槛

复查输入是 `plan_v10_0914` 中六份 ZIP 和独立实施审查文档；具体文件哈希见 `BASELINE.json`。
审查基线为 `6f71c8799ff69439a18f645e63b8c966ca21eec4`。本文件把共同要求归并为可核验工作项，
不把不同审查文件中的同名 N 编号当作同一个任务，也不把建议理解为已验证的结果。
动态执行状态见 `CANONICAL_STATUS.json`，收尾时以 `FINAL_RESULT.json` 为准。

## 1. 测量与工程

| 复查要求 | 本轮落实 | 证据入口 | 范围限制 |
|---|---|---|---|
| 当前/历史状态不能互相矛盾 | 新命名空间与规范状态；旧暂停记录保留 | `CANONICAL_STATUS.json`、`reports/existing_audit_01` | 未完成任务须明确标为运行中，最终状态以实际回执生成 |
| AFS 共享可变账本不可靠 | 独立、不可变、按调用预留与结算；禁止用旧未知项释放预算 | `api_ledger.py`、`reports/ledger_afs_stress_02` | 64 并发文件压力通过；不声称对任意分布式存储实现事务保证 |
| HTTP 错误与 post-response 信息不能丢 | 保存嵌套错误体、响应、计费用量和未决状态 | `api_capture.py`、`test_monitoring_api_ledger_v2.py` | 两次 402 没有可结算用量；不能推定为零费用 |
| provider-specific policy 与 production-bound 不能只是可选 | `FormalSession` 在构造、恢复、步进时强制校验 | `formal_session.py`、`reports/formal_real_01` | 通用研究辅助入口仍存在；论文正式成绩应从正式入口产生 |
| 分支事件和预测开始事件的顺序明确 | `measurement.v3` 在已封存之后、下一事件处理之前执行干预 | `admission.py`、`test_monitoring_v10_contracts.py` | v2 历史语义与旧结果保持不变 |
| selector 重复键不能被覆盖 | 严格 JSON 和嵌套唯一键拒绝 | `test_monitoring_review_v10.py` | 失败输出保留，不选择性修复原回答 |
| 正式会话 pending 恢复必须可验证 | 正式标记在外部 worker 可见前落盘；原目录恢复和 STOP 封闭 | `formal_recovery_01/RESULT.json`、`test_monitoring_formal_restore.py` | 四个新进程、一个真实原生查询；当前仍为单所有者串行 pending |
| 结果量不能冒充测试通过数 | 保存真实命令、JUnit 与退出码 | `validation/full_monitoring_final_01` | 720 测试通过是相应测量实现的回归结果，不是 720 个天气实验 |

表中代码文件位于 `disastertrace-starter/src/disastertrace/monitoring_v1` 或
`monitoring_fixed_v1`，测试位于 `disastertrace-starter/tests`。

## 2. C1/C2 的分解与强对照

| 复查要求 | 本轮落实 | 证据入口 | 尚不能声称的内容 |
|---|---|---|---|
| 区分复制概率与新增信息 | 精确复制、浮点容差、实际差异分别统计 | `reports/packet_attribution_01`、`reports/model_components_01` | 数字变化不证明天气信息增加 |
| E 逐槽正确与最终归约分开 | 原始模型归约分数保留；另算程序归约 | `e_composition.py`、原 E02 重算 | 布尔归约修正不保证只消费槽计数的 F 改变 |
| 失效模型不能获得原生解码的功劳 | model/native/valid-mask 数值路径分开 | `feature_scoring.py`、固定输入模型批次 | 用 Gold 补全错误字段只是诊断，不能作为模型可见证据 |
| 数值 f(B,E) 必须可追溯 | common/mask-age/values 银行、固定特征和校准追踪 | `native_feature_bank_01`、`reports/native_feature_audit_01` | 更复杂后端不自动优于专业基线 |
| 校准、阈值顺序与单调性 | 原始概率为主，冻结 prior/PAV/CDF 为敏感性对照 | `reports/calibration_review_01` | 固定银行不提供季节迁移或选择后校准保证 |
| 固定日程、采用规则、持续覆盖 | 多截止、COPY/KEEP/first/change-epsilon、两种覆盖协议 | `multicutoff_01`、`reports/multicutoff_analysis_01` | 自动回退和旧值持续产生的收益不能全部归于模型 |
| 分配与共享因素、选择器身份分开 | 程序 2×2 与相同 B11 下 round-robin/risk/coverage/batch | `query_controls_01`、`native_feature_sessions_01` | 本轮不是所有 LLM 在四格中均已跑过 |
| 固定后端比较 LLM 调度 | 235B 完成 288 次有效选择；固定原生后端、共同完整 TAF、预算和预测日程，独立审计通过 | `selector_trial_01`、`reports/selector_audit_01` | 冬季 5 km 仍差于 FOLLOW，1 km 无正例；不推断独立过程收益 |
| 单目标可达不等于共享预算联合可达 | 对真实 pending 前缀，在同一合法路径上求解并重放小型参照 | `native_residual_02`、`residual_reachability.py` | 有限档案、串行情形；不是开放世界最优 oracle |
| 输出合同错误不能混作能力极限 | 全部 84 单元统一提示澄清并完成；普通能见度字段 25/144 到 140/144，原分数保留 | `clarified_feature_trial_01`、`reports/clarified_feature_comparison_01` | 固定后端预测未改善；看过错误后的开发诊断，不是独立确认 |

## 3. 数据、时间与独立性

| 工作 | 已有证据 | 必须保留的限制 |
|---|---|---|
| 完整依赖审计 | 22,032 行、65,584 个原生依赖边、8,706 个哈希的审计 | 两个全局依赖块不等于两个已证实独立的天气过程 |
| 四季新开发资料 | 预选 3/6/9/12 月完整周、纽约/芝加哥/丹佛，共 12 区域周和 12,096 机会 | 四个全局日历块；不按正例挑周，不使用保留确认周 |
| 原生 H15 | 完整 TAF、常规 METAR、版本与支持窗口、所有注册机会 | 归档时延情景不等于已证明历史 first-seen；目标是报告标签 |
| 温度后处理 | 2017 拟合、2018 开发；同成员三日事件与独立 EMOS/ECC 重算 | 改善与改坏事件均保留；当前是 F-only，没有合格付费补证 |
| DWD 补证审查 | 真实重开原始 ZIP，复核 729 天 TNK/TXK/QN4 | 最终档案没有逐版本历史可用时间，不能当作合法历史 E |
| MRMS | 保留 12 个已解码小时网格和官方版本绑定文档 | 原精确累计端点/匹配预报/first-seen 门槛未关闭，本轮不重写为合格 F |
| HEFS | 保留原 QINE 产品 E 与现有流量样本链 | 成员、调控、时间支撑、同断面参考和阈值尚须逐项证明；完整共同预报免费 |

H15 的历史归档情景与 DWD 最终档案要保持一致解释：前者可识别原生报告的时间与文本，
但公开时延仍有声明的假设；后者连当时发行的测量版本也不能从当前最终序列还原。
仅给 DWD 最终值附加一个固定小时延迟，不足以恢复其历史版本。

共同结果掩膜只能保证方法使用相同结算集合。缺失时段仍可能与恶劣天气相关，所以需要
分时段、地区、风险及质量原因报告缺失，并在适用时给出全注册机会的 Brier 差敏感性界。

## 4. 论文主张应怎样更新

- C1 是“何时补证与修订值得”，当前有固定日程、共同信息与强对照的可测机制；是否有
  跨过程收益要看实验。LLM 没有超过基线也应保留，不能改用更弱对照制造正结果。
- C2 是“可判定事实、获取约束、提取错误和未来预测价值的分离”。已有能区分这些来源的
  真实任务与错误案例；还需要足够正例和独立过程，检验这些区别是否稳定影响未来概率。
- C3 是按合同可复算的多灾种体系。本轮直接实验覆盖 H15、H10/H11；16 类是总体数据路线，
  不能用已下载来源的数量替代已完成正式任务的数量。

下一阶段优先补足跨季节强基线与自然过程支持，再冻结一次独立确认。
行动 D、原生 MM、联合目标和前瞻提交分别过门槛。整体方案无需再改研究方向。
