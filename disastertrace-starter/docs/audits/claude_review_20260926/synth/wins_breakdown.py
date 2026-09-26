import json, time
from pathlib import Path
from fractions import Fraction as Fr
from itertools import product
R="/mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/disastertrace-starter/artifacts/v21_execution_20260925_04/cost_matched_gpu"
NON=("fixed","no_extra","source_rr","source_hash")
cnt={}
for rep in ("5090a","5090b","h100_share"):
    for row in json.load(open(f"{R}/{rep}/result.json"))["rows"]:
        ml=row["method_losses"]; bm=min(NON,key=lambda m: ml[m])
        if ml["active"]<ml[bm]: cnt[bm]=cnt.get(bm,0)+1
print("816 wins by beaten reference:",cnt)
t=time.time()
B=lambda u,p:p*p+(1-2*p)*u
rows=[]
for r,h,l,d,c,p in product(*[list(map(Fr,x)) for x in (['.6','.7','.8','.9'],['.7','.85','.95'],['.5','.6'])],range(4),[Fr('.5'),Fr(1)],[Fr('.65'),Fr('.8')]):
    a=c*(4-d)/4; rows.append(a*(B(h,p)-B((h+l)/2,p)))
print("exact 384-cell surface in %.4f s (pure-python Fractions, CPU)"%(time.time()-t))
