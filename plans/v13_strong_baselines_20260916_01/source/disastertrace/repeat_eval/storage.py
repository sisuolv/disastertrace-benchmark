"""Publish a complete JSON file atomically without replacing an existing result."""

import os
import uuid
from pathlib import Path

from disastertrace.automated.common import canonical


def atomic_write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name("." + path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("x") as stream:
            stream.write(canonical(value) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        # Linking is atomic and exclusive: a crash exposes either no file or all bytes.
        os.link(temporary, path)
        fd = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        temporary.unlink(missing_ok=True)
