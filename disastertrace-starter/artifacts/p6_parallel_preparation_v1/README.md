# Four-H100 preparation after the user's acceleration request

On 2026-09-08, while the existing single-H100 matrix was running, the user asked
to use more GPUs for speed. Prefer up to four independent one-H100 model workers
for the next suitable matrix. The active pt-gxxtikov process uses a fixed TP=1
engine and cannot add GPUs in place. Its frozen single-worker schedule, consumed
claim and current outputs remain intact.

## Implemented and checked

The new repeat_parallel module prepares and verifies an offline worker layout.
It has no model collection or GPU submission command. A preview refers to source
slot IDs explicitly; it is not a live execution package and contains no usable
new attempt claims. Eighteen CPU tests pass. Initial lint feedback and its
correction are retained in INITIAL_LINT_FAILURE.json.

For the current matrix shape, assign the complete base episode to one worker,
including all conditions, methods, repeats and checkpoints. There are four
case/branch variants per source/family stratum. Rotate their worker assignments
across strata so each of four workers gets one variant per stratum.

| Quantity | Complete matrix | Per H100 worker |
| --- | ---: | ---: |
| Base episodes | 36 | 9 |
| Answer opportunities | 2,160 | 540 |
| Whole trajectories | 432 | 108 |
| Condition pairs | 1,080 | 270 |
| Batches at the existing cap of 12 | 180 | 45 |

Every worker has the same number of opportunities for each source, family,
condition, method and repeat. Each episode retains both condition orders and
the source schedule's relative order. Case/branch distributions are recorded
explicitly; nine episodes per worker cannot divide evenly into four variants.
One- and two-worker layouts are also supported. Three workers are not supported
by this equal four-variant-stratum contract.

The throughput benefit is an expectation of data parallelism, not a measured
speedup. Queue time, model loading, output lengths, host bandwidth and the slowest
worker affect wall time. Four replicas each retain TP=1; distributing this 8B
model itself over four GPUs is not required by this proposal.

## Actual reconstruction command

Run from disastertrace-starter using the existing CPU review environment:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
/mnt/afs/260010168/.venvs/disastertrace-p4-review-cpu-v1/bin/python \
  -m disastertrace.repeat_parallel.cli verify \
  --execution artifacts/p6_live_v1/execution_live_02 \
  --output artifacts/p6_parallel_preparation_v1/four_worker_layout \
  --workers 4
```

Preparation and verification both exit zero. The layout identity is
b8941c3229ef954e63f90d7b906a0b7969f3b3ff068f56c98a0577c927ca5187.
This revalidates the frozen parent and independently rebuilds the entire layout
before comparing it with the saved preview. Commands, logs and observed exits
are retained here. The preview does not reschedule the active matrix.

## Remaining engineering before a new multi-GPU run

1. Bind the chosen new task, global opportunity count, fresh execution and attempt
   identities, and worker layout into a new execution package. Source slot IDs
   remain provenance references, not reusable launch claims.
2. Add independent worker run directories, raw-first journals and a one-use phase
   submission registry. An ambiguous submission stays consumed; another worker
   must not silently regenerate its opportunities.
3. Bind one full H100 per worker, the installed backend, actual preflight, common
   sampling settings and global deadline. Sum worker token/attempt reservations
   and respect the four-concurrent-H100 ceiling.
4. Reconstruct each worker's requests and carriers independently, then merge by
   frozen global slot indices. Check exact disjoint coverage, intact pairs and
   trajectories, unique attempts, and worker/source/method balance.
5. Keep a failed worker's unanswered slots in the global denominator. Add tests
   for partial responses, lost workers, duplicate submissions, altered ownership
   and aggregation from a stopped prefix before any new model launch.
6. Report elapsed phase time separately from summed GPU worker time and preserve
   per-worker outcomes. Redistribution during a run requires a separately defined
   execution design.

The user's GPU preference persists; these are implementation and measurement
requirements, not a request to grant GPU access again.
