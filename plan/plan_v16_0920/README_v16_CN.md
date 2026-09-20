# plan_v16_0920 阅读入口（2026-09-20）

v16 是一个**规划轮**：目标是准备 (a) 一份自包含的数据下载计划，供另一个尚未开始、零上下文的会话据此执行真实下载；(b) 本仓库内不涉及下载的代码/文档准备（episode compiler、P1 harness scaffold、新颖性定位综述）。v16 轮本身不执行任何真实数据下载、不做 forward capture、不跑真实模型评测。

## 先读

1. `DATA_ACQUISITION_PLAN_v16_CN.md`（419 行）—— **给另一个下载会话看的入口文档，自包含，无需先读本仓库其他材料**。覆盖：D12 前提修正（本节点就是执行机，不存在可从中同步真实数据的独立远程机）、全局规则（存储根目录、直连→代理回退、D10 运行标识/预算/收据纪律、D09 隔离规则）、DL-0 连通性探测到 DL-6 forward capture 共 7 个下载任务，每项均有明确验收标准、请求/字节预算上限、收据 JSON schema。
2. `NOVELTY_POSITIONING_v16_CN.md`（96 行）—— 新颖性定位综述：主张收窄表、竞品对比（含 CORE/PERSIST、EvoSCM 的威胁分级）、forward capture 的数据驱动价值论证、BASE0 基线完备性清单、测量纪律清单。全部编译自 5 份既有 v14/v15 文档，未引入新主张。

## 本轮做了什么、关键发现

v16 轮任务序列：W0（数据下载计划）→ W1（修复 PILOT0 解析器 bug，不产生新 API 调用）→ W2（episode compiler：原始 TAF/METAR 文本 → ledger-ready 证据包 + revision-density 审计）→ W3（P1 harness：5-baseline 家族、3-arm 方法 runner、Natural/Controlled episode 配置）→ W3-FIX（修正 W3 对"跑通陷阱策略"的错误自报，改为真正把 IGNORE_AMD/STALE_HOLD 两个陷阱策略接入 runner）→ W4（新颖性定位综述）→ W5/FIN（本轮收尾）。全部代码改动在新分支 `v16-prep-v1`（基于 `v15-review-repair-v1`@`8416d1be0`，该分支未被改动）上完成，官方 `tests/test_revision_*.py` 套件从 272 增至 **351**（新增 episode_compiler 28 项 + p1_harness 51 项），两份独立回归套件 `review_v15/regressions/test_review_{a,b}.py` 保持 **30/30**，零回归。

**本轮关键发现**：D12 的原始表述"从执行机只读同步真实数据"这一前提被证伪——本节点（本 CCI）本身就是执行机，不存在另一台持有真实数据、可供同步的远程机器。因此所有数据获取都必须是全新的、有边界的、面向公开数据源的下载，并受 D10 的按批预算/收据规则约束（而不是简单的"同步"操作）。这一修正是 `DATA_ACQUISITION_PLAN_v16_CN.md` §0.1 的核心前提，也是 `NOVELTY_POSITIONING_v16_CN.md` §3 数据驱动价值论证的出发点之一。

## 明确排除在本轮之外

真实数据下载、forward capture 执行、P1 真实经验性评测运行、values-bank 重新拟合、BASE0 执行——均推迟到 (a) 用户将另起的下载会话（执行 `DATA_ACQUISITION_PLAN_v16_CN.md` 的 DL-0～DL-6）；(b) 真实数据到位后的未来测量轮次。

## 详细回执与索引

- 逐任务回执（reused/files/tests/preservation check 全字段）：`development/v14_revision_20260919_01/PATCH_LOG.md`（W0/W1/W2/W3/W3-FIX/W4/W5 共 7 条）
- v14 主文档的轮次索引：`plan/plan_v14_0919/DisasterTrace_v14_Novelty_Review_and_Consolidated_Plan_20260919_CN.md` §16（本轮小结，追加于既有 §15 v15 轮之后）
- v14 阅读入口的执行轮记录：`plan/plan_v14_0919/README_v14_CN.md`（"v16 执行轮"一节，追加于既有"v15 执行轮"之后）
- 代码产物（本 git 仓库内）：`disastertrace-starter/src/disastertrace/revision_v1/episode_compiler.py`、`disastertrace-starter/src/disastertrace/revision_v1/p1_harness.py`、对应的 `tests/test_revision_episode_compiler.py`、`tests/test_revision_p1_harness.py`
