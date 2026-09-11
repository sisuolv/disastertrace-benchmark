# V2 真实模型验证复查指南

本批结论：12 次生成全部返回，结构解析 12/12，地点集合完整 10/12，完整正确 0/12。
请区分这三个层次，不把 `interface_gate=true` 或 ACP SUCCEEDED 当作任务正确。

先读 `IMPLEMENTATION_STATUS.md` 与生成前的 `EXECUTION_PLAN_CN.md`，再检查：

1. `EXECUTION.json`、`REQUEST_PLAN.json`：固定模型、预算、真实 V2 请求和轨迹顺序。
2. `gpu_run/live/`：原始请求、实际图片、prompt、input_ids、processor manifest、
   生成 intent、输出 token、raw.txt 和解析结果。历史只能来自本轨迹自己的原始回答。
3. `REPORT.json`、`QUERY_COVERAGE.json`、`ERROR_ANALYSIS.json`：固定分母评分、
   漏掉 C 的两个检查点，以及按字段列出的实际值/参考值差异。
4. `DESCRIPTIVE_COMPARISON.json`：V1/V2 只作单事件开发观察，不能声称无偏因果效果。
5. `input_replay_01/VERIFIED.json`、`CPU_REVIEW_RESULT.json`、`validation/`：输入及输出
   解码重放、无 Torch 的迁移评分，以及每个真实命令的退出码。
6. `acp/TERMINAL.json`、`RESOURCE_ACCOUNTING.json`：实际 H100、作业终态和时间核算。

重点复查：结构解析器与完整输出要求之间的差别；缺失地图时的无支持断言；名单证据
与强度文本的混淆；旧来源沿轨迹保留；新增地点覆盖；图片来源与 locator 的绑定。
这些诊断通过冻结参考自动计算，不进行答案修补、人工逐题 Gold 或 LLM judge。

`MM3_V2_REVIEW.zip` 中的 `cpu_review/` 可在原 MM CPU 依赖环境中独立重建分数：

```bash
python cpu_review/review_cpu.py \
  --bundle cpu_review \
  --receipt /tmp/mm3-v2-review-new.json
```

收据使用一个尚不存在的路径。该命令不加载权重、不导入 Torch/Transformers，并用
Python audit hooks 禁止网络和原项目路径读取。此隔离不等同于恶意代码的 OS 沙箱。

四卡问题见 `IMPLEMENTATION_STATUS.md` 与 `NEXT_STEP_CN.md`：当前小批生成仅
约 35 秒，四卡无法消除顺序依赖和重复加载开销。后续足够多的独立轨迹优先用四卡并行。
