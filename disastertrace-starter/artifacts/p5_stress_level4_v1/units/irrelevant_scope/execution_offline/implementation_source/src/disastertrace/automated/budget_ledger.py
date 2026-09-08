"""Deterministic, experiment-wide conservative accounting; no network operations."""

from copy import deepcopy
from decimal import Decimal, InvalidOperation


def default_policy() -> dict:
    return {
        "currency": "USD",
        "allowance": "3.00",
        "max_attempts": 270,
        "prompt_bound": 1048576,
        "input_per_million": "0.44",
        "output_per_million": "1.32",
        "max_requested_output_tokens": 1474560,
        "max_request_bytes": 262144,
    }


def money(value) -> Decimal:
    if not isinstance(value, str):
        raise ValueError("money must be an exact decimal string")
    try:
        result = Decimal(value)
    except InvalidOperation:
        raise ValueError("invalid money") from None
    if not result.is_finite() or result < 0:
        raise ValueError("money must be finite and nonnegative")
    return result


class BudgetLedger:
    def __init__(self, policy: dict):
        if set(policy) != set(default_policy()) or policy["currency"] != "USD":
            raise ValueError("invalid budget policy")
        for name in ("allowance", "input_per_million", "output_per_million"):
            money(policy[name])
        for name in (
            "max_attempts",
            "prompt_bound",
            "max_requested_output_tokens",
            "max_request_bytes",
        ):
            if type(policy[name]) is not int or policy[name] < 1:
                raise ValueError("invalid budget bound")
        self.policy = deepcopy(policy)
        self.rows = {}

    def reserve(self, attempt_id: str, cap: int) -> dict:
        if not isinstance(attempt_id, str) or not attempt_id or type(cap) is not int or cap < 1:
            raise ValueError("invalid attempt or cap")
        if attempt_id in self.rows:
            raise ValueError("attempt already reserved")
        if any(row["status"] != "settled" for row in self.rows.values()):
            raise ValueError("pending/unknown attempt blocks subsequent dispatch")
        policy = self.policy
        amount = (
            policy["prompt_bound"] * money(policy["input_per_million"])
            + cap * money(policy["output_per_million"])
        ) / Decimal(1000000)
        settled = sum((money(r["cost"]) for r in self.rows.values()), Decimal(0))
        if (
            len(self.rows) >= policy["max_attempts"]
            or sum(r["cap"] for r in self.rows.values()) + cap
            > policy["max_requested_output_tokens"]
            or settled + amount > money(policy["allowance"])
        ):
            raise ValueError("budget guard stopped next request")
        row = {
            "attempt_id": attempt_id,
            "cap": cap,
            "reservation": str(amount),
            "cost": "0",
            "status": "reserved",
            "usage": None,
        }
        self.rows[attempt_id] = row
        return deepcopy(row)

    def settle(self, attempt_id: str, usage: dict) -> dict:
        row = self.rows[attempt_id]
        if (
            not isinstance(usage, dict)
            or any(
                type(usage.get(k)) is not int or usage[k] < 0
                for k in ("prompt_tokens", "completion_tokens", "total_tokens")
            )
            or usage["prompt_tokens"] + usage["completion_tokens"] != usage["total_tokens"]
            or usage["prompt_tokens"] > self.policy["prompt_bound"]
            or usage["completion_tokens"] > row["cap"]
        ):
            raise ValueError("usage violates accounting bounds")
        if row["status"] == "settled":
            if usage != row["usage"]:
                raise ValueError("settlement cannot be changed")
            return deepcopy(row)
        if row["status"] == "unknown":
            raise ValueError("unknown requires a separately reviewed resolution")
        cost = usage["prompt_tokens"] * money(self.policy["input_per_million"]) + usage[
            "completion_tokens"
        ] * money(self.policy["output_per_million"])
        cost /= Decimal(1000000)
        if cost > money(row["reservation"]):
            raise ValueError("usage exceeds reservation")
        row.update(cost=str(cost), usage=deepcopy(usage), status="settled")
        return deepcopy(row)

    def unknown(self, attempt_id: str) -> dict:
        row = self.rows[attempt_id]
        if row["status"] == "settled":
            raise ValueError("cannot unset a settlement")
        row["status"] = "unknown"
        return deepcopy(row)

    def snapshot(self) -> dict:
        return {
            "attempts": len(self.rows),
            "settled": str(sum((money(r["cost"]) for r in self.rows.values()), Decimal(0))),
            "pending": str(
                sum(
                    (
                        money(r["reservation"])
                        for r in self.rows.values()
                        if r["status"] != "settled"
                    ),
                    Decimal(0),
                )
            ),
            "rows": deepcopy(list(self.rows.values())),
        }
