"""Lossless source-line provenance for the measured PRE block."""

import hashlib
import html
import re


def normalize(raw):
    if not isinstance(raw, bytes):
        raise TypeError("raw archive bytes required")
    matches = list(re.finditer(rb"<pre\b[^>]*>(.*?)</pre\s*>", raw, re.IGNORECASE | re.DOTALL))
    if len(matches) != 1:
        raise ValueError("exactly one NHC PRE block required")
    block = matches[0]
    source, lines, mappings, offset = block.group(1), [], [], block.start(1)
    for number, part in enumerate(source.splitlines(keepends=True), 1):
        value = html.unescape(part.decode("utf-8").rstrip("\r\n")).replace("\xa0", " ")
        if "\n" in value or "\r" in value or re.search(r"<[/a-zA-Z]", value):
            raise ValueError("ambiguous markup or entity line break in PRE block")
        lines.append(value)
        mappings.append(
            {
                "canonical_line": number,
                "raw_byte_start": offset,
                "raw_byte_end": offset + len(part),
                "raw_line_sha256": hashlib.sha256(part).hexdigest(),
            }
        )
        offset += len(part)
    return {
        "text": "\n".join(lines) + "\n",
        "line_map": mappings,
        "normalization": "single_pre_utf8_html_entities_crlf_to_lf_v1",
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
    }
