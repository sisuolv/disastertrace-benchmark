# DisasterTrace v16 — DL-3R/DL-6R 补充执行计划（TAF 原始文本重下载 + 前向采集补齐 KORD）

## 0. 给零上下文执行者的说明

本文档是**自包含**的：你不需要阅读本仓库其它计划文件、不需要重新推导任何前提，即可按本文档直接执行。你只需要额外只读打开本文档第 0.3 节列出的几份既有数据文件做核对用途（不是"先读别的计划文档"，是"核对几个具体的既有产物文件"）。

本文档**补充并局部取代** `plan/plan_v16_0920/DATA_ACQUISITION_PLAN_v16_CN.md`（以下简称"主合同"）的两处内容：

- **DL-3（主合同 §5，TAF 版本链）的"下载什么格式"这一半**：主合同 §5 本身的验收标准、修订密度审计逻辑、holdout 规则**继续有效**；本文档只改变"用哪个端点、下载出来是什么格式"这一点——因为上一轮实际执行时走了主合同 §4.3 提到的 `taf.py` CSV 备用端点，产出的 CSV 与本仓库解析器不兼容（见 §0.2）。本文档规定的动作代号是 **DL-3R**（R = redo，重做，不是"取代 DL-3"，是"DL-3 的下载部分重新做一遍，其余部分沿用"）。
- **DL-6（主合同 §8，前向实时采集）的每小时请求数**：本文档新增 **DL-6R**，把 `forward_capture.py` 现有的每小时 3 站点（6 请求）硬编码扩展为 4 站点（8 请求），经用户明确授权（见 §0.4）。

本文档**不覆盖**：DL-1/DL-2/DL-4/DL-5 的任何内容（这些不受 CSV 不兼容问题影响，保持主合同原状，不需要重做）；不覆盖 `episode_compiler.py` 等解析器代码的修改（那是另一个并行任务 T2 的范围，见 §0.5）；不覆盖 values-bank 拟合、评分器改造或模型调用。

如果你在执行中发现本文档里标注为"未确认"的端点/参数实际不可用、或格式与预期不符，**如实记录 failure，不要静默降级或编造数据**——这是主合同 D10 的强制要求，本文档继续沿用。

### 0.1 你会用到的既有产物（只读，不要修改）

- `data_real_v16/taf/REVISION_DENSITY_AUDIT_v16.md` —— 上一轮 CSV 批次的按站点汇总统计（35 个月合计，2025-02 holdout 月已排除）：KSFO 9,619 / KDEN 11,283 / KJFK 10,218 / KORD 9,697 个唯一 `product_id`。**注意**：这份文件只有 35 个月的合计数，没有按月拆分——本文档 §A.2/§A.4 要求的"按月核对"数字，你必须自己从 CSV 文件里现算（下面给出算法，不需要写复杂代码，几行 pandas/csv 分组统计即可）。
- `data_real_v16/config/DL0_VERDICTS.json` —— DL-0 连通性探测的裁定文件，条目 `probe1-afos-retrieve` 记录了 `afos/retrieve.py` 端点在 7 天窗口下只返回 167 字节（1 条公报）的真实探测结果，`verdict: "VERIFIED"`（意思是"端点可达、格式对"，不代表"覆盖率对"——覆盖率是否完整正是本文档 §A.2 要重新探测的问题）。
- `data_real_v16/config/20260920T083047Z_99c64d8d2cfe/probe1-afos-retrieve.body` —— 上面那次探测的真实响应体（167 字节）。用 `cat -A` 查看可以看到控制字符框架：`^A`（SOH，十六进制 `\x01`，公报起始）→ 一行数字（字节数，如 `878`）→ WMO 报头行（如 `FTUS46 KMTR 072320`）→ PIL 行（如 `TAFSFO`）→ 空行 →`TAF`独占一行 → 真正的 TAF 头行（`KSFO 072320Z 0800/0906 ...`）→ 若干 `FM...` 行 → 以 `=` 结尾 → 空行 →`^C`（ETX，`\x03`，公报结束）。**这就是 `episode_compiler.py`/`aviation.py::parse_taf()` 需要的原始文本形状**——DL-3R 下载的目标格式就是这个，不是 CSV。
- `data_real_v16/taf/20260920T091835Z_5f8988c0e49a/KDEN_202301.body`（或任意一个站月文件）—— 已下载 CSV 批次里一行的真实样例：

  ```
  KDEN,2023-01-01 03:00,2023-01-01 03:00,14006KT P6SM FEW070 BKN220,False,,6.0,140.0,0.0,6.01,[],"['FEW', 'BKN']","[7000, 22000]",,,,202301010300-KBOU-FTUS45-TAFDEN-AAB,Observation,True
  ```

  第 17 列 `product_id`（如 `202301010300-KBOU-FTUS45-TAFDEN-AAB`）编码了：发布时间戳 `202301010300`（YYYYMMDDHHmm，UTC）、发布单位 `KBOU`（NWS WFO 代码）、TTAAII 通报类型码 `FTUS45`、PIL `TAFDEN`、修订序号 `AAB`（A=原始，B/C/...=第几次修订）。这个字段本身就是 IEM `nwstext` API 的产品 ID，§A.4 的补下载会直接用它。
