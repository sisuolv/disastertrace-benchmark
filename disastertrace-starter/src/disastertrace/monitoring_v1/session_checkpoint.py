"""Whole-controller checkpoints at completed ticks, retaining unresolved charges."""

import json
from dataclasses import asdict

from .execution import bind_execution
from .resources import BudgetLedger, Cost
from .source_execution import bind_source
from .state import MonitoringEngine
from .targets import canonical_hash
from .views import EvidenceStore

CONTROLS = {"acquire", "predict", "selector_kind", "query_limit_per_tick", "per_tick_forecast_cap", "residual_query_plan"}
CONTROLLER_FIELDS = ("calls", "frames", "call_records", "selector_records", "source_receipts")
PENDING_FIELDS = ("pending_predictor", "pending_selector", "pending_source")


def clone(value):
    return json.loads(json.dumps(value, sort_keys=True, allow_nan=False))


def validate_pending_source(pending, runtime, ledger, data, next_tick, controller):
    fields = {
        "receipt_id",
        "query_id",
        "asset_id",
        "payer",
        "request",
        "ticket",
        "binding",
        "clock",
        "tick",
        "cutoff",
        "public_selector_view",
        "forecast_order",
        "selected_query_rank",
        "source_steps",
    }
    if not isinstance(pending, dict) or set(pending) != fields:
        raise ValueError("Invalid pending source cursor")
    entry = ledger.entries.get(pending["receipt_id"])
    catalog = {q["query_id"]: q for q in data["query_catalog"]}
    active = {
        o["opportunity_id"]: o for o in data["opportunities"] if o["cutoff"] == pending["cutoff"]
    }
    request = pending["request"]
    if (
        entry is None
        or entry["settled"]
        or entry["owner"] != pending["payer"]
        or pending["tick"] != next_tick
        or pending["clock"] != runtime._last_time
        or not pending["clock"] < pending["cutoff"]
        or request
        != {
            "query_id": pending["query_id"],
            "catalog": catalog.get(pending["query_id"]),
            "payer": pending["payer"],
            "asset_id": pending["asset_id"],
        }
        or request["catalog"] is None
        or request["catalog"]["available_at"] > pending["clock"]
        or pending["binding"] != entry.get("binding")
        or pending["binding"]["request_sha256"] != canonical_hash(request)
        or not isinstance(pending["ticket"], dict)
        or not pending["ticket"].get("remote_id")
        or not set(pending["forecast_order"]) <= set(active)
        or len(pending["forecast_order"]) != len(set(pending["forecast_order"]))
        or any(not c["completed"] for c in runtime.calls.values())
        or any(r["receipt_id"] == pending["receipt_id"] for r in controller["source_receipts"])
        or any(r not in controller["source_receipts"] for r in pending["source_steps"])
        or len(controller["frames"]) != next_tick
    ):
        raise ValueError("Pending source does not bind the original acquisition")


def validate_pending_selector(pending, runtime, ledger, data, next_tick, controller, config=None):
    from .selector_contract_v2 import selection_system

    fields = {
        "call_id",
        "tick",
        "clock",
        "cutoff",
        "public_selector_view",
        "request",
        "target_handles",
        "query_handles",
        "ticket",
        "binding",
    }
    if not isinstance(pending, dict) or set(pending) != fields:
        raise ValueError("Invalid pending selector cursor")
    request = pending["request"]
    entry = ledger.entries.get(pending["call_id"])
    active = {
        o["opportunity_id"]: o for o in data["opportunities"] if o["cutoff"] == pending["cutoff"]
    }
    if (
        entry is None
        or entry["settled"]
        or entry["owner"] != "session_selector"
        or pending["tick"] != next_tick
        or pending["call_id"] != "select-" + str(next_tick)
        or pending["clock"] != runtime._last_time
        or pending["clock"] != request.get("clock")
        or pending["cutoff"] != request.get("cutoff")
        or not pending["clock"] < pending["cutoff"]
        or pending["binding"] != entry.get("binding")
        or pending["binding"]["request_sha256"]
        != canonical_hash({"system": selection_system(config or {}, request), "request": request})
        or not isinstance(pending["ticket"], dict)
        or not pending["ticket"].get("remote_id")
        or {h: row["opportunity_id"] for h, row in request["targets"].items()}
        != pending["target_handles"]
        or set(pending["target_handles"].values()) != set(active)
        or {h: row["query_id"] for h, row in request["queries"].items()} != pending["query_handles"]
        or any(not c["completed"] for c in runtime.calls.values())
        or any(r["call_id"] == pending["call_id"] for r in controller["selector_records"])
        or len(controller["frames"]) != next_tick
    ):
        raise ValueError("Pending selector does not bind the original invocation")
    for h, oid in pending["target_handles"].items():
        tid = active[oid]["target_id"]
        if request["targets"][h]["common"] != pending["public_selector_view"].get(tid):
            raise ValueError("Pending selector public view differs from its dispatch")


