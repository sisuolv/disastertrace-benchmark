# 给 Codex：只执行整合版第一批

仓库 sisuolv/disastertrace-benchmark，分支 next-phase-v1。参考提交 1eba36dd272c72573d1309c78d45dbe97dd8af12。
本段在用户明确要求你执行时作为第一批范围；它本身不恢复历史资源权限。

先读适用 AGENTS、LATEST_PROGRESS_V12_CN.md、v12 的 FINDINGS_AND_NEXT_GATES_CN.md/RESULT_SUMMARY.json/FINAL_VERIFICATION_01.json/FINAL_REPORT_CN.md，以及本包整合计划和 BACKLOG.json。
核实际 HEAD、dirty/index、当前授权与现有作业。若 SHA 已变化先逐文件差异审计，不 reset、不覆盖用户修改。只读远端核查单列，不伪称全程无网络；随后离线批次禁网络。

只做 I00—I05，加 I06 的有限旧权重时点诊断（默认最多24个元数据固定目标）；不运行 I07 整周矩阵、重拟合或后续模型工作。
1. 刷新当前导航、保护清单、原288+2消费身份；按唯一nodeid核750/628范围。
2. 将最终发送许可、原字节截断/摘要、首次reconcile与failure后恢复消费连成真实生产闭环。
3. 修C2缺报告/需有trace仍passed；从冻结roster验分母。配对身份按实际consumer/bank，而非是否F_COMMON。
4. 新建query-only v2单键合同，固定程序预测由显式adapter补空forecast_handles；v1和原失败不改。
5. residual v2显式排除cached/requested，区分原策略续跑与不再付费查询。
6. 每项先在当前真实模块重现red case，再改代码到green；运行当前完整可得测试与有限历史切片。
7. 固定旧年度bank分解早信息、同信息age变化、晚合法信息；不训练，不从Y/loss选样本。

禁止新天气下载、远程API、LLM/VLM、GPU、云作业、训练、push、重启已消费launcher、改旧原始回复/费用/STOP/checkpoint/bank/score、读取Bay或任何新确认载荷。
附件探针只是审查者局部观察，不要复制其stub作为生产修复，也不要把退出0解释为缺陷已修复。
真实资产缺失时输出精确路径/ID/hash及受阻验收，完成其他可做部分；不得补造或者把unavailable写passed。

交付实际diff、命令/退出码/唯一nodeid/JUnit、源码输入hash、RED_GREEN、TEST_SCOPE_DIFF、历史IMPACT（unchanged/affected/unavailable）、接口/恢复/分析/残余合同、有限CLOCK_AUDIT，以及单页NEXT_ACTION。
最后输出STOP_RECEIPT，分列仓库读取、气象联网、模型请求、GPU、训练和确认读取；完成即停止，不自动运行新12/24/288请求。
