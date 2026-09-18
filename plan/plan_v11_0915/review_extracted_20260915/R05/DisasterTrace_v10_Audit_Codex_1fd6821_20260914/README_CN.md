# DisasterTrace v10 审计与增量计划

基线 `1fd6821fef15b26898a57c74d4715714f33ea779`。先读AUDIT_REPORT_CN.md，再将START_HERE_CODEX_CN.md与CODEX_NEXT_PLAN_CN.md交给Codex。

本包包含15项待执行子任务、60项验收要求；实际定向测试39项，36通过/3失败。失败归两类边界缺口；全量旧结果影响未知。这里没有修复远端仓库或运行新的科学实验。

验证包完整性：`python verify_package.py`。
复现本包隔离检查：`cd audit_probes && PYTHONDONTWRITEBYTECODE=1 python -m pytest test_v10_controls.py -q`（需要pytest）。当前提交预期保留3个red，不要把测试失败日志删除。
生产包复现：`DT_REPO_ROOT=/absolute/disastertrace-benchmark PYTHONDONTWRITEBYTECODE=1 python -m pytest audit_probes/test_v10_controls.py -q`。
查看具体合成输出：`cd audit_probes && python -B reproduce_diagnostics.py`（同样需要pytest，因为复用测试fixture）。

本包不是官方74MB阅读ZIP，也不是两个官方capsule。没有模型权重、API密钥、临时授权链接或全量原生天气数据。源码来自用户指定提交且逐文件核对Git blob。测试不会调用原生METAR/TAF解析器、模型或网络；生产模式才使用完整仓库依赖。
