# DisasterTrace v16 — W0 真实数据获取计划（H15 TAF/METAR/LAMP + NHC 数据资格 + 前向实时采集）

## 0. 给零上下文执行者的说明

本文档是**自包含**的：你不需要阅读本仓库其它计划文件、不需要重新推导任何前提，即可按本文档直接执行下载。本文档只覆盖**下载**（DL-0 ~ DL-6），不覆盖后续的 values-bank 拟合、评分器改造或模型调用（那些是另一批任务）。

**本任务是纯数据获取任务**：不写/改任何 `disastertrace-starter` 下的 Python 源码（解析器已经存在，见 §1.4），不做任何模型 API 调用（NHC 分支尤其禁止，见 D02），不打开新的确认集 holdout（见 D09）。

如果你在执行中发现本文档里标注为"未确认"的端点实际不可用、或格式与预期不符，**如实记录failure，不要静默降级或编造数据**——这是 D10 的强制要求。

---

## 0.1 D12 前提纠正（为什么是"全新下载"而不是"从执行机同步"）

早前 v14 阶段的 D12 决定（见 `plan/plan_v14_0919/RESEARCH_DECISIONS_v14_20260919.yaml`）假设存在一台独立于本节点的"执行机"，真实的年度 TAF/METAR 原始数据和 values bank 保存在那台机器上，D12 当时的 selection 是"原执行机只读运行真实数据；当前节点保留源码、合成数据及少量有哈希标注的开发样例"。

**本次会话（2026-09-20）确认这个前提是错的**：本节点（`/mnt/afs/260010168/extreme_weather_benchmark/`）**就是**执行机，不存在另一台机器可以同步。全仓库范围审计（已完成，无需重复）确认：

- `publication/v13_completed_20260917_01/snapshot/`（75MB，只有文档和代码）、legacy `disastertrace-starter/artifacts/`（11GB，无原始气象数据）、`publication/dataset_export_20260912_01/`（只有文档）——三处均无 H15 年度原始 TAF/METAR 数据或"values bank"。
- 仓库内、v13 快照内均无 IEM/LAMP 下载脚本（对 `mesonet`/`agron`/`iastate`/`aviationweather`/`cgi-bin`/`asos`/`nwstext` 的 grep 零命中）。

这是**执行地点前提的纠正，不是科学决定的变更**：D12 中"不要盲目搬运 11GB 遗留数据""不要同步/打开 holdout"这两条科学性约束依然有效；只是"从执行机只读同步"这条路径不存在了，必须改为"本节点自己发起全部真实下载"。本文档 DL-0 ~ DL-6 就是这条新路径的具体执行计划。

---

## 1. 总规则

### 1.1 存储布局

所有真实下载数据写入**新目录**（本任务本身不创建它，只在此声明布局，由 DL 步骤执行时创建）：

```
/mnt/afs/260010168/extreme_weather_benchmark/data_real_v16/
├── receipts/            # 所有请求的回执 JSONL + 每批次的 manifest.json
├── asos/                # METAR/SPECI 例行观测（DL-2）
├── taf/                 # TAF 版本链（DL-3）
├── lamp/                # LAMP LAV 公报（DL-4）
├── nhc/                 # NHC fstadv + HURDAT2（DL-5，仅数据资格用途）
├── forward_capture/     # 前向实时采集（DL-6），含 bin/ 循环脚本
└── quarantine_holdout/  # 落在冻结确认周内的数据，物理隔离
```

- **该目录不受 git 版本控制**（`extreme_weather_benchmark/` 本身不是 git 仓库，`data_real_v16/` 也不放进 `development/.../repo/` 里）。
- **绝不写入受保护路径**：`publication/`、`development/disastertrace-next/`、`plan/`（这三条与 `PROTECTED_ARTIFACTS.json` 中记录的保护路径一致）。任何 DL 步骤完成后应做一次 `find publication development/disastertrace-next plan -newer <本批次开始时间戳文件>` 式的防越界检查。

### 1.2 网络规则

- 每次请求**先尝试直连**；如果直连失败（超时/连接被拒/DNS 失败），再执行 `source /mnt/afs/260010168/init-proxy.sh`（该文件已存在，设置 `HTTP_PROXY=http://127.0.0.1:17890` 等环境变量），用代理重试**一次**。直连和代理重试都失败才记为不可达。
- 记录每次请求实际走的是 `direct` 还是 `proxy`，写入回执的 `network_path` 字段。

### 1.3 D10 合规：run identity / 预算 / 回执

每一个 DL 批次（DL-0 ~ DL-6 的每一次调用）必须先声明：

```json
{
  "run_id": "<UTC时间戳>_<配置sha256前12位>",
  "batch": "DL-2",
  "max_requests": 250,
  "max_bytes_total": 314572800,
  "deadline_utc": "2026-09-20T18:00:00Z",
  "station_calendar_hash": "<sha256 of DL-1 冻结配置>"
}
```
写入 `data_real_v16/receipts/<run_id>_manifest.json`，**在发出第一个真实请求之前**落盘。

