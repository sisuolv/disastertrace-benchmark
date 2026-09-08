"""Offline program trajectories; no provider call or credential access exists here."""

from copy import deepcopy

from disastertrace.automated.common import canonical, fingerprint

from . import public_oracle
from .renderer import render_request
from .schema import parse_decision, validate_episode


def rehearse(episodes: list[dict], method: str, backend: str = "correct") -> list[dict]:
    rows = []
    for ep in episodes:
        validate_episode(ep)
        previous, history = None, []
        for cp in ep["checkpoints"]:
            request = render_request(
                ep, cp["checkpoint_id"], method=method, previous=previous, history=history
            )
            raw = (
                ""
                if backend == "invalid-control" and cp["checkpoint_id"] == "c2"
                else canonical(
                    public_oracle.answer(
                        request, "correct" if backend == "invalid-control" else backend
                    )
                )
            )
            status, error = "ok", None
            try:
                decision = parse_decision(raw)
            except (ValueError, TypeError, KeyError):
                status, error = "invalid", "answer_schema_invalid"
            else:
                previous = decision
                history.append(deepcopy(decision))
            rows.append(
                {
                    "episode_id": ep["episode_id"],
                    "checkpoint_id": cp["checkpoint_id"],
                    "method": method,
                    "backend": backend,
                    "model_kind": "diagnostic_program",
                    "eligible_for_llm_leaderboard": False,
                    "provider_requests": 0,
                    "request": request,
                    "request_hash": fingerprint(request),
                    "raw_response": raw,
                    "status": status,
                    "error": error,
                    "state_after": deepcopy(previous),
                }
            )
    return rows
