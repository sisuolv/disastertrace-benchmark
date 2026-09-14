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
            elif row["event"] == "execution_unknown":
                ledger.mark_unknown(row["receipt_id"], row["details"])
            elif row["event"] == "bind_request":
                ledger.bind_request(row["receipt_id"], row["binding"])
            elif row["event"] == "execution_timing":
                ledger.record_execution_timing(
                    row["receipt_id"], row["timing"]["last_wall_ns"], row["phase"]
                )
                if ledger.events[-1] != row:
                    raise ValueError("Execution timing replay mismatch")
            elif row["event"] == "execution_reconciled":
                ledger.reconcile_unknown(row["receipt_id"], Cost(**row["actual"]), row["proof"])
            elif row["event"] == "overrun_settled":
                ledger.settle_observed(
                    row["receipt_id"], Cost(**row["actual"]), outcome=row["outcome"]
                )
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
        if entry.get("outcome") == "unknown_execution":
            raise ValueError("Unknown execution requires original response reconciliation")
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
        if outcome in {
            "reserve",
            "overrun_rejected",
            "bind_request",
            "execution_unknown",
            "overrun_settled",
            "execution_reconciled",
            "execution_timing",
        }:
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

    def mark_unknown(self, receipt_id, details):
        entry = self.entries[receipt_id]
        if entry["settled"]:
            raise ValueError("A settled call cannot become unknown")
        if "unknown_details" in entry:
            if entry["unknown_details"] != details:
                raise ValueError("Conflicting unknown-execution receipt")
            return False
        self._record(
            "ledger:unknown:" + receipt_id,
            {"event": "execution_unknown", "receipt_id": receipt_id, "details": details},
        )
        entry["outcome"] = "unknown_execution"
        entry["unknown_details"] = details
        return True

    def bind_request(self, receipt_id, binding):
        from .targets import canonical_hash

        entry = self.entries[receipt_id]
        if set(binding) != {"request_sha256", "execution_sha256"} or any(
            not isinstance(v, str) or len(v) != 64 or any(c not in "0123456789abcdef" for c in v)
            for v in binding.values()
        ):
            raise ValueError("Request requires exact request and executor hashes")
        if "binding" in entry:
            if entry["binding"] != binding:
                raise ValueError("Acquisition or model request identity conflict")
            return False
        if entry["settled"] or entry.get("outcome") == "unknown_execution":
            raise ValueError("Bind request before dispatch and uncertainty")
        self._record(
            "ledger:bind:" + receipt_id,
            {"event": "bind_request", "receipt_id": receipt_id, "binding": dict(binding)},
        )
        entry["binding"] = dict(binding)
        entry["binding_sha256"] = canonical_hash(binding)
        return True

    def record_execution_timing(self, receipt_id, wall_ns, phase):
        entry = self.entries[receipt_id]
        if (
            type(wall_ns) is not int
            or wall_ns < 0
            or phase not in {"dispatch", "poll", "interrupted", "returned"}
            or entry["settled"]
            or entry.get("outcome") == "unknown_execution"
            or "binding" not in entry
        ):
            raise ValueError("Invalid execution timing observation")
        previous = entry.get("timing")
        if previous is None and phase != "dispatch":
            raise ValueError("Original dispatch time required")
        if previous is not None and (phase == "dispatch" or wall_ns < previous["last_wall_ns"]):
            raise ValueError("Execution clock reversal or repeated dispatch")
        first = wall_ns if previous is None else previous["first_wall_ns"]
        timing = {
            "first_wall_ns": first,
            "last_wall_ns": wall_ns,
            "elapsed_us": (wall_ns - first + 999) // 1000,
            "observations": 1 if previous is None else previous["observations"] + 1,
        }
        self._record(
            "ledger:timing:" + receipt_id + ":" + str(timing["observations"]),
            {
                "event": "execution_timing",
                "receipt_id": receipt_id,
                "phase": phase,
                "timing": timing,
            },
        )
        entry["timing"] = dict(timing)

    def reconcile_unknown(self, receipt_id, actual, proof):
        entry = self.entries[receipt_id]
        fields = {"request_sha256", "execution_sha256", "response_sha256", "observed_at"}
        if (
            not isinstance(proof, dict)
            or set(proof) != fields
            or type(proof["observed_at"]) is not int
        ):
            raise ValueError("Original response receipt required for automatic reconciliation")
        if entry.get("binding") != {k: proof[k] for k in ("request_sha256", "execution_sha256")}:
            raise ValueError("Response belongs to a different original request or executor")
        sha = proof["response_sha256"]
        if (
            not isinstance(sha, str)
            or len(sha) != 64
            or any(c not in "0123456789abcdef" for c in sha)
        ):
            raise ValueError("Bound original response hash required")
        if entry["settled"]:
            if entry["actual"] != actual or entry.get("reconciliation_proof") != proof:
                raise ValueError("Conflicting reconciled response")
            return False
        if entry.get("outcome") != "unknown_execution":
            raise ValueError("Only a recorded unknown execution can be reconciled")
        self._record(
            "ledger:reconciled:" + receipt_id,
            {
                "event": "execution_reconciled",
                "receipt_id": receipt_id,
                "actual": asdict(actual),
                "proof": dict(proof),
            },
        )
        self.reserved -= entry["upper"]
        self.spent += actual
        entry.update(
            settled=True,
            actual=actual,
            outcome="reconciled_execution",
            reconciliation_proof=dict(proof),
            overrun=not actual.within(asdict(entry["upper"])),
        )
        return True

    def settle_observed(self, receipt_id, actual, *, outcome="completed"):
        """Retain measured overruns as breaches; they are not admitted free work."""
        entry = self.entries[receipt_id]
        if entry.get("outcome") == "unknown_execution":
            raise ValueError("Unknown execution requires original response reconciliation")
        if actual.within(asdict(entry["upper"])):
            return self.settle(receipt_id, actual, outcome=outcome)
        if entry["settled"]:
            if entry["actual"] != actual or entry["outcome"] != outcome:
                raise ValueError("Conflicting observed settlement")
            return False
        self._record(
            "ledger:observed-overrun:" + receipt_id,
            {
                "event": "overrun_settled",
                "receipt_id": receipt_id,
                "actual": asdict(actual),
                "outcome": outcome,
            },
        )
        self.reserved -= entry["upper"]
        self.spent += actual
        entry.update(settled=True, actual=actual, outcome=outcome, overrun=True)
        return True
