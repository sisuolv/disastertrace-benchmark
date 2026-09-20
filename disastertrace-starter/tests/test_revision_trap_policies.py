"""Tests for the trap policy library + locator (P0-05).

Acceptance criteria from plan v14 section 7.5 / section 10 P0-05 row:
- Synthetic fixture: the locator must UNIQUELY identify each of the 7
  policies (LATEST_MENTION, DOUBLE_COUNT, IGNORE_AMD, STALE_HOLD,
  FOLLOW_ONLY, ALWAYS_UPDATE, ORACLE_LEDGER) from its trajectory output.
- ORACLE_LEDGER must score a perfect fact-layer compliance rate (via P0-04's
  metrics.compute_amendment_compliance_rate, reused/generalized), since it
  perfectly follows ledger semantics -- it must be the ONE policy scoring
  100% compliance on a fixture spanning all 9 ledger kinds.

Behavior table (plan section 7.5, verbatim CN + translation -- see
revision_v1/trap_policies.py module docstring for the full design
rationale of how each prose behavior maps to a deterministic
kind->operation rule):

| policy          | 行为 (behavior)                | 对应失效 (failure)      |
|-----------------|----------------------------------|---------------------------|
| LATEST_MENTION  | 只信最近到达的包，不看版本        | 迟到旧版误用              |
| DOUBLE_COUNT    | 对 duplicate/mirror 再次更新      | overreaction              |
| IGNORE_AMD      | 忽略 amendment/correction         | staleness                 |
| STALE_HOLD      | 首个 commit 后永远 HOLD           | 迟滞                       |
| FOLLOW_ONLY     | 永远 FOLLOW_BASELINE              | 无自主修订                 |
| ALWAYS_UPDATE   | 每包都改概率                      | 过度修订                   |
| ORACLE_LEDGER   | 正确处理账本（程序）              | 事实层上界（非概率上界）    |

Reuses:
- P0-01 `revision_v1/ledger.py::compile_ledger` (via the `make_product`/`us`
  helpers imported from `test_revision_ledger`, per repo convention of
  cross-file helper import) to build real, classifier-derived ledger
  entries of all 9 kinds.
- P0-03 `revision_v1/belief_commit.py::validate_commit_schema` to confirm
  every emitted commit is schema-valid.
- P0-04 `revision_v1/metrics.py::compute_amendment_compliance_rate` as the
  fact-layer compliance metric.
"""

import pytest

from disastertrace.revision_v1.ledger import compile_ledger
from disastertrace.revision_v1.belief_commit import validate_commit_schema
from disastertrace.revision_v1.metrics import compute_amendment_compliance_rate
from disastertrace.revision_v1.trap_policies import (
    POLICY_NAMES,
    KIND_OPERATION_TABLES,
    apply_policy,
    identify_policy,
    amendment_compliance_input,
    fact_layer_compliance_input,
    AMBIGUOUS,
)

from test_revision_ledger import make_product, us


# ---------------------------------------------------------------------------
# Fixture: one ledger entry of each of the 9 P0-01 kinds, merged into a
# single episode with controlled, globally increasing available_at so
# processing order is deterministic regardless of each sub-fixture's local
# clock.
# ---------------------------------------------------------------------------

T0 = us("2026-09-19T00:00:00Z")
HOUR = 3_600_000_000
STEP = 10_000 * 1_000_000  # 10,000 seconds between synthetic arrivals


def _entry_of_kind(products, kind, *, collector_first_seen=None):
    ledger = compile_ledger(products, collector_first_seen=collector_first_seen)
    matches = [e for e in ledger if e["kind"] == kind]
    assert matches, f"fixture did not produce a {kind!r} entry: {ledger}"
    return matches[0]


def _new_observation_entry():
    products = [
        make_product(source_id="ev-no", issued_at=T0, valid_start=T0, valid_end=T0 + 6 * HOUR)
    ]
    return _entry_of_kind(products, "new_observation"), 0.30


