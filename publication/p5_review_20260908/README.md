# P5 private GitHub review publication

Prepared on 2026-09-08 for the owner's requested upload to the existing private
repository `sisuolv/disastertrace-benchmark`, branch `next-phase-v1`.

Start with the new Chinese
[ChatGPT Pro review handoff](../../disastertrace-starter/REVIEW_FOR_CHATGPT_PRO_P5.md).
The previous repository HEAD is
`a23f73adadcbec077b9fcf2aecf8f45dfa4fe061`. The publication includes accumulated
development through P5, its actual 1,620-response GPU matrix, all preserved failed
answers and historical evidence, and new review navigation. No new model answer
is generated for publication and no scientific score is changed.

## Sharing the review

Use the branch's exact commit URL after upload, or record `git rev-parse HEAD`
when cloning. A private repository URL alone does not grant the reviewer access.
Give the reviewer the Markdown document and, as needed, these attachments:

- [chatgpt_pro_p5_review.zip](chatgpt_pro_p5_review.zip): selected code, tests,
  protocols and result evidence, preserving repository-relative paths. The
  attachment manifest lists every selected file and its SHA-256. This is a
  reading package; it omits full raw runs, tokenizer files, environment snapshots
  and many historical artifacts, so it does not support full audit reconstruction.
- [Full frozen P5 archive](../../disastertrace-starter/artifacts/p5_stress_level4_v1/p5_stress_level4_acp_v1_review.tar.gz):
  68,654,483 bytes; SHA-256
  `ec52c2b8197358f253a570638bad02e86f8b42d1add410aceaca89865eb8f1b3`.
  This contains the P4/P5 inputs needed for CPU report and comparison reconstruction.
  It was sealed before the new handoff document, which should accompany it.

## Preservation and validation

Original archives, source snapshots, acceptance records and captures retain their
bytes. Historical `published:false` and pre-launch status fields remain correct
for the times they record. The root `EXPORT_MANIFEST.json` and `handoff_validation/`
describe the earlier review snapshot, not the new P5 publication.

The staged payload check scans the exact Git index, verifies index/worktree byte
agreement, rejects credential filenames/key patterns and oversized Git blobs,
and recursively inspects compressed archives without printing matched values.
It also rejects a staged `.github/workflows/` entry for this publication. Model
weights, environments, caches, credential stores and relocated duplicate runs
are not included. These checks detect configured patterns; they are not a claim
that every possible secret format is recognizable.

`check_payload.py --output NEW_PATH` writes an exclusive local check record.
`build_review_attachment.py` constructs the review ZIP from an explicit reading
scope and writes an exclusive manifest. Neither script launches model evaluation.

Actual publication validation and the final commit/remote comparison receipt are
stored in the ignored `review-outputs/p5-publication-20260908/` directory of the
publishing checkout. This avoids changing the reviewed tree merely to insert its
own commit hash. Inspect the actual GitHub commit to establish remote publication;
this document is prepared before the push and alone does not prove it succeeded.

The existing HTTPS OAuth credential lacks GitHub `workflow` scope. The owner
subsequently provides an SSH key, successfully authenticated as sisuolv over
`ssh.github.com:443`; port 22 times out from this machine. This repository uses
that SSH connection, with host keys pinned from GitHub's HTTPS meta endpoint and
repository-local configuration. No private key is copied into this repository.
The local `.github/workflows/offline.yml` remains excluded from this upload; its
equivalent [documentation template](../../disastertrace-starter/docs/ci/README.md)
is included. No hosted Actions run or public repository release is claimed.
