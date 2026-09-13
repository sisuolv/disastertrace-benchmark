# 本次定向文档与源码核验

本轮实际发出10次有界请求，全部HTTP 200且响应未截断；读取4份官方HTML与6个GitHub
文件。每次设20秒超时、2MB响应上限、无自动重试。保存原响应、解析文本、SHA256及
6个Git blob，5个与用户材料提供的相同文件blob一致。详见
[REFERENCE_VALIDATION.json](REFERENCE_VALIDATION.json)。

GitHub内容读取锁定的是单个文件字节，不等于完整上游仓库commit、环境或算法复现。
未运行所读取的上游代码；LEAP的SKILL文件仅作为研究对象阅读，没有应用其工作流。
上游源码快照用于本机核验，不自动代表后续原样再分发的许可已完成。

| 核验对象 | 实际读取确认 | 尚未验证 |
| --- | --- | --- |
| NOAA LAMP BUFR说明 | BUFR包括比LAV更完整的能见度/条件能见度等概率字段 | 对指定历史站点/起报是否可实际下载这些字段 |
| NOAA LAMP 2.7.0说明 | 存在15分钟最低类别与概率产品；原生能见度阈值包含<1 mile、<3 miles、<=5 miles | 当期实际文件、历史格式、观测窗口覆盖和任务准入 |
| IEM MOS说明 | LAV列出从2020-07-12起部分周期的档案入口 | 每个站/周期完整性、是否包含所需原生概率；未请求LAV科学样例 |
| EUPPBench README与dataset文档 | 插件和站点/格点数据组织；2017--2018 forecast、reforecast及ERA5/站点路径需区分 | 原始数组、actual init/lead/valid身份、站点质量、输入历史可用性和完整许可 |
| SEEPS4ALL README | 欧洲日降水；示例验证2022--2024、气候1991--2020；明确数据非商业许可说明 | 日界、站点小样例、业务预报配对、完整数据条款 |
| LEAP README与适配说明源码 | README很简短；适配说明明确依赖另装`AGENTFUTURE_FINALIZER_BIN`、冻结证据hash | 完整后端、环境、算法可复现性及在本任务的增益 |
| AFABench core/types.py | 部分接口包含可选label用于特权benchmark方法 | 完整环境适配、未读特征权限、异步/共享费用及实际运行 |
| weighted-pcrps helper | `compute_easyuq`中用`idr(y, preds_point_df)`拟合，再预测同一输入 | 不把该评估潜力设计改称本项目部署时合法校准；本轮未运行作者实验 |

EUPPBench文档中的示例、文字或日期坐标不能代替原始init/step/valid数组核验。
SEEPS4ALL README仍使用“in preparation”引用模板，本轮不据此更改论文发表状态。
论文状态和其他未重新读取的文献内容沿用输入包所声明的证据层级，不声称穷尽查新。

## 官方与作者入口

- [LAMP BUFR](https://vlab.noaa.gov/web/mdl/lamp-bufr)
- [LAMP 2.7.0产品说明](https://vlab.noaa.gov/web/mdl/lamp-card-2.7.0)
- [IEM MOS档案说明](https://mesonet.agron.iastate.edu/mos/)
- [EUPPBench插件](https://github.com/EUPP-benchmark/climetlab-eumetnet-postprocessing-benchmark)
- [EUPPBench数据说明](https://eupp-benchmark.github.io/EUPPBench-doc/files/EUPPBench_datasets.html)
- [SEEPS4ALL](https://github.com/ecmwf/rodeo-ai-static-datasets/tree/main/seeps4all)
- [LEAP](https://github.com/layingfish/LEAP)
- [AFABench](https://github.com/Linusaronsson/AFA-Benchmark)
- [weighted-pcrps](https://github.com/tobiasbiegert/weighted-pcrps)

当前没有新增benchmark科学样例、模型调用、GPU作业、外部依赖安装或运行。
这10次成功读取只支持上述具体文档/源码结论，不升级数据A1/A3/A4或科学发布资格。
