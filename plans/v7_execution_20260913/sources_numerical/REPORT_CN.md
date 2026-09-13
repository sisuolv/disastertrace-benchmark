# W1C 数值数据源实测报告

本轮已经下载并解码 EUPPBench 站点温度集合预报、对应站点观测，以及 SEEPS4ALL 的 IFS 日降水预报和 ECA&D 日观测。不是仅访问目录或 README。以下结果支持离线数值接口开发；本轮新增正式 monitoring 准入数仍为 0。

## 1. 已经跑通的内容

| 来源 | 实际下载和验证 | 本轮固定小样例 | 当前可用范围 |
|---|---|---|---|
| EUPPBench Germany station ensemble forecasts | Berus，DWD 460；51 成员 × 730 初始化日 × 21 预报时效的单站 t2m 压缩块；对应 730 × 21 站点观测块 | 前 3 个初始化日、全部 21 时效，共 63 条；其中 60 条时效严格大于 0 | 离线站点温度点目标、原始集合概率／分布接口 |
| DWD CDC hourly temperature | 独立下载 Berus 小型历史 ZIP，并读取实际观测和该站参数元数据 | 63/63 EUPP 观测与 DWD TT_TU + 273.15 在 1e-6 K 内一致；63 条 QN_9 均为 3 | 交叉核对单位、站号、UTC 时间和数值；保留原始质量代码 |
| SEEPS4ALL | 一块 IFS 预报、2024 年所在观测块、站点和时间坐标，以及月气候系数块 | 前 3 站 × 前 3 初始化日 × 前 2 日时效，共 18 条；16 条有双方数值、2 条观测缺失 | 名义日窗离线数值配对；不能直接按已验证的站点物理 24h 窗结算 |

全部选择按源数据数组位置固定，未根据极端事件、模型胜负或观测完整性换站换日。EUPP 样例为 2017-01-01、02、03 00 UTC 起报，时效 0、6、…、120 小时；SEEPS 为 2024-06-01、02、03 00 UTC 起报，时效 1、2 日。样例用于数据与接口验证，不代表极端事件覆盖充分或评测结果有效。

EUPP 的预报来源是 **station ensemble forecasts**；本轮没有下载 reforecasts，也没有用 ERA5 栅格分析替代站点观测。EUPP forecast 的 `GRIB_stepType=instant`，不是日最高、最低温，也不是整小时极值。原始 t2m forecast 元数据明确单位 K；observation 字段却没有 units。本轮用 DWD 历史 ZIP 中适用日期的参数元数据确认 TT_TU 为摄氏度、时间为 UTC，并逐条核对转换结果，而没有仅凭数值量级猜单位。

## 2. 时间、质量与授权边界

### EUPPBench

- `time + step = valid_time`、预报与观测的站号／坐标／time／step 均已实际验证。
- 初始化时刻不是历史公开可获取时刻。样例保留 `historical_forecast_available_at=null` 和 `historical_observation_available_at=null`，不把当前对象存储的 Last-Modified 当作 2017 年发布记录。
- 下载的 EUPP 观测表不保留逐项质量标识；辅助 DWD 快照保留 QN_9，本轮没有把这个代码擅自翻译成“物理真值无误差”。
- forecast 数据许可证明确为 CC BY 4.0；所固定的 EUPP DATA_LICENSE 对站点观测仅列出提供机构，没有逐国完整再分发条款。研究样例下载已跑通，后续发布前应绑定 DWD/EUPP 对应的再分发条款及引用，不把软件许可证等同于全部站点数据许可证。
- 当前可以推进温度瞬时点目标的 R 轨接口开发；温度点的合法数学类型仍须由新接口支持，不能把它塞进要求 `start < end` 的旧区间并宣称语义相同。

### SEEPS4ALL

