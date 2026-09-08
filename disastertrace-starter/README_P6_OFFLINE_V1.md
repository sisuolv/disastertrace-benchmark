# P6 首轮离线里程碑

2026-09-08。整合四份 plan_v3，完成 P5 错误/曝光分析、公开简单策略、配对重复协议、
raw-first 程序采集与独立审计、完整诊断和 CPU 迁移。
状态：`offline_verified_live_pending`；新增模型回答、GPU 作业和付费 API 调用均为0。

建议先读 [详细交接文档](artifacts/p6_offline_v1/HANDOFF_POST_P5.md)，再查看
[整合实施计划](../plans/INTEGRATED_P6_PLAN_V1.md) 和
[下一步执行计划](artifacts/p6_offline_v1/NEXT_STEP_EXECUTION_PLAN.md)。

## 已得到的结果

- P4 和三组 P5 原 capture/report 已独立复验，旧分数不变。
- P5 的230个纯引用错误分成7类，其中109个是同值旧版本引用；90个值/状态错误与
  29个重叠动作错误保留。6480字段行可追溯，8类错误示例按固定规则自动选取。
- 实际曝光：revision为30个episode在c2出现、6个全程零效应；scope在c2，stale在c4。
- 按事实键 latest-issued 程序在 base 和三组压力任务均为180/180，明确当前单链域边界。
- 唯一 E1 候选为2条件×36 episode×5 checkpoint×3方法×2repeat，2160 slots、432轨迹。

| 离线程序模式 | 收到/计划 | 全正确 | 格式屏通过 |
| --- | ---: | ---: | ---: |
| correct | 2160/2160 | 2160 | 36/36 |
| invalid-control | 2160/2160 | 1728 | 0/36 |

invalid-control 的432条无效回答全部留在分母；这些是程序故障对照，不是新模型成绩。
10800个程序上下文机会通过，2373个唯一提示直接测量，最大7002 prompt tokens，
保留8192输出预算后仍低于16384 context。任意模型长载体不由此获得保证。

新增65项核心测试和4项补充测试通过。1189项旧测试已完成逐项核验：首次轻量环境
1137通过、2失败、50错误；对应71项在原安装环境全部通过，其中19项与首次通过
重复，已去重。没有安装/升级依赖或绕过原环境验证。详情见
[VALIDATION_RESULTS.json](artifacts/p6_offline_v1/VALIDATION_RESULTS.json)。

## 复查材料

- [最终验收记录](artifacts/p6_offline_v1/OFFLINE_ACCEPTANCE.json) 与 [复现命令](artifacts/p6_offline_v1/REPRODUCE.md)。
- [错误分析](artifacts/p6_offline_v1/posthoc_final/DIAGNOSTIC_FINDINGS.md)、[实际例子](artifacts/p6_offline_v1/actual_examples/EXAMPLES.md) 与 [来源探针](artifacts/p6_offline_v1/source_binding_probe_v1/report.json)。
- [测量协议](docs/p6/MEASUREMENT_PROTOCOL.md)、[简单求解器边界](docs/p6/SOLVER_EQUIVALENCE.md)、[主张审计](docs/p6/CLAIM_AUDIT.md)。
- [第四方案对照](artifacts/p6_offline_v1/SUPPLEMENTAL_PLAN_RECONCILIATION.md) 与 [开源借鉴范围](docs/p6/UPSTREAM_REUSE.md)。

本轮未启动新模型评测、未获取新的官方 forecast 原文或权重、未训练、未使用heldout、
未把 P6 上传 GitHub。下一步是独立的 live adapter/单次 ACP launcher/无生成硬件预检，
以及随后有界 NHC 真实多版本来源轨；不重新开启任何历史已消费的运行。
