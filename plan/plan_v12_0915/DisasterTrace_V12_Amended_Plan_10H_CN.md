# v12 新复核后的整体方案与 10 小时计划

已结合 `DisasterTrace_V12_Review_Addendum_CN.md`、`DisasterTrace_V12_Plan_Review_808ca19_CN.zip`、当前代码与本地 v11 回执完善方案。原发布计划保持，新增版本位于 `plans/v12_review_amendment_20260915_01`。

1. [完整入口](/mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/plans/v12_review_amendment_20260915_01/README_CN.md)
2. [修订后的整体计划](/mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/plans/v12_review_amendment_20260915_01/OVERALL_PLAN_CN.md)
3. [后续 10 小时执行规格](/mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/plans/v12_review_amendment_20260915_01/NEXT_10H_EXECUTION_CN.md)
4. [复核取舍与源码依据](/mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/plans/v12_review_amendment_20260915_01/REVIEW_DECISIONS_CN.md)

核心修订：先核父状态并验证原策略续跑，再运行精确 query-plan 分支；首批区分 METAR 真取证和 TAF 消费接口审计；最多 6 次前缀重建、6 次无干预续跑、24 条处理分支；局部验收不被原完整审计阻塞。

整体保留 C1/C2/C3、16 类灾害及 A→B→C→D。近期 10 小时先收口和验证工程，后续再开展年度资料/强后端、有限大模型机制实验与独立确认。

**这次仅交付计划，新的 10 小时批次尚未启动。** 既有 v11 后台作业保持原流程；本轮没有新模型、GPU、来源 HTTP、拟合或确认资料访问，也未上传新 GitHub 版本。
