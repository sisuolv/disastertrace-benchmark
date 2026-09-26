"""Shared helpers for the independent DisasterTrace v21 real-dev review (read-only)."""
from __future__ import annotations
import csv, json, math, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

REPO = Path('/mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/disastertrace-starter')
ART = REPO / 'artifacts/v21_execution_20260925_04'
DATA = Path('/mnt/afs/260010168/extreme_weather_benchmark/data_real_v16')
RUN_ID = '20260920T091835Z_5f8988c0e49a'
STATIONS = ('KDEN', 'KJFK', 'KORD', 'KSFO')
MONTHS = ('202501', '202503')
SM_TO_M = 1609.344
THR = 5000.0
ROUTINE_MINUTE = {'KDEN': 53, 'KJFK': 51, 'KORD': 51, 'KSFO': 56}

sys.path.insert(0, str(REPO / 'scripts'))
sys.path.insert(0, str(REPO / 'src'))


def guard(path: Path) -> Path:
    s = str(path)
    assert 'quarantine_holdout' not in s and '2025-02' not in s and '202502' not in s, s
    assert '2023' not in path.name and '2024' not in path.name, s
    return path


def us(dt: datetime) -> int:
    return int(dt.timestamp() * 1_000_000)


def fmt(v: int) -> str:
    return datetime.fromtimestamp(v / 1e6, tz=timezone.utc).strftime('%Y-%m-%d %H:%M')


def load_asos(station: str, month: str) -> list[dict]:
    """Independent parser of IEM ASOS CSV. Returns rows sorted by time."""
    faa = station[1:].lower()
    d = DATA / 'asos' / station / f'{month[:4]}-{month[4:]}'
    files = sorted(d.glob(f'*/asos-{faa}-{month}.body'))
    assert len(files) == 1, files
    out = []
    with open(guard(files[0]), newline='') as fh:
        for r in csv.DictReader(fh):
            v = r['vsby'].strip()
            if v in ('', 'M'):
                continue
            try:
                sm = float(v)
            except ValueError:
                continue
            t = datetime.strptime(r['valid'], '%Y-%m-%d %H:%M').replace(tzinfo=timezone.utc)
            metar = r['metar']
            ghcnh = 'IEM_GHCNH' in metar
            routine = (t.minute == ROUTINE_MINUTE[station]) and not ghcnh
            out.append({'t': us(t), 'dt': t, 'sm': sm, 'm': sm * SM_TO_M, 'routine': routine,
                        'ghcnh': ghcnh, 'metar': metar})
    out.sort(key=lambda r: r['t'])
    return out


def load_taf_products(station: str, month: str, run_id: str = RUN_ID):
    """The builder's own loader (reused, not reimplemented)."""
    import build_v18_dev_episodes as b
    guard(DATA / 'taf' / run_id / f'{station}_{month}.body')
    return b._load_products(DATA, station, month, run_id)


def taf_prob(periods, t0: int, t1: int):
    """Scorer rule: 0.8 if min lower vis bound over overlapping periods < 5000 m else 0.2; None if no bound."""
    lows = []
    for p in periods:
        s, e = p['valid_start'], p['valid_end']
        if e <= t0 or s >= t1:
            continue
        vis = p.get('visibility_m')
        if not isinstance(vis, dict):
            continue
        lo = vis.get('lower')
        if isinstance(lo, (int, float)) and not isinstance(lo, bool) and math.isfinite(float(lo)):
            lows.append(float(lo))
    if not lows:
        return None, None
    return (0.8 if min(lows) < THR else 0.2), min(lows)


def taf_prob_prevailing(periods, t0, t1):
    """Variant: prevailing (non-conditional) groups only."""
    return taf_prob([p for p in periods if not p['conditional']], t0, t1)
