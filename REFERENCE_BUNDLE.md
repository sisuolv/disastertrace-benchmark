# Reference subset for private review

The adjacent `references/` directory contains the exact source snapshots needed
by the existing offline tests and both supported `workflow.build` configurations.
It preserves the `disastertrace-starter/` and sibling `references/` layout so the
original relative paths continue to work. This is a private review package, not
a new dataset release or a claim of new source acquisition or label validation.

## Included files

| Original reference group | Files | Bytes | Purpose |
| --- | ---: | ---: | --- |
| DisasterBench selected snapshot and original manifest | 7 | 450,662 | Inherited planning controls, tool descriptions, evaluator reference, README, and MIT license |
| CyPortQA selected snapshot and original audit | 4 | 76,418 | The 48-template declaration profile, README, and MIT license |
| Original Ida implementation sources | 7 | 117,674 | Default three-advisory build and original HTML/text provenance |
| Frozen NHC cohort | 110 | 1,290,984 | Catalogue, 36 HTML/text pairs, 36 acquisition attempts, and manifest |
| Total original reference files | 128 | 1,935,738 | Unmodified copies from the existing workspace |

An additional exact copy of the existing project `THIRD_PARTY_NOTICES.md`
contributes 9,841 bytes. The 129 copied source/notice files total 1,945,579 bytes;
the generated inventory and verification records are additional packaging files.
The source snapshots have not been rewritten, normalized, redacted, or rebuilt.

The DisasterBench build verifies every manifest row selected for that repository,
including the evaluator, graph description, README, and license. Those files are
therefore retained even where their contents are not executed by the local
adapter. CyPortQA contributes only its template declarations and attribution
files; the full QA dataset, visual assets, and model runners are not included.

The NHC cohort retains all 12 originally planned storms and acquisition records,
including the original parser rejections and source records assigned to heldout
events. Offline regression checks do not issue heldout model requests. Access to
these source records for private review does not authorize model evaluation or
protocol tuning on heldout outcomes.

## Provenance and attribution

Original `MANIFEST.json` files and `opensource_audit_2026-09-06/AUDIT.json` remain
byte-identical. They preserve source URLs, pinned commits where applicable,
retrieval records, and the recorded checksums. The inventory adds a checksum and
provenance entry for every file actually included here:

- [Reference inventory](references/REVIEW_REFERENCE_INVENTORY.json)
- [Reference checksums](references/REVIEW_REFERENCE_SHA256SUMS)
- [Existing third-party notices](references/THIRD_PARTY_NOTICES.md)
- [DisasterBench MIT license](references/no_manual_review_2026-09-06/weather_qa_sources/DisasterBench_Open/LICENSE)
- [CyPortQA MIT license](references/opensource_audit_2026-09-06/snapshots/MLLM-Bench-CyPortQA/LICENSE)

DisasterBench is pinned to commit
`408672bf0da489d94e6245900a87ec913b3d69f9`; CyPortQA is pinned to
`1c38abf339d1471d710f6cb719a5e3874b547077`. NHC records come from official
NOAA/NWS archive URLs and retain their own attribution and recorded reuse terms.
Repository software licenses do not replace terms for third-party materials
referenced inside a task. Referenced external imagery and service outputs are
not acquired by this package.

The original manifests also describe broader research snapshots. Their metadata
is preserved, but unrelated Obshazard, EarthVerse, STATE-Bench, STALE,
ExtremeWeatherBench, and other source files are deliberately absent. The review
inventory is authoritative for bundle membership; an entry in an original audit
does not imply that its referenced repository was included here.

The copied project notice retains its original wording and relative references.
Its original location is `disastertrace-starter/THIRD_PARTY_NOTICES.md`; this copy
preserves attribution rather than creating new licensing conclusions. Advisory
retrieval timestamps do not prove historical first-publication times, and the
controlled schedules and research rules are not official NOAA/NWS products.

## Verification performed

All 130 entries in `REVIEW_REFERENCE_SHA256SUMS` passed: the 129 copied files plus
the generated inventory. Both existing offline build configurations completed
with network connection functions disabled:

- The original Ida build admits three reports and creates two episodes with ten
  checkpoints.
- The frozen cohort build admits 32 reports and creates 20 episodes with 100
  checkpoints, preserving three development and seven heldout admitted storms.
- Both builds retain 230 admitted inherited planning tasks and 48 CyPortQA
  template declarations. Neither build calls a model or runs the named tools.

The relocated cohort build reproduces 14 of the original 15 non-implementation
artifacts byte-for-byte. The remaining file,
`profiles/cyportqa_templates.json`, differs only in its recorded absolute
`source_path`, which now points at this copied snapshot. All other fields in that
profile match. This location field changes the fresh build ID; it is not a source,
label, or evaluation change. Do not claim that a build made in a different checkout
has the same identifier as the original workspace build.

The initial helper incorrectly required byte equality for that absolute path and
failed. Its failure record is retained, and the corrected comparison separately
checks the relocated path and equality of all other profile fields:

- [Final reference verification](references/REVIEW_REFERENCE_VERIFICATION.json)
- [Checksum output](references/REVIEW_REFERENCE_VERIFICATION.log)
- [Initial helper failure](references/REVIEW_REFERENCE_VERIFICATION_initial.json)

These records verify copying and existing build regressions. They do not claim a
new source acquisition, new data-admission protocol, per-item human review, or a
fresh run of the entire test suite. Repository-wide test results, if rerun during
publication preparation, are recorded separately by the review-package owner.

From the repository root, repeat the source checksum verification with:

```bash
cd references
sha256sum --check REVIEW_REFERENCE_SHA256SUMS
```

From `disastertrace-starter/`, after installing the project's dependencies, use
a new output directory for each existing build command:

```bash
disastertrace-auto build --references ../references --output work/review-ida-build
disastertrace-auto build --references ../references --nhc-snapshot ../references/nhc_cohort_v1 --output work/review-cohort-build
```

The inventory and source checksum file do not include their own verification
records, avoiding circular hashes. The enclosing repository/package inventory
can bind this document and the verification records separately.
