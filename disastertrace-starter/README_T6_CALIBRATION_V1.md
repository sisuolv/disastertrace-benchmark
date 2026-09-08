# T6：DeepSeek 新鲜输出校准

本轮在用户确认下一步后，于 **2026-09-07 08:43:29 UTC** 启动。它使用 T0–T5 已验收的执行器；新启动范围为最多 **270 次请求、USD 3 条件预算**，与历史 P1、P2 拟执行实验分别计数。

**本轮已于 09:36:28 UTC 完成：270 次尝试、270 个响应、独立审计通过，共同输出上限选择 8192 tokens。** 没有重试、未发送槽位或本轮未知预留。

请先阅读[中文完整结果](artifacts/t6_deepseek_calibration_v1/runtime/REPORT_ZH.md)、[主要发现与后续工作](artifacts/t6_deepseek_calibration_v1/FINDINGS.md)和[机器可读报告](artifacts/t6_deepseek_calibration_v1/runtime/report/report.json)。实际 usage、缓存和时段支持的费用估计为 **USD 0.628557504**；峰值/缓存未命中的保守结算账为 **USD 0.97628256**。两者均不是账户账单。

4096 下，snapshot 和 answer_history 分别只有 27/30、28/30 格式成功，并有 3、2 个 length 失败，未达到共同门槛。8192 下三方法均为 30/30 格式成功、零 length 失败；已知字段与来源联合正确分别为 snapshot **91/96**、structured_state **90/96**、answer_history **96/96**。8192 是格式可靠性的共同选择，并不保证事实/来源分数对每种方法单调提高。

可用[只读进度入口](artifacts/t6_deepseek_calibration_v1/status.py)查看已完成状态：

```bash
.venv/bin/python artifacts/t6_deepseek_calibration_v1/status.py
```

原后台进程 PID 为 35152，现已结束，工作日志位于 `artifacts/t6_deepseek_calibration_v1/runtime/worker.log`。本轮 270 次范围已用完，initial launch 不可重复执行。系统没有自动重启或重新发送机制。

## 实验范围

| 条件 | 公共输出说明 | 输出上限 | 计划响应机会 |
| --- | --- | ---: | ---: |
| `legacy_4096` | 原有说明 | 4096 | 90 |
| `explicit_4096` | 明确说明 | 4096 | 90 |
| `explicit_8192` | 相同明确说明 | 8192 | 90 |

每条件包含 snapshot、structured_state、answer_history 三方法，以及 Ida、Florence、Dorian 三开发风暴的两个五检查点分支，共 54 条独立载体轨迹。使用冻结的风暴轮换顺序，单请求顺序执行；`reasoning_effort=high`、thinking enabled；socket timeout 和总网络 deadline 均为 180 秒。

没有额外探针、暖缓存或自动重试。只把本轨迹结构有效的真实回答传递到下一个检查点；结构有效的事实错误继续保留。全部失败和未发送机会进入完整计划分母。七个留出风暴、P2 模型矩阵、第二模型和训练均不在本轮范围。

## 启动依据和冻结内容

- [实际授权记录](artifacts/t6_deepseek_calibration_v1/authorization.json)绑定执行身份及本次用户确认。
- [当前价格和限制核对](artifacts/t6_deepseek_calibration_v1/price_attestation.json)及[官方文档获取记录](artifacts/t6_deepseek_calibration_v1/docs/acquisition.json)保存获取时间和 hash。2026-09-07 重新获取的官方价格页面与原绑定页面逐字节一致。
- 官方页面当前列出 `deepseek-v4-flash`、`DeepSeek-V4-Flash-0731`、1M 上下文和 384K 最大输出，并支持本轮参数。服务端实际返回的 model 和 usage 会逐请求核验；文档版本标识不保证服务端权重永远不变。
- [冻结清单](artifacts/t6_deepseek_calibration_v1/launch_manifest.json)绑定 84 个文件，包括完整采集源码、协议、执行包、价格资料、授权和后台入口。运行使用独立的 `frozen/` 源码副本。
- 启动前验证：既有 949 项回归通过；本次后台入口专项 4 项通过；冻结入口另完成 270 槽程序演练、独立审计和报告，模型调用为 0。

执行身份：`590ac03ab8c2ee53cf8b2a7764e069fd5b97167c6c689ca2f491899b476c48a0`。保留原固定 registry 路径，复制执行包不会重置同一身份的启动记录。

## 运行记录和自动报告

原始 journal 位于 `work/t6-deepseek-calibration-v1/`。每个请求保留 prepared bytes、发送意图、响应捕获、费用结算及状态接受记录。凭据不写入源码、配置或运行日志。

后台入口已自动生成：

- `artifacts/t6_deepseek_calibration_v1/runtime/completion.json`：采集状态、独立审计摘要和最终报告入口。
- `artifacts/t6_deepseek_calibration_v1/runtime/report/REPORT.md`：每条件/方法的收到数量、格式成功、length 和已知字段联合正确率。
- `artifacts/t6_deepseek_calibration_v1/runtime/report/report.json`：逐风暴分子分母、等权风暴平均、条件配对差异、usage、时延、费用覆盖范围和共同 cap 选择。

只读监控中的计数不替代最终独立审计。USD 3 是条件停止预算，不保证全部槽位必定完成；峰值/缓存未命中保守账、缓存/时段费用估计和未知预留分别报告，均不冒充账单。单次请求跨越价格时段时，保留估计缺失及其原因。

## 结果如何决定下一步

只有全部 270 个响应收到且独立审计通过，才按预定门槛选择共同 cap：各方法 schema ≥29/30、length ≤1/30，取合格的较小档。矩阵不完整、审计失败或两个 cap 均不合格时输出 `no_selection`，不按方法分别挑选参数，也不单独补跑失败题。

完成 T6 后，再推进 P2 专用真实采集/响应审计和独立开发矩阵。NHC 选择的 cap 仅作为 P2 起点，P2 仍需自己的可靠性检查。历史 P1 的 90 个响应 / 91 次尝试及原 attempt 79 未知收费记录保持独立。
