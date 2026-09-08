"""Freeze a separate P2 development execution without reading credentials or sending."""

import importlib.metadata
import platform
import shutil
from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

from disastertrace.automated.budget_ledger import BudgetLedger, default_policy, money
from disastertrace.automated.common import (
    canonical,
    file_hash,
    fingerprint,
    read_jsonl,
    strict_json,
    write_json,
)
from disastertrace.automated.provider import ProviderConfig, _loopback

from . import package
from .schema import PROTOCOL

ROOT = Path(__file__).resolve().parents[3]
VERSION = "controlled_execution_v1"
CAP = 8192
SLOTS = 270


def read(path):
    return strict_json(Path(path).read_text(encoding="utf-8"))


def candidate_config(fixture_url=None):
    config = ProviderConfig(
        model="deepseek-v4-flash",
        base_url="https://api.deepseek.com",
        key_env="DEEPSEEK_API_KEY",
        max_output_tokens=CAP,
        token_parameter="max_tokens",
        temperature=None,
        timeout=180,
        max_response_bytes=1048576,
        reasoning_effort="high",
        thinking_type="enabled",
    )
    if fixture_url is not None:
        if not isinstance(fixture_url, str) or not _loopback(urlsplit(fixture_url).hostname or ""):
            raise ValueError("HTTP fixture endpoint must be loopback")
        config = replace(config, base_url=fixture_url, key_env=None, model="p2-http-fixture")
    return config


def environment_identity():
    return {
        "python": platform.python_version(),
        "platform": platform.system(),
        "machine": platform.machine(),
        "packages": sorted(
            (dist.metadata["Name"].lower(), dist.version)
            for dist in importlib.metadata.distributions()
        ),
    }


def budget_policy(allowance_usd):
    money(allowance_usd)
    policy = {
        **default_policy(),
        "allowance": allowance_usd,
        "max_requested_output_tokens": SLOTS * CAP,
    }
    BudgetLedger(policy)
    return policy


def _plan(dataset, verified, rates, registry, allowance_usd, fixture_url):
    config = candidate_config(fixture_url)
    if (
        rates.get("schema_version") != "deepseek_price_snapshot_v1"
        or rates.get("model") != "deepseek-v4-flash"
        or rates.get("currency") != "USD"
        or rates.get("peak_per_million_tokens", {}).get("input_cache_miss") != 0.44
        or rates.get("peak_per_million_tokens", {}).get("output") != 1.32
        or rates.get("context", {}).get("reservation_prompt_tokens") != 1048576
    ):
        raise ValueError("unsupported price/context snapshot; version the execution policy")
    episodes = read_jsonl(dataset / "episodes.jsonl")
    schedule = read_jsonl(dataset / "schedule.jsonl")
    if (
        len(episodes) != 18
        or len(schedule) != SLOTS
        or {ep["split"] for ep in episodes} != {"development"}
        or schedule != package._schedule(episodes)
    ):
        raise ValueError("P2 development scope changed")
    return {
        "schema_version": VERSION,
        "protocol": PROTOCOL,
        "dataset_package_id": verified["package_id"],
        "dataset_content_id": verified["dataset_content_id"],
        "dataset_manifest": read(dataset / "manifest.json"),
        "source_identity": package.implementation(),
        "environment_identity": environment_identity(),
        "episodes": episodes,
        "schedule": schedule,
        "config": asdict(config),
        "budget": budget_policy(allowance_usd),
        "rates": rates,
        "rates_sha256": fingerprint(rates),
        "price_document_sha256": rates["source"]["sha256"],
        "registry_path": str(Path(registry).resolve()),
        "total_deadline_seconds": 180,
        "execution_kind": "loopback_fixture" if fixture_url else "development_model",
        "fixture_url": fixture_url,
        "planned_opportunities": SLOTS,
        "planned_trajectories": 54,
        "output_cap_basis": "T6 common format reliability; not measured P2 reliability",
        "reliability_rule": {
            "unit": "family_by_method",
            "slots_per_cell": 30,
            "minimum_schema_valid": 29,
            "maximum_length_finishes": 1,
            "require_complete_audit": True,
        },
        "automatic_retry": False,
        "authorized": False,
        "pricing_requires_fresh_attestation": True,
    }


