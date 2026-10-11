# Evaluate family 325 truncation bounds and their practical effect on matrix-exponential actions

## Publication contents

This PR adds an independent experiment under `experiments/family325-matrix-exponential/`. Run the commands below from that directory. The English research report is [RESEARCH_REPORT.md](RESEARCH_REPORT.md); the [publication guide](PUBLICATION.md) records setup, included evidence, and artifact exclusions.

The code and original plans are preserved byte for byte. Recorded audits describe the original complete local archive; they are not claims that omitted artifacts can be audited from this checkout. No new timed benchmark was run to prepare this publication. The hypothesis IDs below are editorial labels for the questions investigated, not a claim that every question was preregistered.

## Summary

Add a restricted prototype for `exp(A)x` that uses the scalar consequence of the family 325 Crouzeix inequality to choose a shifted Taylor degree. Check its numerical-range enclosure and truncation bound with rational arithmetic, and compare total work with the older constant, a norm-based Taylor bound, SciPy, and Arnoldi.

The theorem gives a useful exact-arithmetic approximation bound in this prototype. **The change of constant alone yields little measured work reduction:** four of 45 matched cases reduce degree by one, and total per-vector SpMV count across the nonnormal cases decreases by **0.18%**. Reusing a polynomial can help on repeated inputs, but almost all of that benefit is also available with the older constant.

## Hypotheses and outcomes

| ID | Hypothesis | Outcome |
|---|---|---|
| F1 | The scalar inequality can support a checkable truncation bound for an exponential-action polynomial. | Supported for the implemented disk/Taylor construction, conditional on the pinned published theorem. Full float64 error is not certified. |
| F2 | Replacing `1+sqrt(2)` with 2 materially reduces application work. | Limited effect: a 17.16% tighter bound for a fixed polynomial, but degree changes in only 4/45 pairs. |
| F3 | A numerical-range disk is substantially better than a simple norm bound. | Case-dependent: it lowers some degrees, but enclosure/setup cost can outweigh savings; large hub and Jordan cases are unfavorable. |
| F4 | The prototype beats existing exponential-action methods. | Sometimes for eight repeated inputs; rarely against prepared SciPy for a single input. No general superiority is established. |
| F5 | Normal matrices demonstrate a benefit specific to the new constant. | Not supported: the spectral theorem already permits constant 1; these are explicit negative controls. |

## Mathematical scope

