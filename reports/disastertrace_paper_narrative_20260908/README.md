# DisasterTrace 论文式汇报

本版围绕整个 benchmark 的研究问题组织材料：背景与动机、相关研究、统一任务、设计理由、实验、发现、贡献与限制、下一步。开发阶段用于附录定位，不承担主讲结构。

## 建议阅读顺序

1. [论文式叙事与逐页讲稿](DisasterTrace_Paper_Storyline_CN.md)：先读第一、二节掌握完整论证，再读第六节的 18 页讲稿与转场。
2. [演示 PDF](DisasterTrace_Paper_Pre_CN.pdf)：18 页主讲、4 页附录，建议 20–25 分钟；可再交给 ChatGPT 精简。
3. 需要准备提问时，读讲稿第七节；需要追溯历史工作时，读第八节。

整场中心问题是：当天气资料持续更新，LLM 能否持续输出与目标匹配、并由当前来源支持的答案？受控更新诊断和官方预报原文是围绕这一问题的互补任务。三种历史配置是实验条件；它们不等于 benchmark 本身。

## 本版如何改写原材料

- 用连续的论文式引言解释从应用背景到可测量问题的推导。
- 为每项设计说明解决的问题、提供的证据及结论边界。
- 用三个研究问题组织实验，将每一项发现对应回前面的动机。
- 为每一页提供讲述内容和转场，方便压缩时保留因果与承接关系。
- 将阶段编号、继承资产和历史故障放到附录，保留查证入口。

## 当前证据边界

来源快照为 **2026-09-08 16:51 UTC**。受控主实验有 2,160 条已验收模型回答。原生任务完成 257 个查询的离线验证，其采集工程和 H100 预检也已通过；快照时四个 worker 均在运行，原生模型成绩尚未验收。本文没有将程序成绩或运行中的部分回答补入已完成模型结果表。

这比旧详细稿的“原生 collector 待实现”状态更新了一步。旧文件仍保留其原有截止点，不随本版自动改写。

论文框架是本次对已有工作的重新组织，不声称全部研究问题早已预注册。六项相关论文的原始页面与摘要已重新核对，记录了阅读范围；没有声称复现外部 benchmark 或已经证明首创性。

## 产物与核验

| 文件 | 作用 |
| --- | --- |
| `DisasterTrace_Paper_Storyline_CN.md` | 引言、整体定义、设计理由、发现、18 页讲稿、答辩与引用 |
| `DisasterTrace_Paper_Pre_CN.pdf` | 22 页 16:9 演示版，中文字体嵌入，矢量图表，可搜索文字 |
| `slide_manifest.json` | 每页文本及图形元素 |
| `evidence/snapshot.json` | 24 个本地来源哈希、关键结果与执行状态快照 |
| `evidence/literature/` | 六项原始论文页面、标题、摘要及核对范围 |
| `evidence/build_inputs.json` | 构建输入与代码哈希 |
| `pdf_validation.json` | 文本完整性、页面边界、字体、书签与视觉检查 |
| `evidence/document_validation.json` | 关键数字、逐页讲稿覆盖与来源一致性检查 |
| `collect_evidence.py` | 只读研究证据并保存本版快照，不提交 benchmark 作业 |
| `build_paper_pre.py` | 根据既有绘图基础生成新 PDF，不改历史报告 |

PDF 自动核验通过，全部 22 页经过联系表视觉检查，另检查统一任务图、两页主结果和官方原文案例的完整尺寸。资料制作没有调用模型或启动 GPU。

重建依赖原工作区的绘图代码、字体和 Python 环境：

```bash
cd /mnt/afs/260010168/extreme_weather_benchmark/reports/disastertrace_paper_narrative_20260908
PYTHONDONTWRITEBYTECODE=1 /mnt/afs/260010168/.venvs/disastertrace-presentation-v1/bin/python build_paper_pre.py
```

`collect_evidence.py` 不覆盖已有快照。后续结果更新应新建版本；重建 PDF 会将视觉检查标记恢复为待检查。分享 PDF 本身无需原工作区，构建脚本和证据快照不等于完整科学实验复现包。
