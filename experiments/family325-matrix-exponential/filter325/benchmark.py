"""Sequential benchmark; all timings exclude tracing, counters, and references."""
import os
for _key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','BLIS_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[_key] = '1'
import argparse
import csv
from datetime import datetime,timezone
import gc
import importlib.metadata
import inspect
import json
from pathlib import Path
import platform
import random
import statistics
import subprocess
import sys
import time
import tracemalloc
from contextlib import contextmanager
from fractions import Fraction as F
import numpy as np
import psutil
from scipy import sparse,linalg
from threadpoolctl import threadpool_info,threadpool_limits
from .core import prepare,count_sparse_products,sqrt_upper,float_up
from .data import ROOT,digest,prepare_datasets,decimal_action


def write_json(path,data):
    path.write_text(json.dumps(data,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')


def versions():
    return {'python':sys.version,'platform':platform.platform(),'processor':platform.processor(),
            'logical_cpus':psutil.cpu_count(),'physical_cpus':psutil.cpu_count(logical=False),
            'ram_bytes':psutil.virtual_memory().total,
            'dependencies':{p:importlib.metadata.version(p) for p in ('numpy','scipy','mpmath','psutil','threadpoolctl')},
            'threadpools':threadpool_info(), 'environment':{k:os.environ.get(k) for k in
             ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','BLIS_NUM_THREADS','NUMEXPR_NUM_THREADS')}}


def all_methods(case):
    return ['crouzeix2','crouzeix_old','norm_taylor','scipy','scipy_cached','arnoldi']+(['normal1'] if case['normal_control'] else [])


def run_batch(p,X):
    ys,infos = [],[]
    for j in range(X.shape[1]):
        y,info = p.apply(X[:,j])
        ys.append(y); infos.append(info)
    return np.column_stack(ys),infos


def stage_data(p):
    return {'setup_s':p.setup_s,'geometry_s':p.geom.geometry_s if p.geom else 0.,
            'scalar_exp_certificate_s':p.geom.scalar_setup_s if p.geom else 0.,
            'degree_search_and_bound_s':p.degree_s,'coefficient_s':p.coefficient_s}


@contextmanager
def capture_scipy_core(counts):
    from scipy.sparse.linalg import _expm_multiply as em
    original = em._expm_multiply_simple_core
    records = []
    def wrapped(A,B,t,mu,m_star,s,tol=None,balance=False):
        c0 = dict(counts)
        y = original(A,B,t,mu,m_star,s,tol,balance)
        records.append({'degree':int(m_star),'scaling':int(s),
                        'core_products':{k:counts[k]-c0[k] for k in counts}})
        return y
    em._expm_multiply_simple_core = wrapped
    try:
        yield records
    finally:
        em._expm_multiply_simple_core = original


def memory_row(out,case,method,tol,config):
    pth = out/'data'/case
    A,X = sparse.load_npz(pth/'A.npz'),np.load(pth/'X.npy')
    proc = psutil.Process()
    before = proc.memory_info()
    np.random.seed(config['order_seed'])
    p = prepare(A,method,tol,config)
    Y,_ = run_batch(p,X)
    after = proc.memory_info()
    peak = getattr(after,'peak_wset',after.rss)
    del p,Y
    gc.collect()
    np.random.seed(config['order_seed'])
    tracemalloc.start()
    p = prepare(A,method,tol,config)
    Y,_ = run_batch(p,X)
    current,tracked_peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {'baseline_rss_bytes':before.rss,'baseline_process_peak_bytes':getattr(before,'peak_wset',before.rss),
            'peak_process_rss_bytes':peak,'tracked_setup_batch_peak_bytes':tracked_peak,
            'tracked_final_bytes':current,'native_peak_scope':'fresh_process_imports_data_setup_batch_without_tracing',
            'tracked_peak_scope':'separate_setup_and_8_outputs_may_exclude_native_library_buffers'}


def benchmark_row(A,X,reference,case,method,tol,config,output,poly_cache):
    for _ in range(config['warmups']):
        np.random.seed(config['order_seed'])
        p = prepare(A,method,tol,config)
        run_batch(p,X)
    single, batch = [],[]
    for _ in range(config['repeats']):
        np.random.seed(config['order_seed'])
        t = time.perf_counter()
        p = prepare(A,method,tol,config)
        t1 = time.perf_counter()
        y,_ = p.apply(X[:,0])
        t2 = time.perf_counter()
        single.append({**stage_data(p),'apply_s':t2-t1,'total_s':t2-t})
        np.random.seed(config['order_seed'])
        t = time.perf_counter()
        p = prepare(A,method,tol,config)
        t1 = time.perf_counter()
        Y,infos = run_batch(p,X)
        t2 = time.perf_counter()
        batch.append({**stage_data(p),'apply_s':t2-t1,'total_s':t2-t})
    p_last = p
    # Count matrix products separately, on the very same explicit sparse path.
    np.random.seed(config['order_seed'])
    with count_sparse_products(A.shape[0]) as counts:
        p = prepare(A,method,tol,config)
        setup_counts = dict(counts)
        input_counts = []
        counted = []
        with capture_scipy_core(counts) as scipy_infos:
            for j in range(X.shape[1]):
                c0 = dict(counts)
                yy,_ = p.apply(X[:,j])
                counted.append(yy)
                input_counts.append({k:counts[k]-c0[k] for k in counts})
    if not np.array_equal(Y,np.column_stack(counted)):
        raise AssertionError(f'Instrumentation changed output: {case["name"]} {method} {tol}')
    errors = np.linalg.norm(Y-reference,axis=0)
    xnorm = np.linalg.norm(X,axis=0)
    ynorm = np.linalg.norm(reference,axis=0)
    exact_xnorm_upper = [sqrt_upper(sum((F.from_float(float(v))**2 for v in X[:,j]),F(0))) for j in range(X.shape[1])]
    bound = np.array([float_up(F.from_float(p.operator_bound)*v) for v in exact_xnorm_upper]) if p.operator_bound is not None else None
    if scipy_infos:
        infos = scipy_infos
    arithmetic = None
    if p.geom:
        key = (str(p.geom.c),p.degree)
        if key not in poly_cache:
            high,_ = decimal_action(A,X[:,0],degree=p.degree,center=float(p.geom.c),dps=config['reference_dps'])
            poly_cache[key] = np.array([float(row[0]) for row in high])
        arithmetic = float(linalg.norm(Y[:,0]-poly_cache[key]))
    row = {'case':case['name'],'family':case['family'],'n':case['n'],'seed':case['seed'],
           'method':method,'tolerance':tol,'degree':p.degree if p.degree is not None else (infos[0].get('degree') if infos else None),'per_vector_info':infos,
           'constant':p.constant,'operator_bound_exact_arithmetic':p.operator_bound,
           'scalar_disk_bound':p.scalar_bound,'radius':float(p.geom.radius) if p.geom else None,
           'norm_radius':float(p.geom.norm_radius) if p.geom else None,
           'abs_errors':errors.tolist(),'relative_output_errors':(errors/ynorm).tolist(),
           'relative_input_errors':(errors/xnorm).tolist(),
           'input_norms':xnorm.tolist(),'input_norm_upper_bounds':[float_up(v) for v in exact_xnorm_upper],'reference_output_norms':ynorm.tolist(),
           'action_bounds_exact_arithmetic':bound.tolist() if bound is not None else None,
           'bound_over_error':(bound/np.maximum(errors,1e-300)).tolist() if bound is not None else None,
           'float_vs_decimal_same_polynomial_first_vector_2norm':arithmetic,
           'meets_target_all_vectors':bool(np.all(errors/xnorm<=float(tol))),
           'raw_single':single,'raw_batch':batch,
           'single_total_median_s':statistics.median(s['total_s'] for s in single),
           'batch_total_median_s':statistics.median(s['total_s'] for s in batch),
           'prepared_apply_median_s':statistics.median(s['apply_s'] for s in batch)/X.shape[1],
           'setup_median_s':statistics.median(s['setup_s'] for s in batch),
           'setup_products':setup_counts,'products_per_input':input_counts,
           'counter_identical_output':True,
           'certificate':p.geom.certificate if p.geom else None}
    for stage in ('geometry_s','scalar_exp_certificate_s','degree_search_and_bound_s','coefficient_s'):
        row[stage[:-2]+'_median_s'] = statistics.median(s[stage] for s in batch)
    np.save(output/'predictions'/f'{case["name"]}__{method}__{tol}.npy',Y)
    return row


def export_csv(out,rows):
    fields = ['case','family','n','method','tolerance','degree','constant','radius','norm_radius',
              'max_abs_error','max_relative_output_error','max_relative_input_error','max_bound',
              'max_conservatism','single_total_median_s','batch_total_median_s','prepared_apply_median_s',
              'setup_median_s','geometry_median_s','scalar_exp_certificate_median_s',
              'degree_search_and_bound_median_s','coefficient_median_s','setup_products_total',
              'first_input_products_total','batch_products_total','peak_process_rss_bytes',
              'tracked_setup_batch_peak_bytes','meets_target_all_vectors']
    with (out/'measurements.csv').open('w',newline='',encoding='utf-8') as f:
        w = csv.DictWriter(f,fieldnames=fields)
        w.writeheader()
        for r in rows:
            d = {k:r.get(k) for k in fields}
            d.update(max_abs_error=max(r['abs_errors']), max_relative_output_error=max(r['relative_output_errors']),
                     max_relative_input_error=max(r['relative_input_errors']),
                     max_bound=max(r['action_bounds_exact_arithmetic']) if r['action_bounds_exact_arithmetic'] else None,
                     max_conservatism=max(r['bound_over_error']) if r['bound_over_error'] else None,
                     setup_products_total=sum(r['setup_products'].values()),
                     first_input_products_total=sum(r['products_per_input'][0].values()),
                     batch_products_total=sum(sum(x.values()) for x in r['products_per_input']))
            for k in ('peak_process_rss_bytes','tracked_setup_batch_peak_bytes'):
                d[k] = r.get('memory',{}).get(k)
            w.writerow(d)


def main():
    if importlib.metadata.version('scipy') != '1.18.1':
        raise RuntimeError('scipy_cached was inspected and tested only with SciPy 1.18.1; use requirements.txt')
    parser = argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=ROOT/'results'/'filter325'/'run-20261011')
    parser.add_argument('--stage',choices=['data','timing','memory','all'],default='all')
    parser.add_argument('--memory',nargs=3,metavar=('CASE','METHOD','TOL'))
    args = parser.parse_args()
    out = args.output.resolve()
    if ROOT/'results'/'filter325' not in out.parents:
        raise ValueError('output must be a new subdirectory of results/filter325')
    config = json.loads((ROOT/'filter325'/'config.json').read_text())
    if args.memory:
        with threadpool_limits(limits=1):
            print(json.dumps(memory_row(out,*args.memory,config)))
        return
    out.mkdir(parents=True,exist_ok=True)
    (out/'predictions').mkdir(exist_ok=True)
    prereg_path = out/'preregistration.json'
    if not prereg_path.exists():
        write_json(prereg_path,{'created_utc':datetime.now(timezone.utc).isoformat(),
                               'plan_sha256':digest(ROOT/'filter325'/'PLAN.md'),
                               'config_sha256':digest(ROOT/'filter325'/'config.json'), 'config':config})
    else:
        reg = json.loads(prereg_path.read_text(encoding='utf-8'))
        if reg['plan_sha256'] != digest(ROOT/'filter325'/'PLAN.md') or reg['config_sha256'] != digest(ROOT/'filter325'/'config.json'):
            raise ValueError('preregistered plan/config changed')
    write_json(out/'versions.json',versions())
    with threadpool_limits(limits=1):
        if args.stage in ('all','data'):
            cases = prepare_datasets(out,config)
        else:
            cases = json.loads((out/'cases.json').read_text(encoding='utf-8'))
        if args.stage in ('all','timing'):
            raw = out/'measurements.jsonl'
            if raw.exists():
                raise FileExistsError('timings already exist: use a fresh output directory')
            order = random.Random(config['order_seed'])
            with raw.open('w',encoding='utf-8') as f:
                for case in cases:
                    d = out/'data'/case['name']
                    A,X,ref = sparse.load_npz(d/'A.npz'),np.load(d/'X.npy'),np.load(d/'reference.npy')
                    work = [(method,tol) for method in all_methods(case) for tol in config['tolerances']]
                    order.shuffle(work)
                    cache = {}
                    for method,tol in work:
                        r = benchmark_row(A,X,ref,case,method,tol,config,out,cache)
                        f.write(json.dumps(r,ensure_ascii=False,allow_nan=False)+'\n'); f.flush()
                    print(f'Timed {case["name"]}: {len(work)} rows',flush=True)
        if args.stage in ('all','memory'):
            rows = [json.loads(s) for s in (out/'measurements.jsonl').read_text(encoding='utf-8').splitlines()]
            memory_path = out/'memory.jsonl'
            done = {}
            if memory_path.exists():
                for line in memory_path.read_text().splitlines():
                    r = json.loads(line)
                    done[(r['case'],r['method'],r['tolerance'])] = r['memory']
            with memory_path.open('a',encoding='utf-8') as f:
                for i,r in enumerate(rows):
                    key = (r['case'],r['method'],r['tolerance'])
                    if key not in done:
                        cmd = [sys.executable,'-m','filter325.benchmark','--output',str(out),'--memory',*key]
                        result = subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,check=True)
                        mem = json.loads(result.stdout)
                        done[key] = mem
                        f.write(json.dumps({'case':key[0],'method':key[1],'tolerance':key[2],'memory':mem})+'\n'); f.flush()
                    r['memory'] = done[key]
                    if (i+1)%20 == 0:
                        print(f'Memory {i+1}/{len(rows)}',flush=True)
            write_json(out/'measurements.json',rows)
            export_csv(out,rows)
        elif (out/'measurements.jsonl').exists():
            rows = [json.loads(s) for s in (out/'measurements.jsonl').read_text(encoding='utf-8').splitlines()]
            write_json(out/'measurements.json',rows)
            export_csv(out,rows)
    write_json(out/'code-hashes.json',{p.relative_to(ROOT).as_posix():digest(p) for p in (ROOT/'filter325').glob('*') if p.is_file()})


if __name__ == '__main__':
    main()
