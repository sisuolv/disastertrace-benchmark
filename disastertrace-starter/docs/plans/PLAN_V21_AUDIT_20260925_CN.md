# plans_v21_0925 最新进度与证据审核（2026-09-25）

## 审核范围

本审核基于当前工作树的实际代码、最新执行产物、v21 执行包以及可复现实验和测试结果。实际 HEAD 为 `9dffe43e81c0a2b47f79ad08139e9d1f0d243f4e`，分支为 `codex/v18-repaired-release-20260923`。工作树不是 clean：11 个 tracked 文件修改、约 648 个 untracked 文件。旧实验结果未覆盖；当前新增 real dev 产物只做 source-only qualification，未读取 holdout 或 quarantine 数据，也没有 provider/API 调用。

## 证据分级

### 已直接验证（PASS，范围受限）

- v17-v21 定向回归共 221 项，全部通过，覆盖 v17 census、v18 grid/natural/evidence/API/dev-builder、v19 offline gate、v21 active policy、delivery intervention、natural score、repair trial 以及 synthetic Y1 adapter。
- `git diff --check` 通过；代码和产物 hash 校验没有 mismatch；相关代码可完成 compileall。
- v21 Natural synthetic 最小闭环已能验证：target hash/snapshot、只读 public state、future-private 不进入 catalogue、隐藏 query 拒绝、content-dependent follow-up、ID renaming invariance。
- delivery intervention 的最小性质已验证：parent 不被修改、catalogue 保持一致、withhold 只改变 delivery、不可用时 no-op。
- repair trial 的最小性质已验证：repair APPLIED、sham 保持原 suffix、repair 改变 suffix、source 不变、evicted query 有明确原因。
- synthetic score fixture 能验证 registration order/carry-forward、invalid cell 处理和 missing-Y 分母；当前三案例 fixture 中 active mean loss 为 0.24，fixed mean loss 为 0.25，差值为 -0.01。
- 新的五方法 fixture 使用同一 evidence stream、同一 F 和同一 checkpoint grid 比较 fixed、no_extra、source_rr、source_hash、active；active mean loss 为 0.24，最佳 non-active 也是 0.24，因此 active 的独立收益仍未显示。
- 新的 bounded real dev source-only roster 已按 metre visibility、TEMPO/conditional semantics 和三 checkpoint 重新生成：24 episodes、72 checkpoints，仍无 outcome、model 或 provider 调用。
- 四个 reserved H100 worker 各写出 8 行 CUDA 结果，worker 侧识别为 `NVIDIA H100 80GB HBM3`，结果 hash 有效。

### 只能算部分完成（PARTIAL）

- 当前 0.01 的 active 相对 fixed 优势来自小型手工 synthetic fixture，且最佳 non-active baseline 同样达到 0.24，不能外推到真实天气、一般数据分布或研究价值。
- H100 job 的平台状态是 `SUSPENDING`，不是 clean `SUCCEEDED`；只能证明 worker 在停止前写出了有效结果，不能把它写成完整稳定的 GPU 运行成功。
- v21 执行包中的 `codex_tasks.json` 仍将 A-00 至 G-01 全部标为 `NOT_STARTED_IN_THIS_PACKAGE`。这说明代码和诊断已经超出包内原始状态，但正式任务状态、acceptance matrix、artifact mapping 尚未回填，不能声称整个 v21 package 已完成。
- A-00/A-01/A-02/A-03 的正式 receipt、corrigendum、diff reconciliation、method/data card 尚未形成完整可审计链。
- B-03 的 identity-repeat/delay chronology、D-01 的 intervention registry、F-03 的 counting/freeze protocol 尚未达到正式交付级别。
- C-03 baseline bridge 尚未完成正式 receipt；E-01/E-02 已有五方法统一 shared-F 的最小 synthetic fixture，但还不是完整 Natural main trace、多 target/shared evidence 和 reliability/delay 矩阵；E-03 的 full Natural output 仍缺失。
- D-02 的同一 parent/suffix、masking/delay/mirror 后网格以及 D-03 的 original/repair/sham/error chain 目前只有最小单元性质，尚未完成计划要求的完整实验矩阵。
- F-01/F-02 的 C3 candidate、source-only reuse matrix、多 target/shared evidence extension 尚未形成可据此做 novelty 判断的结果。
- 当前分支和工作树没有形成一个 clean、可直接发布的 v21 snapshot；tracked 修改与大量 untracked 产物必须先分类。

