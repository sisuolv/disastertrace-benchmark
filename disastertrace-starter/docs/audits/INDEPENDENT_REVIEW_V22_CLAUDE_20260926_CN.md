# DisasterTrace：对 v22 计划与当前实现的独立复查（Claude Code，2026-09-26）

## 元信息

| 项 | 内容 |
|---|---|
| 审查者 | Claude Code（Opus 5.5）主会话 + 4 个并行只读核查子代理（代码契约/测试、真实数据/标签/统计、计划追溯、合成 GPU 实验） |
| 对照计划 | `plan/plans_v22_0925`（仓库内副本：[`packages/CHATGPT_PRO_REVIEW_AND_CODEX_PLAN_V22_20260925.zip`](packages/CHATGPT_PRO_REVIEW_AND_CODEX_PLAN_V22_20260925.zip)，即含 `TASKS.json` 的大包） |
| 审查代码 | 分支 `codex/v18-repaired-release-20260923`，审查时 HEAD `ab4b1e324`；代码与 `8a6e2162c`（v21 release）完全相同。之后的 `7c0bd456b` 只增加文档 |
| 方法 | `git archive HEAD` 干净副本上跑测试与反例；从原始 TAF/ASOS 独立重建开发集和标签；用解析式核对全部 GPU cell；逐项追溯 v22 `TASKS.json` |
| 读取边界 | 只读 2025-01、2025-03 开发读集（KDEN/KJFK/KORD/KSFO）；未读 holdout、quarantine 或任何 2025-02 数据；无 provider 调用、无 GPU 作业；仓库本身零修改（本文件与索引除外） |
| 证据标签 | **VERIFIED**＝本轮实际运行/计算；**STATIC**＝读代码确认；**REPORTED_ONLY**＝仅来自他人文档，本轮未复算 |
| 复现脚本 | [`claude_review_20260926/`](claude_review_20260926/)（含硬编码本机路径；数据脚本需要仓库外的 `data_real_v16`） |

## 与 Codex 两份报告的关系

- Codex 报告：[`INDEPENDENT_REVIEW_V22_PLAN_20260926_CN.md`](INDEPENDENT_REVIEW_V22_PLAN_20260926_CN.md)（v22 计划复核）与 [`INDEPENDENT_REVIEW_V21_20260926_CN.md`](INDEPENDENT_REVIEW_V21_20260926_CN.md)（v21 实现复查）。
- **一致之处**：Codex 列出的 public-schedule 重复检索、`delay(None)`、真实评分不是内容依赖 follow-up、样本全在 1 月且 22/2、合成优势来自生成器、发布快照与复现不闭合——本轮在干净副本上**全部实测复现**。
- **本报告新增的关键发现**（Codex 报告中没有）：
  1. 真实开发集每个检查点**最多只有 1 个可见来源**，选择器打平是构造必然，不是"active 无效"的证据（§2.1）。
  2. 根因是构建脚本按 UTC 签发日分组，且目标窗口起点被锚在第二份 TAF 的签发时刻（§2.1）。
  3. TAF 规则的 Brier **比样本内气候态和常数 0 都差**（§2.2）。
  4. 合成 GPU 两个曲面都有精确闭式解；shared-delay 的 "active" 根本不自适应，其 FINDINGS 的归因是错的（§2.3）。
  5. 干净克隆下 226 项里 16 项失败（`configs/closed_run_ids.json` 从未提交）；合成评分器不评策略的 UPDATE；执行快照与发布代码有 1 个文件不一致（§2.4–2.5）。
  6. v22 计划被交给了 EarthDelta 执行会话（记录了 `PLAN_SCOPE_MISMATCH`），因此 **17 个任务零执行**（§1）。
- **判定差异**：Codex 把 P0-00/01/04/06 记为"部分完成"，是把 v22 之前已存在的代码能力算进去；本报告按 v22 任务自身的交付物与验收标准判定，记为"未开始"。两种口径都成立，阅读时请区分。
- **小更正**：Codex v22-plan 报告写"`ab4b1e324` 只增加审计文档和计划包"，实际计划包是在 `7c0bd456b` 加入的。

