# extreme_weather_benchmark 独立复查（2026-09-26）

## 结论先行

当前项目的准确状态是：**工程/协议基础达到可复查的阶段性通过，研究假设仍然 INCONCLUSIVE，novelty/value 尚未被证明**。

v21 已经把 TAF 解析、时间可见性、ASOS 绑定、Natural selector bridge、审计材料和六个 GPU 合成诊断作成了可复核的证据包；但这只证明了“协议和实验基础设施能运行”。真实开发集的 active 结果不是计划中的内容依赖式自适应跟随实验，而是一个单次查询的公开风险年龄排序器；它与其他源选择器完全打平。因此目前不能声称天气预测收益、active-policy 收益、LLM/provider 收益或方法 novelty。

## 当前仓库与发布状态

- 实际 Git 根目录：`development/disastertrace-next`，代码包：`disastertrace-starter`。
- 当前 HEAD：`8a6e2162c86c46a139a7f438a6d63d8356e8917c`，分支：`codex/v18-repaired-release-20260923`。
- 远端 feature branch 与当前 HEAD 一致；`origin/main` 仍是较旧的 `a23f73ad...`，所以“已发布到 GitHub”不等于 main 已更新。
- tracked diff 当前为空，但工作区仍有约 **631 个 untracked path**，主要是历史 `artifacts/`、`work/` 和生成缓存。它们已导致无过滤 pytest 收集污染。
- v21 证据位于 [`v21_execution_20260925_04`](../../artifacts/v21_execution_20260925_04/)。其中的 `SNAPSHOT_MANIFEST_V4.json` 和 `HANDOFF_REPORT_V4.md` 仍记录执行时的旧 HEAD `9dffe43e...` 和 dirty worktree；这是执行快照，不是当前发布状态，必须补一个 post-publication manifest。

## 原计划执行情况

| 计划范围 | 当前判定 | 依据与偏差 |
|---|---|---|
| TAF 规范化、单位、TEMPO/PROB 语义、source bridge | **PASS_SCOPED** | 24 个开发 episode、72 个 checkpoint；source-only bridge 72 条 trace；actor 未接收 outcome。 |
| ASOS evaluator-only 绑定 | **PASS_SCOPED** | 24/24 绑定成功，四站点、22 个 `y=0`、2 个 `y=1`。仅是小型开发诊断。 |
| v17–v21 回归与静态检查 | **PASS_SCOPED** | 目标子集 226 tests exit 0，compileall 通过；Ruff 是历史收据，本环境未重新执行。 |
| shared-delay / cost-matched GPU | **PASS_SYNTHETIC** / **CONDITIONAL_PASS_SYNTHETIC** | 六个 5090/H100 tide jobs 成功；实验明确 synthetic、无 provider call。成本匹配 surface 中 active 比 best non-active 好 `0.011311`，但生成器把条件优势写入了 q1/q2 可靠性。 |
| 真实 active 内容依赖式跟随 | **NOT_CLOSED** | `run_v21_real_dev_deterministic_score.py` 的 `METHODS` 是 `fixed/earliest_source/hash_source/active_age`；每个 arm 只查询一个 source。source bridge 的两次查询没有进入 score。 |
| intervention/repair/sham/delay 完整矩阵 | **PARTIALLY_CLOSED** | 代码存在，但 `delay` 对 `available_at=None` 会伪造时间；完整同父、原始/修复/错误计数矩阵仍未完成。 |
| 多目标/多 hazard/跨季节扩展 | **NOT_STARTED 或 PARTIAL** | 当前真实开发 roster 只有 24 个 episode，且实际 24 个全是 2025-01；“January/March”是允许读集，不是实现样本分布。 |
| provider/LLM、holdout/quarantine、最终 novelty/value gate | **BLOCKED/NOT_STARTED** | 无 credential；没有读取 holdout/quarantine；没有 provider/model 结果。 |
| 干净、可复现、主分支发布 | **PARTIAL** | feature branch 有 v21 commit，但 main 未更新；快照材料和当前 HEAD 不一致；本地有大量未跟踪树。 |

总体上，原 v21 handoff 包的任务状态不能标为全部完成。外部 `TASK_STATUS_V2` 的历史映射是 7 项 scoped PASS、11 项 partial、3 项 not started、1 项 blocked；v21 证据增加了已完成的受限实验，但没有消除这些 partial/block 条件。

## 主要问题与风险（按优先级）

### P1：公开排程源会让策略重复检索，违反查询预算

