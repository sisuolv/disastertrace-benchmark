# Third-party inputs in this private review snapshot

This is the existing private research repository, not a new public dataset
release. Data access, technical integrity and permission for subsequent public
redistribution remain separate. No model weights or account credentials are added.

- Aviation records are native NWS TAF/METAR retrieved through IEM. IEM is a delivery
  service, not an independent observation source. NOAA LAMP/LAV native archive and
  NOMADS text/BUFR samples retain their source URLs and timing limits.
- CNRFC historical HEFS and USGS Approved samples retain exact product, parameter,
  station and timestamp identities. Timestamp joins do not establish instantaneous
  versus hourly-mean or regulated versus unregulated equivalence.
- EUPPBench station forecasts identify CC BY 4.0. DWD station observations retain
  separate source-policy/attribution requirements; the EUPP software license is not
  assumed to cover all countries' observation redistribution terms.
- SEEPS4ALL identifies CC BY-NC terms; its ECA&D policy and source transformations
  are retained. This snapshot does not remove noncommercial conditions or claim
  that per-station physical accumulation windows and QC reasons are resolved.
- The CPU replay includes the pinned Qwen3-8B tokenizer, model card/configuration
  and available Apache 2.0 license files, without weights. Third-party runtime
  packages are referenced by version, not newly vendored as installed environments.

Authoritative source-specific qualifications accompany
`plans/v7_execution_20260913/sources_lamp/`, `sources_numerical/` and `hydrology/`.
Earlier publication notices remain applicable to unchanged older evidence.
