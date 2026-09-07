from pathlib import Path
from disastertrace.automated.common import read_jsonl
from disastertrace.automated.dynamic import score_dynamic
episodes = [ep for ep in read_jsonl(Path("work/build-deepseek-v1/episodes/dynamic_episodes.jsonl")) if ep["group_id"] == "AL092021"]
traces = read_jsonl(Path("work/deepseek-ida-state-v1/imported_run/trace.jsonl"))
score = score_dynamic(episodes, traces)
assert score["metrics"]["state_accuracy"]["numerator"] == 50
assert score["metrics"]["grounded_state"]["numerator"] == 50, "Expected supported citations 50/50; frozen exact-locator scorer returns 49/50"
