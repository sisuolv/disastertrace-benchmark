# MM-0 至 MM-2 执行清单

日期：2026-09-09。依据：INTEGRATED_PLAN_CN.md；用户已要求依次执行。

本批结束点是一个真实 NHC 开发事件的可自动复算离线任务包。模型生成、付费 API、
GPU、训练和 heldout 推理均不在本批执行清单中。下一批视觉模型预检另建运行身份。

1. MM-0：核验旧补充包 572 个文件，保存旧源码/测试快照哈希；单列旧发布交接状态；
   新增逐轨迹提交账本，先写故障隔离和恢复回归测试，再实现。
2. MM-1：新建 CPU 环境；抓取两个官方目录和四个指定 Francine 候选 ZIP；复用本地
   005/007 文字原件；检查实际图层、绝对有效时间、阈值、坐标系与几何，不静默修复。
3. MM-2：编译受控回放的真实图文 episode 及缺证/延迟/重放分支；自动参考、完整状态、
   局部义务、公开像素程序对照、错误程序、固定分母评分与独立 CPU 复算。
4. 保存初始失败、命令和返回码，检查旧哈希不变，生成验收报告和 MM-3 预检清单。

新目录：`disastertrace-starter/src/disastertrace/multimodal_v1/`；
批次证据：`disastertrace-starter/artifacts/multimodal_v1/mm0_2_20260909/`。

旧发布交接独立记录在 BASELINE.json：补充证据已完成，最终阅读包和 push 收据尚未存在。
本批不重新封存或启动旧作业。实际新状态记录在本批 IMPLEMENTATION_STATUS.md，
历史 IMPLEMENTATION_STATUS.md 与已绑定的 P6-P14 说明保留原字节。

下载上限：累计 512 MiB、单文件 256 MiB、最多并发 2、每地址最多 3 次尝试；包括失败
收到的字节。权重不下载。相同事件及派生产品继承开发分组，拒绝 heldout 事件。

真实来源不足时给出 NEEDS_REAL_SOURCE_VALIDATION，软件检查与真实准入分别报告。
