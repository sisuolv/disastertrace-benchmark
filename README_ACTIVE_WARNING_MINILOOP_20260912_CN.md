# DisasterTrace ActiveWarning 最小闭环

2026-09-12：已使用 NHC/HURDAT2 与 HEFS/USGS 跑通真实数据的固定未来目标预测和自动结算，暂不使用 GEE。

84 个开发目标完成 7,056 条程序基线轨迹；两轮完整 Qwen3-8B 模型试点共 1,120 次实际回复、400 条轨迹，使用最多四张并行 H100。第二轮将长目标编号改为短编号后，400/400 次预测合法。原始回复、失败、未结算目标及两轮独立结果均保留。

主动策略在本次试点中始终选择官方预报，与固定查询产生相同预测；水文近期观测持久性明显优于所有测试 LLM 策略。旧版本整理提供输入稳定性，但精度并非总是更高。工程闭环完成，强 novelty 与真实在线预警收益仍需后续独立事件和前瞻数据验证。

- [详细方案、实际模型成绩、novelty 判断与后续路线](plans/active_warning_miniloop_20260912/README_CN.md)
- [真实使用的数据、时间合同、处理方式和准入边界](plans/active_warning_miniloop_20260912/DATA_CONTRACT_CN.md)
- [修正协议后的模型运行与复算记录](plans/active_warning_miniloop_20260912/model_results_02/COMPLETE.json)
- [核心实现](disastertrace-starter/src/disastertrace/active_warning_v1/)