---

## 结论先行

**当前项目做到哪里**：离线工程已达到"可复现、可审计的回放"——TAF 解析、ASOS 标签绑定、24 个开发目标的构建都能从原始数据逐字节重建。但最新的 v22 计划 17 个任务**一个都没有执行**。

**哪里有问题**：唯一的真实数据实验在设计上无法检验研究假设；合成 GPU 实验的优势是写进生成器的；Natural 协议有多处契约缺陷；干净克隆不能完整复现。

**哪些结论可信**：数据管线与标签在声明规则下正确；"读 TAF 优于 0.5 先验"成立（但没有研究意义）；GPU 数值正确实现了指定生成过程。

**哪些仍未证明**：主动取证（C1）、修订跟踪、轨迹评价、修复→预测损失（C2）、泛化（C3）、LLM/provider 价值。当前真实结果连"TAF 规则优于气候态"都不成立。

**顺序**：先重建有真实选择空间的开发集 → 用强基线加"事后最优上限"判断 C1 值不值得做 → 只修这一步需要的契约和复现 → 更正结论 → 最后才考虑 provider 试验。

---

## 1. 计划执行情况

### 1.1 v22 计划：17 个任务全部未开始（VERIFIED）

v22 计划写于 2026-09-25 约 12:48 UTC。此后仓库只有两个纯文档提交（`ab4b1e324`、`7c0bd456b`），计划中提出的 11 个新文件（如 `tests/test_v21_review_regressions.py`、`tests/test_v21_provider_faults.py`）均不存在，也没有任何 `P0-xx/IMPLEMENTATION.md` 审查目录。

