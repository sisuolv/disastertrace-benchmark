# Codex启动指令

请检查、修复和推进附件，不要再只写总体计划。

基线：`sisuolv/disastertrace-benchmark / next-phase-v1`，发布提交`889620a4fc4ee6ad70757dd3e832a40c7509126a`。
先读适用AGENTS.md和当前工作区，再读LATEST_PROGRESS_V11_CN.md、当前执行README、实际STATUS/作业终态，以及本包AUDIT_REPORT_CN.md、CODEX_NEXT_PLAN_CN.md、TASKS.json。保持W00—W13、C1/C2/C3、E/F/D/MM、X00—X09和16灾种路线。

**第一件事是对账已有运行，不是重新启动。** GitHub在2026-09-15 12:06:47UTC保存的是进行中快照。840条完整周轨迹、72地区月/432逻辑分片、2470原文样例可能已在本地推进。读取exact IDs、CLAIM、COMPLETE、失败和正式审计；不把快照running当实时平台状态，不重跑成功片。

第一批：
W00.reconcile_snapshot；
W01.target_scope；
W06.sample_failure_roster；
并行W07.finish_registered_fullweek、W06.finish_catalog_gap、W11.e_census。

本包10份完整源码与发布Git blob一致；实际58项隔离测试54通过、4失败。旧39项全部通过。3个失败是温度事件资格误依赖未消费变量，1个是年度样例失败时sample+sample重复汇总。当前真实成绩是否受影响未知；不能宣称已污染。先完整package复现，作最小修复，再扫描原任务。严禁修改本包冻结源来使旧报告看似全绿。

命令模板：
```bash
DT_REPO_ROOT=/absolute/path/to/disastertrace-benchmark \
  python -B -m pytest -q -p no:cacheprovider \
  /absolute/path/to/this-package/audit_probes/test_inherited_controls.py \
  /absolute/path/to/this-package/audit_probes/test_v11_boundaries.py
```

源码变更不得碰活跃任务绑定的冻结文件；新generation保存diff、输入输出hash与影响。正式来源v2、API发送门槛、评分19→9次、common适配和五组预检已经实现，不再从零建设。

收口完整周与分层结果后，推进全年原文/角色/强后端和C2同状态分支；只在方法/成本/数据冻结后登记一次有限模型实验。温度F-only继续独立资格，Bay确认载荷仍封闭。

沿用明确且仍有效的原授权覆盖其确切未完成范围；新增或过期API/GPU/大抓取/训练/推送权限不得猜测。旧402、424未尝试和未知预留不能借本次修复重开。没有授权不妨碍CPU只读审计与计划准备。

每批交付实际代码、命令、nodeid、hash、逐机会结果、失败/缺失/未尝试、原始与派生表、不可核范围和下一操作。负结果可交付，不强迫模型改概率，不调到正收益，不把声明程序时延当部署速度。
