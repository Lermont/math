"""Reproducible paired quality comparisons and resource report."""
from __future__ import annotations

import hashlib
import html
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score

from .context_download import OUT,ROOT
from .context_run import METHODS,SEEDS

LABELS={'core':'Граф без контекста','rules':'Простые правила','graph':'NetworkX + контекст','directed':'NetworkX + направление','paper':'NetworkX + №131','edge':'NetworkX + обычные перестановки'}


def dependence_groups(records):
    parent=list(range(len(records)))
    def find(i):
        while parent[i]!=i:
            parent[i]=parent[parent[i]];i=parent[i]
        return i
    seen={}
    for i,r in enumerate(records):
        for kind in ('nodes','transactions'):
            for v in r[kind]:
                key=(kind,v)
                if key in seen:parent[find(i)]=find(seen[key])
                else:seen[key]=i
    roots=[find(i) for i in range(len(records))]
    return [np.flatnonzero(np.asarray(roots)==g) for g in sorted(set(roots))]


def bootstrap(y,scores,groups,draws=1000):
    pairs=[('paper','graph'),('paper','directed'),('paper','edge'),('graph','core'),('directed','core')]
    actual={f'{a}-{b}':float(np.mean([average_precision_score(y,x)-average_precision_score(y,z) for x,z in zip(scores[a],scores[b])])) for a,b in pairs}
    rng=np.random.default_rng(1312027);positive=np.flatnonzero(y==1);negative=np.flatnonzero(y==0)
    result={'draws':draws,'paired_mean_across_model_seeds':True,'differences':{name:{'delta_ap':v} for name,v in actual.items()}}
    for mode in ('stratified_rows','context_components'):
        values={name:[] for name in actual}
        for _ in range(draws):
            ix=np.r_[rng.choice(positive,len(positive)),rng.choice(negative,len(negative))] if mode=='stratified_rows' else np.concatenate([groups[i] for i in rng.integers(len(groups),size=len(groups))])
            if len(np.unique(y[ix]))<2:continue
            aps={m:np.mean([average_precision_score(y[ix],s[ix]) for s in scores[m]]) for m in set(v for p in pairs for v in p)}
            for a,b in pairs:values[f'{a}-{b}'].append(aps[a]-aps[b])
        for name,v in values.items():result['differences'][name][mode+'_ci95']=list(map(float,np.quantile(v,[.025,.975])))
    result['test_dependence_groups']=len(groups)
    result['largest_test_group']=max(map(len,groups))
    return result


