"""Finite, deterministic evidence-support diagnostics for a fixed target.

References concern the declared products, not unobserved physical truth. Exact
subset enumeration is a diagnostic lower bound; it is not an online policy.
"""

from itertools import combinations


def validate_episode(episode):
    cards, target = episode["cards"], episode["target"]
    if not 1 <= len(cards) <= 8 or len({c["id"] for c in cards}) != len(cards):
        raise ValueError("invalid finite card pool")
    if len(set(target["supports"])) != len(target["supports"]):
        raise ValueError("duplicate target support")
    if any(type(c["cost"]) is not int or c["cost"] <= 0 for c in cards):
        raise ValueError("costs must be positive integers")
    relevant = relevant_records(episode, {c["id"] for c in legal_cards(episode)})
    keys = [(r["support"], r.get("version")) if target["operator"] == "revision_delta"
            else r["support"] for r in relevant]
    if len(keys) != len(set(keys)):
        raise ValueError("overlapping product support requires an explicit fusion policy")
    if target["operator"] == "area_threshold":
        sizes = target["support_sizes"]
        if set(sizes) != set(target["supports"]) or sum(sizes.values()) != target["total_pixels"]:
            raise ValueError("spatial support is not a disjoint complete partition")
        for r in relevant:
            if r["quality"] == "valid" and (min(r["value"].values()) < 0
                    or sum(r["value"].values()) > sizes[r["support"]]):
                raise ValueError("invalid water/nonwater counts")


def powerset(ids):
    for n in range(len(ids) + 1):
        yield from combinations(ids, n)


def legal_cards(episode):
    cutoff = episode["cutoff"]
    return [c for c in episode["cards"] if c["available_at"] <= cutoff]


def relevant_records(episode, read_ids):
    target = episode["target"]
    records = []
    for card in legal_cards(episode):
        if card["id"] not in read_ids:
            continue
        for record in card["records"]:
            if (record["entity"] == target["entity"]
                    and record["variable"] == target["variable"]
                    and record["unit"] == target["unit"]
                    and record["support"] in target["supports"]):
                records.append({**record, "card_id": card["id"],
                                "issued_at": card["issued_at"]})
    return records


def reference(episode, read_ids):
    """Return a decision entailed by acquired, compatible product evidence."""
    target = episode["target"]
    records = relevant_records(episode, set(read_ids))
    if target["operator"] == "revision_delta":
        values = {}
        for record in records:
            if record["version"] in target["versions"] and record["quality"] == "valid":
                old = values.get(record["version"])
                if old is not None and old != record["value"]:
                    raise ValueError("conflicting values within one product version")
                values[record["version"]] = record["value"]
        if set(values) != set(target["versions"]):
            return {"decision": "unknown", "reason": "unread_or_absent_required_version", "value": None}
        before, after = [values[x] for x in target["versions"]]
        change = after - before
        return {"decision": "yes" if change >= target["threshold"] else "no",
                "reason": "supported", "value": change}

    by_support = {}
    for record in records:
        support = record["support"]
        prior = by_support.get(support)
        if prior is None or record["issued_at"] > prior["issued_at"]:
            by_support[support] = record
        elif prior["issued_at"] == record["issued_at"] and (
            record["quality"], record["value"]
        ) != (prior["quality"], prior["value"]):
            raise ValueError("conflicting source at equal priority")
    if target["operator"] == "count_threshold":
        yes, no = 0, 0
        for record in by_support.values():
            if record["quality"] != "valid" or record["value"] is None:
                continue
            if record["value"] >= target["value_threshold"]:
                yes += 1
            else:
                no += 1
        total, needed = len(target["supports"]), target["count_threshold"]
        upper = total - no
        decision = "yes" if yes >= needed else "no" if upper < needed else "unknown"
        return {"decision": decision, "reason": "supported" if decision != "unknown" else "insufficient_support",
                "lower": yes, "upper": upper, "value": None}
    if target["operator"] == "area_threshold":
        positive, known_negative = 0, 0
        for record in by_support.values():
            if record["quality"] == "valid":
                positive += record["value"]["positive"]
                known_negative += record["value"]["negative"]
        total = target["total_pixels"]
        if positive + known_negative > total:
            raise ValueError("overlapping support counted more than once")
        lower, upper = positive / total, 1 - known_negative / total
        threshold = target["fraction_threshold"]
        decision = "yes" if lower >= threshold else "no" if upper < threshold else "unknown"
        return {"decision": decision, "reason": "supported" if decision != "unknown" else "incomplete_coverage",
                "lower": lower, "upper": upper, "value": None}
    raise ValueError("unknown target operator")


