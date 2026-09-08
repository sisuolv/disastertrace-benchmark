# P2 共同输出契约 v2 离线交付

入口：[项目说明](../../README_P2_OUTPUT_CONTRACT_V2.md)。这份交付在首轮 P2 实测基础上修订三种方法共同收到的 system 输出说明，保留已有数据、Gold、严格评分与全部历史响应。它不包含新的真实模型成绩。

## 文件导航

| 文件或目录 | 用途 |
| --- | --- |
| `FINDINGS.md` | 本阶段实现和验证结果，以及仍不能得出的结论 |
| `REVIEW_GUIDE.md` | 交给 ChatGPT Pro 复查的重点和定位 |
| `NEXT_PHASE_PLAN.md` | 下一轮 270 次开发筛选的具体计划 |
| `FINAL_STATUS.json` | 已完成的离线范围、各项身份及调用数 |
| `system_message.txt`、`output_contract.json` | 模型将收到的精确 system 文本及其哈希；尚未发送 |
| `execution/` | 新的递归冻结执行包，授权模板仍为 false |
| `proposal.json` | 独立调用范围、参数、条件预算、登记路径和启动条件 |
| `equivalence/` | 六类语义文件、七个语义模块、30 组分数/轨迹和全部机会分母的对照 |
| `diagnostic_report/` | 270 槽位程序诊断的独立审计、固定分母评分与运行观测 |
| `validation/` | 实际命令、退出码、日志、冻结复核和历史保护检查 |
| `baseline/` | 2,554 项历史保护清单及本次改动前的可编辑源码/文档副本 |
| `p2_output_contract_v2_review.tar.gz` | 本阶段复查归档，身份见 `archive_manifest.json` |

`equivalence/request_comparisons.jsonl` 对首轮实测的 270 份公开请求做两种准备方式的字节对照，包括原来的模型载体。这只是未发送的离线投影；候选 v2 的诊断和后续真实运行均不使用旧回答初始化历史，也不能把这些投影算作 v2 的真实暴露。

## 验证入口

完整复现命令见项目入口。13 步核心验收的原始工作目录是
`work/p2-output-contract-v2-acceptance-001/`；终验在 `work/p2-output-contract-v2-acceptance-002/` 显式复用并核对已经通过的核心流水线，保留第一次外层对照失败记录。`001/pipeline/rehearsal/` 为主程序诊断，`001/pipeline/live_registry/` 为独立生产登记目录；`002/frozen_rehearsal/` 保存复制后的冻结源码整矩阵复演。两次诊断均不占用生产 claim。

新旧报告分别以各自冻结源码重算。新源码不能用来覆盖旧执行的实现身份；改变参数、system 文本、模型或依赖也不能沿用旧身份。

本交付不新增 API 调用、人工逐题标注、LLM judge、训练、第二模型或留出推理。原 P1 attempt 79 的未知费用仍属于独立历史问题；P2 首轮已经结清的采集预留不因本次离线工作发生变化。
