# Codex 首轮执行说明：广覆盖登记＋共享契约＋跨灾种离线样例

日期：2026-09-10。与 `DisasterTrace_Master_Plan_CN.md` 配套。

## 任务目标

在已有DisasterTrace代码之上，完成总计划M0–M1，并准备M2/M3的离线演示。**最终范围为多灾种广覆盖；不要把其余数据来源全部推迟到气旋/洪水研究结束后。**本轮也不要求写完58个生产采集器或实施整份总计划。

交付重点：原58来源可查询登记、22类拟议分类、严格证据/时间/交付/预测对象、一个能跨来源复用的最小处理流程及真实运行的离线测试。

## 1. 必读材料和事实基线

先读本包：
1. `DisasterTrace_Master_Plan_CN.md`。
2. `Source_Implementation_Registry_58.json`、`Hazard_Taxonomy_22.json`。
3. `Implementation_Backlog.json`，优先T01–T08；T12–T14/T17–T18只做接口与可用小样本演示。
4. `inputs/DisasterTrace_Data_Online_Audit_CN.md`与`inputs/DisasterTrace_Next_Implementation_Plan_CN.md`。

再检查实际仓库。预期远端开发基线为`next-phase-v1@36082c42a93e11f67d274d8000c87cd1dc098d74`，默认main是较早版本。不得用此预期覆盖本地已更新的工作树。先打印HEAD、分支、未提交/未推送差异、对应规范与保护范围；已有等价模块则适配复用。

旧CURRENT_PHASE中的“运行中”、旧自主窗口和旧部署脚本不是新的启动指令。保留所有旧数据/Gold/报告/失败原始内容；新增协议和输出使用新目录。

## 2. 本轮执行范围

默认仅本地离线开发、读取已存在且允许访问的development样本、程序fixture和测试。**本计划文件不是允许公网批量采集或占用算力的授权。**

不启动模型生成、GPU、训练、付费API、GEE导出或后台采集；不调用LLM judge；不读取protected heldout答案；不恢复旧controller；不自动公开发布/推送。不读取或打印任何用户凭据。

需要网络的采集器可以先完成mock transport与请求生成、分页/重试/失败状态测试。输出下一轮有界scope：provider、AOI/站点、日期、最大记录/字节/请求/像素、权限与许可证。后续以批次管理，不逐文件反复请求确认。

## 3. 先交基线差异表，再编码

输出`BASELINE_LOCK.json`、`CODE_REUSE_MAP.md`、`PROTECTED_SCOPE.json`。

重点核对：
- `forecast_source/pipeline.py`的来源保存与范围保护。
- `forecast_task/compiler.py`单目标/发行排序及public/private分离。
- `forecast_task/protocol.py`累计原文历史。
- `models.py`额外字段、完整引用、KEEP/同值更新。
- `runner.py`固定检查点、送达集合与落盘时机。
- `interventions.py`旧版替换与重复交付的区别。
- 原始数据是否存在于当前工作树，不能只依据README路径假定存在。

之前的8个对象探针是历史审查，不是这一轮测试结果。需要时重写针对新契约的测试，分别标明实际命令、环境、通过和失败。

## 4. 新建最小共享契约

优先使用已经存在的新模块；若没有，可建`src/disastertrace/active_forecast/`，不要再复制`revision_task/mm_trace/multimodal`多套科学内核。

首轮实际实现：
- `contracts.py`：SourceDefinition、EventRecord、ArtifactSnapshot、CaptureRecord、DeliveryEvent、QueryTarget、PredictionRecord、OutcomeRecord和参考侧类型。
- `registry.py`：58原DSID、22标签映射、来源访问/角色/许可/统计状态。
- `storage.py`：内容寻址、追加记录、原始响应先保存、稳定hash。
- `availability.py`与公共投影：historical_strict/controlled_replay/prospective分开。
- 一个导入接口和一个最小编译/参考接口；不要创建所有未来文件的空壳然后报告实现完毕。

