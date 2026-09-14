"""Immutable visible evidence and typed forecasts for controlled comparisons.

This lane does not change monitoring_v1's archived event engine. Providers must
establish source semantics; this module enforces the declared boundary, not the
truth of arbitrary source text or historical availability assumptions.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from typing import Protocol


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def fingerprint(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def finite(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def timestamp(value):
    if type(value) is not int:
        raise ValueError("Timestamps must be integer UTC microseconds")


def require_fields(record, fields, label):
    if not isinstance(record, dict) or set(record) != set(fields.split()):
        raise ValueError("Unexpected or missing fields in " + label)


@dataclass(frozen=True)
class Target:
    target_id: str
    entity: str
    variable: str
    units: str
    output_kind: str
    support_kind: str
    physical_start: int
    physical_end: int
    temporal_semantics: str
    report_policy: str
    event_operator: str | None = None
    threshold: float | None = None
    release_event_at: int | None = None

    def __post_init__(self):
        if not all(
            type(v) is str and v
            for v in (self.target_id, self.entity, self.variable, self.units, self.report_policy)
        ):
            raise ValueError("Incomplete target identity")
        timestamp(self.physical_start)
        timestamp(self.physical_end)
        if self.support_kind == "point":
            valid = self.physical_start == self.physical_end
        elif self.support_kind == "interval":
            valid = self.physical_start < self.physical_end
        else:
            valid = False
        if not valid:
            raise ValueError("Invalid native physical support")
        if self.output_kind == "event_probability":
            if self.event_operator not in {"lt", "le", "gt", "ge"} or not finite(self.threshold):
                raise ValueError("Event target requires a finite native-unit predicate")
        elif (
            self.output_kind != "scalar"
            or self.threshold is not None
            or self.event_operator is not None
        ):
            raise ValueError("Scalar target has no event threshold")
        if self.temporal_semantics == "future_product_release":
            timestamp(self.release_event_at)
        elif self.temporal_semantics not in {"future_physical", "partial_window_nowcast"}:
            raise ValueError("Unknown target temporal semantics")
        if self.temporal_semantics == "partial_window_nowcast" and self.support_kind != "interval":
            raise ValueError("A point has no partially elapsed window")

    @property
    def contract_hash(self):
        row = self.to_dict()
        del row["target_id"]
        return fingerprint(row)

    @property
    def output_units(self):
        return "probability" if self.output_kind == "event_probability" else self.units

    def check_cutoff(self, cutoff):
        timestamp(cutoff)
        if self.temporal_semantics == "future_physical":
            valid = cutoff < self.physical_start
        elif self.temporal_semantics == "future_product_release":
            valid = cutoff < self.release_event_at
        else:
            valid = self.physical_start <= cutoff < self.physical_end
        if not valid:
            raise ValueError("Cutoff contradicts target semantics")

    def check_forecast(self, forecast):
        if (forecast.target_contract_hash, forecast.kind, forecast.units) != (
            self.contract_hash,
            self.output_kind,
            self.output_units,
        ):
            raise ValueError("Forecast target, kind or unit mismatch")

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class Forecast:
    target_contract_hash: str
    kind: str
    units: str
    value: float

    def __post_init__(self):
        if len(self.target_contract_hash) != 64 or any(
            c not in "0123456789abcdef" for c in self.target_contract_hash
        ):
            raise ValueError("Full target hash required")
        if not finite(self.value) or not self.units:
            raise ValueError("Finite typed value required")
        if self.kind == "event_probability":
            if self.units != "probability" or not 0 <= self.value <= 1:
                raise ValueError("Invalid probability")
        elif self.kind != "scalar":
            raise ValueError("Unsupported forecast type")

    def to_dict(self):
        return asdict(self)


BUNDLE_FIELDS = (
    "schema opportunity_id target cutoff baseline state assets receipts authorization_mode "
    "representation availability_basis provider_version"
)
ASSET_FIELDS = (
    "asset_id source_revision raw content available_at observed_at completed_at entitlements "
    "receipt_ids parents transform reference_kind support_assumption visible_information_scope "
    "support_rule_version missingness"
)


def _validate_bundle(row):
    require_fields(row, BUNDLE_FIELDS, "visible bundle")
    if row["schema"] != "disastertrace.frozen_evidence.v1":
        raise ValueError("Unknown evidence schema")
    target = Target(**row["target"])
    cutoff = row["cutoff"]
    target.check_cutoff(cutoff)
    if row["authorization_mode"] not in {"target_private", "session_shared"}:
        raise ValueError("Unknown authorization mode")
    if row["availability_basis"] not in {
        "observed_first_seen",
        "documented_historical_release",
        "declared_archive_scenario",
    }:
        raise ValueError("Availability evidence must be explicitly qualified")
    if not all(row[k] for k in ("opportunity_id", "representation", "provider_version")):
        raise ValueError("Incomplete provider identity")
    base = row["baseline"]
    require_fields(
        base,
        "forecast source_revision issued_at available_at valid_until kind mapping_version content",
        "base",
    )
    target.check_forecast(Forecast(**base["forecast"]))
    for name in ("issued_at", "available_at", "valid_until"):
        timestamp(base[name])
    if not base["issued_at"] <= base["available_at"] <= cutoff < base["valid_until"]:
        raise ValueError("Common baseline unavailable or expired")
    if base["kind"] not in {"professional", "research", "fallback"} or not all(
        base[k] for k in ("source_revision", "mapping_version")
    ):
        raise ValueError("Incomplete baseline identity")
    require_fields(row["state"], "forecast mode protocol", "current state")
    target.check_forecast(Forecast(**row["state"]["forecast"]))
    if row["state"]["mode"] not in {"FOLLOW", "OVERRIDE"} or row["state"]["protocol"] not in {
        "base_bound_override",
        "persistent_override",
    }:
        raise ValueError("Invalid current-state protocol")
    if row["state"]["mode"] == "FOLLOW" and row["state"]["forecast"] != base["forecast"]:
        raise ValueError("FOLLOW state must use the common baseline")

    receipts = {}
    for receipt in row["receipts"]:
        require_fields(
            receipt, "receipt_id owner asset_ids started_at completed_at cost", "receipt"
        )
        rid = receipt["receipt_id"]
        if not rid or rid in receipts or not receipt["owner"]:
            raise ValueError("Nonunique receipt or missing payer")
        for name in ("started_at", "completed_at"):
            timestamp(receipt[name])
        if not receipt["started_at"] <= receipt["completed_at"] <= cutoff:
            raise ValueError("Late receipt")
        require_fields(receipt["cost"], "requests bytes tokens compute_ms", "resource cost")
        if any(not finite(v) or v < 0 for v in receipt["cost"].values()):
            raise ValueError("Invalid resource cost")
        if row["authorization_mode"] == "target_private" and receipt["owner"] != target.target_id:
            raise ValueError("Private inputs require a target-specific receipt/context")
        receipts[rid] = receipt

    assets = {}
    for asset in row["assets"]:
        require_fields(asset, ASSET_FIELDS, "asset")
        aid = asset["asset_id"]
        if (
            not aid
            or aid in assets
            or not asset["source_revision"]
            or not asset["support_rule_version"]
        ):
            raise ValueError("Missing or duplicate source identity")
        for name in ("available_at", "completed_at"):
            timestamp(asset[name])
        if asset["observed_at"] is not None:
            timestamp(asset["observed_at"])
            if asset["observed_at"] > asset["available_at"]:
                raise ValueError("An observation cannot precede its own existence")
        if not asset["available_at"] <= asset["completed_at"] <= cutoff:
            raise ValueError("Asset not lawfully visible at cutoff")
        if target.target_id not in asset["entitlements"]:
            raise ValueError("Target lacks asset authorization")
        if row["authorization_mode"] == "target_private" and set(asset["entitlements"]) != {
            target.target_id
        }:
            raise ValueError("Private context cannot contain another target's memory")
        if asset["visible_information_scope"] != "policy_after_query":
            raise ValueError("Hidden annotations are not acquired evidence")
        if asset["reference_kind"] not in {
            "product_label",
            "measurement",
            "model_estimate",
            "raw_sensor",
        }:
            raise ValueError("Unknown public reference kind")
        if asset["support_assumption"] not in {
            "product_exact",
            "bounded_error",
            "model_estimate",
            "raw_only",
        }:
            raise ValueError("Unsupported factual-support assumption")
        if (
            asset["reference_kind"] in {"model_estimate", "raw_sensor"}
            and asset["support_assumption"] == "product_exact"
        ):
            raise ValueError("Raw imagery or model estimates are not product-label truth")
        require_fields(asset["transform"], "version parameters", "transform")
        if not asset["transform"]["version"] or not isinstance(asset["raw"], str):
            raise ValueError("Transform version and raw source text required")
        if not asset["receipt_ids"] or len(set(asset["receipt_ids"])) != len(asset["receipt_ids"]):
            raise ValueError("Asset requires unique acquisition receipts")
        if any(rid not in receipts for rid in asset["receipt_ids"]):
            raise ValueError("Missing acquisition receipt")
        if any(
            receipts[rid]["completed_at"] > asset["completed_at"] for rid in asset["receipt_ids"]
        ):
            raise ValueError("Derived asset precedes acquisition")
        if not asset["parents"] and not any(
            aid in receipts[rid]["asset_ids"] for rid in asset["receipt_ids"]
        ):
            raise ValueError("Receipt does not bind the source asset")
        assets[aid] = asset

    # Require an acyclic complete transform graph and intersect parent entitlements.
    visited, pending = set(), set()

    def visit(aid):
        if aid in pending or aid not in assets:
            raise ValueError("Missing or cyclic parent lineage")
        if aid in visited:
            return
        pending.add(aid)
        child = assets[aid]
        for parent_id in child["parents"]:
            visit(parent_id)
            parent = assets[parent_id]
            if not set(child["entitlements"]) <= set(parent["entitlements"]) or not set(
                parent["receipt_ids"]
            ) <= set(child["receipt_ids"]):
                raise ValueError("Derived asset widens permissions or drops parent charges")
            if parent["completed_at"] > child["completed_at"]:
                raise ValueError("Transform predates parent")
            if parent["available_at"] > child["available_at"]:
                raise ValueError("Derived availability predates parent availability")
        pending.remove(aid)
        visited.add(aid)

    for aid in assets:
        visit(aid)
    used_receipts = {rid for asset in assets.values() for rid in asset["receipt_ids"]}
    if set(receipts) != used_receipts or any(
        not set(receipt["asset_ids"]) <= set(assets) for receipt in receipts.values()
    ):
        raise ValueError("Unbound receipt or hidden source reference")


@dataclass(frozen=True)
class EvidenceBundle:
    _payload_json: str

    def __post_init__(self):
        _validate_bundle(json.loads(self._payload_json))

    @classmethod
    def freeze(cls, record):
        return cls(canonical(record))

    @property
    def bundle_hash(self):
        return hashlib.sha256(self._payload_json.encode()).hexdigest()

    @property
    def base_hash(self):
        return fingerprint(self.policy_view()["baseline"])

    def policy_view(self):
        return json.loads(self._payload_json)

    def cost(self):
        receipts = self.policy_view()["receipts"]
        return {
            name: sum(r["cost"][name] for r in receipts)
            for name in ("requests", "bytes", "tokens", "compute_ms")
        }

    def to_dict(self):
        row = self.policy_view()
        return {
            "bundle_hash": self.bundle_hash,
            "base_hash": self.base_hash,
            "payload": row,
            "asset_hashes": {a["asset_id"]: fingerprint(a) for a in row["assets"]},
        }

    @classmethod
    def restore(cls, envelope):
        require_fields(envelope, "bundle_hash base_hash payload asset_hashes", "frozen envelope")
        bundle = cls.freeze(envelope["payload"])
        if bundle.to_dict() != envelope:
            raise ValueError("Frozen evidence hash mismatch")
        return bundle


class EvidenceProvider(Protocol):
    def freeze(self, opportunity_id: str, evidence_condition: str) -> EvidenceBundle: ...


class Predictor(Protocol):
    def predict(self, bundle: EvidenceBundle) -> Forecast: ...


class FollowPredictor:
    def predict(self, bundle):
        return Forecast(**bundle.policy_view()["baseline"]["forecast"])


class ForecastState:
    """Small typed reducer; explicit event records permit offline reconstruction."""

    def __init__(self, target, protocol):
        if protocol not in {"base_bound_override", "persistent_override"}:
            raise ValueError("Unknown revision protocol")
        self.target, self.protocol = target, protocol
        self.baseline = self.override = None
        self.base_hash = self.override_base = None
        self.expires_at = None
        self.now = -(10**30)
        self.events = []

    def _advance(self, at):
        timestamp(at)
        if at < self.now:
            raise ValueError("State clock cannot go backwards")
        self.now = at

    def update_baseline(self, forecast, base_hash, at):
        self.target.check_forecast(forecast)
        if not base_hash:
            raise ValueError("Baseline content/version identity required")
        if any(
            event["kind"] == "base"
            and event["base_hash"] == base_hash
            and event["forecast"] != forecast.to_dict()
            for event in self.events
        ):
            raise ValueError("The same baseline identity cannot change its forecast")
        self._advance(at)
        # A partial-window task may retain an earlier forecast, but cannot adopt
        # any new baseline once its target window (or release event) has closed.
        closes_at = (
            self.target.release_event_at
            if self.target.temporal_semantics == "future_product_release"
            else self.target.physical_start
            if self.target.temporal_semantics == "future_physical"
            else self.target.physical_end
        )
        if at >= closes_at:
            self.events.append(
                {
                    "kind": "base_rejected",
                    "at": at,
                    "forecast": forecast.to_dict(),
                    "base_hash": base_hash,
                    "status": "invalid_target_time",
                }
            )
            return "invalid_target_time"
        if self.protocol == "base_bound_override" and self.base_hash != base_hash:
            self.override = self.override_base = self.expires_at = None
        self.baseline, self.base_hash = forecast, base_hash
        self.events.append(
            {"kind": "base", "at": at, "forecast": forecast.to_dict(), "base_hash": base_hash}
        )
        return "accepted"

    def propose(self, forecast, base_hash, at, expires_at):
        self.target.check_forecast(forecast)
        timestamp(expires_at)
        self._advance(at)
        if self.baseline is None:
            raise ValueError("No common baseline")
        known_base = any(e["kind"] == "base" and e["base_hash"] == base_hash for e in self.events)
        invalid_base = not known_base or (
            self.protocol == "base_bound_override" and base_hash != self.base_hash
        )
        try:
            self.target.check_cutoff(at)
            valid_target_time = True
        except ValueError:
            valid_target_time = False
        status = (
            "invalid_target_time"
            if not valid_target_time
            else "late"
            if at > expires_at
            else "stale_base"
            if invalid_base
            else "accepted"
        )
        if status == "accepted":
            self.override, self.override_base, self.expires_at = forecast, base_hash, expires_at
        self.events.append(
            {
                "kind": "proposal",
                "at": at,
                "forecast": forecast.to_dict(),
                "base_hash": base_hash,
                "expires_at": expires_at,
                "status": status,
            }
        )
        return status

    def follow(self, at):
        self._advance(at)
        self.override = self.override_base = self.expires_at = None
        self.events.append({"kind": "follow", "at": at})

    def effective(self, at):
        timestamp(at)
        if at < self.now:
            raise ValueError("Historical lookup requires replay")
        if self.baseline is None:
            raise ValueError("No baseline")
        return (
            self.override if self.override is not None and at <= self.expires_at else self.baseline
        )

    def to_dict(self):
        return json.loads(
            canonical(
                {"target": self.target.to_dict(), "protocol": self.protocol, "events": self.events}
            )
        )

    @classmethod
    def restore(cls, row):
        require_fields(row, "target protocol events", "state journal")
        state = cls(Target(**row["target"]), row["protocol"])
        for event in row["events"]:
            if event["kind"] in {"base", "base_rejected"}:
                status = state.update_baseline(
                    Forecast(**event["forecast"]), event["base_hash"], event["at"]
                )
                if status != event.get("status", "accepted"):
                    raise ValueError("Recorded baseline outcome differs from replay")
            elif event["kind"] == "proposal":
                status = state.propose(
                    Forecast(**event["forecast"]),
                    event["base_hash"],
                    event["at"],
                    event["expires_at"],
                )
                if status != event["status"]:
                    raise ValueError("Recorded proposal outcome differs from replay")
            elif event["kind"] == "follow":
                state.follow(event["at"])
            else:
                raise ValueError("Unknown state event")
        if state.to_dict() != row:
            raise ValueError("State replay changed record fields")
        return state


def paired_scores(opportunities, arms):
    """Strict full opportunity denominator; a missing prediction must be explicit.

    Upstream wrappers must supply their effective fallback for failed proposals.
    Missing outcomes share one mask across all arms, never per-method deletion.
    """
    ids = [r["opportunity_id"] for r in opportunities]
    if not ids or len(set(ids)) != len(ids) or not arms:
        raise ValueError("Nonempty unique opportunity registry and arms required")
    kinds = {(r["target"]["output_kind"], r["target"]["units"]) for r in opportunities}
    if len(kinds) != 1:
        raise ValueError("Do not pool unlike losses or scalar units")
    kind, _ = next(iter(kinds))
    mask = [r["outcome"] is not None for r in opportunities]
    result = {
        "registered": len(ids),
        "settled": sum(mask),
        "missing": len(ids) - sum(mask),
        "score": "brier" if kind == "event_probability" else "mae",
        "arms": {},
    }
    for name, values in arms.items():
        if set(values) != set(ids):
            raise ValueError("Every method must retain exactly all opportunities")
        losses = []
        for row, settled in zip(opportunities, mask):
            t = Target(**row["target"])
            f = Forecast(**values[row["opportunity_id"]])
            t.check_forecast(f)
            if settled:
                y = row["outcome"]
                if not finite(y) or (kind == "event_probability" and y not in (0, 1)):
                    raise ValueError("Invalid evaluation outcome")
                losses.append(
                    (f.value - y) ** 2 if kind == "event_probability" else abs(f.value - y)
                )
        result["arms"][name] = {
            "mean_loss": sum(losses) / len(losses) if losses else None,
            "loss_sum": sum(losses),
            "scored": len(losses),
        }
    return result
