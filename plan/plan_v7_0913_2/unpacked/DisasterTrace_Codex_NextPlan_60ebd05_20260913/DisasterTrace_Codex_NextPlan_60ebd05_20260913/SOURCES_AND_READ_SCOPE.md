# 来源、读取范围与结论边界

核对提交：`60ebd05723f9483590611976d379da2e4edd85b0`。所有R编号指向用户仓库；E编号是外部原始论文或官方资料。

本次没有重跑DisasterTrace的250项测试或模型输出，没有下载科学数组，没有运行任何上游算法。`PLAN_BUNDLE_VALIDATION.json`只检查本计划包自身，不是仓库验证结果。

主计划中的模块、输出名、schema和非零预算是建议，不表示已实现/已授权。原X09是联合目标推理；新增工具选择仅用X01-tools/X07-compute子实验名。

## R01｜最新分支HEAD

状态：`current_connector_read`。
读取范围：分支响应，2026-09-13读取；HEAD与父提交。

```text
https://api.github.com/repos/sisuolv/disastertrace-benchmark/branches/next-phase-v1
```

## R02｜执行后下一阶段计划

状态：`current_connector_read`。
读取范围：当前起始段与W2—W5；尾部已有同提交读取。

```text
https://github.com/sisuolv/disastertrace-benchmark/blob/60ebd05723f9483590611976d379da2e4edd85b0/plans/v7_execution_20260913/NEXT_PLAN_CN.md
```

## R03｜本轮执行报告

状态：`previous_turn_same_commit_read`。
读取范围：本对话此前读取同一不可变提交的正文和尾部，覆盖结果/数据/真实head边界。

```text
https://github.com/sisuolv/disastertrace-benchmark/blob/60ebd05723f9483590611976d379da2e4edd85b0/plans/v7_execution_20260913/FINAL_REPORT_CN.md
```

## R04｜typed合同与固定证据

状态：`targeted_code_read`。
读取范围：此前1—190；本轮190—480；非全文件形式化审计。

```text
https://github.com/sisuolv/disastertrace-benchmark/blob/60ebd05723f9483590611976d379da2e4edd85b0/disastertrace-starter/src/disastertrace/monitoring_fixed_v1/contracts.py
```

## R05｜独立输出heads

状态：`targeted_code_read`。
读取范围：本轮完整返回，核查航空限定/消息/解析。

```text
https://github.com/sisuolv/disastertrace-benchmark/blob/60ebd05723f9483590611976d379da2e4edd85b0/disastertrace-starter/src/disastertrace/monitoring_fixed_v1/heads.py
```

## R06｜旧会话策略

状态：`targeted_code_read`。
读取范围：本轮1—180行；run_session起点、预算与航空限制；未审完整函数。

```text
https://github.com/sisuolv/disastertrace-benchmark/blob/60ebd05723f9483590611976d379da2e4edd85b0/disastertrace-starter/src/disastertrace/monitoring_v1/policies.py
```

## R07｜资源账本

状态：`targeted_code_read`。
读取范围：本轮1—220返回，Cost和预留/结算/恢复。

```text
https://github.com/sisuolv/disastertrace-benchmark/blob/60ebd05723f9483590611976d379da2e4edd85b0/disastertrace-starter/src/disastertrace/monitoring_v1/resources.py
```

## R08｜有限联合可达性

状态：`targeted_code_read`。
读取范围：本轮1—260返回，solve_joint/validate_witness及固定时长范围。

```text
https://github.com/sisuolv/disastertrace-benchmark/blob/60ebd05723f9483590611976d379da2e4edd85b0/disastertrace-starter/src/disastertrace/monitoring_v1/reachability.py
```

## R09｜航空证据支持

状态：`targeted_code_read`。
读取范围：本轮完整返回，存在命题、有限配方、特征。

```text
https://github.com/sisuolv/disastertrace-benchmark/blob/60ebd05723f9483590611976d379da2e4edd85b0/disastertrace-starter/src/disastertrace/monitoring_v1/evidence.py
```

## R10｜旧单写者状态

状态：`targeted_code_read`。
读取范围：本轮1—220行，Baseline、EVENT_ORDER、状态初始化与当前视图；非全文件审计。

```text
https://github.com/sisuolv/disastertrace-benchmark/blob/60ebd05723f9483590611976d379da2e4edd85b0/disastertrace-starter/src/disastertrace/monitoring_v1/state.py
```

## R11｜项目依赖与入口

状态：`current_connector_read`。
读取范围：本轮完整返回。

```text
https://github.com/sisuolv/disastertrace-benchmark/blob/60ebd05723f9483590611976d379da2e4edd85b0/disastertrace-starter/pyproject.toml
```

## R12｜最终验证记录

状态：`current_connector_read`。
读取范围：本轮完整返回；仅仓库声称250项通过，本次未重跑。

```text
https://github.com/sisuolv/disastertrace-benchmark/blob/60ebd05723f9483590611976d379da2e4edd85b0/plans/v7_execution_20260913/FINAL_VALIDATION.json
```

## R13｜16类数据与任务合同

