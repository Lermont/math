"""Verify every stored assignment and summarize the frozen scale schedule."""
from __future__ import annotations
import argparse
import csv
import importlib.metadata
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median
import zipfile
import numpy as np
from .core import ROOT, digest, write_json, batch_for, miss_probability

MIB = 1024**2
METHODS = ["fasterpam", "onebatch64", "onebatch256", "onebatch_auto", "onebatch_2auto", "onebatch_full"]


def csv_write(path, rows):
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def independently_verify(run, records, env):
    """Third implementation: integer vector per medoid, no NxK distance array."""
    for name, expected in env["source_sha256"].items():
        assert digest(run/"source-snapshot"/name) == expected
        assert digest(Path(__file__).parent/name) == expected, name
    assert digest(run/"schedule.json") == env["schedule_sha256"]
    refs = ROOT/"references/kmedian125"
    assert digest(refs/"sources.json") == env["sources_manifest_sha256"]
    manifest = json.loads((refs/"sources.json").read_text(encoding="utf-8"))
    for entry in manifest["files"]:
        assert digest(ROOT/entry["path"]) == entry["sha256"]
    original = ROOT/"results/kmedian125/pilot-20261011-v1"
    assert digest(original/"raw.jsonl") == env["original_pilot_raw_sha256"]
    oldenv = json.loads((original/"environment.json").read_text(encoding="utf-8"))
    for name, expected in oldenv["source_sha256"].items():
        assert digest(ROOT/"kmedian125"/name) == expected
        assert digest(original/"source-snapshot"/name) == expected
    site = Path(importlib.metadata.distribution("onebatch").locate_file(""))
    for name, expected in env["installed_package_sha256"].items():
        assert digest(site/name) == expected, name
    wheel_members = 0
    for wheel in (refs/"wheels").glob("*.whl"):
        prefix = "onebatch/" if wheel.name.startswith("onebatch-") else "kmedoids/"
        with zipfile.ZipFile(wheel) as z:
            for name in z.namelist():
                if name.startswith(prefix) and name.endswith((".py", ".pyd", ".pyx")):
                    assert (site/name).read_bytes() == z.read(name)
                    wheel_members += 1
    datasets = {}
    for ds in json.loads((run/"datasets.json").read_text(encoding="utf-8")):
        name = ds["name"]
        paths = {"features":run/"datasets"/(name+".npy"), "groups":run/"datasets"/(name+"-groups.npy"),
                 "json":run/"datasets"/(name+".json")}
        for part, path in paths.items():
            assert digest(path) == ds[part+"_sha256"]
        datasets[name] = (np.load(paths["features"]).astype(np.int64), np.load(paths["groups"]))
    checked_clients = 0
    for r in records:
        if r["status"] != "ok":
            continue
        x, groups = datasets[r["dataset"]]
        meds = r["medoids"]
        assert len(set(meds)) == r["k"] and min(meds) >= 0 and max(meds) < len(x)
        nearest = np.full(len(x), np.iinfo(np.int64).max, dtype=np.int64)
        assigned = np.empty(len(x), dtype=np.int64)
        for m in meds:
            candidate = sum(np.abs(x[:, axis] - x[m, axis]) for axis in range(x.shape[1]))
            better = candidate < nearest
            assigned[better] = m
            nearest[better] = candidate[better]
        path = run/"raw"/(r["id"]+".npz")
        assert digest(path) == r["assignment_sha256"]
        with np.load(path) as saved:
            np.testing.assert_array_equal(saved["nearest"], nearest)
            np.testing.assert_array_equal(saved["assigned_medoid"], assigned)
        q = r["quality"]
        rare = nearest[groups >= 0]
        assert int(nearest.sum()) == q["cost"] == q["bulk_cost"]+q["rare_cost"]
        assert int(rare.sum()) == q["rare_cost"]
        assert rare.tolist() == q["rare_distances"]
        covered = sorted(set(map(int, groups[meds])) - {-1})
        assert covered == q["covered_group_ids"]
        assert len(covered) == q["rare_groups_covered"]
        assert len(rare) == q["rare_count"]
        assert np.count_nonzero(rare <= 20) == q["rare_served_within_20"]
        expected_batch = batch_for(r["method"], r["n"], r["k"])
        assert r["batch_size"] == expected_batch
        assert r["matrix_payload_bytes"] == 4*r["n"]*expected_batch
        if r["method"] != "fasterpam":
            rng = np.random.default_rng(r["seed"])
            cols = rng.choice(len(x), expected_batch, replace=False)
            assert cols.tolist() == r["info"]["sampled_indices"]
            assert sorted(set(map(int, groups[cols])) - {-1}) == r["info"]["sampled_rare_groups"]
        for key in ("algorithm_seconds", "algorithm_and_assignment_seconds", "process_wall_seconds"):
            assert math.isfinite(r[key]) and r[key] > 0
        assert r["cpu_affinity"] == [env["logical_cpu"]]
        assert all(p["num_threads"] == 1 for p in r["threadpools"])
        checked_clients += len(x)
    return dict(all_checks_passed=True, checked_runs=sum(r["status"] == "ok" for r in records),
                checked_client_assignments=checked_clients, datasets=len(datasets),
                frozen_inputs_unchanged=True, original_pilot_unchanged=True,
                reference_files_verified=len(manifest["files"]), wheel_members_verified=wheel_members,
                full_objective="independent per-medoid integer evaluation for every run",
                analysis_sha256=digest(__file__))


