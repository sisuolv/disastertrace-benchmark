# DisasterTrace：基于现有审查快照的下一阶段 Codex 执行计划

> 基准仓库：`sisuolv/disastertrace-benchmark`
>
> 基准提交：`a23f73adadcbec077b9fcf2aecf8f45dfa4fe061`
>
> 主要依据：`disastertrace-starter/REVIEW_FOR_CHATGPT_PRO.md`、当前实现、P1 归档报告、校准协议及根目录交付说明。
>
> 交付性质：代码级静态审阅与后续实施规格。本次没有修改远端仓库、调用模型、读取凭据、重跑该仓库的 684 项测试，也没有产生新的模型成绩。文中的现有测试结果来自仓库保存的执行记录；所有新模块、验收条件和时间安排均是建议，不是已完成工作。

## 0. 最重要的决定

**不重写仓库，不再从旧 DisasterFrontier starter 开始，不立即接入新评测框架。**

本阶段目标是：

1. 把现有 `legacy_4096 / explicit_4096 / explicit_8192` 离线校准包接入真实、可追溯、可控制预算的执行链路。
2. 用新鲜开发集结果区分输出契约、输出预算与回答载体的影响，而不是继续把 P1 的分数差解读为记忆优势。
3. 独立开发 P2 最小任务集：**部分更新、同有效窗口纠正、可恢复的证据缺失**。保留原 NHC 主线，给新增生成内容和评分语义独立版本。
4. 在共同契约、预算、任务和评分冻结后，再开展第二模型与留出风暴实验。

### 0.1 当前约束

- 不新增逐题人工标注、专家打分或 LLM judge 主评分。
- 不把受控交付写成已证明的历史首次公开可用时间。
- 不把研究阈值写成 NHC、USCG 或港口的真实操作政策。
- 不把模型输出显式 JSON 写成已识别的内部记忆机制。
- 不把 CyPortQA 的 48 个模板声明写成 48 个完整实例或已恢复的多模态数据集。
- 不把 230 条 DisasterBench 继承计划控制合并为 NHC 天气主线题目。
- 原 P1 的授权已消费；新 270 次请求和 USD 3 都只是拟议范围，不是实际调用授权。
- 训练、权重下载、留出集调用、自动重试、公开发布、push、删除历史，均不属于本计划默认执行权限。

### 0.2 当前源材料的优先级

当前实现与实际运行产物 > `REVIEW_FOR_CHATGPT_PRO.md` 的当前说明 > `IMPLEMENTATION_STATUS.md` 最新条目 > `DECISIONS.md` / `BLOCKERS.md` > 历史大计划。

必须额外读取根目录 `README.md`、`REFERENCE_BUNDLE.md` 与 `handoff_validation/README.md`：它们补充了打包后的事实。审阅说明提醒外部 references 可能缺失，但这个 GitHub 快照已经携带构建所需的精简 references；不要继续把“缺少全部外部资料”列为已确认的阻塞。

---

## 1. 当前基线：必须保留的事实

### 1.1 已经完成，不要重复开发

| 项目 | 当前证据支持的状态 |
|---|---|
| NHC 获取、来源和准入 | 12 个候选风暴，36 份获取记录，32 份解析成功；10 个风暴具备完整三公告 |
| 划分 | 3 个开发风暴：Ida / Florence / Dorian；7 个留出风暴尚无真实模型推理 |
| 轨迹 | 每风暴 base、delay 两分支，各五检查点；开发共 30，留出共 70 |
| 三种方法 | snapshot、structured_state、answer_history 均接收累计交付原文 |
| 已实现评分 | V1 与 V2，限制语法的等价证据支持、已知字段主指标、固定分母、离线重评 |
| P1 | 90 个保存响应、91 次累计请求尝试；原 attempt 79 仍未知，另有一次明确授权的重发 |
| 契约校准准备 | 三条件、九个条件×方法单元、54 条轨迹、270 个拟定机会 |
| 离线产物 | 128 个校准产物、54 条未发送初始请求、1,080 个程序诊断回答 |
| 交付验证记录 | 新环境 684 passed / 57.41 秒；另有历史 6,979 项自动审计检查 |

这些数量的单位不同，不可相加，也不构成人工复核、模型样本量或论文显著性的证据。

### 1.2 P1 结果与研究解释

| 方法 | 结构有效 / 30 | V2 已知字段 grounding / 96 | V2 全字段 grounding / 150 |
|---|---:|---:|---:|
| snapshot | 14 | 39 | 69 |
| structured_state | 30 | 96 | 150 |
| answer_history | 24 | 76 | 120 |

已保存的归档分析：

- 20 个回答触及输出上限；另有两个输出结构错误。
- 全部 68 个结构有效回答的字段值、状态和 action 均正确。
- snapshot 仍有一处最大风速的引用指向移动速度所在行，未获得 V2 支持。
- 以上有效回答条件诊断不能替换包含失败的固定分母。

**可支持的结论：当前端到端可靠性差异很大，但存在显著格式、推理/输出预算和载体示例混杂。**

**不可支持的结论：structured_state 已证明记忆机制优势、已解决灾害推理，或 snapshot 没有记忆。**

本阶段应把这一现象视为需要解释的测量问题，而不是宣传性的算法增益。

### 1.3 两条研究线，不混为一个成绩

- **NHC source-grounded reference track**：不改写真实公告，测最新已交付报告及引用；维持现有定义。
- **Controlled update track / P2**：从明确记录和操作生成可验证的更新任务，测组合语义；生成值、编辑、时间和规则必须标为 controlled/generated。

后续可选的有限证据载体诊断、视觉轨道和 FrontierSearch 均另行命名，不改变上述两条线的含义。

---

## 2. 按优先级排列的审阅结论

