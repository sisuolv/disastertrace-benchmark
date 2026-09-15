"""Offline source/excerpt audit. No network, repository writes, or model execution.
Red tests are desired regression specifications, not failures in the repo's reported 750 tests.
"""
import ast
import contextlib
import copy
import datetime as dt
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = '_dt_v11_review'
pkg = types.ModuleType(PACKAGE)
pkg.__path__ = [str(ROOT/'source')]
sys.modules[PACKAGE] = pkg

def load(name):
    spec = importlib.util.spec_from_file_location(PACKAGE+'.'+name, ROOT/'source'/f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module

contract = load('temperature_contract')
post = load('temperature_postprocess')
common = load('common')
support = load('support')
evidence = load('evidence')

# Execute only these exact functions from the hash-verified complete source.
# This deliberately does not claim to import the entire production package.
selected = {'output_json', 'parse_temperature', 'temperature_ensemble_probability'}
tree = ast.parse((ROOT/'source/feature_tasks.py').read_text())
namespace = {'strict_json':common.strict_json, 'event_values':contract.event_values,
             'finite_number':contract.finite_number}
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in selected],
                        type_ignores=[]), 'exact_feature_tasks_functions', 'exec'), namespace)
raw_probability = namespace['temperature_ensemble_probability']
parse_temperature = namespace['parse_temperature']
DAY=contract.DAY
START=1735689600000000

def row(days=1, variable='daily_max_2m_temperature', op='ge', threshold=30):
    products=[]
    for i in range(days):
        products.append({'target_date':dt.datetime.fromtimestamp((START+i*DAY)/1e6,dt.timezone.utc).date().isoformat(),
                         'day_index':i+1,'forecast_max_members_C':[29,30,31,32],
                         'forecast_min_members_C':[-3,-2,-1,0]})
    return {'target':{'physical_start':START,'physical_end':START+days*DAY,'units':'C',
                     'variable':variable,'event_operator':op,'threshold':threshold},
            'cutoff':START-3600000000,'common':{'daily_products':products}}

def outcome(fn, value):
    try:
        return {'accepted':True, 'probability':fn(value)}
    except Exception as exc:
        return {'accepted':False, 'exception':type(exc).__name__, 'message':str(exc)}

def report(value=None, status='disclosed_product_fact'):
    return {'status':status,'reference_kind':'product_label','support_assumption':'product_exact',
            'visible_information_scope':'policy_after_query',
            'reports':[{'visibility':None if value is None else
                       {'lower':value,'upper':value,'lower_closed':True,'upper_closed':True}}]}

class FakePool:
    def __init__(self,*args,**kwargs): pass
    def __enter__(self): return self
    def __exit__(self,*args): return False
    def map(self,fn,items): return map(fn,items)

OBSERVATIONS={}

def annual_fixture(failed_samples=0, late_fail=None):
    plan={'files':{},'units':[f'm{i:02}' for i in range(72)],'sample_units':['m00','m01','m02']}
    saved={}
    called=[]
    def acquire(task):
        unit=task[-1]; called.append(unit)
        failed=unit in plan['sample_units'][:failed_samples] or unit==late_fail
        return {'unit':unit,'complete':not failed}
    ns={'write':lambda path,value:saved.__setitem__(path.name,copy.deepcopy(value)),
        'read':lambda path:plan,'digest':lambda p:'unused','os':types.SimpleNamespace(getpid=lambda:0,environ={}),
        'dt':dt,'ThreadPoolExecutor':FakePool,'acquire_unit':acquire}
    exec((ROOT/'excerpts/annual_execute.py').read_text(),ns)
    with contextlib.redirect_stdout(io.StringIO()):
        try: ns['execute'](Path('/mock/out'),Path('/mock/repo'))
        except SystemExit as exc: code=exc.code
    return {'summary':saved['RESULT.json'],'calls':called,'exit':code}

def audit_fixture(states,failed=False):
    card={'case':'fixture','arms':['M']}
    plan={'cases':[card]}
    complete=[{'case':'fixture','arm':'M','state':'failed' if failed else 'completed'}]
    saved={}
    rows=[{'threshold':1000,'arm':'M','week':'synthetic-week','e_status':s,'loss':.25,'outcome':i%2}
          for i,s in enumerate(states)]
    def read(path):
        if path.name=='PLAN.json':return plan
        return {'results':complete if path.name=='COMPLETE_0.json' else []}
    ns={'read':read,'publish':lambda p,v:saved.__setitem__(p.name,copy.deepcopy(v)),
        'ProcessPoolExecutor':FakePool,'audit_case':lambda task:rows,'defaultdict':defaultdict,
        'math':math,'dt':dt,'digest':lambda p:'mock-row-hash','json':json}
    exec((ROOT/'excerpts/fullweek_audit.py').read_text(),ns)
    with contextlib.redirect_stdout(io.StringIO()): ns['audit'](Path('/mock/out'),1)
    return saved['RESULT.json']['metrics']['1000__all__M']

