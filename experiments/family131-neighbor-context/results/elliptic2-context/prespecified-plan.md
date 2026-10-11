# Elliptic2 context pilot, fixed before test evaluation

## Data and comparison

- Use official Elliptic2 v1 and the existing pinned source of paper 131.
- Select 6,000 subgraphs by stratified sampling (seed 1312027), excluding the
  20,000 previously evaluated subgraphs. Preserve the natural class imbalance.
- Split 40% train, 20% validation, 40% test, stratified, before feature extraction.
- Stream the complete official background_edges.csv ZIP; retain only rows
  incident to selected core nodes. Verify ZIP size/CRC and record hashes.
- Add at most 32 external neighbors per core, selected by a fixed label-blind
  hash. Keep all original core nodes/edges. Use the one-hop incident edge graph,
  not an induced graph: neighbor-to-neighbor edges require a second full scan
  and are out of scope. Retain direction/multiplicity for a control baseline.
- Audit shared nodes and transactions. Remove other labeled core nodes and
  external nodes appearing in more than one split before selecting neighbors;
  also purge any shared transaction IDs. Report how much context this removes.
  This is a strict split-isolated pilot, not a simulation of online deployment.
- IDs are used only for joins, deterministic selection, and reproducibility.
  No IDs, labels of neighbors, or downloaded embeddings enter the features.

## Models and fixed settings

- Core-only NetworkX structural features + ExtraTrees as a matched control.
- Simple depth-3 rules on context degrees and boundary statistics.
- Context NetworkX: core-only features plus context degrees, PageRank,
  Louvain, k-core, clustering, connectivity and marked-core statistics.
- Directed context NetworkX control additionally preserves directed edges
  and multiplicity in its features.
- Paper 131: identical context features plus finite-chain null residuals/tails
  for whole-graph and marked-core statistics. Same ordinary symmetric
  edge-pair switching control, for distinguishing kernel choice from features.
- The graph is projected to simple undirected form for both null models.
  Core membership remains fixed; the graph is rewired without conditioning
  on connectedness or core edge preservation. This is a heuristic feature
  construction, not a fraud probability or a certified mixing result.
- Reuse the tested 131 proposal kernel. Burn 512, 32 retained samples,
  stride 64, count every rejection. No test-driven budget tuning.
- ExtraTrees: 200 trees, minimum leaf 5, all features per split, class weights
  balanced, one CPU thread. Rules: minimum leaf 25, balanced class weights.
- Three runs, seeds 131/132/133, identical records/features/settings per pair.

## Evaluation

- Primary: test average precision (AP), compare with test prevalence and
  paired differences with 95% stratified bootstrap intervals (1,000 draws).
- Also report a cluster bootstrap over test components connected by shared
  nodes/transactions, to check sensitivity to dependence within the test set.
- Secondary: ROC AUC, precision/recall at top 100, recall at a threshold
  selected on validation for at most 1% false positives, realized test FPR.
- Fresh process per method; count feature extraction, fit and prediction.
  Report test feature+prediction time and process peak working set separately.
  CSV acquisition/preparation is a shared cost, measured separately.
- Verify sampler degree/simple-graph invariants and core-marked statistics,
  exact feature parity and split overlap checks. Preserve all prior results.
- A small retrospective sample cannot establish production readiness,
  temporal validity, or superiority over full-data trained GNN systems.
