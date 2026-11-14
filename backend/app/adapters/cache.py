"""Disk cache for every external call (toolkit, Gemini, Nessie).

Modes (env CACHE_MODE):
  off         always call fn; never read or write the cache
  read_write  return cached value if present, else call fn and store it
  read_only   return cached value or raise CacheMiss; never touches the network

JSON values live at cache/<namespace>/<key>.json; binary blobs (images, meshes)
at cache/media/<key><ext>. key = sha256(namespace + sorted params).
"""
from __future__ import annotations

import hashlib
import inspect
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Awaitable, Callable, Literal

from app.config import get_settings

CacheMode = Literal["off", "read_write", "read_only"]


class CacheMiss(KeyError):
    """Raised in read_only mode when the requested entry is not cached."""


def cache_key(namespace: str, params: dict[str, Any]) -> str:
    payload = namespace + json.dumps(params, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def _settings(mode: CacheMode | None, root: Path | None) -> tuple[CacheMode, Path]:
    s = get_settings()
    return (mode or s.cache_mode), Path(root or s.cache_dir)


async def _call(fn: Callable[[], Any | Awaitable[Any]]) -> Any:
    result = fn()
    if inspect.isawaitable(result):
        result = await result
    return result


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


async def cached(
    namespace: str,
    params: dict[str, Any],
    fn: Callable[[], Any | Awaitable[Any]],
    *,
    mode: CacheMode | None = None,
    root: Path | None = None,
) -> Any:
    """Return the JSON-serialisable result of fn(), cached under (namespace, params)."""
    mode, root = _settings(mode, root)
    if mode == "off":
        return await _call(fn)

    key = cache_key(namespace, params)
    path = root / namespace / f"{key}.json"
    if path.exists():
        return json.loads(path.read_text())["value"]
    if mode == "read_only":
        raise CacheMiss(f"{namespace} {params} (key {key})")

    value = await _call(fn)
    entry = {"namespace": namespace, "params": params, "value": value}
    _atomic_write(path, json.dumps(entry, default=str, indent=1).encode())
    return value


async def cached_bytes(
    namespace: str,
    params: dict[str, Any],
    fn: Callable[[], bytes | Awaitable[bytes]],
    *,
    ext: str = "",
    mode: CacheMode | None = None,
    root: Path | None = None,
) -> Path:
    """Cache a binary blob (image, mesh) under cache/media/ and return its local path.

    In mode "off" the blob is still written (callers need a file path) but always refetched.
    """
    mode, root = _settings(mode, root)
    key = cache_key(namespace, params)
    path = root / "media" / f"{key}{ext}"
    if mode != "off" and path.exists():
        return path
    if mode == "read_only":
        raise CacheMiss(f"{namespace} {params} (key {key})")

    data = await _call(fn)
    _atomic_write(path, data)
    return path


def write_json_atomic(path: Path, obj: Any) -> Path:
    """Write JSON to path atomically (temp file + rename), for data/ files (TRD §5)."""
    path = Path(path)
    _atomic_write(path, json.dumps(obj, indent=2, default=str).encode())
    return path
