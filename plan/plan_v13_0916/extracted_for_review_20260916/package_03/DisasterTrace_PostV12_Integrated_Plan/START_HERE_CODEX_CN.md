# DisasterTrace：post-v12 整合计划的 Codex 入口

状态：PROPOSED_FOR_REVIEW。本文不构成新的生产执行、网络、模型、GPU、拟合或发布授权。
参考提交：`1eba36dd272c72573d1309c78d45dbe97dd8af12`；研究方向仍为 C1/C2/C3。

## 先读什么

先读本包 `OVERALL_PLAN_CN.md` 的第 0—4 节、`NEXT_BATCH_EXECUTION_CN.md` 和 `REVIEW_DECISIONS_CN.md`，机器依赖见 `WORK_PACKAGES.json`。原始八 ZIP 加一 Markdown 的身份见 `INPUT_MANIFEST.json`。

进入真实工作区后读取实际适用的 AGENTS 指引，以及当前根目录进展、`plans/v12_execution_20260915_01/{RESULT_SUMMARY.json,FINAL_VERIFICATION_01.json,FINDINGS_AND_NEXT_GATES_CN.md}`。历史授权和旧 CURRENT_PHASE 不得被当成新批次许可。不要 reset、覆盖 dirty/index、重新启动 consumed launcher。实际 HEAD 前进时先生成差异与已修复项表。

## 当前起点，不要重做

年度 72/72 地区月及年度 bank、旧完整周 840 轨迹、六父重建/六次续跑/24 个 GET 分支、288 次模型请求及 24 个评分组均已有完成回执。它们仍是开发结果，不是独立确认。628 和 750 是不同范围的历史测试记录，不可相加或直接推断删测。

## 下一批 R0：只做离线修复与诊断

仅在用户另行批准这批范围后执行：
1. R00：核对最新身份、来源与保护清单，更新当前入口，形成测试 nodeid 集合差异。
2. R01：修 C2 分析器完整性及调用级 trace 绑定；缺报告/缺 trace 不能宣布完整通过。旧概率、Y、分母和失败保持。
3. R02：修比较身份元数据；FOLLOW、common、values 必须按实际消费者和 bank hash 分类，而非只判断方法名是否 F_COMMON。
4. R03：把实际 API worker 的最后许可、捕获字节完整性、离线恢复及 ProductionSpoolBackend 消费端连成一个故障测试工作包。旧 failure 不删除；恢复另加不可变证据；迟到恢复不回填旧截止。
5. R04：冻结 selector_query_only.v2：保留 query_order 和必须为空的 forecast_handles；固定预测时槽。排序是偏好清单，不是每个列出查询都必定执行的购买承诺。
6. R05：给下一批多状态 C2 增加版本化 remaining-new 查询语义；旧 v1 first/second/all 按原合同保留。排除缓存/已请求必须按付款目标、授权和请求状态判断。
7. R06：用已有开发资料只读审计 cutoff−600 秒训练与实际预测时点、合法信息集合及缺证模式，不直接重拟合。
8. R07：普查公开可见候选与真实消费路径；元数据等价、真实字段等价、概率等价分别记录。不以 all/none 不是最优或正收益存在作为 gate。
9. R08：定向失败→修复→定向通过→一次受影响合并回归；核对历史影响，形成分轨终态并停止。

默认新来源 HTTP=0，远程 API=0，被测模型=0，GPU=0，拟合=0，确认读取=false。候选资源为本地 CPU，必要时最多新增一个16CPU/64GiB作业，仍需真实资源范围获准；无须为 CPU 工作加载模型权重。GitHub元数据读取与“新天气来源HTTP”分开记账。

## 本批不塞入的任务

完整温度谱系、通用内容寻址重构、D 行动环境、H07/H08 下载、MM 新影像、全量 bank 重拟合、真实模型接口试验及独立确认均不作为 R0 合并验收的硬前置。按各自消费者设 gate，不是取消这些工作。

## 不能做的“便利修复”

不把原 217 个不合法回复事后改键为合法；不删除失败标记来解除恢复；不覆盖原 capture 哈希；不改旧 bank 的校准年份；不把六父零正例当极端事件验证；不把只有部分产物的派生报告标为 complete；不把程序或模型按来源预算相等写成总成本相等。

## 停止和交付

每项输出 completed/failed/blocked/not_evaluable/not_attempted 及原因、输入身份、命令、退出码和实际资源。缺 AFS 原文或原 trace 时明确不可核验，不重下载补洞。一个支线阻塞不得使其他离线项无限等待。

交付四份摘要：HISTORICAL_IMPACT、INTERFACE_AND_RECOVERY、CLOCK_AND_ACTION_SUPPORT、NEXT_ACTION。附回归和保护清单。没有新的逐批授权，不自动进入 R1—R4。
