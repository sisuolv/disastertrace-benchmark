# DisasterTrace v17 Batch A2 独立 AI 复核报告

复核日期：2026-09-22（UTC）。复核对象：Batch A2 的未提交工作树、census_full_run 和 witness_v1。
参考 HEAD：`daba7cf3f1b53b5b6d8c8d376773c2b9d43d9644`，复核时未变化。

**结论：原始数据身份和主要机械计数可复现，CE1/CE3/CE4 的指定修复成立，CE2 的 AMD 原反例已关闭；但统计解释、候选月份、异常传播和 witness 资格仍有实质问题，不能认可“仪器已完全验收，只剩人工签字”。G1 不应升级为 PASSED。**

本报告由独立于 A2 实现过程的 Codex AI 复核方撰写，**不是独立人工评审**，不能替代项目定义的人工核验。没有修改任何 A2 既有文件或项目状态；本报告中的修复建议均未执行。配套逐条判断位于 `$WITNESS/witness_codex_review.jsonl`，原 `witnesses.jsonl` 保持不变。

## 1. 证据位置和判定标准

本文路径缩写：

- `$REPO` = `/mnt/afs/260010168/extreme_weather_benchmark/development/v14_revision_20260919_01/repo`
- `$CODE` = `$REPO/disastertrace-starter`
- `$PLAN` = `$REPO/plan/plan_v17_0921`
- `$RUN` = `$CODE/artifacts_v17/ba2_20260921T202507Z`
- `$OUT` = `$RUN/census_full_run`
- `$WITNESS` = `$RUN/witness_v1`
- `$RAW` = `/mnt/afs/260010168/extreme_weather_benchmark/data_real_v16/taf/20260920T134949Z_1bbe63aedc00_dl3rbulk`

源代码与测试路径默认相对 `$CODE`；项目报告默认相对 `$PLAN`。JSONL 行号从 1 起，原文字节区间均为从 0 起的半开区间 `[start,end)`。

- **CONFIRMED**：本轮直接读到实现/原始字节，并通过独立计算或实际执行支持该具体命题。
- **DISPUTED**：发现明确反例、口径不符或材料之间矛盾；不表示整份工作无效。
- **CANNOT_VERIFY**：本轮授权证据或执行范围不足，不计为通过，也不自动计为错误。

## 2. 主要发现（按影响排序）

### R1 — 高：将评分期间到达的常规新 TAF 当成“只有初始证据”，使核心科学结论失真

**DISPUTED。** `scripts/run_transition_census_v17.py:208` 的 change-like 集合仅含 AMD/COR/CNL；`scripts/run_transition_census_v17.py:665` 将 ledger kind 映射到 change_type，`scripts/run_transition_census_v17.py:735` 只对 change-like 类型授予 IN_EPISODE_CHANGE，其余返回 INITIAL_ONLY_NO_CHANGE。因此普通新报文即使第一次出现在 INTERVAL_1/2，也不会让目标离开“无变化”状态。

全量独立复算发现：

| 独立计算的事件定义 | 目标数 |
|---|---:|
| 任意 strict_overlap 记录首次在 INTERVAL_1/2 可见 | 14,806 |
| 其中包含 INITIAL_BASELINE 首次在 INTERVAL_1/2 可见 | 14,737 |
| 上一行中仍被标为 INITIAL_ONLY_NO_CHANGE | **14,483** |
| 有 AMD/COR/CNL 在区间内首次可见，包括同时标为 UNRESOLVED 的目标 | 293 |
| 程序主状态 IN_EPISODE_CHANGE | 292 |

这些是**记录到达**统计，不是已经证明合法替代、目标天气内容改变或评分收益的数量。不能用 14,806 直接替换成“有益修订数”；但足以否定“16,743 个目标只有初始 baseline、没有任何后续证据变化”的解释。

直接反例是 W027：KSFO，目标 2023-01-01 06–07Z。`$OUT/all_changes.jsonl:4` 已记录 05:36 常规 TAF，声明可用时间为 05:38，strict_overlap / INTERVAL_2。原文 `$RAW/KSFO_202301.body` 的 `[79891,80079)` 包含该报文，覆盖 0106/0212。程序没有丢掉记录，却在 slot 状态和研究结论中排除了它。

受影响的文字是 `TRANSITION_CENSUS_v17_A2.md:148` 起的“96.1% only their initial baseline ... no further legitimate change”。更严重的是，`tests/test_v17_a2_integration.py:73` 的 scenario6 把 11:10 起报、11:12 可用的新 TAF 放在目标 12Z 的评分期间，`tests/test_v17_a2_integration.py:208` 却要求 INITIAL_ONLY_NO_CHANGE。这里不是空断言，而是**有效断言固化了有问题的语义**。

建议下一批明确拆开：初始可见证据、评分期间新到达记录、已解析版本关系、目标内容变化。若确实只研究 AMD/COR，应将计数和结论明确改为“评分期间 AMD/COR 到达”，不能泛称所有新证据。

### R2 — 高：17,420 并不是文档声称的“35 个允许月份”分母

