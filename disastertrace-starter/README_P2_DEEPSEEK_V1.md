# P2 首轮 DeepSeek 开发集实测

本轮承接已经完成的 T6 输出校准和 P2 离线采集工程，开始评测真实 LLM 在受控气象证据变化下的状态更新能力。

当前状态：2026-09-07 13:15:39 UTC 完成全部 270 个真实响应，独立审计及离线重算通过；**共同格式门槛未通过**。U2 的 snapshot 和 answer_history 均为 28/30，低于至少 29/30 的要求。

| 方法 | 格式有效 | 已知数值与当前引用联合正确 | unknown 正确 |
| --- | ---: | ---: | ---: |
| snapshot | 88/90 | 271/282（96.10%） | 78/78 |
| structured_state | 89/90 | 278/282（98.58%） | 78/78 |
| answer_history | 87/90 | 271/282（96.10%） | 77/78 |

6 个格式失败分为 4 个结构错误和 2 个达到输出上限的空回答；格式有效的回答没有数值/known-unknown 状态错误，另有 3 个引用错误。费用估计 USD 0.298880548，保守结算 USD 0.63745748，本轮未知/未结算预留为 0。

详细解释：[FINDINGS.md](artifacts/p2_deepseek_development_v1/FINDINGS.md)。后续执行顺序：[NEXT_PHASE_PLAN.md](artifacts/p2_deepseek_development_v1/NEXT_PHASE_PLAN.md)。交给 ChatGPT Pro 的入口：[REVIEW_GUIDE.md](artifacts/p2_deepseek_development_v1/REVIEW_GUIDE.md)。

## 本轮固定范围

| 项目 | 冻结设置 |
| --- | --- |
| 模型 | `deepseek-v4-flash` |
| 参数 | high reasoning、thinking enabled、不传 temperature、`max_tokens=8192` |
| 开发数据 | 18 个 episode，来自 3 个 NHC 初值来源组 × 3 个任务族 × 2 个分支 |
| 比较方法 | `snapshot`、`structured_state`、`answer_history` |
| 请求数 | 每 episode 每方法 5 个检查点，共 270 个计划请求、54 条独立载体轨迹 |
| 重复次数 | 1 |
| 条件预算 | 本轮独立 USD 3；最多预留 2,211,840 个请求输出 tokens |
| 传输 | socket timeout 和总网络 deadline 均为 180 秒；不自动重试 |
| 评分 | 冻结的 P2 四字段规则，程序化参考答案与独立公开证据校验 |

用户已批准上述具体范围。实际授权保存在 [authorization.json](artifacts/p2_deepseek_development_v1/authorization.json)，不是继续使用 T6 或 P1 的旧额度。四份官方文档重新下载均为 HTTP 200，价格与参数文件和之前的核验快照逐字节一致。价格适用证据见 [acquisition.json](artifacts/p2_deepseek_development_v1/docs/acquisition.json) 和 [price_attestation.json](artifacts/p2_deepseek_development_v1/price_attestation.json)。

## 测量的能力

模型每轮提交风速、气压、纬度、经度四个字段的完整状态，包含 known/unknown、数值和当前依据的记录/行号。action 按公开风速阈值确定，仅作为辅助一致性指标。

| 任务族 | 变化方式 | 主要测量 |
| --- | --- | --- |
| U1 | 只更新部分字段，之后重放旧记录 | 更新目标字段、保留其他字段、同值换源 |
| U2 | 同窗口纠正，另有其他窗口或实体干扰 | 当前版本选择、旧版重放抵抗、作用域隔离 |
| U3 | 某字段证据首次曝光前缺失，随后恢复交付 | 缺证时 unknown、证据到达后恢复 known |

初始数值来自 Ida、Florence、Dorian 的真实 NHC 记录；之后的数值、实体、窗口、版本图和投递计划明确标记为研究生成。这里测量的是依证据维护状态的能力，不是数值天气预报准确度或实际防灾建议质量。

三种方法每轮都得到截至该检查点的累计公开证据。snapshot 不附带历史回答；structured_state 附带上一份格式有效的完整状态；answer_history 附带此前所有格式有效回答。每次都是新请求，不传隐藏会话。格式无效时保留先前有效载体；格式有效的事实错误会原样进入后续载体。

