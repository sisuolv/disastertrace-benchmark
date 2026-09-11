"""Count a queued/starting one-card request before realized replicas become one."""


def requested_h100(job):
    if job["resource_pool"]["name"] != "computing-cluster-01g-02":
        raise ValueError("unexpected active cluster")
    roles = job["roles"]
    if len(roles) != 1 or int(roles[0]["total_replicas"]) != 1:
        raise ValueError("expected exactly one requested worker")
    specs = roles[0]["resource_spec"]
    if len(specs) != 1:
        raise ValueError("expected exactly one worker specification")
    spec = specs[0]
    if spec["name"] != "N6lS.Iu.I10.1.8c128g" or int(spec["replicas"]) not in (0, 1):
        raise ValueError("unexpected specification or realized replicas")
    if any(int(spec[key]["nvidia.com/gpu"]) != 1 for key in ("requests", "limits")):
        raise ValueError("expected exactly one requested GPU")
    return 1
