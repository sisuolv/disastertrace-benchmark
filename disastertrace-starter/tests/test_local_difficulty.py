"""Predeclared stress factors preserve Gold and admit all existing task branches."""

from copy import deepcopy

import pytest

from disastertrace.controlled import compiler, generator, public_oracle, renderer
from disastertrace.local_eval.difficulty import FACTORS, LEVELS, transform


@pytest.mark.parametrize("factor", FACTORS)
@pytest.mark.parametrize("level", LEVELS)
def test_stress_factors_preserve_checkpoint_answers_for_every_branch(factor, level):
    for original in generator.micro_episodes():
        saved = deepcopy(original)
        changed = transform(original, factor, level)
        assert original == saved
        assert changed["episode_id"] != original["episode_id"]
        for cp in original["checkpoints"]:
            expected = compiler.reference_at(original, cp["checkpoint_id"])
            assert compiler.reference_at(changed, cp["checkpoint_id"]) == expected
            public = renderer.render_request(changed, cp["checkpoint_id"], method="snapshot")
            assert public_oracle.answer(public) == expected


def test_undeclared_difficulty_is_rejected():
    original = generator.micro_episodes()[0]
    with pytest.raises(ValueError):
        transform(original, "adaptive_to_model_errors", 4)
    with pytest.raises(ValueError):
        transform(original, FACTORS[0], 1000)
