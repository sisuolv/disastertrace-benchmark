"""Evaluator-only canonical results and whitelisted comparison interventions."""

import json

from .contracts import canonical, fingerprint, finite, require_fields, timestamp

OUTCOME_FIELDS = (
    "target_contract_hash resolution_version value status source_revision source_sha256 "
    "physical_start physical_end units quality_status observed_at published_at fetched_at "
    "resolved_at availability_basis"
)


class OutcomeRegistry:
    def __init__(self, targets):
        self.targets = {target.contract_hash: target for target in targets}
        if not self.targets:
            raise ValueError("Outcome registry requires declared targets")
        self.records = {}

    def register(self, record):
        optional = {"references", "reference_kind"}
        required = {k: v for k, v in record.items() if k not in optional}
        require_fields(required, OUTCOME_FIELDS, "canonical outcome")
        if ("references" in record and not isinstance(record["references"], list)) or (
            "reference_kind" in record
            and (type(record["reference_kind"]) is not str or not record["reference_kind"])
        ):
            raise ValueError("Invalid optional outcome provenance")
        record = json.loads(canonical(record))
        target = self.targets.get(record["target_contract_hash"])
        if target is None:
            raise ValueError("Unknown outcome target")
        if (record["physical_start"], record["physical_end"], record["units"]) != (
            target.physical_start,
            target.physical_end,
            target.units,
        ):
            raise ValueError("Outcome physical support or units differ from target")
        for name in (
            "physical_start",
            "physical_end",
            "observed_at",
            "published_at",
            "fetched_at",
            "resolved_at",
        ):
            if record[name] is not None:
                timestamp(record[name])
        if record["status"] not in {"mature", "provisional", "missing"}:
            raise ValueError("Unknown outcome resolution status")
        if any(
            type(record[k]) is not str or not record[k]
            for k in ("resolution_version", "quality_status", "status")
        ):
            raise ValueError("Outcome resolution and quality required")
        value = record["value"]
        if value is not None and (
            not finite(value) or (target.output_kind == "event_probability" and value not in (0, 1))
        ):
            raise ValueError("Outcome violates target value type")
        if record["status"] == "mature" and (value is None or not record["source_revision"]):
            raise ValueError("Mature outcome requires a bound result")
        sha = record["source_sha256"]
        if record["status"] != "missing" and (
            not isinstance(sha, str)
            or len(sha) != 64
            or any(c not in "0123456789abcdef" for c in sha)
        ):
            raise ValueError("Canonical outcome needs full source hash")
        if record["availability_basis"] not in {
            "declared_archive_scenario",
            "observed_first_seen",
            "documented_historical_release",
        }:
            raise ValueError("Outcome availability basis required")
        known = [record[k] for k in ("fetched_at", "resolved_at")]
        if None not in known and known[0] > known[1]:
            raise ValueError("Resolution cannot precede local acquisition")
        key = (target.contract_hash, record["resolution_version"])
        if key in self.records:
            if self.records[key] != record:
                raise ValueError("Canonical target outcome conflict across opportunities")
            return False
        self.records[key] = record
        return True

    def export(self):
        payload = {
            "schema": "disastertrace.outcome_registry.v1",
            "records": [self.records[key] for key in sorted(self.records)],
        }
        return {"payload": payload, "sha256": fingerprint(payload)}

    def opportunity_rows(self, opportunities, resolution_versions):
        opportunities = list(opportunities)
        if set(resolution_versions) != {o.opportunity_id for o in opportunities}:
            raise ValueError("Every opportunity requires a frozen result version")
        rows, target_versions = [], {}
        for opportunity in opportunities:
            key = (
                opportunity.target.contract_hash,
                resolution_versions[opportunity.opportunity_id],
            )
            if key[0] in target_versions and target_versions[key[0]] != key[1]:
                raise ValueError("A comparison cannot mix resolution versions across leads")
            target_versions[key[0]] = key[1]
            if key not in self.records:
                raise ValueError("Opportunity references a missing canonical result")
            rows.append({"opportunity_id": opportunity.opportunity_id, **self.records[key]})
        return rows


def experiment_spec(data, bank, config):
    cost_fields = (
        "request_budget",
        "forecast_call_cap",
        "model_call_budget",
        "input_token_cap",
        "output_token_cap",
        "call_compute_cap_ms",
        "token_cap",
        "compute_ms_cap",
        "wakeup_seconds",
        "isolation_mode",
        "public_call_slot_ms",
        "persistence_latency_ms",
    )
    factor_fields = (
        "allocation_mode",
        "authorization_mode",
        "selector_kind",
        "protocol",
        "acquire",
        "predict",
        "query_limit_per_tick",
        "per_tick_forecast_cap",
        "execution_contract",
    )
    return {
        "invariants": {
            "data_universe_sha256": fingerprint(data),
            "bank_sha256": fingerprint(bank),
            "resource_and_time_contract": {k: config.get(k) for k in cost_fields},
            "other_frozen_config": {
                k: v for k, v in config.items() if k not in set(cost_fields) | set(factor_fields)
            },
            "availability_basis": "declared_archive_scenario",
        },
        "interventions": {k: config.get(k) for k in factor_fields},
    }


class ComparisonContract:
    def __init__(self, invariants, allowed_interventions):
        self.invariants = json.loads(canonical(invariants))
        self.allowed_interventions = json.loads(canonical(allowed_interventions))
        if not self.invariants or any(
            not values or not isinstance(values, list)
            for values in self.allowed_interventions.values()
        ):
            raise ValueError("Explicit comparison invariants and intervention values required")

    def validate(self, invariants, interventions):
        if invariants != self.invariants:
            raise ValueError("Common comparison contract changed")
        if set(interventions) != set(self.allowed_interventions) or any(
            interventions[key] not in values for key, values in self.allowed_interventions.items()
        ):
            raise ValueError("Unregistered experiment intervention")

    def export(self):
        payload = {
            "schema": "disastertrace.comparison_contract.v1",
            "invariants": self.invariants,
            "allowed_interventions": self.allowed_interventions,
        }
        return {"payload": payload, "sha256": fingerprint(payload)}
