# Publication and reproduction guide

This directory is an independent review package for **Evaluate family 325 truncation bounds and their practical effect on matrix-exponential actions**. It adds no changes to upstream manuscripts or Lean sources. The mathematical sources are pinned to `openai/math@fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb`.

## Start here

Read [the English research report](RESEARCH_REPORT.md). Original plans, implementation comments and detailed reports may be in Russian; they are retained as historical evidence. Paths and virtual-environment names in those original records refer to the measured local layout. Here, the working directory is `experiments/family325-matrix-exponential/`, rather than the historical `D:\projects\math` path.

Python 3.14; create `.venv-filter325` and install `filter325/requirements.txt`.

Use a fresh local copy and unused output/run names for new measurements. Never interpret skipped existing outputs as a fresh benchmark. The unit tests are safe to run without downloaded experiment datasets; test logs from the original prepublication validation are retained under `results/pr-drafts-20261012/`.

## Included and omitted evidence

Downloaded papers, redundant upstream proof snapshots, numeric matrix caches and output vectors are omitted. Measurement CSV, case metadata, exact-bound validation summary, versions and recorded audits are included. `python restore_references.py` restores pinned reference sources locally; run it before the original source audit. Installed SciPy source snapshots and its BSD license are included. A fresh benchmark generates matrices and outputs for independent checking; the archived-run validation cannot be repeated without the omitted outputs.

Original code, configuration, plans and recorded measurements are copied unchanged. The package adds this guide, an English research report, local reference-restoration helper, a scoped ignore file and a publication manifest. No original benchmark was rerun, no original measured value was edited, and no saved audit was relabeled as a publication-time benchmark. `PUBLICATION_MANIFEST.json` records the exact included bytes and source-relative paths; paths inside historical hash manifests are relative to this experiment directory.

Raw files mentioned by historical reports are not necessarily included here. The omissions above are explicit limits on independent archived-run validation, not missing evidence being treated as a successful check. New runs and their complete outputs remain the route to reproduction.

## Interpretation and license

Keep a paper construction, a restricted certified variant and an experimental heuristic distinct. Unit tests and empirical results do not certify a full theorem or an unmeasured deployment benefit. Original third-party source and dataset licenses remain separate. New prototype code is distributed under the accompanying Apache-2.0 license; upstream mathematical sources retain their original attribution. This is a community experiment, not an official OpenAI release.

## Publication-time checks

The packaged copy passed its relevant unit suite on 2026-10-12; see [the log](PUBLICATION_TESTS.txt). Tests were run from this package directory using the recorded dependency environments. Benchmarks were not rerun.
