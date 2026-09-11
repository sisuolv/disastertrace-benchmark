# 当前代码复用与研究核查清单

状态：基于本地实现的规划审阅；不是一次完整代码审计，也未在本轮重新验证外部仓库或论文。当前源码哈希见 [基线清单](BASELINE_SNAPSHOT.json)。

## 1. 现有模块的具体用法

| 现有文件 | 本轮确认的行为 | 下一阶段建议 |
| --- | --- | --- |
| [models.py](../../disastertrace-starter/src/disastertrace/models.py) | Artifact 有 issue/valid/available；StateLedger 的 KEEP 直接跳过，持久状态只存 evidence IDs | 复用旧类型的设计经验；新内核显式区分 availability 未知、产品/内容/投递、值保持与完整引用刷新 |
| [evidence.py](../../disastertrace-starter/src/disastertrace/evidence.py) | strict 根据可用区间上界与允许等级判合法 | 保留 fail-closed 思路；新 profile 单独支持 first_seen、受控回放与递归父资产检查，不修改历史等级含义 |
| [forecast_source/pipeline.py](../../disastertrace-starter/src/disastertrace/forecast_source/pipeline.py) | 固定来源 scope、字节捕获、双解析、CPU review；旧 scope 硬绑定 12 个指定 body | 抽象同样的来源凭据和独立重建接口，新增 provider scope；不放松旧 selection/字节限制来兼容新数据 |
| [forecast_task/protocol.py](../../disastertrace-starter/src/disastertrace/forecast_task/protocol.py) | 只允许同目标原历史 prefix；snapshot/状态/原答案三载体；每次提供累计可见文本 | 保留历史隔离与调度种子规则；累计全证据不能直接声称实现了预算主动取证，需要新的 read-state |
| [multimodal_v1/types.py](../../disastertrace-starter/src/disastertrace/multimodal_v1/types.py) | FactKey、DeliveryEvent、三值逻辑和按目标/模态选择版本已实现 | 把 threshold_kt、seed extent 等风圈特化项扩为通用目标 schema；边界/unknown 语义逐任务声明 |
| [multimodal_live_v1/adapter.py](../../disastertrace-starter/src/disastertrace/multimodal_live_v1/adapter.py) | 真实 PIL 图像、processor 张量与视觉 token 数检查、上下文预留、贪心生成、deadline | 通过薄适配复用 Qwen backend；多模型维持各自 processor adapter，并绑定实际输入曝光 |
| [multimodal_atomic_v1/runner.py](../../disastertrace-starter/src/disastertrace/multimodal_atomic_v1/runner.py) | 独立任务、raw-first、dispatch intent、每题失败隔离，unknown 不触发重试 | MM-5A 可以复用独立任务模式；动态环境必须另加轨迹状态、动作日志、固定检查点与资源账本 |
| [multimodal_atomic_v1/audit.py](../../disastertrace-starter/src/disastertrace/multimodal_atomic_v1/audit.py) | 从冻结任务与原始捕获重建，检查意图、processor 哈希和未计划捕获 | 复用审计不依赖评分缓存的原则；新报告应重建实际读取状态与每个策略的参考视图 |
| [multimodal_atomic_v1/scoring.py](../../disastertrace-starter/src/disastertrace/multimodal_atomic_v1/scoring.py) | 严格解析、值与引用分解、聚合保留失败 | 不修改旧 scoring；新任务分开支持性、目标完成度、充分性、结果和成本 |
| [MM-4 NEXT_STEP](../../disastertrace-starter/artifacts/multimodal_v1/mm4_atomic_20260909/NEXT_STEP_CN.md) | 80 次等信息对照、空间平衡、第二模型、再扩事件 | 保留为测量工作线；以新版本协议解除它对所有多灾种取数的串行阻塞 |

“复用”优先复用公开接口、不可变工具和已经验证的模式。若旧函数硬绑定批次/路径/语义，新增薄适配或新模块；不要为了追求源码行数少而改动已接受的历史文件。基准 scorer 与 reader 的独立校验也不能共享同一个可能出错的核心变换再相互证明。

## 2. 推荐的新目录职责

以下为设计示意，不代表文件已存在：

```text
src/disastertrace/active_forecast/
  contracts.py          # 目标、内容、版本、捕获、投递、提交
  provenance.py         # 来源、release、父资产、引用 locator
  storage.py            # 不可变内容和追加捕获，恢复/占用规则
  visibility.py         # as-of 和公共投影，递归派生物检查
  providers/            # 各类来源 adapter，不含模型决策逻辑
  references/           # 产品事实、已读/合法池/充分性、后续结果
  environment.py        # 合法动作、预算、逻辑时间和固定检查点
  runner.py             # 轨迹失败隔离、意图/raw 捕获、不可重复提交
  adapters/             # 各模型真实文本/图像处理器
  metrics.py            # 分项评分、覆盖、成本；避免默认总分
  audit.py              # 从原始记录独立重建
```

数据按新版本输出到新的目录，逻辑上分 raw/captures、normalized、public、private references、splits、runs、reports。公共执行根只含允许的材料；仅把路径称为 private 不等于隔离完成。采集器不能把未到截止时刻的产品写进当前模型索引。

