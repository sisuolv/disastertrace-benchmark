# DisasterTrace：整合计划阅读入口

**参考版本：** `next-phase-v1 @ 1eba36dd272c72573d1309c78d45dbe97dd8af12`。

**状态：** 8 ZIP + 1 Markdown + 当前关键源码/回执 + 新近原始研究的整合提案；不是已执行批次。

## 推荐顺序

先读 `01_MASTER_PLAN_CN.md`：事实基线、八计划取舍、novelty、源码修复、同条件桥接、C2机制、强程序、单模型、确认、第二过程/多模态/行动及完整DAG。

要开始下一批时，将 `02_CODEX_START_HERE_CN.md` 交给Codex；它只执行 A00—A06 并停止。详细机器工单见 `03_WORK_PACKAGES.json`，21个工单全部为 PROPOSED_NOT_RUN。

需要追溯取舍时读 `04_PLAN_MERGE_MATRIX_CN.md`；参考出处在 `05_REFERENCES_AND_SOURCE_MAP.md`。本次新做的三组隔离探针及边界说明在 `06_REVIEW_SCOPE_AND_PROBES_CN.md`，回执在 `probes/`。

## 核心优先级

**先做同日历、同后端的程序信息价值桥接；再做多来源状态的真实GET/PROCESS机制；随后才进行新接口的单模型比较与独立确认。**

温度、第二主动链、原生多模态、受控行动及first_seen记录保留为有界旁路，不同时卡住H15主线。原C1/C2/C3、E/F/D/MM和16灾种长期目标不变。

## 首批边界

不下载、不调用模型/API、不使用GPU、不训练、不打开confirmation、不重消费旧运行、不改写历史结果。第一批后的CPU研究实验、条件性重拟合、12-call兼容性提案和最多288-call模型提案均需要各自新的范围冻结与授权。

`INPUT_MANIFEST.json`记录原附件身份；`PACKAGE_MANIFEST.json`校验本整合包文件。不要将探针观察复现、计划写完或文件存在当作科学门槛已经通过。
