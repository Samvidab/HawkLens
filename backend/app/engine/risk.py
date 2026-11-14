"""Risk summary of a set of NPV scenarios (engine/CLAUDE.md "Risk"), alpha = 0.05.

exp_npv   mean NPV
p_loss    share of scenarios with NPV < 0
cvar5     mean of the worst 5% of scenarios (usually negative; higher = better worst case)
hist_bins 30 bins over the 0.5-99.5 percentile range, as [{x0, x1, count}]
          (the risk_histogram widget's format). The extreme 1% of scenarios
          outside that range are left out so one outlier can't squash the chart;
          counts therefore add up to about 99% of K, not exactly K.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np

ALPHA = 0.05
N_BINS = 30


def cvar(values: np.ndarray, alpha: float = ALPHA) -> np.ndarray | float:
    """Mean of the worst ceil(alpha*K) values along the last axis."""
    v = np.asarray(values, float)
    k = v.shape[-1]
    n_tail = max(1, math.ceil(alpha * k))
    worst = np.partition(v, n_tail - 1, axis=-1)[..., :n_tail]   # smallest n_tail, any order
    out = worst.mean(axis=-1)
    return float(out) if out.ndim == 0 else out


def hist_bins(values: np.ndarray, n_bins: int = N_BINS) -> list[dict[str, float]]:
    v = np.asarray(values, float).ravel()
    lo, hi = np.percentile(v, [0.5, 99.5])
    if hi <= lo:                      # all scenarios (nearly) equal: one visible bar
        lo, hi = lo - 0.5, hi + 0.5
    counts, edges = np.histogram(v, bins=n_bins, range=(lo, hi))
    return [{"x0": float(edges[i]), "x1": float(edges[i + 1]), "count": int(counts[i])}
            for i in range(n_bins)]


def summarize(values: np.ndarray, alpha: float = ALPHA) -> dict[str, Any]:
    """Risk numbers for ONE 1-D array of scenario NPVs."""
    v = np.asarray(values, float)
    if v.ndim != 1 or v.size == 0:
        raise ValueError("summarize() takes a non-empty 1-D array of NPVs")
    return {
        "exp_npv": float(v.mean()),
        "p_loss": float((v < 0).mean()),
        "cvar5": cvar(v, alpha),
        "hist_bins": hist_bins(v),
    }
