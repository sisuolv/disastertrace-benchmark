# Third-party inputs and software

This publication is a private research review snapshot. Source access, byte
integrity, task admission, and permission for a future public dataset release
remain distinct. No account credentials or signed download links are included.

## Weather records

The new aviation evidence contains native U.S. NWS TAF and METAR text served by
the Iowa Environmental Mesonet (IEM). Original URLs, capture times, response
hashes, parsing failures and source line identities are retained in the evidence.
IEM is the retrieval service; it is not an independent weather observation from
NWS. The offline report contract does not turn archived reports into continuous
physical ground truth or prove their global first publication time.

GOES-18 ABI samples originate from the NOAA open data service. The evidence
retains instrument/channel/time/region identity, numerical source files and
derived panels. Derived panels and numerical summaries are lossy representations.
No NOAA, IEM or NWS endorsement is implied.

The H08 revision preflight contains three repeated windows from the USGS Water
Data continuous-observation API, including the earlier native captures. The
reported discharge remains provisional. Retrieval-envelope timestamps and raw
payload hashes are distinguished from revisions to actual observation fields.
The source URLs and receipt hashes accompany both versions; no USGS endorsement
or complete flood-warning task admission is implied.

The additional NOAA NWPS gauge-metadata and native stageflow samples contain
current gauge mapping, flood-stage thresholds, deterministic stage forecasts and
observations. USGS parameter 00065 samples provide same-time gage-height records.
NWPS can relay USGS observations, so matching values do not establish independent
measurements. Native stage/flow units, absent timestamps and provisional status
are preserved; current metadata does not establish historical threshold validity.

## Qwen tokenizers and configuration

Only the pinned non-weight tokenizer/processor/configuration files needed for
response replay are included. Qwen3-8B, Qwen3-VL-8B and Qwen3-VL-32B source model
cards identify the Apache License 2.0. Their recorded model cards and available
license files accompany the tokenizer evidence unit. The 32B local snapshot had
no separate LICENSE file; an explicitly named APACHE-2.0.txt provides the same
standard license text as an accompaniment, not as a claimed original pinned file.
Model weights are omitted. Refer to the model repositories for all upstream terms:

- https://huggingface.co/Qwen/Qwen3-8B
- https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct
- https://huggingface.co/Qwen/Qwen3-VL-32B-Instruct

## Independent decoders and runtime dependencies

The native METAR comparison uses python-metar 1.11.0 (BSD license).
The native TAF comparison uses avwx-engine 1.9.9 (MIT license); its recorded
license text accompanies the comparison reports. These are external comparison
implementations, not a second set of observations or unquestionable truth.
Installed package directories and wheel downloads are not vendored in this
snapshot. Version records identify the software used for the actual checks.

Transformers/tokenizers, PyTorch/torchvision, Pillow, NumPy, pytest and pydantic
retain their respective upstream licenses. The new scientific figures use
Matplotlib. Dependency version records are evidence of the measured environment,
not proof that all supported platforms have been tested.

## Prior datasets and review materials

The user-supplied review texts and counterexamples are retained for this private
review. This snapshot does not newly redistribute the full EM-DAT, CMA or xBD
archives. Original dataset-specific restrictions and historical release gates
continue to apply when preparing a later public benchmark release.
