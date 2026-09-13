# v7 实现与实验复现说明

本次交付支持在无模型权重、无新模型调用的条件下核验已记录结果。这里的“离线复现”
是原始响应、token、费用、权限、版本事件和分数的重建；不是重新生成相同模型回答。
新一轮真实推理应另外冻结实验和资源，不能重用已经消费的 GPU 启动标识。

## 1. 阅读与完整证据的区别

- 阅读入口：本目录 `REVIEW_FOR_CHATGPT_PRO_CN.md`，以及
  `../../plans/v7_review_execution_20260912/FINAL_REPORT_CN.md`。
- 精简阅读 ZIP：`DisasterTrace_v7_Implementation_Review_20260913.zip`。
  它包含代码、合同、统计报告、失败记录和图；不包含全部大型原始输出。
- 可复现证据：本目录 `evidence/<unit>/manifest.json` 与 `part-*.zip`。
  `EVIDENCE_INDEX.json` 列出各单元；每个分片均小于 80 MiB。
- `inventories/*_ARCHIVE_CHECK.json` 记录实际完整解压后的内容哈希核验。
  内容一致性不等于新灾种通过科学准入，也不等于模型具有预测收益。

精简 ZIP 中的 `EXPORT_MANIFEST.json` 同时登记 GitHub 完整交付文件。
其中 `in_reading_zip=false` 的条目应从同一 GitHub 提交获取；不要把它们误判成阅读 ZIP 丢件。
SHA256 用于验证实际收到的内容，Git 提交 ID 用于固定所审阅版本。

## 2. 已实跑的隔离检查

`plans/v7_review_execution_20260912/packaged_replay_01_receipts/` 保存第一轮完成证据。
检查从实际证据 ZIP 恢复独立目录，随后完成：

| 检查 | 实际范围 |
| --- | --- |
| 核心与分析测试 | 109 项，0 失败、0 跳过 |
| 原始数据重建 | 2026 日历，11 个派生 JSON 逐字节一致 |
| 文本小样回放 | 16 条原始模型响应 |
| 原生多模态回放 | 72 条 Qwen3-VL-8B 响应 |
| 32B 文本 E 诊断 | 384 条响应 |
| 完整湾区日历回放 | 5,184 条响应 |

上述模型回放合计 5,656 条，不增加本轮模型调用总数。原项目数据/代码读取被拒绝；
测试只允许 loopback，模型及数据回放阻断 socket 网络。回放的是已记录 ACP 作业和硬件
回执，不声称重新查询了线上 GPU 状态。运行使用机器上已经安装的 Python 依赖；没有
把“数据与权重隔离”说成“在任何全新软件环境都已复现”。

随后将复现驱动的模型 Python 路径改为 `--model-python` 可配置参数。第二轮证据以
`packaged_replay_02_receipts/COMPLETE.json` 记录，已经完成同样的 109 项测试、数据重建
和 5,656 条回放。两轮分别保留绑定与执行记录，不累计成独立模型样本。

## 3. 推荐复现顺序

在 GitHub 检出本次完整提交，保持相对目录结构。优先使用 Linux / Python 3.10，
把复现环境放在被审阅仓库以外，避免与“禁止读取原项目”检查冲突。
机器上实测的相关包版本见 `REPLAY_ENVIRONMENT.json`；这些版本是环境记录，不是新的
依赖兼容性保证。核心测试只需要 pytest 与 pydantic。token/图像处理器回放还需要
Transformers、tokenizers、PyTorch、torchvision、Pillow 和 NumPy；不需要 vLLM 推理服务。

先验证一个证据单元，只读校验不还原数据：

```bash
python publication/v7_review_execution_20260912/evidence_archive.py verify \
  --bundle publication/v7_review_execution_20260912/evidence/pilot_02 \
  --receipt /tmp/disastertrace-v7-pilot-content-check.json
```

`--receipt` 必须为尚不存在的文件。所有恢复工具拒绝用不同内容覆盖已有文件。

使用已经安装所列依赖的 Python 运行完整离线复现：

```bash
python plans/v7_review_execution_20260912/replay_packaged_evidence.py \
  --model-python /absolute/path/to/review-environment/bin/python \
  --output /tmp/disastertrace-v7-isolated-replay
```

这里第一个 `python` 要有 pytest、pydantic；`--model-python` 指向能够重放 tokenizer
与图像 processor 的环境。若同一 Python 已具备全部依赖，可以省略该参数。
输出目录必须不存在，且不要放进当前被审阅仓库。成功标记为新输出目录中的
`COMPLETE.json`；中间日志或文件存在不代表整个检查成功。

