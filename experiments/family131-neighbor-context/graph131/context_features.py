"""Core-marked NetworkX and fixed-budget degree-conditioned features."""
from __future__ import annotations

import math
import random
from itertools import combinations

import networkx as nx
import numpy as np

from .features import BASIC_NAMES, GRAPH_NAMES, basic_features, graph_features
from .switches import State, TARGET_NAMES, structural_targets

MARKED_NAMES=['core_internal_edges','core_boundary_edges','triangles_touching_core','core_two_step_pairs','external_core_degree_mixing']
BOUNDARY_NAMES=['core_fraction','external_nodes','boundary_edges','boundary_per_core','core_degree_mean','core_degree_max','core_degree_std','context_degree_mean','context_degree_max','boundary_fraction']
CORE_NX_NAMES=['core_pagerank_mass','core_pagerank_max','core_clustering_mean','core_coreness_mean','core_coreness_max','core_boundary_conductance']
CORE_NAMES=['core_'+n for n in BASIC_NAMES+GRAPH_NAMES]
CONTEXT_BASIC_NAMES=['context_'+n for n in BASIC_NAMES]+BOUNDARY_NAMES
CONTEXT_GRAPH_NAMES=CORE_NAMES+CONTEXT_BASIC_NAMES+['context_'+n for n in GRAPH_NAMES]+CORE_NX_NAMES+MARKED_NAMES
CONTEXT_NULL_NAMES=[f'{kind}_{name}' for kind in ('residual','upper_tail','lower_tail') for name in TARGET_NAMES+MARKED_NAMES]


def core_record(record):
    return {'id':record['id'],'n':record['core_n'],'edges':record['core_edges']}


def marked_targets(state,k):
    adj,edges=state.adj,state.edges
    inside=sum(a<k and b<k for a,b in edges)
    boundary=sum((a<k)!=(b<k) for a,b in edges)
    triangles=0
    for a,b in edges:
        for c in adj[a]&adj[b]:
            if b<c and min(a,b,c)<k:triangles+=1
    pairs=sum(len(adj[a]&adj[b]) for a,b in combinations(range(k),2))
    mixing=sum(state.degrees[a]*state.degrees[b] for a,b in edges if (a<k)!=(b<k))/max(1,boundary)
    return np.array([inside,boundary,triangles,pairs,mixing],dtype=float)


def context_basic(record):
    n,k=record['n'],record['core_n']
    state=State(n,record['edges'])
    d=np.asarray(state.degrees,dtype=float)
    boundary=sum((a<k)!=(b<k) for a,b in state.edges)
    return basic_features(record)+[k/n,n-k,boundary,boundary/k,float(d[:k].mean()),float(d[:k].max()),float(d[:k].std()),float(d[k:].mean()) if n>k else 0.,float(d[k:].max(initial=0)),boundary/max(1,len(state.edges))]


def context_graph(record,seed):
    k=record['core_n']
    g=nx.Graph();g.add_nodes_from(range(record['n']));g.add_edges_from(record['edges'])
    pr=nx.pagerank(g,alpha=.85,tol=1e-8,max_iter=1000)
    clustering=nx.clustering(g,nodes=range(k))
    core=nx.core_number(g)
    volume=sum(g.degree(i) for i in range(k))
    other_volume=2*g.number_of_edges()-volume
    boundary=sum((a<k)!=(b<k) for a,b in g.edges())
    marked_nx=[sum(pr[i] for i in range(k)),max(pr[i] for i in range(k)),np.mean(list(clustering.values())),np.mean([core[i] for i in range(k)]),max(core[i] for i in range(k)),boundary/max(1,min(volume,other_volume))]
    cr=core_record(record)
    return basic_features(cr)+graph_features(cr,seed)+context_basic(record)+graph_features(record,seed)+list(map(float,marked_nx))+marked_targets(State(record['n'],record['edges']),k).tolist()


def context_null(record,*,kernel,seed,burn=512,samples=32,stride=64):
    if kernel not in ('paper','edge'):raise ValueError(kernel)
    if burn<0 or samples<2 or stride<1:raise ValueError('Invalid sampler budget')
    state=State(record['n'],record['edges']);k=record['core_n']
    def targets():return np.r_[structural_targets(state),marked_targets(state,k)]
    observed=targets();size=len(observed)
    if not state.has_switch():
        return np.r_[np.zeros(size),np.ones(2*size)],{'frozen':True,'proposals':0,'accepted':0,'distinct_states':1,'varying_targets':0}
    rng=random.Random(seed)
    step=state.step_paper if kernel=='paper' else state.step_edge
    accepted=sum(step(rng) for _ in range(burn))
    values=[];seen=set()
    for _ in range(samples):
        accepted+=sum(step(rng) for _ in range(stride))
        values.append(targets());seen.add(tuple(sorted(state.edges)))
    assert tuple(map(len,state.adj))==state.degrees
    draws=np.asarray(values)
    residual=(observed-draws.mean(axis=0))/np.sqrt(draws.var(axis=0,ddof=1)+1)
    upper=(1+(draws>=observed-1e-12).sum(axis=0))/(samples+1)
    lower=(1+(draws<=observed+1e-12).sum(axis=0))/(samples+1)
    return np.r_[residual,upper,lower],{'frozen':False,'proposals':burn+samples*stride,'accepted':int(accepted),'distinct_states':len(seen),'varying_targets':int((np.ptp(draws,axis=0)>1e-12).sum())}
