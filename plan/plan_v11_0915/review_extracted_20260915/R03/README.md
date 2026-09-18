# DisasterTrace v10 reviewer pack

This is an independent **limited source review and synthetic CPU test pack**, not
the repository's full scientific replay capsule.

Read `IMPLEMENTATION_REVIEW_CN.md` and `CODEX_V10_FOLLOWUP_PLAN_CN.md`.
`CODEX_WORK_ITEMS.json` contains the dependency/acceptance list.

Run `python reviewer_checks.py` to verify the four source blob identities and
34 reviewer-authored CPU checks, then reproduce four boundary probes.
Run `python propose_temperature_guard_fix.py` only for the local candidate patch
validation; it writes under `proposed/`, never changes a checkout or GitHub.
No network, API, model, cloud, or historical launchers are invoked by these scripts.
Python 3.10+ standard library is sufficient.

Three source modules are imported in full; feature_tasks contributes one exact
function AST to isolate numeric contract behavior. No claim is made to have run
all its dependencies, FormalSession, the 720 upstream tests, full journals, model
re-generation, or the author's two portable capsules.

The patch is a proposal. Its full package imports and integration tests must be
checked in the actual project. Sources remain pinned to 1fd6821f.
