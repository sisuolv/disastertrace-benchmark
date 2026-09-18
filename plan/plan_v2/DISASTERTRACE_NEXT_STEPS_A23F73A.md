# DisasterTrace：基于 a23f73a 审阅快照的后续实施与实验计划

> 基准仓库：`sisuolv/disastertrace-benchmark`  
> 基准提交：`a23f73adadcbec077b9fcf2aecf8f45dfa4fe061`  
> 工作目录：`disastertrace-starter/`  
> 性质：下一阶段建议与 Codex 执行规范，不是已完成的代码变更或模型实验。  
> 本次核验方式：通过 GitHub 连接读取 review、当前源码、实验报告和交付验证记录；未在本次环境重跑仓库测试，未调用模型 API，未修改远端仓库。  
> 日期说明：仓库 review/交付文件标注 2026-09-07，实验记录说明截至 2026-09-06；本计划按提交身份定位，不凭相对日期猜测进度。

## 0. 阅读顺序和权限边界

Codex 首先读取当前适用的 `AGENTS.md`，再读 `REVIEW_FOR_CHATGPT_PRO.md`、`README_CALIBRATION_V1.md`、`IMPLEMENTATION_STATUS.md`、`DECISIONS.md`、`BLOCKERS.md` 和本文件。仓库若已有更新，先做差异审计；不得假定仍与 a23f73a 相同。

本计划不覆盖最新明确的用户授权，也不复活历史已消费授权。默认执行离线工作；不得自行调用付费模型、消耗原 P1 剩余额度、重新发送原未知请求、推送仓库或公开数据。`USD 3 / 270 requests` 目前是方案，不是本文件给予的授权。[S01][S02]

保持当前约束：

- 不依赖新增逐题人工标注、专家逐题复核或 LLM judge 主评分。
- 不训练模型，不接 GPU 作为必要依赖，不重建通用 Agent 平台。
- 不重新做已完成的 NHC 下载/准入、V2 grounding、P1 三方法比较。
- 不把 CyPortQA 的 48 个模板声明当成 48 道实例题，不把 DisasterBench 的计划控制当成真实工具执行。
- 不把受控到达时间说成经证实的历史首次公开时间。
- 不把程序输出、文件校验条目、测试用例或 API 请求尝试数当成独立模型样本。
- 保留历史原始响应、无效回答、未发送机会、费用未知记录以及 V1/V2 分数。
- 七个 heldout 风暴不进入开发校准模型推理。

## 1. 当前真实起点：哪些不要重做

| 层次 | 当前已经具备 | 下一步真正缺口 |
|---|---|---|
| 真实资料 | 12 候选风暴、36 公告、32 份解析通过；10 个完整三公告风暴 | 更有区分度的事实更新语义，而不是马上增加抓取量 |
| 划分 | 3 development、7 heldout | 冻结后使用 heldout 的执行边界和统计设计 |
| 回放 | 每风暴 base/delay 两分支、每分支五检查点 | 新任务协议的逐 fact-key 状态演化 |
| 方法 | snapshot / structured_state / answer_history | 控制输出格式与预算混杂，而不是添加更多未经比较的方法 |
| 评分 | 冻结 V1/V2、有限 NHC 等价支持规则、固定分母指标 | P2 独立自动 Gold 和新协议评分 |
| P1 | 90 个回答、91 次尝试、已记录中断续跑 | 不能据此直接宣称因果记忆优势 |
| 校准准备 | 3 条件、9 cells、54 trajectories、270 slots 的离线方案 | 新契约真实 collector、独立 audit、全矩阵累计账本 |
| 可复现材料 | 当前根目录已经带 references 精简快照和新环境验证记录 | 自动 CI、历史兼容与新构建身份的明确分离 |

仓库交付记录为 684 项测试通过；这不是本次重新执行的测试结果。不要把早期 6 项 starter 测试当作当前起点。[S01][S03][S04]

### 1.1 已完成的 P1 只支持什么

| 方法 | Schema 有效 | V2 known grounding | 固定字段总 grounding |
|---|---:|---:|---:|
| snapshot | 14/30 | 39/96 | 69/150 |
| structured_state | 30/30 | 96/96 | 150/150 |
| answer_history | 24/30 | 76/96 | 120/150 |

报告记录 20 个输出上限失败、2 个结构错误。68 个结构有效回答的字段值、状态和研究规则动作均正确，另有一个数值正确但引用落到移动速度行的 grounding 错误。[S05]

因此当前观察首先是“在这套提示和输出预算下，各方法的可用答案率明显不同”，而不是“structured_state 已解决天气推理”或“snapshot 缺乏记忆”。三种方法都得到累计原文；历史 carrier 还可能成为 JSON 格式示例。[S05][S06]

## 2. 下一阶段总路线

