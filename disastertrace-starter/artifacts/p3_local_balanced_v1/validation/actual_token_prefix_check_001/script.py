from pathlib import Path

from disastertrace.local_eval.adapter import extract, terminal_ids
from disastertrace.local_eval.runtime import tokenizer_for
from disastertrace.local_eval.storage import read

execution = Path('artifacts/p3_local_balanced_v1/execution')
run = Path('work/p3-qwen3-balanced-v1')
tokenizer = tokenizer_for(execution)
files = sorted((run / 'captures').glob('*.json'))[:240]
for path in files:
    capture = read(path)
    ids = capture['result']['output_token_ids']
    extracted = extract(ids, tokenizer)
    assert extracted == capture['extracted']
    texts = {extracted['raw_text']}
    if ids and ids[-1] in terminal_ids(tokenizer):
        texts.add(tokenizer.decode(ids[:-1], skip_special_tokens=False))
    assert capture['result']['runtime_output_text'] in texts
print({'status': 'passed', 'immutable_prefix_captures': len(files),
       'new_model_calls': 0, 'complete_run_audit': False})