**DISPUTED。** `scripts/run_transition_census_v17.py:464` 的候选生成器遍历连续日历，只在 `:505` 检查保护周与 checkpoint 是否相交，没有应用文件输入所用的 ALLOWED_YEAR_MONTHS。

独立读取 slot 元数据发现，17,420 个候选中有 **332 个 target 起始月份为 2025-02**，其中 NO_APPLICABLE_EVIDENCE 312 个，INITIAL_ONLY_NO_CHANGE 20 个。去掉整个未允许月份后为：

```text
17,420 - 332 = 17,088
4 stations × (365 + 366 + 365 - 28) days × 4 routine hours = 17,088
```

原报告 `TRANSITION_CENSUS_v17_A2.md:87`、`BATCH_A2_ACCEPTANCE.md:93` 却将 17,420 称为 35 个允许月份的完整日历。独立排除账本的 116 个 protected_window 候选不能代替整月排除：它们只覆盖保护周及相关 checkpoint。

**这证明候选口径错误，不证明本次读取了 2025-02 原始文件。** 本轮只核对候选日历元数据；没有打开任何该月文件，也没有读取或推导保护周实际资料。

另一个覆盖缺陷在 `scripts/run_transition_census_v17.py:726`：prefix_coverage_insufficient 只比较“该站全部档案中最早 available_at”，不能识别中间整月缺口；`:711` / `:720` 的无证据分支还会在生成该 flag 之前返回。W029/W030 在许可档案起点之前需要历史前缀，却输出 flags=[]。所以 NO_APPLICABLE_EVIDENCE 不能直接解释为自然无证据。

### R3 — 高：异常与缺字段仍可退化成正常或无证据，仪器尚未 fail-closed

**DISPUTED。** 在完全内存、禁止文件写入的补充反例中，直接调用现有函数得到：

| 反例 | 实际结果 |
|---|---|
| 对一组本来 UNRESOLVED 的 ledger 删除 relation_status/relation_reason 再传入 census | slot 从 UNRESOLVED 变成 IN_EPISODE_CHANGE |
| 在真实 run_census 入口中用内存替身提供输入，并令某站 compile_ledger 抛 ValueError | 打印 warning，受影响站的 4 个 slot 全变为 NO_APPLICABLE_EVIDENCE，unresolved=0 |

第一处源于 `scripts/run_transition_census_v17.py:669` 的 `entry.get("relation_status", "not_applicable")`。第二处源于 `:886` 的异常捕获后 `ledger=[]`，而 `:607` 会直接使用这个空 ledger，绕过 `:611` 的 compilation_error 分支。

这里**没有证据声称已交付的真实 run 发生过该异常**；反例证明的是“任何未知/编译失败都被显式传播”这一验收保障尚不成立。`tests/test_v17_a2_integration.py:416` 名为 MissingFieldsNotDefaultedToZero 的测试实际只检查编译器删除 receipt_seq/receipt_stream，没有覆盖 ledger relation 字段缺失。

下一批应将编译失败、缺关系字段与“自然无变化/无可用资料”分开，并在真实顶层入口加异常注入回归测试。

### R4 — 中：37 个历史关系未知不等于 37 次评分期间新变化，也不能证明 equal-BBB 修复被真实数据覆盖

**数字 CONFIRMED，解释 DISPUTED。**

46 条 unresolved 关联确实全部为 bbb_contradicts_receipt_order；其中严格重叠且评分可见的 37 条，有 **36 条属于 INITIAL_PREFIX，1 条属于 INTERVAL_2**。37 个 UNRESOLVED slot 中，只有 **1 个**也有评分期间新 AMD/COR/CNL。因此 `BATCH_A2_ACCEPTANCE.md:118` 将 292+37=329 称为实际“something happened”子集，混合了“期间新到达”和“初始历史就带有未知关系”。

`scripts/run_transition_census_v17.py:732` 的规则是只要任何可见历史关联 unresolved 就将整个 slot 标为 UNRESOLVED，没有检查它是否已被后续合法报文替代或是否仍约束当前预测状态。作为“历史关系异常曾出现”的 flag 可以成立；作为“当前目标无合法权威”尚未获证。

同时，`TRANSITION_CENSUS_v17_A2.md:130` 把 bbb_contradicts_receipt_order 解释为 equal-BBB；`BATCH_A2_ACCEPTANCE.md:66` 声称真实 46/46 均验证“this exact cause”。W023–W026 的原文却是 **AAB 与 AAC**，不是相等 BBB；equal-BBB 新分支的原因字符串是 equal_bbb_no_authority。真实冲突说明非零争议传播有效，**不能替代 CE1 的 equal-BBB 合成回归证据**。

### R5 — 中：CE2 的 AMD 修复不能推广为 compile_ledger 对所有类型都无双向环

**原 AMD 反例 CONFIRMED；一般化保证 DISPUTED。**

`src/disastertrace/revision_v1/ledger.py:275` 将同一 issued_at 的 AMD/COR 候选送入共享 tie resolver，无法定序时不生成 supersedes。现有 AMD 缺 receipt 反例在本轮得到双方 unresolved、无边；真实 census 的已记录 supersedes 边也独立检查为 0 个互指对。