| 编号 | 证据与问题 | 影响 | 必须采取的动作 |
|---|---|---|---|
| R1 / P0 | `collection.py` 调用旧 `render_request`；校准目前没有新契约真实采集入口 | 不能直接运行 explicit 条件并声称曝光已验证 | 新建契约感知 collector，保留原 collector 和历史日志 |
| R2 / P0 | `score_rehearsal` 明确限定 diagnostic_program、零请求 | 不能把程序 rehearsal 改标签当成真实实验 | 新建 live audit/report 路径，先验证 actual，再生成兼容投影 |
| R3 / P0 | 通用 collector 明示没有货币 cap；P1 的累计账本在专用实验脚本中 | 逐个启动九个独立 cell 可能重复使用额度 | 一个实验级调度器、一个累计账本、一个启动归属 |
| R4 / P0 | P1 有已发生的重启与未知请求 | 自动续跑可产生重复付费、未知费用丢失 | 持久化发送前日志，不确定请求阻塞自动恢复 |
| R5 / P0 | 当前 provider 的失败路径不保证返回已收到的原始 body；HTTPError 分支返回空 body | 不能假定新 collector 能完整保留所有错误响应 | 明确 transport 层捕获策略，安全保存可获得的原始错误/部分 body 与不可获得原因 |
| R6 / P0 | `timeout=60` 被传给 urllib blocking timeout | 它不是硬性的总墙钟 deadline；8192 条件可能增加时间截断 | 先冻结 timeout 语义，必要时使用统一、预声明的执行修订 |
| R7 / P1 | 68 个结构有效回答值全对 | 现任务可能以抽取为主，扩数据不一定提高能力区分度 | 校准并行开发 P2，先增加语义而不是题量 |
| R8 / P1 | `port_reopening_time` 始终未知 | 存在字段级固定答未知捷径 | P2 对同一天气字段构造可答/不可答/恢复的匹配任务 |
| R9 / P1 | `reference_at` 选一个最新公告后填写所有字段 | 不能正确覆盖 patch、同窗口纠正和按字段保留来源 | 为 P2 新建 per-fact-key resolver，不复用旧 latest-report Gold |
| R10 / P1 | 实际 references 已打包，历史 build 有路径绑定 | 旧绝对路径不等于新构建不可复现 | 新路径重建并比较内容不变量，不修改历史 manifest |
| R11 / P1 | `provider.validate_public_request` 写死 v1 protocol、FIELDS 与 POLICY | P2 的四字段或新事实键请求不能直接送进原 ProviderClient | 保留 v1 guard；为 P2 新建显式协议验证/适配层，只复用安全传输与序列化 |

R1–R6 是已读代码揭示的实现缺口或设计风险，不是本次通过运行确认的新 bug。必须用回归/故障注入测试验证具体实现。

---

## 3. 实验决策：在写 live launcher 前冻结

### 3.1 保留三条件，不默认增加第四条件

继续使用现有三个条件：

| arm | 契约 | 输出上限 | 机会 |
|---|---|---:|---:|
| legacy_4096 | legacy_v1 | 4096 | 90 |
| explicit_4096 | explicit_v1 | 4096 | 90 |
| explicit_8192 | explicit_v1 | 8192 | 90 |

它们足够回答两个局部对比：

- explicit_4096 − legacy_4096：在 4096 下，这份公共契约的影响。
- explicit_8192 − explicit_4096：在显式契约下，增加预算的影响。

不能计算完整的契约×预算交互；除非研究目标确实包含交互，否则不增加 legacy_8192 的 90 次请求。

保留三方法、三开发风暴、两分支、五检查点、一次重复与现有轮换执行顺序。不能用 P1 历史 90 个响应替代此次 concurrent control。

### 3.2 timeout 决策

原 v1 的 `timeout=60` 已被冻结；不能修改原文、旧 config 或 P1 包。

建议：在任何新模型响应出现前，单独形成 `execution_amendment_v1_1.json`，将所有条件共同的传输等待上限设为 180 秒，并声明/测试总墙钟 deadline。180 秒是工程建议，不是经模型实测的充分预算。研究者若选择原样执行 v1，则保持 60 秒并清楚报告该 ceiling；不得一部分 cell 用 60 秒、另一部分用 180 秒。

首选实施方式：

- 默认先完成同时支持 v1 原配置与显式执行修订的离线代码。
- 校准协议、回答 parser、公共任务内容与 V1/V2 scorer 不变。
- 修订绑定 timeout、deadline 语义、传输实现和修订理由，产生新 execution identity。
- 独立审计检查每个 arm 的共同 timeout 一致。
- 没有正式执行选择与授权时，停在 READY_FOR_AUTHORIZATION。

不得将 urllib 的每次阻塞超时宣传为整个请求的硬上限。若采用进程隔离实现 deadline，必须测试超时杀死后没有后台重试，未结算请求仍保留 reservation。

### 3.3 不同时加入的因素

此次不增加 JSON mode、约束解码、自动 JSON repair、thinking on/off、low/high reasoning 对比、示例答案或新语言 prompt。

这些因素会引入额外干预。尤其不要通过设置 temperature=0 声称 DeepSeek thinking 模式已变成确定性；官方文档说明该模式不使用此参数。provider 返回的 reasoning_content 不作为 benchmark 最终答案，也不得从中补取 JSON。

### 3.4 校准报告必须回答的分支

- 若三方法均接近满分：P1 差距主要与本次契约/预算设置有关的解释得到支持，但不等于单独识别了哪个具体机制；保留历史结果，转向 P2。
- 若格式问题改善后仍有引用/状态错误：按既有原因码分析，不能选择性修题或重跑。
- 若 8192 仍多次截断或发生 transport failure：返回 no_selection，另起有版本的新实验；不能自动升级 16384。
- 若矩阵不完整或审计失败：没有共同预算推荐，保留完整 planned denominator 与未发送状态。

---

## 4. PR-N00：新环境基线复现与来源固定

### 输入

读取根 README、REFERENCE_BUNDLE、handoff_validation，以及项目 AGENTS、REVIEW、IMPLEMENTATION_STATUS、DECISIONS、BLOCKERS、校准协议。