新 source provider、renderer 和 task template 只实现其职责，不为每个灾种复制整套 runner。模块规模可随首批实际需求收缩，避免先建设一个没有真实调用者的大框架。

## 3. 外部开源的复用顺序

以下是候选复用清单，包含附件给出的仓库及常用工具入口。本轮没有 clone、执行、核验最新 commit 或复查许可证。V5-23 负责从第一方链接确定 release/commit，再以真实样本对比官方 reader；代码许可证与数据许可证分别记录。

| 候选项目 | 可以复用的部分 | 仍需 DisasterTrace 实现的部分 |
| --- | --- | --- |
| [WeatherBench 2](https://github.com/google-research/weatherbench2) | 地球科学坐标、连续/集合预测评估、气候基线的已有实践 | LLM 的证据读取、修订、支持性和取证成本；不能直接照搬其模型排名 |
| ExtremeWeatherBench | 极端事件目录、事件窗口和气象目标评价思路；从其官方发行页锁定仓库 | 自然监测负例、产品历史可用性和面向 LLM 的输入协议 |
| [SEVIR](https://github.com/MIT-AI-Accelerator/eie-sevir) | catalog/HDF5 读法、通道与时序处理 | 防未来帧泄漏、任务目标和研究用数据范围 |
| [Digital Typhoon](https://github.com/kitamoto-lab/digital-typhoon) | 官方格式、图像和关联路径的读取 | best-track 裁剪先验声明、在线定位资格、跨版本时序 |
| [ml4floods](https://github.com/spaceml-org/ml4floods) | WorldFloods reader、波段/标签与地理处理约定 | 标签来源审计、有效覆盖逻辑界和时间对齐 |
| [TS-SatFire](https://github.com/zhaoyutim/TS-SatFire) | 火活动时序和现成处理配置 | 数据泄漏分组、火点与真实灾害后果的目标区别 |
| [earthaccess](https://github.com/nsidc/earthaccess) | NASA 元数据搜索与受支持的数据访问 | 本项目的预算、捕获、历史可用性和模型访问隔离 |
| [ECMWF Open Data client](https://github.com/ecmwf/ecmwf-opendata) | 正式预报产品取得方式 | 预报时间锁定、专业基线的目标匹配和可重建评价 |

xarray/rasterio/pyproj、GeoPandas/Shapely、h5py 等可按首批格式需要选择。优先使用已安装可用环境；新增依赖放新环境并锁版本，不升级历史已绑定环境。GEE、STAC/S3、机构直接下载是不同访问接口，不把 GEE 认证设为所有数据接入的必要前提。

## 4. 与已有 benchmark 的研究关系

下表是要验证的比较维度，不是已经完成的文献结论。近期论文名、版本和 arXiv 链接来自 P45 等输入材料，需核查原文、附录、开放代码和实际任务，尤其不能只凭摘要宣称“首次”。

| 对照对象 | 本项目应核查的维度 | 对实验设计的影响 |
| --- | --- | --- |
| WeatherBench 2 / ExtremeWeatherBench | 气象模型、事件目标、专业基线、概率/连续误差 | 未来预测轨必须使用目标兼容的专业基线 |
| SEVIR / WorldFloods / Digital Typhoon 等数据集 | 模态、标签来源、空间时序、已知任务与 split | 将已有数据作为来源，不能把重包装数据本身当成全部创新 |
| CLLMate / WeatherQA / DisasterVQA / AFDBench | 静态多模态理解、自由文本评估、数据与模型污染可能性 | P/C 任务需要说明与现成 VQA 的增量，格式可靠性另列 |
| StateMemBench | 长历史/状态维护、载体表示、评价真值 | 核查状态收益是否依赖长度和特权历史，设计公平载体消融 |
| EarthVerse | 地学多模态/交互范围、工具与评价机制 | 比较任务权限、真实物理量、因果/时空解释等具体层面 |
| DORA / AFABench | 主动检索/取证、工具动作、停止和预算 | 明确三类参考、固定分母、成本曲线是否提供真实新增价值 |

P45 提供的待核查原文入口：StateMemBench `arXiv:2608.19652`，EarthVerse `arXiv:2608.23525`，DORA `arXiv:2605.11633`，AFABench `arXiv:2508.14734`，AFDBench `arXiv:2608.24954`。本轮没有确认这些标识与摘要/代码内容的一致性；核查结果要引用具体章节而非沿用计划中的二手结论。

建议文献对照表固定字段：数据领域、自然/受控时间、公开可用性证明、原始模态、目标是否固定、逐题人工/LLM judge、主动动作、充分性参考、后续 outcome、专业基线、泄漏/事件分组、失败分母、代码与数据版本。

## 5. 可投稿贡献的证据门槛

优先检验三个可组合贡献：

1. 多源、多时标下可复算的证据支持与充分性协议，避免 unknown 退化和未来泄漏。
2. 同目标修订与现实变化分离的轨迹数据，以及值不变但来源变化、覆盖变化等诊断。
3. 在相同预算下的主动取证比较；只在可靠 outcome 子集上进一步声称预测/预警价值。

需要的支撑是合格真实数据、强程序/专业基线、多模型、多事件组、等预算对照和独立重建。模型低分、大数据量、很多 JSON 文件或与简单策略相似的输出模式都不能单独证明这些贡献。
