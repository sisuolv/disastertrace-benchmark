# DisasterTrace：真实下载与历史任务链可行性报告

日期：2026-09-12。最终数据构建：`derived_04/`。范围：导师讨论稿中优先推荐的任务族；所有记录是开发可行性样本。

**结论：温度、美国机场能见度、河流流量三类数据链已经用真实文件跑通；严格降水结算和英国 TAF 配对尚未跑通。现在有依据继续开发 benchmark，但尚不能宣布所有灾种或论文 novelty 已验证。**

本轮实际向公开数据服务发出 72 个逻辑请求，保存响应正文 25,961,766 字节（24.76 MiB，包含失败与不完整响应），并完成原生解码、同对象时间配对及程序基线计算。没有调用模型 API 或提交 GPU 作业。目标时间均已过去，无需等待未来天气。

建议先向导师提供本报告和[整体研究提案](../advisor_review_20260912/PROPOSAL_FOR_ADVISOR_CN.md)，再按需查看[候选数据与 16 灾种明细](../advisor_review_20260912/CANDIDATE_SELECTION_CN.md)。本报告是该提案的实测补充，不改写先前的冻结证据。

## 1. 具体下载了什么，是否能组成任务

| 任务 / 灾种 | 真实预报与参考数据 | 本轮实际内容 | 结论与限制 |
| --- | --- | --- | --- |
| 高温、低温 H10/H11 | NOAA GFS 2m 温度 + NCEI Global Hourly/ISD | Phoenix、Denver 的 9 个完整 GRIB2 字段；分别 122、177 条站点记录；3 个目标、每目标 3 个预报版本 | 2 个目标通过 QC 并精确配对；另 1 个温度质量码为 2，保持未结算。可以进入历史数值任务开发 |
| 机场低能见度 H15，美国 | NWS 原始 TAF，经 IEM 归档；同机场 METAR | KSFO/KDEN 共 6 份原始 TAF，分别 86/97 条归档站报；固定 24 个例行报告目标、每目标 3 个预报版本 | 全部 24 个目标有原始报告；其中 1 个严格低于 1 km，天气码为降雪 SN。可以进入能见度报告预测开发，不能一律称为雾 |
| 河流水文 H08 的连续流量子任务 | NOAA HEFS QINE/CFS + USGS 00060 | 3 站、2 轮预报，29/35/45 个集合成员；每站 229 条观测，共 687 条；6 个精确目标 | 连续流量链路通过。观测为 provisional，缺少适用的官方流量阈值，尚不是已验证的洪水越阈预警任务 |
| 强降水 H07 | GFS 六小时 APCP + New Orleans 的 NCEI 记录 | 3 个完整六小时累计 GRIB2 字段；254 条站点记录 | 下载与累计区间解码通过；固定 00Z 参考的 condition=3，严格目标拒收。23:53 的六小时量只能作近时诊断 |
| 低能见度 H15，英国补充 | EGKK METAR + GFS surface visibility；查询 EGLL/EGKK TAF | 144 条站报，19 条原文能见度低于 1 km；3 个 GFS 字段；两份 TAF CSV 仅表头 | 确有低能见度样本，但本接口在所选窗口没有 TAF 记录。GFS 12Z 与站报 11:50 相差 10 分钟，只作补充诊断 |

水文 6 份预报中，本轮新取得 5 份完整文件；SCOC1 的 2026-09-10 下载超时，采用上一轮已经保存、重新校验的完整文件。复用文件的路径、原始回执和哈希均在 [SOURCE_BINDINGS.json](derived_04/SOURCE_BINDINGS.json) 中，不算本轮新下载成功。

本轮绑定 38 个查询资产：27 个解码预报产品（15 GFS、6 HEFS、6 TAF）、9 个站点参考文件及 2 个空 TAF 查询结果。38 是资产数，既不是独立数据源数，也不是天气过程数。

