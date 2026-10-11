# Prespecified scale comparison: FasterPAM vs OneBatchPAM

Written before scale measurements. This is a new experiment, independent of the
frozen 380-run pilot. No modification of the original pilot, source manifest,
downloaded sources, or other experiments. All outputs live in a new directory
under `results/kmedian125/`. Code lives in `kmedian125/scale/`.

## Questions and comparisons

1. At which tested N does OneBatchPAM become faster and use less memory?
2. What is the change in the **full N-client k-median objective** relative to
   FasterPAM, and how does this differ for rare, remote clients?
3. Does increasing the batch improve rare-point coverage enough to justify its
   time/memory cost? Check dependence on k separately.

Use the existing pinned environment: kmedoids 0.5.5, onebatch 0.1.0, Python 3.11.
These are the actual packaged implementations, not a new implementation of
either paper. OneBatch uses native uniform sampling without replacement,
weighting=True (nearest-sampled-client counts), normalize=True, tol=1e-6,
max_iter=100, n_jobs=1. FasterPAM uses init=random, max_iter=100, n_cpu=1.
Default random initialization is preserved; equal integer seeds do **not**
imply equal initial medoids because the packages use different RNGs.

Main grid: N=1000,1500,2000,3000,5000,7500,10000; k=20; three structures; data
seeds 31 and 47; algorithm seeds 101,202,303. Four methods: FasterPAM,
OneBatch B=256, auto, and 2*auto capped at N. Native auto is
min(N,max(k,floor(100*ln(max(2,N*k))))). This makes 504 fresh processes.
At N=10000 also run B=64 and B=N: 36 processes. Sensitivity k=50 at N=1000 and
10000, all three structures, data seed31, three algorithm seeds, FasterPAM and
auto: 36 processes. Total **576**. The schedule is shuffled with seed60211
before execution. No winner-dependent repeats or parameter tuning.

## Datasets and rare points

Synthetic integer 2D L1 data. Twelve balanced bulk groups centered on a 4x3
grid with spacing1000, each coordinate jittered uniformly in [-100,100].
Reject coordinate duplicates, then shuffle all rows. Original row identities
and order are preserved thereafter; IDs/labels are not algorithm features.

- balanced: all N clients are bulk clients.
- rare_triplets: 24 of N clients form eight remote groups of three.
- rare_singletons: eight of N clients are isolated remote clients.

Remote centers are the eight nonzero vectors of {-100000,0,100000}^2,
with jitter [-5,5]. The rare count stays fixed as N grows, so its fraction
decreases: at N=10000, 0.24%/0.08%; at N=1000, 2.4%/0.8%. Remote groups
are far apart as well as far from the bulk. These deliberately stressful
synthetic cases diagnose rare-client loss; they are not empirical real-data
frequencies and cannot establish a universal performance boundary.

For each run record full integer cost, bulk and rare cost separately, mean /
95th percentile / max distance for rare clients, number of rare groups with a
selected medoid, and the sampled rare groups. Report an uncovered group when
none of its members is selected; also report distance-based rare service
within20 L1 units (any two points of one rare group are at most20 apart).
The full objective, not OneBatch's normalized weighted batch inertia, is the
quality measure. Compute it independently from original coordinates and
returned medoid indices using integer arithmetic. Recheck saved results in
the final analysis. No exact optimum is claimed at these sizes.

Reference quality: for each fixed dataset and k, percentage difference of
each run's full cost from the **median of three FasterPAM costs**. Aggregate
medians and ranges across datasets/seeds; show the worst observed deviation.
Also retain cost relative to the best observed solution (never call it OPT).
Negative differences are allowed. Rare-group miss probabilities for a
uniform batch can be computed exactly as C(N-r,B)/C(N,B); distinguish this
sampling probability from observed optimization behavior.

## Fair resource measurements

One fresh, sequential OS process per run. Identical imports and features;
one selected logical CPU, BLAS/OpenMP/Rayon thread limits1. Record host,
versions, affinity, system free memory and load, source/dataset hashes,
installed package binary hashes, and full raw results including failures.
Distance caches are absent. Both algorithms build C-contiguous float32 L1
matrices using the **same bounded row-block builder**, one NxN matrix for
FasterPAM or one NxB matrix for OneBatch. Distances here are small integers
exactly representable in float32. FasterPAM already accepts float32; avoid
an unnecessary int64/float64 copy. The original pilot's absolute timings
and memory are therefore not directly comparable with this new harness.

Pass the matrix builder as OneBatch's documented callable distance so the
native wrapper samples and normalizes in place, avoiding precomputed-mode
copy overhead. Do not modify the package or its swap kernel. Log and verify
the callback's sampled columns against the seeded RNG.

Time imports, loading, distance construction, fit including weighting,
and full assignment/quality validation separately. Main algorithm time
includes distance construction + fit, measured after imports/data load.
Also report cold process wall time and algorithm + full-assignment time.
FasterPAM already computes all labels; OneBatch's batch labels are not used
as full assignments. Peak memory is the Windows process peak working set
captured immediately after fitting; record baseline and whole-process peak
separately. Count native allocations, working buffers and import overhead;
show matrix bytes alongside measured peak MiB. Peak-minus-baseline is a
diagnostic, not a separately guaranteed allocation measurement.

Report the first tested N with lower median time and peak memory. Also show
a practical threshold using at least10% improvement in each. Require that
the median improvement persists at all larger tested sizes for a sustained
boundary; inspect scenario-specific boundaries and run ranges. This is an
observed boundary on this host, not an asymptotic guarantee or a confidence
interval. System contention may affect timings; randomized order and six
runs per main cell reduce but do not remove it.

Safety limits: 180s /1.5GiB RSS per child, suite3600s. Stop only our own child
if exceeded, preserve failures and unfinished schedule. Never kill unrelated
processes or change host settings. A resumable controller may continue the
same saved schedule without rerunning completed rows. Include all statuses.

## Validation before measurement

Tests: block distances against an independent integer formula; duplicate /
empty-edge conditions in the builder; full objective against scalar Python;
native OneBatch callable vs the same sampled precomputed input; float32
FasterPAM result against its reported loss; rare IDs after row permutation;
known sampling omission probabilities. Snapshot tested code/config/plan
before the first measured process. Archive test output under results/.

Artifacts: raw per-run JSON/assignments, schedule, dataset manifests and
feature arrays, source snapshots, CSV measurements/aggregates, figures,
verification audit, and a Russian report with reproducible commands.

## Controller correction before the complete run

The first launch `scale-20261011-v1` stopped after two child fits: Windows
could report NoSuchProcess between poll() and memory_info(), leaving the
controller's returncode unreaped. Added an unconditional child.wait() and
retention of nonzero-exit status. No dataset, algorithm, parameter, schedule,
or measurement code was changed. Preserve this partial launch, exclude it
from the complete comparison, and restart the entire prespecified schedule
as `scale-20261011-v2`. This is a controller correction, not quality tuning.