每一次 HTTP 请求，无论成功失败，都必须在完成后立刻追加一条记录到 `data_real_v16/receipts/<run_id>_requests.jsonl`（JSON Lines，每行一个请求）：

```json
{"run_id": "...", "seq": 1, "url": "...", "method": "GET",
 "timestamp_utc": "...", "http_status": 200, "bytes_received": 12345,
 "sha256": "...", "network_path": "direct", "outcome": "received",
 "saved_path": "data_real_v16/asos/KSFO/2023-01.csv", "notes": ""}
```
这是"回执"的强制格式，参考自本仓库 v13 快照里已验证可用的模式（`multimodal_v1/acquire.py` 的 `intent.json`/`receipt.json` 两阶段落盘：先记录 `{"url":..., "kind":..., "at":..., "reserved_bytes":...}` 意图，成功后再记录 `{"final_url":..., "bytes_received":..., "sha256":..., "status":...}` 回执）——DL 系列复用同一思想，但**合并为单文件 JSONL** 以简化下游审计。

**在没有产出这条回执记录之前，任何一次下载都不算"完成"**——不能先写数据文件、事后补回执；应该是"请求 → 落盘响应体 → 计算 sha256 → 写回执"这一整个动作要么全部发生，要么请求本身就记为 `failed`。

**旧失败请求永不静默重试**：如果要对一个已经失败过的 URL 重试，新的回执记录必须在 `notes` 字段里显式写明 `"retry_of_seq": <原始 seq 号>`，不能当作一次全新的、无关联的请求。这与 v13 `BLOCKERS.md` 里记录的做法一致（"A first annual KJFK fetch timed out and its declared exact retry succeeds"——原文强调的是"declared exact retry"，即声明式的、可追溯的精确重试，而不是换个标签重新发）。

### 1.4 D09 合规：冻结确认周 & 新 holdout

- 旧的 Bay 确认周 **2025-02-17 至 2025-02-23（UTC）** 保持关闭：这段时间窗口内任何站点的任何原始数据（METAR/TAF/LAMP），落地时必须直接写入 `data_real_v16/quarantine_holdout/`，不得进入 `asos/`、`taf/`、`lamp/` 的常规目录，也不得被后续的修订密度审计（DL-3）或任何统计直接读取。
- 除这段冻结周之外的 2025 年数据，属于"开发日历"（development calendar），可以正常下载进常规目录，但**不能被当作确认/评估用的 holdout 使用**，除非未来方法/网格/评分器/统计方法先完成哈希冻结、并显式开启一个新 holdout（D09 的要求）。**本计划不预先选定新 holdout**——那是哈希冻结之后的独立任务，超出 W0 范围。
- DL-6 前向采集抓到的数据，同样按 D09 精神处理：在方法/网格/评分器/统计冻结之前，视为"已隔离但暂不可用"（quarantined-until-freeze）；实现方式是给每条前向采集记录打 `quarantine_status: "pending_freeze"` 标签，不必物理搬进 `quarantine_holdout/`（因为它本来就该继续按小时追加，物理隔离会破坏其连续性），但下游任何评分代码在冻结之前都不得读取它。

### 1.5 复用的解析器（不要重新实现）

本仓库已有 TAF/METAR 解析器，DL-3 的校验步骤直接调用它们，不要重写：

- `disastertrace-starter/src/disastertrace/monitoring_v1/providers/aviation.py` —— TAF 原始文本解析，含 `amendment_kind = "COR" if "COR" in prefix else "AMD" if "AMD" in prefix else "original"`（第 298 行）、`NIL`/`CNL` 识别（第 310 行）。
- `disastertrace-starter/src/disastertrace/monitoring_v1/providers/taf_timeline.py` —— 将 TAF 版本流投影为固定目标的 timeline 事件，含 `unavailable_product()`（保留无法解析的原始报头）和 `target_withdrawals()`（版本覆盖策略 `legacy_covering.v1` / `latest_before_coverage.v2`）。
- `disastertrace-starter/src/disastertrace/monitoring_v1/providers/versions.py` —— `latest_issuance()`、`taf_semantics()`、`current_taf()`。

---

## 2. DL-0 连通性探测

**目的**：在花费任何下载预算之前，先搞清楚哪些候选端点这台机器实际能连上、返回什么。**不要假设本文档下面写的任何 URL 一定可用——按下面列出的方式逐条探测，如实记录。**

### 2.1 候选端点清单（附来源与确认程度）

