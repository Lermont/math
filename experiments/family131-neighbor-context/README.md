# Elliptic2 neighboring context: graph features and MCMC ablation

[All seven experiments](../README.md) · [Full English report](RESEARCH_REPORT.md) · [Reproduction guide](PUBLICATION.md) · [How to cite](../../CITATION.md)

**Research question:** Does real transaction context help, and does family 131 sampling add anything beyond it?

A separate sample of 6,000 previously unused Elliptic2 subgraphs adds split-isolated one-hop transaction context, a directed control and uncertainty estimates accounting for shared test context. Ordinary context features improve the measured result. Family 131 null features add no convincing incremental benefit.

## Main findings

- On this new sample, mean AP increases from 2.52% for core-only graphs to 6.01% with ordinary context; directed context reaches 9.51%.
- Context plus family 131 achieves 6.08% AP. Its +0.07-percentage-point gain over the context baseline has a context-component 95% interval of [-1.94, +1.49].

**Conclusion:** Context helps on this split; incremental MCMC benefit remains unestablished.

**Limits:** Comparisons are within the new fixed sample; they are not comparisons against the earlier isolated-study split. No temporal holdout or finite-run mixing guarantee is established.

## Evidence and reproduction

- [Context plan](graph131/CONTEXT_PLAN.md)
- [Metrics](results/elliptic2-context/summary.csv)
- [Paired uncertainty](results/elliptic2-context/uncertainty.json)
- [Recorded verification](results/elliptic2-context/final-verification.json)
- [Source provenance](references/graph131-context/sources.json)
- [Recorded publication test log](PUBLICATION_TESTS.txt): 11 test executions; this is a saved log, not a new benchmark.
- [Publication manifest](PUBLICATION_MANIFEST.json): file sizes and SHA-256 digests for the included package.

Raw transaction data, IDs, edges, graph samples, feature matrices and predictions are omitted. The guide describes local acquisition and the approximately 24.5 GB compressed context scan. Read the [publication guide](PUBLICATION.md#included-and-omitted-evidence) before trying to repeat a historical archived-run audit.

## Attribution and citation

This is an independent community experiment published by the [Lermont GitHub account](https://github.com/Lermont). It is not an official OpenAI study. The mathematical source snapshot is [openai/math@fd4aeeb](https://github.com/openai/math/tree/fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb).

Use the [fixed report snapshot](https://github.com/Lermont/math/blob/60ed0f3d9dacd3a279008241328b7692dbb211b8/experiments/family131-neighbor-context/RESEARCH_REPORT.md) for reproducible citation, or the [current report](RESEARCH_REPORT.md) for later corrections. The citation key is `lermont2026_family131_neighbor_context`; see [BibTeX entries](../CITATIONS.bib). Publication history is recorded in [PR #3](https://github.com/Lermont/math/pull/3). [Research integrity and scope](../RESEARCH_INTEGRITY.md) explains review status, AI assistance, evidence exclusions, and correction handling.
