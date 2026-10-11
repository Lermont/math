"""Read back saved artifacts, validate certificates, and build derived outputs."""
import argparse
from contextlib import redirect_stdout
from fractions import Fraction as F
import hashlib
import importlib.metadata
import inspect
import io
import json
from pathlib import Path
import re
import statistics
import unittest
import numpy as np
from scipy import sparse
from .data import ROOT,digest
from .benchmark import write_json,export_csv


def source_audit(out):
    refs = ROOT/'references'/'filter325'
    manifest = json.loads((refs/'manifest.json').read_text())
    for entry in manifest['sources']:
        if digest(ROOT/entry['path']) != entry['sha256']:
            raise AssertionError('source changed: '+entry['path'])
    proofdir = refs/'upstream'/'lean'/'OAI'/'Analysis'/'DirectCrouzeix'
    proofs = list(proofdir.glob('*.lean'))
    hits = []
    for p in proofs:
        for line,text in enumerate(p.read_text(encoding='utf-8').splitlines(),1):
            if re.search(r'\bsorry\b|^axiom\s',text):
                hits.append({'file':p.relative_to(ROOT).as_posix(),'line':line,'text':text})
    # Preserve actual implementation used, with version and content hash.
    import scipy.sparse.linalg._expm_multiply as em
    import scipy.sparse._compressed as compressed
    runtime = []
    for mod,remote in [(em,'scipy/sparse/linalg/_expm_multiply.py'),(compressed,'scipy/sparse/_compressed.py')]:
        original = Path(inspect.getfile(mod))
        target = refs/'scipy-1.18.1'/original.name
        target.parent.mkdir(exist_ok=True)
        if target.exists():
            assert target.read_bytes() == original.read_bytes()
        else:
            target.write_bytes(original.read_bytes())
        runtime.append({'path':target.relative_to(ROOT).as_posix(),'sha256':digest(target),
                        'origin':'installed wheel scipy==1.18.1',
                        'upstream_reference_url':'https://github.com/scipy/scipy/blob/v1.18.1/'+remote})
    dist = importlib.metadata.distribution('scipy')
    for item in dist.files:
        if str(item).endswith('.dist-info/LICENSE.txt') or str(item).endswith('licenses/LICENSE.txt'):
            original = Path(dist.locate_file(item))
            target = refs/'scipy-1.18.1'/'LICENSE.txt'
            if not target.exists(): target.write_bytes(original.read_bytes())
            runtime.append({'path':target.relative_to(ROOT).as_posix(),'sha256':digest(target),'origin':'installed scipy wheel license'})
            break
    write_json(refs/'runtime-source-manifest.json',runtime)
    result = {'source_manifest_verified':True,'downloaded_sources':len(manifest['sources']),
              'upstream_head_check':json.loads((refs/'head-check.json').read_text()),
              'git_tree_was_truncated':manifest['recursive_tree_truncated'],
              'explicit_primary_sources_downloaded':True,
              'direct_solution_files_scanned':len(proofs),'placeholder_or_axiom_text_hits':hits,
              'comparator_challenges_have_intentional_sorry':True,
              'lean_compiled':False,'comparator_executed':False,
              'status':'Inspected statements, scopes, selected solution sources and comparator configuration; no independent full-proof verification.'}
    write_json(out/'source-audit.json',result)
    return result


def check_disk(A,certificate):
    """Check the saved positive witness by exact fractions, independently of
    the candidate iteration and its integer-accumulation implementation.
    """
    c = F(certificate['center'])
    rows = []
    n = A.shape[0]
    for i in range(n):
        row = {int(A.indices[k]):F.from_float(float(A.data[k])) for k in range(A.indptr[i],A.indptr[i+1])}
        row[i] = row.get(i,F(0))-c
        rows.append({j:abs(a) for j,a in row.items() if a})
    col_sums = [F(0)]*n
    row_sums = [sum(row.values(),F(0)) for row in rows]
    for row in rows:
        for j,a in row.items(): col_sums[j] += a
    nr = F(certificate['norm_radius'])
    assert nr*nr >= max(row_sums)*max(col_sums)
    rb = F(certificate['row_radius'])
    assert all(row_sums[i]+col_sums[i] <= 2*rb for i in range(n))
    upper = [nr,rb]
    if 'positive_witness' in certificate:
        v = certificate['positive_witness']
        assert len(v)==n and all(isinstance(x,int) and x>0 for x in v)
        Sv = [sum((a*v[j]/2 for j,a in row.items()),F(0)) for row in rows]
        for i,row in enumerate(rows):
            for j,a in row.items(): Sv[j] += a*v[i]/2
        cr = F(certificate['collatz_radius'])
        assert all(Sv[i] <= cr*v[i] for i in range(n))
        upper.append(cr)
        assert F(certificate['radius'])==min(upper)
    else:
        assert F(certificate['radius'])==nr


