# DisasterTrace published-forecast understanding: development study

This card describes the P10-P14 expanded cohort. The results are development
evidence for a benchmark under construction. Earlier controlled-record stress
tests and the two-storm P7-P9 studies have different designs and denominators.
Read `result_tables_v1/TABLES.md` for verified final counts when that export is
present, and `../../RESULTS_20260909.md` for the current execution status.

## Task and intended measurement

Given currently visible NHC advisory text, answer a query about the latest
explicitly supported forecast for a named storm and absolute target time. Return
the forecast state, numeric fields where available, required units, source
version and line locators. Queries distinguish an explicitly published forecast,
a target not stated in the currently visible evidence, and a DISSIPATED forecast.

This measures extracting, updating and citing information in published forecast
documents. It does not score the physical forecast against later observed
weather. A public deterministic latest-explicit resolver solves the current task
without accessing private Gold. Model errors alone do not establish that a task
requires deep reasoning or a particular internal memory mechanism.

## Sources, split and evaluation units

The expanded cohort uses six development storms: Dorian (AL052019), Isaias
(AL092020), Henri (AL082021), Fiona (AL072022), Lee (AL132023) and Helene (AL092024).
It contains 36 original products, 144 forecast targets and 804 future checkpoints.
Each model-condition matrix schedules three methods and one repeat, giving
2,412 planned answers. These checkpoints are nested in targets and storms; they
are not 2,412 independent weather events.

Sources are original English NHC products with preserved acquisition records and
content hashes. Automated parsing, cross-checks and deterministic scoring produce
the reference answers without new per-item human annotation or an LLM judge.
Parser agreement does not establish every meteorological assumption. Exact
historical public availability is not proved merely by the advisory issue time;
this remains a controlled issued-time replay. Public historical documents may
appear in model training data. The existing heldout split is not used for these
model runs, and no contamination-free or heldout generalization claim is made.

The early-advisory sampling does not represent every storm stage. This cohort
does not contain terminal-revision checkpoints. Its DISSIPATED reference cases
must not be described as demonstrated coverage of actual terminal revisions.

## Inputs and model conditions

Every method receives the same cumulative visible source documents. The
additional own-answer carrier is the comparison:

| Method | Additional carrier |
| --- | --- |
| snapshot | None |
| structured_state | The declared deterministic state projection of saved model answers |
| answer_history | Saved final answers from that model's own trajectory |

Requests use fresh message lists. Diagnostic program answers and private Gold
are excluded from actual model histories. The task therefore compares the effect
of extra answer carriers under cumulative evidence; old source documents are
not hidden from selected methods to force memory retrieval.

| Condition | Model | Contract placement | JSON format whitespace |
| --- | --- | --- | --- |
| P11 | Qwen3-8B and DeepSeek-R1-Distill-Qwen-7B | system | Arbitrary format whitespace allowed |
| P12 | Both models | system | XGrammar default separator spacing |
| P13 | DeepSeek-R1-Distill-Qwen-7B | user | Same default spacing |
| P14 | Qwen3-8B | user | Same default spacing |

The user-role condition prepends the identical contract text and two newline
characters to the original user content, using the model's frozen chat template.
There are three protocol cells, not a complete role-by-whitespace factorial.
Different conditions and models generate their own histories. Matching source
queries and seeds does not make later trajectory inputs identical.

These are local open-weight models, not the DeepSeek hosted API model. The
distilled model has Qwen ancestry, so this is not an architecture-independent
replication. Frozen vLLM 0.10.2 and XGrammar 0.1.23 run one full H100 per worker,
two workers per model matrix, with four batch sequences, bfloat16, temperature
0.6, a 32,768-token context and an 8,192-token output reservation including
reasoning. Exact package and sampling settings are bound in each execution.

## Scoring and failure accounting

The primary count requires all relevant output fields to match jointly: storm,
absolute target time, forecast kind, status, three values, exact unit strings,
current source version and line locators. Coordinates use signed degrees with
N/E positive and S/W negative, with unit `deg`; maximum sustained wind uses `KT`.
No posthoc unit normalization changes the original strict score.

The fixed denominator includes every planned slot after a matrix dispatches,
including unattempted, unknown and invalid outcomes. An undispatched condition
has no measured model accuracy and is reported separately as offline-only.
Coverage, shape, numeric-only scores, reference-status strata, units, source and
locator counts explain the primary result. Component errors overlap; primary
error categories have a defined precedence. Whole-target success in these
matrices concerns one repeat, despite the inherited `both_repeats` field name.

Static grammar constraints enforce public structure rather than correct answers.
They allow incorrect values and citations. A legal incomplete token prefix is not
a complete valid JSON answer, and token-mask compliance is not semantic accuracy.

The frozen collector stops its whole worker if any next-batch request exceeds
the context reservation. This can censor unrelated trajectories. It does not
truncate history or retry, and those missing slots remain visible. The three
protocol conditions also have different dispatch times under a shared deadline.
P14 returns 1,628/2,412 answers before that cutoff, leaving 780 unattempted and
four unknown outcomes. Its planned-denominator difference includes censoring
and cannot be attributed solely to role placement. P11/P12 Qwen are the two
complete matrices; all three DeepSeek conditions are stopped prefixes.

For Qwen P12/P14, the strict-correct change of -108 decomposes into +68 on the
1,628 jointly returned slots and -176 on the 784 slots returned only in P12.
The common-return subset is selected posthoc and does not remove time/history
bias. The primary denominator and every original score remain unchanged.

## Evidence and interpretation

Raw-first capture, immutable executions, independent report reconstruction,
token-mask replay, and isolated CPU review support auditability. A passing audit
does not change an ACP FAILED/SUSPENDED job into a successful collection.
Read the actual return counts, terminal states, stop reasons and LOCATION records.
Postprocessing receipts may state `new_model_calls: 0`: that describes the audit
or export command itself. The evaluated matrix's actual attempts and returns are
recorded separately in its report `counts`; the receipt does not imply that the
matrix used no model inference.

P11's preserved v2 acceptance omitted 14 analysis/command files. Its separate
review addendum binds those files; P12-P14 use the corrected v3 sealer. Full P11
analysis reconstruction requires its original phase evidence plus the final
supplement. This defect and its failing/passing regression logs remain available.

The evidence volumes preserve original bytes and exclude model weights,
environments and credentials. The selected reading ZIP is a convenient review
attachment, not a complete raw reconstruction package. See `CPU_RECONSTRUCTION.md`
and `THIRD_PARTY_NOTICES_ADDITIONS.md` for dependencies and notices.

Results support descriptive comparisons within this development cohort.
Checkpoint counts do not replace independent storm groups or repeated sampling.
Protocol selection, trajectory fault isolation, broader storm-stage coverage,
independent model families and an untouched heldout execution remain future work.
These research measurements are not a validated operational disaster-warning
or emergency-decision system.
