# Fresh-environment handoff validation

This directory records verification of the publication copy on 2026-09-07.
The original benchmark source and historical experiment archives were preserved.

| Check | Actual result | Evidence |
| --- | --- | --- |
| Fresh dependency installation | Successful; editable import resolves to the publication copy | [environment.json](environment.json), [requirements-installed.txt](requirements-installed.txt) |
| Current full test suite | 684 passed in 57.41 seconds; exit 0 | [pytest_result.json](pytest_result.json), [pytest.log](pytest.log) |
| Fresh reference-based build | Successful; 3 development and 7 heldout events; exit 0 | [fresh_build.log](fresh_build.log) |
| Fresh calibration preparation | Successful; 270 planned calls, 54 unsent initial requests; exit 0 | [calibration_prepare.log](calibration_prepare.log) |
| Fresh calibration verification | Passed; 128 artifacts, 54 initial requests and 1,080 diagnostic responses verified; exit 0 | [calibration_verify.log](calibration_verify.log) |

Exact reproduction commands and process timings are in
[offline_reproduction.json](offline_reproduction.json). These checks made no model
API calls. Credential-like environment variables were removed for the build and
calibration subprocesses. Diagnostic responses are program outputs, not LLM answers.

The local Python installation lacked `ensurepip`. The publication environment was
created with `python3 -m venv --without-pip .venv`, then bootstrapped using pip's
`--python .venv/bin/python` option from an existing environment. Installation used
the Tsinghua PyPI mirror and installed `pip` plus `-e '.[dev]'`. No original
environment packages were replaced. This dependency snapshot records the successful
Python 3.10 run; it is not a guarantee for every Python/platform combination.

Fresh outputs are deliberately excluded from Git under
`disastertrace-starter/work/review-build-001/` and
`disastertrace-starter/work/review-calibration-001/`. They can be regenerated with
the root README commands. Their identifiers reflect relocated provenance paths:

- Build: `1e015f8e5ee2a68090941fec7c6eb1ff799a024d4622b807ece5e7a1e466cde4`
- Calibration package: `0cd0a404e310a105755b513029ad75386ac44026e2ef9eeb312922fc2c8b26c0`
- Source implementation: `493d00ca6545ae708064e24e3cebc5c450c7ceee508f4478ae2e5555e06845f0`

The independent audit in `../handoff_audit/` has its own recorded scope and
timestamps. Historical test/audit evidence remains separate from this new run.
