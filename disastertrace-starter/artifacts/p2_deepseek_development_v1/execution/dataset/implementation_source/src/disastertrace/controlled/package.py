"""Self-contained, regenerable P2 offline datasets and program acceptance artifacts."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from disastertrace.automated.common import (
    canonical,
    file_hash,
    fingerprint,
    read_jsonl,
    safe_child,
    strict_json,
    write_json,
    write_jsonl,
)
from disastertrace.automated.sources import parse_nhc

from . import compiler, generator, public_oracle, renderer, runtime, scorer
from .schema import METHODS, PROTOCOL, validate_episode

ROOT = Path(__file__).resolve().parents[3]
DOCUMENTS = (
    "docs/P2_CONTROLLED_SEMANTICS_V1.md",
    "docs/P2_AUTOMATIC_GOLD_VALIDATION.md",
    "docs/P2_EXECUTION_V1.md",
)
SHARED = (
    "__init__.py",
    "common.py",
    "provider.py",
    "workflow.py",
    "sources.py",
    "disasterbench.py",
    "dynamic.py",
    "methods.py",
    "cohort.py",
    "provider_capture.py",
    "budget_ledger.py",
    "run_store.py",
    "execution_observations.py",
)


def implementation() -> dict:
    paths = {
        str(p.relative_to(ROOT)): p
        for p in sorted((ROOT / "src/disastertrace/controlled").rglob("*.py"))
    }
    for name in ("__init__.py", "models.py"):
        path = ROOT / "src/disastertrace" / name
        paths[str(path.relative_to(ROOT))] = path
    for name in SHARED:
        path = ROOT / "src/disastertrace/automated" / name
        paths[str(path.relative_to(ROOT))] = path
    for name in DOCUMENTS:
        paths[name] = ROOT / name
    snapshot = {
        "schema_version": "controlled_recursive_implementation_v1",
        "files": {name: file_hash(path) for name, path in sorted(paths.items())},
    }
    return {**snapshot, "implementation_id": fingerprint(snapshot)}


def content_identity(bindings: list[dict]) -> str:
    episodes = generator.from_bindings(bindings)
    return fingerprint(
        {
            "protocol": PROTOCOL,
            "implementation_id": implementation()["implementation_id"],
            "episodes": episodes,
            "micro_fixtures": generator.micro_episodes(),
            "gold": [
                compiler.reference_at(ep, cp["checkpoint_id"])
                for ep in episodes
                for cp in ep["checkpoints"]
            ],
        }
    )


def _schedule(episodes: list[dict]) -> list[dict]:
    return [
        {
            "slot_number": number,
            "slot_id": method + ":" + ep["episode_id"] + ":" + cp["checkpoint_id"],
            "trajectory_id": method + ":" + ep["episode_id"],
            "method": method,
            "episode_id": ep["episode_id"],
            "group_id": ep["group_id"],
            "root_id": ep["root_id"],
            "family": ep["family"],
            "case": ep["case"],
            "branch": ep["branch"],
            "checkpoint_id": cp["checkpoint_id"],
            "repeat": 0,
        }
        for number, (ep, method, cp) in enumerate(
            (
                (ep, method, cp)
                for index, ep in enumerate(episodes)
                for method in METHODS[index % 3 :] + METHODS[: index % 3]
                for cp in ep["checkpoints"]
            ),
            1,
        )
    ]


def _generated(bindings: list[dict]) -> dict:
    episodes, micros = generator.from_bindings(bindings), generator.micro_episodes()
    files = {
        "episodes.jsonl": episodes,
        "micro_fixtures.jsonl": micros,
        "schedule.jsonl": _schedule(episodes),
    }
    gold = []
    oracle_checks = 0
    for kind, selected in (("development", episodes), ("synthetic_fixture", micros)):
        for ep in selected:
            validate_episode(ep)
            for cp in ep["checkpoints"]:
                reference = compiler.reference_at(ep, cp["checkpoint_id"])
                if kind == "development":
                    gold.append(
                        {
                            "episode_id": ep["episode_id"],
                            "checkpoint_id": cp["checkpoint_id"],
                            "reference": reference,
                        }
                    )
                for method in METHODS:
                    observed = public_oracle.answer(
                        renderer.render_request(ep, cp["checkpoint_id"], method=method)
                    )
                    if observed != reference:
                        raise ValueError("private compiler/public oracle disagree")
                    oracle_checks += 1
    files["private/gold.jsonl"] = gold
    initial = []
    for ep in episodes:
        for method in METHODS:
            request = renderer.render_request(ep, "c0", method=method)
            initial.append(
                {
                    "episode_id": ep["episode_id"],
                    "method": method,
                    "request": request,
                    "request_sha256": fingerprint(request),
                    "kind": "unsent_empty_carrier_request",
                    "model_calls": 0,
                }
            )
    files["public/initial_requests.jsonl"] = initial
    diagnostics = []
    for method in METHODS:
        for backend in (*public_oracle.backends, "invalid-control"):
            traces = runtime.rehearse(episodes, method, backend)
            report = scorer.score(episodes, traces, method)
            if (
                backend in {"correct", "per-key-latest-issued"}
                and report["metrics"]["overall_grounding"]["value"] != 1
            ):
                raise ValueError("valid public control failed")
            failures = {
                "clear-omitted": ("U1", "preservation"),
                "latest-arrival": ("U2", "known_grounded_accuracy"),
                "global-latest-document": ("U1", "preservation"),
                "always-unknown": ("U3", "known_grounded_accuracy"),
                "always-known": ("U3", "unknown_accuracy"),
                "always-copy-previous": ("U1", "update_success"),
                "correct-value-wrong-source": ("U2", "provenance_refresh"),
            }
            if backend in failures:
                family, metric = failures[backend]
                value = report["by_family"][family]["metrics"][metric]["value"]
                if value is None or value >= 1:
                    raise ValueError("targeted mutant fails to expose its declared opportunity")
            if (
                backend == "invalid-control"
                and report["metrics"]["schema_success"]["numerator"] != 72
            ):
                raise ValueError("invalid-response control did not retain its failed opportunities")
            stem = f"diagnostics/{method}/{backend}"
            files[stem + "/trace.jsonl"] = traces
            files[stem + "/score.json"] = report
            diagnostics.append(
                {
                    "method": method,
                    "backend": backend,
                    "responses": len(traces),
                    "metrics": report["metrics"],
                    "model_calls": 0,
                }
            )
    files["audit.json"] = {
        "schema_version": "controlled_offline_acceptance_v1",
        "status": "passed",
        "independent_compiler_oracle_comparisons": oracle_checks,
        "development_episodes": 18,
        "development_checkpoints": 90,
        "micro_fixture_episodes": 12,
        "micro_fixture_checkpoints": 60,
        "diagnostic_responses": 2700,
        "program_configurations": 30,
        "model_calls": 0,
        "heldout_model_calls": 0,
        "new_human_annotations": 0,
        "quarantine": [],
        "quarantine_scope": (
            "This fixed generator admits all instances; external invalid graphs raise "
            "admission errors, never unknown Gold."
        ),
        "controls": diagnostics,
    }
    return files


def _plan(bindings: list[dict]) -> dict:
    return {
        "schema_version": "controlled_offline_preparation_v1",
        "protocol": PROTOCOL,
        "status": "P2_OFFLINE_READY",
        "dataset_content_id": content_identity(bindings),
        "development_episodes": 18,
        "development_checkpoints": 90,
        "source_groups": list(generator.EVENTS),
        "micro_fixture_episodes": 12,
        "micro_fixture_checkpoints": 60,
        "planned_model_slots": 270,
        "planned_model_trajectories": 54,
        "source_case_assignment": {
            event: "secondary" if index == 2 else "primary"
            for index, event in enumerate(generator.EVENTS)
        },
        "model_calls": 0,
        "heldout_model_calls": 0,
        "model_settings_selected": False,
        "selected_output_cap": None,
        "live_ready": False,
        "live_authorized": False,
        "new_human_annotations": 0,
        "llm_judge": False,
        "automatic_retry": False,
        "source_group_interpretation": (
            "Initial values inherit named source groups; later updates are controlled "
            "constructions, not additional observed storms."
        ),
        "next_step": (
            "Freeze P2-specific execution settings and separately authorize a complete "
            "model matrix after NHC output calibration."
        ),
    }


def prepare(source_build: Path, output: Path) -> dict:
    output = Path(output)
    if output.exists():
        raise ValueError("output exists; preserve the earlier package")
    episodes, bindings = generator.development_episodes(Path(source_build))
    source_records = read_jsonl(Path(source_build) / "records/nhc_records.jsonl")
    parents = [
        next(r for r in source_records if r["record_id"] == b["source_record_id"]) for b in bindings
    ]
    generated = _generated(bindings)
    plan, impl = _plan(bindings), implementation()
    generated.update(
        {
            "plan.json": plan,
            "source_bindings.json": bindings,
            "parent_sources.jsonl": parents,
            "implementation.json": impl,
        }
    )
    output.mkdir(parents=True, exist_ok=False)
    for name, value in generated.items():
        (write_jsonl if name.endswith(".jsonl") else write_json)(output / name, value)
    for name in impl["files"]:
        destination = output / "implementation_source" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((ROOT / name).read_bytes())
    files = {
        str(path.relative_to(output)): file_hash(path)
        for path in sorted(output.rglob("*"))
        if path.is_file()
    }
    manifest = {"schema_version": "controlled_package_manifest_v1", "files": files}
    manifest["package_id"] = fingerprint(manifest)
    write_json(output / "manifest.json", manifest)
    return {**plan, "package_id": manifest["package_id"], "artifacts": len(files)}


def _read(path: Path):
    return read_jsonl(path) if path.suffix == ".jsonl" else strict_json(path.read_text())


def verify(output: Path) -> dict:
    output = Path(output)
    manifest = _read(output / "manifest.json")
    if manifest["package_id"] != fingerprint(
        {k: v for k, v in manifest.items() if k != "package_id"}
    ):
        raise ValueError("package identity changed")
    inventory = {
        str(p.relative_to(output))
        for p in output.rglob("*")
        if p.is_file() and p != output / "manifest.json"
    }
    if set(manifest["files"]) != inventory:
        raise ValueError("package file inventory changed")
    for name, digest in manifest["files"].items():
        if file_hash(safe_child(output, name)) != digest:
            raise ValueError("package file changed: " + name)
    impl = implementation()
    if _read(output / "implementation.json") != impl:
        raise ValueError("controlled implementation changed; create a new package")
    parents = _read(output / "parent_sources.jsonl")
    if len(parents) != 3 or [record["storm_id"] for record in parents] != list(generator.EVENTS):
        raise ValueError("parent source scope changed")
    for record in parents:
        provenance = record["provenance"]
        if sha256(record["raw_text"].encode()).hexdigest() != provenance["source_sha256"]:
            raise ValueError("parent source bytes changed")
        parsed = parse_nhc(
            record["raw_text"],
            source_id=record["source_id"],
            source_url=provenance["source_url"],
            source_sha256=provenance["source_sha256"],
        )
        if not parsed["admitted"] or parsed["record"] != record:
            raise ValueError("inherited initial source values differ from the original parser")
    bindings = _read(output / "source_bindings.json")
    build_ids = {binding["source_build_id"] for binding in bindings}
    if (
        len(build_ids) != 1
        or generator.bindings_from_records(parents, next(iter(build_ids))) != bindings
    ):
        raise ValueError("source binding changed")
    generated = _generated(bindings)
    generated.update(
        {
            "plan.json": _plan(bindings),
            "source_bindings.json": bindings,
            "parent_sources.jsonl": parents,
            "implementation.json": impl,
        }
    )
    expected = set(generated) | {"implementation_source/" + name for name in impl["files"]}
    if expected != inventory:
        raise ValueError("unexpected or omitted generated artifact")
    for name, value in generated.items():
        if canonical(_read(output / name)) != canonical(value):
            raise ValueError("semantic regeneration differs: " + name)
    for name, digest in impl["files"].items():
        if file_hash(output / "implementation_source" / name) != digest:
            raise ValueError("archived implementation changed")
    return {
        "status": "passed",
        "package_id": manifest["package_id"],
        "dataset_content_id": generated["plan.json"]["dataset_content_id"],
        "verified_artifacts": len(inventory),
        "model_calls": 0,
        "live_ready": False,
    }
