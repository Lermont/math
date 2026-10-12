# Seven practical experiments associated with openai/math

Independent empirical studies of shortest-superstring storage, Elliptic2 graph features, metric k-median and PAM, P2P broadcast topology, and matrix-exponential actions. These packages contain methods, recorded positive and negative results, implementation checks, and explicit limitations.

[Numerical overview](../README.md#practical-experiments) · [Citation guide](../CITATION.md) · [Research integrity](RESEARCH_INTEGRITY.md) · [Machine-readable catalogue](index.json) · [Plain-text reading guide](../llms.txt)

## Research directory

| Study | Main conclusion | Report and reproduction |
|---|---|---|
| 1. [Shortest-superstring string storage: family 128 benchmark](family128-string-storage/README.md) | Useful overlap-specific storage tradeoff; no general compressor replacement. | [Report](family128-string-storage/RESEARCH_REPORT.md) · [Setup](family128-string-storage/PUBLICATION.md) · [PR #1](https://github.com/Lermont/math/pull/1) |
| 2. [Elliptic2 isolated subgraphs: degree-preserving MCMC features](family131-isolated-subgraphs/README.md) | No convincing incremental AP benefit on isolated subgraphs. | [Report](family131-isolated-subgraphs/RESEARCH_REPORT.md) · [Setup](family131-isolated-subgraphs/PUBLICATION.md) · [PR #2](https://github.com/Lermont/math/pull/2) |
| 3. [Elliptic2 neighboring context: graph features and MCMC ablation](family131-neighbor-context/README.md) | Context helps on this split; incremental MCMC benefit remains unestablished. | [Report](family131-neighbor-context/RESEARCH_REPORT.md) · [Setup](family131-neighbor-context/PUBLICATION.md) · [PR #3](https://github.com/Lermont/math/pull/3) |
| 4. [Metric k-median: feasibility audit and LP rounding pilot](family125-feasibility-pilot/README.md) | A costly heuristic quality check, with no per-instance dominance or evaluation of the full construction. | [Report](family125-feasibility-pilot/RESEARCH_REPORT.md) · [Setup](family125-feasibility-pilot/PUBLICATION.md) · [PR #4](https://github.com/Lermont/math/pull/4) |
| 5. [OneBatchPAM versus FasterPAM: scaling and rare-client coverage](family125-pam-scale/README.md) | Substantial resource savings can come with severe rare-client failures. | [Report](family125-pam-scale/RESEARCH_REPORT.md) · [Setup](family125-pam-scale/PUBLICATION.md) · [PR #5](https://github.com/Lermont/math/pull/5) |
| 6. [P2P broadcast topology: random regular, spectral selection and LPS graphs](family178-p2p-topology/README.md) | Global connectivity helps; additional spectral-selection gains are not established. | [Report](family178-p2p-topology/RESEARCH_REPORT.md) · [Setup](family178-p2p-topology/PUBLICATION.md) · [PR #6](https://github.com/Lermont/math/pull/6) |
| 7. [Matrix-exponential actions: practical effect of a Crouzeix constant-2 bound](family325-matrix-exponential/README.md) | A useful restricted bound with little measured work reduction from the constant alone. | [Report](family325-matrix-exponential/RESEARCH_REPORT.md) · [Setup](family325-matrix-exponential/PUBLICATION.md) · [PR #7](https://github.com/Lermont/math/pull/7) |

## How to assess a result

Start with the full English report for the hypothesis, comparator, metric, sample, and uncertainty. Follow the study's evidence links to recorded tables and audit artifacts. Read its publication guide for omitted files and exact reproduction requirements; published aggregate summaries do not replace omitted raw observations.

[CITATION.cff](../CITATION.cff) describes this experiment collection only. The [BibTeX entries](CITATIONS.bib) link each report to the fixed Git snapshot `60ed0f3d9dacd3a279008241328b7692dbb211b8`. The original mathematical manuscripts require their own upstream citations.

## Check the published files

From a checkout with original Git line endings, run:

```text
python tools/verify_research_publication.py
```

This standard-library-only check verifies publication hashes, catalogue/report consistency, and documentation links. It does not run scientific benchmarks, fetch Elliptic2 data, prove theorems, or independently reproduce the measured outcomes. See the [integrity guide](RESEARCH_INTEGRITY.md) for the distinction between current checks and saved scientific audit logs.