| # | 端点 | 用途 | 确认程度 |
|---|------|------|----------|
| 1 | `http://mesonet.agron.iastate.edu/archive/data/{partialpath}`，`partialpath` 形如 `{YYYY}/{mm}/{dd}/...` | IEM 通用归档镜像 | **在 pyIEM 源码中确认存在**：`reference_code/pyIEM/src/pyiem/util.py:558`，函数 `archive_fetch()`。但 pyIEM 自己的测试只拿它取非文本产品（`tests/test_util.py:76`：`archive_fetch("2024/02/09/mesonet_1200.gif")`），**没有**任何测试或文档证明这个路径能取到原始 TAF/METAR 文本公报——用于文本产品前必须先探测。 |
| 2 | `http://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?...`（IEM 常见的 ASOS 历史 CSV 服务） | METAR/ASOS 例行观测批量下载 | **未在 pyIEM 或本仓库任何地方找到**。pyIEM 是纯解析库（`nws/products/metarcollect.py` 只解析 METAR 文本，不下载），完全没有这个下载端点的代码或文档引用。这是"已知的 IEM 网站惯例"，但**不是从本地代码验证得到的**——必须探测，如果 404/改版，需要在 DL-0 报告里如实写"未确认失败"，交给下一轮找替代路径，不要猜测新 URL 硬编码进批量脚本。 |
| 3 | `http://mesonet.agron.iastate.edu/request/taf.php?...`（IEM 常见的 TAF 历史请求服务） | TAF 版本链批量下载 | 同上，**未在本地代码中找到**，需探测确认。 |
| 4 | `https://www.nhc.noaa.gov/archive/{YYYY}/{basin_lower}/{storm_lower}.fstadv.{NNN:03d}.shtml` | NHC 结构化 fstadv 预报 | **在 v13 快照代码中确认**：`publication/v13_completed_20260917_01/snapshot/disastertrace-starter/src/disastertrace/forecast_source/pipeline.py`，`selection()` 函数构造该 URL 模式，`MAX_BYTES = 2 * 1024 * 1024`（2MB 上限）。 |
| 5 | `https://ftp.nhc.noaa.gov/atcf/gis/{kind}/` | NHC ATCF GIS 目录（含 best-track 相关文件） | **在 v13 快照代码中确认**：`multimodal_v1/seed_sources.py:39`，`index_url = f"https://ftp.nhc.noaa.gov/atcf/gis/{kind}/"`，随后用 `urljoin` 从目录页解析出具体文件链接。 |
| 6 | `https://www.nhc.noaa.gov/data/hurdat/`（HURDAT2 最佳路径存档页面） | HURDAT2 best-track | **未在本地代码中确认具体文件名**——只知道本地曾经有一份 HURDAT2 归档（`plans/v5_0910_feasibility_12h_20260910/attempts/0102/body.bin`，已被早前审计标记为"同机构，非独立测量"，仅供离线比对用，不可当新下载的替代）。DL-0 必须访问该页面本身，抓取真实的当前文件链接，不要凭记忆拼文件名。 |
| 7 | `https://vlab.noaa.gov/web/mdl/lamp-prob-and-thresh` | LAMP 概率/阈值产品说明与分发入口 | 用户指定的起点，**本会话未验证**。DL-0 必须实际访问，如果该页面已下线/改版（NOAA VLab 曾多次迁移），要记录实际返回内容或跳转目标，再决定下一步。 |
| 8 | LAMP LAV 公报的 IEM AFOS 文本归档（候选：走端点 #1 的 `archive/data` 路径，PIL 前缀 `LAV`） | LAMP LAV 原始公报文本 | **未确认**，属于端点 #1 的一个具体用法猜想，必须实际探测（例如尝试 `archive/data/{YYYY}/{mm}/{dd}/afos/LAV....txt` 这一类路径，具体子路径格式由 DL-0 实际探测 IEM 站点导航或用其 API 搜索得到，不要凭空拼）。 |

### 2.2 探测协议

- 每个候选端点**恰好发一次**有界探测请求（GET 或 HEAD，取决于该端点是否支持 HEAD；不确定就用 GET 但设 `max_bytes=65536` 截断读取）。
- 超时 30 秒；单次响应读取上限 65536 字节（足够看到页面结构/JSON 头/CSV 前几行,不需要整份下载）。
- 每次探测都要写回执（格式见 §1.3），另外在 `notes` 字段记录响应内容的前 500 字符预览（文本）或 base64 前 200 字节（二进制),以及是否发生跳转（记录最终 URL）。

### 2.3 验收标准

- 输出文件 `data_real_v16/receipts/dl0_probe_summary.json`：对上表 8 个候选端点逐条给出 `reachable: true/false`、`http_status`、`content_type`、`notes`。
- 8 个端点全部有明确探测结果（不能有遗漏），无论结果是可达还是不可达，都算 DL-0 完成。
- 如果端点 #2/#3（ASOS/TAF 请求服务的猜测 URL 形式）不可达，DL-0 报告必须给出下一步：走 IEM 站点首页导航或搜索确认实际的当前服务路径，而不是直接放弃 METAR/TAF 下载。

### 2.4 预算上限

- 总请求数 ≤ 10（8 个端点 + 最多 2 次因跳转/改版需要的追加探测）。
- 总字节数 ≤ 2MB。
- 时限：30 分钟内完成（8 个独立探测，网络问题不应该互相阻塞太久）。

---

## 3. DL-1 站点/日历冻结

### 3.1 v13 遗留线索（已实际读取原文，逐条引用）

以下引用全部来自 `publication/v13_completed_20260917_01/snapshot/disastertrace-starter/`，已核实行号：

