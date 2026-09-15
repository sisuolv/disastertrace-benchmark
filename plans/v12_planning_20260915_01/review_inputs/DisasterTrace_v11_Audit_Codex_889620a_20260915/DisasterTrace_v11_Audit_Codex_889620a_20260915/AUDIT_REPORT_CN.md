# DisasterTrace v11 定向审计

审阅提交：`889620a4fc4ee6ad70757dd3e832a40c7509126a`；日期：2026-09-15。

## 1. 结论和证据范围

当前实现有实质修复，但不能据本次定向检查宣称全库正确。上一轮39项断言在当前模块上全部通过；新增19项中15通过、4失败，合计58项、54通过。4个失败归属两类问题：温度目标资格与整体产品资格混用（3种输入），全年采集的样例失败分支重复计数（1种输入）。

10份完整源码与当前提交的Git blob哈希一致。测试使用原函数体及原导入语句，在隔离包内加载；原生METAR/TAF解析器被一个调用即报错的哨兵代替，本次没有执行该哨兵。全年采集仅替换acquire_unit的网络依赖，execute函数原样执行，并写真实临时JSON结果。不是616/720/750项全套回归，不是完整FormalSession集成或天气数据复算。

仓库报告585个monitoring测试加165个不同补充测试共750通过；这是本次读取的仓库证据，未独立全跑。官方v11阅读ZIP未能在本环境下载，因此本次未执行官方capsule、全周评分或原始资料重建。

## 2. 版本与正在执行的工作

[S01-S05]当前提交是2026-09-15T12:07:09Z发布，报告快照是12:06:47Z。快照记载：840条完整周轨迹尚在执行；全年72地区月中71完成、1失败；2470份样例TAF原文和三个原生月连接还在单独推进。不能把“快照说running”当成当前ACP实时状态，更不能从逻辑目录数推算全年任务与拟合已经完成。

README里尚保留“本批未上传”的较早执行说明，不应覆盖根目录最新发布快照。规划文件里的planned也不是当前完成状态。Codex应读取实际工作目录、精确作业ID、退出码、产物与冻结清单，先核已有任务而非重新启动。

## 3. 已修复及合理的部分

* temperature_contract.event_values检查严格时间类型、午夜日界、目标长度、有限阈值、日期唯一、目标字段覆盖和成员形状。旧的shifted-day和duplicate-day反例已拒绝。
* feature_tasks.parse_temperature把极大整数和非有限概率纳入ValueError；validate_claims拒绝正无穷下界，保留合法删失上界。
* FormalSession v2绑定input_identity、正式目录、report/journal/STOP和provider policy；score_formal默认需要run_references，legacy必须显式。本次为静态检查。
* score_formal先每臂重放一次，再传入内部_score_replayed，不再重复19次。仓库单案例报告19→9次、1256→554.6秒；未控制文件缓存，不能承诺一般加速倍数。
* common银行适配器拒绝slot特征；common特征返回发生在付费原生字段提取之前。本次数值测试确认common不受付费内容值改变影响；没有重跑完整预测适配器。
* fullweek固定168个日会话条件×5臂，12096个机会；同values银行四臂与F_COMMON不同银行单独绑定，额外核对共同基线和非FOLLOW预测日程。最终审计尚未出现在当前快照。

## 4. F01：温度未消费变量导致合法目标被拒绝

文件：`monitoring_v1/temperature_postprocess.py:10-33`。

`event_values()`已经按变量取出需要的完整成员值，但`event_probability()`随后调用`validate_products(products)`，要求每一天都同时有完整min和max。

合成目标：2018-01-02 00UTC至次日00UTC，提前半天，最高温≥30℃，成员[31,20]。删除最低温列后，feature_tasks.temperature_ensemble_probability返回0.5；postprocess.event_probability抛KeyError。把未使用的最低温列改成缺失/NaN，后者同样拒绝。最低温目标缺最高温的对称情况也成立。

