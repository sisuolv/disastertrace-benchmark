# 本地检查范围

运行：`python -B run_probes.py`（任意工作目录；Python标准库）。

四份源码字节均与GitHub Git blob一致。直接运行regional_calibration、selection、evidence_diagnostic；calibration移除了未使用的.evidence导入，仅执行candidate=None分支。未使用stub天气值或替代标签；所有输入是合成测试夹具，未加载历史API日志。

17组检查包含340种有限E真值组合和40次合成PAV拟合。这些组合不是独立天气样本，也不是数百项仓库测试。

已复现：selector重复JSON键采用最后值。未宣称该输入在真实日志出现。E聚合不一致被保留用于计分属于正确诊断边界；PAV和分支变化是设计敏感性，不当作错误修复后成绩。
