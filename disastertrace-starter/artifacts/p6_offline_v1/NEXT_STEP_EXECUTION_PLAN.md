# 下一步执行计划：P6 首轮离线交付之后

当前 E1 是 `generation_authorized=false / max_model_attempts=0` 的程序验收候选。
它不能直接切换布尔值后作为模型执行包使用；下述工作需要新的版本、执行身份和
单次运行目录。已获得的 GPU 使用许可继续有效，工程冻结与预检不代表再次索要许可。

## 第一优先：把同一矩阵接到实际运行环境

1. 新增模型专用后端，保持当前 renderer/输出轨/评分器不变，传递每个 slot 的 seed。
   后端记录唯一请求身份、实际硬件、版本、采样参数、完整 raw token/text 与 finish。
   对完整与部分返回、提取异常、超上下文、unknown 和跨 repeat 载体污染执行相同反例。
2. 实现单次 phase launcher 和 ACP worker。按
   `/mnt/afs/260010168/ACP-GPU-QUICKSTART.md` 操作，先在一张完整 H100 80GB 上执行
   无生成预检。最多 4 卡上限继续适用；首轮建议单卡顺序执行整个 2160 矩阵，避免
   条件与硬件/worker 混杂。若分卡，必须把每个配对的两条件放到同一 worker，并预先
   冻结每卡调度、资源和跨条件平衡，不在结果出来后重新分片。
3. 检查真实运行环境与本候选的 Qwen3-8B 权重、tokenizer、BF16、vLLM/XGrammar、
   输出 cap、context、multiprocessing、prefix cache 设置。预检只载入模型，不发探针。
   将实际观测绑定到新的 live freeze，同时声明 deadline、one-use run、零重试、
   2160 最大回答机会及 17,694,720 最大生成 token 预留。
4. 通过新 live freeze 的完整程序诊断和独立审计后，在既有 GPU 许可下启动一次。
   初始 launch/claim 无论成功或中断都消费；只允许 CPU 复查已收结果，不能择优补跑。
5. 按本轮协议输出逐 repeat/来源表、双向变化、曝光切片、episode success/pass^2、
   基础设施完整性和 token/GPU 墙钟。结果仍是开发集描述，不能宣布方法普遍胜出。

这个矩阵解决历史硬件/种子/重复不足中的一部分问题，不能扩充天气现象覆盖。禁止
同时悄悄追加另一个三次重复、四因素或第二模型矩阵。

## 第二优先：有界真实 NHC forecast 原文轨

单独建立 source bundle，不覆盖受控任务。起步上限建议 2 个明确的 development
风暴、每个最多 6 份 forecast advisory，共最多 12 份正文。先检查现有 heldout 列表、
plan 已曝光资料及来源台账，再确定确切 storm/advisory IDs。计划里已出现的 Francine
2024 AL06 原文示例，以及第四份方案的 Ian 2022 AL09 advisory 005/009，属于已曝光
候选，不能作为未见 heldout；如与既有 heldout 清单冲突，优先保留冻结 split 并标记
计划曝光，另选开发来源，不自动改写旧分组。

每份正文保存 URL、原始字节与 SHA-256、获取时间、HTML→文本版本和源行映射。
issued、initial/reference、lead、absolute valid time、archive retrieval time 分栏，
没有证据就不推断历史 available_at。仅同绝对 valid time 才能构成 forecast 修订对。

至少两个独立解析路径：一个从官方 forecast 原文块提取；另一个实现独立的表格/
时间解析，必要时用固定 aid/init/tau 的官方 A-deck 做辅助交叉核对。Tropycal 是可选
检查入口，不是唯一 Gold。对阵风/持续风、观测/预报、移动速度、时区/月末/年末、
经纬度符号、KT/MPH、同 +24h 但不同 valid time 建立反例。

两解析器不一致、时间歧义、单位不明或 heldout 冲突均自动 quarantine，保留原因。
不得把当前压力数据填成未来压力预测，不按模型表现修补支持 span，不让 LLM judge
替代主评分。原始表与结构表必须信息等价；同一父产品的两个展示不是独立来源。

## 第三优先：在覆盖与任务版本稳定后比较方法和模型

先决定科学问题，再添加正交干预：长度匹配的 near/far scope、同值与异值修订、
短 ID/一致重命名、ASSERT 行序，或另立共同 prefix 的直接载体干预。记录每项实际
曝光强度和合法 solver 分歧，不能靠更多 token 冒充更多推理深度。

冻结开发/heldout、自动 Gold、评分类别和上下文预算后，再选任务版本完全匹配的
第二模型。工具若直接计算完整 resolver，归为公开程序上界或 tool-assisted 方法。
训练、prompt 搜索、第二灾种和多模态在这些边界稳定后另立任务。

第四方案建议的等内容、不同表示 carrier 对照值得优先纳入下一方法研究：JSON
状态与等信息文本状态保持相同值/引用，另行检查 token 差；oracle carrier 只作为
上界。此研究不加入当前2160矩阵。领域中性显示对照也需新的 schema/parser 和
独立实验，不能把历史受控天气字段静默改名后混表。
