# v10 外部复查包 / 1fd6821

这不是原仓库的完整复建包，也不包含模型权重、API凭据或原始大数组。

先读 `CODEX_NEXT_PLAN_CN.md`，启动提示为 `CODEX_START_PROMPT_CN.txt`。
`REVIEW_SCOPE.json` 区分本次实际执行与只读材料，`FINDINGS.json` 给出三项边界。
`review_results.json` 是首次32个不同检查；`runner_recheck.json` 是加入新结果路径保护后的相同检查，不累加数量。

六个 `verified_sources/` 文件是固定提交的完整源码，Git blob及SHA256见 `SOURCE_MAP.json`。
测试使用原函数和真实临时文件，但HTTP、时间与部分导入辅助函数是测试替身；没有模型或网络调用。不是FormalSession、生产spool或全部720项回归。

## 复运行

```bash
python3 -B review_checks.py --result /一个全新路径/review-result.json
```

现有输出拒绝覆盖。Python 3.10+、标准库即可；`check_satisfied=true` 也可能表示成功复现错误，不等于被审查程序满足应有契约。请先转成完整checkout集成回归，再修复。

`EXECUTED_REVIEW_CHECKS.py` 是首次执行的历史脚本，直接运行会覆盖其相邻review_results.json，故只作为历史来源保留，请运行具备输出路径保护的 `review_checks.py`。

没有检查到实际历史坏输入，就不能声称整批天气分数失效。保留旧冻结、暂停状态、未决费用和封闭确认资料；本包不增加运行授权。
