"""Download immutable source snapshots. Never execute downloaded sources."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
import re
import urllib.request
import time
import ssl
import subprocess
import tempfile
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'references' / 'filter325'
PIN = 'fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb'

def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'filter325-local-research'})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as f:
                return f.read()
        except Exception as exc:
            if isinstance(getattr(exc, 'reason', None), ssl.SSLCertVerificationError):
                # Windows' native chain builder can fetch missing intermediates.
                # Keep verification enabled and all temporary bytes in our area.
                with tempfile.NamedTemporaryFile(dir=DEST, suffix='.download', delete=False) as tmp:
                    path = Path(tmp.name)
                try:
                    subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-File',
                                    str(ROOT/'filter325'/'native_download.ps1'),
                                    '-Url',url,'-Path',str(path)],check=True,capture_output=True)
                    return path.read_bytes()
                finally:
                    path.unlink(missing_ok=True)
            if attempt == 2:
                raise RuntimeError(f'Download failed: {url}: {exc}') from exc
            time.sleep(1 + attempt)

def save(local, url):
    p = DEST / local
    if p.exists():
        data = p.read_bytes()
    else:
        data = get(url)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    return {'path': p.relative_to(ROOT).as_posix(), 'url': url,
            'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}

def main():
    DEST.mkdir(parents=True, exist_ok=True)
    head_raw = get('https://api.github.com/repos/openai/math/commits/main')
    head = json.loads(head_raw)
    # An unexpected upstream update requires inspecting it, never silent repinning.
    if head['sha'] != PIN:
        raise RuntimeError(f'Upstream changed to {head["sha"]}; inspect before repinning')
    (DEST / 'head-check.json').write_text(json.dumps({
        'checked_at_utc': datetime.now(timezone.utc).isoformat(),
        'expected': PIN, 'observed': head['sha'],
        'commit_url': head['html_url'], 'message': head['commit']['message']
    }, indent=2), encoding='utf-8')
    tree_url = f'https://api.github.com/repos/openai/math/git/trees/{PIN}?recursive=1'
    tree = json.loads(get(tree_url))
    required = {'README.md', 'history.md', 'LICENSE', 'lean/docs/325.md',
                'lean/README.md', 'lean/ComparatorChallenges/README.md',
                'lean/lean-toolchain', 'lean/lake-manifest.json', 'lean/lakefile.toml'}
    names = ('DirectCrouzeix','CompleteCrouzeix','CrouzeixHilbert','HilbertCrouzeix','StructuralCrouzeix')
    for n in names:
        for ext in ('.lean', '.json'):
            required.add('lean/ComparatorChallenges/' + n + ext)
    papers = ('A-direct-proof-of-the-complete-Crouzeix-inequality-September-26-2026',
              'The-complete-Crouzeix-theorem-September-23-2026')
    paths = []
    for item in tree['tree']:
        p = item['path']
        if item['type'] != 'blob':
            continue
        if (p in required or any(p.startswith('preprints/' + s + '/') for s in papers)
            or re.match(r'lean/OAI/Analysis/(?:DirectCrouzeix|Crouzeix|CrouzeixHilbert|HilbertCrouzeix|StructuralCrouzeix)/', p)):
            paths.append(p)
    # GitHub's recursive tree can be truncated before docs/preprints. Never infer
    # absence from that response; explicitly retrieve the task's primary sources.
    explicit = {'README.md','history.md','LICENSE','lean/docs/325.md','lean/README.md',
                'lean/ComparatorChallenges/README.md'}
    for paper in papers:
        explicit.update('preprints/'+paper+'/'+p for p in ('README.md','paper.pdf','build/main.tex'))
    paths = sorted(set(paths)|explicit)
    tasks = [(f'upstream/{p}', f'https://raw.githubusercontent.com/openai/math/{PIN}/{p}') for p in paths]
    tasks += [
        ('al-mohy-higham-2011.pdf', 'https://eprints.maths.manchester.ac.uk/1591/1/alhi11.pdf'),
        ('crouzeix-palencia-2017.pdf', 'https://arxiv.org/pdf/1702.00668'),
        ('saad-1992.pdf', 'https://www-users.cse.umn.edu/~saad/PDF/RIACS-90-ExpTh.pdf'),
        ('scipy-expm-multiply.html', 'https://docs.scipy.org/doc/scipy/reference/generated/scipy.sparse.linalg.expm_multiply.html'),
    ]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        entries = list(pool.map(lambda t: save(*t), tasks))
    manifest = {'upstream_commit': PIN, 'recursive_tree_truncated':tree.get('truncated'),
                'coverage':'explicit primary papers and selected proof subtrees; not full repository',
                'sources': sorted(entries, key=lambda x: x['path'])}
    (DEST / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps({'commit': PIN, 'files': len(entries), 'bytes': sum(e['bytes'] for e in entries)}), flush=True)

if __name__ == '__main__':
    main()
