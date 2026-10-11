from __future__ import annotations

import math

import networkx as nx
import numpy as np

from .switches import State, TARGET_NAMES, structural_targets

BASIC_NAMES = ["log_nodes", "log_edges", "density", "mean_degree", "max_degree", "std_degree", "leaf_fraction", "degree2_fraction", "isolate_fraction"]
GRAPH_NAMES = TARGET_NAMES + ["transitivity", "mean_clustering", "max_core", "mean_core", "max_pagerank", "pagerank_entropy", "louvain_count", "louvain_modularity", "bridge_fraction", "articulation_fraction", "global_efficiency"]


def basic_features(record):
    n, edges = record["n"], record["edges"]
    degree = np.zeros(n, dtype=float)
    for a, b in edges:
        degree[a] += 1
        degree[b] += 1
    m = len(edges)
    return [math.log1p(n), math.log1p(m), 2 * m / max(1, n * (n - 1)), float(degree.mean()), float(degree.max(initial=0)), float(degree.std()), float((degree == 1).mean()), float((degree == 2).mean()), float((degree == 0).mean())]


def graph_features(record, seed):
    n, edges = record["n"], record["edges"]
    g = nx.Graph()
    g.add_nodes_from(range(n))
    g.add_edges_from(edges)
    raw = structural_targets(State(n, edges)).tolist()
    core = list(nx.core_number(g).values())
    pr = np.asarray(list(nx.pagerank(g, alpha=0.85, tol=1e-8, max_iter=1000).values()))
    if edges:
        communities = nx.community.louvain_communities(g, seed=seed, weight=None)
        modularity = nx.community.modularity(g, communities, weight=None)
    else:
        communities, modularity = [{i} for i in range(n)], 0.0
    return raw + [nx.transitivity(g), nx.average_clustering(g), max(core, default=0), float(np.mean(core)), float(pr.max(initial=0)), float(-(pr * np.log(pr)).sum()), len(communities), modularity, len(list(nx.bridges(g))) / max(1, len(edges)), len(list(nx.articulation_points(g))) / max(1, n), nx.global_efficiency(g)]