但 `src/disastertrace/revision_v1/ledger.py:449` 的 cancellation 分支仍直接从 latest_issuance 生成 supersedes，未走修复后的 resolver。本轮给两个同站、同 issued_at、相同有效窗、不同语义且无 receipt 的 canceled 包，得到：

```text
A: kind=cancellation, supersedes=["B"], relation_status=not_applicable
B: kind=cancellation, supersedes=["A"], relation_status=not_applicable
```

本次真实 all_changes 没有 CNL，因此没有据此修改其真实计数；这是通用 ledger 声称的边界和后续回归缺口。

### R6 — 中：witness 可追溯，但独立关系覆盖与题目表述不足

**26/26 字节定位 CONFIRMED；充分资格覆盖 DISPUTED/CANNOT_VERIFY。**

- 26 条 change-level witness 实际只有 **13 个唯一 (body_path, byte_start, byte_end)**；4 条 duplicate 是同一来源对投影到 4 个目标，4 条 conflict_unknown 也来自同一 AAB/AAC 对。30 行不代表 30 个独立现象。
- 30 行站点分布为 KSFO 19、KJFK 5、KORD 4、KDEN 2。报告已披露站点集中，但未同样明确披露来源对重复。
- `$RUN/a2_7_witness_select.py:108` 的 cross_window 只检查 INTERVAL_1/2 与 AMD/COR，没有检查前后件有效窗是否改变。W011 的 COR 与前件同为 0112/0218。若“cross-window”意指跨产品有效窗修订，则当前桶没有保证覆盖；若只指评分区间到达，应明确命名，不能混用。
- `$RUN/a2_7_witness_select.py:345` 使用固定 program_answer 模板。W013 恰在 T-20 可用，但模板称 strictly inside，措辞与数值不符。
- 所有 226,930 条记录的 availability_basis 都是 declared_lag；本轮确认它们的计算使用 issue+120 秒。真实到站/接收时刻未获证明。“actually available”只能在该 replay 假设下成立。
- 所有 target_content_change 为 UNASSESSED。W003/W004 的目标适用 FM011000 段未改变，W006 的订正内容发生在目标时段之外；来源正文不同不能升级为固定目标内容变化。
- duplicate witness 未给出可直接打开的前件字节身份。本轮另从同一许可原档定位 AAB 前件，确认 TAF 正文相同；头字段不同，所以不声称原始字节相同或跨提供者 mirror。

### R7 — 中/低：边界事件有披露，但性质与状态汇总仍不一致

**披露存在 CONFIRMED；“仅 near-miss/in spirit”的表述 DISPUTED；原执行全过程 CANNOT_VERIFY。**

`BATCH_A2_PROGRESS.md:704`、`BATCH_A2_ACCEPTANCE.md:121` 和 `TRANSITION_CENSUS_v17_A2.md:58` 均披露了原执行方遍历并打印受禁目录子目录名的事件。按本轮重申的明确边界，“只打印目录名”本身就属于违规，不能降格为只是“in spirit”或 near-miss。这里引用的是既有文档，本轮没有访问受禁目录。

没有原会话的完整系统调用日志，本复核不能独立认证“只打印一行、没有读任何文件”的否定性保证。也没有证据认定其故意隐瞒：三份文档确实写了该事件。

`EXECUTION_STATUS_v17.md:56` / `:76` / `:96` 却宣称仪器已完成且无需进一步代码修复，未同步列出目录误入和两个月资料不完整的 caveat。其 `:16`、`:66` 的 BA-V=PENDING 又与 `:107` 的“已由 731 项回归满足”不一致。`TASK_CONTRACT_v17.json` 的**当前** `meta.g1_gate_status` 仍为 `PENDING_REVERIFICATION`，并非只是 correction_history 的历史文字。这些状态应在新的修订批次统一，而不是通过本复核替作者改写。

## 3. 逐项复核判定