`NaturalKernel` 会把 `public_schedule=True` 且未来才可用的 source 放进 catalogue（[`natural_track_v18.py:253-270`](../../src/disastertrace/monitoring_v1/natural_track_v18.py#L253-L270)），检索结果却只是 `unavailable`，不会进入 `read`（[`natural_track_v18.py:190-213`](../../src/disastertrace/monitoring_v1/natural_track_v18.py#L190-L213)）。`CatalogueSelectorPolicy` 用成功读取数判断预算，并在 `action_count != len(read)` 时继续检索（[`natural_selector_policy_v21.py:118-135`](../../src/disastertrace/monitoring_v1/natural_selector_policy_v21.py#L118-L135)）。`ContentAwareSyntheticPolicy` 也只按成功读取数处理（[`active_policy_v21.py:43-77`](../../src/disastertrace/monitoring_v1/active_policy_v21.py#L43-L77)）。

我用未来 public source 的 adversarial kernel 复现出同一 `query_id` 连续 RETRIEVE，`read=[]` 而 `action_count` 无限增长；因此这是静态确认的契约漏洞。当前真实 bridge 默认使用非 public schedule source，所以 v21 这次 72 条 trace 没触发它，但公开排程是已声明的 Natural contract，不能留到后续 provider pilot。

修复：在公开状态中显式记录 attempted/unavailable IDs；预算按 retrieval attempt 计数；未来 source 返回 WAIT 到最早公开 `available_at` 或明确 STOP；过滤已失败 handle；为 public schedule、hidden/private、deadline、max_queries 写回归测试。任何一个 adversarial case 仍能重复检索时，真实 pilot 必须 STOP。

### P1：delay intervention 把未知 availability 变成了假时间

[`interventions_v18.py:500-503`](../../src/disastertrace/monitoring_v1/interventions_v18.py#L500-L503) 使用 `(available_at or 0) + 86_400_000_000`。当原值是 `None` 时，结果变成 Unix epoch 后一天，而不是“未知”。这会污染时间可见性、delay qualification 和因果解释。直接构造 `available_at=None` 的记录即可复现。

修复：`None` 必须返回明确的 `NOT_APPLICABLE/UNKNOWN_AVAILABILITY` 结果并附 reason，或在进入 delay 前拒绝；加入 None、负值、重复 delay 的回归测试。

### P1：真实开发集没有测到计划中的 active 机制

真实评分脚本明确写成“四个 one-query arms”（[`run_v21_real_dev_deterministic_score.py:1-7`](../../scripts/run_v21_real_dev_deterministic_score.py#L1-L7)），方法列表和选择逻辑在 [`run_v21_real_dev_deterministic_score.py:23-77`](../../scripts/run_v21_real_dev_deterministic_score.py#L23-L77)。`active_age` 只根据公开风险年龄排序 source；它不读取首个内容后选择第二个 source。真实 source bridge 虽然运行了 selector trace，但其结果没有进入 score。

所以“active 在真实开发集没有优势”只能解释为：**一个 one-query public-age selector 与其他 one-query controls 打平**。它不能否证或证明原计划中的 content-dependent follow-up hypothesis。当前正确做法是实现 shared-F、等 query/model cost 的 `fixed/no_extra/source_rr/source_hash/content_adaptive` 五臂真实开发 pilot，再谈 mechanism。

### P1：样本季节声明与实际 roster 不一致

[`G1_DEV_EPISODES_V3.json`](../../artifacts/v21_execution_20260925_04/G1_DEV_EPISODES_V3.json) 的 24 个 `target_start` 实际全部落在 2025-01；代码虽然允许 January/March（[`build_v18_dev_episodes.py:396-403`](../../scripts/build_v18_dev_episodes.py#L396-L403)），随后 round-robin station cap 选出的 24 个 episode 没有 March。发布文档却写成 “January/March 2025”（[`V21_RELEASE_20260925.md:27-33`](../V21_RELEASE_20260925.md#L27-L33)）。

修复二选一：重新构造并强制验证 12 Jan/12 Mar（同时保持站点平衡），或者更正所有 release/claim 文档，明确当前证据只覆盖 January。不能用“允许读集”替代“实际样本覆盖”。

### P1：当前 Brier 结果不能支持 generalization 或 active gain

24 个独立 target 中 22 个是负类、2 个是正类；72 个 checkpoint 只是重复同一 target label，不是 72 个独立样本。固定 0.5 prior 为 `0.25`，三个非固定 source arms 与 `active_age` 都为 `0.1104167`，且 active 与 best non-active 完全打平。没有 target-clustered confidence interval、校准置信区间、预先声明的 harm guard 或 season/station stratified uncertainty。

因此 `active_minus_fixed=-0.1395833` 主要表示固定 0.5 prior 在这个不平衡小样本上的劣势，不能当成 active-policy 贡献。修复：以 episode 为 cluster 做 paired Brier、bootstrap/permutation CI；预注册 active 不得在任何关键分层显著恶化；扩展并平衡真实开发 roster；保持 holdout/quarantine 不可见。

### P1：文档声称可 CPU smoke，但当前环境无法复现

[`REPRODUCE.md:54-69`](../../artifacts/v21_execution_20260925_04/REPRODUCE.md#L54-L69) 要求用 `.venv/bin/python` 运行 synthetic CPU smoke；但两个 synthetic 脚本直接 `import torch`（例如 [`run_v21_cost_matched_adaptive_surface.py:19`](../../scripts/run_v21_cost_matched_adaptive_surface.py#L19)），当前 `pyproject.toml` 没有 torch 依赖（[`pyproject.toml:11-24`](../../pyproject.toml#L11-L24)），实际 CPU 命令以 `ModuleNotFoundError: torch` 结束。

修复：增加明确的 `synthetic`/`gpu` optional extra 和锁定环境，或提供真正的 NumPy CPU backend；在 fresh clone 中执行文档命令并把结果放入 release receipt。

### P2：bridge 的 visibility 摘要可能丢弃后续 TEMPO/PROB period

[`run_v21_real_dev_source_bridge.py:44-52`](../../scripts/run_v21_real_dev_source_bridge.py#L44-L52) 只读取 `projection["periods"][0]` 生成顶层 `visibility_m`，而 deterministic scorer 的 `_projection_probability` 会遍历所有重叠 period（[`run_v21_real_dev_deterministic_score.py:28-47`](../../scripts/run_v21_real_dev_deterministic_score.py#L28-L47)）。这会使 actor policy 看到的摘要和 evaluator 使用的完整 projection 语义不同。

修复：定义唯一的 projection-to-feature 聚合规则（例如目标窗内最小 lower bound、明确 TEMPO/PROB precedence），bridge、policy、score 共用同一函数并加多 period 回归。

### P2：全量测试收集不稳定

目标 v17–v21 子集 226 tests 通过，`compileall` 通过；但 canonical `pytest -c pytest-mm.ini -q` 收集阶段出现 32 errors，原因包括不同目录中重复的裸测试模块名造成 import mismatch，以及缺少 `PIL`、`shapely`、`shapefile` 等可选依赖。无过滤 `pytest` 还会把 artifacts/work 下复制测试一起收集。它不是 v21 核心算法失败，但说明当前仓库不能声称“全套测试可一键复现”。

修复：将测试目录变成包或使用 importlib/唯一模块名，设置严格 `testpaths=tests` 并排除 artifacts/work，明确安装 geo/api extras；在 fresh clone 中执行全量收集。

### P2：数据选择和 availability 仍是受限 replay 证据

roster 以 source id 顺序找第一个重叠窗口（[`build_v18_dev_episodes.py:412-425`](../../scripts/build_v18_dev_episodes.py#L412-L425)），虽然后续 source stream 会按时间排序，但如果 ID 不携带时间语义，目标窗仍可能受 ID 排序影响。`availability_basis` 是 declared archive issue 加 120 秒 replay lag，不是实际 prospective publication receipt。该限制已经披露，但在 live/generalization claim 前必须解决或做敏感性分析。

### P2：GPU 成功只证明合成数值管线，不证明天气价值

六个 GPU jobs 均 SUCCEEDED，硬件包含 RTX 5090 和 H100；但 [`GPU_JOB_STATUS_V4.json`](../../artifacts/v21_execution_20260925_04/GPU_JOB_STATUS_V4.json) 明确 `synthetic=true`、`empirical=false`、`provider_calls=0`。cost-matched generator 明确把“初始 signal=1 时 q1 高可靠、signal=0 时 q2 高可靠”写入数据生成过程（[`run_v21_cost_matched_adaptive_surface.py:40-67`](../../scripts/run_v21_cost_matched_adaptive_surface.py#L40-L67)）。这是一项有用的机制 sanity check，但不是 novelty 证据；继续重复同一 synthetic surface 的 GPU 任务当前收益很低。

## 当前哪些结论可信

可信的结论只有以下几类：

1. 受限 TAF 数据能够被规范化为带单位、可追溯的 source/evidence stream，TEMPO/PROB 信息在 qualification projection 中被保留。
2. evaluator-only ASOS binding 在当前 24 个开发目标上完成，actor 没有读取 outcome，holdout/quarantine 没有被读入。
3. v17–v21 目标回归测试、编译检查和六个合成 GPU 执行收据存在，工程流程可以复核。
4. 在人为构造的等成本 synthetic mechanism 中，content-dependent follow-up 可以优于固定/非自适应控制；它只支持“值得做真实机制实验”的条件性假设。

以下结论仍未证明：真实天气 forecast skill、content-adaptive active 的独立收益、provider/LLM 的收益、跨季节/跨 hazard 泛化、因果/repair 机制、以及研究 novelty/value。README 也明确项目尚非完成的 benchmark，且没有 private Gold annotations。

## 下一阶段建议（按顺序）

### 1. 先修 Natural runtime 与 intervention contract

- **目标**：消除 public-schedule 重复检索、预算失效和 unknown availability 伪造。
- **成功标准**：未来 public source 会 WAIT 或明确不可用；每次 RETRIEVE 只计一次；最多执行声明的 `max_queries`；`delay(None)` 返回显式 N/A/拒绝；新增 adversarial tests 通过。
- **失败标准**：仍能重复同一 query、超过预算或伪造时间；在此情况下停止任何 provider/真实 pilot。

### 2. 先修发布与复现基础设施

- **目标**：让当前证据可在 fresh clone 独立复现。
- **动作**：生成以 `8a6e216` 为基准的 post-publication manifest；把当前 task/claim map 纳入 release；清理或隔离 631 个 untracked 历史树；修复 pytest 收集和 optional dependency；补 `torch` synthetic extra 或 NumPy CPU backend；决定是否把 feature branch 合并/明确为正式 release。
- **成功标准**：fresh clone 的目标测试、全量 collection、文档 CPU smoke 均可执行，artifact 不参与测试收集。
- **失败标准**：继续只能依赖本地脏 workspace；则只能称为 internal engineering snapshot。

### 3. 重做真实开发机制实验

- **目标**：真正测量计划中的 content-dependent follow-up，而非 `active_age` 单次查询。
- **设计**：固定同一 source/outcome map 与 evaluator-only ASOS labels；`fixed/no_extra/source_rr/source_hash/content_adaptive` 使用相同 query/model-call budget、相同 checkpoint denominator；内容适配策略必须只读取公开已获得内容；按 episode cluster 做 paired Brier/CI，并预注册 harm/calibration guard；先强制 12 Jan/12 Mar 或修正文档。
- **成功标准**：active 相对 best non-active 在预注册 CI 和关键分层上有稳定正收益，且无明显 harm。
- **失败标准**：打平或恶化，则放弃“active 已有实证收益”的表述，把贡献转向协议/数据审计方法。

### 4. 完成 intervention/repair/counting 矩阵

- **目标**：验证 same-parent suffix、delay/mirror/matched-sham/withhold、原始/repair/error 计数没有状态泄漏或 phantom rows。
- **成功标准**：每个 intervention 有 registry、pairing、expected delta、failure reason；无 hidden policy state leak；测试和 replay receipt 一致。
- **失败标准**：出现无法解释的状态差异，则暂不做因果或 mechanism claim。

### 5. 只有在 1–3 通过后再做 provider/C3 扩展

- **目标**：用一个明确的 provider-backed development pilot 或一个跨模态/跨 hazard fixture 检验 portability。
- **成功标准**：完整成本、调用、失败和校准账本；不读取 holdout；相对固定和强非自适应 baseline 有可复核改善。
- **失败标准**：无 credential、成本不等、或 active 不优于 baseline，则停止扩展，不投入更多 GPU。

## 现在不值得继续投入的实验

- 重复同一生成器和同一参数面的 5090/H100 synthetic runs；
- 在 runtime contract、样本季节和统计分母未修复前启动 holdout、quarantine 或正式 provider run；
- 用 fixed-prior Brier 差或 226 个测试通过宣称天气 skill/novelty；
- 在单个 24-target、22/2 不平衡开发集上扩展大量 hazard；
- 把当前 source-only one-query `active_age` 结果写成对 content-adaptive active 的否证。

## 最终判断

项目已经做到：**一个可审计的 v21 协议/工程 substrate，加上受限真实开发数据绑定和合成等成本机制诊断**。

项目还存在：**Natural public-schedule 预算漏洞、unknown availability 干预漏洞、真实 active 实验与计划不一致、样本季节与文档不一致、统计证据过弱、发布快照过时和复现环境不完整**。

已经可信的是工程边界、数据绑定边界和合成机制的条件性可行性；尚未可信的是天气预测价值、真实 active 优势、泛化、provider/LLM 效果和 novelty。下一步必须按“修合同 → 修复现/发布 → 重做等成本真实开发机制实验 → 完成 intervention 矩阵 → 最后再做 provider/扩展”的顺序推进。
