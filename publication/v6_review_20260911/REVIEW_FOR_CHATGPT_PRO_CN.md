# 请 ChatGPT Pro 复查 DisasterTrace V6 数据选择与研究设计

请对这份材料进行独立研究审查和代码审查，先列出问题，再给调整建议。不要把已有报告的结论当作正确答案；需要检查代码、统计口径和证据是否支持它们。

仓库：`sisuolv/disastertrace-benchmark`；分支：`next-phase-v1`。
本次主题是 **2026-09-11 的 V6 数据选择阶段**；上一发布父提交为 `a8ea30d6fd35e5889f5f846ee9f49c87480cf96d`。
请记录你实际读取的 commit。首页下方的 P5/P6 或旧 CURRENT_PHASE 属于历史阶段，不是本次数据工作的最新状态。

## 一、研究目标和用户要求

目标是建设评测 LLM/VLM 的极端天气 benchmark，尽可能覆盖热带气旋、大风、雷暴风、龙卷风、冰雹、雷电、极端降水、洪水、沿海灾害、热浪、寒潮、冬季天气、干旱、沙尘、浓雾和野火等 16 类方向。

用户要求先实际取样和验证数据来源，再决定最终数据集与任务。允许复用现有 benchmark、官方产品、已有标注和开源读取器；不新增逐题人工复核，不用 LLM judge 决定 Gold。可以继承已有专家或人工标注，但必须披露来源，不能宣称整个标签链没有人工。

没有硬截止日期。当前先做数据，不启动训练、LLM/VLM/API 评测或批量生成 QA。后续资源最多可用 4 张 H100；本次数据验证没有使用 GPU 或模型 API。

拟采用两层结构：Broad Data Bank 保留有价值的静态、时序和多模态资料；Task-ready subsets 按空间阅读、真实演化、同目标修订、受控证据回放、历史 as-of、未来结果配对等具体任务分别准入。

## 二、本轮已经实际做了什么

| 项目 | 实测结果 | 必须保留的限制 |
| --- | --- | --- |
| 来源清单 | 54 个原始候选 + 20 个互补登记项 | 含 benchmark 和派生产品，不是 74 个独立观测源，也不是全部已解码 |
| Storm Events | 2021/2023 两个完整年度文件，136,982 条报告 | EPISODE_ID 不等于独立天气系统，年度资料需保护事件过滤 |
| ExEBench coldwave | 固定 HF commit 的完整包；9 个源案例，559 时间步，8 国/地区 | 其他子包未下载；跨国案例可能共享物理过程；来源与再分发权利仍待查 |
| ExtremeWeatherBench | 329 条案例定义；一个 GHCN-hourly row group，122,880 行、24 站 | 尚未完成这些观测与具体 EWB 事件的配对；footer 的约 2.99 亿行不是已下载量 |
| GLM | 3 个连续 20 秒产品，flash/group/event 数与父子关系已检查 | 尚未建立极端密度基线或完成边界闪电去重 |
| GEOID/CEMS | 3 组完整前后 SAR/label/validity，连接到 EMSR712/AOI10 | 3 个瓦片洪水正像素均为 0；原 split 为 test，仅保留已观察审计身份 |
| TorNet | 从部分归档提取 3 个完整 train NetCDF | 均为 NUL 负例；龙卷正例和 v1.1 标签映射待验证 |
| DroughtED | 1 MiB 压缩前缀解析 26,666 完整行，3,809 非空分数 | 1,330 个分数为小数；train 实际含 2000–2016，与页面 2000–2009 描述冲突；无完整归档 CRC |
| WildfireSpreadTS | 同一火场 3 天；依作者读取器从探测时刻复算活动火像素为 4/0/0 | 无探测不能直接推断无火；需要独立覆盖质量与更多火场 |
| ISD | 北京与沙特两个站年；34 条雾码、276 条浮尘/扬沙码且有可用能见度 | 本批沙尘暴、冻雨、吹雪所检现象码正例为 0 |
| CO-OPS | 3 个站点共 720 对同基准面观测/预测潮 | 潮汐残差不等于单一风暴潮成因 |
| 交接核验 | VERIFY_REPORT 中 658 项断言通过 | 包括大量文件/hash/引用检查；不能称作 658 个独立科学测试或模型样本 |

本轮新正式任务数、新模型调用和新 GPU 作业均为 0。已有 Active Forecast 内核、104 个历史开发 episode 和 Francine 多模态种子属于此前工作，不计作本轮扩容成果。

## 三、建议阅读顺序

1. `plans/v6_0911_dataset_selection/DATA_READINESS_REVIEW_CN.md`：总体选择、验证结果和路线。
2. `SOURCE_FEASIBILITY.md`、`HAZARD_COVERAGE.md`、`RELATED_BENCHMARK_COMPARISON.md`：逐源、逐灾种和已有 benchmark 对照。
3. `DATA_COUNTS.json`、`SOURCE_REGISTRY.json`、`source_access_report.jsonl`：统计口径和五轴状态。
4. `analysis/SELECTION_AUDIT.json`、`analysis/DOWNLOADED_AUDIT.json`：本次和此前抽样的实际解码结果。后者保留早期失败状态，新审计中相应成功重试单列。
5. `audit_selection.py`、`audit_downloaded.py`、`build_reports.py`、`prepare_decisions.py`、`verify_selection.py`：检查算法、人工录入的科学判断和生成报告的一致性。
6. `plans/multihazard_source_validation_20260911/validate_samples.py`、`assemble_samples.py`、`sample_archives.py`、`probe_sources.py`：格式、QC、HTTP Range、归档和部分响应边界。
7. `BENCHMARK_RAW_LINKS.jsonl`、`SPLIT_AND_DEPENDENCY_RISKS.json`、`SOURCE_DEPENDENCIES.json`、`ASSET_REUSE_INDEX.json`：来源连接与泄漏风险。
8. `NEXT_ACQUISITION_MANIFEST.json`、`REUSE_AND_GAPS.md`：下一步可执行清单及现有接口复用。

