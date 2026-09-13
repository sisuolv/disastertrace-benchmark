"""Typed H15 adapter for the existing stepped session controller.

The controller owns scheduling, quota and acquisition. This adapter has no policy
loop: all baseline, invocation and completion transitions use AdmissionEngine.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict

from ..monitoring_v1.calibration import predict
from ..monitoring_v1.resources import Cost
from .admission import AdmissionEngine, AdmissionEvent, TypedOpportunity
from .aviation import FrozenFrequencyPredictor, typed_target
from .contracts import EvidenceBundle, Forecast, canonical, fingerprint
from .heads import model_messages, parse_response
from .support_bridge import native_slot_support


class TypedAviationRuntime:
    def __init__(self, data, bank, config, *, journal=None):
        self.bank, self.config = bank, config
        self.legacy_targets = {t["target_id"]: t for t in data["targets"]}
        self.targets = {tid: typed_target(t) for tid, t in self.legacy_targets.items()}
        self.pairs = {p["opportunity_id"]: p for p in data["e_f_pairs"]}
        self.catalog = {q["query_id"]: q for q in data["query_catalog"]}
        self.candidates = {(c["target_id"], c["source_id"]): c for c in data["baseline_candidates"]}
        self.opportunities = {o["opportunity_id"]: o for o in data["opportunities"]}
        self.engine = AdmissionEngine(
            [
                TypedOpportunity(o["opportunity_id"], self.targets[o["target_id"]], o["cutoff"])
                for o in data["opportunities"]
            ],
            fallbacks={
                tid: self._forecast(tid, predict(bank, t, None)["probability"]).to_dict()
                for tid, t in self.legacy_targets.items()
            },
            protocol=config["protocol"],
            journal=journal,
        )

    def _forecast(self, tid, value):
        return Forecast(self.targets[tid].contract_hash, "event_probability", "probability", value)

    @property
    def _last_time(self):
        return self.engine._last_time

    @property
    def calls(self):
        return self.engine.calls

    @property
    def attempts(self):
        return self.engine.attempts

    @property
    def snapshots(self):
        return self.engine.snapshots

    @property
    def audit(self):
        return [
            {"target_id": tid, **e}
            for tid, s in sorted(self.engine.states.items())
            for e in s.events
        ]

    def export(self):
        return self.engine.export()

    @classmethod
    def restore(cls, record, data, bank, config):
        adapter = cls(data, bank, config)
        restored = AdmissionEngine.restore(record)
        if restored.contract != adapter.engine.contract:
            raise ValueError("Typed controller opportunity/fallback contract mismatch")
        adapter.engine = restored
        return adapter

    def _base(self, tid, at):
        base = self.engine.baselines.get(tid)
        if base is not None and at < base["valid_until"]:
            return {
                "probability": base["forecast"]["value"],
                "product_revision_id": base["source_revision"],
                "context_hash": self.engine.states[tid].base_hash,
                "baseline_kind": base["kind"],
            }
        return {
            "probability": self.engine.fallbacks[tid]["value"],
            "product_revision_id": "frozen_fallback",
            "context_hash": fingerprint(
                {"target": self.targets[tid].contract_hash, "fallback": self.engine.fallbacks[tid]}
            ),
            "baseline_kind": "fallback",
        }

    def policy_state(self, tid, at):
        state = self.engine.states[tid]
        value = state.effective(at).value if state.baseline else self.engine.fallbacks[tid]["value"]
        return {
            "target_id": tid,
            "probability": value,
            "mode": "follow" if state.override is None else "override",
            "protocol": self.config["protocol"],
        }

    def _baseline(self, tid, candidate, at, pair):
        legacy = self.legacy_targets[tid]
        mapped = predict(self.bank, legacy, candidate)
        return {
            "forecast": self._forecast(tid, mapped["probability"]).to_dict(),
            "source_revision": "frozen_fallback" if candidate is None else candidate["source_id"],
            "issued_at": at if candidate is None else candidate["issued_at"],
            "available_at": at if candidate is None else candidate["available_at"],
            "valid_until": self.targets[tid].physical_start
            if candidate is None
            else candidate["valid_until"],
            "kind": "fallback"
            if candidate is None or candidate.get("projection_status") == "unavailable"
            else "research",
            "mapping_version": self.bank["mapping_version"],
            "content": {
                "native_taf": candidate,
                "legacy_target_contract": legacy,
                "E_question": {
                    "predicate": pair["e_predicate"],
                    "query_ids": sorted(pair["query_ids"]),
                    "threshold_m": pair["threshold_m"],
                },
                "mapping_details": mapped,
                "calibration_bank_sha256": fingerprint(self.bank),
            },
        }

    def _bundle(self, opportunity, base, state, assets=(), receipts=()):
        return EvidenceBundle.freeze(
            {
                "schema": "disastertrace.frozen_evidence.v1",
                "opportunity_id": opportunity["opportunity_id"],
                "target": self.targets[opportunity["target_id"]].to_dict(),
                "cutoff": opportunity["cutoff"],
                "baseline": base,
                "state": state,
                "assets": list(assets),
                "receipts": list(receipts),
                "authorization_mode": self.config["authorization_mode"],
                "representation": "native_text_and_fixed_parser_product_intervals",
                "availability_basis": "declared_archive_scenario",
                "provider_version": "native_h15_snapshot.v1",
            }
        )

    def run(self, events, *, until=None):
        converted = []
        for event in events:
            if isinstance(event, AdmissionEvent):
                converted.append(event)
            elif event.kind == "baseline":
                legacy = event.payload["baseline"]
                tid = legacy.target.target_id
                candidate = self.candidates[tid, legacy.product_revision_id]
                opportunity = next(o for o in self.opportunities.values() if o["target_id"] == tid)
                base = self._baseline(
                    tid, candidate, event.time, self.pairs[opportunity["opportunity_id"]]
                )
                # A common-source arrival is not an invocation or a scored opportunity.
                carrier = dict(opportunity, cutoff=event.time, opportunity_id=event.event_id)
                bundle = self._bundle(
                    carrier,
                    base,
                    {
                        "forecast": base["forecast"],
                        "mode": "FOLLOW",
                        "protocol": self.config["protocol"],
                    },
                )
                converted.append(
                    AdmissionEvent(
                        event.event_id, event.time, "baseline", {"bundle": bundle.to_dict()}
                    )
                )
            elif event.kind == "baseline_withdrawal":
                converted.append(
                    AdmissionEvent(event.event_id, event.time, event.kind, event.payload)
                )
            else:
                raise ValueError("Legacy probability candidates cannot enter typed admission")
        return self.engine.run(converted, until=until)

    def freeze_acquired(self, opportunity, at, store, ledger, source_receipts):
        tid, oid = opportunity["target_id"], opportunity["opportunity_id"]
        # Preview uses exactly the same reducer; common arrivals at invocation time
        # precede the begin event. The authoritative clock is advanced only by run().
        preview = AdmissionEngine.restore(self.engine.export())
        preview.run([], until=at)
        preview._refresh(tid, at)
        current = preview.baselines.get(tid)
        candidate = (
            None
            if current is None or at >= current["valid_until"]
            else current["content"]["native_taf"]
        )
        base = self._baseline(tid, candidate, at, self.pairs[oid])
        state = preview.states[tid]
        recorded = {r["receipt_id"]: r for r in source_receipts}
        assets, receipts = [], {}
        for cached in store.view(tid):
            qid = cached["content"]["query_id"]
            if qid not in self.pairs[oid]["query_ids"]:
                continue
            original = store.assets[cached["asset_id"]]
            if original["parents"] or len(original["receipt_ids"]) != 1:
                raise ValueError("This provider requires one paid native acquisition per asset")
            rid = original["receipt_ids"][0]
            receipt, entry = recorded[rid], ledger.entries[rid]
            if (
                not entry["settled"]
                or entry["outcome"] != "completed"
                or receipt["completed_at"] > at
                or receipt["asset_id"] != cached["asset_id"]
                or entry["owner"] != receipt["payer"]
                or receipt["query_id"] != qid
            ):
                raise ValueError("Evidence lacks a completed paid acquisition receipt")
            receipts[rid] = {
                "receipt_id": rid,
                "owner": entry["owner"],
                "asset_ids": [cached["asset_id"]],
                "started_at": receipt["started_at"],
                "completed_at": receipt["completed_at"],
                "cost": asdict(entry["actual"]),
            }
            result = cached["content"]
            assets.append(
                {
                    "asset_id": cached["asset_id"],
                    "source_revision": fingerprint(result),
                    "raw": "\n".join(r["raw"] for r in result.get("reports", [])),
                    "content": result,
                    "available_at": self.catalog[qid]["available_at"],
                    "observed_at": max(
                        (r["observation_time"] for r in result.get("reports", [])), default=None
                    ),
                    "completed_at": receipt["completed_at"],
                    "entitlements": sorted(original["entitlement"]),
                    "receipt_ids": [rid],
                    "parents": [],
                    "transform": {
                        "version": result["support_rule_version"],
                        "parameters": {"units": "m"},
                    },
                    "reference_kind": result["reference_kind"],
                    "support_assumption": result["support_assumption"],
                    "visible_information_scope": "policy_after_query",
                    "support_rule_version": result["support_rule_version"],
                    "missingness": result["status"],
                }
            )
        return self._bundle(
            opportunity,
            base,
            {
                "forecast": state.effective(at).to_dict(),
                "mode": "FOLLOW" if state.override is None else "OVERRIDE",
                "protocol": self.config["protocol"],
            },
            assets,
            receipts.values(),
        )

    def execute(self, opportunity, call_id, started, store, ledger, source_receipts, backend):
        bundle = self.freeze_acquired(opportunity, started, store, ledger, source_receipts)
        head = "program" if backend is None else self.config.get("typed_head", "joint")
        executor = (
            "frozen_frequency.v1"
            if backend is None
            else self.config.get("executor_id", "typed_backend.v1")
        )
        self.run(
            [
                AdmissionEvent(
                    call_id + "-begin",
                    started,
                    "begin",
                    {
                        "call_id": call_id,
                        "bundle": bundle.to_dict(),
                        "head": head,
                        "executor": executor,
                    },
                )
            ],
            until=started,
        )
        if call_id not in self.calls:
            raise ValueError("Controller produced an inadmissible typed begin")
        if backend is None:
            raw = canonical(FrozenFrequencyPredictor(self.bank).predict(bundle).to_dict())
            details = {
                "input_tokens": 0,
                "output_tokens": 0,
                "seconds": 0.001,
                "ended_with_eos": True,
                "backend": executor,
                "timing_basis": "declared_program_latency_scenario",
            }
        else:
            messages = model_messages(bundle, head)
            raw, details = backend(messages[0]["content"], bundle.policy_view(), call_id)
        duration = max(1, math.ceil(details["seconds"] * 1_000_000))
        persistence = self.config.get("persistence_latency_ms", 1) * 1000
        elapsed = duration + persistence
        if self.config.get("isolation_mode") == "public_schedule":
            elapsed = self.config["public_call_slot_ms"] * 1000
            if duration + persistence > elapsed:
                raise ValueError("Actual call and persistence exceed the public isolation slot")
        completed, persisted = started + duration, started + elapsed
        actual = Cost(
            tokens=details["input_tokens"] + details["output_tokens"],
            compute_ms=math.ceil(duration / 1000),
        )
        error, forecast, status_e = None, None, None
        try:
            if head == "program":
                forecast = Forecast(**json.loads(raw))
            else:
                answer = parse_response(raw, bundle, head)
                forecast, status_e = answer.forecast, answer.e_status
            if details.get("ended_with_eos") is not True:
                raise ValueError("Response unfinished")
        except (ValueError, TypeError, OverflowError) as exc:
            error = str(exc)
        ledger.settle(call_id, actual, outcome="completed" if error is None else "invalid_response")
        receipt = {
            "call_id": call_id,
            "bundle_hash": bundle.bundle_hash,
            "raw": raw,
            "raw_sha256": hashlib.sha256(raw.encode()).hexdigest(),
            "started_at": started,
            "completed_at": completed,
            "persisted_at": persisted,
            "expires_at": max(
                o["cutoff"]
                for o in self.opportunities.values()
                if o["target_id"] == opportunity["target_id"]
            ),
            "cost": asdict(actual),
            "ended_with_eos": details.get("ended_with_eos", False),
            "head": head,
            "executor": executor,
        }
        self.run(
            [AdmissionEvent(call_id + "-complete", persisted, "completion", receipt)],
            until=persisted,
        )
        admission = next(
            a for a in reversed(self.attempts) if a.get("event_id") == call_id + "-complete"
        )
        record = {
            "call_id": call_id,
            "opportunity_id": opportunity["opportunity_id"],
            "head": head,
            "started_at": started,
            "completed_at": completed,
            "persisted_at": persisted,
            "bundle": bundle.to_dict(),
            "receipt": receipt,
            "expected_e_from_disclosed_products": native_slot_support(bundle, at=started)["status"],
            "reported_e": status_e,
            "decision": "E_only" if head == "e_only" else "override",
            "proposed_probability": None if forecast is None else forecast.value,
            "response_error": error,
            "admission_status": admission["status"],
            "evidence_query_ids": sorted(
                a["content"]["query_id"] for a in bundle.policy_view()["assets"]
            ),
            "details": details,
            "raw": raw,
        }
        return record, persisted
