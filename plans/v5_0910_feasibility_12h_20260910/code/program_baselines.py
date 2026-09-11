"""Compare exact offline certificates to online policies without value peeking."""

import itertools
import json
from collections import Counter, defaultdict

from common import ROOT, digest, dump
from evidence_core import certificates, legal_cards, reference, score
from public_inputs import catalog_card, request


def relevant_ids(episode):
    target = episode["target"]
    result = []
    for item in [catalog_card(c) for c in legal_cards(episode)]:
        if any(r["entity"] == target["entity"] and r["variable"] == target["variable"]
               and r["unit"] == target["unit"] and r["support"] in target["supports"]
               and (target["operator"] != "revision_delta" or r["version"] in target["versions"])
               for r in item["record_index"]):
            result.append(item["id"])
    return sorted(result)


def run_order(episode, order, budget):
    read_ids = []
    costs = {c["id"]: c["cost"] for c in legal_cards(episode)}
    for cid in order:
        if sum(costs[x] for x in read_ids) + costs[cid] > budget:
            break
        read_ids.append(cid)
        if reference(episode, read_ids)["decision"] != "unknown":
            break
    answer = {"decision": reference(episode, read_ids)["decision"], "citations": read_ids}
    return score(episode, read_ids, answer, budget)


def main():
    episodes = json.loads((ROOT / "data/PILOT_EPISODES_PRIVATE.json").read_text())
    results = []
    output = ROOT / "data/public_examples_02"
    output.mkdir(exist_ok=False)
    checked_images = 0
    for episode in episodes:
        ids = [x["id"] for x in legal_cards(episode)]
        goal = reference(episode, ids)["decision"]
        cert = certificates(episode)
        for budget in [0, 1, 2, 3, 4]:
            rows = {"always_unknown": score(episode, [], {"decision": "unknown", "citations": []}, budget),
                    "metadata_rule": run_order(episode, relevant_ids(episode), budget),
                    "latest_issued_rule": run_order(episode, [x["id"] for x in sorted(
                        legal_cards(episode), key=lambda x: x["issued_at"], reverse=True)], budget)}
            for policy, result in rows.items():
                results.append({"episode": episode["id"], "family": episode["family"], "group": episode["group"],
                                "variant": episode["variant"], "budget": budget, "policy": policy,
                                "certificate_attainable": cert["minimum_cost"] <= budget, **result})
            random_results = [run_order(episode, order, budget) for order in itertools.permutations(ids)]
            results.append({"episode": episode["id"], "family": episode["family"], "group": episode["group"],
                            "variant": episode["variant"], "budget": budget, "policy": "uniform_random_exact_mean",
                            "certificate_attainable": cert["minimum_cost"] <= budget,
                            **{k: sum(float(x[k]) for x in random_results) / len(random_results)
                               for k in ["goal_correct", "grounded_success", "spent", "read_sufficient"]}})
            results.append({"episode": episode["id"], "family": episode["family"], "group": episode["group"],
                            "variant": episode["variant"], "budget": budget, "policy": "private_certificate_bound",
                            "grounded_success": cert["minimum_cost"] <= budget, "spent": cert["minimum_cost"],
                            "certificate_attainable": cert["minimum_cost"] <= budget})
        for representation in ["text", "image"]:
            public, assets = request(episode, ids, representation, "full", 4)
            if any(key in json.dumps(public) for key in ["PRIVATE", "best_track", "goal_decision", "controlled_pool_withholding"]):
                raise ValueError("private field in public request")
            for asset in assets:
                checked_images += 1
            if episode["family"] in ["NHC", "SEVIR"] and episode["variant"] == "complete_pool":
                prefix = episode["family"] + "-" + representation
                if not (output / (prefix + ".json")).exists():
                    dump(output / (prefix + ".json"), public)
                    for asset in assets:
                        (output / (prefix + "-" + asset["id"] + ".png")).write_bytes(asset["png"])
    aggregates = []
    for budget in [0, 1, 2, 3, 4]:
        for policy in sorted({x["policy"] for x in results}):
            rows = [x for x in results if x["budget"] == budget and x["policy"] == policy]
            aggregates.append({"budget": budget, "policy": policy, "episodes": len(rows),
                               "grounded_success": sum(float(x["grounded_success"]) for x in rows) / len(rows),
                               "mean_reads": sum(x["spent"] for x in rows) / len(rows)})
    dump(ROOT / "analysis/PROGRAM_BASELINES.json", {"rows": results, "aggregate": aggregates,
         "raster_table_checks": checked_images, "rendered_example_directory": str(output.relative_to(ROOT)),
         "random_policy": "Exact average over every legal card permutation; no random selection noise.",
         "oracle_limit": "Private certificates are ex-post lower bounds, not an executable information-blind policy."})
    print(json.dumps({"rendered_table_checks": checked_images,
                      "budget_two": [x for x in aggregates if x["budget"] == 2]}, indent=2))


if __name__ == "__main__":
    main()
