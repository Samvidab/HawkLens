"""Atomic JSON writes into data/ (TRD §5: temp file + rename)."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app.config import get_settings


def data_path(*parts: str) -> Path:
    return Path(get_settings().data_dir).joinpath(*parts)


def write_json(path: Path, obj: Any) -> Path:
    if isinstance(obj, BaseModel):
        obj = obj.model_dump(mode="json")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(obj, f, indent=1)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return path


def read_json(path: Path, default: Any = None) -> Any:
    return json.loads(path.read_text()) if path.exists() else default
