"""Independent exact-arithmetic solver consumes only the model's public JSON."""

from fractions import Fraction
import json

from common import ROOT, dump


def solve(public):
    target = public["target"]
    rows = [r for card in public["evidence"] for r in card["records"]
            if all(r[k] == target[k] for k in ["entity", "variable", "unit"])
            and r["support"] in target["supports"] and r["quality"] == "valid"]
    if target["operator"] == "revision_delta":
        pair = [[r["value"] for r in rows if r["version"] == version] for version in target["versions"]]
        if any(not values for values in pair):
            return "unknown"
        if any(len(set(values)) != 1 for values in pair):
            raise ValueError("ambiguous public forecast version")
        return "yes" if pair[1][0] - pair[0][0] >= target["threshold"] else "no"
    if target["operator"] == "count_threshold":
        known = {r["support"]: r["value"] for r in rows if r["value"] is not None}
        positives = sum(v >= target["value_threshold"] for v in known.values())
        negatives = len(known) - positives
        if positives >= target["count_threshold"]:
            return "yes"
        if len(target["supports"]) - negatives < target["count_threshold"]:
            return "no"
        return "unknown"
    if target["operator"] == "area_threshold":
        positive = sum(r["value"]["positive"] for r in rows)
        negative = sum(r["value"]["negative"] for r in rows)
        required = Fraction(str(target["fraction_threshold"])) * target["total_pixels"]
        if positive >= required:
            return "yes"
        if target["total_pixels"] - negative < required:
            return "no"
        return "unknown"
    raise ValueError("unrecognized public operator")


def main():
    public = json.loads((ROOT / "gpu/wave2/PUBLIC.json").read_text())
    from evidence_core import reference
    episodes = {e["id"]: e for e in json.loads((ROOT / "data/PILOT_EPISODES_PRIVATE.json").read_text())}
    checks = []
    for eid, variants in public.items():
        episode = episodes[eid]
        full = variants["full_text"]["initial"]["public"]
        result = solve(full)
        expected = reference(episode, full["read_ids"])["decision"]
        if result != expected:
            raise ValueError("public-only solver differs from private oracle: " + eid)
        states = variants["active2_text"]["states"]
        for state in states.values():
            visible = solve(state["public"])
            expected_visible = reference(episode, state["public"]["read_ids"])["decision"]
            if visible != expected_visible:
                raise ValueError("public-only visible solver disagreement")
        checks.append({"episode": eid, "full_decision": result, "active_states_checked": len(states)})
    dump(ROOT / "analysis/PUBLIC_SOLVABILITY.json", {"status": "passed", "episodes": len(checks),
        "active_states": sum(c["active_states_checked"] for c in checks), "checks": checks,
        "independence": "Separate arithmetic implementation consumes public evidence, target and rules; scorer is used only for comparison.",
        "limit": "Proves task-relevant facts are available in public text; native image readability is a separate issue."})
    print("Public-only solver agrees on every full and reachable active-text state")


if __name__ == "__main__":
    main()
