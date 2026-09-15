# 审查范围与排除项

本包不修改用户仓库。来源固定为889620a4fc4ee6ad70757dd3e832a40c7509126a。
4份完整源码Git blob核验；21组局部CPU合成检查。包含回归、边界复现，不是全部实现正确认证。
完整模块执行：temperature_contract.py、temperature_postprocess.py。
AST函数执行：feature_tasks.temperature_ensemble_probability、native_feature.validate_feature_bank。
未执行：上游750项回归、FormalSession端到端、云作业、API/LLM/GPU、任何新的科学取数、确认数据。
阅读ZIP的下载尝试失败，没有成功恢复或运行上游capsule；文中的作者运行结果按来源归属。
本包的源文件仅为明确选读的代码，不含模型权重、凭据、签名URL、原始科学档案或任何字体。
执行计划不授予额外账户、费用、训练、确认集或推送权限。
