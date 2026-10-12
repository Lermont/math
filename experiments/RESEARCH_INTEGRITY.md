# Research integrity, provenance, and reproduction scope

## Authorship and review status

The seven experiments in this fork are published by the [Lermont GitHub account](https://github.com/Lermont). Citation metadata uses that public account name; it does not infer a legal name, institution, ORCID, or additional authors. English reports, summaries, and publication documentation were prepared with AI assistance. AI assistance and successful unit tests are not substitutes for independent scientific review.

No independent peer review is documented in this repository. These are community research software and technical reports, not an official OpenAI evaluation or an endorsement by the upstream authors. The original manuscripts retain their own authorship, license, citation, and verification status.

## Sources and version identity

The mathematical inputs are pinned to [openai/math@fd4aeeb](https://github.com/openai/math/tree/fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb). Each package retains its source manifests, reference hashes, and implementation boundary.

The fixed experimental publication snapshot is [60ed0f3d9dacd3a279008241328b7692dbb211b8](https://github.com/Lermont/math/tree/60ed0f3d9dacd3a279008241328b7692dbb211b8). The [citation guide](../CITATION.md) and [catalogue](index.json) distinguish immutable report links from mutable current documentation. The discovery update changes navigation, abstracts, and metadata; the original English reports, benchmark code, plans, measurements, and test logs remain unchanged.

## What each form of evidence establishes

| Evidence | What it checks | What it does not establish |
|---|---|---|
| `PUBLICATION_MANIFEST.json` and the publication integrity check | Included file sizes and hashes; resolvable local evidence links; consistent catalogue and report identity | Truth of a mathematical theorem or empirical generalization |
| `PUBLICATION_TESTS.txt` | Saved publication-time execution of a package's unit tests | A new benchmark or an independent reproduction |
| Saved benchmark measurements and audit reports | The recorded workload and checks described by that experiment | Complete public reproducibility when required raw artifacts were omitted |
| A new independent run with the specified inputs and environment | A new observation to compare with the original result | Automatic agreement across hardware, splits, distributions, or implementations |

The seven package logs contain **59 test executions**, including repeated sampler tests in the context package. They must not be described as 59 distinct scientific validations. Dates in GitHub timestamps are UTC; recorded local publication checks use their stated local dates. Timed benchmarks were not rerun to add this documentation.

## Reproduce without silently changing the claim

1. Select a commit, experiment, and question. Use its `PUBLICATION.md` to identify the required environment, inputs, licenses, and omitted artifacts.
2. Restore reference material or obtain datasets only as described by that package. Record source hashes and report any mismatch; do not silently substitute newer sources.
3. Run the appropriate unit suite, then a new benchmark with an unused output directory. Preserve seeds, splits, stopping rules, thresholds, access traces, timing boundaries, and memory accounting.
4. Run the scientific verifier on the complete new output. Compare results with the published tables and retain failures as well as successes.

The Elliptic2 raw data and row-level artifacts are not redistributed. Other packages omit some downloaded references, caches, output vectors, or per-worker files. Their saved historical audits refer to the original full local archive. The per-study guides are authoritative about which checks can be repeated from the public package alone. Dataset and third-party source licenses remain separate from prototype-code licensing.

Family 125's complete construction and family 178's complete deterministic generator were not implemented. Finite family 131 sampling budgets do not certify mixing. Family 325's exact-arithmetic truncation certificate is not a complete float64-error certificate. Hypothesis identifiers in the English reports are editorial labels, not a blanket claim of preregistration.

## Current publication checks

Run `python tools/verify_research_publication.py` from the repository root. It needs Python 3.10+ and no third-party packages or network access. A fresh clone can preserve recorded bytes with:

```text
git -c core.autocrlf=false clone https://github.com/Lermont/math.git
cd math
python tools/verify_research_publication.py
```

The [GitHub Actions workflow](../.github/workflows/research-publication.yml) runs the same publication check with read-only repository permissions. Its status means the published files and navigation passed those checks; it is not a badge of independent peer review or benchmark replication.

## Corrections and independent replication

For a correction, submit a pull request identifying the experiment ID, exact commit, affected claim, command/environment, and supporting output. Keep original measurements and clearly distinguish a corrected derived summary from a newly timed run. For an independent replication, identify what was reproduced, all deviations, and whether the required original artifacts were available.

The [original seven PRs](README.md#research-directory) provide the publication history. External citations, DOI deposits, independent review, and third-party replication are not claimed merely because metadata or a file check exists.
