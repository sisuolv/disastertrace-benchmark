# DisasterTrace v9复查与Codex计划包

基准提交：`6f71c8799ff69439a18f645e63b8c966ca21eec4`。本次开始、结束核查的分支均为该提交。

推荐阅读顺序：

1. `AUDIT_REPORT_CN.md`：已完成工作、真实模型错误、归因问题与验证边界。
2. `CODEX_NEXT_PLAN_CN.md`：接续N1—N5的实现与实验任务。
3. `START_HERE_CN.md`：新执行授权后可交给Codex的首批说明。
4. `WORK_PACKAGES.json`：依赖、产物、验收和执行模式。

本次执行的是35项局部CPU检查和一条真实E请求/响应复核；没有运行仓库616项测试或整个E/F/温度批次。`source/`只含七个经Git blob核验的有限模块，不是仓库副本，不要覆盖工作区。

无模型权重、API密钥、外部下载器或新作业启动器。当前暂停状态不变。

本地复核（Python3.10+）：

```bash
python -B tests/test_local.py
python -B check_real_example.py
python -B record_diagnostics.py
python -B verify_package.py
```

最后一条检查随包原始文件清单；前述脚本重新生成诊断JSON后若内容变化，应作为自己的复核产物另存，不冒充原始报告。本包原始结果位于`results/`，完整原始样例复核位于`real_example/`。

GitHub源路径及读取范围见`SOURCE_INDEX.json`；源码哈希见`SOURCE_VERIFICATION.json`。不同测试中的枚举真值向量或合成输入不是独立天气样本。由于包只含所需模块，不能用此包直接运行整个DisasterTrace。
