from __future__ import annotations

import json
from pathlib import Path

import typer

from .importers.cyportqa import build_candidate_index
from .importers.nhc_time import parse_nhc_issued_at
from .models import Episode

app = typer.Typer(no_args_is_help=True)


@app.command("validate-episode")
def validate_episode(path: Path) -> None:
    episode = Episode.model_validate_json(path.read_text(encoding="utf-8"))
    typer.echo(
        json.dumps(
            {
                "episode_id": episode.episode_id,
                "artifacts": len(episode.artifacts),
                "checkpoints": len(episode.checkpoints),
            },
            indent=2,
        )
    )


@app.command("index-cyportqa")
def index_cyportqa(encoded_scenario: Path, output: Path) -> None:
    count = build_candidate_index(encoded_scenario, output)
    typer.echo(f"wrote {count} candidates to {output}")


@app.command("parse-nhc-time")
def parse_nhc_time(path: Path) -> None:
    value = parse_nhc_issued_at(path.read_text(encoding="utf-8-sig", errors="replace"))
    typer.echo(value.isoformat())


if __name__ == "__main__":
    app()
