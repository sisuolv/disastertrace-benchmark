# 交给 ChatGPT Pro 的 MM-3 复查说明

请评审这次单事件多模态开发试跑的测量有效性，不把离线测试、程序成功或 ACP
`SUCCEEDED` 当作模型答题成功。关键结果是：真实图片输入和 GPU 前向通过，12 个
回答全部返回且 EOS 结束，但 12 个 `state` 都是数组，因此严格契约有效率为 0/12。

## 建议阅读顺序

1. `IMPLEMENTATION_STATUS.md`：真实完成范围、结果、失败与限制。
2. `EXECUTION_PLAN_CN.md`、`EXECUTION.json`、`REQUEST_PLAN.json`：生成前固定的条件。
3. `gpu_run/live/`：每一项的原始请求、图片、提示、input_ids、processor manifest、
   intent、原始回答、生成 token 和 outcome。
4. `REPORT.json`、`FORMAT_ANALYSIS.json`：严格计分与另列的结构错误分析。
5. `input_replay_01/VERIFIED.json`、`CPU_REVIEW_RESULT.json`：实际输入重放和迁移重建。
6. `../mm3_contract_v2_offline_20260909/`：仅在离线准备的格式说明补充与测试。

## 请重点核对

- 图片是否进入真实 pixel_values 和视觉 token，而不是仅把 base64 放入文字。
- metadata、图片附件、delivery、绝对 valid time 与版本是否一致，未来地点 C
  是否只在其公开请求出现后进入正常轨迹。
- 原始提示是否足以推出解析器要求的地点 ID 对象映射；V2 是否只明确结构，
  没有嵌入正确答案、当前正确来源或未来状态。
- 无效输出是否如实进入模型自己的历史；各轨迹之间是否独立，是否发生答案修补。
- 0/12 是否被准确解释为格式门槛失败，而非直接推断视觉能力或广泛天气能力。
- 无地图与完整信息条件采用不同参考答案时，是否避免把准确率差当成纯视觉贡献。
- 一次事件、两个地图版本和重复检查点，是否被错误当作独立事件扩大统计样本量。
- 作业完成、模型接口通过、科学结论可靠这三个层次是否明确区分。
- 采集源码、模型快照、运行库、原始 token 和 deterministic scorer 是否足以重建。

## 无 GPU 复查

`MM3_REVIEW.zip` 中的 `cpu_review/` 包含可迁移的最小评分副本及原参考。
在已安装 MM CPU 依赖的环境中，可运行：

```bash
python cpu_review/review_cpu.py \
  --bundle cpu_review \
  --receipt /tmp/mm3-review-new.json
```

收据路径必须是尚不存在、且不在受禁止原目录下的路径。复查不会访问模型权重，
不会导入 Torch/Transformers，不会生成新回答。完整图片/token 的 processor 重放
另需记录中的 VLM Python 依赖，但同样不加载模型权重、不调用 GPU 生成。

请按严重性列出协议缺陷、实现问题、统计解释风险和缺失测试，并给出具体文件依据。
请勿将 V2 的 41 项离线测试通过写成“V2 模型已通过”；V2 模型调用仍为零。
