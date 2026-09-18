# DisasterTrace post-v12 整合交付包

入口：START_HERE_CODEX_CN.md。完整路线：OVERALL_PLAN_CN.md。下一批执行细则：NEXT_BATCH_EXECUTION_CN.md。源建议取舍：REVIEW_DECISIONS_CN.md。机器依赖：WORK_PACKAGES.json。

本包结合八ZIP和一Markdown、固定提交1eba36d的实际源码/报告，**只制定计划并做隔离检查，没有修改生产仓库、启动模型或提交云作业**。所有机器任务execution_authorized=false。

INPUT_MANIFEST.json保存原始文件及134个ZIP成员的hash和本次解压路径。原始ZIP/解压材料没有重复嵌入本输出包；它们仍在用户原附件中。SOURCE_MATCHES.json只覆盖本轮远端核对的四个模块、13份附件副本，不是全库一致性证明。

checks目录包含重新复制到隔离目录的两份检查脚本、两个源码文件、原始source绑定和本轮输出；运行检查不会使用真实API，但底层spool是测试替身，不能替代生产恢复验收。LOCAL_CHECKS.json列出命令、结果和未执行范围。

所有建议上限（24真实接口请求、288正式模型请求、12父/48GET、24PROCESS或图像资格）均需以后分别冻结和获准，不代表已执行或本次批准。不以正收益为通过条件，不改旧失败和评分。提供小批次可解释交付，不复制九份材料的全部P0形成巨大串行任务。
