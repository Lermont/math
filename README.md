# Practical benchmarks of openai/math: seven experiments

This fork of [openai/math](https://github.com/openai/math) preserves the upstream mathematical collection and adds **seven independent practical experiments** under [`experiments/`](experiments/). They investigate applications and baselines associated with manuscript families 128, 131, 125, 178, and 325. The experiment reports and conclusions are contributions of this fork, separate from the upstream manuscripts and their authorship.

The studies cover shortest-superstring storage, Elliptic2 graph anomaly features, k-median/PAM clustering, P2P broadcast topology, and matrix-exponential actions.

[Research directory](experiments/README.md) · [How to cite](CITATION.md) · [Evidence and review status](experiments/RESEARCH_INTEGRITY.md) · [Machine-readable catalogue](experiments/index.json) · [LLM reading guide](llms.txt)

## Practical experiments

The table summarizes the completed measurements. Each experiment title links to its detailed English research report; **setup** links to its publication and reproduction guide. Results apply to the recorded datasets, implementations, and measurement conditions.

| Experiment | Main recorded results | Conclusion and limits |
|---|---|---|
| **1. [Family 128: string storage](experiments/family128-string-storage/RESEARCH_REPORT.md)** · [setup](experiments/family128-string-storage/PUBLICATION.md) | Across 11 datasets and six methods, 64 of 66 archive attempts succeeded. For 128 overlapping binary fragments, total storage was **1,265 bytes**, versus 8,728 for plain storage, 2,010 for block Zstd, and 1,167 for whole-dataset Zstd. | Sharing overlaps can combine compact storage with inexpensive reads by original ID. Whole-dataset Zstd remained smaller; packing was expensive, several other datasets expanded, and two larger construction cases hit resource limits. |
| **2. [Family 131: isolated Elliptic2 subgraphs](experiments/family131-isolated-subgraphs/RESEARCH_REPORT.md)** · [setup](experiments/family131-isolated-subgraphs/PUBLICATION.md) | On 20,000 records, adding family 131 features to the NetworkX baseline raised test AP from **2.185% to 2.288%**; test positive-label prevalence was 2.275%. The paired gain was **+0.103 percentage points**, with a 95% interval of **[-0.092, +0.623]**. Full-run time increased from 27.43 to 46.94 seconds. | No convincing incremental classification benefit was established. Kernel and invariant checks support the implementation, but do not certify finite-run MCMC mixing or turn anomaly features into fraud probabilities. |
| **3. [Family 131: neighboring transaction context](experiments/family131-neighbor-context/RESEARCH_REPORT.md)** · [setup](experiments/family131-neighbor-context/PUBLICATION.md) | On **6,000 previously unused records**, ordinary graph AP increased from **2.52% without context to 6.01% with context**; directed context reached 9.51%. Adding family 131 features to the context baseline yielded 6.08%, a +0.07-point gain whose paired intervals crossed zero. | Real context helped on this split; an additional benefit from family 131 sampling was not established. Comparisons use the same new sample within this experiment, rather than the isolated-study sample. |
| **4. [Family 125: feasibility audit and LP pilot](experiments/family125-feasibility-pilot/RESEARCH_REPORT.md)** · [setup](experiments/family125-feasibility-pilot/PUBLICATION.md) | In the 380-run pilot, the ten medium/real tasks had a mean dataset-median gap to a certified lower bound of **0.136% for LP-DR16-swap**, versus **0.451% for FasterPAM**. Median fresh algorithm times were **906.35 ms versus 2.32 ms**. The literal paper preparation recipe implied a grid parameter of at least **6.08522 × 10^28** at epsilon = 0.1. | The separately defined LP heuristic offered a costly quality check, without per-instance dominance. The full family 125 construction was not implemented; its approximation guarantee is not claimed for this heuristic. A gap to a lower bound is an upper bound on relative suboptimality, not necessarily the exact optimality gap. |
| **5. [Family 125 follow-up: PAM scaling and rare clients](experiments/family125-pam-scale/RESEARCH_REPORT.md)** · [setup](experiments/family125-pam-scale/PUBLICATION.md) | Across 576 runs, auto OneBatchPAM first achieved at least 10% savings in both algorithm time and peak memory at tested **N = 3,000**. At N = 10,000 and k = 20, it was **36.69× faster for distance construction plus fitting** (4.75× for the complete process), with peak memory **147.9 versus 486.9 MiB**. Median full-client cost differences from FasterPAM were **+0.28%** on balanced data, **+183.61%** on rare-triplet data, and **+93.52%** on rare-singleton data. | Sampling saved resources but often missed rare remote clients. Larger batches improved coverage; a full batch restored coverage while retaining full-matrix memory. This compares packaged heuristics, not the full family 125 algorithm or a certified optimum. |
| **6. [Family 178: P2P topology and broadcast](experiments/family178-p2p-topology/RESEARCH_REPORT.md)** · [setup](experiments/family178-p2p-topology/PUBLICATION.md) | In 480 simulated scenarios, random regular graphs strongly outperformed rings. With 2,048 nodes, degree 4, heterogeneous latency, and no failures, time to 95% delivery fell from **33.248 to 0.589 seconds**. Spectral selection added no consistent gain; LPS median paired changes ranged from **-2.0% to +1.7%**. | The benefit was ordinary global connectivity in this flooding model. The full deterministic family 178 construction was not implemented or benchmarked. Better pre-failure spectra did not guarantee near-complete delivery after failures, and this was not a live P2P deployment. |
| **7. [Family 325: matrix-exponential actions](experiments/family325-matrix-exponential/RESEARCH_REPORT.md)** · [setup](experiments/family325-matrix-exponential/PUBLICATION.md) | In the restricted disk/Taylor prototype, replacing the older constant `1 + sqrt(2)` with 2 tightened the fixed-polynomial truncation bound by **17.16%**. However, degree fell by one in only **4 of 45 matched pairs**, reducing total per-vector sparse matrix-vector products on nonnormal cases from **2,210 to 2,206 (0.18%)**. | The new constant produced little measured work reduction in this construction. Reusing preparation sometimes helped repeated inputs, largely with the older constant too. Rational checks certify the enclosure and truncation bound conditional on the pinned theorem; they do not certify complete float64 error or independently prove the theorem. |

### Reading and reproducing the results

- **Classification metrics:** AP means average precision, not accuracy. Graph-study intervals are conditional on the fixed splits and fitted models; the context report also accounts for shared test context. These are not estimates of performance on every future dataset.
- **Storage and resources:** Storage totals include payload, index, and metadata. Reports distinguish packing, reading, feature extraction, algorithm time, complete process time, and measured memory. Timing comparisons belong to their own experiment; the two PAM studies use different measurement paths.
- **Mathematical scope:** The reports distinguish paper-derived implementations, restricted certificates, and heuristics. Bounded tests and empirical improvements do not establish all claims of the underlying manuscripts. Source commits, hashes, assumptions, negative controls, and unsuccessful cases are recorded in the individual packages.
- **Reproduction:** Start with the relevant **setup** guide above, then follow that package's commands, dependency versions, and data requirements. The packages include code, plans, selected measurements, test logs, and publication manifests. Raw Elliptic2 data and some large artifacts are excluded; the guides list omissions and explain which historical audits refer to the complete local archive. Dataset and third-party source licenses remain separate from the repository code license.

### Citation and verification

Use [CITATION.cff](CITATION.cff) for this fork's experiment collection and [fixed report citations](CITATION.md) for individual findings. Original upstream manuscripts require separate citations. No independent peer review is documented for the experiments; English publication materials were prepared with AI assistance.

[Publication integrity checks](https://github.com/Lermont/math/actions/workflows/research-publication.yml) verify included file hashes and documentation links. Their status does not certify the mathematical theorems or independently reproduce the benchmarks.

---

## Upstream collection

The original upstream description is retained below. Its statements about model-generated manuscripts, formalization coverage, and authorship refer to the upstream collection.

This repository contains mathematical manuscripts and supporting proof artifacts produced by an internal OpenAI model. 

As part of model development, we evaluate our models on open research problems. We expanded these evaluations after performance on our existing mathematical evaluations saturated. Some outputs build upon earlier results produced by the models.

This collection includes results at different stages of verification. Not all have accompanying Lean formalizations. We will continue to update this repository with Lean formalizations as we obtain them. 

Some of the unformalized results could have issues. We will endeavor to fix any such issues quickly.
We are also exploring community-hosted repositories for these materials. 

## Navigating the collection

The current catalogue contains 719 manuscripts organized into 372 families. A family groups related papers, which may include a principal result, companion arguments, consequences, or alternative proofs. Each family is classified by mathematical discipline.

- Start with the [overview](overview.pdf) for descriptions of the families.
- Use the [manuscript map](CONTENTS.md) to find individual papers and their supporting materials.
- The [`preprints/`](preprints/) directory contains PDFs, source files, and manuscript-specific citation and build instructions.
- The [Lean library](lean/README.md) and [formalization catalogue](lean/formalization.yaml) describe the available formal proofs, their associated papers, and verification configurations. See the [Comparator instructions](lean/ComparatorChallenges/README.md) for additional checking instructions. The repository has ~42% top-line results formalized.
- Updates to the repo are described in the [history](history.md).

### Reasoning summaries

We are also releasing abridged summaries of the model's reasoning, covering the following results:

| Family | Subject |
|---|---|
| 007 | [Ordinary two-point correlations of multiplicative functions](reasoning_traces/ordinary-two-point-correlations.pdf) |
| 017 | [The irrationality exponent of π](reasoning_traces/irrationality-exponent-of-pi.pdf) |
| 087 | [Symmetric and general Mahler conjectures](reasoning_traces/symmetric-and-general-mahler-conjectures.pdf) |
| 102 | [Ordinary NP-hardness at the basic semidefinite threshold](reasoning_traces/basic-semidefinite-threshold-np-hardness.pdf) |
| 159 | [Quasipolynomial bounds for arithmetic progressions](reasoning_traces/quasipolynomial-arithmetic-progressions.pdf) |
| 197 | [Kaplansky's direct-finiteness conjecture in characteristic two](reasoning_traces/kaplansky-direct-finiteness-characteristic-two.pdf) |
| 221 | [The Mézard–Parisi formula for diluted spin glasses](reasoning_traces/mezard-parisi-formula.pdf) |
| 271 | [Spontaneous magnetization in the quantum Heisenberg ferromagnet](reasoning_traces/spontaneous-magnetization-quantum-heisenberg-ferromagnet.pdf) |
| 287 | [Isomorphism of free group factors](reasoning_traces/free-group-factor-isomorphism.pdf) |
| 362 | [The three-dimensional relativistic Vlasov–Maxwell system](reasoning_traces/relativistic-vlasov-maxwell.pdf) |


## How the results were produced

The vast majority of results were obtained with the same procedure using an unreleased internal OpenAI model. On average, each result used three hours of ChatGPT Pro thinking compute with that model. Over the course of the evaluation, the model was posed approximately 4,000 problems. Aggregating the output into result families and manuscripts and requiring an appropriate level of significance led to the catalog outlined above.

Exceptions to this fixed procedure include work on a zero-free region for the Riemann zeta function and proof of the Hodge Conjecture for CM abelian varieties. Additionally, the writeup for the Re(s) > 11/12 zero-free region for the Riemann zeta function was human edited for readability. 


## Versions and citations

We will preserve the public release history of this collection. Corrections and revisions will be recorded as new versions, with previously released versions remaining accessible. 

To cite the individual manuscript, use the BibTeX block in its directory. 
