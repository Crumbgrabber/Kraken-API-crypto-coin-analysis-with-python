from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IndicatorWeights:
    ema_slope: float = 1.0
    return_ytd: float = 1.0
    return_30d: float = 1.0
    return_7d: float = 1.0
    nbars: float = 1.0


@dataclass(frozen=True)
class IndicatorConfig:
    # Multiplier per timeframe applied after summing indicator votes
    timeframe_multipliers: dict[str, float]
    # Global weights for each indicator type (can be tuned)
    indicator_weights: IndicatorWeights
    ema_slope_lookback: int = 5  # bars used to measure EMA slope
    nbars_lookback: int = 5  # bars used for N-bars up/down vote


INDICATOR_SETTINGS = IndicatorConfig(
    timeframe_multipliers={"monthly": 4.0, "daily": 2.0, "4h": 1.0},
    indicator_weights=IndicatorWeights(),
)
