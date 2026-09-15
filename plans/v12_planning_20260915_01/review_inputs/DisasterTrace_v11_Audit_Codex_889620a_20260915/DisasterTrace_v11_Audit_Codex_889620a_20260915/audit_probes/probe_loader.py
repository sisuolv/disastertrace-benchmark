"""Run exact hash-bound modules in an isolated package, or use DT_REPO_ROOT.

No production function body or import is rewritten. Only the unavailable native
METAR/TAF parser module is replaced by a sentinel that raises if invoked. These
probes do not execute native parsing, full session/journal integration or APIs.
"""
import hashlib
import importlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import types

SHA='889620a4fc4ee6ad70757dd3e832a40c7509126a'
ROOT=Path(__file__).resolve().parent/'sources'
EXPECTED={
 'adoption':'3dba7f144254d51392682577488b8b525ea28261',
 'temperature_contract':'5d46a2c8705d9cc92618bd082431be2c5c9124a9',
 'temperature_postprocess':'2e221bb7c82e126b1aa8a68dac495bf4a33f75fa',
 'regional_calibration_v2':'570658377052493448586f3306fc3f420e1e6d7c',
 'support':'d43b56c98aa3e59c4c1d17f72a503941b604698d',
 'evidence':'d921c845ac6689131944271c34a1f462deb5fb9b',
 'native_feature_forecast':'8670ed36befa3fc359c9318bf60db2d5113d92bd',
 'feature_tasks':'12aa74dc5f8ae72c59f8eed3c444a43210c4f576',
 'common':'31ed9e5f3cceabda9d9553b28be89ed1858bfc9f',
}
CHECKS=[]

def package(name):
    m=types.ModuleType(name);m.__path__=[];sys.modules[name]=m
    return m

def unavailable(*args,**kwargs):
    raise RuntimeError('Native parser is not part of this scoped review; use DT_REPO_ROOT')

def load(name,group='monitoring_v1'):
    path=ROOT/(name+'.py');b=path.read_bytes()
    blob=hashlib.sha1(f'blob {len(b)}\0'.encode()+b).hexdigest()
    if blob!=EXPECTED[name]:raise RuntimeError(f'Frozen source mismatch: {name}')
    CHECKS.append({'name':name,'git_blob_sha1':blob,'expected':EXPECTED[name],
                   'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b),'matched':True})
    full='_dt_v11_review.'+group+'.'+name
    spec=importlib.util.spec_from_file_location(full,path)
    m=importlib.util.module_from_spec(spec);sys.modules[full]=m
    spec.loader.exec_module(m)
    return m

if os.getenv('DT_REPO_ROOT'):
    src=Path(os.environ['DT_REPO_ROOT'])/'disastertrace-starter/src'
    sys.path.insert(0,str(src))
    def real(name,group='monitoring_v1'):
        return importlib.import_module('disastertrace.'+group+'.'+name)
    S=real('support');E=real('evidence');TC=real('temperature_contract')
    N=real('native_feature_forecast');F=real('feature_tasks');T=real('temperature_postprocess')
    C=real('regional_calibration_v2');A=real('adoption','monitoring_fixed_v1')
    MODE='production_package'
else:
    for n in ['_dt_v11_review','_dt_v11_review.monitoring_v1',
              '_dt_v11_review.monitoring_v1.providers','_dt_v11_review.forecast_task',
              '_dt_v11_review.monitoring_fixed_v1']:package(n)
    parser=types.ModuleType('_dt_v11_review.monitoring_v1.providers.aviation')
    parser.parse_metar=parser.parse_taf=unavailable
    sys.modules[parser.__name__]=parser
    TC=load('temperature_contract');S=load('support');E=load('evidence')
    N=load('native_feature_forecast');J=load('common','forecast_task')
    F=load('feature_tasks');T=load('temperature_postprocess')
    C=load('regional_calibration_v2');A=load('adoption','monitoring_fixed_v1')
    MODE='isolated_complete_hash_bound_modules'

if __name__=='__main__':
    print(json.dumps({'commit':SHA,'mode':MODE,'files':CHECKS},indent=2))
