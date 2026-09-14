"""Four-GPU tensor-parallel fixed-input inference with immutable raw receipts."""

import argparse
import hashlib
import json
import math
import os
import socket
import time
from pathlib import Path


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(16 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def save(path, value):
    with path.open('x') as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write('\n')
        handle.flush()
        os.fsync(handle.fileno())


def load(path):
    return json.loads(path.read_text())


def main(batch, model_key):
    import torch
    import transformers
    import vllm
    from transformers import AutoTokenizer
    from vllm import LLM, SamplingParams

    plan = load(batch / 'PLAN.json')
    spec = plan['models'][model_key]
    out = batch / model_key
    out.mkdir(exist_ok=False)
    plan_hash = digest(batch / 'PLAN.json')
    save(out / 'STARTED.json', {'model': model_key, 'plan_sha256': plan_hash, 'pid': os.getpid(),
                              'hostname': socket.gethostname(), 'wall_started_ns': time.time_ns()})
    versions = {'torch': torch.__version__.split('+')[0], 'transformers': transformers.__version__,
                'vllm': vllm.__version__}
    assert versions == plan['runtime_versions'], versions
    assert torch.cuda.device_count() == 4
    gpus = [{'name': torch.cuda.get_device_properties(i).name,
             'bytes': torch.cuda.get_device_properties(i).total_memory} for i in range(4)]
    assert all('H100' in gpu['name'] for gpu in gpus)
    verified = []
    for file in spec['files']:
        path = Path(spec['directory']) / file['path']
        assert path.stat().st_size == file['bytes'] and digest(path) == file['sha256'], file['path']
        verified.append(file)
    for rel, expected in plan['files'].items():
        assert digest(batch / rel) == expected, rel
    save(out / 'HARDWARE.json', {'gpus': gpus, 'runtime_versions': versions,
         'hostname': socket.gethostname(), 'model_files_verified': verified,
         'plan_sha256': plan_hash, 'tensor_parallel_size': 4})
    tokenizer = AutoTokenizer.from_pretrained(spec['directory'], local_files_only=True)
    torch.set_num_threads(4)
    boot = time.perf_counter()
    llm = LLM(model=spec['directory'], tokenizer=spec['directory'], tensor_parallel_size=4,
              dtype='auto', quantization=spec['quantization'], seed=plan['generation']['seed'],
              trust_remote_code=False, **plan['engine'])
    save(out / 'MODEL_LOADED.json', {'seconds': time.perf_counter() - boot, 'model': spec['name']})
    parameters = SamplingParams(temperature=0.0, max_tokens=512, seed=plan['generation']['seed'])
    smoke = tokenizer.apply_chat_template([{'role': 'user', 'content': 'Return exactly READY.'}],
                tokenize=True, add_generation_prompt=True, enable_thinking=False)
    save(out / 'SMOKE_REQUEST.json', {'prompt_token_ids': smoke, 'plan_sha256': plan_hash})
    smoke_out = llm.generate([{'prompt_token_ids': smoke}], SamplingParams(temperature=0, max_tokens=16), use_tqdm=False)[0]
    save(out / 'SMOKE_RESPONSE.json', {'raw': smoke_out.outputs[0].text,
         'output_ids': list(smoke_out.outputs[0].token_ids), 'finish_reason': smoke_out.outputs[0].finish_reason})
    completed = 0
    for offset in range(0, len(plan['tasks']), plan['batch_size']):
        rows = plan['tasks'][offset:offset + plan['batch_size']]
        prompts, requests = [], []
        for row in rows:
            item = load(batch / 'policy' / (row['call_id'] + '.json'))
            assert canonical_hash(item['messages']) == row['messages_sha256']
            ids = tokenizer.apply_chat_template(item['messages'], tokenize=True, add_generation_prompt=True,
                                                 enable_thinking=False)
            assert len(ids) == row['models'][model_key]['input_tokens']
            assert canonical_hash(ids) == row['models'][model_key]['input_ids_sha256']
            request = {'call_id': row['call_id'], 'model': model_key, 'plan_sha256': plan_hash,
                       'messages': item['messages'], 'input_ids': ids, 'input_tokens': len(ids),
                       'logical_started_at': row['logical_started_at'], 'logical_cutoff': row['logical_cutoff'],
                       'batch_offset': offset, 'batch_size': len(rows)}
            save(out / (row['call_id'] + '-request.json'), request)
            prompts.append({'prompt_token_ids': ids})
            requests.append(request)
        wall_started, started = time.time_ns(), time.perf_counter()
        try:
            answers = llm.generate(prompts, parameters, use_tqdm=False)
        except Exception as exc:
            save(out / ('BATCH_FAILURE_' + str(offset) + '.json'), {'error_type': type(exc).__name__,
                 'error': str(exc), 'call_ids': [r['call_id'] for r in rows], 'disposition': 'unknown_execution_no_retry'})
            raise
        completed_us = math.ceil((time.perf_counter() - started) * 1_000_000)
        assert len(answers) == len(rows)
        for row, request, answer in zip(rows, requests, answers):
            generated = answer.outputs[0]
            eos_ids = {tokenizer.eos_token_id}
            finish_eos = generated.finish_reason == 'stop' and (
                bool(generated.token_ids) and generated.token_ids[-1] in eos_ids
                or generated.stop_reason in eos_ids)
            raw = generated.text
            response = {'call_id': row['call_id'], 'model': model_key, 'plan_sha256': plan_hash,
                        'raw': raw, 'raw_sha256': hashlib.sha256(raw.encode()).hexdigest(),
                        'output_ids': list(generated.token_ids), 'input_tokens': request['input_tokens'],
                        'output_tokens': len(generated.token_ids), 'finish_reason': generated.finish_reason,
                        'stop_reason': generated.stop_reason, 'ended_with_eos': bool(finish_eos),
                        'batch_elapsed_us': completed_us, 'logical_started_at': row['logical_started_at'],
                        'logical_completed_at': row['logical_started_at'] + completed_us,
                        'timing_basis': 'measured whole four-request batch, including in-batch scheduling'}
            response_path = out / (row['call_id'] + '-response.json')
            save(response_path, response)
            persisted_us = math.ceil((time.perf_counter() - started) * 1_000_000)
            commit = {'call_id': row['call_id'], 'plan_sha256': plan_hash,
                      'request_sha256': digest(out / (row['call_id'] + '-request.json')),
                      'response_sha256': digest(response_path), 'raw_sha256': response['raw_sha256'],
                      'wall_started_ns': wall_started, 'wall_after_response_fsync_ns': time.time_ns(),
                      'completed_elapsed_us': completed_us, 'persisted_elapsed_us': persisted_us,
                      'logical_persisted_at': row['logical_started_at'] + persisted_us,
                      'origin': 'actual_local_vllm_tp4; independent fixed-input diagnostic'}
            save(out / (row['call_id'] + '-commit.json'), commit)
            completed += 1
        print(json.dumps({'model': model_key, 'benchmark_committed': completed, 'expected': len(plan['tasks'])}), flush=True)
    save(out / 'COMPLETE.json', {'model': model_key, 'benchmark_calls': completed, 'compatibility_calls': 1,
                               'all_planned_requests_completed': completed == len(plan['tasks']), 'plan_sha256': plan_hash})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--batch', type=Path, required=True)
    parser.add_argument('--model', required=True)
    args = parser.parse_args()
    main(args.batch.resolve(), args.model)