- `data_real_v16/forward_capture/bin/forward_capture.py`、`data_real_v16/forward_capture/RUNNING_PID.txt` —— DL-6R 要编辑/重启的脚本与当前 PID（写本文档时的值为 `8212`，你执行时必须重新读取，不要用这个旧值）。
- `data_real_v16/config/stations_calendar_v16.json` —— DL-1 冻结的站点配置，含每站 `icao`/`faa`/`issuing_office`/`afos_pil` 四个字段（如 KSFO 的 `afos_pil` 是 `TAFSFO`，KDEN 是 `TAFDEN`，KJFK 是 `TAFJFK`，KORD 是 `TAFORD`），以及 `holdout_exclusion.window_start`=`2025-02-17T00:00:00Z`、`window_end`=`2025-02-24T00:00:00Z`。

### 0.2 背景：为什么现有 CSV 批次不能直接用（如实说明问题链，不猜测超出已知范围的内容）

上一轮下载会话（与本文档写作者是不同的会话）执行主合同 §5 时，实际走的是主合同 §4.3 提到的备用端点 `taf.py`（`https://mesonet.agron.iastate.edu/cgi-bin/request/taf.py?...&fmt=comma`），产出见 `data_real_v16/taf/20260920T091835Z_5f8988c0e49a/*.body`（CSV 格式）。这批数据本身是真实、完整下载的（`REVISION_DENSITY_AUDIT_v16.md` 记录了 40,817 条唯一公报、224,698 行），**不是失败产物**，问题在于：这个 CSV 是 IEM 用 pyIEM 自己解析过的"每行一个预报时段"的分解形式，本仓库 `episode_compiler.py::compile_raw_taf_to_evidence()` 需要的是**完整原始报文文本**（含 `TAF [AMD] STATION DDHHMMZ VALIDWINDOW` 报头，才能提取修订类型、有效期整体窗口），而这个整体有效期窗口在 CSV 的分解行里**不可逆恢复**（CSV 每行只有该行自己的 `fx_valid`/`fx_valid_end`，没有整份公报的 `valid`/`valid_end` 字段）。

与此同时，DL-0 的连通性探测（`probe1-afos-retrieve`，见 §0.1）已经证实主合同 §4.2 的**首选路径** `afos/retrieve.py` 是可达的、且返回的格式**正是**解析器需要的完整原始文本——但上一轮下载会话没有用这条路径，改用了备用 CSV 路径。**为什么会这样，原始下载会话的审计记录已经在同一轮里被删除、无法复原**（见 §0.3 的事故说明），根因无法确定。**唯一有强怀疑但未经验证的线索**：`probe1-afos-retrieve` 那次探测请求的是 7 天窗口（`sdate=2024-01-01T00:00Z&edate=2024-01-08T00:00Z`），但只返回了 167 字节、看起来恰好是 1 条公报——这可能意味着 `afos/retrieve.py` 有一个未在 URL 里显式声明、默认值很小（可能是 1）的 `limit` 参数；但也可能是别的原因（比如 `pil=TAFSFO` 这种不带站点前缀的 PIL 只匹配到了原始报而没匹配到修订报的 PIL 变体、或者该端点本身就是"只返回时间窗口内最新一条"的语义、或者 `sdate`/`edate` 解析方式与预期不同）。**这几种假设都没有被验证过，本文档 §A.2 把"先验证清楚"设为强制的第一步，不允许跳过直接批量下载。**

### 0.3 强制前提：绝不删除任何目录，即使是"放弃的方案"（引用真实事故作为反面教材）

`plan/plan_v16_0920/EXECUTION_STATUS_DL_v16_CN.md`（在 `extreme_weather_benchmark/plan/plan_v16_0920/` 下，**不在本 git 仓库内**，但内容真实、已由上一轮父会话核实）§5.1 记录了一起真实事故，原文（节译）：

