from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np
import pandas as pd
from scipy.signal import argrelextrema


@dataclass
class PatternResult:
    passed: bool
    slope: float
    peaks: pd.DataFrame
    score: float
    violations: int
    max_break_pct: float
    reason: str | None = None


def detect_lower_highs_scored(df: pd.DataFrame, min_peaks: int = 3, order: int = 2) -> PatternResult:
    """
    Detect descending highs with a score (0..1) instead of a binary fail.
    Score is the fraction of descending steps, penalized by any break magnitude.
    """
    if df.empty:
        return PatternResult(False, 0.0, pd.DataFrame(), 0.0, 0, 0.0, reason="no data")
    if len(df) < max(min_peaks * order, 5):
        return PatternResult(False, 0.0, pd.DataFrame(), 0.0, 0, 0.0, reason="insufficient candles")

    highs = df["high"].to_numpy()
    peak_idx = argrelextrema(highs, np.greater, order=order)[0]
    peaks = df.iloc[peak_idx]

    if len(peaks) < min_peaks:
        return PatternResult(False, 0.0, peaks, 0.0, 0, 0.0, reason="not enough peaks")

    highs_series = peaks["high"].to_numpy()
    total_steps = len(highs_series) - 1
    descending_steps = 0
    violations = 0
    max_break_pct = 0.0

    for i in range(1, len(highs_series)):
        if highs_series[i] < highs_series[i - 1]:
            descending_steps += 1
        else:
            violations += 1
            if highs_series[i - 1] > 0:
                break_pct = (highs_series[i] - highs_series[i - 1]) / highs_series[i - 1]
                max_break_pct = max(max_break_pct, break_pct)

    base_score = descending_steps / total_steps if total_steps > 0 else 0.0
    penalty = min(max_break_pct * 0.5, 0.5)
    score = max(base_score - penalty, 0.0)

    # Negative slope indicates descending channel; flat/upward slope reduces score
    x = np.arange(len(highs_series))
    slope, _ = np.polyfit(x, highs_series, 1)
    if slope >= 0:
        score *= 0.5

    passed = score >= 0.5 and descending_steps >= 2  # loose pass: majority descending and at least two steps
    return PatternResult(passed, float(slope), peaks, score, violations, max_break_pct, reason=None if passed else "weak descent")
