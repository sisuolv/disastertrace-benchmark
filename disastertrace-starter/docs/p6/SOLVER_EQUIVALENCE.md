# 现有任务域中的简单求解策略边界

在 P4 base 与三组 P5 的实际冻结任务上，公开 `latest_issued_per_key` 和独立 public
oracle 都达到每组 180/180。统计不乘上三种方法：这些程序使用 snapshot 的公开信息，
不需要模型历史或私有 Gold。结果见 P6 `posthoc_final/shortcut_scores.json`。

这里的 `latest` 必须按完整事实键过滤：实体、绝对有效窗口、measurement kind、
variable 与 unit。全局最新文档、最后交付记录、同数值就接受引用均不是等价规则。

## 为什么在当前域成立

公开 parser 和私有 validator 限制每个事实键只有一条合法版本链：父版本先交付，
子版本的 issued time 严格推进，无 fork、cycle、跨键父指针或第二个冲突根。
因此可见链头恰好是该键已交付断言中 issued time 最大者。PATCH 对未提及的键没有
删除含义；把旧记录再次交付也不会改变其 issue time。按键选择最大 issue time 就能
得到与 authority resolver 相同的值和当前引用。

这个结论需要当前协议的前提，不能推到真实来源冲突、多权威层级、合法分叉、撤销
或 issued/available/effective 三种时间混用的任务。非法输入必须被拒绝，不应为了
让简单策略失败而给它伪造 Gold。

## 本轮实际比较

| 策略 | Base | Revision | Scope | Stale |
| --- | ---: | ---: | ---: | ---: |
| initial_only | 90 | 90 | 90 | 90 |
| last_delivered | 144 | 144 | 144 | 144 |
| most_frequent_value | 144 | 168 | 144 | 144 |
| most_frequent_unique_assertion | 144 | 168 | 144 | 144 |
| latest_issued_per_key | 180 | 180 | 180 | 180 |
| scope_blind_last_delivered | 132 | 132 | 78 | 138 |
| public_oracle | 180 | 180 | 180 | 180 |

每格分母 180。频率策略分别按交付的 ASSERT 次数和唯一 revision 投票；票数相同时
使用最新交付/行号作确定性 tie-break。精确 replay 会改变第一种投票数，也可能影响
两种策略的 tie-break，但不能改变 authority。策略名称与上述规则一起解释。

## 可以支持与不能支持的结论

可支持：当前任务测量显式状态维护、按键筛选、局部更新、旧资料处理与精确来源定位。
P5 中可观察的来源错误可以细分并原样保留，结构合法不意味着事实和引用正确。

不可支持：现有高分证明模型掌握复杂版本图、内部长期记忆更强、某方法普遍优于其他
方法，或者已经具备真实天气预报技能。下一版增加图复杂度必须先公开合法语义与独立
Gold；下一版真实 forecast 轨必须保留官方原始数值和时间，不能借合成修订冒充真实。
