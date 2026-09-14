# DisasterTrace v10 代码、结果与复查材料

本次发布对应 `plans/v10_execution_20260914_01`，以 2026-09-14 的六份 v9 复查包为输入。
研究方向保持 C1/C2/C3 与 16 灾种路线；本轮实际实验主要是低能见度和温度。

阅读顺序：

1. 根目录 `LATEST_PROGRESS_V10_CN.md`：本轮实际完成情况与结论限制。
2. 执行目录 `OVERALL_PLAN_UPDATED_CN.md`：整体路线和下一阶段出口。
   具体工作包见同目录 `NEXT_PHASE_PLAN_CN.md`。
3. 执行目录 `FINAL_RESULT.json`：完整计数、失败和未决项。
4. 本目录 `REVIEW_FOR_CHATGPT_PRO_CN.md`：建议复查问题。
5. 本目录 `EXPORT_MANIFEST.json`：逐文件哈希及明确省略的内容。

代码与阅读材料包不包含模型权重、安装环境、凭据和所有大体积原生档案。
会话的完整检查点也没有全部进入 Git。不能将阅读 ZIP 称为所有实验的完整重建包。

另外提供两种可以在 CPU 上离线复算的有限完整包：

- `portable_capsule_01`：部分旧真实 E/F、Denver 和一个完整温度月，包含对应完整日志。
- `portable_model_capsule_01`：全部 212 个原始 235B 固定输入任务、请求、回答、数值银行和评分器；
  两条无效回答保留。可以重算全部评分，不需要模型或 API。该包不重新生成模型回答。

两个包均另有真实 CPU 节点搬迁回执，原工作区读取和网络访问在验证器中被禁止。
Python 审计钩子的用途是发现意外依赖，不是抵御任意恶意代码的安全沙箱。

复算时进入相应 capsule 目录，使用 Python 3.10 以上版本和全新的结果路径：

```bash
python3 -B verify.py --capsule . --result ../my-replay-result.json
```

不需要安装第三方包、连接 API 或加载模型权重。模型包会同时生成 `_rescored` 目录，
保留原有失败回答并逐文件比较分数。请不要将这个离线评分命令替换成历史模型启动器。

发布使用独立 Git 数据库，以原私有仓库 `sisuolv/disastertrace-benchmark` 的
`next-phase-v1` 为父提交，不改仓库可见性，不改开发 worktree 的 HEAD、索引或旧实验。
原发布包、失败记录、已消费启动器和留存确认周继续保留。请不要运行历史模型启动器。
