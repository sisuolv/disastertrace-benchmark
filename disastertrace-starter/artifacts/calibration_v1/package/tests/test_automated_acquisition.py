from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request

import pytest

from disastertrace.automated.acquisition import (
    FetchResponse,
    _OfficialRedirect,
    catalogue_records,
    extract_pre,
    fetch_cohort,
    validate_source_url,
)

CATALOGUE = Path(__file__).resolve().parents[1] / "configs/nhc_cohort_v1.json"
URL = "https://www.nhc.noaa.gov/archive/2021/al09/al092021.public.009.shtml"


@pytest.fixture
def catalogue(tmp_path):
    value = json.loads(CATALOGUE.read_text())
    value["events"] = value["events"][:1]
    value["planned_event_count"] = 1
    path = tmp_path / "input.json"
    path.write_text(json.dumps(value))
    return path


def test_declared_cohort_has_exact_preassigned_events_and_sources():
    value = json.loads(CATALOGUE.read_text())
    records = catalogue_records(value)
    assert len(records) == 36
    assert len({row["source_id"] for row in records}) == 36
    assert [event["storm_id"] for event in value["events"] if event["split"] == "development"] == [
        "AL092021",
        "AL092017",
        "AL062018",
        "AL052019",
    ]
    assert [event["storm_id"] for event in value["events"] if event["split"] == "heldout"] == [
        "AL142016",
        "AL112017",
        "AL152017",
        "AL142018",
        "AL132020",
        "AL092022",
        "AL102023",
        "AL022024",
    ]
    assert all(event["advisory_numbers"] == ["9", "10", "11"] for event in value["events"])


def test_freeze_is_written_before_any_request_and_exact_whitespace_is_retained(catalogue, tmp_path):
    output = tmp_path / "snapshot"
    raw_html = b"<html><PRE>\r\n  A &amp; B\n\tC&#13;\n</PRE></html>"
    expected_text = b"\r\n  A & B\n\tC\r\n"
    calls = []

    def transport(url, timeout, max_bytes):
        before = json.loads((output / "MANIFEST.json").read_text())
        assert before["status"] == "in_progress"
        assert before["counts"]["pending_records"] == 3
        assert (output / before["catalogue_path"]).read_bytes() == catalogue.read_bytes()
        assert before["catalogue_sha256"] == hashlib.sha256(catalogue.read_bytes()).hexdigest()
        assert before["catalogue"] == json.loads(catalogue.read_text())
        assert timeout == 20 and max_bytes == 2 * 1024 * 1024
        calls.append(url)
        return FetchResponse(raw_html, url)

    manifest = fetch_cohort(catalogue, output, transport=transport)
    assert len(calls) == 3
    assert manifest["counts"] == {
        "planned_events": 1,
        "planned_records": 3,
        "successful_records": 3,
        "failed_records": 0,
        "pending_records": 0,
    }
    for row in manifest["files"]:
        assert (output / row["html_path"]).read_bytes() == raw_html
        assert (output / row["text_path"]).read_bytes() == expected_text
        assert row["text_sha256"] == hashlib.sha256(expected_text).hexdigest()
        assert row["source_origin"] == "official_record"
        assert row["historical_availability_proven"] is False
    assert json.loads((output / "MANIFEST.json").read_text()) == manifest
    for attempt in manifest["attempts"]:
        assert json.loads((output / attempt["attempt_path"]).read_text()) == attempt


def test_failed_sources_stay_in_denominator_and_retry_attempts_are_persisted(catalogue, tmp_path):
    counts = {}

    def transport(url, timeout, max_bytes):
        counts[url] = counts.get(url, 0) + 1
        if ".009." in url and counts[url] == 1:
            raise URLError("temporary failure")
        if ".010." in url:
            raise HTTPError(url, 404, "Not Found", {}, None)
        return FetchResponse(b"<pre>advisory</pre>", url)

    output = tmp_path / "snapshot"
    manifest = fetch_cohort(catalogue, output, transport=transport, workers=1)
    assert manifest["counts"]["successful_records"] == 2
    assert manifest["counts"]["failed_records"] == 1
    assert len(manifest["records"]) == 3
    assert len(manifest["attempts"]) == 5
    assert [row["status"] for row in manifest["records"]] == ["succeeded", "failed", "succeeded"]
    failed = manifest["records"][1]
    assert len(failed["attempts"]) == 2
    assert failed["failure"]["error_type"] == "HTTPError"
    assert all(count <= 2 for count in counts.values())
    assert all(
        attempt["http_status"] == 404
        for attempt in manifest["attempts"]
        if attempt["source_id"] == failed["source_id"]
    )


def test_rejected_extraction_retains_original_html(catalogue, tmp_path):
    raw_html = b"<pre>first</pre><pre>second</pre>"
    output = tmp_path / "snapshot"
    manifest = fetch_cohort(
        catalogue,
        output,
        transport=lambda url, *_: FetchResponse(raw_html, url),
        max_attempts=1,
    )
    assert manifest["files"] == []
    assert manifest["counts"]["failed_records"] == 3
    for attempt in manifest["attempts"]:
        assert attempt["error_type"] == "ValueError"
        assert (output / attempt["html_path"]).read_bytes() == raw_html
        assert attempt["html_sha256"] == hashlib.sha256(raw_html).hexdigest()