def validate_pending(pending, runtime, ledger, data, next_tick, controller):
    fields = {
        "call_id",
        "opportunity_id",
        "tick",
        "clock",
        "cutoff",
        "forecast_index",
        "forecast_order",
        "public_selector_view",
        "source_steps",
        "frame_call_ids",
        "ticket",
        "binding",
    }
    if not isinstance(pending, dict) or set(pending) != fields:
        raise ValueError("Invalid pending predictor cursor")
    call_id = pending["call_id"]
    call, entry = runtime.calls.get(call_id), ledger.entries.get(call_id)
    opportunities = {o["opportunity_id"]: o for o in data["opportunities"]}
    order, index = pending["forecast_order"], pending["forecast_index"]
    if (
        call is None
        or call["completed"]
        or entry is None
        or entry["settled"]
        or entry.get("binding") != pending["binding"]
        or pending["tick"] != next_tick
        or type(index) is not int
        or not isinstance(order, list)
        or len(set(order)) != len(order)
        or not 0 <= index < len(order)
        or order[index] != pending["opportunity_id"]
        or not set(order) <= set(opportunities)
        or any(opportunities[oid]["cutoff"] != pending["cutoff"] for oid in order)
        or pending["clock"] != runtime._last_time
        or call["began_at"] != pending["clock"]
        or call["bundle"]["payload"]["opportunity_id"] != pending["opportunity_id"]
        or not isinstance(pending["ticket"], dict)
        or not pending["ticket"].get("remote_id")
    ):
        raise ValueError("Pending cursor does not bind the original invocation")
    incomplete = {cid for cid, row in runtime.calls.items() if not row["completed"]}
    if incomplete != {call_id}:
        raise ValueError("Unexpected unfinished local invocation")
    current_frame_calls = [
        r["call_id"]
        for r in controller["call_records"]
        if opportunities[r["opportunity_id"]]["cutoff"] == pending["cutoff"]
    ]
    if current_frame_calls != pending["frame_call_ids"]:
        raise ValueError("Pending frame drops already completed calls")