**`BLOCKERS.md`，"## v11 current execution limits, 2026-09-15" 一节（约第 172-189 行）**：

> "Annual432catalog acquisition is active. Three leap-month regional samples pass; their2470 native TAF bodies/full-month joins are a separate active scope. Full annual raw data, purged role qualification, fitting and calibration are not done."
>
> "ChicagoJanuary2023 KORD catalog acquisition receives429 and then a200 response with curl28 timeout on its registered exact retry. The unit remains incomplete; this is retrieval failure, not established source unavailability. Other units continue."
>
> "One initial F_COMMON preflight failed and is preserved; its corrected preflight succeeds in a new directory. A first annual KJFK fetch timed out and its declared exact retry succeeds. These failures are retained, not silently replaced."

**`BLOCKERS.md`，约第 496-499 行**：

> "The fresh 252-call H100 diagnostic completes and independently replays... Real TAF coverage/version inputs qualify a narrow E task... historical TAF is actually verified for KSFO/KDEN."

**`IMPLEMENTATION_STATUS.md`，约第 692 行**：

> "IEM LAV runtime=00Z matches the native 00:30Z product, so native minutes must be retained."

**`IMPLEMENTATION_STATUS.md`，约第 825 行**：

> "Actual IEM bulk requests retrieve three stations' hourly observations in944-958 bytes; one daily request returns72 matching native rows."

**`DECISIONS.md`，约第 436 行**：

> "Use historical native LAMP bulletin minutes, not normalized IEM runtime, for chronology checks."

### 3.2 我对这些线索做了什么核查，结果是什么（如实说明，不要假装比实际更确定）

- 对三份文件（`BLOCKERS.md`、`IMPLEMENTATION_STATUS.md`、`DECISIONS.md`）做了 `K[A-Z]{3}` 机场代码的全文件正则扫描。**三份文件里出现过的机场代码只有四个：KORD、KJFK、KDEN、KSFO**（均在 `BLOCKERS.md` 里，`IMPLEMENTATION_STATUS.md` 和 `DECISIONS.md` 里唯一匹配的 `K[A-Z]{3}` 是误命中的单词 "KEEP"，不是机场代码）。
- "Actual IEM bulk requests retrieve **three stations'** hourly observations" 这句话出现在 `IMPLEMENTATION_STATUS.md`，而这份文件里**没有任何机场代码出现过**——也就是说，"三个站点"具体是哪三个，在 v13 文档里**找不到直接对应关系**。不要假设它就是 KSFO/KDEN/KJFK 三个,也不要假设是另一个未命名的第三个站。**这是一个确认不了的点，如实标注为未知，DL-0/DL-2 阶段用真实探测结果验证。**
- 具体日期方面，**唯一一处出现具体年月的是 "ChicagoJanuary2023 KORD"**——即 KORD、2023 年 1 月。其余提到"annual"（KJFK 的"first annual...fetch"、"Annual432catalog acquisition"）都只说明是"全年"尝试,没有给出具体是哪一年。

### 3.3 冻结依据与流程

1. 以上四个机场代码（KSFO、KDEN、KJFK、KORD）作为候选站点起点，按确认强度排序：
   - **强**：KSFO、KDEN——"historical TAF is actually verified"。
   - **中**：KJFK——首次年度抓取超时，"declared exact retry succeeds"，即最终验证成功,但描述里没提具体产品类型/年份。
   - **弱**：KORD——429 之后拿到 200，但注册的精确重试本身又 curl28 超时,"the unit remains incomplete"。KORD 需要在 DL-0/DL-2 里重新探测,不能假设它现在能用。
2. 结合 DL-0 的连通性结果：**只保留 DL-0 证实端点 #1/#2/#3 中至少一个可达时才能支持的站点**;如果某候选站点在 DL-0/首批 DL-2 试探中持续失败,应该用另一个流量较大的美国主要机场站（如 KDFW、KATL、KLAX 等,同样是 IEM 网络里覆盖度高的站)替换,而不是硬凑数量。
3. 结合 DL-3 的修订密度审计（见 §5）：先用候选站点各拉一小段（比如 2023 年 1 月）TAF 试探性样本，统计 AMD/COR/CNL 事件密度,密度过低的站点应该被替换或补充,而不是被动接受低事件密度。
4. 最终站点数 3-5 个，时间范围遵循 D05 的切分惯例：**2023 全年 = train，2024 年 1-11 月 = calibration，2025 年（除冻结确认周外）= development-only**。这个切分现在只是"日历标签"，真正的 train/calibration/development 角色仍然要等真实曝光账本冻结后才算数（D05 原话："训练/校准/开发的时间划分必须依据真实曝光账本冻结后确定，不能提前假设"）——本计划只是按这个惯例给下载打标签，不代表科学结论已经成立。
5. 产出：`data_real_v16/receipts/station_calendar_freeze_v16.json`，包含 `stations`（3-5 个站点代码及各自确认强度/替换记录）、`date_range`（每个站点各自的实际起止日期,可能因数据可得性不同而不完全一致）、`decision_notes`（记录每个替换/排除的理由）,并计算该文件内容的 sha256,写入文件自身的 `self_sha256` 字段（先写除该字段外的内容算 hash，再回填）。

