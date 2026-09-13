"""Executable protocol examples for the proposed DisasterTrace v7.

These tests are independent review fixtures. They do NOT import repository code,
read private scientific arrays, run a model, or validate monitoring_v1.
Python 3.10+; standard library only. Run: python protocol_counterexamples.py
"""
from __future__ import annotations

import hashlib
import itertools
import json
import unittest
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Acquisition:
    key: str
    cost: int
    targets: frozenset[str]


def feasible_plans(actions: tuple[Acquisition, ...], budget: int):
    """Tiny static fixture only: one deadline, no processing or queue delays."""
    if budget < 0 or len({a.key for a in actions}) != len(actions):
        raise ValueError("Invalid budget or duplicate acquisition identity")
    for count in range(len(actions) + 1):
        for plan in itertools.combinations(actions, count):
            if any(a.cost < 0 for a in plan):
                raise ValueError("Negative cost")
            if sum(a.cost for a in plan) <= budget:
                yield plan, frozenset().union(*(a.targets for a in plan))


def classify_explicit_support(possible_values: frozenset[int], threshold: int) -> str:
    """Only for an explicitly given finite support, not physical image truth."""
    if not possible_values:
        return "inconsistent"
    if all(value >= threshold for value in possible_values):
        return "supported"
    if all(value < threshold for value in possible_values):
        return "refuted"
    return "undetermined"


def content_hash(value: object) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


class ProtocolCounterexamples(unittest.TestCase):
    def test_individually_reachable_is_not_jointly_reachable(self):
        actions = (
            Acquisition("A_only", 1, frozenset({"A"})),
            Acquisition("B_only", 1, frozenset({"B"})),
        )
        possibilities = [targets for _, targets in feasible_plans(actions, 1)]
        self.assertTrue(all(any(t in targets for targets in possibilities) for t in ("A", "B")))
        self.assertFalse(any({"A", "B"} <= targets for targets in possibilities))
        self.assertEqual(max(map(len, possibilities)), 1)

    def test_shared_acquisition_cost_is_not_sum_of_individual_optima(self):
        actions = (Acquisition("shared_image", 1, frozenset({"A", "B"})),)
        all_plans = list(feasible_plans(actions, 1))
        individual = [min(sum(a.cost for a in p) for p, ts in all_plans if t in ts) for t in ("A", "B")]
        joint = min(sum(a.cost for a in p) for p, ts in all_plans if {"A", "B"} <= ts)
        self.assertEqual(sum(individual), 2)
        self.assertEqual(joint, 1)

    def test_empty_support_does_not_vacuously_prove_both_answers(self):
        empty: frozenset[int] = frozenset()
        self.assertTrue(all(x >= 20 for x in empty))
        self.assertTrue(all(x < 20 for x in empty))
        self.assertEqual(classify_explicit_support(empty, 20), "inconsistent")
        self.assertEqual(classify_explicit_support(frozenset({12, 42}), 20), "undetermined")

    def test_hidden_labels_cannot_change_public_evidence_support(self):
        # A public card discloses only coverage, not a class label.
        public = {"covered_cells": ["c0"], "observed_labels": {}}
        hidden_a = {"c0": 0}
        hidden_b = {"c0": 1}
        def public_support(card):
            labels = card["observed_labels"]
            return frozenset({labels["c0"]}) if "c0" in labels else frozenset({0, 1})
        self.assertNotEqual(hidden_a, hidden_b)
        self.assertEqual(public_support(public), frozenset({0, 1}))
        self.assertEqual(classify_explicit_support(public_support(public), 1), "undetermined")

    def test_same_ensemble_mean_does_not_mean_same_baseline_information(self):
        left = [0, 0, 100, 100]
        right = [49, 49, 51, 51]
        self.assertEqual(sum(left) / len(left), sum(right) / len(right))
        self.assertNotEqual(sum(x >= 80 for x in left) / 4, sum(x >= 80 for x in right) / 4)
        self.assertNotEqual(content_hash({"members": left}), content_hash({"members": right}))

    def test_overlap_uses_union_not_sum(self):
        # Eight equally weighted cells, overlapping products, one valid time.
        first = frozenset(range(5))
        second = frozenset(range(3, 8))
        self.assertEqual(len(first) + len(second), 10)
        self.assertEqual(len(first | second), 8)
        self.assertEqual(len(first | first), 5)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ProtocolCounterexamples)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    summary = {
        "kind": "independent_protocol_examples_not_repository_tests",
        "reference_commit": "63c77694797c2436ef79465d9c076fb940404f06",
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "passed": result.wasSuccessful(),
        "limits": [
            "No repository tests were rerun.",
            "No scientific arrays or live sources were read.",
            "No model calls were made.",
            "These are counterexamples to naive interpretations, not evidence of implemented bugs.",
            "The toy reachability search does not model release times, concurrency, inference cost or deadlines."
        ],
    }
    Path(__file__).with_name("PROTOCOL_EXAMPLES_RESULT.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    raise SystemExit(0 if result.wasSuccessful() else 1)