关键要求：
1. 顶层关键字段不静默丢失，未声明字段报错。
2. 时间带时区，区间有效；unknown availability可表达。
3. observed/valid/issued/first_seen/delivered/submitted分别保留。
4. 已发布的未来预报合法，未来才发布的旧观测新版本不合法。
5. Artifact内容去重，重复DeliveryEvent不去重。
6. 完整artifact+span/region+role跨轮存储；来源刷新不必改值。
7. 多query属于同一场景，后续具体C查询不提前给模型。
8. public与private Outcome/Gold在类型、路径和序列化层都分离。
9. 原始科学数组与模型可读图片区分；图像hash/变换/尺寸可记录。
10. predicted point/probability/quantiles是不同契约，不能用公告exact-match替代未来结果验证。

## 5. 来源登记：58项全部进入，不等于58项已接通

保持`DS01…DS58`不变，保留旧 reported_scale、计数单位、online分类及核查日期。新增：
`metadata_registered / account_blocked / fixture_tested / sample_acquired / normalized / task_ready / trace_ready / active_ready`。

这些是不同资格，可用字段或状态组合表达；不能用“registered”自动推导“downloaded”。数据源许可只写已经有证据的状态，未核查则标未核查。

DEP01 USGS观测、DEP02 NDBC候选是验证依赖，单独登记，不算原58项。DEP02当前只有官方入口/元数据的候选确认，不能自动报告API已跑通。

## 6. 跨灾种离线演示

准备六个代表家族的导入fixture/样例契约：
- 气旋：NHC文本与地图元数据。
- 强对流：SEVIR序列manifest。
- 洪水：GEOID-Flood瓦片/模态/标签manifest。
- 温度极端：GHCN或ISD站点窗口。
- 火情：FIRMS检测/FPA事件身份。
- 干旱：USDM相邻周版本。

已有真实、允许使用的小样本优先；没有样本时可以自制最小fixture，但必须标`controlled_generated`或`synthetic_fixture`，不声称真实来源下载成功或形成完整数据集。fixture只证明类型和程序关系。不得仿造官方事件内容却写native。

完成至少一条可运行的“导入→内容登记→有序交付→当前状态参考→未来prediction fixture→独立outcome fixture→分项评分”演示；其他来源做共用接口与字段映射测试。预测fixture不是模型实测。

## 7. 必须写的测试

至少覆盖以下不变量，具体测试函数名可自定：
- extra字段拒绝和已声明字段round-trip。
- reversed interval、无时区、NaN/Infinity、非法概率拒绝。
- unknown availability正确保存，严格历史轨不伪准入。
- 同时刻不同来源合法，不靠隐式排序判权威。
- 相同URL新内容新snapshot；相同内容重复送达保留两事件。
- 不同变量/有效窗不被supersedes误覆盖。
- REFRESH_SUPPORT值不变但引用更新，span/region不丢。
- 只使用公共投影，目录/缓存不能取得私有Gold/outcome。
- 新增C query只在指定时刻开放，历史属于同一场景。
- 结果pending/missing不为负例；结果更正新版本不改已封存prediction。
- 固定目标与逻辑/真实提交时间分开。
- 采集transport的完整分页、空结果、部分页、限流、超字节、凭据脱敏。
- 未来动作循环的失效fixture：单轨失败不会导致其他轨fixture消失。
- 58来源映射、22类别、所有引用source ID和工单依赖校验。

不要求凑测试数量；每个通过结果必须对应真实断言和实际执行。无法运行依赖时明确阻断及未测范围，不填虚构pass。

## 8. 结束时一次性交付

必须提供：修改文件清单、旧文件保全结果、实际测试命令/输出、合成/真实样本来源说明、当前source readiness表、可以复现的离线演示命令、剩余风险、下一批scope和预算建议。

建议保存到新独立工作目录：
```
work/master_v2_first_sprint_<unique_id>/
  BASELINE_LOCK.json
  CODE_REUSE_MAP.md
  SOURCE_READINESS.json
  TEST_RESULTS.json
  OFFLINE_DEMO_REPORT.md
  NEXT_INGEST_SCOPE_DRAFT.json
  HANDOFF.md
```

此处仅规定将来的交付格式，不声称目录已由本次聊天创建于用户仓库。下一轮网络采集在scope明确后可与后续内核和模型研究并行；不要把整个项目重新收缩成“等气旋洪水全部结束再考虑其它灾种”。
