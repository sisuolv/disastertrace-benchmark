# v9 review package

Read REVIEW_AND_CODEX_NEXT_PLAN_CN.md and CODEX_START_HERE.md.

This package contains original hash-verified copies of four small repository modules, not a full checkout. The original repository ZIP was not retrieved. The checks use synthetic weather inputs and the published Denver bank parameter subset, not the original raw weather arrays or full experiment logs.

The 11 executable checks reproduce observed behaviors and controls. The work-package acceptance items are future specifications, not passed repository tests. No remote services, API keys, model weights or font files are included.

Run: `python scripts/reproduce_review_checks.py` from a copy of this directory. This uses only the Python standard library and writes its checks under results/.