此前全候选审查的 97 个来源/产品入口、75 个已解码样本仍见[全候选登记](../all_candidate_data_validation_20260912/README_CN.md)。本轮没有重新下载所有 97 项；它进一步检验优先组合能否从“有样本”走到“有匹配任务”。GEE、NASA/Copernicus 等其他来源的既有验证状态不由本轮推翻，也不由本轮自动升级为正式任务。

## 2. 可直接检查的真实样例

### 2.1 高温和低温：同一目标的三个 GFS 预报版本

下表所有预报均为对应目标有效时刻的 2m 温度，由原始 GRIB 的 K 转成摄氏度；参考值来自精确时刻的 NCEI 记录。

| 对象及目标时刻 UTC | 18h 预报 | 12h 预报 | 6h 预报 | 站点参考 | 准入 |
| --- | ---: | ---: | ---: | ---: | --- |
| Phoenix，2023-07-18 18:00 | 38.570 °C | 40.025 °C | 39.409 °C | 41.7 °C，QC=1 | 可结算 |
| Denver，2024-01-13 18:00 | -18.431 °C | -18.765 °C | -19.444 °C | -22.8 °C，QC=1 | 可结算 |
| Phoenix 原定目标，2023-07-19 00:00 | 45.166 °C | 45.258 °C | 45.342 °C | 原字段 `+0478,2` | 质量码 2，保留未结算 |

Phoenix 白天目标是在发现原定目标质量问题后明确追加的同一高温过程样本。原目标没有被删除或替换，新增目标也不增加独立高温过程数。高温/低温事件的正式统计阈值和抽样规则仍须另外冻结。

取最近 GFS 网格点的规则已保留，Phoenix 距站约 8.04 km，Denver 约 12.13 km。因此这是明确的格点预报到站点观测比较，二者空间支持并不完全相同。

可检查文件：

- [Phoenix 站点 CSV](captures_03/ncei-phx-days.body)；[下载回执](captures_03/ncei-phx-days.json)。
- [Phoenix 的 GFS 完整字段](captures_08/gfs-phx-daytime-t2m-early.body)；[HTTP Range、URL 和哈希](captures_08/gfs-phx-daytime-t2m-early.json)。
- [Denver 站点 CSV](captures_04/ncei-days-den-cold.body)；[解码后的全部产品](derived_04/DECODED_PRODUCTS.json)。

这些是 2023/2024 年的历史 ISD/Global Hourly 资产，不意味着当前观测主线应从 GHCNh 迁回旧产品。NCEI 整年下载超时后，限定日期窗口的官方 API 成功取得完整小样本；重复 CSV 列名也经过一致性检查才合并。

### 2.2 水文：专业预报确实有版本，后来流量也取得了

| HEFS 站点 | USGS 站点 | 集合成员数 | 2026-09-12 00Z / 06Z 观测，ft³/s |
| --- | --- | ---: | --- |
| NRWI4 | 05486000 | 29 | 2,830 / 2,790 |
| CRHA2 | 15493400 | 35 | 4,350 / 4,300 |
| SCOC1 | 11477000 | 45 | 110 / 105 |

对同一 NRWI4 00Z 目标，9 月 10 日版 HEFS 集合均值为 1,167.224 ft³/s，9 月 11 日版为 2,874.216 ft³/s，后来 USGS 记录为 2,830 ft³/s。这证明了真实版本更新与固定未来目标能够配对。

不能据此证明 LLM 取证有增益：更新来自专业预报产品，而且共同基线也应取得合法的新版本。新产品的创建时刻与 12Z 起报时间不同；NRWI4 的样本创建于 19:30，CRHA2 为 21:00。本轮采用 22Z 受控检查点，没有把 12Z 起报误当成当时已经公开可读。

SCOC1 两版产品的起始支持分别为 18Z 与 12Z，只比较共同存在的精确目标。当前样本没有证明是洪峰，也没有给出可兼容的官方 CFS 洪水阈值。水位、流量、潮位不能互换。

证据：[HEFS NRWI4 原文](captures_02/hefs-nrwi4-20260911.body)、[USGS 观测原文](captures_02/usgs-flow-nrwi4.body)、[6 个目标及参考状态](derived_04/private/outcomes.jsonl)。