def test_existing_snapshot_cannot_be_overwritten(catalogue, tmp_path):
    output = tmp_path / "snapshot"
    output.mkdir()
    marker = output / "keep.txt"
    marker.write_bytes(b"preserved")
    with pytest.raises(FileExistsError):
        fetch_cohort(catalogue, output, transport=lambda *_: pytest.fail("must not request"))
    assert marker.read_bytes() == b"preserved"


def test_interruption_leaves_catalogue_and_started_attempt(catalogue, tmp_path):
    output = tmp_path / "snapshot"

    def interrupted(*_):
        raise RuntimeError("simulated process failure")

    with pytest.raises(RuntimeError):
        fetch_cohort(catalogue, output, transport=interrupted, workers=1)
    manifest = json.loads((output / "MANIFEST.json").read_text())
    assert manifest["status"] == "in_progress"
    assert (output / manifest["catalogue_path"]).read_bytes() == catalogue.read_bytes()
    attempts = list((output / "attempts").rglob("*.json"))
    assert attempts and all(
        json.loads(path.read_text())["status"] == "started" for path in attempts
    )


@pytest.mark.parametrize(
    "html",
    [
        b"<html>none</html>",
        b"<pre>x",
        b"<pre></pre>",
        b"<pre>  \n</pre>",
        b"<pre>x</pre><pre>y</pre>",
        b"<pre>x<pre>y</pre></pre>",
        b"</pre><pre>x</pre>",
        b"<pre>\xff</pre>",
    ],
)
def test_ambiguous_or_invalid_pre_is_rejected(html):
    with pytest.raises(ValueError):
        extract_pre(html)


@pytest.mark.parametrize(
    "url",
    [
        URL.replace("https:", "http:"),
        URL.replace("www.nhc.noaa.gov", "evil.example"),
        URL.replace("www.nhc.noaa.gov", "www.nhc.noaa.gov.evil.example"),
        URL.replace("www.nhc.noaa.gov", "user@www.nhc.noaa.gov"),
        URL.replace("www.nhc.noaa.gov", "www.nhc.noaa.gov:443"),
        URL.replace("/2021/", "/2022/"),
        URL + "?redirect=1",
        URL + "#anchor",
        URL.replace("al09/", "al10/"),
    ],
)
def test_nonofficial_or_inconsistent_urls_are_rejected(url):
    with pytest.raises(ValueError):
        validate_source_url(url)


def test_redirect_guard_checks_identity_before_following():
    handler = _OfficialRedirect()
    request = Request(URL)
    for newurl in [
        URL.replace("009", "010"),
        "https://example.com/steal",
        URL.replace("https:", "http:"),
    ]:
        with pytest.raises(ValueError):
            handler.redirect_request(request, None, 302, "redirect", {}, newurl)
    redirected = handler.redirect_request(
        request, None, 302, "redirect", {}, URL.replace("www.nhc.noaa.gov", "nhc.noaa.gov")
    )
    assert redirected.full_url == URL.replace("www.nhc.noaa.gov", "nhc.noaa.gov")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"workers": 0},
        {"workers": 5},
        {"workers": True},
        {"max_attempts": 0},
        {"max_attempts": 4},
        {"max_attempts": True},
        {"timeout": 0},
        {"timeout": 61},
        {"timeout": float("nan")},
        {"timeout": float("inf")},
        {"timeout": True},
    ],
)
def test_resource_bounds_rejected_before_requests(catalogue, tmp_path, kwargs):
    with pytest.raises(ValueError):
        fetch_cohort(
            catalogue,
            tmp_path / "out",
            transport=lambda *_: pytest.fail("must not request"),
            **kwargs,
        )
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize(
    "mutation",
    [
        "duplicate_event",
        "wrong_count",
        "wrong_split",
        "wrong_source",
        "bad_numbers",
        "empty",
    ],
)
def test_invalid_catalogue_is_rejected_before_requests(catalogue, tmp_path, mutation):
    value = json.loads(catalogue.read_text())
    if mutation == "duplicate_event":
        value["events"].append(copy.deepcopy(value["events"][0]))
        value["events"][1]["split"] = "heldout"
        value["planned_event_count"] = 2
    elif mutation == "wrong_count":
        value["planned_event_count"] = True
    elif mutation == "wrong_split":
        value["events"][0]["split"] = "arbitrary"
    elif mutation == "wrong_source":
        value["events"][0]["source_ids"][0] = "unexpected"
    elif mutation == "bad_numbers":
        value["events"][0]["advisory_numbers"] = ["9", "9", "11"]
    else:
        value["events"] = []
        value["planned_event_count"] = 0
    catalogue.write_text(json.dumps(value))
    with pytest.raises(ValueError):
        fetch_cohort(
            catalogue, tmp_path / "out", transport=lambda *_: pytest.fail("must not request")
        )
    assert not (tmp_path / "out").exists()


def test_injected_transport_final_url_is_also_checked(catalogue, tmp_path):
    manifest = fetch_cohort(
        catalogue,
        tmp_path / "out",
        transport=lambda *_: FetchResponse(b"<pre>advisory</pre>", "https://evil.example/"),
        max_attempts=1,
    )
    assert manifest["counts"]["failed_records"] == 3
    assert all(attempt["error_type"] == "ValueError" for attempt in manifest["attempts"])
