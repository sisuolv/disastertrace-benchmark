# Shared-delay synthetic gate

This gate used the same four-checkpoint, fixed Brier denominator for five methods (`fixed`, `no_extra`, `source_rr`, `source_hash`, `active`) over 144 cells (reliability, delay, coverage, confidence) on two RTX 5090 spot replicas and one H100 spot replica. Each cell used 1,000,000 targets.

The active arm improved on the fixed prior (pooled mean active-minus-fixed loss is -0.02637525), and the direction was consistent across the three GPU replicas. That is mechanism evidence only. Against the best non-active method, active was worse on average (pooled mean active-minus-best-non-active is 0.00616053; wins 31/432 cells). The repeated independent retrieval arm (`source_rr`) is a strong comparator and accounts for most of the gap.

The practical decision is therefore conditional: uncertainty-aware selection can help when evidence is delayed or shared, but the current fixture does not support a generic claim that active selection itself is better than cost-matched non-adaptive retrieval. Any real pilot must freeze query cost, source reuse, calibration, reliability strata, and a stopping/harm guard before scoring.

All rows are synthetic, with no weather outcome, provider call, holdout, or quarantine access.