> DL-3 的执行者在从"AFOS retrieve.py 半年批"方案切换到"taf.py CSV 月批"方案时，**删除了前一方案已经产生的 run_id 目录** `taf/20260920T091530Z_d31ba1efd4e2/`（及其对应的 `quarantine_holdout/taf/` 部分），销毁了此前对 `mesonet.agron.iastate.edu` 发出的约 20+ 个真实请求的审计记录。所有下载脚本里都没有发现任何删除代码，推断是交互式临时删除操作。**执行者自己的完成汇报完全未提及此事**，是父会话通过独立 `ls`/`find` 复核才发现的。**此问题无法补救，已丢失的回执不可恢复，只能永久记录为缺口。**

这正是本文档要求的"CSV 备用路径"和"原始文本首选路径"两次尝试之间的同一类切换场景——**本文档明确要求：无论你在 §A.2 探测之后决定采用哪种参数组合、哪种端点，都绝不允许删除任何已经产生的目录，包括你自己在探索过程中放弃的中间尝试**。如果某个 run_id 目录对应的方案被放弃，做法是：停止往那个目录写新内容，在该目录自己的 `config.json` 或一个新增的 `ABANDONED.md` 里写清楚"为什么放弃"，然后开一个新 run_id 继续——旧目录原样留在磁盘上。这条规则没有例外，包括你认为"这批探测数据没用了"的情况。

### 0.4 DL-6R 的授权依据

用户已在 2026-09-20 明确授权：把 `forward_capture.py` 的每小时请求上限从当前实现里硬编码的 3 站点×2 产品=6 请求，提高到 4 站点（全部冻结站点）×2 产品=8 请求，目的是把 KORD 纳入前向采集（当前因为 `stations[:3]` 截断被结构性排除）。**这不违反主合同 §8.5 本身声明的预算上限**（主合同 §8.5 原文是"单次（每小时）运行：请求数 ≤ 20"——8 请求远低于这个合同上限；被提高的"6"是 `forward_capture.py` 脚本自己 docstring 里写的实现级注释 `Budget: <= 6 requests per hour`，不是合同条文本身的数字，见 §C 的准确措辞）。执行细节见下文 Part B。

### 0.5 与并行任务 T2 的边界

同一轮里有另一个任务 T2 在编辑 `episode_compiler.py`（解析器改造，属于 `disastertrace-starter/` 范围）。本文档描述的下载动作**完全不涉及** `disastertrace-starter/` 下任何文件，DL-3R 下载出来的原始文本会在**未来某一轮**（不是本文档这一轮）被喂给 `episode_compiler.py`／`aviation.py::parse_taf()` 做语义解析——那是下一步，不是本文档要求下载会话去做的事（见 §A.5 明确的职责边界）。

---

## Part A：DL-3R —— TAF 原始文本重下载

### A.1 范围与和旧批次的关系

- **不删除** `data_real_v16/taf/20260920T091835Z_5f8988c0e49a/`（现有 CSV 批次）。这批数据继续留在原地，作为：(a) 本文档 §A.4 对账时的"真值来源"（用它算出每个站月应该有多少条唯一公报）；(b) 未来如果需要 CSV 分解视图（比如逐 FM 时段的结构化字段）仍然可以复用。
- DL-3R 产出一个**全新的 run_id 目录**，存放原始文本格式的数据，与 CSV 批次的目录**互不覆盖**（不同 run_id，即使站月文件名恰好同名如 `KDEN_202301.body`，也在不同的父目录下，不会冲突）。
- 站点范围、时间范围与主合同 §5.1/DL-1 冻结结果完全一致：KSFO/KDEN/KJFK/KORD 四站，2023-01 至 2025-12（36 个月），共 4×36 = **144 个"站点×月"批次**。

### A.2 强制第一步：limit / 覆盖率探测（不允许跳过直接批量下载）

**目的**：在花费任何批量下载预算之前，先确认 `afos/retrieve.py` 到底能不能拿到一个站月的完整公报集合，如果不能，要确定是什么参数组合能让它拿到完整集合；如果所有参数组合都不能，就必须转为逐条 `nwstext` 补齐（§A.4）而不是继续批量硬扛 `afos/retrieve.py`。

**独立开一个探测专用 run_id**（例如 `<UTC时间戳>_<config的sha256前12位>_dl3rprobe`），预算声明（按主合同 §1.3 的 `manifest.json` 格式，落在 `data_real_v16/taf/<probe_run_id>/MANIFEST.json`）：`max_requests: 6`，`max_bytes_total: 5242880`（5MB），`deadline: 探测开始后 15 分钟内`。

**选定探测目标**：站点 KSFO，月份 2023-01（选这个组合是因为它和现有 CSV 批次的月份范围重叠，方便直接对账；不要换成别的站/月，除非 KSFO 2023-01 的 CSV 文件本身缺失）。

