"""Restore pinned reference snapshots locally without changing their manifests.
Run explicitly: python restore_references.py
Never executes downloaded material or downloads Elliptic2 raw data.
"""
from pathlib import Path
import hashlib, json, urllib.request
ROOT = Path(__file__).resolve().parent

def sha(data): return hashlib.sha256(data).hexdigest()

def main():
    failures, restored = [], 0
    manifests = sorted((ROOT/'references').glob('**/sources.json'))
    manifests += sorted((ROOT/'references').glob('**/manifest.json'))
    for manifest in manifests:
        doc = json.loads(manifest.read_text(encoding='utf-8'))
        for key in ('files', 'sources', 'references'):
            for item in doc.get(key, []):
                rel, url, expected = item.get('path'), item.get('url'), item.get('sha256')
                if not rel or not url or not expected: continue
                target = (ROOT/rel if rel.startswith('references/') else manifest.parent/rel).resolve()
                if not target.is_relative_to((ROOT/'references').resolve()):
                    raise ValueError('Reference path leaves references/: ' + rel)
                if target.exists():
                    if sha(target.read_bytes()) != expected: failures.append((rel,'existing hash mismatch'))
                    continue
                try:
                    request = urllib.request.Request(url, headers={'User-Agent':'math-experiment-source-reproduction'})
                    with urllib.request.urlopen(request, timeout=60) as response: data = response.read()
                    candidates = [data]
                    # The string-storage manifest explicitly records normalized snapshots.
                    if doc.get('hash_note'):
                        lf = data.replace(b'\r\n',b'\n')
                        candidates.extend([lf,lf.rstrip(b'\n'),lf.rstrip(b'\n')+b'\n',
                                           (lf.rstrip(b'\n')+b'\n').replace(b'\n',b'\r\n')])
                    matches = [value for value in candidates if sha(value)==expected]
                    if not matches: raise ValueError('downloaded hash differs from recorded snapshot')
                    target.parent.mkdir(parents=True,exist_ok=True)
                    target.write_bytes(matches[0]); restored += 1
                except Exception as exc: failures.append((rel,str(exc)))
    print(json.dumps({'restored':restored,'unrestored':failures},indent=2))
    if failures: raise SystemExit(1)

if __name__=='__main__': main()
