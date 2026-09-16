"""Mandatory qualification for new formal H15 sessions; legacy replay stays explicit."""

import hashlib
import json
from pathlib import Path

from ..monitoring_fixed_v1.admission import AdmissionEngine, _score_replayed
from ..monitoring_fixed_v1.outcome_policies import PROVIDER_BINDINGS
from ..monitoring_fixed_v1.outcomes import ComparisonContract, OutcomeRegistry, experiment_spec
from .execution import bind_execution
from .session_checkpoint import SessionCoordinator
from .source_execution import bind_source
from .spool_backend import digest, publish, read
from .targets import canonical_hash

FORMAL_CONFIG = {
    "execution_mode": "production_bound_v1",
    "pending_timing_policy": "lifecycle_wall_v1",
    "admission_semantics": "measurement.v3",
    "session_runtime": "typed_admission_v1",
    "formal_resolution_policy": "h15_routine_archive.v1",
}


def _validate_config(config):
    if any(config.get(k) != v for k, v in FORMAL_CONFIG.items()):
        raise ValueError(
            "Formal session requires production identity, clock, provider policy and v3 admission"
        )


def required_source_files():
    package = Path(__file__).resolve().parents[1]
    return sorted(
        [
            *(package / "monitoring_v1").rglob("*.py"),
            *(package / "monitoring_fixed_v1").rglob("*.py"),
            package / "forecast_task/common.py",
        ]
    )


def _no_outcomes(value):
    if isinstance(value, dict):
        if {"outcomes", "OUTCOMES", "evaluator_results"}.intersection(value):
            raise ValueError("Evaluator outcomes cannot enter a formal policy session")
        for child in value.values():
            _no_outcomes(child)
    elif isinstance(value, list):
        for child in value:
            _no_outcomes(child)


