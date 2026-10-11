# Источники и версии

Манифест `references/kmedian125/sources.json` содержит 61 локальный оригинальный
файл: URL, SHA-256, размер и Git-коммит (где применим). Бумажные источники не
редактировались. `results/kmedian125/provenance-audit.json` проверяет их хеши,
совпадение исполняемых .py/.pyd с сохранёнными wheel и неизменность плана,
конфигурации и исходников измеренных методов относительно snapshot запуска.

| Источник | Закреплённая версия | Использование |
|---|---|---|
| [openai/math](https://github.com/openai/math/tree/fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb) | fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb, current main на 11.10.2026 | №125, две статьи, история исправлений, модель/параметры |
| [FasterPAM, статья](https://arxiv.org/abs/2008.05171v2) | Schubert, Rousseeuw, v2 (2021) | готовый сильный baseline с eager swaps |
| [python-kmedoids](https://github.com/kno10/python-kmedoids) | PyPI kmedoids 0.5.5, сохранён Windows cp311 wheel | реально исполняемый FasterPAM; n_cpu=1 |
| [OneBatchPAM, статья](https://arxiv.org/abs/2501.19285v1) | de Mathelin et al., v1 (2025) | NNIW-вариант взвешивания, полный набор кандидатов при sampled clients |
| [Исходные эксперименты obpam](https://github.com/antoinedemathelin/obpam/tree/ee823101bd43dbb4095b103ef248221c682da88e) | ee823101bd43dbb4095b103ef248221c682da88e | README направляет на новый авторский пакет; исходный код сохранён |
| [Авторский пакет onebatch](https://github.com/antoinedemathelin/onebatch/tree/950cae188f171878c3ff574b81bce7d41736107e) | Git 950cae188f171878c3ff574b81bce7d41736107e; wheel onebatch 0.1.0 | готовая Cython-реализация; normalize=True, weighting=True |
| [UCI Seeds](https://archive.ics.uci.edu/dataset/236/seeds) | zip и страница с SHA-256 в манифесте | 210 измерений, семь признаков; DOI 10.24432/C5H30K, CC BY 4.0 |
| [SciPy milp](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.milp.html) | SciPy 1.16.3 / HiGHS 1.8.0 | статусы решателя, ограничения и численная нижняя граница |

Вопросы к SciPy и kmedoids уточнены через Context7: `/scipy/scipy` и
`/kno10/python-kmedoids`. Фактически установленные сигнатуры дополнительно
прочитаны локально. Окружение: CPython 3.11.16, NumPy 2.2.6, scikit-learn 1.7.2;
все пакеты закреплены в `requirements.lock.txt` и environment.json запуска.

Между raw GitHub-файлом onebatchpam.py и файлом из wheel отличаются байтовые
хеши из-за CRLF/LF; после нормализации концов строк текст совпадает.
Бинарное ядро и установленная обёртка сравниваются с сохранённым wheel
побайтно. Это не предположение, что произвольный current main равен PyPI.

Автоматическая формула batch в пакете — практическая настройка. В статье
оценка достаточного m зависит также от диаметра, минимального различия
стоимостей обменов, числа шагов и вероятности ошибки; из записи O(log n)
не следует гарантия для выбранных 64 точек. На целочисленных метриках
могут быть равные стоимости обменов. Здесь оценивается фактическое качество,
а теорема OneBatch о совпадении траектории не объявляется выполненной.

Готовый пакет использует NNIW-подобное взвешивание; не включается debias-замена
нулевой собственной дистанции. Поэтому он явно отличается от default
`weight='debias'` в исходном obpam. Итоговую невзвешенную сумму по всем клиентам
считает наш независимый проверяющий код: `inertia_` пакета для sampled/normalized
матрицы не используется как качество решения.

Полная схема снятия surplus проверена по разделам самой статьи №125 и её
цитате на Li–Svensson, *Approximating k-Median via Pseudo-Approximation*,
[авторская версия 11.09.2014](https://tcs.nju.edu.cn/shili/papers/KM-SIMPCOMP2016.pdf),
Theorem 4. Эта внешняя PDF прочитана веб-инструментом, но прямое скачивание
на рабочую машину завершилось таймаутом; локального PDF и его хеша нет.
Параметры используемой здесь оценки воспроизводятся из полностью сохранённых
`preliminaries.tex` и `derandomization.tex` №125, а не из неподтверждённой копии PDF.
