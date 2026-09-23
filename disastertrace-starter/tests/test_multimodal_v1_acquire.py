import io
import json
import stat
import zipfile

import pytest

from disastertrace.multimodal_v1.acquire import Fetcher, OfficialRedirect, check_url, zip_members


@pytest.mark.parametrize(
    "url",
    [
        "http://ftp.nhc.noaa.gov/x",
        "https://example.com/x",
        "file:///tmp/x",
        "https://user:password@ftp.nhc.noaa.gov/x",
        "https://ftp.nhc.noaa.gov:444/x",
    ],
)
def test_non_official_or_credentialed_urls_rejected(url):
    with pytest.raises(ValueError):
        check_url(url)


def test_redirect_host_checked_before_fetch():
    with pytest.raises(ValueError):
        OfficialRedirect().redirect_request(
            None, None, 302, "redirect", {}, "https://untrusted.invalid/data"
        )


def archive(name, body=b"valid", mode=None):
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as z:
        item = zipfile.ZipInfo(name)
        if mode:
            item.external_attr = mode << 16
        z.writestr(item, body, compress_type=zipfile.ZIP_DEFLATED)
    return out.getvalue()


@pytest.mark.parametrize("name", ["../escape", "/absolute", "a\\b", "C:/drive"])
def test_unsafe_zip_paths_rejected(name):
    with pytest.raises(ValueError):
        zip_members(archive(name))


def test_symlink_bomb_and_duplicate_members_rejected():
    for data in (archive("link", b"target", stat.S_IFLNK | 0o777), archive("bomb", b"0" * 1000000)):
        with pytest.raises(ValueError):
            zip_members(data)
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as z:
        z.writestr("same", b"a")
        with pytest.warns(UserWarning):
            z.writestr("same", b"b")
    with pytest.raises(ValueError):
        zip_members(output.getvalue())
    assert zip_members(archive("safe/file.txt")) == {"safe/file.txt": b"valid"}


class Response(io.BytesIO):
    def __init__(self, data, url, status=200):
        super().__init__(data)
        self.url, self.status, self.headers = url, status, {"Content-Type": "text/html"}


def test_failed_download_bytes_consume_budget_and_cap_attempts(tmp_path, monkeypatch):
    class Opener:
        def open(self, request, timeout):
            return Response(b"<failed>", request.full_url, 404)

    monkeypatch.setattr("urllib.request.build_opener", lambda *a: Opener())
    fetcher = Fetcher(tmp_path, total_limit=24, file_limit=16)
    for _ in range(3):
        with pytest.raises(ValueError):
            fetcher.fetch("https://ftp.nhc.noaa.gov/a", "html")
    receipts = [json.loads(p.read_text()) for p in tmp_path.glob("*/receipt.json")]
    assert len(receipts) == 3 and sum(r["bytes_received"] for r in receipts) == 24
    with pytest.raises(ValueError, match="attempt cap"):
        fetcher.fetch("https://ftp.nhc.noaa.gov/a", "html")
    with pytest.raises(ValueError, match="budget exhausted"):
        fetcher.fetch("https://ftp.nhc.noaa.gov/b", "html")


def test_cached_download_verified_and_never_refetched(tmp_path, monkeypatch):
    calls = []

    class Opener:
        def open(self, request, timeout):
            calls.append(request.full_url)
            return Response(b"<valid>", request.full_url)

    monkeypatch.setattr("urllib.request.build_opener", lambda *a: Opener())
    fetcher = Fetcher(tmp_path, total_limit=64, file_limit=32)
    first = fetcher.fetch("https://ftp.nhc.noaa.gov/a", "html")
    assert fetcher.fetch("https://ftp.nhc.noaa.gov/a", "html") == first and len(calls) == 1
    first[0].write_bytes(b"changed")
    with pytest.raises(ValueError, match="identity"):
        fetcher.fetch("https://ftp.nhc.noaa.gov/a", "html")


def test_partial_unknown_download_keeps_entire_reservation(tmp_path, monkeypatch):
    folder = tmp_path / "interrupted"
    folder.mkdir()
    (folder / "intent.json").write_text(
        json.dumps({"url": "https://ftp.nhc.noaa.gov/a", "reserved_bytes": 16})
    )
    fetcher = Fetcher(tmp_path, total_limit=16, file_limit=16)
    monkeypatch.setattr(
        "urllib.request.build_opener", lambda *a: pytest.fail("must not start network read")
    )
    with pytest.raises(ValueError, match="budget exhausted"):
        fetcher.fetch("https://ftp.nhc.noaa.gov/b", "html")


def test_html_error_body_is_not_admitted_as_a_zip(tmp_path, monkeypatch):
    class Opener:
        def open(self, request, timeout):
            return Response(b"<html>not a zip</html>", request.full_url)

    monkeypatch.setattr("urllib.request.build_opener", lambda *a: Opener())
    with pytest.raises(zipfile.BadZipFile):
        Fetcher(tmp_path).fetch("https://ftp.nhc.noaa.gov/wrong.zip", "zip")
    receipts = list(tmp_path.glob("*/receipt.json"))
    assert json.loads(receipts[0].read_text())["status"] == "failed"


def test_mid_read_timeout_charges_unobserved_reservation(tmp_path, monkeypatch):
    class FailingResponse(Response):
        def read(self, size):
            raise TimeoutError("partial socket transfer unknown")

    class Opener:
        def open(self, request, timeout):
            return FailingResponse(b"", request.full_url)

    monkeypatch.setattr("urllib.request.build_opener", lambda *a: Opener())
    fetcher = Fetcher(tmp_path, total_limit=32, file_limit=32)
    with pytest.raises(TimeoutError):
        fetcher.fetch("https://ftp.nhc.noaa.gov/a", "html")
    receipt = json.loads(next(tmp_path.glob("*/receipt.json")).read_text())
    assert receipt["bytes_received"] == 0 and receipt["budget_charged_bytes"] == 32
    with pytest.raises(ValueError, match="budget exhausted"):
        fetcher.fetch("https://ftp.nhc.noaa.gov/b", "html")