def budget_edge(record, maximum):
    # onebatch.pam.swap_eager returns the zero-based loop variable s.
    threshold = maximum if record["method"] == "fasterpam" else maximum - 1
    return record["info"]["n_iter"] >= threshold


def measurements(records, cfg):
    references = defaultdict(list)
    best_observed = {}
    for r in records:
        if r["status"] != "ok":
            continue
        key = (r["dataset"], r["k"])
        cost = r["quality"]["cost"]
        best_observed[key] = min(cost, best_observed.get(key, cost))
        if r["method"] == "fasterpam":
            references[key].append(cost)
    rows = []
    for r in records:
        if r["status"] != "ok":
            continue
        key = (r["dataset"], r["k"])
        assert len(references[key]) == 3
        ref = median(references[key])
        q, info, stages = r["quality"], r["info"], r["stages"]
        rows.append(dict(id=r["id"], grid=r["grid"], dataset=r["dataset"], structure=r["structure"],
            data_seed=r["data_seed"], seed=r["seed"], n=r["n"], k=r["k"], method=r["method"], batch=r["batch_size"],
            cost=q["cost"], reference_fasterpam_median=ref,
            delta_cost_pct=100*(q["cost"]/ref-1),
            best_observed=best_observed[key], delta_best_observed_pct=100*(q["cost"]/best_observed[key]-1),
            bulk_cost=q["bulk_cost"], rare_cost=q["rare_cost"],
            rare_groups_covered=q["rare_groups_covered"], rare_groups_total=q["rare_groups_total"],
            rare_coverage_pct=100*q["rare_groups_covered"]/q["rare_groups_total"] if q["rare_groups_total"] else None,
            sampled_rare_groups=len(info["sampled_rare_groups"]) if r["method"] != "fasterpam" else q["rare_groups_total"],
            unsampled_rare_groups_covered=len(set(q["covered_group_ids"])-set(info["sampled_rare_groups"])) if r["method"] != "fasterpam" else 0,
            sampled_rare_groups_without_center=len(set(info["sampled_rare_groups"])-set(q["covered_group_ids"])) if r["method"] != "fasterpam" else 0,
            rare_mean_distance=q["rare_mean_distance"], rare_p95_distance=q["rare_p95_distance"],
            rare_max_distance=q["rare_max_distance"], rare_served_within_20=q["rare_served_within_20"],
            algorithm_ms=1000*r["algorithm_seconds"], distance_ms=1000*stages["distance_seconds"],
            fit_ms=1000*stages["fit_seconds"], assignment_ms=1000*stages["full_assignment_seconds"],
            algorithm_and_assignment_ms=1000*r["algorithm_and_assignment_seconds"],
            process_wall_ms=1000*r["process_wall_seconds"], import_ms=1000*r["import_seconds"],
            load_ms=1000*r["load_seconds"], peak_fit_mib=r["algorithm_peak_working_set_bytes"]/MIB,
            peak_total_mib=r["whole_process_peak_working_set_bytes"]/MIB,
            baseline_mib=r["baseline_rss_bytes"]/MIB,
            peak_above_baseline_mib=(r["algorithm_peak_working_set_bytes"]-r["baseline_rss_bytes"])/MIB,
            matrix_mib=r["matrix_payload_bytes"]/MIB,
            system_available_before_mib=r["system_available_before"]/MIB,
            cpu_seconds=r["algorithm_cpu_seconds"], n_iter=info["n_iter"],
            iteration_limit_reached=budget_edge(r, cfg["max_iter"])))
    return rows