该命令恢复 9 个证据单元，不加载权重，不重新访问天气服务，不启动 GPU，
不消费任何旧作业身份。完整输出在 CPU 上重建的耗时取决于磁盘与 Python 环境。

## 4. 复核其余已完成日历

先恢复所需单元到新的空仓库根目录；例如，`model_front_base` 保存 Front Range 2024
的原始 base 协议批次。所有可用单元以 `EVIDENCE_INDEX.json` 为准。

```bash
python publication/v7_review_execution_20260912/evidence_archive.py restore \
  --bundle publication/v7_review_execution_20260912/evidence/model_front_base \
  --target /tmp/disastertrace-v7-extra-evidence \
  --receipt /tmp/disastertrace-v7-front-restore.json
```

`offline_model_replay.py` 接收恢复后的 `--batch`、`--validation`、`--evidence`、
`--tokenizer-root` 和全新 `--output`。F 结果使用对应数据集 `private/OUTCOMES.json`，
E 诊断使用已冻结的 E 标签表；二者不能交换。标签只在评估器使用，不能交给模型策略。
Front Range 2024 需指定 `--region front_range`，2026 指定 `--region front_range_2026`，
以逐字段重建原报告的区域身份；默认 `bay_area` 只适用于湾区报告。

2026 base 批次的三份 ZIP 恢复与 5,184 条输出回放另有专用驱动：

```bash
python plans/v7_review_execution_20260912/replay_replication_evidence.py \
  --model-python /absolute/path/to/review-environment/bin/python \
  --output /tmp/disastertrace-v7-replication-replay
```

输出同样必须是被审阅仓库以外的新目录。实际成功记录以
`packaged_replay_replication_01_receipts/COMPLETE.json` 是否存在为准。

`analyze_calendar.py` 从原始 trace 重建全部机会的 `ROWS.json` 和报告，随后
`analyze_static_baselines.py` 比较全零与此前月份频率，`analyze_wrappers.py` 分开比较
两种协议的独立运行结果和固定候选回放。大型 `ROWS.json` 未直接塞入阅读 ZIP；它可由
证据恢复后重建。所有工具输出新的目录，不覆盖已有结果。

补充分析也不需要模型权重或新推理：`analyze_warning_ranking.py` 从重建的 ROWS 计算
AP/ROC 与固定阈值；`analyze_resource_pressure.py` 将完整日历报告与绑定 trace 对账；
`analyze_joint_E.py` 将全机会 E 与已核验的源查询路径参照对齐。参照是评估侧离线计算，
不供模型读取，也不优化未来预测。`analyze_e_order.py` 逐案例检查顺序复核相对原轮的
输入 token 和回答变化，不能仅根据未恢复的大型原始文件运行。

`hydro_revision_preflight` 证据单元保留同三站、同窗口的前后两次 USGS 原文；
`verify_hydro_revisions.py` 可以离线比较它们。执行 `capture_hydro_revisions.py`
会产生新的网络请求，因此不是离线复现所需步骤，不能把新下载覆写到已记录版本上。

`hydro_gauge_metadata` 和 `hydro_stage_preflight` 单元保留官方站点映射、当前阈值、
NWPS 原生水位预报/观测与 USGS 00065 样例。`verify_hydro_metadata.py` 和
`verify_hydro_stage.py` 只读取已存文件；后者可用 `--metadata` 指定恢复后的
`hydro_metadata_validation_01/REPORT.json`，仍要求与原绑定 SHA256 完全一致。
这些检查不把 Stage/ft 转换成流量、不补齐缺失时刻、不创建新洪水标签。当前服务配对
不能证明历史阈值有效性或两服务具有独立测量来源。

## 5. 可复现范围的边界

历史公开时刻没有逐条 first-seen 证明，仍按登记的历史延迟假设重放。独立解码器的一致
只针对检查过的原生字段，不证明连续物理真值。72h 资源会话不等于独立风暴；跨年份也
不能自动排除模型训练污染。固定动作的 wrapper 回放不等于重新运行适应性策略。

图像对照只有一个区域过程，32B E 诊断为文本条件。精简交付不包含旧阶段的大型样本、
模型权重、授权密钥、已安装环境，也不改写旧证据。完整 16 类版仍以主计划的准入门槛
逐类推进，不能以当前复现成功替代科学验收。
