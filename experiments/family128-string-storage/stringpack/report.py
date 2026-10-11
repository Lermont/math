"""Generate a self-contained Russian HTML dashboard and Markdown report."""
import argparse
import json
from pathlib import Path

LABELS = {"plain": "Обычное + индекс", "dedup": "Удаление дублей",
          "paper128": "№128", "prefix": "Префиксное · 16 строк",
          "zstd_blocks": "Zstd · 32 строки", "zstd_whole": "Zstd · весь набор"}

HTML = r'''<!doctype html>
<html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>№128 — практический тест упаковки строк</title>
<style>
:root{color-scheme:light;--bg:#f3f5f6;--fg:#152a35;--muted:#586b76;--line:#d8e1e6;--accent:#006f72}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 system-ui,Segoe UI,sans-serif}
main{max-width:1200px;margin:0 auto;padding:40px 24px 72px}header{max-width:950px;margin-bottom:26px}
.eyebrow{font-size:12px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--accent)}
h1{font-size:clamp(29px,4vw,44px);line-height:1.13;letter-spacing:-.025em;margin:12px 0 20px}
h2{font-size:21px;line-height:1.3;margin:0 0 16px}p{margin:12px 0}.lead{font-size:19px;max-width:850px}
.muted,small{color:var(--muted)}a{color:var(--accent)}.panel{background:#fff;border:1px solid var(--line);border-radius:12px;padding:24px;margin:20px 0}
.selector{display:flex;align-items:center;gap:16px;flex-wrap:wrap}select{font:inherit;background:white;border:1px solid #8ca2af;border-radius:6px;padding:9px 12px;max-width:100%}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:22px 0}.stat{border-left:3px solid var(--accent);padding-left:13px}.stat.bad{border-color:#a24c2f}.stat.bad .value{color:#85432c}.value{font-size:25px;line-height:1.2;font-weight:700}.label{font-size:12px;color:var(--muted);margin-top:7px}
.plots{display:grid;grid-template-columns:1fr 1fr;gap:32px;margin:24px 0}.plot h3{font-size:14px}.barline{display:grid;grid-template-columns:145px 1fr 72px;gap:8px;align-items:center;margin:12px 0;font-size:12px}.track{height:13px;background:#eef2f4;border-radius:3px;overflow:hidden}.bar{height:100%;background:#8a9ca7}.bar.paper{background:#007b7e}.bar.zstd{background:#cf7d35}.barvalue{text-align:right;font-variant-numeric:tabular-nums}
.scroll{overflow:auto}table{border-collapse:collapse;width:100%;font-size:14px;white-space:nowrap}th,td{text-align:right;padding:10px 12px;border-bottom:1px solid var(--line);font-variant-numeric:tabular-nums}th{font-size:12px;color:var(--muted)}th:first-child,td:first-child{text-align:left}tr.focus{background:#edf8f6;font-weight:600}.limit{color:#84552c}.notes{font-size:14px;color:var(--muted)}.notes li{margin:8px 0}.links{display:flex;gap:20px;flex-wrap:wrap}code{font-size:.88em;background:#eef2f4;border-radius:3px;padding:2px 4px}footer{margin-top:30px;font-size:13px;color:var(--muted)}
@media(max-width:720px){main{padding:24px 14px}.panel{padding:17px}.stats{grid-template-columns:1fr 1fr;gap:20px}.plots{grid-template-columns:1fr;gap:8px}.barline{grid-template-columns:130px 1fr 65px}}
</style>
<main>
<header><div class="eyebrow">Эксперимент · openai/math · работа №128</div>
<h1>Быстрые срезы из общей надстроки.<br>Что это даёт на практике?</h1>
<p class="lead" id="lead"></p>
<p class="muted" id="environment"></p></header>
<section class="panel"><div class="selector"><label for="dataset"><b>Набор данных</b></label><select id="dataset"></select></div>
<p id="description" class="muted"></p><div class="stats" id="stats"></div>
<div class="plots"><div class="plot"><h3>Размер всего архива, байт · меньше лучше</h3><div id="sizeplot"></div></div><div class="plot"><h3>Чтение одного ID, мкс · меньше лучше</h3><div id="readplot"></div></div></div>
<div class="scroll"><table><thead><tr><th>Метод</th><th>Архив, Б</th><th>Упаковка, мс</th><th>Открытие, мкс</th><th>Один ID, мкс</th><th>Все строки, мс</th></tr></thead><tbody id="rows"></tbody></table></div>
<p class="notes" id="takeaway"></p></section>
<section class="panel"><h2>Как читать результаты</h2><ul class="notes">
<li>Размер включает заголовок, данные и весь индекс, включая возврат исходных ID после сортировки. Ничего не вынесено во внешнюю базу.</li>
<li>Архив уже в RAM. Кэша декодированных блоков нет: Zstd распаковывает блок при каждом запросе. С прогретым кэшем распакованных данных сравнение изменится и потребует больше памяти.</li>
<li>Полное чтение декодирует каждый блок один раз и возвращает строки в исходном порядке. Поэтому ускорение отдельного ID не означает такое же ускорение сканирования всего набора.</li>
<li id="repetitions"></li>
<li>Это сравнение реализаций: №128 и префиксное сжатие написаны на Python, Zstd использует нативный код. Дисковый ввод-вывод и пиковая память не измерялись.</li>
<li id="limits"></li>
</ul></section>
<section class="panel"><h2>Где имеет смысл продолжать</h2>
<p>Небольшие неизменяемые наборы перекрывающихся фрагментов, которые собираются редко и читаются по одному ID много раз. Например, таблица фрагментов текста или бинарного протокола с явно измеренными перекрытиями.</p>
<p>Для каталожных URL и подписей разумнее начать с Zstandard, а для быстрых прямых срезов — с обычного хранения или удаления дублей. Проверенный прототип №128 не показал здесь основания для замены.</p>
<p class="notes">Взята конструкция разделов 2–7 статьи: счётчики, периодические слои, соединение групп и цикл Эйлера. Python-перенос не формально верифицирован; Lean здесь не компилировался. Малые точные проверки и 2 000 стресс-примеров прошли, но стресс-набор не покрывает все редкие ветви соединения запросов и циклов. Теорема о надстроке не гарантирует выигрыш у компрессоров.</p>
</section>
<section class="panel"><h2>Файлы эксперимента</h2><div class="links"><a href="results.csv">Таблица CSV</a><a href="results.json">Все замеры JSON</a><a href="report.md">Текстовый отчёт</a><a href="../../README.md">Запуск и устройство</a></div><p class="notes">Исходные наборы, трассы и архивы лежат в подпапках выбранного набора. Всё можно проверить и повторить локально.</p></section>
<footer>Источник: <a href="https://github.com/openai/math/tree/fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb/preprints/A-Polynomial-Time-2-Approximation-for-Shortest-Common-Superstring-September-24-2026">A Polynomial-Time 2-Approximation for Shortest Common Superstring</a> · commit fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb</footer>
</main><script id="data" type="application/json">__DATA__</script>
<script>
const data=JSON.parse(document.getElementById('data').textContent);
const names=__LABELS__, order=Object.keys(names), fmt=(v,n=2)=>v.toLocaleString('ru-RU',{maximumFractionDigits:n,minimumFractionDigits:n});
const sel=document.getElementById('dataset');
for(const d of data.datasets){const o=document.createElement('option');o.value=d.id;o.textContent=d.title;sel.appendChild(o)}
document.getElementById('environment').textContent=`${data.datasets.length} наборов · Python ${data.environment.python.split(' ')[0]} · Zstd ${data.environment.zstd_version} · ${data.environment.timestamp_utc.slice(0,10)} · ${data.environment.cpu_name||data.environment.processor}`;
const completed=data.rows.filter(r=>r.method==='paper128'&&r.status==='ok');
const wins=completed.filter(p=>{const z=data.rows.find(r=>r.dataset===p.dataset&&r.method==='zstd_blocks'&&r.status==='ok');return z&&p.total_bytes<z.total_bytes&&p.random_us<z.random_us}).length;
document.getElementById('lead').textContent=`№128 сэкономил место относительно блочного Zstandard и ускорил чтение одного ID на ${wins} из ${completed.length} завершённых наборов. В этом эксперименте выигрыш пришёлся на данные с сильными перекрытиями. Для обычных URL и коротких подписей преимущества по размеру не получилось.`;
document.getElementById('repetitions').textContent=`Упаковка: медиана ${data.settings.pack_repeats} замеров; остальные операции: медиана ${data.settings.read_repeats}. У каждой операции отдельный прогрев и серии вызовов. Трасса ${fmt(data.settings.queries,0)} ID одинакова для всех методов.`;
document.getElementById('limits').textContent=`Лимиты №128: ${fmt(data.settings.max_vertices,0)} вершин-подстрок и кооперативный бюджет ${data.settings.max_paper_seconds} с на упаковку. Ошибка лимита не заменяется другим алгоритмом.`;
const element=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e};
function plot(id,rows,key,digits){const target=document.getElementById(id);target.replaceChildren();const max=Math.max(...rows.filter(r=>r.status==='ok').map(r=>r[key]));for(const r of rows){const line=element('div',undefined,'barline');line.append(element('span',names[r.method]));const track=element('div',undefined,'track');if(r.status==='ok'){const bar=element('div',undefined,'bar'+(r.method==='paper128'?' paper':r.method.startsWith('zstd')?' zstd':''));bar.style.width=(r[key]/max*100)+'%';track.append(bar)}line.append(track,element('span',r.status==='ok'?fmt(r[key],digits):'лимит','barvalue'));target.append(line)}}
function render(){const d=data.datasets.find(d=>d.id===sel.value), rows=data.rows.filter(r=>r.dataset===d.id).sort((a,b)=>order.indexOf(a.method)-order.indexOf(b.method)), get=m=>rows.find(r=>r.method===m&&r.status==='ok');
document.getElementById('description').textContent=`${d.description} ${d.count} строк; ${d.unique_count} уникальных; ${fmt(d.raw_bytes,0)} байт исходного текста. ${d.kind==='synthetic'?'Синтетический набор.':'Публичные имена стандартной библиотеки.'}`;
const p=get('paper128'), raw=get('plain'), z=get('zstd_blocks'), stats=document.getElementById('stats');stats.replaceChildren();
const values=p&&raw&&z?[[fmt(Math.abs(1-p.total_bytes/raw.total_bytes)*100,1)+'%','архив '+(p.total_bytes<=raw.total_bytes?'меньше':'больше')+' обычного',p.total_bytes>raw.total_bytes],[fmt(Math.abs(1-p.total_bytes/z.total_bytes)*100,1)+'%','архив '+(p.total_bytes<=z.total_bytes?'меньше':'больше')+' Zstd-блоков',p.total_bytes>z.total_bytes],[fmt(z.random_us/p.random_us,1)+'×','ускорение одного ID к Zstd-блокам'],[fmt(p.pack_ms,1)+' мс','упаковка №128']]:[['Лимит','№128 не завершил упаковку'],[fmt(d.raw_bytes,0)+' Б','исходные данные']];
for(const [v,label,bad]of values){const block=element('div',undefined,'stat'+(bad?' bad':''));block.append(element('div',v,'value'),element('div',label,'label'));stats.append(block)}
plot('sizeplot',rows,'total_bytes',0);plot('readplot',rows,'random_us',3);const body=document.getElementById('rows');body.replaceChildren();
for(const r of rows){const tr=element('tr',undefined,r.method==='paper128'?'focus':'');tr.append(element('td',names[r.method]));if(r.status==='ok'){for(const [key,n]of [['total_bytes',0],['pack_ms',3],['open_us',3],['random_us',3],['full_read_ms',3]])tr.append(element('td',fmt(r[key],n)))}else{const td=element('td',r.reason,'limit');td.colSpan=5;tr.append(td)}body.append(tr)}
let note='Превышение ограничения относится к этому Python-прототипу и выбранным ресурсным лимитам.';
if(p&&z){const saved=z.random_us-p.random_us;note=p.total_bytes<z.total_bytes?'У №128 есть выигрыш относительно блочного Zstd по размеру и прямому чтению. ':'У №128 нет выигрыша по размеру относительно блочного Zstd. ';if(saved>0&&p.pack_ms>z.pack_ms){const calls=(p.pack_ms-z.pack_ms)*1000/saved;note+=`Дополнительная стоимость упаковки окупается по сумме измеренного времени упаковки и чтения примерно через ${fmt(calls,0)} отдельных чтений на одну сборку при этой политике кэша. Это оценка, не замер рабочего сервиса.`}}
document.getElementById('takeaway').textContent=note;
}
sel.addEventListener('change',render);render();
</script></html>'''


