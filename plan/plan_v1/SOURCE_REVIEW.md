# 整合计划的材料与开源核查

核查日期：2026-09-06。用途：支撑 `INTEGRATED_BENCHMARK_PLAN.md` 的规划决定，不是论文结果或运行验收。第 1–5 节记录首轮核查，第 6 节补充用户提出“无需人工复核”后的新核查；其下载范围和评分结论以对应轮次说明为准。

## 1. 本地材料

阅读对比了工作区四份方案：

- `DISASTERTRACE_CODEX_PLAN.md`
- `DISASTERTRACE_CODEX_PLAN(1).md`
- `DisasterTrace_CODEX_IMPLEMENTATION_PLAN(1).md`
- `DISASTERFRONTIER_CODEX_PLAN.md`

只读检查了 `disastertrace-codex-handoff.zip` 的文件列表及 README、HANDOFF_README、STARTER_AUDIT、pyproject 等材料。包中是 Trace starter，没有 Frontier starter。未解压运行代码；材料中的原测试数量及结果不算本轮验证。

原材料提到的 PDF、Notion 内容以及 Frontier 配套 starter 在本次已发现文件中不存在，未作为本轮直接阅读依据。本次综合分析以实际可读的四份方案为准。

## 2. GitHub 核查与复用决定

审计目录：`references/opensource_audit_2026-09-06/`。

其中 `AUDIT.json` 记录完整 commit、来源 URL、选取文件的 SHA256、Git blob SHA1、已核查内容与未验证边界；`snapshots/` 为所选原始文件，`api/` 为文件树和 tag 响应。共保存 28 个上游小文件，连同索引和记录约 4.32 MB；未下载完整数据集、模型权重，未安装或执行第三方代码。

