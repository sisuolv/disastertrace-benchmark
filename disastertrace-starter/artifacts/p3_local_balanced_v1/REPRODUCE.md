# 离线复查与复现

请在项目目录（包含 `artifacts/` 与 `work/`）执行。评审压缩包采用同样的相对目录
结构。已完成的真实采集不能通过再次启动 collector 来“验证”；应重建其报告。

本机已有兼容解释器：

```bash
/mnt/afs/260010168/.venvs/disastertrace-qwen3-v1/bin/python --version
```

把完整评审包放到其他机器时，报告重建不需要 GPU、模型权重、vLLM 或 API key。
可在独立 Python 3.10 环境安装 CPU 侧依赖，使用其中的 tokenizer 文件。版本锁定
到采集所用的 tokenizer 组合；完整软件清单另见 `execution/environment.json`。

```bash
python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple \
  transformers==4.55.2 tokenizers==0.21.4 huggingface-hub==0.34.4 \
  jinja2==3.1.6 pydantic typer PyYAML orjson python-dateutil ijson
```

用冻结源码验证已经存在的模型报告：

```bash
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH="$PWD/artifacts/p3_local_balanced_v1/execution/implementation_source/src" \
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
python -m disastertrace.local_eval.cli verify-report \
  --execution artifacts/p3_local_balanced_v1/execution \
  --run work/p3-qwen3-balanced-v1 \
  --output artifacts/p3_local_balanced_v1/model_report \
  --require-model
```

如果要生成一份新的、与已有报告独立保存的重建结果，把 `verify-report` 改为
`report`，并将 `--output` 指向不存在的新目录。不要改动真实 raw captures。

验证平衡数据、自动 Gold 与程序控制：

```bash
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH="$PWD/artifacts/p3_local_balanced_v1/execution/implementation_source/src" \
python -m disastertrace.local_eval.cli verify-data \
  --dataset artifacts/p3_local_balanced_v1/execution/dataset
```

模型本地重新采样属于新实验，需要新的执行版本、规范和运行目录；相同种子也
不保证不同硬件或软件版本之间逐 token 相同。本轮官方权重下载入口和逐文件
SHA256 在 `model_snapshot.json`，完整权重保留在本机 `models/`，不包含在评审包中。

`analyze_results.py` 是本机辅助表格生成器，读取执行里记录的 canonical run 路径。
跨机器审查时优先使用上面的可重定位核心报告重建命令。
