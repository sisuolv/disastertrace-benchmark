#!/usr/bin/env python3
"""Logical counterexamples for a v7 design review; NOT monitoring_v1 tests.

Only synthetic inputs and the Python standard library are used. No repository
code, source observations, model, network endpoint, or private outcome is read.
Run: python counterexamples.py --output counterexamples_results.json
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
from fractions import Fraction as F
from pathlib import Path
import unittest

OBSERVATIONS: dict[str, dict] = {}


def brier(p: F, y: int) -> F:
    return (p - y) ** 2


def expected_brier(p: F, event_probability: F) -> F:
    return event_probability * brier(p, 1) + (1 - event_probability) * brier(p, 0)


def fact_status(worlds: set[int]) -> str:
    if not worlds:
        return 'inconsistent_evidence'
    if worlds == {1}:
        return 'supported'
    if worlds == {0}:
        return 'refuted'
    return 'undetermined'


class DesignCounterexamples(unittest.TestCase):
    def test_01_different_valid_windows_are_not_one_target(self) -> None:
        # Illustrative timestamps using the documented Day-1 support pattern.
        early = ('point_A', 'reported_tornado', '2026-09-12T12:00Z', '2026-09-13T12:00Z')
        late = ('point_A', 'reported_tornado', '2026-09-12T20:00Z', '2026-09-13T12:00Z')
        self.assertNotEqual(early, late)
        # Same-end-time lookup wrongly merges the targets.
        self.assertEqual((early[0], early[3]), (late[0], late[3]))
        OBSERVATIONS['01'] = {'result': 'Same provider and end time do not establish target equivalence.',
                              'early_target': early, 'late_target': late}

    def test_02_private_predictor_files_do_not_block_selector_signals(self) -> None:
        # A global selector knows A's private value and sends a value-dependent
        # action to B, despite B's input containing no raw private record.
        def selector(private_bit: int) -> str:
            return 'review_now' if private_bit else 'wait'
        def receiver(action: str) -> int:
            return int(action == 'review_now')
        inferred = [receiver(selector(s)) for s in (0, 1)]
        self.assertEqual(inferred, [0, 1])
        OBSERVATIONS['02'] = {'result': 'Action choice itself can transmit private information.',
                              'bits_recovered': inferred, 'claim': 'Logical channel, not a demonstrated repository exploit.'}

    def test_03_automatic_reset_can_create_a_large_difference(self) -> None:
        submitted = F(9, 10)
        new_base = F(1, 10)
        y = 0
        bound_loss = brier(new_base, y)  # Same candidate is invalidated by wrapper.
        persistent_loss = brier(submitted, y)
        difference = persistent_loss - bound_loss
        self.assertEqual(difference, F(4, 5))
        OBSERVATIONS['03'] = {'bound_loss': str(bound_loss), 'persistent_loss': str(persistent_loss),
                              'difference_without_any_new_model_reasoning': str(difference)}

    def test_04_realized_gain_does_not_certify_expected_improvement(self) -> None:
        eta, base, proposal = F(1, 5), F(1, 5), F(2, 5)
        realized_gain = brier(base, 1) - brier(proposal, 1)
        expected_gain = expected_brier(base, eta) - expected_brier(proposal, eta)
        self.assertEqual(realized_gain, F(7, 25))
        self.assertEqual(expected_gain, F(-1, 25))
        OBSERVATIONS['04'] = {'realized_gain_given_y_1': str(realized_gain),
                              'expected_gain_given_eta_0_2': str(expected_gain),
                              'result': 'A realized G_plus contribution can accompany worse expected risk.'}

    def test_05_common_mask_is_not_missingness_identification(self) -> None:
        coverage, conditional_gain = F(9, 10), F(1, 100)
        lower = coverage * conditional_gain - (1 - coverage)
        upper = coverage * conditional_gain + (1 - coverage)
        self.assertEqual((lower, upper), (F(-91, 1000), F(109, 1000)))
        self.assertLess(lower, 0)
        self.assertGreater(upper, 0)
        OBSERVATIONS['05'] = {'coverage': str(coverage), 'settled_only_gain': str(conditional_gain),
                              'full_cohort_conservative_gain_bounds': [str(lower), str(upper)],
                              'assumption': 'Binary Brier improvement lies in [-1,1]; equal target weights.'}

    def test_06_empty_feasible_set_is_not_both_supported_and_refuted(self) -> None:
        worlds = {0}.intersection({1})
        naive_supported = all(w == 1 for w in worlds)
        naive_refuted = all(w == 0 for w in worlds)
        self.assertTrue(naive_supported and naive_refuted)
        self.assertEqual(fact_status(worlds), 'inconsistent_evidence')
        OBSERVATIONS['06'] = {'naive_all_flags': [naive_supported, naive_refuted],
                              'explicit_nonvacuous_status': fact_status(worlds)}

    def test_07_an_opportunity_cutoff_must_not_close_the_target(self) -> None:
        # One outcome at time18, scored at two registered earlier cutoffs.
        cutoffs = (12, 15)
        sealed = {cutoffs[0]}
        last_cutoff = max(cutoffs)
        now = 13
        self.assertNotIn(cutoffs[1], sealed)
        self.assertLess(now, last_cutoff)
        OBSERVATIONS['07'] = {'first_opportunity_sealed': True, 'second_opportunity_open': True,
                              'result': 'Target lifetime and opportunity sealing are distinct.'}

    def test_08_same_source_features_need_not_preserve_information(self) -> None:
        a, b = (0, 2), (1, 1)
        self.assertEqual(sum(a) / len(a), sum(b) / len(b))
        self.assertNotEqual(int(max(a) >= 2), int(max(b) >= 2))
        OBSERVATIONS['08'] = {'arrays': [a, b], 'same_mean_feature': 1,
                              'different_threshold_answers': [1, 0],
                              'result': 'Same-origin summary is not automatically an information-equivalent representation.'}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('counterexamples_results.json'))
    args = parser.parse_args()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(DesignCounterexamples)
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    report = {
        'reviewed_commit': '63c77694797c2436ef79465d9c076fb940404f06',
        'kind': 'synthetic_design_counterexamples_only',
        'repository_code_imported': False,
        'real_data_decoded': False,
        'models_called': 0,
        'gpu_jobs': 0,
        'tests_run': result.testsRun,
        'passed': result.wasSuccessful(),
        'observations': OBSERVATIONS,
        'test_log': stream.getvalue(),
        'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(stream.getvalue())
    print(f'Written: {args.output}')
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
