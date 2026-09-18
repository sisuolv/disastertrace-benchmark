# DisasterTrace v7 → 预测与准备行动：Codex后续计划包

基准提交：`60ebd05723f9483590611976d379da2e4edd85b0`；整理日期：2026-09-13。

这是实施计划和规格文件，不含已经实现的行动代码或新的实验成绩。现有仓库报告与定向源码已核对；没有在本次规划中重跑仓库测试、启动模型、下载科学数组或修改远端仓库。

## 从哪里开始

将 `START_HERE_CN.md` 的内容交给Codex，并将本文件夹作为附件或放在其工作区可读的位置。先执行DS00—DS04本地CPU阶段；不默认启动模型、外部下载或发布。

| 文件 | 用途 |
|---|---|
| `START_HERE_CN.md` | 可直接复制的首批执行任务 |
| `CODEX_PLAN_CN.md` | 完整设计、状态、代码接入、实施顺序和研究边界 |
| `TASK_GRAPH.json` | 16个工作包的依赖、交付与门槛；所有状态为planned |
| `ACCEPTANCE_CASES.json` | 50条验收规格；不是已通过测试结果 |
| `EXPERIMENT_MATRIX.json` | 新DX00—DX09的固定项、改变项和测量项 |
| `CODE_MAP.json` | 已读源码与拟增加模块，区分阅读范围 |
| `REFERENCES.json` | 现有仓库、三份旧材料、论文与官方文档的来源和复用边界 |
| `EXECUTION_POLICY.example.json` | 无模型/无GPU/无外部下载的保守资源模板；本身不授权执行 |
| `OPERATION_PROFILE.example.json` | 假设准备规则示例，不是业务建议或已实现接口 |
| `SYNTHETIC_SINGLE_STEP.example.json` | 单步解析与时间边界的合成输入规格 |
| `validate_bundle.py` | 本计划包自身的JSON、依赖、交叉引用和默认安全约束检查 |
| `BUNDLE_VALIDATION.json` | 仅对本计划包结构检查的实际结果 |
| `MANIFEST.json` | 本包文件SHA256与大小（不自引用） |

## 本计划的主要变化

不删除旧预测与证据任务。在其上新增有准备时长、资源占用、取消和到期的研究性行动子轨，并用相同天气/证据下不同准备条件的配对实验，检查信息是否在还能改变安排时被利用。

现有v7正式16类科学准入不因行动单测而改变；真实历史天气配假设行动规则只能声称该研究场景下的效果，不能直接写成实测经济减损。

## 验证本包

```bash
python validate_bundle.py
```

上述脚本不访问网络、不运行DisasterTrace仓库、不调用模型、不授予任何外部权限。它只验证这组计划文件的内部一致性。重新执行会重写本地`BUNDLE_VALIDATION.json`；若核对原交付哈希，请先运行只读 `python validate_bundle.py --check-only`。
