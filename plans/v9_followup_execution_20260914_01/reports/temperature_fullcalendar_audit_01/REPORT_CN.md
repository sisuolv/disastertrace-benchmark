# 温度连续预报程序试点

24 个日历月份、192 条程序轨迹、11644 个目标机会、3645 个唯一目标。没有模型调用。

同一目标保留多次专业起报版本；不同提前量共享结果，不能作为独立灾害相加。

| 事件 | 程序/协议 | 结算机会 | 正例机会 | Brier | 相对FOLLOW差值 | 改好/改坏 |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| fixed_threshold_hot_spell_3d | copy_current/base_bound_override | 1453 | 16 | 0.003973 | 0.000000 | 0/0 |
| fixed_threshold_hot_spell_3d | copy_current/persistent_override | 1453 | 16 | 0.004659 | 0.000686 | 7/19 |
| fixed_threshold_hot_spell_3d | copy_latest/base_bound_override | 1453 | 16 | 0.003973 | 0.000000 | 0/0 |
| fixed_threshold_hot_spell_3d | copy_latest/persistent_override | 1453 | 16 | 0.003973 | 0.000000 | 0/0 |
| fixed_threshold_hot_spell_3d | first_issue_hold/base_bound_override | 1453 | 16 | 0.003973 | 0.000000 | 0/0 |
| fixed_threshold_hot_spell_3d | first_issue_hold/persistent_override | 1453 | 16 | 0.004659 | 0.000686 | 7/19 |
| fixed_threshold_hot_spell_3d | follow/base_bound_override | 1453 | 16 | 0.003973 | 0.000000 | 0/0 |
| fixed_threshold_hot_spell_3d | follow/persistent_override | 1453 | 16 | 0.003973 | 0.000000 | 0/0 |
| fixed_threshold_ice_spell_3d | copy_current/base_bound_override | 1453 | 20 | 0.009559 | 0.000000 | 0/0 |
| fixed_threshold_ice_spell_3d | copy_current/persistent_override | 1453 | 20 | 0.008540 | -0.001019 | 7/8 |
| fixed_threshold_ice_spell_3d | copy_latest/base_bound_override | 1453 | 20 | 0.009559 | 0.000000 | 0/0 |
| fixed_threshold_ice_spell_3d | copy_latest/persistent_override | 1453 | 20 | 0.009559 | 0.000000 | 0/0 |
| fixed_threshold_ice_spell_3d | first_issue_hold/base_bound_override | 1453 | 20 | 0.009559 | 0.000000 | 0/0 |
| fixed_threshold_ice_spell_3d | first_issue_hold/persistent_override | 1453 | 20 | 0.008540 | -0.001019 | 7/8 |
| fixed_threshold_ice_spell_3d | follow/base_bound_override | 1453 | 20 | 0.009559 | 0.000000 | 0/0 |
| fixed_threshold_ice_spell_3d | follow/persistent_override | 1453 | 20 | 0.009559 | 0.000000 | 0/0 |
| frost_day | copy_current/base_bound_override | 2910 | 446 | 0.036178 | 0.000000 | 0/0 |
| frost_day | copy_current/persistent_override | 2910 | 446 | 0.040763 | 0.004585 | 175/433 |
| frost_day | copy_latest/base_bound_override | 2910 | 446 | 0.036178 | 0.000000 | 0/0 |
| frost_day | copy_latest/persistent_override | 2910 | 446 | 0.036178 | 0.000000 | 0/0 |
| frost_day | first_issue_hold/base_bound_override | 2910 | 446 | 0.036178 | 0.000000 | 0/0 |
| frost_day | first_issue_hold/persistent_override | 2910 | 446 | 0.040763 | 0.004585 | 175/433 |
| frost_day | follow/base_bound_override | 2910 | 446 | 0.036178 | 0.000000 | 0/0 |
| frost_day | follow/persistent_override | 2910 | 446 | 0.036178 | 0.000000 | 0/0 |
| hot_day | copy_current/base_bound_override | 2910 | 88 | 0.008570 | 0.000000 | 0/0 |
| hot_day | copy_current/persistent_override | 2910 | 88 | 0.012242 | 0.003673 | 46/205 |
| hot_day | copy_latest/base_bound_override | 2910 | 88 | 0.008570 | 0.000000 | 0/0 |
| hot_day | copy_latest/persistent_override | 2910 | 88 | 0.008570 | 0.000000 | 0/0 |
| hot_day | first_issue_hold/base_bound_override | 2910 | 88 | 0.008570 | 0.000000 | 0/0 |
| hot_day | first_issue_hold/persistent_override | 2910 | 88 | 0.012242 | 0.003673 | 46/205 |
| hot_day | follow/base_bound_override | 2910 | 88 | 0.008570 | 0.000000 | 0/0 |
| hot_day | follow/persistent_override | 2910 | 88 | 0.008570 | 0.000000 | 0/0 |
| ice_day | copy_current/base_bound_override | 2910 | 103 | 0.018260 | 0.000000 | 0/0 |
| ice_day | copy_current/persistent_override | 2910 | 103 | 0.017049 | -0.001211 | 54/110 |
| ice_day | copy_latest/base_bound_override | 2910 | 103 | 0.018260 | 0.000000 | 0/0 |
| ice_day | copy_latest/persistent_override | 2910 | 103 | 0.018260 | 0.000000 | 0/0 |
| ice_day | first_issue_hold/base_bound_override | 2910 | 103 | 0.018260 | 0.000000 | 0/0 |
| ice_day | first_issue_hold/persistent_override | 2910 | 103 | 0.017049 | -0.001211 | 54/110 |
| ice_day | follow/base_bound_override | 2910 | 103 | 0.018260 | 0.000000 | 0/0 |
| ice_day | follow/persistent_override | 2910 | 103 | 0.018260 | 0.000000 | 0/0 |

COPY_CURRENT/首次值保持如果改变了损失，改变来自旧概率持续有效，不是产生了新概率。
未来阶段仍需合法补充证据、强校准和真实模型预测；本批不证明 C1 的跨灾种收益。
