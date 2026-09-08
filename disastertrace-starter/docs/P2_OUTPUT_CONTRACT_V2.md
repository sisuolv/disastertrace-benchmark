# P2 common output contract v2

## Scope

This is an offline interface revision following the first P2 development matrix.
It does not change the controlled task protocol, Gold or scoring. The observed v1
failures remain six invalid answers (four JSON structure failures and two empty
length finishes) and three citation errors. No response is repaired or replaced.

The source of the exact common system text is
`src/disastertrace/controlled/output_contract.py`. It contains no populated answer,
episode data, private source binding, future evidence or selected failure's answer.
The three methods receive the same system text. The canonical public user message
continues to come from the unchanged `renderer.render_request`.

## Contract and version binding

The system text explicitly requires a root object containing only `state` and
`action`; four exact weather fields under `state`; slot objects with `status`,
`value`, `evidence`; citation objects with `record_id` and positive integer `line`;
and one of the three action strings. It restates unknown/null/empty semantics,
numeric ranges, two-decimal precision, strict types and the existing action rule.
It forbids extra/duplicate keys and copying input containers into the answer.

Citation instructions distinguish a source record from a delivery event, and
require the printed supporting ASSERT line of the current authoritative version.
Known empty evidence remains structurally valid with zero grounded credit. A
wrong but well-typed ID/line is still a scoring error, not a parser rejection.
The strict `parse_decision` is unchanged and performs no repair.

`controlled_output_contract_v1` preserves the previous system, prepared-envelope
shape and hashes. It remains the default for legacy preparation calls and CLI
usage. Select `controlled_output_contract_v2` explicitly for the candidate.

V2 preparations carry a local `output_contract` descriptor with version and SHA256
of the exact UTF-8 system text. That descriptor is part of the prepared-request
identity; it is not an extra provider API parameter. The wire payload changes only
the system message. Capture validation regenerates the selected preparation and
compares the entire canonical envelope before dispatch. Unknown versions, mixed
roles, inconsistent text/digests or missing v2 identity are rejected.

V2 execution manifests use `controlled_execution_v2` and bind that descriptor.
The collector, independent auditor, recovery path, summary and reports use the
frozen selection. Captures remain under the existing transport schema and bind
the full prepared-request hash. Switching contract, implementation or dataset
requires a new execution identity and authorization; captures cannot cross arms.
Historical executions must be verified with their own frozen implementation.

## Fixed experimental settings

- Development scope: 18 episodes, 3 methods, 5 checkpoints, 54 trajectories,
  one repeat, 270 planned calls; same rotated order and all fixed denominators.
- Candidate: `deepseek-v4-flash`, high reasoning, thinking enabled, no temperature,
  `max_tokens=8192`, no response_format/JSON-mode switch, no automatic retries.
- Keep 180-second socket and total deadlines, 1 MiB response bound, existing
  request-byte and conditional-budget guards. Extra system text increases input
  size; byte comparisons are measured offline, actual token usage remains unknown.
- Keep all nine family-by-method screens: each has 30 opportunities, at least 29
  schema-valid answers, at most one length finish, and a complete independent audit.
- Keep invalid full answers and the prior valid carrier; propagate schema-valid
  factual errors unchanged. No Gold correction or diagnostic history enters a live run.

8192 is an initial controlled setting, not a proven sufficient cap. The two v1
length failures remain visible. JSON syntax mode alone would not ensure the
required object structure and is not an additional change in this candidate.

## Offline acceptance

Run `scripts/reproduce_p2_execution.py` with
`--output-contract controlled_output_contract_v2` and a fresh `--output` directory.
It executes the full tests and ordinary offline build, preparation, verification,
270-slot diagnostic collection, independent audit, report and reconstruction.
External network is blocked; local HTTP fixtures are permitted and labeled.

`scripts/verify_p2_output_contract.py` compares frozen v1/v2 semantic files and
unchanged semantic source modules, all 30 program score configurations and their
traces, metric opportunity denominators, and every old actual public request under
both preparers. Historical-carrier projections are unsent comparisons only. They
are never used to seed candidate model collection or to claim v2 model exposure.

The acceptance also verifies version/role isolation, exact HTTP bytes, no leakage,
invalid-answer retention, factual-error propagation, registry separation and all
five interruption boundaries. Captured answers can be finalized offline without
credentials or a second send; unknown dispatch remains stopped with its reserve.

The v2 source is frozen recursively with this document. Semantic files can remain
byte-identical while implementation, dataset content/package and execution IDs
change, because the existing content identity includes implementation identity.
Both frozen reports are independently reconstructed using their own source.

## Subsequent proposal

After offline acceptance, prepare a fresh single-contract 270-call development
screen, initially a separate USD 3 conditional allowance. Use a new production
registry and run directory. Authorization templates remain false, and pricing
requires current matching applicability before model dispatch. No API key is
needed for this offline work; preparation is not a launch authorization.

A comparison with historical v1 is descriptive, not a contemporaneous causal
estimate. A separately frozen, interleaved two-contract 540-call design is a later
option if that research question matters. Second-model, balanced source/case
design (540 calls per model), and heldout inference remain separate later stages.
This package neither performs per-item human annotation nor uses an LLM judge.
