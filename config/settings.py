from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Optional


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
CACHE_DIR = DATA_DIR / "cache"
RESULTS_DIR = BASE_DIR / "results"
PAIRS_CSV = DATA_DIR / "pairs_usd.csv"
RESULTS_HTML = RESULTS_DIR / "summary.html"
STATE_FILE = DATA_DIR / "ohlc_state.json"
INDICATORS_DIR = DATA_DIR / "indicators"

CACHE_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)
INDICATORS_DIR.mkdir(parents=True, exist_ok=True)

PAIRS_JSON = DATA_DIR / "pairs_usd.json"
DATA_DIR.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class TimeframeConfig:
    interval_minutes: int
    history_days: Optional[int]  # None means full history
    cache_ttl_hours: int
    resample_rule: Optional[str] = None  # e.g., "ME" for month-end

    @property
    def cache_ttl(self) -> timedelta:
        return timedelta(hours=self.cache_ttl_hours)


# Kraken OHLC intervals are expressed in minutes; we fetch daily data and
# resample to monthly bars for the monthly test.
TIMEFRAMES: dict[str, TimeframeConfig] = {
    "monthly": TimeframeConfig(interval_minutes=1440, history_days=None, cache_ttl_hours=24, resample_rule="ME"),
    "daily": TimeframeConfig(interval_minutes=1440, history_days=None, cache_ttl_hours=6),
    "4h": TimeframeConfig(interval_minutes=240, history_days=7, cache_ttl_hours=2),
}

# Weighting for overall score aggregation.
TIMEFRAME_WEIGHTS: dict[str, float] = {
    "monthly": 0.4,
    "daily": 0.35,
    "4h": 0.25,
}

PAIR_WHITELIST = {"JTOUSD"}

# Treat these base assets as Solana-origin memecoins for the +1 bonus.
# Expand as we learn the Kraken Solana category; this is an explicit allowlist.
SOL_MEME_BASES = {
    "BONK",
    "WIF",
    "SAMO",
    "JTO",
}

# Solana bonus removed; keep for compatibility set to 0.0
SOL_BONUS = 0.0

# Export controls
TOP_N_DEFAULT = 20
PLOTLY_TOP_N = 10

# Paths for cache/results
CACHE_FILE_TEMPLATE = "{pair}_{tf}.parquet"
RESULTS_CSV = RESULTS_DIR / "analysis.csv"
RESULTS_JSON = RESULTS_DIR / "analysis.json"
PAIRS_LIST_JSON = DATA_DIR / "usd_pairs.json"
ASSET_INFO_JSON = CACHE_DIR / "asset_info.json"
ASSET_PAIRS_JSON = CACHE_DIR / "asset_pairs.json"
INSTRUMENTS_JSON = CACHE_DIR / "instruments.json"
FUTURES_TICKERS_PARQUET = CACHE_DIR / "futures_tickers.parquet"
RISK_RATES_JSON = CACHE_DIR / "risk_rates.json"
INDICATORS_FILE_TEMPLATE = "{pair}_{tf}_indicators.parquet"

# Rate limiting (public REST)
PUBLIC_MIN_INTERVAL_SEC = 1.1  # courteous pacing; adjust if official limits change

# Pattern detector selector: 1 = legacy descending-highs scoring, 2 = windowed-high rules
PATTERN_DETECTOR_VERSION = 2

# Pattern detector v2 windows
PAT2_MONTHS_LOOKBACK = 2  # need current + previous month
PAT2_DAILY_LOOKBACK_DAYS = 30
PAT2_DAILY_RECENT_DAYS = 7
PAT2_4H_LOOKBACK_DAYS = 7
PAT2_4H_RECENT_BARS = 12  # last 12 bars vs prior bars in lookback