Use the scalar case `m=1` of [A direct proof of the complete Crouzeix inequality](https://github.com/openai/math/blob/fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb/preprints/A-direct-proof-of-the-complete-Crouzeix-inequality-September-26-2026/build/main.tex), pinned to `fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb`. The matrix-coefficient completeness property is not needed by this application. Positive matrix/coefficient sizes mean positive dimensions, not positive definiteness of A.

Uniform convergence of the exponential's polynomial partial sums on a bounded disk, together with operator-norm convergence of the matrix series, gives

`||(exp(A) - p(A))x||_2 <= 2 * max_{z in W(A)} |exp(z)-p(z)| * ||x||_2`.

The prototype chooses the polynomial and enclosure; they are not an implementation of the paper's proof. The source/formalization mapping was inspected, but Lean/Comparator and the complete import closure were not independently checked. The pinned materials also cite other scalar constant-2 proofs; this experiment does not establish a unique application available only from family 325.

For finite real float64 inputs interpreted as exact binary rationals, choose the diagonal midpoint c and reject an inexactly represented shift `B=A-cI`. Set `M=abs(B)` entrywise and `S=(M+M^T)/2`. A positive integer witness w gives an exact rational check of `S*w <= r*w`, yielding an outer disk for `W(A)`. Twelve floating-point iterations choose only the witness candidate; acceptance depends on the exact inequalities. Row-sum and norm bounds provide additional candidate radii.

For the shifted Taylor polynomial of degree d and `d+2 > r`, use the disk-wide tail bound

`tail <= exp(c) * r^(d+1)/(d+1)! / (1-r/(d+2))`.

Rational exponential and square-root bounds support degree selection. The first degree satisfying `C*tail <= 0.9*tol` is minimal for this sufficient bound, not a minimax degree. Float64 polynomial evaluation still incurs unbounded-by-this-certificate roundoff; the 10% reserve does not prove a full floating-point guarantee. [THEORY.md](filter325/THEORY.md) gives the derivation and assumptions.

## Proposed scope and experiment

Add `filter325/core.py`, `data.py`, `benchmark.py`, `audit.py`, `report.py`, six unit tests, the [prespecified plan](filter325/PLAN.md), locked requirements, source audit, and `results/filter325/run-20261011/` evidence.

The experiment uses **15 synthetic cases**, sizes **64–2,048**, seeds **32501/32502**, tolerances **1e-4, 1e-7, 1e-10**, and eight input vectors per case. Structural families are symmetric ring, normal directed cycle, directed regular graph, directed hub, Jordan, and Grcar. In deterministic structural families, the two seeds change x rather than A; they are not independent matrices.

The target is `||error||_2 / ||x||_2`, not relative error to `||exp(A)x||_2`. Absolute error and output-relative error are also retained. There are **282 method/case/tolerance rows and 2,256 outputs**, all meeting their requested input-scaled tolerance in the saved reference comparisons.

Methods are `crouzeix2`, `crouzeix_old` with exactly the same disk/polynomial procedure, `norm_taylor`, `normal1` on normal controls, public SciPy `expm_multiply`, a prepared-SciPy adapter, and a local Arnoldi implementation. The prepared adapter reuses the unchanged degree/scaling selection and core of installed SciPy 1.18.1; it depends on private APIs. Arnoldi uses two orthogonalization passes and a heuristic adjacent-approximation stopping rule, checked against the reference afterward.

Each timing uses one warmup and five repeats, one BLAS thread, and identical CSR matrices/input vectors. Total cost is measured for new preparation plus one x and for new preparation plus eight sequential x values. Only matrix/polynomial preparation is reused; outputs and Arnoldi bases are not reused across vectors. A practical win requires at least 10% lower median total time while all eight inputs meet tolerance.

## What changes when the constant changes

With a fixed polynomial, replacing `1+sqrt(2)` by 2 reduces the bound by **17.16%**. Degree changes are:

| Case | Tolerance | Old degree → new degree |
|---|---:|---:|
| Hub, n=128, seed 32501 | 1e-4 | 67 → 66 |
| Hub, n=128, seed 32502 | 1e-4 | 67 → 66 |
| Directed regular, n=1,024, seed 32501 | 1e-10 | 35 → 34 |
| Hub, n=1,024, seed 32502 | 1e-10 | 362 → 361 |

The other **41 pairs** have the same degree and bitwise-identical outputs on all eight vectors. Across the **33 nonnormal case/tolerance combinations**, old versus new degrees sum to **2,210 versus 2,206 SpMVs per one vector per combination**, a **0.18%** reduction. Timing variation and differences in rational-certificate setup are not evidence of faster polynomial application when degrees and outputs are identical.

## End-to-end comparisons and amortization

The table counts wins under the prespecified 10% threshold across 33 nonnormal combinations. Ratios are descriptive medians of paired competitor/prototype times; values above one favor `crouzeix2`.

| Comparator | Wins for one x | Wins for eight x | Median comparator/prototype time ratio, eight x |
|---|---:|---:|---:|
| Norm-based Taylor | 11/33 | 11/33 | 0.92 |
| Public SciPy | 2/33 | 26/33 | 2.15 |
| Prepared SciPy | 2/33 | 18/33 | 1.19 |
| Local Arnoldi | 11/33 | 28/33 | 4.48 |

The public SciPy API has no user-supplied tolerance and often computes a more accurate result. The prepared adapter gives the competitor equivalent access to reusable setup. Arnoldi timings include orthogonalization and small dense exponentials, not just SpMVs.

Examples at tolerance 1e-7 show the role of geometry and setup:

- Directed n=128: degree 29 versus norm-Taylor 38; prototype/prepared-SciPy totals are **2.20/0.76 ms for one x** and **2.76/4.66 ms for eight x**.
- Directed n=1,024: degree 29 versus norm-Taylor 39, but enclosure cost is 5.92 ms and total preparation 7.38 ms. Prototype/prepared-SciPy totals are **7.87/1.14 ms** and **8.83/7.33 ms**. A fitted linear cost model predicts crossover near 38 inputs against norm Taylor and 10 against prepared SciPy; these are extrapolations, not measured additional batches.
- Hub n=1,024: disk radius 126.75 is close to norm radius 129.97. The prototype needs **355 SpMVs per x**, versus 31 for the prepared SciPy core and 16 for Arnoldi. Eight-input totals are **35.74 ms versus 6.20 ms** for prepared SciPy.
- Jordan n=2,048: disk and norm radii coincide; 8.00 ms of enclosure construction does not reduce degree. Eight-input totals are **10.35 ms versus 6.17 ms** for prepared SciPy.

Preparation products, including transposed products, are counted separately. Process peaks across methods are **57.25–59.79 MiB**, including interpreter, dependencies, and data. `tracemalloc` setup-plus-eight-output peaks are also recorded, but omit some native allocations and are not substituted for process memory.

## Reference checks, correction, and limitations

For n<=128, dense Padé results are checked with an independent Decimal80 unshifted series action. Larger cases use Decimal80, with the first vector repeated at Decimal110. The series truncation bound is below 1e-65; its own complete roundoff is not interval-certified.

Saved maximum discrepancies are **1.22e-14** between dense Padé and Decimal80, **5.61e-76** between Decimal80/110 on the repeated vector, and **3.99e-15** between float64 and Decimal80 evaluation of the same finite polynomial on checked first vectors. Differences near machine precision should not be overinterpreted as a ranking of method accuracy.

The original artifact audit rechecks all 2,256 errors, hashes, and exact disk witnesses. After measurement, a derived field name for degree-search time was repaired from raw stage data. Raw timings, cases, degrees, and predictions were unchanged; this was not a benchmark rerun or parameter search.

All **six unit tests** passed again during drafting; [fresh log](results/pr-drafts-20261012/filter-tests.txt). Faber/Chebyshev polynomials, optimized centers, alternative enclosures, restarts, contour methods, and GPU/parallel implementations were not tested. The negative result for changing this constant is specific to this Taylor/disk experiment.

## Reproduction and evidence

From the root with the separate `.venv-filter325` environment and an unused output directory:

```powershell
.\.venv-filter325\Scripts\python.exe -m unittest discover -s filter325 -p test_filter325.py -v
.\.venv-filter325\Scripts\python.exe -m filter325.benchmark --output results/filter325/pr-reproduction --stage all
.\.venv-filter325\Scripts\python.exe -m filter325.audit --output results/filter325/pr-reproduction
.\.venv-filter325\Scripts\python.exe -m filter325.report --output results/filter325/pr-reproduction
```

Run timing/memory series sequentially on the same machine. Recorded conditions include Windows, Python 3.14.7, SciPy 1.18.1, and Intel Core Ultra 7 255H, without exclusive CPU ownership. [README](filter325/README.md) describes setup and the separate acquisition step.

Review [the report](results/filter325/run-20261011/report.md), [all-method tables](results/filter325/run-20261011/all-methods.md), [measurements](results/filter325/run-20261011/measurements.csv), [summary](results/filter325/run-20261011/summary.json), and [validation](results/filter325/run-20261011/validation.json). The [177-file source manifest](references/filter325/manifest.json) and [runtime-source manifest](references/filter325/runtime-source-manifest.json) record the pinned papers and the actual SciPy implementation used. This is evidence for a restricted approximation-bound application, not a new independent proof of the complete theorem.
