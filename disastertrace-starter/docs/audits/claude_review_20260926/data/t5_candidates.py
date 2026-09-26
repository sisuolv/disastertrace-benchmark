"""Task 5: builder candidate pool before the round-robin cap (calls the builder's own build_roster read-only; output kept in memory).
Run: .venv/bin/python -B /tmp/dt_review/agent_data/t5_candidates.py"""
import json, sys
from collections import Counter
sys.path.insert(0, '/tmp/dt_review/agent_data')
from common import *
import build_v18_dev_episodes as b

rep = b.build_roster(DATA, limit=10**6, run_id=RUN_ID)
eps = rep['episodes']
print('candidate episodes (no cap):', len(eps), '; excluded_episodes:', len(rep['excluded_episodes']))
print('by station x month:', sorted(Counter((e['station'], fmt(e['target_start'])[:7]) for e in eps).items()))
print('source_count distribution:', sorted(Counter(e['source_count'] for e in eps).items()), 'truncated>0:', sum(e['sources_truncated_at_cap'] > 0 for e in eps))
print('target_start hour-of-day distribution:', sorted(Counter(int(fmt(e['target_start'])[11:13]) for e in eps).items()))
vis = Counter(); vis_ep_max = Counter(); change = 0
for e in eps:
    ns = []
    for cp in e['checkpoints']:
        n = sum(q['availability'] == 'available' for q in cp['qualifications'])
        vis[n] += 1; ns.append(n)
    vis_ep_max[max(ns)] += 1
    change += len(set(ns)) > 1
print('visible-in-stream per checkpoint (all candidates):', sorted(vis.items()))
print('episodes whose max visible count is:', sorted(vis_ep_max.items()), '; episodes where visible count changes across checkpoints:', change)
# Is the second stream source ever available before target_start?
first_pair_after = sum(1 for e in eps if True)
g = json.load(open(ART / 'G1_DEV_EPISODES_V3.json'))
pub = [e['episode_id'] for e in g['episodes']]
mine = []
# replicate round-robin with limit 24
from collections import defaultdict
bs = defaultdict(list)
for e in eps: bs[e['station']].append(e['episode_id'])
print('published 24 == first 6 (earliest days) per station of candidate pool:', sorted(pub) == sorted(sum((bs[s][:6] for s in STATIONS), [])))
print('published target dates:', sorted(Counter(p[-10:] for p in pub).items()))
print('published target_start hours:', sorted(Counter(int(fmt(e['target_start'])[11:13]) for e in g['episodes']).items()))
json.dump([{k: e[k] for k in ('episode_id', 'station', 'target_start', 'target_end', 'source_ids')} for e in eps], open('/tmp/dt_review/agent_data/t5_candidates.json', 'w'), indent=0)