```text
R00：固定审阅基线，运行现有离线验收
     ├─ 执行线：R01 → R02/R03 → R04 → R05 → R06
     │           协议    collector/ledger  audit  rehearsal  授权后的270次校准
     └─ 研究线：R07 → R08 → R09
                 P2规格  双实现/变形测试  开发题集与程序控制

R06 + R09 → R10：受控 P2 development 模型实验
R10 冻结 → R11：heldout、复现和论文结果包
```

两条线可以离线并行。P2 的规格、自动生成器和测试不需要等待付费校准完成；但 P2 的正式方法比较必须采用事先冻结的公共契约、预算和失败政策。没有调用授权时，停在 live-ready，而不是停掉所有研究开发。

第一轮不要引入多模态、多个灾种、AutoResearch、复杂图数据库、完整 EarthVerse/lmms-eval 集成。现有工作已能承接当前研究问题。

## 3. 优先修正的问题及源码位置

### H1. 新契约不能直接交给旧 collector 当作已支持

`automated/collection.py::collect_model()` 内直接调用 `dynamic.render_request()`；`collection_audit.py` 以原协议审计。`calibration.py` 只准备新契约，未构成真实执行路径。[S07][S08][S09]

修正：新增契约感知采集与独立审计层，复用当前 `ProviderClient.prepare/complete` 和严格回答解析；不要把旧 collector 的结果字段改成“已经 live verified”。

### H2. 每个 cell 的限额不等于整个实验的限额

旧 collector 明确声明 `monetary_cap_enforced=false`。新实验 9 cells 必须共享一个 campaign 账本；不能每个 cell 各自拥有 USD 3 或 270 次额度。[S07]

修正：调用前持久预留；调用后按有效 usage 结算；未知费用保留预留；启动、停止、恢复都不能重置累计尝试数和金额。

### H3. 60 秒可能成为与输出预算竞争的截断因素

旧 provider 将 timeout 传给 `urllib`，然后统计传输耗时；当前代码没有独立、可审计的整体墙钟 deadline 控制。不能仅凭该参数声称严格的端到端 60 秒硬上限。[S10]

建议在任何新调用前制定 `CALIBRATION_PROTOCOL_V1_1.md`，将所有三条件统一的 timeout 提议设为 180 秒，并明确其传输含义；180 秒是预设设计值，不是已证实足够。若要整体 deadline，需另加显式机制、故障测试和协议字段。不得只给 8192 条件加时、失败后临时加时或重发。

保留原 v1 和 60 秒准备包。`calibration.py::provider_configs()` 当前硬编码 60 秒，不能只改外部 JSON；新增版本入口或明确迁移，生成新身份、新输出目录。[S09][S11]

### H4. 当前状态语义是整份最新公告，不是部分更新

`dynamic.reference_at()` 先取最新 issued record，再为所有字段从该 record 取值。`validate_episode()` 和 `ProviderClient.validate_public_request()` 固定原五字段、数值/未知结构及研究阈值。[S06][S10]

修正：P2 用独立 namespace、协议、参考编译器和公共请求校验器。不能只往旧 instruction 加一句“处理 patch”，也不能偷偷更改旧五字段含义。

### H5. 固定 unknown 字段与简单阈值存在捷径

`port_reopening_time` 始终未知；动作只是最大风速相对 100 mph 的公开研究规则。应保留为旧控制，不作为新论文的主要“拒答能力”或真实决策能力证据。[S01][S06]

修正：P2 的同一事实字段有 known/unknown 匹配对，并可在后续恢复支持；动作保留次级地位。

### H6. references 缺失已不是这个导出快照的首要阻塞

根目录 `REFERENCE_BUNDLE.md` 说明当前已带精简资料快照及校验文件；新环境记录已完成 build/prepare/verify。早期 review 中的“不要假定外部 references 已发布”应结合导出包现状理解。[S03][S04]

修正：核验清单和新环境重建，不重复采购/抓取全部数据。迁移路径导致新 build identity 不同是预期，不得重写旧 manifest 伪造同一身份。

## 4. R00：基线固定与离线复现

### 目标

证明后续修改前的起点明确，避免把历史结果、重新构建产物和新模型响应混在一起。

### 执行

从仓库根目录检查当前 commit、工作区差异和适用指令。下列命令是仓库已有入口；输出目录必须全新。

```bash
cd references
sha256sum --check REVIEW_REFERENCE_SHA256SUMS
cd ../disastertrace-starter

# 安装环境按仓库 README 执行，不覆盖用户现有环境。
.venv/bin/python -m pytest tests -o addopts= -q

.venv/bin/disastertrace-auto build \
  --references ../references \
  --nhc-snapshot ../references/nhc_cohort_v1 \
  --output work/next-review-build-001

.venv/bin/python -m disastertrace.automated.calibration prepare \
  --build work/next-review-build-001 \
  --provider-config artifacts/p1_deepseek_development/provider.json \
  --output work/next-review-calibration-001

.venv/bin/python -m disastertrace.automated.calibration verify \
  --output work/next-review-calibration-001
```

