"""Bounded CPU probes against four byte-verified GitHub source files.

Only temperature_contract and temperature_postprocess are imported as complete
modules. Two named functions are AST-loaded without their unrelated imports.
All fixtures are synthetic. This is NOT a full repository or dataset audit.
"""
from pathlib import Path
import ast, copy, hashlib, importlib, json, math, sys, types

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'source'
EXPECTED = {
    'temperature_contract.py':'5d46a2c8705d9cc92618bd082431be2c5c9124a9',
    'temperature_postprocess.py':'2e221bb7c82e126b1aa8a68dac495bf4a33f75fa',
    'feature_tasks.py':'12aa74dc5f8ae72c59f8eed3c444a43210c4f576',
    'native_feature.py':'b3928a682eb146002f501973f641297d9b2a3ffc',
}
for name, expected in EXPECTED.items():
    b=(SOURCE/name).read_bytes()
    assert hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==expected,name
pkg=types.ModuleType('verified_sources');pkg.__path__=[str(SOURCE)];sys.modules[pkg.__name__]=pkg
contract=importlib.import_module('verified_sources.temperature_contract')
post=importlib.import_module('verified_sources.temperature_postprocess')

def load_function(filename, name, context):
    tree=ast.parse((SOURCE/filename).read_text())
    node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
    ns=dict(context)
    exec(compile(ast.Module(body=[node],type_ignores=[]),filename,'exec'),ns)
    return ns[name]

prob=load_function('feature_tasks.py','temperature_ensemble_probability',{'event_values':contract.event_values})
validate=load_function('native_feature.py','validate_feature_bank',{'math':math,'FEATURE_VERSION':'native_h15_features.v1'})
DAY=contract.DAY

def row(days=1):
    return {'cutoff':0,'target':{'units':'C','physical_start':DAY,'physical_end':(1+days)*DAY,
       'variable':'daily_max_2m_temperature' if days==1 else 'min_of_3_daily_max_2m_temperature',
       'event_operator':'ge','threshold':30},
       'common':{'daily_products':[{'day_index':i,'target_date':f'1970-01-0{i+1}',
       'forecast_max_members_C':[31,20],'forecast_min_members_C':[-2,4]} for i in range(1,days+1)]}}

def outcome(fn,*a,**kw):
    try:return {'status':'accepted','value':fn(*a,**kw)}
    except Exception as e:return {'status':'rejected','error_type':type(e).__name__,'message':str(e)}

def bank():
    return {'feature_version':'native_h15_features.v1','mode':'common','feature_names':['lead_hours'],
      'mean':[0.0],'scale':[1.0],'coefficients':[[0.0],[0.0],[0.0]],'intercepts':[0.0]*3,
      'mapping_version':'synthetic_fixture','post_calibration':{t:[{'lower':0.0,'upper':1.0,'value':0.2}] for t in ('1000','5000')}}

results=[]
def add(name,observed,condition,classification='regression'):
    results.append({'id':name,'scope':'synthetic_local','classification':classification,
        'observed':observed,'expectation_verified':bool(condition)})

r=row();v=[prob(r),post.event_probability(r)]
add('T01_valid_daily_agreement',v,v==[0.5,0.5])
values=[True,False,None,'1',float('nan'),float('inf'),10**401,-17.2,0]
observed=[contract.finite_number(v) for v in values]
add('T02_finite_numeric_guard',observed,observed==[False]*7+[True,True])
for ident,mut in [
 ('T03_non_midnight',lambda r:r['target'].update(physical_start=DAY+1,physical_end=2*DAY+1)),
 ('T04_duplicate_date',lambda r:r['common']['daily_products'].append(copy.deepcopy(r['common']['daily_products'][0]))),
 ('T05_nan_threshold',lambda r:r['target'].update(threshold=float('nan'))),
 ('T06_boolean_threshold',lambda r:r['target'].update(threshold=True)),
 ('T07_huge_threshold',lambda r:r['target'].update(threshold=10**401)),
 ('T08_cutoff_at_target',lambda r:r.update(cutoff=DAY)),
 ('T09_empty_members',lambda r:r['common']['daily_products'][0].update(forecast_max_members_C=[])),
 ('T10_day_zero',lambda r:r['common']['daily_products'][0].update(day_index=0)),
]:
 r=row();mut(r);o=[outcome(prob,r),outcome(post.event_probability,r)]
 add(ident,o,all(x['status']=='rejected' and x['error_type']=='ValueError' for x in o))