def run():
    metadata=json.loads((OUT/'run-metadata.json').read_text())
    audit=json.loads((OUT/'data_audit.json').read_text());acq=json.loads((OUT/'acquisition.json').read_text())
    records=json.loads((OUT/'sample.json').read_text())
    tests=[r for r in records if r['split']=='test']
    bymethod={m:[json.loads((OUT/f'seed{s}/{m}.json').read_text()) for s in SEEDS] for m in METHODS}
    scores={};rows=[]
    for m,runs in bymethod.items():
        assert all(r['sample_sha256']==audit['sample_sha256'] for r in runs)
        frames=[pd.read_csv(OUT/f'seed{s}/{m}-predictions.csv') for s in SEEDS]
        assert all(f.id.tolist()==[r['id'] for r in tests] and f.y.tolist()==[r['y'] for r in tests] for f in frames)
        scores[m]=np.asarray([f.score.to_numpy() for f in frames])
        row={'method':m,'label':LABELS[m]}
        for metric in ('ap','roc_auc','precision_at_100','recall_at_100','expected_true_at_100','recall_at_val_1pct_fpr','test_fpr'):
            row[metric]=float(np.mean([r['metrics'][metric] for r in runs]))
        row['ap_min']=min(r['metrics']['ap'] for r in runs);row['ap_max']=max(r['metrics']['ap'] for r in runs)
        for metric in ('total_seconds','test_total_seconds','peak_rss_mib','fit_seconds'):
            row[metric]=float(np.median([r[metric] for r in runs]))
        rows.append(row)
    summary=pd.DataFrame(rows).set_index('method');summary.to_csv(OUT/'summary.csv')
    y=np.asarray([r['y'] for r in tests])
    unc=bootstrap(y,scores,dependence_groups(tests))
    (OUT/'uncertainty.json').write_text(json.dumps(unc,indent=2))
    # Paired models must start with exactly the same observed features.
    checks={'feature_parity':True,'core_feature_parity':True,'no_cross_split_overlap':not any(v for d in audit['overlaps'].values() for v in d.values()),'complete_background_crc_verified':acq['crc_verified'],'sample_hash_match':hashlib.sha256((OUT/'sample.json').read_bytes()).hexdigest()==audit['sample_sha256']}
    for seed in SEEDS:
        g=np.load(OUT/f'seed{seed}/graph-features.npz')['x']
        c=np.load(OUT/f'seed{seed}/core-features.npz')['x']
        np.testing.assert_array_equal(c,g[:,:c.shape[1]])
        for method in ('directed','paper','edge'):
            other=np.load(OUT/f'seed{seed}/{method}-features.npz')['x']
            np.testing.assert_array_equal(g,other[:,:g.shape[1]])
    (OUT/'checks.json').write_text(json.dumps(checks,indent=2))
    colors=['#91a1ad','#91a1ad','#278177','#789357','#316bc5','#8470a0']
    fig,axes=plt.subplots(1,3,figsize=(15,5.3),gridspec_kw={'width_ratios':[1.35,1,1]})
    yy=np.arange(len(METHODS))
    for ax,col,title in zip(axes,['ap','test_total_seconds','peak_rss_mib'],['Качество: Average Precision, %','Чтение теста: признаки + прогноз, с','Пиковая память процесса, MiB']):
        values=summary.loc[METHODS,col].to_numpy()*(100 if col=='ap' else 1)
        ax.barh(yy,values,color=colors,height=.62)
        ax.set_yticks(yy,[LABELS[m] for m in METHODS] if ax is axes[0] else [])
        ax.invert_yaxis();ax.set_title(title,fontsize=10,pad=14)
        ax.spines[['top','right','left']].set_visible(False);ax.tick_params(axis='y',length=0)
        ax.grid(axis='x',alpha=.18);ax.set_axisbelow(True)
        ax.set_xlim(0,max(values)*1.27)
        for y0,v in zip(yy,values):ax.text(v+max(values)*.025,y0,f'{v:.2f}' if col!='peak_rss_mib' else f'{v:.0f}',va='center',fontsize=9)
        if col=='ap':ax.axvline(y.mean()*100,color='#b34e3e',ls='--',lw=1,label='Доля подозрительных');ax.legend(loc='lower right',fontsize=8)
    fig.suptitle(f'Elliptic2: {len(records):,} подграфов, реальный контекст соседей'.replace(',',' '),fontsize=16,x=.53,y=.99)
    fig.text(.33,.015,'Качество — среднее 3 запусков; время и память — медиана. CPU, 1 поток. Загрузка данных отдельно.',fontsize=9,color='#555555')
    fig.tight_layout(rect=[0,.045,1,.94]);fig.savefig(OUT/'comparison.png',dpi=160);fig.savefig(OUT/'comparison.svg');plt.close(fig)
    delta=unc['differences']['paper-graph'];ci=delta['context_components_ci95']
    supported=ci[0]>0
    conclusion=('В этой выборке №131 улучшил AP относительно NetworkX; это локальный результат, требующий независимой проверки.' if supported else 'Практический выигрыш №131 по качеству относительно NetworkX на этой выборке не подтверждён.')
    ntest=len(tests);positive=int(y.sum());contextstats=pd.read_csv(OUT/'contexts.csv')
    md=[f'# Elliptic2 с соседними транзакциями: малый эксперимент','',conclusion,'',
        f'Выборка: **{len(records):,} новых подграфов**, без пересечения с прошлыми 20 000; train/validation/test — '+ '/'.join(str(audit['split'][s]['count']) for s in ('train','val','test'))+f'. В тесте {positive} подозрительных из {ntest} ({y.mean():.2%}). Метка suspicious — исходная аннотация набора, не подтверждённый факт преступления.',
        '', '## Сравнение', '', '| Метод | AP, % ↑ | ROC AUC | Подозрительных в первых 100 | Полный прогон, с ↓ | Тест, с ↓ | Пик RAM, MiB ↓ |','|---|---:|---:|---:|---:|---:|---:|']
    for m,row in summary.iterrows():md.append(f"| {row['label']} | {row.ap*100:.2f} | {row.roc_auc:.3f} | {row.expected_true_at_100:.2f} | {row.total_seconds:.2f} | {row.test_total_seconds:.2f} | {row.peak_rss_mib:.1f} |")
    md += ['',f'Постоянный прогноз: AP = **{y.mean()*100:.2f}%**. AP — average precision; выше лучше. Качество усреднено по трём seeds, время/RAM — медианы. «Тест» включает извлечение признаков и прогноз всех {ntest} подграфов. Полный прогон начинается после импорта библиотек и включает чтение подготовленного JSON, признаки всех частей, обучение, прогноз и сохранение артефактов. Пиковая память включает интерпретатор и библиотеки; это не размер только модели.',
        '',f'![Сравнение](comparison.png)','', '## Парная неопределённость','', '| Сравнение AP | Разница, п.п. | 95% интервал, по подграфам | 95% интервал, по группам общего контекста |','|---|---:|---:|---:|']
    for pair,d in unc['differences'].items():
        a,b=pair.split('-');lo,hi=d['stratified_rows_ci95'];gl,gh=d['context_components_ci95']
        md.append(f'| {LABELS[a]} − {LABELS[b]} | {d["delta_ap"]*100:+.2f} | [{lo*100:+.2f}; {hi*100:+.2f}] | [{gl*100:+.2f}; {gh*100:+.2f}] |')
    md += ['',f'1 000 парных bootstrap-повторов; средняя разница по seeds в каждом повторе. Группы объединяют тестовые подграфы с общими узлами или транзакциями: {unc["test_dependence_groups"]} групп, наибольшая — {unc["largest_test_group"]} подграфов. Интервалы условны на выбранные обучение и разбиение; они не измеряют весь разброс при переобучении на новых выборках.',
        '', '## Какой контекст добавлен','',f'Полностью прочитан официальный `background_edges.csv` Elliptic2 v1: **{acq["rows_scanned"]:,} строк**, CRC ZIP проверен, SHA-256 исходного CSV сохранён. Выгружено по сети {acq["archive_bytes"]/1e9:.2f} GB сжатых данных; {acq["uncompressed_bytes"]/1e9:.2f} GB прочитаны потоком. Сохранены {acq["incident_rows_retained"]:,} строк, инцидентных {acq["selected_core_nodes"]:,} выбранным узлам ядра. Получение заняло {acq["elapsed_seconds"]/60:.1f} мин, пик процесса {acq["peak_rss_mib"]:.0f} MiB. Подготовка выборки: {audit["elapsed_seconds"]:.1f} с, {audit["peak_rss_mib"]:.0f} MiB.',
        '', f'У {audit["with_external_context"]} из {len(records)} подграфов остался внешний контекст. Медиана добавленных соседей: {contextstats.kept_neighbors.median():.0f}; максимум — 32. Ограничение сработало у {audit["capped_subgraphs"]} подграфов. Соседи выбраны детерминированным хешем без использования классов.',
        '',f'Перед выбором соседей удалены {audit["shared_external_nodes_purged"]:,} внешних узлов, встречавшихся в нескольких частях, и внешние вхождения {audit["shared_transaction_ids_context_purged"]:,} общих transaction IDs. Узлы других размеченных ядер также исключены. После подготовки **нет пересечений узлов и transaction IDs между train/validation/test**. Это меняет распределение контекста и делает пилот более ограниченным, чем работа с общим графом.',
        '', 'Используются реальные входящие и исходящие связи на один шаг от ядра. Связи между двумя внешними соседями не извлекались: это граф инцидентных рёбер, а не полный индуцированный ego-граф. Направление и кратность сохраняются в дополнительном baseline; №131 и основной NetworkX используют простой неориентированный граф. Анонимные числовые атрибуты платежей не используются: здесь проверяется только графовая структура.',
        '', '## Что именно сравнивалось','',
        'NetworkX вычисляет PageRank, Louvain, k-core, треугольники, циклы, мосты, компоненты и признаки связи ядра с соседями. Классификатор — ExtraTrees (200 деревьев, minimum leaf 5, balanced, один поток); простые правила — дерево глубины 3. В paired-методах исходные признаки идентичны, что проверено по сохранённым матрицам. Это сравнение лёгких готовых графовых алгоритмов, не воспроизведение GNN/GLASS/RevClassify из публикаций.',
        '', '№131 даёт ядро ленивой цепи перестановок с сохранением степеней. Здесь к NetworkX добавлены остатки и эмпирические хвосты относительно 32 состояний этой цепи: 512 шагов до наблюдений и 64 между ними, всего 2 560 предложений для активного графа, включая отклонения. Для обычного контроля используются те же признаки и бюджет с симметричным предложением пары рёбер. Короткие цепи — эвристика: гарантия перемешивания из теоремы к этому бюджету не применяется.',
        '', '| Цепь | Замороженных графов | Предложений | Принятых, среднее | Различных состояний, среднее на активный граф |','|---|---:|---:|---:|---:|']
    for m in ('paper','edge'):
        ds=[r['diagnostics'] for r in bymethod[m]]
        md.append(f'| {LABELS[m]} | {ds[0]["frozen"]} | {ds[0]["proposals"]:,} | {np.mean([d["accepted"] for d in ds]):,.0f} | {np.mean([d["mean_distinct_states_active"] for d in ds]):.2f} |')
    md += ['', '## Порог тревоги','', '| Метод | Recall при пороге validation FPR ≤ 1% | Фактический FPR на тесте |','|---|---:|---:|']
    for m,row in summary.iterrows():md.append(f'| {row["label"]} | {row.recall_at_val_1pct_fpr:.2%} | {row.test_fpr:.2%} |')
    md += ['', 'Порог выбран только на validation. Тест не использовался для выбора признаков, параметров или числа шагов. Три seeds отражают вариацию модели и MCMC на одном фиксированном разбиении. Нет временного holdout: фоновой контекст охватывает доступный период набора и не доказывает пригодность для прогноза будущих транзакций.',
        '', '## Воспроизведение и источники','',
        '- [План](../../graph131/CONTEXT_PLAN.md), [инструкция запуска](../../graph131/CONTEXT_README.md).',
        '- [Полная таблица](summary.csv), [интервалы](uncertainty.json), [аудит данных](data_audit.json), [получение данных](acquisition.json), [проверки](checks.json), [hashes и параметры](run-metadata.json).',
        '- [Официальная Elliptic2 v1](https://www.kaggle.com/datasets/ellipticco/elliptic2-data-set), [статья авторов](https://arxiv.org/abs/2404.19109). Данные хранятся локально; лицензия набора CC BY-NC-ND 4.0, отдельно от кода.',
        '- [№131, фиксированный commit](https://github.com/openai/math/blob/fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb/lean/docs/131.md).',
        '',f'Среда: {bymethod["graph"][0]["versions"]["platform"]}; Python {sys_version(bymethod)}, NetworkX {bymethod["graph"][0]["versions"]["networkx"]}, scikit-learn {bymethod["graph"][0]["versions"]["scikit_learn"]}. CPU Intel Core Ultra 7 255H; CPU-измерения, GPU не используется.']
    (OUT/'report.md').write_text('\n'.join(md),encoding='utf-8')
    # A standalone reviewable HTML artifact; markdown is the detailed source.
    table=summary[['label','ap','roc_auc','total_seconds','test_total_seconds','peak_rss_mib']].copy()
    table.columns=['Метод','AP','ROC AUC','Весь прогон, с','Тест, с','Пик MiB']
    for c in table.columns[1:]:table[c]=table[c].map(lambda v:f'{v:.3f}')
    svg=(OUT/'comparison.svg').read_text(encoding='utf-8')
    doc=f'''<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Elliptic2: эксперимент с контекстом</title><style>body{{font:17px/1.55 system-ui,sans-serif;background:#f5f4ef;color:#192933;margin:0}}main{{max-width:1180px;margin:auto;padding:44px 28px}}h1{{font-size:36px;line-height:1.15}}.lead{{font-size:23px;max-width:1000px}}.card{{background:white;border:1px solid #e4e3db;border-radius:14px;padding:25px;margin:24px 0}}svg{{width:100%;height:auto}}table{{border-collapse:collapse;width:100%;font-size:14px}}td,th{{padding:10px;text-align:left;border-bottom:1px solid #e5e7e9}}small{{color:#53636d}}a{{color:#205f9f}}</style><main><small>ЛОКАЛЬНЫЙ ЭКСПЕРИМЕНТ · ELLIPTIC2 · {len(records):,} ПОДГРАФОВ</small><h1>Контекст соседей и переключения №131</h1><p class="lead">{html.escape(conclusion)}</p><p>Тест: {ntest} подграфов, {positive} подозрительных. Сравнение трёх запусков на одинаковых данных.</p><div class="card">{svg}</div><div class="card">{table.to_html(index=False,escape=True,border=0)}<p><small>AP и ROC AUC: больше лучше. Время и память: меньше лучше. Время включает вычисление признаков, подготовка исходных данных считается отдельно.</small></p></div><div class="card"><h2>Сколько даёт №131</h2><p>Разница AP относительно NetworkX: <b>{delta['delta_ap']*100:+.2f} п.п.</b>; 95% интервал по группам контекста: [{ci[0]*100:+.2f}; {ci[1]*100:+.2f}] п.п.</p><p>Соседи добавлены у {audit['with_external_context']} из {len(records)} подграфов. Между train, validation и test нет общих узлов и transaction IDs. Не более 32 внешних соседей; только рёбра, касающиеся ядра.</p><p>Полный потоковый просмотр исходного графа: {acq['elapsed_seconds']/60:.1f} мин и {acq['peak_rss_mib']:.0f} MiB. Этот общий расход не включён в таблицу методов.</p></div><p>Короткая цепь перестановок не имеет сертификата перемешивания. Исследуются структурные признаки; это не оценка всех GNN и не проверка на будущих данных.</p><p><a href="report.md">Подробный отчёт и ограничения</a> · <a href="summary.csv">Таблица CSV</a> · <a href="uncertainty.json">Парные интервалы</a> · <a href="data_audit.json">Аудит данных</a></p></main></html>'''
    (OUT/'report.html').write_text(doc,encoding='utf-8')
    print(summary.to_string());print(json.dumps(unc,indent=2));print(conclusion)


def sys_version(bymethod):return bymethod['graph'][0]['versions']['python'].split()[0]


if __name__=='__main__':run()
