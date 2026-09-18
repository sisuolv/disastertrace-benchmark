# DisasterTrace v7：下一阶段 Codex 计划包

建议直接把整个ZIP交给Codex；入口是 `START_HERE_CODEX_CN.md`。

- `CODEX_NEXT_PLAN_CN.md`：详细主计划，包含现有工作、接口桥接、13个工单、原X矩阵、16类门槛与执行边界。
- `tasks.json`：工单依赖、交付、验收与阻塞策略。
- `test_cases.json`：拟实施的测试清单，不是本次仓库测试结果。
- `configs/`：默认离线、有授权小试、任务和确认/前瞻模板。含null项的模板不可直接启动实验。
- `SOURCES_AND_READ_SCOPE.md`、`sources.json`：仓库和外部资料来源与读取边界。
- `validate_plan_bundle.py`：只检查这个计划包的结构、依赖与安全默认值，不执行DisasterTrace。
- `PLAN_BUNDLE_VALIDATION.json`：上述本包校验结果。
- `ARTIFACT_MANIFEST.json`：最终文件大小与SHA-256。

本包不包含模型权重、API凭据、受限原始数据，也不包含已运行的新科学实验结果。

工程开发可以有界推进；GPU、网络科学采集、付费调用、真实前瞻与远端发布需要本轮明确授权。
