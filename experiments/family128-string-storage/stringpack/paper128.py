"""Reference port of family 128, sections 2--7, at upstream fd4aeeb.

Adapted from OpenAI's Apache-2.0 manuscript; this Python translation is new.
No greedy approximation, exact solver, or heuristic replaces the paper's
connection algorithm. Assertions are executable construction invariants, not
a machine-checked proof of this translation. See references/sources.json.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from functools import cmp_to_key
from time import perf_counter


class ResourceLimit(RuntimeError):
    pass


def primitive(s: bytes) -> bytes:
    for p in range(1, len(s) + 1):
        if len(s) % p == 0 and s == s[:p] * (len(s) // p):
            return s[:p]
    raise AssertionError("nonempty period required")


def word(text: bytes, a: int, b: int, shift: int = 0) -> bytes:
    assert b >= a and text
    p = len(text)
    start = (a - shift) % p
    return (text * ((start + b - a + p - 1) // p))[start:start + b - a]


@dataclass
class Layer:
    id: int
    group: bytes
    z: tuple[int, ...]
    rank: int

    @property
    def p(self):
        return len(self.group)

    def last(self, x):
        q, r = divmod(x, self.p)
        return self.z[r] + q * self.p

    def first(self, x):
        return self.last(x - 1)

    def windows(self):
        for a in range(self.p):
            for b in range(self.first(a), self.last(a) + 1):
                yield a, b

    def shortest(self):
        a = min(range(self.p), key=lambda x: (self.first(x) - x, x))
        return a, self.first(a)


@dataclass
class Record:
    target: int
    a: int                 # source-text coordinates
    b: int
    u: int                 # target-text coordinates
    v: int


@dataclass
class Block:
    layers: list[Layer]
    record: Record
    collective: bool
    t: int

    @property
    def p(self):
        return self.layers[0].p


def euler(edges: Counter, start: bytes):
    adj = defaultdict(list)
    for (a, b), count in sorted(edges.items(), reverse=True):
        adj[a].extend([b] * count)
    stack, out = [start], []
    while stack:
        a = stack[-1]
        if adj[a]:
            stack.append(adj[a].pop())
        else:
            out.append(stack.pop())
    out.reverse()
    return out


class Construction:
    def __init__(self, strings, max_vertices=12000, max_seconds=None):
        self.started = perf_counter()
        self.deadline = self.started + max_seconds if max_seconds else float("inf")
        self.stats = {"algorithm": "paper128_reference", "branch_counts": Counter()}
        unique = sorted(set(strings), key=lambda s: (-len(s), s))
        self.required = []
        for i, s in enumerate(unique):
            if i % 64 == 0:
                self.check()
            if s and not any(s in t for t in self.required):
                self.required.append(s)
        self.V = {b""}
        for s in self.required:
            for i in range(len(s)):
                self.V.update(s[i:j] for j in range(i + 1, len(s) + 1))
                if max_vertices and len(self.V) > max_vertices:
                    raise ResourceLimit(f"substring vertices exceed {max_vertices}")
                self.check()
        self.ordered = sorted(self.V - {b""}, key=lambda s: (-len(s), s))
        self.m = {}
        self.base, self.extra = Counter(), Counter()
        self.block_cache = {}
        self.rooted = set()
        self.blocks = []
        self.requests = defaultdict(list)
        self.stats.update(input_count=len(strings), core_count=len(self.required),
                          vertices=len(self.V))

    def check(self):
        if perf_counter() > self.deadline:
            raise ResourceLimit("paper construction exceeded time budget")

    def blocking(self, text, s):
        key = text, s
        if key in self.block_cache:
            return self.block_cache[key]
        total, p = 0, len(text)
        # All contributing words are longer and have final counts already.
        for idx, (r, count) in enumerate(self.m.items()):
            if idx % 2048 == 0:
                self.check()
            if not count or len(r) < len(s) + 2:
                continue
            j = r.find(s, 1, len(r) - 1)
            while j != -1:
                if (r[0] != text[-j % p] and r[-1] != text[(len(r)-1-j) % p]
                        and r[1:-1] == word(text, 1-j, len(r)-1-j)):
                    total += count
                j = r.find(s, j + 1, len(r) - 1)
        self.block_cache[key] = total
        return total

    def counts(self):
        required = set(self.required)
        left, right = defaultdict(int), defaultdict(int)
        # A rule discovered at v constrains a shorter w, but B_A(w) must
        # be evaluated only when ALL words longer than w have final counts.
        # Evaluating it eagerly at v misses intermediate-length blockers.
        lower = defaultdict(dict)
        rules = 0
        for v in self.ordered:
            self.check()
            bound = max((self.blocking(text, v) + k1
                         for text, k1 in lower[v].items()), default=0)
            self.m[v] = max(left[v], right[v], bound, int(v in required))
            # Propagate extensions to their proper prefix/suffix.
            left[v[1:]] += self.m[v]
            right[v[:-1]] += self.m[v]
            for p in range(1, len(v)):
                if v[p:] != v[:-p]:
                    continue
                template = primitive(v[:p])
                if self.m[v] <= self.blocking(template, v):
                    continue
                for k in range(1, (len(v)-1)//p + 1):
                    w = v[:len(v)-k*p]
                    lower[w][template] = max(lower[w].get(template, 0), k + 1)
                    rules += 1
        for s in self.ordered:
            u, d = self.m[s] - left[s], self.m[s] - right[s]
            assert u >= 0 and d >= 0
            if u:
                self.base[s[:-1], s] += u
            if d:
                self.base[s, s[1:]] += d
        self.W = sum(m for s, m in self.m.items() if len(s) == 1)
        assert sum(self.base.values()) == 2*self.W
        self.stats.update(lower_bound=self.W, period_rules=rules,
                          blocking_queries=len(self.block_cache))

    def decompose(self):
        remaining = +self.base
        exits = defaultdict(lambda: defaultdict(list))
        while remaining:
            start = min(a for a, _ in remaining)
            tour = euler(remaining, start)
            assert tour[0] == tour[-1]
            for edge in zip(tour, tour[1:]):
                remaining[edge] -= 1
            remaining = +remaining
            letters = bytes(b[-1] for a, b in zip(tour, tour[1:]) if len(b) > len(a))
            P = len(letters)
            initial = bytes(letters[(i-len(start)) % P] for i in range(P))
            root = primitive(initial)
            rotations = [root[t:]+root[:t] for t in range(len(root))]
            rotation = min(range(len(root)), key=lambda t: rotations[t])
            canonical, p = rotations[rotation], len(root)
            x, end = -rotation, len(start)-rotation
            assert word(canonical, x, end) == start
            for a, b in zip(tour, tour[1:]):
                if len(b) > len(a):
                    end += 1
                else:
                    residue = x % p
                    exits[canonical][residue].append(end-(x-residue))
                    x += 1
                assert word(canonical, x, end) == b
        self.groups, self.layers = {}, []
        for text in sorted(exits, key=lambda s: (len(s), s)):
            columns = [sorted(exits[text][r]) for r in range(len(text))]
            assert len({len(c) for c in columns}) == 1
            group = []
            for rank in range(len(columns[0])):
                layer = Layer(len(self.layers), text, tuple(c[rank] for c in columns), rank)
                for x in range(layer.p):
                    assert x <= layer.first(x) <= layer.last(x)
                self.layers.append(layer)
                group.append(layer)
            self.groups[text] = group
        reproduced = Counter()
        for layer in self.layers:
            for x in range(layer.p):
                for end in range(layer.first(x), layer.last(x)):
                    reproduced[word(layer.group,x,end),word(layer.group,x,end+1)] += 1
                end = layer.last(x)
                reproduced[word(layer.group,x,end),word(layer.group,x+1,end)] += 1
        assert reproduced == self.base
        self.stats.update(layers=len(self.layers), groups=len(self.groups))

    def add_walk(self, path):
        assert path and path[0] == path[-1]
        for a, b in zip(path, path[1:]):
            assert a in self.V and b in self.V
            assert (len(b)==len(a)+1 and b[:-1]==a) or (a and a[1:]==b)
            self.extra[a,b] += 1
        return min(path, key=lambda s: (len(s), s))

    def ordered_walk(self, text, windows, shift=0):
        path = [word(text,*windows[0],shift)]
        for (a,b),(c,d) in zip(windows,windows[1:]):
            assert a <= c and b <= d
            cur = path[-1]
            for _ in range(min(c,b)-a):
                cur = cur[1:]
                path.append(cur)
            if c > b:
                for i in range(b,c):
                    path.extend([word(text,i,i+1,shift),b""])
                cur = b""
            for i in range(max(b,c),d):
                cur += word(text,i,i+1,shift)
                path.append(cur)
            assert cur == word(text,c,d,shift)
        return self.add_walk(path)

    def root_word(self, s):
        path = [s]
        for i in range(1,len(s)+1):
            path.append(s[i:])
        for i in range(1,len(s)+1):
            path.append(s[:i])
        self.add_walk(path)

    def band(self, layers, t, h):
        layers = sorted(layers,key=lambda l:l.rank)
        E, H = layers[0].last(t), layers[-1].first(t)
        assert H-E <= h and h % layers[0].p == 0
        if E < H:
            self.ordered_walk(layers[0].group,[(t,E),(t,H),(t+h,E+h)])

    def find_record(self, text, t, end):
        w = word(text,t,end)
        for target in self.layers:
            self.check()
            for u,v in target.windows():
                r = word(target.group,u,v)
                j = r.find(w)
                while j >= 0:
                    a,b = t-j,t-j+len(r)
                    delta = a-u
                    if (word(text,a,b)==r and
                        word(text,0,len(text)+target.p) !=
                        word(target.group,0,len(text)+target.p,delta)):
                        return Record(target.id,a,b,u,v)
                    j = r.find(w,j+1)
        raise AssertionError("count rule supplied no matching record")

    def fulfill_host(self, host):
        # Bring each child coordinate system into the host's fixed coordinates.
        records = []
        for layers, rec in self.requests[host.id]:
            shift = rec.u-rec.a
            records.append(dict(layers=layers,a=rec.u,b=rec.v,shift=shift,
                                p=layers[0].p,text=layers[0].group))
        first = min(records,key=lambda r:(r["p"],r["text"]))
        a0,b0,q = first["a"],first["b"],host.p
        for r in records:
            if (r["a"],r["b"]) < (a0,b0):
                for k in ("a","b","shift"):
                    r[k] += q
            r["ends"] = sorted(l.first(r["a"]-r["shift"])+r["shift"]
                               for l in r["layers"])
        records.sort(key=lambda r:(r["a"],r["b"],r["p"],r["text"]))
        assert records[0] is first
        ends0,T = first["ends"],a0+q
        windows = [(a0,e) for e in ends0] + [(a0,b0)]
        attachments = []
        for r in records[1:]:
            a,b,p = r["a"],r["b"],r["p"]
            for e in r["ends"]:
                assert a+p < e <= b-p
                s,h = min(a+p,T),max(e,b0)
                windows.append((s,h))
                attachments.append((r,[(s,h),(a+p,e+p),(s+p,h+p)]))
        windows.append((T,ends0[0]+q))
        short = self.ordered_walk(host.group,windows)
        assert len(short) < first["p"]
        for r,wins in attachments:
            self.ordered_walk(r["text"],wins,r["shift"])
        self.root_word(short)
        self.rooted.add(host.id)
        for r in records:
            self.rooted.update(l.id for l in r["layers"])
        self.stats["branch_counts"]["host"] += 1

    def process_groups(self):
        for text, group in self.groups.items():
            self.check()
            p = len(text)
            recipients = [l for l in group if self.requests[l.id]]
            for host in recipients:
                self.fulfill_host(host)
            baseline = max(recipients,key=lambda l:l.rank) if recipients else None
            if baseline:
                a,h = baseline.shortest()
                assert h-a < 2*p
                for layer in group[:baseline.rank]:
                    if layer.id in self.rooted:
                        continue
                    x,e = layer.shortest()
                    if e-x <= p:
                        self.root_word(word(text,x,e))
                    else:
                        e = min(layer.last(a),h)
                        self.ordered_walk(text,[(a,h),(a+p,e+p),(a+p,h+p)])
                    self.rooted.add(layer.id)
            upper = group[baseline.rank+1:] if baseline else group[:]
            n = len(upper)
            if not n:
                continue
            top = upper[-1]
            t = max(range(p),key=lambda x:word(text,x,x+p))
            H = top.first(t)
            if H-t <= n*p:
                self.root_word(word(text,t,H))
                self.rooted.update(l.id for l in upper)
                self.stats["branch_counts"]["easy_root"] += 1
                continue
            if baseline and baseline.last(t) >= H-n*p:
                self.band([baseline]+upper,t,n*p)
                self.rooted.update(l.id for l in upper)
                self.stats["branch_counts"]["baseline_band"] += 1
                continue
            k = 1
            while sum(l.last(t) >= H-k*p for l in group) > k:
                k += 1
            assert k <= n
            K = k*p
            selected = upper[-k:]
            low = selected[0]
            assert low.last(t) >= H-(k-1)*p
            rec = self.find_record(text,t,H-K)
            a,b = rec.a,rec.b
            individual = upper[:]
            if low.last(a)+K >= b:
                self.blocks.append(Block(selected,rec,True,t))
                individual = upper[:-k]
                self.stats["branch_counts"]["collective"] += 1
            requests = []
            for layer in individual:
                x,e = layer.shortest()
                if e-x <= p:
                    self.root_word(word(text,x,e))
                    self.rooted.add(layer.id)
                    self.stats["branch_counts"]["individual_root"] += 1
                elif layer.last(a)+p >= b:
                    self.blocks.append(Block([layer],rec,False,t))
                    self.stats["branch_counts"]["individual_link"] += 1
                else:
                    assert a+p < layer.first(a) <= layer.last(a) < b-p
                    requests.append(layer)
            if requests:
                assert self.layers[rec.target].p > p
                self.requests[rec.target].append((requests,rec))

    def realize(self, block, special=False):
        layers,rec,p = block.layers,block.record,block.p
        text,a,b = layers[0].group,rec.a,rec.b
        if not block.collective:
            layer = layers[0]
            e = max(layer.first(a+p),b)
            assert e <= min(layer.last(a+p),b+p)
            return self.ordered_walk(text,[(a,b),(a+p,e),(a+p,b+p)])
        K = len(layers)*p
        top = layers[-1]
        q = self.layers[rec.target].p
        short = min((word(text,*l.shortest()) for l in layers),key=lambda s:(len(s),s))
        if special and len(short) > q:
            x = min(block.t,a+K)
            F = top.first(x)
            assert b-x < q and b < F <= b+K
            return self.ordered_walk(text,[(a,b),(x,b),(x,F),(a+K,b+K)])
        Y = max(b,top.first(a))
        windows = [(a,b)]
        for layer in reversed(layers):
            x = next(x for x in range(a,a+K+1) if layer.last(x) >= Y)
            assert layer.first(x) <= Y
            windows.append((x,Y))
        windows.append((a+K,b+K))
        contact = self.ordered_walk(text,windows)
        return min([short,contact],key=lambda s:(len(s),s))

    def finish_blocks(self):
        owners = {l.id:i for i,b in enumerate(self.blocks) for l in b.layers}
        assert len(owners)+len(self.rooted) == len(self.layers)
        assert not (set(owners)&self.rooted)
        targets = [owners.get(b.record.target) for b in self.blocks]
        seen,cycles = set(),[]
        for i in range(len(self.blocks)):
            path,index = [],{}
            while i is not None and i not in seen and i not in index:
                index[i] = len(path)
                path.append(i)
                i = targets[i]
            if i in index:
                cycles.append(path[index[i]:])
            seen.update(path)
        def compare(i,j):
            a,b = self.blocks[i],self.blocks[j]
            n = a.p+b.p
            av,bv = word(a.layers[0].group,a.t,a.t+n),word(b.layers[0].group,b.t,b.t+n)
            return (av>bv)-(av<bv)
        done = set()
        for cycle in cycles:
            if len(cycle)==1:
                i = cycle[0]
                b = self.blocks[i]
                self.band(b.layers,b.t,(len(b.layers)-1)*b.p)
                contact = word(b.layers[0].group,b.record.a,b.record.b)
                assert len(contact) < b.p
                self.root_word(contact)
                done.add(i)
                self.stats["branch_counts"]["self_cycle"] += 1
            else:
                i = max(cycle,key=cmp_to_key(compare))
                target = targets[i]
                b = self.blocks[target]
                contact = self.realize(self.blocks[i],special=True)
                assert len(contact) <= b.p
                self.band(b.layers,b.t,(len(b.layers)-1)*b.p)
                self.root_word(contact)
                done.update((i,target))
                self.stats["branch_counts"]["multi_cycle"] += 1
        for i,b in enumerate(self.blocks):
            if i not in done:
                self.realize(b)

    def run(self):
        if not self.required:
            self.stats.update(lower_bound=0,superstring_bytes=0)
            return b"", self.stats
        t = perf_counter()
        self.counts()
        self.stats["counts_seconds"] = perf_counter()-t
        t = perf_counter()
        self.decompose()
        self.process_groups()
        self.finish_blocks()
        self.stats["connections_seconds"] = perf_counter()-t
        assert sum(self.extra.values()) <= 2*self.W
        edges = self.base+self.extra
        balance = Counter()
        for (a,b),c in edges.items():
            balance[a] += c
            balance[b] -= c
        assert all(v==0 for v in balance.values())
        tour = euler(edges,b"")
        assert len(tour)==sum(edges.values())+1 and tour[-1]==b""
        result = bytes(b[-1] for a,b in zip(tour,tour[1:]) if len(b)>len(a))
        assert len(result) <= 2*self.W
        assert all(s in result for s in self.required)
        self.stats.update(superstring_bytes=len(result),
                          additional_up_cost=sum(c for (a,b),c in self.extra.items() if len(b)>len(a)),
                          total_seconds=perf_counter()-self.started)
        self.stats["branch_counts"] = dict(self.stats["branch_counts"])
        return result,self.stats


def pack_superstring(strings: list[bytes], *, max_vertices=12000, max_seconds=None):
    if any(not isinstance(s,bytes) for s in strings):
        raise TypeError("strings must be bytes")
    return Construction(strings,max_vertices,max_seconds).run()
