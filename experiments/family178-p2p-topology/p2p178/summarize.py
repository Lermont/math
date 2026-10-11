"""Export every message, seed-level summaries, paired ratios and a static plot."""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean, median

from .benchmark import write_json


def stats(values):
    valid = [value for value in values if value is not None]
    return {"median": median(valid) if valid else None, "min": min(valid) if valid else None,
            "max": max(valid) if valid else None, "count": len(valid), "missing": len(values) - len(valid)}


def csv_write(path, rows):
    if not rows:
        return
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with Path(path).open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def summarize(directory, plot=True):
    directory = Path(directory)
    raw = json.loads((directory / "raw.json").read_text("utf-8"))
    messages, seed_rows, build_rows = [], [], []
    for record in raw:
        if "build" not in record:
            continue
        build = record["build"]
        base = {key: record[key] for key in ["n", "d", "method", "seed"]}
        accepted = next((a for a in build["attempts"] if a["selected"]), None)
        build_rows.append({**base, **{k: build[k] for k in ["status", "attempt_count", "rejected_count", "total_build_seconds", "generation_seconds", "structure_seconds", "spectral_seconds"]},
                           "peak_build_mib": build["memory"]["peak_rss_bytes"] / 2**20,
                           "build_worker_wall_seconds": record["build_worker_wall_seconds"],
                           "graph_sha256": accepted["graph_sha256"] if accepted else None,
                           "lambda_abs": accepted["spectrum"]["lambda_abs"] if accepted else None,
                           "numeric_pass": accepted["spectrum"]["numeric_pass"] if accepted else None,
                           "total_simulation_seconds": record.get("simulate", {}).get("total_simulation_seconds"),
                           "peak_simulation_mib": record.get("simulate", {}).get("memory", {}).get("peak_rss_bytes", 0) / 2**20,
                           "simulate_worker_wall_seconds": record.get("simulate_worker_wall_seconds")})
        if "simulate" not in record:
            continue
        for scenario in record["simulate"]["scenarios"]:
            context = {**base, "latency_model": scenario["latency_model"], "failure_fraction": scenario["failure_fraction"]}
            rows = scenario["messages"]
            for row in rows:
                messages.append({**context, **row, "trace_sha256": scenario["trace_sha256"]})
            item = {**context, "message_count": len(rows), "simulation_seconds": scenario["simulation_seconds"]}
            for metric in ["unreachable_fraction", "transmissions", "wire_bytes", "duplicates", "failed_transmissions", "duplicate_fraction_of_received"]:
                item[metric] = mean(row[metric] for row in rows)
            for q in (50, 95, 99, 100):
                key = f"t{q}_ms"
                values = [row[key] for row in rows]
                item[key] = mean(values) if all(value is not None for value in values) else None
                item[f"t{q}_censored_messages"] = sum(value is None for value in values)
            seed_rows.append(item)
    csv_write(directory / "messages.csv", messages)
    csv_write(directory / "seed_summary.csv", seed_rows)
    csv_write(directory / "construction.csv", build_rows)
    groups = defaultdict(list)
    group_keys = ["n", "d", "method", "latency_model", "failure_fraction"]
    for row in seed_rows:
        groups[tuple(row[k] for k in group_keys)].append(row)
    metrics = ["t50_ms", "t95_ms", "t99_ms", "t100_ms", "unreachable_fraction", "transmissions", "wire_bytes", "duplicates", "failed_transmissions", "duplicate_fraction_of_received", "simulation_seconds"]
    scenario_summary = []
    for group, rows in sorted(groups.items()):
        item = dict(zip(group_keys, group))
        item["seeds"] = len(rows)
        item["messages"] = sum(r["message_count"] for r in rows)
        for metric in metrics:
            item[metric] = stats([r[metric] for r in rows])
        for q in (50, 95, 99, 100):
            item[f"t{q}_censored_messages"] = sum(r[f"t{q}_censored_messages"] for r in rows)
        scenario_summary.append(item)
    build_groups = defaultdict(list)
    for row in build_rows:
        build_groups[row["n"], row["d"], row["method"]].append(row)
    construction_summary = []
    for (n, d, method), rows in sorted(build_groups.items()):
        item = {"n": n, "d": d, "method": method, "seeds": len(rows),
                "attempts_total": sum(r["attempt_count"] for r in rows),
                "rejected_total": sum(r["rejected_count"] for r in rows),
                "numeric_pass_count": sum(r["numeric_pass"] is True for r in rows)}
        for metric in ["lambda_abs", "total_build_seconds", "generation_seconds", "spectral_seconds", "peak_build_mib", "total_simulation_seconds", "peak_simulation_mib", "build_worker_wall_seconds", "simulate_worker_wall_seconds"]:
            item[metric] = stats([r[metric] for r in rows])
        construction_summary.append(item)
    lookup = {(r["n"], r["d"], r["seed"], r["latency_model"], r["failure_fraction"], r["method"]): r for r in seed_rows}
    paired = []
    for (n, d, method, latency, failure), rows in sorted(groups.items()):
        if method == "random_regular":
            continue
        ratios = []
        pairs = []
        for row in rows:
            baseline = lookup[n, d, row["seed"], latency, failure, "random_regular"]
            ratio = row["t95_ms"] / baseline["t95_ms"] if row["t95_ms"] is not None and baseline["t95_ms"] is not None else None
            ratios.append(ratio)
            pairs.append({"seed": row["seed"], "t95_ratio": ratio,
                          "unreachable_fraction_delta": row["unreachable_fraction"] - baseline["unreachable_fraction"],
                          "bytes_ratio": row["wire_bytes"] / baseline["wire_bytes"]})
        paired.append({"n": n, "d": d, "method": method, "latency_model": latency, "failure_fraction": failure,
                       "t95_ratio": stats(ratios), "pairs": pairs})
    summary = {"aggregation": "mean of 8 messages per seed, then median/min/max of 5 seed means; null seed mean if any message censored",
               "messages": len(messages), "builds": len(build_rows), "scenarios": len(seed_rows),
               "construction": construction_summary, "scenarios_summary": scenario_summary, "paired": paired}
    write_json(directory / "summary.json", summary)
    csv_write(directory / "scenario_summary.csv", [{**{k: r[k] for k in group_keys},
              **{f"{metric}_{sub}": value for metric in metrics for sub, value in r[metric].items()},
              **{f"t{q}_censored_messages": r[f"t{q}_censored_messages"] for q in (50, 95, 99, 100)}} for r in scenario_summary])
    if plot:
        plot_ratios(directory, paired)
    print(json.dumps({"messages": len(messages), "builds": len(build_rows), "scenarios": len(seed_rows)}))


