# Benchmark spectral topology selection for P2P broadcast and audit family 178 feasibility

## Publication contents

This PR adds an independent experiment under `experiments/family178-p2p-topology/`. Run the commands below from that directory. The English research report is [RESEARCH_REPORT.md](RESEARCH_REPORT.md); the [publication guide](PUBLICATION.md) records setup, included evidence, and artifact exclusions.

The code and original plans are preserved byte for byte. Recorded audits describe the original complete local archive; they are not claims that omitted artifacts can be audited from this checkout. No new timed benchmark was run to prepare this publication. The hypothesis IDs below are editorial labels for the questions investigated, not a claim that every question was preregistered.

## Summary

Add a local topology generator and discrete-event broadcast simulator to test whether spectral selection improves delivery over an ordinary random regular graph at the same node count and degree. Include circulant rings, random regular graphs, bounded numerical rejection sampling, and a classical LPS construction.

Random regular graphs greatly outperform local rings in this model. Spectral selection adds no consistent improvement over the random baseline, and LPS has a better measured spectrum without a stable delivery-time advantage. **The full deterministic construction from family 178 is not implemented or benchmarked.**

## Hypotheses and outcomes

| ID | Hypothesis | Outcome |
|---|---|---|
| T1 | Global regular connectivity improves broadcast over a local ring at equal degree. | Supported in the simulated scenarios; this is a baseline topology effect, not a result of the family 178 algorithm. |
| T2 | Selecting a random regular graph inside the numerical Ramanujan bound improves delivery by at least 10%. | Not supported. The first candidate is accepted in 22/25 pairs, and the remaining delivery changes are small and inconsistent. |
| T3 | A classical LPS graph's better spectrum produces a meaningful additional delivery benefit. | Not supported by this pilot: median paired t95 changes range from -2.0% to +1.7% across scenarios. |
| T4 | Spectral topology selection reduces total traffic and duplicates at fixed n,d. | Not supported for the chosen connected, failure-free flooding protocol; total transmissions are fixed by n,d. |
| T5 | Good pre-failure spectral properties ensure near-complete delivery after node failures. | Not supported: with 30% failures, n=2,048,d=4 misses 99% coverage in 32/40 messages even for selected graphs. |
| T6 | The published construction is a ready practical generator at the measured sizes. | Not established by the source audit; numerical thresholds and a runnable full implementation were not obtained. Only the exact small-graph acceptance criterion is implemented. |

## Source status and scope of implementation

