import json

import pytest

from disastertrace.active_forecast.__main__ import main
from disastertrace.active_forecast.schema import Episode

from .test_core import count_data


def test_cli_public_and_score_are_distinct(tmp_path, capsys):
    episode_path = tmp_path / "episode.json"
    episode_path.write_text(Episode.model_validate(count_data()).model_dump_json())
    answer_path = tmp_path / "answer.json"
    answer_path.write_text('{"decision":"yes","citations":["0","1"]}')
    assert main(["public", str(episode_path), "--read", "0", "--budget", "2"]) == 0
    public = json.loads(capsys.readouterr().out)
    assert "goal_decision" not in public and "minimum_cost" not in public
    assert public["remaining_budget"] == 1
    assert (
        main(
            [
                "score",
                str(episode_path),
                "--read",
                "0",
                "--read",
                "1",
                "--budget",
                "2",
                "--answer",
                str(answer_path),
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["grounded_success"] is True


def test_cli_rejects_exhausted_budget(tmp_path):
    path = tmp_path / "episode.json"
    path.write_text(Episode.model_validate(count_data()).model_dump_json())
    with pytest.raises(ValueError, match="budget"):
        main(["public", str(path), "--read", "0", "--budget", "0"])