- 源脚本把 ECA&D RR 除以 10 转换到毫米；forecast 脚本将累计降水相邻时效差分并乘 1000。下载的 forecast/observation Zarr 本身未写 units，因此转换依据固定在所捕获的源版本，不能脱离来源默认 mm。
- 源脚本将 ECA&D 原始 DATE 加 24h 作为结束日期。本轮验证的是该名义日期配对，**尚未获得每个站的实际日累计起止时刻**；不同站的本地观测日约定不能自动当作统一 UTC 00–24。
- source builder 先屏蔽 `Q_RR > 0`，再屏蔽纬度相关异常值、重复出现且大于 120 mm 的值，并剔除超过 99% 为零的站和重复位置站。这些处理可能影响最极端降水尾部；发布的数组未保留每个 NaN 的原始原因。
- 下载 forecast 块中有 515 个负数，最小为 -0.00762939453125 mm。本轮保留原值，不静默截断为零；正式合同需冻结“保留原值并标记”或有明确依据的容差处理。
- 下载 observation 块中有 145,183 个 NaN；不能按模型分别删题，也不能把这批缺失假定为随机缺失。18 个样例保留全部机会与共同缺失标识。
- 根元数据记录 CC-BY-NC，源码 LICENSE 指向 CC BY-NC 4.0；ECA&D 数据政策 PDF 也已下载留存。该限制应与 forecast/obs 的来源一同进入后续发布清单。
- 1991–2020 月气候系数已实际解码，前三站 6 月的轻／重雨阈值可读取；气候统计不等同于可用的实时天气证据，也不自动提供 C1 共享取证实例。

## 3. 本轮发现并修复的传输问题

两次大型 Zarr GET 返回 HTTP 200，却在读取完整 Content-Length 前结束。原始 observation 收到 6,045,696 / 7,930,687 字节，coefficients 收到 6,373,376 / 9,587,463 字节。Blosc 解码拒绝短包，没有把它当成有效数据。

已给 fetcher 加入严格长度检查；保留最初 REQUESTS 记录、partial 文件和 `INCOMPLETE_TRANSFER_AUDIT.json`，然后仅通过 `Range + If-Match` 下载缺失尾部。恢复后两个完整对象的 MD5 均与原始单段 ETag 一致；详情在 `RECOVERED_TRANSFERS.json`。第一次记录中的 HTTP 200 仅说明响应状态，必须结合完整性审计使用，不能单独累计为成功科学样例。

另外保留两次 raw.githubusercontent.com 读取超时和一次 DWD 文档旧路径 404；GitHub blob API 与 DWD 实际目录路径已成功替代。没有安装或修改冻结环境。

## 4. 对 v7 计划的具体调整

1. **温度可以先接数值接口。** 63 条同目标集合预报／站点值足以开发 `instant` 数值输入和保留观测侧标签的 provider；下一步选独立连续时段、固定阈值与训练／确认拆分。无需等待水文所有条件齐备。
2. **SEEPS 先保持 offline-nominal 资格。** 补齐站点实际日窗、原始 QC 来源与极端尾部过滤影响之前，不把当前配对升级为 future_physical 的精确 24h 极端降水任务。
3. **历史发布时刻仍为共同缺口。** 两个离线 benchmark 提供现成对齐数据，但没有因此证明在线能力。要支持 v7 的版本、截止与合法获取，需要额外时刻证据或清楚标注的回放假设。
4. **C1/C2 准入单列。** 当前未证明自然共享证据、联合预算可达性、证据支持判定、取证对未来 F 的增益或跨独立过程结论。不要用增加下载数据集数替代这些出口条件。
5. **保留强数值基线。** EUPP 的 51 成员集合应保留为共同专业基线输入，后续校准只在冻结的训练时段拟合；SEEPS 的确定性 IFS 不能未经映射冒充校准概率。

## 5. 复现与交付

```bash
cd /mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next
PYTHONPATH=/mnt/afs/260010168/.venvs/disastertrace-multihazard-libs-20260911 \
  python plans/v7_execution_20260913/sources_numerical/decode_samples.py
```

该命令只读已下载文件，不发网络请求、不调用模型。预报输入在 `paired_records.json` 和 `paired_rainfall_records.json` 的 `model_visible` 下，观测标签在 `evaluator_only` 下；下游必须保持这层隔离。`DECODE_VALIDATION.json` 记录实际数组规模和检查结果，`QUALIFICATION.json` 记录准入边界，`FILES.sha256.json` 绑定本目录产物。

本轮没有训练、API 调用、GPU 推理，也没有生成“LLM 提升已成立”的结论。