def prepare_execution(
    dataset, output, *, rates, registry, allowance_usd="3.00", fixture_url=None, price_document=None
):
    dataset, output = Path(dataset), Path(output)
    if output.exists():
        raise ValueError("execution output exists; preserve the frozen package")
    verified = package.verify(dataset)
    captured_rates = read(rates)
    price_source = (
        Path(price_document)
        if price_document is not None
        else Path(rates).with_name("pricing.html")
    )
    if price_document is None and not price_source.is_file():
        price_source = ROOT / "artifacts/p1_deepseek_development/docs/pricing.html"
    if file_hash(price_source) != captured_rates["source"]["sha256"]:
        raise ValueError("captured official pricing bytes changed")
    plan = _plan(dataset, verified, captured_rates, registry, allowance_usd, fixture_url)
    plan["execution_id"] = fingerprint(plan)
    output.mkdir(parents=True, exist_ok=False)
    shutil.copytree(dataset, output / "dataset")
    shutil.copyfile(price_source, output / "price_document.html")
    write_json(output / "execution.json", plan)
    write_json(output / "authorization.template.json", authorization_template(plan))
    write_json(
        output / "price_attestation.template.json",
        {
            "execution_id": plan["execution_id"],
            "rates_sha256": plan["rates_sha256"],
            "verified_at": None,
            "evidence": None,
        },
    )
    return plan


def verify_execution(path):
    path = Path(path)
    plan = read(path / "execution.json")
    if plan["execution_id"] != fingerprint({k: v for k, v in plan.items() if k != "execution_id"}):
        raise ValueError("P2 execution identity changed")
    verified = package.verify(path / "dataset")
    expected = _plan(
        path / "dataset",
        verified,
        plan["rates"],
        plan["registry_path"],
        plan["budget"]["allowance"],
        plan["fixture_url"],
    )
    expected["execution_id"] = fingerprint(expected)
    if canonical(expected) != canonical(plan):
        raise ValueError("P2 execution scope, implementation or environment changed")
    if file_hash(path / "price_document.html") != plan["price_document_sha256"]:
        raise ValueError("captured pricing document changed")
    return plan


def authorization_template(plan):
    return {
        "schema_version": "controlled_execution_authorization_v1",
        "authorized": False,
        "execution_id": plan["execution_id"],
        "allowance_usd": plan["budget"]["allowance"],
        "max_attempts": SLOTS,
        "max_requested_output_tokens": SLOTS * CAP,
        "rates_sha256": plan["rates_sha256"],
        "authorization_evidence": None,
    }


def validate_authorization(plan, authorization):
    expected = authorization_template(plan)
    if not isinstance(authorization, dict):
        raise ValueError("explicit P2 execution authorization required")
    evidence = authorization.get("authorization_evidence")
    if not isinstance(evidence, str) or not evidence.strip():
        raise ValueError("explicit P2 execution authorization evidence required")
    expected.update(authorized=True, authorization_evidence=evidence)
    if canonical(authorization) != canonical(expected):
        raise ValueError("P2 authorization scope mismatch")


def utc_timestamp(value):
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.utcoffset() != timedelta(0):
            raise ValueError()
        return parsed
    except (ValueError, TypeError):
        raise ValueError("an explicit UTC timestamp is required") from None


def validate_attestation(plan, attestation, *, at=None):
    if (
        not isinstance(attestation, dict)
        or set(attestation) != {"execution_id", "rates_sha256", "verified_at", "evidence"}
        or attestation["execution_id"] != plan["execution_id"]
        or attestation["rates_sha256"] != plan["rates_sha256"]
        or not isinstance(attestation["evidence"], str)
        or not attestation["evidence"].strip()
    ):
        raise ValueError("matching price attestation required")
    now = datetime.now(timezone.utc) if at is None else utc_timestamp(at)
    if not 0 <= (now - utc_timestamp(attestation["verified_at"])).total_seconds() <= 86400:
        raise ValueError("fresh price attestation required")
