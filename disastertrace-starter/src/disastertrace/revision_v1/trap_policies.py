"""Trap policy library + locator for DisasterTrace v14 (P0-05).

Implements the 7 deterministic "trap" belief-update strategies from plan
section 7.5 (behavior table), plus a locator that identifies which policy
produced a given commit trajectory from the trajectory alone (given the same
public ledger the policies read).

Behavior table (plan v14 doc, section 7.5, verbatim translation):

| policy          | behavior (CN)               | behavior (EN)                              | corresponding failure       |
|-----------------|------------------------------|---------------------------------------------|------------------------------|
| LATEST_MENTION  | 只信最近到达的包，不看版本   | trust only the most-recently arrived        | late-arriving old version    |
|                 |                               | package, ignoring version/order              | misused                      |
| DOUBLE_COUNT    | 对 duplicate/mirror 再次更新 | re-updates on duplicate/mirror packages      | overreaction                 |
| IGNORE_AMD      | 忽略 amendment/correction     | ignores amendment/correction packages        | staleness                    |
| STALE_HOLD      | 首个 commit 后永远 HOLD      | after the first commit, HOLD forever         | lag                          |
| FOLLOW_ONLY     | 永远 FOLLOW_BASELINE         | always defers to the baseline forecast       | no autonomous revision       |
| ALWAYS_UPDATE   | 每包都改概率                  | changes probability on every package         | over-revision                |
| ORACLE_LEDGER   | 正确处理账本（程序）          | program-correct: perfectly follows ledger    | fact-layer upper bound (not  |
|                 |                               | semantics                                    | a probability-layer bound)   |

Design (documented, since the plan doc's table gives behavior in prose, not
an executable spec):

Every policy is defined as a deterministic function from a P0-01 ledger
entry's `kind` (new_observation / amendment_supersedes / correction /
cancellation / lossless_duplicate / mirror / late_superseded /
no_change_reissue / baseline_update) to a P0-03 `operation`
(UPDATE / HOLD / FOLLOW_BASELINE), applied in `available_at` order, EXCEPT
for STALE_HOLD (a purely sequential rule: UPDATE on the first evidence
package, HOLD on everything after, regardless of kind).

ORACLE_LEDGER is the reference table (`_ORACLE_KIND_OPERATION`): it UPDATEs
on kinds that carry genuinely new or corrected information
(new_observation/amendment_supersedes/correction/cancellation), HOLDs on
kinds that carry no new information relative to what is already known
(lossless_duplicate/mirror/late_superseded/no_change_reissue -- a
late-arriving package that was already superseded before it arrived must
NOT overwrite the newer state), and FOLLOW_BASELINEs on baseline_update.

The other three table-driven policies are ORACLE_LEDGER with exactly the
deviation named in the behavior table:
- LATEST_MENTION: like ORACLE, except it also UPDATEs on late_superseded
  (it "doesn't look at version", so a late-arriving old package is treated
  as if it were the newest truth -- the stated failure, "misuse of a
  late-arriving old version").
- DOUBLE_COUNT: like ORACLE, except it also UPDATEs on lossless_duplicate
  and mirror (re-applies duplicate/mirrored evidence as if it were fresh
  corroboration -- the stated failure, overreaction).
- IGNORE_AMD: like ORACLE, except it HOLDs (instead of UPDATE) on
  amendment_supersedes and correction (the stated failure, staleness).

FOLLOW_ONLY and ALWAYS_UPDATE are content-independent: every package (any
kind) maps to FOLLOW_BASELINE, resp. UPDATE.

This per-kind-table design is what makes the locator's job well-posed: a
"well-constructed" fixture is one whose ledger contains at least one package
of every kind where two policies could disagree (see
tests/test_revision_trap_policies.py), so that the observed
(kind -> operation) mapping in the resulting trajectory uniquely matches
exactly one policy.

Reuses:
- P0-01 `revision_v1/ledger.py`: consumes `compile_ledger()` output
  (`kind`, `source_id`, `available_at`) directly -- policies do not
  reclassify evidence, they only decide UPDATE/HOLD/FOLLOW_BASELINE given
  the kind P0-01 already assigned.
- P0-03 `revision_v1/belief_commit.py`: every emitted commit is
  `disastertrace.belief_commit.v14-draft`-shaped (`SCHEMA_VERSION`), uses
  `compute_commit_id()` for the `parent_commit_id` hash chain, and must pass
  `validate_commit_schema()`.
- P0-04 `revision_v1/metrics.py`: `fact_layer_compliance_input()` below
  builds the input list for `compute_amendment_compliance_rate()`, reusing
  it (generalized from "amendments only" to "every ledger-governed
  decision") as the fact-layer compliance metric referenced by the P0-05
  acceptance criteria.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .belief_commit import SCHEMA_VERSION, compute_commit_id

# ---------------------------------------------------------------------------
# Policy names
# ---------------------------------------------------------------------------

POLICY_NAMES = (
    "LATEST_MENTION",
    "DOUBLE_COUNT",
    "IGNORE_AMD",
    "STALE_HOLD",
    "FOLLOW_ONLY",
    "ALWAYS_UPDATE",
    "ORACLE_LEDGER",
)

# Sequential (non-table) policies: their operation for a given evidence
# package cannot be determined from `kind` alone.
_SEQUENTIAL_POLICIES = frozenset({"STALE_HOLD"})
_UNIFORM_POLICIES = {
    "FOLLOW_ONLY": "FOLLOW_BASELINE",
    "ALWAYS_UPDATE": "UPDATE",
}

# ---------------------------------------------------------------------------
# Kind -> operation tables
# ---------------------------------------------------------------------------

_ORACLE_KIND_OPERATION: dict[str, str] = {
    "new_observation": "UPDATE",
    "amendment_supersedes": "UPDATE",
    "correction": "UPDATE",
    "cancellation": "UPDATE",
    "lossless_duplicate": "HOLD",
    "mirror": "HOLD",
    "late_superseded": "HOLD",
    "no_change_reissue": "HOLD",
    "baseline_update": "FOLLOW_BASELINE",
}

_LATEST_MENTION_KIND_OPERATION: dict[str, str] = {
    **_ORACLE_KIND_OPERATION,
    "late_superseded": "UPDATE",
}

_DOUBLE_COUNT_KIND_OPERATION: dict[str, str] = {
    **_ORACLE_KIND_OPERATION,
    "lossless_duplicate": "UPDATE",
    "mirror": "UPDATE",
}

_IGNORE_AMD_KIND_OPERATION: dict[str, str] = {
    **_ORACLE_KIND_OPERATION,
    "amendment_supersedes": "HOLD",
    "correction": "HOLD",
}

KIND_OPERATION_TABLES: dict[str, dict[str, str]] = {
    "ORACLE_LEDGER": _ORACLE_KIND_OPERATION,
    "LATEST_MENTION": _LATEST_MENTION_KIND_OPERATION,
    "DOUBLE_COUNT": _DOUBLE_COUNT_KIND_OPERATION,
    "IGNORE_AMD": _IGNORE_AMD_KIND_OPERATION,
}

# Fallback operation for a kind not present in a table (should not happen
# for the 9 known P0-01 kinds, but keeps this module robust to new kinds).
_DEFAULT_OPERATION = "UPDATE"


# ---------------------------------------------------------------------------
# Timestamp helper (inverse of monitoring_v1.targets.utc_us)
# ---------------------------------------------------------------------------


def _us_to_iso(value_us: int) -> str:
    """Convert a microsecond epoch timestamp to an ISO-8601 UTC string."""
    dt = datetime.fromtimestamp(value_us / 1_000_000, tz=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


# ---------------------------------------------------------------------------
# Commit construction
# ---------------------------------------------------------------------------


def _make_commit(
    *,
    episode_id: str,
    target_id: str,
    parent_commit_id: str | None,
    as_of_us: int,
    operation: str,
    evidence_id: str,
    kind: str,
    probability: float,
    fact_slot: str,
) -> dict:
    """Build a single belief_commit.v14-draft-shaped commit for one evidence package."""
    if operation == "HOLD":
        fact_updates: list[dict] = []
        forecast_updates: list[dict] = []
    else:
        if kind == "cancellation":
            fact_op, support_status, value = "RETRACT", "undetermined", None
        else:
            fact_op, support_status, value = "SET", "supported", probability
        fact_updates = [
            {
                "slot": fact_slot,
                "operation": fact_op,
                "support_status": support_status,
                "value": value,
                "source_ids": [evidence_id],
            }
        ]
        forecast_updates = [
            {"target_id": target_id, "event_probability": probability}
        ]

    commit = {
        "schema_version": SCHEMA_VERSION,
        "episode_id": episode_id,
        "target_id": target_id,
        "parent_commit_id": parent_commit_id,
        "as_of": _us_to_iso(as_of_us),
        "operation": operation,
        "evidence_ids": [evidence_id],
        "fact_updates": fact_updates,
        "forecast_updates": forecast_updates,
        "next_action": {"kind": "WAIT", "until_or_args": ""},
    }
    commit["commit_id"] = compute_commit_id(commit)
    return commit


def _operation_for(policy_name: str, kind: str, index: int) -> str:
    """Resolve the operation a policy chooses for one evidence package.

    `index` is the 0-based position in the (available_at-sorted) evidence
    sequence -- only STALE_HOLD depends on it.
    """
    if policy_name in _UNIFORM_POLICIES:
        return _UNIFORM_POLICIES[policy_name]
    if policy_name == "STALE_HOLD":
        return "UPDATE" if index == 0 else "HOLD"
    table = KIND_OPERATION_TABLES.get(policy_name)
    if table is None:
        raise ValueError(f"Unknown policy: {policy_name}")
    return table.get(kind, _DEFAULT_OPERATION)


def apply_policy(
    policy_name: str,
    *,
    episode_id: str,
    target_id: str,
    ledger: list[dict],
    evidence_values: dict[str, float] | None = None,
    fact_slot: str = "event_status",
) -> list[dict]:
    """Run one trap policy over a ledger, producing a belief_commit trajectory.

    Args:
        policy_name: One of `POLICY_NAMES`.
        episode_id: Episode identifier for every emitted commit.
        target_id: Target identifier for every emitted commit.
        ledger: List of P0-01 `compile_ledger()` entries (must have
            `source_id`, `kind`, `available_at`).
        evidence_values: Optional map source_id -> probability in [0, 1] to
            use for UPDATE/FOLLOW_BASELINE commits touching that evidence.
            Defaults to 0.5 for any source_id not given.
        fact_slot: Fact slot name used for every fact_update.

    Returns:
        A chronologically ordered, hash-chained list of commit dicts (one
        per ledger entry), each `disastertrace.belief_commit.v14-draft`-shaped.
    """
    if policy_name not in POLICY_NAMES:
        raise ValueError(f"Unknown policy: {policy_name!r}, expected one of {POLICY_NAMES}")

    evidence_values = evidence_values or {}
    ordered = sorted(ledger, key=lambda e: (e["available_at"], e["source_id"]))

    commits: list[dict] = []
    parent_id: str | None = None
    for index, entry in enumerate(ordered):
        source_id = entry["source_id"]
        kind = entry["kind"]
        operation = _operation_for(policy_name, kind, index)
        probability = evidence_values.get(source_id, 0.5)

        commit = _make_commit(
            episode_id=episode_id,
            target_id=target_id,
            parent_commit_id=parent_id,
            as_of_us=entry["available_at"],
            operation=operation,
            evidence_id=source_id,
            kind=kind,
            probability=probability,
            fact_slot=fact_slot,
        )
        commits.append(commit)
        parent_id = commit["commit_id"]

    return commits


# ---------------------------------------------------------------------------
# Locator: identify which policy produced a trajectory
# ---------------------------------------------------------------------------

AMBIGUOUS = "AMBIGUOUS"


def _observed_kind_operation(commits: list[dict], kind_by_source: dict[str, str]) -> dict[str, str] | None:
    """Build the observed kind->operation mapping from a trajectory.

    Returns None if the trajectory is inconsistent with ANY fixed per-kind
    rule (i.e. the same kind maps to two different operations at different
    points) -- which is only possible for a sequential policy.
    """
    observed: dict[str, str] = {}
    for commit in commits:
        for ev_id in commit.get("evidence_ids", []):
            kind = kind_by_source.get(ev_id)
            if kind is None:
                continue
            op = commit["operation"]
            if kind in observed and observed[kind] != op:
                return None
            observed[kind] = op
    return observed


def identify_policy(commits: list[dict], ledger: list[dict]) -> str:
    """Identify which of the 7 trap policies produced `commits`.

    The locator is given the SAME public ledger the policies read (per plan
    section 7.5: "确定性伪 agent，读同一账本" -- deterministic pseudo-agents
    reading the same ledger) but is NOT told which policy produced the
    trajectory. It reasons purely from the observed sequence of
    (kind, operation) pairs.

    Returns one of `POLICY_NAMES`, or `AMBIGUOUS` if the trajectory does not
    uniquely match exactly one policy given this ledger (e.g. the ledger
    lacks enough kind diversity to distinguish policies that only disagree
    on a kind absent from it, or a single/short trace that could match
    multiple policies).

    R4 fix (issue #1/#4): A single UPDATE trajectory or a short trace with
    only UPDATE operations on kinds that all table-driven policies handle
    identically cannot uniquely identify a policy. Such traces are AMBIGUOUS
    because multiple policies (ORACLE_LEDGER, LATEST_MENTION, DOUBLE_COUNT,
    ALWAYS_UPDATE) would all produce the same output.
    """
    if not commits:
        return AMBIGUOUS

    kind_by_source = {entry["source_id"]: entry["kind"] for entry in ledger}
    ops = [c["operation"] for c in commits]

    # R4 fix: Collect the kinds that appear in this trajectory
    observed_kinds = set()
    for commit in commits:
        for ev_id in commit.get("evidence_ids", []):
            kind = kind_by_source.get(ev_id)
            if kind:
                observed_kinds.add(kind)

    # Content-independent policies: every operation identical, and that
    # single operation isn't reachable via any table (since FOLLOW_ONLY /
    # ALWAYS_UPDATE never look at kind at all).
    if all(op == "FOLLOW_BASELINE" for op in ops):
        return "FOLLOW_ONLY"

    # R4 fix (issue #1/#4): For all-UPDATE trajectories, we need to check
    # if the observed kinds are sufficient to distinguish ALWAYS_UPDATE from
    # table-driven policies. If all observed kinds would map to UPDATE in
    # every table-driven policy, we cannot uniquely identify ALWAYS_UPDATE.
    if all(op == "UPDATE" for op in ops):
        # Check if any observed kind would NOT map to UPDATE in some table
        # (i.e., check if we have discriminating evidence)
        has_discriminating_kind = False
        for kind in observed_kinds:
            # These kinds map to HOLD in ORACLE_LEDGER (and some others)
            if kind in ("lossless_duplicate", "mirror", "late_superseded", "no_change_reissue"):
                has_discriminating_kind = True
                break
            # baseline_update maps to FOLLOW_BASELINE in ORACLE_LEDGER
            if kind == "baseline_update":
                has_discriminating_kind = True
                break
            # amendment_supersedes/correction map to HOLD in IGNORE_AMD
            if kind in ("amendment_supersedes", "correction"):
                has_discriminating_kind = True
                break

        if not has_discriminating_kind:
            # All observed kinds map to UPDATE in all table policies,
            # so we cannot distinguish ALWAYS_UPDATE from them
            return AMBIGUOUS

        return "ALWAYS_UPDATE"

    # Table-driven policies (ORACLE_LEDGER / LATEST_MENTION / DOUBLE_COUNT /
    # IGNORE_AMD): match the observed kind->operation mapping exactly
    # against each table, restricted to the kinds actually observed.
    observed = _observed_kind_operation(commits, kind_by_source)
    if observed is not None:
        table_matches = [
            name
            for name, table in KIND_OPERATION_TABLES.items()
            if all(table.get(kind) == op for kind, op in observed.items())
        ]
        if len(table_matches) == 1:
            return table_matches[0]
        if len(table_matches) > 1:
            return AMBIGUOUS

    # Sequential fallback: STALE_HOLD (first commit UPDATE, all later
    # commits HOLD, a pattern no per-kind table can reproduce once the
    # trajectory contains a later kind that every table maps to UPDATE).
    if len(ops) >= 2 and ops[0] == "UPDATE" and all(op == "HOLD" for op in ops[1:]):
        return "STALE_HOLD"

    return AMBIGUOUS


# ---------------------------------------------------------------------------
# Fact-layer compliance (reuses P0-04's compute_amendment_compliance_rate)
# ---------------------------------------------------------------------------


def amendment_compliance_input(commits: list[dict], ledger: list[dict]) -> list[dict]:
    """Build P0-04 `compute_amendment_compliance_rate()` input, amendments/corrections only.

    R4 fix (issue #2): An amendment_supersedes/correction package is "properly_adopted"
    only if the policy both:
    1. Emitted UPDATE for it (operation token)
    2. Actually included fact_updates or forecast_updates that reference the evidence

    An empty UPDATE (operation=UPDATE but no actual content updates) does NOT
    constitute proper adoption - it's just a token that proves nothing about
    whether the amended/corrected content was actually incorporated.

    Returns:
        List of {"source_id": ..., "properly_adopted": bool} for every
        amendment_supersedes/correction entry in `ledger`.
    """
    # Build mapping: source_id -> (operation, has_content_updates)
    adoption_by_source: dict[str, tuple[str, bool]] = {}
    for commit in commits:
        op = commit.get("operation", "")
        fact_updates = commit.get("fact_updates", [])
        forecast_updates = commit.get("forecast_updates", [])
        has_content = bool(fact_updates or forecast_updates)

        for ev_id in commit.get("evidence_ids", []):
            adoption_by_source[ev_id] = (op, has_content)

    return [
        {
            "source_id": entry["source_id"],
            "properly_adopted": (
                adoption_by_source.get(entry["source_id"], ("", False))[0] == "UPDATE"
                and adoption_by_source.get(entry["source_id"], ("", False))[1]
            ),
        }
        for entry in ledger
        if entry["kind"] in ("amendment_supersedes", "correction")
    ]


def fact_layer_compliance_input(commits: list[dict], ledger: list[dict]) -> list[dict]:
    """Build a full-ledger fact-layer compliance input, reusing P0-04's compliance metric.

    This generalizes `compute_amendment_compliance_rate()` from "amendments
    only" to every ledger-governed decision: an entry is "properly_adopted"
    if the policy's operation for it matches the operation ORACLE_LEDGER
    (the reference, correct-by-construction policy) would have chosen for
    that kind. Feeding this into
    `disastertrace.revision_v1.metrics.compute_amendment_compliance_rate()`
    yields a fact-layer compliance rate over the WHOLE ledger, not just the
    amendment/correction subset -- this is what makes ORACLE_LEDGER the
    unique 100%-compliance policy among the 7 (per the P0-05 acceptance
    criteria), since every other policy deviates from ORACLE_LEDGER on at
    least one kind by construction (see the behavior table above).

    Returns:
        List of {"source_id": ..., "properly_adopted": bool} for every
        ledger entry.
    """
    op_by_source = {
        ev_id: c["operation"] for c in commits for ev_id in c.get("evidence_ids", [])
    }
    return [
        {
            "source_id": entry["source_id"],
            "properly_adopted": (
                op_by_source.get(entry["source_id"])
                == _ORACLE_KIND_OPERATION.get(entry["kind"], _DEFAULT_OPERATION)
            ),
        }
        for entry in ledger
    ]
