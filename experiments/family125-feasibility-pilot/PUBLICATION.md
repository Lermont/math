# Publication and reproduction guide

This directory is an independent review package for **Audit family 125 feasibility and benchmark an explicitly heuristic LP rounding pipeline**. It adds no changes to upstream manuscripts or Lean sources. The mathematical sources are pinned to `openai/math@fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb`.

## Start here

Read [the English research report](RESEARCH_REPORT.md). Original plans, implementation comments and detailed reports may be in Russian; they are retained as historical evidence. Paths and virtual-environment names in those original records refer to the measured local layout. Here, the working directory is `experiments/family125-feasibility-pilot/`, rather than the historical `D:\projects\math` path.

Python 3.11 x64; create `.venv-kmedian125` and install `kmedian125/requirements.lock.txt`. The measured native wheels are Windows x64.

Use a fresh local copy and unused output/run names for new measurements. Never interpret skipped existing outputs as a fresh benchmark. The unit tests are safe to run without downloaded experiment datasets; test logs from the original prepublication validation are retained under `results/pr-drafts-20261012/`.

## Included and omitted evidence

Downloaded papers, UCI Seeds input, external repository snapshots and binary wheels are omitted. Restore the pinned references locally with `python restore_references.py` before reproducing the pilot. UCI Seeds is attributed in `kmedian125/SOURCES.md` and carries CC BY 4.0. The original per-worker files and numeric caches are omitted; the original raw JSONL, exact-bound summary, measurement tables and audit record are included. Original archived-run audits require the complete original artifacts; a newly generated run creates its own complete artifacts.

Original code, configuration, plans and recorded measurements are copied unchanged. The package adds this guide, an English research report, local reference-restoration helper, a scoped ignore file and a publication manifest. No original benchmark was rerun, no original measured value was edited, and no saved audit was relabeled as a publication-time benchmark. `PUBLICATION_MANIFEST.json` records the exact included bytes and source-relative paths; paths inside historical hash manifests are relative to this experiment directory.

Raw files mentioned by historical reports are not necessarily included here. The omissions above are explicit limits on independent archived-run validation, not missing evidence being treated as a successful check. New runs and their complete outputs remain the route to reproduction.

## Interpretation and license

Keep a paper construction, a restricted certified variant and an experimental heuristic distinct. Unit tests and empirical results do not certify a full theorem or an unmeasured deployment benefit. Original third-party source and dataset licenses remain separate. New prototype code is distributed under the accompanying Apache-2.0 license; upstream mathematical sources retain their original attribution. This is a community experiment, not an official OpenAI release.

## Publication-time checks

The packaged copy passed its relevant unit suite on 2026-10-12; see [the log](PUBLICATION_TESTS.txt). Tests were run from this package directory using the recorded dependency environments. Benchmarks were not rerun.
