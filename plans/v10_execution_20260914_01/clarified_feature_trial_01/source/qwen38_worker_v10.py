"""Four isolated one-H100 replicas, immutable requests, no inference retries."""
import argparse
import datetime
import hashlib
import importlib.metadata
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path


def load(path):
    return json.loads(path.read_text())


def save(path, value):
    with path.open('x') as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write('\n')
        handle.flush()
        os.fsync(handle.fileno())


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(16 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def before_deadline(plan):
    return datetime.datetime.now(datetime.timezone.utc) < datetime.datetime.fromisoformat(plan['last_worker_time'])


def replica(batch, rank):
    import torch
    from transformers import AutoModelForImageTextToText, AutoTokenizer

    plan = load(batch / 'PLAN.json')
    out = batch / ('worker_' + str(rank))
    out.mkdir(exist_ok=False)
    save(out / 'STARTED.json', {'hostname': socket.gethostname(), 'pid': os.getpid(),
                              'plan_sha256': digest(batch / 'PLAN.json'), 'rank': rank})
    assert torch.cuda.device_count() == 1
    hardware = torch.cuda.get_device_properties(0)
    assert 'H100' in hardware.name
    torch.set_num_threads(6)
    torch.manual_seed(plan['generation']['seed'])
    versions = {key: importlib.metadata.version(key) for key in ('torch', 'transformers', 'accelerate', 'tokenizers', 'huggingface-hub')}
    assert versions == load(batch / 'QUALIFICATION.json')['runtime_versions']
    save(out / 'HARDWARE.json', {'name': hardware.name, 'memory_bytes': hardware.total_memory,
                               'versions': versions, 'cuda_visible_devices': os.environ['CUDA_VISIBLE_DEVICES']})
    tokenizer = AutoTokenizer.from_pretrained(plan['model_directory'], local_files_only=True, trust_remote_code=False)
    started = time.perf_counter()
    model = AutoModelForImageTextToText.from_pretrained(
        plan['model_directory'], local_files_only=True, trust_remote_code=False,
        dtype=torch.bfloat16, device_map={'': 'cuda:0'}, attn_implementation='sdpa')
    model.eval()
    save(out / 'MODEL_LOADED.json', {'seconds': time.perf_counter() - started,
                                   'allocated_bytes': torch.cuda.memory_allocated(0)})
    eos = model.generation_config.eos_token_id
    eos = eos if isinstance(eos, list) else [eos]

    def invoke(call_id, messages, cap, meta):
        if not before_deadline(plan):
            raise TimeoutError('Frozen model collection deadline')
        lifecycle_started_ns = time.time_ns()
        lifecycle_started = time.perf_counter()
        ids = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True,
                                             enable_thinking=False, preserve_thinking=False,
                                             return_dict=False)
        assert isinstance(ids, list) and len(ids) <= plan['input_token_cap']
        prompt = torch.tensor([ids], dtype=torch.long, device='cuda')
        save(out / (call_id + '.request.json'), {'call_id': call_id, 'messages': messages,
             'input_ids': ids, 'max_new_tokens': cap, 'meta': meta, 'wall_started_ns': time.time_ns()})
        torch.cuda.synchronize()
        started = time.perf_counter()
        try:
            with torch.inference_mode():
                output = model.generate(input_ids=prompt, attention_mask=torch.ones_like(prompt),
                                        do_sample=False, max_new_tokens=cap,
                                        pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id)
            torch.cuda.synchronize()
            duration = time.perf_counter() - started
            generated = output[0, len(ids):].tolist()
            raw = tokenizer.decode(generated, skip_special_tokens=True)
            record = {'call_id': call_id, 'raw': raw, 'output_ids': generated,
                      'input_tokens': len(ids), 'output_tokens': len(generated), 'seconds': duration,
                      'ended_with_eos': bool(generated and generated[-1] in eos),
                      'request_sha256': digest(out / (call_id + '.request.json')),
                      'wall_returned_ns': time.time_ns()}
            save(out / (call_id + '.response.json'), record)
            # The response bytes are durable before this publication observation.
            save(out / (call_id + '.publication.json'), {
                'call_id': call_id, 'response_sha256': digest(out / (call_id + '.response.json')),
                'lifecycle_started_ns': lifecycle_started_ns, 'published_observed_ns': time.time_ns(),
                'lifecycle_seconds': time.perf_counter() - lifecycle_started,
                'generation_seconds': duration,
                'scope': 'prompt preparation through durable response; warm model loading reported separately'})
            print(json.dumps({'rank': rank, 'call_id': call_id, 'seconds': duration,
                              'output_tokens': len(generated)}), flush=True)
            return record
        except Exception as exc:
            save(out / (call_id + '.unknown.json'), {'error_type': type(exc).__name__,
                 'seconds_observed': time.perf_counter() - started, 'retry': False})
            raise

    smoke = invoke('compatibility', [{'role': 'user', 'content': 'Return exactly READY.'}], 16,
                   {'kind': 'compatibility_not_benchmark'})
    if smoke['raw'].strip().rstrip('.') != 'READY' or not smoke['ended_with_eos']:
        raise ValueError('Compatibility failed; no benchmark calls on this replica')
    completed = []
    for task in plan['tasks']:
        if task['worker'] != rank:
            continue
        path = batch / 'policy' / (task['call_id'] + '.json')
        assert digest(path) == task['policy_sha256']
        request = load(path)
        invoke(task['call_id'], request['messages'], plan['generation']['max_new_tokens'],
               {'representation': task['representation'], 'reasoning': task['reasoning']})
        completed.append(task['call_id'])
    save(out / 'COMPLETE.json', {'benchmark_calls': len(completed), 'compatibility_calls': 1,
                               'completed_call_ids': completed, 'new_model': plan['model']})


