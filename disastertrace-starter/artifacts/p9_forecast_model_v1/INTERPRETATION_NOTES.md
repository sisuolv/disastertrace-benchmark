# Interpretation of the matched native model comparison

This note clarifies the registered comparison without changing its population,
sampling, prompts, output contract, budgets or scoring.

The snapshot method has identical task evidence and message content across
models. Model-specific chat templates and tokenizers still differ. The
structured-state and answer-history methods use each evaluated model's own
previous answers, so their exposed carriers can differ across models even when
the source checkpoint, policy and seed ID match. The primary comparison is
therefore a comparison of complete model-policy trajectories under common task
rules. It is not a single-step intervention holding past answers constant.

The separate P8 representation control holds the original native prefix fixed
and changes JSON versus text serialization for one next answer. Its JSON branch
also includes the common representation legend and explicit carrier section.
Its scores must not be substituted for the original P7 structured-state scores
or pooled into a single leaderboard denominator.

The common8192 output cap includes reasoning. A model that spends this cap before
finishing the answer retains a length/invalid failure. Do not extend only that
model's cap or retry its failures after scores are observed. Any later output-cap
study needs a separately declared comparison and must retain these original runs.

Repeated checkpoints and two sampling repeats increase observations within the
same two development storms. They do not increase the independent storm count.
Descriptive per-storm differences and exact matched counts remain the appropriate
primary reporting level for this instrument-development cohort.