def sufficient(episode, read_ids):
    goal = reference(episode, {x["id"] for x in legal_cards(episode)})
    visible = reference(episode, read_ids)
    if goal["decision"] != "unknown":
        return visible["decision"] == goal["decision"]
    if visible["decision"] != "unknown":
        return False
    target = episode["target"]
    all_records = relevant_records(episode, {x["id"] for x in legal_cards(episode)})
    read_records = relevant_records(episode, set(read_ids))
    if target["operator"] == "revision_delta":
        available = {r["version"] for r in all_records}
        invalid = {r["version"] for r in read_records if r["quality"] != "valid"}
        return any(v not in available or v in invalid for v in target["versions"])
    available = {r["support"] for r in all_records}
    inspected = {r["support"] for r in read_records}
    unread = available - inspected
    if target["operator"] == "count_threshold":
        # Both extreme completions of unread values must remain unresolved.
        return (visible["lower"] + len(unread) < target["count_threshold"]
                and visible["upper"] - len(unread) >= target["count_threshold"])
    if target["operator"] == "area_threshold":
        mass = sum(target["support_sizes"][s] for s in unread) / target["total_pixels"]
        return (visible["lower"] + mass < target["fraction_threshold"]
                and visible["upper"] - mass >= target["fraction_threshold"])
    raise ValueError("unknown target operator")


def certificates(episode):
    cards = legal_cards(episode)
    if len(cards) > 8:
        raise ValueError("exact sufficiency is limited to eight cards")
    costs = {x["id"]: x["cost"] for x in cards}
    minimal = []
    for ids in powerset(list(costs)):
        subset = set(ids)
        if any(set(x["ids"]).issubset(subset) for x in minimal):
            continue
        if sufficient(episode, ids):
            minimal.append({"ids": list(ids), "cost": sum(costs[x] for x in ids)})
    return {"minimal_sets": minimal, "minimum_cost": min(x["cost"] for x in minimal),
            "oracle_access": "private complete pool; ex-post certificate lower bound, not an online controller"}


def extension_cost(episode, read_ids):
    costs = {x["id"]: x["cost"] for x in legal_cards(episode)}
    return min(sum(costs[x] for x in item["ids"] if x not in read_ids)
               for item in certificates(episode)["minimal_sets"])


def score(episode, read_ids, answer, budget):
    cards = {x["id"]: x for x in legal_cards(episode)}
    read_ids = set(read_ids)
    if not read_ids.issubset(cards):
        raise ValueError("read contains an unavailable card")
    spent = sum(cards[x]["cost"] for x in read_ids)
    if spent > budget:
        raise ValueError("read budget exceeded")
    goal = reference(episode, set(cards))
    visible = reference(episode, read_ids)
    valid = (isinstance(answer, dict) and set(answer) == {"decision", "citations"}
             and answer.get("decision") in {"yes", "no", "unknown"}
             and isinstance(answer.get("citations"), list)
             and all(isinstance(x, str) for x in answer.get("citations", [])))
    cited = set(answer["citations"]) if valid else set()
    citation_access = valid and cited.issubset(read_ids)
    grounded = (citation_access and answer["decision"] == goal["decision"]
                and sufficient(episode, cited))
    goal_correct = bool(valid and answer["decision"] == goal["decision"])
    extra = extension_cost(episode, read_ids)
    return {"valid": valid, "goal_correct": goal_correct,
            "visible_decision_correct": bool(valid and answer["decision"] == visible["decision"]),
            "grounded_success": bool(grounded), "cited_only_read": bool(citation_access),
            "read_sufficient": sufficient(episode, read_ids),
            "goal_decision": goal["decision"], "visible_decision": visible["decision"],
            "spent": spent, "minimum_extra_cost": extra,
            "budget_resolvable": extra <= budget - spent,
            "avoidable_unresolved": bool(not goal_correct and extra <= budget - spent),
            "supported_but_incomplete": visible["decision"] == "unknown" and goal["decision"] != "unknown"}
