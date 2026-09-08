# P2 共同输出契约 v2：离线实现与下一轮开发筛选

本阶段承接首轮 P2 的结果：270 次真实响应已完整保留，但 U2 × snapshot 和 U2 × answer_history 的格式有效率均为 28/30，未达到每单元至少 29/30 的要求。新版把完整输出结构与引用说明放入三种方法共用的 system 消息，目的是准备一次可独立检验的接口修订。

当前只执行离线工作，没有新增模型 API 请求，也没有新增人工逐题标注或 LLM judge。离线程序能验证请求、评分和恢复流程；新版是否提高模型格式可靠性，仍须后续真实开发筛选检验。

已完成 **1,074 项核心回归（零跳过）和 9 项补充回归**。主程序诊断与复制后的冻结源码复演分别完成 270/270 响应并通过独立审计、报告重算。六类语义文件、七个语义模块、全部指标分母与检查点机会对照通过；30 组分数按规范化内容一致，30 份程序轨迹按字节一致。详见[离线发现](artifacts/p2_output_contract_v2/FINDINGS.md)和[复查指南](artifacts/p2_output_contract_v2/REVIEW_GUIDE.md)。

## 本次改动

- 根对象仅有 `state` 和 `action`；四个天气字段必须放在 `state` 内，每个字段都有严格的 `status/value/evidence` 结构。
- 明确 `action` 是枚举字符串，不允许复制输入里的 `answer_history`、`previous_state` 等容器。
- 明确引用使用来源文档的 `record_id`，不能使用投递事件的 `delivery_id`；行号必须指向支持该字段当前版本的 ASSERT 行。
- 为 v2 绑定独立的 system 文本哈希、请求身份和冻结执行身份，贯穿采集、恢复、独立审计与报告。旧版默认准备接口继续生成原有字节。

公开用户消息、证据、检查点、Gold、动作规则、载体规则和评分器保持原样。已收到的错误答案不会被清洗或重评分。输出上限暂时固定在 8192，继续使用 high reasoning、thinking enabled、不设置 temperature、不自动重试；原来的两次 length 失败仍是后续观察项。

## 阅读顺序

1. 本文件：目的与使用入口。
2. [技术规格](docs/P2_OUTPUT_CONTRACT_V2.md)：准确的版本边界和固定设置。
3. [离线交付目录](artifacts/p2_output_contract_v2/)：验收结果、冻结执行包、证据对照与后续提案。
4. [上一轮真实结果](artifacts/p2_deepseek_development_v1/FINDINGS.md)：保留失败和完整分母。

源码入口是 `src/disastertrace/controlled/output_contract.py`。system 消息只包含通用规则，没有填好的答案、私有 Gold、未来证据或具体失败题的正确值。

## 复现

在项目目录中，使用一个尚不存在的输出目录：

```bash
.venv/bin/python scripts/reproduce_p2_output_contract.py \
  --output work/p2-output-contract-v2-reproduction
```

该命令运行完整测试、数据构建和冻结、270 槽位程序诊断、独立审计与报告重算，然后分别使用 v1/v2 冻结源码复核报告，执行任务语义与请求对照，并检查历史文件保护清单。外部网络被禁用，本机 HTTP 测试仍可运行。

本次 13 步核心流水线在 `work/p2-output-contract-v2-acceptance-001/pipeline/` 完整通过。随后修正对照工具对 JSON 键顺序的过严检查，终验显式复用该已通过流水线，在 `work/p2-output-contract-v2-acceptance-002/` 完成；原失败记录保留。复用模式会核对完整测试记录、日志哈希、当前实现/环境和报告，不把复用写成再次执行测试。补充回归可单独运行：

```bash
PYTHONDONTWRITEBYTECODE=1 DISASTERTRACE_OFFLINE=1 \
  PYTHONPATH=scripts/offline_guard:src .venv/bin/python -m pytest \
  artifacts/p2_output_contract_v2/test_equivalence.py -q
```

单独准备 v2 时必须显式选择版本：

```bash
.venv/bin/python -m disastertrace.controlled.live prepare \
  --dataset <已验证的新数据包> \
  --rates artifacts/p1_deepseek_development/docs/rates.json \
  --registry <独立的生产登记目录> \
  --output <新的执行目录> \
  --output-contract controlled_output_contract_v2
```

冻结执行的校验包含 Python/依赖环境、实现文件和规范文档。源码变动或换环境后应重新生成候选包；历史结果使用历史冻结源码复核。登记目录具有规范绝对路径绑定，复制文件不产生新的运行许可。

## 下一步

优先准备同一开发矩阵的 **270 次单契约 v2 筛选**，沿用每个 family × method 单元的 29/30 格式门槛和最多一次 length 规则。独立 USD 3 条件预算仍需新的实际执行授权与当前匹配价格证据；它是预算保护，不能保证最坏情况下跑完全部槽位。

这轮筛选只能回答 v2 是否达到既定开发门槛。与历史 v1 的差值不能单独证明契约改动的因果效果；若需要这种结论，再单独设计交错执行的 540 次两契约实验。第二模型、来源 × 情形平衡扩展和留出集测试继续排在其后。
