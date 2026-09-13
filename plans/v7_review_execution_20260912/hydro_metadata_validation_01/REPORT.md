# Official H08 gauge-metadata preflight

All three existing NWS-to-USGS site mappings match current official NWPS metadata.
Native unavailable values remain explicit; stage and discharge are separate variables.

| NWS gauge | USGS site | Action stage, ft | Minor flood stage, ft | Minor flow threshold, cfs |
| --- | --- | ---: | ---: | --- |
| NRWI4 | 05486000 | 17 | 22 | None (raw -9999) |
| CRHA2 | 15493400 | 15.2 | 17.2 | None (raw -9999) |
| SCOC1 | 11477000 | 45 | 51 | None (raw -9999) |

The old QINE/CFS chain remains a discharge task. A flood-stage task requires matched stage forecasts, observations, datum and threshold-history evidence.
CRHA2 metadata notes seasonal ice effects; all datum and quality notes remain in REPORT.json and original payloads.
No flood labels, historical threshold validity or new monitoring admission are inferred from this metadata sample.
