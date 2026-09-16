# v13 修复、影响与未完成事项

## 1. A01：结果完整性和实际消费者

旧 `analyze_branches.py` 在缺报告时 continue、按 opportunity 建单值 trace 索引。现在独立分析入口以注册集合为分母，先拒绝重复，再按实际 call ID 对齐；同机会多个合法调用保留，无调用的合法 fallback 不伪造 trace。alias 必须指向注册的实体执行，父状态/数据/bank 与正式分数绑定分别核查。零效应和缺 Y 不自动变成执行失败。

新增测试用冻结 v12 分析器在临时合成目录中真实复现了“全部报告缺失但 summary passed=true、比较数=0”的边界。这个反例不是对旧真实 24 分支的失败指控。实际历史扫描显示六组输入完整，分数、分母和缺失敏感性界保持不变。

Stage C 的 108 个会话重新与原正式分数做算术对账，不重启策略或 formal scorer。消费者指纹绑定预测程序、代码、bank、feature/calibration、共同信息、预测日程、采用/失效、资源和权限。FOLLOW 不再被归入“相同 values 消费者”。`formal_bound_original_receipts_plus_arithmetic_reconciliation` 表示继承原资格并复核绑定与算术，不是重新执行正式评分器。

## 2. A02：派发、捕获、恢复必须是同一条链

新增 `receipt_bound_api.v2` 显式启用。凭据准备后，在单一派发权威下检查 STOP/期限，写不可覆盖 intent，并在 I/O 后再次检查。网络阶段不持锁；最后本地许可之后的 STOP 不宣称能撤回已在途请求。没有多节点 AFS 锁保证或 provider exactly-once 承诺。

先记录原字节前缀长度、哈希、EOF/截断，再脱敏；只有完整读取才记录 full-body hash。存储的脱敏字节具有独立哈希，解码严格使用 UTF-8。捕获哈希还绑定到独立管理目录中的可信 receipt，首次恢复要验证该 receipt 的预期哈希，不信任 capture 文件自填的哈希。

旧 failure 文件保留。恢复追加 reconciliation，绑定原 request/execution/intent/capture/failure/response。实际 `ProductionSpoolBackend.resolve` 验证后才能消费；已经失败并闭合的会话只允许费用对账，不把晚到结果倒填入原天气判断。测试验证正常恢复、晚恢复、重复结算、双 worker、期限/STOP 边界、崩溃、哈希破坏、非法 UTF-8、脱敏缩短截断、错误模型/usage 等。

首次真实消费者测试有两项失败：旧生产消费者始终拒绝带 failure 的调用。修复后通过，失败日志保留。本批使用 mock HTTP 与真实本地控制器，不代表提供方已经兼容新 schema。

## 3. A03/A04：新合同与旧实验分离

selector v2 的模型输出仅有 query_order。prompt、逻辑 schema、提供方 schema、parser 由同一合同生成，内部适配器固定补空 forecast_handles；仅适用于固定程序预测时隙。候选数决定 schema 最大长度，实际执行器再约束预算和合法前缀。完整意图逐项保留 executed / already_cached / already_requested / budget_exhausted / late / unexecuted_tail 等 disposition；首项不可执行时不跳过它购买后项，缓存复用/旧请求状态单列。空目录没有非法空 enum。完整围栏、重复 key、错误字段等在 v2 被拒绝，旧 v1 的行为不变。

尾部记录和前缀语义在首轮收尾复查中被发现仍有缺口。保留首轮通过/关闭回执，另记 `CLOSEOUT_AMENDMENT_01.json`，四项新增回归先实际失败再修复，其中包含真实异步 source 的原调用续接。最终代码以第二轮冻结的 880 项回归及 `FINAL_RESULT.json` 为准。

原虚拟环境没有 jsonschema；保留 6 项依赖失败记录后，项目测试不新增依赖，额外用既有系统 Python 的 jsonschema 验证了 0/1/2/1000 候选的合法与非法输出。真实提供方不支持的约束必须显式失败，不允许静默降级。

residual v2 为 none/first_new/second_new/all_new。根据 payer、授权范围、缓存权利、原请求身份和生命周期生成 remaining_new，保留排除原因。pending/UNKNOWN/已登记失败均不自动重发；证明未发的失败也需新登记。none 仍继续共同基线更新和固定预测。旧的 24 条 v1 分支此次没有因“已缓存/已请求项”发现需改分的情况。

## 4. A05：时钟与动作信息，而非结果筛选

旧 12 个开发日各按 public opportunity ID 的固定哈希选两个目标，共 24 个，不按 Y/损失替换样本。依次计算：早时钟的合法披露、同一信息在实际时钟的纯算术效果、实际 slot 的真实合法披露，并重建实际 candidate probability。24 项均可复算；早视图明确标为离线重建，没有伪称真实训练调用 capture。

24 项均有可测时钟变化，其中 1 项 TAF 版本改变，全部有早时钟之后完成的付费披露。对称动作空间和时钟错配是下一阶段设计需要面对的证据，但它们没有自动证明 LLM 无价值、需要重拟合，或新 bank 一定更好。

## 5. 仍不能宣称完成的内容

- 新 selector 的真实天气接口小试与正式 288 请求比较尚未执行；旧 71/288 合法率不是新接口的表现。
- 年度 raw bank 尚未覆盖完整 840 条开发轨迹桥接；不能将旧 bank 的 840 条当成年度结果。
- 新 12 父/48 GET 仍是候选清单，尚无真实 parent/continuation 资格；PROCESS 与 WAIT/TIMING 独立限额。
- 多截止、相同未来 target 的持续修订资格、第二条主动灾害链、温度/MM、16 类全链仍需各自证据。
- 4,506 文件保护校验不等于对磁盘所有原始天气文件做了逐字节普查；确认集保持关闭。

这些限制延续稳定研究方向 C1/C2/C3；本轮没有增加新核心概念或把未完成工作包装为新贡献。