### 动作

1. 记录 HEAD 与工作区 dirty 状态；不能 reset 或覆盖用户修改。
2. 核对 references inventory / checksum，确认当前工作区确实有所需数据。
3. 按 Python 3.10 已验证配置建立独立环境；开发依赖安装和模型调用授权分开。
4. 只运行当前 `tests/`，不递归执行 historical artifacts 中的归档测试。
5. 以全新 output path 执行 build → calibration prepare → verify。
6. 把原 source/parser/scorer/数据/归档的保护范围写入版本清单。

### 现有可执行命令

从仓库根目录开始；没有 `.venv` 时先按 README 安装开发环境。

```bash
set -euo pipefail
git rev-parse HEAD
git status --short
(cd references && sha256sum --check REVIEW_REFERENCE_SHA256SUMS)
cd disastertrace-starter
.venv/bin/python -m pytest tests -o addopts= -q

RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)"
.venv/bin/disastertrace-auto build \
  --references ../references \
  --nhc-snapshot ../references/nhc_cohort_v1 \
  --output "work/review-build-${RUN_ID}"
.venv/bin/python -m disastertrace.automated.calibration prepare \
  --build "work/review-build-${RUN_ID}" \
  --provider-config artifacts/p1_deepseek_development/provider.json \
  --output "work/review-calibration-${RUN_ID}"
.venv/bin/python -m disastertrace.automated.calibration verify \
  --output "work/review-calibration-${RUN_ID}"
```

不要执行无主分派的 `python -m disastertrace.automated.cli build`。

### 输出

建议新建 `artifacts/next_phase/baseline/`，记录命令、退出码、环境、源标识、测试日志、构建结果。缺依赖或权限时如实 BLOCKED；不能引用历史 684 passed 冒充本轮通过。

### 验收

所有现有测试在新环境重新运行；新增内容尚未实现时预期基线为 684，但以实际 collection/count 为准。路径不同允许新 build ID，不允许修改旧 manifest 伪造同 ID。重新构建的事件、划分、准入和语义内容应与基线一致。

---

## 5. PR-N01：契约感知真实采集器

### 建议新增文件（尚不存在）

```text
src/disastertrace/automated/calibration_collection.py
tests/test_calibration_collection_live_contract.py
```

复用而不重写：

- `output_contract.render_calibration_request`
- `output_contract.contract_spec`
- `provider.ProviderClient.prepare`
- `dynamic.parse_decision`
- `calibration.make_schedule`
- 已有 `common` 序列化、哈希与安全路径函数。

### 输入边界

collector 接收明确的 execution plan、条件、method、episode、checkpoint 和真实 carrier。不得直接序列化完整 episode 或 build 目录给模型。

同一条轨迹的主键至少为：

```text
experiment_id / arm_id / method / event_id / branch / repeat
```

每个 request 记录：

```text
slot_id, trajectory_id, checkpoint_id
contract_id, contract_version
public_request, public_request_sha256
prepared.endpoint, prepared.config, prepared.payload
raw_wire_request, wire_sha256
carrier_before_sha256, predecessor_response_sha256
implementation_id, build_id, schedule_sha256
```

### 关键流程

1. 用该轨迹此前真实且结构有效的答案重建 carrier。
2. 调用契约感知 renderer。
3. `ProviderClient.prepare` 生成候选 wire payload；此步骤不得读取凭据或触网。
4. budget guard 放行后才发送。
5. 记录底层实际准备/发送的 bytes 与预先哈希的一致性。
6. 保存收到的 provider 原始 body，然后验证 envelope/usage，再解析最终 content。
7. 结构无效答案保留、计失败、不替换最后有效 carrier。
8. 结构有效但事实错误答案原样写入 carrier；不能由 Gold 修复。

### 失败捕获补充

当前 `provider.py` 的部分错误分支抛出异常后不携带原始 body，`urllib_transport` 的 HTTPError 分支返回空 bytes。新采集层不能宣称这些失败已经自动完整保存。

新增传输观察层或显式版本化 transport wrapper，在正常解析前捕获可获得的响应；严格限制大小，清理凭据反射，记录 capture_kind、truncated、HTTP 状态和安全错误码。不要保存 Authorization/header 密钥，不要打印完整环境变量或异常 repr。

没有 provider 响应的超时/断网只能标为 unknown/missing，不得伪造原始 body。捕获错误 body 不得被当成有效模型回答或合法 usage。

现有 `collection_audit.validate_completion` 对 metadata 使用精确键集合验证。新增 capture、contract 和账本字段应放在有独立版本的外层记录，或由新审计协议显式接受；不能随意往旧 completion metadata 添加键后绕过旧校验。

### 必须测试

- legacy_v1 公共请求与原 renderer 一致。
- explicit_v1 只改变公共 instruction，不改变证据/规则/载体。
- 三方法获得相同证据；只有声明的 carrier 不同。
- 54 条轨迹独立；另一 arm/branch/repeat 的有效答案不能混入。
- 无效答案不覆盖此前有效答案；错误但结构有效的答案会传播。
- 当前 c0 不注入填好的全 unknown 示例。
- 后续请求不使用 rehearsal 的程序回答。
- raw wire 与审计输入一致；不存在记录一种 prompt、实际发送另一种的路径。
- 错误 envelope、超大/非 UTF-8 body、空 content、length finish 分开保存。
- 反射凭据的响应不可公开归档；安全错误仍进入账本。

---

## 6. PR-N02：单一累计预算、调度与崩溃安全

### 建议新增文件

```text
src/disastertrace/automated/calibration_execution.py
src/disastertrace/automated/calibration_budget.py
tests/test_calibration_scheduler.py
tests/test_calibration_budget_and_crash.py
```

### 复用来源

