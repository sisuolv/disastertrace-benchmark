# Episode Manifest v16 Disclosure Report

Generated: 2026-09-21T05:23:35.172728+00:00
Manifest: `/mnt/afs/260010168/extreme_weather_benchmark/development/v14_revision_20260919_01/repo/disastertrace-starter/data_contracts/EPISODE_MANIFEST_v16.json`
Selection rule: manifest_selection.v1
Frozen at: 2026-09-21T05:07:48.995150Z
Self SHA256: e83cf42d0c51548971e6684fd65e459041a600bd6dd5e22edb823ec231e2b719

## Summary

- Changed queue: 6 targets
- Unchanged queue: 6 targets
- Total targets: 12
- Checkpoints per target: 3 (T-60, T-40, T-20 min)
- Total checkpoints: 36

## H15 Visibility Thresholds (D02)

Per D02 decision, H15 uses nested 5km/1km thresholds:
- Primary threshold: 5000m (5km)
- Nested threshold: 1000m (1km)
- Event operator: lt (visibility < threshold)

## Per-Lead Eligibility Note

Per-lead-time eligibility reporting is DEFERRED. The codebase (outcome_wiring.py,
episode_compiler.py) does not currently expose a TAF-side-computable notion of
checkpoint/lead eligibility distinct from the target's final Y outcome. Adding
such a primitive would require designing new semantics beyond the scope of this
disclosure-phase bug fix. Per the Missing-Y Contract (PATCH_LOG.md R3), all
checkpoints for a target share the same imputed Y - not independent per checkpoint.

## Target Details

### KDEN_20230811_12

- Station: KDEN
- Queue: changed
- Validity start: 2023-08-11T12:00:00Z
- Revision count: 5
- Tie event count: 0
- Evidence change count: 6
- Lead time coverage: 0.7 hours

Checkpoints:
  - T-60min: 2023-08-11T11:00:00Z (weight=1.0)
  - T-40min: 2023-08-11T11:20:00Z (weight=1.0)
  - T-20min: 2023-08-11T11:40:00Z (weight=1.0)

Outcome (5km): NEGATIVE (vis >= 5km)
Outcome (1km): NEGATIVE (vis >= 1km)

### KDEN_20230826_18

- Station: KDEN
- Queue: changed
- Validity start: 2023-08-26T18:00:00Z
- Revision count: 4
- Tie event count: 0
- Evidence change count: 5
- Lead time coverage: 0.5 hours

Checkpoints:
  - T-60min: 2023-08-26T17:00:00Z (weight=1.0)
  - T-40min: 2023-08-26T17:20:00Z (weight=1.0)
  - T-20min: 2023-08-26T17:40:00Z (weight=1.0)

Outcome (5km): NEGATIVE (vis >= 5km)
Outcome (1km): NEGATIVE (vis >= 1km)

### KJFK_20230328_15

- Station: KJFK
- Queue: changed
- Validity start: 2023-03-28T15:00:00Z
- Revision count: 4
- Tie event count: 0
- Evidence change count: 4
- Lead time coverage: 0.5 hours

Checkpoints:
  - T-60min: 2023-03-28T14:00:00Z (weight=1.0)
  - T-40min: 2023-03-28T14:20:00Z (weight=1.0)
  - T-20min: 2023-03-28T14:40:00Z (weight=1.0)

Outcome (5km): NEGATIVE (vis >= 5km)
Outcome (1km): NEGATIVE (vis >= 1km)

### KJFK_20250626_15

- Station: KJFK
- Queue: changed
- Validity start: 2025-06-26T15:00:00Z
- Revision count: 4
- Tie event count: 0
- Evidence change count: 4
- Lead time coverage: 0.5 hours

Checkpoints:
  - T-60min: 2025-06-26T14:00:00Z (weight=1.0)
  - T-40min: 2025-06-26T14:20:00Z (weight=1.0)
  - T-20min: 2025-06-26T14:40:00Z (weight=1.0)

Outcome (5km): NEGATIVE (vis >= 5km)
Outcome (1km): NEGATIVE (vis >= 1km)

### KDEN_20240401_13

- Station: KDEN
- Queue: changed
- Validity start: 2024-04-01T13:00:00Z
- Revision count: 4
- Tie event count: 0
- Evidence change count: 4
- Lead time coverage: 0.5 hours

Checkpoints:
  - T-60min: 2024-04-01T12:00:00Z (weight=1.0)
  - T-40min: 2024-04-01T12:20:00Z (weight=1.0)
  - T-20min: 2024-04-01T12:40:00Z (weight=1.0)

Outcome (5km): NEGATIVE (vis >= 5km)
Outcome (1km): NEGATIVE (vis >= 1km)

### KDEN_20240222_16

- Station: KDEN
- Queue: changed
- Validity start: 2024-02-22T16:00:00Z
- Revision count: 4
- Tie event count: 0
- Evidence change count: 4
- Lead time coverage: 0.5 hours