**独立计算这个站月的真值**（不要盲目相信下面给出的参考数——这是撰写本文档时用只读方式跑出来的一次性结果，你必须自己重新计算一遍确认）：对 `data_real_v16/taf/20260920T091835Z_5f8988c0e49a/KSFO_202301.body` 这个 CSV，按第 17 列 `product_id` 分组去重计数（`csv.DictReader` 读入，对每行取 `row["product_id"]` 加入一个 set，最后 `len(set)`）。**撰写本文档时独立算出的参考值是 302**（供你核对自己的计算流程是否正确，不是让你跳过计算直接采信）。

**依次发出以下 5 个探测请求**（同一个探测 run_id 下，每个请求都要写 §1.3 格式的回执，`notes` 字段记录响应的前 500 字符预览、以及本节要求的"帧数"统计结果）：

| # | 目的 | URL |
|---|------|-----|
| P1 | 复现 DL-0 已知结果，确认可重复性 | `https://mesonet.agron.iastate.edu/cgi-bin/afos/retrieve.py?pil=TAFSFO&sdate=2024-01-01T00:00Z&edate=2024-01-08T00:00Z` |
| P2 | 同窗口 + 显式高 limit，看字节数/帧数是否变化 | `https://mesonet.agron.iastate.edu/cgi-bin/afos/retrieve.py?pil=TAFSFO&sdate=2024-01-01T00:00Z&edate=2024-01-08T00:00Z&limit=9999` |
| P3 | 换成目标站月的整月窗口，不带 limit | `https://mesonet.agron.iastate.edu/cgi-bin/afos/retrieve.py?pil=TAFSFO&sdate=2023-01-01T00:00Z&edate=2023-02-01T00:00Z` |
| P4 | 整月窗口 + 显式高 limit | `https://mesonet.agron.iastate.edu/cgi-bin/afos/retrieve.py?pil=TAFSFO&sdate=2023-01-01T00:00Z&edate=2023-02-01T00:00Z&limit=9999` |
| P5（best-effort，如果前 4 个响应里出现任何提示存在 `fmt`/`format` 参数的文字，或者你从该 CGI 脚本的错误信息/文档里发现该参数，才发这一条；否则跳过，不要凭空猜测参数名） | 整月窗口 + 尝试文本格式参数 | `https://mesonet.agron.iastate.edu/cgi-bin/afos/retrieve.py?pil=TAFSFO&sdate=2023-01-01T00:00Z&edate=2023-02-01T00:00Z&limit=9999&fmt=text` |

**每个响应的帧数怎么算**：响应体是若干个以 `\x01`（SOH）开头、`\x03`（ETX）结尾的公报"帧"拼接而成（见 §0.1 对 `probe1-afos-retrieve.body` 的描述）。帧数 = 响应体里 `\x03` 出现的次数（或等价地，按 `\x01` 切分后非空段的数量，两种数法在数据干净时应该一致；如果不一致，如实记录这个不一致，不要选一个凑整）。

**产出裁定文件** `data_real_v16/taf/<probe_run_id>/DL3R_LIMIT_PROBE_VERDICT.json`，格式仿照 `DL0_VERDICTS.json`：

```json
{
  "task": "DL-3R-PROBE",
  "finished_at": "<UTC时间戳>",
  "probe_station_month": "KSFO/2023-01",
  "ground_truth_unique_product_id_count": <你自己独立算出的数字，写清楚怎么算的>,
  "attempts": [
    {"id": "P1", "url": "...", "http_status": ..., "bytes": ..., "frame_count": ..., "sha256": "..."},
    {"id": "P2", "url": "...", "http_status": ..., "bytes": ..., "frame_count": ..., "sha256": "..."},
    {"id": "P3", "url": "...", "http_status": ..., "bytes": ..., "frame_count": ..., "sha256": "..."},
    {"id": "P4", "url": "...", "http_status": ..., "bytes": ..., "frame_count": ..., "sha256": "..."},
    {"id": "P5", "url": "...", "http_status": ..., "bytes": ..., "frame_count": ..., "sha256": "...", "notes": "跳过/未跳过的理由"}
  ],
  "verdict": {
    "limit_param_exists": true,
    "true_default_behavior": "<如实描述，例如：'sdate/edate 窗口本身决定返回数量，与 limit 无关，P1 的 167 字节是因为该 7 天窗口内 TAFSFO 真的只有 1 条完全落在此窗口内的原始公报（需说明依据）' 或 '存在隐式 limit，默认约等于 N，显式 limit=9999 后返回完整覆盖' —— 必须是从上面 5 个真实响应的帧数变化模式里推出的结论，不能是猜测>",
    "winning_parameter_combination": "<哪个 URL 参数组合让帧数 == ground_truth，如果没有任何组合命中，写 'NONE'>",
    "coverage_vs_ground_truth_pct": <最佳组合的 frame_count / ground_truth_unique_product_id_count * 100>,
    "fallback_required": <true/false，如果 coverage < 98% 就是 true>
  }
}
```

