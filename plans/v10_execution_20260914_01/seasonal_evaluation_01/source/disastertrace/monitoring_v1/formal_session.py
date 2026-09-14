"""Mandatory qualification for new formal H15 sessions; legacy replay stays explicit."""

import hashlib
import json
from pathlib import Path

from ..monitoring_fixed_v1.admission import AdmissionEngine, score_admitted
from ..monitoring_fixed_v1.outcome_policies import PROVIDER_BINDINGS
from ..monitoring_fixed_v1.outcomes import OutcomeRegistry, experiment_spec
from .execution import bind_execution
from .session_checkpoint import SessionCoordinator
from .source_execution import bind_source
from .spool_backend import publish
from .targets import canonical_hash


def required_source_files():
    package = Path(__file__).resolve().parents[1]
    return sorted([*(package / "monitoring_v1").rglob("*.py"),
                   *(package / "monitoring_fixed_v1").rglob("*.py"),
                   package / "forecast_task/common.py"])


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
    def __init__(self, data, bank, config, *, comparison, bound_files, directory,
                 backend=None, source_backend=None):
        _no_outcomes(data)
        required = {"execution_mode": "production_bound_v1", "pending_timing_policy": "lifecycle_wall_v1",
                    "admission_semantics": "measurement.v3", "session_runtime": "typed_admission_v1",
                    "formal_resolution_policy": "h15_routine_archive.v1"}
        if any(config.get(k) != v for k, v in required.items()):
            raise ValueError("Formal session requires production identity, clock, provider policy and v3 admission")
        self.bound_files = json.loads(json.dumps(bound_files))
        if not {str(p) for p in required_source_files()} <= set(self.bound_files):
            raise ValueError("Formal source manifest is incomplete")
        self._verify_files()
        bound_config = bind_source(bind_execution(config, backend), source_backend)
        spec = experiment_spec(data, bank, bound_config)
        comparison.validate(spec["invariants"], spec["interventions"])
        self.comparison = comparison
        self.coordinator = SessionCoordinator(data, bank, bound_config, backend=backend, source_backend=source_backend)
        self.directory = Path(directory)
        self.directory.mkdir(exist_ok=False)
        self.contract = {"schema": "disastertrace.formal_session.v1", "files": self.bound_files,
                         "comparison": comparison.export(), "initial_experiment": spec,
                         "provider_policy": required["formal_resolution_policy"],
                         "outcomes_visible_to_policy": False,
                         "assurance": "managed frozen execution; not arbitrary Python sandboxing"}
        publish(self.directory / "CONTRACT.json", self.contract)

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
        spec = experiment_spec(self.coordinator.data, self.coordinator.bank, config)
        self.comparison.validate(spec["invariants"], spec["interventions"])
        return self.coordinator.step(controls)

    def snapshot(self):
        return self.coordinator.snapshot()

    def persist(self, path):
        self._verify_files()
        return self.coordinator.persist(path)

    def stop(self, reason):
        publish(self.directory / "STOP.json", {"reason": reason, "done": self.done,
            "contract_sha256": canonical_hash(self.contract),
            "report_sha256": canonical_hash(self.report) if self.report is not None else None})

    def finish(self, *, max_steps):
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
            self.stop("failed_or_step_ceiling")
            raise
        self.stop("completed")
        return self.report


def score_formal(outcomes, arms, *, comparison):
    """Evaluator-only entry: provider-bound records and formal journals are required."""
    if not arms:
        raise ValueError("Registered formal arms required")
    first = AdmissionEngine.from_journal(next(iter(arms.values())))
    for path in arms.values():
        engine = AdmissionEngine.from_journal(path)
        other = engine.contract.get("experiment", {}).get("invariants", {}).get("other_frozen_config", {})
        if (engine.semantics_version != "measurement.v3"
                or other.get("formal_resolution_policy") not in PROVIDER_BINDINGS
                or other.get("execution_mode") != "production_bound_v1"
                or other.get("pending_timing_policy") != "lifecycle_wall_v1"):
            raise ValueError("Formal score cannot admit a legacy or unbound journal")
    registry = OutcomeRegistry(first.targets.values(), mode="formal_provider_bound")
    versions = {}
    for row in outcomes:
        registry.register({k: v for k, v in row.items() if k != "opportunity_id"})
        if row["opportunity_id"] in versions:
            raise ValueError("Duplicate formal result opportunity")
        versions[row["opportunity_id"]] = row["resolution_version"]
    canonical_rows = registry.opportunity_rows(first.opportunities.values(), versions)
    return score_admitted(canonical_rows, arms, comparison=comparison)