| 项目/被复核声称 | 判定 | 独立证据与限定 |
|---|---|---|
| CE1：equal-BBB 的 tied_rows 排列一致 | **CONFIRMED** | tie_resolution.py:140 返回 equal_bbb_no_authority，:200 稳定排序；receipt 测试 :875、:889 检查两成员/三成员全部排列，本轮实际通过 |
| CE1：真实 46 条冲突就是 equal-BBB | **DISPUTED** | 原文 AAB/AAC 与 reason 字段均不同于 equal-BBB 分支，见 R4 |
| CE2：无 receipt 的同刻 AMD 不互相 supersede | **CONFIRMED** | ledger.py:275；test_revision_ledger.py:1723 及本轮内存反例 |
| CE2：compile_ledger 全类型均不会双向 supersede | **DISPUTED** | cancellation 独立反例，见 R5 |
| CE3：实际使用三个 checkpoint 和 available_at | **CONFIRMED** | census.py:635 连续调用三次 visible_at；全 226,930 行独立比较均一致；T-10 与晚可用测试通过 |
| CE3：新证据统计足以回答报告核心问题 | **DISPUTED** | 常规新 TAF 与初始证据混类，见 R1 |
| CE4：显式安全参数不能覆盖路径月份限制 | **CONFIRMED** | access_policy.py:276 起逐项比较；本轮纯内存安全 as_of / year_month 覆盖反例均被拒绝；没有访问该路径 |
| 死 tie_unresolved 字段被真实 relation_status 替换 | **CONFIRMED** | ledger.py:643 实际输出，census.py:669 消费；真实 46 条 unresolved 存在 |
| 任何缺字段/编译异常都不会默认为正常 | **DISPUTED** | 缺 relation_status 和顶层 compile_ledger 异常仍漏出，见 R3 |
| 多 predecessor 不再只截取 [0] | **CONFIRMED（所查 TAF 路径）** | ledger.py:273 返回整个候选列表，census.py:667 保留 list；未推广到禁止读取的模块 |
| 140 文件身份、41,386 包/60 跳过帧 | **CONFIRMED** | 本轮逐个读取相同清单 body，大小/hash 全符，TAF 重解析数字一致；未另读 receipt JSON |
| 226,930 行及三组分布求和 | **CONFIRMED** | 本轮完整流式复算，见第 4 节 |
| 17,420 是 35 个允许月份的正确分母 | **DISPUTED** | 实含 332 个未允许月份候选，见 R2 |
| 292/17,420、37/17,420 的算术 | **CONFIRMED** | 分别约 1.676% / 0.212%；算术对不代表分母与科学含义对 |
| 30 项 witness 的原文/slot 核验 | **CONFIRMED（核验已执行）** | 26 字节定位成功、4 slot 记录匹配；对题目答案仅 22 有条件同意、2 不同意、6 不确定 |
| reverse-chronology gate 导致本包 4 项定位失败 | **DISPUTED（该前提不适用于交付包）** | 4 项都是 slot-level 的 by-construction 无单一字节身份，见第 5 节 |
| 历史 274/731 全回归结果 | **CANNOT_VERIFY（未全量重跑）** | 本轮仅按边界运行 112 项；不将未运行项视为通过 |
| A2 仪器验收完全通过、只等人工 | **DISPUTED** | R1/R2/R3 尚需代码/口径修正与重验证 |
| AI 复核可替代独立人工复核 | **不成立** | 本报告明确不满足人工身份要求 |

## 4. 统计口径的独立复算

### 4.1 实际文件与三组分布

`all_changes.jsonl` **226,930 行**，不是已被更正的 227,430。三组分布各自加总均为 226,930：

| change_type | 数量 |
|---|---:|
| INITIAL_BASELINE | 102,369 |
| AMD | 121,859 |
| COR | 2,687 |
| mirror_duplicate | 15 |
| **合计** | **226,930** |

| checkpoint_classification | 数量 |
|---|---:|
| INITIAL_PREFIX | 206,579 |
| INTERVAL_1 | 169 |
| INTERVAL_2 | 14,899 |
| AFTER_LAST_SCORE | 5,283 |
| **合计** | **226,930** |

| relation_status | 数量 |
|---|---:|
| not_applicable | 102,384 |
| resolved | 124,500 |
| unresolved | 46 |
| **合计** | **226,930** |

额外核对 relation_reason：not_applicable 102,384；strictly_prior 124,304；receipt_order 164；receipt_order+bbb_agree 32；bbb_contradicts_receipt_order 46。合计同样为 226,930。

slot_summary 共 17,420 行，NO_INPUT 0、NO_APPLICABLE_EVIDENCE 348、INITIAL_ONLY_NO_CHANGE 16,743、IN_EPISODE_CHANGE 292、UNRESOLVED 37。逐 slot 与 all_changes 关联后，num_changes 和 change_types 列表均一致；各 slot 的 num_changes 求和为 226,930。

对每行以对应 slot 的三个 cutoff 独立计算：

```text
available <= T-60       -> INITIAL_PREFIX
T-60 < available <= T-40 -> INTERVAL_1
T-40 < available <= T-20 -> INTERVAL_2
available > T-20        -> AFTER_LAST_SCORE
```

与机器字段的**不一致数为 0**。这是真实 CE3 修复证据；它只验证可见时间归类，不自动验证关系权威、内容变化或真实接收时刻。

### 4.2 其他聚合值与命名陷阱

| 指标 | 复算值 | 判定/解释 |
|---|---:|---|
| 唯一 current_source_id | 41,375 | 与 summary 一致 |
| 程序定义的 n_unique_relation_edges | 41,375 | 可复现，但实际是 (change_type, current_source_id, candidate_predecessors 集合) 键，含无边 baseline |
| 去重后的实际 directed supersedes (current, predecessor) 边 | 24,293 | 与上一行不同的统计单位，不应用同一个“边”名称混称 |
| 上述已记录边的互指对 | 0 | 本次真实数据成立；不证明其他包类型没有环 |
| n_target_change_associations | 308 | strict_overlap + AMD/COR/CNL + INTERVAL_1/2 的关联行数；含 unresolved 目标 |
| n_checkpoint_exposures | 510,975 | strict_overlap 中按 prefix/interval1/interval2 分别加权 3/2/1，可复现 |
| n_candidate_blocks | 4,275 | 有三种有效状态的 station/target-day 描述性块 |
| total_process_groups | 275 | 区间 AMD/COR/CNL 的 station/issue-day 块；KDEN 92、KSFO 89、KJFK 49、KORD 45 |
| n_targets_with_initial_evidence（summary） | 16,743 | 实际只是 INITIAL_ONLY_NO_CHANGE 状态数，见 census.py:984 |
| 真正含 strict_overlap / INITIAL_PREFIX 记录的目标 | 17,071 | 若字段意图表示“有初始证据”，现命名/数值不符 |