- 现有 `collection._append` 的追加写、flush/fsync 思路。
- P1 专用 `run_experiment.py`、`background_resume/` 中的单次启动与累计费用思想。
- 原逻辑可抽出成新模块，但不得重写旧归档脚本、attempt 79 或消费过的 authorization。

不得分别给九个 cell 各分配一个 USD 3 预算。一个实验拥有一个总账本。

### 持久化状态机

```text
PLANNED
  -> PREPARED
  -> RESERVED
  -> DISPATCH_INTENT_RECORDED
  -> RESPONSE_CAPTURED
  -> ENVELOPE_AND_USAGE_VERIFIED
  -> DECISION_ACCEPTED | DECISION_REJECTED
  -> SETTLED
```

异常分支至少区分：

```text
NOT_SENT_GUARD_BLOCK
UNCERTAIN_INFLIGHT
TRANSPORT_ERROR
ENVELOPE_INVALID
USAGE_INVALID
AUTHORIZATION_INVALID
```

重要约束：

- 发送意图和费用预留先持久化，后发送网络请求。
- 独立保存 planned slot、admitted attempt、是否观察到 HTTP send、received response。它们不是同一个计数。
- 本地锁和请求 ID 不能保证服务端 exactly-once；未知请求不能自动重发。
- 任何已经保存的响应，包括无效回答，都不得因重启而重新生成。
- 未知发送保留 reservation；重启后只做 offline audit，不默认继续 live。
- 必须分别记录“未发”“发出但结果未知”“收到不合法回答”。
- one-use launch claim 的位置不依赖用户随意更换 output 目录，防止换目录重复启动。
- PID 复用或只看到 execution.json=running 不能证明原 worker 仍活着。

### 费用语义

金额使用 Decimal 或整数最小货币单位，不用 binary float 决定是否放行。

```text
settled_conservative_cost
+ unresolved_reservations
+ next_request_reservation
<= authorized_experiment_allowance
```

当前 v1 历史捕获价格下的单次预留为 0.46678016 / 0.47218688 美元。它们不是本次已核准的新现价。启动前必须重新捕获官方价格、模型限制和时段定义，并绑定 identity；变化时生成新的 accounting amendment。

USD 3 是条件停止额度，不能承诺全部 270 次必然完成。不要按历史均值、请求 bytes 或“通常只有几千 token”擅自减少预留。优化预留只能作为有明确输入上界及安全证明的后续工程工作。

- completion 已含 reasoning 时，不重复计费。
- 有效 usage 结算后才释放多余预留。
- 不合法 benchmark JSON，但 envelope/usage 有效：记模型失败，可继续。
- provider 错误、未知发送、非法/缺失 usage、超 cap、非预期模型 alias：保留记录并停止后续调用。
- 原 attempt 79 的费用不转入新实验，也不当作零；不要使用原 P1 剩余额度冒充新授权。

### 运行环境

采用单 writer、追加 journal 与周期性可重建 summary。直接借鉴已有架构即可，不引入 Redis/Celery/新数据库。持久目录应位于已确认的持久存储，但不能仅凭路径名认为文件锁与 fsync 已获得断电保证；用实际部署文件系统进行双启动、杀进程和读回测试。

### 崩溃注入验收

在以下边界逐一注入异常，再离线重建：

1. plan 写入后。
2. reservation 写入后、dispatch intent 前。
3. dispatch intent 后、响应前。
4. 收到 body 后、summary 前。
5. 解析完成后、carrier 提交前。
6. usage 结算前后。
7. 写入最后一条 journal 时出现部分行。
8. 同一实验不同 output 目录同时启动。

不确定性必须保守保留。不会因为 summary 尚未更新而重复收费，也不会把缺失回复填成程序答案。

---

## 7. PR-N03：独立采集审计与校准报告

### 建议新增文件

```text
src/disastertrace/automated/calibration_collection_audit.py
src/disastertrace/automated/calibration_report.py
tests/test_calibration_live_audit.py
tests/test_calibration_live_report.py
```

### 独立审计职责

从 plan、原始 request/body、usage、journal 重建：

- 270 个 planned slot 是否各有唯一 disposition。
- 每一请求的 contract、config、模型 alias 和 source binding。
- 当前原始材料是否仅含此前已交付证据。
- carrier 是否来自本轨迹真实且已接受的前序答案。
- source、response、wire hash 是否一致。
- attempt/reservation/settlement 是否守恒。
- 剩余 planned slots 与停止原因是否一致。

不能只读取 runtime 写入的 `verified=true` 或 summary 计数。审计可以复用严格 JSON、哈希和公开 schema，但关键 journal replay/费用计算不能只调用 runner 的同一函数然后声称独立发现错误。

### actual trace 与 scoring projection

保留现有 V1/V2 scorer，采用明确的兼容 wrapper：

1. 完整验证实际 collector 的公共请求和 wire body。
2. 保存不可改写的 actual trace。
3. 在独立文件中，只把 instruction 投影成旧 scorer 所需内容；其余证据、carrier、回答与失败机会不变。
4. 用冻结 scorer 计算指标。
5. report 同时绑定 actual hash、projection hash、投影规范和独立采集审计结果。

禁止把 `score_rehearsal` 中的 diagnostic_program/零请求限制简单删除；那是离线程序校验入口。新增 live score entry，禁止以程序控制输出充当模型证据。

哈希审计只能证明归档内部一致性，不能提供服务商签名级别的真实性证明；保留当前审计文档已有的这一边界。

### 报告字段

每个 arm×method 保留：

- planned=30，received，schema_valid，unsubmitted，uncertain_attempts。
- known grounding：固定 96 分母。
- unknown correctness：固定 54 分母，同时单列 port 常未知控制。
- overall grounding：固定 150 分母，仅作补充。
- 固定参考 changes=64、preservations=56、provenance refresh=8。
- length finish、empty final、partial JSON、结构错误、引用原因。
- valid-only 值/证据正确率，仅作条件诊断。
- actual usage、reasoning/content 分解、缓存字段、费用小计与未知预留。
- 成功传输延迟与 timeout 数，不能把超时当作延迟缺失后直接宣称更快。
- 三风暴配对差、event macro、base/delay；不声称总体显著性。

