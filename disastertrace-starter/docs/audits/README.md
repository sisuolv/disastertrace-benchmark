# Independent audit materials

## ChatGPT 阅读入口（2026-09-26）

**当前状态**：v22 是最新计划；实现与实验基线仍是 v21 release（代码 `8a6e2162c`）。v22 的 17 个任务**尚未执行**，等待研究者审核下列两份独立复查后再决定执行范围。

**两份独立复查报告**（请都读，并对两者不一致处逐条裁决）：

1. Claude Code 独立复查：[INDEPENDENT_REVIEW_V22_CLAUDE_20260926_CN.md](INDEPENDENT_REVIEW_V22_CLAUDE_20260926_CN.md)
   - GitHub：https://github.com/sisuolv/disastertrace-benchmark/blob/codex/v18-repaired-release-20260923/disastertrace-starter/docs/audits/INDEPENDENT_REVIEW_V22_CLAUDE_20260926_CN.md
   - 复现脚本：[claude_review_20260926/](claude_review_20260926/)
2. Codex v22 计划复核：[INDEPENDENT_REVIEW_V22_PLAN_20260926_CN.md](INDEPENDENT_REVIEW_V22_PLAN_20260926_CN.md)
   - GitHub：https://github.com/sisuolv/disastertrace-benchmark/blob/codex/v18-repaired-release-20260923/disastertrace-starter/docs/audits/INDEPENDENT_REVIEW_V22_PLAN_20260926_CN.md
3. Codex v21 实现复查（历史基线）：[INDEPENDENT_REVIEW_V21_20260926_CN.md](INDEPENDENT_REVIEW_V21_20260926_CN.md)
   - GitHub：https://github.com/sisuolv/disastertrace-benchmark/blob/codex/v18-repaired-release-20260923/disastertrace-starter/docs/audits/INDEPENDENT_REVIEW_V21_20260926_CN.md

**计划包与提示词**：

- v22 计划包：[packages/CHATGPT_PRO_REVIEW_AND_CODEX_PLAN_V22_20260925.zip](packages/CHATGPT_PRO_REVIEW_AND_CODEX_PLAN_V22_20260925.zip)。这是含 `TASKS.json` 的正式版本；`plan/plans_v22_0925` 中另一个较小的同名 zip 任务编号含义不同，不作为依据。
- 给 ChatGPT 的审查提示词：[CHATGPT_REVIEW_PROMPT_V22_PLAN_20260926.md](../CHATGPT_REVIEW_PROMPT_V22_PLAN_20260926.md)

**建议阅读顺序**：Claude 报告的「与 Codex 两份报告的关系」一节 → Codex v22 计划复核 → Claude 报告 §1–§6 → 计划包 `TASKS.json` → 相关代码与 `artifacts/v21_execution_20260925_04/`。

**需要裁决的主要分歧**：

- 真实开发集是否在结构上不可辨识（Claude §2.1：每个检查点最多 1 个可见来源，选择器打平是构造必然），还是仅仅"active 不是内容依赖 follow-up"（Codex）。
- v22 的 P0-00/01/04/06 应记为"未开始"（Claude，按 v22 任务交付物判定）还是"部分完成"（Codex，计入已有代码能力）。
- 下一步应先重建开发集并做"事后最优上限"判决（Claude T1/T2），还是先按 v22 原序完成 P0 合同修复（Codex）。

---

The current planning version is **v22-plan**. The implementation and published execution evidence it audits are still the **v21 benchmark release**. Keep those labels separate.

- [Claude Code independent review](INDEPENDENT_REVIEW_V22_CLAUDE_20260926_CN.md): second independent review of the v22 plan against the current implementation, with reproduction scripts in [claude_review_20260926/](claude_review_20260926/).
- [v22-plan reconciliation](INDEPENDENT_REVIEW_V22_PLAN_20260926_CN.md): the current primary review, including v22 task status, evidence boundaries, blockers, and next gates.
- [ChatGPT v22-plan prompt](../CHATGPT_REVIEW_PROMPT_V22_PLAN_20260926.md): prompt that asks ChatGPT to perform a second review and generate a Codex ZIP execution package.
- [v22 ChatGPT/Codex plan package](packages/CHATGPT_PRO_REVIEW_AND_CODEX_PLAN_V22_20260925.zip): the supplied review package; its SHA-256 is recorded beside the ZIP.
- [v21 implementation review](INDEPENDENT_REVIEW_V21_20260926_CN.md): historical review of the v21 implementation/evidence baseline.
- [v21 prompt](../CHATGPT_REVIEW_PROMPT_V21_20260926.md): retained for provenance.

Every report separates implementation correctness, execution success, method validity, and research novelty/value. The current evidence supports only scoped engineering/protocol claims and a conditional synthetic mechanism hypothesis; it does not establish weather value, provider/LLM benefit, generalization, or novelty.