class FormalSession:
    def __init__(
        self,
        data,
        bank,
        config,
        *,
        comparison,
        bound_files,
        directory,
        backend=None,
        source_backend=None,
    ):
        _no_outcomes(data)
        _validate_config(config)
        self.bound_files = json.loads(json.dumps(bound_files))
        if not {str(p) for p in required_source_files()} <= set(self.bound_files):
            raise ValueError("Formal source manifest is incomplete")
        self._verify_files()
        bound_config = bind_source(bind_execution(config, backend), source_backend)
        spec = experiment_spec(data, bank, bound_config)
        comparison.validate(spec["invariants"], spec["interventions"])
        self.comparison = comparison
        self.coordinator = SessionCoordinator(
            data, bank, bound_config, backend=backend, source_backend=source_backend
        )
        self.directory = Path(directory)
        self.directory.mkdir(exist_ok=False)
        self.contract = {
            "schema": "disastertrace.formal_session.v2",
            "input_identity": {"data": canonical_hash(data), "bank": canonical_hash(bank)},
            "files": self.bound_files,
            "comparison": comparison.export(),
            "initial_experiment": spec,
            "provider_policy": FORMAL_CONFIG["formal_resolution_policy"],
            "outcomes_visible_to_policy": False,
            "assurance": "managed frozen execution; not arbitrary Python sandboxing",
        }
        publish(self.directory / "CONTRACT.json", self.contract)

    @classmethod
    def fork(cls, path, data, bank, *, parent_directory, comparison, bound_files,
             directory, controls, witness_directory=None):
        """Create a separately sealed child from a captured or witnessed prefix."""
        from .session_checkpoint import CONTROLS

        path, parent_directory = Path(path), Path(parent_directory)
        if not controls or not set(controls) <= CONTROLS:
            raise ValueError("Explicit registered child controls required")
        checkpoint = read(path)
        _no_outcomes(data)
        parent_ref, parent_files, initial = qualify_parent_checkpoint(
            path, parent_directory, data, bank, witness_directory=witness_directory
        )
        coordinator = SessionCoordinator.restore(checkpoint, data, bank)
        config = {**coordinator.config, **controls}
        _validate_config(config)
        spec = experiment_spec(data, bank, config)
        comparison.validate(**initial)
        comparison.validate(**spec)
        if config.get("residual_query_plan") is not None:
            from .residual_query_plan import validate_residual_plan

            validate_residual_plan(data, checkpoint, config["residual_query_plan"])
        value = cls.__new__(cls)
        if any(k in bound_files and bound_files[k] != v for k, v in parent_files.items()):
            raise ValueError("Child and parent file bindings conflict")
        value.bound_files = {**bound_files, **parent_files}
        if not {str(p) for p in required_source_files()} <= set(value.bound_files):
            raise ValueError("Formal child source manifest is incomplete")
        value._verify_files()
        value.comparison, value.coordinator = comparison, coordinator
        coordinator.config = config
        value.directory = Path(directory)
        value.directory.mkdir(exist_ok=False)
        value.contract = {
            "schema": "disastertrace.formal_session.v3_branch",
            "input_identity": {"data": canonical_hash(data), "bank": canonical_hash(bank)},
            "files": value.bound_files, "comparison": comparison.export(),
            "initial_experiment": initial, "fork_experiment": spec,
            "parent_reference": parent_ref,
            "provider_policy": FORMAL_CONFIG["formal_resolution_policy"],
            "outcomes_visible_to_policy": False,
            "assurance": "managed frozen execution; verified inherited prefix; not arbitrary Python sandboxing",
        }
        publish(value.directory / "CONTRACT.json", value.contract)
        return value

    @classmethod
    def restore(cls, path, data, bank, *, directory, backend=None, source_backend=None):
        """Resume one serial owner from a checkpoint bound to its original run."""
        path, directory = Path(path), Path(directory)
        if (directory / "STOP.json").exists():
            raise ValueError("A stopped formal session cannot be reopened")
        marker = path.with_name(path.name + ".formal.json")
        if not marker.exists() or not (directory / "CONTRACT.json").exists():
            raise ValueError("A formal checkpoint binding is required")
        contract, checkpoint = read(directory / "CONTRACT.json"), read(path)
        binding = read(marker)
        expected = {
            "schema": "disastertrace.formal_checkpoint.v1",
            "formal_directory": str(directory.resolve()),
            "contract_file_sha256": digest(directory / "CONTRACT.json"),
            "checkpoint_file_sha256": digest(path),
            "checkpoint_payload_sha256": checkpoint["sha256"],
        }
        if binding != expected or contract.get("schema") not in {"disastertrace.formal_session.v2", "disastertrace.formal_session.v3_branch"}:
            raise ValueError("Original formal checkpoint binding changed")
        _no_outcomes(data)
        _validate_config(checkpoint["payload"]["config"])
        if contract.get("input_identity") != {"data": canonical_hash(data), "bank": canonical_hash(bank)}:
            raise ValueError("Formal input data/bank identity changed")
        value = cls.__new__(cls)
        value.bound_files, value.contract, value.directory = contract["files"], contract, directory
        if not {str(p) for p in required_source_files()} <= set(value.bound_files):
            raise ValueError("Formal source manifest is incomplete")
        value._verify_files()
        comparison = contract["comparison"]["payload"]
        value.comparison = ComparisonContract(
            comparison["invariants"], comparison["allowed_interventions"]
        )
        if value.comparison.export() != contract["comparison"]:
            raise ValueError("Formal comparison checksum changed")
        spec = experiment_spec(data, bank, checkpoint["payload"]["config"])
        value.comparison.validate(spec["invariants"], spec["interventions"])
        value.coordinator = SessionCoordinator.restore(
            checkpoint, data, bank, backend=backend, source_backend=source_backend
        )
        return value

    def _verify_files(self):
        for name, sha in self.bound_files.items():
            if hashlib.sha256(Path(name).read_bytes()).hexdigest() != sha:
                raise ValueError("Formal bound source/data file changed")

    @property
    def done(self):
        return self.coordinator.done

    @property
    def report(self):
        return self.coordinator.report

    def step(self, controls=None):
        self._verify_files()
        if (self.directory / "STOP.json").exists():
            raise ValueError("Formal session is already stopped")
        config = {**self.coordinator.config, **(controls or {})}
        _validate_config(config)
        spec = experiment_spec(self.coordinator.data, self.coordinator.bank, config)
        self.comparison.validate(spec["invariants"], spec["interventions"])
        return self.coordinator.step(controls)

    def snapshot(self):
        return self.coordinator.snapshot()

    def persist(self, path):
        self._verify_files()
        if (self.directory / "STOP.json").exists():
            raise ValueError("Formal session is already stopped")
        path = Path(path)
        checkpoint = self.coordinator.snapshot()
        if path.exists():
            if read(path) != checkpoint:
                raise ValueError("A saved formal checkpoint cannot be replaced")
        else:
            publish(path, checkpoint)
        marker = path.with_name(path.name + ".formal.json")
        binding = {
            "schema": "disastertrace.formal_checkpoint.v1",
            "formal_directory": str(self.directory.resolve()),
            "contract_file_sha256": digest(self.directory / "CONTRACT.json"),
            "checkpoint_file_sha256": digest(path),
            "checkpoint_payload_sha256": checkpoint["sha256"],
        }
        if marker.exists():
            if read(marker) != binding:
                raise ValueError("Formal checkpoint binding cannot be replaced")
        else:
            publish(marker, binding)
        # Both durable bindings precede the underlying outbox worker release.
        return self.coordinator.persist(path)

    def stop(self, reason):
        publish(
            self.directory / "STOP.json",
            {
                "reason": reason,
                "done": self.done,
                "contract_sha256": canonical_hash(self.contract),
                "report_sha256": canonical_hash(self.report) if self.report is not None else None,
            },
        )

    def finish(self, *, max_steps):
        if (self.directory / "STOP.json").exists():
            raise ValueError("Formal session is already stopped")
        if type(max_steps) is not int or max_steps <= 0:
            raise ValueError("Finite step ceiling required")
        try:
            for _ in range(max_steps):
                if self.done:
                    break
                self.step()
            if not self.done:
                raise ValueError("Formal session hit its registered step ceiling")
        except Exception:
            if not (self.directory / "STOP.json").exists():
                self.stop("failed_or_step_ceiling")
            raise
        if self.report is None:
            self.coordinator.finish()
        self.stop("completed")
        return self.report

    def export_journal(self, path):
        """Bind a terminal report and journal to their actual managed run."""
        path = Path(path)
        if path.parent.resolve() != self.directory.resolve():
            raise ValueError("Formal journal must be in its original run directory")
        self._verify_files()
        terminal = read(self.directory / "STOP.json")
        if terminal.get("report_sha256") != canonical_hash(self.report):
            raise ValueError("Formal terminal report identity changed")
        engine = AdmissionEngine.restore(self.report["event_replay"])
        engine.write_journal(path)
        publish(self.directory / "FORMAL_REPORT.json", self.report)
        publish(path.with_name(path.name + ".formal.json"), {
            "schema": "disastertrace.formal_journal.v1",
            "directory": str(self.directory.resolve()),
            "journal_sha256": digest(path),
            "contract_sha256": digest(self.directory / "CONTRACT.json"),
            "report_sha256": digest(self.directory / "FORMAL_REPORT.json"),
            "stop_sha256": digest(self.directory / "STOP.json"),
            "event_replay_sha256": canonical_hash(engine.export()),
        })
        return path


