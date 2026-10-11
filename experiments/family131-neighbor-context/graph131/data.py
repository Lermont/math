from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/elliptic2"


def prepare(count=20000, seed=1312026):
    raw = OUT / "raw"
    labels = pd.read_csv(raw / "connected_components.csv")
    nodes = pd.read_csv(raw / "nodes.csv")
    edges = pd.read_csv(raw / "edges.csv")
    assert set(labels.ccLabel) == {"licit", "suspicious"}
    assert labels.ccId.is_unique and nodes.clId.is_unique
    mapping = dict(zip(nodes.clId, nodes.ccId))
    edge_groups = {}
    crossing = missing = loops = 0
    for a, b, tx in edges.itertuples(index=False, name=None):
        if a not in mapping or b not in mapping:
            missing += 1
            continue
        if mapping[a] != mapping[b]:
            crossing += 1
            continue
        loops += a == b
        edge_groups.setdefault(mapping[a], []).append((a, b, tx))
    assert crossing == missing == 0
    ids = labels.ccId.to_numpy()
    ys = (labels.ccLabel == "suspicious").to_numpy(dtype=int)
    keep, _ = train_test_split(np.arange(len(ids)), train_size=count, stratify=ys, random_state=seed)
    tr, remaining = train_test_split(keep, test_size=0.4, stratify=ys[keep], random_state=seed + 1)
    va, te = train_test_split(remaining, test_size=0.5, stratify=ys[remaining], random_state=seed + 2)
    split = {int(ids[i]): name for name, inds in (("train", tr), ("val", va), ("test", te)) for i in inds}
    grouped_nodes = nodes.groupby("ccId").clId.apply(list).to_dict()
    records, transactions = [], {name: set() for name in ("train", "val", "test")}
    removed_parallel = 0
    for i in sorted(keep, key=lambda i: int(ids[i])):
        cid = int(ids[i])
        members = sorted(grouped_nodes[cid])
        local = {node: j for j, node in enumerate(members)}
        original = edge_groups.get(cid, [])
        simple = sorted({tuple(sorted((local[a], local[b]))) for a, b, _ in original if a != b})
        removed_parallel += len(original) - len(simple)
        transactions[split[cid]].update(tx for _, _, tx in original)
        records.append({"id": cid, "y": int(ys[i]), "split": split[cid], "n": len(members), "edges": simple})
    overlaps = {f"{a}_{b}": len(transactions[a] & transactions[b]) for a, b in (("train", "val"), ("train", "test"), ("val", "test"))}
    # Shared transactions can link distinct endpoint pairs; do not silently permit it.
    if any(overlaps.values()):
        raise ValueError(f"Cross-split transaction leakage: {overlaps}")
    path = OUT / "sample.json"
    path.write_text(json.dumps(records, separators=(",", ":")), encoding="utf-8")
    audit = {
        "seed": seed, "source_subgraphs": len(labels), "source_suspicious": int(ys.sum()),
        "source_node_memberships": len(nodes), "unique_source_nodes": nodes.clId.nunique(),
        "source_edge_rows": len(edges), "source_self_loops": int(loops),
        "cross_subgraph_edges": crossing, "missing_endpoints": missing,
        "sample_subgraphs": len(records), "sample_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "sample_removed_parallel_or_reverse_edges": removed_parallel,
        "transaction_overlap": overlaps, "node_overlap": 0,
        "split": {s: {"count": sum(r["split"] == s for r in records), "suspicious": sum(r["y"] for r in records if r["split"] == s)} for s in ("train", "val", "test")},
        "sample_fewer_than_four_nodes": sum(r["n"] < 4 for r in records),
        "sample_max_nodes": max(r["n"] for r in records),
        "raw_hashes": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in raw.glob("*.csv")},
    }
    (OUT / "data_audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    pd.DataFrame([{k: r[k] for k in ("id", "y", "split", "n")} for r in records]).to_csv(OUT / "split.csv", index=False)
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=20000)
    args = parser.parse_args()
    prepare(args.count)
