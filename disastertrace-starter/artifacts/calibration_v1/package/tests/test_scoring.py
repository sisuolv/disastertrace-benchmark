from datetime import datetime, timezone

from disastertrace.models import (
    ActionCommit,
    ActionOperation,
    BeliefOperation,
    BeliefUpdate,
    CheckpointCommit,
    EvidenceReference,
    ExpectedUpdate,
    ObligationSheet,
    StateLedger,
)
from disastertrace.scoring import score_transition


def test_transition_score_is_non_compensatory() -> None:
    at = datetime(2026, 6, 1, 18, tzinfo=timezone.utc)
    previous = StateLedger()
    commit = CheckpointCommit(
        checkpoint_id="CP_02",
        evidence_used=[EvidenceReference(artifact_id="ADV_02", span_id="warning_span")],
        belief_updates=[
            BeliefUpdate(
                slot="warning_status",
                operation=BeliefOperation.ADD,
                new_value="warning",
                evidence=[EvidenceReference(artifact_id="ADV_02")],
            )
        ],
        action=ActionCommit(operation=ActionOperation.ESCALATE, action="prepare"),
    )
    current = previous.apply(commit, at)
    obligation = ObligationSheet(
        transition_id="T1",
        checkpoint_id="CP_02",
        required_evidence_any_of=[["ADV_02"]],
        required_updates=[
            ExpectedUpdate(
                slot="warning_status", operation=BeliefOperation.ADD, new_value="warning"
            )
        ],
        must_remain_unknown=["port_operation"],
        admissible_actions=["prepare"],
        required_span_ids=["warning_span"],
    )
    score = score_transition(
        obligation=obligation,
        commit=commit,
        previous_state=previous,
        current_state=current,
        delivered_ids={"ADV_02"},
        checkpoint_time=at,
    )
    assert score.strict_pass == 1.0


def test_illegal_evidence_forces_strict_failure() -> None:
    at = datetime(2026, 6, 1, 18, tzinfo=timezone.utc)
    previous = StateLedger()
    commit = CheckpointCommit(
        checkpoint_id="CP_02",
        evidence_used=[EvidenceReference(artifact_id="FUTURE_ADV")],
        action=ActionCommit(operation=ActionOperation.HOLD, action="monitor"),
    )
    score = score_transition(
        obligation=ObligationSheet(
            transition_id="T2", checkpoint_id="CP_02", admissible_actions=["monitor"]
        ),
        commit=commit,
        previous_state=previous,
        current_state=previous,
        delivered_ids={"ADV_02"},
        checkpoint_time=at,
    )
    assert score.audit.evidence_legal == 0.0
    assert score.strict_pass == 0.0
