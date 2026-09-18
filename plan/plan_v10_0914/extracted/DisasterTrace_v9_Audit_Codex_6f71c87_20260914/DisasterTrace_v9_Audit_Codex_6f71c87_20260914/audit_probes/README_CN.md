# 本包实际检查

在本目录执行：

```bash
PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider test_review_regressions.py test_v8_additional.py test_v9_properties.py
```

需要本地Python与pytest，不调用模型/网络。59通过是已记录的本环境执行；请核对all_probes.txt/xml。

完整仓库生产模式（使用明确的新只读/测试工作区路径）：

```bash
export DISASTERTRACE_AUDIT_MODE=repo
export DISASTERTRACE_REPO_ROOT=/absolute/path/to/disastertrace-benchmark
export PYTHONPATH="$DISASTERTRACE_REPO_ROOT/disastertrace-starter/src"
PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider test_review_regressions.py test_v8_additional.py test_v9_properties.py
```

生产模式另需仓库真实依赖。本环境未执行生产模式，也未跑616项原范围。

`isolated_loader.py`只删顶层相对导入并装载已核对依赖；不改被测函数体。E原生helper使用已经披露的报告区间，不是把真实气象传感器当无误差物理真值。calibration诊断限定无TAF分支，不替换天气特征提取器。

12份源码全文件Git blob相符，校验见SOURCE_HASH_VERIFICATION.json。测试名中的v8表示探针来源历史，不代表本轮跑的是v8源码。

校准切换是预期行为诊断，测试通过只证明它会发生，不证明它科学上总合理或实际造成某次增益。原E回复汇总错误的测试通过表示成功复现错误，不是模型回答正确。59不是benchmark正确率，也不含待做AC条件。
