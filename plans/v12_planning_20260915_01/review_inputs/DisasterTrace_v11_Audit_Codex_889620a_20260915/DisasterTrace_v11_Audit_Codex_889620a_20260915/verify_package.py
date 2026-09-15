"""Verify this review bundle without network access or executing its source copies."""
import hashlib
import json
from pathlib import Path

root=Path(__file__).resolve().parent
manifest=json.loads((root/'MANIFEST.json').read_text(encoding='utf-8'))
for relative,entry in manifest['files'].items():
    path=root/relative
    if not path.resolve().is_relative_to(root.resolve()) or path.is_symlink():
        raise ValueError('Unsafe path: '+relative)
    raw=path.read_bytes()
    if len(raw)!=entry['bytes'] or hashlib.sha256(raw).hexdigest()!=entry['sha256']:
        raise ValueError('Mismatch: '+relative)
print(json.dumps({'verified_files':len(manifest['files']),'source_commit':manifest['source_commit']},indent=2))
