"""Task 4: Brier reproduction, baselines, dev-month climatology, episode-clustered bootstrap.
Run after t1 (needs t1_rows.json): .venv/bin/python -B /tmp/dt_review/agent_data/t4_stats.py"""
import json, sys
import numpy as np
from collections import defaultdict
sys.path.insert(0, '/tmp/dt_review/agent_data')
from common import *

sc = json.load(open(ART / 'REAL_DEV_DETERMINISTIC_SCORE.json'))
rows = sc['rows']
eps = sorted({r['episode_id'] for r in rows})
cps = ['T-60', 'T-40', 'T-20']
P = defaultdict(dict); Y = {}
for r in rows:
    P[r['method']][(r['episode_id'], r['checkpoint_id'])] = r['probability']; Y[r['episode_id']] = r['outcome_y']
print('published summary:', {m: round(v['mean_brier'], 6) for m, v in sc['summary'].items()}, 'active-fixed', sc['active_minus_fixed'], 'active-best', sc['active_minus_best_nonactive'])
# identical selections across arms?
sel = defaultdict(set)
for r in rows:
    if r['method'] != 'fixed':
        sel[(r['episode_id'], r['checkpoint_id'])].add(r['selected_query_id'])
print('cells where the 3 selector arms picked different sources:', sum(len(v) > 1 for v in sel.values()))

# climatology from ALL hours of dev months (in-sample/dev), first obs in [HH:00,HH+1:00)
clim = {}; clim_any = {}
for s in STATIONS:
    byh = defaultdict(list)
    for m in MONTHS:
        for o in load_asos(s, m):
            byh[o['dt'].replace(minute=0)].append(o)
    first = [v[0]['m'] < THR for v in byh.values()]
    anyv = [any(o['m'] < THR for o in v) for v in byh.values()]
    clim[s] = float(np.mean(first)); clim_any[s] = float(np.mean(anyv))
    print(f'{s}: hourly windows with >=1 obs = {len(first)}, first-obs<5km = {sum(first)} ({clim[s]:.4f}), any-obs<5km = {sum(anyv)} ({clim_any[s]:.4f})')
t1 = {(r['ep'], r['cp']): r for r in json.load(open('/tmp/dt_review/agent_data/t1_rows.json'))}
st = {e: e.split('-')[2] for e in eps}
F = {
    'fixed_0.5': lambda e, c: 0.5,
    'taf_rule(published, =all 3 selector arms)': lambda e, c: P['active_age'][(e, c)],
    'taf_rule_inforce_fill (7 fallback cells -> latest in-force TAF)': lambda e, c: t1[(e, c)]['p_fill'],
    'const_0': lambda e, c: 0.0,
    'base_rate_2/24 (in-sample)': lambda e, c: 2 / 24,
    'station_climatology_dev (in-sample)': lambda e, c: clim['K' + st[e]] if not st[e].startswith('K') else clim[st[e]],
}
# per-episode mean Brier over its 3 checkpoints (cluster unit)
def ep_brier(f):
    return np.array([np.mean([(f(e, c) - Y[e]) ** 2 for c in cps]) for e in eps])
EB = {k: ep_brier(f) for k, f in F.items()}
print('\nmean Brier over 72 cells:')
for k, v in EB.items():
    print(f'  {k:62s} {v.mean():.5f}')
rng = np.random.default_rng(20260926)
idx = rng.integers(0, len(eps), size=(10000, len(eps)))
def ci(a, b):
    d = EB[a] - EB[b]; bs = d[idx].mean(axis=1)
    return d.mean(), np.percentile(bs, 2.5), np.percentile(bs, 97.5), (bs >= 0).mean()
T = 'taf_rule(published, =all 3 selector arms)'
for a, b in [(T, 'fixed_0.5'), (T, 'station_climatology_dev (in-sample)'), (T, 'const_0'), (T, 'base_rate_2/24 (in-sample)'),
             ('taf_rule_inforce_fill (7 fallback cells -> latest in-force TAF)', 'station_climatology_dev (in-sample)'),
             ('taf_rule_inforce_fill (7 fallback cells -> latest in-force TAF)', 'const_0')]:
    m, lo, hi, pge = ci(a, b)
    print(f'  {a[:40]:40s} - {b[:40]:40s}: {m:+.5f}  95% CI [{lo:+.5f}, {hi:+.5f}]  P(boot diff>=0)={pge:.3f}')
act = ep_brier(lambda e, c: P['active_age'][(e, c)]); best = min(['fixed', 'earliest_source', 'hash_source'], key=lambda m: np.mean([P[m][(e, c)] for e in eps for c in cps]))
bn = {m: ep_brier(lambda e, c, m=m: P[m][(e, c)]) for m in ['fixed', 'earliest_source', 'hash_source']}
bm = min(bn, key=lambda m: bn[m].mean())
d = act - bn[bm]; bs = d[idx].mean(axis=1)
print(f'  active - best non-active ({bm}): {d.mean():+.5f} CI [{np.percentile(bs,2.5):+.5f},{np.percentile(bs,97.5):+.5f}] (identically 0 in every resample: {np.all(bs==0)})')
# 2x2 at episode level using T-20 (published) and the source p
print('\n2x2 episode-level (TAF p at T-20, published):')
tab = defaultdict(int)
for e in eps:
    tab[(P['active_age'][(e, 'T-20')], Y[e])] += 1
for p in (0.8, 0.5, 0.2):
    print(f'  p={p}: y=1 {tab[(p,1)]:2d}  y=0 {tab[(p,0)]:2d}')
print('2x2 episode-level (in-force-filled, T-20):')
tab = defaultdict(int)
for e in eps:
    tab[(t1[(e, 'T-20')]['p_fill'], Y[e])] += 1
for p in (0.8, 0.5, 0.2):
    print(f'  p={p}: y=1 {tab[(p,1)]:2d}  y=0 {tab[(p,0)]:2d}')
json.dump({'clim_first': clim, 'clim_any': clim_any}, open('/tmp/dt_review/agent_data/t4_clim.json', 'w'), indent=1)
