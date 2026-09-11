# 已有 benchmark 的复用与研究差异

本表依据已捕获的作者文档、目录、读取器和样例，服务于数据选择。只声明核验到的能力；没有把“本次未发现”写成“原项目完全不支持”。独立首创性/发表新颖性仍需完整文献检索。

| 对照项目 | 已实查的资料 | 值得复用 | DisasterTrace 需要补的研究层 |
| --- | --- | --- | --- |
| [ExEBench / EarthExtreme-Bench](https://github.com/zhaoshan2/EarthExtreme-Bench) | 固定 HF commit 的寒潮包、数值序列读取器、配置；9 个病例 NetCDF/CSV | 多灾种变量与数值资料组织；非美国病例；空间温度场 | 面向 LLM/VLM 的证据阅读、时效状态、冲突/未知处理；同一案例不增加来源独立性 |
| [ExtremeWeatherBench](https://github.com/brightbandtech/ExtremeWeatherBench) | 329 个事件定义、数据适配代码、小时地面观测 row group | 独立事件配置、观测/预报/参考产品分层、真实极端定义 | 把案例与具体证据包配对；区分模型天气预报成绩与 LLM 读取/推理成绩 |
| [WeatherQA](https://github.com/chengqianma/WeatherQA) | 文档中的 20 参数地图组织；SPC MD0398 原文；Drive 数据失败 | 地图和气象业务文本关联方式、上游产品入口 | 同一地图分析时间 17:00Z 与正文发行 17:56Z 必须分开；图文任务需要确定性可评分标签，开放解释不作 Gold |
| [CyPortQA](https://github.com/ChenchenMobility/MLLM-Bench-CyPortQA) | Dorian/Harvey/Florence 各一图一文、模板、LICENSE | 气旋图文格式、港口情境与业务问题模板 | 先逐产品核对时刻，再考虑行动问题；港口关闭/开放要有显式政策及外部状态依据 |
| [GEOID-Flood](https://github.com/links-ads/geoid-flood) | 3 组 12 个对齐资产、发布清单哈希、CEMS activation/AOI | 三类标签、前后 SAR、有效区域和事件来源链 | 像素标签转为确定性空间/状态问题；私有 Gold-derived validity 隔离；补真正正例及新事件 |
| [CLLMate](https://github.com/hobolee/CLLMate) | 公共 JSON 中的节点、日期、坐标与新闻/图像路径字段 | 事件检索和跨媒体关联候选 | 新闻/图像未取回、因果边未核验，不能继承为 causal Gold；优先做证据支持程度判断 |
| [TorNet](https://github.com/mit-ll/tornet) | 作者读取器/发布说明及 3 个完整负例雷达文件 | 雷达序列、事件身份与难负例 | 先核正例与 v1.1，再建立地面确认/雷达表现/LLM 答案的分层评估 |
| [WildfireSpreadTS](https://github.com/SebastianGer/WildfireSpreadTS) | 作者读取器及 3 个相邻日 TIFF | 同一事件的真实演化、活动火探测时刻解释 | 分开探测/无探测/覆盖缺失；审计输入预报的 as-of 信息；避免将火灾成因默认标为天气 |

推荐论文主问题：同一极端天气事件中，当图像、观测和官方产品具有不同时间、空间支撑范围与可靠性时，LLM/VLM 能否给出有依据的状态结论，随有效证据更新，并在证据不足时正确保留未知？

该问题需要用以下方法落实，才能超过现有资料拼接：

1. 将物理过程演化、同目标预报修订、受控证据交付分别建集与计分。
2. 固定事件与答案，控制过期证据、矛盾证据、重复来源、缺失模态，形成可解释的成对诊断。
3. 保留 oracle structured evidence 与原始影像输入对照，分离感知错误和推理/更新错误。
4. 用独立事件族、跨地区和跨灾种留出测试衡量泛化，避免按帧/瓦片/问题重写扩大有效样本数。
5. 以来源和确定性规则产生 Gold；允许披露来源的已有专家/人工数据集标注，不新增逐题人工复核。

当前证据支持以上研究定位；其优势大小、必要的任务规模和相对于所有相关工作的创新范围，仍要由后续系统文献检索及冻结实验确定。
