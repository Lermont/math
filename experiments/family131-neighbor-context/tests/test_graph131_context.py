import itertools
import random
import unittest

import networkx as nx
import numpy as np

from graph131.context_data import prepare_records
from graph131.context_features import (context_null, marked_targets, context_graph,
    CONTEXT_GRAPH_NAMES)
from graph131.switches import State


class ContextTests(unittest.TestCase):
    def test_split_isolation_and_original_preservation(self):
        selection=[{'id':1,'y':0,'split':'train'},{'id':2,'y':1,'split':'test'}]
        members={1:{10,11},2:{20,21}}
        original={1:[(10,11,1)],2:[(20,21,2)]}
        incident=[(10,11,1),(20,21,2),(10,90,3),(20,90,4),
                  (11,91,5),(21,92,5),(11,93,6),(20,94,7),
                  (10,20,8),(10,80,9)]
        records,stats,audit=prepare_records(selection,members,original,incident,{10,11,20,21,80})
        self.assertEqual(records[0]['nodes'],[10,11,93])
        self.assertEqual(records[1]['nodes'],[20,21,94])
        self.assertEqual(records[0]['core_edges'],[(0,1)])
        self.assertEqual(audit['shared_external_nodes_purged'],1)
        self.assertEqual(audit['shared_transaction_ids_context_purged'],1)
        self.assertTrue(all(v==0 for x in audit['overlaps'].values() for v in x.values()))
        # The label values cannot affect graph selection.
        reverse=[{**r,'y':1-r['y']} for r in selection]
        changed,_,_=prepare_records(reverse,members,original,reversed(incident),{10,11,20,21,80})
        for a,b in zip(records,changed):
            self.assertEqual({k:v for k,v in a.items() if k!='y'},{k:v for k,v in b.items() if k!='y'})

    def test_cap_deterministic_and_direction_preserved(self):
        selection=[{'id':1,'y':0,'split':'train'}]
        incident=[(0,i,10+i) for i in range(2,50)]+[(2,0,99),(0,2,100)]
        a,_,_=prepare_records(selection,{1:{0,1}},{1:[(0,1,0)]},incident,{0,1},cap=4)
        b,_,_=prepare_records(selection,{1:{0,1}},{1:[(0,1,0)]},reversed(incident),{0,1},cap=4)
        self.assertEqual(a,b);self.assertEqual(a[0]['n'],6)
        c,_,_=prepare_records(selection,{1:{0,1}},{1:[(0,1,0)]},incident,{0,1},cap=100)
        self.assertEqual(len(c[0]['directed']),len(incident)+1)
        self.assertEqual(len(c[0]['edges']),49)

    def test_marked_counts_against_matrix_and_cliques(self):
        rng=random.Random(131)
        for n in range(3,12):
            k=n//2
            edges=[e for e in itertools.combinations(range(n),2) if rng.random()<.4]
            g=nx.Graph();g.add_nodes_from(range(n));g.add_edges_from(edges)
            a=nx.to_numpy_array(g,nodelist=range(n));a2=a@a
            triangles=sum(1 for c in nx.enumerate_all_cliques(g) if len(c)==3 and any(v<k for v in c))
            values=marked_targets(State(n,edges),k)
            self.assertEqual(values[0],a[:k,:k].sum()/2)
            self.assertEqual(values[1],a[:k,k:].sum())
            self.assertEqual(values[2],triangles)
            self.assertEqual(values[3],sum(a2[i,j] for i,j in itertools.combinations(range(k),2)))

    def test_null_reproducible_budget_and_frozen(self):
        r={'id':1,'n':8,'core_n':3,'edges':list(nx.cycle_graph(8).edges()),'core_edges':[(0,1),(1,2)]}
        for kernel in ('paper','edge'):
            values,d=context_null(r,kernel=kernel,seed=5,burn=100,samples=10,stride=20)
            v2,d2=context_null(r,kernel=kernel,seed=5,burn=100,samples=10,stride=20)
            np.testing.assert_array_equal(values,v2);self.assertEqual(d,d2)
            self.assertEqual(d['proposals'],300);self.assertEqual(values.shape,(30,));self.assertTrue(np.isfinite(values).all())
        values,d=context_null({'n':3,'core_n':2,'edges':[(0,1),(0,2)]},kernel='paper',seed=1)
        self.assertTrue(d['frozen']);np.testing.assert_equal(values,np.r_[np.zeros(10),np.ones(20)])
        self.assertEqual(len(context_graph(r,seed=1)),len(CONTEXT_GRAPH_NAMES))


if __name__=='__main__':unittest.main()