def markdown(data):
    lines = ["# Практическое сравнение упаковщиков строк", "",
             "Размеры включают заголовок и полный индекс. Архивы находятся в RAM; кэша декодированных блоков нет.", "",
             f"Медианы: упаковка — {data['settings']['pack_repeats']} повтора, чтение — {data['settings']['read_repeats']}. `мкс/ID` — время одного запроса из общей трассы {data['settings']['queries']} ID.", ""]
    for dataset in data["datasets"]:
        lines += [f"## {dataset['title']}", "", dataset["description"], "",
                  f"Строк: {dataset['count']}; уникальных: {dataset['unique_count']}; исходные байты: {dataset['raw_bytes']}.", "",
                  "| Метод | Архив, Б | Упаковка, мс | Открытие, мкс | мкс/ID | Все строки, мс |",
                  "|---|---:|---:|---:|---:|---:|"]
        rows = sorted((r for r in data["rows"] if r["dataset"] == dataset["id"]),
                      key=lambda r:list(LABELS).index(r["method"]))
        for r in rows:
            if r["status"] == "ok":
                lines.append(f"| {LABELS[r['method']]} | {r['total_bytes']} | {r['pack_ms']:.3f} | {r['open_us']:.3f} | {r['random_us']:.3f} | {r['full_read_ms']:.3f} |")
            else:
                lines.append(f"| {LABELS[r['method']]} | Лимит: {r['reason']} | — | — | — | — |")
        lines += ["", f"SHA-256 входа: `{dataset['sha256']}`", ""]
    lines += ["## Условия и воспроизведение", "",
              "Полная методика, устройство формата, границы переноса и команды — в [README](../../README.md).",
              "Все исходные замеры — [results.json](results.json), таблица — [results.csv](results.csv).",
              "Python-перенос не формально верифицирован. Lean-проект не компилировался.", "",
              "```json", json.dumps(data["environment"],ensure_ascii=False,indent=2), "```", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", type=Path)
    args = parser.parse_args()
    data = json.loads(args.results.read_text(encoding="utf-8"))
    embedded = json.dumps(data,ensure_ascii=False).replace("<","\\u003c")
    page = HTML.replace("__DATA__",embedded).replace("__LABELS__",json.dumps(LABELS,ensure_ascii=False))
    args.results.with_name("report.html").write_text(page,encoding="utf-8")
    args.results.with_name("report.md").write_text(markdown(data),encoding="utf-8")
    print(args.results.with_name("report.html").resolve())


if __name__ == "__main__":
    main()
