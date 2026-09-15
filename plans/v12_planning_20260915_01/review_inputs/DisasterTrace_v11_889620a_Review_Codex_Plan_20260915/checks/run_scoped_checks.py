"""Offline checks of three byte-verified upstream modules.

No repository-wide test, scientific-file replay, model call, or production C2
compiler execution is claimed. The candidate-pool filter is a deliberately
labelled minimal reproducer of the selection order read in build_native_v2.py
and prepare_c2.py. Fixtures below are synthetic, not weather observations.
"""
from __future__ import annotations
import copy
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'upstream'))
from disastertrace.monitoring_v1.temperature_contract import DAY, event_values
from disastertrace.monitoring_v1.targets import utc_us
from disastertrace.monitoring_v1.providers.versions import current_taf

EXPECTED = {
 'temperature_contract.py': '5d46a2c8705d9cc92618bd082431be2c5c9124a9',
 'providers/versions.py': '847668671020990cf44f694d9ea536e689ba8d8a',
 'targets.py': 'df3862303f5ec9b28ab4c20969b88861ed06bf74',
}
root = HERE / 'upstream/disastertrace/monitoring_v1'
for name, expected in EXPECTED.items():
    data = (root/name).read_bytes()
    assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest() == expected

rows = []
def check(name, fn, kind='existing_guard'):
    try:
        detail = fn()
        rows.append({'check':name,'passed':True,'kind':kind,'detail':detail})
    except Exception as exc:
        rows.append({'check':name,'passed':False,'kind':kind,'error':repr(exc)})

def equal(actual, expected):
    assert actual == expected, (actual,expected)
    return {'actual':actual,'expected':expected}

def rejected(fn):
    try: fn()
    except ValueError as exc: return {'rejected':True,'type':'ValueError','message':str(exc)}
    raise AssertionError('Invalid synthetic fixture accepted')

start = utc_us('2025-01-02T00:00:00Z')
row = {'cutoff': start-DAY//2, 'target': {'units':'C','physical_start':start,
 'physical_end':start+DAY, 'variable':'daily_max_2m_temperature',
 'event_operator':'ge','threshold':30}}
products = [{'target_date':'2025-01-02','day_index':1,'forecast_max_members_C':[31.,29.]}]
check('T01_max_only_does_not_require_unused_min_field', lambda: equal(event_values(row,products),[[31.,29.]]))
r=copy.deepcopy(row);r['target']['variable']='daily_min_2m_temperature';r['target']['threshold']=0
check('T02_negative_minimum_is_legal',lambda: equal(event_values(r,[{'target_date':'2025-01-02','day_index':1,'forecast_min_members_C':[-5.,2.]}]),[[-5.,2.]]))

def bad_row(key,value):
    r=copy.deepcopy(row)
    (r if key=='cutoff' else r['target'])[key]=value
    return rejected(lambda:event_values(r,products))
check('T03_nonmidnight_start_rejected',lambda:bad_row('physical_start',start+1))
check('T04_late_cutoff_rejected',lambda:bad_row('cutoff',start))
check('T05_boolean_threshold_rejected',lambda:bad_row('threshold',True))
check('T06_wrong_duration_rejected',lambda:bad_row('physical_end',start+2*DAY))
check('T07_unqualified_variable_rejected',lambda:bad_row('variable','other_temperature'))
for name,value in [('T08_boolean_member_rejected',True),('T09_NaN_member_rejected',float('nan')),('T10_huge_integer_member_rejected',10**400)]:
    def test(value=value):
        p=copy.deepcopy(products);p[0]['forecast_max_members_C'][0]=value
        return rejected(lambda:event_values(row,p))
    check(name,test)
