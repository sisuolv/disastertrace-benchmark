# DisasterTrace v10 小型完整重建包

本包按预先指定的普通 F／Denver 诊断／2017-01 温度和一个 E02 错误实例抽取。它是完整日志重放子集，不代表所有实验、独立天气过程或新模型调用。

运行：`python verify.py --capsule . --result /tmp/disastertrace-capsule-result.json`。只需 Python 3.10+；不需要 API、GPU、模型权重或原始仓库。验证器阻止网络以及对原工作区的额外读取，核对字节清单、完整事件日志、原计分、独立 Brier 算术、原模型响应及两个 E 归约器。

数据来自 NOAA/NWS 经 Iowa Environmental Mesonet 归档的原生 TAF/METAR，以及先前已解析的 EUPPBench 集合预报和 DWD 站点日产品。保留原结果来源与完整原始文件哈希；归档情景延迟不代表已证明的历史首次公开时间。E02 示例按错误选取，仅解释程序汇总，不用于估计总体收益。温度为完整一个月的两条 COPY 程序轨，尚非温度 LLM 或补证 C1 结果。

原始路径仅作为来源标识保留于 MANIFEST.json，不应在重建时访问。上游资料的使用条款继续适用；本包供项目私有研究复核。