| 仓库 | 核查 commit 简写 | 实际读取依据 | 建议 |
| --- | --- | --- | --- |
| [CyPortQA](https://github.com/ChenchenMobility/MLLM-Bench-CyPortQA) | `1c38abf339d1` | README、MIT LICENSE、`run_gpt4o.py`、QA template、文件树 | 候选材料、模态编码与 adapter 参考 |
| [Inspect AI](https://github.com/UKGovernmentBEIS/inspect_ai) | `856f41f19deb` | MIT LICENSE、pyproject、`_generate_config.py`、release tag API | 一个优先候选模型适配层 |
| [EarthVerse](https://github.com/CuiZHIQ/Earth-Verse) | `6ee72d4094c2` | LICENSE、README、submission validator、agent runner | 参考输入包、验证与日志组织 |
| [lmms-eval](https://github.com/EvolvingLMMs-Lab/lmms-eval) | `4eb7d01b9d16` | LICENSE、README、0.7 release、tau2 task README | 延后 exporter/adapter，避免两套核心 runner |
| [STATE-Bench](https://github.com/microsoft/STATE-Bench) | `5644b1838d96` | MIT LICENSE、README、schemas、scoring | StateDiff 与确定性状态约束参考 |
| [ExtremeWeatherBench](https://github.com/brightbandtech/ExtremeWeatherBench) | `2f37abd464eb` | MIT LICENSE、README、cases.py、文件树 | 事件组织与后续天气预测轨参考 |
| [STALE](https://github.com/icedreamc/STALE) | `ea7d391103a1` | MIT LICENSE、README、temporal、transitions、premise verifier | 后期显式记忆 baseline |
| [CyPort](https://github.com/ChenchenMobility/Maritime-Data-CyPort) | `5cb1d8778d39` | README、文件树 | 后期影响/结果资料参考 |

关键核查结论：

1. CyPortQA 文件树确认 `dataset/CyPortQA.json` 为 98,747,532 bytes，`Encoded_senario.json` 为 9,409,152 bytes；本轮没有下载、清洗或核验这两份大 JSON。README 的 117k+ QA 为作者描述，不能当作本项目独立事件规模。所读 runner 使用随机打乱和固定模型名，不适合作为正式时序回放内核。
2. Inspect 当前源码有 `ResponseSchema` 与 `GenerateConfig.response_schema`。原方案候选版本 `0.3.263` 的 tag 指向 `7aa7343e4a14fa7be07e5a09c7431df5e88c17ee`，与本轮当前 main 快照分开记录；仍需验证所选发布版及 provider 的实际兼容性。
3. STATE-Bench 的 StateDiff 和确定性评分代码真实存在，但面向合成企业工作流；它不是 StateMemBench，也不是气象数据源。
4. ExtremeWeatherBench 的 README 和 cases.py 面向预报与观测比较，其官方示例使用 forecast、target 和天气误差指标。可以参考事件目录，不能直接当作多模态模型状态修订评测器。

## 3. 许可边界

- CyPortQA、Inspect、STATE-Bench、ExtremeWeatherBench 和 STALE 的所读许可文件为 MIT；复制源码需要保留相应声明，第三方数据另行核查。
- EarthVerse 原创 scripts 与配置为 Apache-2.0；原创题目、答案、rubric、computed Gold、元数据、schema、文档为 CC BY-NC 4.0；第三方证据保留原提供者条款。
- lmms-eval 主 pipeline 为 MIT，`lmms_eval/tasks` 与 `lmms_eval/models` 新增代码为 Apache-2.0；数据集权利不由框架许可证统一覆盖。
- CyPort 未发现独立 LICENSE 且 GitHub API 许可字段为 null，但 README 明确声明数据 CC BY 4.0；应记录这一声明，继续核查逐来源条款，不能写成完全无许可。

上述记录用于选择复用范围；代码可用不等于所有归档地图、截图和业务材料都可用同一许可证重发。

## 4. 官方资料抽查

本轮访问以下页面均返回 HTTP 200，读取了相关正文。此处记录的是网页内容核查摘要，尚未构成带原始文件哈希、时间依据及人工审核的正式 episode 来源包。

| 来源 | 本轮直接观察 | 对计划的影响 |
| --- | --- | --- |
| [NHC cone 定义](https://www.nhc.noaa.gov/aboutcone.shtml) | 官方说明 cone 表示热带气旋中心可能轨迹，并说明圆半径与历史预报误差的关系 | 不将 cone 当完整风雨/风暴潮影响区；构建历史 GIS 时匹配当年产品 |
| [NHC Ian 2022 archive](https://www.nhc.noaa.gov/archive/2022/IAN.shtml) | 可读取连续日期的 advisory 索引与 UTC 标注 | Ian 是可行候选，但索引可访问不等于完整港口 episode 已恢复 |
| [USCG Ida ZULU 公告](https://content.govdelivery.com/accounts/USDHSCG/bulletins/2eed0da) | 页面记录 `08/28/2021 02:59 PM EDT` 分发时间；正文分别列 1400、2200 local time 生效的不同范围限制及例外 | 发布与生效时间、来源时区、河段范围和例外必须分开建模；一份公告不是一个通用港口状态 |

例如该 USCG 页面同时包含 Sunshine Bridge 至 MM 20 BHP、后续更大河段和其他航道的限制。正式入库仍须保存原文、来源时区依据和辖区映射，不能仅凭标题给全部 New Orleans 区域写入同一时间标签。

## 5. 尚未核验

没有运行模型、复现实验、评测真实结果或完成专家标注；也未证明候选资料具备全部版本、精确历史公开时间、跨模态必要性或可再分发性。

部分 GitHub raw 请求停滞后终止，最后获取 Inspect README 与 EWB `events.yaml` 的 API 请求遇到未认证限流；这两份文件未保存，也未作为已读源码依据。ExtremeWeatherBench 的 README 已通过其他成功请求读取并保存，事件数量尚未独立统计。

Tropycal、DisasterBench_Open、Obshazard-bench 仅核查仓库/commit/API 元数据，未审核其源码或许可正文。访问 USCG Homeport 说明页时遇到 DNS 解析失败，本次不据此断言该网站或历史资料的当前可用状态。

Hypothesis、GIS 库属于原方案推荐的工程工具，本轮没有新增版本兼容测试。前序文件中引用的 AFDBench 等论文也未独立复现；整体计划不以它们已有实验效果作为前提。

## 6. 无新增人工复核方案的追加核查

为明确能否继承标签、哪些结果可确定性评分，进一步读取了 CyPortQA 模板/数据前缀、NHC 原文、EarthVerse 原题/Gold/judge、STALE 评分提示，以及 DisasterBench 和 Obshazard 源码。详情与准确 commit/哈希记录在：

- [已有 Gold 核查](references/no_manual_review_2026-09-06/existing_gold/REVIEW.md)
- [灾害规划与遥感 benchmark 核查](references/no_manual_review_2026-09-06/weather_qa_sources/REVIEW.md)

主要结论：

| 资源 | 追加确认 | 对 v0.3 的影响 |
| --- | --- | --- |
| CyPortQA | 实际数据前64 KiB含 answer；原生文本和表格题型存在；前缀案例有登陆地点/受影响范围混淆、问句与选项范围冲突 | 继承标签对照与可核验派生题分开；不直接承诺全部文本题都能进入新主轨 |
| NHC/CyPortQA Ida文本 | Advisory 10原文含发布时间、中心坐标、105mph等明确字段 | 可作为自动解析候选，不证明完整港口行动答案 |
| EarthVerse | judge.py 明确无确定性exact-match，正确性、容差与语义等价均交给LLM judge；示例computed_gt提供数值和来源路径 | 原官方分数不能称确定性；派生数值子集需取得原证据并自行重算，尚未完成 |
| STATE-Bench | state requirements可确定性比较missing/unexpected；其他task requirements/UX含LLM judge | 只借鉴状态判分模块，不称整个benchmark无模型裁判 |
| STALE | 三类状态探测有生成与judge提示；原评分会将部分“未知”判失败 | 借鉴诊断维度，不能照搬到应合理缺证的分支 |
| DisasterBench_Open | 完整benchmark.jsonl实际解析233条，具有task_desc/structured_plan；工具定义26项，MIT文件存在 | 可做无需新增标注的灾害工具规划对照；广泛灾害不全部等于极端天气 |
| Obshazard-bench | GitHub源码依赖卫星图像并使用启发式答案比较；数据在HF，本次访问失败 | 不进入文本主轨；没有宣称取得实际标签或核实数据许可 |

CyPortQA 的数据前缀仅供只读检查，没有落盘或取得完整98.7MB QA文件；观察到的具体反例只代表该前缀和对应模板。其场景JSON前缀另一次读取超时，未算核查成功。

本轮新增保存15个小文件：已有Gold核查6个源文件，另两仓库核查9个快照；其中包含DisasterBench完整的小型JSONL文件。每项有来源URL和SHA256；没有执行上游代码、调用模型或新增逐题人工标注。

EarthVerse示例要求按指定资料和窗口计算峰值、三日均值与热小时湿度。它的provenance提到compute_gt.py，但在已保存GitHub树中未找到该脚本，事件证据尚未下载，不能称其数值已经独立复算。

DisasterBench的原评测比较参考计划、工具、参数与依赖，并对步骤顺序敏感。分数表示与该参考协议的匹配，不证明工具实际执行成功，也不能覆盖全部等价计划。

以上依据已用于重写整合方案 v0.3：取消新增逐样本复核，改用来源分级、自动准入、明确拒收歧义、程序化分支Gold和来源分表。v0.2保留在 references/plan_history/，其中人工审核要求已不再是当前默认流程。