### 共同预算选择

保留 v1 规则：完整且独立审计通过的 270 响应，usage 有效；每方法至少 29/30 schema valid、最多 1/30 length；选满足条件的最小共同预算，否则 no_selection。

不得只调用 `screen_budget` 就给出 live recommendation。其结果现有 `evidence_validated=false` 是正确边界。29/30 是开发筛选，不是 95% 总体可靠性证明。

### 篡改测试

改契约但重算所有局部哈希；跨方法挪 carrier；复制另一实验 response；遗漏一次计费；把 pending 改 zero；重复 slot；删除失败行；将 full denominator 改 received denominator；篡改投影中的非 instruction 字段——以上必须被独立审计或明示的可信根验证拒绝。

---

## 8. PR-N04：冻结执行包，等待独立授权

### 准备产物

```text
plan.json
schedule.jsonl
execution_amendment.json        # 如采用统一 timeout 修订
provider_configs/
pricing_snapshot/
source_and_implementation_manifest.json
protected_history_manifest.json
runtime_fault_tests.json
collection_audit_tests.json
authorization.template.json
LAUNCH_READINESS.md
```

`authorization.template.json` 必须 `authorized=false`。Codex 不能自己改成 true 或代替用户生成批准。

### 执行包验收

- 全部旧测试和新增测试实际通过，网络在 offline 测试中被阻断。
- 九 cell/54 trajectory/270 slot 计数与隔离验证通过。
- 故障注入后费用和载体一致。
- 新 implementation/build/preparation/execution identity 明确，旧归档不变。
- 配置和代码冻结后才进入 READY_FOR_AUTHORIZATION。
- 实际 live 运行必须独立获模型、方法、条件、次数、费用、timeout 和重试范围授权。

以下命令名只是建议的新接口，不是当前仓库已经支持的 CLI；实现后必须以 --help 和离线测试验证：

```text
python -m disastertrace.automated.calibration_execution prepare ...
python -m disastertrace.automated.calibration_execution preflight ...
python -m disastertrace.automated.calibration_collection_audit verify ...
python -m disastertrace.automated.calibration_report report ...
```

本计划不提供可以误启动旧 P1 或新付费批次的默认 live 命令。

---

## 9. PR-N05：P2 新语义数据契约（可与 N01–N03 并行离线设计）

### 原则

保持 NHC v1 原轨道不变。P2 使用独立 protocol 与 dataset/scorer identity；不得让同一个函数名偷偷改变“最新公告”和“同有效窗口纠正”的定义。

初版只做三种能力，不做自由文本冲突判断、真实港口调度、图像、工具执行或训练。

### 建议新增结构

```text
src/disastertrace/automated/updates_v2/
    schema.py
    public_view.py
    generator.py
    reference.py
    audit_reference.py
    scoring.py
    controls.py
    cli.py
```

建议 protocol：`disastertrace_controlled_updates_v2`。这是新提议，尚未实现。

### 事实身份

```text
fact_key = (entity_id, variable, valid_window, measurement_kind)
```

同一变量但不同窗口不是同一个事实。全局最新 document 不能覆盖其他 entity/window 的值。

每个可见更新至少声明：

```json
{
  "record_id": "u002",
  "issued_at": "2030-01-01T10:00:00Z",
  "delivered_at": "2030-01-01T10:02:00Z",
  "entity_id": "synthetic_storm_A",
  "valid_window": ["2030-01-01T12:00:00Z", "2030-01-01T18:00:00Z"],
  "measurement_kind": "controlled_report",
  "operation": "patch",
  "updates": {"maximum_wind_mph": 110},
  "supersedes": {"maximum_wind_mph": "u001"},
  "source_origin": "controlled_generated"
}
```

上述数值、2030 日期和实体仅为 schema 示例，不是实际天气数据或候选实验结果。

### public / private 边界

可公开：任务语义、当前时间、查询 fact scope、已交付记录与原文行号、声明的先前回答载体。

不可公开：Gold 当前值、预期更新集合、expected affected fields、family fail 标签、未来 schedule、程序 control 的答案、oracle relation verdict。

生成器和 reference 可以持有内部 annotations，renderer 必须字段白名单选择，不能把内部对象全量 dump 到 prompt。

### 初始输出范围

优先保留 known / unknown 和数值值/行引用的有限表达能力，不加入新 conflict status。如使用原五字段形状，`port_reopening_time` 只作为 legacy sanity control，不能计入新增 answerability 主贡献。也可在新的 P2 protocol 中采用四个天气字段；两种 schema 必须在首次生成模型任务前选定并写入 spec，不能按模型表现切换。

推荐最小选择：P2 使用四个天气字段、单一查询实体/窗口的输出结构；输入可有无关实体/窗口，用于检查 scope。不要复用固定 FIELDS 的旧 parse_decision；复用严格 JSON 词法校验，定义新的固定 schema 和 parser。

### P2 请求也需要独立协议适配

`provider.validate_public_request` 当前验证 `disastertrace_text_v1`、原五字段和固定 POLICY；只增加 generator 不能让新请求直接进入旧 provider。建议增加 `updates_v2/provider_adapter.py` 或有显式版本选择的 public-request registry。保留 v1 的严格验证不变；新适配器先验证 P2 公共请求，再复用无重试、安全 URL、费用预留和原始 body 捕获的传输能力。不要把旧 validator 放宽成接受任意 dict。

NHC 输出校准的 collector 可继续只支持 v1 两种 instruction。P2 适配在 N05–N07 的独立实现中完成，并为 unknown protocol、私有 Gold 注入、错误字段集、跨协议 response 混用加回归测试。

---

## 10. P2 三个最小任务族与匹配反例

### U1：部分更新与来源保留

示例：

```text
u1：风速=90，气压=980，纬度=20，经度=-70
u2：只更新风速=110
```