def aggregate(rows):
    grouped = defaultdict(list)
    for r in rows:
        grouped[(r["n"], r["k"], r["structure"], r["method"])].append(r)
        grouped[(r["n"], r["k"], "all", r["method"])].append(r)
    output = []
    metrics = ["algorithm_ms", "distance_ms", "fit_ms", "assignment_ms", "algorithm_and_assignment_ms",
               "process_wall_ms", "peak_fit_mib", "peak_total_mib", "peak_above_baseline_mib",
               "delta_cost_pct", "rare_groups_covered", "rare_coverage_pct", "rare_mean_distance", "rare_p95_distance"]
    for (n, k, structure, method), members in sorted(grouped.items()):
        row = dict(n=n, k=k, structure=structure, method=method, runs=len(members),
                   batch=members[0]["batch"], matrix_mib=members[0]["matrix_mib"])
        for metric in metrics:
            values = [r[metric] for r in members if r[metric] is not None]
            for suffix, fn in (("median", median), ("min", min), ("max", max),
                               ("mean", lambda x: sum(x)/len(x))):
                row[metric+"_"+suffix] = fn(values) if values else None
        row["rare_groups_covered_sum"] = sum(r["rare_groups_covered"] for r in members)
        row["rare_groups_total_sum"] = sum(r["rare_groups_total"] for r in members)
        row["sampled_rare_groups_sum"] = sum(r["sampled_rare_groups"] for r in members)
        row["iteration_limit_runs"] = sum(r["iteration_limit_reached"] for r in members)
        output.append(row)
    lookup = {(r["n"], r["k"], r["structure"], r["method"]):r for r in output}
    for r in output:
        f = lookup[(r["n"], r["k"], r["structure"], "fasterpam")]
        r["speedup_median"] = f["algorithm_ms_median"]/r["algorithm_ms_median"]
        r["memory_reduction_pct"] = 100*(1-r["peak_fit_mib_median"]/f["peak_fit_mib_median"])
        r["cold_speedup_median"] = f["process_wall_ms_median"]/r["process_wall_ms_median"]
    return output


def boundaries(agg, cfg):
    out = []
    for structure in ["all"] + cfg["structures"]:
        for method in cfg["methods"]:
            if method == "fasterpam":
                continue
            rows = sorted([r for r in agg if r["k"] == cfg["k"] and r["structure"] == structure
                           and r["method"] == method], key=lambda r:r["n"])
            row = dict(structure=structure, method=method)
            for name, predicate in (
                ("time", lambda r:r["speedup_median"] > 1),
                ("memory", lambda r:r["memory_reduction_pct"] > 0),
                ("both", lambda r:r["speedup_median"] > 1 and r["memory_reduction_pct"] > 0),
                ("both_10pct", lambda r:r["speedup_median"] >= 1/0.9 and r["memory_reduction_pct"] >= 10)):
                row[name+"_first_n"] = next((r["n"] for r in rows if predicate(r)), None)
                row[name+"_sustained_n"] = next((r["n"] for i, r in enumerate(rows)
                                                  if all(predicate(t) for t in rows[i:])), None)
            out.append(row)
    return out


