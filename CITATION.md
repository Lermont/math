# Citing the independent experiments

Citation metadata in this fork applies to the seven experiments under `experiments/`. It does not assign their authorship to OpenAI or reassign authorship of the upstream manuscripts.

Use the public publishing-account name **Lermont**, the experiment title, the year **2026**, and a link to the exact report snapshot. The current collection citation is provided in [CITATION.cff](CITATION.cff); individual [BibTeX entries](experiments/CITATIONS.bib) use fixed Git URLs.

## Collection

Lermont (GitHub account). (2026). *Seven practical experiments associated with openai/math* [Research software and technical reports]. Git snapshot `60ed0f3d9dacd3a279008241328b7692dbb211b8`. [Recorded collection](https://github.com/Lermont/math/tree/60ed0f3d9dacd3a279008241328b7692dbb211b8/experiments).

This is a Git snapshot identifier, not a DOI or a claim of a peer-reviewed publication. The date in `CITATION.cff` is the original snapshot's UTC publication date, not the date of a benchmark rerun.

## Individual reports

| Report | Fixed version to cite |
|---|---|
| 1. Evaluate family 128 shortest-superstring storage against indexed and compressed baselines | [Report permalink](https://github.com/Lermont/math/blob/60ed0f3d9dacd3a279008241328b7692dbb211b8/experiments/family128-string-storage/RESEARCH_REPORT.md) |
| 2. Evaluate family 131 degree-preserving null features on isolated Elliptic2 subgraphs | [Report permalink](https://github.com/Lermont/math/blob/60ed0f3d9dacd3a279008241328b7692dbb211b8/experiments/family131-isolated-subgraphs/RESEARCH_REPORT.md) |
| 3. Test whether one-hop Elliptic2 context changes the value of family 131 null features | [Report permalink](https://github.com/Lermont/math/blob/60ed0f3d9dacd3a279008241328b7692dbb211b8/experiments/family131-neighbor-context/RESEARCH_REPORT.md) |
| 4. Audit family 125 feasibility and benchmark an explicitly heuristic LP rounding pipeline | [Report permalink](https://github.com/Lermont/math/blob/60ed0f3d9dacd3a279008241328b7692dbb211b8/experiments/family125-feasibility-pilot/RESEARCH_REPORT.md) |
| 5. Measure OneBatchPAM scaling and rare-client failures against FasterPAM | [Report permalink](https://github.com/Lermont/math/blob/60ed0f3d9dacd3a279008241328b7692dbb211b8/experiments/family125-pam-scale/RESEARCH_REPORT.md) |
| 6. Benchmark spectral topology selection for P2P broadcast and audit family 178 feasibility | [Report permalink](https://github.com/Lermont/math/blob/60ed0f3d9dacd3a279008241328b7692dbb211b8/experiments/family178-p2p-topology/RESEARCH_REPORT.md) |
| 7. Evaluate family 325 truncation bounds and their practical effect on matrix-exponential actions | [Report permalink](https://github.com/Lermont/math/blob/60ed0f3d9dacd3a279008241328b7692dbb211b8/experiments/family325-matrix-exponential/RESEARCH_REPORT.md) |

When citing a numerical conclusion, include its dataset/workload, comparator, units, and uncertainty or limitations. The [catalogue](experiments/index.json) connects each study to its current report, fixed report, measurements, and recorded checks.

## Upstream papers and third-party material

Cite the underlying mathematical paper separately using the citation in its [pinned upstream manuscript directory](https://github.com/openai/math/tree/fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb/preprints); the individual reports identify the exact sources. Cite external datasets and packages according to the corresponding source lists and licenses.

For authorship, AI assistance, review status, omitted artifacts, and correction handling, see [Research integrity](experiments/RESEARCH_INTEGRITY.md).