### 2.3 美国机场：真实低能见度结果与 TAF 条件段

KDEN 2024-01-13 08:53 UTC 的实际原文包含：

```text
KDEN 130853Z 05009KT 1/2SM R35L/6000VP6000FT SN VV010 M19/M23 A2971 ...
```

`1/2SM` = 804.672 m；天气码为 `SN`。目标严格低于本轮明示的 1,000 m 研究阈值，是降雪相关低能见度样本。

同机场 05:37Z 发行的真实 TAF 已包含：

```text
TEMPO 1308/1311 1/2SM SN FZFG
```

这是 08Z—11Z 的暂时性条件段。只抽取 prevailing 主导段会遗漏这条风险，不能把这种遗漏解释成“完整专业预报没有预见”或“必须获得额外独立信息”。这正是构建强基线前需要解决的语义问题。

本轮保留原始 INITIAL/FM/TEMPO 和修订；数值诊断仅使用明确标注的 `prevailing_only` 投影。`TEMPO` 不转换成臆定的单时刻概率，`P6SM` 保留大于 6 英里的下界，不当成 6.01 英里的精确值。其他尚未覆盖的 TAF 操作符应先扩展解析与测试，不能直接扩大本解析器的通用能力声明。

证据：[TAF 05:37Z 原文](captures_04/taf-native-den-2.body)、[METAR 原始 CSV](captures_03/metar-serial-den.body)、[6 个 TAF 的选择记录](TAF_SELECTION_01.json)。

### 2.4 英国补充：原生数据与派生列会给出不同阈值标签

EGKK 的 144 条站报中：

- 按 METAR 原生米制字段，严格低于 1 km：**19 条**。
- 恰好 1,000 m：**11 条**。
- 若把 IEM 四舍五入后的英里列再换算成米，会得到“30 条低于 1 km”的错误统计。

例如原文 `1000` 被记录为 `0.62` 英里，反算为 997.79328 m，就跨过了阈值。早先 [CONTRACT_ADDENDUM_CN.md](CONTRACT_ADDENDUM_CN.md) 的“30 条”来自初步派生列统计；本报告明确更正为 19 条，原始记录保留。最终 `derived_04/SUPPLEMENTARY.json` 从原生报文计算，使用正确的 19 条；新增回归测试覆盖该边界。

另一个真实报告是：

```text
EGKK 271150Z VRB02KT 0800 R08R/P1500N FG OVC001 06/06 Q1033
```

此时确有 800 m、天气码 `FG` 的雾报告。同日 12Z 的三个 GFS 能见度预报约 24.135 km，但站点与格点相距约 12.07 km、有效时刻相差 10 分钟。该差异只在[补充诊断](derived_04/SUPPLEMENTARY.json)中记录，不进入严格目标分数，也不推断一般性的模型能力结论。

源文件：[EGKK CSV](captures_03/metar-serial-egkk.body)。全部 11 条舍入差异在 [FEASIBILITY_METRICS.json](FEASIBILITY_METRICS.json) 的 `uk_native_rounding_diagnostic` 中。

### 2.5 降水：有数据，但不能放宽规则来凑成成功

New Orleans 的固定六小时窗口为 2024-09-11 18Z 至 2024-09-12 00Z。三个 GFS 对应累计值为 41.6875、43.1875、67.0625 mm，均检查了真实累计起止，不混入从起报累计的同名 APCP 字段。

精确 00Z 的 NCEI 字段是 `AA1="06,0610,3,1"`。官方 ISD 文档将 condition=3 定义为累计期开始；不能把这里的 61.0 mm 自动当成结束于 00Z 的合格六小时结果。本轮固定目标因此保留 `unresolved_accumulation_condition`。

23:53 的 `AA2="06,0607,9,1"` 给出 60.7 mm；同条 METAR 的 `60239` 即 2.39 英寸，换算 60.706 mm，数值和单位吻合。但窗口结束相差 7 分钟，不能替代原目标。condition=9 表示条件未提供，仍需要独立检查数值与 QC。

