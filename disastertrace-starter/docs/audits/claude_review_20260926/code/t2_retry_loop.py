import hashlib, json
from disastertrace.monitoring_v1.natural_track_v18 import NaturalKernel, NaturalSource, NaturalAction, replay_suffix
from disastertrace.monitoring_v1.natural_selector_policy_v21 import CatalogueSelectorPolicy
from disastertrace.monitoring_v1.active_policy_v21 import ContentAwareSyntheticPolicy, run_policy
from disastertrace.monitoring_v1.synthetic_natural_v21 import target_card, _execute

def mk():
    t = target_card()
    return NaturalKernel([NaturalSource("sched", 50, {"visibility_m": 3000.0}, public_schedule=True)],
                         start=0, deadline=100, target=t)

for name, pol in [("CatalogueSelectorPolicy", CatalogueSelectorPolicy(max_queries=1)),
                  ("CatalogueSelectorPolicy-rr", CatalogueSelectorPolicy(selector_kind="round_robin_cycle.v1", max_queries=2)),
                  ("ContentAwareSyntheticPolicy", ContentAwareSyntheticPolicy())]:
    k = mk()
    print("==", name, "catalogue:", k.public_state()["catalogue"])
    seen = []
    for i in range(20):
        s = k.public_state()
        if s["terminal"]:
            break
        a = pol(s)
        r = k.step(a)
        seen.append((a.kind, a.query_id, r["status"]))
    s = k.public_state()
    print(" unique actions:", set(seen), " steps:", len(seen), " clock:", s["clock"], " action_count:", s["action_count"], " read:", s["read_query_ids"], " terminal:", s["terminal"])
    # Drivers with caps
    for drv in ("replay_suffix", "synthetic._execute"):
        k2 = mk()
        try:
            if drv == "replay_suffix":
                out = replay_suffix(k2.snapshot(), pol, max_actions=12)
            else:
                out = _execute(k2, pol, max_actions=12)
            print("  ", drv, "returned", len(out))
        except Exception as e:
            print("  ", drv, "RAISED", type(e).__name__, e, "| kernel action_count after:", k2.public_state()["action_count"])