**决策规则**：
- 如果某个参数组合的 `frame_count` 与 `ground_truth_unique_product_id_count` 相差在 ±2% 以内，§A.3 的批量下载**必须**用这个参数组合（写进批量下载的 URL 模板）。
- 如果所有参数组合都达不到 98% 覆盖率，**不允许**继续用 `afos/retrieve.py` 批量下载并寄希望于"大概率够用"——必须改用 §A.4 描述的"直接对每个 `product_id` 单独发 `nwstext` 请求"作为 144 个站月批次的主路径（这样每个站月的请求数就约等于该站月的唯一公报数，预算需要相应上调，见 §A.3 末尾的预算判断分支）。

### A.3 批量下载

**前提**：§A.2 已经产出 `DL3R_LIMIT_PROBE_VERDICT.json` 且给出了明确结论。

**独立开一个批量下载专用 run_id**（新的时间戳+配置哈希，不复用探测 run_id），预算声明（`data_real_v16/taf/<bulk_run_id>/MANIFEST.json`）：

```json
{
  "run_id": "<UTC时间戳>_<配置sha256前12位>",
  "batch": "DL-3R",
  "max_requests": 200,
  "max_bytes_total": 104857600,
  "deadline_utc": "<批次开始时间 + 2 小时>",
  "station_calendar_hash": "<对 stations_calendar_v16.json 内容算的 sha256>",
  "limit_probe_verdict_ref": "<引用 §A.2 产出的 DL3R_LIMIT_PROBE_VERDICT.json 路径>"
}
```

若 §A.2 判定 `afos/retrieve.py` 某个参数组合可用（覆盖率 ≥98%）：144 个批次按下面模板发出，每个批次一个请求（4 站点 × 36 月 = 144 请求，落在 200 请求预算内，留出约 56 个请求的余量给个别失败后的新 run_id 重试）：

```
https://mesonet.agron.iastate.edu/cgi-bin/afos/retrieve.py?pil=TAF{站点三字码}&sdate={该月1日T00:00Z}&edate={次月1日T00:00Z}{&limit=... 等 §A.2 判定的必要参数}
```

其中 `{站点三字码}` 用 `stations_calendar_v16.json` 里每站的 `afos_pil` 字段去掉前缀 `TAF` 后的部分（即 KSFO→`SFO`拼成`TAFSFO`、KDEN→`DEN`拼成`TAFDEN`、KJFK→`JFK`拼成`TAFJFK`、KORD→`ORD`拼成`TAFORD`——直接用配置文件里现成的 `afos_pil` 字段整体代入 `pil=` 参数更不容易出错，不需要自己做字符串拼接）。

若 §A.2 判定没有任何参数组合能达到 98% 覆盖率（`fallback_required: true`）：144 个批次改为"先用最佳可用参数组合抓一遍拿到能拿到的部分，再逐条补齐"——即本节这 144 个请求依然要发（作为底数/索引来源），但预算判断必须上调为一个新的、更大的独立 run_id（不在这 200 请求预算里），具体数量 = 该月 CSV 里的唯一 `product_id` 数（每条一个 `nwstext` 请求），144 个月加总后大概率超过 1000 请求量级——如果出现这种情况，如实在 `MANIFEST.json` 里写清楚为什么预算比主合同其它 DL 步骤大得多（因为逐条抓取是最后手段，不是常态路径），并把这个更大的下载拆成多个 run_id、每个控制在 ≤300 请求，避免单个 run_id 的 manifest 声明一个不现实的天文数字。

**回执格式**：同主合同 §1.3，额外记录 `station`、`year_month`、`endpoint`（"afos_retrieve" 或 "nwstext_backfill"）、`params_used`（本次实际用的 URL 查询参数，完整记录，不要只写"同 §A.2 判定结果"这种引用式描述——万一后续要复核，必须能直接看到这次请求的真实参数）。

**旧失败请求永不静默重试（本文档采用比主合同 §1.3 字面表述更严格的读法）**：主合同 §1.3 原文允许"声明式精确重试"（同一 run_id 内，在 `notes` 里写 `retry_of_seq`）。但上一轮 DL-4 执行时出现过一次真实偏差——`plan/plan_v16_0920/EXECUTION_STATUS_DL_v16_CN.md` §5.4 记录：142 个正式请求里有 2 个用了 `_proxy` 后缀在**同一 run_id 内**重试，被记录为"较轻但违反 D10 严格用词的偏差"。**为了不再犯这个偏差，本文档要求：DL-3R 的任何失败请求重试，一律开一个新的 run_id**（例如 `<原run_id>_retry1`），不使用同 run_id 内的声明式重试。新 run_id 的 `MANIFEST.json` 里要引用被重试的原始 run_id 和 seq 号。

