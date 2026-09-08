# Single-repeat interpretation and historical scorer field names

The frozen P7 scorer includes a legacy JSON field named both_repeats. Its
implementation aggregates all scheduled repeats for each target/method; it does
not assert that two repeats are present. P11 schedules only repeat0,so that field
is numerically a one-repeat whole-target count here. It is not evidence of success
in two repeats and must not be described as sampling-repeat reliability.

Keep the inherited scorer and raw reports unchanged. The P11 comparison report
must reconstruct whole-target success directly from the scheduled repeat0 score
records and name it whole_target_single_repeat. Report the explicit set of repeat
IDs alongside it. This naming clarification changes no value,status,citation,
opportunity or correctness judgment and requires no model recollection.

P7/P9 have two repeats and retain their original both-repeats interpretation.
P8 source-repeat identities refer to repeated original prefixes and single-step
branches; they are not full native trajectories. Never pool these summaries.
