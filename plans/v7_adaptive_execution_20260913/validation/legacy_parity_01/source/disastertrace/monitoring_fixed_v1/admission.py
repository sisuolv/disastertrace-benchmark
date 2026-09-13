"""Typed cutoff admission, driven by the existing session clock.

The trusted controller records events; a model cannot supply its own admission
time. Archive scenarios explicitly map measured durations to a declared clock.
Hash chains prove replay integrity, not upstream historical public availability.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from ..monitoring_v1.event_loop import run_clock
from ..monitoring_v1.journal import read_journal
from ..monitoring_v1.resources import Cost
from .contracts import (
    EvidenceBundle,
    Forecast,
    ForecastState,
    Target,
    canonical,
    fingerprint,
    paired_scores,
    require_fields,
    timestamp,
)
from .heads import _reject_constant, _unique_object, parse_response

PHASES = {
    "baseline": 0,
    "completion": 1,
    "cancel": 1,
    "begin": 5,
    "follow": 5,
    "prepare": 5,
    "cancel_preparation": 1,
}


@dataclass(frozen=True)
class TypedOpportunity:
    opportunity_id: str
    target: Target
    cutoff: int

    def __post_init__(self):
        if not self.opportunity_id:
            raise ValueError("Opportunity ID required")
        self.target.check_cutoff(self.cutoff)

    def to_dict(self):
        return {
            "opportunity_id": self.opportunity_id,
            "target": self.target.to_dict(),
            "cutoff": self.cutoff,
        }


@dataclass(frozen=True)
class AdmissionEvent:
    event_id: str
    time: int
    kind: str
    payload: dict

    def __post_init__(self):
        timestamp(self.time)
        if not self.event_id or self.event_id.startswith("__") or self.kind not in PHASES:
            raise ValueError("Invalid admission event")
        canonical(self.payload)

    def to_dict(self):
        return {
            "event_id": self.event_id,
            "time": self.time,
            "kind": self.kind,
            "payload": json.loads(canonical(self.payload)),
        }


def baseline_context(bundle):
    row = bundle.policy_view()
    base = row["baseline"]
    content = base["content"]
    if row["provider_version"] == "native_h15_snapshot.v1":
        # All target-applicable conditions matter, even when the scalar is equal.
        # Bulletin wrapping, mirrors and the independent E question do not.
        content = {
            "projection": content["native_taf"]["projection"],
            "mapping_details": content["mapping_details"],
            "calibration_bank_sha256": content["calibration_bank_sha256"],
        }
    return fingerprint(
        {
            "target": Target(**row["target"]).contract_hash,
            "forecast": base["forecast"],
            "content": content,
            "valid_until": base["valid_until"],
            "kind": base["kind"],
            "mapping_version": base["mapping_version"],
            "context_rule": row["provider_version"],
        }
    )


class AdmissionEngine:
    def __init__(
        self,
        opportunities,
        *,
        fallbacks,
        protocol="base_bound_override",
        time_basis="declared_archive_scenario",
        journal=None,
        preparation=None,
    ):
        opportunities = list(opportunities)
        self.opportunities = {o.opportunity_id: o for o in opportunities}
        if not opportunities or len(self.opportunities) != len(opportunities):
            raise ValueError("Nonempty unique opportunity registry required")
        self.targets = {}
        for o in opportunities:
            if o.target.target_id in self.targets and self.targets[o.target.target_id] != o.target:
                raise ValueError("Target ID collision")
            self.targets[o.target.target_id] = o.target
        if time_basis not in {
            "declared_archive_scenario",
            "observed_first_seen",
            "documented_historical_release",
        }:
            raise ValueError("Explicit clock basis required")
        self.protocol, self.time_basis = protocol, time_basis
        self.fallbacks = json.loads(canonical(fallbacks))
        if set(self.targets) != set(fallbacks):
            raise ValueError("Frozen fallback required for every target")
        self.states = {}
        for tid, target in self.targets.items():
            target.check_forecast(Forecast(**fallbacks[tid]))
            self.states[tid] = ForecastState(target, protocol)
        self.baselines, self.calls, self.snapshots, self.attempts = {}, {}, {}, []
        self._events, self._processed, self._last_time = {}, set(), None
        self.journal = journal
        self.contract = {
            "schema": "disastertrace.typed_admission.v1",
            "protocol": protocol,
            "time_basis": time_basis,
            "opportunities": [o.to_dict() for o in opportunities],
            "fallbacks": self.fallbacks,
        }
        self.preparation = None
        if preparation is not None:
            from ..monitoring_v1.preparation import PreparationReducer

            self.preparation = PreparationReducer(preparation)
            if any(job["target_id"] not in self.targets for job in self.preparation.jobs.values()):
                raise ValueError("Preparation references an unknown target")
            self.contract["preparation"] = self.preparation.card
        self.contract_hash = fingerprint(self.contract)
        if journal is not None:
            if journal.records:
                raise ValueError("Fresh admission journal required; restore explicitly")
            journal.append("__contract", self.contract)

    def _open(self, tid, at):
        return any(
            o.target.target_id == tid and o.cutoff >= at and oid not in self.snapshots
            for oid, o in self.opportunities.items()
        )

    def _refresh(self, tid, at):
        base = self.baselines.get(tid)
        state = self.states[tid]
        if base is None or at >= base["valid_until"]:
            context = fingerprint(
                {"target": self.targets[tid].contract_hash, "fallback": self.fallbacks[tid]}
            )
            if state.base_hash != context and self._open(tid, at):
                state.update_baseline(Forecast(**self.fallbacks[tid]), context, at)
        if state.override is not None and at > state.expires_at:
            state.follow(at)

    def _process(self, event):
        p, at = event.payload, event.time
        if event.kind in {"prepare", "cancel_preparation"}:
            if self.preparation is None:
                raise ValueError("Preparation scenario not enabled")
            action = (
                self.preparation.request if event.kind == "prepare" else self.preparation.cancel
            )
            action(p["job_id"], at)
            return
        if event.kind == "baseline":
            bundle = EvidenceBundle.restore(p["bundle"])
            row, base = bundle.policy_view(), bundle.policy_view()["baseline"]
            tid = row["target"]["target_id"]
            if tid not in self.targets or Target(**row["target"]) != self.targets[tid]:
                raise ValueError("Unknown baseline target")
            if base["available_at"] != at or row["availability_basis"] != self.time_basis:
                raise ValueError("Baseline availability/clock mismatch")
            if not self._open(tid, at):
                self.attempts.append({"event_id": event.event_id, "status": "closed_target"})
                return
            self.states[tid].update_baseline(
                Forecast(**base["forecast"]), baseline_context(bundle), at
            )
            self.baselines[tid] = base
            return
        if event.kind == "begin":
            status = "begun"
            try:
                require_fields(p, "call_id bundle head executor", "begin")
                if not p["call_id"] or p["call_id"] in self.calls or not p["executor"]:
                    raise ValueError("Nonunique call ID/executor")
                if p["head"] not in {"program", "e_only", "f_only", "joint"}:
                    raise ValueError("Unknown head")
                bundle = EvidenceBundle.restore(p["bundle"])
                row = bundle.policy_view()
                tid = row["target"]["target_id"]
                opportunity = self.opportunities[row["opportunity_id"]]
                if (
                    opportunity.target != Target(**row["target"])
                    or opportunity.cutoff != row["cutoff"]
                    or row["opportunity_id"] in self.snapshots
                    or at >= row["cutoff"]
                    or row["availability_basis"] != self.time_basis
                ):
                    raise ValueError("Input opportunity closed or mismatched")
                latest_input = max(
                    [row["baseline"]["available_at"]]
                    + [a["completed_at"] for a in row["assets"]]
                    + [r["completed_at"] for r in row["receipts"]]
                )
                if latest_input > at:
                    raise ValueError("Input not visible at begin")
                self._refresh(tid, at)
                state = self.states[tid]
                mode = "FOLLOW" if state.override is None else "OVERRIDE"
                if (
                    baseline_context(bundle) != state.base_hash
                    or row["state"]["forecast"] != state.effective(at).to_dict()
                    or row["state"]["mode"] != mode
                    or row["state"]["protocol"] != self.protocol
                ):
                    raise ValueError("Input baseline/current state mismatch")
                self.calls[p["call_id"]] = {
                    **p,
                    "target_id": tid,
                    "began_at": at,
                    "context_hash": state.base_hash,
                    "visible_view_hash": fingerprint(row),
                    "completed": False,
                    "canceled": False,
                }
            except (ValueError, KeyError, TypeError) as exc:
                status = "invalid_begin"
                self.attempts.append(
                    {"event_id": event.event_id, "status": status, "error": str(exc)}
                )
            return
        if event.kind == "cancel":
            call = self.calls.get(p["call_id"])
            if call is None:
                raise ValueError("Cannot cancel missing call")
            call["canceled"] = True
            return
        if event.kind == "follow":
            tid = p["target_id"]
            if tid not in self.targets:
                raise ValueError("Unknown control target")
            status = "follow" if self._open(tid, at) else "closed_target"
            if status == "follow":
                self.states[tid].follow(at)
            self.attempts.append({"event_id": event.event_id, "time": at, "status": status})
            return
        call = self.calls.get(p.get("call_id"))
        attempt = {"event_id": event.event_id, "time": at, **p}
        if call is None:
            status = "missing_begin"
        elif call["completed"]:
            status = "duplicate_completion"
        else:
            try:
                require_fields(
                    p,
                    "call_id bundle_hash raw raw_sha256 started_at completed_at "
                    "persisted_at expires_at cost ended_with_eos head executor",
                    "receipt",
                )
                for name in ("started_at", "completed_at", "persisted_at", "expires_at"):
                    timestamp(p[name])
                require_fields(p["cost"], "requests bytes tokens compute_ms", "actual cost")
                Cost(**p["cost"])
                if (
                    p["started_at"] != call["began_at"]
                    or not p["started_at"] < p["completed_at"] <= p["persisted_at"] == at
                    or p["bundle_hash"] != call["bundle"]["bundle_hash"]
                    or hashlib.sha256(p["raw"].encode()).hexdigest() != p["raw_sha256"]
                    or p["head"] != call["head"]
                    or p["executor"] != call["executor"]
                ):
                    raise ValueError("Receipt does not bind begin, raw response and persistence")
            except (ValueError, KeyError, TypeError, AttributeError) as exc:
                status = "invalid_receipt"
                attempt["error"] = str(exc)
            else:
                tid = call["target_id"]
                self._refresh(tid, at)
                if call["canceled"]:
                    status = "canceled"
                elif not self._open(tid, at):
                    status = "late"
                elif at > p["expires_at"]:
                    status = "expired_lifetime"
                else:
                    try:
                        if p["ended_with_eos"] is not True:
                            raise ValueError("Response unfinished")
                        if call["head"] == "program":
                            forecast = Forecast(
                                **json.loads(
                                    p["raw"],
                                    object_pairs_hook=_unique_object,
                                    parse_constant=_reject_constant,
                                )
                            )
                            self.targets[tid].check_forecast(forecast)
                        else:
                            answer = parse_response(
                                p["raw"], EvidenceBundle.restore(call["bundle"]), call["head"]
                            )
                            forecast = answer.forecast
                            attempt["fact_truth"] = answer.fact_truth
                    except (ValueError, TypeError, OverflowError) as exc:
                        status = "invalid_response"
                        attempt["error"] = str(exc)
                    else:
                        status = (
                            "e_only_recorded"
                            if forecast is None
                            else self.states[tid].propose(
                                forecast, call["context_hash"], at, p["expires_at"]
                            )
                        )
                        if forecast is not None:
                            attempt["candidate_forecast"] = forecast.to_dict()
                        if status == "accepted":
                            self.states[tid].admitted_call_id = p["call_id"]
            call["completed"] = True
        attempt["status"] = status
        self.attempts.append(attempt)

    def _expiry_times(self, upcoming):
        if self.preparation is not None:
            yield from self.preparation.boundaries(upcoming)
        for event in upcoming:
            if event.kind == "baseline":
                yield event.payload["bundle"]["payload"]["baseline"]["valid_until"]
            if event.kind == "completion" and type(event.payload.get("expires_at")) is int:
                yield event.payload["expires_at"]
        for base in self.baselines.values():
            yield base["valid_until"]
        for state in self.states.values():
            if state.expires_at is not None:
                yield state.expires_at

    def _invalidate(self, at):
        for tid in self.targets:
            self._refresh(tid, at)
        if self.preparation is not None:
            self.preparation.progress(at)

    def _seal(self, at):
        if self.preparation is not None:
            self.preparation.seal(at)
        prefix = [
            r
            for r in self._events.values()
            if r["time"] < at or (r["time"] == at and PHASES[r["kind"]] <= 1)
        ]
        prefix.sort(key=lambda r: (r["time"], PHASES[r["kind"]], r["event_id"]))
        for oid, o in sorted(self.opportunities.items()):
            if o.cutoff != at or oid in self.snapshots:
                continue
            tid, state = o.target.target_id, self.states[o.target.target_id]
            base = self.baselines.get(tid)
            active_base = base is not None and at < base["valid_until"]
            self.snapshots[oid] = {
                "opportunity_id": oid,
                "target": o.target.to_dict(),
                "cutoff": at,
                "forecast": state.effective(at).to_dict(),
                "base_forecast": state.baseline.to_dict(),
                "mode": "FOLLOW" if state.override is None else "OVERRIDE",
                "override_call_id": None if state.override is None else state.admitted_call_id,
                "baseline_context_hash": state.base_hash,
                "baseline_kind": base["kind"] if active_base else "fallback",
                "protocol": self.protocol,
                "time_basis": self.time_basis,
                "prefix_sha256": fingerprint({"contract": self.contract_hash, "events": prefix}),
            }

    def _after_seal(self, at):
        if self.preparation is not None:
            self.preparation.after_seal(at)
        for state in self.states.values():
            if state.override is not None and at >= state.expires_at:
                state.follow(at)

    def run(self, events, *, until=None):
        if until is not None:
            timestamp(until)
            if self._last_time is not None and until < self._last_time:
                raise ValueError("Cannot reverse admission clock")
        result = run_clock(
            self, events, until=until, event_order=PHASES, decode=lambda r: AdmissionEvent(**r)
        )
        if self.preparation is not None:
            self.preparation.progress(self._last_time)
        if self.journal is not None:
            self.journal.append(
                "__advance_" + str(len(self.journal.records)),
                {
                    "schema": "disastertrace.admission_advance.v1",
                    "until": self._last_time,
                    "snapshots_sha256": fingerprint(self.snapshots),
                    "attempts_sha256": fingerprint(self.attempts),
                    **(
                        {"preparation_sha256": fingerprint(self.preparation.to_dict())}
                        if self.preparation is not None
                        else {}
                    ),
                },
            )
        return result

    @classmethod
    def from_journal(cls, path):
        if not isinstance(path, (str, bytes)) and not hasattr(path, "__fspath__"):
            raise ValueError("Formal scores require a durable journal path")
        journal = read_journal(path)
        if journal.incomplete_tail or not journal.records:
            raise ValueError("Complete journal required for scoring")
        contract = journal.records[0]["payload"]
        if contract.get("schema") != "disastertrace.typed_admission.v1":
            raise ValueError("Wrong admission contract")
        engine = cls(
            [
                TypedOpportunity(r["opportunity_id"], Target(**r["target"]), r["cutoff"])
                for r in contract["opportunities"]
            ],
            fallbacks=contract["fallbacks"],
            protocol=contract["protocol"],
            time_basis=contract["time_basis"],
            preparation=contract.get("preparation"),
        )
        pending = []
        for entry in journal.records[1:]:
            row = entry["payload"]
            if row.get("schema") == "disastertrace.admission_advance.v1":
                engine.run(pending, until=row["until"])
                pending = []
                if (
                    fingerprint(engine.snapshots) != row["snapshots_sha256"]
                    or fingerprint(engine.attempts) != row["attempts_sha256"]
                ):
                    raise ValueError("Replay differs from committed cutoff state")
                if engine.preparation is not None and fingerprint(
                    engine.preparation.to_dict()
                ) != row.get("preparation_sha256"):
                    raise ValueError("Preparation replay differs from committed state")
            else:
                pending.append(AdmissionEvent(**row))
        if pending:
            raise ValueError("Journal has uncommitted clock events")
        return engine


def score_admitted(outcomes, arms):
    engines = {name: AdmissionEngine.from_journal(path) for name, path in arms.items()}
    if not engines:
        raise ValueError("No admitted arms")
    first = next(iter(engines.values()))
    for engine in engines.values():
        if engine.contract != first.contract or set(engine.snapshots) != set(first.opportunities):
            raise ValueError("All arms need the same full sealed opportunity contract")
        if engine.calls and {c["head"] for c in engine.calls.values()} == {"e_only"}:
            raise ValueError("E-only calls are not a forecasting arm")
    results = {r["opportunity_id"]: r for r in outcomes}
    if len(results) != len(outcomes) or set(results) != set(first.opportunities):
        raise ValueError("Every opportunity needs an explicit outcome or missing status")
    rows = []
    for oid, o in first.opportunities.items():
        outcome = results[oid]
        require_fields(
            outcome, "opportunity_id target_contract_hash value status source_revision", "outcome"
        )
        if outcome["target_contract_hash"] != o.target.contract_hash:
            raise ValueError("Outcome target mismatch")
        if outcome["status"] not in {"mature", "provisional", "missing"}:
            raise ValueError("Unknown maturity status")
        if outcome["status"] == "mature" and (
            outcome["value"] is None or not outcome["source_revision"]
        ):
            raise ValueError("Mature outcome needs value and revision")
        rows.append(
            {
                "opportunity_id": oid,
                "target": o.target.to_dict(),
                "outcome": outcome["value"] if outcome["status"] == "mature" else None,
            }
        )
    return {
        "schema": "disastertrace.admitted_scores.v1",
        "contract_sha256": first.contract_hash,
        "time_basis": first.time_basis,
        "outcome_sha256": fingerprint(outcomes),
        "scores": paired_scores(
            rows,
            {
                name: {oid: s["forecast"] for oid, s in engine.snapshots.items()}
                for name, engine in engines.items()
            },
        ),
        "admission_statuses": {
            name: [r["status"] for r in engine.attempts] for name, engine in engines.items()
        },
    }
