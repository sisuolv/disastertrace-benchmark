# P8: shared-prefix carrier representation control

Completed: all844 actual answers and all422 pairs are independently verified.
JSON has118/422 fully correct answers; the lossless text representation has143/422.
The descriptive difference is5.92 percentage points on two development storms.
Text also uses36-54 more prompt tokens, so this is not an equal-length control.
All four jobs succeed and release; no missing answers,retries,length finishes or
extraction errors occur. Exact token replay and CPU relocation,including original
P7 source-journal replay,pass. Read artifacts/p8_carrier_representation_v1/FINDINGS.md
and that bundle's COMPLETED_ACCEPTANCE.json. All claims are consumed.


This separate experiment compares JSON and explicit path/value text encodings of
the same saved previous forecast answer. Its design and all844 branch slots were
registered before P7 native model scores were read. It addresses a different
question from the original three-policy native forecast evaluation.

The selection includes all422 noninitial structured-state source queries across
the two original repeats. Both branches share the exact source prefix and a fresh
paired seed. Each generates one next answer; branch outputs never feed later
queries. Lossless encoding preserves wrong values, units, statuses and citations.
Missing source prefixes stay in the fixed denominator without replacement.

Implementation: src/disastertrace/carrier_repr. Protocol and preregistration:
artifacts/p8_carrier_representation_v1/DESIGN_BEFORE_NATIVE_RESULTS.md and
PREREGISTRATION.json. The frozen native task, native collector and model captures
remain unchanged. The native source journal is archived for independent replay.

The offline gate checks all paired requests, real tokenizer lengths, complete
latest/invalid/missing program controls and relocated CPU reconstruction with
original paths, network and model backends blocked. The relocated review also
reconstructs the archived original native run before accepting its saved prefixes.
Program diagnostics are never treated as new model answers.

Live bounds after acceptance: same Qwen3-8B checkpoint, four TP1 full H100s,
batch4, context32768, output8192 including reasoning, at most844 answers and
6914048 requested output tokens. Independent two-hour deadline, capped by the
user's ten-hour autonomous window. No retries, paid API, heldout or training.

Current execution evidence is phase-local: CPU_ACCEPTANCE.json appears only after
all offline gates pass; PREFLIGHT_ACCEPTANCE.json only after actual no-generation
H100 loading and release; finalization_01/FINAL_STATUS.json only after the live
observer finishes. Inspect those files for actual status rather than assuming
this protocol document proves execution.

The first combined installed-test invocation had a pytest basename collision.
The corrected CPU driver uses importlib mode. Both logs and the original failure
remain in the bundle's validation directories; no model retry was involved.

Report paired outcomes, storm/transition/repeat tables, invalid or absent answers,
and actual text-minus-JSON prompt lengths. Equal information is not equal length.
Only two storms are represented; no population significance or universal model
memory claim follows from this experiment.
