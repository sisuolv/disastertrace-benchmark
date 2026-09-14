"""Frozen multi-region E diagnostics, with two API models and no future labels."""

import concurrent.futures
from collections import Counter, defaultdict
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from evidence_diagnostic import independent_reference, messages, parse
from disastertrace.monitoring_fixed_v1.aviation import AviationProvider
from disastertrace.monitoring_fixed_v1.support_bridge import native_slot_support
from disastertrace.monitoring_v1.api_capture import ApiBudget, capture
from disastertrace.monitoring_v1.spool_backend import digest, publish, read
from disastertrace.monitoring_v1.targets import canonical_hash

ROOT = Path(os.environ.get('DISASTERTRACE_FOLLOWUP_ROOT', Path(__file__).resolve().parents[1]))
OUT = ROOT / 'api_evidence_02'
V8 = ROOT.parent / 'v8_measurement_execution_20260913_01'
TRUTH = {'supported':'true','refuted':'false','undetermined':'unknown','inconsistent':'conflict'}


def main():
    if '--execute' in sys.argv:
        execute()
        return
    OUT.mkdir(exist_ok=False)
    for name in ['policy','evaluator','source','captures']:
        (OUT/name).mkdir()
    selected, rejected = [], []
    for region in ['bay','new_york','chicago','denver']:
        dataset = V8/'calendar_extension_01/dataset_v2_complete_02' if region == 'bay' else V8/'regional_calendar_extension_01'/region/'dataset_v2'
        bank = read(ROOT/'reports/regional_baselines_01'/region/'BANK.json')
        provider = AviationProvider(dataset,bank)
        counts = Counter()
        ordered = sorted(provider.opportunities.values(), key=lambda o: canonical_hash(o['opportunity_id']))
        for opportunity in ordered:
            if opportunity['lead_hours'] != 1:
                continue
            oid = opportunity['opportunity_id']
            try:
                bundle = provider.freeze(oid,'all_registered',as_of=opportunity['cutoff']-600_000_000)
                reference = independent_reference(bundle.policy_view())
                canonical = native_slot_support(bundle)
                assert reference['fact_truth'] == TRUTH[canonical['status']]
                assert reference['slots'] == {s['query_id']:TRUTH[s['status']] for s in canonical['slots']}
                key = opportunity['threshold_m'], reference['fact_truth']
                if counts[key] >= 2:
                    continue
                views = {condition:provider.freeze(oid,condition,as_of=opportunity['cutoff']-600_000_000)
                         for condition in ['common_only','fixed_one','all_registered']}
            except (ValueError,KeyError,TypeError) as exc:
                rejected.append({'region':region,'opportunity_id':oid,'error_type':type(exc).__name__})
                continue
            counts[key] += 1
            selected.append((region,oid,views))
    assert selected, 'No eligible real evidence snapshots'
    tasks, references = [], {}
    for region, oid, views in selected:
        for condition,bundle in views.items():
            view=bundle.policy_view()
            reference=independent_reference(view)
            canonical=native_slot_support(bundle)
            assert reference['fact_truth']==TRUTH[canonical['status']]
            assert reference['slots']=={s['query_id']:TRUTH[s['status']] for s in canonical['slots']}
            for representation in ['full_bundle','focused_slots']:
                for reasoning in ['direct','slotwise']:
                    ident=canonical_hash([region,oid,condition,representation,reasoning])[:24]
                    policy={'call_id':ident,'messages':messages(view,representation,reasoning)}
                    publish(OUT/'policy'/(ident+'.json'),policy)
                    tasks.append({'call_id':ident,'region':region,'opportunity_id':oid,'condition':condition,
                         'representation':representation,'reasoning':reasoning,
                         'query_ids':view['baseline']['content']['E_question']['query_ids']})
                    references[ident]=reference
    publish(OUT/'evaluator/REFERENCES.json',references)
    publish(OUT/'evaluator/PREPARATION_REJECTIONS.json',rejected)
    shutil.copyfile(Path(__file__),OUT/'source/run_api_evidence.py')
    shutil.copyfile(ROOT/'scripts/evidence_diagnostic.py',OUT/'source/evidence_diagnostic.py')
    for module in ['monitoring_v1','monitoring_fixed_v1']:
        shutil.copytree(ROOT.parents[1]/'disastertrace-starter/src/disastertrace'/module,
                       OUT/'source/disastertrace'/module,ignore=shutil.ignore_patterns('__pycache__'))
    (OUT/'source/disastertrace/__init__.py').write_text('"""Frozen native E API experiment."""\n')
    shutil.copyfile(ROOT/'model_catalog/probe_01/deepseek_pricing.body',OUT/'source/PRICING.html')
    publish(OUT/'BUDGET.json',{'limit_nanodollars':3_000_000_000,'max_calls':1008,'calls':{}})
    assert 2*len(tasks)==1008
    previous=ROOT/'api_evidence_01'
    assert tasks==read(previous/'PLAN.json')['tasks']
    assert references==read(previous/'evaluator/REFERENCES.json')
    for task in tasks:
        cid=task['call_id']
        assert read(OUT/'policy'/(cid+'.json'))==read(previous/'policy'/(cid+'.json'))
    publish(OUT/'evaluator/INPUT_EQUIVALENCE.json',{'all_tasks_and_prompts_identical':True,
        'all_references_identical':True,'prior_plan_sha256':digest(previous/'PLAN.json'),
        'changes':'AFS lock and wire-persistence collector only; complete fresh experiment namespace'})
    frozen={str(p):digest(p) for parent in ['policy','evaluator','source'] for p in (OUT/parent).rglob('*') if p.is_file()}
    publish(OUT/'PLAN.json',{'tasks':tasks,'models':['deepseek-flash','deepseek-v4-pro'],
        'frozen_at':dt.datetime.now(dt.timezone.utc).isoformat(),'files':frozen,
        'underlying_opportunities':len(selected),'api_calls':2*len(tasks),'api_concurrency':4,'fee_upper_usd':3,
        'selection':'up to two hash-ordered examples per region/threshold/visible-E state; never future F label',
        'max_tokens':512,'thinking':'disabled','retries':0,'confirmation_opened':False,
        'scope':'state-stratified exposed E diagnostic; not natural frequency or independent processes'})
    env=dict(os.environ,PYTHONPATH=str(OUT/'source'),DISASTERTRACE_FOLLOWUP_ROOT=str(ROOT),PYTHONDONTWRITEBYTECODE='1')
    result=subprocess.run([sys.executable,str(OUT/'source/run_api_evidence.py'),'--execute'],env=env)
    publish(OUT/'EXECUTION_EXIT.json',{'exit_code':result.returncode})
    if result.returncode:
        raise RuntimeError('Frozen E worker exited unsuccessfully')