Checkpoints:
  - T-60min: 2024-02-22T15:00:00Z (weight=1.0)
  - T-40min: 2024-02-22T15:20:00Z (weight=1.0)
  - T-20min: 2024-02-22T15:40:00Z (weight=1.0)

Outcome (5km): POSITIVE (vis < 5km)
Outcome (1km): POSITIVE (vis < 1km)

### KORD_20230307_00

- Station: KORD
- Queue: unchanged
- Validity start: 2023-03-07T00:00:00Z
- Revision count: 0
- Tie event count: 1
- Evidence change count: 2
- Lead time coverage: 0.7 hours

Checkpoints:
  - T-60min: 2023-03-06T23:00:00Z (weight=1.0)
  - T-40min: 2023-03-06T23:20:00Z (weight=1.0)
  - T-20min: 2023-03-06T23:40:00Z (weight=1.0)

Outcome (5km): NEGATIVE (vis >= 5km)
Outcome (1km): NEGATIVE (vis >= 1km)

### KORD_20230719_12

- Station: KORD
- Queue: unchanged
- Validity start: 2023-07-19T12:00:00Z
- Revision count: 0
- Tie event count: 1
- Evidence change count: 2
- Lead time coverage: 0.7 hours

Checkpoints:
  - T-60min: 2023-07-19T11:00:00Z (weight=1.0)
  - T-40min: 2023-07-19T11:20:00Z (weight=1.0)
  - T-20min: 2023-07-19T11:40:00Z (weight=1.0)

Outcome (5km): NEGATIVE (vis >= 5km)
Outcome (1km): NEGATIVE (vis >= 1km)

### KSFO_20250106_06

- Station: KSFO
- Queue: unchanged
- Validity start: 2025-01-06T06:00:00Z
- Revision count: 0
- Tie event count: 1
- Evidence change count: 2
- Lead time coverage: 0.7 hours

Checkpoints:
  - T-60min: 2025-01-06T05:00:00Z (weight=1.0)
  - T-40min: 2025-01-06T05:20:00Z (weight=1.0)
  - T-20min: 2025-01-06T05:40:00Z (weight=1.0)

Outcome (5km): NEGATIVE (vis >= 5km)
Outcome (1km): NEGATIVE (vis >= 1km)

### KJFK_20240416_18

- Station: KJFK
- Queue: unchanged
- Validity start: 2024-04-16T18:00:00Z
- Revision count: 0
- Tie event count: 0
- Evidence change count: 3
- Lead time coverage: 0.5 hours

Checkpoints:
  - T-60min: 2024-04-16T17:00:00Z (weight=1.0)
  - T-40min: 2024-04-16T17:20:00Z (weight=1.0)
  - T-20min: 2024-04-16T17:40:00Z (weight=1.0)

Outcome (5km): NEGATIVE (vis >= 5km)
Outcome (1km): NEGATIVE (vis >= 1km)

### KJFK_20250823_00

- Station: KJFK
- Queue: unchanged
- Validity start: 2025-08-23T00:00:00Z
- Revision count: 0
- Tie event count: 0
- Evidence change count: 3
- Lead time coverage: 0.3 hours

Checkpoints:
  - T-60min: 2025-08-22T23:00:00Z (weight=1.0)
  - T-40min: 2025-08-22T23:20:00Z (weight=1.0)
  - T-20min: 2025-08-22T23:40:00Z (weight=1.0)

Outcome (5km): NEGATIVE (vis >= 5km)
Outcome (1km): NEGATIVE (vis >= 1km)

### KDEN_20230821_18

- Station: KDEN
- Queue: unchanged
- Validity start: 2023-08-21T18:00:00Z
- Revision count: 0
- Tie event count: 0
- Evidence change count: 3
- Lead time coverage: 0.3 hours

Checkpoints:
  - T-60min: 2023-08-21T17:00:00Z (weight=1.0)
  - T-40min: 2023-08-21T17:20:00Z (weight=1.0)
  - T-20min: 2023-08-21T17:40:00Z (weight=1.0)

Outcome (5km): NEGATIVE (vis >= 5km)
Outcome (1km): NEGATIVE (vis >= 1km)

## Disclosure Statistics

### 5km Threshold Statistics

- Total checkpoints evaluated: 36
- Resolved (non-missing): 36
- Missing/undetermined: 0
- Positive (vis < 5km): 3
- Negative (vis >= 5km): 33
- Natural positive rate: 8.33% (3/36)
- Missingness rate: 0.00% (0/36)

### 1km Threshold Statistics (Nested)

- Total checkpoints evaluated: 36
- Resolved (non-missing): 36
- Missing/undetermined: 0
- Positive (vis < 1km): 3
- Negative (vis >= 1km): 33
- Natural positive rate: 8.33% (3/36)
- Missingness rate: 0.00% (0/36)

## Label Maturity Confirmation

All targets were selected within the archive's covered period
(2023-01-01 through 2025-12-31, excluding Feb 2025 holdout).
ASOS observation archives provide ground truth for all selected windows.
