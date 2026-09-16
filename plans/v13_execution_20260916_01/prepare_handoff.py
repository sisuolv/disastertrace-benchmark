"""Concrete unsent next-gate rosters and implemented contracts, no launcher."""

import json
from pathlib import Path

from audit_history import RUN, REPO, OLD, TRUST, bound
from disastertrace.monitoring_v1.selector_contract_v2 import VERSION, contract
from disastertrace.monitoring_v1.spool_backend import digest, publish, read
from disastertrace.monitoring_v1.targets import canonical_hash


def main():
    publish(RUN/"QUERY_ONLY_V2_CONTRACT.json",{**contract(['q0','q1','q2']),
        "dynamic_enum_source":"actual registered public request.queries handles",
        "length_cap":"candidate count, never affordable count",
        "runtime_adapter":{"forecast_handles":[]},"legacy_contract_default":"selector.v1",
        "required_runtime":{"selector_kind":"llm","predictor_kind":"program","forecast_schedule":"public_serial_slots.v1"},
        "native_fences_allowed":False,"provider_unsupported_schema":"fail visibly; no silent fallback",
        "source_path":"disastertrace-starter/src/disastertrace/monitoring_v1/selector_contract_v2.py"})
    publish(RUN/"TRANSPORT_V2_CONTRACT.json",{
        "version":"receipt_bound_api.v2","opt_in":"frozen ProductionSpoolBackend.execution_contract.api_transport_v2",
        "states":["registered","claim","prepare","final_local_permit","durable_intent","send_once",
                  "durable_capture","trusted_authority_anchor","validate","publish","consume_settle"],
        "scope":"single local dispatch authority; no AFS multi-node lock qualification",
        "permission_boundary":"STOP/deadline rechecked after credential preparation and after intent I/O; STOP following final local permit cannot revoke in-flight request",
        "clock":"UTC for anchors and phase deadline; monotonic elapsed for duration and expiry backstop",
        "capture":"bounded raw prefix length/hash/EOF/truncation before redaction; raw full-body hash only on complete read; stored transformed bytes have a separate hash; strict UTF8",
        "trust":"Separate managed authority capture receipt; caller supplies expected anchor hash. Capture-local self-reported hash alone is insufficient. Trusted worker/authority filesystem is an explicit assumption",
        "recovery":"append reconciliation binding original request/execution/intent/capture/failure/response; old failure retained; original ProductionSpoolBackend consumer verifies it",
        "accounting":"late original response through resolve and coordinator.reconcile_costs; no duplicate settlement or reopening of closed weather decisions",
        "unknown":"no resend, no invented cost, no reservation release without original response proof",
        "new_real_api_calls":0,"provider_exactly_once_guarantee":False,
        "source_path":"disastertrace-starter/src/disastertrace/monitoring_v1/api_transport_v2.py"})
    publish(RUN/"RESIDUAL_V2_CONTRACT.json",{
        "schema":"disastertrace.residual_query_plan.v2","rules":["none","first_new","second_new","all_new"],
        "version_dispatch":"freeze_residual_plan(..., version='disastertrace.residual_query_plan.v2')",
        "legacy_default":"disastertrace.residual_query_plan.v1; first/second/all semantics preserved",
        "inventory":"public relatedness/availability; payer-scoped query asset key and authorized cache; original ledger receipt lifecycle",
        "remaining_new":"related available candidates minus entitled cache and all original requested identities",
        "not_sent_failure":"still excluded; a new separately registered identity is needed, never automatic retry",
        "private_scope":"another target's private purchase grants neither access nor an exclusion of this target's new private purchase",
        "none":"no subsequent paid query; common baseline updates and scheduled forecasts remain",
        "budget_time":"same restored parent and legal runtime prefix; unavailable/budget/late/tail dispositions retained",
        "E_F":"E sufficiency and F probability remain distinct; no new oracle or future Y access",
        "new_real_c2_branches":0})
    root=OLD/'stage_C';intent=bound(root/'INTENT.json');policy=bound(root/'API_POLICY.json')
    (RUN/'m00_unsent').mkdir(exist_ok=False)
    proposals=[]
    for i,item in enumerate(intent['cases']):
        prefix=str(root/item['case']/'spool')+'/'
        names=[p for p in TRUST if p.startswith(prefix) and p.endswith('.request.json')]
        name=min(names,key=lambda p:canonical_hash({'case':item['case'],'request_name':Path(p).name}))
        old=bound(name);view={**old['request'], 'selector_contract_version':VERSION}
        spec=contract(view['queries']);view['output_contract']=spec['logical_schema']
        payload={'model':policy['model'],'messages':[{'role':'system','content':spec['system']},
            {'role':'user','content':json.dumps(view,sort_keys=True,separators=(',',':'),allow_nan=False)}],
            'temperature':0,'max_tokens':policy['output_cap'],'enable_thinking':False,'stream':False,
            'response_format':spec['provider_schema']}
        path=RUN/'m00_unsent'/f'{i:02d}_PAYLOAD.json';publish(path,payload)
        proposals.append({'proposal_id':f'v13-m00-unsent-{i:02d}','case':item['case'],
            'original_public_request_path':name,'original_public_request_sha256':digest(Path(name)),
            'new_payload_path':str(path.relative_to(REPO)),'new_payload_sha256':digest(path),
            'query_count':len(view['queries']), 'conservative_input_bytes_plus_margin':sum(len(m['content'].encode()) for m in payload['messages'])+4096,
            'input_allowance':policy['input_cap'],'output_allowance':policy['output_cap'],
            'executed':False})
    publish(RUN/'M00_PROPOSAL.json',{'execution':False,'requests_max':12,'roster':proposals,
        'role':'weather-shaped output/transport smoke only; not a new weather-effectiveness experiment',
        'route':policy['model'],'base_url':policy['base_url'],'automatic_retries':0,
        'next_launch_requirements':['A02/A03 regression pass','fresh execution ID and real ProductionSpool controller binding',
                                    'fresh absolute phase deadline and STOP/authority directory','verify registered caps for every payload'],
        'boundary_coverage':{'empty_query_catalog':'not present in selected real requests; offline only',
                             'synthetic_length_and_failure_edges':'offline only'},
        'credential_included':False,'api_calls_sent':0})
    old_plan_path=REPO/'plans/v11_execution_20260915_01/fullweek_02/PLAN.json'
    old_plan=read(old_plan_path)
    roster=[{k:r[k] for k in ('case','date','region','threshold','week','opportunities')} for r in old_plan['cases']]
    fit=OLD/'annual_stage_B/fit'
    publish(RUN/'B00_ROSTER_PROPOSAL.json',{'execution':False,'cases':roster,'case_count':len(roster),
        'source_calendar_path':str(old_plan_path),'source_calendar_sha256':digest(old_plan_path),
        'arms':['FOLLOW','F_COMMON','F_BASE_ONLY','B11_BATCH','B11_COVERAGE'],
        'banks':{k:{'path':str(fit/f'BANK_{k}.json'),'sha256':digest(fit/f'BANK_{k}.json'),
                      'runtime_transform':'remove post_calibration for primary raw arm; freeze transformed hash before launch'} for k in ('common','values')},
        'trajectories_max':840,'opportunities_max':12096,'method_rows_max':60480,
        'reuse_count':'pending exact input/consumer/code/schedule/contract/scorer admission; not preclaimed',
        'primary_same_values_comparisons':[['F_BASE_ONLY','B11_BATCH'],['F_BASE_ONLY','B11_COVERAGE'],['B11_BATCH','B11_COVERAGE']],
        'separate_consumer_controls':['FOLLOW','F_COMMON'],'outcome_selection':False,
        'new_weather_downloads':0,'new_model_calls':0,'new_fits':0,
        'follow_on_training':'clock drift is measured; retain v1 banks for bridge, then consider one separately registered slot-aligned candidate'})
    clock=read(RUN/'CLOCK_INFORMATION_AUDIT.json')
    parents=[]
    for item in intent['cases']:
        options=[r for r in clock['rows'] if r['case']==item['case']]
        choice=min(options,key=lambda r:canonical_hash(r['opportunity_id']))
        parents.append({'case':item['case'],'opportunity_id':choice['opportunity_id'],
            'source_report':str(root/item['case']/'B11_COVERAGE/FORMAL_REPORT.json'),
            'source_report_sha256':digest(root/item['case']/'B11_COVERAGE/FORMAL_REPORT.json'),
            'parent_materialized':False,'original_continuation_verified':False,
            'source_state_qualification':'must inspect actual restored legal state; no claimed full/partial/none coverage from region/date alone'})
    publish(RUN/'C00_ROSTER_PROPOSAL.json',{'execution':False,'parents_max':12,'parent_candidates':parents,
        'selection':'one public-ID/hash-ranked opportunity per already exposed registered case; no Y or branch-loss selection',
        'source_distribution':'natural exposed development calendar; not independent-process confirmation',
        'chosen_forecast_bank':'frozen annual raw values, same as B00; reconstruct prefix from session start',
        'materializations_max':12,'original_continuations_max':12,'GET_branches_max':48,
        'GET_rules':['none','first_new','second_new','all_new'],
        'qualification_gaps':['actual checkpoint identity','exact original continuation','source-state strata and residual opportunity roster'],
        'separate_not_in_GET_cap':{'PROCESS_max':12,'WAIT_TIMING_pairs_max':6},'new_real_branches':0})
    # Correct one ambiguous output label without overwriting the first diagnostic receipt.
    corrected={**clock,'rows':[{('forecast_cutoff' if k=='future_weather' else k):v for k,v in row.items()} for row in clock['rows']],
               'original_receipt_sha256':digest(RUN/'CLOCK_INFORMATION_AUDIT.json'),
               'revision':'field name only: old future_weather was the decision cutoff; no recomputation or target change'}
    publish(RUN/'CLOCK_INFORMATION_AUDIT_V2.json',corrected)
    print(json.dumps({'unsent_requests':len(proposals),'B00_cases':len(roster),'C00_parent_candidates':len(parents)}),flush=True)


if __name__=='__main__':main()
