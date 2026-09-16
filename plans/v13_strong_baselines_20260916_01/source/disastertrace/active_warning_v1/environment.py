"""An outcome-free replay clock with request-time snapshots and append-only commits."""

import hashlib
import json
from copy import deepcopy
from datetime import timedelta
from fractions import Fraction

from disastertrace.active_forecast.schema import parse_exact, parse_instant

from .schema import Episode


def wire(value):
    if isinstance(value, Fraction):
        return float(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: wire(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [wire(item) for item in value]
    return value


def fact(artifact):
    return {
        "artifact_id": artifact.id,
        "product_id": artifact.product_id,
        "provider": artifact.provider,
        "entity": artifact.entity,
        "variable": artifact.variable,
        "unit": artifact.unit,
        "kind": artifact.kind,
        "issued_at": None if artifact.issued_at is None else artifact.issued_at.isoformat(),
        "valid_at": artifact.valid_at.isoformat(),
        "values": [float(value) for value in artifact.values],
        "quality": artifact.quality,
    }


class Environment:
    def __init__(self, episode, budget, max_pending=2):
        self.episode = Episode.model_validate(episode)
        if type(budget) is not int or budget < 0 or type(max_pending) is not int or max_pending < 1:
            raise ValueError("invalid resource limits")
        self.budget, self.max_pending, self.spent = budget, max_pending, 0
        self.now = self.episode.start_at
        self.receipts, self.commits, self.events = [], [], []
        self.stopped = False
        self._selected = {}
        self.initial = next(
            a for a in self.episode.artifacts if a.id == self.episode.initial_artifact_id
        )
        self._event("start", budget=budget, availability_mode="controlled_replay")

    def _event(self, kind, **fields):
        event = {
            "index": len(self.events),
            "at": self.now.isoformat(),
            "kind": kind,
            "previous_sha256": self.events[-1]["sha256"] if self.events else None,
            **wire(fields),
        }
        body = json.dumps(event, sort_keys=True, allow_nan=False).encode()
        event["sha256"] = hashlib.sha256(body).hexdigest()
        self.events.append(event)

    def available(self, kind, at=None):
        at = self.now if at is None else parse_instant(at)
        return [a for a in self.episode.artifacts if a.kind == kind and a.release_at <= at]

    def query(self, tool_id):
        tool = next((t for t in self.episode.tools if t.id == tool_id), None)
        if tool is None or self.stopped or self.now > self.episode.deadline:
            raise ValueError("unknown tool, stopped acquisition, or expired deadline")
        if self.spent + tool.cost > self.budget:
            raise ValueError("query would exceed budget")
        if sum(r["status"] == "pending" for r in self.receipts) >= self.max_pending:
            raise ValueError("concurrency limit reached")
        kind = "observation" if tool.kind == "observation" else "forecast"
        candidates = self.available(kind)
        selected = None
        if candidates:
            candidates.sort(key=lambda a: (a.issued_at or a.valid_at, a.valid_at, a.id))
            selected = candidates[0] if tool.kind == "archive" else candidates[-1]
        payload = [] if selected is None else [selected]
        if selected is not None and kind == "forecast":
            if self.episode.scenario == "duplicate":
                payload.append(selected)
            elif self.episode.scenario == "stale":
                payload.append(self.initial)
        ident = f"q{len(self.receipts):04d}"
        self.spent += tool.cost
        receipt = {
            "id": ident,
            "tool_id": tool.id,
            "requested_at": self.now,
            "completed_at": self.now + timedelta(seconds=tool.latency_seconds),
            "delivered_at": None,
            "read_at": None,
            "status": "pending",
            "cost": tool.cost,
        }
        # The selected revision is frozen now, even if a newer one appears in flight.
        self._selected[ident] = tuple(payload)
        self.receipts.append(receipt)
        self._event("query", receipt_id=ident, tool_id=tool.id, cost=tool.cost)
        return ident

    def wait_until(self, at):
        at = parse_instant(at)
        if at < self.now or at > self.episode.deadline:
            raise ValueError("clock cannot move backward or beyond decision deadline")
        self.now = at
        for receipt in self.receipts:
            if receipt["status"] == "pending" and receipt["completed_at"] <= self.now:
                receipt["status"] = "completed"
                self._event(
                    "completed", receipt_id=receipt["id"], completed_at=receipt["completed_at"]
                )
        self._event("wait")

    def read(self, receipt_id):
        receipt = next((r for r in self.receipts if r["id"] == receipt_id), None)
        if receipt is None or receipt["status"] != "completed":
            raise ValueError("read requires one completed, unread request")
        payload = [fact(a) for a in self._selected[receipt_id]]
        receipt.update(
            status="read",
            delivered_at=self.now,
            read_at=self.now,
            payload=payload,
            bytes=len(json.dumps(payload, sort_keys=True).encode()),
        )
        self._event(
            "read",
            receipt_id=receipt_id,
            artifact_ids=[p["artifact_id"] for p in payload],
            bytes=receipt["bytes"],
            payload_sha256=hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest(),
        )
        return deepcopy(payload)

    def forecast(self, answer):
        if not isinstance(answer, dict) or set(answer) != {
            "target_id",
            "value",
            "probability",
            "citations",
        }:
            raise ValueError("forecast must use the exact output contract")
        if answer["target_id"] != self.episode.id or self.now > self.episode.deadline:
            raise ValueError("wrong target or late forecast")
        value = parse_exact(answer["value"])
        probability = None if answer["probability"] is None else parse_exact(answer["probability"])
        if value < 0 or (probability is not None and not 0 <= probability <= 1):
            raise ValueError("invalid forecast value or probability")
        if self.episode.threshold is None and probability is not None:
            raise ValueError("no binary probability for a target without a threshold")
        citations = answer["citations"]
        allowed = {"initial"} | {
            r["id"] for r in self.receipts if r["status"] == "read" and r["payload"]
        }
        if (
            not isinstance(citations, list)
            or not citations
            or any(type(c) is not str or c not in allowed for c in citations)
            or len(citations) != len(set(citations))
        ):
            raise ValueError("citations must identify actually read nonempty receipts")
        commit = {
            "at": self.now,
            "target_id": self.episode.id,
            "value": value,
            "probability": probability,
            "citations": list(citations),
        }
        self.commits.append(commit)
        self._event("forecast", **commit)

    def stop(self):
        self.stopped = True
        self._event("stop_acquisition")

    def invalid(self, reason, raw_sha256=None):
        self._event("invalid", reason=str(reason), raw_sha256=raw_sha256)

    def view(self, canonical=False):
        initial_facts = [fact(self.initial)]
        if self.episode.initial_observation_id is not None:
            initial_facts += [
                fact(a)
                for a in self.episode.artifacts
                if a.id == self.episode.initial_observation_id
            ]
        delivered = [{"receipt_id": "initial", "facts": initial_facts}]
        delivered += [
            {"receipt_id": r["id"], "facts": deepcopy(r["payload"])}
            for r in self.receipts
            if r["status"] == "read"
        ]
        if canonical:
            latest = {}
            for block in delivered:
                for item in block["facts"]:
                    key = (item["kind"], item["entity"], item["variable"], item["valid_at"])
                    issued = item["issued_at"] or item["valid_at"]
                    previous = latest.get(key, {}).get("fact", {})
                    previous_issued = previous.get("issued_at") or previous.get("valid_at", "")
                    if key not in latest or issued > previous_issued:
                        latest[key] = {"fact": item, "receipt_id": block["receipt_id"]}
            delivered = [
                {"receipt_id": row["receipt_id"], "facts": [row["fact"]]}
                for _, row in sorted(latest.items())
            ]
        return {
            "target": {
                "id": self.episode.id,
                "entity": self.episode.entity,
                "variable": self.episode.variable,
                "unit": self.episode.unit,
                "valid_at": self.episode.target_at.isoformat(),
                "threshold": wire(self.episode.threshold),
                "threshold_meaning": self.episode.threshold_meaning,
            },
            "now": self.now.isoformat(),
            "deadline": self.episode.deadline.isoformat(),
            "budget_remaining": self.budget - self.spent,
            "max_concurrent_requests": self.max_pending,
            "catalog": [tool.model_dump(mode="json") for tool in self.episode.tools],
            "pending": [
                {k: wire(r[k]) for k in ("id", "tool_id", "requested_at", "status")}
                for r in self.receipts
                if r["status"] == "pending"
            ],
            "read_evidence": delivered,
            "previous_forecasts": wire(self.commits),
            "availability_mode": "controlled_replay",
        }

    def export(self):
        return wire(
            {
                "episode_id": self.episode.id,
                "scenario": self.episode.scenario,
                "budget": self.budget,
                "spent": self.spent,
                "receipts": self.receipts,
                "commits": self.commits,
                "events": self.events,
            }
        )
