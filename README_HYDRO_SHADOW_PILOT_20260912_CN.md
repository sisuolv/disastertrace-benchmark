# 多站点水文核验与在线影子评测

本轮接续已完成的 ActiveWarning 最小闭环，继续排除 GEE。

- 9 个候选站点已下载核验，7 个通过数据准入，6 个进入前瞻采集。
- 2026-09-12 06:00 UTC 已启动后台进程，登记 18 个未来目标、4 个程序基线。
- 首轮 24 次下载成功，初始与首轮更新共 144 条预测通过原始数据独立核验。
- 当前结果尚未成熟；后台计划于 2026-09-13 10:00 UTC 结束采集并自动审计。
- 45 项新增测试、97 项原有相关测试通过；原最小闭环的 3,968 个文件保持不变。

详细说明：[下载、数据准入、前瞻协议及后续研究计划](plans/hydro_shadow_pilot_20260912/README_CN.md)。

实时状态：[PROGRESS.json](plans/hydro_shadow_pilot_20260912/shadow_01/run/PROGRESS.json)。

首轮独立审计：[PREFIX_AUDIT_01.json](plans/hydro_shadow_pilot_20260912/shadow_01/PREFIX_AUDIT_01.json)。

本轮是实际在线数据与程序预测的试点。未来观测自动结算后，才能报告本轮预测误差；新的 LLM 对比尚未运行。
