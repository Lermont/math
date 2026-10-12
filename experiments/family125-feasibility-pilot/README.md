# Metric k-median: feasibility audit and LP rounding pilot

[All seven experiments](../README.md) · [Full English report](RESEARCH_REPORT.md) · [Reproduction guide](PUBLICATION.md) · [How to cite](../../CITATION.md)

**Research question:** Can the published construction be instantiated cheaply, and what does a separate LP heuristic achieve?

A source audit examines the literal preparation recipe for family 125. A distinct heuristic, LP-DR16-swap, combines assignment LP, dependent rounding and local swaps in a 380-run pilot. Exact small-instance solutions and rational lower bounds help assess quality separately from solver success flags.

## Main findings

- Across ten medium/real tasks, the mean dataset-median gap to a certified lower bound is 0.136% for LP-DR16-swap versus 0.451% for FasterPAM.
- Median fresh algorithm times are 906.35 ms for LP-DR16-swap and 2.32 ms for FasterPAM; the complete-process comparison is much closer.
- At epsilon = 0.1, the literal sufficient preparation recipe implies Delta >= 6.08522 x 10^28.

**Conclusion:** A costly heuristic quality check, with no per-instance dominance or evaluation of the full construction.

**Limits:** The full family 125 construction is not implemented. Its approximation guarantee does not transfer to LP-DR16-swap. Gaps to lower bounds are upper bounds on relative suboptimality, not necessarily exact optimality gaps.

## Evidence and reproduction

- [Experiment plan](kmedian125/PLAN.md)
- [Feasibility calculation](kmedian125/FEASIBILITY.md)
- [Result tables](results/kmedian125/pilot-20261011-v1/TABLES.md)
- [Recorded verification](results/kmedian125/pilot-20261011-v1/verification.json)
- [Source provenance](kmedian125/SOURCES.md)
- [Recorded publication test log](PUBLICATION_TESTS.txt): 10 test executions; this is a saved log, not a new benchmark.
- [Publication manifest](PUBLICATION_MANIFEST.json): file sizes and SHA-256 digests for the included package.

Papers, external snapshots, wheels, UCI Seeds input and some worker/cache files are omitted. Raw JSONL, tables and audit records are included; the guide distinguishes restoration from full archived-run verification. Read the [publication guide](PUBLICATION.md#included-and-omitted-evidence) before trying to repeat a historical archived-run audit.

## Attribution and citation

This is an independent community experiment published by the [Lermont GitHub account](https://github.com/Lermont). It is not an official OpenAI study. The mathematical source snapshot is [openai/math@fd4aeeb](https://github.com/openai/math/tree/fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb).

Use the [fixed report snapshot](https://github.com/Lermont/math/blob/60ed0f3d9dacd3a279008241328b7692dbb211b8/experiments/family125-feasibility-pilot/RESEARCH_REPORT.md) for reproducible citation, or the [current report](RESEARCH_REPORT.md) for later corrections. The citation key is `lermont2026_family125_feasibility_pilot`; see [BibTeX entries](../CITATIONS.bib). Publication history is recorded in [PR #4](https://github.com/Lermont/math/pull/4). [Research integrity and scope](../RESEARCH_INTEGRITY.md) explains review status, AI assistance, evidence exclusions, and correction handling.
