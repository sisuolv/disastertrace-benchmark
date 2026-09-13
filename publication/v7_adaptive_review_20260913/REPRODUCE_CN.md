# 本次发布的阅读与复现

代码与报告可以在 GitHub 直接浏览。完整实验材料保留在本目录的
`evidence/full_execution/`；原始捕获、源数据、失败日志和复现副本按内容去重保存，
只排除 Python、pytest 和 Ruff 缓存。原始冻结文件没有改写。

## 最简 CPU 离线复现

下载仓库中的：

`plans/v7_adaptive_execution_20260913/DisasterTrace_v7_typed_adaptive_20260913_review.zip`

其 SHA256 为 `b7e9a42812a3d5baee9fe8c15f156c1a70b3c93eebad15a52ac93da481bf8ee6`，
大小 8,972,043 字节。将 ZIP 解压到新目录，进入包含 `verify_portable.py` 的目录，
用 Python 3.10 或更新版本执行：

```bash
python3 -I -B verify_portable.py . ../adaptive-replay-output
```

输出目录必须尚不存在。脚本使用标准库并禁用网络；无需模型权重、API、GPU 或新增推理。
应核对 1,800 个清单文件、重放 36 份类型化日志和 8 条控制器分支，重新审计 252 次
新回答和 108 次旧回答。解压包内的数据和源码是其自身冻结版本。

## 检查当前源码

安装环境依赖后，从仓库根目录执行：

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=disastertrace-starter/src python -m pytest \
  disastertrace-starter/tests/test_monitoring*.py \
  plans/v7_execution_20260913/tests/test_fixed*.py -q
```

当前范围为 313 项测试。区域 JSON 与固定输入矩阵的测试样例同步展开在仓库中，
避免因缺数据而跳过测试。此范围不是所有历史 P1-P14 测试；GPU 结果以冻结源码重放为准。

## 验证发布材料或展开完整材料

从完整仓库检出目录执行：

```bash
python publication/v7_adaptive_review_20260913/verify_export.py \
  --root . --scope full --verify-evidence --receipt /tmp/dt-adaptive-export-check.json
```

若只有轻量阅读 ZIP，解压后使用 `--scope reading`，不加 `--verify-evidence`。
轻量阅读 ZIP 不包含所有大型表、模型捕获和测试样例；完整 CPU ZIP 是最便捷的重放入口。

展开全部原始执行材料到一个新目录：

```bash
python publication/v7_adaptive_review_20260913/evidence_archive.py restore \
  --bundle publication/v7_adaptive_review_20260913/evidence/full_execution \
  --target /tmp/dt-adaptive-materials \
  --receipt /tmp/dt-adaptive-restore.json
```

输出和回执名称需尚不存在。每个压缩对象都有哈希和原始路径，恢复器拒绝覆盖不同内容。
完整归档还保留上一轮 `v7_followup_execution_20260913` 及整体计划
`v7_next_20260913_2`。之前发布的其他研究阶段继续在 Git 历史和既有路径中保留。

真实 GPU 运行目录均已消费，请使用验证器复查。新模型实验需要新冻结，不能通过再次
执行旧 launcher 来复现。公开可获取、归档可解码、工程通过与科学准入是不同结论。
