"""Offline reviewer checks of exact pinned source files; no models or network.

Full imports: temperature_contract, temperature_postprocess, support.
AST-extracted unchanged functions: temperature_ensemble_probability;
validate_claims, feature_vector, predict_features. Raw METAR/TAF parsers,
formal runners, persisted logs and remote backends are NOT exercised.
"""
import ast,copy,hashlib,importlib.util,json,math,sys,types,unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parent; SRC=ROOT/'source'
BINDINGS=json.loads((ROOT/'SOURCE_BINDINGS.json').read_text())
for r in BINDINGS:
 b=(SRC/r['path']).read_bytes()
 assert hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==r['expected_git_blob']
pkg=types.ModuleType('reviewed');pkg.__path__=[str(SRC)];sys.modules['reviewed']=pkg

def module(name):
 spec=importlib.util.spec_from_file_location('reviewed.'+name,SRC/(name+'.py'))
 m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m);return m
C=module('temperature_contract');T=module('temperature_postprocess');S=module('support')

def extracted(filename,names,extra):
 tree=ast.parse((SRC/filename).read_text())
 selected=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name in names]
 assert len(selected)==len(names)
 env={'__name__':'reviewed.extracted','__package__':'reviewed',**extra}
 exec(compile(ast.Module(body=selected,type_ignores=[]),str(SRC/filename),'exec'),env)
 return env

F=extracted('feature_tasks.py',{'temperature_ensemble_probability'}, {'event_values':C.event_values})
def untested(*a,**kw):raise AssertionError('Provider parser is outside this reviewer scope')
def interval(d):
 def bound(x):return math.inf if x=='+inf' else -math.inf if x=='-inf' else x
 return S.Interval(bound(d['lower']),bound(d['upper']),d.get('lower_closed',True),d.get('upper_closed',True))
N=extracted('native_feature_forecast.py',{'validate_claims','feature_vector','predict_features'},
 {'math':math,'datetime':datetime,'timezone':timezone,'HOUR':3600_000_000,
  'FEATURE_VERSION':'native_h15_features.v1','interval_from_dict':interval,
  'native_claims':untested,'parse_taf':untested,'taf_features':untested})
raw=F['temperature_ensemble_probability'];post=T.event_probability
START=int(datetime(2020,1,2,tzinfo=timezone.utc).timestamp()*1e6);DAY=C.DAY

def row(variable='daily_max_2m_temperature',operator='ge',threshold=30):
 days=3 if '_3_' in variable else 1
 ps=[]
 for i in range(days):
  ps.append({'target_date':(datetime(2020,1,2)+timedelta(days=i)).date().isoformat(),
             'day_index':i+1,'forecast_max_members_C':[31.,29.],
             'forecast_min_members_C':[-1.,1.]})
 return {'target':{'units':'C','variable':variable,'physical_start':START,
   'physical_end':START+days*DAY,'threshold':threshold,'event_operator':operator},
   'cutoff':START-3600_000_000,'common':{'daily_products':ps}}

def claim(upper=1000,closed=True):
 return {'q1':{'visibility':{'lower':0,'upper':upper,'lower_closed':True,'upper_closed':closed},
               'temperature_c':3.,'dewpoint_c':-2.}}
TARGET={'physical_start':START,'physical_end':START+3600_000_000,'entity':'station:KZZZ'}
AT=START-3600_000_000
DISC={'q1':{'status':'disclosed_product_fact','reports':[{'observation_time':AT-1800_000_000}]}}
def features(claims,mode='values',disc=None):
 return N['feature_vector'](TARGET,None,['q1'],DISC if disc is None else disc,at=AT,mode=mode,claims=claims)

