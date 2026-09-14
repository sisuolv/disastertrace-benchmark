"""Relocatable, network-disabled full journal and raw-response verification."""

import argparse
import hashlib
import json
import math
import socket
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--capsule", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()
    capsule = args.capsule.resolve()

    def deny_network(*args, **kwargs):
        raise RuntimeError("Network disabled by capsule verifier")

    socket.create_connection = deny_network
    socket.socket.connect = deny_network

    def audit(event, values):
        if event != "open" or not isinstance(values[0], (str, bytes)):
            return
        path = Path(values[0]).resolve()
        forbidden = Path("/mnt/afs/260010168/extreme_weather_benchmark")
        if path.is_relative_to(forbidden) and not path.is_relative_to(capsule):
            raise RuntimeError("Verifier attempted to read original workspace: " + str(path))

    sys.addaudithook(audit)
    sys.path.insert(0, str(capsule / "source"))
    sys.path.insert(0, str(capsule / "helpers"))
    from disastertrace.monitoring_fixed_v1.admission import (
        AdmissionEngine,
        score_admitted,
    )
    from disastertrace.monitoring_fixed_v1.contracts import EvidenceBundle
    from disastertrace.monitoring_fixed_v1.outcomes import ComparisonContract
    from disastertrace.monitoring_fixed_v1.support_bridge import native_slot_support
    from evidence_diagnostic import independent_reference, parse

    def read(path):
        return json.loads(path.read_text())

    manifest = read(capsule / "MANIFEST.json")
    for rel, record in manifest["files"].items():
        p = capsule / rel
        if p.stat().st_size != record["bytes"] or hashlib.sha256(p.read_bytes()).hexdigest() != record["sha256"]:
            raise ValueError("Capsule byte manifest mismatch: " + rel)
    result = {"network_disabled": True, "original_workspace_access_blocked": True,
              "manifest_files_verified": len(manifest["files"]), "model_calls": 0, "units": []}
    for unit in read(capsule / "UNITS.json")["F_units"]:
        folder = capsule / unit["path"]
        comp = read(folder / "COMPARISON.json")["payload"]
        comparison = ComparisonContract(comp["invariants"], comp["allowed_interventions"])
        journals = {a: folder / a / "admission.jsonl" for a in unit["arms"]}
        outcomes = read(folder / "OUTCOMES.json")
        canonical = score_admitted(outcomes, journals, comparison=comparison)
        y = {r["opportunity_id"]: r["value"] for r in outcomes}
        for arm, journal in journals.items():
            engine = AdmissionEngine.from_journal(journal)
            expected = read(folder / arm / "SCORES.json")["scores"]["arms"][arm]
            if canonical["scores"]["arms"][arm] != expected:
                raise ValueError("Full F score differs from original captured score")
            losses = [(r["forecast"]["value"]-y[oid])**2 for oid, r in engine.snapshots.items() if y[oid] is not None]
            if not math.isclose(math.fsum(losses), expected["loss_sum"], rel_tol=1e-12, abs_tol=1e-12):
                raise ValueError("Independent F arithmetic mismatch")
            report = read(folder / arm / "REPORT.json")
            if report["event_replay"] != engine.export():
                raise ValueError("Original F report and full journal disagree")
            captured = {}
            for path in (folder / arm / "captures").glob("*/REQUEST.json"):
                request = read(path)
                cid = request["call_id"].rsplit("/", 1)[-1]
                if cid in captured:
                    raise ValueError("Duplicate original F request")
                body = (path.parent / "RESPONSE.body").read_bytes()
                response, wire = read(path.parent / "RESPONSE.json"), read(path.parent / "WIRE_RECEIPT.json")
                assert hashlib.sha256(body).hexdigest() == wire["stored_body_sha256"]
                assert json.loads(body) == response["body"]
                captured[cid] = (request, response)
            if captured:
                assert set(captured) == {c["call_id"] for c in report["calls"]}
                for call in report["calls"]:
                    request, response = captured[call["call_id"]]
                    assert json.loads(request["payload"]["messages"][1]["content"]) == call["bundle"]["payload"]
                    assert response["body"]["choices"][0]["message"]["content"] == call["raw"]
        result["units"].append({"kind": "full_F_sessions", "path": unit["path"],
            "arms": unit["arms"], "opportunities": len(outcomes), "full_journals_replayed": len(journals)})
    folder = capsule / "temperature"
    units = read(capsule / "UNITS.json")["temperature"]
    comp = read(folder / units["arms"][0] / "COMPLETE.json")["invariants"]
    comparison = ComparisonContract(comp, {"arm": ["follow", "copy_current", "copy_latest", "first_issue_hold"],
        "protocol": ["base_bound_override", "persistent_override"]})
    scores = score_admitted(read(folder / "OUTCOMES.json"),
        {a: folder / a / "admission.jsonl" for a in units["arms"]}, comparison=comparison)
    original = read(folder / "SCORES.json")
    for arm in units["arms"]:
        if scores["scores"]["arms"][arm] != original["scores"]["arms"][arm]:
            raise ValueError("Temperature score differs from complete original month")
        engine = AdmissionEngine.from_journal(folder / arm / "admission.jsonl")
        if engine.snapshots != read(folder / arm / "SNAPSHOTS.json"):
            raise ValueError("Temperature full journal/snapshot mismatch")
    result["units"].append({"kind": "temperature_full_month", "month": "2017-01",
        "opportunities": scores["scores"]["registered"], "arms": units["arms"]})
    truth = {"supported": "true", "refuted": "false", "undetermined": "unknown", "inconsistent": "conflict"}
    e = read(capsule / "E02/UNIT.json")
    by_view = {}
    for task in e["tasks"]:
        request = read(capsule / "E02/policy" / (task["call_id"] + ".json"))
        if task["representation"] == "full_bundle":
            by_view[task["condition"]] = json.loads(request["messages"][1]["content"])
    count, changed, invalid = 0, 0, 0
    for task in e["tasks"]:
        view = by_view[task["condition"]]
        ref = independent_reference(view)
        bundle = EvidenceBundle.freeze(view)
        assert ref["fact_truth"] == truth[native_slot_support(bundle)["status"]]
        for model in e["models"]:
            prefix = capsule / "E02/captures" / model / task["call_id"]
            response, body = read(prefix / "RESPONSE.json"), (prefix / "RESPONSE.body").read_bytes()
            assert hashlib.sha256(body).hexdigest() == response["original_body_sha256"]
            assert json.loads(body) == response["body"]
            original_score = read(prefix / "ORIGINAL_SCORE.json")
            try:
                answer = parse(response["body"]["choices"][0]["message"]["content"], task["query_ids"], task["reasoning"])
            except (ValueError, TypeError):
                assert not original_score["valid"] and not original_score["correct"]
                count += 1
                invalid += 1
                continue
            valid = response["body"]["choices"][0]["finish_reason"] == "stop"
            assert original_score["correct"] == (valid and answer["fact_truth"] == ref["fact_truth"])
            if task["reasoning"] == "slotwise":
                from disastertrace.monitoring_v1.e_composition import aggregate

                changed += aggregate(answer["slots"].values()) != answer["fact_truth"]
            count += 1
    result["units"].append({"kind": "E02_raw_response_and_two_reducers", "answers": count,
        "aggregation_changes": changed, "invalid_retained": invalid, "selection": e["selection"]})
    result["passed"] = True
    args.result.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