状态：`previous_turn_same_commit_read`。
读取范围：本对话此前分段读取；保留16类/子类资格，不视为全部已完成。

```text
https://github.com/sisuolv/disastertrace-benchmark/blob/60ebd05723f9483590611976d379da2e4edd85b0/plans/v7_0912_overall_research/HAZARD_DATA_PLAN_CN.md
```

## R14｜v7整体计划与原实验矩阵

状态：`current_connector_read`。
读取范围：本对话此前总纲；本轮219—380行，明确X00—X09、分组与评分。

```text
https://github.com/sisuolv/disastertrace-benchmark/blob/60ebd05723f9483590611976d379da2e4edd85b0/plans/v7_0912_overall_research/OVERALL_PLAN_CN.md
```

## E01｜AFABench

状态：`paper_html_read`。
读取范围：2026-02-22版本；§2.3、§3.2离线分类与固定外部预测器。
用途与边界：固定预测器与策略比较，不整套改造天气引擎。

```text
https://arxiv.org/html/2508.14734v3
```

## E02｜BRiG-AFA

状态：`paper_html_read`。
读取范围：2026-08预印本；Bellman风险回归与实验范围；未复现。
用途与边界：先一步两步适配；测试期不看未读值/标签。

```text
https://arxiv.org/html/2608.02305v1
```

## E03｜BTF-2

状态：`paper_html_read`。
读取范围：2026-04预印本；§4.2固定材料与研究/判断对照。
用途与边界：不要声称首次分离检索与预测。

```text
https://arxiv.org/html/2604.26106v1
```

## E04｜LEAP

状态：`paper_html_read`。
读取范围：2026-09预印本；固定证据预测聚合。公开适配器此前本对话读取见E12。
用途与边界：仅先用冻结/接口思想；独立后端未复现。

```text
https://arxiv.org/html/2609.01337v1
```

## E05｜EarthVerse

状态：`abstract_read`。
读取范围：本轮摘要页；跨灾种可执行答案、科学可靠性与控制实验。未重新审完整论文。
用途与边界：只支持近邻边界，不凭摘要宣称精确缺少某特性。

```text
https://arxiv.org/abs/2608.23525
```

## E06｜ExtremeWeatherBench官方文档

状态：`official_docs_read`。
读取范围：本轮官方文档首页；未复现代码/数据。
用途与边界：来源/预报结果适配；实施时固定版本。

```text
https://extremeweatherbench.readthedocs.io/en/latest/
```

## E07｜pysteps官方融合示例

状态：`official_search_excerpt`。
读取范围：本轮官方检索返回示例代码/输入条件；v1.21.4 API完整open缓存失败，不声称逐行审计当前实现。
用途与边界：雨量场/时间网格合格后采用；实施时核对本机版本。

```text
https://pysteps.readthedocs.io/en/v1.20.0/auto_examples/steps_blended_forecast.html
```

## E08｜ForecastBench

状态：`official_site_read`。
读取范围：本轮官方首页；未来提交/结算的参考，不声称本次执行。
用途与边界：前瞻影子轨参考，历史污染边界仍单列。

```text
https://forecastbench.org/
```

## E09｜USGS NLDI导航

状态：`official_docs_read`。
读取范围：本轮官方导航文档；上下游模式，未调用数据API。
用途与边界：辅助河网连接，不替代流量定义或传播时间。

```text
https://api.water.usgs.gov/docs/nldi/navigation/
```

## E10｜AWC Data API

状态：`official_docs_read`。
读取范围：本轮官方产品/缓存/频率/错误码文档。
用途与边界：批量缓存为强对手，当前接口不作多年归档。

```text
https://aviationweather.gov/data/api/
```

## E11｜LAMP官方webservices（本轮受限）

状态：`fetch_failed_403`。
读取范围：本轮直接读取403；LAMP具体已有进度依据R03，不假装本轮验证科学字段。
用途与边界：Codex优先复用仓库已保存的原生文档和样例；不绕过权限。

```text
https://vlab.noaa.gov/web/mdl/lamp-nws-webservices
```

## E12｜LEAP适配器

状态：`previous_turn_connector_code_read`。
读取范围：本对话此前GitHub读取，blob a3dc453b89f0c4f1c7c2023d9dec90a2c0d50687；未运行外部finalizer。
用途与边界：要求单独AGENTFUTURE_FINALIZER_BIN；接口可借鉴不等于算法已复现。

```text
https://github.com/layingfish/LEAP/blob/main/SKILL.md
```

## E13｜AFABench仓库

状态：`previous_turn_connector_read`。
读取范围：本对话此前README读取；本轮论文再次核查。
用途与边界：当前范围以实际固定commit核对，禁止评估标签进入正常策略。

```text
https://github.com/Linusaronsson/AFA-Benchmark
```

## E14｜BRiG-AFA仓库

状态：`previous_turn_connector_read`。
读取范围：本对话此前README读取；本轮论文再次核查。
用途与边界：选择性借风险回归，避免启动全量训练矩阵。

```text
https://github.com/JIAORONG-FENG/BRiG-AFA
```

