# v8 复查整合：整体路线与下一批计划

已读取六个 ZIP 和一份 Markdown，核验六包内部 100 个文件，并对照当前代码和实际数据/实验记录。
30 个 monitoring 源文件与已上传的 `6c7c7e8` 一致。研究继续采用 v7 的 C1/C2/C3、16 类灾害和 X00-X09。

阅读顺序：

1. [整体后续计划](OVERALL_PLAN_CN.md)：方向、novelty、合同、实验、阶段与发布门槛。
2. [下一批具体执行](NEXT_BATCH_CN.md)：CPU 测量加固、历史影响审计、验收及接续步骤。
3. [数据与 16 类灾害路线](DATA_AND_HAZARD_ROADMAP_CN.md)：每类来源、近期优先级和可用性边界。
4. [机器工作包](WORK_PACKAGES.json)：统一依赖、旧 CP/X 映射、交付和门槛。
5. [当前代码审计](analysis/CURRENT_CODE_AUDIT_CN.md)、[A/B/C 裁决](analysis/REVIEW_ABC_CN.md)、[D/E/F 裁决](analysis/REVIEW_DEF_CN.md)。

本轮新增核验包括：22 项当前模块边界测试（17 通过、5 失败）、8 组独立 CPU 探针、
21 项既有 typed/TAF 测试通过，以及新 432 机会日历的 TAF 元数据筛查（0 个风险标记）。
这些范围不能合并成一个“通过率”，也不是新的天气模型成绩。元数据筛查不能替代原文/评分影响审计。

总体调整是先修版本、时钟、失败事务、结果和比较合同，再完成全日历程序及公平机制实验。
CP04b 必须完成，但不阻塞所有离线诊断；D/MM、前瞻与完整 16 类按独立门槛推进。
本轮只做规划与定向核验，没有修复科学代码、修改历史结果或新增模型/GPU/网络调用。

交付结构与核验范围见 [PLAN_VALIDATION.json](PLAN_VALIDATION.json)，文件绑定见 [MANIFEST.json](MANIFEST.json)。
边界测试的 5 项失败仍保留，计划结构通过不表示这些问题已修复。例行 `git status` 刷新了 index 元数据，
字节哈希因此变化，开始/结束的 tracked status 相同；未执行暂存、重置或检出。该核验差异及初次严格检查失败
记录在 [GIT_STATUS_REFRESH.json](analysis/GIT_STATUS_REFRESH.json)，未覆盖原 CODE_BASELINE。