不要运行所有历史 artifacts 中归档的旧测试作为同一套新测试。不要将上面的 prepare 解释为启动模型。

### 新产物

`artifacts/next_steps/baseline/{git_state.json,environment.json,commands.json,test_result.json,checksums.json}`。

### 验收

记录真实命令、退出码、通过/失败/跳过数；references 清单和已有归档不改变；新 build 仍为 3 development / 7 heldout。版本发生变化时说明变化原因，不要求路径绑定的 build ID 与旧机相同。

## 5. R01：先冻结将执行的校准协议

### 默认研究选择

保留三个条件：

| 条件 | 公共契约 | 输出上限 | 完整机会 |
|---|---|---:|---:|
| legacy_4096 | legacy | 4096 | 90 |
| explicit_4096 | explicit | 4096 | 90 |
| explicit_8192 | explicit | 8192 | 90 |

比较只能解释：在 4096 下的这项契约干预；在 explicit 下的预算干预。没有 legacy_8192，不识别完整交互。除非论文决定把交互作为核心结论，否则不增加第四条件。新增第四条件需新方案和额外 90 次完整范围，不能临时补失败样本。[S11]

### 协议版本处理

建议新增 `docs/CALIBRATION_PROTOCOL_V1_1.md`、`docs/CALIBRATION_AMENDMENT_V1_1.md` 和新 preparation 入口，统一调整 timeout 后重建 270 个槽位、54 个初始请求。保持旧 parser/scorer、源资料、方法、reasoning 设置不变；不要同时加入 JSON mode、自动 repair 或关闭 thinking。

显式契约不意味着与 carrier 的格式示例作用完全等价。若校准后仍要把优势解释为“历史内容”而非“格式示例”，另设使用不同虚构实体且不能回答当前题目的通用格式示例控制；不得把全 unknown 的填好答案作为共享示例，因为它可直接回答 c0。该控制不加入当前 270 条件矩阵。

### 验收

能够从新协议重建完整 schedule；所有三条件具有相同 timeout 政策；只存在预声明差异；原 P1 90 回答不作为新鲜 legacy control；七个 heldout 不在 schedule；旧方案字节不改。

## 6. R02：契约感知 collector

### 建议新增文件（以下为拟新增，不是现有命令）

- `src/disastertrace/automated/calibration_collection.py`
- `tests/test_calibration_collection.py`

### 可直接复用

`output_contract.render_calibration_request()`、`ProviderClient.prepare()`、`ProviderClient.complete()`、`dynamic.parse_decision()`、现有 canonical/hash、当前 method 定义和明确公开字段选择。[S06][S09][S10]

### 必须实现

每个槽位必须有：

```text
campaign_id / protocol_id / cell_id / arm_id / method
storm_id / branch_id / repeat_id / trajectory_id / checkpoint_id
slot_id / attempt_id / predecessor_slot_id
contract_sha256 / source_manifest_sha256 / actual_request_sha256
wire_body_sha256 / carrier_sha256 / provider_config_sha256
```

`slot_id` 是评分机会身份，`attempt_id` 是调用尝试身份；不能混为一谈。一次得到回答不等于只尝试一次。

每一步：

1. 从已提交 journal 重建该 trajectory 自己的最近有效回答/全部有效历史。
2. 用契约感知 renderer 构建当时累计已交付证据和声明 carrier。
3. `prepare()` 产生最终 wire body，不读密钥、不发送。
4. 先经过 R03 预留与启动 claim，再发送一次。
5. 保存允许留存的原始 provider envelope 和最终 content；不把 reasoning text 当作最终 JSON 解析。
6. 结构有效但事实错误的回答进入 carrier；结构无效回答留在分母但不替换既有有效 carrier。
7. 写清 accepted/invalid、finish_reason、usage、hash 和状态前后。
8. 不调用 scorer 决定是否接受到 carrier，不使用 Gold 修复。

初始请求可预生成；后续 live carrier 未存在前，不得把后续 wire body 宣称为实际请求。离线程序回答仅用于 rehearsal。

### 无网络测试

记录传给 transport 的原始 bytes；与准备和审计记录逐字比对。用携带虚构字符串的错误回答验证“错误也会传播”；用无效 JSON 验证旧 carrier 保留；对 arm/method/branch/repeat 交叉污染分别测试。

## 7. R03：单一累计账本与崩溃语义

### 新增文件

`automated/calibration_campaign.py`、`tests/test_calibration_campaign.py`。

优先保留现有顺序、追加 journal 风格，不部署消息队列或数据库服务。一个 campaign 单一协调进程。文件系统锁、原子重命名和 fsync 必须实测；不默认声称跨机器共享盘具有 exactly-once 保证。