class ValidTemperature(unittest.TestCase):
    def assert_rejects_both(self,r):
        for fn in (raw_probability,post.event_probability):
            self.assertFalse(outcome(fn,r)['accepted'])
    def test_daily_max_match(self):
        r=row(); self.assertEqual(raw_probability(r),.75); self.assertEqual(post.event_probability(r),.75)
    def test_daily_min_match(self):
        r=row(variable='daily_min_2m_temperature',op='lt',threshold=0)
        self.assertEqual(raw_probability(r),.75);self.assertEqual(post.event_probability(r),.75)
    def test_three_day_member_path(self):
        r=row(3,'min_of_3_daily_max_2m_temperature')
        r['common']['daily_products'][1]['forecast_max_members_C']=[31,29,31,31]
        r['common']['daily_products'][2]['forecast_max_members_C']=[31,31,29,31]
        self.assertEqual(raw_probability(r),.25);self.assertEqual(post.event_probability(r),.25)
    def test_three_day_ice_match(self):
        r=row(3,'max_of_3_daily_max_2m_temperature',op='lt',threshold=0)
        for p in r['common']['daily_products']:p['forecast_max_members_C']=[-2,-1,0,1]
        self.assertEqual(raw_probability(r),.5);self.assertEqual(post.event_probability(r),.5)
    def test_nonmidnight_rejected(self):
        r=row();r['target']['physical_start']+=DAY//2;r['target']['physical_end']+=DAY//2;self.assert_rejects_both(r)
    def test_duplicate_day_rejected(self):
        r=row();r['common']['daily_products']*=2;self.assert_rejects_both(r)
    def test_nan_threshold_rejected(self):
        r=row();r['target']['threshold']=float('nan');self.assert_rejects_both(r)
    def test_bool_threshold_rejected(self):
        r=row();r['target']['threshold']=True;self.assert_rejects_both(r)
    def test_huge_threshold_rejected(self):
        r=row();r['target']['threshold']=10**400;self.assert_rejects_both(r)
    def test_empty_required_array_rejected(self):
        r=row();r['common']['daily_products'][0]['forecast_max_members_C']=[];self.assert_rejects_both(r)
    def test_infinite_member_rejected(self):
        r=row();r['common']['daily_products'][0]['forecast_max_members_C'][0]=float('inf');self.assert_rejects_both(r)
    def test_bool_member_rejected(self):
        r=row();r['common']['daily_products'][0]['forecast_max_members_C'][0]=False;self.assert_rejects_both(r)
    def test_cutoff_equal_start_rejected(self):
        r=row();r['cutoff']=START;self.assert_rejects_both(r)
    def test_day0_rejected(self):
        r=row();r['common']['daily_products'][0]['day_index']=0;self.assert_rejects_both(r)
    def test_required_dimension_mismatch_rejected(self):
        r=row(3,'min_of_3_daily_max_2m_temperature');r['common']['daily_products'][1]['forecast_max_members_C']=[32];self.assert_rejects_both(r)
    def test_ecc_full_product_still_requires_min(self):
        r=row();del r['common']['daily_products'][0]['forecast_min_members_C']
        with self.assertRaises(KeyError):post.ecc_products(r['common']['daily_products'],{})
    def test_same_common_member_permutation_invariance(self):
        r=row(3,'min_of_3_daily_max_2m_temperature');expected=raw_probability(r)
        for p in r['common']['daily_products']:
            for key in ('forecast_min_members_C','forecast_max_members_C'):p[key]=list(reversed(p[key]))
        self.assertEqual(raw_probability(r),expected);self.assertEqual(post.event_probability(r),expected)

class StrictResponses(unittest.TestCase):
    def test_huge_probability_rejected(self):
        with self.assertRaises(ValueError):parse_temperature('{"probability":'+str(10**400)+'}')
    def test_duplicate_response_key_rejected(self):
        with self.assertRaises(ValueError):parse_temperature('{"probability":0.1,"probability":0.2}')
    def test_nan_probability_rejected(self):
        with self.assertRaises(ValueError):parse_temperature('{"probability":NaN}')
    def test_valid_probability_fence(self):
        self.assertEqual(parse_temperature('```json\n{"probability":0.25}\n```'),(.25,{'whole_json_fence':True}))

