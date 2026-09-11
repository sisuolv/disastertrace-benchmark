# DisasterTrace V5：可行性验证与最终研究方案

本轮将 V5 的广泛候选路线收敛为天气产品证据使用 benchmark：评测 LLM/VLM 的目标对齐、证据充分性、预算内取证和版本更新。核心采用 NHC 公告、HURDAT2、GHCN-Daily、USDM、SEVIR；洪水暂为满足接入条件后再加入的扩展。

## 阅读入口

| 文件 | 用途 |
| --- | --- |
| [FINAL_PLAN_CN.md](FINAL_PLAN_CN.md) | 最终设计、数据源取舍、自动参考、第一周与约 12 周路线 |
| [RESULTS_CN.md](RESULTS_CN.md) | 真实数据与七批 H100 实验的结果及解释边界 |
| [FINAL_DATASETS.json](FINAL_DATASETS.json) | 5 项核心产品集合的版本、来源、许可与资格 |
| [NOVELTY_AUDIT_CN.md](reports/NOVELTY_AUDIT_CN.md) | 与最接近 benchmark 的碰撞核查和贡献边界 |
| [REVIEW_FOR_CHATGPT_PRO_CN.md](REVIEW_FOR_CHATGPT_PRO_CN.md) | 可直接交给外部复查者的背景和问题清单 |
| [REVIEW_PACKAGE.zip](REVIEW_PACKAGE.zip) | 包含方案、结果、关键代码和逐题审计的精简复查包；不含权重和全部原始数据 |
| [REPRODUCIBILITY.md](REPRODUCIBILITY.md) | 离线重放方法、环境与发布依赖 |
| [FINAL_RESULTS_02.json](analysis/FINAL_RESULTS_02.json) | 最终机器结果，包含 Wave7 辅助诊断 |
| [RESOURCE_ACCOUNTING.json](RESOURCE_ACCOUNTING.json) | 实际作业、并发、调用、token、下载与计量限制 |
| [VERIFICATION.json](verification/final_01/VERIFICATION.json) | 最终七批原始响应重放与绑定核验 |
| [CLOSURE.json](CLOSURE.json) | 本轮完成范围、时间与尚未建设的正式 benchmark 部分 |

本轮采用最多 4 张 H100 并行，完成 3,599 次调用；最初协议失败与后续修订独立保留。没有新增逐题人工标注/复核、LLM judge、付费 API、训练或 heldout 推理。已有公开专家产品的原始人工来源予以披露。

“12 小时”是用户授予的自主执行时间上限。实际起止和用时记录在关闭文件中，不会因为提前完成可行性验证而把等待时间记成实验工作。

## 结果应怎样理解

主要产品事实矩阵有 92 个开发 episode，其中一半是受控删资料变体；它们不是 92 个独立极端事件。主指标要求正确结论与充分的已读引用。结果表、错误分解、源/模型成本分开报告，不用一个总分概括全部天气能力。

自然缺测诊断保留原始 VIL 像素中的缺测值。紧凑计数和程序上下界是后加的探索性接口诊断，不替换原始分数。原生视觉、精确数值、确定性工具与历史状态载体各自有信息/成本差异。

文献核查不支持将“多灾种 + 多模态 + 主动取证 + 自动评分”本身作为首创主张。拟议的新测量范围是固定天气目标、源产品支持语义和证书/预算分解；正式论文仍需更多独立分组与跨模型谱系证据。

## 目录与版本

`data/`、`analysis/`、`gpu/`、`attempts/` 保存实际材料；`code/` 保存本轮可执行工具。`BASELINE.json` 绑定继承材料，本轮没有回退或改写它们。`TASK_LEDGER.json` 是本轮状态表。

`analysis/FINAL_RESULTS.json` 是 Wave7 前的汇总；后者加入后，规范入口为 `analysis/FINAL_RESULTS_02.json`。SEVIR、Sen1Floods11 和气候基准期的早期失败/修正报告均保留，规范版本由 `FINAL_DATASETS.json` 指定。

本目录是本地开发与复查材料。公开完整 benchmark 所需的可移植环境、未见测试集、规模化数据和最终论文矩阵，列在最终计划中。本轮没有新建 Git 提交或推送。
