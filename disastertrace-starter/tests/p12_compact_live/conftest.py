"""Small synthetic software fixtures, independent of natural task selection."""

import pytest

from disastertrace.forecast_cohort.protocol import schedule
from disastertrace.forecast_source import normalization, parser_a, parser_b
from disastertrace.forecast_task.compiler import compile_sources


def source(
    number=5,
    issue="2100 UTC TUE DEC 31 2024",
    center="31/2100Z",
    rows=None,
    storm="AL062024",
    lat="15.0N",
    lon="50.0W",
    wind=65,
    gust=80,
):
    if rows is None:
        rows = f"FORECAST VALID 01/0600Z {lat} {lon}\nMAX WIND {wind} KT...GUSTS {gust} KT.\n"
    raw = (
        f"<html><pre>\nHURRICANE EXAMPLE FORECAST/ADVISORY NUMBER {number}\n"
        f"NWS NATIONAL HURRICANE CENTER MIAMI FL {storm}\n{issue}\n"
        f"HURRICANE CENTER LOCATED NEAR 14.0N 49.0W AT {center}\n"
        "PRESENT MOVEMENT TOWARD THE WEST OR 270 DEGREES AT 12 KT\n"
        "MAXIMUM SUSTAINED WINDS 50 KT WITH GUSTS TO 60 KT.\n"
        "ESTIMATED MINIMUM CENTRAL PRESSURE 980 MB\n"
        f"REPEAT...CENTER LOCATED NEAR 14.0N 49.0W AT {center}\n"
        f"{rows}\n$$\nFORECASTER EXAMPLE\n</pre></html>"
    ).encode()
    first, second = parser_a.parse(raw), parser_b.parse(raw)
    assert first == second
    return {
        "source_id": f"{storm.lower()}-fstadv-{number:03d}",
        "product": first,
        "canonical": normalization.normalize(raw),
        "raw": raw,
        "retrieved_at": "2026-09-08T00:00:00+00:00",
        "url": "fixture://synthetic",
    }


@pytest.fixture
def sources():
    return [
        source(
            rows=(
                "FORECAST VALID 01/0600Z 15.0N 50.0W\nMAX WIND 65 KT...GUSTS 80 KT.\n"
                "FORECAST VALID 01/1800Z 16.0N 51.0W\nMAX WIND 70 KT...GUSTS 90 KT.\n"
                "OUTLOOK VALID 02/0600Z 17.0N 52.0W...POST-TROPICAL\nMAX WIND 35 KT...GUSTS 45 KT.\n"
                "OUTLOOK VALID 03/0600Z...DISSIPATED\n"
            )
        ),
        source(
            number=6,
            issue="0300 UTC WED JAN 01 2025",
            center="01/0300Z",
            rows=(
                "FORECAST VALID 01/0600Z 15.0N 50.0W\nMAX WIND 65 KT...GUSTS 80 KT.\n"
                "FORECAST VALID 01/1200Z 16.0N 51.0W\nMAX WIND 70 KT...GUSTS 90 KT.\n"
                "OUTLOOK VALID 02/0600Z 18.0N 52.0W...POST-TROPICAL\nMAX WIND 35 KT...GUSTS 45 KT.\n"
                "OUTLOOK VALID 03/0600Z...ABSORBED\n"
            ),
        ),
        source(
            number=7,
            issue="0900 UTC WED JAN 01 2025",
            center="01/0900Z",
            rows=(
                "FORECAST VALID 01/1200Z 16.5N 52.0W\nMAX WIND 80 KT...GUSTS 95 KT.\n"
                "OUTLOOK VALID 02/1800Z 19.0N 53.0W...INLAND\nMAX WIND 20 KT...GUSTS 30 KT.\n"
            ),
        ),
    ]


@pytest.fixture
def dataset(sources):
    return compile_sources(sources, {"kind": "synthetic_software_fixture"})


class Tokenizer:
    eos_token_id = 257

    def apply_chat_template(self, messages, **kwargs):
        from disastertrace.forecast_task.common import canonical

        return canonical(messages) + "<think>"

    def encode(self, text, **kwargs):
        markers = {"</think>": 256, "<|im_end|>": 257, "<|endoftext|>": 258}
        if text in markers:
            return [markers[text]]
        return [ord(c) + 1024 for c in text]

    def decode(self, tokens, **kwargs):
        return "".join(
            {256: "</think>", 257: "<|im_end|>", 258: "<|endoftext|>"}.get(
                t, chr(t - 1024) if t >= 1024 else "?"
            )
            for t in tokens
        )


@pytest.fixture(params=["qwen3", "deepseek_r1"])
def bundle(tmp_path, monkeypatch, dataset, request):
    from disastertrace.compact_live import package, profiles
    from disastertrace.compact_live.backend import ProgramBackend
    from disastertrace.compact_live.storage import write

    root, run = tmp_path / "execution", tmp_path / "run"
    public = dataset["public"]
    slots = package.assign(public, schedule(public), "unit-phase")
    plan = {
        "model_profile": request.param,
        "settings": profiles.ADAPTERS[request.param].SETTINGS,
        "execution_id": "unit-execution",
        "phase_id": "unit-phase",
        "kind": "diagnostic",
        "generation_authorized": False,
        "deadline_utc": None,
        "run_root": None,
    }
    private = dataset["private_reference"]
    write(root / "task/data/private_reference.json", private)
    write(root / "resources/tokenizer/config.json", {"vocab_size": 200000})
    monkeypatch.setattr(package, "verify", lambda *args, **kwargs: (plan, public, slots))
    tokenizer = Tokenizer()
    return root, run, plan, public, slots, tokenizer, ProgramBackend(tokenizer)


@pytest.fixture(params=["qwen3", "deepseek_r1"])
def model_adapter(request):
    from disastertrace.compact_live.profiles import ADAPTERS

    return request.param, ADAPTERS[request.param]