def qualify_parent_checkpoint(path, directory, data, bank, *, witness_directory=None):
    """Verify provenance separately from the mechanical controller restoration."""
    path, directory = Path(path), Path(directory)
    parent = read(directory / "CONTRACT.json")
    report, stop, checkpoint = (read(p) for p in
        (directory / "FORMAL_REPORT.json", directory / "STOP.json", path))
    cp = parent["comparison"]["payload"]
    comparison = ComparisonContract(cp["invariants"], cp["allowed_interventions"])
    engine = AdmissionEngine.restore(report["event_replay"])
    _verify_run_reference(directory / "admission.jsonl", directory, engine, comparison)
    if not stop["done"] or stop["reason"] != "completed":
        raise ValueError("Fork requires a verified completed parent")
    if parent["input_identity"] != {"data": canonical_hash(data), "bank": canonical_hash(bank)}:
        raise ValueError("Parent input identity changed")
    p = checkpoint["payload"]
    if p["schema"] != "disastertrace.session_quiescent.v1" or canonical_hash(p) != checkpoint["sha256"]:
        raise ValueError("Fork requires a valid quiescent checkpoint")
    if p["runtime"]["payload"]["contract"]["experiment"] != parent["initial_experiment"]:
        raise ValueError("Inherited experiment differs from original parent")
    files = {**parent["files"], **{str(f.resolve()): digest(f) for f in (
        path, directory / "CONTRACT.json", directory / "FORMAL_REPORT.json",
        directory / "STOP.json", directory / "admission.jsonl",
        directory / "admission.jsonl.formal.json")}}
    marker = path.with_name(path.name + ".formal.json")
    if witness_directory is None:
        expected = {
            "schema": "disastertrace.formal_checkpoint.v1",
            "formal_directory": str(directory.resolve()),
            "contract_file_sha256": digest(directory / "CONTRACT.json"),
            "checkpoint_file_sha256": digest(path),
            "checkpoint_payload_sha256": checkpoint["sha256"],
        }
        if not marker.exists() or read(marker) != expected:
            raise ValueError("Captured parent checkpoint binding required")
        files[str(marker.resolve())] = digest(marker)
        kind = "originally_captured_formal_checkpoint"
    else:
        witness = Path(witness_directory)
        names = ["PARENT_BINDING.json", "PREFIX_REPORT.json", "NOOP_REPORT.json", "NOOP_EQUIVALENCE.json", "RESULT.json"]
        binding, prefix, noop, equivalence, result = (read(witness / n) for n in names)
        if (path.resolve() != (witness / "PARENT_CHECKPOINT.json").resolve()
                or binding["original_directory"] != str(directory.resolve())
                or binding["checkpoint_sha256"] != digest(path)
                or binding["checkpoint_payload_sha256"] != checkpoint["sha256"]
                or binding["parent_contract_sha256"] != digest(directory / "CONTRACT.json")
                or binding["original_report_sha256"] != digest(directory / "FORMAL_REPORT.json")
                or binding["source_and_data_hashes"] != parent["files"]
                or digest(Path(binding["source_file"])) != binding["source_sha256"]
                or prefix["event_replay"] != p["runtime"]
                or noop != report or not equivalence["passed"] or not result["passed"]
                or equivalence["original_sha256"] != canonical_hash(report)
                or equivalence["continuation_sha256"] != canonical_hash(noop)):
            raise ValueError("Reconstructed parent witness differs from frozen original")
        files.update({str((witness / n).resolve()): digest(witness / n) for n in names})
        kind = "reconstructed_prefix_with_exact_original_continuation"
    for key, report_key in (("frames", "frames"), ("call_records", "calls"),
                            ("selector_records", "selector_calls"), ("source_receipts", "source_receipts")):
        rows = p["controller"][key]
        if rows != report[report_key][:len(rows)]:
            raise ValueError("Inherited controller is not the original report prefix")
    ledger_rows = p["ledger"]["events"]
    if ledger_rows != report["resource_events"][:len(ledger_rows)]:
        raise ValueError("Inherited fees differ from original parent prefix")
    return ({
        "kind": kind, "directory": str(directory.resolve()),
        "checkpoint_path": str(path.resolve()), "checkpoint_sha256": digest(path),
        "checkpoint_payload_sha256": checkpoint["sha256"], "next_tick": p["next_tick"],
        "clock": p["clock"], "original_contract_sha256": digest(directory / "CONTRACT.json"),
        "original_stop_sha256": digest(directory / "STOP.json"),
    }, files, parent["initial_experiment"])