正确：风速更新为 110 / 引用 u2；气压、坐标保留值且仍引用 u1。

匹配控制：u2 显式重复所有字段。两个版本的当前事实应一致，但未更新字段的 provenance 语义可能不同，按预声明规范判分。

禁止：遗漏被解释成撤销；整张表用最新 packet 重置；旧证据仍可用却全部答 unknown。

必须测量：更新准确率、未受影响字段保留、错误覆盖、每字段来源。

### U2：同有效窗口纠正与旧版重放

示例：

```text
u1：窗口 W，风速=90
u2：同窗口 W，明确 supersedes u1，风速=110
u1：迟到或重复到达
```

正确：最终仍为 110，引用 u2。

匹配反例：u2 的 valid_window 改为 W2，查询仍是 W。此时 u2 不能覆盖 W；仅按全局 latest issue 或 latest arrival 都会错。

初版限定明确无歧义的纠正链和自足的 replacement 值。版本环、重复 ID 不同内容、不可判定冲突为 invalid source/task，不变成模型应答 unknown 的题。

不得把受控生成的 110 或 supersedes 关系表述为 NHC 真实发布的纠正。

### U3：可恢复缺失与同字段可答性

同一变量、同一事实窗口，构造：

```text
A：支持从未交付 -> unknown
B：足够支持交付 -> known
C：迟交付分支先 unknown，恢复支持后 known
```

关键信息缺失必须在第一次曝光前实施；不能让模型先见答案，再删原文，就规定它必须忘记。

所有支持副本一起控制，包括摘要、正文重复、其他图表/metadata 中的答案。此前仍有效的同键支持存在时，不应仅因新 packet 省略该字段而判 unknown；这属于 U1 preservation。

匹配样本优先使用四个现有天气字段，而不是继续依赖永远未知的 port_reopening_time。

必须测量：known coverage、known correctness、unknown correctness、unsupported closure、支持恢复后的恢复速度。全 unknown、全填值两种策略都应失败。

### 三族共同约束

- 每个事实操作的语义公开；不能要求模型猜 generator 的隐含规则。
- 值域、种子、族比例、分支和排除规则先冻结，再看模型响应。
- 无关更新、重复记录、行号平移、独立键更新交换顺序不应改变事实结果。
- 同值新来源需要的 provenance refresh 与数值 change 分开。
- P2 的生成变换不是严格的自然历史 replay；数据卡明确标注。

---

## 11. PR-N06：双实现参考答案与可区分性验证

### 两个独立语义实现

- reference compiler：按规范对事件日志进行逐键归约，产生答案及 expected support。
- audit resolver：从当前可见记录、事实键和可见替代关系独立求解，不能直接读取 compiler 的最终状态。

可共用类型、哈希、严格 JSON 工具；不能完全复用决定 authoritative value 的同一 reducer，再称为独立验证。

### 控制程序

至少包括：

| 程序 | 用途 |
|---|---|
| correct_spec | 验证任务与主评分可实现 |
| latest_arrival | 检查旧版迟到/重复的破坏作用 |
| latest_document | 检查全局新文档覆盖全部字段的捷径 |
| overwrite_all_on_patch | 检查部分更新导致其他字段丢失 |
| ignore_valid_window | 检查同变量跨窗口混淆 |
| always_unknown | 检查不足证据模板捷径 |
| always_copy_previous | 检查拒绝修订与恢复失败 |
| value_correct_provenance_wrong | 检查只测数值掩盖来源错误 |

每个任务族必须至少拒绝它对应的错误策略。正确程序满分是工具验证，不是证明 LLM 已具备能力。

### 验证不以测试数量为目标

验收目标是独立 reference 一致、负控在预定机会失败、public view 无私有 Gold、元数据可追溯，以及错误分支不被生成器静默排除。不设“必须达到 1000 tests”这类无研究意义目标。

### 最小开发包建议

规模仅为规划目标：

```text
3 个开发风暴来源组
× 3 个能力族
× 2 个匹配分支
× 5 个 checkpoint
= 90 个 checkpoint opportunities / 方法 / 模型 / 重复
```

这些并不是 90 个独立风暴。开发全部三方法、一个模型、一次重复为 270 次新请求，需单独准备/授权；不要混入前述输出校准的 270 请求预算。

若某条新语义需要更多 checkpoint，在预冻结生成清单时重新计算精确数量；不可用表中目标覆盖实际 schedule。

---

## 12. PR-N07：开发阶段检验，不急于使用 heldout

### 执行前

先完成输出校准，选统一契约与预算。P2 的更长公共说明/历史可能再次影响输出，所以做离线大小检查并预声明统一运行设置；不得假定 P1 的预算结论无条件适用于任意长度的 P2。

若需要新预算校准，独立命名；禁止按方法或仅按失败 cell 选预算。

### 研究问题

1. 在格式可用时，模型能否保留 patch 未改字段的值与来源？
2. 明确纠正同一窗口后，旧包晚到是否重新覆盖新事实？
3. 同一变量的 known/unknown/recovery 是否真实变化，而非固定字段模板？
4. 回答载体是否降低或放大错误传播？这是当前全证据设置下的载体效应，不是内部记忆证明。

### 主指标

以任务族分开报告：

- 已知字段 grounded accuracy（固定 opportunity denominator）。
- 更新字段准确率与 preservation 准确率。
- 同窗口纠正成功与 stale override。
- known/unknown matched pair 双通过率与恢复准确率。
- provenance freshness / inherited provenance correctness。
- schema、length、transport、费用作为独立维度。

action 仍是研究规则执行的辅助指标。不要让同一 wind 字段决定的 action 与字段正确率双重包装成两个独立推理能力。

### Go / 修订逻辑

