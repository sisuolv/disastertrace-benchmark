"""Scoped v11 regressions. Network is never used; acquisition outcomes are faked.

The source implementation of annual execute() is unchanged. Its acquire_unit()
network dependency alone is patched to deterministic success/failure receipts.
"""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pytest
from probe_loader import F,T,N,TC,MODE
from test_inherited_controls import row,product,START,DAY,feature_inputs

@pytest.mark.parametrize('case',['max_only','min_invalid','min_only'])
def test_event_probability_does_not_require_unconsumed_variable(case):
    r=row()
    if case=='max_only':
        del r['common']['daily_products'][0]['forecast_min_members_C']
    elif case=='min_invalid':
        r['common']['daily_products'][0]['forecast_min_members_C']=[float('nan')]
    else:
        r=row(variable='daily_min_2m_temperature',operator='lt',threshold=0)
        del r['common']['daily_products'][0]['forecast_max_members_C']
    assert F.temperature_ensemble_probability(r)==0.5
    try:
        other=T.event_probability(r)
    except (ValueError,KeyError) as exc:
        pytest.fail('Unused variable rejects a complete target-specific event: '+repr(exc))
    assert other==0.5

@pytest.mark.parametrize('value',[True,10**400,float('nan'),float('inf')])
def test_both_probability_paths_reject_bad_threshold(value):
    r=row();r['target']['threshold']=value
    for fn in (F.temperature_ensemble_probability,T.event_probability):
        with pytest.raises(ValueError):fn(r)

@pytest.mark.parametrize('raw',['{"probability":'+str(10**400)+'}',
                              '{"probability":1e10000}',
                              '{"probability":NaN}'])
def test_large_nonfinite_response_has_uniform_value_error(raw):
    with pytest.raises(ValueError):F.parse_temperature(raw)

def test_required_max_missing_rejected_in_both_paths():
    r=row();del r['common']['daily_products'][0]['forecast_max_members_C']
    for fn in (F.temperature_ensemble_probability,T.event_probability):
        with pytest.raises(ValueError):fn(r)

def test_common_vector_does_not_access_paid_values():
    target,d,at=feature_inputs()
    a=N.feature_vector(target,None,['q'],{},at=at,mode='common')
    poisoned={'q':{'query_id':'q','unusable_paid_body':'not a decoded report'}}
    b=N.feature_vector(target,None,['q'],poisoned,at=at,mode='common')
    assert a==b and not any(k.startswith('slot') for k in a)

def test_day_index_relation_not_yet_attested_characterization():
    # Diagnosis only: present validators enforce positive index, not origin/date
    # provenance. This does not assert a real archive error or a passed lineage gate.
    r=row();r['common']['initialization']='2018-01-01T00:00:00+00:00'
    r['common']['daily_products'][0]['day_index']=99
    assert F.temperature_ensemble_probability(r)==T.event_probability(r)==0.5

@pytest.fixture
def annual(monkeypatch):
    root=os.getenv('DT_REPO_ROOT')
    path=(Path(root)/'plans/v11_execution_20260915_01/annual_catalogs.py' if root else
          Path(__file__).parent/'sources/annual_catalogs.py')
    if not root:
        b=path.read_bytes()
        assert hashlib.sha1(f'blob {len(b)}\0'.encode()+b).hexdigest()=='d5a51d9eeb7cb03c67e68c2f79515fe0bdbf3ee1'
    spec=importlib.util.spec_from_file_location('_v11_annual_test',path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    for k in ('HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','http_proxy','https_proxy','all_proxy'):
        monkeypatch.delenv(k,raising=False)
    return m

def simulate(annual,tmp_path,monkeypatch,failures):
    units=[f'u{i:02d}' for i in range(72)]
    plan={'units':units,'sample_units':units[:3],'files':{}}
    (tmp_path/'PLAN.json').write_text(json.dumps(plan))
    called=[]
    def fake_acquire(task):
        name=task[2];called.append(name)
        return {'unit':name,'complete':name not in failures}
    monkeypatch.setattr(annual,'acquire_unit',fake_acquire)
    with pytest.raises(SystemExit) as exitinfo:annual.execute(tmp_path,tmp_path)
    return annual.read(tmp_path/'RESULT.json'),called,exitinfo.value.code

def test_failed_sample_is_not_counted_twice(annual,tmp_path,monkeypatch):
    result,called,code=simulate(annual,tmp_path,monkeypatch,{'u01'})
    assert code==1 and set(called)=={'u00','u01','u02'} and len(called)==3
    assert len(result['results'])==3, 'Failed sample was concatenated with itself'
    assert result['completed_units']==2
    assert len(result['not_attempted'])==69

def test_all_annual_units_success_unique(annual,tmp_path,monkeypatch):
    result,called,code=simulate(annual,tmp_path,monkeypatch,set())
    assert code==0 and result['passed']
    assert len(called)==len(set(called))==len(result['results'])==result['completed_units']==72
    assert not result['not_attempted']

def test_failure_after_sample_keeps_other_units(annual,tmp_path,monkeypatch):
    result,called,code=simulate(annual,tmp_path,monkeypatch,{'u10'})
    assert code==1 and not result['passed']
    assert len(called)==len(set(called))==len(result['results'])==72
    assert result['completed_units']==71 and not result['not_attempted']

@pytest.mark.parametrize('year,month,days',[(2023,2,28),(2024,2,29),(2023,12,31)])
def test_month_boundaries(annual,year,month,days):
    a,b=annual.month_bounds(year,month)
    assert (b-a).days==days and b.day==1
