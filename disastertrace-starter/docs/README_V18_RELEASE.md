# v18 修复审查发布包

本目录对应 v18 review v2 的代码与审查材料。它包含：

- `src/disastertrace/monitoring_v1/`：证据资格、完整网格评分、Natural Track 和 provider contract 实现；
- `scripts/build_v18_*.py` 与 `scripts/run_v18_controlled_api.py`：开发 roster、synthetic fixture 和受控 API runner；
- `tests/test_v18_*.py`：v18 contract 与 regression tests；
- `docs/CHATGPT_PRO_V18_ANALYSIS_PROMPT.md`：给 ChatGPT Pro 的独立审查 prompt；
- `review/v18_execution_20260923/`：V2 review manifest、claim boundary、测试状态和 synthetic/source-only 产物。

本发布包没有包含原始天气数据、holdout、API key、`.venv`、缓存或历史 `work/` 目录。当前证据仍不支持真实 forecast gain、calibration 或 ranking claim。