def plot_ratios(directory, pairs):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "svg.fonttype": "none"})
    fig, grid = plt.subplots(2, 2, figsize=(12, 8), sharey=True, layout="constrained")
    axes = grid.ravel()
    xcases = [(model, failure) for model in ["uniform", "heterogeneous"] for failure in [0, .1, .3]]
    for ax, (n, d) in zip(axes, [(512, 4), (2048, 4), (2048, 8), (2184, 6)]):
        for method, color, shift, label in [("spectral_rejection", "#196F9A", -.06, "Спектральный отбор"),
                                            ("lps", "#C56B25", .06, "LPS (5,13)")]:
            selected = [r for r in pairs if (r["n"], r["d"], r["method"]) == (n, d, method)]
            if not selected:
                continue
            for index, case in enumerate(xcases):
                r = next(r for r in selected if (r["latency_model"], r["failure_fraction"]) == case)["t95_ratio"]
                if r["median"] is not None:
                    ax.errorbar(index + shift, r["median"], yerr=[[r["median"] - r["min"]], [r["max"] - r["median"]]],
                                fmt="o", markersize=5, color=color, capsize=3, label=label if index == 0 else None)
        ax.axhline(1, color="#555555", lw=1)
        ax.axhline(.9, color="#888888", lw=.8, ls="--")
        ax.set_title(f"n={n}, d={d}")
        ax.set_xticks(range(6), ["U/0", "U/10", "U/30", "H/0", "H/10", "H/30"])
        ax.set_xlabel("Задержки / отключённые узлы, %")
        ax.grid(axis="y", alpha=.18)
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].set_ylabel("t95 / t95 случайного регулярного графа")
    axes[2].set_ylabel("t95 / t95 случайного регулярного графа")
    axes[3].legend(fontsize=9, loc="best")
    fig.suptitle("Медиана и min–max пяти парных повторов; ниже — быстрее", fontsize=13)
    fig.text(.5, -.03, "U — 10 ms; H — неоднородные задержки. Среднее восьми сообщений на повтор. Полоса 0.9 = −10%.",
             ha="center", fontsize=9)
    fig.savefig(directory / "paired-t95.png", dpi=170, bbox_inches="tight")
    fig.savefig(directory / "paired-t95.svg", bbox_inches="tight")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory")
    parser.add_argument("--no-plot", action="store_true")
    args = parser.parse_args()
    summarize(args.directory, not args.no_plot)


if __name__ == "__main__":
    main()
