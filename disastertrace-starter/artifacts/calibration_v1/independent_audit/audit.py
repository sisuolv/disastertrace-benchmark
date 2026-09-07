"""Independent offline integrity and calibration-package review; no provider calls."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ORIGINAL_BUILD = ROOT / "work/build-p1-deepseek-v1"
P1_SUMS = ROOT / "artifacts/p1_deepseek_development/continuation_package/SHA256SUMS"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class Audit:
    def __init__(self) -> None:
        self.checks = []
        self.bindings = {}

    def check(self, condition: bool, name: str, details=None) -> None:
        row = {"name": name, "passed": bool(condition)}
        if details is not None:
            row["details"] = details
        self.checks.append(row)

    def bind(self, path: Path) -> None:
        self.bindings[str(path.resolve())] = sha(path)

    def historical_integrity(self) -> None:
        self.bind(P1_SUMS)
        entries = [line.split("  ", 1) for line in P1_SUMS.read_text().splitlines() if line]
        self.check(len(entries) == 359, "original_completed_archive_has_359_entries")
        for expected, name in entries:
            path = ROOT / name
            self.check(path.is_file() and sha(path) == expected, "historical_checksum:" + name)
        implementation_path = ORIGINAL_BUILD / "implementation.json"
        self.bind(implementation_path)
        implementation = read(implementation_path)
        self.check(len(implementation["files"]) == 20, "original_core_has_20_files")
        for name, expected in implementation["files"].items():
            path = ROOT / "src/disastertrace/automated" / name
            self.check(path.is_file() and sha(path) == expected, "original_core_source:" + name)
        self.check(
            implementation["implementation_id"]
            == "58acc19bf32eb83709344c7f8c001b2d86d8b665339ef251a5cd7b774784e716",
            "original_implementation_identity",
        )

    def contract_surface(self) -> None:
        from disastertrace.automated.common import canonical
        from disastertrace.automated.dynamic import FIELDS, render_request
        from disastertrace.automated.output_contract import (
            contract_spec,
            render_calibration_request,
        )
        from disastertrace.automated.provider import ProviderClient, ProviderConfig

        source = ROOT / "src/disastertrace/automated/output_contract.py"
        self.bind(source)
        episodes = [
            json.loads(line)
            for line in (ORIGINAL_BUILD / "episodes/dynamic_episodes.jsonl")
            .read_text()
            .splitlines()
            if json.loads(line)["split"] == "development"
        ]
        instructions = set()
        config = ProviderConfig.from_dict(
            read(ROOT / "artifacts/p1_deepseek_development/provider.json")
        )
        client = ProviderClient(config)
        carrier = {
            "state": {
                name: {"status": "unknown", "value": None, "evidence": []} for name in FIELDS
            },
            "action": "prepare",
        }
        carrier["state"]["maximum_wind_mph"] = {"status": "known", "value": -777473, "evidence": []}
        for episode in episodes:
            visible = []
            records = {record["record_id"]: record for record in episode["records"]}
            for checkpoint in episode["checkpoints"]:
                visible.extend(checkpoint["arrivals"])
                evidence = [
                    {
                        "delivery_index": index,
                        "record_id": record_id,
                        "issued_at": records[record_id]["issued_at"],
                        "text": "\n".join(
                            f"{number}: {line}"
                            for number, line in enumerate(
                                records[record_id]["raw_text"].splitlines(), 1
                            )
                        ),
                    }
                    for index, record_id in enumerate(visible)
                ]
                poisoned = copy.deepcopy(episode)
                poisoned["private_gold"] = "AUDIT_PRIVATE_SENTINEL"
                for record in poisoned["records"]:
                    record["fields"] = {name: 777474 for name in FIELDS}
                    record["field_evidence"] = {"private": "AUDIT_PRIVATE_SENTINEL"}
                    record["provenance"] = {"private": "AUDIT_PRIVATE_SENTINEL"}
                    if record["record_id"] not in visible:
                        record["raw_text"] += "\nAUDIT_FUTURE_SENTINEL"
                for method in ("snapshot", "structured_state", "answer_history"):
                    label = ":".join((episode["episode_id"], checkpoint["checkpoint_id"], method))
                    previous, history = copy.deepcopy(carrier), [copy.deepcopy(carrier)]
                    before = copy.deepcopy((poisoned, previous, history))
                    request = render_calibration_request(
                        poisoned,
                        checkpoint["checkpoint_id"],
                        previous,
                        method=method,
                        history=history,
                    )
                    legacy = render_request(
                        episode,
                        checkpoint["checkpoint_id"],
                        previous,
                        method=method,
                        history=history,
                    )
                    old_contract = render_calibration_request(
                        poisoned,
                        checkpoint["checkpoint_id"],
                        previous,
                        method=method,
                        history=history,
                        contract="legacy_v1",
                    )
                    self.check(old_contract == legacy, "legacy_byte_equivalence:" + label)
                    self.check(
                        set(request) == set(legacy)
                        and {key for key in legacy if request[key] != legacy[key]}
                        == {"instruction"},
                        "instruction_only_change:" + label,
                    )
                    self.check(
                        request["evidence"] == evidence, "independent_delivered_evidence:" + label
                    )
                    self.check(
                        all(
                            datetime.fromisoformat(record["issued_at"])
                            <= datetime.fromisoformat(checkpoint["at"])
                            for record in evidence
                        ),
                        "no_future_issued_records:" + label,
                    )
                    text = canonical(request)
                    self.check(
                        "AUDIT_PRIVATE_SENTINEL" not in text
                        and "AUDIT_FUTURE_SENTINEL" not in text
                        and "777474" not in text,
                        "private_and_future_poison_not_exposed:" + label,
                    )
                    self.check(
                        (poisoned, previous, history) == before,
                        "request_inputs_not_mutated:" + label,
                    )
                    if method == "structured_state":
                        self.check(
                            request["previous_state"] == carrier,
                            "model_error_carrier_not_repaired:" + label,
                        )
                    elif method == "answer_history":
                        self.check(
                            request["answer_history"] == [carrier],
                            "model_error_history_not_repaired:" + label,
                        )
                    instructions.add(request["instruction"])
                    wire = json.loads(client.prepare(request)["raw_request"])
                    self.check(
                        len(wire["messages"]) == 2
                        and [m["role"] for m in wire["messages"]] == ["system", "user"]
                        and json.loads(wire["messages"][1]["content"]) == request
                        and "response_format" not in wire
                        and "tools" not in wire,
                        "fresh_plain_json_prompt_wire:" + label,
                    )
        self.check(
            len(instructions) == 1, "common_explicit_instruction_across_all_methods_and_checkpoints"
        )
        spec = contract_spec()
        self.check(
            "always unknown" not in canonical(spec).lower()
            and "examples" not in canonical(spec["json_schema"]),
            "no_instance_examples_or_port_gold_shortcut",
        )
        self.check(
            spec["provider_json_mode"] is False
            and spec["scope"] == "offline_prompt_calibration_only",
            "contract_does_not_claim_live_json_mode",
        )

    def write(self, path: Path) -> dict:
        self.check(
            all(
                Path(name).is_file() and sha(Path(name)) == digest
                for name, digest in self.bindings.items()
            ),
            "bound_inputs_unchanged_during_audit",
        )
        result = {
            "schema_version": "calibration_independent_audit_v1",
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "passed": all(row["passed"] for row in self.checks),
            "check_count": len(self.checks),
            "failure_count": sum(not row["passed"] for row in self.checks),
            "checks": self.checks,
            "input_sha256": self.bindings,
            "audit_source_sha256": sha(Path(__file__)),
            "new_api_calls": 0,
            "new_human_item_reviews": 0,
            "new_llm_judge_calls": 0,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            raise ValueError("audit result exists; preserve the prior result")
        path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="ascii")
        return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--contract", action="store_true")
    args = parser.parse_args()
    audit = Audit()
    audit.historical_integrity()
    if args.contract:
        audit.contract_surface()
    result = audit.write(args.output)
    print(
        json.dumps(
            {
                key: result[key]
                for key in ("passed", "check_count", "failure_count", "new_api_calls")
            }
        )
    )
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