- 所有方法/多个模型均满分：保留完整结果，下一版增加实体/窗口/操作组合；不要只删除简单题。
- 简单错误程序也满分：任务无区分度，先修语义或对照，暂不增加真实调用。
- 仍主要是 JSON/truncation 失败：预算/契约尚未稳定，不宣称更新语义困难。
- 值正确而来源错误：保留这一可解释结果，不通过放宽评分“修好”模型。
- reference 双实现不一致：阻塞该 release，不把不可判定条目写成模型 unknown。

---

## 13. PR-N08：第二模型、heldout 与发布

### 留出边界

七个留出风暴已经存在，但当前无真实模型结果；不能为了新增语义先查它们哪题容易出错。

先在三个开发事件和独立合成 fixture 中确定协议，再对七事件派生对应任务。所有变体、分支、翻译、源复用和同风暴港口组合归同一事件组。

一旦看过 heldout 输出再修改协议，此版本结果为 exploratory；下一轮正式验证另选未用事件，不把原七事件重新标为未见。

### 分阶段预算

现有 NHC 原轨道：

```text
70 留出 checkpoint × 3 方法 × 2 模型 × R 重复 = 420R 请求
R=3 时为 1260 请求
```

这不是启动建议，更不是授权。P2 按独立生成 schedule 另算，不能挪用校准余款。先看开发阶段变异与族覆盖再选共同重复数。

七事件即使每事件生成数百变体仍是七个来源组。多次模型调用测服务随机性，不增加独立天气样本数。

### 报告与统计

- 逐风暴、逐能力族、逐分支给分子/分母。
- 先给等权 event macro，再给 pooled counts。
- 方法比较在同一风暴内配对。
- 事件数足够时才做 storm-group bootstrap；七事件区间仍只能谨慎解释。
- 对于生成轨道，来源事件、generator seed、模板族是不同泛化维度，分别报告。
- 如果要声称更一般的 LLM 能力，加入第二模型家族；只换同一 provider 的两个 alias 不能自动视为独立架构。

### 复现交付

- 精简 references snapshot + 精确下载 manifest，而非下载所有相邻 benchmark。
- 当前已验证环境锁定文件；历史环境保留。
- canonical public views、私有 reference、actual trace、projection 分开。
- 失败、未知尝试、排除事件与版本差保留。
- 路径可移植性通过新 build 验证，不编辑历史绝对路径。
- 源码 license 与外部资料来源条件分别说明。
- 当前仓库是私有审查包；公开发布需要单独检查和授权。

---

## 14. 应暂缓的工作

| 工作 | 暂缓原因 | 重新考虑条件 |
|---|---|---|
| 大规模迁移 Inspect / LangGraph | 当前 runtime、日志、审计已经成形，迁移会重做校准 | 多 provider 管理确有不可替代需求 |
| 完整 CyPortQA 图像恢复 | 现有只是模板画像，不是已接入数据 | 独立视觉 task、GIS Gold、许可与时间语义先成立 |
| FrontierSearch / 主动难例搜索 | 现有自然任务近天花板、属性 oracle 尚未覆盖复杂更新 | 冻结 P2 后，固定预算比较 random 与 adaptive；保留公平 canonical set |
| 记忆因果实验 | 当前全原文可见，不隔离记忆必要性 | 独立有限证据轨道 + 同前缀 carrier 干预 + 无关字段控制 |
| conflict / retract / expiry 全家桶 | known/unknown schema 尚无完整表达 | 为新状态制定协议、独立 oracle 后再加 |
| AFDBench 训练、长篇 AFD 输出 | 与当前可验证的数值状态任务不同 | 需要独立 communication 研究问题时 |
| 真实港口操作评价 | 无新增专家判分约束下难保证真实 action Gold | 有已公开、可机械验证的适用规则与边界 |
| 第二灾种 | 先增加语义区分度比扩大领域更直接 | 日期、单位、缺失值、参考计算可自动复现 |

Hypothesis 已在 dev 依赖中，可用于纯程序语义与故障边界测试。当前不需要另一个大型 benchmark 框架来证明进展。

---

## 15. 建议时间和并行方式

以下是开发排期估计，不是工期保证。

| 阶段 | 预计开发时间 | 可交付结果 |
|---|---:|---|
| N00 | 半天–1天 | 新环境基线、正确 sources 布局、保护清单 |
| N01–N03 | 3–5天 | 新契约 collector、累计 guard、journal、audit/report 与离线故障测试 |
| N04 | 半天–1天 | 冻结 execution package，等待授权 |
| N05–N06 | 3–5天，可与 runtime 线并行 | P2 schema、3族匹配任务、双 oracle、负控覆盖 |
| 获授权的校准执行/分析 | 取决于授权、服务和预算 | 三条件结果与共同预算结论或 no_selection |
| N07 | 2–4天工程/分析 | 独立 P2 开发模型验证及研究判断 |
| N08 | 根据事件与模型范围确定 | 留出比较、可复现报告、发布准备 |

并行工作必须避免新模块改变运行中实验的 implementation identity：使用分离 worktree/冻结执行副本与独立环境。运行中的代码、prompt、scorer 不可热修改。

### 防止过度工程化

N00–N04 的退出目标是“能安全执行且能独立解释校准”，不是无止境增加 manifest 层和审计计数。N05–N06 的退出目标是“已定义语义与负控可区分”，不是追求复杂 graph platform。

---

## 16. Codex 首轮启动指令