def _verify_run_reference(path, directory, engine, comparison):
    path, directory = Path(path), Path(directory)
    if path.parent.resolve() != directory.resolve():
        raise ValueError("Formal journal belongs to a different directory")
    marker = path.with_name(path.name + ".formal.json")
    if not marker.exists():
        raise ValueError("Formal journal binding is missing")
    binding = read(marker)
    expected = {
        "schema": "disastertrace.formal_journal.v1", "directory": str(directory.resolve()),
        "journal_sha256": digest(path), "contract_sha256": digest(directory / "CONTRACT.json"),
        "report_sha256": digest(directory / "FORMAL_REPORT.json"),
        "stop_sha256": digest(directory / "STOP.json"),
        "event_replay_sha256": canonical_hash(engine.export()),
    }
    if binding != expected:
        raise ValueError("Formal journal/report binding changed")
    contract, report, stop = (read(directory / name) for name in
                              ("CONTRACT.json", "FORMAL_REPORT.json", "STOP.json"))
    if (contract.get("schema") not in {"disastertrace.formal_session.v2", "disastertrace.formal_session.v3_branch"}
            or not contract.get("input_identity")
            or contract["comparison"] != comparison.export()
            or contract["initial_experiment"] != engine.contract["experiment"]
            or stop["contract_sha256"] != canonical_hash(contract)
            or stop["report_sha256"] != canonical_hash(report)
            or report["event_replay"] != engine.export()):
        raise ValueError("Formal run contract/report identity changed")
    if contract["schema"] == "disastertrace.formal_session.v3_branch":
        reference = contract["parent_reference"]
        if (digest(Path(reference["checkpoint_path"])) != reference["checkpoint_sha256"]
                or digest(Path(reference["directory"]) / "STOP.json") != reference["original_stop_sha256"]):
            raise ValueError("Formal child parent binding changed")
        comparison.validate(**contract["fork_experiment"])
    for name, sha in contract["files"].items():
        if digest(Path(name)) != sha:
            raise ValueError("Formal bound source/data file changed")
    return contract["provider_policy"]


