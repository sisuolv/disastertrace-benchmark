"""Offline schema, validation, public projection, scoring and migration commands."""

import argparse
import json

from .core import Evaluator
from .provenance import load_json, sha256
from .public import PublicView, public_view
from .schema import Answer, Episode


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m disastertrace.active_forecast")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("schema", help="emit versioned JSON schemas")
    for name in ("validate", "public", "score"):
        command = commands.add_parser(name)
        command.add_argument("episode")
        if name != "validate":
            command.add_argument("--read", action="append", default=[])
            command.add_argument("--budget", type=int, required=True)
        if name == "score":
            command.add_argument("--answer", required=True)
    replay = commands.add_parser(
        "replay-legacy", help="audit migration into a new private directory"
    )
    replay.add_argument("--bundle", required=True)
    replay.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    if args.command == "schema":
        result = {
            "episode": Episode.model_json_schema(),
            "answer": Answer.model_json_schema(),
            "public": PublicView.model_json_schema(),
        }
    elif args.command == "replay-legacy":
        from .replay import replay_legacy

        result = replay_legacy(args.bundle, args.output)
    else:
        episode = Episode.model_validate(load_json(args.episode))
        if args.command == "public":
            result = public_view(episode, args.read, args.budget).model_dump(mode="json")
        else:
            evaluator = Evaluator(episode)
            if args.command == "validate":
                result = {
                    "status": "valid",
                    "episode_id": episode.id,
                    "episode_sha256": sha256(episode.model_dump_json().encode("utf-8")),
                    "eligible_cards": list(evaluator.legal_ids),
                }
            else:
                result = evaluator.score(args.read, load_json(args.answer), args.budget).model_dump(
                    mode="json"
                )
    print(json.dumps(result, ensure_ascii=True, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
