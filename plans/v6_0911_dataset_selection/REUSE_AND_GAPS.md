# 复用现有实现与需要增加的接口

现有仓库已经有真实多模态实现，不能再沿用“尚无 MM 框架”的旧结论。已读取 `disastertrace-starter/README_MULTIMODAL_V1.md`、`CURRENT_PHASE.md`、`multimodal_v1/types.py` 和实际 admission；本轮未修改这些冻结模块。

| 现有部分 | 可以复用 | 还要补什么 |
| --- | --- | --- |
| multimodal_v1: ArtifactMeta、FactKey、DeliveryEvent、QuerySpec | 源资产、语义键、交付、确定性查询的已有协议 | 通用变量/单位/时间支撑区间；FactKey.threshold_kt 不能直接用于温度/雨量/土壤湿度 |
| NHC/MM 原始获取、存储、空间参考 | 哈希、官方产品、矢量参考及受控投递分支 | 扩展 source adapter；原生图像解读单列，不将数据重绘误标为原始卫星 |
| active_forecast exact kernel | 确定性计数、面积、修订运算及已有评分约束 | 各灾种 source admission；状态、输入、私有标签的运行时隔离；新增预算规则另行验收 |
| 现有受保护配置和源 manifest | 冻结样例/保护 ID 的继承 | 同一物理事件、重叠瓦片/时窗、跨 benchmark 资产重复的完整图 |
| 当前匿名有界下载、Range、解码脚本 | 捕获回执、失败、断点拼接、局部读、哈希及已有标签检查 | 重复运行的增量注册、provider schema 漂移检查、正负样例策略及测试覆盖 |

建议只增加数据准入/桥接层，不重写 benchmark 框架。最小数据记录应包含 source/version、artifact SHA256、变量和单位、valid time/issue time/retrieved time、空间范围/CRS、缺测/QC、原始 split、event ID、label authority、rights、parent products。historical_available_at 没有证据就保留 null。

三种图分开：physical-event graph 用于跨源事件切分；asset-reuse graph 用于重复影像、裁剪和派生资产防泄漏；source-dependency graph 用于独立证据声明。共享 ERA5 不会把所有天气事件连接成一个簇。

Gold 采用确定性记录读取、阈值/持续时间算法、空间运算及已有官方/公开数据集标签。允许已有专家标签并标注来源，例如 USDM、洪水人工掩膜；不新增逐题人工复核，也不使用 LLM judge 决定事实。数据发生冲突、时空或许可不能确定时，自动拒绝该题或显式输出 unknown，不能用模型补造真值。

未完成：多灾种通用 adapter、概率/分层抽样、全量事件去重、正式 train/dev/test、严格 as-of、原生影像必要性检查、跨灾种 Gold 一致性测试，以及新增模型实验。本轮的资产可解码不代表上述能力已实现。
