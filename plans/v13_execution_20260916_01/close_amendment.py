"""Final receipt after the additional selector-prefix regression; retain first close."""

import datetime as dt
import json
from pathlib import Path

from finalize import RUN, REPO, STARTER, read, sha, write


def main():
    report=read(RUN/'regression_02/RESULT.json');registration=read(RUN/'regression_02/REGISTRATION.json')
    describe=read(RUN/'runtime/regression_02/DESCRIBE_FINAL.json')
    job=json.loads(describe['stdout'])
    protected=read(RUN/'PROTECTION_MANIFEST.json')
    historical=[p for p,h in protected['historical_files'].items() if not (REPO/p).exists() or sha(REPO/p)!=h]
    current=[]
    frozen_root=RUN/'regression_02/source'
    for p,h in registration['source_hashes'].items():
        actual=STARTER/'src'/Path(p).relative_to(frozen_root)
        if not actual.exists() or sha(actual)!=h:current.append(str(actual))
    for p,h in registration['test_hashes'].items():
        if not Path(p).exists() or sha(Path(p))!=h:current.append(p)
    git=REPO/'.git';gitdir=(REPO/git.read_text().strip().split(': ',1)[1]).resolve() if git.is_file() else git
    index_same=sha(gitdir/'index')==protected['index_sha256']
    if historical or current or not index_same:
        write('AMENDMENT_PRESERVATION_FAILURE.json',{'historical':historical,'current':current,'index_unchanged':index_same})
        raise RuntimeError('Unexpected preservation difference; stop for inspection')
    write('FINAL_PRESERVATION_02.json',{'passed':True,'historical_files':len(protected['historical_files']),
        'historical_changed':historical,'current_source_and_tests_match_final_regression':True,'index_unchanged':True})
    success=report['passed'] and job.get('state')=='SUCCEEDED' and read(RUN/'runtime/regression_02/EXIT.json')['exit_code']==0
    tests=next(r for r in report['results'] if Path(r['module']).name=='test_monitoring_v13_selector.py')
    write('SELECTOR_V2_OFFLINE_MATRIX_02.json',{'passed':success,'tests':tests,
        'schema_validation_sha256':sha(RUN/'SELECTOR_SCHEMA_VALIDATION.json'),
        'amendment':'complete prefix/tail dispositions; first infeasible intent stops later paid GET; original pending source resume tested',
        'real_api_calls':0,'supersedes_matrix_sha256':sha(RUN/'SELECTOR_V2_OFFLINE_MATRIX.json')})
    write('TEST_RECEIPTS_02.json',{'passed':success,'unique_nodes':report['unique_nodes'],
        'historical_expected_nodes':793,'new_v13_unique_tests':report['unique_nodes']-793,
        'result_sha256':sha(RUN/'regression_02/RESULT.json'),'registration_sha256':sha(RUN/'regression_02/REGISTRATION.json'),
        'previous_regression_retained':True,'same_test_scope_plus_four_selector_boundary_tests':True,
        'red_exit_code':1,'red_junit_sha256':sha(RUN/'tests/SELECTOR_TAIL_RED.xml'),
        'targeted_green_exit_code':0,'targeted_green_junit_sha256':sha(RUN/'tests/SELECTOR_TAIL_GREEN_01.xml')})
    original=read(RUN/'RESULT_SUMMARY.json')
    final={**original,'schema':'disastertrace.v13.final_amended_result.v1',
        'closed_at':dt.datetime.now(dt.timezone.utc).isoformat(),'engineering_complete':success and original['engineering_complete'],
        'regression_unique_tests':report['unique_nodes'],'first_summary_sha256':sha(RUN/'RESULT_SUMMARY.json'),
        'amendment_sha256':sha(RUN/'CLOSEOUT_AMENDMENT_01.json'),
        'canonical_final_receipt':True,'final_regression':'regression_02/RESULT.json',
        'resource_jobs':[read(RUN/'runtime/regression_01/JOB.json')['job_id'],job['name']],
        'jobs_run_sequentially':True,'peak_remote_cpu':16,'final_source_prefix_dispositions_verified':success}
    final['tasks']['A03']='passed' if success else 'blocked'
    final['tasks']['A06']='passed' if success else 'blocked'
    if not success:
        final['gate_readiness']['M00']['technical_prerequisites_passed']=False
    write('FINAL_RESULT.json',final)
    write('STOP_RECEIPT_02.json',{'batch_closed':True,'engineering_complete':final['engineering_complete'],
        'at':final['closed_at'],'canonical_final_receipt':'FINAL_RESULT.json','stop_after':'A06',
        'cloud_jobs_terminal':job.get('state'),'automatic_next_phase':False,
        'prior_stop_retained_sha256':sha(RUN/'STOP_RECEIPT.json')})
    print(json.dumps({'closed':True,'engineering_complete':final['engineering_complete'],
                      'final_unique_tests':report['unique_nodes'],'job_state':job.get('state')}),flush=True)


if __name__=='__main__':main()
