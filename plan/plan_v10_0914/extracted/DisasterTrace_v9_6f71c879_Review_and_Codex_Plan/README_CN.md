# 本次审查包

固定提交 `6f71c8799ff69439a18f645e63b8c966ca21eec4`。先阅读 `IMPLEMENTATION_REVIEW_CN.md` 与 `CODEX_V9_FOLLOWUP_PLAN_CN.md`，机器任务见 `CODEX_WORK_ITEMS.json`。

本包由本次复查生成，不是用户仓库发布的全量实验包。仅包含五个Git-blob一致的源文件、34项定向标准库测试、两个合成归因探针、一条既有回答的内容复核、报告与建议。测试通过不表示全仓616项已复现。

```bash
PYTHONDONTWRITEBYTECODE=1 python reviewer_tests.py
PYTHONDONTWRITEBYTECODE=1 python reviewer_probes.py
```

测试不发网络请求、不调用模型。源码绑定见 `SOURCE_BINDINGS.json`；内容哈希见 `PACKAGE_MANIFEST.json`。实际仓库、权重、数据、源服务及已封存结果未修改。费用/校准/模型研究范围均见主报告。
