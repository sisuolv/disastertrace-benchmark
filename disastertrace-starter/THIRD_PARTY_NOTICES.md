# Third-party notices

The second work package adds the frozen `../references/nhc_cohort_v1/` snapshot:
36 selected NHC public advisories across 12 planned Atlantic storms. Every URL,
original HTML/text hash, extraction result and request attempt is retained in its
MANIFEST.json and attempt files. The NHC/NWS attribution and source terms recorded
below also apply to this expansion; the new provider/collector code is original
project code, not copied from an SDK.

This document identifies the upstream materials used by the automated first work
package as of 2026-09-06. Repository software licenses, inherited benchmark labels,
and underlying source records retain their respective provenance. A repository's
software license does not by itself establish rights to every third-party image,
dataset, service, or resource mentioned by that repository.

The generated reports describe a derived evaluation protocol. They are not
official results endorsed by the benchmark authors, NOAA, or NWS.

## DisasterBench_Open

- Repository: <https://github.com/TamuChen18/DisasterBench_Open>
- Pinned commit: `408672bf0da489d94e6245900a87ec913b3d69f9`
- Repository license: MIT, as stated in the pinned LICENSE and README.
- License source: <https://github.com/TamuChen18/DisasterBench_Open/blob/408672bf0da489d94e6245900a87ec913b3d69f9/LICENSE>
- Source snapshot manifest: `../references/no_manual_review_2026-09-06/weather_qa_sources/MANIFEST.json`

The adapter reads the upstream [benchmark records](https://github.com/TamuChen18/DisasterBench_Open/blob/408672bf0da489d94e6245900a87ec913b3d69f9/data/benchmark.jsonl)
and [tool descriptions](https://github.com/TamuChen18/DisasterBench_Open/blob/408672bf0da489d94e6245900a87ec913b3d69f9/interfaces/tools/tools_manifest.json).
Its ordered plan comparison follows the canonical-field comparison semantics in
the upstream [evaluator](https://github.com/TamuChen18/DisasterBench_Open/blob/408672bf0da489d94e6245900a87ec913b3d69f9/evaluators/evaluators.py).
The local implementation in `src/disastertrace/automated/disasterbench.py` adds a
strict response/admission contract, explicit quarantine, and missing-answer
denominators. This adaptation is not an unchanged execution of the original
completion parser or the authors' full evaluation system.

The selected source file contains 233 inherited labeled tasks; 230 pass the
implemented structural admission rules. Labels remain inherited and unreviewed.
This package does not obtain or redistribute the external imagery, documents, or
service outputs referenced by task paths, and it does not execute the named tools.
Their independent terms are not replaced by the repository's MIT license. The
observed repository license is recorded here without asserting a separately
verified license for every underlying benchmark input.

The upstream MIT notice is reproduced verbatim:

```text
MIT License

Copyright (c) 2026

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## CyPortQA

- Repository: <https://github.com/ChenchenMobility/MLLM-Bench-CyPortQA>
- Pinned commit: `1c38abf339d1471d710f6cb719a5e3874b547077`
- Repository license: MIT, as stated in the pinned LICENSE and README.
- License source: <https://github.com/ChenchenMobility/MLLM-Bench-CyPortQA/blob/1c38abf339d1471d710f6cb719a5e3874b547077/LICENSE>
- Source snapshot manifest: `../references/opensource_audit_2026-09-06/AUDIT.json`

The work package profiles 48 declarations in
[CyPortQA_template.json](https://github.com/ChenchenMobility/MLLM-Bench-CyPortQA/blob/1c38abf339d1471d710f6cb719a5e3874b547077/source_data/CyPortQA_template.json).
This is a template inventory, not a full download, label audit, or reproduction of
the complete CyPortQA benchmark. Template IDs and modality/answer-kind declarations
are retained in the profile, together with the source hash. The original visual
assets and full QA dataset are not included in this work package's model inputs.

The earlier CyPortQA snapshot of
[IDA_2021_24h.txt](https://github.com/ChenchenMobility/MLLM-Bench-CyPortQA/blob/1c38abf339d1471d710f6cb719a5e3874b547077/dataset/MultiModalInput/Cyclone%20Text%20Archive%20Advisory/IDA_2021_24h.txt)
was compared with the directly retrieved NHC advisory 010 and found byte-identical.
That text is attributed to NHC under its own source terms, not treated as new
CyPortQA-authored government information. The lead-time filename does not prove
historical publication time.

The upstream MIT notice is reproduced verbatim:

```text
MIT License

Copyright (c) 2025 CyPortQA

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## NOAA / NWS / National Hurricane Center

The source material is Hurricane Ida public-advisory text published by the
National Hurricane Center, National Weather Service, National Oceanic and
Atmospheric Administration, U.S. Department of Commerce:

| Product | Official source | Stated issue time, converted to UTC |
| --- | --- | --- |
| AL092021 public advisory 009 | <https://www.nhc.noaa.gov/archive/2021/al09/al092021.public.009.shtml> | 2021-08-28 15:00 UTC |
| AL092021 public advisory 010 | <https://www.nhc.noaa.gov/archive/2021/al09/al092021.public.010.shtml> | 2021-08-28 21:00 UTC |
| AL092021 public advisory 011 | <https://www.nhc.noaa.gov/archive/2021/al09/al092021.public.011.shtml> | 2021-08-29 03:00 UTC |

These are web archive snapshots, so no Git commit applies. Retrieval timestamps,
original HTML hashes, extracted text hashes, and the HTML-to-text extraction
method are recorded in `../references/implementation_sources/MANIFEST.json`.
The original HTML and exact text extracted from its sole `pre` element are
retained alongside that manifest. Retrieval occurred on 2026-09-06 and does not
establish when the material first became publicly available in 2021.

The official [NWS disclaimer and reuse policy](https://www.weather.gov/disclaimer),
under "Use of NOAA/NWS Data and Products", was read on 2026-09-06. It states:

> The information on National Weather Service (NWS) Web pages are in the public domain, unless specifically noted otherwise, and may be used without charge for any lawful purpose so long as you do not: 1) claim it is your own (e.g., by claiming copyright for NWS information -- see below), 2) use it in a manner that implies an endorsement or affiliation with NOAA/NWS, or 3) modify its content and then present it as official government material.

The selected NHC advisory text is identified here as incorporated NWS material
and is not subject to a copyright claim by this project. The NWS policy also
distinguishes third-party information, protected names and visual identifiers,
and external mapping products; this notice does not grant rights in those items.
The policy page is not copied into the source dataset. Its retrieved HTML SHA256
was `2de6e0d8719c50de2dc7f53ca1fb5287eec08c23603fc44b59807e06f992ef4d`.

The dynamic examples preserve the advisory text while using explicitly controlled
delivery schedules and project-defined task rules. These schedules, extracted
fields, references, and rules are project derivatives and must not be presented
as new official NHC releases, historical first-publication evidence, NOAA/NWS
endorsements, or operational emergency instructions.

## Other references and dependencies

EarthVerse, STATE-Bench, STALE, ExtremeWeatherBench, and other repositories in the
adjacent research snapshots informed the broader plan. Their datasets, scoring
code, and model runners are not incorporated into this automated work package.
Keeping a research reference snapshot does not relicense its contents.

The original starter's Python dependencies retain their own licenses and notices.
This document records the source-specific reuse above; it is not an exhaustive
software dependency license inventory. No upstream license is replaced by this
document or by a future license applied to newly written project code.
