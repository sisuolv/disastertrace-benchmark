from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any



def iter_encoded_scenarios(path: Path) -> Iterator[tuple[str, dict[str, Any]]]:
    """Stream CyPortQA's Encoded_senario.json without loading the whole file."""
    try:
        import ijson  # type: ignore
    except ImportError:
        # Small-file fallback for smoke tests. Install ijson for the full CyPortQA file.
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict):
            raise ValueError("Encoded_senario.json root must be an object")
        for scenario_id, payload in data.items():
            if isinstance(payload, dict):
                yield str(scenario_id), payload
        return

    with path.open("rb") as handle:
        for scenario_id, payload in ijson.kvitems(handle, ""):
            if isinstance(payload, dict):
                yield str(scenario_id), payload


def build_candidate_index(path: Path, output: Path) -> int:
    """Create a compact candidate index; this does not invent publication times."""
    output.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with output.open("w", encoding="utf-8") as writer:
        for scenario_id, payload in iter_encoded_scenarios(path):
            scenario = payload.get("senario", {})  # upstream spelling is intentional
            port = scenario.get("port", {})
            cyclone = scenario.get("cyclone", {})
            time_map = scenario.get("time", {})
            row = {
                "scenario_id": scenario_id,
                "storm_name": cyclone.get("name"),
                "storm_year": cyclone.get("year"),
                "port_name": port.get("name"),
                "port_lon": (port.get("location") or {}).get("lon"),
                "port_lat": (port.get("location") or {}).get("lat"),
                "lead_times": sorted(time_map.keys(), key=lambda x: int(x)),
                "has_operation_labels": any(bool((entry or {}).get("operation")) for entry in time_map.values()),
            }
            writer.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1
    return count
