# CPU 可移植复现完成记录

已将本轮三批真实 GPU 捕获整理为独立 CPU 复现包。包内包含冻结核心源码、144 个原始可见证据 bundle、BANK、原始程序预测、720 次请求/响应及 token IDs，以及单独保存的 evaluator 结果。没有模型权重，也不依赖原工程目录。

| 原始实验 | 保存调用数 | E 正确 | 适用 F 评分的调用数 |
| --- | ---: | ---: | ---: |
| `fixed_matrix_01` | 144 | 93 | 144 |
| `prompt_probe_01` | 288 | 99 | 288 |
| `fact_truth_probe_01` | 288 | 241 | 144 |
| 合计 | 720 | 433 | 576 |

这些仍然是 48 个已曝光开发机会、2 个正例。不同提示词和证据条件重复使用机会，不能据此增加独立样本数。E-only 的 144 次调用没有模型 F 分数。

## 实际完成的检验

1. 标准库 `python -I` 重放：核对全部 2,426 个打包输入文件，重建证据合同、消息、统计映射、E 状态和适用的 Brier；所有方法使用完整共同结果掩膜，失败 F 输出保留共同基线。
2. 将完整包移至 `/tmp`，拒绝原工程/模型路径读取、socket 和子进程后，标准库重放通过。策略模块从包内冻结 `source/` 导入，后续现行核心修订不会影响它。
3. 使用现有 CPU Python 环境，仅加载包内 tokenizer，再逐调用重建 chat template、重编码输入 IDs、解码输出 IDs。720 次全部通过；输入 token 1,916,920、输出 token 13,295，合计 1,930,215。
4. 标准库、本地完整 token 和移址结果逐行一致。与三份原始 GPU verifier 的 7,056 个字段、72 个 Brier 单元交叉核对一致。
5. 在可丢弃副本中执行四个负向用例：修改响应原文、修改输入 token 数、将 cutoff 移至物理支持开始时刻、删除一条捕获。四个用例全部被拒绝，真实包没有被修改。

## 隔离与复现的实际边界

CCI 不允许创建网络命名空间；`unshare -n true` 实测返回 `Operation not permitted`。移址验证采用 Python audit hook，先主动测试原工程/模型路径读取与 socket 创建被拒绝，再运行完整评分。这证明了本复现程序在该守卫下可运行，不能表述为操作系统级沙箱或对任意恶意原生代码的隔离保证。

标准库模式完成 token 计数与保存记录一致性检查；完整 token 模式额外依赖现有 Transformers/Tokenizers 环境，完成真正的编码和解码。两种验证明确区分。所有复现运行新增模型调用均为 0，未调用 GPU 或网络数据接口。

本包从已冻结的可见 bundle 开始，没有重建全部原始数据清洗，也没有重新验证历史首次可用时刻。原始 `INPUT_BINDINGS.json` 中未打包的上游引用保留为来源记录。原来的历史可用时间假设、少量正例、提示词敏感性及非独立过程限制继续有效。

## 主要文件

- `package_01/README_CN.md`：独立包的执行方法。
- `result_stdlib_01/REPORT.json`：标准库重放结果。
- `result_guard_full_tokens_01/REPORT.json`：移址、访问阻断及完整 token 结果。
- `ORIGINAL_VERIFIER_CROSSCHECK.json`：与原始三份 verifier 的交叉核对。
- `negative_checks_01/REPORT.json`：四项篡改/缺失/时间约束测试。
- `ZIP_MANIFEST.json`：最终 ZIP 的 SHA256、长度及导出核验记录。

`captured_original_model_calls=720` 表示被复现的原始真实调用，`new_model_calls=0` 表示这次 CPU 重放没有产生新的推理。不能将 CPU 重放再次计入实验调用数或天气样本数。
