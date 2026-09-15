# v11 审查包

基准 `889620a4fc4ee6ad70757dd3e832a40c7509126a`。
先读 `CODEX_START_PROMPT_CN.txt` 和 `CODEX_NEXT_PLAN_CN.md`，再按问题查看 `FINDINGS.json`、`REVIEW_SCOPE.json`、`review_results.json`。

离线检查运行：
```bash
python3 -B review_checks.py --result my_new_result.json
```
结果路径必须全新。只需Python3.10+标准库；没有网络/模型调用，不需要旧复查ZIP，不修改用户仓库。

8份源码完整字节已按本次GitHub返回的blob SHA验证。测试使用模拟HTTP/时钟/spool依赖，校准银行仅运行原AST验证函数；不是全套项目或完整天气日志重放。41个情形中5个是故意复现边界，不能把其check_satisfied解释为功能合格。

本包不包含完整私有仓库、天气数组、模型权重、任何凭据或750项测试运行结果。进行中作业的状态以用户本机新的回执为准；本文件不创建新资源授权。
