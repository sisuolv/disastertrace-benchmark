"""Immutable offline rescoring of locally trusted, hash-verified source snapshots."""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import sys
import tempfile
import threading
import uuid
from contextlib import contextmanager
from pathlib import Path

from .common import file_hash, fingerprint, read_jsonl, safe_child, strict_json, write_json

_IMPORT_LOCK = threading.RLock()


def _read(path: Path) -> dict:
    value = strict_json(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError("rescoring artifact must contain a JSON object")
    return value


def _tree_hashes(root: Path) -> dict:
    if not root.is_dir():
        raise ValueError("artifact root must be a directory")
    files = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError("artifact trees must not contain symlinks")
        if path.is_file():
            files[path.relative_to(root).as_posix()] = file_hash(path)
    return files


def _verify_implementation(source: Path, recorded: dict) -> None:
    expected = {key: value for key, value in recorded.items() if key != "implementation_id"}
    if recorded.get("implementation_id") != fingerprint(expected):
        raise ValueError("implementation fingerprint mismatch")
    if recorded.get("schema_version") != "automated_implementation_v1":
        raise ValueError("unsupported saved implementation schema")
    files = recorded.get("files")
    if not isinstance(files, dict) or "__init__.py" not in files or "workflow.py" not in files:
        raise ValueError("incomplete saved implementation")
    if any(Path(name).name != name or not name.endswith(".py") for name in files):
        raise ValueError("invalid implementation source path")
    actual = {}
    for path in sorted(source.glob("*.py")):
        if path.is_symlink() or not path.is_file():
            raise ValueError("implementation sources must be regular local files")
        actual[path.name] = file_hash(path)
    if actual != files:
        raise ValueError("implementation source hashes or file set changed")


def _verify_archived_build(build_path: Path) -> tuple[dict, dict]:
    manifest = _read(build_path / "manifest.json")
    if manifest.get("build_id") != fingerprint(
        {key: value for key, value in manifest.items() if key != "build_id"}
    ):
        raise ValueError("historical build manifest fingerprint mismatch")
    if manifest.get("schema_version") != "automated_build_v1" or not isinstance(
        manifest.get("files"), dict
    ):
        raise ValueError("unsupported historical build manifest")
    for name, expected in manifest["files"].items():
        path = safe_child(build_path, name)
        if not path.is_file() or path.is_symlink() or file_hash(path) != expected:
            raise ValueError("historical build artifact hash changed: " + name)
    implementation = _read(build_path / "implementation.json")
    source = build_path / "implementation_source/automated"
    _verify_implementation(source, implementation)
    required = {"implementation.json"} | {
        "implementation_source/automated/" + name for name in implementation["files"]
    }
    if not required <= set(manifest["files"]):
        raise ValueError("historical build does not bind all executable implementation files")
    return manifest, implementation


@contextmanager
def _loaded_snapshot(source: Path, implementation: dict):
    # This isolates module identity, not arbitrary code execution. Snapshots must be trusted.
    with _IMPORT_LOCK, tempfile.TemporaryDirectory(prefix="disastertrace-snapshot-") as scratch:
        _verify_implementation(source, implementation)
        isolated_source = Path(scratch) / "automated"
        isolated_source.mkdir()
        for filename in implementation["files"]:
            (isolated_source / filename).write_bytes((source / filename).read_bytes())
        _verify_implementation(isolated_source, implementation)
        name = "_disastertrace_offline_" + uuid.uuid4().hex
        previous_bytecode = sys.dont_write_bytecode
        sys.dont_write_bytecode = True
        try:
            spec = importlib.util.spec_from_file_location(
                name,
                isolated_source / "__init__.py",
                submodule_search_locations=[str(isolated_source)],
            )
            if spec is None or spec.loader is None:
                raise ValueError("cannot load saved implementation package")
            package = importlib.util.module_from_spec(spec)
            sys.modules[name] = package
            spec.loader.exec_module(package)
            yield name
        finally:
            for module_name in list(sys.modules):
                if module_name == name or module_name.startswith(name + "."):
                    del sys.modules[module_name]
            sys.dont_write_bytecode = previous_bytecode


def _original_inventory(build_path: Path, run_path: Path, historical_score: Path | None) -> dict:
    run = _read(run_path / "run.json")
    if run.get("track") != "dynamic":
        raise ValueError("offline v2 rescoring applies only to the dynamic weather track")
    collection = None
    if "collection_binding" in run:
        if run["collection_binding"].get("relative_path") != "../collection":
            raise ValueError("unsupported historical collection binding")
        collection_path = run_path.parent / "collection"
        collection = {"path": str(collection_path), "files": _tree_hashes(collection_path)}
    return {
        "build": {"path": str(build_path), "files": _tree_hashes(build_path)},
        "run": {"path": str(run_path), "files": _tree_hashes(run_path)},
        "collection": collection,
        "historical_score": None
        if historical_score is None
        else {"path": str(historical_score), "sha256": file_hash(historical_score)},
    }


def _check_output_location(output: Path, original: dict, *, must_be_new: bool) -> None:
    protected = [Path(original["build"]["path"]), Path(original["run"]["path"])]
    if original["collection"] is not None:
        protected.append(Path(original["collection"]["path"]).parent)
    target = output.resolve()
    if any(target.is_relative_to(root.resolve()) for root in protected):
        raise ValueError(
            "derived output must be outside historical build/run/collection directories"
        )
    if must_be_new and (output.exists() or output.is_symlink()):
        raise ValueError("derived output already exists; choose a new path")


def _inputs_unchanged(original: dict) -> None:
    historical = original["historical_score"]
    actual = _original_inventory(
        Path(original["build"]["path"]),
        Path(original["run"]["path"]),
        None if historical is None else Path(historical["path"]),
    )
    if actual != original:
        raise ValueError("original artifact hashes changed during or after rescoring")


def _historical_replay(build_path: Path, run_path: Path, output: Path) -> dict:
    _, implementation = _verify_archived_build(build_path)
    with _loaded_snapshot(build_path / "implementation_source/automated", implementation) as name:
        workflow = importlib.import_module(name + ".workflow")
        return workflow.score(build_path, run_path, output)


def _selected_inputs(build_path: Path, run_path: Path) -> tuple[list[dict], list[dict]]:
    config = _read(run_path / "run.json")
    selected = set(config["selected_episode_ids"])
    episodes = [
        episode
        for episode in read_jsonl(build_path / "episodes/dynamic_episodes.jsonl")
        if episode["episode_id"] in selected
    ]
    if [episode["episode_id"] for episode in episodes] != config["selected_episode_ids"]:
        raise ValueError("historical episode selection mismatch")
    return episodes, read_jsonl(run_path / "trace.jsonl")


def _snapshot_current(output: Path) -> dict:
    source = Path(__file__).parent
    destination = output / "implementation_source/automated"
    destination.mkdir(parents=True)
    for path in sorted(source.glob("*.py")):
        (destination / path.name).write_bytes(path.read_bytes())
    implementation = {
        "schema_version": "automated_implementation_v1",
        "files": _tree_hashes(destination),
    }
    implementation["implementation_id"] = fingerprint(implementation)
    _verify_implementation(source, implementation)
    write_json(output / "implementation.json", implementation)
    return implementation


def _compute_v2(
    source: Path, implementation: dict, episodes: list[dict], traces: list[dict]
) -> tuple[dict, dict]:
    with _loaded_snapshot(source, implementation) as name:
        scorer = importlib.import_module(name + ".scoring_v2")
        support = importlib.import_module(name + ".evidence_support")
        return scorer.score_dynamic_v2(episodes, traces), support.build_evidence_index(episodes)


def _comparison(v1: dict, v2: dict) -> dict:
    invariants = {}
    for metric in (
        "schema_success",
        "state_accuracy",
        "action_accuracy",
        "unknown_accuracy",
        "known_answer_coverage",
    ):
        if v1["metrics"][metric] != v2["metrics"][metric]:
            raise ValueError("rescoring changed frozen factual/schema/action metric: " + metric)
        invariants[metric] = v1["metrics"][metric]
    before = {(row["episode_id"], row["checkpoint_id"]): row for row in v1["per_checkpoint"]}
    after = {(row["episode_id"], row["checkpoint_id"]): row for row in v2["per_checkpoint"]}
    if before.keys() != after.keys():
        raise ValueError("rescoring changed the checkpoint denominator")
    per_field = []
    for key, old in before.items():
        new = after[key]
        if old["status"] != new["status"] or old["action_correct"] != new["action_correct"]:
            raise ValueError("rescoring changed response validity or action correctness")
        if old["slots"].keys() != new["slots"].keys():
            raise ValueError("rescoring changed the field denominator")
        for field, old_slot in old["slots"].items():
            new_slot = new["slots"][field]
            if old_slot["value_correct"] != new_slot["value_correct"]:
                raise ValueError("rescoring changed field value correctness")
            per_field.append(
                {
                    "episode_id": key[0],
                    "checkpoint_id": key[1],
                    "field": field,
                    "v1": {name: old_slot[name] for name in ("value_correct", "grounded_correct")},
                    "v2": {name: new_slot[name] for name in ("value_correct", "grounded_correct")},
                    "grounding_changed": old_slot["grounded_correct"]
                    != new_slot["grounded_correct"],
                    "reason": new_slot.get("reason"),
                    "citation_checks": new_slot.get("citation_checks", []),
                }
            )
    return {
        "schema_version": "offline_scoring_comparison_v1",
        "new_provider_requests": 0,
        "interpretation": "Different evidence validation of identical saved answers; not a change in model behavior.",
        "invariants": invariants,
        "checkpoint_count": len(before),
        "field_count": len(per_field),
        "metric_differences": {
            metric: {"v1": value, "v2": v2["metrics"][metric]}
            for metric, value in v1["metrics"].items()
            if metric in v2["metrics"] and value != v2["metrics"][metric]
        },
        "per_field": per_field,
        "changed_fields": [row for row in per_field if row["grounding_changed"]],
    }


def rescore(
    build_path: Path, run_path: Path, output: Path, *, historical_score: Path | None = None
) -> dict:
    build_path, run_path = Path(build_path).resolve(), Path(run_path).resolve()
    output = Path(output)
    historical_score = None if historical_score is None else Path(historical_score).resolve()
    original = _original_inventory(build_path, run_path, historical_score)
    _check_output_location(output, original, must_be_new=True)
    build_manifest, old_implementation = _verify_archived_build(build_path)
    output.mkdir(parents=True)
    baseline = _historical_replay(build_path, run_path, output / "baseline_v1.json")
    if historical_score is not None and baseline != _read(historical_score):
        raise ValueError("provided historical score differs from archived implementation replay")
    episodes, traces = _selected_inputs(build_path, run_path)
    implementation = _snapshot_current(output)
    v2, index = _compute_v2(
        output / "implementation_source/automated", implementation, episodes, traces
    )
    comparison = _comparison(baseline, v2)
    write_json(output / "score_v2.json", v2)
    write_json(output / "evidence_index_v2.json", index)
    write_json(output / "comparison.json", comparison)
    _inputs_unchanged(original)
    manifest = {
        "schema_version": "offline_rescore_v1",
        "new_provider_requests": 0,
        "original_inputs": original,
        "historical_build_id": build_manifest["build_id"],
        "historical_implementation_id": old_implementation["implementation_id"],
        "new_implementation_id": implementation["implementation_id"],
        "evidence_index_sha256": fingerprint(index),
        "scorer_version": v2["scorer_version"],
        "trusted_executable_source_required": True,
        "files": _tree_hashes(output),
    }
    manifest["rescore_id"] = fingerprint(manifest)
    write_json(output / "manifest.json", manifest)
    return manifest


def verify_rescore(output: Path) -> dict:
    output = Path(output).resolve()
    manifest = _read(output / "manifest.json")
    if (
        manifest.get("schema_version") != "offline_rescore_v1"
        or manifest.get("new_provider_requests") != 0
    ):
        raise ValueError("unsupported offline rescoring manifest")
    if manifest.get("rescore_id") != fingerprint(
        {key: value for key, value in manifest.items() if key != "rescore_id"}
    ):
        raise ValueError("rescoring manifest fingerprint mismatch")
    actual = _tree_hashes(output)
    actual.pop("manifest.json", None)
    if actual != manifest.get("files"):
        raise ValueError("derived artifact hashes or file set changed")
    original = manifest["original_inputs"]
    _check_output_location(output, original, must_be_new=False)
    _inputs_unchanged(original)
    build_path, run_path = Path(original["build"]["path"]), Path(original["run"]["path"])
    build_manifest, old_implementation = _verify_archived_build(build_path)
    if (
        manifest["historical_build_id"] != build_manifest["build_id"]
        or manifest["historical_implementation_id"] != old_implementation["implementation_id"]
    ):
        raise ValueError("historical implementation identity changed")
    with tempfile.TemporaryDirectory(prefix="disastertrace-offline-rescore-") as scratch:
        baseline = _historical_replay(build_path, run_path, Path(scratch) / "baseline.json")
    if baseline != _read(output / "baseline_v1.json"):
        raise ValueError("recomputed historical score differs")
    historical_score = original["historical_score"]
    if historical_score is not None and baseline != _read(Path(historical_score["path"])):
        raise ValueError("recomputed provided historical score differs")
    implementation = _read(output / "implementation.json")
    if implementation["implementation_id"] != manifest["new_implementation_id"]:
        raise ValueError("derived implementation identity changed")
    episodes, traces = _selected_inputs(build_path, run_path)
    v2, index = _compute_v2(
        output / "implementation_source/automated", implementation, episodes, traces
    )
    if v2 != _read(output / "score_v2.json") or index != _read(output / "evidence_index_v2.json"):
        raise ValueError("recomputed v2 score or evidence index differs")
    with _loaded_snapshot(output / "implementation_source/automated", implementation) as name:
        archived_migration = importlib.import_module(name + ".rescoring")
        comparison = archived_migration._comparison(baseline, v2)
    if comparison != _read(output / "comparison.json"):
        raise ValueError("recomputed per-field comparison differs")
    if (
        manifest["evidence_index_sha256"] != fingerprint(index)
        or manifest["scorer_version"] != v2["scorer_version"]
    ):
        raise ValueError("recomputed scorer or evidence identity differs")
    _inputs_unchanged(original)
    final_files = _tree_hashes(output)
    final_files.pop("manifest.json", None)
    if final_files != manifest["files"] or manifest != _read(output / "manifest.json"):
        raise ValueError("derived artifacts changed during verification")
    return {
        "schema_version": "offline_rescore_verification_v1",
        "verified": True,
        "rescore_id": manifest["rescore_id"],
        "new_provider_requests": 0,
        "historical_artifacts_unchanged": True,
        "changed_fields": len(comparison["changed_fields"]),
        "historical_collection_reaudited": original["collection"] is not None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    migrate = commands.add_parser(
        "rescore", help="derive v1/v2 scores from a trusted local snapshot"
    )
    migrate.add_argument("--build", required=True, type=Path)
    migrate.add_argument("--run", required=True, type=Path)
    migrate.add_argument("--output", required=True, type=Path)
    migrate.add_argument("--historical-score", type=Path)
    verify = commands.add_parser("verify", help="verify hashes and recompute the derived package")
    verify.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.command == "rescore":
        result = rescore(args.build, args.run, args.output, historical_score=args.historical_score)
        print("Created offline rescore " + result["rescore_id"] + "; new provider requests: 0")
    else:
        result = verify_rescore(args.output)
        print("Verified offline rescore " + result["rescore_id"] + "; new provider requests: 0")


if __name__ == "__main__":
    main()