### 状态模型

```text
PLANNED → RESERVED → DISPATCH_INTENT → RESPONSE_CAPTURED → SETTLED
                              └────→ OUTCOME_UNKNOWN → BLOCKED
```

`RESPONSE_CAPTURED/SETTLED` 内另记 benchmark decision 为 valid/invalid；模型 JSON 无效不是 transport failure。

必须先持久化 `DISPATCH_INTENT`，才调用网络。若该标记之后崩溃，无论是否真的发出，都保守记作可能发送、结果未知。API 不提供已验证幂等能力时，不承诺 exactly-once；保证本客户端不自动重发不确定请求。

### 额度公式

```text
settled_conservative_cost
+ retained_unresolved_reservations
+ next_request_reservation
<= authorized_campaign_limit
```

同时检查累计 attempt cap、输出 token 预留 cap、请求 bytes、模型配置和单次启动归属。预留不是已支付费用；未结算不等于零费用。reasoning tokens 不与 completion tokens 重复计费。

原 P1 第 79 次未知请求保持在旧账本；新 campaign 引用其历史说明，但不使用旧额度作为新授权。拟议 USD 3 是条件停止额度，不承诺完成270次。

### 价格与边界

真实启动前保存官方价格/模型限制原文与抓取时间、适用窗口和配置哈希。当前审阅不提供新的可信实时报价；不要用搜索摘要替代正式价格快照。改变价格或模型上下文上限须更新会计方案，而非覆盖原 rates.json。

未经证明的“字节数约等于 tokens”或历史平均 usage 只能做成本预测，不能替代计费上界。现有全上下文预留虽保守，但优先保证账本可解释；以后有可验证 tokenizer/服务端计数上界时再单独修订。

### 至少覆盖的故障点

- 预留前、预留后但 dispatch 前崩溃。
- dispatch 后、响应前崩溃。
- 响应落盘后、usage 结算前崩溃。
- journal 尾部不完整、重复结算、摘要落后于 journal。
- 第二进程同时启动、scope/hash 不匹配、额度恰好达到边界。
- timeout、429、缺失 usage、usage 超限、返回模型别名异常。
- 无效 benchmark JSON 但 provider envelope/usage 合法。

恢复只复用审计通过的既有前缀；不重复计费、不释放未知预留、不重试已有无效回答。新 live launch/recovery 需要绑定范围，不自动接续已消费授权。

## 8. R04：独立采集审计与 projection 边界

### 新增文件

`automated/calibration_collection_audit.py`、`tests/test_calibration_collection_audit.py`。

该审计不能只读 collector 写出的 `verified=true`，也不能只比较 hash。它应从冻结协议、源资料、schedule、原始响应重新走一遍公开输入和 carrier 接受序列。

审计证明链：

```text
frozen protocol + sources + schedule
       ↓ independent reconstruction
actual public request
       ↓ verified serialization
actual wire body
       ↓ captured provider response + usage
accepted/invalid outcome + next carrier
       ↓ instruction-only, labeled compatibility transformation
scoring projection → frozen V1/V2 scores
```

允许共享 canonical JSON、hash 和字段定义；不得共享 collector 的接受结论、carrier 更新结果作为审计真值。与 P2 的独立语义 Gold 相区分：独立运行同一代码只证明一致复算，不自动证明语义正确。

projection 只做兼容层：只替换 instruction 为旧 scorer 可复验的 instruction，更新 projection hash，其他证据、carrier、response、失败机会不变。保留 actual trace，禁止把 projection 冒充模型曝光。

### 独立篡改测试

为请求中的 instruction、一个 delivery、一个原文行、一个 carrier 值、一个 raw response、一个 wire body 字节、一个 usage 数字各建立篡改反例，必须 fail closed。不得靠重算全部 hash 后让任意内容通过。

## 9. R05：全矩阵 offline rehearsal 与 live-ready 验收

使用 injected transport 走与正式 collector 相同的路径，模拟270个响应；标为 `diagnostic_program` 或 `injected_transport_unverified`，不得改成真实模型记录。

程序控制：rule、last-arrival、no-update、invalid-control，以及故障/超时 envelope 控制。

产物：

```text
artifacts/calibration-live-ready-v1_1/
  protocol.json
  frozen_schedule.jsonl
  source_manifest.json
  implementation_manifest.json
  rehearsal/
  independent_audit.json
  failure_injection_report.json
  launch_manifest.json          # authorized=false
  README.md
```

验收：270个机会、54条独立轨迹；预期条件差异外的输入一致；后续carrier全由该trajectory已收到的有效回答产生；累计限额不重置；未知attempt阻塞；独立audit全部通过；历史P1/校准v1不改。

此时状态写 `live_ready_not_authorized`，不是 `calibration_completed`。

## 10. R06：授权后的新鲜270次校准

