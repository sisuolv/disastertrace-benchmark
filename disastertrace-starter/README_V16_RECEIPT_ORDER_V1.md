# v16 receipt-order round — RRx recognition + same-minute tie-breaking

Documents the `disastertrace.revision_v1` DL-3R TAF/METAR ledger pipeline
(episode compiler → ledger → semantic validator). This is unrelated to the
P1-P14 DeepSeek/Qwen automated-evaluation pilot described in the top-level
`README.md` — the two lines of work share this repository but not a
codebase or a documentation lineage. This file covers branch
`v16-receipt-order-v1` (5 commits over `v16-measure-prep-v1`: `RO1`-`RO4`
plus a merge commit), the fourth round of a stacked sequence
(`v16-prep-v1` → `v16-datafix-v1` → `v16-measure-prep-v1` →
`v16-receipt-order-v1`, visible in `git log --oneline v16-prep-v1..HEAD`
on this branch).

## Problem

The prior round's full-archive run (140 station-months, 41,386 compiled
packages) found two gaps: 34 packages carry WMO `RRA`/`RRB` retransmission
codes the classifier didn't recognize, and 42 groups produced more than one
"latest" record with different content hashes — same-minute issuance ties,
because both the WMO header and the TAF body only carry minute-precision
timestamps.

## Idea

Archive `.body` files are strictly ordered newest-to-oldest on disk. That
receipt order is a sub-minute clock signal the timestamps themselves don't
carry. This round turns it into two explicit, tested fields
(`receipt_seq` / `receipt_stream`, attached in `episode_compiler.py`) and
uses them in exactly two places: `versions.py::resolve_receipt_tie`
(existing multi-hash-tie path only) and `ledger.py`'s visibility filter at
equal `available_at` — the actual fix for a cyclic-supersedes bug that
tie-breaking in `latest_issuance` alone could not fix (the two members of a
tied pair only ever see each other, so a single-value `latest_issuance` call
has nothing left to break a tie against). Every consumer falls back to
unmodified legacy behavior whenever the premise doesn't hold: missing
field, mismatched stream, non-monotonic `issued_at`, or unorderable seqs.

The semantic validator (`validate_dl3r_semantics.py`) detects ties
independently of resolving them, so a resolved tie always stays visible in
the report instead of silently disappearing, and it cross-checks each
resolution against BBB letter order before accepting it.

## Result

Independently re-verified against the raw archive at this branch's tip, not
copied from any task's self-report. Full 140-file / 41,386-package run,
`--expected-skips 60`:

- 60 skipped packages — pre-existing, class `other`, explicitly disclosed and out of scope for this round.
- 0 `wmo_bbb` violations — all 34 RRx packages now correctly recognized as `original`.
- 37 / 42 same-minute ties auto-resolved by receipt order.
- 5 / 42 left as residual conflicts — real cases (e.g. KSFO, 2024-08) where BBB letter order and receipt order disagree. These are **not** force-resolved; doing so would violate the validator's own audit-integrity rule that a disagreement must stay an open conflict. Exit code 1 is expected because of these 5, not a failure.

Tests: 464 in `tests/test_revision_*.py` (up from 432 before this round), 49
in `tests/test_validate_dl3r_semantics.py` (up from 31), 30/30 on both
external regression suites — all re-run fresh at this branch's tip.

## Verify

```bash
VENV=/mnt/afs/260010168/extreme_weather_benchmark/development/v14_revision_20260919_01/.venv
$VENV/bin/python -m pytest -o addopts= -q -p no:cacheprovider \
  tests/test_revision_*.py tests/test_validate_dl3r_semantics.py

$VENV/bin/python scripts/validate_dl3r_semantics.py --expected-skips 60
```

The validator run writes a fresh semantic-validation report next to the
archive and exits 1 by design (see the 5 residual conflicts above) — that is
the expected result, not a broken build.

## Not covered by this round

Values-bank refit, the BASE0 baseline-completeness contract, LAMP
categorical wiring, a frozen episode manifest and real empirical measurement
runs, confirmation-holdout opening, and download-execution ownership are all
still open. The 60 disclosed pre-existing skips are unfixed by design
(confirmed via `--expected-skips`, not silently dropped).