证据：[NCEI 降水样本](captures_04/ncei-days-msy-rain.body)、[官方 ISD 格式 PDF](captures_03/isd-format-doc.body)、[文档提取文本](ISD_FORMAT_TEXT.txt)。

## 3. 实际构建规模与基线结果

最终输出是 **34 个固定目标、96 个检查点、192 条基线机会**：

| 参考状态 | 目标数 | 含义 |
| --- | ---: | --- |
| `quality_controlled_observation` | 2 | 通过本轮 NCEI 温度 QC |
| `provisional_observation` | 6 | USGS 暂定流量观测，后续仍可能修订 |
| `archived_report` | 24 | 原始 METAR 报告，并非额外的最终传感器质量认证 |
| `unresolved_quality` | 1 | 温度质量不通过 |
| `unresolved_accumulation_condition` | 1 | 降水累计条件不通过 |

因此 32 个目标可以按本轮已声明的参考规则结算，2 个未结算；不是 32 条同等级最终物理真值。192 条基线记录中，180 条有定义的误差或分类结果，12 条保留为空；空值不算预测正确或无灾害。

为了避免重复检查点放大样本量，下面只展示每个目标最后一个检查点的描述性结果：

| 任务 | 最后检查点的程序基线 | 结果 | 如何解读 |
| --- | --- | --- | --- |
| 温度 | 最新 GFS / 最近合格观测持久性 | 2 个可结算目标，MAE 2.824 / 1.100 °C | 仅 2 个目标，持久性是必须保留的对照，不能据此给模型排名 |
| 流量 | 最新 HEFS 集合均值 / 持久性 | 6 个目标，MAE 26.205 / 15.833 ft³/s | 三站量级不同且短时间高度相关；该平均数仅核验计算，不作为跨流域正式指标 |
| 机场能见度 | TAF prevailing 投影 / 持久性 | 两者均 23/24 分类正确，但都漏掉唯一低于 1 km 的目标 | 95.8% 准确率不能代表好的预警；完整 TAF 的 TEMPO 已有相关风险信息 |
| 降水 | GFS / 持久性 | 固定目标均无正式误差 | 未结算没有被丢弃 |

这些基线没有 LLM，也没有主动获取策略。完整检查点分数在 [baselines.jsonl](derived_04/baselines.jsonl)，汇总在 [FEASIBILITY_METRICS.json](FEASIBILITY_METRICS.json)。Denver 的低温与低能见度属于同一父天气过程；连续时点和不同灾种标签不能增加独立事件数。

## 4. 对计划与 novelty 的实际判断

| 假设 | 本轮已证明的数据条件 | 尚须证明的核心部分 |
| --- | --- | --- |
| N1：主动取证在共同专业预报之外有增量 | 多个自然预报版本、截止前站点证据、固定后来目标能够连接 | 有限预算下，额外证据是否改变预测；固定预测器、专业预报共同更新、全读与廉价策略的公平比较 |
| N2：新内容、来源依赖与表示变化的作用可以区分 | 已保留原始版本和原生表示，实际发现精度转换跨阈值、TAF 条件段投影丢信息 | 完整来源谱系、同事实的等内容/等长度对照、真正新增且相关的输入；不能把舍入损失当成无损表示实验 |
| N3：截止和过程干预能解释部分失败 | 受控时钟、预报/观测合法性、原始结果与可复算评分已具备 | 真正查询/完成/提交轨迹、预算与延迟实验、运行时隔离、感知/状态/决定的限定干预及多事件验证 |

**本轮证明“部分核心组合值得继续做”，没有证明“论文的正向 novelty 已经成立”。** 同机构的预报与观测也不保证统计独立；不同查询 URL 或资产 ID 更不等于独立证据。新增观测可能已进入数值同化系统，需按观测时刻和产品谱系明确描述。

对首轮选择的建议据实调整为：

