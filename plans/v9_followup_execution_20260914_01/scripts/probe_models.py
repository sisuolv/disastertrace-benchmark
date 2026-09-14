"""Bounded official model discovery; never print authentication material."""

import datetime as dt
import argparse
import hashlib
import json
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--proxy', action='store_true')
    args = parser.parse_args()
    out = ROOT / "model_catalog" / ("probe_02" if args.proxy else "probe_01")
    out.mkdir(exist_ok=False)
    session = requests.Session()
    session.trust_env = args.proxy
    checks = [
        ("glm53_official", "https://huggingface.co/api/models/zai-org/GLM-5.3", False),
        ("glm53_mirror", "https://hf-mirror.com/api/models/zai-org/GLM-5.3", False),
        ("glm_catalog", "https://huggingface.co/api/models?author=zai-org&search=GLM-5&limit=15", False),
        ("deepseek_models", "https://api.deepseek.com/models", True),
        ("deepseek_pricing", "https://api-docs.deepseek.com/quick_start/pricing", False),
    ]
    if args.proxy:
        checks = [
            ("glm53_official_proxy", "https://huggingface.co/api/models/zai-org/GLM-5.3", False),
            ("glm53_modelscope", "https://modelscope.cn/api/v1/models/ZhipuAI/GLM-5.3", False),
            ("glm53_github", "https://api.github.com/repos/zai-org/GLM-5.3", False),
        ]
    rows = []
    for name, url, auth in checks:
        row = {"name": name, "url": url, "requested_at": dt.datetime.now(dt.timezone.utc).isoformat()}
        headers = {}
        if auth:
            key = Path('/mnt/afs/260010168/.config/disastertrace/deepseek_followup_20260914.key').read_text().strip()
            headers['Authorization'] = 'Bearer ' + key
        try:
            response = session.get(url, headers=headers, timeout=(15, 45))
            body = response.content
            path = out / (name + '.body')
            path.write_bytes(body)
            row.update(status=response.status_code, bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
            if response.status_code == 200:
                try:
                    data = response.json()
                    if name == 'deepseek_models':
                        row['model_ids'] = [r['id'] for r in data.get('data', [])]
                    elif isinstance(data, dict):
                        row.update(model_id=data.get('id'), revision=data.get('sha'), gated=data.get('gated'),
                                   safetensors=data.get('safetensors'), pipeline_tag=data.get('pipeline_tag'))
                    elif isinstance(data, list):
                        row['model_ids'] = [r.get('id') for r in data]
                except ValueError:
                    pass
        except Exception as exc:
            row['error_type'] = type(exc).__name__
        rows.append(row)
    (out / 'RESULTS.json').write_text(json.dumps({'checks': rows, 'generation_calls': 0}, indent=2) + '\n')
    print(json.dumps(rows), flush=True)


if __name__ == '__main__':
    main()
