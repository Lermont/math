# Test whether one-hop Elliptic2 context changes the value of family 131 null features

## Publication contents

This PR adds an independent experiment under `experiments/family131-neighbor-context/`. Run the commands below from that directory. The English research report is [RESEARCH_REPORT.md](RESEARCH_REPORT.md); the [publication guide](PUBLICATION.md) records setup, included evidence, and artifact exclusions.

The code and original plans are preserved byte for byte. Recorded audits describe the original complete local archive; they are not claims that omitted artifacts can be audited from this checkout. No new timed benchmark was run to prepare this publication. The hypothesis IDs below are editorial labels for the questions investigated, not a claim that every question was preregistered.

## Summary

Extend the isolated-subgraph experiment with real neighboring transactions on **6,000 previously unused Elliptic2 subgraphs**. The extension adds split-isolated one-hop context, a directed control, paired feature checks, and bootstrap intervals that also account for shared context within the test set.

Context improves the observed AP of ordinary graph features on this new sample. Adding the family 131 null features provides no convincing additional improvement: AP is **6.08% versus 6.01%**, with wider uncertainty than the observed difference and higher runtime.

## Hypotheses and outcomes

| ID | Hypothesis | Outcome |
|---|---|---|
| C1 | Real neighboring transactions add predictive information beyond core-only structure. | Supported conditionally on this split: context minus core AP is +3.48 percentage points, with both reported paired intervals above zero. |
| C2 | Direction and multiplicity are useful when context is available. | The directed model has the highest observed AP, 9.51%. Its gain over core-only has positive paired intervals; a universal ranking over the other context models is not established. |
| C3 | Family 131 residuals add useful information beyond the same context features. | Not established: +0.07 percentage points over the context baseline, with intervals crossing zero. |
| C4 | The paper kernel is preferable to ordinary switching with matched features/budget. | Not established: +0.42 percentage points, with intervals crossing zero. |
| C5 | Preventing cross-split overlap and accounting for within-test dependence leave the main conclusion intact. | Split checks pass; component-bootstrap intervals still do not establish an incremental family 131 benefit. |

## Scope and relation to the first experiment

Add `graph131/context_download.py`, `context_data.py`, `context_features.py`, `context_worker.py`, `context_run.py`, `context_report.py`, and `tests/test_graph131_context.py`, with the separate [context plan](graph131/CONTEXT_PLAN.md), [README](graph131/CONTEXT_README.md), and `results/elliptic2-context/` artifacts. Reuse the tested switch kernel from the isolated-subgraph experiment.

Preserve the first experiment's results. This is a new sample and a new design: all 6,000 selected subgraph IDs are disjoint from the earlier 20,000. Use the core-only control on this new sample for the context comparison; comparing AP between the two studies would confound data and model differences.

## Acquisition and leakage controls

Select with seed `1312027`; preserve class imbalance; split into **2,400 train / 1,200 validation / 2,400 test** records. The test set contains **55 suspicious records**, giving constant-score AP **2.29%**.

The acquisition scans all **196,215,606 rows** of official `background_edges.csv`, verifies ZIP CRC, and records the streamed CSV hash. It transfers 24.48 GB compressed and processes 82.88 GB uncompressed, retaining 95,539 rows incident to 21,581 selected core nodes. The recorded acquisition cost is 26.8 minutes and 543 MiB peak process memory, separate from model timing.

Before choosing neighbors, remove other labeled core nodes, 436 external nodes shared across splits, and external occurrences of 2,792 shared transaction IDs. The resulting train/validation/test graphs have no node or transaction-ID overlap. This pruning changes the available context and limits the deployment interpretation.

At most 32 external neighbors per core are chosen using a fixed label-blind hash. External context remains for 3,490 of 6,000 records; the cap affects 30. Neighbor-to-neighbor edges are not collected, so these are **one-hop incident-edge graphs, not complete induced ego graphs**. IDs serve only joins, selection, and auditing. Numeric payment attributes and downloaded embeddings/models are not used. RevTrack's transformed sender–receiver pickle was examined as an alternative source and excluded from the reproducible pipeline.

## Methods and evaluation

Compare core-only NetworkX features, depth-three rules, NetworkX context features, a directed/multiplicity-preserving context control, and the same context features augmented with either paper-kernel or conventional-switch residuals.

ExtraTrees uses 200 trees, minimum leaf size five, all features per split, balanced weights, and one thread. Seeds are 131/132/133. Both null models use the simple undirected projection, 512 burn-in proposals, 32 retained states, and stride 64, counting rejections. Core membership stays marked while rewiring; connectedness and original core edges are not conditioned on. The features remain finite-chain heuristics.

