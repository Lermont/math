# Publication and reproduction guide

This directory is an independent review package for **Benchmark spectral topology selection for P2P broadcast and audit family 178 feasibility**. It adds no changes to upstream manuscripts or Lean sources. The mathematical sources are pinned to `openai/math@fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb`.

## Start here

Read [the English research report](RESEARCH_REPORT.md). Original plans, implementation comments and detailed reports may be in Russian; they are retained as historical evidence. Paths and virtual-environment names in those original records refer to the measured local layout. Here, the working directory is `experiments/family178-p2p-topology/`, rather than the historical `D:\projects\math` path.

Python 3.14; create `.venv-graph131` and install `p2p178/requirements.txt`. Optional plotting dependencies are in `p2p178/requirements-plot.txt`.

Use a fresh local copy and unused output/run names for new measurements. Never interpret skipped existing outputs as a fresh benchmark. The unit tests are safe to run without downloaded experiment datasets; test logs from the original prepublication validation are retained under `results/pr-drafts-20261012/`.

## Included and omitted evidence

Downloaded papers, external repository snapshots, original per-job graphs/traces and the large raw simulation JSON are omitted. Construction/scenario/message tables, summary, source audit and original verification record are included. `python restore_references.py` fetches references locally without changing the saved manifest. A mutable upstream API snapshot in that manifest may no longer match; any mismatch is reported, never silently accepted. A fresh benchmark creates the graph and trace artifacts used by its verifier.

Original code, configuration, plans and recorded measurements are copied unchanged. The package adds this guide, an English research report, local reference-restoration helper, a scoped ignore file and a publication manifest. No original benchmark was rerun, no original measured value was edited, and no saved audit was relabeled as a publication-time benchmark. `PUBLICATION_MANIFEST.json` records the exact included bytes and source-relative paths; paths inside historical hash manifests are relative to this experiment directory.

Raw files mentioned by historical reports are not necessarily included here. The omissions above are explicit limits on independent archived-run validation, not missing evidence being treated as a successful check. New runs and their complete outputs remain the route to reproduction.

## Interpretation and license

Keep a paper construction, a restricted certified variant and an experimental heuristic distinct. Unit tests and empirical results do not certify a full theorem or an unmeasured deployment benefit. Original third-party source and dataset licenses remain separate. New prototype code is distributed under the accompanying Apache-2.0 license; upstream mathematical sources retain their original attribution. This is a community experiment, not an official OpenAI release.

## Publication-time checks

The packaged copy passed its relevant unit suite on 2026-10-12; see [the log](PUBLICATION_TESTS.txt). Tests were run from this package directory using the recorded dependency environments. Benchmarks were not rerun.
