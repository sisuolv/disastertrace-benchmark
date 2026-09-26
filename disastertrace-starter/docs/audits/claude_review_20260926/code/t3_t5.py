from disastertrace.monitoring_v1.interventions_v18 import apply_intervention
from disastertrace.monitoring_v1.evidence_qualification_v18 import qualify_stream

print("=== Task 3: delay with unknown availability")
recs = [
  {"source_id":"S","source_revision":"r1","kind":"taf","issued_at":10,"available_at":20,"valid_start":100,"valid_end":200,"content":{"v":1}},
  {"source_id":"S","source_revision":"r2","kind":"taf","issued_at":30,"available_at":None,"valid_start":100,"valid_end":200,"content":{"v":2}},
]
res = apply_intervention(recs, "delay", target_start=100, target_end=200, as_of=1000)
print("parent last available_at:", recs[-1]["available_at"], "-> child last available_at:", res.records[-1]["available_at"], "changed:", res.changed_fields)
for q in res.qualification:
    print("  qual:", q["status"], q["availability"], "available_at=", q["witness"]["available_at"])
# with as_of None
res2 = apply_intervention(recs, "delay", target_start=100, target_end=200)
print("as_of=None quals:", [(q["status"], q["availability"]) for q in res2.qualification])
# edge: available_at=0 (legit epoch) also fine; available_at earlier than issued -> child availability 86400000000 vs issued?
print("parent quals:", [(q.status,q.availability) for q in qualify_stream(recs, target_start=100, target_end=200, as_of=1000)])
print("=== Task 5: same-arrival conflicts")
def rec(src, rev, v, st="unknown"):
    return {"source_id":src,"source_revision":rev,"kind":"taf","issued_at":10,"available_at":20,"valid_start":100,"valid_end":200,"content":{"v":v},"relation_status":st}
for label, stream in [("A1,A2 adjacent", [rec("A","r1",1), rec("A","r1",2)]),
                      ("A1,B5,A2", [rec("A","r1",1), rec("B","r1",5), rec("A","r1",2)]),
                      ("A-r1,A-r2 adjacent (diff revision)", [rec("A","r1",1), rec("A","r2",2)]),
                      ("A-r1,B,A-r2", [rec("A","r1",1), rec("B","r1",5), rec("A","r2",2)])]:
    try:
        out = qualify_stream(stream, target_start=100, target_end=200, as_of=1000)
        print(f"  {label}: ACCEPTED ->", [q.status for q in out])
    except ValueError as e:
        print(f"  {label}: REJECTED ->", e)
