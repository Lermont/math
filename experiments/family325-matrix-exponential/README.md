# Matrix-exponential actions: practical effect of a Crouzeix constant-2 bound

[All seven experiments](../README.md) · [Full English report](RESEARCH_REPORT.md) · [Reproduction guide](PUBLICATION.md) · [How to cite](../../CITATION.md)

**Research question:** Does a tighter Crouzeix truncation bound materially reduce work for exp(A)x?

A restricted disk/Taylor prototype uses the scalar consequence of the pinned family 325 theorem to choose a polynomial degree for exp(A)x. Rational arithmetic checks the numerical-range enclosure and exact-arithmetic truncation bound. The experiment separates changing the constant from reusing polynomial preparation.

## Main findings

- Replacing 1 + sqrt(2) with 2 tightens a fixed-polynomial bound by 17.16%, but lowers degree by one in only 4 of 45 matched pairs.
- Across the nonnormal case/tolerance combinations, total per-vector sparse matrix-vector products fall from 2,210 to 2,206, a 0.18% reduction.

**Conclusion:** A useful restricted bound with little measured work reduction from the constant alone.

**Limits:** The certificate is conditional on the published theorem and does not certify complete float64 error. Repeated-input reuse can help with the older constant as well. The experiment is not an independent proof of the complete theorem.

## Evidence and reproduction

- [Experiment plan](filter325/PLAN.md)
- [Bound derivation](filter325/THEORY.md)
- [Measurements](results/filter325/run-20261011/measurements.csv)
- [Recorded validation](results/filter325/run-20261011/validation.json)
- [Source provenance](references/filter325/manifest.json)
- [Recorded publication test log](PUBLICATION_TESTS.txt): 6 test executions; this is a saved log, not a new benchmark.
- [Publication manifest](PUBLICATION_MANIFEST.json): file sizes and SHA-256 digests for the included package.

Measurements, case metadata and validation summaries are included. Matrix caches, output vectors and some downloaded sources are omitted; exact archived-run numerical validation needs the omitted outputs. Read the [publication guide](PUBLICATION.md#included-and-omitted-evidence) before trying to repeat a historical archived-run audit.

## Attribution and citation

This is an independent community experiment published by the [Lermont GitHub account](https://github.com/Lermont). It is not an official OpenAI study. The mathematical source snapshot is [openai/math@fd4aeeb](https://github.com/openai/math/tree/fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb).

Use the [fixed report snapshot](https://github.com/Lermont/math/blob/60ed0f3d9dacd3a279008241328b7692dbb211b8/experiments/family325-matrix-exponential/RESEARCH_REPORT.md) for reproducible citation, or the [current report](RESEARCH_REPORT.md) for later corrections. The citation key is `lermont2026_family325_matrix_exponential`; see [BibTeX entries](../CITATIONS.bib). Publication history is recorded in [PR #7](https://github.com/Lermont/math/pull/7). [Research integrity and scope](../RESEARCH_INTEGRITY.md) explains review status, AI assistance, evidence exclusions, and correction handling.