def score_formal(outcomes, arms, *, comparison, run_references=None, legacy=False):
    """Evaluator-only entry: provider-bound records and formal journals are required."""
    if not arms:
        raise ValueError("Registered formal arms required")
    if run_references is None and not legacy:
        raise ValueError("Formal scoring requires original run references; legacy replay is explicit")
    if run_references is not None and set(run_references) != set(arms):
        raise ValueError("Formal reference roster differs from scored arms")
    engines = {name: AdmissionEngine.from_journal(path) for name, path in arms.items()}
    first = next(iter(engines.values()))
    policies = set()
    for name, engine in engines.items():
        other = (
            engine.contract.get("experiment", {})
            .get("invariants", {})
            .get("other_frozen_config", {})
        )
        if (
            engine.semantics_version != "measurement.v3"
            or other.get("formal_resolution_policy") not in PROVIDER_BINDINGS
            or other.get("execution_mode") != "production_bound_v1"
            or other.get("pending_timing_policy") != "lifecycle_wall_v1"
        ):
            raise ValueError("Formal score cannot admit a legacy or unbound journal")
        policy = other["formal_resolution_policy"]
        if (run_references is not None
                and _verify_run_reference(arms[name], run_references[name], engine, comparison) != policy):
            raise ValueError("Formal outcome policy differs from executed provider policy")
        policies.add(policy)
    if len(policies) != 1:
        raise ValueError("Formal arms require a common provider policy")
    registry = OutcomeRegistry(first.targets.values(), mode="formal_provider_bound")
    versions = {}
    for row in outcomes:
        if row.get("resolution_policy") not in policies:
            raise ValueError("Outcome provider policy differs from formal run")
        registry.register({k: v for k, v in row.items() if k != "opportunity_id"})
        if row["opportunity_id"] in versions:
            raise ValueError("Duplicate formal result opportunity")
        versions[row["opportunity_id"]] = row["resolution_version"]
    canonical_rows = registry.opportunity_rows(first.opportunities.values(), versions)
    return _score_replayed(canonical_rows, engines, comparison=comparison)
