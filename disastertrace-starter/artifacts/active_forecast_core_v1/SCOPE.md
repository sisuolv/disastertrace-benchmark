# Active Forecast core v1: D1-D2 execution

This is a new engineering milestone following the closed V5 feasibility study.
The governing roadmap is `../../../plans/v5_0910_feasibility_12h_20260910/FINAL_PLAN_CN.md`.

Deliver a typed, versioned `disastertrace.active_forecast` package with exact
arithmetic, explicit product/support/availability/capture/delivery clocks,
verifiable source locators, deterministic evidence certificates and scoring,
and a whitelist public projection. Preserve the prototype and historical scores.

Acceptance: regression tests precede implementation; replay all 104 frozen
development episodes and their legal read subsets; compare decisions,
certificates and score fields with the frozen prototype; reject malformed new
inputs explicitly. Bind imported facts to frozen JSON and original captures.
Historical availability that was not proved remains null. Archive delivery is
a logical step and must never be converted into an invented historical timestamp.

This milestone uses CPU only. No dataset expansion, new model inference, training,
heldout access or paid API calls are needed. Existing four-H100 authorization
continues for later protocol-frozen model work. D2-D3 grouping/admission and data
expansion remain subsequent milestones.

Only `IMPLEMENTATION_STATUS.md` is an intended modification to existing files.
New code, tests, documentation and execution artifacts use new paths.
