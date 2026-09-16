# v13 代码、计划与进行中结果快照

从仓库根目录 `LATEST_PROGRESS_V13_CN.md` 开始，再读本目录的 `REVIEW_FOR_CHATGPT_PRO_CN.md`。`PROGRESS_SNAPSHOT.json` 记录本次导出实际观察到的进度和时间；GitHub 上的快照不会随服务器后台任务自动更新。

本次整理当前源码与测试、v13 总计划、A00-A06 完成回执、历史影响核查、B00/C00/M00 的已有记录、B02 强程序设计与回归结果、C01 资格缺口，以及 M01 模型对照执行器和资源排队状态。不同批次的历史状态保留原样，不能把旧文档中的“下一步未启动”当成最新状态。

`DisasterTrace_v13_progress_and_code.zip` 是适合交给 ChatGPT Pro 的代码与证据阅读包。`EXPORT_MANIFEST.json` 列出逐文件 SHA256、观察时间和范围。年度原始报文、完整运行 journal/checkpoint、模型权重、API/SSH 凭据和未读确认集不包含在内，因此它不是完整科学实验重放包。执行脚本中的绝对 AFS 路径和旧 claim 属于原执行身份，不能直接重启这些 launcher。

为支持有限离线测试，附带此前已反复用于工程测试的 `regional_01` 七个处理后输入文件；没有包含其 private 结果或新确认周。初次导出遗漏这些夹具，产生 24 passed / 4 skipped，因而没有放行推送；`EXPORT_TESTS_ATTEMPT_01.xml/log` 与 `FIXTURE_AMENDMENT.json` 保留该记录。补入原文件后重新建立独立导出目录并验证，不更改原测试或实验代码。

在已有兼容 Python 依赖的环境，从解压后的根目录执行以下有限检查，不会启动真实模型或云任务：

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=disastertrace-starter/src:disastertrace-starter/tests \
python -m pytest -q -p no:cacheprovider \
  plans/v13_selector_execution_20260916_01/test_model_run.py \
  plans/v13_selector_execution_20260916_01/test_wait_submit.py
```

导出在独立 Git 对象库中叠加到远端 `next-phase-v1`，不改开发仓库的 HEAD/index、不覆盖历史结果，不强推。先核验选中内容与 ZIP，再验证导出源码及有限离线测试，推送后从独立对象库读回核对。没有声称 GitHub Actions 已运行。

这次发布不新增天气下载、拟合、确认实验或被测模型请求；已授权的后台任务自行继续。运行中材料按逐文件读取形成带时间的观察，不冒充跨进程的原子终态快照。