只有 scope、额度、实际模型、价格快照、timeout政策和launch ownership均绑定，才执行。授权不在本计划中自动产生。

继续既定单请求顺序和按风暴轮转的条件/方法顺序，不私自并发，不添加暖缓存请求，不用本地 response cache 替代独立重复。

### 结果报告

同时报告固定分母 known grounding、schema success、length、empty content、partial JSON、结构错误、transport失败、not_sent、usage缺失、来源拒绝原因及每风暴结果。provider截断与格式错误可重叠，别重复加总为不同独立样本。

共同预算选择保留预注册要求：完整、独立审计通过的270响应矩阵；每方法至少29/30结构有效、最多1个length、没有基础设施/会计错误。选择满足条件的最小共同预算；未完成或两个候选都失败则 `no_selection`。29/30不是总体可靠性置信保证。[S11]

### 科学决策

- 显式契约后差距收缩：把P1解释为接口/预算混杂，转向P2；不是项目失败。
- schema都稳定但仍有方法差异：保留“完整原文条件下的carrier处理差异”描述，不能直接说记忆依赖。
- 有效回答仍接近满分：停止在现有四字段上增加大量模型，进入P2。
- 8192仍明显截断/timeout：保留结果，另立统一预算/推理模式方案；不单独重跑失败cells。
- 基础设施中断：报告固定计划完成率与部分系统分数，不把未提交全当作模型知识错误；不宣布共同预算选择。

## 11. R07：P2-Controlled Revision 的最小规格

### 研究定位

保留 `NHC-Observed-v1`：原始官方公告 + controlled delivery + latest reported observation。新增 `Controlled-Revision-v1`：程序生成的事实更新和干预 + 完全公开的操作语义。两轨分别报告，不混写成“真实历史纠正”。[S01][S12]

P2目标是：模型能否根据已交付证据对正确的实体、变量和有效窗口进行选择性更新，保留仍有效事实，并在支持缺失时恰当保持未知。

### 新namespace

```text
src/disastertrace/revision_tasks/
  schema.py
  source_cards.py
  generator.py
  compiler.py
  oracle_check.py
  public_view.py
  runner.py
  provider_adapter.py
  scoring.py
  controls.py
```

以上是拟新增文件。不要把P2塞进 `dynamic.FIELDS` 或原 `validate_public_request()`。新adapter只复用既有传输、hash、错误处理思想；新公共协议有自己的校验。旧provider为五固定字段设计，不能仅改prompt就支持P2。[S06][S10]

### 事实键和证据身份

```text
FactKey = (entity_id, variable, valid_from, valid_to)
```

每个证据卡片至少有 `record_id, issued_at, delivery_event_id, entity_id, updates, source_origin, fact_origin, schedule_origin`。每个update有完整fact key、操作、值、单位、证据locator、必要的supersedes事实级目标。

初版：非歧义的 `SET` 和 `NO_UPDATE`；显式同key supersedes。冲突、撤销、过期先不实现，以免 silently 扩展 known/unknown schema。

时间、单位、公差规则在模型实验前定义。跨单位任务另行立项；不要把NHC双单位显示取整误差直接当预测允许误差。

### P2第一批仅三类

#### A. 部分更新：遗漏不是删除

示意：同一个实体和有效窗口，R1设wind=70、pressure=990；R2只更新wind=80。

Gold必须是wind=80引用R2，pressure=990仍引用R1。不能把所有字段都重置为unknown，也不能把压力的来源改为R2。

匹配对只改变patch的一项值或有无该patch；其他key不变。加入等值重发：值不变但来源按公开规则刷新，和“遗漏所以来源保留”区分。

必须击败：last-arrival、整记录overwrite、always-update。正确的每key reducer应满分。

#### B. 同有效窗口纠正：旧版本不能复活

R1对FactKey K报80；R2显式supersedes R1对K的值，改为65；之后重复投递R1。Gold仍65引用R2。

必须同时提供一个不同实体或不同valid window的更新作为最小干扰：它不能覆盖K。不把新的观测时刻直接标成对旧窗口的纠正。

对supersedes图要求：不跨非法key、不成环、目标合法；无明确顺序的冲突不进入初版主评分，不能靠record_id字典序任意裁决。

必须击败：latest delivery、最大数值、忽视有效窗口、重放旧版本。正确per-key版本resolver是上界，不要求它失败。

#### C. 可恢复缺失：同字段known/unknown成对出现

同一FactKey构造两个分支：一边在首次查询前提供全部必要支持，另一边在首次查询前withhold所有支持副本；后者晚一轮才交付。前者known、后者先unknown再known；无关key完全相同。

关键：不只删摘要而保留正文；使用受控source card时可精确列举支持集合。不能因为资料下载/解析失败就制造unknown Gold。

关键：已经看见且仍有效的事实，不会仅因原文离开上下文就变unknown。若要测forgetting那是另外的有限证据窗口诊断，不与此任务混合。显式撤销前不做known→unknown主张。

