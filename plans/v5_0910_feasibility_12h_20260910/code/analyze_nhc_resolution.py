"""Separate source revision correctness from retrospective best-track error."""

from collections import Counter, defaultdict
import json
from statistics import mean

from common import ROOT, dump


def main():
    joins = json.loads((ROOT / "data/NHC_OUTCOME_JOINS_PRIVATE.json").read_text())
    chains = json.loads((ROOT / "data/NHC_REVISION_CHAINS.json").read_text())
    known = {}
    for row in joins["joined"]:
        key = (row["storm_id"], row["target_time"])
        value = row["best_track_wind_kt"]
        if key in known and known[key] != value:
            raise ValueError("same-target best-track outcome inconsistent")
        known[key] = value
    changes, unresolvable = [], []
    for chain in chains:
        outcome = known.get((chain["storm_id"], chain["target_time"]))
        revisions = chain["revisions"]
        for old, new in zip(revisions, revisions[1:]):
            if new["issue_time"] <= old["issue_time"]:
                raise ValueError("revision order invalid")
            if outcome is None:
                unresolvable.append({"storm": chain["storm_id"], "target": chain["target_time"]})
                continue
            before, after = abs(old["forecast_wind_kt"] - outcome), abs(new["forecast_wind_kt"] - outcome)
            changes.append({"storm": chain["storm_id"], "target": chain["target_time"],
                "before_issue": old["issue_time"], "after_issue": new["issue_time"],
                "before_wind_kt": old["forecast_wind_kt"], "after_wind_kt": new["forecast_wind_kt"],
                "best_track_wind_kt": outcome, "before_error_kt": before, "after_error_kt": after,
                "value_changed": old["forecast_wind_kt"] != new["forecast_wind_kt"],
                "outcome_effect": "improved" if after < before else "worsened" if after > before else "unchanged"})
    lead_groups = defaultdict(list)
    for row in joins["joined"]:
        hours = row["lead_hours"]
        label = next((f"({low},{high}]h" for low, high in [(0, 24), (24, 48), (48, 72), (72, 120)] if low < hours <= high), ">120h")
        lead_groups[label].append(row)
    report = {"joined_forecast_rows": len(joins["joined"]), "unmatched_rows": len(joins["unmatched"]),
        "storm_groups": len({r["storm_id"] for r in joins["joined"]}),
        "resolved_revision_transitions": len(changes), "unresolved_revision_transitions": len(unresolvable),
        "all_resolved_transition_effects": dict(Counter(r["outcome_effect"] for r in changes)),
        "changed_value_transition_effects": dict(Counter(r["outcome_effect"] for r in changes if r["value_changed"])),
        "source_refresh_only_transitions": sum(not r["value_changed"] for r in changes),
        "lead_groups": [{"lead": lead, "rows": len(rows),
            "nhc_forecast_mae_kt": mean(abs(r["forecast_wind_kt"] - r["best_track_wind_kt"]) for r in rows),
            "persistence_mae_kt": mean(abs(r["persistence_wind_kt"] - r["best_track_wind_kt"]) for r in rows)}
            for lead, rows in sorted(lead_groups.items())],
        "rows": changes,
        "interpretation": "A newer compatible source can be correctly selected even when its wind forecast becomes less accurate against frozen retrospective HURDAT2.",
        "limitations": ["Selected development storms, correlated targets and decreasing forecast lead; no causal effect of revision frequency.",
            "HURDAT2 is same-agency retrospective analysis; no independent raw observation truth.",
            "No LLM future forecasting was evaluated here."]}
    dump(ROOT / "analysis/NHC_RESOLUTION_DIAGNOSTIC.json", report)
    print(json.dumps({k: v for k, v in report.items() if k != "rows"}, indent=2))


if __name__ == "__main__":
    main()
