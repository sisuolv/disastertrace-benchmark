# Offline dataset audit, version 1

`disastertrace.automated.dataset_audit.audit_dataset(build_path)` audits the
frozen NHC cohort without network access or model calls. It returns a JSON-safe
report with the build ID, explicit Boolean checks, frozen method parameters,
descriptive coverage and size results, and a canonical SHA-256 digest. The caller
decides where to save that report; the audit does not change any build artifact.

## Exact and lexical similarity

Every parsed report participates, including parsed sources from events that
failed complete-triple admission. Each parsed source ID appears once: repeated
deliveries and paired branches are not counted as additional source documents.
The acquisition inventory supplies a separate exact text-hash screen covering
rejected reports, whose raw text is not included in the build's parsed records.

Exact duplicates compare SHA-256 of UTF-8 raw report text. Normalized duplicates
compare SHA-256 after Python `str.casefold()`, Unicode whitespace splitting, and
joining with one ASCII space. These operations are analysis copies only. Original
text, labels, admission decisions, parser, and event split remain unchanged.

The fixed near-duplicate screen tokenizes the full raw report with
`re.findall(r'[a-z0-9]+', raw_text.casefold())`, takes the set of consecutive
five-word tuples, and computes Jaccard similarity as intersection size divided
by union size. Numbers remain in tokens. An empty union produces `null`, not a
perfect match. The threshold is 0.9. Exact and normalized matches are reported
separately and cannot be reclassified as harmless template matches.

Each non-exact candidate includes the exact intersection and union counts,
source IDs, event IDs, splits, differences in available report metadata, and the
fraction of shared shingles occurring in at least three distinct parsed storm
events. This common-text measure is descriptive context: common words are not
removed from the similarity computation. Metadata differences and common text
do not establish either leakage or harmless boilerplate. No candidate requires
new human annotation or automatically changes admission.

The public task template is hashed separately using only protocol, instruction,
required fields, and public policy. A shared task template is expected. It means
the heldout split tests different events under the same task format; it does not
make all source reports duplicates.

## Coverage, integrity, and input size

The audit reports planned, parsed, used, rejected, and orphan sources separately.
It preserves the planned/admitted event map, event names, year counts, dependent
base/delay branches, and original rejection reasons. Manifest hashes are checked
before use, and every audit input must be declared in that manifest. Parsed raw
hashes and source metadata are compared with the acquisition inventory. Episode
records, paired branches, split assignments, and reference/checkpoint sets are
also checked. Artifact consistency does not authenticate the remote server or
prove scientific truth.

Input sizes are measured by rendering each checkpoint's public request with
`previous_state=None`. Evidence counts include repeated delivery of old reports
because the current protocol actually includes those texts. The report records
numbered evidence characters, canonical request characters, and UTF-8 bytes.
The model's actual previous carrier and provider message envelope add size, so
these are not maximum provider request sizes or tokenizer/context guarantees.

The auditor separately reads frozen private references to count the public
research rule's actions and checks them against the existing episode contract.
These references are never supplied to the public request renderer as a carrier.
The action distribution is descriptive: it does not tune the policy or labels.

## Acceptance and limits

Cross-split exact or normalized duplicates fail explicit checks, as do detected
integrity/assignment inconsistencies. Near-duplicate candidates remain descriptive
findings without an automatic failure or exclusion rule. The report exposes both
per-check values and `all_required_checks_pass` for preflight integration.

This audit does not measure or rule out model pretraining contamination. It does
not turn public archived reports into secret heldout data. The purposeful small
Atlantic tropical-cyclone cohort does not establish representative or cross-hazard
extreme-weather coverage. Controlled release time is not verified historical
availability, and paired branches remain dependent observations of one storm.
