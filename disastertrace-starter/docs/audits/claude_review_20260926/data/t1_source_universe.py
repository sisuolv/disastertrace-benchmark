"""Task 1+2: full TAF source universe per checkpoint vs artifact; revision dynamics.
Reuses builder _load_products (identical parse), independent selection logic.
Run: .venv/bin/python -B /tmp/dt_review/agent_data/t1_source_universe.py"""
import json, sys
from collections import Counter
sys.path.insert(0, '/tmp/dt_review/agent_data')
from common import *

g = json.load(open(ART / 'G1_DEV_EPISODES_V3.json'))
sc = json.load(open(ART / 'REAL_DEV_DETERMINISTIC_SCORE.json'))
oc = json.load(open(ART / 'REAL_DEV_ASOS_OUTCOMES.json'))
y = {r['episode_id']: r['outcome_y'] for r in oc['rows']}
prods = {}
for s in STATIONS:
    prods[s] = []
    for m in MONTHS:
        prods[s] += load_taf_products(s, m)
    prods[s].sort(key=lambda p: (p['issued_at'], p['source_id']))
art_prob = {(r['episode_id'], r['checkpoint_id']): r for r in sc['rows'] if r['method'] == 'earliest_source'}

rows = []
print('episode | cp | as_of | artifact n_vis,p | covering-available products (issue,AMD?,p) | latest-covering p | any-overlap-available n')
for e in g['episodes']:
    s, t0, t1 = e['station'], e['target_start'], e['target_end']
    for cp in e['checkpoints']:
        a = cp['as_of']
        avail = [p for p in prods[s] if p['available_at'] <= a]
        cover = [p for p in avail if p['valid_start'] <= t0 and p['valid_end'] >= t1]
        overlap = [p for p in avail if p['valid_start'] < t1 and p['valid_end'] > t0]
        det = []
        for p in cover:
            pr, lo = taf_prob(p['content']['periods'], t0, t1)
            det.append((fmt(p['issued_at'])[5:], p['source_id'][-3:], p['relation_status'][:3], pr, lo))
        latest = cover[-1] if cover else None
        lp = taf_prob(latest['content']['periods'], t0, t1)[0] if latest else None
        ar = art_prob[(e['episode_id'], cp['checkpoint_id'])]
        # reproduce artifact prob from raw product (for the one visible source)
        rep = None
        if ar['selected_query_id']:
            p0 = next(p for p in prods[s] if p['source_id'] == ar['selected_query_id'])
            rep = taf_prob(p0['content']['periods'], t0, t1)[0]
        rows.append(dict(ep=e['episode_id'], cp=cp['checkpoint_id'], as_of=a, n_art=ar['visible_source_count'], p_art=ar['probability'],
                         p_rep=rep, n_cover=len(cover), n_overlap=len(overlap), latest=latest['source_id'] if latest else None,
                         p_latest=lp, y=y[e['episode_id']], cover=[d[0] + ' ' + d[1] for d in det], cover_p=[d[3] for d in det]))
        print(e['episode_id'][8:], cp['checkpoint_id'], fmt(a)[11:], f"{ar['visible_source_count']},{ar['probability']}", det, lp, len(overlap))

print('\nartifact-vs-reproduced prob mismatches (source cells):', sum(1 for r in rows if r['p_rep'] is not None and r['p_rep'] != r['p_art']))
print('n_cover distribution:', Counter(r['n_cover'] for r in rows))
print('n_art distribution:', Counter(r['n_art'] for r in rows))
print('cells where artifact had 0 sources but >=1 covering product available:', [(r['ep'][8:], r['cp'], r['n_cover'], r['latest'], r['p_latest']) for r in rows if r['n_art'] == 0])
# do covering products at a checkpoint disagree on p?
print('cells where available covering products disagree on p:', sum(1 for r in rows if len(set(x for x in r['cover_p'] if x is not None)) > 1))
print('cells where latest-covering p != artifact p (artifact source cells):', [(r['ep'][8:], r['cp'], r['p_art'], r['p_latest']) for r in rows if r['n_art'] and r['p_latest'] != r['p_art']])

# Brier impact of filling fallback cells with latest covering product
def brier(key):
    return sum((r[key] - r['y']) ** 2 for r in rows) / len(rows)
for r in rows:
    r['p_fill'] = r['p_art'] if r['n_art'] else (r['p_latest'] if r['p_latest'] is not None else 0.5)
    r['p_latest_all'] = r['p_latest'] if r['p_latest'] is not None else 0.5
print('mean Brier artifact TAF arm = %.5f ; with 7 fallbacks filled by latest in-force TAF = %.5f ; always-latest-covering = %.5f' % (brier('p_art'), brier('p_fill'), brier('p_latest_all')))

# Task 2: revision dynamics
print('\n== Task 2: new TAF availability between checkpoints')
cnt_any = cnt_cov = 0
for e in g['episodes']:
    s, t0, t1 = e['station'], e['target_start'], e['target_end']
    a60, a20 = e['checkpoints'][0]['as_of'], e['checkpoints'][2]['as_of']
    new = [p for p in prods[s] if a60 < p['available_at'] <= a20]
    newc = [p for p in new if p['valid_start'] <= t0 and p['valid_end'] >= t1]
    newo = [p for p in new if p['valid_start'] < t1 and p['valid_end'] > t0]
    second = [p for p in prods[s] if p['source_id'] == e['source_ids'][1]][0]
    cnt_any += bool(new); cnt_cov += bool(newc)
    print(e['episode_id'][8:], 'new in (T-60,T-20]:', [(fmt(p['issued_at'])[11:], p['source_id'][-3:]) for p in new], 'covering:', len(newc), 'overlap:', len(newo),
          '| 2nd src issued', fmt(second['issued_at'])[11:], 'avail-target_start = %+d s' % ((second['available_at'] - t0) // 1_000_000),
          '| valid_start==target_start', second['valid_start'] == t0)
print('episodes with ANY new TAF avail in (T-60,T-20]:', cnt_any, '; covering target:', cnt_cov)
json.dump(rows, open('/tmp/dt_review/agent_data/t1_rows.json', 'w'), indent=1, default=str)
