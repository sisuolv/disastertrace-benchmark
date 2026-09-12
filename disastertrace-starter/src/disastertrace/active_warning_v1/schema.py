"""Contracts deliberately separate input evidence from later outcome records."""

from typing import Annotated, Literal

from pydantic import BeforeValidator, Field, model_validator

from disastertrace.active_forecast.schema import (
    Exact,
    Instant,
    Name,
    SourceLocator,
    StrictModel,
    as_tuple,
)


class Artifact(StrictModel):
    id: Name
    product_id: Name
    provider: Name
    entity: Name
    variable: Name
    unit: Name
    kind: Literal["forecast", "observation"]
    issued_at: Instant | None
    valid_at: Instant
    release_at: Instant
    captured_at: Instant
    proved_historical_available_at: None = None
    values: Annotated[tuple[Exact, ...], BeforeValidator(as_tuple), Field(min_length=1)]
    source: SourceLocator
    quality: Name

    @model_validator(mode="after")
    def temporal_contract(self):
        if self.issued_at is not None and self.release_at < self.issued_at:
            raise ValueError("controlled release cannot precede issue")
        if self.kind == "forecast" and self.issued_at is None:
            raise ValueError("forecast issue time is required")
        if self.kind == "observation" and self.valid_at > self.release_at:
            raise ValueError("observation cannot be delivered before observation time")
        if any(value < 0 for value in self.values):
            raise ValueError("this pilot admits only nonnegative wind/discharge")
        return self


class Tool(StrictModel):
    id: Name
    kind: Literal["forecast", "observation", "mirror", "archive"]
    description: Name
    cost: Annotated[int, Field(ge=1)] = 1
    latency_seconds: Annotated[int, Field(ge=0)] = 60


class Episode(StrictModel):
    schema_version: Literal["active_warning.v1"] = "active_warning.v1"
    id: Name
    group: Name
    family: Literal["tropical_cyclone", "river_discharge"]
    entity: Name
    variable: Name
    unit: Name
    start_at: Instant
    target_at: Instant
    deadline: Instant
    checkpoints: Annotated[tuple[Instant, ...], BeforeValidator(as_tuple), Field(min_length=1)]
    threshold: Exact | None
    threshold_meaning: Name
    initial_artifact_id: Name
    initial_observation_id: Name | None = None
    artifacts: Annotated[tuple[Artifact, ...], BeforeValidator(as_tuple), Field(min_length=1)]
    tools: Annotated[tuple[Tool, ...], BeforeValidator(as_tuple), Field(min_length=1)]
    availability_mode: Literal["controlled_replay"] = "controlled_replay"
    scenario: Literal["clean", "duplicate", "stale", "delayed"] = "clean"
    split: Literal["exposed_development"] = "exposed_development"

    @model_validator(mode="after")
    def contract(self):
        if not self.start_at <= self.checkpoints[0] <= self.deadline < self.target_at:
            raise ValueError("all forecast checkpoints must precede the future target")
        if (
            tuple(sorted(set(self.checkpoints))) != self.checkpoints
            or self.checkpoints[-1] != self.deadline
        ):
            raise ValueError("checkpoints must be unique, ordered, and end at deadline")
        ids = [item.id for item in self.artifacts]
        if len(ids) != len(set(ids)) or self.initial_artifact_id not in ids:
            raise ValueError("artifact identities must be unique and include initial forecast")
        if len({tool.id for tool in self.tools}) != len(self.tools):
            raise ValueError("duplicate tool id")
        for item in self.artifacts:
            if (item.entity, item.variable, item.unit) != (self.entity, self.variable, self.unit):
                raise ValueError("incompatible entity, variable, or unit")
            if item.kind == "forecast" and item.valid_at != self.target_at:
                raise ValueError("forecast does not describe the fixed future target")
            if item.kind == "observation" and item.valid_at >= self.target_at:
                raise ValueError("outcome-time observations cannot enter the evidence pool")
        initial = next(item for item in self.artifacts if item.id == self.initial_artifact_id)
        if initial.kind != "forecast" or initial.release_at > self.start_at:
            raise ValueError("initial forecast must already be available")
        if self.initial_observation_id is not None:
            obs = next((a for a in self.artifacts if a.id == self.initial_observation_id), None)
            if obs is None or obs.kind != "observation" or obs.release_at > self.start_at:
                raise ValueError("initial observation must already be available")
        return self


class Outcome(StrictModel):
    episode_id: Name
    entity: Name
    variable: Name
    unit: Name
    valid_at: Instant
    value: Exact | None
    status: Literal["retrospective_analysis", "provisional_observation", "unresolved"]
    source: SourceLocator | None
    captured_at: Instant
    reason: Name

    @model_validator(mode="after")
    def resolved(self):
        if (self.status == "unresolved") != (self.value is None):
            raise ValueError("unresolved outcomes require null values")
        if self.value is not None and (self.value < 0 or self.source is None):
            raise ValueError("resolved outcomes require nonnegative values and source")
        if self.captured_at < self.valid_at:
            raise ValueError("outcome capture cannot precede its valid time")
        return self
