# 本次实际重跑范围

此目录是本回答重跑附件局部探针的回执，不是作者原始实验，也不是已修复源码。
28观察=22正常/保护行为+6反例观察，另有2个恢复案例和配对身份/3项缺失界算术控制。各套覆盖有交叠，不能相加为全仓库测试数。

原始工作目录记录在VALIDATION_SUMMARY，下载后路径需以此目录为根定位。复算命令：
```bash
python network_blocked_runner.py boundary_suite/review_checks.py
python network_blocked_runner.py recovery_and_pair/probe_recovery.py
python network_blocked_runner.py recovery_and_pair/probe_pair_provenance.py
```
这会在当前副本写新结果，应先复制此目录再运行以保留下载的回执。Python网络审计钩子是额外保护，不是操作系统级沙箱。脚本自带假transport/clock/spool/合成结果，不接触真实凭据或天气资产。

退出0意味着观察复现（含缺陷），不是修复验证。真实模块/并发文件系统/原AFS数据/628全测试/840轨迹/288请求仍需工作区独立验证。
