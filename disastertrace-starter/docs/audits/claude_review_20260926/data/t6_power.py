"""Task 6: rough power/feasibility counts over Jan+Mar 2025 (dev readset only).
Hourly windows = [HH:00, HH+1:00). TAF via builder _load_products; AMD counts via independent raw CSV scan.
Run: .venv/bin/python -B /tmp/dt_review/agent_data/t6_power.py"""
import csv, gzip, io, json, re, sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
sys.path.insert(0, '/tmp/dt_review/agent_data')
from common import *

H = 3_600_000_000
# ---- ASOS positives per station-month
asos = {(s, m): load_asos(s, m) for s in STATIONS for m in MONTHS}
print('ASOS hourly windows: station month | windows | first<5km | any<5km | routine-first<5km')
hours = {}
for (s, m), obs in asos.items():
    byh = defaultdict(list)
    for o in obs:
        byh[us(o['dt'].replace(minute=0))].append(o)
    hours[(s, m)] = byh
    f = sum(v[0]['m'] < THR for v in byh.values()); a = sum(any(o['m'] < THR for o in v) for v in byh.values())
    rr = [next((o for o in v if o['routine']), None) for v in byh.values()]
    r = sum(1 for o in rr if o and o['m'] < THR)
    print(f'  {s} {m} | {len(byh)} | {f} | {a} | {r}   last obs {fmt(obs[-1]["t"])}')

# ---- AMD counts, independent raw scan
print('\nTAF products per station-month (raw CSV scan): total | AMD (is_amendment/AA?) | COR | routine | issue range')
for s in STATIONS:
    for m in MONTHS:
        for fn in [f'{s}_{m}.body'] + ([f'{s}_{m}_proxy.body'] if (s, m) == ('KJFK', '202503') else []):
            p = guard(DATA / 'taf' / RUN_ID / fn)
            pid = {}
            with open(p, newline='') as fh:
                for r in csv.DictReader(fh):
                    if r.get('product_id'):
                        pid.setdefault(r['product_id'], r.get('is_amendment'))
            amd = sum(1 for k, v in pid.items() if v == 'True' or re.search(r'-AA[A-Z]$', k))
            cor = sum(1 for k in pid if re.search(r'-CC[A-Z]$', k))
            iss = sorted(k[:12] for k in pid)
            print(f'  {fn:24s} {len(pid):4d} | {amd:4d} | {cor:3d} | {len(pid)-amd-cor:4d} | {iss[0]}..{iss[-1]}')

# ---- TAF disagreement / revision counts per hourly window
print('\nPer hourly window H (decision at T-60 = H-60min and T-20 = H-20min; product covers [H,H+1h) and available_at <= decision):')
tot = Counter()
for s in STATIONS:
    prods = sorted(sum((load_taf_products(s, m) for m in MONTHS), []), key=lambda p: (p['issued_at'], p['source_id']))
    for m in MONTHS:
        c = Counter()
        for h, v in sorted(hours[(s, m)].items()):
            y = int(v[0]['m'] < THR)
            def avail(dec):
                return [p for p in prods if p['available_at'] <= dec and p['valid_start'] <= h and p['valid_end'] >= h + H]
            a60, a20 = avail(h - H), avail(h - H // 3)
            if not a60:
                c['no_cover_T60'] += 1; continue
            pr = [taf_prob(p['content']['periods'], h, h + H)[0] for p in a60]
            pr = [x for x in pr if x is not None]
            c['ge2_cover_T60'] += len(a60) >= 2
            if len(set(pr)) > 1:
                c['any_pair_disagree_T60'] += 1; c['any_pair_disagree_T60_y1'] += y
            # latest vs previous covering product (most recent revision) at T-60
            if len(a60) >= 2:
                pl = taf_prob(a60[-1]['content']['periods'], h, h + H)[0]; pp = taf_prob(a60[-2]['content']['periods'], h, h + H)[0]
                if pl != pp:
                    c['latest_vs_prev_disagree_T60'] += 1; c['latest_vs_prev_disagree_T60_y1'] += y
            new = [p for p in a20 if p['available_at'] > h - H]
            if new:
                c['new_cover_TAF_in_(T-60,T-20]'] += 1
                p60 = taf_prob(a60[-1]['content']['periods'], h, h + H)[0]; p20 = taf_prob(a20[-1]['content']['periods'], h, h + H)[0]
                if p60 != p20:
                    c['..and_latest_answer_flips'] += 1; c['..and_latest_answer_flips_y1'] += y
            pl = taf_prob(a60[-1]['content']['periods'], h, h + H)[0]
            c['latest_T60_says_<5k'] += pl == 0.8; c['latest_T60_says_<5k_and_y1'] += (pl == 0.8) * y; c['y1'] += y
        tot.update(c)
        print(f'  {s} {m}:', dict(c))
print('  TOTAL:', dict(tot))

# ---- METAR persistence at T-60 (latest obs at or before H-60min)
pc = Counter()
for (s, m), obs in asos.items():
    ts = [o['t'] for o in obs]
    import bisect
    for h, v in hours[(s, m)].items():
        i = bisect.bisect_right(ts, h - H) - 1
        if i < 0: continue
        pc[(int(obs[i]['m'] < THR), int(v[0]['m'] < THR))] += 1
print('\nMETAR persistence (latest obs at T-60 <5km, first obs in window <5km):', dict(pc))

# ---- LAMP (LAV) availability for these stations
print('\nLAMP LAV blocks per station in dev months:')
lroot = DATA / 'lamp/raw/20260920T100529Z_09c70a575ad2'
lc = Counter(); cat = Counter(); hrs = Counter()
for m in MONTHS:
    for cyc in ('0000', '0600', '1200', '1800'):
        p = guard(lroot / f'lav-{m}-{cyc}z.body')
        txt = gzip.decompress(p.read_bytes()).decode('latin-1').splitlines()
        for i, line in enumerate(txt):
            mm = re.match(r'\s*(KDEN|KJFK|KORD|KSFO)\s+GFS LAMP GUIDANCE\s+(\S+)\s+(\d{4}) UTC', line)
            if not mm: continue
            st = mm.group(1); lc[(st, m, cyc)] += 1
            utc = txt[i + 1].split()[1:]; vis = txt[i + 3].split()[1:]
            hrs[tuple(utc)] += 1
            for v in vis: cat[(st, v)] += 1
print('  blocks (station,month,cycle):', sorted(set(lc.values())), 'per key;', len(lc), 'keys')
print('  projection hours seen:', dict(hrs))
print('  VIS category counts (1-4 = <3SM i.e. <4828m; 5 = 3-5SM straddles 5000m; 6-7 >5SM):')
for st in STATIONS:
    print('   ', st, {k: cat[(st, k)] for k in '1234567'})
