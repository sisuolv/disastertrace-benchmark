# Output Contract V1

The offline calibration package compares the original public instruction with a
versioned instruction that states the complete response shape. The existing
parser, evidence rules, field values, research action rule, and scores remain
unchanged. This is preparation for a separately specified experiment; it does
not make or authorize model API calls.

## Motivation

The legacy instruction asks for exactly `state` and `action` and describes each
field slot, but leaves the action's JSON type implicit. The completed P1 batch
contains truncated outputs and structurally invalid outputs, while the carrier
methods can expose prior valid JSON answers as implicit format examples.
Making the same response contract explicit for every method supports a future
controlled comparison of this possible format effect. Offline checks do not
establish that the new wording improves model performance or fixes truncation.

## Interface

`disastertrace.automated.output_contract` exports:

```python
LEGACY_CONTRACT = "legacy_v1"
EXPLICIT_CONTRACT = "explicit_v1"

contract_spec(contract=EXPLICIT_CONTRACT)

render_calibration_request(
    episode,
    checkpoint_id,
    previous,
    *,
    method=DEFAULT_METHOD,
    history=None,
    contract=EXPLICIT_CONTRACT,
)
```

`contract_spec` returns a fresh dictionary containing the schema version,
contract name, protocol, marker, full JSON Schema, schema hash, lexical
requirements, grounding requirement, instruction suffix, parser authority, scope,
provider JSON mode flag, and contract ID. The schema hash is the canonical
fingerprint of `json_schema`. The contract ID is the canonical fingerprint of
the complete descriptor before adding `contract_id`. Thus both wording and
constraints are bound, without a self-referential hash. Callers can mutate a
returned descriptor without changing later calls.

The legacy descriptor documents the frozen parser's shape; its schema and marker
are not appended to legacy requests. `legacy_v1` delegates directly to
`render_request` and preserves canonical public request bytes.

For `explicit_v1`, only `instruction` changes. The renderer appends its marker,
contract ID, explicit shape instructions, lexical requirements, grounding
guidance, and canonical JSON Schema. The appended text is identical across all
methods and checkpoints. It includes no answer instances or numerical answer
examples. Schema bounds such as a positive citation line are constraints, not
example weather values.

## Response Shape

The top level is an object with exactly `state` and `action`.

- `action` is a string selected from `monitor`, `prepare`, and `request_evidence`.
- `state` has exactly `maximum_wind_mph`, `latitude_deg`, `longitude_deg`,
  `minimum_pressure_mb`, and `port_reopening_time`.
- Each field slot has exactly `status`, `value`, and `evidence`.
- An `unknown` slot has a null value and an empty evidence array.
- A `known` slot has a finite numeric value and an evidence array.
- Each evidence reference has exactly a string `record_id` and a positive
  integer `line`.

The JSON Schema uses Draft 2020-12 and disallows extra keys at every object
level. The same slot definition applies to all five fields. It does not encode
a shortcut that fixes the port field to unknown.

The frozen parser accepts a known slot with an empty evidence array and accepts
an empty `record_id` string structurally. The schema preserves both behaviors;
it does not add `minItems: 1` or `minLength: 1`. Grounding is evaluated separately.
The instruction requests at least one supported reference for a known value to
receive grounded credit. A schema-valid citation is not evidence that its record
exists, is visible, contains the claimed fact, or supports the correct value.

## Lexical Requirements And Parser Authority

`disastertrace.automated.dynamic.parse_decision` remains the authoritative
response parser. The contract requires one complete JSON object, double-quoted
keys and strings, no duplicate keys, no Markdown fences, no explanatory prose,
and no trailing data. Known numeric values must survive the frozen parser's
finite-number check; non-finite values and numeric overflow are unsupported.

A JSON Schema validator operates on already parsed data and cannot certify all
of these textual requirements. In particular, JSON Schema's integer type admits
mathematically integral numbers such as `1.0`, while the frozen parser requires
the citation line to parse as a Python integer. Therefore its JSON token must
have neither a fractional part nor an exponent. Duplicate-key rejection and
the implementation's finite-number behavior also require the frozen JSON/parser
path. The descriptor records these lexical requirements alongside the schema.
Do not replace the parser with a generic schema validator or claim that schema
validation alone is equivalent to parser acceptance.

The existing parser can raise `TypeError` for an action object because it checks
membership in a set of allowed strings. This module does not repair that parser
behavior or alter its rejection result. Offline regressions preserve rejection
of action objects and swapped state/action shapes.

## Evidence And Carrier Preservation

The renderer obtains public evidence exclusively through the existing
`render_request`. It does not inspect generated reference answers, parsed source
field values, private labels, or future arrivals when constructing the appended
instruction. The request protocol remains `disastertrace_text_v1`, and all
existing public keys retain their shapes.

All methods receive the same cumulative delivered evidence. Structured state
receives the actual previous schema-valid model decision; answer history receives
actual schema-valid decisions in order; snapshot has no answer carrier. Factual
errors and unsupported citations in accepted prior answers are preserved. The
contract renderer does not repair them against private labels. Existing deep-copy
behavior prevents modifying returned requests from mutating source carriers.

## Integration Boundary

Both variants pass the existing `ProviderClient.prepare` public-request and wire
validation. Their wire hashes differ because the messages differ. No provider
JSON mode, response-format setting, tools, or additional request key is introduced.

This compatibility concerns offline request preparation. The unchanged
`collect_model` and `audit_collection` reconstruct legacy `render_request`
instructions and have not gained a new live explicit-contract collection path.
A future live experiment must explicitly bind and audit its chosen contract.
Do not transform messages after collection recording and then claim the legacy
collection audit proves the transformed messages were sent.

Adding this module changes the implementation identity used by new builds.
Prepare a fresh build for new calibration artifacts. Historical builds, original
requests, raw answers, parser/scorer sources, and P1 scores remain preserved.

## Offline Verification

`tests/test_automated_output_contract.py` forbids network access and provider
completion calls. It covers legacy ambiguity and byte equality, identical shared
instructions, instruction-only changes, no input mutation, private/future data
exclusion, factual-error carriers, stable identities, complete schema structure,
frozen parser acceptance and rejection cases, lexical limits, and provider wire
preparation without JSON mode.

The tests inspect the schema declaration and use the existing parser as the
acceptance authority. A third-party JSON Schema validator is not installed or
claimed as an additional validation authority.

```bash
.venv/bin/python -m pytest -o addopts= -q tests/test_automated_output_contract.py
.venv/bin/ruff check src/disastertrace/automated/output_contract.py tests/test_automated_output_contract.py
.venv/bin/ruff format --check src/disastertrace/automated/output_contract.py tests/test_automated_output_contract.py
```

Actual command results and source hashes are retained under
`artifacts/calibration_v1/contract_checks/`.
