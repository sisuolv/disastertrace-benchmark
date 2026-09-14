"""Download a frozen ModelScope file list with bounded resumable transfers."""

import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import time
import urllib.parse
import urllib.request

HERE = Path(__file__).resolve().parent
DEST = Path('/mnt/afs/260010168/models/Qwen3-235B-A22B-Instruct-2507-FP8-ms-20260913')
MODEL = 'Qwen/Qwen3-235B-A22B-Instruct-2507-FP8'


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def transfer(row):
    name = row['Path']
    if '/' in name or name in {'.', '..'}:
        raise ValueError('Unexpected model file path')
    path = DEST / name
    if path.exists():
        if path.stat().st_size == row['Size'] and digest(path) == row['Sha256']:
            return {'file': name, 'status': 'verified_existing'}
        raise ValueError('Existing model file differs from pinned manifest: ' + name)
    partial = path.with_name(name + '.partial')
    attempts = []
    for attempt in range(3):
        offset = partial.stat().st_size if partial.exists() else 0
        if offset == row['Size']:
            break
        query = urllib.parse.urlencode({'Revision': row['Revision'], 'FilePath': name})
        url = 'https://modelscope.cn/api/v1/models/' + MODEL + '/repo?' + query
        request = urllib.request.Request(url, headers={'Range': f'bytes={offset}-'} if offset else {})
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                if offset and response.status != 206:
                    raise ValueError('Server did not honor the resume range')
                if offset and not response.headers.get('Content-Range', '').startswith(f'bytes {offset}-'):
                    raise ValueError('Wrong resume position')
                with partial.open('ab' if offset else 'wb') as output:
                    for chunk in iter(lambda: response.read(8 * 1024 * 1024), b''):
                        output.write(chunk)
                    output.flush()
                    os.fsync(output.fileno())
            attempts.append({'attempt': attempt + 1, 'offset': offset, 'status': 'received'})
            break
        except Exception as exc:
            attempts.append({'attempt': attempt + 1, 'offset': offset, 'error_type': type(exc).__name__})
            if attempt < 2:
                time.sleep(2)
    if not partial.exists() or partial.stat().st_size != row['Size'] or digest(partial) != row['Sha256']:
        return {'file': name, 'status': 'failed_integrity', 'attempts': attempts}
    partial.rename(path)
    return {'file': name, 'status': 'verified', 'bytes': row['Size'], 'sha256': row['Sha256'], 'attempts': attempts}


def main():
    DEST.mkdir(exist_ok=True)
    rows = json.loads((HERE / 'qwen235_fp8_ms.json').read_text())['Data']['Files']
    rows = [r for r in rows if r['Type'] == 'blob']
    (HERE / 'LARGE_MODEL_FREEZE.json').write_text(json.dumps({'model': MODEL, 'destination': str(DEST), 'files': rows}, indent=2) + '\n')
    with (HERE / 'download_receipts.jsonl').open('x') as log:
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(transfer, row) for row in sorted(rows, key=lambda r: r['Size'])]
            reports = []
            for future in concurrent.futures.as_completed(futures):
                try:
                    report = future.result()
                except Exception as exc:
                    report = {'status': 'error', 'error_type': type(exc).__name__, 'error': str(exc)}
                reports.append(report)
                log.write(json.dumps(report) + '\n'); log.flush(); os.fsync(log.fileno())
                print(json.dumps(report), flush=True)
    result = {'model': MODEL, 'destination': str(DEST), 'files': len(rows), 'results': reports,
              'all_verified': all(r['status'].startswith('verified') for r in reports)}
    (HERE / 'DOWNLOAD_RESULT.json').write_text(json.dumps(result, indent=2) + '\n')
    raise SystemExit(0 if result['all_verified'] else 1)


if __name__ == '__main__':
    main()
