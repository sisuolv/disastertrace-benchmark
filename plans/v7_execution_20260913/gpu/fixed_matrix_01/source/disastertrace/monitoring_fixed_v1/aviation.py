"""Freeze lawful H15 snapshots from the existing native archive contract."""

from __future__ import annotations

import json
from pathlib import Path

from disastertrace.monitoring_v1.calibration import predict
from disastertrace.monitoring_v1.evidence import exists_report_support

from .contracts import EvidenceBundle, Forecast, Target, canonical, fingerprint


def load(path):
    return json.loads(Path(path).read_text())


def typed_target(legacy):
    if (
        legacy["spatial_support"] != "station:" + legacy["entity"]
        or legacy.get("spatial_radius_m") is not None
    ):
        raise ValueError("This adapter only covers exact station report support")
    return Target(
        legacy["target_id"],
        legacy["spatial_support"],
        legacy["variable"],
        legacy["units"],
        "event_probability",
        "interval",
        legacy["physical_start"],
        legacy["physical_end"],
        legacy["temporal_semantics"],
        legacy["report_policy"],
        legacy["event_operator"],
        legacy["threshold"],
        legacy.get("release_event_at"),
    )


class AviationProvider:
    """Builder-only archive access; predictors receive only immutable bundles."""

    def __init__(self, dataset, bank):
        dataset = Path(dataset)
        self.bank = bank
        self.targets = {r["target_id"]: r for r in load(dataset / "public/TARGETS.json")}
        self.opportunities = {
            r["opportunity_id"]: r for r in load(dataset / "public/OPPORTUNITIES.json")
        }
        self.pairs = {r["opportunity_id"]: r for r in load(dataset / "public/E_F_PAIRS.json")}
        self.catalog = {r["query_id"]: r for r in load(dataset / "public/QUERY_CATALOG.json")}
        self.results = {r["query_id"]: r for r in load(dataset / "environment/QUERY_RESULTS.json")}
        self.bases = {
            r["opportunity_id"]: r for r in load(dataset / "environment/LATEST_BASELINES.json")
        }

    def freeze(self, opportunity_id, evidence_condition):
        if evidence_condition not in {"common_only", "fixed_one", "all_registered"}:
            raise ValueError("Unregistered evidence condition")
        opportunity = self.opportunities[opportunity_id]
        legacy = self.targets[opportunity["target_id"]]
        target = typed_target(legacy)
        pair = self.pairs[opportunity_id]
        query_ids = sorted(pair["query_ids"])
        selected = (
            []
            if evidence_condition == "common_only"
            else query_ids[:1]
            if evidence_condition == "fixed_one"
            else query_ids
        )
        candidate = self.bases.get(opportunity_id)
        if candidate is None:
            raise ValueError("No native baseline in this bounded diagnostic; retain rejection")
        mapped = predict(self.bank, legacy, candidate)
        forecast = Forecast(
            target.contract_hash, "event_probability", "probability", mapped["probability"]
        )
        base = {
            "forecast": forecast.to_dict(),
            "source_revision": candidate["source_id"],
            "issued_at": candidate["issued_at"],
            "available_at": candidate["available_at"],
            "valid_until": candidate["valid_until"],
            "kind": "research",
            "mapping_version": self.bank["mapping_version"],
            "content": {
                "native_taf": candidate,
                "legacy_target_contract": legacy,
                "E_question": {
                    "predicate": pair["e_predicate"],
                    "query_ids": query_ids,
                    "threshold_m": pair["threshold_m"],
                },
                "mapping_details": mapped,
                "calibration_bank_sha256": fingerprint(self.bank),
            },
        }
        assets, receipts = [], []
        for query_id in selected:
            catalog, result = self.catalog[query_id], self.results[query_id]
            completed_at = catalog["available_at"] + catalog["latency_ms"] * 1000
            receipt_id = opportunity_id + ":" + query_id
            receipts.append(
                {
                    "receipt_id": receipt_id,
                    "owner": target.target_id,
                    "asset_ids": [query_id],
                    "started_at": catalog["available_at"],
                    "completed_at": completed_at,
                    "cost": catalog["archive_cost"],
                }
            )
            assets.append(
                {
                    "asset_id": query_id,
                    "source_revision": fingerprint(result),
                    "raw": "\n".join(r["raw"] for r in result.get("reports", [])),
                    "content": result,
                    "available_at": catalog["available_at"],
                    "observed_at": max(
                        (r["observation_time"] for r in result.get("reports", [])), default=None
                    ),
                    "completed_at": completed_at,
                    "entitlements": [target.target_id],
                    "receipt_ids": [receipt_id],
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
        return EvidenceBundle.freeze(
            {
                "schema": "disastertrace.frozen_evidence.v1",
                "opportunity_id": opportunity_id,
                "target": target.to_dict(),
                "cutoff": opportunity["cutoff"],
                "baseline": base,
                "state": {
                    "forecast": forecast.to_dict(),
                    "mode": "FOLLOW",
                    "protocol": "base_bound_override",
                },
                "assets": assets,
                "receipts": receipts,
                "authorization_mode": "target_private",
                "representation": "native_text_and_fixed_parser_product_intervals",
                "availability_basis": "declared_archive_scenario",
                "provider_version": "native_h15_snapshot.v1",
            }
        )


class FrozenFrequencyPredictor:
    """The prior-month map sees the same disclosed records as the model."""

    def __init__(self, bank):
        self.bank = bank

    def predict_with_details(self, bundle):
        row = bundle.policy_view()
        content = row["baseline"]["content"]
        if fingerprint(self.bank) != content["calibration_bank_sha256"]:
            raise ValueError("Predictor calibration differs from the frozen common map")
        mapped = predict(
            self.bank,
            content["legacy_target_contract"],
            content["native_taf"],
            content["E_question"]["query_ids"],
            {a["asset_id"]: a["content"] for a in row["assets"]},
        )
        target = Target(**row["target"])
        return Forecast(
            target.contract_hash, "event_probability", "probability", mapped["probability"]
        ), mapped

    def predict(self, bundle):
        return self.predict_with_details(bundle)[0]


def visible_e_status(bundle):
    row = bundle.policy_view()
    question = row["baseline"]["content"]["E_question"]
    return exists_report_support(
        question["query_ids"],
        {a["asset_id"]: a["content"] for a in row["assets"]},
        question["threshold_m"],
    )


SYSTEM = """You forecast a fixed future native routine visibility report using one frozen evidence snapshot. Return exactly JSON with two keys: {"probability":0.1,"e_status":"undetermined"}. probability is a finite number in [0,1] for the target's strict visibility-below-threshold event in the native routine report hour. e_status answers the separate E_question: whether ANY of the registered PAST neighbor slots reports visibility below its threshold, using ONLY disclosed assets. Allowed E answers are supported, refuted, undetermined, inconsistent. A single definite low report supports; refuted requires every registered slot definitely not low; unseen slots remain unknown. E sufficiency is not F probability: unknown E does not mean probability 0.5. The common full TAF and smoothed prior-month research probability are already available to every predictor. TAF TEMPO is not an official probability. The provided parser intervals describe native product values, not error-free physical visibility. You may retain the baseline if extra reports do not improve your estimate. Use only this snapshot, no remembered event outcomes and no external retrieval. All timestamps are UTC microseconds. No prose or extra fields."""


def model_messages(bundle):
    # Fresh messages per opportunity/condition prevent target-private state leakage.
    return [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": canonical(bundle.policy_view())},
    ]


def parse_response(raw, bundle):
    row = json.loads(raw)
    if not isinstance(row, dict) or set(row) != {"probability", "e_status"}:
        raise ValueError("Invalid fixed-predictor response schema")
    if row["e_status"] not in {"supported", "refuted", "undetermined", "inconsistent"}:
        raise ValueError("Invalid E support status")
    target = Target(**bundle.policy_view()["target"])
    forecast = Forecast(
        target.contract_hash, "event_probability", "probability", row["probability"]
    )
    return forecast, row["e_status"]