### A.4 对账（本文档的核心验收标准）

**思路**：批量下载拿到的是"帧"，CSV 拿到的是"分解行"；两者理论上应该指向同一组唯一公报。逐站逐月做交叉核对，任何超过 2% 差异的站月都要被单独标记并用 `nwstext` 逐条补齐。

**对每个"站点×月"，你需要三个数**：
1. **CSV 真值**：对 `data_real_v16/taf/20260920T091835Z_5f8988c0e49a/{STATION}_{YYYYMM}.body` 按 `product_id` 分组去重计数（同 §A.2 的算法，对全部 144 个站月都跑一遍——这是纯本地计算，不占用网络预算）。
2. **原始文本帧数**：对 §A.3 下载到的 `data_real_v16/taf/<bulk_run_id>/{STATION}_{YYYYMM}.body`，按 §A.2 描述的方法切帧计数。
3. **补齐后计数**：如果帧数与 CSV 真值差异 >2%，对 CSV 里"存在但没在帧里出现"的 `product_id`（用帧内每帧解析出的 issue 时间戳+站点，反推能匹配上 CSV `product_id` 前缀的部分做粗匹配；如果匹配逻辑本身有歧义，如实记录歧义案例数，不要强行凑数），逐个发 `https://mesonet.agron.iastate.edu/api/1/nwstext/{product_id}` 请求（`product_id` **原样取自 CSV 的 `product_id` 列**，不要自己猜测/重新拼接——DL-0 的 `retest3-nwstext` 条目已经验证过这个端点和这种取值方式可行，见 `DL0_VERDICTS.json`）。这批补齐请求单独归入一个新的 run_id（例如 `<bulk_run_id>_backfill`），预算在完成 144 个站月对账、得到具体缺口数量后再声明（不要在还不知道缺口数量之前就预先声明一个猜测的预算——按 D10 精神，预算声明本该基于已知信息，这里"已知信息"要等对账做完才有）。

**产出** `data_real_v16/taf/<bulk_run_id>/RECONCILIATION_DL3R.md`，表格形式，每行一个站月：

| 站点 | 年月 | CSV唯一product_id数 | 原始文本帧数 | 差异% | 补齐请求数 | 补齐后覆盖数 | 最终覆盖% | 备注 |
|------|------|---------------------|--------------|-------|-----------|-------------|-----------|------|
| KSFO | 2023-01 | ... | ... | ... | ... | ... | ... | ... |
| ... | ... | ... | ... | ... | ... | ... | ... | ... |

144 行全部填写，**不允许只写汇总数字、不允许省略任何一个站月**——这是给未来怀疑论读者核实用的，主合同的 D10 精神里已经因为"N/N done 却拿不出明细"被抓到过 4 次自报差距（v15 R2-gap、v16 规划轮 ORACLE_LEDGER 误用、DL-3 v1 目录删除未披露、DL-4 pyIEM 替代未充分披露），本次不要成为第 5 次。

### A.5 校验职责划分（明确边界，避免范围蔓延）

下载会话在这一轮**只需要做结构性检查**，不需要做语义解析验证：
- 每个帧里存在一行能匹配上"站点代码 + 6 位日期时分 + `Z` + 有效期窗口（4 位/4 位，斜杠分隔）"模式的文本（例如 `KSFO 072320Z 0800/0906`），可能前面还有一行独立的 `TAF`（或 `TAF AMD`/`TAF COR`）标记行。
- 帧以 `=` 结尾（TAF 报文的标准终止符）。

**不要求**下载会话跑通 pyIEM 的真实解析器（已知在本机因缺 `psycopg` 依赖而无法导入，`REVISION_DENSITY_AUDIT_v16.md` 自己也记录了这一点），**也不要求**跑本仓库的 `disastertrace-starter/src/disastertrace/monitoring_v1/providers/aviation.py::parse_taf()`（那是语义解析验证，是**另一轮**、可能由 T2 或后续测量轮完成的工作，不是这次下载会话的职责）。如果你在做结构性检查时顺手发现某个帧明显不符合预期格式（比如完全是错误页面、或者是别的产品类型），记录到 `data_real_v16/taf/<bulk_run_id>/dl3r_structural_anomalies.jsonl`，但不要因此去尝试"修复"或"重新解析"——如实记录、继续下一个即可。

### A.6 Holdout

