"""Extract captured primary papers with stable section/page locators; offline only."""

import hashlib
import io
import json
import sys
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, "/mnt/afs/260010168/.venvs/disastertrace-feasibility-libs-20260910")


def main():
    for batch in sorted((ROOT / "batches").iterdir()):
        if not batch.is_dir():
            continue
        for result_path in sorted(batch.glob("*.json")):
            record = json.loads(result_path.read_text())
            result = record.get("final", {})
            if result.get("http_status") != 200 or not result.get("complete"):
                continue
            name = record["id"]
            body = (ROOT / result["attempt_path"] / "body.bin").read_bytes()
            if name.endswith("-html"):
                soup = BeautifulSoup(body, "html.parser")
                article = soup.select_one("article") or soup
                blocks = []
                for node in article.select("h1,h2,h3,h4,h5,p,table,figcaption"):
                    if node.find_parent("table") or node.find_parent("figcaption"):
                        continue
                    section = node.find_parent("section")
                    locator = node.get("id") or (section.get("id") if section else None)
                    blocks.append({"locator": locator, "tag": node.name,
                                   "text": node.get_text(" ", strip=True)})
                text = "\n\n".join(f'[{x["locator"] or "unlocated"}] {x["text"]}' for x in blocks)
            elif name.endswith("-pdf") and body.startswith(b"%PDF"):
                from pypdf import PdfReader

                reader = PdfReader(io.BytesIO(body))
                blocks = [{"page": i + 1, "text": page.extract_text()}
                          for i, page in enumerate(reader.pages)]
                text = "\n\n".join(f'[page {x["page"]}] {x["text"]}' for x in blocks)
            else:
                continue
            output = ROOT / "literature" / (name + ".txt")
            if output.exists():
                continue
            output.write_text(text + "\n")
            output.with_suffix(".json").write_text(json.dumps({
                "url": result["url"], "body_path": result["attempt_path"] + "/body.bin",
                "body_sha256": hashlib.sha256(body).hexdigest(), "blocks": blocks,
            }, ensure_ascii=False, indent=2) + "\n")
            print(name, len(blocks), len(text))


if __name__ == "__main__":
    main()