`TRANSITION_CENSUS_v17_A2.md:38` 把旧 issue-day grouping 说成“同一个 grouping 改名为 n_candidate_blocks”，并不准确：现在 4,275 按 target day，275 才按 eligible changes 的 issue day。

此外 `scripts/run_transition_census_v17.py:128` 的 PROCESS_GROUPING_RULE 仍写“ONE independent weather process”和“Cross-day boundaries represent synoptic breaks”，与报告“仅描述性、无独立性主张”不一致。两组数字都不能凭 UTC 切日证明天气过程独立。

本轮独立计算公式均只使用已有 census 字段；没有调用 outcome/label，也没有依据模型表现选择子集。原始 TAF 已重新解析，但未从头重跑 140 文件的完整 ledger→census 管线；因此是原始身份/解析验证、现有全量产物复算和合成反例的组合，不冒充第二次完整真实清点。

## 5. 30 项 witness 的独立判断

### 5.1 方法及盲法限制

按要求先完成项目报告阅读，再分批查看每条 witness 的问题、station/target 和 byte_identity，读取对应原文字节；在显示该条 program_answer/rule_basis 前，先在内存记录独立答案。所有 30 条原始独立答案已原样保留在配套 JSONL 的 your_independent_answer，后续比较写入 notes，没有倒改初判以迎合程序。

需要明确：先读项目报告本身会接触部分汇总结论和案例，这是用户要求的顺序。因此是**对逐条 program_answer/rule_basis 隐藏的复核，不是对项目结论完全双盲**。前件比较只使用同一 140 文件清单内原文；4 条 slot witness 另与 slot_summary 的对应行逐字段核对。

“agree”按已声明的 issue+120 秒 replay、来源级变化/相关性解释；不认证真实接收时间、目标气象内容变化或预测好坏。两条 disagree 分别是 W013 的严格区间措辞、W027 的宽泛“无新证据”含义，严重程度不同。uncertain 不计为通过。

**汇总：agree 22；disagree 2；uncertain 6。** 其中 26 条 change witness 为 21/1/4，4 条 slot witness 为 1/1/2。不得把 22/30 当成抽样准确率：选择不是随机的，且存在重复来源对。

### 5.2 逐条汇总

下表 byte 文件均位于 `$RAW`；每条原始完整判断见配套 JSONL。

| ID | 原文或 slot 证据 | 独立判断要点 | 比较 |
|---|---|---|---|
| W001 | KSFO_202301 [80280,80472) | 03:03 AAB AMD 与 AAA 前件不同；声明 03:05 可用，早于检查点 | agree（来源级） |
| W002 | KSFO_202301 [80082,80274) | 04:01 AAC 相较 AAB 风向等改变；声明 04:03 可用 | agree（来源级） |
| W003 | 同 W001，目标 12–13Z | 属初始历史；来源有变化，但目标 FM011000 段未变 | agree（不承诺目标变化） |
| W004 | 同 W002，目标 12–13Z | 同上，不能推导本目标概率必须更新 | agree（不承诺目标变化） |
| W005 | KSFO_202301 [79316,79504) | 12:14 COR 修改风/云；12:16 早于该目标检查点 | agree |
| W006 | KORD_202301 [70311,70591) | 11:35 COR 将 TEMPO 13–16Z 云底 OVC003 改为 OVC002；不在本条 18–19Z 目标内 | agree（来源级） |
| W007 | 同 W005，目标 12–13Z | 12:14 起报已晚于 11:40 | agree |
| W008 | KJFK_202301 [90278,90590) | 06:13 起报晚于 05:40 | agree |
| W009 | KORD_202301 [70021,70305) | 12:18 起报晚于 11:40 | agree |
| W010 | KSFO_202301 [76634,76904) | 17:50 起报晚于 17:40 | agree |
| W011 | 同 W006，目标 12–13Z | 11:37 落在 (11:20,11:40]；未证明跨产品有效窗 | agree（评分区间） |
| W012 | KORD_202301 [69185,69435) | 17:07 落在 (17:00,17:20] | agree |
| W013 | KSFO_202301 [75428,75638) | 05:38+2min=05:40，恰等于 T-20；INTERVAL_2 正确，strictly inside 错 | **disagree（文字）** |
| W014 | KDEN_202301 [71446,71829) | 23:02 落在 (23:00,23:20] | agree |
| W015 | 同 W001，目标次日 06–07Z | 0103/0206 在目标起点结束，无严格重叠 | agree |
| W016 | 同 W002，目标次日 06–07Z | 0104/0206 在目标起点结束 | agree |
| W017 | KSFO_202301 [79693,79887) | 0109/0212 在目标起点结束 | agree |
| W018 | 同 W005，目标次日 18–19Z | 0112/0218 在目标起点结束 | agree |
| W019 | KSFO_202301 [29515,29718) | AAC 与 AAB 前件 [29722,29930) 的 TAF 正文相同，头不同 | agree（正文语义重复） |
| W020 | 同 W019，另一目标 | 同一重复对，非独立事件 | agree（同上） |
| W021 | 同 W019，另一目标 | 同一重复对，非独立事件 | agree（同上） |
| W022 | 同 W019，另一目标 | 同一重复对，非独立事件 | agree（同上） |
| W023 | KJFK_202307 [71031,71467) | AAB 与 AAC 前件 [71471,71912) 风向不同；BBB/推定 receipt 相悖，保守未知有依据 | **uncertain（完整权威问题）** |
| W024 | 同 W023，目标 18–19Z | 同一冲突对，不能仅据旧关系认定当前目标不可解 | **uncertain** |
| W025 | 同 W023，目标次日 00–01Z | 当前状态是否受后续合法版本消解需另证 | **uncertain** |
| W026 | 同 W023，目标次日 06–07Z | 旧冲突不等于当前无权威 | **uncertain** |
| W027 | slot_summary:2；另读 KSFO [79891,80079) | slot 复制吻合，但 05:38 常规 TAF 是区间内新证据 | **disagree（统计含义）** |
| W028 | slot_summary:3 | slot 复制吻合；11:39 常规 TAF 声明 11:41 可用，已晚于末次评分 | agree（允许输入内） |
| W029 | slot_summary:1 | 无输入记录吻合；检查点在许可档案起点之前，不能证明现实无变化 | **uncertain** |
| W030 | slot_summary:5 | 同上，KDEN 的前缀缺失不能当作真实负例 | **uncertain** |

