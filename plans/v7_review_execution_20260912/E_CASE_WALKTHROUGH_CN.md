# 用三个真实案例解释 C2 测量什么

这些例子按预先声明的错误类型取排序后的第一例，用于说明合同，不代表错误率或总体样本。
全部统计仍以 96 案例报告及完整 F 日历为准。下列结论来自公开产品和固定逻辑，不使用人工标签或 LLM 评委。

E 命题是：登记的两个邻站报告槽位中，是否至少有一个报告的能见度严格低于 1000m。
任一合法已读槽位确定低于阈值即可 supported；所有登记槽位均合法已读且不低于阈值才 refuted；否则 undetermined。

## 例 1：supported

案例 ID：`0739a0ae0dc83425482171958bcd5f11bbc04c7c177f4d1d091b877e6c519fb0`。

登记槽位：`routine-KDEN-2024-01-05T14:00:00Z`；`routine-KPUB-2024-01-05T14:00:00Z`。

| 已读来源 | 原生能见度支持区间（米） | 原始报告 |
| --- | --- | --- |
| routine-KDEN-2024-01-05T14:00:00Z | [16093.44, 16093.44] | `KDEN 051453Z 24005KT 10SM FEW060 SCT100 SCT200 M04/M08 A2987 RMK AO2 SLP141 T10391083 57002` |
| routine-KPUB-2024-01-05T14:00:00Z | [0, 402.336) | `KPUB 051453Z 31005KT M1/4SM R08R/1000V1200FT FZFG BKN001 OVC080 M04/M04 A2989 RMK AO2 SLP146 I1000 I3000 T10391044 53005` |

未读槽位：无。

| 模型 | 联合 F/E | E-only | E 加规则例子 | E 事实表 |
| --- | --- | --- | --- | --- |
| qwen3_8b | supported | refuted | supported | undetermined |
| qwen3vl_32b | supported | supported | supported | supported |

合法已读报告中已有一个上界严格低于 1000m 的区间，因此存在命题确定成立；另一个邻站能见度高不改变这个结论。

同链 F 仍是 `KCOS-2024-01-05T17:00:00Z-vis-lt-1000m` 的未来报告。当前邻站事实的 supported/refuted 不是该未来目标的确定结果，不能据此自动把 F 概率设为 1/0。

## 例 2：undetermined

案例 ID：`001f1aaf7217518d7123effe33adcc5df68a92722811a7c216b9cae04ceae141`。

登记槽位：`routine-KCOS-2024-01-06T06:00:00Z`；`routine-KPUB-2024-01-06T06:00:00Z`。

| 已读来源 | 原生能见度支持区间（米） | 原始报告 |
| --- | --- | --- |
| routine-KPUB-2024-01-06T06:00:00Z | [14484.096, 14484.096] | `KPUB 060653Z AUTO 32004KT 9SM FEW041 OVC055 M01/M03 A2990 RMK AO2 SLP138 T10111028 400391061` |

未读槽位：routine-KCOS-2024-01-06T06:00:00Z。

| 模型 | 联合 F/E | E-only | E 加规则例子 | E 事实表 |
| --- | --- | --- | --- | --- |
| qwen3_8b | undetermined | undetermined | supported | refuted |
| qwen3vl_32b | undetermined | undetermined | supported | refuted |

当前没有已读报告确定低于阈值，并且仍有未读登记槽位。不能由已读槽位的高能见度推导所有登记槽位均无低能见度。

同链 F 仍是 `KDEN-2024-01-06T09:00:00Z-vis-lt-1000m` 的未来报告。当前邻站事实的 supported/refuted 不是该未来目标的确定结果，不能据此自动把 F 概率设为 1/0。

## 例 3：refuted

案例 ID：`0033f7b7647befe7d220246c31db503cc4929b0cee132f3e9896834171d72fdc`。

登记槽位：`routine-KCOS-2024-01-24T00:00:00Z`；`routine-KPUB-2024-01-24T00:00:00Z`。

| 已读来源 | 原生能见度支持区间（米） | 原始报告 |
| --- | --- | --- |
| routine-KCOS-2024-01-24T00:00:00Z | [16093.44, 16093.44] | `KCOS 240054Z 16006KT 10SM BKN050 BKN090 BKN200 05/M03 A2994 RMK AO2 SLP155 T00501033` |
| routine-KPUB-2024-01-24T00:00:00Z | [16093.44, 16093.44] | `KPUB 240053Z 10006KT 10SM OVC110 05/M03 A2991 RMK AO2 SLP145 T00501033` |

未读槽位：无。

| 模型 | 联合 F/E | E-only | E 加规则例子 | E 事实表 |
| --- | --- | --- | --- | --- |
| qwen3_8b | supported | refuted | refuted | refuted |
| qwen3vl_32b | undetermined | refuted | refuted | refuted |

两个登记槽位都已取得合法报告，并且可见支持均不低于阈值，因此当前存在命题被反驳。

同链 F 仍是 `KDEN-2024-01-24T03:00:00Z-vis-lt-1000m` 的未来报告。当前邻站事实的 supported/refuted 不是该未来目标的确定结果，不能据此自动把 F 概率设为 1/0。

## 怎样解释这些错误

这些输出能定位模型回答与合法可见支持之间的不一致，但不能单凭输出断定模型内部究竟混淆了单位、存在量词、槽位、来源还是提示字段。
事实表由同一已读产品确定性转换而来，属于公开标明的辅助条件；没有把隐藏未来结果交给模型。它不是原生图像得到的精确物理真值。
顺序复核保留这些消息，改变条件/案例执行排列；结果以新批次实测为准，不修改本轮原始回答。
