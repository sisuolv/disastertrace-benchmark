# 给 ChatGPT Pro / 外部代码复查者

这是 DisasterTrace 的平衡开发集与本地开放权重模型评测扩展。先阅读最终
`FINDINGS.md` 和根目录 `README_P3_LOCAL_BALANCED_V1.md`；技术规格在
`docs/P3_LOCAL_BALANCED_V1.md`，更高难度的离线候选说明在 `STRESS_DESIGN.md`。
报告完成前，这些结果入口不会被填写为模型成功。

请优先检查这些具体问题：

1. 测量目标是否准确？题目检验累计证据条件下的状态修订、当前版本引用和
   固定行动规则，而非数值天气预报或实际应急决策正确性。三个来源组不足以
   支持广义极端天气能力结论。
2. 平衡设计是否真的消除了来源/案例分配混淆？检查 3×3×2×2×5×3 完整覆盖、
   18 个匹配根、108 条载体轨迹和每方法 180 次回答；不要把 540 个回答当作
   540 个独立天气事件。
3. 是否存在 Gold、未来证据或分组标签泄漏？从每个 batch intent 的 messages
   和 token 输入出发核验；模型只能看到已送达的公开记录与指定回答载体。
4. 错误是否被保留？检查 schema、未结束思考、length、引用错误和未提交槽位
   的固定分母；有效但错误的回答应继续进入对应方法的载体，不能用 oracle 修复。
5. 本地采样来源与诊断来源是否分开？检查权重逐文件版本/摘要、冻结源码、
   tokenizer、vLLM 配置与原始 token，确认程序诊断没有被当作模型输出。
6. 结论是否过度？旧 DeepSeek 是 270 版本，新 Qwen 是 540 版本，不能直接排名。
   同样的 8192 数字和不同模型的 thinking 设置也不代表相同计算预算。
7. 辅助难度因素是否仍有独立自动 Gold？检查所有候选的原题 Gold 不变、公开
   oracle 一致，以及没有 PATCH 的 control 被如实标为零新增修订。

重点源码为冻结执行中的 `implementation_source/src/disastertrace/local_eval/`。
旧 `controlled` 的 generator、renderer、compiler、schema、scorer 均保留原实现。
新增 `data.py` 选择平衡 episode；`adapter.py` 固定提示词/token/思考分离；
`runtime.py` 记录真实本地生成；`audit.py` 独立重建提示词、载体和指标。

`model_report/` 是最终独立评分，真实原始记录位于 `work/p3-qwen3-balanced-v1/`。
`diagnostic_run/` 和 `diagnostic_report/` 全部是程序诊断，不能进入 LLM 成绩表。
`runtime/*_result.json` 记录真实采集、报告生成和重建的实际子进程退出码。

复查报告无需重新生成模型答案，也不需要 API key。复现 tokenizer/评分需要
兼容 Python 环境及冻结的小型 `model_config/` 文件；完整 16.4 GB 权重不放入
评审压缩包，逐文件官方 URL、版本和 SHA256 在 `model_snapshot.json` 中。
若复制压缩包到另一台机器，应调整命令中的解压目录；审计仍核对原始执行 claim。

请将发现区分为阻断测量正确性的缺陷、可复现性问题和后续研究改进，并给出
具体文件/字段与最小复现条件。不要要求以逐题人工改答案取代可执行语义检查。
