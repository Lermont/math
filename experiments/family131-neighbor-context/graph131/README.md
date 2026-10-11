# Elliptic2: локальная проверка применения №131

Результаты и границы вывода: [отчёт](../results/elliptic2/report.md).
До основного прогона зафиксирован [план](PLAN.md). Все исходные CSV берутся из
официальной Elliptic2 v1; синтетические графы используются только в тестах
корректности. Полный background graph не загружается.

```powershell
python -m venv .venv-graph131
.\.venv-graph131\Scripts\python.exe -m pip install -r results/elliptic2/requirements-lock.txt
.\.venv-graph131\Scripts\python.exe -m graph131.download
.\.venv-graph131\Scripts\python.exe -m graph131.data
.\.venv-graph131\Scripts\python.exe -m unittest discover -s tests -p test_graph131.py -v
.\.venv-graph131\Scripts\python.exe -m graph131.run
.\.venv-graph131\Scripts\python.exe -m graph131.extra_runs
.\.venv-graph131\Scripts\python.exe -m graph131.report
```

Уже сохранённые прогоны пропускаются. Для повторного измерения перенесите старые
`seed*` каталоги в отдельный архив внутри `results/elliptic2/` или используйте
отдельную копию проекта. Изменение источников/параметров требует нового прогона;
наличие старого JSON не проверяет его совместимость с новым кодом.

`switches.py` реализует ядро предложения из №131 и обычное симметричное
предложение пары рёбер. `features.py` использует NetworkX. `worker.py` измеряет
каждый метод в свежем процессе, `evaluate.py` считает качество, `report.py`
оценивает парную неопределённость. `directed.py` сохраняет доступное направление
и кратность платежей в дополнительном контрольном методе.

Гарантия статьи не относится к конечному бюджету наших прогонов. Прикладные
признаки и классификатор — экспериментальная конструкция этого проекта.