```text
请读取当前仓库适用的 AGENTS.md，以及
REVIEW_FOR_CHATGPT_PRO.md、IMPLEMENTATION_STATUS.md、DECISIONS.md、BLOCKERS.md、
README_CALIBRATION_V1.md、docs/CALIBRATION_PROTOCOL_V1.md；
同时读取仓库根 README.md、REFERENCE_BUNDLE.md、handoff_validation/README.md。

随后执行本计划 PR-N00～PR-N03 的离线工作，以当前 disastertrace-starter 为起点，
不要从早期 DisasterFrontier starter 重建，也不要迁移大型评测框架。

优先补齐：契约感知采集、真实 wire body 记录、270槽位的单一持久调度、
累计预算与未知请求保护、独立 collection audit、actual/projection 分离和报告。
先写 regression / fault-injection 测试，再实现。

保留 legacy_v1、原 source/answer parsers、V1/V2 scorer 与历史 P1 归档。
不要把 diagnostics 当模型响应，不要按失败情况自动 retry，
不要更改 heldout 划分或试跑 heldout。

默认零模型请求、不读取模型凭据、不训练、不下载权重、不 push、不公开发布。
USD3/270只是计划，不构成授权。涉及 timeout 或其他固定设置变化时，
先创建显式 execution amendment 草案，不能改写原协议。

每个阶段记录真实命令、退出码、测试、改动、identity 和 BLOCKED 项。
如不能执行完整测试，如实列出原因，不用历史 684 passed 代替。
完成后给出可检查的 diff、验收记录及 READY_FOR_AUTHORIZATION / BLOCKED 状态，
不要自行启动付费校准。
```

## 17. 来源索引与可复核位置

所有仓库事实均以基准提交为准；下列路径直接定位本计划依据。网页补充只用于 provider/timeout 语义，不替换仓库记录。

- [S1 主要审查说明](https://github.com/sisuolv/disastertrace-benchmark/blob/a23f73adadcbec077b9fcf2aecf8f45dfa4fe061/disastertrace-starter/REVIEW_FOR_CHATGPT_PRO.md)
- [S2 根目录与当前打包事实](https://github.com/sisuolv/disastertrace-benchmark/blob/a23f73adadcbec077b9fcf2aecf8f45dfa4fe061/README.md)
- [S3 P1 完整报告](https://github.com/sisuolv/disastertrace-benchmark/blob/a23f73adadcbec077b9fcf2aecf8f45dfa4fe061/disastertrace-starter/work/p1-deepseek-background-continuation-v1/report/REPORT.md)
- [S4 校准协议](https://github.com/sisuolv/disastertrace-benchmark/blob/a23f73adadcbec077b9fcf2aecf8f45dfa4fe061/disastertrace-starter/docs/CALIBRATION_PROTOCOL_V1.md)
- [S5 当前状态](https://github.com/sisuolv/disastertrace-benchmark/blob/a23f73adadcbec077b9fcf2aecf8f45dfa4fe061/disastertrace-starter/IMPLEMENTATION_STATUS.md)
- [S6 后续语义与研究边界](https://github.com/sisuolv/disastertrace-benchmark/blob/a23f73adadcbec077b9fcf2aecf8f45dfa4fe061/disastertrace-starter/OPTIMIZATION_ROADMAP.md)
- [S7 dynamic.py：build_episodes / reference_at / render_request / parse_decision](https://github.com/sisuolv/disastertrace-benchmark/blob/a23f73adadcbec077b9fcf2aecf8f45dfa4fe061/disastertrace-starter/src/disastertrace/automated/dynamic.py)
- [S8 collection.py：旧 renderer 与无 monetary cap 的通用 collector](https://github.com/sisuolv/disastertrace-benchmark/blob/a23f73adadcbec077b9fcf2aecf8f45dfa4fe061/disastertrace-starter/src/disastertrace/automated/collection.py)
- [S9 provider.py：prepare / complete / urllib_transport](https://github.com/sisuolv/disastertrace-benchmark/blob/a23f73adadcbec077b9fcf2aecf8f45dfa4fe061/disastertrace-starter/src/disastertrace/automated/provider.py)
- [S10 output_contract.py](https://github.com/sisuolv/disastertrace-benchmark/blob/a23f73adadcbec077b9fcf2aecf8f45dfa4fe061/disastertrace-starter/src/disastertrace/automated/output_contract.py)
- [S11 calibration.py：make_schedule / screen_budget / score_rehearsal](https://github.com/sisuolv/disastertrace-benchmark/blob/a23f73adadcbec077b9fcf2aecf8f45dfa4fe061/disastertrace-starter/src/disastertrace/automated/calibration.py)
- [S12 collection_audit.py：一致性而非 provider 身份认证](https://github.com/sisuolv/disastertrace-benchmark/blob/a23f73adadcbec077b9fcf2aecf8f45dfa4fe061/disastertrace-starter/src/disastertrace/automated/collection_audit.py)
- [S13 references 包的真实内容](https://github.com/sisuolv/disastertrace-benchmark/blob/a23f73adadcbec077b9fcf2aecf8f45dfa4fe061/REFERENCE_BUNDLE.md)
- [S14 新环境验证记录](https://github.com/sisuolv/disastertrace-benchmark/blob/a23f73adadcbec077b9fcf2aecf8f45dfa4fe061/handoff_validation/README.md)
- [S15 项目指令](https://github.com/sisuolv/disastertrace-benchmark/blob/a23f73adadcbec077b9fcf2aecf8f45dfa4fe061/disastertrace-starter/AGENTS.md)
- [S17 当前阻塞与已解决项](https://github.com/sisuolv/disastertrace-benchmark/blob/a23f73adadcbec077b9fcf2aecf8f45dfa4fe061/disastertrace-starter/BLOCKERS.md)
- [S16 已有依赖](https://github.com/sisuolv/disastertrace-benchmark/blob/a23f73adadcbec077b9fcf2aecf8f45dfa4fe061/disastertrace-starter/pyproject.toml)
- [E1 DeepSeek thinking 官方说明](https://api-docs.deepseek.com/guides/thinking_mode/)
- [E2 DeepSeek 价格入口；需执行前重新抓取，不能靠搜索缓存结算](https://api-docs.deepseek.com/quick_start/pricing/)
- [E3 Python urllib timeout 官方说明](https://docs.python.org/3/library/urllib.request.html)

**本计划的最终判断：先把当前分数差测清楚，再让任务真的需要逐字段更新与有效窗口推理；最后才讨论更大数据、多模态、主动搜索或更强的 novelty 主张。**
