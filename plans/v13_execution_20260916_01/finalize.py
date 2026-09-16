"""Observe completed first-batch gates, preserve inputs, and stop before B/C/M."""

import datetime as dt
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

RUN=Path(__file__).resolve().parent
REPO=RUN.parents[1]
STARTER=REPO/'disastertrace-starter'


def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(name,value):
    with (RUN/name).open('x') as f:json.dump(value,f,sort_keys=True,indent=2);f.write('\n')


def main():
    regression=read(RUN/'regression/RESULT.json')
    per_test={Path(r['module']).name:r for r in regression['results']}
    c2=read(RUN/'C2_INTEGRITY.json');history=read(RUN/'HISTORICAL_REPORT_IMPACT.json')
    clock=read(RUN/'CLOCK_INFORMATION_AUDIT_V2.json');schema=read(RUN/'SELECTOR_SCHEMA_VALIDATION.json')
    def passed(name):
        r=per_test[name]
        return r['exit_code']==0 and r['cases'] and all(c['status']=='passed' for c in r['cases'])
    statuses={
        'A00':read(RUN/'A00_RESULT.json')['passed'],
        'A01':c2['analysis_complete'] and c2['execution_complete'] and history['all_checked_numerical_results_unchanged'] and passed('test_monitoring_v13_integrity.py'),
        'A02':passed('test_monitoring_v13_transport.py'),
        'A03':passed('test_monitoring_v13_selector.py') and schema['passed'],
        'A04':passed('test_monitoring_v13_residual.py'),
        'A05':len(clock['rows'])==24 and all(r['status']!='insufficient_support' for r in clock['rows']),
    }
    source_checks={}
    for row in read(RUN/'METHOD_FINGERPRINTS.json')['fingerprints']:
        for name,expected in row['consumer_files'].items():
            if name not in source_checks:
                source_checks[name]={'expected':expected,'actual':sha(Path(name))}
    source_verified=all(v['expected']==v['actual'] for v in source_checks.values())
    write('CONSUMER_SOURCE_VERIFICATION.json',{'passed':source_verified,'files':source_checks,
            'basis':'original bound formal execution contract, separately checked from current code'})
    statuses['A01']=statuses['A01'] and source_verified
    matrix={k:per_test[k] for k in per_test if k.startswith('test_monitoring_v13_')}
    write('DISPATCH_CAPTURE_RECOVERY_TESTS.json',{'passed':statuses['A02'],
        'tests':matrix['test_monitoring_v13_transport.py'],'real_provider_calls':0,
        'production_consumer_exercised':True,'real_coordinator_and_ledger_exercised':True,
        'network_mode':'injected HTTP and local byte stream; not a provider reliability test'})
    write('SELECTOR_V2_OFFLINE_MATRIX.json',{'passed':statuses['A03'],
        'tests':matrix['test_monitoring_v13_selector.py'],'independent_schema_validation':schema,
        'actual_provider_accepts_schema':'not tested'})
    previous_exits={'INTEGRITY_RED':2,'INTEGRITY_GREEN_01':0,'SELECTOR_RED':1,
        'SELECTOR_GREEN_01':1,'RESIDUAL_RED':1,'SELECTOR_RESIDUAL_GREEN_02':0,
        'TRANSPORT_RED':1,'TRANSPORT_GREEN_01':0,'V13_TARGETED_01':0}
    receipts=[]
    for stem,code in previous_exits.items():
        xml=RUN/'tests'/(stem+'.xml');log=RUN/'logs'/(stem+'.log')
        nodes=[]
        for c in ET.parse(xml).getroot().iter('testcase'):
            nodes.append({'node':c.attrib.get('classname','')+'::'+c.attrib['name'],
                'status':'failed' if c.find('failure') is not None or c.find('error') is not None else
                         'skipped' if c.find('skipped') is not None else 'passed'})
        receipts.append({'name':stem,'observed_exit_code':code,'junit_sha256':sha(xml),'log_sha256':sha(log),'nodes':nodes,
            'source_at_invocation':'not separately frozen for each targeted iteration; final combined regression binds exact source/test hashes'})
    write('TEST_RECEIPTS.json',{'passed':regression['passed'],'combined_registration_sha256':sha(RUN/'regression/REGISTRATION.json'),
        'combined_result_sha256':sha(RUN/'regression/RESULT.json'),'combined_unique_tests':regression['unique_nodes'],
        'prior_scopes_reconciled':793,'new_v13_unique_tests':sum(len(x['cases']) for x in matrix.values()),
        'targeted_iterations':receipts,'final_new_test_modules':matrix,
        'red_test_interpretation':'Initial missing-module errors are new-API red tests, not historical runtime defect reproductions. TRANSPORT_RED reproduces two real-consumer failures; final integrity suite also runs frozen v12 missing-report analyzer in a temporary fixture.'})
    protected=read(RUN/'PROTECTION_MANIFEST.json')
    oldchanges=[];missing=[]
    for name,expected in protected['historical_files'].items():
        p=REPO/name
        if not p.is_file():missing.append(name)
        elif sha(p)!=expected:oldchanges.append(name)
    allowed={str((STARTER/'src/disastertrace/monitoring_v1'/n).relative_to(REPO)) for n in
             read(RUN/'EDIT_SCOPE.json')['current_module_allowlist']+read(RUN/'EDIT_SCOPE_AMENDMENT_01.json')['additional_current_modules']}
    allowed.update(str((STARTER/n).relative_to(REPO)) for n in read(RUN/'EDIT_SCOPE.json')['mutable_navigation'])
    changed=[name for name,h in protected['current_before'].items() if not (REPO/name).exists() or sha(REPO/name)!=h]
    unexpected=sorted(set(changed)-allowed)
    git=REPO/'.git'
    gitdir=(REPO/git.read_text().strip().split(': ',1)[1]).resolve() if git.is_file() else git
    index_sha=sha(gitdir/'index')
    preserve=not missing and not oldchanges and not unexpected and index_sha==protected['index_sha256']
    write('FINAL_PRESERVATION.json',{'passed':preserve,'protected_historical_files':len(protected['historical_files']),
        'missing_historical_files':missing,'changed_historical_files':oldchanges,'authorized_current_changes':changed,
        'unexpected_current_changes':unexpected,'index_sha256':index_sha,'index_unchanged':index_sha==protected['index_sha256'],
        'universal_raw_weather_preservation_claim':False})
    if unexpected or oldchanges or missing:
        raise RuntimeError('Unexpected preservation difference; stop and inspect')
    describe=read(RUN/'runtime/regression_01/DESCRIBE_01.json')
    job=json.loads(describe['stdout']) if describe['returncode']==0 else {}
    succeeded=job.get('state') == 'SUCCEEDED'
    write('RESOURCE_RESULT.json',{'job_id':read(RUN/'runtime/regression_01/JOB.json')['job_id'],
        'platform_succeeded_observed':succeeded,'worker_exit':read(RUN/'runtime/regression_01/EXIT.json')['exit_code'],
        'registered_cpu':16,'actual_cpu_quota':read(RUN/'regression/CLAIM.json')['cpu_quota'],
        'gpu_count':0,'test_workers':8,'source_frozen':regression['source_and_tests_unchanged'],
        'describe_receipt_sha256':sha(RUN/'runtime/regression_01/DESCRIBE_01.json')})
    statuses['A06']=regression['passed'] and preserve and succeeded
    gates={name:{'technical_prerequisites_passed':all(statuses[s] for s in dependencies),'dependencies':dependencies,
        'executed':False,'execution_within_closed_batch':False} for name,dependencies in
        {'B00':['A00','A01','A05'],'C00':['A00','A01','A04'],'M00':['A00','A02','A03']}.items()}
    gates['B00']['remaining_before_launch']=['freeze current raw bank transformation, full calendar and code','admit any exact reusable runs; preserve different-bank results']
    gates['C00']['remaining_before_launch']=['materialize selected new-bank parents','verify original continuations and legal source-state strata; no checkpoint bank replacement']
    gates['M00']['remaining_before_launch']=['fresh actual production-controller run and12-request launch contract','fresh absolute deadline, cap freeze and single dispatch authority']
    write('NEXT_GATE_DECISION.json',{'gates':gates,'recommended_order':['B00','C00 and M00 after their distinct freezes'],
        'B01':'clock effect measured; no benefit-based refit selection. Run fixed-bank bridge first, then review one separately registered slot-aligned candidate.',
        'M01':'not ready; requires real M00 interface qualification plus stronger program/action-space checks',
        'automatic_next_phase':False})
    at=dt.datetime.now(dt.timezone.utc).isoformat()
    summary={'schema':'disastertrace.v13.first_batch_result.v1','closed_at':at,'batch_closed':True,
        'engineering_complete':all(statuses.values()),'tasks':{k:'passed' if v else 'blocked' for k,v in statuses.items()},
        'regression_unique_tests':regression['unique_nodes'],'historical_c2_branches':24,'historical_method_sessions':108,
        'classification_corrections':history['stage_C']['consumer_classification_corrections'],
        'numerical_historical_scores_changed':False,'clock_diagnostic_targets':24,'api_history_records':290,
        'model_calls':0,'new_weather_http':0,'new_training':0,'new_scientific_branches':0,'gpu_count':0,
        'confirmation_opened':False,'scientific_claims_added':[],
        'observational_findings_added':['actual-consumer classification correction','public action-cost/age/topology symmetry','bounded clock-information decomposition'],
        'git_push_performed':False,'gate_readiness':gates}
    write('RESULT_SUMMARY.json',summary)
    write('STOP_RECEIPT.json',{'batch_closed':True,'at':at,'engineering_complete':summary['engineering_complete'],
        'stop_after':'A06','new_B_C_M_executions':0,'registered_cloud_jobs_terminal':succeeded,
        'reason':'Approved first batch ends for review; resource permission does not bypass scientific/launch gates'})
    print(json.dumps({k:summary[k] for k in ('batch_closed','engineering_complete','tasks','regression_unique_tests')}),flush=True)


if __name__=='__main__':main()