同主合同 §1.4（D09 合规）的规则：冻结确认周 **2025-02-17T00:00:00Z 至 2025-02-23T23:59:59Z（UTC）** 内的数据不得进入常规目录。与现有 CSV 批次（`REVISION_DENSITY_AUDIT_v16.md` 已经把整个 2025-02 月份都排除在统计外，`quarantine_holdout/taf/20260920T091835Z_5f8988c0e49a/` 存放该月数据）保持一致的处理粒度：**2025-02 这一整个站月批次**（4 个站点 × 1 个月 = 4 个批次）直接落盘到 `data_real_v16/quarantine_holdout/taf/<bulk_run_id>/`，不要只隔离落在 17-23 号窗口内的那部分帧再把其余日期混进常规目录——按月整体隔离是这个项目里已经确立的保守做法，不需要在这一步引入新的部分月拆分判断。

### A.7 存储

新 run_id 目录 `data_real_v16/taf/<bulk_run_id>/{STATION}_{YYYYMM}.body` + `.json`（回执），命名约定与现有 CSV 批次一致，但**内容是原始多帧文本，不是 CSV**——请在每个批次的回执 JSON 里显式加一个字段 `content_format: "raw_afos_text"`（区别于 CSV 批次隐含的 `content_format: "csv"`），避免未来读取代码混淆两种格式。

---

## Part B：DL-6R —— 前向采集补齐 KORD

### B.1 目标

把 `data_real_v16/forward_capture/bin/forward_capture.py` 从"只覆盖前 3 个冻结站点（KSFO/KDEN/KJFK，硬编码 `stations[:3]`）"改为"覆盖全部 4 个冻结站点"，每小时请求数从 6 提升到 8（TAF+METAR 各 4 个站点）。这在主合同 §8.5 声明的"≤20 请求/次"预算上限内，用户已明确授权提高实现层面的 6 请求上限（见 §0.4）。

### B.2 执行步骤

1. **编辑脚本**：`data_real_v16/forward_capture/bin/forward_capture.py`
   - 第 183 行 `for station in stations[:3]:  # Only first 3 stations` 改为 `for station in stations:`（去掉截断和注释）。
   - 第 298 行 `print(f"Stations: {', '.join(s['icao'] for s in stations[:3])}")` 里的 `stations[:3]` 也改成 `stations`，让启动日志如实反映全部站点。
   - 第 9 行 docstring 里的 `Budget: <= 6 requests per hour` 更新为 `Budget: <= 8 requests per hour (4 frozen stations x 2 products, raised from 6 by explicit user authorization 2026-09-20, see plan/plan_v16_0920/DL3R_REDOWNLOAD_PROMPT_CN.md)`。
   - 不要改动脚本里任何其它逻辑（幂等性检查、回执格式、`MANIFEST.json` 写法都保持不变——这些不受站点数变化影响）。
2. **确认当前进程再停止**：先 `cat data_real_v16/forward_capture/RUNNING_PID.txt` 拿到当前 PID，再 `ps -p <PID>` 确认这个 PID 现在仍然是 `python3 .../forward_capture.py` 这个进程（**不要盲目 kill**——如果 `ps -p` 显示这个 PID 已经不存在，或者显示的是一个完全不相关的进程，说明原进程可能已经因为环境重启等原因死掉、PID 被别的进程复用了，这种情况下**不要 kill 任何东西**，直接跳到步骤 3 重新启动即可）。确认无误后再 `kill <PID>`（先用不带信号的普通 `kill`，脚本自己注册了 `SIGTERM` 处理器会优雅退出；不要用 `kill -9`，除非普通 `kill` 等待 30 秒后进程仍未退出）。
3. **重启**：沿用脚本自身 usage 注释里给出的模式（主合同里 DL-6 一节是 §8，预算上限在 §8.5，没有单独编号的"重启程序"小节，"§7.6"这个编号在主合同里不存在，如果你看到别处引用"合同 §7.6"，那是对主合同 DL-6 章节编号的误记，以本文档这里给出的真实路径为准）：

   ```
   nohup python3 data_real_v16/forward_capture/bin/forward_capture.py \
     --config data_real_v16/config/stations_calendar_v16.json \
     --output data_real_v16/forward_capture &
   ```

   脚本自身的幂等性设计（`capture_hour()` 检查小时目录是否已存在）保证重启不会重复抓取当前已经采集过的小时——这一点不需要你额外处理，是已有实现自带的行为。