这不是数值公式算错，而是资格判断不一致。若产品级EMOS/ECC确实需要min/max，严格检查合理；若只是计算原生最高温事件，不应让未消费最低温缺失改变可计分分母。当前计划W01已经提出这种区分，本次是确认该项尚未落实完整，不包装为旧漏洞再次出现。

最小修复：拆开target-level事件校验与joint-product后处理资格。event_probability只校验其实际变量/日期；ecc_products保留完整min/max条件。两个数值归约仍独立。调用者如果明确要求完整产品，应在命名和schema里标明，而不是隐式混用。

历史影响：未扫描真实温度所有输入，不能宣布0影响或全部无效。按已登记POLICY、模型包任务和原始参考逐项列unchanged/affected/not_evaluated。只读扫描，修订结果另存；不得重新调用模型。

## 5. F02：年度样例失败时结果被复制两次

文件：`plans/v11_execution_20260915_01/annual_catalogs.py:164-183`，关键行为在177行。

现式：
```python
results = sample + (list(pool.map(acquire_unit, remaining_tasks)) if sample_ok else sample)
```

样例失败时等于sample+sample。实际离线执行72单位注册、3个样例中2成功1失败，只有3次模拟acquire调用，最终JSON却有6条结果、completed_units=4、not_attempted=69。passed仍为false，退出码仍为1。没有发生额外HTTP，也没有误宣布全年度通过；错误在失败汇总和单位计数。

当前三个闰月样例在发布中是通过的，因此不能将当前71/72目录状态归因于该反例。当前失败来自后续KORD分片，属于另一路径；测试验证样例通过后1个后续单位失败时仍正确得到72条、71成功。

最小修复：样例失败的追加列表为空；每个终态强制唯一unit_id，按registered=completed+failed+not_attempted分区核对。HTTP精确重试单独按attempt_id计，不变成新的逻辑unit。补回归后不重跑已完成年度下载，也不覆写旧失败JSON。

## 6. 待补资格：不计作新的真实数据错误

[S06]day_index仅检查为正整数，未验证origin+day_index与target_date相符。注入day_index99仍通过是已执行的特征性观察。等长数组也不能证明同成员lineage；当前报告已经披露。需要来源坐标、原始成员ID、日期与起报对齐，而不是猜测数组下标可靠。

[S05]C2的72个覆盖任务全为full，144任务构建不是难度或预测价值验证。E版本/覆盖问题使用共同TAF时属于免费共同事实，不能因为为其增加读取工具就收取额外信息费。需要普查非平凡自然状态，并验证哪个字段实际进入F。

[S11]正式来源、STOP、评分、API最后许可点本次只做静态阅读，未作端到端故障注入。不能将59/58项合成探针、仓库750项和本地平台实测混写一个通过数。

## 7. 研究解释

本轮零新增被测LLM调用；v10负结果继续有效。完整周最终损失仍未知，不把旧首日平均或新360条预检代替全周结果。现有论文重点应是区分共同信息后处理、同后端额外信息、预算内取得信息、提取与采用各环节，而不是换版本号或累加下载量。

当前优先顺序合理：收口已有全周 → 全年来源与角色/后端 → 同状态C2 → 有界模型 → 冻结确认。建议把C2任务普查、checkpoint一致性小试和全年下载并行，但小试结果只作开发，不抢先声称科学机制已确认。

## 8. 本地复查命令

```bash
cd audit_probes
python -B -m pytest -q -p no:cacheprovider test_inherited_controls.py test_v11_boundaries.py
python -B reproduce_diagnostics.py
```

当前冻结代码预期4失败/54通过，失败原样保留，不设xfail掩盖。Codex在完整工作区运行：
```bash
DT_REPO_ROOT=/absolute/path/to/disastertrace-benchmark \
  python -B -m pytest -q -p no:cacheprovider test_inherited_controls.py test_v11_boundaries.py
```
修改后的仓库测试应该验证正确新行为，不能修改本包冻结源码来伪造原始观察。旧39项测试仅迁移DAY常量读取位置到temperature_contract，断言未改。

本包不含远端凭据、临时下载token、模型权重或全年天气原始资料。来源详见SOURCES.json。
