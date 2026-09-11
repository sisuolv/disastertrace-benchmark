"""Separate migration audit; historical scores and source bytes are never rewritten."""

import importlib.util
import math
import platform
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pydantic

from .core import Evaluator, powerset
from .legacy import FrozenPilotImporter
from .provenance import sha256, write_json
from .public import PublicView, public_view


def replay_legacy(bundle, output):
    bundle, output = Path(bundle).resolve(), Path(output).resolve()
    if output.is_relative_to(bundle):
        raise ValueError("migration output must be outside the frozen source bundle")
    output.mkdir(parents=True, exist_ok=False)
    started = datetime.now(timezone.utc).isoformat()
    loader = FrozenPilotImporter(bundle)
    prototype_path = bundle / "code/evidence_core.py"
    loader.reader.bind(prototype_path)
    spec = importlib.util.spec_from_file_location(
        "frozen_feasibility_evidence_core", prototype_path
    )
    prototype = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(prototype)
    pairs, originals = [], {}
    for relative in ("data/PILOT_EPISODES_PRIVATE.json", "data/NATURAL_EPISODES_PRIVATE.json"):
        pairs.extend(loader.import_file(relative))
        originals.update({e["id"]: e for e in loader.read_prototype_json(relative)})
    if len(pairs) != 104 or len(originals) != 104:
        raise ValueError("frozen migration cohort must contain exactly 104 development episodes")
    frozen_references = loader.read_prototype_json("data/PILOT_REFERENCES_PRIVATE.json")
    failures, failure_count, checks = [], 0, Counter()

    def equal(label, expected, actual, identity, read=()):
        nonlocal failure_count
        checks[label] += 1
        if expected != actual:
            failure_count += 1
            if len(failures) < 50:
                failures.append(
                    {
                        "check": label,
                        "episode": identity,
                        "read": list(read),
                        "expected": expected,
                        "actual": actual,
                    }
                )

    episodes, details, payload_hashes = [], [], []
    for imported, episode, snapshot in pairs:
        original = originals[imported["id"]]
        evaluator = Evaluator(episode)
        ids = evaluator.legal_ids
        budget_max = sum(c.cost for c in evaluator.cards.values())
        old_certs = prototype.certificates(original)
        equal(
            "certificates",
            old_certs,
            evaluator.certificates().model_dump(mode="json"),
            original["id"],
        )
        if original["id"] in frozen_references:
            equal(
                "frozen_certificates",
                frozen_references[original["id"]]["certificates"],
                old_certs,
                original["id"],
            )
            equal(
                "frozen_goals",
                frozen_references[original["id"]]["goal"],
                prototype.reference(original, ids),
                original["id"],
            )
        for read in powerset(ids):
            old_ref, new_ref = prototype.reference(original, read), evaluator.reference(read)
            equal("read_decisions", old_ref["decision"], new_ref.decision, original["id"], read)
            equal("read_reasons", old_ref["reason"], new_ref.reason, original["id"], read)
            for field in ("value", "lower", "upper"):
                expected, actual = old_ref.get(field), getattr(new_ref, field)
                agrees = expected is None and actual is None
                if expected is not None and actual is not None:
                    agrees = math.isclose(expected, float(actual), rel_tol=0, abs_tol=1e-12)
                equal("numeric_compatibility", True, agrees, original["id"], read)
            equal(
                "read_sufficiency",
                prototype.sufficient(original, read),
                evaluator.sufficient(read),
                original["id"],
                read,
            )
            equal(
                "extra_cost",
                prototype.extension_cost(original, read),
                evaluator.extension_cost(read),
                original["id"],
                read,
            )
            spent = sum(evaluator.cards[x].cost for x in read)
            view = public_view(episode, read, budget_max)
            equal(
                "public_roundtrip",
                True,
                PublicView.model_validate_json(view.model_dump_json()) == view,
                original["id"],
                read,
            )
            payload_hashes.append(sha256(view.model_dump_json().encode("utf-8")))
            answers = [
                {"decision": decision, "citations": list(citations)}
                for citations in powerset(read)
                for decision in ("yes", "no", "unknown")
            ]
            unread = [ident for ident in ids if ident not in read]
            if unread:
                answers.append({"decision": new_ref.decision, "citations": [unread[0]]})
            answers.extend([{"decision": new_ref.decision, "citations": ["not-in-pool"]}, None, {}])
            for budget in sorted({max(spent, 2), budget_max}):
                for answer in answers:
                    equal(
                        "score_cases",
                        prototype.score(original, read, answer, budget),
                        evaluator.score(read, answer, budget).model_dump(),
                        original["id"],
                        read,
                    )
        serialized = episode.model_dump(mode="json")
        episodes.append(serialized)
        details.append(
            {
                "legacy_id": original["id"],
                "episode_id": episode.id,
                "episode_sha256": sha256(episode.model_dump_json().encode("utf-8")),
                "source_snapshot": snapshot.model_dump(mode="json"),
                "family": episode.family,
                "group": episode.group,
                "variant": episode.variant,
                "goal": evaluator.reference(ids).model_dump(mode="json"),
                "certificates": evaluator.certificates().model_dump(mode="json"),
                "read_subsets": 2 ** len(ids),
            }
        )
    loader.reader.verify_unchanged()
    write_json(output / "EPISODES_PRIVATE.json", episodes)
    write_json(output / "EPISODE_AUDIT_PRIVATE.json", details)
    write_json(output / "SOURCE_BINDINGS.json", loader.reader.bindings)
    module_root = Path(__file__).parent
    source_files = sorted(module_root.glob("*.py"))
    report = {
        "status": "passed" if failure_count == 0 else "failed",
        "started_at": started,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "schema_version": "active_forecast.v1",
        "episodes": len(pairs),
        "families": dict(Counter(e.family for _, e, _ in pairs)),
        "groups_by_family": {
            family: len({e.group for _, e, _ in pairs if e.family == family})
            for family in sorted({e.family for _, e, _ in pairs})
        },
        "checks": dict(checks),
        "failure_count": failure_count,
        "failures_first_50": failures,
        "fact_checks_with_repeated_variants": loader.fact_checks,
        "bound_files": len(loader.reader.bindings),
        "resolved_unique_locators": len(loader.reader.resolved_locators),
        "public_payloads_sha256": sha256("\n".join(payload_hashes).encode("ascii")),
        "prototype_sha256": sha256(prototype_path.read_bytes()),
        "core_source_sha256": {p.name: sha256(p.read_bytes()) for p in source_files},
        "environment": {"python": platform.python_version(), "pydantic": pydantic.__version__},
        "numeric_comparison": "Decisions/certificates/scores exact; old displayed float bounds compared within 1e-12. New arithmetic uses Fraction.",
        "intentional_protocol_changes": [
            "Strict schema rejects floats at the Python API; JSON loader preserves decimal tokens with Decimal.",
            "Instants normalize to UTC; station dates and map dates remain calendar supports.",
            "Logical archive delivery remains separate from unproved historical public availability.",
            "Only NHC issue timestamps are established; legacy SEVIR frame and USDM map labels are not product issue times.",
            "Duplicate citations, duplicate read IDs and unrecognized fields fail closed.",
            "An unavailable read raises an error in reference as well as scoring.",
            "Area targets require a geometrically disjoint complete rectangle partition.",
        ],
        "limits": [
            "Migration compatibility, not a new model evaluation or benchmark score.",
            "USDM source bytes and frozen point facts verified; polygon operations not repeated in this milestone.",
            "Fact-check counts include repeated variants and distractors; they are not independent event counts.",
            "Source-native images, online acquisition, automatic group assignment and scaled source admission remain subsequent work.",
        ],
        "model_calls": 0,
        "gpu_jobs": 0,
        "historical_results_rewritten": False,
    }
    write_json(output / "COMPATIBILITY.json", report)
    if failure_count:
        raise ValueError(
            f"migration comparison failed: {failure_count} mismatches; report retained"
        )
    return report
