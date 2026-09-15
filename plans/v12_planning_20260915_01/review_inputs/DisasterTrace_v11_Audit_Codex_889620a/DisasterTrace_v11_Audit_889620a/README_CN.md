# 使用本复查包

审阅版本：`889620a4fc4ee6ad70757dd3e832a40c7509126a`。

阅读顺序：`AUDIT_REPORT_CN.md` → `CODEX_NEXT_PLAN_CN.md` → `START_HERE_CN.md`。机器任务表为`WORK_PACKAGES.json`，共14项建议任务、61条待执行验收。任务不是已完成声明。

本轮实际有限检查：32项，29通过、3失败、0错误；日志和反例在`results/`。测试在当前未修复快照上故意保留三个回归红项，退出码1是预期的证据，不是新的运行事故。

```bash
python3 -B tests/test_review.py
```

Python需要3.10或以上，不需网络、第三方包、被测模型或GPU。测试结果写到`results/LOCAL_VALIDATION.json`和`results/TEST_LOG.txt`；若需保留本包原结果，请复制到新目录后运行。

`source/`仅为6个哈希核验的有限源副本；`excerpts/`是两段用于模拟测试的函数，不是全仓库。禁止用本目录替换生产代码。这些测试不等于原750项回归，也未重新执行完整天气评分或云作业。

`SOURCE_INDEX.json`记录源路径和固定版本。`PACKAGE_MANIFEST.json`记录交付文件哈希。所有研究值和任务结果必须来自工作仓库的原始记录；本包合成测试不能计作天气样本。
