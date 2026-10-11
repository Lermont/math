# Measure OneBatchPAM scaling and rare-client failures against FasterPAM

## Publication contents

This PR adds an independent experiment under `experiments/family125-pam-scale/`. Run the commands below from that directory. The English research report is [RESEARCH_REPORT.md](RESEARCH_REPORT.md); the [publication guide](PUBLICATION.md) records setup, included evidence, and artifact exclusions.

The code and original plans are preserved byte for byte. Recorded audits describe the original complete local archive; they are not claims that omitted artifacts can be audited from this checkout. No new timed benchmark was run to prepare this publication. The hypothesis IDs below are editorial labels for the questions investigated, not a claim that every question was preregistered.

## Summary

Add a separate 576-run scale experiment for packaged FasterPAM and OneBatchPAM on 1,000–10,000 synthetic clients. Measure full-client cost, rare-group coverage, distance construction, fitting, full assignment, process wall time, and measured peak memory.

On this host and fixed design, auto OneBatch first sustains at least 10% savings in both algorithm time and process peak memory at **N=3,000**. At **N=10,000**, it is **36.69× faster** for distance construction plus fitting, but loses many rare remote clients. Increasing the batch improves coverage without eliminating the problem; using the full batch restores coverage while retaining full-matrix memory.

This is a baseline scale study following the family 125 pilot. It does not implement or test the full family 125 approximation algorithm.

## Hypotheses and outcomes

| ID | Hypothesis | Outcome |
|---|---|---|
| P1 | Auto OneBatch achieves a useful time-and-memory advantage as N grows. | Supported on the measured grid from N=3,000 onward, including each scenario separately; the precise boundary between tested sizes is unknown. |
| P2 | That advantage preserves the full objective and rare-client representation. | Small changes on balanced data; substantial failures on deliberately rare remote groups and singletons. |
| P3 | A larger batch repairs the rare-client problem at acceptable cost. | Doubling auto improves coverage but still misses most singletons; B=N preserves all rare groups with nearly unchanged full-matrix memory. |
| P4 | Increasing k removes the problem. | Not supported by the k=50 sensitivity cases at N=10,000. |
| P5 | Batch inclusion probabilities explain the observed risk. | Consistent with the saved runs: covered rare groups exactly match sampled rare groups. The probability calculation concerns sampling, not a universal optimization guarantee. |

## Scope and design

Add `kmedian125/scale/` with its [plan](kmedian125/scale/PLAN.md), configuration, native-package adapters, tests, isolated-process runner, analysis, report, and plotting instructions. Preserve the original 380-run pilot. The complete series is `results/kmedian125/scale-20261011-v2/`; the interrupted v1 remains separate.

Use `kmedoids==0.5.5` and `onebatch==0.1.0`, with their native swap implementations and default random initialization. OneBatch uses `weighting=True`, `normalize=True`, `tol=1e-6`, and a 100-iteration limit; FasterPAM also uses a 100-iteration limit. Equal integer seeds do not imply identical initial medoids.

The main grid uses `N=1000,1500,2000,3000,5000,7500,10000`, `k=20`, three structures, data seeds 31/47, and algorithm seeds 101/202/303. It compares FasterPAM with OneBatch B=256, auto, and 2×auto. Additional N=10,000 controls use B=64 and B=N; a separate sensitivity grid uses k=50 at N=1,000 and 10,000. The preshuffled schedule, seed 60211, contains **576 fresh sequential processes** over **42 datasets**.

The metric is exact integer two-dimensional L1. Twelve balanced bulk groups form the ordinary dataset. Stress cases replace 24 or eight clients with eight remote groups of three or one client. Their count stays fixed as N grows: at N=10,000 they represent 0.24% and 0.08% of clients. IDs and group labels do not enter optimization features. These deliberately separated synthetic groups diagnose a failure mode; they do not estimate how often it occurs in real data.

## Measurement controls

Both methods use the same bounded distance builder, producing exact-in-float32 integer distances. FasterPAM stores one N×N matrix; the native callable-distance path lets OneBatch store one N×B matrix without a redundant precomputed-mode copy. All N points remain candidate centers: only the clients used to evaluate swaps are sampled.

Algorithm time includes distance construction and fitting after imports/data loading. Full assignment and integer cost checks are separate; OneBatch's sampled labels and normalized inertia are not full-data quality measures. Process wall time additionally includes Python startup, imports, I/O, and checks. Process peak working set is captured immediately after fitting, with a separate whole-process peak. No matrix cache is used, and OS disk caches are not flushed.

Execution is pinned to one logical CPU with BLAS/OpenMP/Rayon and native parallelism limited to one. Limits are 180 s and 1.5 GiB per child and 3,600 s for the suite. No run reaches a time, memory, or iteration limit.

## Resource results

Each row below aggregates 18 runs per method and N at k=20. The reported ratios compare medians, not a guarantee for each run.

| N | Auto B | FasterPAM, ms | Auto, ms | Speedup | Peak FasterPAM → auto, MiB | Peak saving |
|---:|---:|---:|---:|---:|---:|---:|
| 1,000 | 990 | 10.44 | 9.79 | 1.07× | 105.1 → 104.9 | 0.2% |
| 1,500 | 1,030 | 26.89 | 13.28 | 2.03× | 110.1 → 107.1 | 2.7% |
| 2,000 | 1,059 | 55.11 | 18.69 | 2.95× | 117.1 → 109.2 | 6.7% |
| 3,000 | 1,100 | 202.80 | 27.14 | 7.47× | 136.3 → 113.8 | 16.5% |
| 5,000 | 1,151 | 724.66 | 48.49 | 14.95× | 198.4 → 123.2 | 37.9% |
| 7,500 | 1,191 | 1,879.93 | 72.45 | 25.95× | 318.7 → 135.4 | 57.5% |
| 10,000 | 1,220 | 3,812.67 | 103.92 | 36.69× | 486.9 → 147.9 | 69.6% |

