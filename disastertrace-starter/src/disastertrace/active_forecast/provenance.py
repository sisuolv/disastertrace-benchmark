"""Offline content-bound source access; never exposed as a model tool."""

import hashlib
import json
import re
from decimal import Decimal
from pathlib import Path

from .schema import SourceLocator


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _constant(value):
    raise ValueError(f"nonfinite JSON number: {value}")


def decode_json(body):
    return json.loads(body, parse_float=Decimal, parse_constant=_constant, object_pairs_hook=_pairs)


def load_json(path):
    return decode_json(Path(path).read_bytes())


def sha256(body):
    return hashlib.sha256(body).hexdigest()


def write_json(path, value):
    body = json.dumps(value, ensure_ascii=True, indent=2, allow_nan=False) + "\n"
    with Path(path).open("x", encoding="utf-8") as stream:
        stream.write(body)


class SourceReader:
    """Hash each file before use; optionally recheck every bound file at completion."""

    def __init__(self, root):
        self.root = Path(root).resolve()
        self._bodies = {}
        self._json = {}
        self.bindings = {}
        self.resolved_locators = set()

    def path(self, relative):
        path = (self.root / relative).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("source path resolves outside the declared root")
        return path

    def bind(self, path, role="derived_product", pointer=None):
        path = Path(path).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("source path outside the declared root")
        relative = path.relative_to(self.root).as_posix()
        body = self._bodies.get(relative)
        if body is None:
            body = path.read_bytes()
        loc = SourceLocator(
            kind="whole_file" if pointer is None else "json_pointer",
            path=relative,
            sha256=sha256(body),
            role=role,
            pointer=pointer,
        )
        self.resolve(loc)
        return loc

    def resolve(self, locator: SourceLocator):
        loc = SourceLocator.model_validate(locator)
        path = self.path(loc.path)
        body = self._bodies.get(loc.path)
        if body is None:
            body = path.read_bytes()
        digest = self.bindings.get(loc.path, {}).get("sha256") or sha256(body)
        if digest != loc.sha256:
            raise ValueError(f"source hash mismatch: {loc.path}")
        self._bodies[loc.path] = body
        self.bindings[loc.path] = {"sha256": digest, "bytes": len(body)}
        self.resolved_locators.add(loc.model_dump_json())
        if loc.kind == "whole_file":
            return body
        if loc.kind == "byte_range":
            if loc.end > len(body):
                raise ValueError("byte locator beyond source length")
            return body[loc.start : loc.end]
        if loc.kind == "uint8_tile":
            height, width, frames = loc.array_shape
            if len(body) != height * width * frames:
                raise ValueError("raw uint8 bytes do not match declared C-order array shape")
            y0, y1, x0, x1 = loc.box
            return b"".join(
                body[(y * width + x0) * frames + loc.frame : (y * width + x1) * frames : frames]
                for y in range(y0, y1)
            )
        if loc.path not in self._json:
            self._json[loc.path] = decode_json(body)
        value = self._json[loc.path]
        if loc.pointer == "":
            return value
        try:
            for part in loc.pointer[1:].split("/"):
                if re.search(r"~(?![01])", part):
                    raise ValueError("invalid JSON pointer escape")
                part = part.replace("~1", "/").replace("~0", "~")
                if isinstance(value, list):
                    if not re.fullmatch(r"0|[1-9][0-9]*", part):
                        raise ValueError("noncanonical JSON array index")
                    value = value[int(part)]
                elif isinstance(value, dict):
                    value = value[part]
                else:
                    raise ValueError("JSON pointer traverses a scalar")  # noqa: TRY004
        except (KeyError, IndexError) as exc:
            raise ValueError(f"JSON pointer does not resolve: {loc.pointer}") from exc
        return value

    def verify_unchanged(self):
        for path, binding in self.bindings.items():
            if sha256(self.path(path).read_bytes()) != binding["sha256"]:
                raise ValueError(f"source changed during verification: {path}")
