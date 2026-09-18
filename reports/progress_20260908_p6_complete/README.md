# DisasterTrace P6 完成版汇报材料

请从 [PRESENTATION_CN.md](PRESENTATION_CN.md) 开始阅读。这是一套面向 15–20 分钟研究汇报的中文 Markdown 讲稿，包含 12 页主讲、逐页解释与过渡、16 个追问回答，以及完整数据和验证附录。

本版依据 P6 最终验收结果：2,160 条真实受控任务回答收齐，1,861 条完整正确；12 份官方预报来源已完成试点，原生预报任务尚未进行 LLM 评测。它补充此前 `reports/progress_20260908/` 中较早的运行快照，不改动旧版材料或已验收实验。

## 材料

| 文件 | 使用方式 |
| --- | --- |
| [PRESENTATION_CN.md](PRESENTATION_CN.md) | 汇报主线、12 页讲稿、附录与不同时间长度的取舍 |
| [可靠性图](figures/01_reliability.png) | 检查点全对、五轮全对、两次都五轮全对 |
| [错误归因图](figures/02_error_attribution.png) | 展示值/状态错误与来源错误 |
| [配对结果图](figures/03_paired_outcomes.png) | 曝光后四种配对结果，保留双向变化 |
| [真实来源示例图](figures/04_forecast_example.png) | Francine 同一目标时刻在三份公告中的覆盖和更新 |
| [presentation_data.json](evidence/presentation_data.json) | 图表对应的数字、分母与来源摘录 |
| [validation.json](evidence/validation.json) | 本次图表生成和输入文件检查 |

每张图同时提供 PNG、SVG 和 PDF；正文中的中文表格保留全部核心结果，图表使用英文标签便于直接导出。讲稿是 Markdown，没有生成新的 PPTX 幻灯片文件。分享目录或随附 ZIP 时，相对图片和本地证据链接可用；指向原实验工程的链接需要完整项目目录。

## 重建

在此目录运行：

```bash
python3 tooling/build_figures.py
```

使用当前环境已有的 Matplotlib 和 NumPy。脚本只读已有结果，核对分子、分母和真实来源行的原始字节，重建图表与 CSV。它不会调用模型、访问网络或重新运行实验评分。

本次检查覆盖所使用的数字、来源摘录及 16 个关键输入文件保持不变，另检查 Markdown 链接与主结果表。它不替代历史 9,434 文件的完整科学验收；相关验收记录与复现入口在主讲稿附录 H 中。
