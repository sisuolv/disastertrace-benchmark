# V6 数据选择 GitHub / ChatGPT Pro 复查包

优先阅读 [给 ChatGPT Pro 的复查任务](REVIEW_FOR_CHATGPT_PRO_CN.md)。

- [单文件 Markdown](CHATGPT_PRO_REVIEW_ALL_IN_ONE.md)：含审查任务、主要报告和关键数据审计代码，便于独立交接。
- [代码和报告 ZIP](disastertrace_v6_chatgpt_review.zip)：保留仓库相对路径，含更多机器可读审计和必要的代码上下文。
- [文件清单](PUBLICATION_FILES.json)：本次选定文件及 SHA256。
- [上传前校验](PUBLICATION_VALIDATION.json)：内容核验、发布文件检查和阅读包边界。

目标分支为 `sisuolv/disastertrace-benchmark` 的 `next-phase-v1`。本次增量发布接续 `a8ea30d6fd35e5889f5f846ee9f49c87480cf96d`，保留历史结果和原工作区已有暂存状态。

本包发布代码、方案、统计和审计记录；原始 HTTP payload、遥感/雷达数组、未明确再分发条款的数据、模型权重、凭据及运行环境留在原工作区。CAPTURE_INDEX 与 FILE_MANIFEST 提供字节身份及位置，不能据此声称 GitHub 含完整数据重建材料。

随包可运行检查：

```bash
python3 publication/v6_review_20260911/verify_review_snapshot.py
```

此命令只校验随包文件和报告统计，不联网、不调用模型。`plans/v6_0911_dataset_selection/verify_selection.py` 属于原数据工作区的完整检查，读取包缺少原始数组时不能直接替代运行。

本文件及复查提示词由 Codex 编写。它们不代表 ChatGPT Pro 已经读取仓库或完成分析；本次会话没有可用的 ChatGPT Pro 对话操作工具。