AP is primary. Thresholds are selected only on validation for at most 1% validation FPR. Test labels are not used to tune features, model parameters, or sampling budgets. Report both stratified row bootstrap and context-component bootstrap with 1,000 paired draws. The test set has 2,383 dependence components, largest size four.

## Results

Quality is the mean over three seeds; runtime and peak memory are medians.

| Method | AP, % | ROC-AUC | Expected suspicious in top 100 | Full run, s | Test features + prediction, s | Peak MiB |
|---|---:|---:|---:|---:|---:|---:|
| Core-only graph | 2.52 | 0.514 | 3.07 | 7.98 | 2.92 | 192.8 |
| Simple rules | 3.26 | 0.593 | 5.45 | 0.36 | 0.08 | 191.8 |
| NetworkX context | 6.01 | 0.632 | 8.30 | 28.49 | 10.88 | 198.8 |
| Directed context | 9.51 | 0.587 | 10.42 | 34.22 | 13.07 | 201.3 |
| Context + family 131 | 6.08 | 0.604 | 6.05 | 38.54 | 14.61 | 204.0 |
| Context + conventional switches | 5.65 | 0.597 | 6.56 | 39.44 | 14.99 | 203.8 |

Expected top-100 counts use random tie resolution; fractional counts are intentional.

| Paired AP difference | Mean, percentage points | Row-bootstrap 95% interval | Context-component 95% interval |
|---|---:|---:|---:|
| Family 131 − context | +0.07 | [-1.85, +1.53] | [-1.94, +1.49] |
| Family 131 − directed context | -3.44 | [-9.42, +1.19] | [-9.71, +1.47] |
| Family 131 − conventional switches | +0.42 | [-0.37, +1.16] | [-0.33, +1.16] |
| Context − core-only | +3.48 | [+0.51, +8.84] | [+0.67, +9.36] |
| Directed context − core-only | +6.99 | [+1.16, +14.77] | [+1.48, +15.07] |

At validation-selected thresholds, context, directed context, and family 131 achieve test recalls **5.45%, 9.09%, and 4.85%**, with realized test FPRs **1.48%, 0.41%, and 0.95%** respectively. A validation FPR constraint does not guarantee the same test FPR.

## Diagnostics, reporting correction, and limits

Both samplers have 3,379 frozen graphs and 6,709,760 proposals per run. Mean accepted proposals are 220,731 for the paper kernel and 1,183,703 for conventional switching; mean distinct retained states per active graph are 12.13 and 19.35. These observations do not certify convergence or uniformity.

After measurement, the CSV reader in `context_report.py` was corrected to use round-trip float parsing. Adjacent floating-point prediction scores otherwise changed order and affected recomputed AP. The original reporting source is retained; runtime/model/feature sources, predictions, and timings were unchanged. The [final verification](results/elliptic2-context/final-verification.json) confirms all 18 measurements, feature parity, prediction/AP agreement, split isolation, and preservation of the prior sample. These PR numbers use the corrected report.

The bootstrap conditions on one split and fitted models. The background spans the dataset's available period, and no temporal holdout was constructed. Context pruning and the 32-neighbor cap further limit scope. These results do not establish prospective fraud detection, full-graph GNN performance, or production readiness. The suspicious label is a dataset annotation.

## Validation and reproduction

The seven sampler tests and four context tests all passed again during drafting; [fresh log](results/pr-drafts-20261012/root-tests.txt). Core/context feature parity and overlap checks are recorded in [checks.json](results/elliptic2-context/checks.json).

With previously acquired and prepared data:

```powershell
.\.venv-graph131\Scripts\python.exe -m unittest discover -s tests -p 'test_graph131*.py' -v
.\.venv-graph131\Scripts\python.exe -m graph131.context_run
.\.venv-graph131\Scripts\python.exe -m graph131.context_report
```

The runner skips compatible saved measurements. Use an isolated copy and unused result destinations for new timing; acquisition is a separate substantial operation documented in [the README](graph131/CONTEXT_README.md). The recorded environment is Windows, Python 3.14.7, NetworkX 3.7, and scikit-learn 1.9.1 on an Intel Core Ultra 7 255H.

## Evidence and sources

Review [the report](results/elliptic2-context/report.md), [metrics](results/elliptic2-context/summary.csv), [intervals](results/elliptic2-context/uncertainty.json), [data audit](results/elliptic2-context/data_audit.json), [acquisition record](results/elliptic2-context/acquisition.json), and [run metadata](results/elliptic2-context/run-metadata.json).

The [source manifest](references/graph131-context/sources.json) pins official Elliptic2 v1 and family 131 to `openai/math@fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb`. Raw dataset material stays local; its recorded CC BY-NC-ND 4.0 license is separate from the repository code license.
