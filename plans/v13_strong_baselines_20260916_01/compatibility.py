"""Qualify legacy reuse without pretending the new package has identical bytes."""

import ast
import json
import os
import subprocess
from pathlib import Path

from disastertrace.monitoring_v1.spool_backend import digest, publish, read
from disastertrace.monitoring_v1.targets import canonical_hash

RUN = Path(__file__).resolve().parent
REPO = RUN.parents[1]
OLD = REPO / "plans/v13_followup_20260916_01/source/disastertrace"


class SpecializeLegacy(ast.NodeTransformer):
    """Remove only the explicit new-selector guard/branch, retaining legacy AST."""

    def visit_ImportFrom(self, node):
        return None if node.module == "public_query_selectors" else node

    def visit_If(self, node):
        expression = ast.dump(node.test)
        if "id='public_selector_kinds'" in expression and isinstance(node.test, (ast.Compare, ast.BoolOp)):
            # A negative membership test also mentions the set but is retained.
            if isinstance(node.test, ast.BoolOp) or ast.unparse(node.test) == "selector in public_selector_kinds":
                return None
        return self.generic_visit(node)

    def visit_BinOp(self, node):
        if isinstance(node.op, ast.BitOr) and isinstance(node.right, ast.Name) and node.right.id == "public_selector_kinds":
            return node.left
        return self.generic_visit(node)


def audit_source(old, new):
    before = {str(p.relative_to(old)): digest(p) for p in old.rglob("*.py")}
    after = {str(p.relative_to(new)): digest(p) for p in new.rglob("*.py")}
    added, removed = sorted(after.keys()-before.keys()), sorted(before.keys()-after.keys())
    changed = sorted(k for k in before.keys() & after.keys() if before[k] != after[k])
    permitted = "monitoring_v1/policies.py"
    if added != ["monitoring_v1/public_query_selectors.py"] or removed or changed != [permitted]:
        raise ValueError("Unexpected source difference outside public selector extension")
    old_ast = ast.parse((old / permitted).read_text())
    new_ast = SpecializeLegacy().visit(ast.parse((new / permitted).read_text()))
    equal = ast.dump(old_ast) == ast.dump(new_ast)
    if not equal:
        raise ValueError("Legacy specialization is not structurally equal")
    consumers = ["monitoring_v1/native_feature_forecast.py", "monitoring_fixed_v1/native_feature.py",
                 "monitoring_v1/calibration.py", "monitoring_fixed_v1/support_bridge.py"]
    return {"passed": True, "added": added, "changed": changed, "removed": removed,
            "old_source_sha256": canonical_hash(before), "new_source_sha256": canonical_hash(after),
            "legacy_ast_exact_after_specialization": equal,
            "unchanged_prediction_modules": {k: before[k] for k in consumers},
            "prediction_consumer_sha256": canonical_hash({k: before[k] for k in consumers}),
            "qualification": "versioned query ordering only; legacy paths structurally equal; whole package hashes differ"}


def replay_fixture(destination):
    from test_monitoring_forecast_schedule import scheduled
    from disastertrace.monitoring_v1.policies import run_session

    result = {}
    for kind in ("round_robin", "risk", "coverage", "batch_complete"):
        for authorization in ("target_private", "session_shared"):
            for allocation in ("fixed_quota", "global_budget"):
                if kind == "batch_complete" and (authorization, allocation) != ("session_shared", "global_budget"):
                    continue
                data, bank, cfg = scheduled(selector_kind=kind, authorization_mode=authorization,
                                            allocation_mode=allocation)
                report = run_session(data, bank, cfg)
                result["|".join((kind, authorization, allocation))] = canonical_hash(report)
    publish(Path(destination), result)


def execute():
    reg = read(RUN / "REGISTRATION.json")
    result = audit_source(OLD, RUN / "source/disastertrace")
    paths = []
    for name, source in (("old", OLD.parent), ("new", RUN / "source")):
        output = RUN / ("LEGACY_REPLAY_" + name + ".json")
        env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1",
               "PYTHONPATH": str(source) + ":" + str(REPO / "disastertrace-starter/tests")}
        args = [reg["python"], str(Path(__file__)), "fixture", str(output)]
        with (RUN / ("LEGACY_REPLAY_" + name + ".log")).open("x") as log:
            code = subprocess.run(args, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=600).returncode
        if code:
            raise ValueError("Legacy fixture replay failed: " + name)
        paths.append(output)
    if read(paths[0]) != read(paths[1]):
        raise ValueError("Legacy reports differ under new source")
    result.update(replayed_configurations=len(read(paths[0])), replay_exact=True,
                  fixture_role="engineering replay only, not new independent method-days",
                  replay_files={str(p): digest(p) for p in paths})
    publish(RUN / "COMPATIBILITY.json", result)
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    import sys
    replay_fixture(sys.argv[2]) if sys.argv[1] == "fixture" else execute()
