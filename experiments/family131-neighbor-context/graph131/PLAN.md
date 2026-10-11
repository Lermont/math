# Elliptic2 pilot: decisions made before inspecting test outcomes

- Dataset: official Elliptic2 version 1, only connected_components.csv,
  nodes.csv and edges.csv. The 49-million-node background and anonymized
  attributes are excluded. This is independent-subgraph classification, not
  reproduction of GLASS or a comparison against commercial products.
- Select 20,000 subgraphs by stratified sampling, seed 1312026. Split 60/20/20
  train/validation/test. Verify node and transaction separation. Keep the natural
  suspicious prevalence. No identifiers are model features.
- Every method sees the same simple undirected graph: collapse parallel and
  opposite edges, discard direction, amounts and time. Audit these losses.
- Rules: depth-3 decision tree over size, density and degree summaries.
- Degree control: ExtraTrees over the same summaries.
- Graph baseline: the same ExtraTrees plus NetworkX PageRank, Louvain,
  clustering, core, bridges and connectivity features.
- Paper 131: add degree-conditioned structural residual features to the graph
  baseline. Use exactly the paper's lazy four-vertex proposal kernel, count all
  proposals including rejections, allow disconnected realizations.
- Conventional randomization control: identical residual features using a lazy
  edge-pair proposal kernel with uniform stationary law (not NetworkX's
  successful-swap stopping rule). This is our reference implementation of a
  standard switch, not an optimized external engine.
- Both samplers: 512 burn-in proposals, 32 retained graphs, 64 proposals between
  retained graphs. Trivial degree spaces may be skipped after an exhaustive
  valid-switch check. Budgets are heuristic, not a mixing guarantee.
- Null statistics: triangles, four-cycles, degree mixing, component count,
  largest-component fraction. Features are observed minus sample mean, scaled
  by sqrt(sample variance + 1), and smoothed upper/lower tail frequencies.
  They are Monte Carlo features, not calibrated p-values or fraud probabilities.
- No hyperparameter search: ExtraTrees has 200 trees, min_samples_leaf=10,
  max_features=1.0, class_weight=balanced, one thread. Three paired seeds
  (131, 132, 133), including the model and sampler seeds.
- Primary quality: average precision (AP, not trapezoidal PR-AUC). Also ROC-AUC,
  precision/recall at top 100 with expected tie breaking, and test recall/FPR at
  a threshold chosen only on validation to allow at most 1% validation FPR.
- Timing: feature extraction for each split, fit and prediction separately;
  report total workload time for all 20,000 graphs. CSV acquisition is excluded.
  Measure each method in a fresh subprocess, one CPU thread, report Windows
  process peak working set including Python, libraries, data and model.
- Correctness: enumerate small degree spaces; compare exact transition
  probabilities with the paper, check reversibility, degree preservation and
  structural counts against independent NetworkX calculations.
- Evidence: retain seeds, input hashes, split IDs, predictions, raw timing,
  versions and source snapshot. Paired stratified bootstrap (1,000 resamples)
  describes test uncertainty conditional on the fixed split and trained models.
- Decide usefulness from measured quality gain versus added runtime; do not
  infer real-world fraud detection, production scaling or theorem validity.

## Additional control after the raw-data audit

The primary matched-input comparison discards direction and repeated payments.
An additional NetworkX/ExtraTrees baseline retains both from edges.csv, using
the same frozen split, 200-tree settings and three seeds. It is added to check
the cost of projecting the data to paper 131's model. It is not a tuned result
or a reproduction of a GNN; there is no test-driven hyperparameter search.

The finite-budget caveat is checked with one additional paper-kernel run at
seed 131: burn-in 2,048, stride 256, still 32 retained samples (4x proposals).
Its result is reported as sensitivity, never selected as the main result.
