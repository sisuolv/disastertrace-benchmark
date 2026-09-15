"""Small, network-free observations, kept separate from weather experiment results."""
import copy
import hashlib
import importlib.util
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
from probe_loader import F,T,TC,MODE,CHECKS,SHA
from test_inherited_controls import row


def observe(fn,r):
    try:return {'accepted':True,'probability':fn(r)}
    except Exception as exc:return {'accepted':False,'exception':type(exc).__name__,'message':str(exc)}

results={'commit':SHA,'execution_mode':MODE,'synthetic_only':True,'temperature':{}}
for scenario in ('complete','max_only','unconsumed_min_missing','shifted_day','duplicate_day','wrong_day_index'):
    r=row()
    if scenario=='max_only':del r['common']['daily_products'][0]['forecast_min_members_C']
    if scenario=='unconsumed_min_missing':r['common']['daily_products'][0]['forecast_min_members_C']=[None]
    if scenario=='shifted_day':
        r['target']['physical_start']+=TC.DAY//2;r['target']['physical_end']+=TC.DAY//2
    if scenario=='duplicate_day':r['common']['daily_products'].append(copy.deepcopy(r['common']['daily_products'][0]))
    if scenario=='wrong_day_index':
        r['common']['initialization']='2018-01-01T00:00:00+00:00'
        r['common']['daily_products'][0]['day_index']=99
    results['temperature'][scenario]={
        'feature_tasks':observe(F.temperature_ensemble_probability,r),
        'postprocess':observe(T.event_probability,r)}
path=Path(__file__).parent/'sources/annual_catalogs.py'
b=path.read_bytes();blob=hashlib.sha1(f'blob {len(b)}\0'.encode()+b).hexdigest()
assert blob=='d5a51d9eeb7cb03c67e68c2f79515fe0bdbf3ee1'
spec=importlib.util.spec_from_file_location('_annual_diagnostic',path)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
with tempfile.TemporaryDirectory() as d:
    d=Path(d);units=[f'u{i:02d}' for i in range(72)]
    (d/'PLAN.json').write_text(json.dumps({'units':units,'sample_units':units[:3],'files':{}}))
    actual=[]
    def fake(task):
        name=task[2];actual.append(name);return {'unit':name,'complete':name!='u01'}
    with patch.object(m,'acquire_unit',fake):
        try:m.execute(d,d)
        except SystemExit as e:exit_code=e.code
    result=m.read(d/'RESULT.json')
    results['annual_sample_failure']={'actual_calls':len(actual),'actual_unique_units':len(set(actual)),
        'actual_success_units':2,'summary_rows':len(result['results']),
        'summary_completed_units':result['completed_units'],'not_attempted':len(result['not_attempted']),
        'passed':result['passed'],'exit_code':exit_code,'results':result['results'],
        'network_used':False,'current_published_sample_gate':'reported passed; this failed branch was not established on current run'}
Path(__file__).with_name('DIAGNOSTICS.json').write_text(json.dumps(results,indent=2,ensure_ascii=False)+'\n')
checks=CHECKS+[{'name':'annual_catalogs','git_blob_sha1':blob,'expected':blob,
               'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b),'matched':True}]
Path(__file__).with_name('SOURCE_HASH_VERIFICATION.json').write_text(json.dumps({'commit':SHA,'mode':MODE,'files':checks},indent=2)+'\n')
print(json.dumps(results,indent=2,ensure_ascii=False))
