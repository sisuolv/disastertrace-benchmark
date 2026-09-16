# 下一批顺序：固定预测器桥接、机制扩展、真实接口

以下均为后续执行提案，不会被本批收尾脚本自动启动。技术前提与剩余冻结要求分别见 `NEXT_GATE_DECISION.json`。

## B00：优先完成完整日历的程序比较

使用 `B00_ROSTER_PROPOSAL.json` 的 168 个 region/day/threshold 单元；3 地区×4 周×7 日×2 阈值，每日重置、lead1h、48 次来源信用，原 public slots 和 base_bound_override。五臂 FOLLOW、F_COMMON、F_BASE_ONLY、B11_BATCH、B11_COVERAGE，上限 840 轨迹 / 12,096 机会 / 60,480 方法行。

1. 固定已有年度 common/values bank 的 raw 转换及 hash，不重拟合。原含 post_calibration 的文件保留。
2. 核验原 DATA/目标/许可可用性合同、消费者语义、公共日程、scorer；对任何可复用旧单元逐一证明一致。复用数尚未预填。
3. 少量注册程序单元通过重建后，由普通 CPU 作业完成全量固定 roster；父日历/失败分母不能按初步结果缩减。
4. 首先比较同 values 程序下无查询→batch、无查询→coverage、batch→coverage；FOLLOW 和 F_COMMON 的消费者差异单列。完整缺失界、地区/时段与正负事件分层都保留。

优先用 CCI/ACP 16 CPU 或已有可用 CPU 配额并行，不消耗被测模型 API。脚本负责运行、失败回执、结果汇总和停止，仅在完成/失败节点检查。不要重复旧 claim 或反复扫描大目录。

## B01/B02：依据证据处理时钟与强基线

本批已测到保持信息不变时的时钟效应，但还没有适应性能证据。先保留 v1 年度 bank 完成 B00；如后续决定重拟合，至多另登记一个 slot-aligned values 候选，2023 拟合/内部选择、2024 年 1—11 月校准、12 月排除，2025 仅暴露开发。不能在新旧开发损失中挑赢家后叫独立确认。

原 288 请求的成本/年龄/覆盖数量对称，下一批先从注册公开元数据确认是否存在真实可利用差异。不要人为制造障碍或按最佳动作非 all/none 筛样本。强 batch/coverage 必须保留；round-robin、公开 risk/age、固定 hash 与 2×2 权限/分额控制按整体计划最多新增 72 个程序方法日。有训练侧价值估计才加入可部署 expected-VOI。

## C00：新增 GET 机制，先验证父状态

`C00_ROSTER_PROPOSAL.json` 提供 12 个跨原地区/季节开发日的公开 ID/hash 候选。先确定与 B00 一致的 bank，从会话起点重建前缀，不能替换旧 checkpoint 内 bank。最多 12 次材料化与 12 次原策略等价续跑，通过后最多 48 条 v2 GET。

每个父继承相同预算、缓存、授权、唤醒和预测日程；主分母是全部剩余机会。真实缺报、删失、TAF full/partial/none、订正/冲突等分层由恢复后的合法状态核实，无样本层保留为空。候选来自多日期并不自动等于独立天气过程。原策略续跑与 none 分别报告；PROCESS 最多 12 条路径、WAIT/TIMING 最多 6 对路径独立登记。

## M00：12 次接口小试，与 B/C 使用独立门槛

`M00_PROPOSAL.json` / `m00_unsent/` 已有 12 份真实旧天气公开视图转成的新合同请求。优先沿用已有实际证据的 SiliconFlow `deepseek-ai/DeepSeek-V4-Flash` 路由，temperature=0、thinking=false、output cap=512，一次发送、无自动补请求。API key 位于仓库外。

启动前还需新 run_id、实际生产控制器冻结、最终 caps/deadline、STOP 与可信 capture authority。固定单派发权威；多提供方或多模型路由发现不混进这 12 次。所选真实请求没有空候选等全部极端形状，这些边界只在离线测试中覆盖，不能据此声称提供方均已验证。

12/12 合同通过只代表本次 smoke。M01 的正式 288 请求仍要求冻结科学日历、强程序和实际消费者，结果必须保留失败、未执行和所有机会。更大 Qwen/GLM/Kimi 或 4 H100 推理可在同合同资格完成后另设资源和模型对照，避免再把格式失败与模型推理能力混在一起。

## 收口

先得到完整 B00，再结合 C00/M00 决定正式 selector 是否有足够可测动作空间与合法过程证据。没有正收益也可以交付 benchmark 的有效边界；独立确认、16 类完整发布依旧需要后续真实任务证据。
