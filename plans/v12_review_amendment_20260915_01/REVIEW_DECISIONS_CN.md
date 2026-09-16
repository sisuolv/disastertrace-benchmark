# 新增两份复核的取舍与代码核对

本轮完成文档阅读、ZIP 三成员安全解压、源码静态核对、六个父目录文件库存核对及本地短回执快照。未执行 ZIP 内的 isolated_probes.py，未重新运行历史 750 测试，未做真实 prefix/branch、拟合或模型实验。

审查针对 GitHub 提交 `808ca1912c7065ff6c774004626867676118a9cf`；开发工作树 HEAD `36082c42a93e11f67d274d8000c87cd1dc098d74` 源于既有隔离发布流程。二者不同不等于源码回退。保留旧计划、发布回执和开发 index；本轮不做 Git 提交或上传。

## 1. 逐项处理

| 复核意见 | 当前证据与边界 | 本次计划修改 |
|---|---|---|
| 父状态未物化 | prepare_c2 明写 false；run_arm finish 后只 export journal；六候选目录都无中途 checkpoint | 增加 parent_inventory、parent_materialization 和 no-op 三个门槛；重建能力仍待实测 |
| restore 不是 fork | FormalSession.restore 拒绝 STOP，绑定原 path/contract/hash | 新子身份/合同绑定；不修改父 STOP；正式与 legacy 诊断资格分开 |
| 6/24 预算含糊 | 重建前缀、续跑与干预不是同类动作 | 分别上限 6/6/24，失败消耗额度；别名不增独立 N |
| 精确查询计划没有接口 | CONTROLS 只有 acquire/predict/selector_kind/数量控制；query 由原排序选择 | 增加版本化显式 query-plan consumer，核 planned/executed；不靠删目录或假 LLM 实现 |
| TAF 处理干预尚未接入 F | NativeFeaturePredictor 使用 raw TAF 和已授权资产；feature_vector 重解析并核 projection | 第一批仅 wiring_audited_not_intervened；METAR 才运行实际 GET 分支 |
| 状态混用 | METAR、TAF E、产品状态和缺 frame 不同 | 保留各自 schema；缺测/未执行不暗转 refuted |
| 全来源被预过滤 | prepare_c2 读取 baseline_candidates；旧题仍可作为 supplied packet QA | 新 C2 universe join 完整已登记索引、回执、raw/version；新任务身份 |
| 档案完整性被高估 | 索引不证明历史全量；声明 available_at 不等于真实 first_seen | 明示 closed scope/unknown scope；先可见版本、后覆盖；公开/评估目录分开 |
| 同时控制信息和时间 | 原流程有免费新 TAF、age、override 与 deadline | 主报有限计划总效果，等时诊断另列；不增加本批真实分支上限 |
| 只报选中目标 | 六父属于共享预算日会话 | 固定剩余 U_parent、同结果掩膜；全会话主报，选中目标辅报 |
| 固定 predictor 不等于 schedule | 现有 scheduled_starts/public_slots 会忽略 forecast_handles | 复用该路径；selector-only 必须非空固定 schedule，并做负控制 |
| W05 与正文收尾冲突 | 旧机器图 local acceptance 等 W07.closeout | local/full/batch closeout 分开；外部审计 pending 不伪装科学完成 |
| E 肯定状态漏计 | audit 汇总使用 entailed/refuted，producer 使用 supported/refuted | 新派生 E 汇总和四状态回归；不改原 F/Y/损失 |
| 年度失败 sample+sample | 实际表达式在 sample_ok=false 时重复样例；原实际样例成功 | 修失败分支与唯一 roster；不归因为实际 71/72 的原因 |
| bank 数值守卫不足 | 负输出、域顺序/重叠、巨大整数需受控处理 | 真实 consumer 回归，扫描实际 bank 影响；保留合法 sparse gap 与外推 |
| 五臂配对不全 | 现 PAIRS 为六对，缺 COMMON→BASE_ONLY、BASE_ONLY→BATCH 等 | 新派生十配对，标事后开发描述性分析，不改原预注册 |
| 年度下载规模不清 | 62,691 为成功月的目录引用，未做全局 raw/cache 核验 | inventory 分 reference/identity/version/hash/cache/missing/conflict；不伪报剩余对象数 |
| 2024 角色与历史暴露 | 2024-12 曾参与旧 bank；月样例有 QA 暴露 | EXPOSURE_LEDGER 分 QA、标签、损失和方法选择；unknown 明示 |
| purge 过度或不足 | 动态来源与共享静态元数据意义不同 | 按真实动态足迹 purge，静态 schema/站点不合并所有年份 |
| 两补充槽位解释过度 | 每目标有限槽位不代表会话无预算竞争 | 统计 session queries/beneficiaries/重复/预算/不同动作；不预判有无 C1 空间 |
| 确认仅覆盖模型胜负 | C2 机制诊断需要新过程复現 | 两类确认终点分别预注册；无显著优势不能写等效/无价值 |