def readback(out):
    reg = json.loads((out/'preregistration.json').read_text(encoding='utf-8'))
    assert reg['plan_sha256']==digest(ROOT/'filter325'/'PLAN.md')
    assert reg['config_sha256']==digest(ROOT/'filter325'/'config.json')
    cases = json.loads((out/'cases.json').read_text())
    rows = [json.loads(line) for line in (out/'measurements.jsonl').read_text(encoding='utf-8').splitlines()]
    memory = { (r['case'],r['method'],r['tolerance']):r['memory'] for r in
              (json.loads(s) for s in (out/'memory.jsonl').read_text().splitlines())}
    assert len(rows)==282 and len(memory)==282
    ix = {(r['case'],r['method'],r['tolerance']):r for r in rows}
    assert len(ix)==len(rows)
    equal_poly_pairs = 0
    canonical = {}
    for case in cases:
        path = out/'data'/case['name']
        for name,expected in case['hashes'].items():
            assert digest(path/name)==expected,(case['name'],name)
        A,X,R = sparse.load_npz(path/'A.npz'),np.load(path/'X.npy'),np.load(path/'reference.npy')
        h = hashlib.sha256()
        for val in (np.array(A.shape,dtype='<i8'),A.indptr.astype('<i8'),A.indices.astype('<i8'),A.data.astype('<f8')):
            h.update(val.tobytes())
        canonical[case['name']]={'matrix_content_sha256':h.hexdigest(),'vectors_content_sha256':hashlib.sha256(X.astype('<f8').tobytes()).hexdigest()}
        checked = set()
        for r in (s for s in rows if s['case']==case['name']):
            Y = np.load(out/'predictions'/f'{r["case"]}__{r["method"]}__{r["tolerance"]}.npy')
            err = np.linalg.norm(Y-R,axis=0)
            np.testing.assert_allclose(err,r['abs_errors'],rtol=2e-14,atol=1e-30)
            assert r['meets_target_all_vectors'] and np.all(err/np.linalg.norm(X,axis=0)<=float(r['tolerance']))
            if r['certificate']:
                key = json.dumps(r['certificate'],sort_keys=True)
                if key not in checked:
                    check_disk(A,r['certificate']); checked.add(key)
                assert all(s['csr_forward']==r['degree'] and s['csc_adjoint']==0 for s in r['products_per_input'])
                assert r['operator_bound_exact_arithmetic']<=.900000001*float(r['tolerance'])
                assert np.all(err<=np.array(r['action_bounds_exact_arithmetic']))
            r['memory']=memory[(r['case'],r['method'],r['tolerance'])]
            # Repair a derived field-name typo from first run; raw times unchanged.
            r.pop('degree_median_search_and_bound_median_s',None)
            for stage in ('geometry_s','scalar_exp_certificate_s','degree_search_and_bound_s','coefficient_s'):
                r[stage[:-2]+'_median_s']=statistics.median(x[stage] for x in r['raw_batch'])
        for tol in reg['config']['tolerances']:
            new,old=ix[(case['name'],'crouzeix2',tol)],ix[(case['name'],'crouzeix_old',tol)]
            assert new['certificate']==old['certificate']
            assert new['degree']<=old['degree']
            if new['degree']==old['degree']:
                files=[out/'predictions'/f'{case["name"]}__{method}__{tol}.npy' for method in ('crouzeix2','crouzeix_old')]
                np.testing.assert_array_equal(np.load(files[0]),np.load(files[1]))
                equal_poly_pairs+=1
            if case['normal_control']:
                assert (A.T@A-A@A.T).nnz==0
                assert ix[(case['name'],'normal1',tol)]['degree']<=new['degree']
    write_json(out/'measurements.json',rows)
    export_csv(out,rows)
    result={'rows':len(rows),'predictions':len(rows)*reg['config']['vectors'],
            'all_meet_requested_input_scaled_tolerance':True,
            'source_and_input_hashes_verified':True,'disk_witnesses_checked_exactly':True,
            'same_degree_new_old_bitwise_identical_pairs':equal_poly_pairs,
            'raw_timings_unchanged':True,'derived_field_name_repaired':True,
            'observed_approximation_bound_violations':0,
            'roundoff_not_formally_certified':True,'canonical_dataset_hashes':canonical}
    write_json(out/'validation.json',result)
    write_json(out/'final-code-hashes.json',{p.relative_to(ROOT).as_posix():digest(p) for p in (ROOT/'filter325').glob('*') if p.is_file()})
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=ROOT/'results'/'filter325'/'run-20261011')
    args=parser.parse_args()
    a=source_audit(args.output)
    b=readback(args.output)
    print(json.dumps({'sources':a['downloaded_sources'],'rows':b['rows'],'predictions':b['predictions'],'status':'PASS'}))


if __name__=='__main__':
    main()
