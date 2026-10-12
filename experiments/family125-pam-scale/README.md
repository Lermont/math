# OneBatchPAM versus FasterPAM: scaling and rare-client coverage

[All seven experiments](../README.md) · [Full English report](RESEARCH_REPORT.md) · [Reproduction guide](PUBLICATION.md) · [How to cite](../../CITATION.md)

**Research question:** When does client sampling save resources, and what quality is lost on rare remote groups?

This follow-up benchmarks packaged FasterPAM and OneBatchPAM in 576 isolated runs over 42 synthetic datasets with 1,000 to 10,000 clients. It measures complete-client cost and rare-group coverage separately from the sampled objective. The full family 125 approximation algorithm is outside the implementation.

## Main findings

- At N = 10,000 and k = 20, auto OneBatchPAM is 36.69x faster for distance construction plus fitting and 4.75x faster for the complete process. Peak memory is 147.9 versus 486.9 MiB.
- Median full-client cost differences from the same-dataset FasterPAM baseline are +0.28% for balanced data, +183.61% for rare triplets and +93.52% for rare singletons.
- The first tested size with at least 10% savings in both algorithm time and peak memory is N = 3,000.

**Conclusion:** Substantial resource savings can come with severe rare-client failures.

**Limits:** These are synthetic stress cases and heuristic-to-heuristic comparisons, not gaps to a certified optimum. Larger batches improve coverage, but full coverage at a full batch retains full-matrix memory.

## Evidence and reproduction

- [Scale plan](kmedian125/scale/PLAN.md)
- [Result tables](results/kmedian125/scale-20261011-v2/TABLES.md)
- [Full measurements](results/kmedian125/scale-20261011-v2/measurements.csv)
- [Recorded verification](results/kmedian125/scale-20261011-v2/verification.json)
- [Source provenance](kmedian125/SOURCES.md)
- [Recorded publication test log](PUBLICATION_TESTS.txt): 5 test executions; this is a saved log, not a new benchmark.
- [Publication manifest](PUBLICATION_MANIFEST.json): file sizes and SHA-256 digests for the included package.

Synthetic builders, measurements and aggregate evidence are included. Some raw worker/cache artifacts and reference downloads are omitted; follow the guide for restoration and new runs. Read the [publication guide](PUBLICATION.md#included-and-omitted-evidence) before trying to repeat a historical archived-run audit.

## Attribution and citation

This is an independent community experiment published by the [Lermont GitHub account](https://github.com/Lermont). It is not an official OpenAI study. The mathematical source snapshot is [openai/math@fd4aeeb](https://github.com/openai/math/tree/fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb).

Use the [fixed report snapshot](https://github.com/Lermont/math/blob/60ed0f3d9dacd3a279008241328b7692dbb211b8/experiments/family125-pam-scale/RESEARCH_REPORT.md) for reproducible citation, or the [current report](RESEARCH_REPORT.md) for later corrections. The citation key is `lermont2026_family125_pam_scale`; see [BibTeX entries](../CITATIONS.bib). Publication history is recorded in [PR #5](https://github.com/Lermont/math/pull/5). [Research integrity and scope](../RESEARCH_INTEGRITY.md) explains review status, AI assistance, evidence exclusions, and correction handling.
