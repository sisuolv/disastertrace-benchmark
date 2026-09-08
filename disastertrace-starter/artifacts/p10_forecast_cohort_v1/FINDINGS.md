# Expanded development task: offline results

The task compiles and reconstructs from all36 admitted original NHC forecast
advisories for Dorian,Isaias,Henri,Fiona,Lee and Helene. These sources were selected
by storm/year and advisory number before download and any expanded-model score.
There are no new downloads or model generations during compilation/reconstruction.

The original source catalogue admitted26/36 products. All six Isaias products
and the first four Helene products used POTENTIAL TROP CYCLONE in the center
header,which the original parser A did not recognize. Parser B already supported
them. A separately versioned parser extends only that spelling. The36 original
bodies,old products,failed records and original26/36 result remain intact in the
new review_v2. Its independent parsers and canonical line/byte map agree on all36.
The third public-text-only resolver needs no change.

## Complete opportunity accounting

| Quantity | Count |
| --- | ---: |
| Independent storm source groups |6 |
| Admitted products / planned |36/36 |
| Unique target valid times |144 |
| Candidate target/delivery pairs |864 |
| Included strictly future checkpoints |804 |
| Excluded nonfuture checkpoints |60 |
| Explicit forecast rows |282 |
| Successive covering source revisions |138 |
| Answers per model,three methods,repeat0 |2412 |

Reference statuses:598 numeric,196 not_stated,10 DISSIPATED. Transition counts:
144 first checkpoints,99 still-not-stated,97 first-explicit,326 no-new-coverage,
96 changed-wind and42 unchanged-wind. There are four terminal source rows but no
terminal-revision checkpoint under the unchanged P7 definition.

Adjacent numbered advisories use alternating horizon grids. The first source
catalogue's zero adjacent-number matches does not mean zero forecast revisions.
Grouping successive covering versions of the same absolute target reveals138
revisions,including96 wind and137 coordinate changes. No source is substituted.

## Program controls and context

Each of the nine controls retains all2412 opportunities. Counts below are
program diagnostic outputs,not real LLM responses or stochastic repeated trials.

| Public policy | Fully correct /2412 |
| --- | ---: |
| latest_explicit |2412 |
| last_displayed_row |108 |
| same_relative_lead |1020 |
| newest_document |1434 |
| maximum_wind |75 |
| current_pressure |618 |
| first_covering |1707 |
| invalid_even |1224 |
| missing_even |1224 |

There are21,708 program answer opportunities and8626 unique rendered requests.
Each request passes the pinned Qwen3 and DeepSeek tokenizers with the complete8192
output reservation:17,252 tokenizer checks. Maximum prompt plus reservation is
22,977 for Qwen3 and22,969 for DeepSeek,below the common32768 context. Actual model
histories must be checked again at runtime; program histories do not bound every
possible future model output.

All110 related tests pass. A new copy-based CPU review independently reruns source
admission,compilation,the nine controls,public requests,scores and both tokenizer
checks. It blocks original project/model paths,network and child processes before
importing the copied code. The known urllib3 IPv6 capability probe is recorded and
remains denied. Neither Torch nor vLLM is imported for this review.

The execution ID is
f880b4013b89a4e266de4260f91fa06338b5ef1a89be527cf5b597d67457b1a5.
The package ID is
e5fce002ddebe102e10a8c87aeda2428b90071f44df9373ff449afa2c0dad797.
The driver finishes at2026-09-08T18:17:19.174516+00:00 with both build and
CPU relocation exiting0. All initial lint findings and the earlier source-parser
regressions remain recorded. No frozen historical implementation is modified.

## Interpretation and next execution

This is a curated development cohort of the first six forecast advisories for
each storm. It does not sample complete storm life cycles,landfall extremes or
all hazards. Weather forecast skill,historical public availability and pretraining
decontamination remain unestablished. The task-defined retention of the latest
visible explicit horizon is not an NHC operational-validity claim.

P11 separately freezes two models and two H100 replicas per model,4824 planned
answers,one repeat and no retries. It preserves these804 queries and the original
task semantics. GPU generation requires its own complete diagnostics,actual
no-generation preflights,current resource identities and one-use claims. This
offline task remains generation-disabled and cannot be toggled into a live run.