def capture_session(context, next_tick):
    runtime, ledger, store = (context[k] for k in ("runtime", "ledger", "store"))
    unknown = [rid for rid, entry in ledger.entries.items() if not entry["settled"]]
    pending = context.get("pending_predictor")
    selector = context.get("pending_selector")
    source = context.get("pending_source")
    if sum(c is not None for c in (pending, selector, source)) > 1:
        raise ValueError("Only one original controller invocation may be pending")
    if pending is not None:
        validate_pending(pending, runtime, ledger, context["data"], next_tick, context)
    if selector is not None:
        validate_pending_selector(selector, runtime, ledger, context["data"], next_tick, context, context["config"])
    if source is not None:
        validate_pending_source(source, runtime, ledger, context["data"], next_tick, context)
    waiting = pending or selector or source
    waiting_id = None if waiting is None else waiting.get("call_id", waiting.get("receipt_id"))
    if any(
        ledger.entries[rid].get("outcome") != "unknown_execution"
        and (waiting is None or rid != waiting_id)
        for rid in unknown
    ) or (pending is None and any(not c["completed"] for c in runtime.calls.values())):
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
        "schema": "disastertrace.session_inflight_source.v5"
        if source is not None
        else "disastertrace.session_inflight_selector.v4"
        if selector is not None
        else "disastertrace.session_inflight_predictor.v3"
        if pending is not None
        else "disastertrace.session_unresolved.v2"
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
        **({"pending_predictor": pending} if pending is not None else {}),
        **({"pending_selector": selector} if selector is not None else {}),
        **({"pending_source": source} if source is not None else {}),
        "tick_local_state": (
            "frozen native source dispatch; no entitlement before original receipt settles"
            if source is not None
            else "frozen selector dispatch before acquisition; poll original ticket only"
            if selector is not None
            else "frozen predictor dispatch and current tick cursor; poll original ticket only"
            if pending is not None
            else "complete local tick; unresolved remote executions retain reservation, no automatic reissue"
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
        "disastertrace.session_inflight_predictor.v3",
        "disastertrace.session_inflight_selector.v4",
        "disastertrace.session_inflight_source.v5",
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
    if any(k in payload for k in PENDING_FIELDS) and payload["config"] != config:
        raise ValueError("Cannot change current-frame controls while an invocation is pending")
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
        elif event["event"] == "execution_timing":
            ledger.record_execution_timing(
                event["receipt_id"], event["timing"]["last_wall_ns"], event["phase"]
            )
        elif event["event"] == "execution_reconciled":
            ledger.reconcile_unknown(event["receipt_id"], Cost(**event["actual"]), event["proof"])
        else:
            ledger.settle(event["receipt_id"], Cost(**event["actual"]), outcome=event["event"])
    if (
        ledger.events != ledger_row["events"]
        or asdict(ledger.spent) != ledger_row["spent"]
        or asdict(ledger.reserved) != ledger_row.get("reserved", asdict(Cost()))
        or (
            "pending_predictor" not in payload
            and any(not c["completed"] for c in runtime.calls.values())
        )
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
    if "pending_predictor" in payload:
        if payload["schema"] != "disastertrace.session_inflight_predictor.v3":
            raise ValueError("Pending invocation requires its versioned checkpoint")
        validate_pending(
            payload["pending_predictor"], runtime, ledger, data, next_tick, payload["controller"]
        )
    elif payload["schema"] == "disastertrace.session_inflight_predictor.v3":
        raise ValueError("Checkpoint drops its pending invocation")
    if "pending_selector" in payload:
        if payload["schema"] != "disastertrace.session_inflight_selector.v4":
            raise ValueError("Pending selector requires its versioned checkpoint")
        validate_pending_selector(
            payload["pending_selector"], runtime, ledger, data, next_tick, payload["controller"], payload["config"]
        )
    elif payload["schema"] == "disastertrace.session_inflight_selector.v4":
        raise ValueError("Checkpoint drops its pending selector")
    if "pending_source" in payload:
        if payload["schema"] != "disastertrace.session_inflight_source.v5":
            raise ValueError("Pending source requires its versioned checkpoint")
        validate_pending_source(
            payload["pending_source"], runtime, ledger, data, next_tick, payload["controller"]
        )
        if payload["pending_source"]["binding"]["execution_sha256"] != canonical_hash(
            config.get("source_execution_contract")
        ):
            raise ValueError("Pending source execution identity differs from its controller")
    elif payload["schema"] == "disastertrace.session_inflight_source.v5":
        raise ValueError("Checkpoint drops its pending source")
    return {
        "runtime": runtime,
        "ledger": ledger,
        "store": store,
        "next_tick": next_tick,
        **(
            {"pending_predictor": clone(payload["pending_predictor"])}
            if "pending_predictor" in payload
            else {}
        ),
        **(
            {"pending_selector": clone(payload["pending_selector"])}
            if "pending_selector" in payload
            else {}
        ),
        **(
            {"pending_source": clone(payload["pending_source"])}
            if "pending_source" in payload
            else {}
        ),
        **clone(payload["controller"]),
    }


class SessionCoordinator:
    """Steps the original run_session loop; never reissues a recorded prefix call."""

    def __init__(self, data, bank, config, *, backend=None, source_backend=None):
        self.data, self.bank, self.config = (
            clone(data),
            clone(bank),
            clone(bind_source(bind_execution(config, backend), source_backend)),
        )
        self.backend = backend
        self.source_backend = source_backend
        self.checkpoint = None
        self.report = None

    @classmethod
    def restore(cls, record, data, bank, *, backend=None, source_backend=None):
        config = record["payload"]["config"]
        bind_source(bind_execution(config, backend), source_backend)
        restore_session(record, data, bank, config)
        session = cls(data, bank, config, backend=backend, source_backend=source_backend)
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
        if (self.config.get("residual_query_plan") is not None and controls
                and "residual_query_plan" in controls
                and controls["residual_query_plan"] != self.config["residual_query_plan"]):
            raise ValueError("A finite residual plan cannot be replaced")
        if (
            controls
            and self.checkpoint is not None
            and any(k in self.checkpoint["payload"] for k in PENDING_FIELDS)
        ):
            raise ValueError("Cannot change current-frame controls while an invocation is pending")
        if self.done:
            return self.report
        from .policies import run_session

        self.config = {**self.config, **(controls or {})}
        result = run_session(
            self.data,
            self.bank,
            self.config,
            backend=self.backend,
            source_backend=self.source_backend,
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

    def persist(self, path):
        """Durably save controller state before releasing a staged remote request."""
        from pathlib import Path

        from .spool_backend import publish, read

        checkpoint = self.snapshot()
        path = Path(path)
        if path.exists():
            if read(path) != checkpoint:
                raise ValueError("A saved controller checkpoint cannot be replaced")
        else:
            publish(path, checkpoint)
        source_pending = "pending_source" in checkpoint["payload"]
        transport = self.source_backend if source_pending else self.backend
        committer = getattr(transport, "commit_checkpoint", None)
        if committer is not None and any(k in checkpoint["payload"] for k in PENDING_FIELDS):
            committer(path)
        return checkpoint

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
                source_backend=self.source_backend,
                _resume=self.checkpoint,
                _max_ticks=0,
            )
            self.checkpoint = result.pop("session_checkpoint")
            self.report = result
        while not self.done:
            self.step()
            if any(k in self.checkpoint["payload"] for k in PENDING_FIELDS):
                return self.report
        return self.report

    def policy_view(self, target_id=None):
        if self.checkpoint is None:
            raise ValueError("No completed public prefix")
        p = self.checkpoint["payload"]
        pending = p.get("pending_selector") or p.get("pending_predictor") or p.get("pending_source")
        # Environment hashes and queued future baselines belong to the evaluator.
        view = {
            "clock": p["clock"],
            "spent": p["ledger"]["spent"],
            "public_selector_view": pending["public_selector_view"]
            if pending is not None
            else p["controller"]["frames"][-1]["public_selector_view"],
        }
        if target_id is not None:
            if target_id not in p["store"]["targets"]:
                raise ValueError("Unknown predictor target")
            view["cache"] = [a for a in p["store"]["assets"] if target_id in a["entitlement"]]
        return clone(view)
