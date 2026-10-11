# Audit family 125 feasibility and benchmark an explicitly heuristic LP rounding pipeline

## Publication contents

This PR adds an independent experiment under `experiments/family125-feasibility-pilot/`. Run the commands below from that directory. The English research report is [RESEARCH_REPORT.md](RESEARCH_REPORT.md); the [publication guide](PUBLICATION.md) records setup, included evidence, and artifact exclusions.

The code and original plans are preserved byte for byte. Recorded audits describe the original complete local archive; they are not claims that omitted artifacts can be audited from this checkout. No new timed benchmark was run to prepare this publication. The hypothesis IDs below are editorial labels for the questions investigated, not a claim that every question was preregistered.

## Summary

Document the feasibility of the published metric k-median construction and add a bounded experiment around assignment LP, cardinality-preserving dependent rounding, and local swaps.

The literal preparation recipe already requires an impractical grid parameter for this pilot. The measured implementation is therefore named **LP-DR16-swap** and treated as a separate heuristic. On the medium-sized test problems it has the smallest average certified upper bound on relative suboptimality, at much higher runtime and memory cost than packaged PAM baselines. These measurements do not evaluate the complete family 125 algorithm.

## Hypotheses and outcomes

| ID | Hypothesis | Outcome |
|---|---|---|
| K1 | The full published construction can be directly instantiated within a small local prototype budget. | Not supported by the literal recipe: its sufficient preparation bounds imply an enormous grid parameter before history enumeration and surplus removal. |
| K2 | LP-guided rounding plus swaps yields better solutions than inexpensive baselines. | Qualified support: lowest average dataset-median gap to a certified lower bound, but no per-instance dominance and a substantial resource cost. |
| K3 | A small sampled client batch preserves quality on rare remote clients. | Not supported by the batch-64 stress case; its worst individual-run gap is 92.958%. |
| K4 | The default sampled method demonstrates an order-of-memory improvement at these sizes. | Not tested effectively: the package's auto batch equals the full dataset in this pilot. |
| K5 | Feasibility, costs, and lower bounds can be checked independently of solver success flags. | Supported by exact small-instance solutions, integer cost recomputation, and rational lower-bound certificates. |

## Source audit and implementation boundary

