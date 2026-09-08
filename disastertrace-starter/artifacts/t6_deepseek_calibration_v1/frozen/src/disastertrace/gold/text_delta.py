from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

SECTION_HEADER = re.compile(r"^[A-Z][A-Z /-]{4,}:?\s*$")


@dataclass(frozen=True)
class SentenceDelta:
    section: str
    kind: str  # added | removed | changed
    previous: str | None
    current: str | None
    similarity: float


def split_sections(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {"PREAMBLE": []}
    current = "PREAMBLE"
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if SECTION_HEADER.match(line):
            current = line.rstrip(":")
            sections.setdefault(current, [])
        else:
            sections[current].append(raw_line)
    return {name: "\n".join(lines).strip() for name, lines in sections.items()}


def _sentences(text: str) -> list[str]:
    return [x.strip() for x in re.split(r"(?<=[.!?])\s+|\n+", text) if x.strip()]


def build_text_delta(previous: str, current: str, threshold: float = 0.72) -> list[SentenceDelta]:
    prev_sections, curr_sections = split_sections(previous), split_sections(current)
    deltas: list[SentenceDelta] = []
    for section in sorted(set(prev_sections) | set(curr_sections)):
        old = _sentences(prev_sections.get(section, ""))
        new = _sentences(curr_sections.get(section, ""))
        used_new: set[int] = set()
        for old_sentence in old:
            candidates = [
                (SequenceMatcher(None, old_sentence, new_sentence).ratio(), index, new_sentence)
                for index, new_sentence in enumerate(new)
                if index not in used_new
            ]
            best = max(candidates, default=(0.0, -1, None), key=lambda item: item[0])
            similarity, index, new_sentence = best
            if similarity >= threshold:
                used_new.add(index)
                if old_sentence != new_sentence:
                    deltas.append(
                        SentenceDelta(section, "changed", old_sentence, new_sentence, similarity)
                    )
            else:
                deltas.append(SentenceDelta(section, "removed", old_sentence, None, 0.0))
        for index, new_sentence in enumerate(new):
            if index not in used_new:
                deltas.append(SentenceDelta(section, "added", None, new_sentence, 0.0))
    return deltas