The pinned paper, [Deterministic nonbipartite Ramanujan graphs in every fixed degree](https://github.com/openai/math/tree/fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb/preprints/Deterministic-nonbipartite-Ramanujan-graphs-in-every-fixed-degree-September-23-2026), states a deterministic construction for each fixed `d >= 3` and every sufficiently large even n, with bit complexity `O_d(n^k_d)`. Its practical `n0(d)` and exponent for this benchmark scale were not established. The source snapshot is `fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb`.

The [source audit](results/p2p178/source-audit.md) found no runnable full generator or corresponding Lean entry in the inspected pinned materials. This is a bounded artifact search, not proof that no third-party implementation exists. It also inspected a specific external normalization objection: the alleged equality between `J_T` and `|T_tau|` did not follow from the inspected text. That narrow finding is not an independent proof review.

`p2p178/graphs.py` implements the paper's exact acceptance condition for a supplied regular graph,

`B^T (4(d-1)I - A^2) B` positive definite, where `B = [e_i - e_n]`,

using integer elimination on graphs up to 32 vertices. This tests the criterion, not the four-stage construction or its complexity. Large benchmark graphs use numerical extremal-eigenvalue diagnostics and have no exact spectral certificate.

Proposed scope also includes `simulate.py`, `benchmark.py`, `verify_results.py`, `summarize.py`, `write_report.py`, `tests/test_p2p178.py`, the [fixed plan](p2p178/PLAN.md), configuration, source manifest, and `results/p2p178/pilot/` artifacts.

## Prespecified comparison

The main grid uses `n=512/2048`, `d=4/8`, and seeds 17801–17805. An additional matched set uses `n=2184,d=6` for classical **LPS X^(5,13)**, a bipartite graph. Vertex labels are shuffled before assigning physical conditions. For deterministic topologies, seeds vary placement and workload, not the graph's isomorphism type.

The spectral-selection method accepts the first simple connected nonbipartite candidate with numerical `lambda_abs < 2*sqrt(d-1) - 1e-7`, with a maximum of 32 candidates. Its first candidate is identical to the paired random-regular baseline. Every rejection is retained and charged. This is an explicit heuristic, distinct from family 178.

The simulator uses eager flooding: forward a message on first receipt to all neighbors except the sender, then discard duplicate IDs. Each scenario sends eight messages, each 16 KiB plus 64 bytes of modeled overhead, 100 ms apart. Each node has one 10 Mbit/s FIFO outgoing channel. Receivers and queues have no capacity limit; caches start empty and retain all eight message IDs.

Latency is either 10 ms uniformly, or four-region latency of 5 ms within a region / 50 ms between regions plus fixed pairwise jitter in `[0,20)` ms. Exactly `floor(f*n)` nodes fail before broadcast for `f=0,0.1,0.3`. Failed-peer transmissions still consume channel time and bytes. Placement, sources, jitter, and failure sets are paired across topologies. No repair or recovery occurs.

The completed pilot contains **80 constructions, 83 candidates, 480 scenarios, and 3,840 messages**. These are finite traffic bursts, not steady-state throughput measurements.

## Delivery and failure results

For heterogeneous latency without failures, values are medians over five seed-level means of eight messages:

| n / d | Topology | t50, s | t95, s | t99, s |
|---|---|---:|---:|---:|
| 2,048 / 4 | Ring | 17.520 | 33.248 | 34.679 |
| 2,048 / 4 | Random regular = selected | 0.485 | 0.589 | 0.620 |
| 2,048 / 8 | Ring | 9.964 | 18.892 | 19.673 |
| 2,048 / 8 | Random regular = selected | 0.448 | 0.534 | 0.561 |
| 2,184 / 6 | Ring | 13.499 | 25.609 | 26.700 |
| 2,184 / 6 | Random regular = selected | 0.435 | 0.520 | 0.547 |
| 2,184 / 6 | LPS X^(5,13) | 0.431 | 0.518 | 0.545 |

At n=2,048, the random graph reduces t95 by roughly **56× at d=4** and **35× at d=8** relative to the ring. Selected and random graphs are literally identical for every parameter set except n=512,d=4.

Across the 25 selection jobs, 28 candidates are examined and three rejected. For n=512,d=4, the median paired t95 change across the six scenarios ranges from 0 to +0.71%; individual pairs range from -2.9% to +10.9%. Selection does not produce a consistent speedup.

LPS has `lambda_abs ≈ 4.2497`, compared with median `≈4.4548` for the n=2,184,d=6 random graph and threshold `≈4.4721`. Its median paired t95 changes range from **-2.0% to +1.7%**; individual pairs range from -4.5% to +6.0%. None of the scenarios reaches the prespecified 10% median-improvement guideline.

With heterogeneous latency and 30% failed nodes:

- Random/selected n=2,048,d=4 has median unreachable fraction 1.325%; t99 is unreachable in **32/40 messages**. The corresponding ring has median unreachable fraction 98.536%.
- Random/selected n=2,048,d=8 reaches all surviving nodes in this sample, with median t95 0.636 s; the ring's median unreachable fraction is 86.768%.
- At n=2,184,d=6, random versus LPS median t95 is 0.656 versus 0.648 s, with median unreachable fractions 0.131% versus 0.065%.

Threshold times target all surviving nodes, including the source. An unreachable threshold is stored as null, not treated as a timeout or replaced with a time conditional on delivered messages. Min–max ranges in the full report are descriptive seed ranges, not confidence intervals.

## Traffic and construction cost

For a connected d-regular graph without failures, transmissions per message are exactly

`T = n*d - (n-1)`, with duplicates `T - (n-1)`.

At n=2,048,d=4 this is **6,145 transmissions, 4,098 duplicates, and 96.39 MiB** of modeled wire traffic; at d=8 it is **14,337 transmissions, 12,290 duplicates, and 224.89 MiB**. A topology change at fixed n,d cannot reduce these totals under this protocol. Low bytes caused by a disconnected surviving network mean lost reachability, not efficiency.

Where rejection occurs, n=512,d=4, median construction plus verification is **28.1 ms for selection versus 17.4 ms for random regular**. This includes rejected candidates and saved graph artifacts. Both baselines pay for spectral diagnostics; generation alone is recorded separately. Timing differences for identical candidates are execution noise.

The full measurement run takes **173.2 s**, including process startup, imports, and I/O; internal timer sums are 12.15 s for construction and 89.56 s for simulation. Maximum process working sets are 77.0 MiB for construction and 50.8 MiB for a six-scenario simulation batch. These exclude the controller and OS cache; the batch peak is not a per-scenario peak.

## Validation and limits

All **11 unit tests** passed in the original run and again during drafting; [fresh log](results/pr-drafts-20261012/p2p-tests.txt). Independent checks cover graph hashes, regularity/simplicity/connectivity, paired conditions, reachability components, FIFO serialization, shortest-path behavior without queuing, and transmission conservation.

The saved [verification](results/p2p178/pilot/verification.json) checks all 83 graph artifacts and 480 scenarios. Independent dense checks for six graphs and analytical spectra for 25 rings disagree by at most **1.70e-13**; the maximum reported iterative residual is approximately **7.8e-10**. Numerical agreement is not a formal spectral certificate. Exactly `+d` is excluded for connected nonbipartite graphs, and exactly `+d` and `-d` for the connected bipartite LPS comparator.

This simulator does not implement Gossipsub's mesh management, gossip/pull, peer scoring, or duplicate suppression extensions. It does not test real churn, correlated failures, congestion control, NAT, Sybil/Byzantine behavior, or consensus safety. The measured conclusion is limited to these synthetic physical conditions and this flooding protocol. Family 178's potential value as a deterministic guarantee at broader graph sizes remains unmeasured.

## Reproduction and evidence

With the recorded Python 3.14.7, NetworkX 3.7, NumPy 2.5.4, SciPy 1.18.1, and psutil 7.2.2 environment:

```powershell
$env:OPENBLAS_NUM_THREADS = '1'
$env:OMP_NUM_THREADS = '1'
& .\.venv-graph131\Scripts\python.exe -m unittest discover -s p2p178/tests -v
& .\.venv-graph131\Scripts\python.exe -m p2p178.benchmark run --output results/p2p178/pr-reproduction
& .\.venv-graph131\Scripts\python.exe -m p2p178.verify_results results/p2p178/pr-reproduction
& .\.venv-graph131\Scripts\python.exe -m p2p178.summarize results/p2p178/pr-reproduction --no-plot
& .\.venv-graph131\Scripts\python.exe -m p2p178.write_report results/p2p178/pr-reproduction
```

The output directory must be new. The existing graph environment is reused as an interpreter; its packages need not be changed. See [the README](p2p178/README.md) for standalone environment setup and optional plotting.

Evidence: [report](results/p2p178/pilot/report.md), [full tables](results/p2p178/pilot/measurements.md), [per-message CSV](results/p2p178/pilot/messages.csv), [summary](results/p2p178/pilot/summary.json), and [42-file source manifest](references/p2p178/sources.json). Original sources retain their own license/provenance.