### 3.4 验收标准

- `station_calendar_freeze_v16.json` 存在、可被 `json.load` 解析、`self_sha256` 校验通过。
- 站点数在 3-5 之间。
- 每个站点都能在 `notes` 里说明选择/替换依据（引用 DL-0 或试探性 DL-2/DL-3 结果，或引用本节 §3.1-3.2 的 v13 线索）。
- **这一步一旦完成，必须立即触发 DL-6（前向实时采集）开始运行**——不等 DL-2/DL-3/DL-4/DL-5 做完。DL-6 只依赖这份冻结配置,不依赖历史数据下载的完成。

### 3.5 预算上限

- 本步骤自身不发起大规模下载,只做少量试探性抓取(如需要,复用 DL-3 §5 的小样本试探,计入 DL-3 预算)。
- 纯分析/决策部分无网络预算。

---

## 4. DL-2 METAR/ASOS 例行链（2023-2025）

### 4.1 范围

对 DL-1 冻结的 3-5 个站点，按"每站点每月"为批次单位,下载 METAR 例行观测**及 SPECI（特殊天气报）**,�covers DL-1 冻结的日期范围(原则上 2023-01 至 2025-12,实际按各站点可得性调整)。

### 4.2 冻结周隔离

任何观测时间落在 **2025-02-17T00:00:00Z 至 2025-02-23T23:59:59Z** 区间内的记录,下载后必须存入 `data_real_v16/quarantine_holdout/asos/`,不得混入 `data_real_v16/asos/` 常规目录。判断依据是观测记录自身的 valid time,不是下载发生的时间。

### 4.3 验收标准

- 每个"站点×月"批次产出一个数据文件 + 至少一条回执;文件内至少包含例行 METAR 记录,SPECI 记录若该月存在则一并包含(若该来源把 METAR/SPECI 分开成两个请求,则各自独立记录回执)。
- 每个站点的总记录数与月历天数做粗校验(如某月记录数明显低于"每小时至少 1 条"的下限,在 manifest 里标注 `coverage_flag: "sparse"`,不静默接受)。
- 冻结周内的记录 100% 落在 `quarantine_holdout/`,可用一次事后扫描验证(按记录时间戳过滤,确认 `asos/` 目录下没有落在该区间的记录)。

### 4.4 预算上限

- 请求粒度:每请求覆盖一个站点一个月(如实际服务粒度不同,如只能按天/按年,请在回执 `notes` 里记录实际粒度并相应调整总请求数,不要为了凑"每站点每月 1 请求"的假设而拆分/合并出错误数据)。
- 总请求数 ≤ 250(约 4 站点 × 36 月 ≈ 144,留出重试/SPECI 独立请求的余量)。
- 单请求响应体上限 10MB(METAR/SPECI 文本量很小,10MB 已是充分宽松的上限,用于捕获异常大响应并及时中止)。
- 批次总字节数上限 300MB。
- 批次时限:6 小时。

### 4.5 回执格式

同 §1.3 通用格式,额外在 `notes` 里记录 `station`、`year_month`、`report_type`("routine"/"speci"/"combined")。

---

## 5. DL-3 TAF 版本链（2023-2025）+ 修订密度审计

### 5.1 范围

对 DL-1 冻结的站点,下载 TAF **完整版本链**,包括原始发布(original)、AMD(amendment)、COR(correction)、CNL(cancellation/NIL)在内的所有版本,覆盖同样的日期范围。

### 5.2 用现有解析器校验(不写新解析代码,只调用)

下载完成后,对样本(建议每站点每季度抽 1 周)跑一次 `disastertrace-starter/src/disastertrace/monitoring_v1/providers/aviation.py` 的原始文本解析入口和 `taf_timeline.py::target_withdrawals()`,确认:

1. 每条原始 TAF 报文都能被解析出 `amendment_kind`(`"COR"`/`"AMD"`/`"original"`)而不抛异常;
2. `NIL`/`CNL` 报文被正确识别(`aviation.py` 第 310 行的 `body in {"NIL", "CNL"}` 分支);
3. 对同一站点同一有效期窗口,`versions.py::latest_issuance()` 能给出确定的最新版本,不出现二义。

解析失败的样本要被记录(不是丢弃),写入 `data_real_v16/receipts/dl3_parse_failures.jsonl`,包含原始报文全文、失败原因、站点、时间。

### 5.3 修订密度审计(下载完成后的纯分析步骤,不需要网络)

对每个站点每月,统计:
- AMD 事件数
- COR 事件数
- CNL 事件数
- supersession(新版本覆盖旧版本)事件数

产出 `data_real_v16/receipts/revision_density_v16.json`,按站点×月给出上述四个计数。基于这份统计:

