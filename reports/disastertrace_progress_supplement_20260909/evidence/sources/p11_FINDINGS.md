# P11: expanded native protocol, completed audits

Both registered model matrices now have verified terminal reports and descriptive
analyses. Qwen3-8B returns all 2,412 answers; DeepSeek-R1-Distill-Qwen-7B returns
1,604 before its two workers stop at the context guard. Both DeepSeek jobs remain
FAILED. All four GPU allocations are released. Audit completion does not mean
both collections completed.

The task uses six development storms, 36 original products, 144 targets, 804
future checkpoints, three carrier methods and repeat0 only. All methods receive
the same cumulative visible source documents. Their difference is the additional
carrier made from the model's own previous answers. The common system contract
and native public-shape grammar remain unchanged throughout this phase.

## Planned-denominator results

| Model | Returned / planned | Shape valid | Strictly correct / planned | Strict % | Unattempted |
| --- | ---: | ---: | ---: | ---: | ---: |
| Qwen3-8B | 2,412/2,412 | 2,411 | 1,000/2,412 | 41.4594 | 0 |
| DeepSeek-R1-Distill-Qwen-7B | 1,604/2,412 | 1,514 | 3/2,412 | 0.1244 | 808 |

Unknown outcomes are zero for both models. Returned-only DeepSeek correctness is
3/1,604 (0.1870%); it is supplementary, not the primary denominator. All three
DeepSeek fully correct answers are `not_stated` cases. Details and exact context
projections are in DEEPSEEK_FINDINGS.md.

| Model | Method | Returned / 804 | Strictly correct / 804 | Whole targets correct / 144 |
| --- | --- | ---: | ---: | ---: |
| Qwen3 | snapshot | 804 | 356 | 4 |
| Qwen3 | structured_state | 804 | 345 | 22 |
| Qwen3 | answer_history | 804 | 299 | 15 |
| DeepSeek distill | snapshot | 538 | 1 | 0 |
| DeepSeek distill | structured_state | 530 | 1 | 0 |
| DeepSeek distill | answer_history | 536 | 1 | 0 |

All 144 Qwen targets per method are fully captured. DeepSeek has only 18 fully
captured targets per method. The inherited report field `both_repeats` is not a
two-repeat estimate here: the verified analysis labels it
`whole_target_single_repeat`. Snapshot has the highest Qwen checkpoint total,
while structured_state has the highest whole-target total. These different
metrics do not identify one universally best carrier.

## Storm and reference-status breakdowns

Qwen strict counts, with 134 planned checkpoints in every storm-method cell:

| Storm | snapshot | structured_state | answer_history |
| --- | ---: | ---: | ---: |
| Dorian AL052019 | 71 | 66 | 59 |
| Isaias AL092020 | 50 | 56 | 33 |
| Henri AL082021 | 57 | 49 | 38 |
| Fiona AL072022 | 53 | 50 | 62 |
| Lee AL132023 | 60 | 56 | 50 |
| Helene AL092024 | 65 | 68 | 57 |

The leading method changes by storm. Each storm has equal planned size, so the
storm macro average equals the checkpoint-weighted average in this particular
cohort; neither creates additional independent storm groups.

| Reference status | Planned per method | Qwen snapshot | Qwen structured_state | Qwen answer_history |
| --- | ---: | ---: | ---: | ---: |
| numeric | 598 | 183 | 171 | 131 |
| not_stated | 196 | 170 | 168 | 164 |
| DISSIPATED | 10 | 3 | 6 | 4 |

Qwen numeric correctness is 485/1,794 (27.0346%), compared with 502/588
not_stated and 13/30 DISSIPATED. The headline 41.46% is not numeric forecast-row
accuracy. This distinction matters when naming the task and interpreting scores.

For the 96 changed-wind checkpoints per method, Qwen strict correctness is
snapshot42, structured_state26 and answer_history6. For 326 no-new-coverage
checkpoints, it is snapshot75, structured_state94 and answer_history77. These
are descriptive strata with dependent checkpoints and independently generated
histories, not isolated causal interventions or population significance tests.

