"""Explicit information views; physical caching never grants authorization."""

from __future__ import annotations

from copy import deepcopy

PUBLIC_SELECTOR_FIELDS = frozenset(
    {
        "baseline_probability",
        "baseline_context_hash",
        "deadline",
        "entity",
        "public_query_ids",
        "quota_remaining",
        "public_coverage",
    }
)


def selector_view(common_metadata):
    return {
        target: {k: deepcopy(v) for k, v in metadata.items() if k in PUBLIC_SELECTOR_FIELDS}
        for target, metadata in common_metadata.items()
    }


class EvidenceStore:
    def __init__(self, authorization_mode, targets):
        if authorization_mode not in {"target_private", "session_shared"}:
            raise ValueError("Unknown authorization mode")
        self.authorization_mode = authorization_mode
        self.targets = frozenset(targets)
        self.assets = {}

    def register(self, asset_id, content, *, owner, receipt_id):
        if owner not in self.targets or not receipt_id:
            raise ValueError("Asset requires registered payer and durable receipt")
        entitlement = (
            self.targets if self.authorization_mode == "session_shared" else frozenset({owner})
        )
        row = {
            "asset_id": asset_id,
            "content": deepcopy(content),
            "owner": owner,
            "receipt_ids": (receipt_id,),
            "entitlement": entitlement,
            "parents": (),
        }
        if asset_id in self.assets:
            if self.assets[asset_id] != row:
                raise ValueError("Conflicting asset identity; private copies need scoped keys")
            return False
        self.assets[asset_id] = row
        return True

    def derive(self, asset_id, content, parents):
        if not parents or asset_id in self.assets:
            raise ValueError("Derived asset needs existing parents and fresh identity")
        records = [self.assets[parent] for parent in parents]
        entitlement = frozenset.intersection(*(row["entitlement"] for row in records))
        receipts = tuple(sorted({receipt for row in records for receipt in row["receipt_ids"]}))
        self.assets[asset_id] = {
            "asset_id": asset_id,
            "content": deepcopy(content),
            "owner": "derived",
            "receipt_ids": receipts,
            "entitlement": entitlement,
            "parents": tuple(parents),
        }

    def view(self, target):
        if target not in self.targets:
            raise ValueError("Unknown target")
        return [
            {k: deepcopy(row[k]) for k in ("asset_id", "content", "receipt_ids", "parents")}
            for _, row in sorted(self.assets.items())
            if target in row["entitlement"]
        ]