def markdown_tables(run, agg, cuts, cfg):
    lines = ["# Полные таблицы масштаба", "", "Все времена — мс; память — MiB. Медианы по 6 запускам",
             "на основную ячейку (2 seed данных × 3 seed алгоритма); k=50 — по 3.",
             "ΔC сравнивает полную стоимость каждого запуска с медианой FasterPAM на том же наборе.",
             "Отрицательная ΔC допустима; это не разрыв до OPT. Диапазоны — наблюдения, не доверительные интервалы.", ""]
    for structure in cfg["structures"]:
        lines += ["## " + structure + ", k=20", "", "|N|Метод|B|Время med [min,max]|Cold med|Пик fit|Матрица|ΔC med [min,max], %|Удалённых групп покрыто / всего|",
                  "|---:|---|---:|---:|---:|---:|---:|---:|---:|"]
        subset = sorted([r for r in agg if r["structure"] == structure and r["k"] == 20],
                        key=lambda r:(r["n"], METHODS.index(r["method"])))
        for r in subset:
            lines.append(f"|{r['n']}|{r['method']}|{r['batch']}|{r['algorithm_ms_median']:.2f} "
                         f"[{r['algorithm_ms_min']:.2f}, {r['algorithm_ms_max']:.2f}]|{r['process_wall_ms_median']:.1f}|"
                         f"{r['peak_fit_mib_median']:.1f}|{r['matrix_mib']:.2f}|{r['delta_cost_pct_median']:.3f} "
                         f"[{r['delta_cost_pct_min']:.3f}, {r['delta_cost_pct_max']:.3f}]|"
                         f"{r['rare_groups_covered_sum']}/{r['rare_groups_total_sum']}|")
        lines += [""]
    lines += ["## Устойчивые границы на измеренной сетке", "", "|Сценарий|Метод|Время|Память|Оба|Оба на ≥10%|",
              "|---|---|---:|---:|---:|---:|"]
    for r in cuts:
        lines.append(f"|{r['structure']}|{r['method']}|{r['time_sustained_n']}|{r['memory_sustained_n']}|"
                     f"{r['both_sustained_n']}|{r['both_10pct_sustained_n']}|")
    (run/"TABLES.md").write_text("\n".join(lines)+"\n", encoding="utf-8")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run-id", required=True)
    args = p.parse_args()
    run = ROOT/"results/kmedian125"/args.run_id
    cfg = json.loads((run/"config.json").read_text(encoding="utf-8"))
    env = json.loads((run/"environment.json").read_text(encoding="utf-8"))
    tasks = json.loads((run/"schedule.json").read_text(encoding="utf-8"))
    done = json.loads((run/"completion.json").read_text(encoding="utf-8"))
    assert done["completed"] == done["scheduled"] == len(tasks), "Incomplete schedule"
    records = [json.loads((run/"raw"/(t["id"]+".json")).read_text(encoding="utf-8")) for t in tasks]
    assert [r["id"] for r in records] == [t["id"] for t in tasks]
    assert records == [json.loads(line) for line in (run/"raw.jsonl").read_text(encoding="utf-8").splitlines()]
    audit = independently_verify(run, records, env)
    audit["statuses"] = dict(Counter(r["status"] for r in records))
    audit["max_iteration_reached"] = sum(budget_edge(r, cfg["max_iter"]) for r in records if r["status"] == "ok")
    audit["iteration_counter_note"] = "OneBatch steps is zero-based; audit compares with max_iter-1, independently of the raw flag."
    audit["max_observed_counter_by_method"] = {
        method:max(r["info"]["n_iter"] for r in records if r["status"] == "ok" and r["method"] == method)
        for method in METHODS if any(r["status"] == "ok" and r["method"] == method for r in records)}
    rows = measurements(records, cfg)
    agg = aggregate(rows)
    cuts = boundaries(agg, cfg)
    sampling = [dict(n=n, k=20, method=method, batch=batch_for(method, n, 20), group_size=size,
                     group_miss_probability=miss_probability(n, batch_for(method, n, 20), size),
                     expected_groups_represented=8*(1-miss_probability(n, batch_for(method, n, 20), size)))
                for n in cfg["sizes"] for method in cfg["methods"][1:] for size in (1, 3)]
    csv_write(run/"measurements.csv", rows)
    csv_write(run/"aggregate.csv", agg)
    csv_write(run/"boundaries.csv", cuts)
    csv_write(run/"sampling.csv", sampling)
    write_json(run/"aggregate.json", agg)
    write_json(run/"boundaries.json", cuts)
    write_json(run/"verification.json", audit)
    markdown_tables(run, agg, cuts, cfg)
    (run/"analysis-source.py").write_bytes(Path(__file__).read_bytes())
    print(json.dumps(audit, ensure_ascii=False, indent=2))
    print("BOUNDARIES:", json.dumps([r for r in cuts if r["method"] == "onebatch_auto"], ensure_ascii=False))


if __name__ == "__main__":
    main()
