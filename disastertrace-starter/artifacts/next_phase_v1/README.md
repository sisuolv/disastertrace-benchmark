# T0–T5 离线交付与验收记录

当前说明：[README_NEXT_PHASE_V1.md](../../README_NEXT_PHASE_V1.md)。本目录保存本阶段代码与离线结果的可复查记录，不含新增真实模型响应。

## 已实际运行

| 验证 | 结果 |
| --- | --- |
| 首轮完整离线验收 `acceptance_001` | 931 项测试通过，127.10 秒；全部构建、演练和验证步骤退出 0 |
| 增补报告后的完整验收 `acceptance_002` | 949 项测试通过，131.14 秒，零 skips；全部 11 步退出 0 |
| 时间、费用和采集/报告专项 | 35 项测试通过，49.05 秒 |
| 实际 AFS 上的存储专项 | 12 项测试通过，1.71 秒 |
| 最终新代码检查 | Ruff E/F/I、28 文件格式检查及 pip check 均通过 |
| 历史保护 | 1,616 个既有源码、测试、资料和实验文件逐字节不变 |

全套验收后，只把报告中一条过长的字符串字面量拆行；Python AST 和运行时文本相同，证据见 [format_equivalence.json](root_checks/format_equivalence.json)。`acceptance_003` 使用最终源码重新生成并核验全部数据包，显式跳过已经运行的测试；其 `tests_requested=false` 不表示又通过了一遍测试。以 [validation/status.json](validation/status.json) 中的实际退出码和最终身份为准。

本机的完整最终运行目录是 `work/next-phase-acceptance-003/`。各步骤的精确命令、退出码、用时、日志 SHA256 复制至 `validation/acceptance_*/commands.json`，对应日志保留原文。`root_checks/` 也保留之前的失败记录，包括 tests-first 缺模块、AFS 锁释放问题和格式检查失败；这些不算成功测试。

## 可交给其他审阅者的材料

- [offline_package_v1.tar.gz](offline_package_v1.tar.gz)：冻结 build、校准准备、执行包、270 槽诊断 journal、实际输入/评分投影、报告、P2 数据包，以及源码、测试、文档、资料和验证记录快照。
- [archive_manifest.json](archive_manifest.json)：归档 SHA256 和逐文件 SHA256，用于核验内容完整性。
- [verification.json](verification.json)：实际重新读取归档内容后的校验结果及历史保护结果。
- [validation/status.json](validation/status.json)：最终包身份、各次验收是否实际运行测试、核心计数及零模型调用记录。
- [validation/environment.json](validation/environment.json)：实际 Python、导入路径及安装版本；[依赖版本](validation/requirements-installed.txt)作为环境快照。
- [baseline/protected_files.json](baseline/protected_files.json)：本轮保护的全部 1,616 个历史文件 hash。

归档用于保留本阶段冻结内容，配合 `a23f73a` 审查仓库使用；它不重复打包所有历史实验依赖。部分旧 manifest 绑定绝对路径和环境。移交后应在完整仓库中使用 `scripts/reproduce_next_phase.py` 生成新身份，不改写这些历史路径来冒充原运行。

归档中的模型回答全部是程序诊断。诊断成本是模拟，不能算新增消费；`selected_output_tokens=null`。P2 数据包标为 `P2_OFFLINE_READY`、`live_ready=false`，不具备真实模型采集来源证明。最新真实成绩仍来自历史 P1，未知 attempt 79 仍未解决。

## 重新验证文件完整性

从项目目录执行：

```bash
.venv/bin/python artifacts/next_phase_v1/assemble_delivery.py --verify-only
```

该命令只读归档与保护清单，不启动模型或解压覆盖现有目录。它重新计算每个归档成员和整个归档的 hash，并检查本 worktree 的历史保护文件。源码、数据语义和采集审计的可执行复现入口仍是 [主脚本](../../scripts/reproduce_next_phase.py)。

GitHub Actions 工作流已添加到开发分支；本目录没有声称远端 CI 已运行。新提交或推送的状态以实际 Git 记录为准。