def _amendment_supersedes_entry():
    products = [
        make_product(source_id="ev-as-orig", issued_at=T0, valid_start=T0, valid_end=T0 + 6 * HOUR),
        make_product(
            source_id="ev-as-amd",
            issued_at=T0 + 10 * 60_000_000,
            valid_start=T0,
            valid_end=T0 + 6 * HOUR,
            amendment_kind="AMD",
            semantic_content={"body": "amd-content"},
        ),
    ]
    return _entry_of_kind(products, "amendment_supersedes"), 0.65


def _correction_entry():
    products = [
        make_product(source_id="ev-cor-orig", issued_at=T0, valid_start=T0, valid_end=T0 + 6 * HOUR),
        make_product(
            source_id="ev-cor-cor",
            issued_at=T0 + 10 * 60_000_000,
            valid_start=T0,
            valid_end=T0 + 6 * HOUR,
            amendment_kind="COR",
            semantic_content={"body": "cor-content"},
        ),
    ]
    return _entry_of_kind(products, "correction"), 0.55


def _cancellation_entry():
    products = [
        make_product(source_id="ev-cx-orig", issued_at=T0, valid_start=T0, valid_end=T0 + 6 * HOUR),
        make_product(
            source_id="ev-cx-cnl",
            issued_at=T0 + HOUR,
            valid_start=T0,
            valid_end=T0 + 6 * HOUR,
            status="canceled",
        ),
    ]
    return _entry_of_kind(products, "cancellation"), 0.0


def _lossless_duplicate_entry():
    shared = {"body": "dup-content", "vis": 10000}
    products = [
        make_product(source_id="ev-ld-a", issued_at=T0, valid_start=T0, valid_end=T0 + 6 * HOUR, semantic_content=shared),
        make_product(source_id="ev-ld-b", issued_at=T0, valid_start=T0, valid_end=T0 + 6 * HOUR, semantic_content=shared),
    ]
    return _entry_of_kind(products, "lossless_duplicate"), 0.40


def _mirror_entry():
    shared = {"body": "mirror-content", "vis": 5000}
    products = [
        make_product(source_id="nws-ev-mi", issued_at=T0, valid_start=T0, valid_end=T0 + 6 * HOUR, semantic_content=shared),
        make_product(
            source_id="aviationweather-ev-mi",
            issued_at=T0 + 1_000_000,
            valid_start=T0,
            valid_end=T0 + 6 * HOUR,
            semantic_content=shared,
        ),
    ]
    return _entry_of_kind(products, "mirror"), 0.40


def _late_superseded_entry():
    lag = 2 * 60_000_000
    products = [
        make_product(source_id="ev-ls-orig", issued_at=T0, valid_start=T0, valid_end=T0 + 6 * HOUR),
        make_product(
            source_id="ev-ls-amd",
            issued_at=T0 + HOUR,
            valid_start=T0,
            valid_end=T0 + 6 * HOUR,
            amendment_kind="AMD",
            semantic_content={"body": "ls-amd"},
        ),
        make_product(
            source_id="ev-ls-late",
            issued_at=T0 + 30 * 60_000_000,
            valid_start=T0,
            valid_end=T0 + 6 * HOUR,
            semantic_content={"body": "ls-late-old"},
        ),
    ]
    collector_times = {
        "ev-ls-orig": T0 + lag,
        "ev-ls-amd": T0 + HOUR + lag,
        "ev-ls-late": T0 + 2 * HOUR,
    }
    return _entry_of_kind(products, "late_superseded", collector_first_seen=collector_times), 0.20


def _no_change_reissue_entry():
    content = {"body": "ncr-content", "vis": 10000}
    products = [
        make_product(source_id="ev-ncr-v1", issued_at=T0, valid_start=T0, valid_end=T0 + 6 * HOUR, semantic_content=content),
        make_product(
            source_id="ev-ncr-reissue",
            issued_at=T0 + 2 * HOUR,
            valid_start=T0,
            valid_end=T0 + 6 * HOUR,
            semantic_content=content,
        ),
    ]
    return _entry_of_kind(products, "no_change_reissue"), 0.30


def _baseline_update_entry():
    products = [
        make_product(source_id="ev-bu-1", issued_at=T0, valid_start=T0, valid_end=T0 + 6 * HOUR)
    ]
    products[-1]["is_baseline"] = True
    return _entry_of_kind(products, "baseline_update"), 0.50