def execute():
    plan=read(OUT/'PLAN.json')
    tasks=plan['tasks']
    references=read(OUT/'evaluator/REFERENCES.json')
    for path,expected in plan['files'].items():
        assert digest(Path(path))==expected
    budget=ApiBudget(OUT/'BUDGET.json')

    def run(pair):
        model,task=pair
        ident=task['call_id'];key=OUT.name+'/'+model+'/'+ident
        directory=OUT/'captures'/model
        directory.mkdir(exist_ok=True)
        policy=read(OUT/'policy'/(ident+'.json'))
        row={**task,'model':model,'valid':False,'correct':False,'all_fields_correct':False}
        try:
            raw,details=capture(policy['messages'],model,key,directory/ident,budget)
            answer=parse(raw,task['query_ids'],task['reasoning'])
            expected=references[ident]
            row.update(valid=details['ended_with_eos'],answer=answer,details=details)
            row['correct']=row['valid'] and answer['fact_truth']==expected['fact_truth']
            row['all_fields_correct']=row['correct'] and (task['reasoning']=='direct' or answer['slots']==expected['slots'])
        except Exception as exc:
            row['error_type']=type(exc).__name__
        publish(directory/(ident+'.score.json'),row)
        return row

    work=[(model,task) for model in ['deepseek-flash','deepseek-v4-pro'] for task in tasks]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        rows=list(pool.map(run,work))
    publish(OUT/'RESULTS.json',rows)
    groups=defaultdict(Counter)
    for row in rows:
        key=row['model']+'__'+row['representation']+'__'+row['reasoning']
        groups[key].update(n=1,valid=int(row['valid']),correct=int(row['correct']),all_fields_correct=int(row['all_fields_correct']))
    publish(OUT/'COMPLETE.json',{'groups':dict(groups),'planned_calls':len(work),
        'underlying_opportunities':plan['underlying_opportunities'],'budget':read(OUT/'BUDGET.json'),
        'always_unknown_per_model':sum(r['fact_truth']=='unknown' for r in references.values()),
        'independent_reference_agreement':len(tasks),'new_F_calls':0})
    print(json.dumps(dict(groups)),flush=True)


if __name__=='__main__':
    main()
