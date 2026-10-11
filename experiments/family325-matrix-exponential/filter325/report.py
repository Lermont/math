"""Generate concise Russian tables from audited measurements; no new benchmarks."""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import statistics
from .data import ROOT
from .benchmark import write_json


LABELS={'symmetric_ring':'симметричное кольцо','normal_cycle':'нормальный цикл',
        'directed_regular':'направленный граф','directed_hub':'граф с hub',
        'jordan':'Jordan','grcar':'Grcar'}
METHODS={'crouzeix2':'№325, C=2','crouzeix_old':'старая C=1+√2','norm_taylor':'Taylor через норму',
         'scipy':'SciPy, публичный API','scipy_cached':'SciPy с подготовкой','arnoldi':'Arnoldi','normal1':'нормальный C=1'}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=ROOT/'results'/'filter325'/'run-20261011')
    args=parser.parse_args()
    out=args.output
    rows=json.loads((out/'measurements.json').read_text(encoding='utf-8'))
    cases=json.loads((out/'cases.json').read_text())
    validation=json.loads((out/'validation.json').read_text())
    ix={(r['case'],r['method'],r['tolerance']):r for r in rows}
    cx={c['name']:c for c in cases}
    new=[r for r in rows if r['method']=='crouzeix2']
    nonnormal=[r for r in new if not cx[r['case']]['normal_control']]
    differences=Counter(ix[(r['case'],'crouzeix_old',r['tolerance'])]['degree']-r['degree'] for r in new)
    savings=[{'case':r['case'],'tol':r['tolerance'],'new_degree':r['degree'],
              'old_degree':ix[(r['case'],'crouzeix_old',r['tolerance'])]['degree']} for r in new
             if ix[(r['case'],'crouzeix_old',r['tolerance'])]['degree']>r['degree']]
    comparisons=[]
    for method in ('crouzeix_old','norm_taylor','scipy','scipy_cached','arnoldi'):
        ratios={field:[ix[(r['case'],method,r['tolerance'])][field]/r[field] for r in nonnormal]
                for field in ('single_total_median_s','batch_total_median_s')}
        comparisons.append({'competitor':method,'pairs':len(nonnormal),
                            'single_wins_at_least_10pct':sum(q>=1/.9 for q in ratios['single_total_median_s']),
                            'batch_wins_at_least_10pct':sum(q>=1/.9 for q in ratios['batch_total_median_s']),
                            'median_competitor_over_new_single':statistics.median(ratios['single_total_median_s']),
                            'median_competitor_over_new_batch':statistics.median(ratios['batch_total_median_s'])})
    old_spmv=sum(ix[(r['case'],'crouzeix_old',r['tolerance'])]['degree'] for r in nonnormal)
    new_spmv=sum(r['degree'] for r in nonnormal)
    max_rounding=max(r['float_vs_decimal_same_polynomial_first_vector_2norm'] or 0 for r in rows)
    max_reference=max(max(c['reference_dense_vs_decimal_2norm']) for c in cases)
    max_refine=max(c['reference_refinement_2norm'] for c in cases)
    conservative=[v for r in nonnormal for v in r['bound_over_error']]
    large=ix[('directed_regular_n1024_s32501','crouzeix2','1e-7')]
    hub=ix[('directed_hub_n1024_s32502','crouzeix2','1e-7')]
    hub_scipy=ix[(hub['case'],'scipy_cached','1e-7')]
    hub_arnoldi=ix[(hub['case'],'arnoldi','1e-7')]
    jordan=ix[('jordan_n2048_s32501','crouzeix2','1e-7')]
    def crossing(r,method):
        other=ix[(r['case'],method,r['tolerance'])]
        delta=other['prepared_apply_median_s']-r['prepared_apply_median_s']
        if delta<=0:return 'не ожидается по этой модели'
        return str(max(1,math.ceil(max(r['setup_median_s']-other['setup_median_s'],0)/delta)))
    rss=[r['memory']['peak_process_rss_bytes']/1048576 for r in rows]
    tracked={m:max(r['memory']['tracked_setup_batch_peak_bytes'] for r in rows if r['method']==m)/1024 for m in METHODS}
    env=json.loads((out/'versions.json').read_text())
    cpu=json.loads((out/'cpu.json').read_text(encoding='utf-8-sig'))['Name'] if (out/'cpu.json').exists() else env['processor']
    summary={'new_old_degree_difference_histogram':dict(differences),'degree_savings':savings,
             'nonnormal_old_degree_sum':old_spmv,'nonnormal_new_degree_sum':new_spmv,
             'nonnormal_spmv_saving_fraction':(old_spmv-new_spmv)/old_spmv,
             'fixed_polynomial_bound_reduction_fraction':1-2/(1+math.sqrt(2)),
             'comparisons_nonnormal_only':comparisons,'max_roundoff_first_vector':max_rounding,
             'max_dense_reference_disagreement':max_reference,'max_decimal_refinement_difference':max_refine,
             'all_targets_met':validation['all_meet_requested_input_scaled_tolerance']}
    write_json(out/'summary.json',summary)
    lines=[
        '# №325 для матричной экспоненты: результат локального эксперимента', '',
        '11 октября 2026. **Теорему удалось применить напрямую к оценке ошибки, но заметного общего ускорения именно от новой константы не обнаружено.** '
        'При одинаковых диске и Taylor-полиноме константа 2 уменьшила степень только в 4 из 45 пар, каждый раз на единицу. '
        'Полиномиальный фильтр полезен при повторном использовании, однако почти весь этот эффект доступен со старой константой.', '',
        '**Что измерено.** 15 синтетических случаев, n=64…2048; seeds 32501/32502; '
        'допуски 1e-4, 1e-7, 1e-10 для `‖ошибка‖₂/‖x‖₂`; по 8 разных x. '
        '282 строки, 2256 результатов: все прошли целевой допуск. Это не допуск относительно выходного сигнала; '
        'абсолютная и относительная выходная ошибки сохранены отдельно. Два seed структурных семейств меняют x, а не A. '
        'Критерий выигрыша до запуска — ≥10% полного времени при выполнении допуска на всех входах. '
        f'Пять повторов после разминки, один поток BLAS, CPU {cpu}, {env["platform"]}; общий рабочий компьютер без эксклюзивного закрепления CPU.', '',
        '**Вклад новой константы.** На фиксированном полиноме граница меньше на 17.16%. '
        'При tol=1e-4 hub128: степень 67→66 для обоих seeds; при tol=1e-10 направленный граф1024: 35→34, hub1024: 362→361. '
        f'На 33 ненормальных сочетаниях сумма SpMV на один x сократилась с {old_spmv} до {new_spmv} ({100*(old_spmv-new_spmv)/old_spmv:.2f}%). '
        'В остальных 41 паре степени и восемь выходов битово одинаковы. Разброс времени этих пар и различная стоимость рационального сертификата '
        'не считаются доказательством ускорения самого применения. На нормальных контролях уже доступна C=1; преимуществ №325 там не заявляем.', '',
        'Ниже tol=1e-7. Seed 32501, кроме hub1024 (32502). Ошибка — максимум по восьми x. '
        '`B/‖x‖` — верхняя граница **усечения в точной арифметике**. Время включает новую подготовку; '
        'в ячейках времени порядок «№325 / SciPy с сохранением подготовки».', '',
        '| Матрица | n | Степени 2 / старая / норма | Ошибка/‖x‖ | B/‖x‖ | 1 x, мс | 8 x, мс |',
        '|---|---:|---:|---:|---:|---:|---:|'
    ]
    selected=[c for c in cases if c['seed']==32501 or c['n']>128]
    for c in selected:
        r=ix[(c['name'],'crouzeix2','1e-7')]
        old=ix[(c['name'],'crouzeix_old','1e-7')]
        norm=ix[(c['name'],'norm_taylor','1e-7')]
        scipy=ix[(c['name'],'scipy_cached','1e-7')]
        lines.append(f'| {LABELS[c["family"]]} | {c["n"]} | {r["degree"]} / {old["degree"]} / {norm["degree"]} | '
                     f'{max(r["relative_input_errors"]):.2e} | {r["operator_bound_exact_arithmetic"]:.2e} | '
                     f'{r["single_total_median_s"]*1000:.2f} / {scipy["single_total_median_s"]*1000:.2f} | '
                     f'{r["batch_total_median_s"]*1000:.2f} / {scipy["batch_total_median_s"]*1000:.2f} |')
    lines += ['',
        'У нормальных контролей `normal1` выбирает степень 18 вместо 19 при этом допуске. '
        f'Консервативность ненормальных границ по всем допускам: от {min(conservative):.2f} до {max(conservative):.2e} относительно измеренной ошибки; '
        'верхний край в основном сравнивает грубую границу с погрешностью около машинного уровня.', '',
        'Сравнение **33 ненормальных сочетаний**, без нормальных контролей. Число выигрышей по заранее заданному порогу в этой серии; '
        'последний столбец — медиана `время конкурента / время №325` для 8 x. '
        'Значение >1 означает более быстрый №325 в медиане отношений. Это описательные результаты небольшой зависимой выборки, без статистической гарантии.', '',
        '| Конкурент | Выигрыш №325, 1 x | Выигрыш №325, 8 x | Отношение времени, 8 x |',
        '|---|---:|---:|---:|'
    ]
    for c in comparisons:
        if c['competitor']=='crouzeix_old':continue
        lines.append(f'| {METHODS[c["competitor"]]} | {c["single_wins_at_least_10pct"]}/33 | {c["batch_wins_at_least_10pct"]}/33 | {c["median_competitor_over_new_batch"]:.2f} |')
    lines += ['',
        'Публичный `expm_multiply` не имеет пользовательского tol и обычно выдаёт более точный результат. '
        '`scipy_cached` — адаптер к неизменённым внутренним выбору степени/масштаба и ядру SciPy 1.18.1, '
        'с общей подготовкой на матрицу. Это устраняет преимущество только от доступности кеша. '
        'Arnoldi — наша реализация с двумя проходами ортогонализации и эвристической остановкой по соседним приближениям; '
        'все её результаты проверены по эталону, но критериям не приписана строгая гарантия.', '',
        f'**Окупаемость области.** Для направленного графа1024 область строилась {large["geometry_median_s"]*1000:.2f} мс; вся подготовка №325 — {large["setup_median_s"]*1000:.2f} мс; '
        f'применение — {large["prepared_apply_median_s"]*1000:.3f} мс. Степень 29 против 39 у простого нормового Taylor, '
        'но за восемь входов нет выигрыша ≥10% над ним, а подготовленный SciPy быстрее. '
        f'Линейная модель из измеренных стадий предсказывает пересечение с нормовым Taylor примерно после {crossing(large,"norm_taylor")} входов, '
        f'с подготовленным SciPy — после {crossing(large,"scipy_cached")}; это экстраполяция, а не дополнительные измеренные серии. '
        f'У hub1024 диск r={hub["radius"]:.2f} почти не улучшает нормовый R={hub["norm_radius"]:.2f}: {hub["degree"]} SpMV на x против '
        f'{sum(hub_scipy["products_per_input"][0].values())} в ядре SciPy и {sum(hub_arnoldi["products_per_input"][0].values())} у Arnoldi. '
        f'У Jordan2048 радиусы совпали; построение области заняло {jordan["geometry_median_s"]*1000:.2f} мс и не помогло выбрать степень. '
        'У hub128 подготовка и применение лучше нормового Taylor, однако одно применение быстрее делает Arnoldi.', '',
        '**Затраты и проверки.** Помимо степеней сохранены фактические SpMV, в том числе при подготовке и для транспонированной матрицы. '
        f'Например, hub1024: подготовленный SciPy расходует {hub_scipy["setup_products"]["csr_forward"]} прямых + '
        f'{hub_scipy["setup_products"]["csc_adjoint"]} транспонированных произведений один раз, затем {sum(hub_scipy["products_per_input"][0].values())} на первый x; '
        f'№325 — {sum(hub["setup_products"].values())} произведений с вспомогательной S, затем {hub["degree"]}. Ортогонализация Arnoldi учитывается во времени, а не в SpMV. '
        f'Во всех методах пиковый working set свежего процесса {min(rss):.2f}–{max(rss):.2f} MiB, включая Python/библиотеки/данные. '
        f'Максимумы трассируемых выделений setup+8 выходов: №325 {tracked["crouzeix2"]:.0f} KiB, нормовый Taylor {tracked["norm_taylor"]:.0f} KiB, '
        f'SciPy {tracked["scipy"]:.0f} KiB, SciPy с подготовкой {tracked["scipy_cached"]:.0f} KiB, Arnoldi {tracked["arnoldi"]:.0f} KiB. Трассировка не охватывает все native-буферы; '
        'RSS снят отдельно без её накладных расходов.', '',
        f'Шесть тестов прошли; повторное чтение подтвердило хеши, все {validation["predictions"]} ошибки и точные рациональные свидетели дисков. '
        f'Плотный Padé и Decimal80 расходились максимум на {max_reference:.2e}; Decimal80/110 для первого x — не более {max_refine:.2e}. '
        'Остаток высокоточного ряда <1e-65; это оценка усечения, не всех его округлений. '
        f'Float64-применение выбранного полинома расходилось с Decimal80 максимум на {max_rounding:.2e} на проверенных первых x. '
        '**Полная float64-ошибка не сертифицирована**; резерв 10% не заменяет анализа округлений.', '',
        '**Математический статус.** Использован m=1 из '
        '[теоремы №325](https://github.com/openai/math/blob/fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb/preprints/A-direct-proof-of-the-complete-Crouzeix-inequality-September-26-2026/build/main.tex), '
        'а переход к exp обоснован равномерной сходимостью полиномиального ряда. Внешний диск и остаток проверены рационально; '
        'выбор Taylor и области — наш прототип. '
        '[Каталог Lean](https://github.com/openai/math/blob/fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb/lean/docs/325.md) '
        'заявляет формализацию; проверены формулировки, условия и связь с файлами решения, но Lean/Comparator не запускались. '
        'Коммит совпал с указанным пользователем, новых исправлений нет. Полнота для матричных коэффициентов в этом скалярном приложении не используется.', '',
        'Практический вывод: прототип даёт воспроизводимый способ выбрать степень с обоснованной оценкой усечения. '
        'На повторных входах он иногда дешевле готового API, даже с подготовкой у конкурента; '
        f'замена одной константы сама по себе дала лишь {100*(old_spmv-new_spmv)/old_spmv:.2f}% экономии SpMV в ненормальной части этой выборки. '
        'Для единичных действий и крупных hub-графов готовый метод предпочтительнее в измеренной серии. '
        'Это не отрицательный результат для всех полиномов/областей: Faber, Chebyshev, оптимальный центр и другие геометрии не исследовались.', '',
        'Воспроизведение, сохранённые SHA-256 и подробный вывод оценки: '
        '[README](../../../filter325/README.md), [план](../../../filter325/PLAN.md), '
        '[теория и первоисточники](../../../filter325/THEORY.md), [CSV](measurements.csv), '
        '[сырые времена](measurements.jsonl), [проверка](validation.json). '
        'Конкуренты: [Al-Mohy–Higham](https://eprints.maths.manchester.ac.uk/1591/), '
        '[Crouzeix–Palencia 2017](https://arxiv.org/abs/1702.00668), '
        '[Saad](https://www-users.cse.umn.edu/~saad/PDF/RIACS-90-ExpTh.pdf).'
    ]
    lines += ['', 'Команды из `D:\\projects\\math` после установки зависимостей в отдельную среду; `reproduce` — новый каталог:', '',
              '```powershell',
              '.\\.venv-filter325\\Scripts\\python.exe -m unittest discover -s filter325 -p test_filter325.py -v',
              '.\\.venv-filter325\\Scripts\\python.exe -m filter325.benchmark --output results/filter325/reproduce --stage all',
              '.\\.venv-filter325\\Scripts\\python.exe -m filter325.audit --output results/filter325/reproduce',
              '.\\.venv-filter325\\Scripts\\python.exe -m filter325.report --output results/filter325/reproduce',
              '```']
    (out/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    # Complete comparison, preserving all cases, tolerances and methods.
    details=['# Полная таблица времени и ошибок','',
             'Время в миллисекундах; B — точная арифметика. SciPy degree — m_star одной стадии, число стадий и фактические SpMV в JSON.','',
             '| Случай | tol | Метод | Степень | max abs error | max error/‖x‖ | max error/‖y‖ | max B | setup, мс | 1 x, мс | 8 x, мс |',
             '|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for r in sorted(rows,key=lambda r:(r['case'],float(r['tolerance']),r['method'])):
        b=f'{max(r["action_bounds_exact_arithmetic"]):.3e}' if r['action_bounds_exact_arithmetic'] else '—'
        details.append(f'| {r["case"]} | {r["tolerance"]} | {r["method"]} | {r["degree"]} | '
                       f'{max(r["abs_errors"]):.3e} | {max(r["relative_input_errors"]):.3e} | {max(r["relative_output_errors"]):.3e} | {b} | '
                       f'{r["setup_median_s"]*1000:.3f} | {r["single_total_median_s"]*1000:.3f} | {r["batch_total_median_s"]*1000:.3f} |')
    (out/'all-methods.md').write_text('\n'.join(details)+'\n',encoding='utf-8')
    print(json.dumps({'report':str(out/'report.md'),'rows':len(rows),'status':'written'},ensure_ascii=False))


if __name__=='__main__':
    main()
