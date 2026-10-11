"""Additional ready-method baseline retaining direction and multiplicity."""
import json
from collections import Counter

import networkx as nx
import numpy as np
import pandas as pd

from .data import OUT

DIRECTED_NAMES = ["log_transactions", "parallel_ratio", "max_in_degree", "max_out_degree", "std_in_degree", "std_out_degree", "source_fraction", "sink_fraction", "reciprocity", "scc_fraction", "largest_scc_fraction", "directed_pagerank_max", "directed_pagerank_entropy", "dag", "dag_longest_path_fraction", "max_weighted_in", "max_weighted_out"]


def prepare():
    records = json.loads((OUT / "sample.json").read_text(encoding="utf-8"))
    selected = {r["id"] for r in records}
    nodes = pd.read_csv(OUT / "raw/nodes.csv")
    mapping = {}
    for cid, group in nodes[nodes.ccId.isin(selected)].groupby("ccId"):
        for i, node in enumerate(sorted(group.clId)):
            mapping[node] = (int(cid), i)
    result = {str(cid): [] for cid in selected}
    for a, b in pd.read_csv(OUT / "raw/edges.csv", usecols=["clId1", "clId2"]).itertuples(index=False, name=None):
        if a in mapping:
            cid, i = mapping[a]
            assert mapping[b][0] == cid
            result[str(cid)].append([i, mapping[b][1]])
    (OUT / "directed.json").write_text(json.dumps(result, separators=(",", ":")), encoding="utf-8")
    print("Saved direction-preserving input for the same 20,000 graphs")


def directed_features(n, edges):
    counts = Counter(map(tuple, edges))
    g = nx.DiGraph()
    g.add_nodes_from(range(n))
    g.add_weighted_edges_from((a, b, w) for (a, b), w in counts.items())
    indeg = np.array([g.in_degree(i) for i in range(n)])
    outdeg = np.array([g.out_degree(i) for i in range(n)])
    scc = list(nx.strongly_connected_components(g))
    pr = np.array(list(nx.pagerank(g, weight="weight", tol=1e-8, max_iter=1000).values()))
    dag = nx.is_directed_acyclic_graph(g)
    return [np.log1p(len(edges)), len(edges) / max(1, len(counts)), indeg.max(), outdeg.max(), indeg.std(), outdeg.std(), (indeg == 0).mean(), (outdeg == 0).mean(), nx.reciprocity(g) if counts else 0, len(scc) / n, max(map(len, scc)) / n, pr.max(), -(pr * np.log(pr)).sum(), float(dag), nx.dag_longest_path_length(g, weight=None) / n if dag else 0, max(dict(g.in_degree(weight="weight")).values()), max(dict(g.out_degree(weight="weight")).values())]


if __name__ == "__main__":
    prepare()
