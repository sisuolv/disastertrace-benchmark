# Completed paired carrier representation experiment

All844 planned Qwen3-8B answers arrive; all four H100 jobs succeed and release.
Independent report reconstruction, exact XGrammar final/EOS token replay and
CPU relocation pass at2026-09-08T18:19:07.669689+00:00. Relocation also extracts
and re-audits the archived original P7 source journals with original paths and
network blocked. No response is replaced, repaired or retried.

## Paired results

The population is every noninitial P7 structured-state checkpoint, including both
original sampling repeats:422 source prefixes, each with one JSON branch and one
lossless text branch. All422 prefixes are available and eligible. Both branches
use the same actual original prefix and matched fresh seed. Generated branch
answers never feed a later branch.

| Outcome | Pairs |
| --- | ---: |
| Both JSON and text fully correct |88 |
| JSON correct, text wrong |30 |
| JSON wrong, text correct |55 |
| Both wrong |249 |
| Total |422 |

JSON is fully correct118/422 (27.96%); text143/422 (33.89%). The paired difference
is25/422, or5.92 percentage points in favor of this text representation. Both
storms and both source repeats show a positive descriptive difference.

| Source group | Pairs | JSON correct | Text correct | Difference in correct answers |
| --- | ---: | ---: | ---: | ---: |
| Francine AL062024 |210 |72 |85 |13 |
| Ida AL092021 |212 |46 |58 |12 |
| Original repeat0 |211 |61 |71 |10 |
| Original repeat1 |211 |57 |72 |15 |

The storm and repeat tables partition the same422 pairs in different ways; they
must not be added together. There are only two independent storm source groups.
The many target horizons and checkpoints within each storm are dependent.

## Information, length and remaining errors

The codec preserves the same parsed carrier information in both arms, including
wrong values, types, nulls, citations, missing/invalid markers and negative zero.
There is no reference correction. Equal information is not equal token length:
text has36-54 more prompt tokens in every pair, mean47.34 and median54. No pair
is exactly equal in length. The result concerns this concrete representation
change, including its length and syntax; it does not isolate an abstract format
effect from token count, prove a causal benefit of memory, or establish universal
text superiority over JSON.

All844 outputs are shape-valid and have correct storm,absolute time,forecast kind
and units. There are261 fully correct branch answers and583 failures. Disjoint
primary categories are379 value/status/unit errors,174 wrong locators,24 wrong
source versions and6 superseded-same-value citations. Units are correct throughout,
so the379 category is value/status driven. Keep component errors separate from
these disjoint labels because component metrics overlap.

## Resource and verification evidence

There are no missing answers,unknown outcomes,length finishes or extraction
errors. Total generated tokens are1,241,085:1,111,437 reasoning,127,960 content,
844 close-think delimiters and844 terminal tokens. The reservation remains the
original maximum6,914,048 output tokens. The model allocation consumes2.09694
H100-hours across four TP1 jobs, excluding the separate no-generation preflight.
GPU count itself is not a measured speedup relative to a serial counterfactual.

Before inference,87 P8 core tests,3 P8 installed tests and9 inherited native
installed tests pass. Three complete844-slot program controls and relocation
pass; every diagnostic remains separate from model-origin results. Preserve the
earlier duplicate-module collection and missing-transformers driver failures.
The successful driver is validate_offline_03.py; all preceding logs remain.

Canonical evidence: execution_live_01, source_prefixes_01/native_evidence.tar.gz,
finalization_01/global_report.json, finalization_01/token_replay.json,
finalization_01/cpu_relocated/receipt.json and finalization_01/FINAL_STATUS.json.
The model run is work/p8-carrier-qwen3-v1. Every launch and model claim is consumed.

This remains a development benchmark of understanding published forecast claims
under task-defined latest explicit coverage. It is not physical weather prediction
or an assertion about operational NHC horizon validity. Broader development
sources and the second local model are separate subsequent phases.
