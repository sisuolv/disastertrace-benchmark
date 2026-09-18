# DisasterTrace v10 审阅与后续计划包

固定提交：`1fd6821fef15b26898a57c74d4715714f33ea779`。

先读 `AUDIT_REPORT_CN.md`；实施按 `CODEX_NEXT_PLAN_CN.md` / `WORK_PACKAGES.json`；简短入口 `START_HERE_CN.md`。

此包是本轮新生成的审阅产物，不是仓库发布的74MB阅读ZIP，也不是仓库两个完整capsule。没有模型权重、凭据或全部原生数据。`source/`只有八个Git blob已核验文件，不能作为完整包安装或覆盖生产。

## 复现本次局部测试

```bash
python3 -B tests/test_review.py
```

需要Python3.10+，无第三方依赖。测试从八个完整源文件加载模块或AST函数；没有原生航空解析器、FormalSession或云作业。审阅的是未修复版本，**预期35项、31通过、4失败、exit=1**。这些红项不是仓库720项中出现失败。

结果写入 `results/LOCAL_VALIDATION.json` 和 `results/local_tests.log`，测试源码包含SHA核验。重跑会更新此包内的测试日志；发布清单记录的是交付时版本，文件变化应另立运行目录。`COUNTEREXAMPLES.json`中的NaN输入用说明字符串序列化，真正NaN反例由测试脚本构造。

工作包和验收条件全部是建议任务，未在远端执行。不得自动使用旧运行授权或启动已消费的模型launcher。