必须击败：always-unknown、无支持时照抄别的窗口、提前回答未来值；正确可见支持程序通过。

### Provenance

真实源值保留原source id；生成的数字或变换标 `fact_origin=generated_by_spec`；交付标controlled。生成卡片不得冒充官方NHC公告，不添加伪官方签章/来源。将不可见的Gold、未来计划和generator隐藏变量排除在模型视图之外。

## 12. R08：自动Gold的双实现与变形测试

### 不把“独立审计”混同为语义独立

主参考编译器A按交付事件顺序做event-sourced reduction。独立oracle B按每个FactKey查询当前可见候选集合、显式supersedes关系和有效窗口，计算应保留的值与支持集合。B不能调用A的状态更新或冲突解析函数；可共享schema、hash和精确数值类型。

再用小型显式预期fixtures验证二者，避免“两份代码同样理解错公开规则”。这不需要逐题人工标注真实样本；它是研究规格的可执行单元测试。

### 必做关系

| 变形 | 预期 |
|---|---|
| 重复投递旧卡片 | 不改变当前值/权威来源 |
| 相同窗口同key被新证据supersede | 更新目标key，不影响其他key |
| patch遗漏字段 | 值和来源都保留 |
| 全部时间等量平移 | 去除绝对时间后的输出关系相同 |
| 实体与record ID一致双射改名 | 输出随键名对应、语义不变 |
| 无依赖patch调换顺序 | 最终状态相同 |
| 必要支持整体延后 | 首个可回答点同步延后 |
| 同数值换成不同变量/窗口/单位 | 不再是有效支持 |
| 加入无关实体卡片 | 目标key不变 |
| 输入未来secret marker | public_view/audit必须阻止 |

生成任何新题之前验证这些关系。程序控制必须预先冻结，不按照DeepSeek失败题选样。正确程序不接触Gold文件，只读取公共视图。

### 自动化不能覆盖的边界

有限语法以外的任意自然语言蕴含、无明确优先级的跨来源争议、真实港口操作最优性、未知历史首次公开时间：均不进入当前自动主Gold。必要时标unverifiable/quarantined，而非强行判断为模型幻觉。

## 13. R09：题集、指标和开发规模

### 先12条微轨迹，全部只跑程序

三类语义 × 两档最小干扰 × 两个匹配分支 = 12条五检查点微轨迹。用于语义和代码验收，不是12个独立真实风暴。保证至少一次必要更新、一次必要保留、一个来源判别；题量可由固定覆盖规则调整，不能按模型错题调整。

### 首轮P2 development候选矩阵

```text
3个development源组 × 3任务族 × 2匹配分支 × 5检查点
= 90个检查点机会 / 方法 / 模型 / 重复
```

三方法、一模型、一重复为270次请求；两模型、两重复为1080次请求。它们是待预注册设计，不是当前授权，也不是独立样本量；同源风暴和同base scenario的所有变体归为同组。

优先在三个任务族都通过程序验收后，用校准选出的统一配置执行一次完整dev矩阵。不能只执行看起来最难或预期最有利的族。没有预算选择时继续离线，不把任意较大token cap当已校准。

### 指标

主表至少有以下固定机会指标：schema成功、known grounded correctness、unknown正确率、required update成功、未受影响key保留、provenance正确/刷新、matched pair pass。两分支都答错但一致，不能取得pair pass。

另记：unsupported certainty（Gold unknown但模型known）、over-abstention（Gold known但模型unknown）、stale reliance、wrong-scope更新、来源错误、parser不支持语法、transport/length失败。

按method报告条件性自身错误恢复，但保留其模型相关分母，不拿它取代固定reference转移指标。没有机会返回null，不记100%。

程序支持检查无法证实时可在strict grounding记0，但原因应为unverifiable，不直接命名为false fact。报告自动支持语法覆盖和正/负例控制，避免把有限验证器的边界伪装成模型错误。

### 方法比较的边界

full-evidence下比较三种carrier仍是“答案表示与干扰”的比较。它本身不能证明memory necessity。新论文可以先以动态证据可靠性为主，不把有限窗口memory实验作为必需交付。

## 14. R10：方法差异与可选载体机制诊断

完成校准与P2自动验收后，先一模型完整dev矩阵，再增加预先选定的第二模型家族和统一重复数。选择应绑定具体provider/model ID与成本许可；本计划不选择或授权新的付费provider。

若确实要研究carrier机制，另立有限证据窗口诊断：从同一个真实已生成前缀分叉，保持当前证据不变，仅对carrier做actual/reset/delete/wrong-entry。记录分叉前缀hash、target frontier、无关key控制；未来随机生成的输出各自重新采样，不拿同一结果当多个重复。