## 2. 当前已核对的关键代码

- [fullweek.py](../v11_execution_20260915_01/fullweek.py)：run_arm 的终态导出、audit_case 的 E 与 F 行以及汇总。
- [prepare_c2.py](../v11_execution_20260915_01/prepare_c2.py)：72 noon 引用、checkpoint_materialized=false 与 baseline_candidates 来源。
- [formal_session.py](../../disastertrace-starter/src/disastertrace/monitoring_v1/formal_session.py)：原 run restore/persist/STOP 与绑定。
- [session_checkpoint.py](../../disastertrace-starter/src/disastertrace/monitoring_v1/session_checkpoint.py)：允许的 controls、内存 checkpoint、pending 保护。
- [policies.py](../../disastertrace-starter/src/disastertrace/monitoring_v1/policies.py)：公开日程、query 排序与额度/时限执行。
- [forecast_schedule.py](../../disastertrace-starter/src/disastertrace/monitoring_v1/forecast_schedule.py)：public_serial_slots 与固定 public_slots。
- [native_feature.py](../../disastertrace-starter/src/disastertrace/monitoring_fixed_v1/native_feature.py)：bank 守卫和预测器实际消费入口。
- [native_feature_forecast.py](../../disastertrace-starter/src/disastertrace/monitoring_v1/native_feature_forecast.py)：raw/projection 校验、METAR 字段与特征表示。
- [annual_catalogs.py](../v11_execution_20260915_01/annual_catalogs.py)：样例失败分支与年度结果。
- [analyze_fullweek.py](../v11_execution_20260915_01/analyze_fullweek.py)：当前六个配对和原 rows hash 验证。

源码核对只能证明设计缺口在当前接口中存在或尚无实现；不是对所有历史结果影响的证明。父库存也只核对文件存在性和绑定摘要，没有导入生产包复演完整状态。

## 3. 不在这一批扩大范围的部分

采纳两份复核共同建议，首批优先 H15 的收口与获取工程。TAF 新处理适配器、年度生产/拟合、LLM、温度、API 恢复、MM 和独立确认保留在整体路线，按消费者条件放行。

不要求用正收益换准入，也不追加新的核心贡献编号。当前研究差异化需要严谨任务、强对照和独立确认来支持，本次文档检查不构成 novelty 已验证。

## 4. 证据与校验

[REVIEW_INPUTS.json](REVIEW_INPUTS.json) 记录原两输入与解压成员的 SHA256；[CURRENT_STATE.json](CURRENT_STATE.json) 固定观察时刻；[PARENT_CANDIDATES.json](PARENT_CANDIDATES.json) 保存六个元数据候选与未验证资格；[PROTECTED_FILES.json](PROTECTED_FILES.json) 记录 188 个相关源/旧计划/合同/STOP/Git 文件的保护摘要。

本轮验证只检查计划包、DAG、数目上限、文件链接和保护摘要，不是 benchmark 回归或全量 raw 数据保护审计。校验结果见 [VALIDATION.json](VALIDATION.json)。