At N=10,000, complete process time is approximately **4.65 s versus 0.98 s**, a **4.75×** speedup. Matrix payload is 381.47 MiB versus 46.54 MiB; it must not be confused with complete process memory.

## Full-client quality and rare coverage

Define `Delta C = 100 * (C / median(FasterPAM costs on the same dataset and k) - 1)`. This compares heuristics, not a certified optimum. Every original client contributes to C, including clients absent from the batch. Coverage counts rare groups containing a selected center.

At N=10,000, k=20:

| Method | B | Algorithm time, ms | Peak MiB | Balanced median ΔC | Triplet median ΔC | Mean triplet groups / 8 | Singleton median ΔC | Mean singletons / 8 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| FasterPAM | 10,000 | 3,812.67 | 486.9 | 0.00% | 0.00% | 8.00 | 0.00% | 8.00 |
| OneBatch B=64 | 64 | 7.24 | 103.2 | +7.88% | +346.61% | 0.33 | +108.81% | 0.00 |
| OneBatch B=256 | 256 | 18.05 | 110.7 | +1.37% | +341.77% | 0.17 | +103.27% | 0.17 |
| OneBatch auto | 1,220 | 103.92 | 147.9 | +0.28% | +183.61% | 2.50 | +93.52% | 1.00 |
| OneBatch 2×auto | 2,440 | 200.11 | 194.9 | +0.08% | +111.91% | 4.83 | +60.92% | 1.83 |
| OneBatch B=N | 10,000 | 962.81 | 487.1 | -0.01% | +0.00% | 8.00 | +0.00% | 8.00 |

Balanced-data auto median differences across sizes range from -0.40% to +0.37%; the worst individual balanced run is +1.24%. Conversely, at N=1,500 the triplet median difference of +0.02% hides a worst run of +203.14%. Report ranges as well as medians.

Full-batch OneBatch covers all eight rare groups in every relevant N=10,000 run. Its largest individual cost difference across the three scenarios is +0.216%, and its algorithm time is 3.96× lower than FasterPAM, but its memory is essentially the same. Consequently, the observed speedup cannot be attributed to client sampling alone; the package kernels and swap trajectories also differ.

For k=50 at N=10,000, auto B=1,312 still loses rare clients: median cost differences are **+380.71% for triplets** and **+173.78% for singletons**, with average coverage **1.67/8** and **1.33/8**. The balanced difference is +1.01%. This is a limited sensitivity check, not a search over k.

## Sampling interpretation

For a particular group of r clients sampled uniformly without replacement, omission probability is `choose(N-r, B) / choose(N, B)`. At N=10,000 and B=1,220, it is **87.8% for a singleton** and **67.68% for a triplet**. Doubling B gives **75.6%** and **43.20%**. Including all eight specified singletons with probability at least 99% requires **B >= 9,988**.

This calculation describes inclusion in the batch, not a guarantee that optimization selects the right centers. In these saved runs, sampled and covered rare groups coincide exactly. Nearest-sampled-client weighting can transfer mass but cannot restore missing client geometry. Batches at different sizes are not nested, so individual outcomes need not improve monotonically with B.

## Validation, provenance, and limitations

All **576/576 runs** succeed. The independent audit rechecks **2,718,000 client assignments**, dataset hashes, frozen inputs, the original pilot, 61 reference files, and six wheel members. The five scale tests passed again during drafting; see [the combined fresh log](results/pr-drafts-20261012/kmedian-tests.txt).

The initial v1 controller stopped after two child fits because of a Windows process-polling race. An unconditional `wait()` corrected process reaping; the entire unchanged schedule was then run as v2. The partial v1 is preserved and excluded from aggregates. The final iteration audit explicitly handles OneBatch's zero-based step counter.

The recorded runtime is Python 3.11.16, NumPy 2.2.6, SciPy 1.16.3, and scikit-learn 1.7.2 on an Intel Core Ultra 7 255H. The machine was shared; available RAM ranged from 850 to 3,068 MiB. These are descriptive results, not confidence intervals or a universal crossover. Other metrics, dimensions, real data, or parallel FasterPAM may behave differently. Absolute timings cannot be merged with the earlier pilot, which used a different distance-conversion and precomputed-input path.

## Reproduction and evidence

Use an unused run ID from the project root:

```powershell
& '.\.venv-kmedian125\Scripts\python.exe' -m unittest kmedian125.scale.test_scale -v
& '.\.venv-kmedian125\Scripts\python.exe' -m kmedian125.scale.run --run-id scale-pr-reproduction
& '.\.venv-kmedian125\Scripts\python.exe' -m kmedian125.scale.analyze --run-id scale-pr-reproduction
& '.\.venv-kmedian125\Scripts\python.exe' -m kmedian125.scale.report --run-id scale-pr-reproduction
```

See [the full report](results/kmedian125/scale-20261011-v2/REPORT.md), [tables](results/kmedian125/scale-20261011-v2/TABLES.md), [measurements](results/kmedian125/scale-20261011-v2/measurements.csv), [aggregates](results/kmedian125/scale-20261011-v2/aggregate.csv), [sampling calculations](results/kmedian125/scale-20261011-v2/sampling.csv), and [verification](results/kmedian125/scale-20261011-v2/verification.json). Source/package provenance is inherited from [the pinned source list](kmedian125/SOURCES.md) and recorded again in the scale environment metadata. Plotting is separate from benchmarking, with instructions in [PLOTTING.md](kmedian125/scale/PLOTTING.md).
