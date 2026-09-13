# v7 后续执行入口

本批完成了类型化评分准入、真实 H15 证据支持、无在途会话分支、合成准备状态机，
以及 108 次独立 E-only / F-only / joint 的 Qwen3-8B 实测。

- [完整执行报告](FINAL_REPORT_CN.md)：完成范围、真实结果与研究限制。
- [工作包状态](EXECUTION_STATUS.json)：7 项完成、4 项部分完成，16 项保留后续依赖；完成均以注明的工程范围为准。
- [最终验收](VALIDATION.json)：289 项相关测试、Ruff、迁移后的离线重放与历史保全。
- [下一批具体动作](NEXT_EXECUTION_CN.md)：统一自适应控制器、E 失败分层、新题型 head、独立日历。
- [离线复查 ZIP](DisasterTrace_v7_followup_20260913_review.zip)：386 个受哈希约束文件及标准库复验脚本。

模型调用和 GPU 作业已经完成；`gpu/heads_smoke_01/` 的一次性启动不能重用。
108 条回答可解析，但所有 F 回答保留基线，E-only 全部回答 unknown。
模型收益、独立天气过程、前瞻可用性以及完整 16 类资格尚未由本批证明。

离线复验可在复制后的目录运行：

```bash
python3 -B verify_portable.py
```

该命令在 `portable_01/` 内运行，不调用 API 或 GPU。
完整 GPU 请求、输出 token、原始回答、落盘回执、作业身份与源码冻结保存在本批 `gpu/heads_smoke_01/`。
复查 ZIP 以封存、评分、真实证据与分支复放为范围，未打包模型权重。
