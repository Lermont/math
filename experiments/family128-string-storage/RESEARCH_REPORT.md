# Evaluate family 128 shortest-superstring storage against indexed and compressed baselines

## Publication contents

This PR adds an independent experiment under `experiments/family128-string-storage/`. Run the commands below from that directory. The English research report is [RESEARCH_REPORT.md](RESEARCH_REPORT.md); the [publication guide](PUBLICATION.md) records setup, included evidence, and artifact exclusions.

The code and original plans are preserved byte for byte. Recorded audits describe the original complete local archive; they are not claims that omitted artifacts can be audited from this checkout. No new timed benchmark was run to prepare this publication. The hypothesis IDs below are editorial labels for the questions investigated, not a claim that every question was preregistered.

## Summary

Add a byte-preserving storage prototype based on the family 128 shortest-common-superstring construction, together with an exact small-instance oracle and a reproducible six-method benchmark.

The measured benefit is specific: overlapping fragments can share a compact payload while retaining inexpensive reads by original ID. The implementation does not provide a general compression or packing-speed advantage. Index overhead, construction cost, and explicit resource limits materially change the practical result.

## Hypotheses and outcomes

| ID | Hypothesis | Outcome in this experiment |
|---|---|---|
| S1 | A common superstring can preserve arbitrary bytes, IDs, input order, duplicates, and empty strings. | Supported by round-trip, individual-read, and CLI tests; all 64 saved successful archives passed the original artifact audit. |
| S2 | The port satisfies the paper's superstring-length inequalities on small instances. | Supported on the enumerated and randomized checks described below. This is bounded implementation evidence, not a proof of the complete port. |
| S3 | Sharing overlaps improves total storage while retaining direct reads. | Supported for the two overlapping-fragment cases relative to plain, deduplicated, prefix, and block-Zstd storage. Whole-dataset Zstd remains smaller. |
| S4 | The method is a broadly better replacement for existing string storage. | Not supported: several datasets expand relative to plain storage, packing is expensive, and both larger construction cases hit resource limits. |

## Implementation and scope

- `stringpack/paper128.py`: forced occurrence counts, hierarchical graph, periodic layers, connection operations, group processing, cycle opening, and Euler traversal, following Sections 2–7 of the pinned paper. All periods and base edges are retained. An exact solver is used only in tests.
- `stringpack/storage.py` and the CLI: self-contained archives and reads by original ID. The superstring method stores one `(offset, length)` pair per original record.
- `stringpack/datasets.py`, `benchmark.py`, and `report.py`: fixed datasets, shared access traces, serialized-size accounting, and separate packing/opening/random-read/full-read measurements.
- `tests/test_paper128.py`, `tests/test_storage.py`, `tests/test_cli.py`, and `scripts/validate_port.py`: oracle comparisons, regressions, round trips, and stress validation.
- `results/main/`, `results/validation.json`, and `references/sources.json`: recorded measurements, validation evidence, and source provenance. `results/pilot/` is a preliminary run, not an additional independent confirmation.

## Experimental design

The main run contains **11 datasets × 6 methods = 66 attempts**: 64 successful archives and two explicit `resource_limit` outcomes, both for `paper128`. Ten datasets are synthetic; the remaining dataset contains the 297 public names in the recorded Python standard-library module catalog. The dataset seed is `1282026`; exact inputs and SHA-256 hashes are retained.

Baselines are plain concatenation, exact deduplication, prefix coding with 16-record restart blocks, Zstd level 3 with 32-record blocks, and one whole-dataset Zstd frame. Total size includes the 20-byte header, payload, complete index, block offsets, and any original-ID mapping. No external dictionary is omitted from accounting.

Each method passes a complete round trip and individual reads before timing. Packing uses three repeats after warmup; opening and reading use five. Every method receives the same 4,096-ID uniform-with-replacement trace. Archives are already in RAM, decoded blocks are not cached, and reads return materialized `bytes`. Full reads decode each block once and restore original order.

## Results

Representative measurements from [the full CSV](results/main/results.csv):

