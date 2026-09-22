"""Public input rendering: no scoring references or future suffix are exposed."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .provider import canonical, digest
from .qualification import iso, parse_frame, read_body, readset_rows, reference_state

SYSTEM_PROMPT = """You maintain a risk forecast for one fixed airport and future target hour.
The event is visibility below 5000 metres in the routine station report selected for
that target hour. It is not a claim about every instant of the hour. Professional
TAFs are evidence, not future observational truth. No future observation is provided.

At each cutoff, use only the provided public evidence. Maintain the current TAF
source applicable to the complete target hour: use the latest native TAF issue
whose validity covers the target. A routine new TAF can replace an older TAF;
an AMD/COR indicator alone is not evidence of applicability. Arrival order alone
does not establish authority. Repeated copies of the same source ID are one source.
If different same-issue products cannot be resolved, report UNRESOLVED rather than
inventing authority. Historical products may inform your risk reasoning even when
they are no longer the current product. Update source facts independently of the
probability: new facts do not force a probability change.

Return ONE JSON object, no Markdown and no extra commentary, using the supplied
commit contract. The object itself must have exactly the contract root keys; never
wrap it in a `commit_contract_example` or any other outer key. Cite only provided
source IDs. The carrier, if present, is YOUR
previous submitted state and can be wrong; verify it against current evidence.
The public last probability is a prior submitted value, not an official forecast.
SET_PROBABILITY requires one forecast update; KEEP_PROBABILITY requires none.
Use operation UPDATE when writing a fact or probability. HOLD requires both update
arrays to be empty. An invalid submission keeps the last valid state and is logged.
Do not reveal private reasoning. Report a concise machine-readable commit only."""


class NativeReader:
    def __init__(self, readset_path):
        self.rows = {row["canonical_body_path"]: row for row in readset_rows(readset_path)}
        self.memory = {}

    def text(self, source):
        path = source["body_path"]
        if path not in self.rows:
            raise PermissionError("source outside body readset")
        if path not in self.memory:
            self.memory[path] = read_body(self.rows[path])
        data = self.memory[path]
        start, end = source["byte_start"], source["byte_end"]
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(data):
            raise ValueError("invalid source byte range")
        raw = data[start:end]
        if hashlib.sha256(raw).hexdigest() != source["frame_sha256"]:
            raise ValueError("frame identity changed")
        check = parse_frame(data, self.rows[path], start, end)
        if check["source_id"] != source["source_id"]:
            raise ValueError("source identity does not match native bytes")
        return raw.decode("utf-8").strip("\x01\x03 \r\n")


def public_view(episode, index, reader):
    cutoff = episode["checkpoints_us"][index]
    sources = [source for source in episode["sources"] if source["available_at_us"] <= cutoff]
    public = []
    for source in sources:
        public.append({"source_id": source["source_id"], "station": source["station"],
                       "native_issue_time": iso(source["issued_at_us"]),
                       "available_at": iso(source["available_at_us"]),
                       "availability_basis": "declared_issue_plus_120_seconds",
                       "raw_product": reader.text(source)})
    return {
        "episode_id": episode["episode_id"], "target_id": episode["target_id"],
        "station": episode["station"], "target_start": iso(episode["target_start_us"]),
        "target_end": iso(episode["target_end_us"]), "threshold_metres": episode["threshold_m"],
        "as_of": iso(cutoff), "history_start": iso(episode["prefix_start_us"]), "evidence": public,
    }


def initial_state():
    return {"fact_state": None, "probability": 0.5, "probability_origin": "TECHNICAL_FALLBACK",
            "parent_commit_id": None}


def schema_example(view, before):
    return {
        "schema_version": "disastertrace.belief_commit.v14-draft",
        "episode_id": view["episode_id"], "target_id": view["target_id"],
        "parent_commit_id": before["parent_commit_id"], "as_of": view["as_of"],
        "operation": "UPDATE", "forecast_op": "SET_PROBABILITY",
        "evidence_ids": ["<provided source ID>"],
        "fact_updates": [{
            "slot": "target_source_state", "operation": "SET", "support_status": "supported",
            "value": {"active_source_ids": ["<provided source ID>"],
                      "valid_start": "<UTC ISO timestamp>", "valid_end": "<UTC ISO timestamp>",
                      "relation_status": "RESOLVED"},
            "source_ids": ["<provided source ID>"],
        }],
        "forecast_updates": [{"target_id": view["target_id"], "event_probability": "<number between 0 and 1>"}],
        "next_action": {"kind": "WAIT", "until_or_args": None},
    }


def messages_for(view, arm, before, variant="O"):
    if arm not in ("FRESH", "STATEFUL"):
        raise ValueError("unsupported method")
    main = {"task_and_evidence": view, "public_last_probability": before["probability"],
            "public_probability_origin": before["probability_origin"],
            "previous_valid_commit_id": before["parent_commit_id"],
            "commit_contract_example": schema_example(view, before),
            "contract_notes": "Replace placeholders; use actual probability. The fact value has exactly four fields. "
                              "RESOLVED requires one current source covering the target and its full native validity; "
                              "UNRESOLVED/NO_APPLICABLE_EVIDENCE use no current IDs and null validity bounds."}
    if arm == "STATEFUL":
        main["previous_self_written_fact_state"] = before["fact_state"]
    duplicate_length = 0
    if variant in ("D", "S"):
        original = view["evidence"][-1]
        duplicate = canonical({"source_id": original["source_id"], "raw_product": original["raw_product"]})
        duplicate_length = len(duplicate)
        if variant == "D":
            main["presentation_padding"] = duplicate
        else:
            main["presentation_padding"] = ("padding " * ((len(duplicate) + 7) // 8))[:len(duplicate)]
        main["padding_instruction"] = "Presentation padding is not a new source or a new issuance. "
        main["padding_instruction"] += "Repeated source IDs remain the same source."
    elif variant not in ("O", "R"):
        raise ValueError("unsupported presentation variant")
    messages = [{"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": canonical(main)}]
    return messages, {"external_view_sha256": digest(view), "messages_sha256": digest(messages),
                      "source_ids": [source["source_id"] for source in view["evidence"]],
                      "input_characters": sum(len(m["content"]) for m in messages),
                      "padding_characters": duplicate_length,
                      "sham_matching": "character-count, not tokenizer-exact" if variant == "S" else None}


def deterministic_baseline(view):
    products = []
    for public in view["evidence"]:
        raw = public["raw_product"].encode()
        row = {"station": public["station"], "year_month": public["native_issue_time"][:7],
               "canonical_body_path": "PUBLIC_INPUT_ONLY", "raw_text_sha256": hashlib.sha256(raw).hexdigest()}
        parsed = parse_frame(raw, row)
        if parsed["source_id"] != public["source_id"]:
            raise ValueError("public baseline source identity mismatch")
        products.append(parsed)
    from datetime import datetime
    us = lambda value: int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()) * 1_000_000
    return reference_state(products, us(view["as_of"]), us(view["target_start"]), us(view["target_end"]))
