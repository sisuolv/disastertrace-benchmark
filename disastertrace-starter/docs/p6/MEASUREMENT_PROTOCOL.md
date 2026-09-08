# P6：配对重复的测量契约

本文件解释新的离线候选，不授权模型生成。机器契约以
`artifacts/p6_offline_v1/execution/execution.json` 为准。P1–P5 的原始评分不变。

## 矩阵与研究问题

选择两份方案共同推荐的最小 E1：base / irrelevant_scope level4，36 个基础 episode、
每个 5 checkpoint、3 方法、2 repeat。共 2160 个回答机会、432 条独立运行轨迹。
这仍是 3 个来源风暴的派生任务，不是 432 个独立天气事件。

研究问题是：在同一模型、硬件和共同解码设置下，scope 干扰对整条闭环策略的表现
及重复可靠性有何影响。所有方法仍收到累计公开证据，区别在于额外的显式状态或
答案历史。历史回答会影响后续输入，因此估计包含载体传播路径的总变化。

两次重复是第一步；实现支持另立版本增加重复，但不能在看到新模型结果后挑选
重复次数、替换失败回答或增删压力条件。revision_chain 和 stale replay 的模型重复
不属于这个 E1，不能从历史不同配置的实验中拼入。

## 身份与随机性

采样身份包含 `model_identity / base_episode_id / method / checkpoint_id / repeat /
master_seed`，不包含 condition。由此计算的同一配对种子跨条件相同。
轨迹身份另含 experiment 和 condition；slot 身份含 checkpoint；attempt 身份另行绑定。
不同方法、重复和条件均维护各自的 previous_state / answer_history，禁止响应缓存。

采样 master seed 为 60719；调度使用独立 `random.Random(60720)`。
调度按 c0–c4 波次进行，一批最多 12 个不同轨迹的请求。条件相邻，先后顺序按
基础 episode×method 的稳定序号与 repeat 反转；完整矩阵每个 repeat 的两种先后
顺序各占 54 对。调度不依赖 Python hash 或后端初始化对全局 RNG 的修改。

相同种子不能保证跨硬件输出一致，也不能使后来已不同的历史载体变成同一输入。
P4 的 MIG 与 P5 的完整 H100、新旧 slot seeds 均是历史比较的限制。

## 固定输出轨与上下文

继承 Qwen3-8B、BF16、单卡、vLLM 0.10.2、XGrammar 0.1.23、16384 context、8192
完整输出预留、thinking、temperature 0.6 / top_p 0.95 / top_k 20 等冻结设置。
结构 grammar 不约束正确数值、当前引用、单位语义或动作正确性。错误答案仍可合法。
`VLLM_ENABLE_V1_MULTIPROCESSING=0` 是未来共同运行配置中的新设置，不能追称 P5
已经使用了它。实际 GPU 配置和无生成预检在本轮保持未验证。

程序上下文校验涵盖 2 条件×36 episode×5 checkpoint×3 方法×10 种程序载体，
即 10800 个请求机会。重复对确定性程序输入没有影响，因此不把相同输入重复计算
成独立上下文样本。此检查不能保证任意模型生成的合法长引用数组都能装入上下文；
运行时必须在每次发送前保留完整 8192 输出预算，超限就停止，不截断或减少 cap。

## 先保存 raw，再解析

顺序为：独占 registry claim → 请求意图落盘 → 开始标记落盘 → 后端返回 → 整批 raw
原子落盘 → 按 attempt_id 解析 → 校验输出契约 → 更新各自载体。
写入使用临时文件、fsync 与独占 hard-link 发布，既有结果不可覆盖。

整批 raw 含实际 prompt/output token IDs、原始文本、finish/stop、请求身份及批次墙钟。
整批返回后即使首条提取失败，其他 raw 仍保留。部分返回按 attempt_id 对齐：已知
结果保留，未返回槽位标 unknown，停止后续发送。未知不等于确认未发送。

合法但错误的答案原样进入后续载体；无效 JSON 保留上一合法载体。恢复只做 CPU
重建，不自动补调用，不写回原采集目录。独立 auditor 从公开请求、raw tokens 与
冻结规则重算状态，不信任 collector 保存的 state_after、counter 或“complete”。
当前 collector 只接受明确标注的程序模式，拒绝 `mode=model`；未来 live 后端与
一次性 ACP phase launcher 是尚待实现的单独工作。

## 评分、曝光与统计

主分母保留所有计划机会，包括无效、unknown、未提交和基础设施中断。按
condition×repeat×method 分开调用原 scorer；family 格式屏仍为计划 60、至少 58
个契约合法、最多 2 个 length。程序 invalid-control 在所有轨迹 c2 注入错误 JSON。

每个配对保留 both_correct / base_only / condition_only / both_wrong 四种结果，
不能只报净变化。曝光按实际公开证据计算，另区分首次曝光前、曝光后和从未曝光。
证据字节、去重 fact/value 集合、当前目标状态、实际 carrier 和 seed 不混为同一种相等。
对未收到的未来请求，只能计算冻结数据的证据投影，实际 carrier 相等性为 null。

episode 成功要求该次重复的全部五个 checkpoint 都正确。
若 R 次中 c 次 episode 成功，`pass^k = C(c,k)/C(R,k)`；两次中仅一次成功时 pass^2=0。
R<k 返回 null，不是 pass@k；中断结果保留全分母并显示 incomplete。

逐来源、逐 repeat 的计数和均值/范围同时提供。三个来源不报告总体显著性结论，
checkpoint、字段、branch 和 repeat 不能充作独立事件。90 值错、230 引用错与
29 动作错有层级/重叠关系，不能相加成独立错题数。

## 结果身份与帮助层级

所有新报告绑定 execution、experiment、data、model、scorer、output track 和声明的
runtime profile。程序 oracle 是自动评分与软件验证上界，不是新增 LLM 方法成绩。
reasoning/content/delimiter/terminal 之和构成生成 token，不重复加 reasoning。
批次墙钟不是单请求纯推理延迟；没有 GPU 调用不能被描述为已测 GPU 成本。
