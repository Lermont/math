"""Aggregate raw runs, paired uncertainty and a standalone Russian report."""
from __future__ import annotations

import hashlib
import html
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score

from .data import OUT, ROOT
from .evaluate import metrics

METHODS = ["rules", "degree", "graph", "paper", "edge", "directed"]
NAMES = {"rules": "Дерево простых правил", "degree": "Степени + ExtraTrees", "graph": "Графовые методы + ExtraTrees", "paper": "Графовые методы + №131", "edge": "Графовые методы + обычные перестановки", "directed": "Графовые методы с направлением"}


def load(method, seed):
    return json.loads((OUT / f"seed{seed}/{method}.json").read_text(encoding="utf-8"))


def report():
    audit = json.loads((OUT / "data_audit.json").read_text())
    all_runs = {m: [load(m, s) for s in (131, 132, 133)] for m in METHODS}
    diagnostics = pd.read_csv(OUT / "seed131/paper-diagnostics.csv")
    active_ids = set(diagnostics.loc[~diagnostics.frozen, "id"])
    predictions, rows = {}, []
    for m, runs in all_runs.items():
        pred = [pd.read_csv(OUT / f"seed{s}/{m}-predictions.csv", float_precision="round_trip") for s in (131, 132, 133)]
        for p, saved_run in zip(pred, runs):
            assert (p.id.to_numpy() == pred[0].id.to_numpy()).all()
            assert abs(average_precision_score(p.y, p.score) - saved_run["metrics"]["ap"]) < 1e-12
        predictions[m] = np.stack([p.score.to_numpy() for p in pred])
        if m == METHODS[0]:
            ids, y = pred[0].id.to_numpy(), pred[0].y.to_numpy()
        assert (ids == pred[0].id.to_numpy()).all() and (y == pred[0].y.to_numpy()).all()
        active = np.array([i in active_ids for i in ids])
        rows.append({"method": m, "name": NAMES[m], "ap_mean": np.mean([r["metrics"]["ap"] for r in runs]), "ap_min": min(r["metrics"]["ap"] for r in runs), "ap_max": max(r["metrics"]["ap"] for r in runs), "roc_auc_mean": np.mean([r["metrics"]["roc_auc"] for r in runs]), "precision100_mean": np.mean([r["metrics"]["precision_at_100"] for r in runs]), "recall100_mean": np.mean([r["metrics"]["recall_at_100"] for r in runs]), "test_recall_val1pct_mean": np.mean([r["metrics"]["recall_at_val_1pct_fpr"] for r in runs]), "test_fpr_mean": np.mean([r["metrics"]["test_fpr"] for r in runs]), "total_seconds_median": np.median([r["total_seconds"] for r in runs]), "feature_seconds_median": np.median([sum(r["feature_seconds"].values()) for r in runs]), "fit_seconds_median": np.median([r["fit_seconds"] for r in runs]), "test_features_seconds_median": np.median([r["feature_seconds"]["test"] for r in runs]), "test_predict_seconds_median": np.median([r["test_predict_seconds"] for r in runs]), "test_total_seconds_median": np.median([r["test_total_seconds"] for r in runs]), "peak_rss_mib_median": np.median([r["peak_rss_mib"] for r in runs]), "active_ap_mean": np.mean([average_precision_score(y[active], p.score.to_numpy()[active]) for p in pred]), "active_roc_mean": np.mean([roc_auc_score(y[active], p.score.to_numpy()[active]) for p in pred])})
    frame = pd.DataFrame(rows)
    frame.to_csv(OUT / "summary.csv", index=False)
    # One common resample per iteration preserves pairing between all methods.
    rng = np.random.default_rng(1312026)
    pos, neg = np.flatnonzero(y), np.flatnonzero(y == 0)
    bootstrap = {m: [] for m in METHODS}
    for b in range(1000):
        ix = np.r_[rng.choice(pos, len(pos), replace=True), rng.choice(neg, len(neg), replace=True)]
        for m in METHODS:
            bootstrap[m].append(np.mean([average_precision_score(y[ix], s[ix]) for s in predictions[m]]))
        if (b + 1) % 250 == 0:
            print(f"Paired bootstrap {b+1}/1000", flush=True)
    intervals = {m: {"ap_ci95": list(map(float, np.quantile(bootstrap[m], [.025, .975])))} for m in METHODS}
    for baseline in ("rules", "graph", "edge", "directed"):
        delta = np.array(bootstrap["paper"]) - bootstrap[baseline]
        intervals[f"paper_minus_{baseline}"] = {"mean_delta_ap": float(frame.loc[frame.method == "paper", "ap_mean"].iloc[0] - frame.loc[frame.method == baseline, "ap_mean"].iloc[0]), "paired_delta_ci95": list(map(float, np.quantile(delta, [.025, .975])))}
    (OUT / "uncertainty.json").write_text(json.dumps(intervals, indent=2), encoding="utf-8")
    high = json.loads((OUT / "seed131-budget4/paper.json").read_text())
    pdiag = all_runs["paper"][0]["diagnostics"]
    ed = all_runs["edge"][0]["diagnostics"]
    fonts = {"font.family": "DejaVu Sans", "font.size": 10}
    plt.rcParams.update(fonts)
    short = ["Правила", "Степени + ML", "Графовые методы", "+ №131", "+ обычные swaps", "С направлением"]
    colors = ["#8b98a6", "#8b98a6", "#387a9b", "#d58234", "#69874e", "#5871a2"]
    fig, axes = plt.subplots(1, 3, figsize=(14, 5), layout="constrained")
    order = np.arange(len(METHODS))
    axes[0].barh(order, frame.ap_mean * 100, color=colors)
    for i, m in enumerate(METHODS):
        lo, hi = np.array(intervals[m]["ap_ci95"]) * 100
        axes[0].plot([lo, hi], [i, i], color="#172b3a", linewidth=1.5)
    axes[0].axvline(y.mean() * 100, linestyle="--", color="#a33443", label="Доля suspicious")
    axes[0].set_title("Качество: AP и 95% интервал")
    axes[0].set_xlabel("AP, % — больше лучше")
    axes[0].legend(fontsize=8)
    axes[1].barh(order, frame.total_seconds_median, color=colors)
    axes[1].set_xscale("log"); axes[1].set_title("Полный прогон 20 000 подграфов")
    axes[1].set_xlabel("Секунды, логарифмическая шкала")
    axes[2].barh(order, frame.peak_rss_mib_median, color=colors)
    axes[2].set_title("Пиковая память процесса")
    axes[2].set_xlabel("MiB, включая Python и библиотеки")
    for ax in axes:
        ax.set_yticks(order, short if ax is axes[0] else [""] * len(short))
        ax.invert_yaxis(); ax.grid(axis="x", alpha=.18); ax.set_axisbelow(True)
    fig.suptitle("Elliptic2: ограниченный эксперимент на структуре подграфов", fontsize=15)
    fig.savefig(OUT / "comparison.png", dpi=160)
    plt.close(fig)
    table = "| Метод | AP, % | ROC-AUC | Полный прогон, с | Анализ 4000 новых, с | Пик RAM, MiB |\n|---|---:|---:|---:|---:|---:|\n"
    for row in rows:
        table += f"| {row['name']} | {row['ap_mean']*100:.3f} | {row['roc_auc_mean']:.3f} | {row['total_seconds_median']:.2f} | {row['test_total_seconds_median']:.2f} | {row['peak_rss_mib_median']:.1f} |\n"
    dif = intervals["paper_minus_graph"]
    ci = [v * 100 for v in dif["paired_delta_ci95"]]
    text = f"""# Elliptic2 и работа №131: результаты локального эксперимента

Дата: 11 октября 2026. Практический выигрыш №131 в этом эксперименте не подтверждён.
Это ограниченная проверка выбранных признаков и реализаций, а не оценка всех
применений теоремы, всей Elliptic2 или коммерческих систем антифрода.

{table}

AP — average precision для класса suspicious; это не доля правильных ответов
и не трапецеидальная PR-AUC. Доля suspicious в тесте — {y.mean()*100:.3f}%:
это AP постоянного скоринга. Качество усреднено по трём seed; время и память —
медианы трёх отдельных процессов. Память включает интерпретатор, зависимости,
входные данные, признаки и модель. Время включает загрузку подготовленного
входа, вычисление признаков всех 20 000 графов, обучение, оценку и сохранение
результатов; скачивание и общая подготовка CSV исключены. Анализ новых графов
включает их признаки и предсказание, но не переобучение. CPU один поток,
частота и нагрузка ОС не фиксировались; это замеры Python-реализаций.

## Что сравнивалось

- Правила: дерево глубины 3 по размеру, плотности и распределению степеней.
- Контроль степеней: ExtraTrees по тем же 9 признакам.
- Готовые графовые методы: NetworkX PageRank, Louvain, k-core, треугольники,
  кластеризация, мосты, точки сочленения и эффективность графа + ExtraTrees.
- №131: к тем же признакам добавлены отклонения пяти структурных статистик
  от выборки графов с фиксированными степенями вершин. Это наша прикладная
  конструкция классификатора; статья сама не предлагает детектор отмывания.
- Обычные перестановки: такой же классификатор и признаки, но обычное
  предложение пары рёбер с сохранением степеней и учётом отклонённых шагов.
- Дополнительный контроль сохраняет направление и повторные переводы:
  входящие/исходящие степени, PageRank с кратностью переводов, сильные
  компоненты, источники/стоки и длину пути в ациклических графах.

Все ExtraTrees: 200 деревьев, min_samples_leaf=10, max_features=1.0,
class_weight=balanced, один поток. Параметры не подбирались по тесту.
Точные параметры и дополнительные проверки описаны в graph131/PLAN.md.

## Данные и границы результата

Использована Elliptic2 v1 от Elliptic: connected_components.csv, nodes.csv,
edges.csv. Это 121 810 исходных размеченных подграфов. Взяты 20 000 с seed
1312026 с сохранением доли классов. Обучение: 12 000 / 272 suspicious;
валидация: 4 000 / 91; тест: 4 000 / 91. Подозрительность — метка набора,
а не самостоятельное подтверждение преступления.

Узлы и транзакции между частями не пересекаются. ID не являются признаками.
Разделение случайное, не временное: в трёх выбранных файлах нет временных
атрибутов. Связи внутри семейства транзакций за пределами этих CSV не проверены.
В основном сравнении убрано направление и схлопнуто {audit['sample_removed_parallel_or_reverse_edges']}
повторных/обратных строк рёбер; метод с направлением — отдельный контроль.
Фоновый граф на 49 млн вершин, признаки сумм и времени не используются.
Поэтому это не воспроизведение GLASS, и числа из статьи о GLASS нельзя
ставить в одну таблицу с нашими замерами. Преимущество от глобального контекста
здесь не проверяется.

## Процедура №131 и диагностика

Перенесено точное ядро предложения из статьи: вероятность 1/2 остаться,
равномерная четвёрка вершин, равномерная пара разных совершенных паросочетаний.
Отклонение тоже считается шагом. Никакого требования сохранить связность нет.
Стандартный контроль также имеет симметричные вероятности перехода, но другая
скорость предложения; теорема №131 на него автоматически не переносится.

В основном прогоне burn-in=512, 32 сохранённых графа, интервал 64 предложения.
Это конечный эвристический бюджет, а не сертифицированная равномерная выборка.
Точный равномерный алгоритм с редкой экспоненциальной веткой из статьи не
реализован. Хвостовые частоты не интерпретируются как калиброванные p-value.
Статистики: треугольники, циклы длины 4, смешивание степеней, число компонент,
доля наибольшей компоненты. Для неизменяемого пространства признаки константны.

В выборке {audit['sample_fewer_than_four_nodes']} графов имеют меньше 4 вершин.
У {pdiag['frozen']} из 20 000 нет ни одного допустимого переключения.
Из остальных у {pdiag['active_no_varying_targets']} не менялась ни одна из пяти
измеряемых статистик в сохранённых состояниях (seed 131). Общее число
предложений {pdiag['proposals']:,}, успешных перестановок {pdiag['accepted']:,};
в обычной цепи — {ed['accepted']:,} при том же числе предложений.
Это показатели движения цепи, не доказательство перемешивания.

В тесте перестройка возможна для {int(active.sum())} графов, из них
{int(y[active].sum())} suspicious. AP на этом подмножестве по тем же, уже
обученным моделям приведена в summary.csv (`active_ap_mean`); дополнительного
обучения на нём нет.

Контроль с 4-кратным бюджетом (один seed 131, 2048 + 32×256 предложений):
AP={high['metrics']['ap']*100:.3f}%, ROC-AUC={high['metrics']['roc_auc']:.3f},
время={high['total_seconds']:.2f} с, пик={high['peak_rss_mib']:.1f} MiB.
Он не выбирался вместо основного результата.

## Неопределённость и проверки

Средняя разница AP «№131 минус графовые методы» составляет
{dif['mean_delta_ap']*100:+.3f} процентного пункта. Парный 95% bootstrap-интервал:
[{ci[0]:+.3f}; {ci[1]:+.3f}] п.п. Перевыборка стратифицирована по меткам,
1000 повторов, одна и та же для методов и seed. Интервал условен на фиксированном
разделении и обученных моделях, не учитывает весь разброс других выборок.
Число положительных примеров мало, поэтому небольшие различия неубедительны.
Полные интервалы: uncertainty.json. Остальные метрики, включая top-100 и
порог по валидации с FPR не выше 1%, находятся в summary.csv и сырых JSON.
При совпадающих оценках top-100 использует ожидаемое случайное разрешение
ничьих; поэтому число находок может быть дробным. FPR на тесте не обязан
равняться валидационному.

Семь тестов проверяют 1158 графов из малых пространств реализаций степеней,
точные вероятности перехода №131, сохранение степеней/простоты, независимые
матричные подсчёты мотивов, воспроизводимость и работу с одинаковыми оценками.
Это проверка кода, не формальная верификация статьи и не доказательство
сходимости конечных прогонов. Источники, версии, хеши данных, разбиение,
матрицы признаков, предсказания и диагностика сохранены рядом.

## Практическое решение

На выбранном представлении данных №131 не дал убедительного преимущества
перед простыми правилами и готовыми методами. Добавленная стоимость расчёта
не оправдывается качеством №131, близким к постоянному скорингу. Прототип
не достиг качества, оправдывающего практическое внедрение.
Следующий содержательный эксперимент требует более богатого контекста
транзакций или другого набора, а не просто увеличения числа перестановок.

## Воспроизведение

Из D:/projects/math, Python из .venv-graph131:

```powershell
python -m graph131.download
python -m graph131.data
python -m unittest discover -s tests -p test_graph131.py -v
python -m graph131.run
python -m graph131.extra_runs
python -m graph131.report
```

`run` и `extra_runs` пропускают уже сохранённые результаты. Для нового полного
замера используйте новую копию каталога проекта без seed*-результатов.
Зависимости зафиксированы в requirements-lock.txt. Исходные CSV не публикуются;
лицензия данных Elliptic2 CC BY-NC-ND 4.0 записана отдельно от лицензии кода.

Источники: [Elliptic2, данные](https://www.kaggle.com/datasets/ellipticco/elliptic2-data-set),
[официальный код](https://github.com/MITIBMxGraph/Elliptic2),
[статья о датасете](https://arxiv.org/abs/2404.19109),
[область результата №131](https://github.com/openai/math/blob/fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb/lean/docs/131.md),
[NetworkX Louvain](https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.community.louvain.louvain_communities.html),
[scikit-learn AP](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.average_precision_score.html).
"""
    (OUT / "report.md").write_text(text, encoding="utf-8")
    display = frame[["name", "ap_mean", "roc_auc_mean", "total_seconds_median", "test_total_seconds_median", "peak_rss_mib_median"]].copy()
    display["ap_mean"] *= 100
    display.columns = ["Метод", "AP, %", "ROC-AUC", "Полный прогон, с", "4000 новых, с", "RAM, MiB"]
    html_page = '<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Elliptic2 × №131</title><style>body{font:17px/1.6 system-ui;color:#152b3d;background:#f5f7fa;max-width:1180px;margin:40px auto;padding:0 24px}h1{font-size:34px;line-height:1.2}table{border-collapse:collapse;width:100%;font-size:14px;background:white}td,th{padding:10px;border-bottom:1px solid #d8e0e7;text-align:right}td:first-child,th:first-child{text-align:left}img{width:100%;height:auto}pre{white-space:pre-wrap;background:white;padding:24px;border-radius:12px;font:15px/1.7 system-ui}a{color:#1c6589}</style><h1>Elliptic2: есть ли польза от №131?</h1><p>20 000 подграфов · 3 seed · 4 000 тестовых примеров · 91 suspicious</p><p><strong>В этом ограниченном эксперименте практический выигрыш не подтверждён.</strong></p>' + display.to_html(index=False, float_format=lambda v: f"{v:.3f}", border=0) + '<img src="comparison.png" alt="Качество, время и память"><p><a href="report.md">Полный отчёт</a> · <a href="summary.csv">Таблица CSV</a> · <a href="uncertainty.json">Неопределённость</a></p><pre>' + html.escape(text) + '</pre></html>'
    (OUT / "report.html").write_text(html_page, encoding="utf-8")
    (OUT / "final_code_sha256.json").write_text(json.dumps({str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT / "graph131").glob("*.py")}, indent=2), encoding="utf-8")
    print(frame.to_string(index=False))
    print(json.dumps(intervals, indent=2))


if __name__ == "__main__":
    report()