The pinned source is [The Approximation Threshold for Metric k-Median](https://github.com/openai/math/tree/fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb/preprints/The-Approximation-Threshold-for-Metric-k-Median-September-24-2026) at `fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb`. The source review covers preparation, rounding, derandomization, and the Li–Svensson surplus-removal reduction. The related recovery variant requires an anchor promise that was not instantiated or benchmarked. Lean/Comparator were not executed.

For the literal sufficient preparation inequalities, a necessary consequence is

`Delta >= 144 * (1 + eta)^2 * (2 + eta)^2 / eta^10`, with `eta = epsilon / 40`.

At `epsilon = 0.1`, this gives **Delta >= 6.08522 × 10^28**. This calculation concerns the displayed recipe and its copy representation. It is not a complexity lower bound for k-median, a counterexample to the theorem, or a proof that every compressed implementation is infeasible. The derivation is in [FEASIBILITY.md](kmedian125/FEASIBILITY.md).

The implemented heuristic solves assignment LP, applies an unweighted pairwise dependent-rounding step, evaluates 16 rounded solutions on all clients when rounding is needed, and performs local swaps. It omits bundles/suppliers, the tapered graph, full history-based derandomization, and Li–Svensson reduction. **The paper's `1 + 2/e + epsilon` guarantee is not claimed for LP-DR16-swap.**

## Proposed scope

Package the `kmedian125/` pilot code, plan/configuration, locked dependencies, source audit, feasibility calculation, and tests. Include the saved `pilot-20261011-v1` measurements, source snapshot, independently checked bounds, and both original and revised summary tables. The later scale experiment belongs in a separate PR.

Baselines are deterministic Greedy+1-swap, FasterPAM from `kmedoids==0.5.5`, and OneBatchPAM from `onebatch==0.1.0` with auto and batch-64 settings. Their native implementations are used; normalized sampled `inertia_` is never reported as full-client cost.

## Experimental design

The completed pilot has **380 runs**, taking **390.93 s** of the 1,200-second suite budget. All runs finish successfully with exactly `k` distinct admissible centers.

- Eight small instances use `n=18, k=3`; every instance is checked by all **816** possible center subsets and an independent MILP.
- Eight medium synthetic tasks use `n=240, k=12/24`; two real-data tasks use UCI Seeds, `n=210, k=10/20`. These are ten tasks on five underlying datasets, not ten independent samples.
- Data include compact and imbalanced groups, rare remote clients, an integer shortest-path graph metric, and seven UCI Seeds features scaled and rounded to integers in `[0,1000]`. Class labels and IDs are excluded from features. All measured problems use `F=J` and integer L1 or graph distances.
- Randomized methods use seeds 101/202/303; Greedy is deterministic. Each task/method/seed/mode runs in a fresh subprocess, sequentially, on one logical CPU. Child limits are 60 s and 1 GiB; solver limit is 30 s.
- `fresh` includes required distance construction and the algorithm after imports and data loading. `shared` uses an already prepared full distance matrix and is reported separately. Process wall time additionally includes startup, imports, I/O, and verification.

## Quality and resource results

The following table covers the **ten medium/real tasks in fresh mode**. The first quality column averages `100 * (median seed cost / LB - 1)` with equal weight per task; the second shows the worst individual run. Time and memory are medians over all fresh runs of that method in these tasks. Because `LB <= OPT`, the gap to LB is an upper bound on relative error to OPT, not an exact optimality gap when OPT is unknown.

| Method | Mean dataset-median gap to LB, % | Worst individual-run gap, % | Median fresh time, ms | Median process peak, MiB |
|---|---:|---:|---:|---:|
| Greedy+1-swap | 0.644 | 1.529 | 15.84 | 101.9 |
| FasterPAM | 0.451 | 1.449 | 2.32 | 102.2 |
| OneBatch auto | 0.713 | 2.448 | 1.67 | 102.0 |
| OneBatch batch=64 | 16.628 | 92.958 | 0.97 | 101.0 |
| LP-DR16-swap | 0.136 | 0.456 | 906.35 | 200.1 |

Comparing best-of-three solutions, LP-DR16-swap is better than FasterPAM on five tasks, ties on three, and is worse on two. Such a comparison must charge all three attempts; it is not the cost of one run.

Examples make the limitations concrete:

- On compact groups with `k=24`, LP returns cost 4,976 versus FasterPAM's 5,025–5,042.
- On the outlier task with `k=12`, LP returns 11,736 while the best FasterPAM solution is 11,707.
- On the graph task with `k=24`, LP returns 1,299–1,300, while FasterPAM reaches certified OPT 1,298.
- On UCI Seeds with `k=20`, LP reaches certified OPT 73,103 versus FasterPAM's 73,123–73,230.
- Batch 64 returns 9,673–11,207 on the `k=24` outlier task, versus certified OPT 5,808.

LP is integral on all eight small instances and fractional on eight of the ten medium/real tasks. The latter actually exercise the 16-rounding path. These measurements are not timings of the omitted family 125 stages.

Median complete process times are approximately **0.92 s for FasterPAM and 1.83 s for LP**, much closer than their in-process algorithm timings. With a shared matrix, median algorithm times are 1.70 ms and 931.59 ms; the LP difference is measurement variation rather than evidence that caching accelerates the solver. Peak memory includes imports, solver, matrices, and verification.

## Exact verification and post-run bound refinement

The saved audit includes **380 independent cost checks**, **130 matched fresh/shared pairs**, **84 original dual certificates**, and **84 strengthened certificates**. Metric triangle inequalities are checked. Optimality is certified for eight small and four medium tasks.

The original certificate did not exploit `y_i <= 1`. After measurement, the audit strengthened the lower bound using the same saved rational prices. With `b_i = sum_j max(alpha_j - d_ji, 0)`, any set of `k` distinct centers satisfies

`cost >= sum_j alpha_j - sum(k largest b_i)`.

Prices use integer numerators with denominator `10^6`; verification uses integer arithmetic and rounds the lower bound upward for the integer objective. Equality with a feasible cost certifies optimality. No optimization run, seed, prediction, or timing changed. The original `summary-planned-bound.*` and `TABLES-planned-bound.md` remain available, and certificate-audit time is separate from algorithm time. See [POSTRUN_AUDIT.md](kmedian125/POSTRUN_AUDIT.md).

The ten pilot/certificate unit tests passed again during drafting; the combined [fresh test log](results/pr-drafts-20261012/kmedian-tests.txt) also contains the five scale tests.

## Reproduction and evidence

From the project root with the pinned Python 3.11 environment, use a new run ID:

```powershell
& '.\.venv-kmedian125\Scripts\python.exe' -m unittest kmedian125.test_kmedian125 kmedian125.test_certificates -v
& '.\.venv-kmedian125\Scripts\python.exe' -m kmedian125.run_experiment --run-id pilot-pr-reproduction
& '.\.venv-kmedian125\Scripts\python.exe' -m kmedian125.summarize --run-id pilot-pr-reproduction
```

The [README](kmedian125/README.md) separately documents environment restoration, the feasibility calculation, and source provenance checking. Recorded dependencies include Python 3.11.16, NumPy 2.2.6, SciPy 1.16.3/HiGHS 1.8.0, and scikit-learn 1.7.2.

Review [REPORT.md](kmedian125/REPORT.md), [full tables](results/kmedian125/pilot-20261011-v1/TABLES.md), [summary.csv](results/kmedian125/pilot-20261011-v1/summary.csv), [verification.json](results/kmedian125/pilot-20261011-v1/verification.json), and [source provenance](results/kmedian125/provenance-audit.json). The [source list](kmedian125/SOURCES.md) distinguishes pinned package wheels, papers, and dataset licensing; UCI Seeds is recorded separately under CC BY 4.0.

The supported conclusion is a tradeoff on these sizes: LP provides a more expensive quality check and verifiable lower bound, while FasterPAM and auto OneBatch are inexpensive baselines. Three seeds, small datasets, fixed method order, and shared-machine timing do not establish general service performance or representation quality for other applications. The evidence does not isolate a benefit from the novel full family 125 rounding construction.