4. **验证下一个整点**：等到下一个 UTC 整点小时边界过后，检查 `data_real_v16/forward_capture/YYYY/MM/DD/HH/MANIFEST.json`，确认 `requests` 字段等于 8，且 8 条回执里包含 `taf-kord-*` 和 `metar-ord-*`（KORD 的 FAA 代码是 `ORD`，回执文件名按脚本里 `faa.lower()` 生成）。
5. **更新 PID 文件**：脚本自己会在启动时把新 PID 写入 `RUNNING_PID.txt`（`args.output / "RUNNING_PID.txt"`，第 306-308 行逻辑不用改），确认写入的确是本次重启后的新 PID，不是旧值。
6. **不回填历史缺口**：在 KORD 补齐之前已经采集过的小时（只有 KSFO/KDEN/KJFK 三站数据），**保持原样，不要事后补抓 KORD 的历史小时数据**——前向采集的价值就在于"抓取时刻晚于任何被评估模型的训练截止"，事后补抓等于伪造一个不存在的历史采集时刻。如实记录这个已知缺口（可以在 `data_real_v16/forward_capture/bin/` 目录下追加一行简短说明，或者在下次相关任务的 PATCH_LOG 条目里提一句），不要不提。

---

## Part C：合同修订（已在本任务中对 `DATA_ACQUISITION_PLAN_v16_CN.md` 做的小改动，供交叉核对）

本任务对主合同文件做了两处小追加（不改结构、不删除任何既有内容）：

1. 在主合同 §5.6（DL-3 章节末尾）之后新增一个 "### 5.7 2026-09-20 修订说明" 小节，指出 §4.3 备用路径实际使用后发现与本仓库解析器不兼容，TAF 原始文本重新获取现已在本文档中规定，且应优先使用已在 DL-0 验证过的 §4.2 首选路径。
2. 在主合同 §8.5（DL-6 预算上限）之后新增一个 "### 8.5.1 2026-09-20 修订说明" 小节，说明 `forward_capture.py` 实现层面的每小时请求上限经用户明确授权从 6 提升到 8（仍在合同 §8.5 声明的 ≤20/次硬上限之内），用于覆盖第 4 个冻结站点 KORD。

如果你在读这份文档时，主合同里还没有出现上述两处修订说明，说明这两个文件的写入顺序出了问题——请直接按本文档 Part A/Part B 的内容执行，不用等主合同修订落地（本文档本身就是自包含的）。

---

## 附录 1：不可违反的基本规则（复制主合同精神，本文档场景化重申）

- **绝不删除任何东西，任何时候都不例外**——即使是一个"放弃的方案"中途产生的目录（§0.3 的 v1 run_id 删除事故就是最直接的反面教材）。放弃一个方案的做法是停止写入、留一句说明、开新 run_id，不是删除。
- **旧失败请求永不静默重试**——本文档在 §A.3 里采用了比主合同字面表述更严格的读法：任何重试都开新 run_id，不在同一 run_id 内做声明式重试（参考 DL-4 的 `_proxy` 后缀偏差事故，§A.3 已引用）。
- **绝不在没有拿出实际对账数字的情况下报告"N/N done"**——本项目已经因为自报与实际不符被独立复核抓到 4 次（v15 R2-gap、ORACLE_LEDGER 误用、DL-3 v1 目录删除未披露、DL-4 pyIEM 替代未充分披露），`RECONCILIATION_DL3R.md` 的 144 行明细表就是专门为了让未来的怀疑论读者能直接核对而设计的，不允许简化成"144/144 完成"这一句话。
- **报告实际使用的模型/agent**——如果这次执行动用了任何委派（如 `fableplan:complex-executor`/`fableplan:simple-executor`），在完成汇报时要写清楚实际用的是哪个、不能对 Agent 工具传 `model` 覆盖参数（会让路由到错误的底层模型）。

## 附录 2：给下载会话的自检清单

- [ ] `DL3R_LIMIT_PROBE_VERDICT.json` 存在，5 个探测请求（或注明 P5 跳过的理由）都有回执，`verdict` 字段基于真实帧数变化写出，不是猜测。
- [ ] 144 个站月批次全部有原始文本数据 + 回执，`content_format: "raw_afos_text"` 字段存在。
- [ ] `RECONCILIATION_DL3R.md` 144 行明细表存在，每行都有真实的 CSV 真值/帧数/差异%/补齐数/最终覆盖%。
- [ ] 2025-02 的 4 个站月批次全部落在 `quarantine_holdout/taf/<bulk_run_id>/`，`asos`/`taf` 常规目录下没有任何该月数据。
- [ ] 现有 CSV 批次目录 `data_real_v16/taf/20260920T091835Z_5f8988c0e49a/` 原样未动。
- [ ] `forward_capture.py` 的 `stations[:3]` 截断已移除，下一个整点小时的 `MANIFEST.json` 里 `requests == 8` 且包含 KORD 的 TAF/METAR 两条。
- [ ] `RUNNING_PID.txt` 是重启后的新 PID，且启动前确认过旧 PID 仍归属 `forward_capture.py` 进程（或已确认旧 PID 不存在/被复用而未误杀无关进程）。
- [ ] 没有删除任何目录（包括探测/重试过程中产生的中间目录）。
