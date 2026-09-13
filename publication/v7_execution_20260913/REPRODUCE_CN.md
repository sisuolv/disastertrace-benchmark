# 本次发布的阅读与复现

本快照包含两层材料：可直接浏览的源码/报告，以及完整本轮材料的压缩归档。
原始数据、失败记录、生成中间表、GPU捕获和重复复现目录均在完整归档中，缓存除外。
清单与压缩内容经过逐文件哈希/解压核验；这不代替科学任务准入。

## 1. 最简CPU复现

下载 `plans/v7_execution_20260913/replay/DisasterTrace_V7_CPU_Replay_20260913.zip`，
解压后进入包目录，以Python3.10或更新版本执行：

```bash
python -I run_replay.py --output replay_result
```

输出必须是新目录。该命令用标准库核对冻结输入、保存响应及E/F评分，没有模型调用。
若已安装兼容Transformers/Tokenizers，可加 `--full-tokens` 验证完整编码/解码；无需
权重、网络或API Key。它从已冻结bundle开始，不重建全部上游清洗。

## 2. 验证或展开完整本轮材料

从仓库根目录执行，核对压缩归档全部对象：

```bash
python publication/v7_execution_20260913/evidence_archive.py verify \
  --bundle publication/v7_execution_20260913/evidence/full_execution \
  --receipt /tmp/disastertrace-v7-archive-check.json
```

需要读取全部大表或原始科学样例时，恢复到一个新目录：

```bash
python publication/v7_execution_20260913/evidence_archive.py restore \
  --bundle publication/v7_execution_20260913/evidence/full_execution \
  --target /tmp/disastertrace-v7-materials \
  --receipt /tmp/disastertrace-v7-archive-restore.json
```

所有输出名称需尚不存在。恢复器不会覆盖不同内容的文件。归档按内容去重，将原路径
恢复为独立文件；大的JSON以压缩对象保存，避免GitHub单文件限制。

## 3. 当前代码与历史实验版本

新代码在 `disastertrace-starter/src/disastertrace/monitoring_fixed_v1/`，旧
`monitoring_v1`保持原样。当前源码的边界修复和独立head接口在旧GPU冻结之后完成；
历史GPU和CPU复现包按自己的冻结源码运行，不被当前版本静默替换。

源码测试从仓库根目录运行，环境依赖沿用项目说明：

本次同时展开原有 `plans/v7_review_execution_20260912/regional_01/` 测试样例，
避免旧区域回归因找不到数据被跳过。保留的是同一原始样例，没有新增天气过程。

```bash
PYTHONPATH=disastertrace-starter/src python -m pytest \
  disastertrace-starter/tests/test_monitoring*.py \
  plans/v7_execution_20260913/tests/test_fixed*.py -q
```

不要启动已经消费的GPU运行目录；它们的捕获、失败和launch记录是研究证据。原计划
中的绝对路径保留为来源记录，不代表其他机器具备相同环境。文件读取说明中的本机
命令需要相应环境，独立CPU ZIP则提供不依赖原目录的明确入口。