## Errors and resource use

Qwen's disjoint primary error partition is 1 invalid final shape, 3 wrong keys,
892 wrong value/status/unit cases, 33 wrong source versions, 483 wrong locators
and 1,000 correct answers. All 2,411 shape-valid answers use the required `deg`,
`deg` and `KT` units. Its only length finish is invalid and has a reasoning
extraction error; all 2,411 stop finishes have valid shapes. Format compliance
therefore does not account for most of Qwen's semantic and citation failures.

Qwen has 1,754 current-source flags, 1,167 correct locators and exact-value counts
of 1,588 latitude, 1,589 longitude and 1,721 wind. These component totals include
null-valued reference statuses and must not be relabeled numeric-only accuracy.
The primary error categories have precedence; lower-priority errors can overlap.

DeepSeek has 808 unattempted slots, 90 invalid final shapes, 232 wrong keys,
1,273 wrong value/status/unit cases, 5 wrong source versions, 1 wrong locator
and 3 correct answers. Its 90 length finishes are all invalid. Only 137 valid
answers use `deg` for each coordinate. Its two blocked next batches each contain
one oversized answer_history request and three requests that would fit. The
unchanged collector stops the entire worker, censoring independent trajectories.

| Model | Output tokens | Generation-job H100 allocation hours | Whitespace in final texts |
| --- | ---: | ---: | ---: |
| Qwen3 | 3,317,090 | 5.2233333 | 103,133 characters; maximum 100 |
| DeepSeek distill | 2,097,855 | 2.8316667 | 1,657,688 characters; maximum 301,418 |

Allocation time includes loading and worker lifetime, and excludes the separate
no-generation preflights. It is neither instantaneous utilization nor an invoice.
Whitespace counts include whitespace inside strings. No answer is cleaned,
normalized, replaced, truncated or retried.

## Verification and preserved observer failure

For each model, report reconstruction, report verification, token-mask replay
and isolated CPU relocation exit zero. Qwen replay checks 347,857 final/EOS
tokens without violations. The analysis independently reproduces the fixed
denominator, partitions, single-repeat target counts and token accounting.

The original cross-phase review daemon stops when the newly launched P12 initial
observer rejects ACP QUEUEING/INIT metadata. This happens before P11 Qwen's audit
finishes and does not affect any model answer. Its failed status is preserved in
`../autonomy_10h_v1/cohort_reviews_01/FINAL_STATUS.json`.

A fresh CPU review controller analyzes and verifies P11 Qwen and explicitly
reuses the previously verified P11 DeepSeek analysis. Per-model LOCATION records
bind exact finalization paths, analysis paths, report IDs and file hashes. The
versioned acceptance builder includes these records and the earlier failure.
P11's original model observers themselves both finish successfully.

- Qwen report: `a8427f3e11a0dd3f56bafb6b021cb4a23b547a8a00cbafc8d30f7acaac59dfae`.
- Qwen analysis: `e54116face914904f5b032c8de555c811c6476a4eb35cce97533291bf7e26559`.
- DeepSeek report: `2eee8cceb3356b08b56274a5b6d2242542b18f923d55c042d54c592fb7eec799`.
- DeepSeek analysis: `eabf96989b3930a86760b2cbe3a5e96db3595a2e1896e10d1703f1f52d8e5615`.

## Limits and next registered conditions

The deterministic public resolver solves this task without private Gold. The
benchmark measures published-forecast document/version understanding under
cumulative evidence, not numerical weather prediction or inaccessible-memory
recovery. Six early-advisory development storms, one repeat, English inputs,
unknown exact historical availability and shared Qwen ancestry limit broader
claims. The cohort has no terminal-revision checkpoints and heldout is untouched.

P12 is a separate, already registered default-JSON-spacing condition. P13/P14
move the same contract text into user messages under that spacing rule. They
generate their own histories. These three protocol cells are not a full
role-by-whitespace factorial. No later condition changes the P11 evidence or
repairs the collector's whole-worker stopping policy.