- 划出一个"**压力子集**"(stress subset):修订密度显著高于该站点均值的月份/时段,用于测试系统在密集修订下的语义事件处理能力。
- 划出一个"**自然子集**"(natural subset):按自然频率分布、不做筛选的常规月份/时段,用于常规评估。
- **如果某个冻结站点在全部覆盖月份里修订密度持续过低(例如全年 AMD+COR+CNL 事件数 < 个位数)**,应该回到 DL-1,考虑替换/新增站点,而不是接受低事件密度继续往下走——这是任务里明确要求的("if a station is too revision-sparse, prefer swapping/adding stations over accepting low event density")。

### 5.4 验收标准

- 每个"站点×月"批次产出版本链数据 + 回执。
- 抽样解析校验(§5.2)全部样本要么解析成功、要么被记录为 `dl3_parse_failures.jsonl` 里的已知失败,不允许静默丢弃报文。
- `revision_density_v16.json` 存在,每个冻结站点都有非零的统计覆盖(哪怕密度低,也要有真实计数,不能是占位符)。
- stress/natural 子集划分写入同一份或配套的 json,标明具体是哪些"站点×月"属于哪个子集。

### 5.5 预算上限

- 请求粒度:同 DL-2,每站点每月 1 请求(若实际服务粒度不同同样要如实记录)。
- 总请求数 ≤ 250。
- 单请求响应体上限 10MB。
- 批次总字节数上限 300MB。
- 批次时限:6 小时(不含 §5.2 的解析校验和 §5.3 的统计分析时间——这两步是本地计算,不占用网络预算/时限)。

### 5.6 回执格式

同 §1.3,额外记录 `station`、`year_month`、`taf_variant`("original"/"amendment_chain"/"cancellation" 等,视实际服务参数而定)。

### 5.7 2026-09-20 修订说明

实际执行本节时,下载会话走了 §4.3 提到的备用端点(`taf.py` CSV 服务),产出的分解式 CSV 与本仓库 `episode_compiler.py`/`aviation.py::parse_taf()` 需要的完整原始报文文本不兼容(CSV 缺少整份公报的有效期窗口字段,不可逆恢复)。TAF **原始文本**的重新获取现已在 `DL3R_REDOWNLOAD_PROMPT_CN.md` 中单独规定,应优先使用 §4.2 的首选路径(`afos/retrieve.py`,已在 DL-0 验证可达)而非本节 §4.3 的备用路径。§5.1-§5.5 的验收标准、修订密度审计逻辑、holdout 规则本身继续有效,不受此修订影响。

---

## 6. DL-4 LAMP LAV 公报(D11:仅作为基线用途)

### 6.1 范围与 D11 合规

D11 的 selection 明确要求:"LAMP 概率产品、类别(categorical)产品、条件概率产品必须分开登记,不可混同。阈值(threshold)、支持范围(support)、版本必须对齐后才能比较。" 因此 DL-4 下载时必须**从一开始就把这三类产品存进不同子目录**:

```
data_real_v16/lamp/
├── probabilistic/    # 概率产品
├── categorical/      # 类别产品
└── conditional/      # 条件概率产品
```

每类产品各自记录自己的阈值定义、支持范围(支持的预报时效/更新频率)、版本号,写入该类别子目录下的 `registry.json`。

### 6.2 IEM 运行时 vs 原生产品时间差记录

按 v13 线索(`IMPLEMENTATION_STATUS.md` 约第 692 行:"IEM LAV runtime=00Z matches the native 00:30Z product, so native minutes must be retained"; `DECISIONS.md` 约第 436 行:"Use historical native LAMP bulletin minutes, not normalized IEM runtime, for chronology checks"),下载时必须**同时记录两个时间戳**:

- `iem_runtime`:IEM 系统标注的运行时次(如归一化为整点的 00Z)
- `native_bulletin_time`:公报文本自身携带的原生发布时间(如实际的 00:30Z)

两者不一致时,一律以 `native_bulletin_time` 作为时序判定依据(这是 v13 DECISIONS.md 明确记录的教训),`iem_runtime` 仅作参考字段保留,不用于时序计算。

### 6.3 验收标准

- 三类产品(概率/类别/条件)各自的 `registry.json` 都存在且互不覆盖。
- 每条下载记录都同时有 `iem_runtime` 与 `native_bulletin_time` 两个字段;若某来源确实无法拿到原生时间(如只提供了归一化运行时),必须在 `notes` 里显式标注 `native_time_unavailable: true`,不能悄悄用 `iem_runtime` 顶替。
- 覆盖 DL-1 冻结站点、2023-2025 范围(若 LAMP 历史归档保留期比 3 年短,如实记录实际可得的最早日期,不要假设三年数据都存在)。

### 6.4 预算上限

- 总请求数 ≤ 150(LAMP 更新频率高于 TAF,但历史归档粒度未知,先保守估计每站点每月 1-3 请求)。
- 单请求响应体上限 5MB。
- 批次总字节数上限 100MB。
- 批次时限:3 小时。

### 6.5 回执格式

同 §1.3,额外记录 `station`、`product_class`("probabilistic"/"categorical"/"conditional")、`iem_runtime`、`native_bulletin_time`。

---

## 7. DL-5 NHC 数据资格(D02:仅数据资格审查,绝不做模型调用)