W027–W030 的 status、flags、num_changes、change_types 均与原 slot 记录一致。数值复制正确与负例资格成立是不同命题。

### 5.3 对 byte_identity_unresolved_count=4 的专门核实

`selection_report.json` 的 26 resolved / 4 unresolved 计数可复现。四个 unresolved 正是 W027–W030，实际字段为：

```json
{"resolved": false, "reason": "no change record for this slot -- nothing to locate"}
```

没有一条 change-level witness 在本包中因 reverse-chronology premise gate 失败而未解析。因此不能按任务描述中的该前提虚构四个失败原因，也不能说本轮跳过了它们；四条均已做 slot 级核对。

`$RUN/a2_7_witness_select.py:221` 确实有 receipt_seq 被剥离后无法从该字段定位字节的分支。该说明对“这条定位方法失去输入”合理，但不证明原文原则上不可定位；更不能用未触发的分支解释本包的四条 slot witness。`LABEL_QUALIFICATION_v17_A2.md:77` 对这 4 条的解释与真实包一致。

## 6. 回归测试与补充反例

### 6.1 实际执行结果

本轮实际执行 **112 passed，0 failed，0 skipped**。这是已选择测试的结果，不是历史 274/731 项全量结果。

为遵守“除了两份复核产物不产生其他文件”的边界，执行时设置 PYTHONDONTWRITEBYTECODE=1、PYTEST_DISABLE_PLUGIN_AUTOLOAD=1，使用 Python -B，在内存安装审计 hook，拒绝文件写入/目录变更、测试中的真实数据访问以及 outcome/label 模块文件读取。pytest 参数：

```text
-o addopts= -q -p no:cacheprovider -p no:logging
--capture=sys --assert=plain --noconftest
tests/test_revision_receipt_order.py
tests/test_revision_ledger.py
tests/test_transition_census_v17.py::TestCensusImportIsolation
tests/test_transition_census_v17.py::TestProcessGroupingRule
tests/test_transition_census_v17.py::TestChangeClassification
tests/test_transition_census_v17.py::TestCalendarSlotGeneration
tests/test_transition_census_v17.py::TestDeDuplication
tests/test_transition_census_v17.py::TestCheckpointAwareCensus
tests/test_v17_a2_integration.py::TestOrderAndSuffixInvariants
tests/test_v17_a2_integration.py::TestMissingFieldsNotDefaultedToZero
```

审计 hook 在成功运行中的拦截事件为 0，禁止模块导入列表为空。关闭自动插件后出现 1 条 asyncio_mode 未识别配置警告，不影响通过数。

首次尝试未禁用 pytest logging 插件，hook 拦截其以写模式打开 /dev/null 的动作，pytest 以内部错误 exit 3 结束；拦截发生在写入前。随后禁用 logging 并成功执行上述 112 项。**本报告没有将首次失败记为通过，也没有隐藏它；未发生该次文件写入。**

会创建 tmp_path 文件/输出 artifacts 的集成路径未运行；会导入禁止 outcome 模块的测试未运行。这是有意缩小执行范围，**不是 skip 后计为 pass**。例如 access_policy 的 CE4 通过静态测试阅读和本轮纯内存参数反例核实，但没有假称整份 test_revision_access_policy.py 已重跑。

### 6.2 覆盖真实性

