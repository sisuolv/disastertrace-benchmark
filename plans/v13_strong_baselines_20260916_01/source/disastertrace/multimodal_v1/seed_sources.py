"""Acquire only the predeclared Francine development seed."""

from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

from .acquire import Fetcher
from .storage import digest, publish_bytes, read, write


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.hrefs.extend(v for k, v in attrs if k == "href" and v)


def acquire_seed(project, output):
    project, output = Path(project), Path(output)
    old = project / "artifacts/nhc_forecast_source_v1"
    scope = read(old / "SOURCE_SCOPE.json")
    if "AL062024" in scope["protected_heldout_ids"]:
        raise ValueError("seed intersects heldout")
    selected = [
        x
        for x in scope["selected"]
        if x["storm_id"] == "AL062024" and x["advisory_number"] in (5, 7)
    ]
    if len(selected) != 2 or any(x["split"] != "development" for x in selected):
        raise ValueError("seed lacks development assignment")
    if (output / "sources.json").exists():
        raise FileExistsError("source inventory already built; inspect or reuse it")
    output.mkdir(parents=True, exist_ok=True)
    fetcher, records = Fetcher(output / "downloads"), []
    for kind, suffix in [("fst", "fcst"), ("5day", "5day")]:
        index_url = f"https://ftp.nhc.noaa.gov/atcf/gis/{kind}/"
        index, receipt = fetcher.fetch(index_url, "html")
        links = Links()
        links.feed(index.read_text(errors="strict"))
        discovered = {urljoin(index_url, href) for href in links.hrefs}
        records.append(
            {"role": "source_directory", "path": str(index.relative_to(output)), **receipt}
        )
        for advisory in (5, 7):
            url = index_url + f"al062024_{suffix}_{advisory:03d}.zip"
            if url not in discovered:
                raise ValueError("candidate absent from actual directory: " + url)
            path, receipt = fetcher.fetch(url, "zip")
            records.append(
                {
                    "role": "wind_radii" if kind == "fst" else "track_cone_context_only",
                    "advisory": advisory,
                    "storm_id": "AL062024",
                    "split": "development",
                    "path": str(path.relative_to(output)),
                    "directory_sha256": digest(index.read_bytes()),
                    **receipt,
                }
            )
    old_results = {x["source_id"]: x for x in read(old / "acquisition/results.json")}
    for item in selected:
        original = old_results[item["source_id"]]
        data = (old / "acquisition" / item["source_id"] / "body.html").read_bytes()
        if (
            original["status"] != "received"
            or original["split"] != "development"
            or digest(data) != original["raw_sha256"]
        ):
            raise ValueError("text source reuse identity differs")
        path = output / "reused" / (item["source_id"] + ".html")
        publish_bytes(path, data)
        records.append(
            {
                "role": "forecast_text",
                "advisory": item["advisory_number"],
                "path": str(path.relative_to(output)),
                "origin": "local_verified_reuse",
                **original,
            }
        )
    inventory = {
        "schema": "mm_sources_v1",
        "storm_id": "AL062024",
        "split": "development",
        "global_event_id": "AL062024",
        "source_scope_sha256": digest((old / "SOURCE_SCOPE.json").read_bytes()),
        "records": records,
        "new_body_bytes": sum(x.get("bytes_received", 0) for x in records),
        "full_text_may_reveal_geometry": True,
        "model_calls": 0,
    }
    publish_bytes(output / "scope.json", (old / "SOURCE_SCOPE.json").read_bytes())
    write(output / "sources.json", inventory)
    return inventory
