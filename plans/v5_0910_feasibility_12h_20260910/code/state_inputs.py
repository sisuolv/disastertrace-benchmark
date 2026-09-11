"""Public state-carrier intervention; never imports private expected states."""

SYSTEM = (
    "Track the latest published NHC forecast for the one fixed storm and future valid time. "
    "Use the greatest issue_time among compatible forecasts actually delivered so far. "
    "A current-intensity estimate is not a forecast for the fixed future target. "
    "Older redeliveries, exact duplicates and other storms must not replace a compatible newer forecast. "
    "This is a controlled replay of archived products, not a real-time weather forecast. "
    "Return only the state JSON object itself, without a wrapper, prose or additional keys."
)


def state_request(trace, step, carrier, previous):
    if carrier not in {"full_history", "last_state"}:
        raise ValueError("unsupported carrier")
    public = {"fixed_target": trace["target"], "delivery_step": step,
        "question": "What is the latest delivered compatible forecast maximum wind for this exact target?",
        "evidence": trace["deliveries"][:step + 1] if carrier == "full_history" else [trace["deliveries"][step]],
        "reply_format": 'Reply exactly {"wind_kt":NUMBER,"source_id":"ID","issue_time":"TIME"}. '
            'Use an integer wind value, the original source card ID and its exact issue_time. '
            'Use null for all three fields only if no compatible delivered forecast can be identified.'}
    if carrier == "last_state":
        public["previous_state"] = previous
        public["memory_note"] = "This is your own previous state. Retain it unless new compatible evidence supersedes it."
    return {"system": SYSTEM, "public": public, "assets": []}


def parse_state(raw):
    import json

    try:
        def unique(items):
            result = {}
            for k, v in items:
                if k in result:
                    raise ValueError("duplicate key")
                result[k] = v
            return result
        result = json.loads(raw, object_pairs_hook=unique)
    except (ValueError, TypeError):
        return None
    if not isinstance(result, dict) or set(result) != {"wind_kt", "source_id", "issue_time"}:
        return None
    if all(v is None for v in result.values()):
        return result
    if type(result["wind_kt"]) is int and isinstance(result["source_id"], str) and isinstance(result["issue_time"], str):
        return result
    return None
