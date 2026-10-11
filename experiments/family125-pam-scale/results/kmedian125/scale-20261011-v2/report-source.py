"""Reproducible Russian narrative and compact tables from verified results."""
from __future__ import annotations
import argparse
import csv
import json
import math
import re
from pathlib import Path
from .core import ROOT, digest, write_json, miss_probability

LABELS = {"fasterpam":"FasterPAM", "onebatch64":"OneBatch B=64", "onebatch256":"OneBatch B=256",
          "onebatch_auto":"OneBatch auto", "onebatch_2auto":"OneBatch 2×auto", "onebatch_full":"OneBatch B=N"}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run-id", required=True)
    args = p.parse_args()
    run = ROOT/"results/kmedian125"/args.run_id
    agg = json.loads((run/"aggregate.json").read_text(encoding="utf-8"))
    audit = json.loads((run/"verification.json").read_text(encoding="utf-8"))
    done = json.loads((run/"completion.json").read_text(encoding="utf-8"))
    assert audit["all_checks_passed"] and audit["checked_runs"] == 576
    rows = list(csv.DictReader((run/"measurements.csv").open(encoding="utf-8")))
    lookup = {(r["n"],r["k"],r["structure"],r["method"]):r for r in agg}
    prefix = "/" + run.as_posix()
    code_prefix = "/" + Path(__file__).parent.as_posix()

    def get(n, method, structure="all", k=20):
        return lookup[n,k,structure,method]

    f10, o10, full10 = [get(10000,m) for m in ("fasterpam","onebatch_auto","onebatch_full")]
    regular, triplets, singletons = [get(10000,"onebatch_auto",s) for s in ("balanced","rare_triplets","rare_singletons")]
    lines = ["# FasterPAM и OneBatchPAM на 1 000–10 000 объектах", "",
      f"Полная серия `{args.run_id}`: **{done['successful']}/{done['scheduled']} успешных запусков**, "
      f"{done['elapsed_this_session']:.1f} с работы контроллера. Качество повторно проверено для "
      f"**{audit['checked_client_assignments']:,} назначений** независимым целочисленным расчётом. "
      "Пять тестов пройдены до замера; лимиты времени, памяти и итераций не достигнуты.", "",
      "## Вывод", "",
      "В этом синтетическом L1-тесте на одном логическом CPU **практический выигрыш OneBatch auto "
      "начинается с N=3 000**: экономия и времени, и измеренного пика памяти превышает10% "
      "и сохраняется на всех больших проверенных размерах, в каждом из трёх сценариев. "
      "Небольшое преимущество медиан есть уже на N=1 000, но память отличается всего на0.2%, "
      "а холодный запуск Python у auto немного медленнее.", "",
      f"На N=10 000 auto ускоряет матрицу+fit в **{o10['speedup_median']:.1f} раза**; "
      f"пик процесса падает с **{f10['peak_fit_mib_median']:.0f} до {o10['peak_fit_mib_median']:.0f} MiB** "
      f"(−{o10['memory_reduction_pct']:.1f}%). С запуском Python, импортами, чтением/записью и проверкой "
      f"ускорение составляет **{o10['cold_speedup_median']:.2f} раза**: "
      f"{f10['process_wall_ms_median']/1000:.2f} → {o10['process_wall_ms_median']/1000:.2f} с.", "",
      f"На обычных группах auto увеличивает полную стоимость на **{regular['delta_cost_pct_median']:.2f}%** "
      "по медиане. Однако на редких удалённых группах по три точки стоимость увеличивается на "
      f"**{triplets['delta_cost_pct_median']:.1f}%**, на удалённых одиночных точках — "
      f"на **{singletons['delta_cost_pct_median']:.1f}%**. Среднее покрытие — "
      f"**{triplets['rare_groups_covered_mean']:.1f}/8** и **{singletons['rare_groups_covered_mean']:.1f}/8**, "
      "тогда как FasterPAM даёт центры всем восьми группам во всех соответствующих запусках.", "",
      "Если редкие удалённые объекты важны, эти результаты не поддерживают замену FasterPAM "
      "на auto без отдельной проверки полного набора. Здесь полезен контроль **OneBatch B=N**: "
      f"все редкие группы сохранены, максимальная разница стоимости на трёх сценариях всего "
      f"**+{full10['delta_cost_pct_max']:.3f}%**, расчёт быстрее в **{full10['speedup_median']:.2f} раза**. "
      "Но экономии памяти практически нет: хранится та же полная матрица.", "",
      f"![Сравнение времени, памяти, обычного качества и редких групп]({prefix}/figures/overview.png)", "",
      "## Где начинается выигрыш в ресурсах", "",
      "Медианы18 запусков на метод и размер: три сценария × два seed данных × три seed алгоритма, k=20. "
      "Время включает построение расстояний и fit, после импортов/чтения. "
      "Память — Windows peak working set сразу после fit, включая библиотеки и рабочие буферы. "
      "MiB=2²⁰ байт. Порог10% был записан в плане до измерений.", "",
      "|N|Auto B|FasterPAM, мс|Auto, мс|Ускорение|Пик FasterPAM → auto, MiB|Экономия пика|",
      "|---:|---:|---:|---:|---:|---:|---:|"]
    for n in (1000,1500,2000,3000,5000,7500,10000):
        f,o = get(n,"fasterpam"),get(n,"onebatch_auto")
        lines.append(f"|{n:,}|{o['batch']}|{f['algorithm_ms_median']:.2f}|{o['algorithm_ms_median']:.2f}|"
                     f"{o['speedup_median']:.2f}×|{f['peak_fit_mib_median']:.1f} → {o['peak_fit_mib_median']:.1f}|{o['memory_reduction_pct']:.1f}%|")
    lines += ["", "При N=10 000 матрицы занимают381.47 MiB у FasterPAM и46.54 MiB у auto, "
      "то есть отличаются в8.20 раза. Полный пик отличается только в3.29 раза из-за общих расходов процесса. "
      "Пик за весь процесс, включая проверку и сохранение результата: "
      f"{f10['peak_total_mib_median']:.1f} против {o10['peak_total_mib_median']:.1f} MiB.", "",
      "### Фазы при N=10 000", "", "Каждый столбец — отдельная медиана; сумма медиан фаз может отличаться от медианы суммы.", "",
      "|Метод|Расстояния, мс|Остальной fit, мс|Назначение всех N и стоимость, мс|Расчёт + назначение, мс|Процесс целиком, мс|",
      "|---|---:|---:|---:|---:|---:|"]
    for method in ("fasterpam","onebatch_auto","onebatch_2auto","onebatch_full"):
        r=get(10000,method)
        lines.append(f"|{LABELS[method]}|{r['distance_ms_median']:.2f}|{r['fit_ms_median']:.2f}|"
                     f"{r['assignment_ms_median']:.2f}|{r['algorithm_and_assignment_ms_median']:.2f}|{r['process_wall_ms_median']:.1f}|")
    lines += ["", "У FasterPAM полные метки уже есть после fit; у OneBatch собственные labels относятся "
      "к выборке. Поэтому полные назначения вычислены дополнительно и одинаково проверены для всех методов. "
      "Свежий процесс не означает холодный дисковый кеш: кеши ОС не сбрасывались; кеша матриц не было.", "",
      "## Качество и редкие удалённые точки", "",
      "Стоимость C — сумма L1-расстояний **всех N объектов** до ближайшего выбранного центра. "
      "ΔC=100·(C/C_F−1), где C_F — медиана трёх FasterPAM запусков на том же наборе. "
      "Это сравнение эвристик, **не разрыв до доказанного оптимума**. Значения могут быть отрицательными. "
      "Внутренний нормированный batch inertia OneBatch для качества не используется.", "",
      "Обычный набор содержит12 сбалансированных групп на сетке4×3 с шагом1000 и шумом±100 по координате. "
      "В двух стресс-сценариях24 или8 объектов заменены восемью удалёнными группами по3 или1 точке. "
      "Их центры — восемь ненулевых векторов из{−100000,0,100000}², шум±5. "
      "Число редких объектов фиксировано: при N=10 000 это0.24% и0.08%. "
      "Данные синтетические, с намеренно большим удалением; это диагностика риска, а не оценка его "
      "частоты в реальных данных. Метки групп и IDs не входят в признаки.", "",
      "Группа считается покрытой, если в ней выбран хотя бы один центр. На этих данных это также "
      "означает обслуживание всех её точек в пределах20 единиц L1. "
      "Непокрытые точки не удаляются из данных или оценки; их большие расстояния входят в полную стоимость.", "",
      "### Auto на всей сетке размеров", "",
      "По6 запусков на ячейку. Покрытие — среднее число редких групп из8; стоимость — медиана [худший запуск].", "",
      "|N|Обычные: ΔC, %|По3 точки: ΔC, %|Покрыто /8|Одиночные: ΔC, %|Покрыто /8|",
      "|---:|---:|---:|---:|---:|---:|"]
    for n in (1000,1500,2000,3000,5000,7500,10000):
        a,b,c=[get(n,"onebatch_auto",s) for s in ("balanced","rare_triplets","rare_singletons")]
        lines.append(f"|{n:,}|{a['delta_cost_pct_median']:+.2f} [{a['delta_cost_pct_max']:+.2f}]|"
                     f"{b['delta_cost_pct_median']:+.2f} [{b['delta_cost_pct_max']:+.2f}]|{b['rare_groups_covered_mean']:.2f}|"
                     f"{c['delta_cost_pct_median']:+.2f} [{c['delta_cost_pct_max']:+.2f}]|{c['rare_groups_covered_mean']:.2f}|")
    lines += ["", "На обычных группах медианная разница auto по размерам лежит от−0.40% до+0.37%; "
      "худший отдельный запуск — +1.24%. Для удалённых групп уже на N=1 500 медиана по3 точки "
      "скрывает риск: +0.02% по медиане, но +203.14% в худшем запуске.", "",
      f"При N=10 000 медиана среднего расстояния редкой точки: "
      f"{triplets['rare_mean_distance_median']:,.0f} для групп по3 и "
      f"{singletons['rare_mean_distance_median']:,.0f} для одиночек; у FasterPAM — около4.06 и0. "
      "Среднее покрытие auto составляет31.25% групп по3 и12.5% одиночек. "
      "В отдельных запусках auto не покрывает ни одной удалённой одиночной точки. "
      "Снижение относительной ΔC на самых больших N не означает восстановления редких точек: "
      "растёт стоимость обычной части и меняется знаменатель сравнения.", "",
      f"![Полная стоимость на редких удалённых точках]({prefix}/figures/rare_tradeoff.png)", "",
      "### Размер выборки при N=10 000, k=20", "",
      "ΔC — медиана. Покрытие — среднее из8 групп за6 запусков. Ресурсы объединяют18 запусков трёх сценариев.", "",
      "|Метод|B|Время, мс|Пик, MiB|Обычные ΔC|По3 ΔC|Покрыто /8|Одиночные ΔC|Покрыто /8|",
      "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for method in ("fasterpam","onebatch64","onebatch256","onebatch_auto","onebatch_2auto","onebatch_full"):
        r=get(10000,method)
        a,b,c=[get(10000,method,s) for s in ("balanced","rare_triplets","rare_singletons")]
        lines.append(f"|{LABELS[method]}|{r['batch']}|{r['algorithm_ms_median']:.2f}|{r['peak_fit_mib_median']:.1f}|"
                     f"{a['delta_cost_pct_median']:+.2f}%|{b['delta_cost_pct_median']:+.2f}%|{b['rare_groups_covered_mean']:.2f}|"
                     f"{c['delta_cost_pct_median']:+.2f}%|{c['rare_groups_covered_mean']:.2f}|")
    lines += ["", "Удвоение auto улучшает покрытие, но сохраняет только4.83/8 групп по3 и1.83/8 одиночек "
      "в среднем; полная стоимость всё ещё выше FasterPAM на111.9% и60.9%. "
      "Малые B=64/256 почти полностью пропускают редкую часть. "
      "Выборки разных B не вложены друг в друга, а начальные центры тоже различаются; "
      "конкретный большой B не обязан обыгрывать меньший при каждом seed. "
      "Полный B=N сохраняет8/8 в каждом запуске; для редких групп по3 максимальный разрыв "
      "до FasterPAM меньше0.0002%, для одиночек стоимость совпадает.", "",
      "## Почему удвоение не устраняет риск", "",
      "Все N объектов остаются кандидатами на центры. Выборка ограничивает **клиентов, по которым "
      "оцениваются замены центров**. Если удалённый клиент не представлен, его геометрия не входит "
      "в эту оценку. Перевзвешивание по ближайшему выбранному клиенту переносит массу, но не "
      "возвращает отсутствующую геометрию. Во всех измеренных OneBatch запусках набор покрытых "
      "удалённых групп точно совпал с набором групп, попавших в выборку; ни одной лишней или "
      "пропущенной представленной группы в журнале нет.", "",
      "При равномерной выборке без возвращения вероятность полностью пропустить фиксированную "
      "группу размера r равна C(N−r,B)/C(N,B). При N=10 000, auto B=1220 она составляет "
      f"**{100*miss_probability(10000,1220,1):.1f}% для одиночки** и "
      f"**{100*miss_probability(10000,1220,3):.2f}% для тройки**; при B=2440 — "
      f"{100*miss_probability(10000,2440,1):.1f}% и{100*miss_probability(10000,2440,3):.2f}%.", "",
      "Чтобы включить все восемь заданных одиночек в выборку с вероятностью не менее99%, "
      "нужно B≥9988 из10000: вероятность включения всех равна произведению "
      "∏_{j=0}^7(B−j)/(N−j). Это только утверждение о попадании в выборку, не гарантия "
      "качества оптимизации. Автоматический B≈100·ln(Nk) не обеспечивает защиту таких редких точек.", "",
      "## Проверка при k=50", "",
      "Один seed данных31 и три запуска на ячейку, отдельно от основной сетки. При N=1000 "
      "auto использует весь набор B=1000 и сохраняет все удалённые группы. При N=10000 B=1312:", "",
      "|Сценарий|Auto ΔC median [max]|Среднее покрытие /8|Ускорение расчёта|",
      "|---|---:|---:|---:|"]
    for structure,label in (("balanced","Обычные группы"),("rare_triplets","Удалённые по3"),("rare_singletons","Удалённые одиночки")):
        r=get(10000,"onebatch_auto",structure,50)
        coverage=f"{r['rare_groups_covered_mean']:.2f}" if structure!="balanced" else "—"
        lines.append(f"|{label}|{r['delta_cost_pct_median']:+.2f}% [{r['delta_cost_pct_max']:+.2f}%]|{coverage}|{r['speedup_median']:.1f}×|")
    lines += ["", "Увеличение числа центров здесь не устранило проблему: размер выборки растёт только логарифмически. "
      "Это ограниченная проверка чувствительности, а не полный поиск по k.", "",
      "## Условия, воспроизводимость и ограничения", "",
      "- Intel Core Ultra7 255H, Windows, 31.4 GiB физической RAM по ОС; affinity=один логический CPU0, "
      "BLAS/OpenMP/Rayon=1, FasterPAM n_cpu=1. Это не сравнение при использовании всех16 потоков CPU.",
      "- Python3.11.16, kmedoids0.5.5, onebatch0.1.0, NumPy2.2.6, SciPy1.16.3, scikit-learn1.7.2. "
      "Пакеты и библиотеки не обновлялись. Библиотеки для рисунков установлены в отдельный каталог "
      "результатов только после завершения измерений.",
      "- 42 набора, N=1000/1500/2000/3000/5000/7500/10000, data seeds31/47, algorithm seeds101/202/303. "
      "576 процессов в заранее перемешанном порядке с seed60211. Никаких выборочных повторов по результатам.",
      "- Одинаковый блочный построитель точных целочисленных L1-расстояний в float32. "
      "FasterPAM хранит одну NxN, OneBatch — одну NxB матрицу. callable-distance путь OneBatch "
      "сохраняет нативную выборку/ядро и избегает лишней копии precomputed режима. "
      "Нормализация/веса OneBatch выполняются самим пакетом; его вычисления float32 являются частью метода.",
      "- У обоих max_iter=100 и случайная инициализация; у OneBatch weighting=True, normalize=True, "
      "tol=1e-6, n_jobs=1. Равные числовые seed не означают равных начальных центров. "
      "Auto B=min(N,max(k,floor(100·ln(max(2,Nk))))). Реализация пакета использует NNIW-перевзвешивание; "
      "гарантия статьи на эти настройки автоматически не переносится.",
      f"- Машина не была выделенным стендом: доступная RAM перед запуском менялась от "
      f"{min(float(r['system_available_before_mib']) for r in rows):.0f} до "
      f"{max(float(r['system_available_before_mib']) for r in rows):.0f} MiB. "
      "Медианы и диапазоны уменьшают влияние фоновой нагрузки, но не являются доверительными интервалами. "
      "Точная граница между соседними N, поведение другой метрики/размерности, параллельного FasterPAM "
      "и реальные данные этим тестом не установлены.",
      "- Полный B=N также ускорился: выигрыш времени здесь объясняется не одной выборкой, "
      "но и реализациями ядра, порядком замен и числом проходов. Память полной матрицы при этом сохраняется.",
      "- Исходный пилот использовал другую цепочку преобразования int64/float64 и precomputed OneBatch; "
      "его абсолютные времена/память напрямую с этой серией не склеиваются. Его файлы,61 исходный "
      "источник и установленные файлы из wheel независимо проверены по хешам и сохранены.",
      "- Первый контроллер v1 прервался после двух child fits из-за гонки poll/memory_info в Windows. "
      "Полная серия v2 повторила тот же заранее заданный план после исправления wait(), без изменения "
      "алгоритмов/данных. Частичный v1 сохранён и не включён в статистику.",
      "- Код анализа написан после запуска по заранее записанным метрикам. Аудит учитывает, "
      "что OneBatch steps — счётчик с нуля: максимум наблюдался4, против лимита100; "
      "у FasterPAM максимум5. Ни один результат не объясняется остановкой по этому лимиту.", "",
      "### Файлы и команды", "",
      f"- [Все таблицы с диапазонами и границами]({prefix}/TABLES.md)",
      f"- [576 измерений CSV]({prefix}/measurements.csv), [агрегаты CSV]({prefix}/aggregate.csv)",
      f"- [Полная проверка]({prefix}/verification.json), [среда и хеши]({prefix}/environment.json)",
      f"- [Исходные результаты JSONL]({prefix}/raw.jsonl), [все метрики вероятности выборки]({prefix}/sampling.csv)",
      f"- [PDF общего графика]({prefix}/figures/overview.pdf), [PDF редких точек]({prefix}/figures/rare_tradeoff.pdf)",
      f"- [Замороженный план]({code_prefix}/PLAN.md), [воспроизведение]({code_prefix}/README.md), "
      f"[источники предыдущего пилота]({code_prefix}/../SOURCES.md)", "",
      "```powershell",
      "& '.\\.venv-kmedian125\\Scripts\\python.exe' -m unittest kmedian125.scale.test_scale -v",
      "& '.\\.venv-kmedian125\\Scripts\\python.exe' -m kmedian125.scale.run --run-id scale-replication-001",
      "& '.\\.venv-kmedian125\\Scripts\\python.exe' -m kmedian125.scale.analyze --run-id scale-replication-001",
      "& '.\\.venv-kmedian125\\Scripts\\python.exe' -m kmedian125.scale.report --run-id scale-replication-001",
      "```", "",
      "Отрисовка не требует повторного расчёта методов. Скрипт `plot.py` принимает `--run-dir`; "
      f"его отдельные зависимости и точные команды сохранены в [PLOTTING.md]({code_prefix}/PLOTTING.md).", ""]
    text="\n".join(lines)
    # Only typography cleanup in prose, preserving numerical results and identifiers.
    text=re.sub(r"(?<=[А-Яа-яЁё])(?=[0-9±{−+])", " ", text)
    text=re.sub(r"(?<=\d),(?=\d{3}(?:\D|$))", " ", text)
    for old,new in {"Python3":"Python 3", "kmedoids0":"kmedoids 0", "onebatch0":"onebatch 0",
                    "NumPy2":"NumPy 2", "SciPy1":"SciPy 1", "scikit-learn1":"scikit-learn 1",
                    "Ultra7":"Ultra 7", "CPU0":"CPU 0", "seeds31":"seeds 31",
                    "seeds101":"seeds 101", "seed60211":"seed 60211", "файлы,61":"файлы, 61"}.items():
        text=text.replace(old,new)
    output=run/"REPORT.md"
    output.write_text(text, encoding="utf-8")
    write_json(run/"report-manifest.json", dict(report_path=str(output), report_sha256=digest(output),
               generator_sha256=digest(__file__), analysis_sha256=digest(Path(__file__).with_name("analyze.py")),
               aggregate_sha256=digest(run/"aggregate.json"), verification_sha256=digest(run/"verification.json")))
    print(str(output))


if __name__ == "__main__":
    main()
