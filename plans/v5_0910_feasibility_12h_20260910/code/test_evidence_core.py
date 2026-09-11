"""Synthetic semantic counterexamples; no synthetic record enters real-data counts."""

import copy
import itertools
import unittest

from evidence_core import certificates, powerset, reference, score, sufficient, validate_episode


def make_count(values):
    supports = [str(i) for i in range(len(values))]
    episode = {"cutoff": 0, "target": {"entity": "s", "variable": "v", "unit": "u",
               "supports": supports, "operator": "count_threshold", "value_threshold": 1,
               "count_threshold": 2}, "cards": []}
    for index, value in enumerate(values):
        episode["cards"].append({"id": str(index), "available_at": 0, "issued_at": "2024-01-01",
            "cost": 1, "records": [{"entity": "s", "variable": "v", "unit": "u",
            "support": str(index), "value": value, "quality": "valid" if value is not None else "missing"}]})
    return episode


def decision(values):
    if sum(x == 1 for x in values) >= 2:
        return "yes"
    if sum(x != 0 for x in values) < 2:
        return "no"
    return "unknown"


class EvidenceSupportTests(unittest.TestCase):
    def test_every_count_certificate_against_possible_worlds(self):
        checked = 0
        for values in itertools.product([0, 1, None], repeat=3):
            episode = make_count(values)
            validate_episode(episode)
            for subset in powerset(["0", "1", "2"]):
                unread = [i for i in range(3) if str(i) not in subset]
                worlds = set()
                for completion in itertools.product([0, 1, None], repeat=len(unread)):
                    world = list(values)
                    for index, value in zip(unread, completion):
                        world[index] = value
                    worlds.add(decision(world))
                expected = worlds == {decision(values)}
                self.assertEqual(sufficient(episode, subset), expected, (values, subset, worlds))
                checked += 1
        self.assertEqual(checked, 216)

    def test_unknown_has_a_nontrivial_early_certificate(self):
        episode = make_count([None, None, 1])
        self.assertEqual(certificates(episode)["minimal_sets"], [{"ids": ["0", "1"], "cost": 2}])
        self.assertFalse(sufficient(episode, []))

    def test_always_unknown_does_not_solve_an_answerable_target(self):
        result = score(make_count([1, 1, 0]), [], {"decision": "unknown", "citations": []}, 3)
        self.assertTrue(result["visible_decision_correct"])
        self.assertFalse(result["goal_correct"])
        self.assertFalse(result["grounded_success"])
        self.assertTrue(result["avoidable_unresolved"])
        self.assertEqual(result["minimum_extra_cost"], 2)

    def test_citation_must_have_been_read_and_must_prove_the_claim(self):
        episode = make_count([1, 1, 0])
        result = score(episode, ["0"], {"decision": "yes", "citations": ["0", "1"]}, 3)
        self.assertTrue(result["goal_correct"])
        self.assertFalse(result["cited_only_read"])
        self.assertFalse(result["grounded_success"])
        self.assertFalse(score(episode, ["0", "1"], {"decision": "yes", "citations": ["0"]}, 3)["grounded_success"])
        self.assertTrue(score(episode, ["0", "1"], {"decision": "yes", "citations": ["0", "1"]}, 3)["grounded_success"])

    def test_unavailable_future_and_wrong_units_are_not_evidence(self):
        episode = make_count([1, 1, 1])
        episode["cards"][1]["available_at"] = 1
        episode["cards"][2]["records"][0]["unit"] = "different"
        self.assertEqual(reference(episode, ["0", "1", "2"])["decision"], "unknown")
        with self.assertRaises(ValueError):
            score(episode, ["0", "1"], {"decision": "yes", "citations": []}, 3)

    def test_duplicate_support_cannot_double_count(self):
        episode = make_count([1, 1, 0])
        episode["cards"][1]["records"][0]["support"] = "0"
        with self.assertRaisesRegex(ValueError, "overlapping"):
            validate_episode(episode)

    def test_exact_budget_and_invalid_output(self):
        episode = make_count([1, 1, 0])
        with self.assertRaisesRegex(ValueError, "budget"):
            score(episode, ["0", "1"], {"decision": "yes", "citations": []}, 1)
        result = score(episode, [], None, 1)
        self.assertFalse(result["valid"])
        self.assertFalse(result["goal_correct"])
        self.assertFalse(result["budget_resolvable"])

    def test_revision_requires_both_versions_even_if_value_unchanged(self):
        episode = make_count([60, 60])
        episode["target"].update(operator="revision_delta", supports=["2024-01-03"],
                                 versions=["old", "new"], threshold=0)
        for card, version in zip(episode["cards"], ["old", "new"]):
            card["records"][0].update(support="2024-01-03", version=version)
        self.assertEqual(reference(episode, ["1"])["decision"], "unknown")
        self.assertEqual(reference(episode, ["0", "1"])["decision"], "yes")
        self.assertEqual(certificates(episode)["minimum_cost"], 2)

    def test_spatial_nodata_is_neither_nonwater_nor_free_information(self):
        episode = make_count([1, 1, 0])
        episode["target"].update(operator="area_threshold", total_pixels=6,
                                 support_sizes={"0": 2, "1": 2, "2": 2}, fraction_threshold=0.5)
        for card, counts in zip(episode["cards"], [(2, 0), (0, 0), (0, 2)]):
            card["records"][0].update(value={"positive": counts[0], "negative": counts[1]})
        validate_episode(episode)
        result = reference(episode, ["0", "1", "2"])
        self.assertEqual(result["decision"], "unknown")
        self.assertAlmostEqual(result["lower"], 1 / 3)
        self.assertAlmostEqual(result["upper"], 2 / 3)
        self.assertFalse(sufficient(episode, []))

    def test_spatial_certificates_against_extreme_completions(self):
        states = [(2, 0), (0, 2), (0, 0), (1, 0), (0, 1), (1, 1)]
        def classify(values):
            lower = sum(x[0] for x in values)
            upper = 6 - sum(x[1] for x in values)
            return "yes" if lower >= 3 else "no" if upper < 3 else "unknown"
        for values in itertools.product(states, repeat=3):
            episode = make_count([1, 1, 0])
            episode["target"].update(operator="area_threshold", total_pixels=6,
                                     support_sizes={"0": 2, "1": 2, "2": 2}, fraction_threshold=0.5)
            for card, (water, nonwater) in zip(episode["cards"], values):
                card["records"][0].update(value={"positive": water, "negative": nonwater})
            for subset in powerset(["0", "1", "2"]):
                unread = [i for i in range(3) if str(i) not in subset]
                worlds = set()
                for completion in itertools.product(states[:3], repeat=len(unread)):
                    world = list(values)
                    for index, value in zip(unread, completion):
                        world[index] = value
                    worlds.add(classify(world))
                self.assertEqual(sufficient(episode, subset), worlds == {classify(values)})


if __name__ == "__main__":
    unittest.main(verbosity=2)
