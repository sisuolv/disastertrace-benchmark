# NHC forecast source verification v1

This is a source-validation milestone. It does not yet define or execute a new
LLM forecast task, replace the controlled P6 tasks, or measure forecasting skill.
The model matrix completes its audit before this bundle performs network acquisition.

## Bounded selection

Exactly twelve forecast-advisory bodies are planned: Francine AL062024 advisories
005-010 and Ida AL092021 advisories009-014. Each source has one acquisition attempt;
HTTP failures remain in the twelve-body denominator without replacement. URLs,
source paths, response-size limit and all source code are frozen in SOURCE_SCOPE.json.

The old catalogue declares eight heldout storms, of which seven were admitted in
the original pipeline. All eight declared IDs are protected. Ian AL092022 is
mentioned in supplied plan examples but remains heldout; its plan exposure is
recorded and it is not acquired here. Francine is explicitly development after
plan exposure. Ida was already development. A different NHC product for Ida is
not an additional independent storm. Development status makes no claim about
pretraining decontamination.

## Distinct time quantities

| Quantity | Meaning | Rule |
| --- | --- | --- |
| issued_at | UTC timestamp in the official advisory header | Parse and validate the calendar weekday |
| center_at | Timestamp explicitly attached to the center-location statement | Within six hours before issue, not inferred from advisory number |
| valid_at | Absolute timestamp of each FORECAST/OUTLOOK VALID block | Resolve the day against the calendar, including month/year rollover |
| lead_hours_from_center | Derived difference valid_at minus center_at | A derived interval, not a claimed NHC model-initialization lead |
| initialization_at | Model/synoptic initialization time | Null because this product does not establish it |
| retrieved_at | Time these archive bytes were fetched | Acquisition provenance only |
| available_at | Proven historical first public availability | Null; neither issue nor retrieval establishes it |

The first published forecast row need not be twelve hours after the center time.
Only matching storm ID and identical absolute valid_at form a revision key.
Two rows both described as +24 hours from different references do not match.

## Measurements and independent parsing

The initial measurement fields are latitude, longitude and maximum sustained
wind in KT. Hemisphere signs are explicit. Gusts and location qualifiers are
retained as source information and are not substituted for sustained wind.
Current position, motion speed, observed intensity, wind radii and current
pressure are separate material. No forecast pressure is invented.

Parser A extracts a PRE block using a byte regex, recognizes product blocks with
regexes, and resolves times using adjacent calendar-month candidates. Parser B
uses an independent HTMLParser, token-based header/block selection and enumerated
day candidates. They do not share heading selection or time-resolution code.
Admission requires exact agreement, including source line references. Failure,
ambiguity, identity mismatch or disagreement produces an automatic quarantine
record; neither parser is preferred and no LLM or per-item human judge resolves it.

DISSIPATED/ABSORBED terminal rows retain their explicit status and null numeric
values. The latest-covering utility means the latest explicit row for the exact
key before an issue cutoff. It is a document-claim resolver; it does not infer a
continuous physical forecast, interpolate missing times, or propagate terminal
status to unstated future horizons. Such semantics require a later task contract.

## Provenance and exports

Every response retains its URL, final URL, HTTP status, fetch time, selected
response headers, raw bytes and SHA-256. PRE normalization records UTF-8 decoding,
HTML entity expansion and CRLF-to-LF conversion. Each canonical line maps to an
exact raw-byte interval and raw-line hash. Raw acquisition is sealed before review.

The raw export keeps every canonical source line. The normalized export partitions
those same lines into measured-support and other-source lines and adds derived
columns. Sorting and restoring its lines must reproduce the complete canonical
text byte for byte. Observed pressure, radii and other nuisance information are
therefore retained in both exports. These are source-review exports, not an
already-executed pure raw-versus-table model comparison or a token-matched carrier
experiment. Derived parsing can itself assist an LLM and must be labelled in any
future comparison.

Two parsers of one advisory are not two independent weather sources. Twelve
advisories from two storms are not twelve independent events. Agreement lowers
implementation risk but cannot establish universal parser correctness.

## Validation and next task boundary

26 CPU tests pass, including one deterministic Hypothesis test with up to80
examples. Tests cover UTC month/year rollovers, hemisphere signs, incorrect units,
gust/observation/motion confusion, wrong weekdays, invalid timestamps, classified
and repeated center statements, terminal rows, same-valid pairing, a later
document that lacks the requested key, HTTP failure retention, heldout/path/URL
scope tampering and lossless source exports. Failed implementation-stage tests
remain recorded. This is automated software validation, not human Gold annotation.

After real acquisition, report all twelve planned bodies, admitted/quarantined
counts, forecast rows, matching-valid-time version pairs and actual changes.
Preserve raw bytes when refining a generic parser; use a new review version and
never overwrite earlier quarantine or consensus results. No source-stage model
inference is authorized by the mere existence of automatically parsed columns.

The next LLM task must freeze its public input, event split, exact-valid-time query,
evidence citation format, missing/terminal semantics, scorer and context budget.
Raw and derived input tracks must be labelled separately. Only then should a new
bounded model matrix or carrier-representation study be specified.
