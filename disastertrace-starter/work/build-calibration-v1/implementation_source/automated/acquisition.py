"""Acquire a predeclared NHC cohort while retaining every attempted source.

Acquisition does not determine scientific validity or parser admission. The exact
catalogue and group assignments are persisted before the first network request.
"""

from __future__ import annotations

import hashlib
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .common import strict_json, write_json

ACQUISITION_VERSION = "nhc_predeclared_acquisition_v1"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
EXTRACTION = (
    "Python html.parser.HTMLParser(convert_charrefs=True), concatenate data inside "
    "the sole pre element; UTF-8 encode without whitespace normalization. "
    "Original HTML retained. Retrieval time does not establish historical publication time."
)
_HOSTS = {"www.nhc.noaa.gov", "nhc.noaa.gov"}
_ARCHIVE = re.compile(r"/archive/(\d{4})/(al\d{2})/(al\d{2}\d{4})\.public\.(\d{3})\.shtml")


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def validate_source_url(url: str, expected_url: str | None = None) -> str:
    """Require HTTPS, official host and an unchanged archive record identity."""
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or parsed.netloc not in _HOSTS
        or parsed.params
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("URL must identify an HTTPS NHC archive record on an official host")
    match = _ARCHIVE.fullmatch(parsed.path)
    if not match or match[3] != match[2] + match[1]:
        raise ValueError("URL archive identity is inconsistent")
    if expected_url is not None:
        validate_source_url(expected_url)
        if parsed.path != urlparse(expected_url).path:
            raise ValueError("Redirect changed the selected archive record identity")
    return url


class _OfficialRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_source_url(newurl, req.full_url)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


@dataclass(frozen=True)
class FetchResponse:
    body: bytes
    resolved_url: str
    status: int = 200


def _http_fetch(url: str, timeout: float, max_bytes: int) -> FetchResponse:
    validate_source_url(url)
    request = Request(url, headers={"User-Agent": "DisasterTrace-source-acquisition/1.0"})
    with build_opener(_OfficialRedirect()).open(request, timeout=timeout) as response:
        resolved_url = validate_source_url(response.geturl(), url)
        body = response.read(max_bytes + 1)
        if len(body) > max_bytes:
            raise ValueError("NHC response exceeds the declared byte limit")
        return FetchResponse(body, resolved_url, response.status)


