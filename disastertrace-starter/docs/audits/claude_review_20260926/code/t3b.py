from disastertrace.monitoring_v1.interventions_v18 import apply_intervention
T=1_700_000_000_000_000
recs = [
  {"source_id":"S","source_revision":"r1","kind":"taf","issued_at":T,"available_at":T+10,"valid_start":T+100,"valid_end":T+200,"content":{"v":1}},
  {"source_id":"S","source_revision":"r2","kind":"taf","issued_at":T+20,"available_at":None,"valid_start":T+100,"valid_end":T+200,"content":{"v":2}},
]
for recs_ in (recs, recs[1:]):
    try:
        r = apply_intervention(recs_, "delay", target_start=T+100, target_end=T+200, as_of=T+1000)
        print("OK", r.records[-1]["available_at"], [q["status"] for q in r.qualification])
    except Exception as e:
        print("RAISED", type(e).__name__, e)
