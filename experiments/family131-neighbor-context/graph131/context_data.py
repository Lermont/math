"""Prepare split-isolated one-hop incident contexts from a complete scan."""
from __future__ import annotations

from collections import defaultdict
import hashlib
import json
import time

import numpy as np
import pandas as pd
import psutil

from .context_download import OUT, RAW, ROOT

SPLIT_BITS={'train':1,'val':2,'test':4}


def neighbor_key(cid, node):
    return hashlib.blake2b(f'{cid}:{node}:1312027'.encode(),digest_size=8).digest()


def prepare_records(selection, members, original, incident, all_core_nodes, cap=32):
    lookup={node:r['id'] for r in selection for node in members[r['id']]}
    splits={r['id']:r['split'] for r in selection}
    candidate=defaultdict(set)
    external_masks=defaultdict(int)
    tx_masks=defaultdict(int)
    original_tx_masks=defaultdict(int)
    for cid,rows in original.items():
        if cid in splits:
            for a,b,tx in rows:
                tx_masks[tx]|=SPLIT_BITS[splits[cid]]
                original_tx_masks[tx]|=SPLIT_BITS[splits[cid]]
    removed_other_core=0
    for a,b,tx in incident:
        for cid in {lookup[v] for v in (a,b) if v in lookup}:
            # Keep own-core pairs; other annotated subgraphs cannot become context.
            core=members[cid]
            if any(v in all_core_nodes and v not in core for v in (a,b)):
                removed_other_core+=1
                continue
            candidate[cid].add((a,b,tx))
            bit=SPLIT_BITS[splits[cid]]
            tx_masks[tx]|=bit
            for v in (a,b):
                if v not in core:external_masks[v]|=bit
    shared_nodes={v for v,mask in external_masks.items() if mask.bit_count()>1}
    shared_txs={v for v,mask in tx_masks.items() if mask.bit_count()>1}
    assert all(mask.bit_count()==1 for mask in original_tx_masks.values())
    records=[]
    stats=[]
    for r in selection:
        cid=r['id']; core=members[cid]
        rows=candidate[cid]
        raw_neighbors={v for a,b,_ in rows for v in (a,b) if v not in core}
        # Original core transactions remain; purge conflicting context occurrences.
        original_rows=set(original.get(cid,[]))
        clean={row for row in rows if not ({row[0],row[1]} & shared_nodes) and row[2] not in shared_txs}
        clean|=original_rows
        available={v for a,b,_ in clean for v in (a,b) if v not in core}
        chosen=set(sorted(available,key=lambda v:neighbor_key(cid,v))[:cap])
        node_order=sorted(core)+sorted(chosen)
        local={v:i for i,v in enumerate(node_order)}
        clean={row for row in clean if row[0] in local and row[1] in local}
        simple=sorted({tuple(sorted((local[a],local[b]))) for a,b,_ in clean if a!=b})
        core_edges=sorted({tuple(sorted((local[a],local[b]))) for a,b,_ in original_rows if a!=b})
        drows=sorted(clean)
        rec={**r,'core_n':len(core),'n':len(node_order),'nodes':node_order,'edges':simple,
             'core_edges':core_edges,'directed':[[local[a],local[b]] for a,b,tx in drows],
             'transactions':[tx for a,b,tx in drows]}
        assert set(map(tuple,core_edges))<=set(map(tuple,simple))
        records.append(rec)
        stats.append({'id':cid,'split':r['split'],'y':r['y'],'core_n':len(core),'raw_neighbors':len(raw_neighbors),'eligible_neighbors':len(available),'kept_neighbors':len(chosen),'capped':len(available)>cap,'n':len(node_order),'m':len(simple),'directed_rows':len(drows),'self_loops':sum(a==b for a,b,_ in drows),'rows_collapsed_by_simple_projection':len(drows)-len(simple)})
    overlaps={}
    for key in ('nodes','transactions'):
        sets={s:{v for r in records if r['split']==s for v in r[key]} for s in SPLIT_BITS}
        overlaps[key]={f'{a}_{b}':len(sets[a]&sets[b]) for a,b in [('train','val'),('train','test'),('val','test')]}
    assert all(v==0 for d in overlaps.values() for v in d.values()), overlaps
    audit={'shared_external_nodes_purged':len(shared_nodes),'shared_transaction_ids_context_purged':len(shared_txs),'candidate_incidences_to_other_annotated_cores_removed':removed_other_core,'overlaps':overlaps,'cap_external_nodes':cap}
    return records,stats,audit


def run():
    t=time.perf_counter()
    acquisition=json.loads((OUT/'acquisition.json').read_text())
    assert acquisition['crc_verified']
    assert hashlib.sha256((OUT/'raw/incident-edges.csv').read_bytes()).hexdigest()==acquisition['retained_sha256']
    assert hashlib.sha256((OUT/'selection.json').read_bytes()).hexdigest()==acquisition['selection_sha256']
    sources=json.loads((ROOT/'references/graph131/sources.json').read_text())
    for source in sources['files']:
        assert hashlib.sha256((RAW/source['name']).read_bytes()).hexdigest()==source['sha256']
    selection=json.loads((OUT/'selection.json').read_text())
    nodes=pd.read_csv(RAW/'nodes.csv')
    selected={r['id'] for r in selection}
    members=nodes[nodes.ccId.isin(selected)].groupby('ccId').clId.apply(set).to_dict()
    node_cc=dict(zip(nodes.clId,nodes.ccId))
    original=defaultdict(list)
    for a,b,tx in pd.read_csv(RAW/'edges.csv').itertuples(index=False,name=None):
        cid=node_cc[a]
        if cid in selected:original[cid].append((a,b,tx))
    incident=pd.read_csv(OUT/'raw/incident-edges.csv')
    observed_rows=set(incident.itertuples(index=False,name=None))
    expected_rows={row for rows in original.values() for row in rows}
    observed_nodes=set(incident.clId1)|set(incident.clId2)
    expected_nodes=set().union(*members.values())
    records,stats,audit=prepare_records(selection,members,original,incident.itertuples(index=False,name=None),set(nodes.clId))
    frame=pd.DataFrame(stats)
    frame.to_csv(OUT/'contexts.csv',index=False)
    path=OUT/'sample.json'
    path.write_text(json.dumps(records,separators=(',',':')))
    audit.update({'count':len(records),'sample_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
        'original_core_edge_rows':len(expected_rows),'original_core_rows_missing_in_background':len(expected_rows-observed_rows),
        'selected_core_nodes_absent_in_background_edges':len(expected_nodes-observed_nodes),
        'split':{s:{'count':sum(r['split']==s for r in records),'suspicious':sum(r['y'] for r in records if r['split']==s)} for s in SPLIT_BITS},
        'with_external_context':int((frame.kept_neighbors>0).sum()),'capped_subgraphs':int(frame.capped.sum()),
        'selected_context_self_loops':int(frame.self_loops.sum()),'rows_collapsed_by_simple_projection':int(frame.rows_collapsed_by_simple_projection.sum()),
        'incident_exact_duplicate_rows':int(incident.duplicated().sum()),
        'node_statistics':frame[['core_n','raw_neighbors','eligible_neighbors','kept_neighbors','n','m']].describe().to_dict(),
        'elapsed_seconds':time.perf_counter()-t,'peak_rss_mib':psutil.Process().memory_info().peak_wset/2**20})
    (OUT/'data_audit.json').write_text(json.dumps(audit,indent=2))
    print(json.dumps(audit,indent=2))


if __name__=='__main__':run()
