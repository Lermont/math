"""Fresh-process benchmark; each method pays for its own feature extraction."""
from __future__ import annotations

import os
for _name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[_name]='1'

import argparse
import hashlib
import json
import platform
import sys
import time

import networkx as nx
import numpy as np
import pandas as pd
import psutil
import scipy
import sklearn
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.tree import DecisionTreeClassifier, export_text
from threadpoolctl import threadpool_limits

from .context_download import OUT
from .context_features import (CORE_NAMES, CONTEXT_BASIC_NAMES, CONTEXT_GRAPH_NAMES,
    CONTEXT_NULL_NAMES, core_record, context_basic, context_graph, context_null)
from .directed import DIRECTED_NAMES, directed_features
from .evaluate import metrics, threshold_at_fpr
from .features import basic_features, graph_features

METHODS=['core','rules','graph','directed','paper','edge']


def run(method,seed):
    started=time.perf_counter()
    source=(OUT/'sample.json').read_bytes()
    source_hash=hashlib.sha256(source).hexdigest()
    records=json.loads(source)
    del source
    destination=OUT/f'seed{seed}';destination.mkdir(exist_ok=True)
    if (destination/f'{method}.json').exists():raise FileExistsError('Measurement already exists')
    names=(CORE_NAMES if method=='core' else CONTEXT_BASIC_NAMES if method=='rules' else CONTEXT_GRAPH_NAMES)+(
        CONTEXT_NULL_NAMES if method in ('paper','edge') else ['directed_'+n for n in DIRECTED_NAMES] if method=='directed' else [])
    x=np.empty((len(records),len(names)),dtype=float)
    timing={s:0. for s in ('train','val','test')}
    diagnostics=[]
    for i,r in enumerate(records):
        begin=time.perf_counter()
        if method=='core':
            cr=core_record(r);values=basic_features(cr)+graph_features(cr,seed=seed+r['id'])
        elif method=='rules':values=context_basic(r)
        else:values=context_graph(r,seed=seed+r['id'])
        if method in ('paper','edge'):
            null,diag=context_null(r,kernel=method,seed=seed*1000003+r['id'])
            values+=null.tolist();diagnostics.append({'id':r['id'],'split':r['split'],**diag})
        elif method=='directed':values+=directed_features(r['n'],r['directed'])
        x[i]=values;timing[r['split']]+=time.perf_counter()-begin
        if (i+1)%2000==0:print(f'{method} seed={seed}: {i+1}/{len(records)}, {time.perf_counter()-started:.1f}s',flush=True)
    assert np.isfinite(x).all()
    ids=np.asarray([r['id'] for r in records]);y=np.asarray([r['y'] for r in records]);split=np.asarray([r['split'] for r in records])
    train,val,test=split=='train',split=='val',split=='test'
    model=DecisionTreeClassifier(max_depth=3,min_samples_leaf=25,class_weight='balanced',random_state=seed) if method=='rules' else ExtraTreesClassifier(n_estimators=200,min_samples_leaf=5,max_features=1.,class_weight='balanced',random_state=seed,n_jobs=1)
    with threadpool_limits(limits=1):
        t=time.perf_counter();model.fit(x[train],y[train]);fit=time.perf_counter()-t
        t=time.perf_counter();vs=model.predict_proba(x[val])[:,1];vp=time.perf_counter()-t
        threshold=threshold_at_fpr(y[val],vs)
        t=time.perf_counter();ts=model.predict_proba(x[test])[:,1];tp=time.perf_counter()-t
    pd.DataFrame({'id':ids[test],'y':y[test],'score':ts}).to_csv(destination/f'{method}-predictions.csv',index=False)
    np.savez_compressed(destination/f'{method}-features.npz',x=x,y=y,ids=ids,split=split)
    if method=='rules':(destination/'rules.txt').write_text(export_text(model,feature_names=names))
    result={'method':method,'seed':seed,'sample_sha256':source_hash,'features':names,'feature_seconds':timing,'fit_seconds':fit,
        'validation_predict_seconds':vp,'test_predict_seconds':tp,'test_total_seconds':timing['test']+tp,
        'metrics':metrics(y[test],ts,threshold),'validation':metrics(y[val],vs,threshold),
        'feature_importance':sorted(zip(names,map(float,model.feature_importances_)),key=lambda item:-item[1]),
        'sampler':{'burn':512,'samples':32,'stride':64} if diagnostics else None,
        'versions':{'python':sys.version,'platform':platform.platform(),'networkx':nx.__version__,'numpy':np.__version__,'scikit_learn':sklearn.__version__,'scipy':scipy.__version__}}
    if diagnostics:
        d=pd.DataFrame(diagnostics);d.to_csv(destination/f'{method}-diagnostics.csv',index=False)
        active=d[~d.frozen]
        result['diagnostics']={'frozen':int(d.frozen.sum()),'proposals':int(d.proposals.sum()),'accepted':int(d.accepted.sum()),'active_no_varying_targets':int((active.varying_targets==0).sum()),'mean_distinct_states_active':float(active.distinct_states.mean()),'median_acceptance_active':float((active.accepted/active.proposals).median())}
    result['total_seconds']=time.perf_counter()-started
    result['peak_rss_mib']=psutil.Process().memory_info().peak_wset/2**20
    (destination/f'{method}.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({k:result[k] for k in ('method','seed','metrics','total_seconds','test_total_seconds','peak_rss_mib')}),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--method',choices=METHODS,required=True);parser.add_argument('--seed',type=int,default=131)
    run(**vars(parser.parse_args()))
