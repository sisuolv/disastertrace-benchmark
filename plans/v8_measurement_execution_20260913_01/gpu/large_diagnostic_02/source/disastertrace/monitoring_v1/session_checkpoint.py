"""Whole-controller checkpoints at completed ticks, retaining unresolved charges."""

import json
from dataclasses import asdict

from .execution import bind_execution
from .resources import BudgetLedger, Cost
from .state import MonitoringEngine
from .targets import canonical_hash
from .views import EvidenceStore

CONTROLS = {"acquire", "predict", "selector_kind", "query_limit_per_tick", "per_tick_forecast_cap"}
CONTROLLER_FIELDS = ("calls", "frames", "call_records", "selector_records", "source_receipts")


def clone(value):
    return json.loads(json.dumps(value, sort_keys=True, allow_nan=False))


def capture_session(context, next_tick):
    runtime, ledger, store = (context[k] for k in ("runtime", "ledger", "store"))
    unknown = [rid for rid, entry in ledger.entries.items() if not entry["settled"]]
    if any(ledger.entries[rid].get("outcome") != "unknown_execution" for rid in unknown) or any(
        not c["completed"] for c in runtime.calls.values()
    ):
        raise ValueError("Unfinished local invocations require in-flight checkpoints")
    assets = []
    for row in store.assets.values():
        assets.append(
            {
                **row,
                "entitlement": sorted(row["entitlement"]),
                "parents": list(row["parents"]),
                "receipt_ids": list(row["receipt_ids"]),
            }
        )
    payload = {
        "schema": "disastertrace.session_unresolved.v2"
        if unknown
        else "disastertrace.session_quiescent.v1",
        "next_tick": next_tick,
        "clock": runtime._last_time,
        "runtime": runtime.export(),
        "data_sha256": canonical_hash(context["data"]),
        "bank_sha256": canonical_hash(context["bank"]),
        "config": context["config"],
        "rng": {"kind": "stateless_sha256", "seed": context["config"]["seed"]},
        "ledger": {
            "limits": ledger.limits,
            "allocation_mode": ledger.allocation_mode,
            "quotas": ledger.quotas,
            "events": ledger.events,
            "spent": asdict(ledger.spent),
            **(
                {"reserved": asdict(ledger.reserved), "unresolved_receipt_ids": sorted(unknown)}
                if unknown
                else {}
            ),
        },
        "store": {
            "authorization_mode": store.authorization_mode,
            "targets": sorted(store.targets),
            "assets": assets,
        },
        "controller": {name: context[name] for name in CONTROLLER_FIELDS},
        "tick_local_state": (
            "complete local tick; unresolved remote executions retain reservation, no automatic reissue"
            if unknown
            else "none; checkpoint is after a complete tick, no in-flight model or query"
        ),
    }
    payload = clone(payload)
    return {"payload": payload, "sha256": canonical_hash(payload)}


def restore_session(record, data, bank, config):
    payload = record["payload"]
    if canonical_hash(payload) != record["sha256"]:
        raise ValueError("Checkpoint integrity mismatch")
    if payload["schema"] not in {
        "disastertrace.session_quiescent.v1",
        "disastertrace.session_unresolved.v2",
    }:
        raise ValueError("Unknown checkpoint schema")
    if payload["data_sha256"] != canonical_hash(data) or payload["bank_sha256"] != canonical_hash(
        bank
    ):
        raise ValueError("Checkpoint environment/bank binding mismatch")
    frozen = lambda c: {k: v for k, v in c.items() if k not in CONTROLS}
    if frozen(payload["config"]) != frozen(config) or payload["rng"] != {
        "kind": "stateless_sha256",
        "seed": config["seed"],
    }:
        raise ValueError("Branch changes frozen resource/protocol/RNG contract")
    if config.get("session_runtime") == "typed_admission_v1":
        from ..monitoring_fixed_v1.adaptive import TypedAviationRuntime

        runtime = TypedAviationRuntime.restore(payload["runtime"], data, bank, config)
    else:
        runtime = MonitoringEngine.restore(payload["runtime"])
    if runtime._last_time != payload["clock"]:
        raise ValueError("Checkpoint clock mismatch")
    ledger_row = payload["ledger"]
    ledger = BudgetLedger(
        ledger_row["limits"],
        allocation_mode=ledger_row["allocation_mode"],
        quotas=ledger_row["quotas"],
    )
    for event in ledger_row["events"]:
        if event["event"] == "reserve":
            ledger.reserve(event["receipt_id"], Cost(**event["upper"]), event["owner"])
        elif event["event"] == "overrun_rejected":
            raise ValueError("Unresolved resource overrun is not a quiescent boundary")
        elif event["event"] == "overrun_settled":
            ledger.settle_observed(
                event["receipt_id"], Cost(**event["actual"]), outcome=event["outcome"]
            )
        elif event["event"] == "execution_unknown":
            ledger.mark_unknown(event["receipt_id"], event["details"])
        elif event["event"] == "bind_request":
            ledger.bind_request(event["receipt_id"], event["binding"])
        elif event["event"] == "execution_reconciled":
            ledger.reconcile_unknown(event["receipt_id"], Cost(**event["actual"]), event["proof"])
        else:
            ledger.settle(event["receipt_id"], Cost(**event["actual"]), outcome=event["event"])
    if (
        ledger.events != ledger_row["events"]
        or asdict(ledger.spent) != ledger_row["spent"]
        or asdict(ledger.reserved) != ledger_row.get("reserved", asdict(Cost()))
        or any(not c["completed"] for c in runtime.calls.values())
    ):
        raise ValueError("Checkpoint resource/in-flight mismatch")
    unresolved = sorted(rid for rid, entry in ledger.entries.items() if not entry["settled"])
    if unresolved != ledger_row.get("unresolved_receipt_ids", []):
        raise ValueError("Checkpoint drops unresolved execution identities")
    row = payload["store"]
    store = EvidenceStore(row["authorization_mode"], row["targets"])
    pending = list(row["assets"])
    while pending:
        eligible = [r for r in pending if set(r["parents"]) <= set(store.assets)]
        if not eligible:
            raise ValueError("Checkpoint has missing or cyclic cache parents")
        for asset in eligible:
            if asset["parents"]:
                store.derive(asset["asset_id"], asset["content"], asset["parents"])
            else:
                if len(asset["receipt_ids"]) != 1:
                    raise ValueError("Unbound acquisition receipt")
                rid = asset["receipt_ids"][0]
                if rid not in ledger.entries or not ledger.entries[rid]["settled"]:
                    raise ValueError("Cache without settled acquisition")
                store.register(
                    asset["asset_id"], asset["content"], owner=asset["owner"], receipt_id=rid
                )
            new = store.assets[asset["asset_id"]]
            if (
                set(new["entitlement"]) != set(asset["entitlement"])
                or list(new["receipt_ids"]) != asset["receipt_ids"]
            ):
                raise ValueError("Checkpoint broadens cache entitlement or drops charges")
            pending.remove(asset)
    next_tick = payload["next_tick"]
    cutoffs = sorted({o["cutoff"] for o in data["opportunities"]})
    if (
        type(next_tick) is not int
        or not 0 <= next_tick <= len(cutoffs)
        or len(payload["controller"]["frames"]) != next_tick
        or (next_tick and runtime._last_time < cutoffs[next_tick - 1])
    ):
        raise ValueError("Checkpoint controller cursor mismatch")
    return {
        "runtime": runtime,
        "ledger": ledger,
        "store": store,
        "next_tick": next_tick,
        **clone(payload["controller"]),
    }