class Checks(unittest.TestCase):
 def test_daily_max_ge(self):self.assertEqual(raw(row()),.5);self.assertEqual(post(row()),.5)
 def test_daily_max_lt(self):self.assertEqual(raw(row(operator='lt')),.5);self.assertEqual(post(row(operator='lt')),.5)
 def test_daily_min_ge(self):self.assertEqual(raw(row('daily_min_2m_temperature',threshold=0)),.5)
 def test_daily_min_lt(self):self.assertEqual(post(row('daily_min_2m_temperature','lt',0)),.5)
 def test_three_day_same_member(self):
  r=row('min_of_3_daily_max_2m_temperature');self.assertEqual(raw(r),.5);self.assertEqual(post(r),.5);self.assertNotEqual(raw(r),.5**3)
 def test_three_day_ice(self):
  r=row('max_of_3_daily_max_2m_temperature','lt',0)
  for p in r['common']['daily_products']:p['forecast_max_members_C']=[-1,1]
  self.assertEqual(raw(r),.5);self.assertEqual(post(r),.5)
 def test_threshold_equality(self):
  r=row(threshold=31);self.assertEqual(raw(r),.5);r['target']['event_operator']='lt';self.assertEqual(post(r),.5)
 def test_negative_temperature_allowed(self):
  r=row(threshold=-10);r['common']['daily_products'][0]['forecast_max_members_C']=[-20,-5];self.assertEqual(raw(r),.5)
 def test_date_order_invariant(self):
  r=row('min_of_3_daily_max_2m_temperature');a=raw(r);r['common']['daily_products'].reverse();self.assertEqual(raw(r),a);self.assertEqual(post(r),a)
 def test_probability_input_unmodified(self):
  r=row();b=copy.deepcopy(r);raw(r);post(r);self.assertEqual(r,b)
 def test_relevant_max_only_contract(self):
  r=row();del r['common']['daily_products'][0]['forecast_min_members_C'];self.assertEqual(raw(r),.5)
 def test_ecc_does_not_mutate(self):
  ps=row()['common']['daily_products'];before=copy.deepcopy(ps)
  bank={v:{'a':0,'b':1,'log_c':-10,'log_d':0} for v in ('min','max')}
  converted,trace=T.ecc_products(ps,bank);self.assertEqual(ps,before);self.assertEqual(trace['member_day_pairs'],2);self.assertFalse(trace['joint_calibration_guarantee'])
 def test_ecc_repair_logged(self):
  ps=row()['common']['daily_products'];bank={'min':{'a':50,'b':0,'log_c':0,'log_d':-10},'max':{'a':-50,'b':0,'log_c':0,'log_d':-10}}
  converted,trace=T.ecc_products(ps,bank);self.assertEqual(trace['minmax_projections'],2)
  self.assertTrue(all(a<=b for a,b in zip(converted[0]['forecast_min_members_C'],converted[0]['forecast_max_members_C'])))
 def test_visibility_positive_infinite_upper_allowed(self):N['validate_claims'](claim('+inf'),DISC)
 def test_visibility_missing_allowed(self):
  a=claim();a['q1']['visibility']=None;N['validate_claims'](a,DISC)
 def test_visibility_infinite_lower_rejected(self):
  a=claim('+inf');a['q1']['visibility']['lower']='+inf'
  with self.assertRaises(ValueError):N['validate_claims'](a,DISC)
 def test_visibility_negative_lower_rejected(self):
  a=claim();a['q1']['visibility']['lower']=-1
  with self.assertRaises(ValueError):N['validate_claims'](a,DISC)
 def test_visibility_invalid_endpoint_type(self):
  a=claim();a['q1']['visibility']['upper_closed']=1
  with self.assertRaises(ValueError):N['validate_claims'](a,DISC)
 def test_claims_huge_integer_rejected(self):
  a=claim();a['q1']['temperature_c']=10**400
  with self.assertRaises(ValueError):N['validate_claims'](a,DISC)
 def test_claims_bool_rejected(self):
  a=claim();a['q1']['temperature_c']=True
  with self.assertRaises(ValueError):N['validate_claims'](a,DISC)
 def test_claims_unregistered_slot_rejected(self):
  with self.assertRaises(ValueError):N['validate_claims'](claim(),{})
 def test_common_ignores_paid_claims(self):
  a=features(claim(),mode='common');b=features(claim(9000),mode='common');self.assertEqual(a,b);self.assertFalse(any(k.startswith('slot') for k in a))
 def test_mask_age_ignores_numbers(self):self.assertEqual(features(claim(),mode='mask_age'),features(claim(9000),mode='mask_age'))
 def test_values_use_numbers(self):self.assertNotEqual(features(claim()),features(claim(9000)))
 def test_future_target_rejected(self):
  with self.assertRaises(ValueError):N['feature_vector'](TARGET,None,['q1'],DISC,at=START,claims=claim())
 def test_future_observation_rejected(self):
  d=copy.deepcopy(DISC);d['q1']['reports'][0]['observation_time']=START
  with self.assertRaises(ValueError):features(claim(),disc=d)
 def test_threshold_cdf_coherence(self):
  bank={'feature_version':'native_h15_features.v1','feature_names':[], 'mean':[],'scale':[], 'coefficients':[[],[],[]],'intercepts':[0.,1.,2.],'mapping_version':'synthetic'}
  p=N['predict_features'](bank,{})
  self.assertTrue(0<=p['1000']<=p['5000']<=1);self.assertAlmostEqual(sum(p['classes']),1)

def invalid_test(change):
 def test(self):
  r=row();change(r)
  for fn in (raw,post):
   with self.subTest(function=fn.__name__):
    with self.assertRaises(ValueError):fn(r)
 return test
