# DisasterTrace Codex 交接包

## 内容

- `DISASTERTRACE_CODEX_PLAN.md`：主实施计划，21 个任务、48 组行为验收场景。
- `AGENTS.md`：仓库级编码指令，默认完成离线 M1，默认不调用付费模型。
- `docs/STARTER_AUDIT.md`：原 starter 的实际测试和缺陷核查。
- `audit_artifacts/`：审计探针、原始结果和原文件哈希清单。
- 其余代码、示例、测试和 README：从原始 `disastertrace-starter.zip` 原样复制。

本包没有替 Codex 实施计划中的新功能，也没有修复 starter 的已知缺陷。
`run/score/report` 等新命令要依照计划开发后才能执行。

## 使用

在解压后含 `pyproject.toml` 的项目目录中打开 Codex，把以下内容作为任务：

```text
请读取 DISASTERTRACE_CODEX_PLAN.md 和 AGENTS.md，从 DT-00 开始。
先复现审计问题，再按依赖完成 M1 离线端到端闭环。
不要重写整个仓库，不要仅生成另一份计划。
默认不调用付费模型，不伪造真实数据或人工审核。
每项完成后执行相关测试，更新 IMPLEMENTATION_STATUS.md，记录真实结果与阻塞。
```

只有 Markdown 文件时，将其放入已有 starter 项目根目录即可；它本身包含所需接口、
任务依赖、测试、外部来源和完成定义。已有 AGENTS.md 时合并，不直接覆盖。

## 当前可用的基线检查

在已满足依赖的环境、项目根目录中：

```bash
PYTHONPATH=src python -m pytest -q
PYTHONPATH=src python -m disastertrace.cli validate-episode examples/episode.json
```

本次审计为 6 tests passed；这不等于计划中的新功能已完成。
