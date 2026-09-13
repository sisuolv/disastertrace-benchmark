"""Componentwise hard limits and durable reservation/settlement semantics."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass

DIMENSIONS = ("requests", "bytes", "tokens", "compute_ms")


@dataclass(frozen=True)
class Cost:
    requests: int = 0
    bytes: int = 0
    tokens: int = 0
    compute_ms: int = 0

    def __post_init__(self):
        if any(type(value) is not int or value < 0 for value in asdict(self).values()):
            raise ValueError("Resource costs must be nonnegative integer quantities")

    def __add__(self, other: Cost) -> Cost:
        return Cost(**{key: getattr(self, key) + getattr(other, key) for key in DIMENSIONS})

    def __sub__(self, other: Cost) -> Cost:
        return Cost(**{key: getattr(self, key) - getattr(other, key) for key in DIMENSIONS})

    def within(self, limits: Mapping[str, int | None]) -> bool:
        validate_limits(limits)
        return all(bound is None or getattr(self, key) <= bound for key, bound in limits.items())


def validate_limits(limits):
    if any(
        key not in DIMENSIONS or (value is not None and (type(value) is not int or value < 0))
        for key, value in limits.items()
    ):
        raise ValueError("Invalid resource limits")


class BudgetLedger:
    def __init__(self, limits, *, allocation_mode="global_budget", quotas=None, journal=None):
        validate_limits(limits)
        if allocation_mode not in {"global_budget", "fixed_quota"}:
            raise ValueError("Unknown allocation mode")
        self.limits = dict(limits)
        self.allocation_mode = allocation_mode
        self.quotas = dict(quotas or {})
        for quota in self.quotas.values():
            validate_limits(quota)
        self.spent = Cost()
        self.reserved = Cost()
        self.entries = {}
        self.events = []
        self.journal = journal
        if journal is not None:
            if journal.records:
                raise ValueError("Use explicit ledger restore for an existing journal")
            journal.append(
                "ledger:contract",
                {
                    "schema": "disastertrace.monitoring.resource_ledger.v1",
                    "limits": self.limits,
                    "allocation_mode": allocation_mode,
                    "quotas": self.quotas,
                },
            )

    def _record(self, identity, event):
        if self.journal is not None:
            self.journal.append(identity, event)
        self.events.append(event)

    @classmethod
    def restore(cls, journal):
        if not journal.records or journal.records[0]["event_id"] != "ledger:contract":
            raise ValueError("Missing durable ledger contract")
        contract = journal.records[0]["payload"]
        if contract.get("schema") != "disastertrace.monitoring.resource_ledger.v1":
            raise ValueError("Unknown ledger contract")
        ledger = cls(
            contract["limits"],
            allocation_mode=contract["allocation_mode"],
            quotas=contract["quotas"],
        )
        for record in journal.records[1:]:
            row = record["payload"]
            if row["event"] == "reserve":
                ledger.reserve(row["receipt_id"], Cost(**row["upper"]), row["owner"])
            elif row["event"] == "overrun_rejected":
                entry = ledger.entries[row["receipt_id"]]
                if Cost(**row["actual"]).within(asdict(entry["upper"])):
                    raise ValueError("Invalid overrun receipt")
                ledger.events.append(row)
            else:
                ledger.settle(row["receipt_id"], Cost(**row["actual"]), outcome=row["event"])
        ledger.journal = journal
        return ledger

    def reserve(self, receipt_id: str, upper: Cost, owner: str):
        if receipt_id in self.entries:
            entry = self.entries[receipt_id]
            if entry["upper"] != upper or entry["owner"] != owner:
                raise ValueError("Idempotency identity conflict")
            return False
        if not (self.spent + self.reserved + upper).within(self.limits):
            raise ValueError("Global reservation exceeds hard limits")
        if self.allocation_mode == "fixed_quota":
            if owner not in self.quotas:
                raise ValueError("No target quota")
            charged = Cost()
            for entry in self.entries.values():
                if entry["owner"] == owner:
                    charged += entry["actual"] if entry["settled"] else entry["upper"]
            if not (charged + upper).within(self.quotas[owner]):
                raise ValueError("Initiating target must pay the complete shared asset cost")
        self._record(
            "ledger:reserve:" + receipt_id,
            {
                "event": "reserve",
                "receipt_id": receipt_id,
                "owner": owner,
                "upper": asdict(upper),
            },
        )
        self.entries[receipt_id] = {
            "owner": owner,
            "upper": upper,
            "settled": False,
            "actual": None,
        }
        self.reserved += upper
        return True

    def settle(self, receipt_id: str, actual: Cost, *, outcome="completed"):
        entry = self.entries[receipt_id]
        if entry["settled"]:
            if entry["actual"] != actual or entry["outcome"] != outcome:
                raise ValueError("Conflicting settlement replay")
            return False
        if not actual.within(asdict(entry["upper"])):
            self._record(
                "ledger:overrun:" + receipt_id + ":" + str(len(self.events)),
                {"event": "overrun_rejected", "receipt_id": receipt_id, "actual": asdict(actual)},
            )
            raise ValueError("Actual usage exceeds reservation; no silent release")
        if outcome in {"reserve", "overrun_rejected"}:
            raise ValueError("Reserved ledger event name cannot be a settlement outcome")
        self._record(
            "ledger:settle:" + receipt_id,
            {
                "event": outcome,
                "receipt_id": receipt_id,
                "actual": asdict(actual),
            },
        )
        self.reserved -= entry["upper"]
        self.spent += actual
        entry.update(settled=True, actual=actual, outcome=outcome)
        return True
