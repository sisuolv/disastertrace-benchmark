# Claude Code 复查（2026-09-26）复现脚本

这些脚本是 [INDEPENDENT_REVIEW_V22_CLAUDE_20260926_CN.md](../INDEPENDENT_REVIEW_V22_CLAUDE_20260926_CN.md) 中标为 VERIFIED 的结论的计算来源，按原样保存，没有改写成可移植工具。

| 目录 | 对应报告章节 | 内容 |
|---|---|---|
| `code/` | §2.4、§2.5 | 重复检索（t2）、delay(None)（t3/t3b）、共同分母（t4）、A-B-A（t3_t5）、时钟/UPDATE/deadline（t6）、句柄重命名（t7）、bridge 与 scorer 口径（t9） |
| `data/` | §2.1、§2.2、§6 | 来源集合重建（t1）、标签复核（t3）、Brier 与 episode 簇 bootstrap（t4）、候选池（t5/t5b）、1 月+3 月可行性统计（t6） |
| `synth/` | §2.3 | cost-matched 与 shared-delay 的闭式解核对、816 wins 拆解、Bayes-F 对照 |

使用前请注意：

- 脚本含硬编码的本机路径（`/mnt/afs/260010168/...`、`/tmp/dt_review/...`），重跑前需要改路径。
- `data/` 脚本需要仓库外的原始数据根 `data_real_v16`，只读 KDEN/KJFK/KORD/KSFO 的 2025-01 与 2025-03；不读 holdout、quarantine 或任何 2025-02 数据。`t4_stats.py` 需要 numpy。
- `code/` 脚本针对 `git archive HEAD` 导出的干净副本运行（`PYTHONPATH` 指向副本的 `src`）。
- `synth/` 脚本只需要 numpy，不需要 GPU。
- 文件名都不是 `test_*`，不会被 pytest 收集；它们不是 benchmark 测试。
