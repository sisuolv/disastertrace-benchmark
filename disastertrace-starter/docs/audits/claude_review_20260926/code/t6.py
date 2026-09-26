from disastertrace.monitoring_v1.natural_track_v18 import NaturalKernel, NaturalSource, NaturalAction, replay_suffix
from disastertrace.monitoring_v1.synthetic_natural_v21 import target_card
from disastertrace.monitoring_v1.grid_scoring_v18 import score_complete_grid
t = target_card(); print("target window:", t["target_start"], t["target_end"])
# 6a clock advance
k = NaturalKernel([NaturalSource("q0", 0, {"visibility_m": 1.0})], start=0, deadline=20, target=t)
for a in [NaturalAction("RETRIEVE",0,query_id="q0"), NaturalAction("UPDATE",0,probability=0.7), NaturalAction("UPDATE",0,probability=0.1)]:
    k.step(a); print(" after", a.kind, "clock=", k.clock)
# 6b UPDATE persistence
ps = k.public_state()
print("6b public_state keys:", sorted(ps)); print("   any probability in public_state?:", "0.7" in repr(ps) or "0.1" in repr(ps))
print("   probability only in kernel.actions log:", [x["result"].get("probability") for x in k.actions if x["action"]=="UPDATE"])
k.step(NaturalAction("WAIT",0,wake_at=5)); print("6a after WAIT clock=", k.clock)
# 6c start/deadline after target window
try:
    k2 = NaturalKernel([NaturalSource("q0", 0, {"visibility_m": 1.0})], start=210, deadline=300, target=t)
    r1 = k2.step(NaturalAction("RETRIEVE",210,query_id="q0")); r2 = k2.step(NaturalAction("UPDATE",210,probability=1.0)); r3=k2.step(NaturalAction("STOP",210))
    print("6c start=210 deadline=300 target=[100,200): ACCEPTED", r1["status"], r2, r3)
except Exception as e:
    print("6c RAISED", e)
# also deadline way after target_end with start inside
try:
    k3 = NaturalKernel([], start=150, deadline=10**9, target=t); k3.step(NaturalAction("WAIT",150,wake_at=250)); print("6c' WAIT past target_end then UPDATE:", k3.step(NaturalAction("UPDATE",250,probability=0.3)))
except Exception as e:
    print("6c' RAISED", e)
# 6d max_actions: kernel has no cap; replay_suffix raises
k4 = NaturalKernel([NaturalSource("q0", 0, {"visibility_m": 1.0})], start=0, deadline=20, target=t)
n=0
for i in range(1000):
    k4.step(NaturalAction("UPDATE",0,probability=0.5)); n+=1
print("6d kernel accepted", n, "UPDATEs, action_count=", k4.public_state()["action_count"], "clock=", k4.clock)
try:
    replay_suffix(NaturalKernel([], start=0, deadline=20, target=t).snapshot(), lambda s: NaturalAction("UPDATE", s["clock"], probability=0.5), max_actions=5)
except Exception as e:
    print("6d replay_suffix:", type(e).__name__, e)