对用户指定的 5 份测试做静态检查：receipt 40 个 test 定义、ledger 48、access_policy 33、census 26、A2 integration 18。未发现显式 skip/skipif 装饰或调用，也未发现空测试函数。静态发现不代表所有环境下测试都不会被外部插件跳过。

已读的新测试确有结果断言，而非只 collect：

- `tests/test_revision_receipt_order.py:875` / `:889` 对排列结果集合断言，不只循环调用。
- `tests/test_revision_ledger.py:1636` / `:1723` 覆盖有/无 receipt 的 AMD 关系及无互指要求。
- `tests/test_transition_census_v17.py:865` / `:952` 覆盖 T-10 和晚 available_at。
- `tests/test_revision_access_policy.py:496` / `:513` 验证参数与路径月份矛盾被拒绝；`:302` / `:341` 有拒绝后的读/glob 计数断言。
- `tests/test_v17_a2_integration.py:443` 确有顶层 unresolved positive-control 断言；本轮只静态审查该文件写入型 fixture 路径，未运行它。

不足集中在**测试命题选错或缺少关键负例**，不是“测试全是假的”：R1 的 routine baseline、R2 的整月分母、R3 的异常/字段缺失、R5 的 CNL 双向环都未被现有通过结果排除。

### 6.3 独立内存反例的输入范围

补充测试只构造字符串/字典，不打开真实文件，不生成 fixture：

- CE4 使用一个未创建的 /tmp 路径字符串模拟月份冲突，安全 as_of 与安全 year_month 两种覆盖均被拒绝。
- AMD / CNL 两包反例使用同一 station/issued_at/validity、不同 source_id/native_semantics_sha256、相同 provider/product_series，无 receipt 信号。AMD 无边，canceled 包互指。
- 缺关系字段反例从当前 compile_ledger 得到的 unresolved 结果中删除 relation_status/relation_reason，再传给原 classify_changes_for_slot。
- 顶层编译失败反例仅将输入/解析器替换为内存对象，给原 run_census 注入 ValueError，artifacts_dir=None；没有读写任何假路径。

## 7. 原执行方披露与本轮边界自查

### 7.1 披露交叉表

| 事项 | 已披露位置 | 复核结论 |
|---|---|---|
| 原执行方打印受禁目录子目录名 | PROGRESS:704；ACCEPTANCE:121；CENSUS_A2:58 | 披露存在；性质应为实际边界违反，而非仅 near-miss；没有完整日志验证访问上限 |
| KDEN_202506 / KORD_202306 不完整 | PROGRESS:723；CENSUS_A2:166；ACCEPTANCE:129、:168；LABEL_A2:123 | 多份文档一致披露；EXECUTION_STATUS 未突出该 caveat |
| witness 站点集中 | LABEL_A2:58；ACCEPTANCE:172 | 未隐藏；但重复来源对数量未清楚披露 |
| 26/26 与 4 个 slot 无字节身份 | LABEL_A2:77；ACCEPTANCE:102 | 与原包一致，无 reverse-chronology 实例可核 |
| BA-V 当前状态 | EXECUTION_STATUS:16、:66 对照 :107 | PENDING 与“已满足”并存 |
| G1 状态迁移 | EXECUTION_STATUS:56、:76；ACCEPTANCE:151；TASK_CONTRACT meta | 状态页/验收报告为 PENDING_INDEPENDENT_REVIEW，但当前 meta.g1_gate_status=PENDING_REVERIFICATION；correction_history 另保留两次撤回理由，旧报告顶部指针存在 |
| 原执行方 A2-4 修改/合成测试 outcome_wiring | PROGRESS:493、:556；git 文件名级 diff | 有公开说明；本轮依硬边界未打开该模块。不能从文件名推断读过真实 outcome，也不能认证该模块功能正确 |

本轮对两个不完整月份只在已许可 canonical body 中验证身份与 TAF 解析：KDEN_202506 317 包、2 skipped；KORD_202306 201 包、1 skipped。没有打开外部 reconciliation/backfill 文件来判断应补多少条。因此“已披露不完整”成立，**真实缺失量及对修订数的影响 CANNOT_VERIFY**；不能凭现有证据保证只是 slight undercount。

### 7.2 本复核执行边界

- 原始数据读取仅限 input_readset.jsonl 的同一 140 个 TAF .body；逐项校验 station/month/path 后使用显式路径，未枚举数据目录。未另开清单里的 receipt .json。
- 140 个 body 共 **11,127,663 字节**，大小与 raw_text_sha256/receipt_sha256 声明均一致；重新调用 TAF 编译路径得到 41,386 包、60 skipped。这里是与账本声明比对，不是另读下载 receipt 的真实性认证。
- 未打开/列举受禁目录，未读取任何 2025-02 文件，未读取/推导保护周实际资料。候选日历月份核对仅针对已有非实际观测元数据。
- 未读取 ASOS/METAR 实际结果；未打开或导入 outcome/label 模块。共享编译模块中仅使用 TAF 路径；不因其中存在其他定义就调用它们。
- 未调用模型/API/GPU、训练或下载；未进行真实 freeze/disclose/LAMP 注册/outcome 结算。
- 未写数据、缓存、索引、临时测试文件；仅新建本报告和 witness_codex_review.jsonl。未 commit/push/merge，未删除或覆盖既有文件。
- 本轮没有发现自己实际越过上述访问/写入边界。被审计 hook 阻止的 /dev/null 写入尝试已在第 6 节披露。
- 由于没有原执行方完整命令日志和完整历史快照，本轮不声称已证明其全过程零越界、731 项历史结果，或每个 A2 工作树改动均在相同时间产生。

