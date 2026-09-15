"""Offline probe: execute the unmodified validator, not the full predictor runtime."""
import ast
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent
path = ROOT / 'source/native_feature.py'
raw = path.read_bytes()
expected = 'b3928a682eb146002f501973f641297d9b2a3ffc'
actual = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
assert actual == expected
node = next(n for n in ast.parse(raw).body if isinstance(n, ast.FunctionDef) and n.name == 'validate_feature_bank')
namespace = {'math': math, 'FEATURE_VERSION': 'native_h15_features.v1'}
exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), namespace)
base = {'feature_version': 'native_h15_features.v1', 'mode': 'common',
        'feature_names': ['taf_present'], 'mean': [0.0], 'scale': [1.0],
        'coefficients': [[0.0], [0.0], [0.0]], 'intercepts': [0.0, 0.0, 0.0],
        'mapping_version': 'reviewer_synthetic_only',
        'post_calibration': {str(t): [{'lower': 0.0, 'upper': 1.0, 'value': -0.1}] for t in [1000, 5000]}}
try:
    namespace['validate_feature_bank'](base, calibrated=True)
    accepted, error = True, None
except Exception as exc:
    accepted, error = False, type(exc).__name__
result = {'id': 'NEGATIVE_CALIBRATION_VALUE', 'validator_accepted': accepted,
          'synthetic_calibration_output': -0.1, 'error': error,
          'expected': 'reject a calibration output outside [0,1]',
          'scope': 'Unmodified AST-extracted bank validator only. No captured bank, actual prediction, or formal session was executed. Downstream probability validation can still reject this value.'}
(ROOT/'BANK_GUARD_PROBE.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result, indent=2))