def parent(batch):
    plan = load(batch / 'PLAN.json')
    (batch / 'PARENT_CLAIM').mkdir(exist_ok=False)
    if datetime.datetime.now(datetime.timezone.utc) >= datetime.datetime.fromisoformat(plan['late_start_cutoff']):
        raise TimeoutError('Late start: no inference')
    manifest = load(batch / 'MODEL_MANIFEST.json')
    verified = []
    for file in manifest['files']:
        path = Path(manifest['directory']) / file['path']
        assert path.stat().st_size == file['bytes'] and digest(path) == file['sha256']
        verified.append(file['path'])
    qualification = load(batch / 'QUALIFICATION.json')
    for rel, sha in qualification['frozen_files'].items():
        assert digest(batch / rel) == sha
    save(batch / 'WORKER_PREFLIGHT.json', {'verified_model_files': verified,
                                         'source_and_input_bindings_pass': True})
    processes = []
    for rank in range(4):
        handle = (batch / ('worker_' + str(rank) + '.log')).open('x')
        env = dict(os.environ, CUDA_VISIBLE_DEVICES=str(rank), OMP_NUM_THREADS='6')
        p = subprocess.Popen([sys.executable, str(Path(__file__)), '--batch', str(batch), '--rank', str(rank)],
                             stdout=handle, stderr=subprocess.STDOUT, env=env)
        processes.append((rank, p, handle))
    codes = []
    for rank, process, handle in processes:
        code = process.wait()
        handle.close()
        codes.append(code)
        save(batch / ('worker_' + str(rank) + '.exit.json'), {'exit_code': code})
    save(batch / 'WORKERS_EXIT.json', {'exit_codes': codes, 'all_workers_complete': not any(codes)})
    if any(codes):
        raise SystemExit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--batch', type=Path, required=True)
    parser.add_argument('--rank', type=int)
    args = parser.parse_args()
    parent(args.batch) if args.rank is None else replica(args.batch, args.rank)