| Dataset / method | Total archive, bytes | Pack, ms | Open, µs | Random read, µs/ID | Full read, ms |
|---|---:|---:|---:|---:|---:|
| 128 overlapping binary fragments / plain | 8,728 | 0.014 | 6.373 | 0.197 | 0.024 |
| Same / family 128 | 1,265 | 119.638 | 10.547 | 0.271 | 0.032 |
| Same / block Zstd | 2,010 | 0.061 | 1.577 | 4.007 | 0.040 |
| Same / whole Zstd | 1,167 | 0.033 | 1.440 | 6.507 | 0.022 |
| 96 overlapping text fragments / family 128 | 1,072 | 211.125 | 8.468 | 0.259 | 0.024 |
| Same / block Zstd | 1,510 | 0.041 | 1.603 | 4.004 | 0.027 |
| Same / whole Zstd | 973 | 0.029 | 1.992 | 7.447 | 0.023 |

The binary-fragment superstring payload is 221 bytes, but its per-record index contributes another 1,024 bytes. Reporting only the payload would substantially overstate the storage benefit.

The negative and boundary cases are retained:

| Dataset | Family 128 outcome | Relevant comparison |
|---|---|---|
| 128 URL strings | 3,841 bytes; 359.263 ms packing | Plain: 3,320 bytes; prefix: 1,170; whole Zstd: 891. |
| 297 module names | 3,949 bytes | Plain: 3,469; whole Zstd: 2,104. |
| 128 random identifiers | 2,949 bytes; 1,863.604 ms packing | Plain: 2,584; whole Zstd: 1,551. |
| 64 UTF-8 labels | 2,520 bytes; 9,330.002 ms packing | Plain: 2,264; whole Zstd: 503. |
| 64 periodic strings | 674 bytes | Plain: 3,771; whole Zstd: 474. |
| 128 records with duplicates | 1,686 bytes | Deduplication alone: 1,684; whole Zstd: 656. |
| 1,024 overlapping binary fragments | `resource_limit` | More than 20,000 substring vertices. |
| 16,384 URL strings | `resource_limit` | Exceeded the cooperative 20-second construction budget. |

The resource cap is reported as a failure to complete the construction; there is no fallback heuristic presented as the paper's output.

## Correctness evidence and limits

The exact subset-DP oracle checks **all 1,471 subsets of size at most four** drawn from nonempty binary words of length at most three. This is not enumeration of every subset of those words. A further 250 randomized instances and targeted edge/regression cases check

`W <= exact OPT <= output length <= 2 * exact OPT`.

The saved 2,000-case stress run exercises `easy_root` and `collective`, but does not cover every request/cycle branch. Executable invariants also check counts, added-edge budgets, balance, edge traversal, and input containment. The Python port is not formally verified, and Lean was not compiled. The paper's approximation statement concerns superstring length; it does not bound complete archive size or imply a speed advantage over Zstd.

The format uses 32-bit offsets and is limited to archives below 4 GiB. Disk I/O, peak memory, operating-system cache behavior, and service latency were not measured. Python implementations and native Zstd have different implementation costs; no CPU affinity or fixed clock was imposed.

## Validation and reproduction

The original [artifact audit](results/main/verification.json) verifies 11 dataset hashes, shared trace hashes, 64 archive sizes/hashes and round trips, and 10 pinned source files. During PR drafting, all nine storage/CLI/paper tests passed again as part of the 20-test root suite; see [the fresh test log](results/pr-drafts-20261012/root-tests.txt). The 2,000-case stress run and timed benchmark were not rerun during drafting.

From the project root, using Python 3.14+ with `compression.zstd`:

```powershell
python -m unittest tests.test_paper128 tests.test_storage tests.test_cli -v
python scripts/validate_port.py --cases 2000 --output results/validation-pr-reproduction.json
python -m stringpack.benchmark --output results/stringpack-pr-reproduction
python -m stringpack.report results/stringpack-pr-reproduction/results.json
python scripts/verify_results.py results/stringpack-pr-reproduction/results.json
```

Use unused output paths to preserve the measured run. The recorded runtime is Python 3.14.7; settings and environment details are in [results.json](results/main/results.json).

## Sources and interpretation

The source is [A Polynomial-Time 2-Approximation for Shortest Common Superstring](https://github.com/openai/math/tree/fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb/preprints/A-Polynomial-Time-2-Approximation-for-Shortest-Common-Superstring-September-24-2026), pinned to `fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb`. Stored-source hashes and the newline-normalization note are in [the manifest](references/sources.json).

These results support a limited overlap-sharing use case with inexpensive direct access. They do not establish a general-purpose compressor or invalidate the paper's mathematical result. The full [benchmark report](results/main/report.md) retains every method and dataset.