1. **温度与美国 TAF/METAR 优先进入下一阶段开发。** 先补独立过程、正常/近阈值窗口与合格附加资料，再决定正式主实验规模；两个示例过程或唯一低能见度正例不够形成确认集。
2. **HEFS/USGS 保留为有条件的水文主线。** 多轮产品存在这一点已通过；长时段历史覆盖、适用流量阈值、洪峰过程与上游/降雨附加资料仍需补齐。当前可做连续流量，不直接标成洪水预警完成。
3. **降水、英国 TAF 保留为待补齐项。** 降水优先找与原目标精确匹配且成熟的累计参考；若研究需要容许近时窗口，必须另立合同和版本，不能修改本轮失败结果。英国需先找到真实历史 TAF 覆盖或另立纯 GFS 任务合同。
4. **保留整体 16 灾种路线。** 本轮只处理高温、低温、低能见度、水文和降水候选，不代表剩余灾种完成。NHC 继续承担既有工程/版本对照；原生雷达/卫星的多模态增量属于另一个待匹配的实验阶段。

下一阶段的关键产物应是“小规模、来源与时间受控、含强基线的机制实验数据集”，而非继续增加互不配对的下载文件。先固定共同最新专业预报，再比较额外取证；获取专业预报更新本身应单独设实验。既有 LLM 最小闭环没有主动收益的结果仍保留。

## 5. 时间、参考与实验隔离的边界

- GFS 采用起报后 5 小时可读、TAF 起报后 15 分钟可读、此前观测名义时刻后 5 分钟可读。这些是受控历史回放设置，不是测得的历史业务延迟。
- 水文使用 9 月 10/11 日 22Z 两个共同检查点，并检查已创建产品；创建时间仍不是历史首次公开时间的证明。
- 本系统 2026-09-12 的真实下载回执只能证明本次取得时刻。历史归档观测也可能带有后来的质量修订，不能伪装成当时原始到达版本。
- `public/checkpoints.jsonl` 与 `private/outcomes.jsonl` 分开，独立验证了行内时间和结果字段隔离；尚未在本轮为新任务验证模型进程/文件系统隔离。不得让模型直接读取包含未来记录的原始全年或多日文件。
- 本轮没有概率模型校准、真实行动损失或安全决策评估；1 km 是明示研究阈值，不是对所有机场、运行场景通用的业务行动规则。
- 当前产物是本地研究验证。获取成功不自动证明全部上游资料可再分发；正式发布时仍逐产品记录条款、引用要求和可公开资产范围。

## 6. 请求成功、失败与本地验证

完整统计与失败条目见 [FEASIBILITY_METRICS.json](FEASIBILITY_METRICS.json)。实际请求起止为 2026-09-12 10:00:02—10:19:41 UTC。

| 传输结果 | 逻辑请求数 |
| --- | ---: |
| HTTP 200 且 curl 正常结束 | 47 |
| HTTP 206 且 curl 正常结束 | 15 |
| HTTP 404 | 4 |
| HTTP 429 | 2 |
| 超时、不完整或没有正文 | 4 |

62 个完整 HTTP 响应共 14,742,633 字节；它们包含索引、格式文档和空 CSV，因此不能都计为科学数据集成功。其余正文与失败也保存，合计 25,961,766 字节。

初次 IEM 同主机并发得到限流；后续使用每主机一个请求、IEM 请求间隔 3 秒、总并发最多 4 的 CPU 下载器。3 个猜测 TAF API 和 1 个文档地址返回 404 后，实际找到官方表单使用的 `cgi-bin/request/taf.py` 及 `api/1/nwstext/` 原文接口。2 个 NCEI 整年文件和 1 个 HEFS 文件超时，未作为完整来源准入；另一个 GitHub 表单源码请求无正文。

一个 APCP 请求规格因同时匹配六小时与起报总量、产生重复 ID，在联网派发前被拒绝，留在 [REQUEST_SPEC_05_REJECTION.json](REQUEST_SPEC_05_REJECTION.json)；不计入 72 个已派发逻辑请求。

验证结果：

