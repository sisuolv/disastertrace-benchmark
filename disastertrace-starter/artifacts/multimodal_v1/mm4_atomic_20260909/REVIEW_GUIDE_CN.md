# 提交给 ChatGPT Pro 的 MM-4 复查说明

请复查一个以 LLM/VLM 为评测对象的极端天气 benchmark 开发批次。阅读本文件、
`RESULTS_CN.md`、`EXECUTION_PLAN_CN.md` 与 `NEXT_STEP_CN.md`，再审阅冻结源码和真实回答。
项目当前研究名为 DisasterTrace，数据在本批只包含一个 Francine 开发事件。
本批目标是诊断模型读取、引用、逻辑和版本选择中的错误，不是发布正式排行榜。

## 本包内容与已知结果

40 个独立请求，使用已固定的 Qwen3-VL-8B-Instruct 权重；40 个真实回答全部结构有效、
查询完整、EOS。严格正确：空间 8/9，名单 3/9，明示逻辑 9/12，元数据选择 7/10。
程序控制与真实模型回答分开。无人工逐题 Gold、无 LLM judge、无付费 API、无训练或 heldout 推理。

请特别注意：六个有图任务有五个 inside、一个 outside，模型全答 inside；
六个有名单任务 watched 全答 true。两个事后简单程序仅看证据是否存在，就能得到相同的值预测。
这不是内部推理机制的证据，也不能用来夸大模型已经具备空间或名单读取能力。

原计划 4 个一卡 worker，每片 10 次。提交器在 STARTING replica 计数上发生一次停止，
修正后仅提交剩余三片。第一片已先结束，实际最大并发为 3；四个作业均 SUCCEEDED 并释放。
完整初始失败、五项资源回归测试、续提交命令和平台记录均保留。

## 文件导航

| 文件/目录 | 审阅内容 |
| --- | --- |
| `EXECUTION.json` | 冻结哈希、设置、预算、有效窗口和代码绑定 |
| `REQUEST_PLAN.json` | 40 个模型任务、无历史策略、四片固定分配 |
| `references.json` | 仅评估程序读取的自动参考 |
| `source/src/disastertrace/multimodal_atomic_v1/` | 任务、参考、解析评分、适配器、采集、审计和 worker |
| `seed/public/requests/` | 用于构造投影任务的原始公开数据；非全部都发给模型 |
| `seed/private/geometry_lineage.json` | 参考计算所用几何；不在模型输入中 |
| `AUTOMATIC_CONTROLS.json` | 调用前完成的独立程序核对；不是模型分数 |
| `gpu_runs/*/live/*/` | 每次实际请求、prompt、图像、处理器哈希、意图、raw 与 token |
| `REPORT.json` / `ERROR_ANALYSIS.json` | 主评分和逐字段错误 |
| `POSTHOC_PRESENCE_CONTROLS.json` | 观察后补充的证据存在性程序对照，明确标为 posthoc |
| `input_replay_01/VERIFIED.json` | 40 个实际输入/输出重放及 6 个像素检查 |
| `CPU_REVIEW_RESULT.json` | 搬迁后的请求、参考、控制与报告重建 |
| `RESOURCE_ACCOUNTING.json` / `acp/` / `acp_continuation_02/` | 真实 GPU 作业与计数故障恢复 |
| `TESTS_02.xml` / `TESTS_CONTRACT_03.xml` / `RESOURCE_TESTS_02.xml` | 96 个不同功能节点与另 5 个资源回归节点 |

`source` 是冻结的科学执行代码。根目录后加的归档、描述性分析脚本有独立文件记录，
不得误认为它们在模型调用前已经冻结。`POSTHOC_PRESENCE_CONTROLS.json` 是事后分析，
旧 MM-3 的输出不在本批当作新样本。先看 `EXECUTION.json.bound_files` 判断预先绑定范围。

模型没有使用工具。worker 每次只将该任务的公开消息和实际 PNG 附件传给处理器，
没有将全部计划、Gold、几何或其他任务答案放入上下文。逻辑题的事实是显式特权诊断输入，
不计作视觉读取成功。版本题只含元数据，整个名单的来源选择与逐地点 WATCH 行引用的语义不同。

## 请重点检查的问题

1. 测量是否有效：空间 8/9 与名单值 6/9 是否被类别不平衡和证据存在性模式解释；
   报告是否充分区分引用正确、结构正确、地点覆盖和实际任务成功。
2. 任务与参考是否一致：尤其 watch-01 的 C 缺失、false AND null、边界/unknown 空间真值、
   同一有效时间的版本规则和旧图重放；是否存在静态投影改变任务定义却未声明的问题。
3. 输入是否泄漏：检查 GPU 捕获的真实 prompt/public_text 和图像，而不是只读模板；
   查明模型是否可能见到参考值或未来地点。静态任务明示 C 与轨迹提前泄漏 C 必须区别。
4. 采集与审计是否保持固定分母、独立空历史、无重试和完整失败记录；资源故障恢复是否只
   继续三个从未提交的 worker，是否错误地声称四卡并发或四倍速度。
5. 新计划是否合理：显式字段/行号文本与 JSON 的对照能否保证同信息、同输出说明、
   同模型预算；是否应先补平衡空间样本，再扩大模型或完整轨迹。
6. 当前自动化验证还有哪些缺口；请给出按严重程度排序的具体问题、文件引用、
   可复现例子与最小修复建议。不要假设存在人工审核、训练数据污染结论或未运行的额外评测。

## 无 GPU 的独立复查

复查 ZIP 解压后包含 `batch/` 与 `REVIEW_MANIFEST.json`。下列命令只重建公开任务、
参考和报告，不推理、不访问 API、不需要模型权重；输出目录必须在解压位置，且 receipt 文件不存在。

```bash
PYTHONDONTWRITEBYTECODE=1 python batch/review_cpu.py \
  --bundle . --receipt REVIEW_LOCAL.json
```

需要 Python 3.10+ 及项目 CPU 依赖；本机已验证的 CPU 环境使用 NumPy 2.2.6、Pillow 11.3.0、
Pydantic 2.13.5、Shapely 2.1.1、pyproj 3.7.1、pyshp 2.3.1。输入张量重放另外需要固定的
Transformers/Torch 环境和本地模型处理器文件；它与此处不依赖权重的评分重建是两个验证层级。

不要运行 `prepare_offline.py`、`freeze.py`、`submit_jobs.py`、`continue_submission_02.py`、
任何 GPU worker、`finalize.py` 或 `seal.py` 来复查旧批次；它们是已消费的一次性执行入口。
副本和 ZIP 解压后的 CPU 重建已经实际执行。最新归档接受记录位于原始批次的 `COMPLETED.json`；
该文件在 ZIP 创建后写入，因此不属于 ZIP 内部内容，避免自引用哈希。
