"""Verify immutable raw runs and produce CSV/Markdown tables, without rerunning methods."""
from __future__ import annotations
from collections import defaultdict
from pathlib import Path
import argparse
import csv
import json
import statistics as stat
from time import perf_counter
import numpy as np
from kmedian125.data import ROOT, digest, independent_cost, write_json
from kmedian125.methods import verify_certificate
from kmedian125.certify import strengthen_certificate, verify_strengthened

LABELS = {"greedy_swap": "Greedy+swap", "fasterpam": "FasterPAM", "onebatch_auto": "OneBatch auto",
          "onebatch64": "OneBatch 64", "lp_dr16_swap": "LP-DR16-swap"}

def csv_write(path, rows):
    if not rows:
        return
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    run = ROOT/"results/kmedian125"/args.run_id
    audit_started = perf_counter()
    rows = [json.loads(line) for line in (run/"raw.jsonl").read_text(encoding="utf-8").splitlines()]
    completion = json.loads((run/"completion.json").read_text())
    assert completion["completed"] == len(rows)
    manifests = json.loads((run/"datasets.json").read_text())
    datasets = {}
    bounds = {}
    qa = dict(independent_cost_checks=0, exact_dual_checks=0, shared_pairs_checked=0,
              exact_small_crosschecks=0, data_hashes_verified=0, strengthened_dual_checks=0,
              strengthened_certificate_seconds=0, failures=[])
    for manifest in manifests:
        path = run/"datasets"/(manifest["name"]+".json")
        assert digest(path) == manifest["json_sha256"]
        assert digest(path.with_suffix(".npy")) == manifest["matrix_sha256"]
        qa["data_hashes_verified"] += 2
        ds = json.loads(path.read_text(encoding="utf-8"))
        d = np.load(path.with_suffix(".npy"))
        datasets[ds["name"]] = ds, d
        relevant = [r for r in rows if r["dataset"] == ds["name"] and r["status"] == "ok"]
        optima = [r["info"]["proven_optimum"] for r in relevant if r["method"] == "enumeration"]
        certificates = [r["info"]["certificate"] for r in relevant if "certificate" in r.get("info", {})]
        lbs = []
        strengthened = []
        for cert in certificates:
            lbs.append(verify_certificate(d, cert, ds["k"]))
            qa["exact_dual_checks"] += 1
            strong = strengthen_certificate(d, cert, ds["k"])
            strong_lb = verify_strengthened(d, strong, ds["k"])
            lbs.append(strong_lb)
            strengthened.append(strong)
            qa["strengthened_dual_checks"] += 1
            qa["strengthened_certificate_seconds"] += strong["audit_seconds"]
        if optima:
            assert len(set(optima)) == 1
            lb = optima[0]
            for r in relevant:
                if r["method"] == "milp":
                    assert r["info"]["status"] == 0 and r["cost"] == lb and r["info"]["mip_gap"] == 0
                    qa["exact_small_crosschecks"] += 1
        else:
            lb = max(lbs) if lbs else (ds["n"]-ds["k"]) * int(d[~np.eye(ds["n"], dtype=bool)].min())
        best = min(r["cost"] for r in relevant)
        assert lb <= best and all(v <= best for v in lbs)
        bounds[ds["name"]] = dict(lower_bound=lb, proven_optimum=lb if optima or lb == best else None,
                                  best_feasible=best, proof="enumeration" if optima else "exact integer dual" if lbs else "minimum-distance trivial bound")
        if strengthened:
            bounds[ds["name"]]["certificate"] = max(strengthened, key=lambda c: c["integer_lower_bound"])
    for r in rows:
        if r["status"] != "ok":
            qa["failures"].append({k: r.get(k) for k in ("dataset", "method", "seed", "mode", "status", "error")})
            continue
        ds, _ = datasets[r["dataset"]]
        assert independent_cost(ds, r["medoids"]) == r["cost"]
        assert len(r["medoids"]) == ds["k"] and r["center_count"] == ds["k"]
        qa["independent_cost_checks"] += 1
        if r["mode"] == "shared":
            fresh = [s for s in rows if all(s.get(k) == r.get(k) for k in ("dataset", "method", "seed")) and s["mode"] == "fresh"]
            assert len(fresh) == 1 and fresh[0]["cost"] == r["cost"] and fresh[0]["medoids"] == r["medoids"]
            qa["shared_pairs_checked"] += 1
    qa["postrun_verification_seconds"] = perf_counter()-audit_started
    write_json(run/"bounds.json", bounds)
    write_json(run/"verification.json", qa)
    groups = defaultdict(list)
    for r in rows:
        if r["method"] in LABELS and r["status"] == "ok":
            groups[r["dataset"], r["mode"], r["method"]].append(r)
    summary = []
    for (name, mode, method), group in groups.items():
        c = [r["cost"] for r in group]
        times = [r["algorithm_seconds"] for r in group]
        bound = bounds[name]
        summary.append(dict(dataset=name, n=group[0]["n"], k=group[0]["k"], mode=mode, method=method,
                            seeds=len(group), cost_min=min(c), cost_median=stat.median(c), cost_max=max(c),
                            lower_bound=bound["lower_bound"], proven_optimum=bound["proven_optimum"],
                            median_gap_to_bound_pct=100*(stat.median(c)/bound["lower_bound"]-1),
                            seconds_min=min(times), seconds_median=stat.median(times), seconds_max=max(times),
                            best_of_all_seeds_total_seconds=sum(times),
                            peak_mib_median=stat.median(r["peak_working_set_bytes"]/(1024**2) for r in group),
                            process_seconds_median=stat.median(r["process_wall_seconds"] for r in group),
                            verified_seconds_median=stat.median(r["verified_seconds"] for r in group)))
    csv_write(run/"summary.csv", summary)
    flat = []
    for r in rows:
        if r["status"] == "ok":
            rec = {k: r[k] for k in ("dataset", "method", "seed", "mode", "n", "k", "cost", "center_count", "algorithm_seconds", "verified_seconds", "process_wall_seconds", "peak_working_set_bytes", "distance_payload_bytes")}
            for stage in ("distance", "model", "lp", "certificate", "rounding", "greedy", "local_search", "fit", "enumeration", "milp_model_and_solve", "verification"):
                rec[stage+"_seconds"] = r["stages"].get(stage, 0)
            flat.append(rec)
    csv_write(run/"measurements.csv", flat)
    overall = []
    for scale in ("small", "medium"):
        for mode in ("fresh", "shared"):
            for method in LABELS:
                cases = [s for s in summary if (s["n"] == 18) == (scale == "small") and s["mode"] == mode and s["method"] == method]
                if not cases:
                    continue
                raw = [r for r in rows if (r["n"] == 18) == (scale == "small") and r["mode"] == mode and r["method"] == method and r["status"] == "ok"]
                overall.append(dict(scale=scale, mode=mode, method=method, cases=len(cases), runs=len(raw),
                                    macro_median_gap_pct=stat.mean(s["median_gap_to_bound_pct"] for s in cases),
                                    worst_gap_pct=max(100*(r["cost"]/bounds[r["dataset"]]["lower_bound"]-1) for r in raw),
                                    seconds_median=stat.median(r["algorithm_seconds"] for r in raw),
                                    peak_mib_median=stat.median(r["peak_working_set_bytes"]/(1024**2) for r in raw),
                                    peak_mib_max=max(r["peak_working_set_bytes"]/(1024**2) for r in raw),
                                    process_seconds_median=stat.median(r["process_wall_seconds"] for r in raw),
                                    verified_seconds_median=stat.median(r["verified_seconds"] for r in raw)))
    write_json(run/"aggregate.json", overall)
    lines = ["# Таблицы измерений", "", "Свежие данные: время после импорта/загрузки, с построением нужных расстояний; QA указан отдельно в CSV.", ""]
    for scale, title in [("small", "Малые, n=18, k=3"), ("medium", "Средние и реальные, n=210–240, k=10–24")]:
        lines += ["## "+title, "", "| Метод | Средний разрыв медиан до LB, % | Худший разрыв, % | Медиана, мс | Peak RSS медиана, MiB | Макс. peak, MiB |", "|---|---:|---:|---:|---:|---:|"]
        for s in overall:
            if s["scale"] == scale and s["mode"] == "fresh":
                lines.append(f"| {LABELS[s['method']]} | {s['macro_median_gap_pct']:.3f} | {s['worst_gap_pct']:.3f} | {1000*s['seconds_median']:.3f} | {s['peak_mib_median']:.1f} | {s['peak_mib_max']:.1f} |")
        lines += [""]
    lines += ["## Стоимости по задачам: min / median / max по seeds, fresh", "", "| Набор | LB / OPT | Greedy+swap | FasterPAM | OneBatch auto | OneBatch 64 | LP-DR16-swap |", "|---|---:|---:|---:|---:|---:|---:|"]
    for name, (ds, _) in datasets.items():
        b = bounds[name]
        cells = []
        for method in LABELS:
            candidates = [s for s in summary if s["dataset"] == name and s["mode"] == "fresh" and s["method"] == method]
            if candidates:
                s = candidates[0]
                cells.append(f"{s['cost_min']:g} / {s['cost_median']:g} / {s['cost_max']:g}")
            else:
                cells.append("нет результата")
        lines.append("| "+name+f" | {b['lower_bound']}"+(" OPT" if b["proven_optimum"] is not None else " LB")+" | "+" | ".join(cells)+" |")
    lines += ["", "## Повторное использование готовой матрицы: средние задачи", "", "| Метод | Медиана fresh, мс | Медиана shared, мс | Медиана процесса fresh, с |", "|---|---:|---:|---:|"]
    for method in LABELS:
        fresh = next(s for s in overall if s["scale"] == "medium" and s["mode"] == "fresh" and s["method"] == method)
        shared = next(s for s in overall if s["scale"] == "medium" and s["mode"] == "shared" and s["method"] == method)
        lines.append(f"| {LABELS[method]} | {fresh['seconds_median']*1000:.3f} | {shared['seconds_median']*1000:.3f} | {fresh['process_seconds_median']:.3f} |")
    (run/"TABLES.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
    print(json.dumps(dict(completion=completion, verification=qa, aggregate=overall), indent=2))

if __name__ == "__main__":
    main()
