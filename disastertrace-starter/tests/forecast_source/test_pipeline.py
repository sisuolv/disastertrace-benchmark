"""Scope, source bytes, automatic quarantine and reversible review exports."""

from datetime import datetime, timedelta, timezone

import pytest
from test_parsers import advisory

from disastertrace.automated.common import canonical, fingerprint
from disastertrace.forecast_source import pipeline, views
from disastertrace.local_eval.storage import read


@pytest.fixture
def bundle(tmp_path):
    result = tmp_path / "bundle"
    pipeline.prepare(result)
    return result


@pytest.mark.parametrize("mutation", ["url", "path", "protected", "retry", "bytes"])
def test_rehashed_scope_cannot_expand_acquisition(bundle, mutation):
    path = bundle / "SOURCE_SCOPE.json"
    scope = read(path)
    if mutation == "url":
        scope["selected"][0]["url"] = (
            "https://www.nhc.noaa.gov/archive/2022/al09/al092022.fstadv.005.shtml"
        )
    elif mutation == "path":
        scope["selected"][0]["source_id"] = "../outside"
    elif mutation == "protected":
        scope["protected_heldout_ids"] = []
    elif mutation == "retry":
        scope["automatic_retries"] = 1
    else:
        scope["maximum_bytes_per_body"] *= 2
    scope["scope_id"] = fingerprint({k: v for k, v in scope.items() if k != "scope_id"})
    path.write_text(canonical(scope) + "\n")
    with pytest.raises(ValueError):
        pipeline.verify_scope(bundle)


class Response:
    def __init__(self, url, body, status):
        self.url, self.body, self.status = url, body, status
        self.headers = {"Content-Type": "text/html"}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, limit):
        return self.body[:limit]

    def geturl(self):
        return self.url


def test_full_pipeline_retains_http_failure_and_never_refetches(bundle, tmp_path, monkeypatch):
    calls = []

    def fetch(request, timeout):
        url = request.full_url
        calls.append(url)
        stem, _, number, _ = url.rsplit("/", 1)[1].split(".")
        number, storm = int(number), stem.upper()
        minimum = 5 if storm == "AL062024" else 9
        issue = datetime(int(storm[-4:]), 8, 28, tzinfo=timezone.utc) + timedelta(
            hours=6 * (number - minimum)
        )
        body = advisory(
            issue=issue.strftime("%H%M UTC %a %b %d %Y").upper(),
            center=issue.strftime("%d/%H%MZ"),
            valid="30/0600Z",
            number=number,
            wind=str(60 + number),
            gust="100",
        ).replace(b"AL062024", storm.encode())
        return Response(url, body, 404 if len(calls) == 2 else 200)

    monkeypatch.setattr(pipeline.urllib.request, "urlopen", fetch)
    pipeline.acquire(bundle)
    assert len(calls) == 12
    with pytest.raises(FileExistsError):
        pipeline.acquire(bundle)
    assert len(calls) == 12
    result = pipeline.reconstruct(bundle)
    assert result["report"]["received_bodies"] == 11
    assert result["report"]["admitted_bodies"] == 11
    assert result["report"]["quarantined_bodies"] == 1
    assert result["report"]["same_valid_revision_pairs"] == 9
    for value in result["views"].values():
        original = "\n".join(line["text"] for line in value["raw"]["source_lines"]) + "\n"
        assert views.restore(value["normalized"]) == original
    report = tmp_path / "report"
    pipeline.review(bundle, report)
    pipeline.review(bundle, report, verify=True)
    source_id = read(bundle / "SOURCE_SCOPE.json")["selected"][0]["source_id"]
    with (bundle / "acquisition" / source_id / "body.html").open("ab") as stream:
        stream.write(b"tampered")
    with pytest.raises(ValueError):
        pipeline.reconstruct(bundle)


def test_lossless_line_map_covers_raw_source_entities():
    from disastertrace.forecast_source import consensus, normalization

    raw = advisory().replace(b"MAX WIND 65", b"MAX WIND 6&#53;").replace(b"\n", b"\r\n")
    result = normalization.normalize(raw)
    product = consensus.agree(raw)
    assert product["forecasts"][0]["max_sustained_wind_kt"] == 65
    for mapping in result["line_map"]:
        part = raw[mapping["raw_byte_start"] : mapping["raw_byte_end"]]
        import hashlib

        assert hashlib.sha256(part).hexdigest() == mapping["raw_line_sha256"]
    exports = views.export(product, result["text"])
    assert views.restore(exports["normalized"]) == result["text"]
    exports["normalized"]["other_source_lines"].pop(0)
    with pytest.raises(ValueError):
        views.restore(exports["normalized"])
