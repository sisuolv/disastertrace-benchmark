# P6-P14 private review publication

Start with [the current results entry](../../RESULTS_20260909.md) and the detailed
[Chinese ChatGPT Pro handoff](../../disastertrace-starter/REVIEW_FOR_CHATGPT_PRO_P6_PLUS.md).
The historical root README and accepted historical documents retain their bytes;
their older descriptions are not the current phase pointer.

The authorized target is the existing private repository
`sisuolv/disastertrace-benchmark`, branch `next-phase-v1`. The prior published HEAD
is `dd5ee358f9708e2eb2f2032db9eaac14fa237adc`. Use the final commit identity when
reviewing. A private URL alone does not give ChatGPT Pro access to the repository.

## Reading versus reconstruction

- `chatgpt_pro_p6_p14_reading.zip` is a selected reading attachment: code, tests,
  protocols, phase summaries, and interpretation. `reading_manifest.json` records
  its exact digest and scope. It does not contain the complete raw runs or
  tokenizers and cannot reconstruct all reports by itself.
- `evidence_p6_p10/` contains seven accepted P6-P10 inventories: 32,982 original
  paths, deduplicated into three ZIP parts totaling 224,567,019 bytes. Each original
  file has a SHA256-addressed gzip object. All original scientific bytes remain
  unchanged. The complete package has been restored locally and all seven
  acceptance inventories have been checked again.
- Subsequent completed phase archives are listed in the results entry after
  terminal audits and sealing. Read each archive's manifest for its exact accepted
  scope. An acceptance proves the recorded stopped or completed run is auditable;
  it does not turn a failed GPU job into a successful or fully collected matrix.

Keep this handoff, the notices, and all parts of the relevant evidence package
together. Model weights, installed environments, credentials, and the unrelated
local `.github/` directory are excluded. See
[additional third-party notices](THIRD_PARTY_NOTICES_ADDITIONS.md) for copied
backend source and model metadata licenses.

## Restore the evidence

The archive tool uses only the Python standard library. Restore into a new
directory or an appropriate checkout of this publication. It creates missing
files, accepts byte-identical existing files, and refuses conflicting files.
It never replaces a different existing file.

```bash
python publication/autonomy_review_20260909/evidence_archive.py restore \
  --bundle publication/autonomy_review_20260909/evidence_p6_p10 \
  --target /path/to/review-workspace \
  --receipt /path/to/new-p6-p10-restore-receipt.json
```

Run the same command for each subsequent evidence directory listed in the
results entry, reusing the target but choosing a fresh receipt filename.
`verify --bundle DIR --target RESTORED_ROOT --receipt NEW_PATH` checks every
restored accepted byte again. A restore receipt records byte recovery, not a
fresh independent scientific audit.

CPU reconstruction also requires the compatible Python dependencies recorded in
the execution environment receipts. The saved CPU wrappers block the original
project, weights, network, and subprocesses. Use absolute arguments because those
wrappers change their working directory. Do not run model launchers as part of
review: all historical phase and worker claims are consumed.

## Publication verification

`check_payload.py` checks the actual Git index and matching worktree bytes,
including nested ZIP/gzip/TAR contents detected by bytes. It reports credential
pattern matches without printing their values, checks paths and file sizes, and
rejects `.github/workflows/` entries for this publication. No hosted Actions run
is claimed. Configured pattern scanning is not a proof of recognizing every
possible credential format.

The final staged-tree check and commit/remote comparison receipts are kept under
the ignored `review-outputs/autonomy-publication-20260909/` directory of the
publishing checkout. This avoids changing the tree to insert its own commit hash.
The GitHub commit and remote comparison establish publication; this document's
preparation alone does not establish that a push has succeeded.
