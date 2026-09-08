import json
from copy import deepcopy
from pathlib import Path

import pytest

from disastertrace.automated.common import fingerprint
from disastertrace.automated.dynamic import render_request as legacy_render
from disastertrace.automated.provider import ProviderConfig
from disastertrace.automated.provider import validate_public_request as legacy_validate
from disastertrace.controlled import generator, package, provider_adapter, renderer

ROOT = Path(__file__).resolve().parents[1]


def test_protocol_adapters_reject_cross_protocol_and_private_fields():
    episode = generator.micro_episodes()[0]
    request = renderer.render_request(episode, "c1", method="snapshot")
    config = ProviderConfig.from_dict(
        json.loads((ROOT / "artifacts/p1_deepseek_development/provider.json").read_text())
    )
    prepared = provider_adapter.prepare(request, config)
    assert prepared["wire_payload_sha256"] == fingerprint(prepared["payload"])
    with pytest.raises(ValueError):
        legacy_validate(request)
    old_episode = json.loads(
        (ROOT / "work/build-deepseek-v1/episodes/dynamic_episodes.jsonl")
        .read_text()
        .splitlines()[0]
    )
    with pytest.raises(ValueError):
        provider_adapter.prepare(legacy_render(old_episode, "c0", None), config)
    request["gold"] = "PRIVATE_SENTINEL"
    with pytest.raises(ValueError):
        provider_adapter.prepare(request, config)


def test_preparation_and_semantic_verification_are_offline(tmp_path, monkeypatch):
    import socket

    from disastertrace.automated.provider import ProviderClient

    def forbidden(*args, **kwargs):
        pytest.fail("offline P2 attempted a network/model request")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(ProviderClient, "complete", forbidden)
    first = tmp_path / "first"
    summary = package.prepare(ROOT / "work/build-cohort-v1", first)
    assert summary["model_calls"] == 0
    assert summary["development_episodes"] == 18
    assert summary["planned_model_slots"] == 270
    assert summary["micro_fixture_episodes"] == 12
    assert package.verify(first)["status"] == "passed"
    with pytest.raises(ValueError):
        package.prepare(ROOT / "work/build-cohort-v1", first)
    plan_path = first / "plan.json"
    plan = json.loads(plan_path.read_text())
    plan["model_calls"] = 1
    plan_path.write_text(json.dumps(plan))
    manifest_path = first / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    from disastertrace.automated.common import file_hash

    manifest["files"]["plan.json"] = file_hash(plan_path)
    manifest["package_id"] = fingerprint({k: v for k, v in manifest.items() if k != "package_id"})
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        package.verify(first)


def test_content_identity_ignores_parent_build_location_but_not_values():
    bindings = generator.source_bindings(ROOT / "work/build-cohort-v1")
    alternate = deepcopy(bindings)
    for binding in alternate:
        binding["source_build_id"] = "different-path-derived-build-id"
    assert package.content_identity(bindings) == package.content_identity(alternate)
    alternate[0]["inherited_values"]["maximum_wind_mph"] += 1
    assert package.content_identity(bindings) != package.content_identity(alternate)


def test_recursive_manifest_relocation_and_resource_binding(tmp_path, monkeypatch):
    bindings = generator.source_bindings(ROOT / "work/build-cohort-v1")
    before = package.content_identity(bindings)
    implementation = package.implementation()
    assert "src/disastertrace/__init__.py" in implementation["files"]
    assert "src/disastertrace/models.py" in implementation["files"]
    for name in implementation["files"]:
        destination = tmp_path / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((ROOT / name).read_bytes())
    monkeypatch.setattr(package, "ROOT", tmp_path)
    assert package.implementation() == implementation
    assert package.content_identity(bindings) == before
    resource = tmp_path / "docs/P2_CONTROLLED_SEMANTICS_V1.md"
    resource.write_bytes(resource.read_bytes() + b"\nChanged rule resource.\n")
    assert package.content_identity(bindings) != before
