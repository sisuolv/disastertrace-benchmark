import sys, json, collections, importlib.util
sys.path.insert(0, "/tmp/dt_review/agent_code/clean/disastertrace-starter/scripts")
def load(name):
    spec = importlib.util.spec_from_file_location(name, f"/tmp/dt_review/agent_code/clean/disastertrace-starter/scripts/{name}.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
bridge = load("run_v21_real_dev_source_bridge"); score = load("run_v21_real_dev_deterministic_score")
from disastertrace.monitoring_v1.natural_selector_policy_v21 import CatalogueSelectorPolicy
proj = {"periods": [
    {"valid_start": 100, "valid_end": 150, "visibility_m": {"lower": 9000, "upper": 9999}},
    {"valid_start": 150, "valid_end": 200, "visibility_m": {"lower": 1600, "upper": 1600}}]}
v = bridge._visibility_number(proj)
pol = CatalogueSelectorPolicy()
actor_p = pol._forecast({"read": {"x": {"visibility_m": v}}})
print("synthetic 2-period: bridge visibility_m =", v, "-> actor p =", actor_p, "| scorer p =", score._projection_probability(proj, 100, 200))
# scan real dev G1 artifact
g1 = json.load(open("/tmp/dt_review/agent_code/clean/disastertrace-starter/artifacts/v21_execution_20260925_04/G1_DEV_EPISODES_V3.json"))
c = collections.Counter(); examples=[]
for ep in g1["episodes"]:
    for cp in ep["checkpoints"]:
        for q in cp.get("qualifications", []):
            pr = q.get("witness", {}).get("current_projection")
            if not isinstance(pr, dict): continue
            n = len(pr.get("periods") or [])
            c[f"periods={min(n,3)}{'+' if n>=3 else ''}"] += 1
            v = bridge._visibility_number(pr)
            a = CatalogueSelectorPolicy(baseline_probability=0.5)._forecast({"read": {"x": {"visibility_m": v}}})
            s = score._projection_probability(pr, ep["target_start"], ep["target_end"])
            key = "agree" if a == s else "DISAGREE"
            c[key] += 1
            if a != s: examples.append((ep["episode_id"], cp["checkpoint_id"], v, a, s, n))
print(dict(c)); print("examples (episode, checkpoint, bridge_vis, actor_p, scorer_p, n_periods):", examples)
