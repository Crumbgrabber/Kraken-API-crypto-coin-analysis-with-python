from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from config import settings
from src.analysis.pattern_detector import PatternResult


def _slope(y: np.ndarray) -> float:
    if len(y) < 2:
        return 0.0
    x = np.arange(len(y))
    m, _ = np.polyfit(x, y, 1)
    return float(m)


def _load_indicators(pair: str, tf: str) -> pd.DataFrame | None:
    path = settings.INDICATORS_DIR / settings.INDICATORS_FILE_TEMPLATE.format(pair=pair, tf=tf)
    if not path.exists():
        return None
    try:
        return pd.read_parquet(path)
    except Exception:
        return None


def _ema_desc(ind: pd.DataFrame | None, col: str, lag: int, strict: bool = True, tol: float = 0.0) -> tuple[bool, str | None]:
    """
    Check if EMA is descending over the specified lag.
    If data is missing/insufficient and strict=False, return pass=True (do not auto-fail for short history).
    """
    if ind is None or col not in ind:
        return (False, f"missing {col}") if strict else (True, None)
    clean = ind.dropna(subset=[col])
    if len(clean) <= lag:
        return (False, f"insufficient {col}") if strict else (True, None)
    past_val = clean[col].iloc[-(lag + 1)]
    recent_val = clean[col].iloc[-1]
    descending = recent_val < past_val * (1 + tol)
    return descending, (None if descending else f"{col} not descending")


def detect_descending_rules(df: pd.DataFrame, tf: str, pair: str) -> PatternResult:
    """
    Simple windowed-high rule:
    - monthly: fail if current month high > previous month high.
    - daily: use last N days; fail if max(high) in recent window > max(high) in earlier window.
    - 4h: use last N days; fail if max(high) in last K bars > max(high) in earlier bars within window.
    Plus EMA slope checks:
    - monthly: ema_12 last < value 12 bars ago
    - daily: ema_200 last < 200 bars ago AND ema_50 last < 50 bars ago
    - 4h: ema_7 last < value 7 bars ago
    """
    if df.empty:
        return PatternResult(False, 0.0, pd.DataFrame(), 0.0, 0, 0.0, reason="no data")

    ind = _load_indicators(pair, tf)

    if tf == "monthly":
        if len(df) < settings.PAT2_MONTHS_LOOKBACK:
            return PatternResult(False, 0.0, pd.DataFrame(), 0.0, 0, 0.0, reason="insufficient months")
        last_two = df.tail(settings.PAT2_MONTHS_LOOKBACK)
        current_high = last_two["high"].iloc[-1]
        prev_high = last_two["high"].iloc[-2]
        highs_pass = current_high <= prev_high
        ema_pass, reason = _ema_desc(ind, "ema_12", 12, strict=True)
        passed = highs_pass and ema_pass
        slope = _slope(last_two["high"].to_numpy())
        return PatternResult(passed, slope, last_two, float(passed), 0 if passed else 1, 0.0, reason=None if passed else reason or "current high > prev high")

    if tf == "daily":
        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=settings.PAT2_DAILY_LOOKBACK_DAYS)
        window = df[df["time"] >= cutoff]
        if window.empty:
            return PatternResult(False, 0.0, pd.DataFrame(), 0.0, 0, 0.0, reason="no recent data")
        recent_cut = datetime.now(tz=timezone.utc) - timedelta(days=settings.PAT2_DAILY_RECENT_DAYS)
        recent = window[window["time"] >= recent_cut]
        baseline = window[window["time"] < recent_cut]
        if baseline.empty or recent.empty:
            return PatternResult(False, 0.0, window, 0.0, 0, 0.0, reason="not enough split")
        highs_pass = recent["high"].max() <= baseline["high"].max()
        ema_pass = False
        reason = None
        if ind is not None and "ema_50" in ind:
            clean = ind.dropna(subset=["ema_50"])
            ema50_ready = len(clean) > 50
            ema50_pass = False
            ema200_pass = True
            r50 = r200 = None
            if ema50_ready:
                ema50_pass, r50 = _ema_desc(ind, "ema_50", 50, strict=True)
            if "ema_200" in ind and len(ind.dropna(subset=["ema_200"])) > 200:
                ema200_pass, r200 = _ema_desc(ind, "ema_200", 200, strict=True)
            # If we have 200 bars, require both; if not, require 50 only.
            if len(ind.dropna(subset=["ema_200"])) > 200:
                ema_pass = ema50_pass and ema200_pass
                if not ema_pass:
                    reason = r200 or r50 or "ema 50/200 not descending"
            else:
                ema_pass = ema50_pass
                if not ema_pass:
                    reason = r50 or "ema 50 not descending"
        else:
            ema_pass = False
            reason = "missing ema 50"
        passed = highs_pass and ema_pass
        slope = _slope(window["high"].to_numpy())
        return PatternResult(passed, slope, window, float(passed), 0 if passed else 1, 0.0, reason=None if passed else reason or "recent high > prior window")

    if tf == "4h":
        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=settings.PAT2_4H_LOOKBACK_DAYS)
        window = df[df["time"] >= cutoff]
        if window.empty:
            return PatternResult(False, 0.0, pd.DataFrame(), 0.0, 0, 0.0, reason="no recent data")
        recent_bars = settings.PAT2_4H_RECENT_BARS
        if len(window) <= recent_bars:
            return PatternResult(False, 0.0, window, 0.0, 0, 0.0, reason="not enough bars")
        recent = window.tail(recent_bars)
        baseline = window.iloc[:-recent_bars]
        if baseline.empty:
            return PatternResult(False, 0.0, window, 0.0, 0, 0.0, reason="not enough baseline")
        highs_pass = recent["high"].max() <= baseline["high"].max()
        ema_pass = False
        reason = None
        if ind is not None and "ema_7" in ind:
            ind_window = ind[ind["time"] >= cutoff] if "time" in ind else ind
            ind_window = ind_window.dropna(subset=["ema_7"])
            if ind_window.shape[0] > 7:
                # allow small tolerance to avoid rejecting flat/near-flat
                ema_pass, reason = _ema_desc(ind_window, "ema_7", 7, strict=True, tol=0.002)
            else:
                ema_pass = False
                reason = "insufficient ema_7"
        else:
            ema_pass = False
            reason = "missing ema_7"
        passed = highs_pass and ema_pass
        slope = _slope(window["high"].to_numpy())
        return PatternResult(passed, slope, window, float(passed), 0 if passed else 1, 0.0, reason=None if passed else reason or "recent high > prior bars")

    return PatternResult(False, 0.0, pd.DataFrame(), 0.0, 0, 0.0, reason="unsupported tf")
