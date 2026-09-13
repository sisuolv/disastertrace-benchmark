"""Single-writer deterministic archive clock and version-scoped predictions."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field

from .targets import Opportunity, TargetSpec, canonical_hash


@dataclass(frozen=True)
class Baseline:
    target: TargetSpec
    product_revision_id: str
    relevant_content: dict
    probability: float
    released_at: int
    valid_until: int
    calibrator_version: str
    source_id: str
    baseline_kind: str = "professional"
    _content_json: str = field(init=False, repr=False)

    def __post_init__(self):
        if not _valid_probability(self.probability) or self.valid_until < self.released_at:
            raise ValueError("Invalid baseline probability or lifetime")
        if (
            self.baseline_kind not in {"professional", "research", "fallback"}
            or not self.calibrator_version
            or not self.source_id
        ):
            raise ValueError("Baseline identity and probability mapping required")
        object.__setattr__(
            self,
            "_content_json",
            json.dumps(self.relevant_content, sort_keys=True, allow_nan=False),
        )

    @property
    def context_hash(self):
        return canonical_hash(
            {
                "target_contract": self.target.contract_hash,
                "content": json.loads(self._content_json),
                "probability": self.probability,
                "valid_until": self.valid_until,
                "calibrator": self.calibrator_version,
                "source": self.source_id,
                "kind": self.baseline_kind,
            }
        )

    def policy_view(self):
        return {
            "target_id": self.target.target_id,
            "target_contract_hash": self.target.contract_hash,
            "product_revision_id": self.product_revision_id,
            "context_hash": self.context_hash,
            "relevant_content": json.loads(self._content_json),
            "probability": self.probability,
            "released_at": self.released_at,
            "valid_until": self.valid_until,
            "calibrator_version": self.calibrator_version,
            "source_id": self.source_id,
            "baseline_kind": self.baseline_kind,
        }

    def to_dict(self):
        return {
            "target": asdict(self.target),
            "product_revision_id": self.product_revision_id,
            "relevant_content": json.loads(self._content_json),
            "probability": self.probability,
            "released_at": self.released_at,
            "valid_until": self.valid_until,
            "calibrator_version": self.calibrator_version,
            "source_id": self.source_id,
            "baseline_kind": self.baseline_kind,
        }


def _valid_probability(value):
    return type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1


def _encode(value):
    if isinstance(value, Baseline):
        return {"__baseline__": value.to_dict()}
    if isinstance(value, float) and not math.isfinite(value):
        return "invalid_nonfinite_probability:" + str(value)
    if isinstance(value, dict):
        return {k: _encode(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_encode(v) for v in value]
    return value


def _decode(value):
    if isinstance(value, dict) and set(value) == {"__baseline__"}:
        data = dict(value["__baseline__"])
        data["target"] = TargetSpec(**data["target"])
        return Baseline(**data)
    if isinstance(value, dict):
        return {k: _decode(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_decode(v) for v in value]
    return value


EVENT_ORDER = {
    "baseline": 0,
    "baseline_withdrawal": 0,
    "candidate": 1,
    "cancel": 1,
    "begin": 5,
    "follow": 5,
    "no_change": 5,
    "action": 5,
}


@dataclass(frozen=True)
class Event:
    event_id: str
    time: int
    kind: str
    payload: dict

    def __post_init__(self):
        if self.kind not in EVENT_ORDER or not self.event_id or type(self.time) is not int:
            raise ValueError("Invalid event identity/time/kind")

    def to_dict(self):
        return {
            "event_id": self.event_id,
            "time": self.time,
            "kind": self.kind,
            "payload": _encode(self.payload),
        }


class MonitoringEngine:
    def __init__(
        self, opportunities, *, fallback_probabilities, protocol="base_bound_override", journal=None
    ):
        if protocol not in {"base_bound_override", "persistent_override"}:
            raise ValueError("Unknown override protocol")
        self.opportunities = {o.opportunity_id: o for o in opportunities}
        if len(self.opportunities) != len(opportunities):
            raise ValueError("Duplicate opportunity")
        self.targets = {}
        for opportunity in opportunities:
            target = opportunity.target
            if target.target_id in self.targets and self.targets[target.target_id] != target:
                raise ValueError("Target identity collision")
            self.targets[target.target_id] = target
        self.fallbacks = dict(fallback_probabilities)
        if set(self.fallbacks) != set(self.targets) or not all(
            _valid_probability(p) for p in self.fallbacks.values()
        ):
            raise ValueError("Every target requires a frozen fallback")
        self.protocol = protocol
        self.journal = journal
        self.baselines = {}
        self.overrides = {}
        self.calls = {}
        self.actions = {}
        self.snapshots = {}
        self.attempts = []
        self.audit = []
        self._events = {}
        self._processed = set()
        self._last_time = None

    def _base(self, target_id, time):
        baseline = self.baselines.get(target_id)
        if baseline is not None and baseline.released_at <= time <= baseline.valid_until:
            return baseline.policy_view()
        probability = self.fallbacks[target_id]
        return {
            "target_id": target_id,
            "probability": probability,
            "baseline_kind": "fallback",
            "context_hash": canonical_hash(
                {
                    "target": self.targets[target_id].contract_hash,
                    "fallback_probability": probability,
                }
            ),
            "relevant_content": {},
            "product_revision_id": "frozen_fallback",
        }

    def _open(self, target_id, time):
        return any(
            o.target.target_id == target_id
            and o.cutoff >= time
            and o.opportunity_id not in self.snapshots
            for o in self.opportunities.values()
        )

    def policy_state(self, target_id, time):
        baseline = self._base(target_id, time)
        override = self.overrides.get(target_id)
        if override is not None and (
            time > override["expires_at"]
            or (
                self.protocol == "base_bound_override"
                and override["context_hash"] != baseline["context_hash"]
            )
        ):
            override = None
        return {
            "target_id": target_id,
            "mode": "follow" if override is None else "override",
            "probability": baseline["probability"] if override is None else override["probability"],
            "active_override": None if override is None else dict(override),
            "protocol": self.protocol,
        }

    def _end_override(self, target_id, time, reason):
        if target_id not in self.overrides:
            return
        previous = self.overrides.pop(target_id)
        self.audit.append(
            {
                "time": time,
                "kind": "override_end",
                "target_id": target_id,
                "call_id": previous["call_id"],
                "reason": reason,
            }
        )

    def _invalidate(self, time):
        for target_id, override in list(self.overrides.items()):
            if time > override["expires_at"]:
                self._end_override(target_id, time, "expired_lifetime")
            elif (
                self.protocol == "base_bound_override"
                and override["context_hash"] != self._base(target_id, time)["context_hash"]
            ):
                self._end_override(target_id, time, "expired_base_context")

    def _process(self, event):
        time, payload = event.time, event.payload
        if event.kind == "baseline":
            baseline = payload["baseline"]
            target_id = baseline.target.target_id
            if (
                target_id not in self.targets
                or self.targets[target_id].contract_hash != baseline.target.contract_hash
            ):
                self.audit.append(
                    {"event_id": event.event_id, "kind": "rejected_baseline_target_mismatch"}
                )
                return
            if baseline.released_at != time:
                raise ValueError("Release event must match baseline availability")
            self.baselines[target_id] = baseline
        elif event.kind == "baseline_withdrawal":
            target_id = payload["target_id"]
            if target_id not in self.targets or not payload.get("product_revision_id"):
                raise ValueError("Withdrawal requires target and source revision identity")
            self.baselines.pop(target_id, None)
            self.audit.append(
                {
                    "event_id": event.event_id,
                    "time": time,
                    "kind": "baseline_withdrawn",
                    "target_id": target_id,
                    "product_revision_id": payload["product_revision_id"],
                    "reason": payload.get("reason", "source_withdrawal"),
                }
            )
        elif event.kind == "begin":
            target_id, call_id = payload["target_id"], payload["call_id"]
            if target_id not in self.targets or call_id in self.calls:
                raise ValueError("Unknown target or duplicate call identity")
            view = self._base(target_id, time)
            self.calls[call_id] = {
                "target_id": target_id,
                "began_at": time,
                "context_hash": view["context_hash"],
                "baseline_snapshot": view,
                "completed": False,
                "canceled": False,
            }
        elif event.kind == "cancel":
            if payload["call_id"] not in self.calls:
                raise ValueError("Cannot cancel a nonexistent call")
            self.calls[payload["call_id"]]["canceled"] = True
        elif event.kind == "candidate":
            attempt = {"event_id": event.event_id, "time": time, **_encode(payload)}
            call = self.calls.get(payload["call_id"])
            probability = payload.get("probability")
            if call is None:
                status = "missing_begin"
            elif call["completed"]:
                status = "duplicate_completion"
            elif call["canceled"]:
                status = "canceled"
            elif time <= call["began_at"]:
                status = "nonpositive_duration"
            elif not self._open(call["target_id"], time):
                status = "late"
            elif not _valid_probability(probability):
                status = "invalid_probability"
            elif payload.get("decision", "override") not in {"override", "follow", "no_change"}:
                status = "invalid_decision"
            elif type(payload.get("expires_at")) is not int or payload["expires_at"] < time:
                status = "expired_lifetime"
            elif (
                self.protocol == "base_bound_override"
                and call["context_hash"] != self._base(call["target_id"], time)["context_hash"]
            ):
                status = "expired_base_context"
            elif payload.get("decision") == "follow":
                self._end_override(call["target_id"], time, "explicit_follow_candidate")
                status = "declined_follow"
            elif payload.get("decision") == "no_change":
                status = "declined_no_change"
            else:
                status = "accepted"
                self._end_override(call["target_id"], time, "explicit_replacement")
                self.overrides[call["target_id"]] = {
                    "call_id": payload["call_id"],
                    "probability": probability,
                    "context_hash": call["context_hash"],
                    "expires_at": payload["expires_at"],
                    "committed_at": time,
                }
            attempt["status"] = status
            if call is not None:
                call["completed"] = True
                attempt.update(
                    target_id=call["target_id"],
                    began_at=call["began_at"],
                    snapshot_context_hash=call["context_hash"],
                    current_context_hash=self._base(call["target_id"], time)["context_hash"],
                )
            self.attempts.append(attempt)
        elif event.kind == "follow":
            self._end_override(payload["target_id"], time, "explicit_follow")
        elif event.kind == "action":
            action_id = payload["action_id"]
            if payload["target_id"] not in self.targets or action_id in self.actions:
                raise ValueError("Unknown target or duplicate action")
            self.actions[action_id] = dict(payload, committed_at=time)
        elif event.kind != "no_change":
            raise ValueError("Unknown event kind")

    def run(self, events, *, until=None):
        for event in events:
            encoded = event.to_dict()
            if event.event_id in self._events:
                if self._events[event.event_id] != encoded:
                    raise ValueError("Conflicting idempotent event")
                continue
            if self._last_time is not None and event.time <= self._last_time:
                raise ValueError("No backdated events after a processed clock boundary")
            # This JSON round trip is also a snapshot of mutable caller payloads.
            if self.journal is not None:
                self.journal.append(event.event_id, encoded)
            self._events[event.event_id] = json.loads(json.dumps(encoded, allow_nan=False))
        upcoming = [
            Event(r["event_id"], r["time"], r["kind"], _decode(r["payload"]))
            for key, r in self._events.items()
            if key not in self._processed
        ]
        end = (
            max(
                [e.time for e in upcoming] + [o.cutoff for o in self.opportunities.values()],
                default=0,
            )
            if until is None
            else until
        )
        times = {e.time for e in upcoming if e.time <= end}
        times.update(
            o.cutoff
            for o in self.opportunities.values()
            if o.cutoff <= end and o.opportunity_id not in self.snapshots
        )
        for event in upcoming:
            if event.kind == "baseline":
                expiry = event.payload["baseline"].valid_until
                if expiry <= end:
                    times.add(expiry)
            elif event.kind == "candidate" and type(event.payload.get("expires_at")) is int:
                if event.payload["expires_at"] <= end:
                    times.add(event.payload["expires_at"])
        if self._last_time is not None:
            times = {t for t in times if t > self._last_time}
        for time in sorted(times):
            group = sorted(
                (e for e in upcoming if e.time == time),
                key=lambda e: (EVENT_ORDER[e.kind], e.event_id),
            )
            for event in group:
                if EVENT_ORDER[event.kind] <= 1:
                    self._process(event)
            self._invalidate(time)
            for opportunity in sorted(self.opportunities.values(), key=lambda o: o.opportunity_id):
                if opportunity.cutoff != time or opportunity.opportunity_id in self.snapshots:
                    continue
                target_id = opportunity.target.target_id
                baseline = self._base(target_id, time)
                override = self.overrides.get(target_id)
                self.snapshots[opportunity.opportunity_id] = {
                    "opportunity_id": opportunity.opportunity_id,
                    "target_id": target_id,
                    "cutoff": time,
                    "probability": baseline["probability"]
                    if override is None
                    else override["probability"],
                    "base_probability": baseline["probability"],
                    "baseline_kind": baseline["baseline_kind"],
                    "baseline_context_hash": baseline["context_hash"],
                    "mode": "follow" if override is None else "override",
                    "override_call_id": None if override is None else override["call_id"],
                    "protocol": self.protocol,
                }
            for target_id, override in list(self.overrides.items()):
                if time >= override["expires_at"]:
                    self._end_override(target_id, time, "expired_lifetime")
            for action_id, action in list(self.actions.items()):
                if time >= action["expires_at"]:
                    del self.actions[action_id]
            for event in group:
                if EVENT_ORDER[event.kind] > 1:
                    self._process(event)
                self._processed.add(event.event_id)
            self._last_time = time
        # Observing an otherwise empty interval still advances the legal clock.
        self._last_time = end if self._last_time is None else max(self._last_time, end)
        return self.snapshots

    def export(self):
        payload = {
            "schema": "disastertrace.monitoring.event_replay.v1",
            "protocol": self.protocol,
            "opportunities": [asdict(o) for o in self.opportunities.values()],
            "fallback_probabilities": self.fallbacks,
            "events": list(self._events.values()),
            "processed_through": self._last_time,
        }
        return {"payload": payload, "sha256": canonical_hash(payload)}

    @classmethod
    def restore(cls, record):
        payload = record["payload"]
        if canonical_hash(payload) != record["sha256"]:
            raise ValueError("Event replay integrity check failed")
        opportunities = [
            Opportunity(row["opportunity_id"], TargetSpec(**row["target"]), row["cutoff"])
            for row in payload["opportunities"]
        ]
        engine = cls(
            opportunities,
            fallback_probabilities=payload["fallback_probabilities"],
            protocol=payload["protocol"],
        )
        events = [
            Event(row["event_id"], row["time"], row["kind"], _decode(row["payload"]))
            for row in payload["events"]
        ]
        engine.run(events, until=payload["processed_through"])
        return engine
