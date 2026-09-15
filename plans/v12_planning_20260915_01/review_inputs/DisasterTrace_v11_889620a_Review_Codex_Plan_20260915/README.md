# v11复查包

先读 `REVIEW_AND_CODEX_NEXT_PLAN_CN.md`；交给Codex的短入口为 `CODEX_START_HERE.md`。

- `specs/work_packages.json`：9个映射现有W00—W13的增量工作包。
- `specs/acceptance_tests.json`：40条待实施验收要求，不是已通过的项目测试。
- `specs/findings.json`：已确认问题与明确的影响边界。
- `specs/review_scope.json`：发布时间、进行中状态、审阅实际执行范围。
- `specs/sources.json`：25项代码/文档来源登记，不包含私有下载token。
- `checks/`：3个按Git blob核验的原模块、21项定向合成检查，另1项E汇总表达式复现。

离线复算本包定向检查（Python3.10+）：

```bash
python -B checks/run_scoped_checks.py
python -B checks/check_e_summary.py
```

这些命令不访问网络、不调用模型、不修改原仓库。它们会更新本包自己的检查输出。
没有包含全库原始数据、完整运行日志或模型权重，不能代替750项项目测试或840条完整日历复算。