check('T11_duplicate_dates_rejected',lambda:rejected(lambda:event_values(row,products+products)))
p0=copy.deepcopy(products);p0[0]['day_index']=0
check('T12_day_zero_rejected',lambda:rejected(lambda:event_values(row,p0)))
check('T13_missing_requested_date_rejected',lambda:rejected(lambda:event_values(row,[{'target_date':'2025-01-03','day_index':2,'forecast_max_members_C':[1.,2.]}])))
r3=copy.deepcopy(row);r3['target']['physical_end']=start+3*DAY;r3['target']['variable']='min_of_3_daily_max_2m_temperature'
p3=[{'target_date':f'2025-01-0{d}','day_index':d-1,'forecast_max_members_C':[40.,20.]} for d in (2,3,4)]
pbad=copy.deepcopy(p3);pbad[1]['forecast_max_members_C'].append(10.)
check('T14_member_shape_mismatch_rejected',lambda:rejected(lambda:event_values(r3,pbad)))
def lineage_scope():
    a=event_values(r3,p3)
    b=copy.deepcopy(p3);b[1]['forecast_max_members_C'].reverse();c=event_values(r3,b)
    probability=lambda z:sum(all(v>=30 for v in path) for path in zip(*z,strict=True))/len(z[0])
    pa,pb=probability(a),probability(c)
    assert pa==0.5 and pb==0.0
    return {'aligned_member_paths':pa,'one_day_permuted_paths':pb,
      'interpretation':'Known scope limit: shape checking cannot certify source member identity; not proof actual data are misaligned.'}
check('T15_shape_is_not_member_lineage',lineage_scope,'documented_scope_limit')

H=3_600_000_000
base=utc_us('2025-01-01T00:00:00Z')
def product(sid,issue,lo,hi,semantic):
    return {'source_id':sid,'station':'KTEST','issued_at':base+issue*H,
      'valid_start':base+lo*H,'valid_end':base+hi*H,
      'status':'active','native_semantics_sha256':semantic}
old=product('old',0,0,24,'old_semantics')
new=product('new_short',6,6,12,'new_semantics')
kwargs={'station':'KTEST','cutoff':base+10*H,'start':base+15*H,'end':base+16*H}
def projectable_pool(pool):
    # Minimal selection-order reproducer; not a replacement TAF parser.
    return [p for p in pool if p['status']=='active' and p['valid_start']<=kwargs['start']<kwargs['end']<=p['valid_end']]
check('V01_core_latest_before_coverage',lambda:equal(current_taf([old,new],**kwargs)['status'],'current_version_does_not_cover_target'))
def lost_version():
    full=current_taf([old,new],**kwargs);filtered=current_taf(projectable_pool([old,new]),**kwargs)
    assert full['selected_id']=='new_short' and filtered['selected_id']=='old'
    return {'full_directory':full,'projectable_candidate_pool':filtered,
       'scope':'Real current_taf on synthetic metadata; selection-order reproducer, not execution of the complete data compiler.'}
check('V02_projectable_pool_hides_new_noncovering_version',lost_version,'confirmed_selection_boundary')
full_new=product('new_full',6,6,24,'different_semantics')
check('V03_core_retains_same_issue_conflict',lambda:equal(current_taf([new,full_new],**kwargs)['status'],'conflict'))
def lost_conflict():
    full=current_taf([new,full_new],**kwargs);filtered=current_taf(projectable_pool([new,full_new]),**kwargs)
    assert full['status']=='conflict' and filtered['status']=='active'
    return {'full_directory':full,'projectable_candidate_pool':filtered}
check('V04_projectable_pool_hides_same_issue_conflict',lost_conflict,'confirmed_selection_boundary')
mirror=copy.deepcopy(full_new);mirror['source_id']='another_alias'
check('V05_equivalent_mirrors_keep_semantics',lambda:equal(current_taf([full_new,mirror],**kwargs)['source_ids'],['another_alias','new_full']))
check('V06_future_issue_not_yet_legal',lambda:equal(current_taf([old,new],**{**kwargs,'cutoff':base+6*H})['selected_id'],'old'))

result={'reviewed_commit':'889620a4fc4ee6ad70757dd3e832a40c7509126a',
 'scope':'Three Git-blob-verified upstream modules, synthetic fixtures only',
 'checks':rows,'total':len(rows),'passed':sum(r['passed'] for r in rows),
 'model_calls':0,'scientific_downloads':0,'repository_test_suite_rerun':False,
 'production_C2_compiler_executed':False,'actual_72_prefix_impact_recomputed':False}
(HERE/'SCOPED_RESULTS.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='checks'},ensure_ascii=False,indent=2))
for r in rows:
    print(('PASS' if r['passed'] else 'FAIL'),r['check'])
if result['passed']!=result['total']: raise SystemExit(1)