r=row(3);r['common']['daily_products'][1]['forecast_max_members_C']=[20,31]
o=[prob(r),post.event_probability(r)]
add('T11_same_member_three_day',o,o==[0.0,0.0])
r=row(3);r['common']['daily_products'][1]['forecast_max_members_C']=[31]
o=[outcome(prob,r),outcome(post.event_probability,r)]
add('T12_member_dimensions',o,all(x['status']=='rejected' for x in o))
r=row();del r['common']['daily_products'][0]['forecast_min_members_C']
o=[outcome(prob,r),outcome(post.event_probability,r)]
add('T13_max_only_scope_difference',o,o[0]=={'status':'accepted','value':0.5} and o[1]['error_type']=='KeyError','reproduced_contract_boundary')
r=row();r['common']['daily_products'][0]['forecast_min_members_C'][0]=float('nan')
o=[outcome(prob,r),outcome(post.event_probability,r)]
add('T14_irrelevant_minimum_scope_difference',o,o[0]=={'status':'accepted','value':0.5} and o[1]['status']=='rejected','reproduced_contract_boundary')
r=row(3);saved=copy.deepcopy(r)
b={'min':{'a':100,'b':1,'log_c':0,'log_d':0},'max':{'a':0,'b':1,'log_c':0,'log_d':0}}
converted,trace=post.ecc_products(r['common']['daily_products'],b)
add('T15_ecc_immutable_and_ordered',trace,r==saved and trace['minmax_projections']>0 and all(lo<=hi for p in converted for lo,hi in zip(p['forecast_min_members_C'],p['forecast_max_members_C'])))
b=bank();o=outcome(validate,b,calibrated=True);add('B01_valid_common_bank',o,o['status']=='accepted')
b=bank();b['feature_names']=['slot0_visibility_lower_log'];o=outcome(validate,b)
add('B02_common_rejects_paid_feature',o,o['status']=='rejected')
b=bank();b['post_calibration']['1000'][0]['value']=-0.2;o=outcome(validate,b,calibrated=True)
add('B03_negative_probability_map_accepted',o,o['status']=='accepted','reproduced_validation_gap')
b=bank();b['post_calibration']['1000']=[{'lower':0.8,'upper':1.0,'value':0.2},{'lower':0.0,'upper':0.2,'value':0.8}];o=outcome(validate,b,calibrated=True)
add('B04_reversed_domain_blocks_accepted',o,o['status']=='accepted','reproduced_validation_gap')
b=bank();b['post_calibration']['1000']=[{'lower':0.0,'upper':0.5,'value':0.8},{'lower':0.5,'upper':1.0,'value':0.2}];o=outcome(validate,b,calibrated=True)
add('B05_nonmonotone_values_rejected',o,o['status']=='rejected')
b=bank();b['post_calibration']['1000'][0]['value']=1.2;o=outcome(validate,b,calibrated=True)
add('B06_greater_than_one_rejected',o,o['status']=='rejected')
report={'commit':'889620a4fc4ee6ad70757dd3e832a40c7509126a','source_hashes_verified':4,
 'checks':len(results),'verified_expectations':sum(r['expectation_verified'] for r in results),
 'not_full_repository_audit':True,'no_real_data_or_model_calls':True,'results':results}
(ROOT/'LOCAL_CHECKS.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False))
print(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False))
assert all(r['expectation_verified'] for r in results)
