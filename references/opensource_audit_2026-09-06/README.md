# Open-source reference audit, 2026-09-06

This directory contains a read-only research snapshot for the proposed extreme-weather benchmark. It is reference material, not an installed dependency or an executable project starter.

`AUDIT.json` records repository URLs, complete resolved commits, licensing observations, verified findings, unverified claims, and SHA256 hashes of every saved upstream source file. Each saved source file was also checked against its GitHub tree's Git blob SHA1. `api/` preserves the retrieved tree and Inspect release-tag responses. `snapshots/` contains the selected unmodified upstream files.

| Resource | Recommended use | Main limitation |
| --- | --- | --- |
| CyPortQA | Candidate evidence and small media-adapter smoke test | Static QA gold and event metadata do not establish historical evidence availability. |
| CyPort | Later outcome-data reference | README declares CC BY 4.0; inspect original source terms and keep future outcomes out of model inputs. |
| Inspect AI | Candidate single evaluation framework / model adapter | Tag 0.3.263 exists; provider and runtime compatibility still need testing. |
| EarthVerse | Submission validation, provenance, report organization | Code, annotations, and third-party evidence have different licenses. |
| lmms-eval | Later backend/export integration | Avoid maintaining two core evaluation frameworks in the first version. |
| STATE-Bench | StateDiff and structured state-requirement scoring ideas | Synthetic enterprise workflows; a different project from StateMemBench. |
| ExtremeWeatherBench | Later event registry, hazard taxonomy, or separate forecast track | Evaluates numerical/ML weather forecasts, not LLM temporal reasoning. |
| STALE / CUP-Mem | Later explicitly identified memory baseline | Do not silently give its verifier to every evaluated model. |

## Licensing observations

- CyPortQA, Inspect AI, STATE-Bench, ExtremeWeatherBench, and STALE have MIT license files.
- CyPort has no standalone license file in the inspected tree, but its README explicitly declares CC BY 4.0 for the dataset. GitHub's null license metadata therefore does not mean there is no license declaration.
- EarthVerse original `scripts/` code and configuration are Apache-2.0; original questions, answers, rubrics, computed ground truth, metadata, schemas, and documentation are CC BY-NC 4.0. Third-party evidence retains provider terms.
- lmms-eval's main pipeline is MIT; added code under `lmms_eval/tasks` and `lmms_eval/models` is Apache-2.0. Upstream data rights require their own review.
- This snapshot is for local research planning. Redistribution must preserve applicable notices and satisfy each source's terms.

## What this audit establishes

The inspected repositories and listed commits existed on the audit date. The saved files match their upstream Git blobs. Selected source code supports the reuse ideas recorded in `AUDIT.json`.

No third-party code was executed, packages installed, models called, results reproduced, or large datasets downloaded. README dataset counts remain author-reported unless explicitly noted otherwise. The CyPortQA main QA JSON and scenario JSON were checked for existence and byte size in the tree, not downloaded or scientifically audited.

Inspect's current-main source snapshot and the proposed `0.3.263` release are separately identified in the audit. Reading current-main APIs does not certify that a release or provider implements them correctly.

Some raw-file downloads stalled and were terminated. The final unauthenticated GitHub API requests for the Inspect README and ExtremeWeatherBench `events.yaml` returned rate-limit errors. Those files are absent and are not described as reviewed. Tropycal, DisasterBench_Open, and Obshazard-bench received metadata-only checks, detailed separately in `AUDIT.json`.
