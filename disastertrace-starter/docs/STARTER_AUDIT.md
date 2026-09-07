# Starter 审计记录

## 范围

本记录来自本次对已上传 `disastertrace-starter.zip` 的实际解压、源代码检查和本地执行。
没有修改原 starter 源代码；没有执行付费 API、训练、真实灾害数据构建或新虚拟环境安装。

原压缩包 SHA-256：

```text
823ffa9fcbea8f114565fba36ee9e3fc9bd94f7a1618b45724e790c8bedae6c6
```

测试环境：Python 3.13.5，Pydantic 2.13.4，pytest 9.0.2。

## 原有测试

在原始 starter 根目录，已执行：

```bash
PYTHONPATH=src python -m pytest -q
PYTHONPATH=src python -m disastertrace.cli validate-episode examples/episode.json
python -m compileall -q src
```

结果：6 个测试通过；demo 包含 2 个文本 artifact、2 个 checkpoint；compileall 通过。
现有 CLI 仅包含 `validate-episode`、`index-cyportqa`、`parse-nhc-time`。

## 补充探针

复现脚本位于 `audit_artifacts/probe_starter.py`。在项目根目录：

```bash
PYTHONPATH=src python audit_artifacts/probe_starter.py
```

此探针输出当前缺陷行为，不是全部使用 assertion 的正式 regression suite。
Codex 应先把这些行为转成针对预期正确语义的失败测试，再修复。

实际输出：

```json
{
  "timing_applied_to_hold": {
    "admissible": 1.0,
    "timing": 0.0
  },
  "unknown_metadata_causes_preservation_failure": {
    "before_value": null,
    "after_value": null,
    "preservation": 0.0
  },
  "unbound_span_wrong_artifact_passes": {
    "grounding": 1.0,
    "strict_pass": 1.0
  },
  "duplicate_slot_updates_accepted_by_ledger": {
    "last_value": "second"
  },
  "nhc_public_header_not_supported": "no explicit NHC UTC issue line found",
  "extra_schema_keys_silently_ignored": true
}
```

## 解释

| 探针 | 当前行为 | 应修订的契约 |
|---|---|---|
| timing_applied_to_hold | monitor 已被允许，仍因某时间窗口得 timing=0 | 窗口绑定目标 action；首次触发由序列计算 |
| unknown_metadata_causes_preservation_failure | unknown 值未变，但更新时间引起 preservation=0 | 按业务语义比较，审计元数据变化另列 |
| unbound_span_wrong_artifact_passes | A 的 span 写在 B 上，grounding 和 strict 均为 1 | 绑定 claim、artifact、view 和 locator |
| duplicate_slot_updates_accepted_by_ledger | 两个 ADD 写同一 slot，第二个覆盖第一个 | 严格唯一更新与事务性 apply |
| nhc_public_header_not_supported | 常见 local header+UTC summary 格式被拒绝 | 按产品解析本地标题并交叉核验 UTC/跨日 |
| extra_schema_keys_silently_ignored | 未识别输出字段消失，没有 validation error | 模型输出禁止 extra keys |

另由源代码确认：输出目录无 arm/repeat、hash 缺完整参数和最终 Schema、仅 episode 结束落盘、
未区分 delivered 与 actually presented、carrier 无 action、GIS 无条件 union/buffer、arrival 无法表示旧文件重复送达等。
完整对应任务见主计划 F01–F16。未做专门复现的项目没有标成“已实测失败”。

## 不应过度解释

小型 synthetic 探针只用于说明代码契约缺口，不证明真实模型存在某种灾害推理失败。
现有 6 项测试通过，也不代表数据来源、因果辨识、GIS 正确性或模型 API 已得到验证。