## 8. G1 建议与后续最小验收条件

**建议 G1 继续保持未通过；若只能二选一，应维持 PENDING_INDEPENDENT_REVIEW，不能因本报告升级为 PASSED。更准确的管理状态是重新打开仪器再验证依赖（PENDING_REVERIFICATION），并同时保留 PENDING_INDEPENDENT_REVIEW。**

本轮已有足够证据给出倾向性意见：**确实存在可追溯、按声明时钟在评分区间到达的真实 TAF AMD/COR，CE3 原缺陷已修复；但“频率约 1.68%、其余几乎无新证据、仪器只等人工确认”的组合结论尚不可信。** 这不是判 H15 必然失败，也不是独立人工资格通过。

下一批应先满足以下小范围条件，再讨论 G1：

1. 冻结事件定义：分别统计任意新可见来源、AMD/COR/CNL、当前有效关系未知、目标内容变化；修正 W027 和 scenario6 的语义，保留 source/target 两层。
2. 候选范围严格对齐允许月份；对缺失历史前缀/中间断档单独标记。不得为修复分母而读取未授权月份。
3. 对顶层编译异常和关系字段缺失 fail-closed，并补真实入口的合成回归；为 CNL 补关系方向测试或明确收窄保证。
4. 分开初始历史冲突与新到达冲突，去除“真实 46 条就是 equal-BBB”的错误归因；明确是否需要当前 authority-set 状态指标。
5. 在获准的新输出目录重跑清点，旧产物保留；用同一输入清单重新对账，不能在当前已交付文件上静默更正。
6. witness 补充普通 TAF 区间到达负例、正确的 no-change 对照、缺前缀非负例说明，按唯一来源对报告覆盖；完善前件字节身份和精确端点文字。
7. 由真正独立人工审阅修订后的包；本 AI 报告提供辅助证据，不能承担该身份。

OR1a 的真实标签分布、模型胜负和预测质量均不在本轮权限内，未据此决定哪些 witness 更重要，也没有借本复核扩大实验范围。

## 附录 A. 审阅快照身份

以下 SHA256 在生成复核文件之前，对当前既有文件只读计算。它们绑定本报告所指的工作树与产物，不等于签署整个项目历史的完整性。

快照时间：2026-09-22T02:22:09.861770+00:00。

| 相对 `$REPO` 的文件 | SHA256 |
|---|---|
| `disastertrace-starter/src/disastertrace/revision_v1/tie_resolution.py` | `ce6d0651896befb72cb37164a09417ca9b8d80c9e78c7db4f48351f607745d3c` |
| `disastertrace-starter/src/disastertrace/revision_v1/ledger.py` | `c67d82f66f1b9ca250616c12f99d7e27ffab530fa6f8c07bcaf7729c5b003f34` |
| `disastertrace-starter/src/disastertrace/revision_v1/access_policy.py` | `2b0e99c67ee1dbaf452387361679539aee3ebbee8f5eeefd7ba981cd9daaca17` |
| `disastertrace-starter/scripts/run_transition_census_v17.py` | `0c84aa6b2a3f63be54fcbf2a63ac3d6d4b7971994b857a1c7b49222755ab7e8b` |
| `disastertrace-starter/tests/test_v17_a2_integration.py` | `ba797243f34a785e6f6a02f91621279263d2766f55f5ab7624e09ce8bb15fe42` |
| `disastertrace-starter/artifacts_v17/ba2_20260921T202507Z/census_full_run/census_summary.json` | `5615cb79c92744b9eee83d08ecd804580371b1888bdb879939ac47d546dad6b8` |
| `disastertrace-starter/artifacts_v17/ba2_20260921T202507Z/census_full_run/input_readset.jsonl` | `0e88c2b9565c47af463308520804acbeb8f9110772fe08e2877995637f5745c9` |
| `disastertrace-starter/artifacts_v17/ba2_20260921T202507Z/census_full_run/all_changes.jsonl` | `9a724c03a6c94e74ce85fcc4d555e476d8679e6c420a5cc271165c5c17e6d267` |
| `disastertrace-starter/artifacts_v17/ba2_20260921T202507Z/census_full_run/slot_summary.jsonl` | `0b58596b7662b612e86354ed11b19802557c02fef97c5444e135d1f92df1d03d` |
| `disastertrace-starter/artifacts_v17/ba2_20260921T202507Z/witness_v1/witnesses.jsonl` | `dd87ce8dd388d1ffae4066c29add7994dd52452efb00f1a3b61546652041b315` |

配套 JSONL 的 `agree_with_program` 取布尔 `true` / `false` 或字符串 `"uncertain"`；`is_independent_human_review=false` 在全部 30 行均明确记录。
