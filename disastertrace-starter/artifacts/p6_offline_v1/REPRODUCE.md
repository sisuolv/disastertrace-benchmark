# P6 离线复查命令

以下在 `disastertrace-starter/` 根目录运行。环境和代码都已存在，无需安装包、下载
权重或提供 API key。Python 路径是本机已有环境；迁移到其他机器时使用等价的固定
依赖环境。已消费的程序 collection 目录也不能覆盖或重启。

## 使用冻结代码重新核验现有报告

```bash
P6_CPU_PYTHON=/mnt/afs/260010168/.venvs/disastertrace-p4-review-cpu-v1/bin/python
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=artifacts/p6_offline_v1/execution/implementation_source/src \
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
"$P6_CPU_PYTHON" artifacts/p6_offline_v1/offline_entry.py \
  disastertrace.repeat_eval.cli verify-report \
  --execution artifacts/p6_offline_v1/execution \
  --run work/p6-offline-v1/runs/correct \
  --output artifacts/p6_offline_v1/reports/correct
```

invalid-control 的命令将 run 与 output 末尾均改成 `invalid-control`。
`verify-report --output` 指已经存在的报告，只读核验，不写新模型结果。
原始调用的实际输出/退出记录见 `validation/13_correct_report/`、
`validation/14_invalid_report/`、`validation/17_portable_reconstruction/`。

## 迁移复查

现有成功的副本在 `work/p6-portable-review-v1`。如需再次建立全新副本：

```bash
.venv/bin/python artifacts/p6_offline_v1/prepare_portable.py \
  --output work/p6-portable-review-user-002

PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=work/p6-portable-review-user-002/execution/implementation_source/src \
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
"$P6_CPU_PYTHON" work/p6-portable-review-user-002/verify_portable.py \
  --copy work/p6-portable-review-user-002 \
  --original-project . \
  --model-directory /mnt/afs/260010168/models/Qwen3-8B-modelscope-pinned-v1 \
  --output work/p6-portable-review-user-002/verification.json
```

auditor 只加载复制的源码/config/runs/reports，拒绝原项目、权重、socket访问。
CPU环境没有Torch/vLLM；tokenizer依赖为transformers4.55.2、tokenizers0.21.4、
Jinja2 3.1.6。程序报告重建不依赖XGrammar运行库；实际grammar负控另由旧测试验证。

## 新测试与补充探针

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/p6 -o addopts= -q
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  artifacts/p6_offline_v1/test_source_binding.py -o addopts= -q
```

对应65项核心测试与4项补充测试。Hypothesis6.167.1已存在，固定seed20260908，
每个property最多100个样例、无在线调用或持久example数据库。

旧测试有两个不同环境要求。一次完整轻量环境命令未全部通过，保留该失败；已将
所有52个未通过node对应到安装环境下71/71通过的constrained/stress子集。
实际命令在 `validation/06_legacy_regression/intent.json` 与
`validation/12_legacy_tokenizer_grammar/intent.json`。不要在CPU review环境中假设
已经安装pytest、jsonschema或XGrammar；也不要为了复查升级冻结GPU依赖。

## 新生成程序产物

`disastertrace.repeat_eval.cli` 的公开入口为 `prepare`、`context`、
`collect-diagnostic`、`report`、`verify-report`，没有模型入口。
重新演练应先指定全新的execution、registry、run和report路径；不同输出目录不能
绕过同一execution/mode的单次claim。原始2160正确与2160无效对照均已消费。

posthoc的重新生成使用 `disastertrace.post_p5.cli --project . --baseline
artifacts/p6_offline_v1/baseline --output NEW_DIRECTORY`。字段与原始capture完整绑定，
不支持无capture时冒充verified报告。`source_binding_probes.py` 和 `build_examples.py`
也要求全新输出目录；其首次实际命令见 `validation/19_source_binding_probes/` 与
`validation/20_actual_examples/`。

历史源文件保全可用 `verify_preservation.py --output NEW_JSON_PATH` 重新检查。
最终P6验收可用 `accept_offline.py --verify` 只读核验其文件散列清单。
