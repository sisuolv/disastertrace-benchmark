# 最新进展：v8 大模型开发实验（2026-09-14）

本次更新包含最新测量代码、独立审计、实际实验结果及后续计划。

- [完整实验报告](plans/v8_measurement_execution_20260913_01/RUN_REPORT_CN.md)
- [235B 自适应实验分数表](plans/v8_measurement_execution_20260913_01/ADAPTIVE_SCORECARD_CN.md)
- [下一阶段整体计划](plans/v8_measurement_execution_20260913_01/NEXT_PHASE_PLAN_CN.md)
- [ChatGPT Pro 复查入口](publication/v8_measurement_20260914/README_CN.md)
- [最新代码和结果复查 ZIP](publication/v8_measurement_20260914/DisasterTrace_v8_code_and_progress.zip)

4 张 H100 的 52 个自适应全天会话已全部完成，5,108 次真实调用与四组独立计分通过。
另有固定输入实验 1,010 次实际调用。共 502 项不同相关测试通过。
4,916 次预测回答中，4,915 次等于可见当前概率，另一次等于可见最新基线概率；
当前没有证明新增预测信息或独立过程收益。11,232 个方法机会来自同一个开发日，
不等于独立天气过程。完整 16 类灾害、X09、多模态与完整决策反馈仍有待完成项。

任务平台状态 FAILED 与推理完成须分开看：推理 exit=0，原自动审计在既定外层时限
未全部完成；最终分数来自保留原始来源的完整补充审计。详见实验报告。
