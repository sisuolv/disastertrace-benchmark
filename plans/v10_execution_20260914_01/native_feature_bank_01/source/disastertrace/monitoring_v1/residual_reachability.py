"""Exact bounded E reference for a serial immutable-source acquisition frame.

The initial ledger/cache are actual engine states. Unresolved reservations stay
held; a caller must finish any original in-flight serial invocation before this
reference starts. This is an evaluator oracle, not a query-selection policy.
"""

from copy import deepcopy
from dataclasses import asdict, dataclass
from types import SimpleNamespace

from .resources import DIMENSIONS, BudgetLedger, Cost
from .targets import canonical_hash
from .views import EvidenceStore


@dataclass(frozen=True)
class ResidualQuery:
    query_key: str
    asset_id: str
    owner: str
    content: dict
    upper: Cost
    actual: Cost
    released_at: int
    duration: int

    def __post_init__(self):
        if (not all(isinstance(s, str) and s for s in (self.query_key, self.asset_id, self.owner))
                or type(self.released_at) is not int or type(self.duration) is not int
                or self.duration <= 0 or not self.actual.within(asdict(self.upper))):
            raise ValueError("Invalid residual query identity, duration or resource contract")
        canonical_hash(self.content)


def _state(ledger, store, cached_completed):
    contract = {"schema": "disastertrace.monitoring.resource_ledger.v1", "limits": ledger.limits,
                "allocation_mode": ledger.allocation_mode, "quotas": ledger.quotas}
    records = [{"event_id": "ledger:contract", "payload": contract}]
    records.extend({"event_id": str(i), "payload": event} for i, event in enumerate(ledger.events))
    replayed = BudgetLedger.restore(SimpleNamespace(records=records))
    replayed.journal = None
    if (replayed.spent != ledger.spent or replayed.reserved != ledger.reserved
            or replayed.entries != ledger.entries or replayed.events != ledger.events):
        raise ValueError("Residual ledger does not reconstruct from its actual events")
    if set(cached_completed) != set(store.assets) or any(type(t) is not int for t in cached_completed.values()):
        raise ValueError("Every cached asset needs its actual completion time")
    rebuilt = EvidenceStore(store.authorization_mode, store.targets)
    pending = list(store.assets.values())
    while pending:
        eligible = [r for r in pending if set(r["parents"]) <= set(rebuilt.assets)]
        if not eligible:
            raise ValueError("Unbound derived cache")
        for row in eligible:
            if any(rid not in ledger.entries or not ledger.entries[rid]["settled"]
                   for rid in row["receipt_ids"]):
                raise ValueError("Cache requires original settled resource receipts")
            if row["parents"]:
                rebuilt.derive(row["asset_id"], row["content"], row["parents"])
            else:
                if len(row["receipt_ids"]) != 1:
                    raise ValueError("Native cache must bind one original receipt")
                rebuilt.register(row["asset_id"], row["content"], owner=row["owner"], receipt_id=row["receipt_ids"][0])
            if rebuilt.assets[row["asset_id"]] != row:
                raise ValueError("Cache changes ownership or authorization")
            pending.remove(row)
    return replayed, rebuilt, dict(cached_completed)


def _validate(ledger, store, queries, goals, start, source_credit, acquisition_deadline):
    if type(start) is not int or type(source_credit) is not int or source_credit < 0:
        raise ValueError("Invalid residual clock/source credit")
    if (not goals or len({g.deadline for g in goals}) != 1
            or len({g.target_id for g in goals}) != len(goals)
            or any(g.target_id not in store.targets for g in goals)):
        raise ValueError("Serial residual reference requires unique targets and one cutoff")
    if type(acquisition_deadline) is not int or acquisition_deadline > goals[0].deadline:
        raise ValueError("Acquisition horizon cannot exceed the shared E deadline")
    keys = {q.query_key for q in queries}
    if len(keys) != len(queries) or any(q.owner not in store.targets for q in queries):
        raise ValueError("Duplicate queries or unregistered payer")
    versions = {}
    for q in queries:
        if "residual:" + q.query_key in ledger.entries:
            raise ValueError("Residual invocation collides with an existing receipt")
        signature = canonical_hash(q.content)
        if q.asset_id in versions and versions[q.asset_id] != signature:
            raise ValueError("An immutable residual asset cannot have conflicting versions")
        versions[q.asset_id] = signature
    assets = set(store.assets) | {q.asset_id for q in queries}
    if any(not recipe <= assets for g in goals for recipe in g.alternatives):
        raise ValueError("Goal recipe refers to an unregistered asset")


def _resolved(store, completed, goals):
    return sorted(g.target_id for g in goals if any(recipe <= {
        aid for aid, row in store.assets.items()
        if g.target_id in row["entitlement"] and completed[aid] <= g.deadline
    } for recipe in g.alternatives))


def _witness(actions, ledger, initial_spent, store, completed, goals, start):
    return {"actions": actions, "resolved": _resolved(store, completed, goals),
            "incremental_cost": asdict(ledger.spent - initial_spent),
            "final_spent": asdict(ledger.spent), "final_reserved": asdict(ledger.reserved),
            "completion_time": actions[-1]["completed_at"] if actions else start}


def _dominates(a, b):
    return (set(a["resolved"]) >= set(b["resolved"])
            and a["completion_time"] <= b["completion_time"]
            and all(a["incremental_cost"][k] <= b["incremental_cost"][k] for k in DIMENSIONS))


