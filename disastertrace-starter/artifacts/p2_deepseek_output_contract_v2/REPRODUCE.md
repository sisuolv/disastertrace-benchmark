# 无 API 复查与复现

以下命令在本项目 `disastertrace-starter` 目录执行。历史数据、真实采集结果和
冻结源码均保留原样；命令不启动模型请求，也不需要凭据。

查看后台状态：

```bash
.venv/bin/python artifacts/p2_deepseek_output_contract_v2/runner.py status
```

本轮完成或停止并生成报告后，可在新的检查目录重新验证全部结果：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python artifacts/p2_deepseek_output_contract_v2/finalize.py --output work/p2-v2-independent-review-001
```

`finalize.py` 会自动禁用外网、清除子进程的凭据变量、使用冻结源码，先重建报告，
再核对错误清单、格式清单、结果表和历史对照。已有结果只做重建比较，不覆盖；
检查输出目录也必须是新的。最后复查准备阶段记录的 3,116 个历史/源码文件。
首次实际检查的九个成功子命令记录在 `validation/finalization_001/`，但会话结束
时保全结束记录尚未生成，外层退出码未知。最终收尾在独立的
`validation/finalization_002/` 完成：五个重建验证命令与外层进程均 exit 0，
3,116 个历史/源码文件未变化。两次目录都保留，未重新采集模型响应。

单独核验本轮 report：

```bash
PYTHONDONTWRITEBYTECODE=1 DISASTERTRACE_OFFLINE=1 PYTHONPATH=scripts/offline_guard:artifacts/p2_deepseek_output_contract_v2/execution/dataset/implementation_source/src .venv/bin/python -m disastertrace.controlled.live verify-report --execution artifacts/p2_deepseek_output_contract_v2/execution --run work/p2-deepseek-output-contract-v2 --output artifacts/p2_deepseek_output_contract_v2/runtime/report
```

单独核验历史描述性对照：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python artifacts/p2_deepseek_output_contract_v2/compare_historical.py --old-bundle artifacts/p2_deepseek_development_v1 --output artifacts/p2_deepseek_output_contract_v2/runtime/historical_comparison.json --verify
```

该命令分别在独立子进程中导入各自的冻结源码，重建各自报告，再比较固定分母。
不同版本不能在同一个 Python 进程里混用核心模块。

启动器与历史比较的单元测试：

```bash
PYTHONDONTWRITEBYTECODE=1 DISASTERTRACE_OFFLINE=1 PYTHONPATH=scripts/offline_guard:src .venv/bin/python -m pytest artifacts/p2_deepseek_output_contract_v2/test_runner.py artifacts/p2_deepseek_output_contract_v2/test_compare_historical.py -q -o addopts= -p no:cacheprovider
```

这 19 项是本轮新增启动/对照检查；此前 1,074 项核心测试和 9 项离线候选比较测试
属于上一阶段的记录，不能声称本轮再次运行了整套核心测试。

完整重建需要记录中的 Python/依赖版本、原始绝对运行路径和 registry claim。
当前 archive 用于静态代码/数据复查和保全原始字节，未承诺任意目录解压后即可
绕过这些执行约束。全历史保护检查还依赖原工作区中的历史文件集合；结果包不是
整个工作区的完整副本。`runner.py verify` 还检查当前价格证明的新鲜度，可能在 24 小时
后拒绝；历史报告验证按实际发送时间检查价格证据，不需要为复查刷新历史证明。

不要再次执行 `launch`、`worker` 或 `diagnostic`，不要重置 claim，也不要为了复现
覆盖已保存的日志、授权、Gold 或模型响应。
