from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import numpy as np
import pandas as pd

from config import settings
from src.analysis.pattern_detector import PatternResult
from src.analysis.volume_profile import VolumeProfileResult


@dataclass
class TimeframeOutcome:
    name: str
    pattern: PatternResult
    volume_profile: VolumeProfileResult
    volume_decline_score: float
    poc_distance_score: float

    @property
    def passed(self) -> bool:
        return self.pattern.passed


def volume_decline_score(df: pd.DataFrame) -> float:
    """Score 0..1 for how much volume has declined from early to recent data."""
    if df.shape[0] < 10:
        return 0.0
    split = max(df.shape[0] // 4, 1)
    early = df["volume"].iloc[:split].mean()
    recent = df["volume"].iloc[-split:].mean()
    if early <= 0:
        return 0.0
    decline = (early - recent) / early
    return float(np.clip(decline, 0.0, 1.0))


def poc_distance_score(df: pd.DataFrame, vp: VolumeProfileResult) -> float:
    """Score 0..1 where closer to POC is better (we care about nearby support)."""
    last_close = df["close"].iloc[-1]
    if np.isnan(vp.poc) or last_close == 0:
        return 0.0
    distance = abs(last_close - vp.poc) / last_close
    return float(np.clip(1 - distance, 0.0, 1.0))


def score_timeframe(tf_name: str, df: pd.DataFrame, pattern: PatternResult, vp: VolumeProfileResult) -> TimeframeOutcome:
    vol_decline = volume_decline_score(df)
    poc_score = poc_distance_score(df, vp)
    return TimeframeOutcome(
        name=tf_name,
        pattern=pattern,
        volume_profile=vp,
        volume_decline_score=vol_decline,
        poc_distance_score=poc_score,
    )


def aggregate_score(timeframes: List[TimeframeOutcome], is_solana: bool) -> float:
    score = 0.0
    for tf in timeframes:
        weight = settings.TIMEFRAME_WEIGHTS.get(tf.name, 0)
        # Pattern score already in 0..1; include volume decline and POC proximity
        tf_score = 0.6 * tf.pattern.score + 0.25 * tf.volume_decline_score + 0.15 * tf.poc_distance_score
        score += weight * tf_score

    if is_solana:
        score += settings.SOL_BONUS
    return score
