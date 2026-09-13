import json

from disastertrace.monitoring_v1.journal import EventJournal
from e_probe_runtime import run_session


def test_invalid_probe_keeps_every_case_and_charges_real_tokens(tmp_path):
    cases = [
        {
            "case_id": str(i),
            "read_query_ids": [],
            "requests": {"E_only": {"case_id": str(i)}},
        }
        for i in range(3)
    ]
    data = {"cases": cases, "systems": {"E_only": "test"}}
    config = {
        "condition": "E_only",
        "token_cap": 300,
        "compute_ms_cap": 3000,
        "input_token_cap": 80,
        "output_token_cap": 20,
        "call_compute_cap_ms": 1000,
    }
    replies = iter(
        ["invalid", '{"e_status":"supported","extra":1}', '{"e_status":"undetermined"}']
    )
    with (
        EventJournal(tmp_path / "events") as events,
        EventJournal(tmp_path / "resources") as resources,
    ):
        trace = run_session(
            data,
            {},
            config,
            lambda *_: (
                next(replies),
                {
                    "input_tokens": 10,
                    "output_tokens": 5,
                    "seconds": 0.01,
                    "ended_with_eos": True,
                },
            ),
            events,
            resources,
        )
    assert [c["case_id"] for c in trace["calls"]] == ["0", "1", "2"]
    assert [bool(c["error"]) for c in trace["calls"]] == [True, True, False]
    assert trace["resource_spent"]["tokens"] == 45
    assert trace["resource_spent"]["compute_ms"] == 30
    assert not any(trace["resource_reserved"].values())
    assert "labels" not in json.dumps(data)