class SessionCoordinator:
    """Steps the original run_session loop; never reissues a recorded prefix call."""

    def __init__(self, data, bank, config, *, backend=None):
        self.data, self.bank, self.config = (
            clone(data),
            clone(bank),
            clone(bind_execution(config, backend)),
        )
        self.backend = backend
        self.checkpoint = None
        self.report = None

    @classmethod
    def restore(cls, record, data, bank, *, backend=None):
        config = record["payload"]["config"]
        bind_execution(config, backend)
        restore_session(record, data, bank, config)
        session = cls(data, bank, config, backend=backend)
        session.checkpoint = clone(record)
        return session

    @property
    def done(self):
        return self.checkpoint is not None and self.checkpoint["payload"]["next_tick"] == len(
            {o["cutoff"] for o in self.data["opportunities"]}
        )

    def step(self, controls=None):
        if controls and not set(controls) <= CONTROLS:
            raise ValueError("Unregistered branch control")
        if self.done:
            return self.report
        from .policies import run_session

        self.config = {**self.config, **(controls or {})}
        result = run_session(
            self.data,
            self.bank,
            self.config,
            backend=self.backend,
            _resume=self.checkpoint,
            _max_ticks=1,
        )
        self.checkpoint = result.pop("session_checkpoint")
        self.report = result
        return self.report

    def snapshot(self):
        if self.checkpoint is None:
            raise ValueError("Step to a quiescent boundary before snapshot")
        return clone(self.checkpoint)

    def reconcile_costs(self, responses):
        """Reconcile original receipts without reopening a failed forecast decision."""
        if self.checkpoint is None:
            raise ValueError("No captured original invocation")
        context = restore_session(self.checkpoint, self.data, self.bank, self.config)
        for response in responses:
            proof = response["proof"]
            if proof["observed_at"] < context["runtime"]._last_time:
                raise ValueError("Reconciliation cannot backdate the observation clock")
            changed = context["ledger"].reconcile_unknown(
                response["receipt_id"], Cost(**response["actual"]), proof
            )
            if changed:
                context["runtime"].run([], until=proof["observed_at"])
        context.update(data=self.data, bank=self.bank, config=self.config)
        self.checkpoint = capture_session(context, context["next_tick"])
        self.report = None
        return self.snapshot()

    def finish(self):
        if self.done and self.report is None:
            from .policies import run_session

            result = run_session(
                self.data,
                self.bank,
                self.config,
                backend=self.backend,
                _resume=self.checkpoint,
                _max_ticks=0,
            )
            self.checkpoint = result.pop("session_checkpoint")
            self.report = result
        while not self.done:
            self.step()
        return self.report

    def policy_view(self, target_id=None):
        if self.checkpoint is None:
            raise ValueError("No completed public prefix")
        p = self.checkpoint["payload"]
        # Environment hashes and queued future baselines belong to the evaluator.
        view = {
            "clock": p["clock"],
            "spent": p["ledger"]["spent"],
            "public_selector_view": p["controller"]["frames"][-1]["public_selector_view"],
        }
        if target_id is not None:
            if target_id not in p["store"]["targets"]:
                raise ValueError("Unknown predictor target")
            view["cache"] = [a for a in p["store"]["assets"] if target_id in a["entitlement"]]
        return clone(view)
