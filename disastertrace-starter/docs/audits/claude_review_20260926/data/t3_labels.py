"""Task 3: independent ASOS re-parse of the 24 target windows (own CSV parser, not the binder).
Run: .venv/bin/python -B /tmp/dt_review/agent_data/t3_labels.py"""
import json, sys
sys.path.insert(0, '/tmp/dt_review/agent_data')
from common import *

g = json.load(open(ART / 'G1_DEV_EPISODES_V3.json'))
oc = {r['episode_id']: r for r in json.load(open(ART / 'REAL_DEV_ASOS_OUTCOMES.json'))['rows']}
import build_v18_dev_episodes as b
prods = {s: sorted(sum((load_taf_products(s, m) for m in MONTHS), []), key=lambda p: p['issued_at']) for s in STATIONS}
asos = {}
out = []
print('episode | window | pub first(y) | my first obs (t,m,type) y | any<5k | min m | n obs | routine-first y | TAF p(2nd src) | p(1st src)')
for e in g['episodes']:
    s, t0, t1 = e['station'], e['target_start'], e['target_end']
    mon = fmt(t0)[:7].replace('-', '')
    if (s, mon) not in asos:
        asos[(s, mon)] = load_asos(s, mon)
    obs = [r for r in asos[(s, mon)] if t0 <= r['t'] < t1]
    first = obs[0]
    rout = [r for r in obs if r['routine']]
    pub = oc[e['episode_id']]
    y_first = int(first['m'] < THR)
    y_any = int(any(r['m'] < THR for r in obs))
    y_rout = int(rout[0]['m'] < THR) if rout else None
    ok = (pub['observation_valid'] == first['t'] and abs(pub['observation_visibility_m'] - first['m']) < 1e-6 and pub['outcome_y'] == y_first)
    p2 = [p for p in prods[s] if p['source_id'] == e['source_ids'][1]][0]
    p1 = [p for p in prods[s] if p['source_id'] == e['source_ids'][0]][0]
    pp2 = taf_prob(p2['content']['periods'], t0, t1)
    pp1 = taf_prob(p1['content']['periods'], t0, t1)
    ppv = taf_prob_prevailing(p1['content']['periods'], t0, t1)
    out.append(dict(ep=e['episode_id'], station=s, t0=t0, y_pub=pub['outcome_y'], y_first=y_first, y_any=y_any, y_rout=y_rout,
                    min_m=min(r['m'] for r in obs), n=len(obs), match=ok, first_routine=first['routine'], first_ghcnh=first['ghcnh'],
                    p_src1=pp1[0], p_src1_prevailing=ppv[0], p_src2=pp2[0], rel2=p2['relation_status']))
    print(e['episode_id'][8:], fmt(t0)[11:], '-', fmt(t1)[11:], '|', fmt(pub['observation_valid'])[11:], round(pub['observation_visibility_m']), pub['outcome_y'], '|',
          fmt(first['t'])[11:], round(first['m']), 'R' if first['routine'] else ('G' if first['ghcnh'] else 'S'), y_first, '|', y_any, '|', round(min(r['m'] for r in obs)), '|', len(obs),
          '|', y_rout, '| src2', pp2[0], p2['relation_status'], '| src1', pp1[0], 'prevailing-only', ppv[0], '| match', ok)
print('\nall published labels reproduced:', all(r['match'] for r in out))
for k in ('y_first', 'y_any', 'y_rout'):
    print(k, 'positives =', sum(r[k] or 0 for r in out), '; flips vs published:', [r['ep'][8:] for r in out if r[k] != r['y_pub']])
print('first obs is routine METAR in', sum(r['first_routine'] for r in out), '/24 ; GHCNh-sourced:', sum(r['first_ghcnh'] for r in out))
print('episodes where 2nd (never-visible) src p != 1st src p:', [(r['ep'][8:], r['p_src1'], r['p_src2']) for r in out if r['p_src1'] != r['p_src2']])
print('episodes where prevailing-only p != any-group p (1st src):', [(r['ep'][8:], r['p_src1'], r['p_src1_prevailing']) for r in out if r['p_src1'] != r['p_src1_prevailing']])
print('relation_status of 2nd src:', [r['rel2'] for r in out])
json.dump(out, open('/tmp/dt_review/agent_data/t3_labels.json', 'w'), indent=1)
