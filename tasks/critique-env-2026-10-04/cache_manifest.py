#!/usr/bin/env python3
"""Record the provenance of the mock backend's response cache (cache/, gitignored) in fixtures/CACHE_MANIFEST.json.

Each cached upstream GET (mock_api.py::upstream) is listed with its request path, HTTP status, body size and sha256
and the cache file's modification time (when it was fetched). The manifest is committed so a later run can tell
which production responses the critique saw; the cache itself is regenerated on first use and never committed.
Run after a session: python3 cache_manifest.py
"""
import datetime
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, 'cache')
OUT = os.path.join(HERE, 'fixtures', 'CACHE_MANIFEST.json')

def iso(ts: float) -> str:
    return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).isoformat(timespec='seconds')

entries = []
for name in sorted(os.listdir(CACHE)) if os.path.isdir(CACHE) else []:
    if not name.endswith('.json'):
        continue
    fp = os.path.join(CACHE, name)
    with open(fp, 'rb') as f:
        raw = f.read()
    try:
        rec = json.loads(raw)
    except json.JSONDecodeError:
        rec = {}
    body = rec.get('body') if isinstance(rec, dict) else None
    if body is not None:
        entry = {'file': f'cache/{name}', 'kind': 'upstream-response', 'path': rec.get('path'), 'status': rec.get('status'),
                 'content_type': rec.get('ctype'), 'body_bytes': len(body.encode('utf-8')),
                 'body_sha256': hashlib.sha256(body.encode('utf-8')).hexdigest()}
    else:  # build_fixture.py's copy of the production summary document
        entry = {'file': f'cache/{name}', 'kind': 'raw-json', 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
    entry['fetched_at'] = iso(os.path.getmtime(fp))
    entries.append(entry)

manifest = {'upstream': 'https://api.earningsnerd.io', 'cache_dir': 'cache/ (gitignored; regenerated on first use)',
            'recorded_at': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
            'entries': entries}
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, 'w') as f:
    json.dump(manifest, f, indent=1)
    f.write('\n')
print(f'wrote {OUT}: {len(entries)} cached responses')
if not entries:
    sys.exit(1)
