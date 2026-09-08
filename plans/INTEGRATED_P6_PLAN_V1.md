# P6 整合实施计划：先解释测量，再准备匹配重复

实施基线：`dd5ee358f9708e2eb2f2032db9eaac14fa237adc`，2026-09-08。
初始输入为 [plan_v3](plan_v3/) 的三份原方案，原文及 SHA-256 保留在
`disastertrace-starter/artifacts/p6_offline_v1/plan_inputs.json`。
执行中用户补充 `DISASTERTRACE_POST_P5_CODEX_PLAN.md`；四份原文的完整索引保存在
`disastertrace-starter/artifacts/p6_offline_v1/plan_inputs_v2.json`，不覆盖初始索引。

## 本轮交付范围

完成三方案共同的第一阶段：P5 只读错误/曝光分析、合法简单策略审计、新配对重复
协议、raw-first 采集与独立审计、完整程序演练和 CPU 迁移验收。新代码使用
`post_p5/` 和 `repeat_eval/`，复用现有公开 renderer、严格 parser、scorer、
Qwen tokenizer 与结构 grammar。原有 P1-P5 文件、源码、回答与分数保持原样。

本轮不生成新模型回答、不下载权重、不训练、不启用 heldout、不重开历史 claim。
这落实原方案的首轮离线停止点；实际硬件、live scope 和启动记录保持未验证/未启动。
已有 GPU 权限不是把未冻结新矩阵当成已启动实验的依据。本轮不自动发布 P6。

## 合并三方案的选择

| 分歧 | 本轮选择与理由 |
| --- | --- |
| 两次/三次重复 | 两份方案的最小 E1：base + irrelevant_scope level4，2 repeats，2160 机会、432 轨迹；实现支持新版本选择三次，但不同时冻结/运行另一个矩阵 |
| 四因素 6480 回答 | 后续候选；先验证 scope 的重复协议，不能把 scope 结果用于确认另外两因素 |
| 引用标签细度 | 字段主类固定优先级，保留逐引用细类、混合引用和历史载体关联；90 值错和230 引用错分开守恒 |
| 真实资料网络获取 | 首轮仅登记来源和设计，默认不联网获取新 NHC/上游代码；真实轨另建有界来源目录与双解析器验收，不能用计划中的示例冒充已抓取原文 |
| 新方法/新题型 | 简单公开程序基线在本轮；竞争值、短 ID、行序、公开验证工具等保留为独立后续版本，不修改重复矩阵 |
| 文献复用 | 本轮 design_only，登记实际阅读范围；未核验 commit/license 为 null，没有导入或运行上游框架 |

## 实施顺序和验收

1. **P6-00 基线与保全。** 记录 Git/计划输入/环境；用冻结源码独立核对 P4 与三组 P5
   真实报告；建立不可覆盖的新目录和历史文件索引。对账失败即阻止历史实测分析发布。
2. **P6-01 引用与实际曝光。** 从真实请求与 capture 建立逐字段/逐引用表、双向配对、
   首次曝光、同值引用刷新与错误恢复。验证 1620/1360/260、90+230=320、29 动作重叠。
   对缺失、无效与不可分类情况显式记录，旧 scorer 和所有主分母不变。
3. **P6-02 行为与主张。** 增加公开简单求解策略、策略分歧、输入难度与 MFT/INV/DIR
   测试；验证 latest-issued 在当前合法线性版本域的充分性；记录结构 grammar 可达错例。
4. **P6-03 重复协议。** condition 纳入运行身份、排除于配对采样身份；不同 repeat/
   method/episode 完全隔离；按 checkpoint 波次与平衡条件顺序调度。真实 tokenizer
   检查完整 8192 输出预留，保留 BF16、16384 context 和 P5 解码设置。
5. **P6-04 raw-first 与独立审计。** dispatch 前写意图，返回整批先原子保存，再提取和
   晋升合法载体。进程中断后只做 CPU 重建，不重生成；未知结果保留全部失败机会。
   测试篡改并重算表面 hash、重复启动、错载体、错误合法回答和无效回答传播。
6. **P6-05 完整离线验收。** correct 与 invalid-control 各运行完整 2160 程序机会，
   独立重建固定分母、每 repeat 格式屏、来源级表、双向配对、episode success 与 pass^k。
   CPU 换目录屏蔽原资料/权重/网络重建；运行相关新旧测试并再次核对历史保全。

未通过实际硬件/模型启动验收时，标 `offline_verified_live_pending`，不得写成全套
live 条件都满足。程序回答不计入模型样本。验收日志保留失败尝试和对应修正，不累加
重复测试数或旧记录充当本轮测试。

## 后续研究路线

完成首轮后，再按新任务推进：有界 NHC 同绝对 valid time 的多版本原文获取与双解析；
等信息原始表/结构表；独立开发事件；匹配任务版本的第二模型；冻结后 heldout。
若要区分 scope 相似性与长度效应，先另立 near/far 长度控制；若要测直接载体效应，
另立共同前缀实验。更多重复不能代替独立来源，也不能把累计证据实验称为内部记忆证明。

交付入口计划为 `disastertrace-starter/README_P6_OFFLINE_V1.md`，实际完成情况与
下一任务写入新 P6 bundle 的状态和交接文档，不以本计划的列表宣称完成。

## 第四份计划的增量纳入

其 PR-P6-00–04 首轮离线停止点、两条件两次重复选项 A 与本轮一致。
补充独立 `source_binding_probe_v1`、纯程序 Hypothesis 序列测试和按固定排序选择的
实际 P5 错误例子；它们不修改已经冻结的 E1 任务与采样身份。
StateMemBench/StateMem 与 Microsoft STATE-Bench 分开登记；LongMemEval、AFDBench
及 CAP/VTEC 仅登记后续参考，没有下载/运行或声称复现。
跨方法共享 seed 是可选设计，本轮保持 method 属于采样身份，只在处理条件之间
配对；等内容不同表示的载体研究与长度匹配探针另立后续版本。
详细对照见新 bundle 的 `SUPPLEMENTAL_PLAN_RECONCILIATION.md`。
