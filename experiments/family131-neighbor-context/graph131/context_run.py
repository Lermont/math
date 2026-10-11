from __future__ import annotations
import hashlib
import json
import subprocess
import sys
from datetime import datetime,timezone
from pathlib import Path
from .context_download import ROOT,OUT

METHODS=['core','rules','graph','directed','paper','edge']
SEEDS=[131,132,133]


def run():
    code=[ROOT/'graph131/CONTEXT_PLAN.md']+sorted((ROOT/'graph131').glob('*.py'))+[ROOT/'tests/test_graph131_context.py']
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in code}
    metadata={'created_utc':datetime.now(timezone.utc).isoformat(),'source_hashes':hashes,'sample_sha256':hashlib.sha256((OUT/'sample.json').read_bytes()).hexdigest(),'seeds':SEEDS,'methods':METHODS,'parallel_workers':1,'threads_per_worker':1}
    mpath=OUT/'run-metadata.json'
    if mpath.exists():
        old=json.loads(mpath.read_text());assert old['source_hashes']==hashes and old['sample_sha256']==metadata['sample_sha256'],'Sources or data changed since initial measurement'
    else:mpath.write_text(json.dumps(metadata,indent=2))
    # Rotated method order reduces systematic warm-cache/order effects.
    for i,seed in enumerate(SEEDS):
        order=METHODS[i:]+METHODS[:i]
        for method in order:
            p=OUT/f'seed{seed}/{method}.json'
            if p.exists():
                assert json.loads(p.read_text())['sample_sha256']==metadata['sample_sha256']
                continue
            subprocess.run([sys.executable,'-m','graph131.context_worker','--method',method,'--seed',str(seed)],cwd=ROOT,check=True)


if __name__=='__main__':run()