### 明确阻塞（BLOCKED）

- 真实天气 dev pilot、真实 TAF 读取、provider/API run、holdout/quarantine 数据读取仍未执行。
- D1/P1/Y1/L1/L2/H2 等需要额外明确授权的真实或扩展实验仍保持 blocked。
- 因而目前没有 empirical forecast claim，也没有真实环境下 active policy 优于 fixed/source-RR/hash baseline 的证据。

## 对研究结论的判断

工程正确性在 synthetic scope 内已有较强证据；方法有效性只有“在该 synthetic signal 和该小 fixture 中 active 略优”的证据；研究 novelty/value 仍为 INCONCLUSIVE。当前最重要的不确定性是：active policy 的收益是否来自可复现的 evidence reliability/availability 机制，还是只来自手工 fixture 的信号设定。H100 只提高了计算执行证据，不能替代真实或更完整的研究比较。

## 建议的后续顺序

1. 先建立 clean snapshot：分类 11 个 tracked 修改和 untracked 产物，生成实际 diff reconciliation，并把 v21 task/acceptance 状态逐项回填；不要覆盖旧结果或直接把 dirty 工作树当 release。
2. 补齐 A/B/C 的正式协议材料：corrigendum、target/predictor/data card、共享语义、identity-repeat/delay chronology、baseline bridge 和 source/catalogue replay threat receipt。
3. 扩展已经落地的五方法 synthetic 主实验到多 target、shared evidence、reliability 和 delay strata；继续使用同一个 F、固定 budget、完整 failure denominator 和 missing-Y 规则。
4. 完成 D-02/D-03 的同 parent/suffix、masking/delay/mirror、repair/sham/original/error 全矩阵，并把每个结果接入统一 registry。
5. 完成 F-01/F-02/F-03 的 C3 candidate 和最小多 target/shared-evidence extension，冻结 counting protocol 后再谈 novelty。
6. 只有上述 synthetic gates 通过后，才申请一个新的、完整 denominator 的 real dev pilot；使用修复后的 aviation parser（visibility 以 metres、保留 TEMPO/PROB 语义）、新的 run ID、严格 target schema、provider response model/request ID 记录。仍不得触碰 holdout/quarantine。
7. 对 real dev 结果执行预注册的 go/no-go：若 active 在多个信号可靠性和延迟条件下稳定优于 baselines 才继续扩展；若收益消失或只在手工设定出现，应转向更明确的 data/reliability contribution，而不是扩大算力。

## 可复现入口

- `v21_execution_20260924/EXECUTION_MANIFEST.json`
- `v21_execution_20260924/EXECUTION_STATUS.md`
- `v21_execution_20260924/CLAIM_EVIDENCE_TABLE.md`
- `v21_execution_20260924/HANDOFF_REPORT_CN.md`
- `v21_execution_20260924/NEXT_GATE.md`
- `v21_execution_20260924/REPRODUCE.md`
- `v21_execution_20260924/H100_RESULT_VALIDATION.json`
- `v21_execution_20260924/GPU_JOB_STATUS.json`
- `v21_execution_20260925_01/HANDOFF_REPORT_CN.md`
- `v21_execution_20260925_01/EXECUTION_MANIFEST_V4.json`
- `v21_execution_20260925_01/G1_DEV_EPISODES_V2.json`
- `v21_execution_20260925_01/NATURAL_SYNTHETIC_SCORE_V2.json`
- `plans_v21_0925/DisasterTrace_Codex_Execution_Package_20260924_NotionAligned_v2.zip`
