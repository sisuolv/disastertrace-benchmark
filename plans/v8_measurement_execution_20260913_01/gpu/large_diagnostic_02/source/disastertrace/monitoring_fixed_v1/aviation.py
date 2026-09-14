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
        self.native_products = load(dataset / "environment/NATIVE_PRODUCT_INDEX.json")
        self.candidates = {
            (r["opportunity_id"], r["source_id"]): r
            for r in load(dataset / "environment/BASELINE_CANDIDATES.json")
        }

    def freeze(self, opportunity_id, evidence_condition, *, as_of=None):
        if evidence_condition not in {"common_only", "fixed_one", "all_registered"}:
            raise ValueError("Unregistered evidence condition")
        opportunity = self.opportunities[opportunity_id]
        if as_of is not None and (
            type(as_of) is not int or as_of > opportunity["cutoff"]
        ):
            raise ValueError("Snapshot time must be an integer no later than cutoff")
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
        if as_of is not None:
            from ..monitoring_v1.providers.versions import current_taf

            decision = current_taf(
                self.native_products,
                station=legacy["entity"],
                cutoff=as_of,
                start=target.physical_start,
                end=target.physical_end,
            )
            if decision["status"] not in {"active", "unparsed"}:
                raise ValueError("No usable current native baseline: " + decision["status"])
            candidate = self.candidates.get((opportunity_id, decision["selected_id"]))
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
            "kind": "fallback"
            if candidate.get("projection_status") == "unavailable"
            else "research",
            "mapping_version": self.bank["mapping_version"],
            "content": {
                "native_taf": candidate,
                **(
                    {"native_semantics_sha256": candidate["native_semantics_sha256"]}
                    if "native_semantics_sha256" in candidate
                    else {}
                ),
                "legacy_target_contract": legacy,
                "E_question": {
                    "predicate": pair["e_predicate"],
                    "query_ids": query_ids,
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
        assets, receipts = [], []
        for query_id in selected:
            catalog, result = self.catalog[query_id], self.results[query_id]
            completed_at = catalog["available_at"] + catalog["latency_ms"] * 1000
            if as_of is not None and completed_at > as_of:
                raise ValueError("Requested evidence is not complete at snapshot time")
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
    """The frozen development map sees the same disclosed records as the model."""

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
            {a["content"]["query_id"]: a["content"] for a in row["assets"]},
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
        {a["content"]["query_id"]: a["content"] for a in row["assets"]},
        question["threshold_m"],
    )


PROMPT_VERSION = "explicit_truth_joint.v1"
TRUTH_TO_SUPPORT = {
    "true": "supported",
    "false": "refuted",
    "unknown": "undetermined",
    "conflict": "inconsistent",
}
SYSTEM = "Answer a factual query about the PAST registered neighbor report slots in E_question. The proposition is existential: AT LEAST ONE registered slot has reported visibility strictly below threshold_m. Use only the assets disclosed in this frozen snapshot. fact_truth is one of four JSON strings: true, false, unknown, conflict. Return true only if a disclosed report's visibility interval proves it is below threshold_m. Return false only if EVERY registered slot is disclosed and its report interval proves it is NOT below threshold_m. Return unknown if the proposition cannot yet be determined, including unqueried or unresolved slots unless another disclosed slot already proves the existential proposition. Return conflict only for inconsistent source facts, not ordinary uncertainty. The presence of some evidence does not itself make the proposition true. Use visibility bounds in meters, including open/closed endpoints; a lower bound already above threshold proves that report is not below. There are no default answers and no example output values. Timestamps are UTC microseconds. The parsed intervals describe native product facts, not error-free physical weather. Do not retrieve external sources or use memorized weather outcomes. Return only JSON, no explanations. Your output object must contain exactly fact_truth and probability. probability is your numeric [0,1] forecast for the separate FUTURE native routine visibility report target. Use the common full TAF and frozen prior-month research probability; you may retain that baseline. TEMPO is not an official event probability. The past E proposition and future F target are different: unknown E does not force F probability to 0.5, and known E does not determine the future."


def model_messages(bundle):
    # Fresh messages per opportunity/condition prevent target-private state leakage.
    return [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": canonical(bundle.policy_view())},
    ]


def parse_response(raw, bundle):
    row = json.loads(raw)
    if not isinstance(row, dict) or set(row) != {"probability", "fact_truth"}:
        raise ValueError("Invalid fixed-predictor response schema")
    if type(row["fact_truth"]) is not str or row["fact_truth"] not in TRUTH_TO_SUPPORT:
        raise ValueError("Invalid E support status")
    target = Target(**bundle.policy_view()["target"])
    forecast = Forecast(
        target.contract_hash, "event_probability", "probability", row["probability"]
    )
    return forecast, TRUTH_TO_SUPPORT[row["fact_truth"]]
