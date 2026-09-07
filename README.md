# DisasterTrace：LLM 极端天气证据推理评测审查包

这是供独立代码与研究设计审查使用的项目快照。当前已完成一轮 DeepSeek 开发集比较，以及下一轮输出规范 / token 预算校准的离线准备。

**请先阅读 [REVIEW_FOR_CHATGPT_PRO.md](disastertrace-starter/REVIEW_FOR_CHATGPT_PRO.md)。** 这份中文文档不依赖聊天上下文，说明研究目标、数据、方法、真实结果、限制、复查问题和下一步工作。

## 当前事实

| 项目 | 状态 |
| --- | --- |
| 真实动态任务资料 | 10 个准入风暴，3 个开发、7 个留出；尚无留出集模型结果 |
| P1 模型实验 | DeepSeek，三种方法，90 个响应 / 91 次请求尝试；包含一次已记录的中断续跑 |
| P1 主要结果 | 已知字段及证据正确：snapshot 39/96，structured_state 96/96，answer_history 76/96 |
| 下一轮校准 | 原规范 / 4096、明确规范 / 4096、明确规范 / 8192，共 270 次拟执行请求，尚未运行 |
| 离线程序验证 | 上传副本在新环境下再次通过 684 项测试（57.41 秒）；历史校准包另有 6,979 项独立审计检查。不是新增模型成绩 |
| 人工与模型判分 | 不新增逐题人工标注或主观复核，不使用 LLM judge 作为主评分器 |

三种方法都看到当前已交付的累计证据。当前结果不证明因果记忆优势，也不能代表一般极端天气预测或真实应急决策能力。P1 中有 20 个输出上限失败、2 个结构错误，相关回答均保留在分母里。

## 阅读入口

- [详细审查说明与八个重点问题](disastertrace-starter/REVIEW_FOR_CHATGPT_PRO.md)
- [当前实现状态](disastertrace-starter/IMPLEMENTATION_STATUS.md)
- [P1 真实实验报告](disastertrace-starter/work/p1-deepseek-background-continuation-v1/report/REPORT.md)
- [输出规范与校准协议](disastertrace-starter/docs/CALIBRATION_PROTOCOL_V1.md)
- [核心实现](disastertrace-starter/src/disastertrace/automated/) 与 [测试](disastertrace-starter/tests/)
- [资料快照说明](REFERENCE_BUNDLE.md) 与 [第三方来源和许可](disastertrace-starter/THIRD_PARTY_NOTICES.md)
- [导出文件清单](EXPORT_MANIFEST.json) 与 [审查包说明](REVIEW_PACKAGE.md)
- [本次新环境验证记录](handoff_validation/README.md) 与 [独立交付检查](handoff_audit/review_result.json)

## 目录结构

```text
disastertrace-starter/       原项目代码、测试、文档、配置与已保存实验资料
references/                 构建和测试使用的精简原始资料快照
handoff_audit/               本次交付的检查与实际执行记录
handoff_validation/          新环境依赖、完整测试和离线重建执行记录
INTEGRATED_BENCHMARK_PLAN.md  整体研究计划；较早进度文字以当前状态文档为准
```

`work/` 和 `artifacts/` 中的旧结果是历史证据，包括失败记录。部分旧 manifest 含原机器的绝对路径；不应改写它们以伪装成可移植的新实验。换环境后请使用新的输出路径构建和验证。

## 安装与离线验证

建议使用 Python 3.10 或更新版本。以下命令从仓库根目录开始，项目的 `../references/` 布局已保留。

```bash
cd disastertrace-starter
python3 -m venv .venv
.venv/bin/python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -e '.[dev]'
.venv/bin/python -m pytest tests -o addopts= -q
```

镜像暂不可用时可改用官方 PyPI。只运行 `tests/`：历史 `artifacts/` 中还保存了其他版本的独立测试，不应把这些归档测试自动混成同一次测试执行。`requirements-verified.txt` 记录了开发环境的一份依赖快照；它不构成所有 Python 版本的安装兼容保证。

Ubuntu / Debian 如果提示缺少 `ensurepip`，需要先安装与 Python 版本对应的 `python3-venv` 系统包。本次已在全新 Python 3.10 环境中完成依赖安装和全部测试，具体版本保存在 [依赖快照](handoff_validation/requirements-installed.txt)。

用本包资料重新构建并进行零模型调用的校准准备：

```bash
.venv/bin/disastertrace-auto build \
  --references ../references \
  --nhc-snapshot ../references/nhc_cohort_v1 \
  --output work/review-build-001

.venv/bin/python -m disastertrace.automated.calibration prepare \
  --build work/review-build-001 \
  --provider-config artifacts/p1_deepseek_development/provider.json \
  --output work/review-calibration-001

.venv/bin/python -m disastertrace.automated.calibration verify \
  --output work/review-calibration-001
```

输出目录必须不存在。54 个初始请求不会发送，1,080 个诊断回答来自程序；这些命令不读取模型凭据。不要以为此准备包已经实现新的真实采集器，或已授权 270 次付费请求。历史配置也不是启动旧批次的授权。

本次已实际执行这三个命令，全部成功，验证了 128 个校准文件、54 个未发送请求和 1,080 个程序诊断回答。新输出目录不纳入版本控制，执行日志单独保存在 `handoff_validation/`；新构建的 ID 与历史归档不同，符合来源路径变化的预期。

## 给审阅者的任务

请以代码和记录为依据，优先列出会改变研究结论的问题，并给出文件位置、影响、修正方式和验收标准。重点关注时间语义、可见证据与 Gold 隔离、格式 / 预算混杂、固定分母、证据支持规则、状态传递、测试代表性和下一阶段任务设计。

代码审查与研究设计建议不属于对 benchmark 样本新增主观判分。请不要启动任何模型调用，也不要把离线诊断结果或计划功能描述为真实模型实验结果。

本次私有 GitHub 审查快照由项目所有者明确授权。子目录 `AGENTS.md` 中保留的是历史阶段约束；本次导出授权不改变其中的模型实验范围，也不代表授权公开发布资料。