| 任务 | 状态 | 当前 HEAD 上的证据 |
|---|---|---|
| P0-00 绑定版本/计划 | 未开始 | 没有审查目录或逐项映射 |
| P0-01 修复现入口 | 未开始 | [`REPRODUCE.md:43-44`](../../artifacts/v21_execution_20260925_04/REPRODUCE.md#L43-L44) 把 bridge 文件传给评分脚本，[`run_v21_real_dev_deterministic_score.py:89`](../../scripts/run_v21_real_dev_deterministic_score.py#L89) 读 `source["episodes"]`，实测 `KeyError: 'episodes'` |
| P0-02 目标/ASOS 政策 | 未开始 | binder 仍取"窗口内首条有效观测"（[`bind_v21_dev_asos_outcomes.py:114`](../../scripts/bind_v21_dev_asos_outcomes.py#L114)），而 bridge 声明的是"terminal observation"（[`run_v21_real_dev_source_bridge.py:33`](../../scripts/run_v21_real_dev_source_bridge.py#L33)），口径自相矛盾 |
| P0-03 共同网格 | 未开始 | [`grid_scoring_v18.py:183-191`](../../src/disastertrace/monitoring_v1/grid_scoring_v18.py#L183-L191)：某方法整体缺席时仍判为可比（实测） |
| P0-04 证据语义 | 未开始 | A-B-A 同到达时间冲突被接受（[`evidence_qualification_v18.py:406-450`](../../src/disastertrace/monitoring_v1/evidence_qualification_v18.py#L406-L450)，实测） |
| P0-05 Natural 推进 | 未开始 | 未来公开排程来源导致无限重复检索（实测，见 §2.4） |
| P0-06 干预 | 未开始 | [`interventions_v18.py:502`](../../src/disastertrace/monitoring_v1/interventions_v18.py#L502) 仍为 `(available_at or 0) + 86_400_000_000` |
| P0-07 provider gate | 未开始 | `configs/closed_run_ids.json` 从未提交到任何分支，干净克隆 16 个测试失败 |
| P1-00 至 P3-01 | 未开始 | P1-02、P2-01、P2-02、P3-01 另受 D1/Y1/P1/L1/L2/H2 授权门限制 |

**为什么没执行**：`plans_v22_0925` 被交给了一个 EarthDelta 执行会话，它在 `earthdelta_autonomous_10h_20260925T171247Z/TASK_STATUS.json` 里记录 `PLAN_SCOPE_MISMATCH`，随后只做了 EarthDelta 的工作。`plans_v22_0925` 里的 `EARTHDELTA_*.md` 和 8 个 `earthdelta_*` 目录属于另一个项目（远端 `sisuolv/EarthDelta`），没有触碰本仓库（VERIFIED）。

**计划包版本歧义**：`plans_v22_0925` 里有两个同名 zip。只有大包（96 KB）含 `TASKS.json`；小包（30 KB）的 P0-01 至 P0-07 含义不同（例如其 P0-01 是单位/TAF 语义，P0-06 是 provider adapter）。仓库内 `docs/audits/packages/` 存的是大包，建议正式指定它为唯一版本。

### 1.2 v21 执行包（上一版）：自报偏乐观

按交付物核对（VERIFIED）：5 项最小完成、11 项部分完成、5 项未开始、1 项偏离（E-02 原定单设置 CPU 预演，实际扩成约 24 个 GPU 作业）。执行包点名的约 33 个交付文件中只找到 2 个。自报状态为 7 PASS_SCOPED / 11 PARTIAL / 3 NOT_STARTED / 1 BLOCKED（REPORTED_ONLY）。

授权记录缺口：`_04` 读了原始数据与 ASOS outcome 并运行 GPU，但 A-00 起始收据写明"仅合成，另需授权"；执行目录中未找到授权记录（可能在对话中口头授权，无法核验）。

### 1.3 研究目标层面

- **C1 主动取证**：只有合成证据；真实数据上无法检验（§2.1）。
- **C2 机制归因**：只有时序/状态类干预；"取证失败""匹配失败"（C2-1/C2-2）零实现。
- **C3 泛化**：未开始；v21 代码不引用多模态、水文或多目标模块。
- **v18 原计划 7.1–7.4 四组论文实验**：均未以 LLM + 真实 outcome 运行。
- **研究决策 D01–D12**：D02（H15 单领域）、D03（T-60/40/20）、D09（代码层 holdout 守卫）被遵守；D08（CI）、D11（LAMP 基线）、D02 的 routine 报文目标、D10（预算/授权收据）未遵守。

### 1.4 两条代码线分叉（VERIFIED）

- v14→v17 线（`v16-*`、`v17-batch-a-v1`、PR #1–#3）不是当前 HEAD 的祖先，分叉点是 9/8 的 `36082c42a`。PR #1–#3 仍开着，`origin/main` 停在 9/7 的 `a23f73a`。
- `src/disastertrace/revision_v1/` 是整体拷贝进来的：`belief_commit`、`trap_policies`、`metrics`（轨迹 Q）、`lamp_categorical`、`p1_harness`、`manifest`、`pilot_v17` 在当前线没有调用方；对应的 `test_revision_*` 测试没带过来。
- v16 冻结的 episode 清单（12 目标 × 3 检查点）、LAMP registry、BASE0 基线都不在当前线；v21 的 24 目标名册是替换而不是延续。
- **与缺陷直接相关**：v16 专门重下载的原始文本 TAF 批次 `*_dl3rbulk` 未被使用；v21 构建脚本读的是 CSV 批次，而 CSV 的基础组把起始时间记成签发时间——这正是 §2.1 目标锚定问题的来源。

---

## 2. 发现的问题

### 2.1 真实开发集在结构上无法检验任何主动或修订假设（最关键；VERIFIED）

1. **选择空间为零**。[`REAL_DEV_DETERMINISTIC_SCORE.json`](../../artifacts/v21_execution_20260925_04/REAL_DEV_DETERMINISTIC_SCORE.json) 的 72 个检查点中，可见来源数 65 个为 1、7 个为 0；earliest、hash、active_age 在 72/72 个检查点选中同一来源。"active 与对照打平"是恒等式，不是实验结论；它既不能证实也不能否证主动取证。
2. **原因一：按 UTC 签发日分组**。[`build_v18_dev_episodes.py:402-437`](../../scripts/build_v18_dev_episodes.py#L402-L437) 以"站点 + UTC 签发日"分组，前一天签发、此刻仍生效的 TAF 被排除。原始档案中每个检查点实际生效的 TAF **中位数为 6 份**（分布 1–11）。7 个回退到 0.5 的检查点全部是漏掉了前一天签发的在效 TAF（如 KJFK-01-04 漏掉 `202501032330-KOKX`）；补上后 TAF 规则 Brier 从 0.1104 降到 0.0900。
3. **原因二：目标窗口锚在第二份 TAF 的签发时刻**。IEM CSV 把 TAF 基础组的 `fx_valid` 记为签发时间，[`build_v18_dev_episodes.py:314`](../../scripts/build_v18_dev_episodes.py#L314) 以此作为产品 `valid_start`，配对规则（[`:414-424`](../../scripts/build_v18_dev_episodes.py#L414-L424)）因此总把目标起点放在第二份 TAF 的签发时刻。结果 24/24 个 episode 的第二个来源在所有检查点都不可见；截断前候选池 241 个 episode 全部恰好 2 个来源、最多 1 个可见。
4. **没有修订动态**。检查点只跨 40 分钟（T-60 到 T-20），仅 3/24 个 episode 在窗口内有新 TAF 到达，且都不改变答案。适应/稳定、轨迹与终点对比、修订跟踪都测不了。
5. **样本问题**。24 个目标全在 2025-01-01 至 01-06（round-robin 取每站前 6 天），15 个在 05Z，没有 3 月；[`V21_RELEASE_20260925.md`](../V21_RELEASE_20260925.md) 写的 "January/March" 不实。
6. **原始数据缺陷**。`data_real_v16/taf/20260920T091835Z_5f8988c0e49a/KJFK_202503.body` 截断在 03-24 11:23（同目录 `_proxy.body` 完整）；ASOS 月文件都缺 31 日（IEM 结束日参数不含当天）。

### 2.2 真实结果的解读有误（VERIFIED）

- 24/24 标签复现正确；换成"窗口内任意观测""窗口最小值""仅 routine 报文"等替代定义都不翻转。
- 但 TAF 规则比气候态更差：

| 方法 | Brier（72 格） |
|---|---|
| 固定 0.5 | 0.2500 |
| TAF 规则（0.8/0.2 映射，earliest/hash/active 相同） | 0.1104 |
| TAF 规则（补齐 7 个漏掉的在效 TAF） | 0.0900 |
| 常数 0 | 0.0833 |
| 样本内基准率 2/24 | 0.0764 |
| 开发月站点气候态（样本内） | 0.0764 |

- 以 episode 为簇 bootstrap（1 万次，seed 20260926）：TAF − 0.5 = −0.140，95% CI [−0.198, −0.066]；TAF − 气候态 = +0.034，CI [−0.092, +0.149]；active − 最佳非 active 在每次重采样中都恰为 0。
- TAF 判别本身没问题（episode 级：报 0.8 的 4 个中 2 命中、2 误报；报 0.2 的 19 个全为负；无漏报），问题是 0.8/0.2 映射对 8% 的基准率严重失准。
- **口径不一致**：概率取所有重叠时段（含 TEMPO/PROB）的最小下界，表达"窗口内任意时刻"；标签是单条首观测。若只用 prevailing 时段，KDEN-01-04 与 KORD-01-06 的概率会变。

### 2.3 合成 GPU 实验的优势是写进生成器的（VERIFIED）

- **cost-matched**（[`run_v21_cost_matched_adaptive_surface.py:50-61`](../../scripts/run_v21_cost_matched_adaptive_surface.py#L50-L61)）：active 直接写死生成器的路由表（第 60 行）；F 只用最后一个信号，丢掉初始观测；"rr" 永远查 q1、"hash" 永远查 q2。相对等成本对照的优势恰为 −a(2p−1)(h−l)/2，384 格全部为负；GPU 结果与解析值最大偏差 1.13e-3（最大 z = 3.86 / 4608 次比较，纯 MC 噪声）。
- **"816 wins"**：比较对象是在不同成本参照中事后取最小，包含 0 次查询的 fixed 与 1 次查询的 no_extra；816 = 768 个解析胜出 + 48 个被噪声分走的平局；全部 336 次失利都输给只查 1 次的 no_extra。
- **shared-delay**：其 "active" 没有自适应成分——p=0.65 时与 hash 逐位相同（216/216），d=0 时与 no_extra 相同（108/108）；期望上 E[rr]=E[active]，解析结果 0 胜 / 96 平 / 48 负，报告的 31 胜是噪声。`SHARED_DELAY_FINDINGS.md` 说差距主要来自 source_rr，**这是错的**：差距来自概率映射的校准差异。
- 每个 GPU 作业计算 0.3–0.55 秒；CPU 上用解析式算完 384 格只需约 8 毫秒。

### 2.4 协议契约缺陷（干净副本实测全部复现）

| 缺陷 | 位置 | 实测 |
|---|---|---|
| 未来公开排程来源无限重复检索 | [`natural_track_v18.py:201-209`](../../src/disastertrace/monitoring_v1/natural_track_v18.py#L201-L209)、[`:253-260`](../../src/disastertrace/monitoring_v1/natural_track_v18.py#L253-L260)；[`natural_selector_policy_v21.py:129-133`](../../src/disastertrace/monitoring_v1/natural_selector_policy_v21.py#L129-L133)；[`active_policy_v21.py:54-74`](../../src/disastertrace/monitoring_v1/active_policy_v21.py#L54-L74) | 20 步内 RETRIEVE 20 次，时钟不动、`read` 为空；预算按成功读取数计永不触发；两个策略都没有 WAIT 分支；触顶只抛异常、不产生评分记录 |
| NaturalKernel 时钟/预测/deadline | [`natural_track_v18.py:214-251`](../../src/disastertrace/monitoring_v1/natural_track_v18.py#L214-L251) | 只有 WAIT 推进时钟；UPDATE 不保存生效预测；目标 [100,200)、deadline=300 时窗口内仍可提交；1000 次 UPDATE 照收 |
| 合成评分器不评策略的 UPDATE | [`synthetic_natural_v21.py:75-76`](../../src/disastertrace/monitoring_v1/synthetic_natural_v21.py#L75-L76) | 用最后读到的内容重算概率，被评分的不是策略提交的预测 |
| 共同分母检查过宽 | [`grid_scoring_v18.py:166`](../../src/disastertrace/monitoring_v1/grid_scoring_v18.py#L166)、[`:183-191`](../../src/disastertrace/monitoring_v1/grid_scoring_v18.py#L183-L191) | A 只有 m1、B 只有 m2 仍 `comparison_eligible=True`，且方法被混成一个分数；测试里只有断言 True 的用例 |
| 句柄重命名不变性不成立 | [`active_policy_v21.py`](../../src/disastertrace/monitoring_v1/active_policy_v21.py)；[`tests/test_v21_natural_active.py:60-65`](../../tests/test_v21_natural_active.py#L60-L65) | 测试只把前缀 q 换成 z（保持字典序）；同角色换成 a/z/b 后输出 0.8→0.2 |
| bridge 与 scorer 口径不一 | [`run_v21_real_dev_source_bridge.py:44-52`](../../scripts/run_v21_real_dev_source_bridge.py#L44-L52) vs [`run_v21_real_dev_deterministic_score.py:28-47`](../../scripts/run_v21_real_dev_deterministic_score.py#L28-L47) | bridge 只取 `periods[0]`；真实数据 144 个 projection 中 6 个两者不一致 |
| delay(None) | [`interventions_v18.py:502`](../../src/disastertrace/monitoring_v1/interventions_v18.py#L502) | 小时间戳（测试夹具）下把"未知"静默变成"一天后"；真实微秒时间戳下直接报错。两种都是缺陷，但对真实数据是"响亮失败"而非静默污染 |
| 硬编码计数 | [`natural_synthetic_score_v21.py:147`](../../src/disastertrace/monitoring_v1/natural_synthetic_score_v21.py#L147) | `"fixed_invalid_cells": 3` 是常量而非计数 |

### 2.5 复现与发布（VERIFIED）

- 干净克隆跑发布命令（v17–v21 测试）：**16 失败 / 210 通过**，失败全部是 `FileNotFoundError: configs/closed_run_ids.json`（[`run_v18_controlled_api.py:26`](../../scripts/run_v18_controlled_api.py#L26) 依赖它，docstring 却称其"Git-tracked"）。补上该文件后 226 全过。
- 全量收集：2946 项、87 个错误（71 个来自 `artifacts/` 下重复测试文件名，12 个来自缺失的 untracked 脚本，4 个来自可选依赖 PIL/shapely/shapefile）；`pyproject.toml` 未设 `testpaths`。
- `REPRODUCE.md` 的评分命令 KeyError；改用 `G1_DEV_EPISODES_V3.json` 作输入后，输出与发布 JSON **逐字节一致**；bridge 重跑也逐字节一致。
- 6 个 `run_v21_*` 脚本 `import torch`，但 `pyproject.toml` 未声明；文档中的 CPU smoke 命令因此失败。
- [`SNAPSHOT_MANIFEST_V4.json`](../../artifacts/v21_execution_20260925_04/SNAPSHOT_MANIFEST_V4.json) 中 `natural_selector_policy_v21.py` 的哈希与 HEAD 不符（执行后又改过并提交于 `8a6e2162c`）；bridge 输出仍能逐字节复现，属于溯源缺口。
- 工作区有 631 个 untracked 路径，其中只有 `configs/closed_run_ids.json` 被已提交代码依赖。

### 2.6 过程风险（VERIFIED，计数为近似）

- 9/19 至 9/26 共 8 天：9 个计划版本、约 40 个计划/审查文件、至少 12 次审查、约 19 轮执行；同期**对真实 outcome 打分的 LLM 预测为 0 条**（v18 的 provider 运行 108 次尝试中 6 次有效，且都不含 outcome）。
- 同一批缺陷（delay、重复检索、A-B-A）在 v21 被标为 PASS_SCOPED/PARTIAL，v22 又原样列出——项目卡在"审查→修补"循环。
- 旧线上的负面信号未被纳入决策：早期 M01 实验中 LLM 选源 Brier 0.004915，hash 0.004859，round-robin 0.004866，仅 3 个正例（REPORTED_ONLY，出自旧 AI 审计报告，本轮未复算）。

---

## 3. 结果是否支持当前研究结论

| 结论 | 判断 |
|---|---|
| TAF 管线、单位、标签、构建可复现 | **可信**（VERIFIED） |
| actor 代码路径不接触 outcome；builder/binder 有 holdout 守卫 | **可信**（只证明代码路径，不能审计全部历史访问） |
| GPU 数值正确实现了指定生成过程 | **可信**（只能算实现层正控制） |
| "读 TAF 比 0.5 先验好" | 成立但没有意义 |
| TAF 规则有超过气候态的技巧 | **不成立**（点估计更差，CI 跨 0） |
| active 在真实数据上"没有优势" | **测不出**：选择空间为零，既不能证实也不能否证 |
| content-dependent follow-up 优于等成本对照 | **未证明**：优势来自 oracle 路由 |
| shared-delay 的 FINDINGS 归因 | **错误** |
| 修订跟踪、适应/稳定、轨迹评价、修复→损失、C3、LLM 价值 | **均未检验** |

测试通过只说明代码按写的方式运行，不代表科学假设成立。当前没有任何一项证据支持"主动获取天气证据能改善风险判断"。

---

## 4–5. 问题优先级与解决方法

| 优先级 | 问题 | 解决方法 |
|---|---|---|
| **P0-1** | 真实开发集没有选择空间、没有修订动态 | 改用原始文本 TAF（`*_dl3rbulk`）解析真实有效期；来源集合＝检查点时刻所有在效产品（不按签发日分组）；目标放在不依赖签发时刻的固定网格上，只按来源侧条件分层、不看 Y；检查点延长到 T-6h/-3h/-1h/-20m；覆盖 1 月与 3 月全部日期；补齐 KJFK 3 月（用 `_proxy`）与 31 日 |
| **P0-2** | 基线弱、映射失准、口径不一致、没有 CI | 冻结唯一 OutcomePolicy，事件定义与预测口径一致；基线：气候态、常数、最新 TAF（映射在训练月校准）、METAR 持续性、LAMP、简单叠加统计 F；指标用 BSS（相对气候态）与按事件簇的 CI（1 月+3 月约 46 个独立事件簇） |
| **P0-3** | 合成证据被误读为机制支持 | claim 表与发布文档改称"实现正控制"；更正 shared-delay 结论；把闭式解写成单元测试（相当于关闭 P1-00）；停止 GPU |
| **P1-1** | Natural 契约缺陷（§2.4 全部） | 先写失败测试再修：预算按尝试次数计；不可用时 WAIT/STOP；保存并评分生效预测；deadline 必须早于 target_start；按完整名册判断可比；任意 ID 置换不变性；delay(None) 返回 N/A |
| **P1-2** | 干净克隆不可复现 | 提交 `closed_run_ids.json` 或使其可选；修 REPRODUCE；加 torch 可选依赖；`testpaths=tests`；补以当前 HEAD 为基准的发布清单 |
| **P1-3** | 文档与 claim 不实 | 删 "January/March"；写明打平是结构性的；把 816 拆开说明 |
| **P2-1** | 代码线分叉、死代码、PR 与 main 失效 | 决定 `revision_v1`、v16 清单、LAMP registry 是移植还是正式退役；关闭或重建 PR |
| **P2-2** | 过程循环、计划送错项目、授权记录缺失 | T1/T2 产出数据前不再开新审查包；每轮执行前写授权收据；EarthDelta 产物移出 DisasterTrace 计划目录（需研究者确认） |

**对 v22 计划本身的评价**：证据纪律与缺陷清单基本正确，但需调整三处——
1. **顺序**：8 个 P0 工程任务排在"选择空间核查"（P1-02）之前。既然已确认选择空间为零，照原序做完 P0 只会把协议修好去服务一个测不出东西的实验。
2. **provider 试验**：P2-01 预设的"12 个开发目标"若沿用现名册，provider 调用必然浪费。
3. **漏项**：未覆盖按签发日分组、目标锚定签发时刻、CSV 有效期丢失、数据截断、口径不一致、映射失准。

---

## 6. 下一阶段计划（按顺序；等待研究者审核，尚未执行）

**T1 重建真实开发集**（v22 P1-02 提前，合入 P0-04 数据部分；需 D1 授权读原始 TAF 文本，读集仍为 1 月与 3 月）
- 解决：§2.1 的选择空间为零与无修订动态。
- 成功：构建全程不读 Y，冻结哈希后才绑定 Y；每个检查点合法来源数中位数 ≥ 2；≥ 15% 的检查点各合法来源对事件判断不一致（原始数据中约 407 个这样的小时）；≥ 30% 的 episode 在检查点之间有新产品到达。
- 失败：判断不一致的检查点不足约 40 个独立事件簇 → 单靠 TAF 撑不起 C1，需加入 LAMP/METAR 来源或重新定义 C1（注意 LAMP 只下载了 00/06/12/18Z 四个周期，只覆盖一半小时）。

**T2 强基线 + 事后最优上限判决门**（合入 P0-02 与 P1-02 基线部分；C1 的 go/no-go；纯 CPU、确定性）
- 解决：主动选源到底还有没有提升空间。在 T1 名册上计算各基线，及"事后从合法来源中挑最好一个"的 oracle 相对"总用最新 TAF"的差距。参考：T-60 时最新 TAF 能抓住 311 个正例中的 239 个，METAR 持续性抓住 227 个——20–60 分钟提前量下持续性本身就很强。
- 成功：最佳基线相对气候态 BSS > 0 且 CI 不含 0；oracle 相对最佳非自适应基线的提升 ≥ δ（建议 δ = 0.005 Brier，由研究者冻结）且 CI 不含 0。
- 失败：提升 < δ → 任何选源策略都赢不了，停止 C1 在该领域的投入，转向更长提前量或调整定位。
- 注意：气候态用 2023–2024（需另授权）或 1 月/3 月交叉拟合，不能用同批样本。

**T3 只修 T2/T5 需要的契约 + 干净克隆可复现**（v22 P0-01、P0-03、P0-05；与 T1/T2 改动文件不重叠，可并行）
- 成功：§2.4 每个反例先写成失败测试、修复后通过；`git archive` 干净副本 100% 通过；REPRODUCE 命令全部可跑。
- 失败：任何一项仍可复现 → 不启动 provider 试验。

**T4 更正结论 + 研究定位决策**（约半天，T2 出结果后定稿）
- 内容：修正 §2.3、§2.5 涉及的文档与 claim 表；根据 T2 判决决定 C1 继续或转向（例如定位为"版本化航空天气证据的可审计回放协议"这类数据/协议贡献）。
- 成功：claim 表无超出证据的表述，并经一次独立核验。

**T5 有条件的 provider 试验**（v22 P2-00 至 P2-02；仅当 T2 通过且 T3 全绿）
- 在 T1 名册上，LLM 或自适应规则对最佳非自适应基线，查询预算相同，δ 与伤害阈值事先登记，保留完整分母。
- 成功：以事件为簇的 CI 整体优于 −δ，且各站点无显著恶化。失败：CI 落在 [−δ, δ] → 登记为负结果，停止扩大 LLM 规模。

**暂不值得投入**
- 任何同一生成器的 GPU/MC 实验，包括 v22 P1-01 的 12 条件 × 5 seed × 2 万规模（改成解析测试即可）。
- 在现有 24 目标名册上跑 provider 试验。
- P0-06 干预/修复矩阵、P0-07 provider 传输加固、P1-03（待 T2 通过）。
- C3 多领域/多模态扩展、开 holdout、L1/L2 前瞻采集。
- 在 T1/T2 产出数据之前再写新的审查包。
- 超出发布测试集范围的全量收集清理。

---

## 最终结论

**做到哪里**：离线工程可复现，标签正确，数据可追溯；最新 v22 计划零执行（被送到了 EarthDelta 会话）。

**问题在哪**：唯一的真实实验每个检查点最多 1 个来源、也没有窗口内修订，测不出任何主动或修订效应；TAF 规则不如气候态；合成优势写进了生成器；另有 Natural 契约缺陷与干净克隆失败。

**哪些可信**：数据管线与标签正确；"读 TAF 好于 0.5"；GPU 数值正确实现了指定生成过程。

**哪些未证明**：C1、C2、C3、LLM 价值、修订跟踪、轨迹评价。

**顺序**：重建有选择空间的开发集 → 强基线加 oracle 上限判决 → 只修必需的契约与复现 → 更正结论 → 有条件的 provider 试验。

建议总状态：`PARTIAL_PASS_ENGINEERING__REAL_DEV_UNIDENTIFIABLE__RESEARCH_UNTESTED`
