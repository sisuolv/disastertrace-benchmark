# DisasterTrace V6：plan_2 研究与执行建议

日期：2026-09-11。本目录保存对用户 `plan_2.md`、当前工作区、相关论文/代码和少量水文数据的交叉核查。

请先阅读 [详细研究计划](RESEARCH_PLAN_CN.md)。推荐主线是：在固定专业预报、合法信息、取证预算和准备截止下，评估 LLM/VLM 的证据选择是否改善未来观测结算的预测与决定。广灾种数据银行继续保留 16 类目标。

本文档提出下一阶段方案，尚未实现新的主动预警协议。此次完成 127 项相关现有 CPU 测试、六个公开仓库的选定源码核查，以及三张 NIMS 实图/同站水位的小规模配对；新增完整预警 episode、GPU 作业和模型调用均为零。

| 入口 | 内容 |
| --- | --- |
| [RESEARCH_PLAN_CN.md](RESEARCH_PLAN_CN.md) | 贡献取舍、相关工作、代码复用、数据组合、任务/评分、基线、约十二周路线及紧接的交付单 |
| [HYDRO_FEASIBILITY.json](HYDRO_FEASIBILITY.json) | 水文样例的实际计数与未通过的同站链 |
| [CODE_PINS.json](CODE_PINS.json) | 六个代码仓库的固定提交；LEAP 后端、MiniProphet 归属限制 |
| [REFERENCE_CAPTURE_SUMMARY.json](REFERENCE_CAPTURE_SUMMARY.json) | 72 次捕获的完整记录，包含失败 |
| [LOCAL_INPUT_BINDINGS.json](LOCAL_INPUT_BINDINGS.json) | 当前代码、用户计划和继承证据的哈希 |
| [VERIFY_REPORT.json](VERIFY_REPORT.json) | 本轮结束核查 |

`references_01` 至 `references_05` 保存原始响应、解析文本和逐项回执；失败请求仍保留。捕获程序没有运行下载的作者代码。测试第一次因环境缺少依赖失败，后续在正确的既有环境中通过；两类记录均在目录中。

本目录没有修改历史冻结数据和成绩。论文优先权、完整数据准入、正式留出测试和实际业务收益均未被本次研究验证。