class ExistingEvidenceAndAudit(unittest.TestCase):
    def test_true_witness_with_unknown(self):
        self.assertEqual(evidence.exists_report_support(['a','b'],{'a':report(500)},1000),'supported')
    def test_negative_with_unread_not_refuted(self):
        self.assertEqual(evidence.exists_report_support(['a','b'],{'a':report(5000)},1000),'undetermined')
    def test_all_negative(self):
        self.assertEqual(evidence.exists_report_support(['a','b'],{'a':report(5000),'b':report(5000)},1000),'refuted')
    def test_conflict(self):
        self.assertEqual(evidence.exists_report_support(['a'],{'a':report(status='inconsistent_same_slot_facts')},1000),'inconsistent')
    def test_fullweek_brier_control_unchanged(self):
        result=audit_fixture(['supported','refuted','undetermined','inconsistent'])
        self.assertEqual(result['brier'],.25);self.assertEqual(result['registered'],4)
    def test_failed_arm_not_declared_complete(self):
        with self.assertRaises(ValueError):audit_fixture(['refuted'],failed=True)
    def test_annual_all_samples_pass(self):
        o=annual_fixture();self.assertEqual(o['summary']['completed_units'],72);self.assertTrue(o['summary']['passed'])
        self.assertEqual(len(set(o['calls'])),72);self.assertEqual(len(o['calls']),72)
    def test_annual_later_failure_is_not_duplicate(self):
        o=annual_fixture(late_fail='m20');self.assertEqual(o['summary']['completed_units'],71)
        self.assertFalse(o['summary']['passed']);self.assertEqual(len(o['summary']['results']),72)

class NewRegressionSpecifications(unittest.TestCase):
    def test_fullweek_positive_support_is_counted(self):
        states=[evidence.exists_report_support(['a'],{'a':report(500)},1000),
                evidence.exists_report_support(['a'],{'a':report(5000)},1000),
                'undetermined','inconsistent']
        observed=audit_fixture(states);OBSERVATIONS['E_status_count']={'actual_states':states,'observed':observed,'expected_determined':2}
        self.assertEqual(observed['e_determined'],2,'supported is omitted by entailed/refuted test')
    def test_failed_sample_roster_is_unique(self):
        o=annual_fixture(failed_samples=1);OBSERVATIONS['annual_sample_failure']=o
        self.assertEqual(len(o['summary']['results']),len(set(r['unit'] for r in o['summary']['results'])),
                         'sample+sample duplicates three receipts when the sample gate fails')
    def test_raw_max_only_probability_entrypoints_agree(self):
        r=row();del r['common']['daily_products'][0]['forecast_min_members_C']
        a,b=outcome(raw_probability,r),outcome(post.event_probability,r)
        OBSERVATIONS['max_only_raw_probability']={'feature_tasks':a,'temperature_postprocess':b}
        self.assertEqual(a,b,'raw max event should not inconsistently depend on unused minimum field')

if __name__=='__main__':
    class Recorded(unittest.TextTestResult):
        def __init__(self,*a,**k):super().__init__(*a,**k);self.records=[]
        def addSuccess(self,test):super().addSuccess(test);self.records.append({'id':test.id(),'status':'passed'})
        def addFailure(self,test,err):super().addFailure(test,err);self.records.append({'id':test.id(),'status':'failed','detail':self._exc_info_to_string(err,test)})
        def addError(self,test,err):super().addError(test,err);self.records.append({'id':test.id(),'status':'error','detail':self._exc_info_to_string(err,test)})
    suite=unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    with (ROOT/'results/TEST_LOG.txt').open('w') as stream:
        r=unittest.TextTestRunner(stream=stream,verbosity=2,resultclass=Recorded).run(suite)
    result={'commit':'889620a4fc4ee6ad70757dd3e832a40c7509126a','tests_run':r.testsRun,
            'passed':r.testsRun-len(r.failures)-len(r.errors),'failures':len(r.failures),'errors':len(r.errors),
            'observations':OBSERVATIONS,'cases':r.records,
            'scope':'CPU-only: complete verified modules, exact AST functions, two source function excerpts with mocked IO/executors. No FormalSession/native-weather replay, network, model, or complete 750-test run.',
            'repo_modified':False,'upstream_reported_tests_not_rerun':750,
            'fixtures_are_synthetic_not_scientific_results':True}
    (ROOT/'results/LOCAL_VALIDATION.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({k:result[k] for k in ('tests_run','passed','failures','errors')},ensure_ascii=False))
    print(json.dumps(OBSERVATIONS,indent=2))
    sys.exit(0 if r.wasSuccessful() else 1)
