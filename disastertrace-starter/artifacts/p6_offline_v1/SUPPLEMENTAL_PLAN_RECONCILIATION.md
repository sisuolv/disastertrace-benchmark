# 第四份 plan 的纳入记录

用户在本轮执行过程中补充 `DISASTERTRACE_POST_P5_CODEX_PLAN.md`。已复制原文并
记录 SHA-256；四份输入索引为 `plan_inputs_v2.json`。以下对照指向实际实现或明确
的后续任务，不将新增参考阅读当成新增模型实验。

| 补充方案重点 | 纳入方式 | 边界 |
| --- | --- | --- |
| PR-P6-00–04 先离线、停止于候选 | 与本轮一致 | 实际缺 live adapter/launcher/硬件验收，使用更准确的 offline_verified_live_pending |
| 默认选项 A，2160 个机会 | 与已冻结 E1 一致 | 不另外启动三次重复或6480 |
| 每个错误标签的固定排序最小例子 | 新增 `build_examples.py` 与 `actual_examples/` | 按 factor/method/base_episode/checkpoint/field 排序，不手挑戏剧性案例 |
| 逐字段绑定原 audit、seed、root 与 prompt hash | 新增 `actual_examples/field_provenance.jsonl` | 6480 行分析覆盖；不向旧 slot 回写 repeat |
| 重复交付、同值来源刷新、异值刷新 | 新增独立 `source_binding_probe_v1/` | 九个受控探针及私有证书，未并入 E1；完整长度匹配因子矩阵尚未实现 |
| Hypothesis 纯程序性质检查 | 使用已安装 Hypothesis 6.167.1，固定 seed、100 个序列样例上限 | 不访问模型；1 个 property test 仍按1项测试计，不冒充100项独立实测 |
| private/public oracle 对非法图分别拒绝 | fork、跨键父指针、子先父后反例 | 未用同一个 resolver 两次冒充双实现 |
| 旧曝光检查的增量增强 | 原 P5 比较器保留；新表增加实际 token/carrier/采样及语义曝光 | 不宣称此前没有任何曝光检查 |
| 可选跨方法共 seed | 本轮保持 method 入采样身份，条件间配对 | 改为方法间配对会产生另一协议，不能在已冻结候选上静默修改 |
| 等内容不同表示的 carrier 研究 | 纳入后续独立研究 | 不能把相近长度等同于相同信息量 |
| StateMemBench 与 STATE-Bench | 分别登记 | 本轮没有独立核验 StateMem 论文或代码；不能合并成同一项目 |
| LongMemEval、AFDBench、CAP/VTEC | 补充 design-only 来源登记 | 不导入 grader，不宣称 AFDBench 会议状态，不同时扩张多条真实资料路线 |
| NHC Ian 2022 005/009 示例 | 列为计划已曝光的开发候选 | 与 Francine 示例同样不能作为未见 heldout，先查现有 split；本轮没有下载 |

初始三方案与补充方案有不同的后续来源数量建议。下一步先使用更小的上限：最多
2 个明确 development 风暴、每个最多6份正文，先验证时间解析与来源等价；成功后
再另立更大来源清单。原方案中的8事件×3产品对作为扩展候选，不同时实施。

本轮没有增加人工逐条标注或 LLM judge。补充来源 URL 见
`plans/p6/source_registry_supplement.json`，阅读层级是 supplied_plan_only；本地
Hypothesis 的实际运行与外部文档复现分开记录。