不在正式模型输入中提供私有Gold或oracle carrier；正确程序上界属于离线控制。将“被控外部载体的影响”与“模型内部记忆机制”区分。错误条目遇到当前充分证据时应被纠正，不奖励盲从。

无历史证据的snapshot本来就信息更少，其下降不能单独说明记忆质量差；与full-evidence参考分开展示。此诊断可后置，不阻塞第一篇聚焦证据更新的结果包。[S12]

## 15. R11：heldout与发布复现

### 两个测试域分开

原NHC heldout：7风暴 × 2分支 × 5检查点 = 70机会/方法。若三方法、两模型、两重复，共840请求。

P2 heldout候选：7源组 × 3任务族 × 2分支 × 5检查点 = 210机会/方法。相同三方法、两模型、两重复，共2520请求。

这两个数字只是完整候选设计成本计数。优先决定论文要支持的结论，再冻结实际范围；不要默认全部自动运行。原始资料、源组衍生题、同一base seed的变形和翻译都不能跨split。测试模板泛化还需要单独template split，不能只靠storm split声称。

### 统计

development仅描述；三个风暴不做伪精确总体显著性。heldout报告每风暴与每任务族结果、原始分子/分母、方法配对差值。置信区间若使用重采样，以storm/source group为cluster；重复嵌套其中，七组仍不足以支持广泛强结论。不要用270或2520作为独立n。

访问测试资料用于构建完整性核验，不等于已经使用模型输出调参；一旦看过heldout模型结果后修改题集或评分，后续报告标exploratory，并保留新正式评估的未使用组。

### 复现层次

1. 数据复现：references原bytes/许可/准入和拒绝记录。
2. 编译复现：同规格得到同语义题集和split；位置变化的环境身份单列。
3. 评分复现：历史原响应+冻结评分器重算相同结果。
4. 新鲜推理复现：调用可变provider时重跑，不保证输出逐字一致。

保留当前原历史build ID。新版本考虑把稳定 `content_id` 与机器相关 `execution_id` 分离；这属于新schema，不能回写旧manifest。

新增CI仅跑离线tests/fixtures/references检查，不使用模型密钥、不扫描全部旧artifacts测试。只在实际验证过的Python平台声明支持；不要为了兼容矩阵无限扩展工程范围。

公开发布另行检查授权与第三方条款；当前私有审阅授权不等于公开数据发布授权。[S03][S13]

## 16. 推荐PR/任务边界

| ID | 主要交付 | 前置 | 验收关键点 |
|---|---|---|---|
| R00 | baseline记录 | 无 | 真实离线结果、历史不改 |
| R01 | calibration v1.1协议与新准备包 | R00 | timeout共同、270固定、无新变量 |
| R02 | contract-aware collector | R01 | actual wire一致、carrier隔离 |
| R03 | campaign ledger | R01 | 全局限额、未知不重试 |
| R04 | independent collection audit | R02/R03 | 独立重建曝光与费用 |
| R05 | 270-slot rehearsal | R04 | 故障矩阵通过、live-ready |
| R06 | 270 fresh calibration报告 | R05 + 明确授权 | 不选择性重跑、共同预算选择 |
| R07 | P2语义规格/schema | R00，可并行 | 三任务族、事实键与来源清楚 |
| R08 | compiler/oracle/metamorphic | R07 | 双实现不共享resolver |
| R09 | P2程序题集与controls | R08 | 捷径控制失败、正确程序通过 |
| R10 | P2 development模型比较 | R06/R09 + 明确授权 | 完整矩阵、第二家族后置 |
| R11 | heldout/复现报告 | R10冻结 + 明确授权 | 按组划分、按组统计、授权发布 |

不设置“跑得越多越完成”的KPI。阶段完成由可解释的验收和研究决策决定。不要继续把AGENTS里旧默认M1与当前已完成P1混为进度；增加最新scope章节但保留历史授权记录。

## 17. 第一轮发给Codex的指令

```text
请在当前 disastertrace-benchmark 仓库上增量实施，不整体重写。
先读取适用 AGENTS.md、REVIEW_FOR_CHATGPT_PRO.md、README_CALIBRATION_V1.md、
IMPLEMENTATION_STATUS.md、DECISIONS.md、BLOCKERS.md 和本计划。

基准提交是 a23f73adadcbec077b9fcf2aecf8f45dfa4fe061。
如果当前HEAD更晚，先记录相对该基准的差异，不覆盖新增用户修改。

本轮只做离线 R00-R05，以及可并行的 R07-R09；不启动任何模型请求。
先运行现有测试/资料校验，再添加故障回归测试并实现：
契约感知collector、独立采集audit、全矩阵累计账本、270-slot rehearsal。
对60秒timeout的改变使用独立协议修订和新准备包，保留原v1。

P2另建revision_tasks namespace，先实现部分更新、同窗口纠正、
可恢复缺失三个任务族。编译器和独立oracle不得共用状态resolver。
不得把新任务塞入原五字段协议，也不得更改P1 source/parser/scorer/原响应。

维持无新增逐题人工标注、无LLM judge主评分、无训练、无heldout模型调用。
不重试原未知第79次请求，不复用已消费授权，不自行将authorized改为true。
不把诊断回答用于live carrier，不把projection声称为actual exposure。

每完成一个任务，记录修改文件、实际测试命令与结果、产物身份、
未完成项和下一任务。没有真实执行的测试不得记通过。
缺少价格核验或模型授权时标live_ready_not_authorized，继续离线P2工作。
最终交付可复验的live-ready包和P2程序控制报告，不要只再写一份计划。
```

