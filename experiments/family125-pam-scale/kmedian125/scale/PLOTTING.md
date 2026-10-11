# Воспроизведение графиков

Графики Matplotlib строятся только из уже проверенного `aggregate.json`.
Они экспортируются как PNG, SVG и PDF. Алгоритмы кластеризации повторно
не запускаются. Для первоначальной серии библиотеки отрисовки установлены
**после** окончания всех 576 измерений, в отдельный каталог результатов.
Пакеты среды `.venv-kmedian125` не менялись.

Для сохранённой серии из корня `D:\projects\math`:

```powershell
& '.\.venv-kmedian125\Scripts\python.exe' -c "import sys,runpy; sys.path.insert(0,r'D:\projects\math\results\kmedian125\scale-20261011-v2\plot-runtime'); sys.argv=['plot','--run-dir',r'D:\projects\math\results\kmedian125\scale-20261011-v2']; runpy.run_module('kmedian125.scale.plot',run_name='__main__')"
```

Для нового запуска сначала выполните `scale.analyze`, затем установите
зависимости в его отдельный каталог. Используйте сохранённый lock-файл:

```powershell
& '.\.venv-kmedian125\Scripts\python.exe' -m pip install --no-compile --target 'results\kmedian125\scale-replication-001\plot-runtime' -r 'results\kmedian125\scale-20261011-v2\plot-requirements.lock.txt'
```

В команде отрисовки замените оба `scale-20261011-v2` на свой run-id и при
необходимости замените абсолютный корень проекта. Это оставляет зависимости
измерителя и отрисовки раздельными.

После отрисовки можно сформировать текстовый отчёт:

```powershell
& '.\.venv-kmedian125\Scripts\python.exe' -m kmedian125.scale.report --run-id scale-replication-001
```

Команда создаёт `REPORT.md` внутри каталога своего запуска в `results/`;
сырые измерения, таблицы, замороженные исходники и конфигурация остаются там же.
Файл `kmedian125/scale/REPORT.md` служит ссылкой на сохранённую полную серию.
Полосы на рисунках означают наблюдённый минимум–максимум, не доверительный
интервал. Рисунки используют k=20; k=50 вынесено в отчёт и CSV.
