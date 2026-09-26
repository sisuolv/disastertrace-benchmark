import json
from disastertrace.monitoring_v1.grid_scoring_v18 import score_complete_grid
def reg(t, m, y):
    return [{"target_id":t,"method":m,"checkpoint_id":c,"checkpoint_index":i,"base":0.5,"fallback":0.5,"outcome":y,"checkpoint_weight":1.0} for i,c in enumerate(("T-60","T-40"))]
def sub(t, m, p):
    return [{"target_id":t,"method":m,"checkpoint_id":c,"checkpoint_index":i,"status":"valid","probability":p} for i,c in enumerate(("T-60","T-40"))]
regs = reg("A","m1",1) + reg("B","m2",0)
subs = sub("A","m1",0.9) + sub("B","m2",0.9)
r = score_complete_grid(regs, subs)
print("comparison_eligible:", r["comparison_eligible"])
rep = r["report"]
print("report top-level keys:", sorted(rep)[:40])
print("any per-method breakdown key?:", [k for k in rep if "method" in k.lower()])
for k in ("brier","brier_score","mean_brier","skill","opportunities","settled"):
    if k in rep: print(" ", k, rep[k])
print(json.dumps({k:v for k,v in rep.items() if not isinstance(v,(list,dict))}, indent=0)[:800])
print("--- variant: A has m1+m2, B has only m1")
regs = reg("A","m1",1) + reg("A","m2",1) + reg("B","m1",0)
subs = sub("A","m1",0.9) + sub("A","m2",0.1) + sub("B","m1",0.1)
r = score_complete_grid(regs, subs); print("comparison_eligible:", r["comparison_eligible"], "system_brier:", r["report"]["system_brier"])
