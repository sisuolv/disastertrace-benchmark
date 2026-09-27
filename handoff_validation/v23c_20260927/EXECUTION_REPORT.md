# DisasterTrace v23c 执行进度

> 这是一份截至 2026-09-27 的 GitHub 交接记录。它区分代码正确性、作业执行、方法结果和研究结论；不把作业成功等同于科学假设成立。

## 1. 发布边界

- 仓库：`sisuolv/disastertrace-benchmark`
- 分支：`v23-exec`
- 当前 HEAD：`8a5def77f310a9037ef9f6388e6b3d16e8c633b4`
- 执行目录：`/mnt/afs/260010168/extreme_weather_benchmark/plan/plans_v23_0926/exec_v23c_20260927T042855Z/`
- 本次上传只加入本报告和元数据 manifest；没有加入原始 TAF/METAR/ASOS/LAMP 正文、完整预测 JSONL、Y1 行级结果或任何凭据。

## 2. 代码与测试

本分支相对执行起点增加了 v23c 的实现和校验提交，最新两项是：

- `f22402666`：加入离线 H100 的 M1/M2 推理 worker。
- `8a5def77f`：移除概率提示中与 K6 冲突的两行 action 模板，并更新回归测试。

此前同一链路还提交了 METAR remark/peak-wind、航空距离和年份词泄漏扫描修复，以及 v23c 预注册/J2 合同。

针对最新提示修复运行：

```text
PYTHONPATH="$PWD/disastertrace-starter:$PWD/disastertrace-starter/src" \
python3 -m pytest \
  disastertrace-starter/tests/test_v23c_prereg_and_contracts.py \
  disastertrace-starter/tests/test_v23c_j2_analysis.py -q

结果：10 passed（仅有 pytest 配置的 asyncio_mode warning）。
```

## 3. C1 预注册与 prompt

C1 已完成并封存。`PREREG_SEAL_v2_rev1.json` 绑定当前代码、source-only roster、F/策略/固定调度合同和 prompt manifest。

- M1 prompt：23,808 行；SHA-256 `117508b272b1a8c7e280a095dff9cad92c0573f5ba4c1918c6d27113c02f720f`。
- M2 prompt：5,768 行；SHA-256 `21119bf1bf8cba46a54bde5ede04cf112b3ade2672f51b212940eb3ac39f9dc9`。
- prompt 泄漏扫描：PASS；最终概率 prompt 不含 K6 action 模板。
- `G_adapt` 合成验收：零价值世界判 STOP，正价值世界判 GO；Y-oracle 的 H 仅保留 STOP 角色。
- prereg seal SHA-256：`0976251c459fd680ad0b2c481c25649a234d6fe6a29166245774b4b2df0d1c47`。

## 4. C2 ACP/H100 真实作业

CCI 只负责提交和监控 ACP；模型推理在标准 H100 worker 上运行。所有四个作业均为 `SUCCEEDED`，输出行数和概率格式校验均通过：

| 阶段 | ACP job | 输出 | GPU·h | 结果 |
|---|---|---:|---:|---|
| smoke | `pt-z5ly1fnr` | M1/M2 各 20 | 0.1067 | 20/20 有效 |
| M1 full | `pt-avmt6awf` | 23,808/23,808 | 0.1286 | 全部有效 |
| M2 shard 0 | `pt-j91edy4n` | 2,884/2,884 | 0.6322 | 全部有效 |
| M2 shard 1 | `pt-lxm2fdvy` | 2,884/2,884 | 0.6242 | 全部有效 |

合计 `1.4917 GPU·h`，低于 12 GPU·h 上限。`LLM_PREDICTION_SEAL.json` 已建立，SHA-256 为 `7a1a0975b86491bddabd8ad901b3b822acbfa81f9b3b4b134eb8a1192db6c0dc`。

> 注：上面 seal 的 SHA-256 以外部 artifact 中的实际文件为准；完整预测文件没有提交到 Git，manifest 保存其外部路径和哈希。

## 5. C3 Y1 与探索性分析

读取前 gate 通过后，Y1 只读取批准的 8 个 ASOS body/receipt 对（16 个文件）；未读取 D1、TAF body、holdout/quarantine、2025-02、2023–2024 或 2025-04～12。Y1 日志恰好 16 行。

- 目标：5,952
- BOUND：5,755
- MISSING：197
- CONFLICT/UNDETERMINED：0/0
- routine 规则：`iem_routine_unique_hour.v1`；11:51Z 归入 `[11:00,12:00)`
- provider calls：0

C3 的 J2a 结果标记为 `development_status=exploratory`，因为 Jan/Mar 开发数据已暴露，不能作为确认性结论：

| 量 | 点估计 | 95% CI | 预注册判定 |
|---|---:|---|---|
| `V_fusion` | 0.0002263 | [-0.0003031, 0.0008027] | STOP |
| `G_adapt` | -0.0004334 | [-0.0011297, 0.0002178] | STOP |
| `H`（STOP only） | 0.0129663 | [0.0092810, 0.0171465] | 不能用于 GO |
| `D_llm` M1 raw | -0.0317034 | [-0.0382004, -0.0257953] | STOP |
| `D_llm` M1 calibrated | -0.0161940 | [-0.0231289, -0.0099898] | STOP |
| `D_llm` M2 raw subset | -0.0397397 | [-0.0575714, -0.0262951] | STOP |
| `D_llm` M2 calibrated subset | -0.0130143 | [-0.0206693, -0.0061798] | STOP |

这些结果支持“在当前暴露开发集和当前协议下没有观察到自适应/LLM 增益”的工程决策信号，但不支持对未暴露确认集作最终天气价值或 novelty 宣称。

## 6. 尚未完成与当前判断

- C1：PASS（封存和泄漏校验通过，独立复核仍 `REVIEW_PENDING`）。
- C2：PASS（ACP 真实 H100 作业、行级完整性和预测 seal 通过）。
- C3/J2a：已运行，结果为 exploratory；Y1 绑定完整性通过。
- C4/J2b：尚未运行。
- C5/K6：尚未运行；只有在 C4 明确 GO 时才应启动。
- C6：尚未运行。

执行目录中的 `C2/STATUS.json`、`C3/STATUS.json`、`C4/STATUS.json` 和根目录 `STOP_STATUS.json` 是首次本地 GPU 阻塞时生成的历史记录；续跑后的真实 ACP 证据以 `C2/ACP_VALIDATION.json`、`C2/LLM_PREDICTION_SEAL.json`、`C3/Y1_PRE_READ_GATE.json`、`C3/Y1_BINDING_SUMMARY.json` 和 `C3/J2A_LLM_SCORE.json` 为准。它们没有被覆盖，以保留完整审计轨迹。

当前最稳妥的下一步是先独立复核 C2 seal、Y1 读取日志和 J2a 计算，再执行 C4 的 `G_adapt` 判决。若 C4 维持 STOP，应封存 STOP 结果并停止 K6/provider 扩展；若要获得确认性天气结论，必须另行批准未暴露确认保留集和相应授权。

外部 artifact 的逐文件 SHA-256、大小和路径见 [ARTIFACT_MANIFEST.json](ARTIFACT_MANIFEST.json)。
