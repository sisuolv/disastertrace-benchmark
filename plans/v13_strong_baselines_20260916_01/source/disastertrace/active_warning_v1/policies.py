"""Public-input policies and a common, outcome-blind forecasting interface."""

import hashlib
import json
from datetime import timedelta
from fractions import Fraction

from disastertrace.active_forecast.provenance import decode_json

from .environment import Environment
from .schema import Episode

FORECAST_SYSTEM = """You forecast one fixed future weather quantity from the supplied evidence.
Use only the shown evidence, and respect entity, units, target time, versions, and source dependence.
Repeated or mirrored reports are not independent observations. Current observations need not equal a future outcome.
Return exactly one JSON object and no other text:
{"target_id":"the supplied id","value":0,"probability":null,"citations":["initial"]}
value is a nonnegative predicted quantity in the target unit. If threshold is given, probability is your
finite probability from 0 to 1 that the future value is >= threshold; otherwise probability must be null.
citations must be a nonempty list of receipt IDs actually shown in read_evidence. Never invent a source.
"""

ACQUIRE_SYSTEM = """Choose information queries for the fixed future target, under the remaining budget.
You have two scheduled forecast checkpoints. Keep resources for later updates when useful.
All pending queries run in parallel with the stated service latency. Do not query results or future observations.
Mirrors share the same upstream forecast; archives may be obsolete. No more than two queries now.
Return exactly one JSON object, no other text: {"queries":["forecast"]}
Use available tool IDs. An empty list means no query this round.
"""


def scenario_episode(episode, scenario):
    data = episode.model_dump()
    data["scenario"] = scenario
    if scenario == "delayed":
        artifacts = []
        for item in episode.artifacts:
            value = item.model_dump()
            if item.kind == "forecast" and item.id != episode.initial_artifact_id:
                value["release_at"] = max(item.release_at, episode.deadline + timedelta(seconds=1))
            artifacts.append(value)
        data["artifacts"] = artifacts
    return Episode.model_validate(data)


def latest(view, kind):
    options = [
        (item, block["receipt_id"])
        for block in view["read_evidence"]
        for item in block["facts"]
        if item["kind"] == kind
    ]
    return (
        max(
            options,
            key=lambda pair: (pair[0]["issued_at"] or pair[0]["valid_at"], pair[0]["valid_at"]),
        )
        if options
        else None
    )


def fixed_forecast(view, fusion="official"):
    forecast, citation = latest(view, "forecast")
    value = sum(Fraction(str(v)) for v in forecast["values"]) / len(forecast["values"])
    citations = [citation]
    observation = latest(view, "observation")
    if observation and fusion in ("persistence", "blend"):
        obs, obs_citation = observation
        current = sum(Fraction(str(v)) for v in obs["values"]) / len(obs["values"])
        value = current if fusion == "persistence" else (value + current) / 2
        citations = (
            [obs_citation]
            if fusion == "persistence"
            else list(dict.fromkeys(citations + [obs_citation]))
        )
    threshold = view["target"]["threshold"]
    return {
        "target_id": view["target"]["id"],
        "value": str(value),
        "probability": None if threshold is None else int(value >= Fraction(str(threshold))),
        "citations": citations,
    }


def choose_fixed(policy, round_index, remaining):
    if policy in ("initial", "initial_persistence") or not remaining:
        return []
    if policy in ("latest", "fixed_forecast"):
        return ["forecast"]
    if policy in ("observe", "fixed_observation"):
        return ["observation"]
    if policy == "archive":
        return ["archive"]
    if policy == "mirror":
        return ["mirror"]
    if policy == "forecast_then_observe":
        return ["forecast" if round_index == 0 else "observation"]
    if policy == "observe_then_forecast":
        return ["observation" if round_index == 0 else "forecast"]
    if policy == "all_read":
        return ["forecast", "observation"][:remaining]
    raise ValueError("unknown fixed acquisition policy")


def run_episode(episode, budget, policy, fusion="official", backend=None):
    env = Environment(episode, budget)
    calls = []
    canonical = policy == "active_canonical"

    def ask(system, stage, round_index):
        view = env.view(canonical=canonical)
        view["scheduled_checkpoints"] = [time.isoformat() for time in episode.checkpoints]
        response, details = backend(system, json.dumps(view, allow_nan=False), stage, round_index)
        calls.append({"stage": stage, "round": round_index, **details})
        return decode_json(response)

    for round_index, checkpoint in enumerate(episode.checkpoints):
        env.wait_until(max(env.now, checkpoint - timedelta(seconds=120)))
        if policy.startswith("active_"):
            try:
                answer = ask(ACQUIRE_SYSTEM, "acquire", round_index)
                if not isinstance(answer, dict) or set(answer) != {"queries"}:
                    raise ValueError("invalid acquisition contract")
                queries = answer["queries"]
                if (
                    not isinstance(queries, list)
                    or len(queries) > 2
                    or any(type(q) is not str for q in queries)
                ):
                    raise ValueError("invalid query list")
            except (ValueError, TypeError) as error:
                env.invalid("acquisition: " + str(error))
                queries = []
        else:
            queries = choose_fixed(policy, round_index, env.budget - env.spent)
        for query in queries:
            try:
                env.query(query)
            except ValueError as error:
                env.invalid("query: " + str(error))
        env.wait_until(checkpoint)
        for receipt in list(env.receipts):
            if receipt["status"] == "completed":
                env.read(receipt["id"])
        try:
            answer = (
                ask(FORECAST_SYSTEM, "forecast", round_index)
                if backend
                else fixed_forecast(env.view(), fusion)
            )
            env.forecast(answer)
        except (ValueError, TypeError) as error:
            env.invalid("forecast: " + str(error))
    env.stop()
    return {
        **env.export(),
        "policy": policy,
        "fusion": "llm" if backend else fusion,
        "backend": "model" if backend else "program",
        "calls": calls,
    }


def audit_trace(episode, trace):
    previous = None
    for index, event in enumerate(trace["events"]):
        body = {k: v for k, v in event.items() if k != "sha256"}
        if event["index"] != index or event["previous_sha256"] != previous:
            raise ValueError("event chain reordered")
        digest = hashlib.sha256(
            json.dumps(body, sort_keys=True, allow_nan=False).encode()
        ).hexdigest()
        if digest != event["sha256"]:
            raise ValueError("event content hash changed")
        previous = digest
    env = Environment(episode, trace["budget"])
    for event in trace["events"][1:]:
        kind = event["kind"]
        if kind == "wait":
            env.wait_until(event["at"])
        elif kind == "query":
            env.query(event["tool_id"])
        elif kind == "read":
            env.read(event["receipt_id"])
        elif kind == "forecast":
            env.forecast(
                {
                    "target_id": event["target_id"],
                    "value": str(event["value"]),
                    "probability": None
                    if event["probability"] is None
                    else str(event["probability"]),
                    "citations": event["citations"],
                }
            )
        elif kind == "stop_acquisition":
            env.stop()
        elif kind == "invalid":
            env.invalid(event["reason"], event.get("raw_sha256"))
        elif kind != "completed":
            raise ValueError("unknown event")
    replay = env.export()
    for key in ("spent", "receipts", "commits", "events"):
        if replay[key] != trace[key]:
            raise ValueError("reconstructed trace mismatch: " + key)
    return True
