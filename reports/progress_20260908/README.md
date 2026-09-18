# DisasterTrace 汇报材料

新增的 [完整 Markdown 演示稿](PRESENTATION_CN.md) 将主讲内容、讲解提示和扩展实验结果整合在一个文件中：24 个主讲章节、8 个附录、30 张表与 5 张图。Markdown 快照为 2026-09-08 13:11:33 UTC（北京时间 21:11:33），P6 已保存 1908/2160。旧 PPT/PDF 保留各自的历史快照。

分享 Markdown 时推荐使用 [Markdown 与图表压缩包](DisasterTrace_Markdown_Pre_20260908.zip)，包含相对路径图片、汇总 JSON、CSV 和来源核对记录。新增五轮全对等指标均由既有评分聚合，属于补充诊断，不改变原实验评分。

快照：**2026-09-08 12:52:04 UTC**（北京时间 **2026-09-08 20:52:04**）。

核心结论：P5 已完成 1620 条真实压力评测，1360/1620 完整正确；P6 的 2160 槽位配对实验已保存 1680 条，最终报告仍待验收。P5 已上传 GitHub，P6 本地更新。

## 推荐使用顺序

1. [PowerPoint：20 页主讲 + 4 页附录](DisasterTrace_Progress_20260908.pptx)：可编辑文字和图形，逐页备注已内嵌，约 18–20 分钟。
2. [PDF 演示版](DisasterTrace_Progress_20260908.pdf)：嵌入中文字体，可直接投屏或分享。
3. [运行结果与迭代逻辑](ITERATION_RESULTS.md)：每轮问题、改动、实测、下一步，以及完整分子分母表。
4. [详细解释与答辩问答](REPORT_CN.md)：任务定义、自动 Gold、已测发现、边界和后续验收标准。
5. [逐页讲稿](SPEAKER_NOTES.md)：可直接练习，含每页时间与来源索引。
6. [整套幻灯片预览](preview/contact_sheet.jpg)：用于快速检查叙事顺序。

`charts/` 有独立 PNG、SVG、PDF 图表；`report_data.json` 为绘图数据；`evidence/` 保存状态快照、来源散列与制作校验记录。

## 字体与技术验证

PPT 使用 **Noto Sans SC**，`fonts/` 附静态 Regular/Bold 与 OFL 许可。电脑没有该字体时，PowerPoint/WPS 可能替换字体；可安装随附字体，或直接使用已经嵌入字体的 PDF。PPT 的图表为高分辨率图，其他文字和图形可编辑；矢量图独立保存于 `charts/`。

已检查数字守恒、PPTX/XML 可解析、24 页与全部备注存在、元素画布边界及中文字符覆盖。PNG/PDF 从相同布局源用 Pillow/ReportLab 生成；当前环境无 PowerPoint/LibreOffice，未声称经过它们的实际排版渲染。

## 如何理解“最新”

这是一份带时间戳的静态汇报。P6 作业继续运行后，保存条数会增加；最终能力结论需以完整独立报告为准。运行中的计数不等同于已验收得分。P6 官方 forecast 来源试点在本快照仍为范围和解析准备，没有最终准入数据报告。

历史记录有冻结边界，最新入口是：

- [CURRENT_PHASE.md](/mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/disastertrace-starter/CURRENT_PHASE.md)
- [P6 CONTINUE.md](/mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/disastertrace-starter/artifacts/p6_live_v1/CONTINUE.md)
- [P5 实测与交接](/mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/disastertrace-starter/REVIEW_FOR_CHATGPT_PRO_P5.md)

GitHub 已核验 P5 提交：[dd5ee358f970](https://github.com/sisuolv/disastertrace-benchmark/commit/dd5ee358f9708e2eb2f2032db9eaac14fa237adc)，仓库私有。P6 未并入该快照。

## 生成方式

所有脚本在 `tooling/`，只读原项目，写本汇报目录。使用独立 `/mnt/afs/260010168/.venvs/disastertrace-presentation-v1` 环境，未改变 benchmark 的运行环境。P6 完成后，需先阅读最终结果并调整进行中叙述，再重新生成；不要只刷新计数就声称科学结论已更新。

```bash
python3 tooling/collect_report_data.py
/mnt/afs/260010168/.venvs/disastertrace-presentation-v1/bin/python tooling/build_presentation.py
/mnt/afs/260010168/.venvs/disastertrace-presentation-v1/bin/python tooling/write_reports.py
```

字体来自 Google Fonts 的 Noto Sans SC，通过 jsDelivr 下载；绘图/演示依赖从清华 PyPI 镜像安装。无需模型 API 密钥或 GPU 即可重新生成材料。
