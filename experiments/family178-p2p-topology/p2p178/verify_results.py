"""Read-only validation of saved artifacts, plus independent spectral oracles."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import networkx as nx
import numpy as np

from .benchmark import ROOT, write_json
from .graphs import load_graph


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify(directory):
    directory = Path(directory)
    config = json.loads((directory / "config.json").read_text("utf-8"))
    frozen = json.loads((directory / "code_hashes.json").read_text("utf-8"))
    for name, value in frozen.items():
        assert sha(ROOT / name) == value, f"benchmark source changed: {name}"
    sources = json.loads((directory / "sources.json").read_text("utf-8"))["sources"]
    for source in sources:
        assert sha(ROOT / "references/p2p178" / source["path"]) == source["sha256"]
    raw = json.loads((directory / "raw.json").read_text("utf-8"))
    assert len(raw) == 80
    seen_jobs = set()
    traces, first_candidates = {}, {}
    counts = {"jobs": 0, "graphs": 0, "scenarios": 0, "messages": 0, "source_files": len(sources)}
    oracles = []
    for record in raw:
        job_key = tuple(record[k] for k in ["n", "d", "method", "seed"])
        assert job_key not in seen_jobs
        seen_jobs.add(job_key)
        assert "error" not in record and record["build"]["status"] == "ok"
        folder = directory / record["directory"]
        assert json.loads((folder / "build.json").read_text("utf-8")) == record["build"]
        assert json.loads((folder / "simulation.json").read_text("utf-8")) == record["simulate"]
        graph = None
        for attempt in record["build"]["attempts"]:
            path = folder / attempt["graph_file"]
            assert sha(path) == attempt["graph_sha256"]
            candidate = load_graph(path.read_bytes())
            assert set(candidate) == set(range(record["n"]))
            assert nx.number_of_selfloops(candidate) == 0
            assert all(d == record["d"] for _, d in candidate.degree())
            assert nx.is_connected(candidate)
            assert attempt["spectrum"]["residual_max"] <= config["residual_limit"]
            if attempt["selected"]:
                graph = candidate
                if record["method"] == "spectral_rejection":
                    assert not nx.is_bipartite(graph)
                    assert attempt["spectrum"]["margin_to_bound"] > config["spectral_margin"]
                if record["n"] == 512 and record["seed"] == config["seeds"][0]:
                    # Different algorithm: full dense symmetric LAPACK spectrum.
                    values = np.linalg.eigvalsh(nx.to_numpy_array(graph, nodelist=range(len(graph))))
                    values = values[:-1]
                    if nx.is_bipartite(graph):
                        values = values[1:]
                    expected = float(np.max(np.abs(values)))
                    difference = abs(expected - attempt["spectrum"]["lambda_abs"])
                    assert difference < 1e-7
                    oracles.append({"job": list(job_key), "oracle": "full dense eigvalsh", "difference": difference})
                if record["method"] == "circulant":
                    k = np.arange(1, record["n"])
                    values = sum(2 * np.cos(2 * np.pi * step * k / record["n"]) for step in range(1, record["d"] // 2 + 1))
                    difference = abs(float(np.max(np.abs(values))) - attempt["spectrum"]["lambda_abs"])
                    assert difference < 1e-7
                    oracles.append({"job": list(job_key), "oracle": "analytic circulant spectrum", "difference": difference})
            counts["graphs"] += 1
        assert graph is not None
        if record["method"] in ["random_regular", "spectral_rejection"]:
            key = record["n"], record["d"], record["seed"]
            digest = record["build"]["attempts"][0]["graph_sha256"]
            if key in first_candidates:
                assert first_candidates[key] == digest
            first_candidates[key] = digest
        for scenario in record["simulate"]["scenarios"]:
            trace = json.loads((folder / scenario["trace_file"]).read_text("utf-8"))
            trace_key = record["n"], record["seed"], scenario["failure_fraction"]
            if trace_key in traces:
                assert traces[trace_key] == trace, "methods must have identical physical conditions"
            traces[trace_key] = trace
            down = set(trace["failed"])
            live = graph.subgraph(set(graph) - down)
            for row in scenario["messages"]:
                component = nx.node_connected_component(live, row["source"])
                unreachable = (len(live) - len(component)) / len(live)
                assert abs(unreachable - row["unreachable_fraction"]) < 1e-12
                sent = sum(graph.degree(u) for u in component) - (len(component) - 1)
                failed_sent = sum(1 for u in component for v in graph[u] if v in down)
                assert row["transmissions"] == sent
                assert row["failed_transmissions"] == failed_sent
                assert row["duplicates"] == sent - failed_sent - (len(component) - 1)
                assert row["wire_bytes"] == sent * (config["payload_bytes"] + config["header_bytes"])
                for q in (50, 95, 99, 100):
                    assert (row[f"t{q}_ms"] is None) == (len(component) < math.ceil(len(live) * q / 100))
                counts["messages"] += 1
            counts["scenarios"] += 1
        counts["jobs"] += 1
    assert counts["scenarios"] == 480 and counts["messages"] == 3840
    result = {"status": "PASS", **counts, "identical_first_candidate_pairs": len(first_candidates),
              "distinct_shared_traces": len(traces), "independent_spectral_oracles": oracles,
              "max_oracle_error": max(x["difference"] for x in oracles),
              "claim": "artifact consistency, topology/traffic invariants and numerical cross-checks; not formal certification"}
    write_json(directory / "verification.json", result)
    print(json.dumps({k: v for k, v in result.items() if k != "independent_spectral_oracles"}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("directory")
    verify(parser.parse_args().directory)