- [独立复算](validation_03/INDEPENDENT_CHECK.json)通过：38 个来源文件及回执绑定、15 个 GRIB 原始数组重新解码、34 个参考目标、96 个检查点、192 条评分。验证器没有导入数据构建器；这仍不是人工气象审查或对全部源语义的第二套通用解析。
- [9 个语义回归测试](validation_03/contracts.log)通过，包括温度 QC、METAR/TAF 条件段、删失与分数单位、月份跨界、此前观测可读时间及 1,000 m 舍入边界。
- 5 个当前 Python 文件的 Ruff 检查与格式检查通过。`derived_03/` 与最终 `derived_04/` 结果逐文件字节一致；末轮清理没有改变数据和分数。
- 全部 72 个响应正文的长度和 SHA-256 重新检查通过。汇总器首次未处理可变风向字段而失败，补齐后通过，失败日志仍在；构建器的原生能见度结果未受影响。
- 原始失败、前期派发规格、构建快照及 lint 日志保留在本目录。最终构建/独立验证命令见 [COMMANDS.json](validation_03/COMMANDS.json)，汇总修复后的命令见 [SUMMARY_COMMANDS.json](validation_03/SUMMARY_COMMANDS.json)。

## 7. 离线复现与文件入口

工作目录为 `extreme_weather_benchmark/development/disastertrace-next`。以下重建只读已保存原始文件，不下载新资料；输出目录和复算回执必须使用尚不存在的名称。

```bash
export PYTHONPATH=/mnt/afs/260010168/.venvs/disastertrace-multihazard-libs-20260911
python plans/task_chain_feasibility_20260912/test_contracts.py
python plans/task_chain_feasibility_20260912/build_chains.py \
  --output plans/task_chain_feasibility_20260912/reproduce_01
python plans/task_chain_feasibility_20260912/verify_chains.py \
  --data plans/task_chain_feasibility_20260912/reproduce_01 \
  --output plans/task_chain_feasibility_20260912/REPRODUCE_CHECK_01.json
python plans/task_chain_feasibility_20260912/summarize_results.py \
  --data plans/task_chain_feasibility_20260912/reproduce_01 \
  --output plans/task_chain_feasibility_20260912/REPRODUCE_METRICS_01.json
```

本机科学环境使用 NumPy 2.2.6、ecCodes 2.48.2；PDF 初次提取另用了 pypdf 6.1.3，本地构建不再依赖 pypdf。需要一并携带 `SOURCE_BINDINGS.json` 引用的旧 SCOC1 文件/回执；下载器还复用上一轮 `fetch_samples.py`。发行包不能只拷贝本目录而遗漏这些相对依赖。

| 文件 | 作用 |
| --- | --- |
| [PLAN_CN.md](PLAN_CN.md)、[CONTRACT_ADDENDUM_CN.md](CONTRACT_ADDENDUM_CN.md) | 开始时计划和处理合同；初步英国数量已在本报告更正 |
| `captures_01/`—`captures_08/` | 72 个真实请求的正文、回执、批次清单与失败 |
| [build_chains.py](build_chains.py) | 原生产品解码、任务与基线生成 |
| [verify_chains.py](verify_chains.py) | 独立检查文件、数值、时间与分数 |
| [summarize_results.py](summarize_results.py) | 响应正文检查、分数汇总与英国舍入诊断 |
| [public/checkpoints.jsonl](derived_04/public/checkpoints.jsonl) | 96 个受控检查点，供后续适配器设计 |
| [private/outcomes.jsonl](derived_04/private/outcomes.jsonl) | 34 个目标的私有结果与拒收理由 |
| [REPORT.json](derived_04/REPORT.json) | 最终构建计数、参考身份及限制 |
| [FEASIBILITY_METRICS.json](FEASIBILITY_METRICS.json) | 请求统计、数值基线与边界诊断 |

给导师的判断可以表述为：已经用真实历史数据证明三类任务的基本链路可构建，并发现若干会改变标签或基线结论的源语义问题。后续值得投入的是独立过程扩展、额外信息价值与限定机制实验；完整 16 灾种发布和正向科学贡献尚待验证。