# Fixed processing order (arbitrary but deterministic); position 0 matters
# for STALE_HOLD, so keep new_observation first.
_KIND_FIXTURE_ORDER = [
    ("new_observation", _new_observation_entry),
    ("amendment_supersedes", _amendment_supersedes_entry),
    ("correction", _correction_entry),
    ("cancellation", _cancellation_entry),
    ("lossless_duplicate", _lossless_duplicate_entry),
    ("mirror", _mirror_entry),
    ("late_superseded", _late_superseded_entry),
    ("no_change_reissue", _no_change_reissue_entry),
    ("baseline_update", _baseline_update_entry),
]


def build_nine_kind_ledger():
    """Build one merged ledger spanning all 9 P0-01 kinds, plus evidence values.

    Returns (ledger, evidence_values, episode_id, target_id).
    """
    ledger = []
    evidence_values = {}
    for i, (kind, builder) in enumerate(_KIND_FIXTURE_ORDER):
        entry, value = builder()
        assert entry["kind"] == kind
        entry = dict(entry)
        entry["available_at"] = i * STEP  # globally sequential, deterministic order
        ledger.append(entry)
        evidence_values[entry["source_id"]] = value

    return ledger, evidence_values, "ep-trap-001", "target-trap-001"


# ---------------------------------------------------------------------------
# Test: behavior table -- each policy's chosen operation per kind matches
# the §7.5 prose behavior (translated to the deterministic rule documented
# in trap_policies.py).
# ---------------------------------------------------------------------------


class TestBehaviorTable:
    def _ops_by_kind(self, policy_name, ledger, evidence_values, episode_id, target_id):
        commits = apply_policy(
            policy_name,
            episode_id=episode_id,
            target_id=target_id,
            ledger=ledger,
            evidence_values=evidence_values,
        )
        kind_by_source = {e["source_id"]: e["kind"] for e in ledger}
        return {
            kind_by_source[ev_id]: c["operation"]
            for c in commits
            for ev_id in c["evidence_ids"]
        }

    def test_oracle_ledger_matches_reference_table(self):
        ledger, values, ep, tgt = build_nine_kind_ledger()
        ops = self._ops_by_kind("ORACLE_LEDGER", ledger, values, ep, tgt)
        assert ops == KIND_OPERATION_TABLES["ORACLE_LEDGER"]

    def test_latest_mention_updates_on_late_superseded_unlike_oracle(self):
        """LATEST_MENTION: 只信最近到达的包，不看版本 -> misuses late-arriving old version."""
        ledger, values, ep, tgt = build_nine_kind_ledger()
        ops = self._ops_by_kind("LATEST_MENTION", ledger, values, ep, tgt)
        assert ops["late_superseded"] == "UPDATE"  # deviation from oracle (HOLD)
        # everywhere else, matches oracle
        oracle = KIND_OPERATION_TABLES["ORACLE_LEDGER"]
        for kind, op in ops.items():
            if kind != "late_superseded":
                assert op == oracle[kind]

    def test_double_count_updates_on_duplicate_and_mirror_unlike_oracle(self):
        """DOUBLE_COUNT: 对 duplicate/mirror 再次更新 -> overreaction."""
        ledger, values, ep, tgt = build_nine_kind_ledger()
        ops = self._ops_by_kind("DOUBLE_COUNT", ledger, values, ep, tgt)
        assert ops["lossless_duplicate"] == "UPDATE"
        assert ops["mirror"] == "UPDATE"
        oracle = KIND_OPERATION_TABLES["ORACLE_LEDGER"]
        for kind, op in ops.items():
            if kind not in ("lossless_duplicate", "mirror"):
                assert op == oracle[kind]

    def test_ignore_amd_holds_on_amendment_and_correction_unlike_oracle(self):
        """IGNORE_AMD: 忽略 amendment/correction -> staleness."""
        ledger, values, ep, tgt = build_nine_kind_ledger()
        ops = self._ops_by_kind("IGNORE_AMD", ledger, values, ep, tgt)
        assert ops["amendment_supersedes"] == "HOLD"
        assert ops["correction"] == "HOLD"
        oracle = KIND_OPERATION_TABLES["ORACLE_LEDGER"]
        for kind, op in ops.items():
            if kind not in ("amendment_supersedes", "correction"):
                assert op == oracle[kind]

    def test_stale_hold_only_first_commit_updates(self):
        """STALE_HOLD: 首个 commit 后永远 HOLD -> lag."""
        ledger, values, ep, tgt = build_nine_kind_ledger()
        commits = apply_policy(
            "STALE_HOLD", episode_id=ep, target_id=tgt, ledger=ledger, evidence_values=values
        )
        assert commits[0]["operation"] == "UPDATE"
        assert all(c["operation"] == "HOLD" for c in commits[1:])

    def test_follow_only_always_follow_baseline(self):
        """FOLLOW_ONLY: 永远 FOLLOW_BASELINE -> no autonomous revision."""
        ledger, values, ep, tgt = build_nine_kind_ledger()
        commits = apply_policy(
            "FOLLOW_ONLY", episode_id=ep, target_id=tgt, ledger=ledger, evidence_values=values
        )
        assert all(c["operation"] == "FOLLOW_BASELINE" for c in commits)

    def test_always_update_updates_every_package(self):
        """ALWAYS_UPDATE: 每包都改概率 -> over-revision."""
        ledger, values, ep, tgt = build_nine_kind_ledger()
        commits = apply_policy(
            "ALWAYS_UPDATE", episode_id=ep, target_id=tgt, ledger=ledger, evidence_values=values
        )
        assert all(c["operation"] == "UPDATE" for c in commits)


