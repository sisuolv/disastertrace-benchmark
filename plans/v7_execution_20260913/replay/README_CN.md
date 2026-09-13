# v7 固定证据实验：CPU 离线复现包

本包用冻结的可见证据、统计映射、模型请求和保存的响应重新计算 E 判断及 Brier。整个复现过程不重新调用模型、不需要 GPU、不请求网络，也不需要原工程目录或模型权重。

## 内容与边界

- `matrix/`：BANK、144 个固定证据 bundle、注册表和原始程序预测；政策视图不含未来结果标签。
- `evaluator/`：48 个开发机会的结果及其原始结果表，独立放置；只在评分阶段读取。
- `batches/`：每轮原始 PLAN、冻结源码、policy bundle、每次请求/响应、token IDs 和完成记录。原始 PLAN 保持字节不变，包括其中作为历史来源记录的绝对路径；复现器使用显式移植映射。
- `tokenizer/`：用于可选完整 token 核验的分词器、chat template、配置和许可；不包含模型权重。
- `PACKAGE_MANIFEST.json`：所有打包输入的 SHA256。注册的各轮实验都应完整纳入，不能只选表现较好的输出。

默认标准库复现核对整个打包文件清单、冻结 bundle/asset hash、权限/截止合同、消息重建及 hash、请求/响应绑定、整数 token IDs 与长度、EOS、逐工作进程 token 总数、原始统计映射预测、E 判断，以及完整公共结果掩膜下的 Brier。无效 F 输出回退到共同基线，不能按方法删题。E-only 条件没有模型 F 分数。

这份包复现的是冻结快照实验。历史原始数据的获取/解析管道和历史首次可用时间没有因此重新得到证明；旧 `INPUT_BINDINGS.json` 中的未打包上游路径仅作为来源记录。实验只有 48 个已经曝光的开发机会、2 个正例，重复提示词/证据条件不会增加独立天气过程数量。

## 标准库运行

解压后进入包目录，以 Python 3.10 或更新版本运行：

```bash
python -I run_replay.py --output replay_result
```

`replay_result` 必须是新目录，避免覆盖旧结果。该模式核验 token 数量与保存记录的内部一致性；它不会声称标准库已经完成分词器重编码或 token 到原始文本的解码。

已安装 Transformers/Tokenizers 的 CPU 环境可进行完整 token 核验：

```bash
python -I run_replay.py --full-tokens --output replay_with_tokens
```

该模式只加载包内分词器，并逐调用重建 chat template、核对输入 IDs、解码输出 IDs；HF 离线模式开启。它仍不加载模型权重。

## 移址与访问阻断验证

将整个包复制到原工程之外，例如 `/tmp`，然后运行：

```bash
python -I run_replay.py --guard-original-paths-and-network --output isolated_result
```

守卫使用 Python audit hook，拒绝原工程/模型路径访问、socket 创建/连接以及子进程。复现开始时会主动尝试两次原路径读取和一次 socket 创建，确认被拒绝后才执行评分。这是对该 Python 复现程序的运行检验，不是操作系统级沙箱或对任意恶意原生代码的隔离证明。当前 CCI 的 `unshare -n` 不被允许，该限制应在执行记录中保留。

结果中的 `captured_original_model_calls` 是保存的原始推理次数，`new_model_calls` 始终为零。最终包括哪些完整批次、各批次多少次调用，以 `REGISTRY.json` 和复现输出 `REPORT.json` 为准。
