from datetime import datetime, timezone, timedelta
import json
from disastertrace.models import *
from disastertrace.scoring import score_transition
from disastertrace.importers.nhc_time import parse_nhc_issued_at
T = datetime(2026, 6, 1, 8, tzinfo=timezone.utc)
report = {}
base = StateLedger()
commit = CheckpointCommit(checkpoint_id='CP1', action=ActionCommit(operation=ActionOperation.HOLD, action='monitor'))
o = ObligationSheet(transition_id='T1', checkpoint_id='CP1', admissible_actions=['monitor'], earliest_admissible_time=T+timedelta(hours=2))
s = score_transition(obligation=o, commit=commit, previous_state=base, current_state=base, delivered_ids=set(), checkpoint_time=T)
report['timing_applied_to_hold'] = {'admissible':s.audit.action_admissible, 'timing':s.audit.action_timing_correct}
ku = lambda cp: CheckpointCommit(checkpoint_id=cp, belief_updates=[BeliefUpdate(slot='port_condition',operation=BeliefOperation.KEEP_UNKNOWN)], action=ActionCommit(operation=ActionOperation.HOLD,action='monitor'))
before = base.apply(ku('CP0'), T)
after = before.apply(ku('CP1'), T+timedelta(hours=1))
o = ObligationSheet(transition_id='T2',checkpoint_id='CP1',must_preserve=['port_condition'],admissible_actions=['monitor'])
s = score_transition(obligation=o,commit=ku('CP1'),previous_state=before,current_state=after,delivered_ids=set(),checkpoint_time=T+timedelta(hours=1))
report['unknown_metadata_causes_preservation_failure'] = {'before_value':before.slots['port_condition'].value,'after_value':after.slots['port_condition'].value,'preservation':s.audit.preservation_correct}
c = CheckpointCommit(checkpoint_id='CP1',evidence_used=[EvidenceReference(artifact_id='A'), EvidenceReference(artifact_id='B',span_id='gold_span_for_A')],action=ActionCommit(operation=ActionOperation.HOLD,action='monitor'))
o = ObligationSheet(transition_id='T3',checkpoint_id='CP1',required_evidence_any_of=[['A']],required_span_ids=['gold_span_for_A'],admissible_actions=['monitor'])
s = score_transition(obligation=o,commit=c,previous_state=base,current_state=base,delivered_ids={'A','B'},checkpoint_time=T)
report['unbound_span_wrong_artifact_passes'] = {'grounding':s.audit.grounding_correct, 'strict_pass':s.strict_pass}
c = CheckpointCommit(checkpoint_id='CP1',belief_updates=[BeliefUpdate(slot='x',operation=BeliefOperation.ADD,new_value='first'),BeliefUpdate(slot='x',operation=BeliefOperation.ADD,new_value='second')],action=ActionCommit(operation=ActionOperation.HOLD,action='monitor'))
report['duplicate_slot_updates_accepted_by_ledger'] = {'last_value':base.apply(c,T).slots['x'].value}
text='1100 PM EDT Fri Sep 30 2022\nSUMMARY OF 1100 PM EDT...0300 UTC...INFORMATION'
try:
    parse_nhc_issued_at(text)
    report['nhc_public_header_not_supported'] = False
except ValueError as e:
    report['nhc_public_header_not_supported'] = str(e)
c = CheckpointCommit.model_validate({'checkpoint_id':'CP1','action':{'operation':'HOLD','action':'monitor'},'unrecognized_field':'ignored'})
report['extra_schema_keys_silently_ignored'] = 'unrecognized_field' not in c.model_dump()
print(json.dumps(report,ensure_ascii=False,indent=2))
