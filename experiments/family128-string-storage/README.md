# Shortest-superstring string storage: family 128 benchmark

[All seven experiments](../README.md) · [Full English report](RESEARCH_REPORT.md) · [Reproduction guide](PUBLICATION.md) · [How to cite](../../CITATION.md)

**Research question:** Can overlapping byte strings share storage without sacrificing reads by original ID?

A byte-preserving shortest-common-superstring prototype is compared with plain, deduplicated, prefix-coded, block-Zstd and whole-dataset-Zstd storage on 11 datasets. It preserves IDs, order, duplicates and empty strings. Overlapping fragments benefit from shared storage, but the method is not a general compression or packing-speed improvement.

## Main findings

- For 128 overlapping binary fragments, the complete archive is 1,265 bytes, versus 8,728 for plain storage, 2,010 for block Zstd and 1,167 for whole-dataset Zstd.
- 64 of 66 archive attempts completed; both larger paper-construction cases reached explicit resource limits.

**Conclusion:** Useful overlap-specific storage tradeoff; no general compressor replacement.

**Limits:** Packing cost, index overhead and input structure dominate practicality. Bounded oracle and round-trip tests are implementation evidence, not a proof of the full port.

## Evidence and reproduction

- [Benchmark design](RESEARCH_REPORT.md#experimental-design)
- [Measurements](results/main/results.csv)
- [Recorded archive audit](results/main/verification.json)
- [Source provenance](references/sources.json)
- [Recorded publication test log](PUBLICATION_TESTS.txt): 9 test executions; this is a saved log, not a new benchmark.
- [Publication manifest](PUBLICATION_MANIFEST.json): file sizes and SHA-256 digests for the included package.

Synthetic/catalogue data builders are included. Stored archives and input/trace caches are omitted; new runs regenerate them. Read the [publication guide](PUBLICATION.md#included-and-omitted-evidence) before trying to repeat a historical archived-run audit.

## Attribution and citation

This is an independent community experiment published by the [Lermont GitHub account](https://github.com/Lermont). It is not an official OpenAI study. The mathematical source snapshot is [openai/math@fd4aeeb](https://github.com/openai/math/tree/fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb).

Use the [fixed report snapshot](https://github.com/Lermont/math/blob/60ed0f3d9dacd3a279008241328b7692dbb211b8/experiments/family128-string-storage/RESEARCH_REPORT.md) for reproducible citation, or the [current report](RESEARCH_REPORT.md) for later corrections. The citation key is `lermont2026_family128_string_storage`; see [BibTeX entries](../CITATIONS.bib). Publication history is recorded in [PR #1](https://github.com/Lermont/math/pull/1). [Research integrity and scope](../RESEARCH_INTEGRITY.md) explains review status, AI assistance, evidence exclusions, and correction handling.
