# P6 完成版汇报 PDF

[打开汇报 PDF](DisasterTrace_P6_Presentation_CN.pdf)

- 16:9 横版，共 18 页：前 12 页主讲，后 6 页附录。
- 建议主讲 15–20 分钟；各页有 PDF 书签。
- 中文字体已嵌入，文字可复制与搜索；图表和图形均为矢量。
- 内容固定在已验收 P6：2,160 条受控任务回答、1,861 条全对；原生预报来源试点完成，原生任务尚未实测。
- 制作期间 CURRENT_PHASE.md 出现新阶段更新。按用户要求，本 PDF 保持 P6 截止范围；新增进展另存更新版。

全部 18 页已渲染检查，文字完整性、页面边界、字体嵌入、书签与输入文件核对通过。详情见 [pdf_validation.json](pdf_validation.json)。

重建使用现有汇报专用环境，不需要模型或 GPU：

```bash
/mnt/afs/260010168/.venvs/disastertrace-presentation-v1/bin/python build_pdf.py
/mnt/afs/260010168/.venvs/disastertrace-presentation-v1/bin/python validate_pdf.py
```

完整讲稿见 [PRESENTATION_CN.md](../PRESENTATION_CN.md)。