# ---------------------------------------------------------------------------
# Test: every emitted commit is schema-valid and hash-chained (P0-03 reuse)
# ---------------------------------------------------------------------------


class TestSchemaAndChain:
    @pytest.mark.parametrize("policy_name", POLICY_NAMES)
    def test_every_commit_passes_schema_validation(self, policy_name):
        ledger, values, ep, tgt = build_nine_kind_ledger()
        commits = apply_policy(
            policy_name, episode_id=ep, target_id=tgt, ledger=ledger, evidence_values=values
        )
        assert len(commits) == len(ledger)
        for commit in commits:
            result = validate_commit_schema(commit)
            assert result["valid"] is True, result["error"]

    @pytest.mark.parametrize("policy_name", POLICY_NAMES)
    def test_hash_chain_integrity(self, policy_name):
        ledger, values, ep, tgt = build_nine_kind_ledger()
        commits = apply_policy(
            policy_name, episode_id=ep, target_id=tgt, ledger=ledger, evidence_values=values
        )
        assert commits[0]["parent_commit_id"] is None
        for prev, cur in zip(commits, commits[1:]):
            assert cur["parent_commit_id"] == prev["commit_id"]

    @pytest.mark.parametrize("policy_name", POLICY_NAMES)
    def test_hold_commits_have_empty_updates(self, policy_name):
        ledger, values, ep, tgt = build_nine_kind_ledger()
        commits = apply_policy(
            policy_name, episode_id=ep, target_id=tgt, ledger=ledger, evidence_values=values
        )
        for commit in commits:
            if commit["operation"] == "HOLD":
                assert commit["fact_updates"] == []
                assert commit["forecast_updates"] == []

    def test_unknown_policy_name_raises(self):
        ledger, values, ep, tgt = build_nine_kind_ledger()
        with pytest.raises(ValueError, match="Unknown policy"):
            apply_policy("NOT_A_POLICY", episode_id=ep, target_id=tgt, ledger=ledger)


# ---------------------------------------------------------------------------
# Test: locator uniquely identifies each of the 7 policies
# ---------------------------------------------------------------------------


