from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from config import settings
from config.indicator_config import INDICATOR_SETTINGS
from src.analysis.pattern_detector import PatternResult
from src.analysis.volume_profile import VolumeProfileResult


@dataclass
class TimeframeOutcome:
    name: str
    pattern: PatternResult
    volume_profile: VolumeProfileResult
    volume_decline_score: float
    poc_distance_score: float
    indicator_score: float
    indicator_breakdown: Dict[str, float]

    @property
    def passed(self) -> bool:
        return self.pattern.passed


def _load_indicators(pair: str, tf: str) -> pd.DataFrame | None:
    path = settings.INDICATORS_DIR / settings.INDICATORS_FILE_TEMPLATE.format(pair=pair, tf=tf)
    if not path.exists():
        return None
    try:
        return pd.read_parquet(path)
    except Exception:
        return None


def _ema_slope_votes(ind: pd.DataFrame | None, lookback: int, weight: float) -> Tuple[float, Dict[str, float]]:
    if ind is None:
        return 0.0, {}
    votes: Dict[str, float] = {}
    total = 0.0
    ema_cols = [c for c in ind.columns if c.startswith("ema_")]
    for col in ema_cols:
        clean = ind[col].dropna()
        if len(clean) < 2:
            continue
        tail = clean.tail(max(lookback, 2))
        x = np.arange(len(tail))
        slope, _ = np.polyfit(x, tail, 1)
        if slope > 0:
            votes[f"ema_slope:{col}"] = weight
            total += weight
        elif slope < 0:
            votes[f"ema_slope:{col}"] = -weight
            total -= weight
    return total, votes


def _compute_returns(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"ytd": None, "d30": None, "d7": None}
    last_close = df["close"].iloc[-1]
    tz = df["time"].dt.tz if "time" in df else None
    now = pd.Timestamp.now(tz=tz)
    start_year = pd.Timestamp(year=now.year, month=1, day=1, tz=tz)

    def _ret(window: pd.DataFrame) -> float | None:
        if window.empty:
            return None
        first = window["close"].iloc[0]
        if first == 0:
            return None
        return (last_close - first) / first

    ytd_df = df[df["time"] >= start_year] if "time" in df else df
    ret_ytd = _ret(ytd_df)
    cutoff_30 = now - pd.Timedelta(days=30)
    cutoff_7 = now - pd.Timedelta(days=7)
    ret_30 = _ret(df[df["time"] >= cutoff_30]) if "time" in df else None
    ret_7 = _ret(df[df["time"] >= cutoff_7]) if "time" in df else None
    return {"ytd": ret_ytd, "d30": ret_30, "d7": ret_7}


def _return_votes(df: pd.DataFrame, weight_ytd: float, weight_30: float, weight_7: float) -> Tuple[float, Dict[str, float]]:
    returns = _compute_returns(df)
    votes: Dict[str, float] = {}
    total = 0.0
    for key, wt in (("ytd", weight_ytd), ("d30", weight_30), ("d7", weight_7)):
        val = returns[key]
        if val is None or pd.isna(val) or val == 0:
            continue
        vote = wt if val > 0 else -wt
        votes[f"return:{key}"] = vote
        total += vote
    return total, votes


def _nbars_votes(df: pd.DataFrame, lookback: int, weight: float) -> Tuple[float, Dict[str, float]]:
    if df.empty:
        return 0.0, {}
    tail = df.tail(max(lookback, 2))
    if len(tail) < 2:
        return 0.0, {}
    highs = tail["high"].to_numpy()
    lows = tail["low"].to_numpy()
    votes: Dict[str, float] = {}
    total = 0.0
    for idx in range(1, len(tail)):
        if highs[idx] > highs[idx - 1]:
            total += weight
            votes[f"nbars:high:{idx}"] = weight
        elif highs[idx] < highs[idx - 1]:
            total -= weight
            votes[f"nbars:high:{idx}"] = -weight
        if lows[idx] > lows[idx - 1]:
            total += weight
            votes[f"nbars:low:{idx}"] = weight
        elif lows[idx] < lows[idx - 1]:
            total -= weight
            votes[f"nbars:low:{idx}"] = -weight
    return total, votes


def _indicator_votes(tf_name: str, pair: str, df: pd.DataFrame) -> Tuple[float, Dict[str, float]]:
    cfg = INDICATOR_SETTINGS
    weights = cfg.indicator_weights

    ind_df = _load_indicators(pair, tf_name)
    ema_score, ema_breakdown = _ema_slope_votes(ind_df, cfg.ema_slope_lookback, weights.ema_slope)

    ret_score, ret_breakdown = _return_votes(df, weights.return_ytd, weights.return_30d, weights.return_7d)

    nbars_score, nbars_breakdown = _nbars_votes(df, cfg.nbars_lookback, weights.nbars)

    total = ema_score + ret_score + nbars_score
    breakdown: Dict[str, float] = {}
    breakdown.update(ema_breakdown)
    breakdown.update(ret_breakdown)
    breakdown.update(nbars_breakdown)
    return total, breakdown


def score_timeframe(tf_name: str, df: pd.DataFrame, pattern: PatternResult, vp: VolumeProfileResult, pair: str) -> TimeframeOutcome:
    indicator_score, indicator_breakdown = _indicator_votes(tf_name, pair, df)
    return TimeframeOutcome(
        name=tf_name,
        pattern=pattern,
        volume_profile=vp,
        volume_decline_score=0.0,  # skipped in simplified scheme
        poc_distance_score=0.0,  # skipped in simplified scheme
        indicator_score=indicator_score,
        indicator_breakdown=indicator_breakdown,
    )


def aggregate_score(timeframes: List[TimeframeOutcome], is_solana: bool) -> float:
    total = 0.0
    for tf in timeframes:
        multiplier = INDICATOR_SETTINGS.timeframe_multipliers.get(tf.name, 1.0)
        total += multiplier * tf.indicator_score

    if is_solana:
        total -= settings.SOL_BONUS
    return total