### 7.1 严格边界

D02 selection 原文:"H15 为唯一主试点领域(sole primary pilot domain);NHC 工作降级为孤立的小规模数据资格审查(isolated data-qualification only),不做任何模型调用(no model calls)。" **DL-5 的唯一目标是回答"结构化字段能否被解析、能否在时间上对齐"这一个问题,不产生任何评分、不喂给任何模型。**

### 7.2 复用 v13 下载模式

- fstadv 结构化预报:复用 `publication/v13_completed_20260917_01/snapshot/disastertrace-starter/src/disastertrace/forecast_source/pipeline.py` 里验证过的 URL 模式和字节上限(`MAX_BYTES = 2 * 1024 * 1024`),即 `https://www.nhc.noaa.gov/archive/{YYYY}/{basin_lower}/{storm_lower}.fstadv.{NNN:03d}.shtml`。
- 该文件里已有一份具体的 storm 选择示例(`AL062024`/`FRANCINE`,advisory 5-11;`AL092021`/`IDA`,advisory 9-15)——可以直接复用这个 selection 作为起点样本,也可以扩展到 DL-0 探测确认可达之后发现的其它风暴。
- HURDAT2 best-track:通过 DL-0 探测 `https://www.nhc.noaa.gov/data/hurdat/` 得到的实际当前文件链接下载,**不要**复用本地 `plans/v5_0910_feasibility_12h_20260910/attempts/0102/body.bin` 里的旧文件当新下载的替代——那份文件已被早前审计标记为"同机构,非独立测量",且是否为当前版本未知,只能用作离线交叉比对参考,不能顶替一次新的、有回执的下载。
- ATCF GIS 目录:复用 `multimodal_v1/seed_sources.py` 里验证过的 `https://ftp.nhc.noaa.gov/atcf/gis/{kind}/` 模式,先取目录页解析出真实文件链接,再逐个下载,不要凭空拼具体文件名。

### 7.3 验收标准

- 至少覆盖 2-3 个风暴、每个风暴至少 5 期 advisory 的 fstadv 结构化字段成功解析(字段完整、时间戳可解析为 UTC)。
- HURDAT2 best-track 至少 1 份完整文件下载成功,且能与 fstadv 样本里出现的风暴 ID 做时间对齐匹配(即同一风暴同一时间点,fstadv 的位置/强度字段与 HURDAT2 的对应记录能关联上,不要求数值一致,只要求能匹配上同一观测点)。
- 产出 `data_real_v16/receipts/dl5_qualification_report.json`,明确回答"结构化字段是否可解析"(是/否 + 具体字段清单)和"是否可与 HURDAT2 时间对齐"(是/否 + 匹配方法说明)。
- **不生成任何评分、不调用任何模型 API、不写任何 prompt**——这是硬性红线。

### 7.4 预算上限

- 总请求数 ≤ 60。
- 单请求响应体上限 2MB(沿用 v13 `pipeline.py` 里验证过的 `MAX_BYTES`)。
- 批次总字节数上限 50MB。
- 批次时限:2 小时。

### 7.5 回执格式

同 §1.3,额外记录 `storm_id`、`advisory_number`(fstadv 场景)或 `gis_kind`(ATCF GIS 场景)。

---

## 8. DL-6 前向实时采集(用户已批准,DL-1 冻结后尽早启动)

### 8.1 目的与合规基础

用户在 2026-09-20 的 AskUserQuestion 中已批准:从现在(2026-09)起持续采集当前的 TAF/METAR(+LAMP LAV)数据,作为**唯一无泄漏的确认资源**——这批数据是在所有被评估模型的训练截止日期之后采集的,按构造不可能出现在预训练语料里。**这是本计划里唯一"边下载边使用未来"的合法路径**,但仍然受 D09 约束:在方法/网格/评分器/统计哈希冻结之前,这批数据只能被采集和保存,不能被用于评分或模型开发决策(见 §1.4 最后一段)。

### 8.2 启动条件

**DL-1(§3)一旦产出 `station_calendar_freeze_v16.json`,DL-6 立即启动**,不等待 DL-2/DL-3/DL-4/DL-5 完成。DL-6 只需要站点列表,不需要历史数据。

### 8.3 实现要求

- 循环脚本位置:`data_real_v16/forward_capture/bin/`(具体文件名/语言由执行者决定,建议 shell 脚本调用 Python 下载逻辑,或纯 Python 用 `schedule`/cron 语义的自建循环)。
- **按小时循环**:每小时一次,对 DL-1 冻结的每个站点抓取当前 TAF + 最新 METAR(+ 若 DL-0/DL-4 确认可达则含 LAMP LAV)。
- **幂等 / 可重启**:脚本重启后,必须先检查本小时是否已经成功采集过(通过检查 `forward_capture/` 下是否已有该小时该站点的回执且 `outcome: "received"`),已采集则跳过,不重复请求、不重复计费。
- **只增不改(append-only)**:采集结果一律追加写入,不改写/不删除已有记录。
- **持续运行**:这个循环脚本设计上要能长期(数周/数月)运行;每次运行只负责"这一个小时"的采集,通过外部调度(cron/循环 sleep)反复调用。
- 同样遵守 §1.3 的回执要求——每小时的每次请求都要有 JSONL 回执,另外建议按天或按周滚动出一个 `forward_capture/receipts/<date>.jsonl` 避免单文件无限增长。