mutations={
 'midday_window':lambda r:r['target'].update(physical_start=START+DAY//2,physical_end=START+DAY+DAY//2),
 'cutoff_at_start':lambda r:r.update(cutoff=START),
 'float_cutoff':lambda r:r.update(cutoff=float(AT)),
 'bool_start':lambda r:r['target'].update(physical_start=True),
 'nonpositive_window':lambda r:r['target'].update(physical_end=START),
 'two_day_daily':lambda r:r['target'].update(physical_end=START+2*DAY),
 'wrong_units':lambda r:r['target'].update(units='K'),
 'unknown_variable':lambda r:r['target'].update(variable='unspecified'),
 'nan_threshold':lambda r:r['target'].update(threshold=float('nan')),
 'huge_threshold':lambda r:r['target'].update(threshold=10**400),
 'bool_threshold':lambda r:r['target'].update(threshold=True),
 'bad_operator':lambda r:r['target'].update(event_operator='gt'),
 'duplicate_date':lambda r:r['common']['daily_products'].append(copy.deepcopy(r['common']['daily_products'][0])),
 'day0':lambda r:r['common']['daily_products'][0].update(day_index=0),
 'bool_day_index':lambda r:r['common']['daily_products'][0].update(day_index=True),
 'empty_members':lambda r:r['common']['daily_products'][0].update(forecast_max_members_C=[]),
 'nan_member':lambda r:r['common']['daily_products'][0].update(forecast_max_members_C=[float('nan'),1]),
 'bool_member':lambda r:r['common']['daily_products'][0].update(forecast_max_members_C=[True,1]),
 'missing_day':lambda r:r['common']['daily_products'][0].update(target_date='2020-01-03'),
}
for name,change in mutations.items():setattr(Checks,'test_reject_'+name,invalid_test(change))

class Recorded(unittest.TextTestResult):
 def __init__(self,*a,**k):super().__init__(*a,**k);self.checks=[]
 def addSuccess(self,t):super().addSuccess(t);self.checks.append({'test':t.id(),'status':'passed'})
 def addFailure(self,t,e):super().addFailure(t,e);self.checks.append({'test':t.id(),'status':'failed'})
 def addError(self,t,e):super().addError(t,e);self.checks.append({'test':t.id(),'status':'error'})

def attempt(fn,r):
 try:return {'accepted':True,'probability':fn(r)}
 except Exception as e:return {'accepted':False,'error':type(e).__name__,'message':str(e)}

def probes():
 ps=[]
 r=row();del r['common']['daily_products'][0]['forecast_min_members_C']
 ps.append({'id':'TEMP_MAX_ONLY','scope':'source functions, not production adapter','feature_tasks':attempt(raw,r),'postprocess':attempt(post,r)})
 r=row();r['common']['daily_products'][0]['forecast_min_members_C']=[float('nan'),1]
 ps.append({'id':'TEMP_UNUSED_MIN_NAN','feature_tasks':attempt(raw,r),'postprocess':attempt(post,r)})
 r=row('min_of_3_daily_max_2m_temperature')
 for p in r['common']['daily_products']:p['member_ids']=['A','B']
 before=raw(r);r['common']['daily_products'][1]['member_ids']=['B','A'];r['common']['daily_products'][1]['forecast_max_members_C']=[29.,31.]
 ps.append({'id':'MEMBER_LINEAGE','before':before,'after_semantically_equivalent_reordering':raw(r),'same_physical_member_paths_expected':.5,
            'scope':'extra identity metadata is not consumed by these numerical helpers; actual source misalignment NOT established'})
 open_c,closed_c=claim(1000,False),claim(1000,True)
 a,b=features(open_c),features(closed_c)
 ps.append({'id':'ENDPOINT_INFORMATION_LOSS','open_E':S.classify(interval(open_c['q1']['visibility']),'lt',1000),
  'closed_E':S.classify(interval(closed_c['q1']['visibility']),'lt',1000),'features_identical':a==b,
  'scope':'explicit hypothetical claims with candidate=None; not evidence of a captured METAR at this endpoint; no production session run'})
 return ps

if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=1,resultclass=Recorded).run(unittest.defaultTestLoader.loadTestsFromTestCase(Checks))
 report={'commit':'889620a4fc4ee6ad70757dd3e832a40c7509126a','tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skips':len(result.skipped),'checks':result.checks,
 'scope':__doc__,'no_model_calls':True,'no_network':True,'source_bindings':BINDINGS}
 (ROOT/'LOCAL_TEST_RESULTS.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
 data=probes();(ROOT/'BOUNDARY_PROBES.json').write_text(json.dumps(data,ensure_ascii=False,indent=2))
 print(json.dumps(data,ensure_ascii=False,indent=2));sys.exit(not result.wasSuccessful())
