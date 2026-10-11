"""Standalone Matplotlib figures from verified aggregate JSON; no reruns."""
from __future__ import annotations
import argparse
import importlib.metadata
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

METHODS = ["fasterpam", "onebatch_auto", "onebatch_2auto", "onebatch256"]
COLORS = {"fasterpam":"#244f6b", "onebatch_auto":"#14816b", "onebatch_2auto":"#c17b13",
          "onebatch256":"#ac5364", "onebatch64":"#86899c", "onebatch_full":"#7951a0"}
LABELS = {"fasterpam":"FasterPAM", "onebatch_auto":"OneBatch auto", "onebatch_2auto":"OneBatch 2×auto",
          "onebatch256":"OneBatch B=256", "onebatch64":"OneBatch B=64", "onebatch_full":"OneBatch B=N"}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run-dir", required=True, type=Path)
    args = p.parse_args()
    run = args.run_dir.resolve()
    agg = json.loads((run/"aggregate.json").read_text(encoding="utf-8"))
    audit = json.loads((run/"verification.json").read_text(encoding="utf-8"))
    assert audit["all_checks_passed"]
    out = run/"figures"
    out.mkdir(exist_ok=True)
    plt.rcParams.update({"font.family":"DejaVu Sans", "font.size":10,
                         "axes.spines.top":False, "axes.spines.right":False,
                         "axes.titleweight":"bold", "axes.labelcolor":"#273641",
                         "axes.edgecolor":"#c3cbd0", "text.color":"#273641",
                         "xtick.color":"#52626d", "ytick.color":"#52626d",
                         "figure.facecolor":"white", "savefig.facecolor":"white",
                         "pdf.fonttype":42, "svg.fonttype":"none"})

    def rows(structure, method):
        return sorted([r for r in agg if r["k"] == 20 and r["structure"] == structure
                       and r["method"] == method], key=lambda r:r["n"])

    def curve(ax, structure, method, metric, band=False):
        records = rows(structure, method)
        xs = np.array([r["n"] for r in records])
        ys = np.array([r[metric+"_median"] for r in records])
        ax.plot(xs, ys, "o-", color=COLORS[method], lw=2, ms=4, label=LABELS[method])
        if band:
            ax.fill_between(xs, [r[metric+"_min"] for r in records], [r[metric+"_max"] for r in records],
                            color=COLORS[method], alpha=.1, linewidth=0)
        ax.set_xticks([1000, 3000, 5000, 7500, 10000])
        ax.xaxis.set_major_formatter(FuncFormatter(lambda v,p:f"{v/1000:g}k"))
        ax.set_xlabel("Число объектов N")
        ax.grid(axis="y", color="#e7ecef", lw=.7)
        ax.set_axisbelow(True)

    def save(fig, name):
        for ext in ("png", "svg", "pdf"):
            fig.savefig(out/(name+"."+ext), dpi=180, bbox_inches="tight")
        plt.close(fig)

    fig, axes = plt.subplots(2, 2, figsize=(12.6, 8.3))
    fig.subplots_adjust(hspace=.44, wspace=.28, top=.87, bottom=.1)
    fig.suptitle("OneBatchPAM: выигрыш в ресурсах и цена выборки", fontsize=17, fontweight="bold", y=.98)
    fig.text(.5, .925, "L1, k=20 · одинаковые float32-расстояния · отдельный процесс на каждый запуск",
             ha="center", color="#667681", fontsize=10)
    for method in METHODS:
        curve(axes[0,0], "all", method, "algorithm_ms")
        curve(axes[0,1], "all", method, "peak_fit_mib")
    axes[0,0].set_title("A  Время: матрица + fit")
    axes[0,0].set_ylabel("Медиана, мс · логарифмическая шкала")
    axes[0,0].set_yscale("log")
    axes[0,0].legend(frameon=False, fontsize=8.5, loc="upper left")
    axes[0,1].set_title("B  Измеренный пик памяти")
    axes[0,1].set_ylabel("Рабочий набор процесса, MiB")
    axes[0,1].set_ylim(85, None)
    for method in METHODS[1:]:
        curve(axes[1,0], "balanced", method, "delta_cost_pct", band=True)
    axes[1,0].axhline(0, color="#52626d", lw=.8, ls="--")
    axes[1,0].set_title("C  Качество на обычных группах")
    axes[1,0].set_ylabel("Изменение полной стоимости, %")
    axes[1,0].text(.02, .95, "Медиана и диапазон 6 запусков", transform=axes[1,0].transAxes,
                    va="top", fontsize=8.5, color="#667681")
    selected = ["fasterpam", "onebatch256", "onebatch_auto", "onebatch_2auto", "onebatch_full"]
    pos = np.arange(len(selected))
    for shift, structure, color, label in ((-.18, "rare_triplets", "#14816b", "Группы по 3 точки"),
                                         (.18, "rare_singletons", "#d8973d", "Одиночные точки")):
        records = [next(r for r in rows(structure, method) if r["n"] == 10000) for method in selected]
        means = np.array([r["rare_groups_covered_mean"] for r in records])
        low = means - np.array([r["rare_groups_covered_min"] for r in records])
        high = np.array([r["rare_groups_covered_max"] for r in records]) - means
        axes[1,1].bar(pos+shift, means, .34, color=color, label=label,
                      yerr=np.array([low, high]), capsize=3,
                      error_kw={"ecolor":"#6e7d86", "elinewidth":1})
    axes[1,1].set_xticks(pos, ["FasterPAM", "B=256", "auto", "2×auto", "B=N"], fontsize=9)
    axes[1,1].set_ylim(0, 8.8)
    axes[1,1].set_yticks([0, 2, 4, 6, 8])
    axes[1,1].set_ylabel("Групп со своим центром из 8")
    axes[1,1].set_title("D  Редкие точки при N=10 000")
    axes[1,1].legend(frameon=False, fontsize=8.5, loc="upper center", bbox_to_anchor=(.5, 1), ncol=1)
    axes[1,1].grid(axis="y", color="#e7ecef", lw=.7)
    axes[1,1].set_axisbelow(True)
    fig.text(.02, .015, "A–B: медианы 18 запусков на размер. C: относительно FasterPAM на тех же данных. "
             "D: среднее и диапазон 6 запусков.\nСинтетический стресс-тест; FasterPAM не объявляется точным оптимумом.",
             fontsize=8.5, color="#667681")
    save(fig, "overview")

    fig, axes = plt.subplots(1, 2, figsize=(12.6, 4.5))
    fig.subplots_adjust(wspace=.28, top=.8, bottom=.22)
    fig.suptitle("Редкие удалённые точки: ошибка на полном наборе", fontsize=16, fontweight="bold", y=.98)
    for ax, structure, title in zip(axes, ("rare_triplets", "rare_singletons"),
                                    ("Восемь групп по 3 точки", "Восемь одиночных точек")):
        for method in METHODS[1:]:
            curve(ax, structure, method, "delta_cost_pct", band=True)
        ax.set_title(title)
        ax.set_ylabel("Изменение стоимости к FasterPAM, %")
        ax.axhline(0, color="#52626d", lw=.8, ls="--")
    axes[0].legend(frameon=False, fontsize=9)
    fig.text(.02, .04, "Линия — медиана, полоса — минимум–максимум 6 запусков. k=20. "
             "Все объекты остаются кандидатами в центры.\nЧисло удалённых объектов фиксировано: их доля падает с ростом N. "
             "Меньшая относительная ошибка не означает лучшего покрытия редких групп.",
             fontsize=8.5, color="#667681")
    save(fig, "rare_tradeoff")
    metadata = {"matplotlib":matplotlib.__version__, "numpy":np.__version__,
                "source":"verified aggregate.json", "run_dir":str(run)}
    (out/"environment.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(str(out))


if __name__ == "__main__":
    main()