因此，方法差异只能解释为在这套任务和完整证据输入下，显式回答载体的附加效果。它不能单独证明模型内部记忆机制，也不是长上下文受限条件下的记忆压缩实验。

## 如何判断结果

先看完整覆盖与独立审计，再看 9 个“任务族 × 方法”格式单元。每个单元固定 30 个机会，要求至少 29 个格式有效、最多 1 个 length 截断，并且整轮采集完整。格式失败和缺失项均保留，不通过修改分母或补跑提高通过率。

每种方法固定有 90 个检查点、360 个字段机会，其中 282 个 Gold-known、78 个 Gold-unknown。报告分别给出数值正确、数值和当前版本引用联合正确、unknown 正确、更新成功、字段保留、同值换源、支持恢复、同窗口纠正和作用域保留。

错误清单由冻结评分结果自动生成，保留期望值、实际值和引用对应的可见行。它不引入逐题人工复核或 LLM judge，也不修改原始答案、Gold 或已冻结的引用规则。没有把程序预演当作 LLM 成绩。

三个来源组、生成的配对分支和多个检查点存在依赖。方法配对比较属于开发集描述性结果，不把 270 次调用当成 270 场独立天气事件，也不据此给出广域 leaderboard 或统计显著性结论。

## 验证与费用

核心实现沿用已经通过的 999 项测试，本轮未修改核心源代码。新增后台启动器有 8 项通过的测试，覆盖文件漂移、路径越界、重复启动、凭据处理和真实报告来源约束。冻结启动器完成全部 270 个程序预演槽位，独立审计、直接评分及报告重算均成功，外部网络在预演时被阻断。

1,923 个历史保护条目与此前 P2/T6 交付目录内的 262 个文件已重新核验一致。新启动器使用复制的冻结执行包，并保留原本绑定的生产 registry，复制文件不能重置启动额度。

费用分为返回 usage 支持的缓存/时段估计、按峰值/缓存未命中价格计算的保守结算、以及未结算或未知预留。USD 3 是条件预算上限，不是实际账单或保证完成全部请求的承诺。历史 P1 attempt 79 的未知收费继续单列。

## 文件和操作入口

本轮目录：[artifacts/p2_deepseek_development_v1](artifacts/p2_deepseek_development_v1/README.md)。

只读查看完成记录：

```bash
.venv/bin/python artifacts/p2_deepseek_development_v1/runner.py status
```

最终采集日志位于 `work/p2-deepseek-development-v1/journal.jsonl`。后台已在 `artifacts/p2_deepseek_development_v1/runtime/report/` 生成独立审计、机器报告、各方法评分和原始回答轨迹，并重算验证。额外的字段错误、结构错误和完整结果表也已生成并离线复核。

不使用 API 的独立重算命令：

```bash
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=scripts/offline_guard:artifacts/p2_deepseek_development_v1/execution/dataset/implementation_source/src \
DISASTERTRACE_OFFLINE=1 .venv/bin/python -m disastertrace.controlled.live verify-report \
  --execution artifacts/p2_deepseek_development_v1/execution \
  --run work/p2-deepseek-development-v1 \
  --output artifacts/p2_deepseek_development_v1/runtime/report
```

这些命令使用当前工作区布局及冻结的生产 registry 路径。复核归档 `artifacts/p2_deepseek_development_v1/p2_deepseek_development_v1.tar.gz` 保存源码、文档、实际日志、登记和结果；文件清单与哈希见同目录 `archive_manifest.json`。归档用于完整保留本轮证据，不通过改写历史绝对路径伪装成新的可启动实验。

`runner.py launch` 是一次性入口，不能用于查看或恢复进度。已有启动意图、运行目录或生产 claim 时不得重新提交。未知发送状态保留费用预留并停止；不通过新目录、重启或复制执行包来补发。

七个留出风暴和第二模型尚不在本轮范围。本次改动与结果保留在本地开发 worktree，尚未新建提交或推送至 GitHub。
