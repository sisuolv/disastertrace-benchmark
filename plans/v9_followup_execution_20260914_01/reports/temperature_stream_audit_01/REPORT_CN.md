# 温度连续预报程序试点

8 个日历窗口、64 条程序轨迹、876 个目标机会、280 个唯一目标。没有模型调用。

同一目标保留多次专业起报版本；不同提前量共享结果，不能作为独立灾害相加。

| 事件 | 程序/协议 | 结算机会 | 正例机会 | Brier | 相对FOLLOW差值 | 改好/改坏 |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| fixed_threshold_hot_spell_3d | copy_current/base_bound_override | 111 | 0 | 0.000921 | 0.000000 | 0/0 |
| fixed_threshold_hot_spell_3d | copy_current/persistent_override | 111 | 0 | 0.000998 | 0.000076 | 1/1 |
| fixed_threshold_hot_spell_3d | copy_latest/base_bound_override | 111 | 0 | 0.000921 | 0.000000 | 0/0 |
| fixed_threshold_hot_spell_3d | copy_latest/persistent_override | 111 | 0 | 0.000921 | 0.000000 | 0/0 |
| fixed_threshold_hot_spell_3d | first_issue_hold/base_bound_override | 111 | 0 | 0.000921 | 0.000000 | 0/0 |
| fixed_threshold_hot_spell_3d | first_issue_hold/persistent_override | 111 | 0 | 0.000998 | 0.000076 | 1/1 |
| fixed_threshold_hot_spell_3d | follow/base_bound_override | 111 | 0 | 0.000921 | 0.000000 | 0/0 |
| fixed_threshold_hot_spell_3d | follow/persistent_override | 111 | 0 | 0.000921 | 0.000000 | 0/0 |
| fixed_threshold_ice_spell_3d | copy_current/base_bound_override | 111 | 0 | 0.000530 | 0.000000 | 0/0 |
| fixed_threshold_ice_spell_3d | copy_current/persistent_override | 111 | 0 | 0.000256 | -0.000274 | 1/1 |
| fixed_threshold_ice_spell_3d | copy_latest/base_bound_override | 111 | 0 | 0.000530 | 0.000000 | 0/0 |
| fixed_threshold_ice_spell_3d | copy_latest/persistent_override | 111 | 0 | 0.000530 | 0.000000 | 0/0 |
| fixed_threshold_ice_spell_3d | first_issue_hold/base_bound_override | 111 | 0 | 0.000530 | 0.000000 | 0/0 |
| fixed_threshold_ice_spell_3d | first_issue_hold/persistent_override | 111 | 0 | 0.000256 | -0.000274 | 1/1 |
| fixed_threshold_ice_spell_3d | follow/base_bound_override | 111 | 0 | 0.000530 | 0.000000 | 0/0 |
| fixed_threshold_ice_spell_3d | follow/persistent_override | 111 | 0 | 0.000530 | 0.000000 | 0/0 |
| frost_day | copy_current/base_bound_override | 218 | 22 | 0.002086 | 0.000000 | 0/0 |
| frost_day | copy_current/persistent_override | 218 | 22 | 0.003145 | 0.001058 | 6/24 |
| frost_day | copy_latest/base_bound_override | 218 | 22 | 0.002086 | 0.000000 | 0/0 |
| frost_day | copy_latest/persistent_override | 218 | 22 | 0.002086 | 0.000000 | 0/0 |
| frost_day | first_issue_hold/base_bound_override | 218 | 22 | 0.002086 | 0.000000 | 0/0 |
| frost_day | first_issue_hold/persistent_override | 218 | 22 | 0.003145 | 0.001058 | 6/24 |
| frost_day | follow/base_bound_override | 218 | 22 | 0.002086 | 0.000000 | 0/0 |
| frost_day | follow/persistent_override | 218 | 22 | 0.002086 | 0.000000 | 0/0 |
| hot_day | copy_current/base_bound_override | 218 | 4 | 0.009954 | 0.000000 | 0/0 |
| hot_day | copy_current/persistent_override | 218 | 4 | 0.018687 | 0.008733 | 5/22 |
| hot_day | copy_latest/base_bound_override | 218 | 4 | 0.009954 | 0.000000 | 0/0 |
| hot_day | copy_latest/persistent_override | 218 | 4 | 0.009954 | 0.000000 | 0/0 |
| hot_day | first_issue_hold/base_bound_override | 218 | 4 | 0.009954 | 0.000000 | 0/0 |
| hot_day | first_issue_hold/persistent_override | 218 | 4 | 0.018687 | 0.008733 | 5/22 |
| hot_day | follow/base_bound_override | 218 | 4 | 0.009954 | 0.000000 | 0/0 |
| hot_day | follow/persistent_override | 218 | 4 | 0.009954 | 0.000000 | 0/0 |
| ice_day | copy_current/base_bound_override | 218 | 11 | 0.007449 | 0.000000 | 0/0 |
| ice_day | copy_current/persistent_override | 218 | 11 | 0.008575 | 0.001125 | 3/9 |
| ice_day | copy_latest/base_bound_override | 218 | 11 | 0.007449 | 0.000000 | 0/0 |
| ice_day | copy_latest/persistent_override | 218 | 11 | 0.007449 | 0.000000 | 0/0 |
| ice_day | first_issue_hold/base_bound_override | 218 | 11 | 0.007449 | 0.000000 | 0/0 |
| ice_day | first_issue_hold/persistent_override | 218 | 11 | 0.008575 | 0.001125 | 3/9 |
| ice_day | follow/base_bound_override | 218 | 11 | 0.007449 | 0.000000 | 0/0 |
| ice_day | follow/persistent_override | 218 | 11 | 0.007449 | 0.000000 | 0/0 |

COPY_CURRENT/首次值保持如果改变了损失，改变来自旧概率持续有效，不是产生了新概率。
未来阶段仍需合法补充证据、强校准和真实模型预测；本批不证明 C1 的跨灾种收益。
