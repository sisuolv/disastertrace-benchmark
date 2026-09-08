# Notices for the P6-P14 review publication

These notices supplement the historical
`disastertrace-starter/THIRD_PARTY_NOTICES.md`. They do not change the licenses,
provenance, or contents of any frozen scientific bundle. License files are exact
copies; `licenses/COPY_RECEIPT.json` records their sources, versions, sizes, and
SHA256 digests. The repository's own license does not replace these terms.

| Component | Material in the evidence | Observed license | Included notice |
| --- | --- | --- | --- |
| vLLM 0.10.2 | Selected installed backend source files, copied without modifications for audit | Apache-2.0 | `licenses/vllm-0.10.2-LICENSE.txt` |
| XGrammar 0.1.23 | Selected installed grammar/backend source files, copied without modifications for audit | Apache-2.0 | `licenses/xgrammar-0.1.23-LICENSE.txt` and `licenses/xgrammar-0.1.23-NOTICE.txt` |
| Qwen3-8B | Pinned tokenizer, configuration, and model metadata; no weights | Apache-2.0 | `licenses/Qwen3-8B-LICENSE.txt` |
| DeepSeek-R1-Distill-Qwen-7B | Pinned tokenizer, configuration, license, and model card; no weights | MIT | `licenses/DeepSeek-R1-Distill-Qwen-7B-LICENSE.txt` |
| Transformers 4.55.2 | Runtime dependency identified in environment receipts | Apache-2.0 | `licenses/transformers-4.55.2-LICENSE.txt` |

The copied source files retain their own original notices. The relevant
`backend_files.json`, resource manifests, and model snapshot receipts identify
the exact included files. The publication does not redistribute the installed
Python environment, shared libraries, model weight tensors, or an upstream
repository in its entirety. The installed tokenizers 0.21.4 library is identified
in runtime receipts; its installed distribution is not included here.

The saved DeepSeek model card describes the Qwen-derived model's ancestry and
its original upstream terms. Recording its MIT license does not imply an
independent architecture family, official benchmark endorsement, or ownership
of the underlying Qwen contributions. The saved card and licenses should travel
with a redistributed evidence archive.

The source expansions include original NHC forecast/advisory products and their
retrieval receipts. Attribution is to the National Hurricane Center, National
Weather Service, NOAA, U.S. Department of Commerce. The NWS reuse policy and
non-endorsement conditions recorded in the historical notices also apply to
these additions. Controlled replay schedules, parsed fields, task rules, and
evaluation results are project derivatives. They are not official NHC products
or operational emergency guidance. The archive's retrieval time does not prove
the source's historical first-publication time.

This file is a source-specific publication supplement, not a license inventory
for every transitive dependency, linked website, or earlier reference snapshot.
