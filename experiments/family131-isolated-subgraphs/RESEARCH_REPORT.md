# Evaluate family 131 degree-preserving null features on isolated Elliptic2 subgraphs

## Publication contents

This PR adds an independent experiment under `experiments/family131-isolated-subgraphs/`. Run the commands below from that directory. The English research report is [RESEARCH_REPORT.md](RESEARCH_REPORT.md); the [publication guide](PUBLICATION.md) records setup, included evidence, and artifact exclusions.

The code and original plans are preserved byte for byte. Recorded audits describe the original complete local archive; they are not claims that omitted artifacts can be audited from this checkout. No new timed benchmark was run to prepare this publication. The hypothesis IDs below are editorial labels for the questions investigated, not a claim that every question was preregistered.

## Summary

Add a controlled Elliptic2 experiment that uses the family 131 lazy switch kernel to generate degree-conditioned structural features. Compare the resulting classifier with simple rules, degree summaries, standard NetworkX features, a conventional switch kernel, and a control retaining direction and repeated payments.

The main result is **no convincing practical improvement from the family 131 features on this representation**. Test average precision remains close to suspicious-label prevalence, while feature extraction becomes more expensive.

## Hypotheses and outcomes

| ID | Hypothesis | Outcome |
|---|---|---|
| G1 | Degree-conditioned residuals improve classification beyond ordinary graph features. | Not established: AP increases by 0.103 percentage points, with a paired 95% interval crossing zero. |
| G2 | The paper's proposal kernel is more useful than a conventional degree-preserving switch at the same proposal budget. | Not established: AP is 2.288% versus 2.265%; the paired difference is uncertain. |
| G3 | Removing direction and repeated edges explains the weak result. | The directed control also stays near prevalence; it does not recover useful discrimination on these isolated subgraphs. |
| G4 | Increasing the proposal budget fourfold materially improves the result. | Not supported by the single-seed sensitivity run: AP is 2.243%, with substantially higher runtime. |
| G5 | The implementation matches the specified transition kernel and preserves graph invariants. | Supported by exhaustive small-state checks and independent structural-count tests; finite-run mixing remains unverified. |

## Scope and method

Package `graph131/switches.py`, `features.py`, `directed.py`, `data.py`, `worker.py`, `evaluate.py`, `run.py`, `extra_runs.py`, and `report.py`, with the [prespecified plan](graph131/PLAN.md), [tests](tests/test_graph131.py), source metadata, and `results/elliptic2/` evidence.

The paper kernel stays put with probability 1/2, samples four vertices uniformly, and samples an ordered pair of distinct perfect matchings uniformly. Rejected proposals count as steps. Disconnected realizations are allowed. The conventional control uses a symmetric edge-pair proposal and the same residual statistics and budget.

Each active graph receives 512 burn-in proposals and 32 retained states separated by 64 proposals: **2,560 proposals**, including rejections. The five null statistics are triangle count, four-cycle count, degree mixing, component count, and largest-component fraction. Features include scaled residuals and smoothed empirical tails. The exact uniform sampler with the rare exponential branch is not implemented. These finite-chain features are heuristic; they are not calibrated p-values or fraud probabilities.

All ExtraTrees models use 200 trees, `min_samples_leaf=10`, `max_features=1.0`, balanced class weights, and one thread. Simple rules use a depth-three decision tree. Model/sampler seeds are 131, 132, and 133, with no test-driven hyperparameter selection.

## Data and evaluation

Use official Elliptic2 v1 `connected_components.csv`, `nodes.csv`, and `edges.csv`. Select **20,000 of 121,810 labeled subgraphs**, stratified with seed `1312026`. The fixed train/validation/test sizes are **12,000 / 4,000 / 4,000**, containing **272 / 91 / 91 suspicious** records. Test prevalence is **2.275%**.

Node and transaction IDs do not overlap across splits and are not predictive features. The main projection removes direction and collapses 5,119 parallel/reverse edge rows; the directed control separately retains direction and multiplicity. Background context, amounts, and time attributes are absent. The split is random, not temporal, and the experiment does not reproduce GLASS or a full-data GNN pipeline.

Primary quality is average precision (AP), not accuracy or trapezoidal PR-AUC. Secondary metrics include ROC-AUC, top-100 precision/recall with expected random tie breaking, and recall at a threshold selected only on validation for at most 1% validation FPR. Realized test FPR is reported separately.

