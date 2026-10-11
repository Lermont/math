# Локальный пилот k-median, семейство 125

Начните с [REPORT.md](REPORT.md). Это проверка реализуемости и отдельной
эвристики LP-DR16-swap, не реализация полного алгоритма статьи с её гарантией.
Полный метод оценён в [FEASIBILITY.md](FEASIBILITY.md); источники — [SOURCES.md](SOURCES.md).

Рабочая директория: `D:\projects\math`. Окружение уже готово в
`.venv-kmedian125`; прочие окружения проекта не используются.

```powershell
Set-Location 'D:\projects\math'
& '.\.venv-kmedian125\Scripts\python.exe' -m unittest discover -s kmedian125 -p 'test*.py' -v
& '.\.venv-kmedian125\Scripts\python.exe' -m kmedian125.feasibility
& '.\.venv-kmedian125\Scripts\python.exe' -m kmedian125.run_experiment --run-id replication-001
& '.\.venv-kmedian125\Scripts\python.exe' -m kmedian125.summarize --run-id replication-001
```

`--run-id` должен быть новым: существующие результаты не переписываются.
Новый запуск снова выполняет 380 отдельных процессов, последовательный лимит
1200 с, по 60 с / 1 GiB на процесс и 30 с на solver. Хеши плана, конфигурации
и кода сохраняются до измерений в environment.json и source-snapshot/.
Кеши данных и все сырые результаты находятся только под results/kmedian125/.
Итоговый анализ повторно проверяет сертификаты и стоимость, но методы не запускает.

Для независимой проверки сохранённого пилота:

```powershell
& '.\.venv-kmedian125\Scripts\python.exe' -m kmedian125.summarize --run-id pilot-20261011-v1
& '.\.venv-kmedian125\Scripts\python.exe' -m kmedian125.provenance
```

`provenance` проверяет конкретно исходный пилот v1 и его исходники, оригинальные
источники и совпадение реально установленных файлов FasterPAM/OneBatch с
сохранёнными wheel. Усиленная после запуска проверка нижней границы описана
в POSTRUN_AUDIT.md; первоначальные таблицы не потеряны.

При восстановлении среды используйте Python 3.11 x64 и только отдельную среду:

```powershell
# Выполнять создание только если .venv-kmedian125 ещё отсутствует.
& 'C:\Users\r\AppData\Roaming\uv\python\cpython-3.11.16-windows-x86_64-none\python.exe' -m venv .venv-kmedian125
& '.\.venv-kmedian125\Scripts\python.exe' -m pip install -r kmedian125\requirements.lock.txt
& '.\.venv-kmedian125\Scripts\python.exe' kmedian125\fetch_sources.py
```

Исходный Python-путь относится к этой машине; на другой машине подставляется
путь Python 3.11. Хеши wheel ключевых baseline-пакетов хранятся в манифесте
references/kmedian125/sources.json, сами wheel — в references/kmedian125/wheels/.
`fetch_sources.py` получает закреплённые коммиты и фиксирует текущий main отдельно;
для архивного аудита сначала используйте уже сохранённый манифест, поскольку
повторная загрузка обновляет только его время проверки/main metadata.

Структура кода:

- `data.py`: генераторы, метрики, независимый целочисленный пересчёт стоимости.
- `methods.py`: LP/MILP/перебор, парное округление, greedy и 1-swap.
- `worker.py`, `run_experiment.py`: изолированные измерения и лимиты.
- `certify.py`, `summarize.py`: точные сертификаты и общие таблицы.
- `test*.py`: модель, бюджет, моменты, метрики, независимые проверки.
- `requirements.lock.txt`, `config.json`, `PLAN.md`: воспроизводимая конфигурация.

Сырые UCI Seeds и оригинальные статьи остаются в references/kmedian125/.
Лицензия Seeds CC BY 4.0, авторы Charytanowicz et al.; она отдельно от лицензии
кода проекта. Обёртки и бинарные реализации baseline используются как пакеты,
оригинальные источники не редактируются. Работа локальная, публикаций нет.
