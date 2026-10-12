# Elliptic2 isolated subgraphs: degree-preserving MCMC features

[All seven experiments](../README.md) · [Full English report](RESEARCH_REPORT.md) · [Reproduction guide](PUBLICATION.md) · [How to cite](../../CITATION.md)

**Research question:** Do family 131 degree-conditioned graph features improve suspicious-label classification?

The family 131 lazy switch kernel supplies structural residual features for a classifier on 20,000 isolated Elliptic2 subgraphs. Comparisons include ordinary NetworkX features, conventional switches, degree summaries and a directed control. The added features do not establish a convincing classification benefit on this representation.

## Main findings

- Mean test average precision (AP) is 2.288% with family 131 features, versus 2.185% for NetworkX; test positive-label prevalence is 2.275%.
- The paired AP gain is +0.103 percentage points, with a conditional 95% interval of [-0.092, +0.623]. Median full-run time rises from 27.43 to 46.94 seconds.

**Conclusion:** No convincing incremental AP benefit on isolated subgraphs.

**Limits:** The uncertainty is conditional on a fixed split and fitted models. Finite-budget MCMC mixing is unverified, and these features are not calibrated fraud probabilities.

## Evidence and reproduction

- [Experiment plan](graph131/PLAN.md)
- [Metrics](results/elliptic2/summary.csv)
- [Paired uncertainty](results/elliptic2/uncertainty.json)
- [Data audit](results/elliptic2/data_audit.json)
- [Source provenance](references/graph131/sources.json)
- [Recorded publication test log](PUBLICATION_TESTS.txt): 7 test executions; this is a saved log, not a new benchmark.
- [Publication manifest](PUBLICATION_MANIFEST.json): file sizes and SHA-256 digests for the included package.

Raw Elliptic2 data, row-level IDs, graph samples, features and predictions are omitted. Local acquisition is required; dataset licensing is separate. Read the [publication guide](PUBLICATION.md#included-and-omitted-evidence) before trying to repeat a historical archived-run audit.

## Attribution and citation

This is an independent community experiment published by the [Lermont GitHub account](https://github.com/Lermont). It is not an official OpenAI study. The mathematical source snapshot is [openai/math@fd4aeeb](https://github.com/openai/math/tree/fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb).

Use the [fixed report snapshot](https://github.com/Lermont/math/blob/60ed0f3d9dacd3a279008241328b7692dbb211b8/experiments/family131-isolated-subgraphs/RESEARCH_REPORT.md) for reproducible citation, or the [current report](RESEARCH_REPORT.md) for later corrections. The citation key is `lermont2026_family131_isolated_subgraphs`; see [BibTeX entries](../CITATIONS.bib). Publication history is recorded in [PR #2](https://github.com/Lermont/math/pull/2). [Research integrity and scope](../RESEARCH_INTEGRITY.md) explains review status, AI assistance, evidence exclusions, and correction handling.
