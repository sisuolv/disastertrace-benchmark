"""Real native program rehearsal, without new models or fitted-bank claims."""

import importlib.util
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
path = ROOT / 'scripts/run_api_pilot.py'
spec = importlib.util.spec_from_file_location('offline_pilot_preflight', path)
pilot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilot)
out = ROOT / 'reports/api_program_preflight_01'
out.mkdir(exist_ok=False)
pilot.OUT = out
for module in ['monitoring_v1','monitoring_fixed_v1']:
    shutil.copytree(REPO/'disastertrace-starter/src/disastertrace'/module,
                    out/'source/disastertrace'/module, ignore=shutil.ignore_patterns('__pycache__'))
(out/'source/disastertrace/__init__.py').write_text('"""Zero-model engineering rehearsal."""\n')
shutil.copyfile(path,out/'source/run_api_pilot.py')
shutil.copyfile(ROOT.parent/'v8_measurement_execution_20260913_01/scripts/run_program_calendar.py',out/'source/program_reference.py')
shutil.copyfile(ROOT/'model_catalog/probe_01/deepseek_pricing.body',out/'PRICING.html')
case, arms = pilot.prepare_case('new_york','2025-01-06',5000,
    bank_path=ROOT.parent/'v8_measurement_execution_20260913_01/contracts/BANK.json')
selected=['copy_current','batch_program','fixed_quota__target_private','global_budget__session_shared']
for arm in selected:
    pilot.run_arm(case,arm)
(out/'VALIDATION.json').write_text(json.dumps({'arms':selected,'model_calls':0,'scope':'engineering only; old Bay bank is explicitly not regional qualification'},indent=2)+'\n')
print(json.dumps({'passed':True,'arms':selected,'model_calls':0}))