### 8.4 验收标准

- 首次运行后,`data_real_v16/forward_capture/` 下能看到至少 1 个完整小时、覆盖全部冻结站点的采集记录+回执。
- 手动模拟"重启"(连续跑两次同一小时)后,第二次运行的回执里对应记录的 `outcome` 是 `"skipped_duplicate"` 而不是重复的 `"received"`(验证幂等性)。
- 脚本本身有清晰的启动/停止方式说明(写在 `forward_capture/bin/` 目录下的简短 README 或脚本头注释里,不需要额外的完整文档)。

### 8.5 预算上限

- 单次(每小时)运行:请求数 ≤ 20(3-5 站点 × 2-3 种产品),单请求响应体上限 5MB,单次运行总字节数 ≤ 20MB。
- 由于是持续运行,不设总预算上限,但**每次运行必须独立声明自己的 run_id 和当次预算**(复用 §1.3 的 manifest 格式,run_id 里含具体的采集小时,如 `20260921T0300Z_forward`)。

### 8.5.1 2026-09-20 修订说明

`forward_capture.py` 的实际实现在脚本自身 docstring 里把每小时请求数进一步收紧到 ≤6(硬编码只覆盖冻结站点里的前 3 个,`stations[:3]`),导致第 4 个冻结站点 KORD 被结构性排除在前向采集之外。经用户明确授权,该实现层面的每小时上限已提高到 ≤8(覆盖全部 4 个冻结站点 × TAF/METAR 2 种产品),纳入 KORD。这**仍在本节声明的 ≤20 请求/次硬上限之内**,不构成对本合同预算条款的突破。具体执行步骤见 `DL3R_REDOWNLOAD_PROMPT_CN.md` Part B(DL-6R)。

### 8.6 回执格式

同 §1.3,额外记录 `capture_hour_utc`、`station`、`product_type`("taf"/"metar"/"lav")、`quarantine_status: "pending_freeze"`(固定值,标记该记录在冻结前不可用于评分)。

---

## 9. 执行顺序总览

```
DL-0(连通性探测)
   │
   ▼
DL-1(站点/日历冻结) ──────────► DL-6(前向实时采集,立即启动,持续运行)
   │
   ├──► DL-2(METAR/ASOS)
   ├──► DL-3(TAF 版本链 + 修订密度审计)──(密度过低则回到 DL-1 换站)
   ├──► DL-4(LAMP LAV)
   └──► DL-5(NHC 数据资格,与其它 DL 步骤相互独立,可并行)
```

DL-2/DL-3/DL-4/DL-5 之间除"DL-3 密度审计可能要求回到 DL-1 补站"外没有强制先后顺序,可以按资源情况并行或顺序执行,但**不要在同一时刻对同一站点的同一批次发起两个并发下载任务**(避免回执竞争写入同一个 run_id 目录)。

---

## 附录:引用来源清单

- `reference_code/pyIEM/src/pyiem/util.py`(第 530-576 行,`archive_fetch()`)
- `reference_code/pyIEM/tests/test_util.py`(第 47-76 行,`archive_fetch()` 用法示例)
- `reference_code/pyIEM/src/pyiem/nws/products/taf.py`、`reference_code/pyIEM/src/pyiem/models/taf.py`、`reference_code/pyIEM/data/product_examples/TAF/*.txt`(证明 pyIEM 是纯解析库,不含下载端点)
- `publication/v13_completed_20260917_01/snapshot/disastertrace-starter/BLOCKERS.md`(约第 172-189 行、第 496-499 行)
- `publication/v13_completed_20260917_01/snapshot/disastertrace-starter/IMPLEMENTATION_STATUS.md`(约第 692 行、第 825 行)
- `publication/v13_completed_20260917_01/snapshot/disastertrace-starter/DECISIONS.md`(约第 436 行)
- `publication/v13_completed_20260917_01/snapshot/disastertrace-starter/src/disastertrace/forecast_source/pipeline.py`
- `publication/v13_completed_20260917_01/snapshot/disastertrace-starter/src/disastertrace/multimodal_v1/acquire.py`
- `publication/v13_completed_20260917_01/snapshot/disastertrace-starter/src/disastertrace/multimodal_v1/seed_sources.py`
- `publication/v13_completed_20260917_01/snapshot/disastertrace-starter/src/disastertrace/automated/acquisition.py`
- `disastertrace-starter/src/disastertrace/monitoring_v1/providers/{aviation.py,taf_timeline.py,versions.py}`(本仓库当前分支,已存在,直接复用)
- `plan/plan_v14_0919/RESEARCH_DECISIONS_v14_20260919.yaml`(D02/D05/D09/D10/D11/D12,均为 `status: APPROVED`,2026-09-20 批准)
