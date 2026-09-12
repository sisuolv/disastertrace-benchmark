# DisasterTrace：最小闭环已经跑通，核心研究收益尚待验证

## 最新：全部候选数据补缺与使用清单（2026-09-12）

当前 97 个来源/产品入口中，84 项有已解析样例、6 项可作事件目录，7 项仍有获取或授权缺口。
本轮实际补齐 TCIR、CAMELSH、CEMS、FloodNet、CrisisMMD、UrbanSARFloods、SenForFlood、GWIS、EFFIS。
完整 [数据报告](plans/all_dataset_utilization_20260912/README_CN.md)、[97 项清单](plans/all_dataset_utilization_20260912/usage_02/USAGE_REGISTRY_CN.md)
和 [16 灾种组合](plans/all_dataset_utilization_20260912/usage_02/HAZARD_CHAINS_CN.md) 已更新。

请将 [ChatGPT Pro 复查任务](publication/dataset_review_20260912/REVIEW_FOR_CHATGPT_PRO_CN.md)
或 [精选阅读 ZIP](publication/dataset_review_20260912/chatgpt_pro_dataset_review_20260912.zip) 交给审阅者。
93 次实际数据请求、约 975 MB 正文和 1,081 个文件的本机独立核验已有记录。
源码、回执和审计结果随仓库提供；新原始大数组与环境保留本地。
样本可读不代表 16 类预警链全部建成；本轮没有新模型调用，既有主动取证未显示收益的结果保留。

2026-09-12。最新复查入口：[给 ChatGPT Pro 的详细说明](publication/active_warning_review_20260912/REVIEW_FOR_CHATGPT_PRO_CN.md)。

已经完成的最小闭环使用真实 NHC/HURDAT2、HEFS/USGS 数据，执行 LLM 取证与预测，再自动评分。
84 个目标中 78 个可结算、6 个缺失；两轮 Qwen3-8B 实验共 1,120 条真实回复，第二轮 400 次预测提交全部格式有效。

关键负结果是主动策略始终查询官方预报，与固定查询没有区别；平静水文片段中的简单观测持续性明显优于测试的 LLM 方法。
因此可以确认工程闭环可行，但不能确认主动获取改善预警价值这一核心研究假设。

最新扩展完成 9 个水文站点的实际样例核验，7 个通过，6 个进入前瞻程序试点。首轮采集与预测已经通过审计，未来结果仍待观测到达。
建议主实验优先使用历史多事件时序回放，在线试点作为并行补充；这一路线选择与原始 novelty idea 已列入复查材料。

- [完整最小闭环、模型结果与限制](README_ACTIVE_WARNING_MINILOOP_20260912_CN.md)
- [多站点下载、准入与前瞻试点](README_HYDRO_SHADOW_PILOT_20260912_CN.md)
- [复查说明及阅读附件](publication/active_warning_review_20260912/README.md)

GitHub 中的前瞻进度是上传时的静态快照；本地后台之后产生的结果需要后续同步。