class TestLocatorUniqueIdentification:
    def test_locator_uniquely_identifies_each_policy(self):
        ledger, values, ep, tgt = build_nine_kind_ledger()

        identified = {}
        for policy_name in POLICY_NAMES:
            commits = apply_policy(
                policy_name, episode_id=ep, target_id=tgt, ledger=ledger, evidence_values=values
            )
            identified[policy_name] = identify_policy(commits, ledger)

        # Each policy is identified as itself.
        for policy_name in POLICY_NAMES:
            assert identified[policy_name] == policy_name, (
                f"{policy_name} misidentified as {identified[policy_name]}"
            )

        # No ambiguity: 7 distinct trajectories map to 7 distinct labels.
        assert len(set(identified.values())) == len(POLICY_NAMES)
        assert AMBIGUOUS not in identified.values()

    @pytest.mark.parametrize("policy_name", POLICY_NAMES)
    def test_locator_identifies_each_policy_individually(self, policy_name):
        ledger, values, ep, tgt = build_nine_kind_ledger()
        commits = apply_policy(
            policy_name, episode_id=ep, target_id=tgt, ledger=ledger, evidence_values=values
        )
        assert identify_policy(commits, ledger) == policy_name

    def test_low_diversity_fixture_is_not_well_constructed(self):
        """Document the caveat: a fixture without enough kind diversity can be
        genuinely ambiguous between policies that only disagree elsewhere.

        With only new_observation packages, ORACLE_LEDGER's trajectory is
        indistinguishable from ALWAYS_UPDATE's (both UPDATE on every
        package) -- this is why the 9-kind fixture above is required for
        unique identification, not a locator bug.
        """
        entry, value = _new_observation_entry()
        entry2 = dict(entry)
        entry2["source_id"] = "ev-no-2"
        entry2["available_at"] = entry["available_at"] + HOUR
        ledger = [entry, entry2]
        values = {entry["source_id"]: value, entry2["source_id"]: value}

        oracle_commits = apply_policy(
            "ORACLE_LEDGER", episode_id="ep", target_id="tgt", ledger=ledger, evidence_values=values
        )
        # Both ops are UPDATE (new_observation), so the absolute
        # all-UPDATE check claims ALWAYS_UPDATE first.
        assert identify_policy(oracle_commits, ledger) == "ALWAYS_UPDATE"


# ---------------------------------------------------------------------------
# Test: ORACLE_LEDGER fact-layer compliance is perfect (P0-04 reuse)
# ---------------------------------------------------------------------------


class TestFactLayerCompliance:
    def test_oracle_ledger_scores_perfect_full_ledger_compliance(self):
        ledger, values, ep, tgt = build_nine_kind_ledger()
        commits = apply_policy(
            "ORACLE_LEDGER", episode_id=ep, target_id=tgt, ledger=ledger, evidence_values=values
        )
        rate = compute_amendment_compliance_rate(fact_layer_compliance_input(commits, ledger))
        assert rate == 1.0

    @pytest.mark.parametrize(
        "policy_name",
        [p for p in POLICY_NAMES if p != "ORACLE_LEDGER"],
    )
    def test_no_other_policy_scores_perfect_full_ledger_compliance(self, policy_name):
        """ORACLE_LEDGER is the ONE policy with 100% fact-layer compliance."""
        ledger, values, ep, tgt = build_nine_kind_ledger()
        commits = apply_policy(
            policy_name, episode_id=ep, target_id=tgt, ledger=ledger, evidence_values=values
        )
        rate = compute_amendment_compliance_rate(fact_layer_compliance_input(commits, ledger))
        assert rate is not None
        assert rate < 1.0

    def test_amendment_only_compliance_narrower_metric(self):
        """The narrower amendment/correction-only metric: ORACLE is still perfect,
        but is not the only one (LATEST_MENTION/DOUBLE_COUNT/ALWAYS_UPDATE also
        adopt every amendment/correction -- their failures live in other
        layers per the §7.5 failure-correspondence column, e.g. overreaction
        for DOUBLE_COUNT, which is a probability-layer, not fact-layer,
        metric). IGNORE_AMD scores 0.0 here by construction.
        """
        ledger, values, ep, tgt = build_nine_kind_ledger()

        oracle_commits = apply_policy(
            "ORACLE_LEDGER", episode_id=ep, target_id=tgt, ledger=ledger, evidence_values=values
        )
        oracle_rate = compute_amendment_compliance_rate(
            amendment_compliance_input(oracle_commits, ledger)
        )
        assert oracle_rate == 1.0

        ignore_amd_commits = apply_policy(
            "IGNORE_AMD", episode_id=ep, target_id=tgt, ledger=ledger, evidence_values=values
        )
        ignore_amd_rate = compute_amendment_compliance_rate(
            amendment_compliance_input(ignore_amd_commits, ledger)
        )
        assert ignore_amd_rate == 0.0