上述缩写路径均相对 `plans/v6_0911_dataset_selection/`，除非已给出完整仓库相对路径。

如要检查任务接口，阅读 `disastertrace-starter/src/disastertrace/multimodal_v1/types.py` 和 `disastertrace-starter/src/disastertrace/active_forecast/`。已有模块是真实实现，不能重新建议从零搭框架；但 `FactKey.threshold_kt` 等气旋语义尚不能直接泛化为所有灾种。

## 四、请重点回答的审查问题

### 1. 数据选择是否充分、合理且可落实

- 哪些来源真正可以优先适配，哪些仍只是目录、负例、背景层或部分文件？五轴状态有没有互相冒充？
- 16 类覆盖表是否夸大细类：积雪与冻雨、扬沙与沙尘暴、雷达回波与冰雹/下击暴流、热点与天气相关野火、总水位与风暴潮？
- 当前便利抽样应该怎样改为正负、地区、季节和事件分层抽样？每个优先来源的最低证据单元应是什么？
- 哪些来源是同源派生或重复资产？如果要降低成本，最应该删减或合并哪些获取工作？
- 用已有 benchmark 补全球覆盖是否可靠？请给出明确的保留、补证、暂缓或替换建议，不只建议“多下数据”。

### 2. 数量、时间、标签及物理语义是否正确

- 所有计数是否分开 source case、真实事件族、报告、站日、时间步、瓦片、分支和任务？
- ExEBench t2m 场与序列的空间聚合定义是否被实际验证，还是仅日期匹配？
- DroughtED 小数 score 的聚合公式与训练年份冲突怎样处理？数据文件完整性和标签稀疏性还缺哪些核验？
- 读取器对 NaN、nodata、质量标记、缺失哨兵、温度/雨量/流量单位是否正确？地面日界是否被误称 UTC？
- GEOID 的 Gold-derived validity 是否充分隔离？已观察的外部 test 样例能否进入后续开发/隐藏测试？
- 是否把预报潜势当成已观测事件、把 issued_at/retrieved_at/Last-Modified 当成历史 available_at？

### 3. 来源链、去重与切分是否足够

- 物理事件图、资产重复图、来源依赖图是否被正确区分？共享 ERA5 是否错误导致所有事件合并？
- 同一气旋的 NHC/CyPortQA/IBTrACS、同一洪水的 CEMS/多个 benchmark，以及跨国寒潮该如何归并？
- 原始 split、现有保护风暴和关联派生标签有没有遗漏？unknown 的分组如何隔离？
- 公开已有 benchmark 可能进入 LLM 预训练，未来测试应该怎样减少污染并如实报告限制？

### 4. Novelty 是否站得住

请对照 ExEBench、ExtremeWeatherBench、WeatherQA、CyPortQA、CLLMate、洪水/野火时序 benchmark，以及其他相关动态证据或地学工具评测。

拟议核心是“跨灾种、可追溯证据下的 LLM/VLM 状态判断与信息更新”。请判断：哪些已有工作已覆盖，哪些只是应用迁移，哪些确有新测量价值？若创新不足，给出最小可行重定位，以及能够证实或否定该贡献的实验。不得仅以灾种/数据规模增加来宣告 novelty，也不要未经检索写“首次”。

有联网能力时请核验论文和作者仓库，给出链接与检索日期；如果无法检索，明确把新颖性结论标为暂定。

### 5. 后续计划应如何重排

对 NEXT_ACQUISITION_MANIFEST 的 12 项任务逐项判断：应马上做、依赖前置条件、延期或取消。优先修复会影响结论和数据准入的问题，不以新增模型调用掩盖数据缺口。

请给出一周数据阶段和两周试点阶段的顺序及停止条件。资源约束为无需新增逐题人工复核、当前先不调用模型、未来最多 4 张 H100；不要求凑旧的 3,050 episode 配额。

## 五、希望你返回的格式

1. **P0/P1/P2 问题列表**：文件/行号或 JSON Pointer、证据、触发条件、影响、最小修复方案。区分已证实问题、疑点和材料缺失；没有明确缺陷就如实说。
2. **逐来源决策表**：保留/补证/暂缓/替换、支持哪些灾种及任务、最关键的未满足条件。
3. **16 类覆盖修正版**：真实已验证证据、缺失细类和优先补样路线。
4. **Novelty 评估**：已有工作对照、应收缩的主张和推荐核心贡献。
5. **最多 5 项最高优先改动**，以及按依赖排序的一周/两周实施安排。

请不要只复述报告、简单肯定方案或泛泛建议增加数据和模型。不要把完整性断言数量当成实验强度。

## 六、材料与执行边界

本次 GitHub 快照和 ZIP 为研究/代码阅读包，包含代码、报告和结构化审计；不含数百 MB 原始 HTTP 字节、科学数组、权重和运行环境。FILE_MANIFEST/RUN_MANIFEST 中的一些路径保留原工作区的证据引用，路径不存在不等于原环境未做验证，但限制了你在阅读包内独立重放数组结果。

`python3 publication/v6_review_20260911/verify_review_snapshot.py` 可在仓库或解压后的阅读包运行，核验随包文件哈希与选定统计关系，不联网。完整 `audit_selection.py` 和 `verify_selection.py` 需要原始数据，不要把阅读包检查说成完整原始数据复算。

请不要自动启动抓取器、历史 GPU worker、付费 API 或更改受保护 split。本次让你分析并提出可审核的修改建议；实施工作另行执行。
