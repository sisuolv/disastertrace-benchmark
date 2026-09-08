"""Bounded controlled probes with literal expectations, separate from frozen E1 tasks."""

import argparse
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path

from disastertrace.automated.common import canonical, fingerprint
from disastertrace.controlled import compiler, generator, public_oracle, renderer
from disastertrace.controlled.schema import FIELDS
from disastertrace.local_eval.storage import seal, write
from disastertrace.post_p5.policies import POLICIES, solve

OPERATIONS = ("replay", "same", "change", "other_entity", "other_window")


def build(operations):
    if not operations or len(operations) > 20 or any(o not in OPERATIONS for o in operations):
        raise ValueError("bounded nonempty operation sequence required")
    ep = deepcopy(generator.micro_episodes()[0])
    root = deepcopy(ep["records"][0])
    ep["records"] = [root]
    ep["deliveries"] = ep["deliveries"][:1]
    base_time = datetime.fromisoformat(ep["checkpoints"][0]["at"])
    ep["checkpoints"] = [
        {"checkpoint_id": f"c{i}", "at": (base_time + timedelta(minutes=m)).isoformat()}
        for i, m in enumerate((0, 1, 30, 40, 50))
    ]
    expected = {
        "state": {
            field: {
                "status": "known",
                "value": value,
                "evidence": [{"record_id": root["record_id"], "line": i + 2}],
            }
            for i, (field, value) in enumerate(zip(FIELDS, (90, 980, 20, -70)))
        },
        "action": "monitor",
    }
    prior = root["assertions"][0]["revision_id"]
    certificates = []
    for index, operation in enumerate(operations):
        before = deepcopy(expected)
        at = (base_time + timedelta(minutes=index + 2)).isoformat()
        if operation == "replay":
            record_id = root["record_id"]
        else:
            record_id = f"probe-record-{index}"
            value = expected["state"][FIELDS[0]]["value"]
            if operation == "change":
                value = 110 if value == 90 else 90
            assertion = {
                **deepcopy(root["assertions"][0]),
                "revision_id": f"probe-revision-{index}",
                "supersedes": prior,
                "value": value,
            }
            if operation.startswith("other_"):
                assertion["supersedes"] = None
                if operation == "other_entity":
                    assertion["entity_id"] = f"other-entity-{index}"
                else:
                    assertion["valid_end"] = (base_time + timedelta(hours=index + 2)).isoformat()
            else:
                prior = assertion["revision_id"]
                expected["state"][FIELDS[0]] = {
                    "status": "known",
                    "value": value,
                    "evidence": [{"record_id": record_id, "line": 2}],
                }
                expected["action"] = "prepare" if value == 110 else "monitor"
            ep["records"].append(
                {
                    "record_id": record_id,
                    "issued_at": at,
                    "operation": "SET" if operation.startswith("other_") else "PATCH",
                    "source_origin": "controlled_generated",
                    "assertions": [assertion],
                }
            )
        ep["deliveries"].append(
            {"delivery_id": f"probe-delivery-{index}", "record_id": record_id, "delivered_at": at}
        )
        certificates.append(
            {
                "operation": operation,
                "public_transformation": operation,
                "changed_keys": [f for f in FIELDS if before["state"][f] != expected["state"][f]],
                "preserved_keys": [f for f in FIELDS if before["state"][f] == expected["state"][f]],
                "expected_relation": "identity"
                if operation in ("replay", "other_entity", "other_window")
                else "same_value_new_authority"
                if operation == "same"
                else "new_value_new_authority",
            }
        )
    return ep, expected, certificates


def prepare(output):
    sequences = [(o,) for o in OPERATIONS] + [
        ("same", "replay"),
        ("change", "same", "replay"),
        ("same", "change", "replay"),
        ("other_entity", "same", "other_window"),
    ]
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    probes, coverage = [], []
    for index, operations in enumerate(sequences):
        ep, expected, certificates = build(operations)
        req = renderer.render_request(ep, "c2", method="snapshot")
        if compiler.reference_at(ep, "c2") != expected or public_oracle.answer(req) != expected:
            raise ValueError("independent oracles differ from literal probe expectation")
        probes.append(
            {
                "probe_id": f"source-binding-{index}",
                "origin": "synthetic_software_fixture",
                "episode": ep,
                "public_request": req,
                "private_expected": expected,
                "private_legality_certificate": certificates,
                "public_request_sha256": fingerprint(req),
            }
        )
        coverage.extend(
            {
                "probe_id": f"source-binding-{index}",
                "policy": policy,
                "all_correct": solve(req, policy) == expected,
            }
            for policy in POLICIES
        )
    with (output / "fixtures.jsonl").open("x") as stream:
        for row in probes:
            stream.write(canonical(row) + "\n")
    write(output / "policy_coverage.json", coverage)
    result = {
        "status": "passed",
        "schema_version": "source_binding_probe_v1",
        "probes": len(probes),
        "public_private_literal_agreements": len(probes),
        "operations": list(OPERATIONS),
        "additional_model_calls": 0,
        "included_in_E1": False,
        "length_matched_factorial_matrix_implemented": False,
    }
    write(output / "report.json", result)
    seal(output)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    print(prepare(parser.parse_args().output), flush=True)
