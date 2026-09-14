"""A synthetic preparation reducer; scheduling is owned by the session clock."""

import json
import math


class PreparationReducer:
    def __init__(self, card):
        if (
            card.get("schema") != "disastertrace.preparation_scenario.v1"
            or card.get("kind") != "research_assumption"
            or not card.get("units")
            or type(card["capacity"]) is not int
            or card["capacity"] < 1
            or type(card["budget"]) is not int
            or card["budget"] < 0
        ):
            raise ValueError("Explicit finite preparation scenario required")
        self.card = json.loads(json.dumps(card, allow_nan=False))
        self.jobs = {r["job_id"]: r for r in self.card["jobs"]}
        if not self.jobs or len(self.jobs) != len(self.card["jobs"]):
            raise ValueError("Unique preparation jobs required")
        if len({job["target_id"] for job in self.jobs.values()}) != len(self.jobs):
            raise ValueError("This scenario requires one job per target")
        for job in self.jobs.values():
            if set(job) != {
                "job_id",
                "target_id",
                "deadline",
                "duration",
                "expires_at",
                "cost",
                "cleanup_duration",
                "cleanup_cost",
            }:
                raise ValueError("Wrong preparation job fields")
            if (
                not job["job_id"]
                or not job["target_id"]
                or any(
                    type(job[k]) is not int or job[k] < 0
                    for k in (
                        "deadline",
                        "duration",
                        "expires_at",
                        "cost",
                        "cleanup_duration",
                        "cleanup_cost",
                    )
                )
                or job["duration"] == 0
                or job["cleanup_duration"] == 0
            ):
                raise ValueError("Invalid preparation timing/cost")
        self.states = {
            jid: {"status": "unstarted", "spent": 0, "reserved_cleanup": 0} for jid in self.jobs
        }
        self.snapshots, self.history = {}, []
        self.now = None

    @property
    def spent(self):
        return sum(s["spent"] for s in self.states.values())

    @property
    def reserved(self):
        return sum(s["reserved_cleanup"] for s in self.states.values())

    def occupied(self):
        return sum(s["status"] in {"running", "ready", "cleaning"} for s in self.states.values())

    def progress(self, at):
        if self.now is not None and at < self.now:
            raise ValueError("Preparation clock cannot reverse")
        self.now = at
        for jid, state in self.states.items():
            if state["status"] == "running" and state["finished_at"] <= at:
                state["status"] = "ready"
                self.history.append({"job_id": jid, "at": state["finished_at"], "status": "ready"})
            if state["status"] == "cleaning" and state["released_at"] <= at:
                state["status"] = "canceled"
                self.history.append(
                    {"job_id": jid, "at": state["released_at"], "status": "cleanup_complete"}
                )
            if state["status"] == "ready" and at > self.jobs[jid]["expires_at"]:
                state.update(status="expired", reserved_cleanup=0)

    def request(self, jid, at):
        self.progress(at)
        job, state = self.jobs[jid], self.states[jid]
        if state["status"] != "unstarted":
            status = "already_started"
        elif (
            at >= job["deadline"]
            or at + job["duration"] > job["deadline"]
            or at + job["duration"] > job["expires_at"]
        ):
            status = "too_late"
        elif self.occupied() >= self.card["capacity"]:
            status = "capacity_rejected"
        elif self.spent + self.reserved + job["cost"] + job["cleanup_cost"] > self.card["budget"]:
            status = "budget_rejected"
        else:
            status = "started"
            state.update(
                status="running",
                started_at=at,
                finished_at=at + job["duration"],
                spent=job["cost"],
                reserved_cleanup=job["cleanup_cost"],
            )
        self.history.append({"job_id": jid, "at": at, "status": status})

    def cancel(self, jid, at):
        self.progress(at)
        job, state = self.jobs[jid], self.states[jid]
        if state["status"] in {"running", "ready"}:
            state.update(
                status="cleaning",
                released_at=at + job["cleanup_duration"],
                spent=state["spent"] + job["cleanup_cost"],
                reserved_cleanup=0,
            )
            status = "canceled_cleanup_pending"
        else:
            status = "no_active_preparation"
        self.history.append({"job_id": jid, "at": at, "status": status})

    def seal(self, at):
        for jid, job in self.jobs.items():
            if job["deadline"] == at and jid not in self.snapshots:
                state = self.states[jid]
                ready = (
                    state["status"] == "ready" and state["finished_at"] <= at <= job["expires_at"]
                )
                self.snapshots[jid] = {
                    "job_id": jid,
                    "target_id": job["target_id"],
                    "deadline": at,
                    "ready": ready,
                    "spent_at_deadline": state["spent"],
                }

    def after_seal(self, at):
        for jid, state in self.states.items():
            if state["status"] == "ready" and at >= self.jobs[jid]["expires_at"]:
                state.update(status="expired", reserved_cleanup=0)

    def boundaries(self, events):
        for job in self.jobs.values():
            yield job["deadline"]
            yield job["expires_at"]
        for event in events:
            if event.kind in {"prepare", "cancel_preparation"}:
                job = self.jobs[event.payload["job_id"]]
                yield (
                    event.time + job["duration" if event.kind == "prepare" else "cleanup_duration"]
                )
        for state in self.states.values():
            if state["status"] == "running":
                yield state["finished_at"]
            if state["status"] == "cleaning":
                yield state["released_at"]

    def to_dict(self):
        return json.loads(
            json.dumps(
                {
                    "card": self.card,
                    "states": self.states,
                    "snapshots": self.snapshots,
                    "history": self.history,
                    "clock": self.now,
                },
                allow_nan=False,
            )
        )


def one_step_prepare(probability, cost, miss_penalty):
    if (
        type(probability) not in (int, float)
        or not math.isfinite(probability)
        or not 0 <= probability <= 1
        or any(
            type(v) not in (int, float) or not math.isfinite(v) or v < 0
            for v in (cost, miss_penalty)
        )
    ):
        raise ValueError("Invalid one-step inputs")
    return probability * miss_penalty > cost


def score_preparation(reducer, outcomes, *, miss_penalty):
    if set(outcomes) != set(reducer.jobs) or set(reducer.snapshots) != set(reducer.jobs):
        raise ValueError("All unique jobs need cutoff states and explicit outcomes")
    if (
        type(miss_penalty) not in (int, float)
        or not math.isfinite(miss_penalty)
        or miss_penalty < 0
    ):
        raise ValueError("Invalid miss penalty")
    losses, missing = [], 0
    for jid, value in outcomes.items():
        if value is None:
            missing += 1
            continue
        if type(value) not in (int, float) or value not in (0, 1):
            raise ValueError("Binary synthetic demand required")
        losses.append(miss_penalty * value * (not reducer.snapshots[jid]["ready"]))
    return {
        "unique_jobs": len(outcomes),
        "settled_jobs": len(losses),
        "missing_jobs": missing,
        "preparation_cost": reducer.spent,
        "settled_miss_penalty": sum(losses),
        "total_cost": reducer.spent + sum(losses) if not missing else None,
        "cost_lower_bound": reducer.spent + sum(losses),
        "cost_upper_bound": reducer.spent + sum(losses) + missing * miss_penalty,
        "scope": "synthetic_research_assumption_not_operational_weather_benefit",
    }
