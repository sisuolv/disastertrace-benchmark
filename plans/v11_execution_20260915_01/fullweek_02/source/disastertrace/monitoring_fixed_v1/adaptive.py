"""Typed H15 adapter for the existing stepped session controller.

The controller owns scheduling, quota and acquisition. This adapter has no policy
loop: all baseline, invocation and completion transitions use AdmissionEngine.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import asdict

from ..monitoring_v1.calibration import predict
from ..monitoring_v1.resources import Cost
from .admission import AdmissionEngine, AdmissionEvent, TypedOpportunity
from .aviation import FrozenFrequencyPredictor, typed_target
from .contracts import EvidenceBundle, Forecast, canonical, fingerprint
from .copy_controls import COPY_KINDS, VisibleValuePredictor
from .heads import model_messages, parse_response
from .native_feature import FEATURE_KINDS, NativeFeaturePredictor
from .outcomes import experiment_spec
from .preparation_schedule import bind_preparation_schedule
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
        preparation, self.preparation_events = bind_preparation_schedule(config)
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
            experiment=experiment_spec(data, bank, config),
            preparation=preparation,
            semantics_version=config.get("admission_semantics", "measurement.v2"),
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
        expected = json.loads(canonical(restored.contract))
        before = restored.active_interventions
        after = adapter.engine.active_interventions
        changes = {key: value for key, value in after.items() if before.get(key) != value}
        allowed = {
            "acquire",
            "predict",
            "selector_kind",
            "query_limit_per_tick",
            "per_tick_forecast_cap",
        }
        if "experiment" in expected:
            expected["experiment"]["interventions"] = after
        if expected != adapter.engine.contract or not set(changes) <= allowed:
            raise ValueError("Typed controller opportunity/fallback contract mismatch")
        if changes:
            restored.run(
                [
                    AdmissionEvent(
                        "branch-" + fingerprint({"parent": record["sha256"], "changes": changes}),
                        restored._last_time + 1,
                        "policy_intervention",
                        {"parent_checkpoint_sha256": record["sha256"], "changes": changes},
                    )
                ],
                until=restored._last_time,
            )
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
                **(
                    {"native_semantics_sha256": candidate["native_semantics_sha256"]}
                    if candidate is not None and "native_semantics_sha256" in candidate
                    else {}
                ),
                "legacy_target_contract": legacy,
                "E_question": {
                    "predicate": pair["e_predicate"],
                    "query_ids": sorted(pair["query_ids"]),
                    "threshold_m": pair["threshold_m"],
                },
                "mapping_details": mapped,
                "calibration_bank_sha256": fingerprint(self.bank),
                "calibration_metadata": self.bank.get(
                    "fit_disclosure",
                    {
                        "period_status": "not_explicitly_bound_in_legacy_bank",
                        "contract_sha256": self.bank.get("contract_sha256"),
                    },
                ),
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
        preview = self.engine.fork()
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
            self.config.get("program_prediction") + ".v1"
            if backend is None
            and self.config.get("program_prediction") in COPY_KINDS | FEATURE_KINDS
            else "frozen_frequency.v1"
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
        observed_start = time.perf_counter()
        if backend is None:
            program_kind = self.config.get("program_prediction", "frequency_mapping")
            if program_kind in FEATURE_KINDS:
                predictor = NativeFeaturePredictor(
                    self.config["native_feature_bank"],
                    at=started,
                    calibrated=program_kind == "native_feature_calibrated",
                )
            else:
                predictor = (
                    VisibleValuePredictor(program_kind)
                    if program_kind in COPY_KINDS
                    else FrozenFrequencyPredictor(self.bank)
                )
            raw = canonical(predictor.predict(bundle).to_dict())
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
            ledger.bind_request(
                call_id,
                {
                    "request_sha256": fingerprint(messages),
                    "execution_sha256": fingerprint(self.config["execution_contract"]),
                },
            )
            from ..monitoring_v1.execution import PendingExecution
            from ..monitoring_v1.lifecycle import elapsed_us, invoke

            try:
                raw, details = invoke(
                    backend,
                    (messages[0]["content"], bundle.policy_view(), call_id),
                    call_id,
                    ledger,
                    policy=self.config.get("pending_timing_policy", "backend_receipt_v1"),
                )
            except PendingExecution:
                if not callable(getattr(backend, "resolve", None)):
                    details = {
                        "exception_type": "MissingOriginalTicketResolver",
                        "observed_wall_seconds": time.perf_counter() - observed_start,
                    }
                    ledger.mark_unknown(call_id, details)
                    elapsed = (
                        max(
                            1,
                            self.config.get(
                                "public_call_slot_ms", self.config["call_compute_cap_ms"]
                            ),
                        )
                        * 1000
                    )
                    return self._failed_execution(
                        opportunity,
                        bundle,
                        call_id,
                        started,
                        self._failure_time(started, elapsed, details["observed_wall_seconds"]),
                        head,
                        executor,
                        "unknown_execution",
                        None,
                        details,
                    )
                raise
            except Exception as exc:  # noqa: BLE001 - record failure without a free retry.
                details = {
                    "exception_type": type(exc).__name__,
                    "observed_wall_seconds": max(
                        time.perf_counter() - observed_start,
                        elapsed_us(ledger, call_id) / 1_000_000,
                    ),
                }
                ledger.mark_unknown(call_id, details)
                elapsed = (
                    max(
                        1,
                        self.config.get("public_call_slot_ms", self.config["call_compute_cap_ms"]),
                    )
                    * 1000
                )
                return self._failed_execution(
                    opportunity,
                    bundle,
                    call_id,
                    started,
                    self._failure_time(started, elapsed, details["observed_wall_seconds"]),
                    head,
                    executor,
                    "unknown_execution",
                    None,
                    details,
                )
        return self._complete_execution(
            opportunity,
            bundle,
            call_id,
            started,
            ledger,
            head,
            executor,
            raw,
            details,
            observed_start,
        )

    def resume_pending(self, opportunity, call_id, ledger, backend, ticket):
        from ..monitoring_v1.execution import PendingExecution
        from ..monitoring_v1.lifecycle import elapsed_us, invoke

        call = self.calls[call_id]
        if call["completed"] or not callable(getattr(backend, "resolve", None)):
            raise ValueError("Pending invocation requires its original resolvable backend")
        bundle = EvidenceBundle.restore(call["bundle"])
        binding = ledger.entries[call_id]["binding"]
        if binding != {
            "request_sha256": fingerprint(model_messages(bundle, call["head"])),
            "execution_sha256": fingerprint(self.config["execution_contract"]),
        }:
            raise ValueError("Pending request differs from original dispatch binding")
        observed_start = time.perf_counter()
        try:
            raw, details = invoke(
                backend,
                (),
                call_id,
                ledger,
                ticket=ticket,
                policy=self.config.get("pending_timing_policy", "backend_receipt_v1"),
            )
        except PendingExecution as exc:
            if exc.ticket != ticket:
                raise ValueError("Poll changed the original remote identity") from exc
            raise
        except Exception as exc:  # noqa: BLE001 - original reservation remains charged.
            details = {
                "exception_type": type(exc).__name__,
                "phase": "pending_resolution",
                "observed_wall_seconds": max(
                    time.perf_counter() - observed_start, elapsed_us(ledger, call_id) / 1_000_000
                ),
            }
            ledger.mark_unknown(call_id, details)
            elapsed = (
                max(1, self.config.get("public_call_slot_ms", self.config["call_compute_cap_ms"]))
                * 1000
            )
            return self._failed_execution(
                opportunity,
                bundle,
                call_id,
                call["began_at"],
                self._failure_time(call["began_at"], elapsed, details["observed_wall_seconds"]),
                call["head"],
                call["executor"],
                "unknown_execution",
                None,
                details,
            )
        return self._complete_execution(
            opportunity,
            bundle,
            call_id,
            call["began_at"],
            ledger,
            call["head"],
            call["executor"],
            raw,
            details,
            observed_start,
        )

    def _complete_execution(
        self,
        opportunity,
        bundle,
        call_id,
        started,
        ledger,
        head,
        executor,
        raw,
        details,
        observed_start,
    ):
        try:
            if (
                not isinstance(raw, str)
                or type(details["seconds"]) not in (int, float)
                or not math.isfinite(details["seconds"])
                or details["seconds"] < 0
            ):
                raise ValueError("Invalid measured backend duration or response")
            if any(
                type(details[k]) is not int or details[k] < 0
                for k in ("input_tokens", "output_tokens")
            ):
                raise ValueError("Invalid measured backend token counts")
            elapsed_seconds = details.get("elapsed_seconds", details["seconds"])
            if (
                type(elapsed_seconds) not in (int, float)
                or not math.isfinite(elapsed_seconds)
                or elapsed_seconds < details["seconds"]
            ):
                raise ValueError("Invalid elapsed delivery duration")
            duration = max(1, math.ceil(elapsed_seconds * 1_000_000))
            compute_us = max(1, math.ceil(details["seconds"] * 1_000_000))
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            from ..monitoring_v1.lifecycle import elapsed_us

            diagnostic = {
                "error_type": type(exc).__name__,
                "observed_wall_seconds": max(
                    time.perf_counter() - observed_start, elapsed_us(ledger, call_id) / 1_000_000
                ),
            }
            ledger.mark_unknown(call_id, diagnostic)
            elapsed = (
                max(1, self.config.get("public_call_slot_ms", self.config["call_compute_cap_ms"]))
                * 1000
            )
            return self._failed_execution(
                opportunity,
                bundle,
                call_id,
                started,
                self._failure_time(started, elapsed, diagnostic["observed_wall_seconds"]),
                head,
                executor,
                "invalid_backend_response",
                raw if isinstance(raw, str) else None,
                diagnostic,
            )
        persistence = self.config.get("persistence_latency_ms", 1) * 1000
        elapsed = duration + persistence
        slot_overrun = False
        if self.config.get("isolation_mode") == "public_schedule":
            slot = self.config["public_call_slot_ms"] * 1000
            slot_overrun = elapsed > slot
            elapsed = max(elapsed, slot)
        completed, persisted = started + duration, started + elapsed
        actual = Cost(
            tokens=details["input_tokens"] + details["output_tokens"],
            compute_ms=math.ceil(compute_us / 1000),
        )
        resource_overrun = not actual.within(asdict(ledger.entries[call_id]["upper"]))
        if slot_overrun or resource_overrun:
            disposition = "slot_overrun" if slot_overrun else "resource_overrun"
            ledger.settle_observed(call_id, actual, outcome=disposition)
            return self._failed_execution(
                opportunity,
                bundle,
                call_id,
                started,
                persisted,
                head,
                executor,
                disposition,
                raw,
                details,
                actual=actual,
                completed=completed,
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
            "decision": "E_only"
            if head == "e_only"
            else "keep"
            if admission["status"] == "adoption_kept"
            else "override",
            "proposed_probability": None if forecast is None else forecast.value,
            "adoption_policy": self.config.get("adoption_policy", "typed_auto_propose.v1"),
            "proposed_action": "OVERRIDE" if forecast is not None else None,
            "admitted_action": "OVERRIDE" if admission["status"] == "accepted" else None,
            "effective_state_after_completion": self.policy_state(
                opportunity["target_id"], persisted
            ),
            "response_error": error,
            "admission_status": admission["status"],
            "evidence_query_ids": sorted(
                a["content"]["query_id"] for a in bundle.policy_view()["assets"]
            ),
            "details": details,
            "raw": raw,
        }
        if "adoption_decision" in admission:
            record["adoption_decision"] = admission["adoption_decision"]
        return record, persisted

    def _failure_time(self, started, reserved_duration, observed_seconds):
        # A reservation is not a bound on an already observed failed invocation.
        observed_us = max(1, math.ceil(observed_seconds * 1_000_000))
        return max(
            started + reserved_duration, max(started, self._last_time or started) + observed_us
        )

    def _failed_execution(
        self,
        opportunity,
        bundle,
        call_id,
        started,
        observed_at,
        head,
        executor,
        status,
        raw,
        details,
        *,
        actual=None,
        completed=None,
    ):
        payload = {
            "call_id": call_id,
            "status": status,
            "bundle_hash": bundle.bundle_hash,
            "raw": raw,
            "raw_sha256": None if raw is None else hashlib.sha256(raw.encode()).hexdigest(),
            "cost": None if actual is None else asdict(actual),
            "details": details,
            "executor": executor,
            "head": head,
        }
        self.run(
            [AdmissionEvent(call_id + "-failure", observed_at, "execution_failure", payload)],
            until=observed_at,
        )
        record = {
            "call_id": call_id,
            "opportunity_id": opportunity["opportunity_id"],
            "head": head,
            "started_at": started,
            "completed_at": completed,
            "persisted_at": observed_at,
            "bundle": bundle.to_dict(),
            "receipt": payload,
            "expected_e_from_disclosed_products": native_slot_support(bundle, at=started)["status"],
            "reported_e": None,
            "decision": "no_admitted_control",
            "proposed_probability": None,
            "adoption_policy": "typed_auto_propose.v1",
            "proposed_action": None,
            "admitted_action": None,
            "effective_state_after_completion": self.policy_state(
                opportunity["target_id"], observed_at
            ),
            "response_error": status,
            "admission_status": status,
            "timely_disposition": observed_at <= opportunity["cutoff"],
            "evidence_query_ids": sorted(
                a["content"]["query_id"] for a in bundle.policy_view()["assets"]
            ),
            "details": details,
            "raw": raw,
        }
        return record, observed_at
