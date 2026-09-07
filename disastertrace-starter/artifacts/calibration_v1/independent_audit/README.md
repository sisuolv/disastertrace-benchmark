# Independent calibration preparation audit

The final automated audit completes with **6,979 passing checks**, zero failures,
and zero model API calls. These are artifact and replay checks, not additional
pytest test cases or observations of an LLM. `final_result.json` is the final
source-bound result; `final_execution.json` and `final_execution.log` retain the
actual command, timestamps, exit code, and output.

The checker verifies:

- All 359 entries in the completed P1 archive and the 20 original automated
  source files remain unchanged, including the source parser and both scorers.
- All 15 nonimplementation data artifacts in the fresh build equal P1. The new
  implementation and its 128 preparation artifacts are bound to their hashes.
- Three development storms, three methods and three declared arms have exactly
  270 scheduled opportunities and 1,474,560 requested output tokens. The order
  is reconstructed independently from the protocol's rotations and branch rule.
- Only the instruction changes between contracts. Cumulative delivered evidence
  is independently reconstructed, including repeated arrivals. Poisoned private
  fields and future records do not enter requests; schema-valid factual errors
  in a carrier are retained without repair.
- All 54 initial requests remain unsent. All 1,080 full-trajectory responses are
  deterministic program controls. Accepted responses rebuild each branch's own
  history sequentially; invalid responses retain their failed opportunities.
- Actual diagnostic traces and scoring projections differ only in the declared
  instruction and its hash. Every one of the 36 complete V1 and V2 diagnostic
  results is replayed directly with the unchanged scorers. Projection hashes
  and the explicit non-live flags are verified.
- The USD 3 allowance and 270 calls remain a proposal, with authorization and
  live-readiness false. Reservation arithmetic is independently recomputed:
  USD 0.46678016 at 4096, USD 0.47218688 at 8192, and USD 126.517248 for all calls
  at the deliberately conservative full-context ceilings.

The final checker rejects the provider completion and HTTP transport entry
points throughout its execution. After independent checks, it also calls the
package's own semantic verifier under that restriction. It never calls a paid
model, reads a credential, changes Gold, edits old artifacts, or creates live
predictions. Current calibration results remain unknown; live collection and
the budget guard still require their separate implementation and authorization.

The review identified scope fields insufficiently checked after a manifest was
rebound, incomplete retention of the full V1 diagnostic result, and missing
documentation of the scoring projection. Those were addressed before the final
build. The final source review has no remaining blocking findings. The earlier
initial-integrity and contract-review JSON files remain as recorded intermediate
snapshots; the final result binds the completed source and package identities.

Recheck into a fresh audit result path:

```bash
.venv/bin/python artifacts/calibration_v1/independent_audit/package_review.py \
  --prepared work/calibration-v1-preparation \
  --output artifacts/calibration_v1/independent_audit/recheck-001.json
```

`audit.py` holds the historical-integrity and adversarial public-contract checks.
`package_review.py` holds the separate schedule, configuration, trajectory,
projection and score replay review. A later change to either implementation or
the prepared package requires a fresh audit result; existing result files are
never overwritten.
