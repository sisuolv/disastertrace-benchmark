from disastertrace.monitoring_v1.natural_track_v18 import NaturalKernel, NaturalSource
from disastertrace.monitoring_v1.synthetic_natural_v21 import target_card, _execute
from disastertrace.monitoring_v1.active_policy_v21 import ContentAwareSyntheticPolicy
def run(ids):
    roles = [("initial_signal",4000.0),("followup_a",3000.0),("followup_b",9000.0)]
    srcs = [NaturalSource(i, 0, {"visibility_m": v, "source_role": r}) for i,(r,v) in zip(ids, roles)]
    k = NaturalKernel(srcs, start=0, deadline=20, target=target_card())
    tr = _execute(k, ContentAwareSyntheticPolicy())
    upd = [x["result"]["probability"] for x in tr if x["action"]=="UPDATE"]
    roles_read = [k.read[q]["source_role"] for q in k.read]
    return [x["query_id"] for x in tr if x["action"]=="RETRIEVE"], roles_read, upd
for ids in (("q0","q1","q2"), ("z0","z1","z2"), ("a","z","b"), ("q2","q1","q0")):
    print(ids, "->", run(ids))
