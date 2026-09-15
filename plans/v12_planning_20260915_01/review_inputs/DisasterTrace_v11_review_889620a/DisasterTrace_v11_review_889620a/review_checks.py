"""Bounded offline review of hash-verified v11 source files.

Uses actual ApiLedger/capture functions and real temporary local files. HTTP,
clock, and spool helper imports are test substitutes; no model/provider call is
made. Feature extraction is NOT exercised: its unused validate_claims import is
an explicit raising stub. This is not a full repository/capsule replay.
"""
from __future__ import annotations
import argparse, copy, hashlib, importlib.util, json, os, sys, tempfile, types
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

ROOT=Path(__file__).resolve().parent
SRC=ROOT/'verified_sources'
_parser=argparse.ArgumentParser(description=__doc__)
_parser.add_argument('--result',type=Path,required=True,help='Fresh result JSON path; existing files are never overwritten')
_args=_parser.parse_args()
if _args.result.exists(): raise FileExistsError(_args.result)
SHA={r['file']:r['expected'] for r in json.loads((ROOT/'SOURCE_IDENTITIES.json').read_text())}
verified={}
for f,h in SHA.items():
 b=(SRC/f).read_bytes(); got=hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
 if got!=h: raise RuntimeError(f'Source identity mismatch: {f}')
 verified[f]={'git_blob':got,'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)}

for name in ['review_pkg','review_pkg.forecast_task','review_pkg.monitoring_v1']:
 m=types.ModuleType(name);m.__path__=[];sys.modules[name]=m

def load(name,file):
 spec=importlib.util.spec_from_file_location(name,SRC/file)
 m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
common=load('review_pkg.forecast_task.common','common.py')
stub=types.ModuleType('review_pkg.monitoring_v1.native_feature_forecast')
def not_used(*args,**kwargs): raise AssertionError('Feature extraction not under test')
stub.validate_claims=not_used;sys.modules[stub.__name__]=stub
# Transport helpers are substitutes (documented), not a full production spool.
spool=types.ModuleType('review_pkg.monitoring_v1.spool_backend')
def publish(path,value):
 path=Path(path)
 with path.open('x',encoding='utf-8') as f:
  json.dump(value,f,sort_keys=True,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
spool.publish=publish;spool.digest=common.digest;spool.read=common.read
sys.modules[spool.__name__]=spool
rates=types.ModuleType('review_pkg.monitoring_v1.api_capture')
rates.RATES={'deepseek-flash':(300,1200),'deepseek-v4-pro':(1320,3960)}
sys.modules[rates.__name__]=rates
identity=types.ModuleType('review_pkg.monitoring_v1.targets');identity.canonical_hash=common.fingerprint
sys.modules[identity.__name__]=identity
temp_contract=load('review_pkg.monitoring_v1.temperature_contract','temperature_contract.py')
features=load('review_pkg.monitoring_v1.feature_tasks','feature_tasks.py')
temp=load('review_pkg.monitoring_v1.temperature_postprocess','temperature_postprocess.py')
coverage=load('review_pkg.monitoring_v1.audit_contracts','audit_contracts.py')
ledger_mod=load('review_pkg.monitoring_v1.api_ledger','api_ledger.py')
api=load('review_pkg.monitoring_v1.api_capture_v2','api_capture_v2.py')
RESULTS=[]

def record(name,kind,actual,assertion=True):
 if not assertion: raise AssertionError((name,actual))
 RESULTS.append({'name':name,'kind':kind,'observation':actual,'check_satisfied':True})

def observe(fn,*a,**kw):
 try: return {'accepted':True,'value':fn(*a,**kw)}
 except Exception as e: return {'accepted':False,'exception':type(e).__name__,'message':str(e)}

def rejects(name,fn,*a,**kw):
 r=observe(fn,*a,**kw);record(name,'protection_control',r,not r['accepted']);return r

DAY=86_400_000_000
start=int(datetime(2018,1,2,tzinfo=timezone.utc).timestamp()*1e6)
def product(date,values,index=1):
 return {'target_date':date,'day_index':index,
         'forecast_max_members_C':values,'forecast_min_members_C':[v-5 for v in values]}
base={'cutoff':start-DAY//2,'target':{'units':'C','physical_start':start,'physical_end':start+DAY,
 'variable':'daily_max_2m_temperature','event_operator':'ge','threshold':30},
 'common':{'daily_products':[product('2018-01-02',[31,32,10])]}}

def pair(row):
 return {'feature_task':observe(features.temperature_ensemble_probability,row),
         'postprocess':observe(temp.event_probability,row)}
normal=pair(base)
record('temperature_valid_daily_agrees','normal_control',normal,
 normal['feature_task']['value']==normal['postprocess']['value']==2/3)
negative=copy.deepcopy(base);negative['target'].update(variable='daily_min_2m_temperature',event_operator='lt',threshold=0)
negative['common']['daily_products'][0]['forecast_min_members_C']=[-5,0,2]
r=pair(negative);record('negative_celsius_and_open_zero','normal_control',r,
 r['feature_task']['value']==r['postprocess']['value']==1/3)
three=copy.deepcopy(base);three['target'].update(physical_end=start+3*DAY,variable='min_of_3_daily_max_2m_temperature')
three['common']['daily_products']=[product('2018-01-02',[31,10],1),product('2018-01-03',[10,31],2),product('2018-01-04',[31,10],3)]
r=pair(three);record('three_day_member_dependence_not_marginal_product','normal_control',r,
 r['feature_task']['value']==r['postprocess']['value']==0)
permuted=copy.deepcopy(three)
for p in permuted['common']['daily_products']:
 for field in ['forecast_min_members_C','forecast_max_members_C']: p[field].reverse()
r=pair(permuted);record('common_member_permutation_raw_event_invariant','normal_control',r,
 r['feature_task']['value']==0 and r['postprocess']['value']==0)
for name,mutate in [
 ('noon_shift',lambda r:r['target'].update(physical_start=start+DAY//2,physical_end=start+3*DAY//2)),
 ('duplicate_product',lambda r:r['common']['daily_products'].append(product('2018-01-02',[40,40,40]))),
 ('boolean_day_index',lambda r:r['common']['daily_products'][0].update(day_index=True)),
 ('nan_threshold',lambda r:r['target'].update(threshold=float('nan'))),
 ('boolean_threshold',lambda r:r['target'].update(threshold=True)),
]:
 row=copy.deepcopy(base);mutate(row);r=pair(row)
 record(name,'previous_boundary_now_rejected',r,
  not r['feature_task']['accepted'] and not r['postprocess']['accepted'])
# Needed max data remain complete; unrelated min values must not decide a raw max event.
for name,variant in [('max_only_product','missing_min'),('invalid_unused_min','nan_min'),('different_unused_min_member_count','short_min')]:
 row=copy.deepcopy(base);p=row['common']['daily_products'][0]
 if variant=='missing_min':del p['forecast_min_members_C']
 elif variant=='nan_min':p['forecast_min_members_C']=[float('nan')]*3
 else:p['forecast_min_members_C']=[10.0]
 r=pair(row)
 record(name,'counterexample_target_scope',r,r['feature_task']['accepted'] and r['feature_task']['value']==2/3 and not r['postprocess']['accepted'])
# Do not weaken full min/max requirements of the ECC transformation itself.
row=copy.deepcopy(base);del row['common']['daily_products'][0]['forecast_min_members_C']
rejects('ecc_full_product_rejects_missing_min',temp.validate_products,row['common']['daily_products'])
for name,mutate in [
 ('day0',lambda r:r['common']['daily_products'][0].update(day_index=0)),
 ('post_cutoff',lambda r:r.update(cutoff=start)),
 ('bad_unit',lambda r:r['target'].update(units='K')),
 ('empty_members',lambda r:r['common']['daily_products'][0].update(forecast_max_members_C=[])),
]:
 row=copy.deepcopy(base);mutate(row);r=pair(row)
 record(name,'protection_control',r,not r['feature_task']['accepted'] and not r['postprocess']['accepted'])
for text in ['{"probability":0.2}','```json\n{"probability":0.2}\n```']:
 r=observe(features.parse_temperature,text);record('valid_probability_json_'+str(len(RESULTS)),'normal_control',r,r['accepted'])
for label,text in [
 ('boolean','{"probability":true}'),('negative','{"probability":-0.01}'),
 ('nonfinite','{"probability":NaN}'),('duplicate_key','{"probability":0.1,"probability":0.2}')]:
 rejects('probability_rejects_'+label,features.parse_temperature,text)
r=observe(features.parse_temperature,'{"probability":'+ '1'+'0'*400+'}')
record('temperature_head_oversized_integer','previous_boundary_now_rejected',r,r.get('exception')=='ValueError')
for expected,observed,label in [(['a','b'],['a'],'missing'),(['a'],['a','b'],'extra'),(['a'],['a','a'],'duplicate')]:
 rejects('coverage_rejects_'+label,coverage.require_exact_ids,expected,observed,label)
record('coverage_exact_set_control','normal_control',coverage.require_exact_ids(['a','b'],['b','a'],'ok'),True)

# Real ApiLedger objects, real per-call files, fake HTTP and controlled wall clock.
class Clock:
 def __init__(self): self.n=1_000_000_000
 def time_ns(self): return self.n
 def perf_counter(self): return self.n/1e9
 def monotonic(self): return self.n/1e9
 def sleep(self,s): self.advance(s)
 def advance(self,seconds): self.n+=int(seconds*1e9)
class Response:
 status=200
 def __init__(self,body):self.body=body
 def __enter__(self):return self
 def __exit__(self,*args):return False
 def read(self,n):return self.body[:n]
class Opener:
 def __init__(self,clock,body,exception=None):self.clock=clock;self.body=body;self.exception=exception;self.calls=[]
 def open(self,request,timeout):
  self.calls.append({'at_ns':self.clock.n,'timeout':timeout})
  if self.exception:raise self.exception
  self.clock.advance(.01);return Response(self.body)
class BrokenBody:
 def read(self,n):raise OSError('injected_error_body_failure')
 def close(self):pass

with tempfile.TemporaryDirectory(prefix='v11-review-') as td:
 t=Path(td);key=t/'dummy-key';key.write_text('dummy-review-key-no-provider-access')
 messages=[{'role':'user','content':'offline test'}]
 body=json.dumps({'usage':{'prompt_tokens':8,'completion_tokens':3},'model':'test-only',
  'choices':[{'message':{'content':'{"probability":0.2}'},'finish_reason':'stop'}]}).encode()
 def run_api(name,*,pre=None,between=None,exception=None):
  clock=Clock();ledger_mod.time=clock;api.time=clock
  specs=[ledger_mod.call_spec('call',messages,'deepseek-flash',input_cap=8192,max_tokens=32)]
  ledger=ledger_mod.ApiLedger.create(t/name,specs,limit_nanodollars=10_000_000,max_calls=1,deadline_wall_ns=clock.n+2_000_000_000)
  if pre=='deadline':clock.advance(3)
  if pre=='stop':ledger.stop('preexisting stop')
  opener=Opener(clock,body,exception);api.build_opener=lambda *a:opener
  old=Path.read_text
  def key_hook(p,*a,**kw):
   value=old(p,*a,**kw)
   if p==key:
    if between=='deadline':clock.advance(3)
    if between=='stop':ledger.stop('injected stop after claim before dispatch')
   return value
  with patch.dict(os.environ,{'DISASTERTRACE_DEEPSEEK_KEY_FILE':str(key)}),patch.object(Path,'read_text',key_hook):
   result=observe(api.capture,ledger,'call',messages)
  terminal=ledger.attempt('call')/'terminal.json'
  summary={'result':result,'http_open_calls':opener.calls,'deadline_ns':ledger.contract['deadline_wall_ns'],
           'stop_exists':(ledger.path/'STOP.json').exists(),'ledger':ledger.reduce(),
           'terminal':common.read(terminal) if terminal.exists() else None}
  return summary,ledger
 r,ledger=run_api('normal')
 record('api_normal_fsynced_usage_and_terminal','normal_control',r,
  len(r['http_open_calls'])==1 and r['ledger']['settled']==1 and r['ledger']['actual_upper_nanodollars']==6000)
 rejects('api_duplicate_claim_rejected',ledger.claim,'call',messages)
 for name,pre in [('api_stop_before_claim','stop'),('api_deadline_before_claim','deadline')]:
  r,_=run_api(name,pre=pre);record(name,'protection_control',r,len(r['http_open_calls'])==0 and not r['result']['accepted'])
 for name,between in [('api_stop_after_claim','stop'),('api_deadline_after_claim','deadline')]:
  r,_=run_api(name,between=between)
  record(name,'previous_boundary_now_rejected',r,len(r['http_open_calls'])==0 and not r['result']['accepted'] and r['terminal']['state']=='FAILED_PRE_DISPATCH')
 err=HTTPError('https://example.invalid',402,'test error',{},BrokenBody())
 r,_=run_api('nested_error',exception=err)
 record('api_nested_error_now_preserves_terminal','protection_control',r,
  r['terminal']['error_type']=='HTTPError' and r['terminal']['error_body_read_error']=='OSError' and r['ledger']['unresolved_reservations']==1)

# Test the fetched original validation function, not the downstream predictor.
import ast,math
source=(SRC/'native_feature.py').read_text()
node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='validate_feature_bank')
ns={'math':math,'FEATURE_VERSION':'native_h15_features.v1'}
exec(compile(ast.Module(body=[node],type_ignores=[]),'native_feature.py','exec'),ns)
validate_bank=ns['validate_feature_bank']
bank={'feature_version':'native_h15_features.v1','mode':'common','feature_names':['lead_hours'],
      'mean':[0.0],'scale':[1.0],'coefficients':[[0.0],[0.0],[0.0]],'intercepts':[0.0,0.0,0.0],
      'mapping_version':'offline-review-only',
      'post_calibration':{k:[{'lower':0.0,'upper':1.0,'value':0.4}] for k in ['1000','5000']}}
r=observe(validate_bank,bank,calibrated=True);record('valid_common_bank','normal_control',r,r['accepted'])
b=copy.deepcopy(bank);b['feature_names']=['slot0_read'];rejects('common_bank_rejects_paid_slot',validate_bank,b)
b=copy.deepcopy(bank);b['scale']=[0.0];rejects('bank_rejects_nonpositive_scale',validate_bank,b)
b=copy.deepcopy(bank);b['coefficients']=[[0.0],[0.0]];rejects('bank_rejects_wrong_class_count',validate_bank,b)
b=copy.deepcopy(bank);b['post_calibration']['1000'][0]['value']=-0.2
r=observe(validate_bank,b,calibrated=True);record('negative_calibration_probability_passes_guard','counterexample_bank_guard',r,r['accepted'])
b=copy.deepcopy(bank);b['post_calibration']['1000']=[{'lower':0.7,'upper':0.9,'value':0.2},{'lower':0.1,'upper':0.3,'value':0.4}]
r=observe(validate_bank,b,calibrated=True);record('unordered_calibration_domain_passes_guard','counterexample_bank_guard',r,r['accepted'])

out={'commit':'889620a4fc4ee6ad70757dd3e832a40c7509126a','source_verification':verified,
     'scope':'Offline function/module-level synthetic checks; real local files and original ApiLedger/capture; mocked HTTP/clock and transport helpers. Not the 750-test suite, real-weather replay, production FormalSession or a live HTTP concurrency test. NativeFeature bank guard is an AST-extracted original function with constants bound; no calibrated forecast is executed.',
     'no_model_calls':True,'no_network_calls_in_checks':True,'cases':RESULTS,
     'counts':{k:sum(r['kind']==k for r in RESULTS) for k in sorted({r['kind'] for r in RESULTS})}}
with _args.result.open('x',encoding='utf-8') as _out:
 json.dump(out,_out,ensure_ascii=False,indent=2,allow_nan=False);_out.write('\n')
print(json.dumps({'total':len(RESULTS),'counts':out['counts'],'verified_sources':len(verified)},ensure_ascii=False))
for r in RESULTS:
 if r['kind'].startswith('counterexample'):
  print(r['name'],json.dumps(r['observation'],ensure_ascii=False)[:430])