## Results

Quality is averaged over three seeds. Runtime and memory are medians of separate processes.

| Method | AP, % | ROC-AUC | Full run, s | 4,000 test graphs, s | Peak process memory, MiB |
|---|---:|---:|---:|---:|---:|
| Simple rules | 2.376 | 0.517 | 0.50 | 0.08 | 187.0 |
| Degrees + ExtraTrees | 2.127 | 0.472 | 1.21 | 0.10 | 189.4 |
| NetworkX + ExtraTrees | 2.185 | 0.483 | 27.43 | 5.18 | 194.4 |
| NetworkX + family 131 | 2.288 | 0.490 | 46.94 | 8.94 | 209.5 |
| NetworkX + conventional switches | 2.265 | 0.487 | 49.22 | 9.45 | 209.7 |
| Directed graph features | 2.279 | 0.492 | 46.11 | 8.29 | 209.5 |

For family 131 minus NetworkX, the AP difference is **+0.103 percentage points**, with a paired 95% bootstrap interval of **[-0.092, +0.623] percentage points**. For family 131 minus conventional switches it is about **+0.023**, with interval **[-0.420, +0.553]**. These 1,000 stratified paired resamples describe uncertainty conditional on the fixed split and fitted models; they do not represent the variation from new training splits.

The fourfold-budget control uses seed 131, burn-in 2,048, stride 256, and 32 retained states. It produces AP **2.243%**, ROC-AUC **0.496**, runtime **203.15 s**, and peak memory **208.2 MiB**. It remains a sensitivity check and is not substituted for the prespecified main run.

## Diagnostics and limitations

- 13,481 graphs have fewer than four vertices; 13,989 of 20,000 have no valid switch. For another 1,757, none of the five retained-state statistics changes in the seed-131 run. This limits the information the chosen null features can add.
- The seed-131 main paper run counts 15,388,160 proposals and 826,635 accepted switches; the conventional kernel accepts 2,892,943 under the same proposal budget. Acceptance counts do not establish mixing.
- The active test subset contains 1,242 graphs and only 31 suspicious labels. Its saved metrics use the already-trained models; no separate model is trained on that subset.
- Full runtime includes prepared-input loading, all feature extraction, fitting, evaluation, and artifact saving. Acquisition and shared CSV preparation are excluded. Test runtime includes features and prediction, without retraining. Peak working set includes Python, dependencies, data, features, and model.
- The available representation and small positive class constrain the conclusion. It does not establish future-transaction performance, the validity of the theorem, or the performance of every application of the kernel.

## Validation and reproduction

The original [checks](results/elliptic2/checks.json) record seven passing tests, **1,158 enumerated paper-kernel states**, 70 exact conventional-kernel states, and identical shared feature matrices/IDs across paired methods. Tests cover exact transition probabilities, reversibility, degree and simplicity preservation, independent motif counts, reproducibility, tied scores, and validation thresholds. All seven passed again during drafting; see [the fresh root-suite log](results/pr-drafts-20261012/root-tests.txt).

With prepared local data and the pinned `.venv-graph131` environment:

```powershell
.\.venv-graph131\Scripts\python.exe -m unittest discover -s tests -p test_graph131.py -v
.\.venv-graph131\Scripts\python.exe -m graph131.run
.\.venv-graph131\Scripts\python.exe -m graph131.extra_runs
.\.venv-graph131\Scripts\python.exe -m graph131.report
```

These commands resume/skip existing results. A genuinely new timed run requires an isolated project copy with prepared data and unused `results/elliptic2/seed*` destinations, as described in [the README](graph131/README.md). Do not present a skipped run as new measurement. Acquisition commands are documented separately and are not needed to inspect the saved evidence.

## Evidence and source status

Review [the full report](results/elliptic2/report.md), [metrics](results/elliptic2/summary.csv), [paired intervals](results/elliptic2/uncertainty.json), [data audit](results/elliptic2/data_audit.json), and [run metadata](results/elliptic2/run_metadata.json). Per-seed predictions and record-level sampler diagnostics remain in the local research archive; aggregate evidence is included here.

Family 131 is pinned to [openai/math at fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb](https://github.com/openai/math/blob/fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb/lean/docs/131.md); source URLs/hashes are in [the manifest](references/graph131/sources.json). Raw Elliptic2 data remain local, with the dataset's recorded CC BY-NC-ND 4.0 license kept separate from the code license.
