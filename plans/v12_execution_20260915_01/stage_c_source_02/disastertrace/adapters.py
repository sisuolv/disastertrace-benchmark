from __future__ import annotations

import base64
import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel
from .models import CheckpointCommit


@dataclass(frozen=True)
class ModelRequest:
    system_prompt: str
    user_prompt: str
    image_paths: tuple[Path, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ModelResponse:
    raw_text: str
    commit: CheckpointCommit
    usage: dict[str, Any] = field(default_factory=dict)
    provider_metadata: dict[str, Any] = field(default_factory=dict)


class ModelAdapter(Protocol):
    async def generate(self, request: ModelRequest) -> ModelResponse: ...


def extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].lstrip()
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    if start < 0:
        raise ValueError("model response does not contain a JSON object")
    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                parsed = json.loads(text[start : index + 1])
                if not isinstance(parsed, dict):
                    raise ValueError("top-level response must be an object")
                return parsed
    raise ValueError("unterminated JSON object")


class ScriptedAdapter:
    """Deterministic adapter for tests and scorer fixtures."""

    def __init__(self, commits: dict[str, CheckpointCommit]) -> None:
        self.commits = commits
        self.requests: list[ModelRequest] = []

    async def generate(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        checkpoint_id = str(request.metadata["checkpoint_id"])
        commit = self.commits[checkpoint_id]
        return ModelResponse(raw_text=commit.model_dump_json(), commit=commit)


class OpenAICompatibleAdapter:
    """Small Chat-Completions-style multimodal adapter.

    The benchmark core does not depend on this class; providers can be swapped
    without changing the replay/evaluation code.
    """

    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        base_url: str | None = None,
        max_tokens: int = 1800,
        temperature: float = 0.0,
    ) -> None:
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("install disastertrace[api]") from exc
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

    @staticmethod
    def _image_part(path: Path) -> dict[str, Any]:
        mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{encoded}"}}

    async def generate(self, request: ModelRequest) -> ModelResponse:
        content: list[dict[str, Any]] = [{"type": "text", "text": request.user_prompt}]
        content.extend(self._image_part(path) for path in request.image_paths)
        schema = CheckpointCommit.model_json_schema()
        schema_instruction = (
            "\nReturn exactly one JSON object matching this schema; no Markdown:\n"
            + json.dumps(schema, ensure_ascii=False)
        )
        last_error: Exception | None = None
        for attempt in range(4):
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    messages=[
                        {"role": "system", "content": request.system_prompt},
                        {"role": "user", "content": content + [{"type": "text", "text": schema_instruction}]},
                    ],
                )
                break
            except Exception as exc:  # provider-specific transient errors
                last_error = exc
                if attempt == 3:
                    raise
                await asyncio.sleep(min(2**attempt, 8))
        else:  # pragma: no cover
            raise RuntimeError("model request failed") from last_error
        raw = response.choices[0].message.content or ""
        commit = CheckpointCommit.model_validate(extract_json_object(raw))
        usage = response.usage.model_dump() if response.usage is not None else {}
        return ModelResponse(raw_text=raw, commit=commit, usage=usage)