class _SolePre(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.count = 0
        self.depth = 0
        self.parts: list[str] = []
        self.malformed = False

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() == "pre":
            self.count += 1
            self.depth += 1
            if self.depth != 1:
                self.malformed = True

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "pre":
            if self.depth != 1:
                self.malformed = True
            self.depth -= 1

    def handle_data(self, data: str) -> None:
        if self.depth > 0:
            self.parts.append(data)


def extract_pre(raw_html: bytes) -> bytes:
    """Extract one complete PRE element, preserving its decoded text whitespace."""
    parser = _SolePre()
    parser.feed(raw_html.decode("utf-8"))
    parser.close()
    if parser.count != 1 or parser.depth != 0 or parser.malformed:
        raise ValueError("Expected exactly one complete, non-nested PRE element")
    text = "".join(parser.parts)
    if not text.strip():
        raise ValueError("NHC PRE element is empty")
    return text.encode("utf-8")


def catalogue_records(catalogue: dict) -> list[dict]:
    """Validate group membership and expand the declared list without replacement."""
    if (
        not isinstance(catalogue, dict)
        or catalogue.get("schema_version") != "nhc_cohort_catalogue_v1"
    ):
        raise ValueError("Unsupported NHC cohort catalogue")
    events = catalogue.get("events")
    if not isinstance(events, list) or not events:
        raise ValueError("Catalogue must declare at least one event")
    if type(catalogue.get("planned_event_count")) is not int or catalogue[
        "planned_event_count"
    ] != len(events):
        raise ValueError("Catalogue planned_event_count disagrees with events")
    per_event = catalogue.get("advisories_per_event")
    if type(per_event) is not int or not 1 <= per_event <= 100:
        raise ValueError("Catalogue advisories_per_event must be an integer in 1..100")
    seen: set[str] = set()
    records = []
    for event in events:
        if not isinstance(event, dict):
            raise ValueError("Catalogue event must be an object")
        storm = event.get("storm_id")
        if not isinstance(storm, str) or not re.fullmatch(r"AL\d{2}\d{4}", storm):
            raise ValueError("Catalogue storm_id must use uppercase Atlantic identity")
        if storm in seen:
            raise ValueError("A storm may occur in only one catalogue event and split")
        seen.add(storm)
        if not isinstance(event.get("storm_name"), str) or not event["storm_name"]:
            raise ValueError("Catalogue storm_name must be nonempty")
        if event.get("split") not in {"development", "heldout"}:
            raise ValueError("Catalogue split must be development or heldout")
        numbers = event.get("advisory_numbers")
        if (
            not isinstance(numbers, list)
            or len(numbers) != per_event
            or any(not isinstance(n, str) or not re.fullmatch(r"[1-9]\d{0,2}", n) for n in numbers)
            or len(set(numbers)) != len(numbers)
        ):
            raise ValueError(
                "Catalogue advisory_numbers must be distinct positive canonical strings"
            )
        expected_ids = [f"nhc-{storm.lower()}-public-{int(n):03d}" for n in numbers]
        if event.get("source_ids") != expected_ids:
            raise ValueError("Catalogue source_ids disagree with selected storm and advisories")
        for number, source_id in zip(numbers, expected_ids):
            basename = f"{storm.lower()}.public.{int(number):03d}"
            source_url = (
                f"https://www.nhc.noaa.gov/archive/{storm[4:]}/{storm[:4].lower()}/{basename}.shtml"
            )
            validate_source_url(source_url)
            records.append(
                {
                    "source_id": source_id,
                    "source_url": source_url,
                    "storm_id": storm,
                    "storm_name": event["storm_name"],
                    "split": event["split"],
                    "advisory_number": number,
                    "status": "pending",
                    "attempts": [],
                }
            )
    return records


def fetch_cohort(
    catalogue_path: Path,
    output: Path,
    *,
    transport: Callable[[str, float, int], FetchResponse] | None = None,
    workers: int = 4,
    timeout: float = 20,
    max_attempts: int = 2,
) -> dict:
    """Download to a new snapshot; failures remain in the frozen planned cohort.

    The transport hook supports offline tests. Production HTTP redirects are
    checked before following them, and every returned final URL is checked again.
    Per-attempt files survive an interrupted acquisition; this function never
    resumes or overwrites an existing directory.
    """
    if type(workers) is not int or not 1 <= workers <= 4:
        raise ValueError("workers must be an integer in 1..4")
    if type(max_attempts) is not int or not 1 <= max_attempts <= 3:
        raise ValueError("max_attempts must be an integer in 1..3")
    if type(timeout) not in {int, float} or not 0 < timeout <= 60:
        raise ValueError("timeout must be greater than zero and at most 60 seconds")
    raw_catalogue = Path(catalogue_path).read_bytes()
    catalogue = strict_json(raw_catalogue.decode("utf-8"))
    planned = catalogue_records(catalogue)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    (output / "catalogue.json").write_bytes(raw_catalogue)
    manifest = {
        "schema_version": "nhc_cohort_snapshot_v1",
        "acquisition_version": ACQUISITION_VERSION,
        "status": "in_progress",
        "started_at": _utcnow(),
        "catalogue_path": "catalogue.json",
        "catalogue_sha256": _hash(raw_catalogue),
        "catalogue": catalogue,
        "extraction": EXTRACTION,
        "limits": {
            "workers": workers,
            "timeout_seconds": timeout,
            "max_attempts_per_source": max_attempts,
            "max_response_bytes": MAX_RESPONSE_BYTES,
        },
        "records": planned,
        "files": [],
        "attempts": [],
        "counts": {
            "planned_events": len(catalogue["events"]),
            "planned_records": len(planned),
            "successful_records": 0,
            "failed_records": 0,
            "pending_records": len(planned),
        },
    }
    write_json(output / "MANIFEST.json", manifest)
    fetch = transport or _http_fetch

    def acquire(item: dict) -> tuple[dict, dict | None, list[dict]]:
        item = dict(item)
        attempts = []
        successful = None
        for index in range(1, max_attempts + 1):
            attempt = {
                "source_id": item["source_id"],
                "source_url": item["source_url"],
                "attempt": index,
                "started_at": _utcnow(),
                "status": "started",
            }
            attempt_path = Path("attempts") / item["source_id"] / f"{index:02d}.json"
            attempt["attempt_path"] = str(attempt_path)
            write_json(output / attempt_path, attempt)
            try:
                response = fetch(item["source_url"], float(timeout), MAX_RESPONSE_BYTES)
                validate_source_url(response.resolved_url, item["source_url"])
                attempt["resolved_url"] = response.resolved_url
                attempt["http_status"] = response.status
                if response.status != 200:
                    raise ValueError(f"Unexpected HTTP status {response.status}")
                if not isinstance(response.body, bytes) or len(response.body) > MAX_RESPONSE_BYTES:
                    raise ValueError("Transport returned invalid or oversized response bytes")
                html_path = Path("raw") / f"{item['source_id']}.attempt-{index:02d}.html"
                (output / html_path).parent.mkdir(parents=True, exist_ok=True)
                with (output / html_path).open("xb") as stream:
                    stream.write(response.body)
                attempt.update(html_path=str(html_path), html_sha256=_hash(response.body))
                text = extract_pre(response.body)
                text_path = Path("text") / f"{item['source_id']}.txt"
                (output / text_path).parent.mkdir(parents=True, exist_ok=True)
                with (output / text_path).open("xb") as stream:
                    stream.write(text)
                attempt.update(text_path=str(text_path), text_sha256=_hash(text))
                attempt.update(status="succeeded", finished_at=_utcnow())
                successful = {
                    **{
                        key: value
                        for key, value in item.items()
                        if key not in {"attempts", "status"}
                    },
                    "status": "succeeded",
                    "resolved_url": response.resolved_url,
                    "retrieved_at": attempt["finished_at"],
                    "html_path": str(html_path),
                    "html_sha256": _hash(response.body),
                    "text_path": str(text_path),
                    "text_sha256": _hash(text),
                    "size_bytes": len(text),
                    "html_size_bytes": len(response.body),
                    "source_origin": "official_record",
                    "historical_availability_proven": False,
                }
            except (HTTPError, URLError, OSError, ValueError) as exc:
                attempt.update(
                    status="failed",
                    finished_at=_utcnow(),
                    error_type=type(exc).__name__,
                    error_detail=str(exc).replace("\n", " ")[:500],
                )
                if isinstance(exc, HTTPError):
                    attempt["http_status"] = exc.code
            write_json(output / attempt_path, attempt)
            attempts.append(attempt)
            if successful is not None:
                break
        item["status"] = "succeeded" if successful is not None else "failed"
        item["attempts"] = [entry["attempt_path"] for entry in attempts]
        if successful is None:
            item["failure"] = {
                "error_type": attempts[-1]["error_type"],
                "error_detail": attempts[-1]["error_detail"],
            }
        return item, successful, attempts

    with ThreadPoolExecutor(max_workers=workers) as executor:
        results = list(executor.map(acquire, planned))
    manifest["records"] = [record for record, _, _ in results]
    manifest["files"] = [record for _, record, _ in results if record is not None]
    manifest["attempts"] = [attempt for _, _, attempts in results for attempt in attempts]
    successes = len(manifest["files"])
    manifest["counts"].update(
        successful_records=successes,
        failed_records=len(planned) - successes,
        pending_records=0,
    )
    manifest.update(status="complete", finished_at=_utcnow())
    write_json(output / "MANIFEST.json", manifest)
    return manifest
