# 给外部复查者的说明：DisasterTrace V5 可行性与最终设计

本包用于研究设计、数据语义、自动评分和实验证据的复查。请区分“已经完成的开发验证”与“下一阶段拟建设的正式 benchmark”。

## 建议阅读顺序

1. [最终方案](FINAL_PLAN_CN.md)：研究问题、最终来源取舍、自动参考、首周至 12 周路线。
2. [结果报告](RESULTS_CN.md)：7 个开发批次、协议失败、真实缺测、状态与成本的分项结果。
3. [文献核查](reports/NOVELTY_AUDIT_CN.md)：EarthVerse、DORA、StateMemBench、AFABench、SURE-RAG、DEMM-Bench 等近邻。
4. [最终来源清单](FINAL_DATASETS.json)：5 项核心产品集合、版本/来源/许可凭据、条件扩展。
5. [机器结果](analysis/FINAL_RESULTS_02.json)、[资源账](RESOURCE_ACCOUNTING.json)、[最终复核](verification/final_01/VERIFICATION.json)。

## 请优先检查的问题

### 科学贡献是否成立

项目不再声称首个多灾种、多模态、主动取证、状态追踪或自动评分基准。拟议贡献是天气产品固定目标与来源支持语义下的证书、预算可达性和错误分解。请检查这是否仍只是已有工作的场景迁移；如果是，指出最小需要补充的实验或重新定位方式，不要求为了“显得创新”堆更多数据源。

### 评分是否测到了声称的对象

阅读 [evidence_core.py](code/evidence_core.py) 的 `reference`、`sufficient`、`certificates`、`score`。yes/no 来自兼容产品支持；unknown 的充分性要求完整池在未读值的可能补全下仍无法判定。请核查枚举所用值域、覆盖假设、无效质量、空证书、未读引用、预算不可达、同目标版本的边界。原型限定至 8 张卡，重叠支持未经显式融合政策会被拒绝。

自动程序一致不等于源产品无误，有限补全证书也不是物理世界真实性保证。请指出文档中仍存在的混淆。

### 数据与时间语义是否正确

NHC 同一未来有效时刻的公告可形成自然预报修订；USDM 周际、GHCN 日际、SEVIR 帧际变化不属于同一目标订正。公告发行时间不能填成已经证明的首次公开时间。HURDAT2 只作评估器私有的同机构事后最佳路径结果。VIL 不等于地面降雨。USDM 的地图许可不被外推到所有相关产品，Sen1Floods11 的许可元数据冲突被保留。

### 实验是否过度解释

- Wave1 输出包装歧义导致失败；Wave2 完整重跑，旧结果不替换。请核查“只改输出协议”的比较口径。
- 主实验图像是等信息表格 PNG。原生 VIL 是另一项感知任务；精确计数和像素输入不视为同难度。
- Wave5 全历史与上次状态的 token 和信息量不同，不能推出等成本记忆算法优势。
- Wave6 只有 12 帧，no/unknown/yes 为 6/5/1；8B 原生图像全部答 unknown。必须对照恒答行为。
- Wave7 在观察 Wave6 后追加，包含表示澄清和程序算术辅助；只能作为探索性诊断，不能替换成绩或当单因素因果实验。
- InternVL 的视觉架构不同，但语言骨干也是 Qwen3。小样来自美国资料和少量开发事件，不能推出跨全球/跨模型谱系普遍结论。

### 统计与可复现性

92 episode 包含相关变体，12 条状态轨迹只来自 4 个风暴。8 个 USDM 点还共享周图。请核查正式计划中的事件/信息重叠分组、地区季节分块、类别分层与自然机会队列是否充分。当前不报告确认性显著性。

所有模型提交保留原始字符串、输入、token、processor、来源和计划哈希；评估在推理结束后执行。错误与失败保留在分母中。最终验证通过也不证明不存在所有软件或标签错误。

## 原始证据入口

| 内容 | 路径 |
| --- | --- |
| 主任务与私有参考 | `data/PILOT_EPISODES_PRIVATE.json`、`data/PILOT_REFERENCES_PRIVATE.json` |
| NHC 原公告及结果对应 | `data/NHC_PRODUCTS.json`、`data/NHC_REVISION_CHAINS.json`、`data/NHC_OUTCOME_JOINS_PRIVATE.json` |
| 状态目标与参考 | `data/STATE_PUBLIC.json`、`data/STATE_REFERENCES_PRIVATE.json` |
| SEVIR 原始数组来源 | `data/SEVIR_ARRAYS.json`、`data/NATURAL_COVERAGE_ARRAYS.json` |
| 自然缺测的完整帧统计 | `analysis/NATURAL_COVERAGE_FEASIBILITY.json` |
| USDM 原始/修复/独立点查询 | `analysis/USDM_POINT_REFERENCE_RECHECK.json` |
| GHCN 独立基准期 | `analysis/CLIMATOLOGY_FEASIBILITY_02.json` |
| 冻结输入与实际响应 | `gpu/wave*/PLAN.json`、`PUBLIC.json`、`runs/` |
| 初始 5 批普通评分 | `analysis/WAVE1_AUDIT.json` 至 `analysis/WAVE5_AUDIT.json` |
| 自然覆盖与辅助诊断 | `analysis/WAVE6_AUDIT.json`、`analysis/WAVE7_AUDIT.json` |
| 下载失败/部分完成 | `attempts/`、`batches/`、`gpu/model32_acquisition/`、`gpu/model32_resume_01/` |
| 输入计划整合与原件 | `../v5_0910_integrated/`；旧产物不属于本轮新实验 |

## 可直接给复查模型的提示

> 请作为严谨的 benchmark 研究与代码审稿人复查这个包。先按 P0/P1/P2 列出会使科学结论失效、评分错误、数据不可用或实验不公平的具体问题，并引用文件与代码位置。把已经有证据的问题、合理怀疑、需要新实验才能判断的问题分开。重点评估 novelty 是否被已有基准覆盖、unknown/证据充分性定义是否可靠、自然与受控机制是否混用、VLM 是否实际接收到可解的公开输入、统计独立性及源产品权利。不要把更多数据和更多模型作为默认建议；给出能改变研究结论的最小补充实验。最后判断下一阶段应继续原方向、缩小为诊断集，还是更换主要科学问题。

## 本地重放

从本目录运行 `python3 code/verify_feasibility.py --output verification/reviewer_01` 可在一个新的输出目录重放现有证据，不调用模型。输出目录必须尚不存在。完整环境与可复现边界见 [REPRODUCIBILITY.md](REPRODUCIBILITY.md)。

该脚本需要本机已有原始捕获与模型处理记录；只复制本 Markdown 不能复现全部验证。本文没有宣称本轮文件已经推送到 GitHub。
