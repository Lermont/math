"""Finite eager-broadcast discrete-event model with shared per-node uplink."""
from __future__ import annotations

import hashlib
import heapq
import json
import math
import random

import networkx as nx

from .graphs import seed_for


def make_trace(n: int, seed: int, failure_fraction: float, messages: int) -> dict:
    failure_order = list(range(n))
    random.Random(seed_for(seed, n, "failures")).shuffle(failure_order)
    failed = sorted(failure_order[:math.floor(n * failure_fraction)])
    failed_set = set(failed)
    active = [u for u in range(n) if u not in failed_set]
    source_rng = random.Random(seed_for(seed, n, "sources"))
    region_rng = random.Random(seed_for(seed, n, "regions"))
    trace = {"n": n, "seed": seed, "failure_fraction": failure_fraction, "failed": failed,
             "sources": [source_rng.choice(active) for _ in range(messages)],
             "regions": [region_rng.randrange(4) for _ in range(n)],
             "latency_field_seed": seed_for(seed, n, "latency"),
             "service_order_seed": seed_for(seed, n, "service")}
    trace["sha256"] = hashlib.sha256(json.dumps(trace, sort_keys=True).encode()).hexdigest()
    return trace


def edge_latency(u: int, v: int, model: str, trace: dict) -> float:
    if model == "uniform":
        return 10.0
    if model != "heterogeneous":
        raise ValueError(model)
    a, b = sorted((u, v))
    jitter = seed_for(trace["latency_field_seed"], a, b) / 2**64 * 20.0
    return (5.0 if trace["regions"][u] == trace["regions"][v] else 50.0) + jitter


def simulate(graph: nx.Graph, trace: dict, config: dict, latency_model: str) -> dict:
    """Milliseconds throughout; no idle caches, loss, repair, receive limit."""
    n = len(graph)
    m = config["messages"]
    assert n == trace["n"] and m == len(trace["sources"])
    failed = set(trace["failed"])
    available = n - len(failed)
    assert available > 0 and all(s not in failed for s in trace["sources"])
    adjacency = [sorted(graph[u]) for u in range(n)]
    active_graph = graph.subgraph([u for u in range(n) if u not in failed])
    component_size = {}
    for component in nx.connected_components(active_graph):
        component_size.update({u: len(component) for u in component})
    latencies = {}
    for u, v in graph.edges():
        latencies[u, v] = latencies[v, u] = edge_latency(u, v, latency_model, trace)
    wire_size = config["payload_bytes"] + config["header_bytes"]
    serialization_ms = 8.0 * wire_size / (config["uplink_mbps"] * 1000)
    seen = [[math.inf] * n for _ in range(m)]
    tx_free = [0.0] * n
    transmissions, duplicates, drops = [0] * m, [0] * m, [0] * m
    serial = 0
    queue = []
    for msg, source in enumerate(trace["sources"]):
        heapq.heappush(queue, (msg * config["interval_ms"], serial, msg, source, -1))
        serial += 1
    peak_events = len(queue)
    max_backlog_ms = 0.0
    last_event = 0.0
    while queue:
        timestamp, _, msg, node, sender = heapq.heappop(queue)
        last_event = max(last_event, timestamp)
        if seen[msg][node] != math.inf:
            duplicates[msg] += 1
            continue
        seen[msg][node] = timestamp
        targets = sorted((v for v in adjacency[node] if v != sender),
                         key=lambda v: seed_for(trace["service_order_seed"], msg, node, v))
        for target in targets:
            finish = max(timestamp, tx_free[node]) + serialization_ms
            tx_free[node] = finish
            max_backlog_ms = max(max_backlog_ms, finish - timestamp)
            transmissions[msg] += 1
            if target in failed:
                drops[msg] += 1
                last_event = max(last_event, finish)
                continue
            arrival = finish + latencies[node, target]
            heapq.heappush(queue, (arrival, serial, msg, target, node))
            serial += 1
        peak_events = max(peak_events, len(queue))
    rows = []
    for msg, source in enumerate(trace["sources"]):
        launch = msg * config["interval_ms"]
        times = sorted(t - launch for t in seen[msg] if t != math.inf)
        reached = len(times)
        assert reached == component_size[source], "delivery must equal the live connected component"
        assert transmissions[msg] - drops[msg] == (reached - 1) + duplicates[msg]
        expected = sum(len(adjacency[u]) for u in range(n) if seen[msg][u] != math.inf) - (reached - 1)
        assert transmissions[msg] == expected
        row = {"message": msg, "source": source, "launch_ms": launch, "reached": reached,
               "available": available, "unreachable_fraction": (available - reached) / available,
               "transmissions": transmissions[msg], "wire_bytes": wire_size * transmissions[msg],
               "duplicates": duplicates[msg], "failed_transmissions": drops[msg],
               "unique_deliveries": reached - 1, "duplicate_fraction_of_received":
                   duplicates[msg] / max(1, transmissions[msg] - drops[msg]),
               "last_unique_ms": times[-1]}
        for quantile in (50, 95, 99, 100):
            index = math.ceil(available * quantile / 100) - 1
            row[f"t{quantile}_ms"] = times[index] if index < reached else None
        rows.append(row)
    return {"latency_model": latency_model, "failure_fraction": trace["failure_fraction"],
            "trace_sha256": trace["sha256"], "messages": rows, "wire_message_bytes": wire_size,
            "serialization_ms": serialization_ms, "model_end_ms": last_event,
            "live_edges": active_graph.number_of_edges(),
            "live_components": nx.number_connected_components(active_graph),
            "peak_pending_events": peak_events, "max_uplink_backlog_ms": max_backlog_ms}