## 18. 近期最小成功定义

不是“再增加几千条题目”，而是同时得到：

1. 一个真正经过故障测试的新契约live-ready采集链路，随后能在明确授权下完成可解释的270次校准。
2. 一组无需逐题人工标注的P2题：正确程序通过；错误的last-arrival、整记录覆盖、总答unknown等程序在预定义反例上失败。
3. 一份把接口失败、证据理解、选择性状态更新分开报告的结果，而不是只呈现某方法100%。

如果校准消除了旧方法差距，这说明旧实验找到了重要测量混杂；如果P2仍全部接近满分，则按预先定义的新规格增加依赖结构，而不是按模型错题筛样。两者都应保留并诚实报告。

## 19. 来源与审阅范围

文中 `[Sxx]` 指下列提交固定的源码或记录；它们是本次读取的依据，不代表已经逐行审计全部仓库。

[S01]: https://github.com/sisuolv/disastertrace-benchmark/blob/a23f73adadcbec077b9fcf2aecf8f45dfa4fe061/disastertrace-starter/REVIEW_FOR_CHATGPT_PRO.md
[S02]: https://github.com/sisuolv/disastertrace-benchmark/blob/a23f73adadcbec077b9fcf2aecf8f45dfa4fe061/disastertrace-starter/AGENTS.md
[S03]: https://github.com/sisuolv/disastertrace-benchmark/blob/a23f73adadcbec077b9fcf2aecf8f45dfa4fe061/REFERENCE_BUNDLE.md
[S04]: https://github.com/sisuolv/disastertrace-benchmark/blob/a23f73adadcbec077b9fcf2aecf8f45dfa4fe061/handoff_validation/README.md
[S05]: https://github.com/sisuolv/disastertrace-benchmark/blob/a23f73adadcbec077b9fcf2aecf8f45dfa4fe061/disastertrace-starter/work/p1-deepseek-background-continuation-v1/report/REPORT.md
[S06]: https://github.com/sisuolv/disastertrace-benchmark/blob/a23f73adadcbec077b9fcf2aecf8f45dfa4fe061/disastertrace-starter/src/disastertrace/automated/dynamic.py
[S07]: https://github.com/sisuolv/disastertrace-benchmark/blob/a23f73adadcbec077b9fcf2aecf8f45dfa4fe061/disastertrace-starter/src/disastertrace/automated/collection.py
[S08]: https://github.com/sisuolv/disastertrace-benchmark/blob/a23f73adadcbec077b9fcf2aecf8f45dfa4fe061/disastertrace-starter/src/disastertrace/automated/collection_audit.py
[S09]: https://github.com/sisuolv/disastertrace-benchmark/blob/a23f73adadcbec077b9fcf2aecf8f45dfa4fe061/disastertrace-starter/src/disastertrace/automated/calibration.py
[S10]: https://github.com/sisuolv/disastertrace-benchmark/blob/a23f73adadcbec077b9fcf2aecf8f45dfa4fe061/disastertrace-starter/src/disastertrace/automated/provider.py
[S11]: https://github.com/sisuolv/disastertrace-benchmark/blob/a23f73adadcbec077b9fcf2aecf8f45dfa4fe061/disastertrace-starter/docs/CALIBRATION_PROTOCOL_V1.md
[S12]: https://github.com/sisuolv/disastertrace-benchmark/blob/a23f73adadcbec077b9fcf2aecf8f45dfa4fe061/disastertrace-starter/OPTIMIZATION_ROADMAP.md
[S13]: https://github.com/sisuolv/disastertrace-benchmark/blob/a23f73adadcbec077b9fcf2aecf8f45dfa4fe061/README.md

外部接口核验：DeepSeek官方 API reference 与 first-call guide表明模型别名/版本和接口参数会演化，因此正式执行前需重新绑定官方配置和价格快照。本次在线价格入口返回的内容不足以建立新的计费表，本计划没有用搜索摘要更新仓库价格。历史金额仍仅作为历史记录。

```text
https://api-docs.deepseek.com/api/create-chat-completion/
https://api-docs.deepseek.com/quick_start/
https://api-docs.deepseek.com/quick_start/pricing
```
