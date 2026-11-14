"""Guardrails (TRD §10): number check on LLM prose, step/loop caps.

LLMs write words; every number a user sees must come from source JSON. `check_numbers` finds
numbers in text that no source value explains (after rounding / unit rules). `{{placeholders}}`
are ignored. `guarded_text` rejects a draft with invented numbers and regenerates without numbers.
"""
from __future__ import annotations

import re
from typing import Any, Awaitable, Callable, Iterable

MAX_VERIFIER_LOOPS = 2
MAX_TOOL_STEPS = 8

_PLACEHOLDER = re.compile(r"\{\{.*?\}\}")
# optional sign/$, digits with thousands commas or plain, optional decimals, optional k/M/B suffix, optional %
_NUMBER = re.compile(r"(?<![\w.])[-−]?\$?(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?\s?([kKmMbB](?![a-zA-Z]))?\s?(%)?")
_SUFFIX = {"k": 1e3, "m": 1e6, "b": 1e9}


def _parse(m: re.Match) -> tuple[float, int, float, bool]:
    """(value, decimals, unit multiplier, is_percent)"""
    whole, frac = m.group(1).replace(",", ""), m.group(2) or ""
    val = float(whole + frac)
    return val, max(len(frac) - 1, 0), _SUFFIX.get((m.group(3) or "").lower(), 1.0), bool(m.group(4))


def _numbers_in(text: str) -> list[re.Match]:
    return list(_NUMBER.finditer(_PLACEHOLDER.sub(" ", text)))


def _collect(obj: Any, out: set[float]) -> None:
    if isinstance(obj, bool) or obj is None:
        return
    if isinstance(obj, (int, float)):
        out.add(abs(float(obj)))
    elif isinstance(obj, str):
        for m in _numbers_in(obj):
            v, _, mult, _ = _parse(m)
            out.add(v * mult)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            _collect(k, out)
            _collect(v, out)
    elif isinstance(obj, Iterable):
        for v in obj:
            _collect(v, out)
    elif hasattr(obj, "model_dump"):
        _collect(obj.model_dump(), out)


def source_numbers(sources: Any) -> set[float]:
    out: set[float] = set()
    _collect(sources, out)
    return out


def _explained(n: float, decimals: int, mult: float, pct: bool, pool: set[float]) -> bool:
    target = n * mult
    for v in pool:
        for cand in ((v * 100, v) if pct else (v,)):
            if round(cand, decimals) == round(target, decimals) if mult == 1 else \
                    abs(cand - target) <= 0.5 * 10 ** (-decimals) * mult:
                return True
    return False


def check_numbers(text: str, sources: Any) -> list[str]:
    """Numbers in `text` not explained by `sources` (empty list = ok)."""
    pool = source_numbers(sources)
    bad = []
    for m in _numbers_in(text):
        v, dec, mult, pct = _parse(m)
        if not _explained(v, dec, mult, pct, pool):
            bad.append(m.group(0).strip())
    return bad


async def guarded_text(generate: Callable[[bool], Awaitable[str]], sources: Any, *,
                       fallback: str | None = None) -> str:
    """generate(allow_numbers) -> text. Reject drafts with invented numbers and regenerate once
    with allow_numbers=False; if that still has numbers (or fails), return `fallback`."""
    draft = await generate(True)
    if not check_numbers(draft, sources):
        return draft
    retry = await generate(False)
    if not check_numbers(retry, sources) and not _numbers_in(retry):
        return retry
    if fallback is None:
        raise ValueError(f"LLM text kept inventing numbers: {check_numbers(retry, sources)}")
    return fallback


def fill_placeholders(text: str, values: dict[str, Any]) -> str:
    """Substitute {{name}} from code-computed values; unknown placeholders raise."""
    def sub(m: re.Match) -> str:
        key = m.group(0)[2:-2].strip()
        if key not in values:
            raise KeyError(f"no value for placeholder {{{{{key}}}}}")
        return str(values[key])
    return _PLACEHOLDER.sub(sub, text)


class CapExceeded(RuntimeError):
    pass


class StepCounter:
    """Per-agent step cap (<= 8 tool steps) and per-claim verifier-loop cap (2)."""

    def __init__(self, max_steps: int = MAX_TOOL_STEPS, max_loops: int = MAX_VERIFIER_LOOPS):
        self.max_steps, self.max_loops = max_steps, max_loops
        self.steps: dict[str, int] = {}
        self.loops: dict[str, int] = {}

    def step(self, agent: str) -> int:
        n = self.steps[agent] = self.steps.get(agent, 0) + 1
        if n > self.max_steps:
            raise CapExceeded(f"{agent} exceeded {self.max_steps} steps")
        return n

    def can_loop(self, claim_id: str) -> bool:
        return self.loops.get(claim_id, 0) < self.max_loops

    def loop(self, claim_id: str) -> int:
        if not self.can_loop(claim_id):
            raise CapExceeded(f"claim {claim_id} exceeded {self.max_loops} verifier loops")
        n = self.loops[claim_id] = self.loops.get(claim_id, 0) + 1
        return n
