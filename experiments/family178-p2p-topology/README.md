# P2P broadcast topology: random regular, spectral selection and LPS graphs

[All seven experiments](../README.md) · [Full English report](RESEARCH_REPORT.md) · [Reproduction guide](PUBLICATION.md) · [How to cite](../../CITATION.md)

**Research question:** Does spectral topology selection improve broadcast beyond an ordinary random regular graph?

A discrete-event flooding simulation compares rings, random regular graphs, bounded numerical spectral selection and a classical LPS construction. The pilot covers 80 constructions, 480 scenarios and 3,840 messages. It separates ordinary connectivity effects from benefits attributable to spectral selection.

## Main findings

- With 2,048 nodes, degree 4, heterogeneous latency and no failures, median time to 95% delivery falls from 33.248 seconds for a ring to 0.589 seconds for a random regular graph.
- Spectral selection adds no consistent gain. LPS median paired delivery-time changes range from -2.0% to +1.7%, below the prespecified 10% improvement threshold.

**Conclusion:** Global connectivity helps; additional spectral-selection gains are not established.

**Limits:** The full deterministic family 178 construction is not implemented or benchmarked. The model is finite-burst eager flooding, not a live Gossipsub deployment. Pre-failure spectral quality does not guarantee delivery after failures.

## Evidence and reproduction

- [Experiment plan](p2p178/PLAN.md)
- [Measurement tables](results/p2p178/pilot/measurements.md)
- [Per-message measurements](results/p2p178/pilot/messages.csv)
- [Recorded verification](results/p2p178/pilot/verification.json)
- [Source audit](results/p2p178/source-audit.md)
- [Source provenance](references/p2p178/sources.json)
- [Recorded publication test log](PUBLICATION_TESTS.txt): 11 test executions; this is a saved log, not a new benchmark.
- [Publication manifest](PUBLICATION_MANIFEST.json): file sizes and SHA-256 digests for the included package.

Simulation code, message tables and selected verification/provenance records are published. The guide lists omitted graph and reference artifacts needed for complete archived-run checks. Read the [publication guide](PUBLICATION.md#included-and-omitted-evidence) before trying to repeat a historical archived-run audit.

## Attribution and citation

This is an independent community experiment published by the [Lermont GitHub account](https://github.com/Lermont). It is not an official OpenAI study. The mathematical source snapshot is [openai/math@fd4aeeb](https://github.com/openai/math/tree/fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb).

Use the [fixed report snapshot](https://github.com/Lermont/math/blob/60ed0f3d9dacd3a279008241328b7692dbb211b8/experiments/family178-p2p-topology/RESEARCH_REPORT.md) for reproducible citation, or the [current report](RESEARCH_REPORT.md) for later corrections. The citation key is `lermont2026_family178_p2p_topology`; see [BibTeX entries](../CITATIONS.bib). Publication history is recorded in [PR #6](https://github.com/Lermont/math/pull/6). [Research integrity and scope](../RESEARCH_INTEGRITY.md) explains review status, AI assistance, evidence exclusions, and correction handling.
