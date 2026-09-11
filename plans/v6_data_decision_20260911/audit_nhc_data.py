"""Recheck frozen NHC source bytes and derive data-selection audit tables offline."""

import argparse
import csv
import hashlib
import io
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path


class PreText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.blocks = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        if tag == "pre":
            if self.current is not None:
                raise ValueError("nested PRE")
            self.current = []

    def handle_endtag(self, tag):
        if tag == "pre" and self.current is not None:
            self.blocks.append("".join(self.current).strip())
            self.current = None

    def handle_data(self, data):
        if self.current is not None:
            self.current.append(data)


def load(path):
    return json.loads(path.read_text())


def checked_source(repo, record):
    path = (repo / record["path"]).resolve()
    path.relative_to(repo.resolve())
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != record["sha256"]:
        raise ValueError(f"source hash mismatch: {path}")
    return raw


def resolve_time(issue, token):
    day, hhmm = token.rstrip("Z").split("/")
    candidates = []
    for shift in range(7):
        day_date = issue.date() + timedelta(days=shift)
        if day_date.day == int(day):
            candidate = datetime(day_date.year, day_date.month, day_date.day,
                                 int(hhmm[:2]), int(hhmm[2:]), tzinfo=timezone.utc)
            if candidate > issue:
                candidates.append(candidate)
    if len(candidates) != 1:
        raise ValueError("ambiguous or non-future target")
    return candidates[0]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise ValueError("output directory must be new")
    repo = Path(__file__).resolve().parents[2]
    prior = repo / "plans/v5_0910_feasibility_12h_20260910"
    products = load(prior / "data/NHC_PRODUCTS.json")
    old_join = load(prior / "data/NHC_OUTCOME_JOINS_PRIVATE.json")
    forecasts, sources, non_numeric = [], [], []
    for product in products:
        source = product["source"]
        raw = checked_source(repo, source)
        html = PreText()
        html.feed(raw.decode("utf-8"))
        if html.blocks != [product["raw_text"]]:
            raise ValueError("raw PRE text differs from inherited product")
        text = html.blocks[0]
        issue_match = re.search(r"^(\d{4} UTC [A-Z]{3} [A-Z]{3} \d{2} \d{4})$", text, re.M)
        issue = datetime.strptime(issue_match[1], "%H%M UTC %a %b %d %Y").replace(tzinfo=timezone.utc)
        storm = re.search(r"\b(AL\d{6})\b", text)[1]
        advisory = int(re.search(r"FORECAST/ADVISORY NUMBER\s+(\d+)", text)[1])
        current_wind = int(re.search(r"MAX SUSTAINED WINDS\s+(\d+) KT", text)[1])
        if (storm, advisory, issue.isoformat(), current_wind) != (
            product["storm_id"], product["advisory_number"], product["issue_time"], product["current_wind_kt"]
        ):
            raise ValueError("product header disagreement")
        lines = text.splitlines()
        parsed = []
        for i, line in enumerate(lines):
            tokens = line.split()
            if len(tokens) < 3 or tokens[:2] not in (["FORECAST", "VALID"], ["OUTLOOK", "VALID"]):
                continue
            next_tokens = lines[i + 1].split() if i + 1 < len(lines) else []
            if len(next_tokens) < 4 or next_tokens[:2] != ["MAX", "WIND"]:
                non_numeric.append({"storm_id": storm, "advisory": advisory, "line": i + 1})
                continue
            if next_tokens[3] != "KT...GUSTS":
                raise ValueError("unexpected forecast wind unit/format")
            valid = resolve_time(issue, tokens[2])
            wind = int(next_tokens[2])
            parsed.append((valid.isoformat(), wind))
            forecasts.append({
                "storm_id": storm, "advisory_number": advisory,
                "issue_time": issue.isoformat(), "target_time": valid.isoformat(),
                "forecast_wind_kt": wind, "persistence_wind_kt": current_wind,
                "lead_hours": (valid - issue).total_seconds() / 3600,
                "historical_available_at": None,
                "availability_reason": "no historical public availability proof",
                "source_path": source["path"], "source_sha256": source["sha256"],
                "decoded_pre_target_line": i + 1,
            })
        if parsed != [(r["valid_time"], r["wind_kt"]) for r in product["forecasts"]]:
            raise ValueError("independent line parser disagreement")
        sources.append({"path": source["path"], "sha256": source["sha256"], "bytes": len(raw)})

    outcome_source = old_join["source"]
    raw_outcome = checked_source(repo, outcome_source)
    sources.append({"path": outcome_source["path"], "sha256": outcome_source["sha256"],
                    "bytes": len(raw_outcome)})
    selected_storms = {r["storm_id"] for r in forecasts}
    reader = csv.reader(io.StringIO(raw_outcome.decode("utf-8")))
    outcomes = defaultdict(list)
    for header in reader:
        if not header or not re.fullmatch(r"AL\d{6}", header[0].strip()):
            raise ValueError("invalid HURDAT2 header")
        storm, count = header[0].strip(), int(header[2])
        for _ in range(count):
            row = [part.strip() for part in next(reader)]
            if storm not in selected_storms:
                continue
            valid = datetime.strptime(row[0] + row[1], "%Y%m%d%H%M").replace(tzinfo=timezone.utc)
            outcomes[storm, valid.isoformat()].append({"wind_kt": int(row[6]), "status": row[3],
                                                      "record_identifier": row[2], "raw_line": reader.line_num})
    by_target = defaultdict(list)
    for forecast in forecasts:
        by_target[forecast["storm_id"], forecast["target_time"]].append(forecast)
    targets, matched, unresolved = [], [], []
    for (storm, target), rows in sorted(by_target.items()):
        observed = outcomes.get((storm, target), [])
        values = {r["wind_kt"] for r in observed}
        reason = None
        if not observed:
            reason = "no_exact_best_track_time"
        elif len(values) != 1:
            reason = "conflicting_outcomes"
        elif min(values) < 0:
            reason = "missing_wind_sentinel"
        value = None if reason else observed[0]["wind_kt"]
        target_record = {
            "target_id": f"{storm}:{target}:maximum_sustained_wind:ge64kt",
            "storm_id": storm, "target_time": target,
            "variable": "storm_maximum_sustained_wind", "unit": "kt",
            "operator": ">=", "threshold": 64, "forecast_version_count": len(rows),
            "source_role": "retrospective_same_agency_reference", "status": "unresolved" if reason else "resolved",
            "outcome_value": value, "y": None if reason else int(value >= 64),
            "reason": reason, "outcome_records": observed,
            "source_path": outcome_source["path"], "source_sha256": outcome_source["sha256"],
            "exposure": "previously_observed_development", "independent_group": storm,
        }
        targets.append(target_record)
        for row in rows:
            if reason:
                unresolved.append({**row, "reason": reason})
            else:
                matched.append({**row, "best_track_wind_kt": value})

    def signature(row):
        return (row["storm_id"], row["advisory_number"], row["issue_time"], row["target_time"],
                row["forecast_wind_kt"], row["persistence_wind_kt"], row["best_track_wind_kt"])

    if Counter(map(signature, matched)) != Counter(map(signature, old_join["joined"])):
        raise ValueError("new source-derived join disagrees with inherited join")
    old_unmatched = {(r["storm_id"], r["advisory_number"], r["target_time"]) for r in old_join["unmatched"]}
    new_unmatched = {(r["storm_id"], r["advisory_number"], r["target_time"]) for r in unresolved}
    if old_unmatched != new_unmatched:
        raise ValueError("unresolved forecast rows changed")
    resolved_targets = [r for r in targets if r["status"] == "resolved"]
    report = {
        "status": "source_verified_for_controlled_development_data_design",
        "source_files_verified": len(sources), "inherited_source_bytes_verified": sum(r["bytes"] for r in sources),
        "advisories": len(products), "forecast_rows": len(forecasts), "matched_forecast_rows": len(matched),
        "unmatched_forecast_rows": len(unresolved), "unique_targets": len(targets),
        "resolved_unique_targets": len(resolved_targets),
        "unresolved_unique_targets": len(targets) - len(resolved_targets),
        "unique_target_labels_ge64kt": dict(Counter(str(r["y"]) for r in resolved_targets)),
        "storm_groups": len(selected_storms), "storm_ids": sorted(selected_storms),
        "resolved_targets_per_storm": dict(Counter(r["storm_id"] for r in resolved_targets)),
        "matched_best_track_statuses": dict(Counter(s["status"] for r in resolved_targets for s in r["outcome_records"])),
        "non_numeric_forecast_lines": non_numeric, "inherited_join_reproduced": True,
        "formal_warning_episodes_created": 0, "new_model_calls": 0,
        "limitations": ["Four selected, previously exposed development systems; correlated target times and versions.",
                        "Forecast issue time is not established historical availability.",
                        "HURDAT2 is retrospective same-agency analysis, not independent raw measurements.",
                        "The threshold labels wind magnitude, not tropical cyclone status or local wind exposure.",
                        "Data design audit tables are not a frozen benchmark or calibrated probability baseline."],
        "sources": sources,
    }
    args.output_dir.mkdir(parents=True)
    for name, rows in [("forecast_rows.jsonl", forecasts), ("outcome_targets_private.jsonl", targets),
                       ("unresolved_rows_private.jsonl", unresolved)]:
        with (args.output_dir / name).open("x") as stream:
            for row in rows:
                stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    (args.output_dir / "AUDIT.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "sources"}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