def solve_residual(ledger, store, queries, goals, *, start, cached_completed=None,
                   source_credit=None, acquisition_deadline=None, max_states=50000,
                   max_additional_queries=None):
    cached_completed = {} if cached_completed is None else cached_completed
    source_credit = ledger.limits.get("requests") if source_credit is None else source_credit
    acquisition_deadline = goals[0].deadline if acquisition_deadline is None else acquisition_deadline
    _validate(ledger, store, queries, goals, start, source_credit, acquisition_deadline)
    if type(max_states) is not int or max_states < 1 or (max_additional_queries is not None
            and (type(max_additional_queries) is not int or max_additional_queries < 0)):
        raise ValueError("Invalid finite residual search cap")
    seed = _state(ledger, store, cached_completed)
    graph = {"queries": [asdict(q) for q in queries], "goals": [
        {**asdict(g), "alternatives": [sorted(r) for r in g.alternatives]} for g in goals],
        "initial_ledger_events": ledger.events, "limits": ledger.limits,
        "quotas": ledger.quotas, "allocation_mode": ledger.allocation_mode,
        "authorization_mode": store.authorization_mode,
        "initial_assets": [{**r, "entitlement": sorted(r["entitlement"])} for r in store.assets.values()],
        "cached_completed": cached_completed, "start": start, "source_credit": source_credit,
        "acquisition_deadline": acquisition_deadline, "max_additional_queries": max_additional_queries,
        "concurrency": 1, "pending_original_invocation": False}
    stack, frontier, reachable = [(start, *seed, [])], [], set()
    explored, lower = 0, 0.0
    while stack and explored < max_states:
        now, current, cache, completed, actions = stack.pop()
        explored += 1
        witness = _witness(actions, current, ledger.spent, cache, completed, goals, start)
        reachable.update(witness["resolved"])
        lower = max(lower, sum(g.weight for g in goals if g.target_id in witness["resolved"]))
        if not any(_dominates(w, witness) for w in frontier):
            frontier = [w for w in frontier if not _dominates(witness, w)] + [witness]
        if max_additional_queries is not None and len(actions) >= max_additional_queries:
            continue
        for q in sorted(queries, key=lambda q: q.query_key, reverse=True):
            begin = max(now, q.released_at)
            if (q.asset_id in cache.assets or begin + q.duration > acquisition_deadline
                    or current.spent.requests + current.reserved.requests + q.upper.requests > source_credit):
                continue
            next_ledger, next_cache, next_completed = deepcopy((current, cache, completed))
            rid = "residual:" + q.query_key
            try:
                next_ledger.reserve(rid, q.upper, q.owner)
            except ValueError:
                continue
            next_ledger.settle(rid, q.actual)
            next_cache.register(q.asset_id, q.content, owner=q.owner, receipt_id=rid)
            next_completed[q.asset_id] = begin + q.duration
            step = {"query_key": q.query_key, "started_at": begin, "completed_at": begin + q.duration}
            stack.append((begin + q.duration, next_ledger, next_cache, next_completed, actions + [step]))
    exact = not stack
    return {"schema": "disastertrace.residual_E_reference.v1", "graph": graph,
            "graph_sha256": canonical_hash(graph), "exact": exact, "explored_states": explored,
            "max_states": max_states, "lower_bound": lower,
            "upper_bound": lower if exact else sum(g.weight for g in goals),
            "individual_status": {g.target_id: "reachable_relaxation" if g.target_id in reachable
                else "unreachable_in_frozen_graph" if exact else "unknown_search_truncated" for g in goals},
            "frontier": frontier,
            "scope": "same-cutoff immutable-source serial acquisition; earliest starts suffice; evaluator only",
            "future_prediction_or_decision_optimum": False}


def replay_residual_witness(witness, ledger, store, queries, goals, *, start,
                            cached_completed=None, source_credit=None,
                            acquisition_deadline=None, max_additional_queries=None):
    """Replay the claimed path through the production ledger/store, without search."""
    cached_completed = {} if cached_completed is None else cached_completed
    source_credit = ledger.limits.get("requests") if source_credit is None else source_credit
    acquisition_deadline = goals[0].deadline if acquisition_deadline is None else acquisition_deadline
    _validate(ledger, store, queries, goals, start, source_credit, acquisition_deadline)
    charged, visible, completed = _state(ledger, store, cached_completed)
    qmap, seen, now = {q.query_key: q for q in queries}, set(), start
    if max_additional_queries is not None and len(witness["actions"]) > max_additional_queries:
        raise ValueError("Witness violates the frame query cap")
    for step in witness["actions"]:
        key, begin, end = step["query_key"], step["started_at"], step["completed_at"]
        q = qmap[key]
        if (key in seen or q.asset_id in visible.assets or begin < max(now, q.released_at)
                or end != begin + q.duration or end > acquisition_deadline):
            raise ValueError("Witness violates serial release/duration/cache constraints")
        if charged.spent.requests + charged.reserved.requests + q.upper.requests > source_credit:
            raise ValueError("Witness exceeds released calendar credit")
        rid = "residual:" + key
        charged.reserve(rid, q.upper, q.owner)
        charged.settle(rid, q.actual)
        visible.register(q.asset_id, q.content, owner=q.owner, receipt_id=rid)
        completed[q.asset_id] = end
        now = end
        seen.add(key)
    reconstructed = _witness(witness["actions"], charged, ledger.spent, visible, completed, goals, start)
    if reconstructed != witness:
        raise ValueError("Residual witness costs, completion or resolved targets disagree")
    return {"passed": True, "resolved": reconstructed["resolved"],
            "ledger": charged, "store": visible, "completed": completed}
