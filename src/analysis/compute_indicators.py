from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Dict, List

import pandas as pd

from config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def ema(series: pd.Series, window: int) -> pd.Series:
    """Exponential moving average of closing price."""
    return series.ewm(span=window, adjust=False, min_periods=window).mean()


def pct_change(start: float | None, end: float | None) -> float | None:
    """Safe percent change; returns None when inputs are missing or start is zero."""
    if start is None or end is None:
        return None
    try:
        if start == 0:
            return None
        return (end - start) / start
    except Exception:  # noqa: BLE001
        return None


WINDOWS: Dict[str, List[int]] = {
    "monthly": [5, 12],  # 5 for short view, 12 per request
    "daily": [5, 30, 50, 200],
    "4h": [5, 7],
}


def compute_for_pair(pair: str, timeframes: List[str], output_dir: Path) -> None:
    for tf in timeframes:
        cache_path = settings.CACHE_DIR / settings.CACHE_FILE_TEMPLATE.format(pair=pair, tf=tf)
        if not cache_path.exists():
            logger.debug("Skipping %s %s (no cache)", pair, tf)
            continue
        df = pd.read_parquet(cache_path)
        # Ensure time is datetime for sorting/output
        if "time" in df.columns:
            df = df.copy()
            df["time"] = pd.to_datetime(df["time"])
            df = df.sort_values("time")
        else:
            logger.warning("No time column for %s %s, skipping", pair, tf)
            continue

        out = df[["time", "close"]].copy()
        for w in WINDOWS.get(tf, []):
            out[f"ema_{w}"] = ema(out["close"], w)

        # Daily timeframe: attach YTD, 30d, and 7d percent returns.
        if tf == "daily" and not out.empty:
            latest = out.dropna(subset=["close"]).iloc[-1]
            latest_close = float(latest["close"])
            latest_ts = latest["time"]

            # YTD: first close of the current calendar year vs latest.
            year_mask = out["time"].dt.year == latest_ts.year
            year_df = out.loc[year_mask & out["close"].notna()]
            ytd_start = float(year_df.iloc[0]["close"]) if not year_df.empty else None
            ytd_return = pct_change(ytd_start, latest_close)

            # Rolling windows relative to latest.
            def window_return(days: int) -> float | None:
                cutoff = latest_ts - pd.Timedelta(days=days)
                window_df = out.loc[out["time"] >= cutoff].dropna(subset=["close"])
                if window_df.empty:
                    return None
                start_val = float(window_df.iloc[0]["close"])
                return pct_change(start_val, latest_close)

            return_30d = window_return(30)
            return_7d = window_return(7)

            out["return_ytd"] = ytd_return
            out["return_30d"] = return_30d
            out["return_7d"] = return_7d

        out_path = output_dir / settings.INDICATORS_FILE_TEMPLATE.format(pair=pair, tf=tf)
        out.to_parquet(out_path, index=False)
        logger.info("Wrote indicators for %s %s -> %s", pair, tf, out_path)


def load_pairs(limit: int | None = None, start: int | None = None, only: List[str] | None = None) -> List[str]:
    pairs_csv = settings.PAIRS_CSV
    if not pairs_csv.exists():
        raise FileNotFoundError(f"{pairs_csv} not found. Run main.py with --export-pairs first.")
    df = pd.read_csv(pairs_csv)
    pairs = df["altname"].tolist()
    if only:
        only_upper = {p.upper() for p in only}
        pairs = [p for p in pairs if p.upper() in only_upper]
    if start:
        pairs = pairs[start:]
    if limit:
        pairs = pairs[:limit]
    return pairs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compute VWMA indicators for cached OHLC data.")
    parser.add_argument("--timeframes", type=str, default="monthly,daily,4h", help="comma-separated tfs (monthly,daily,4h)")
    parser.add_argument("--limit", type=int, default=None, help="limit number of pairs")
    parser.add_argument("--start", type=int, default=None, help="start index into pair list")
    parser.add_argument("--pairs", type=str, default=None, help="comma-separated specific pairs (altname)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    tfs = [tf.strip() for tf in args.timeframes.split(",") if tf.strip()]
    only_pairs = args.pairs.split(",") if args.pairs else None
    pairs = load_pairs(limit=args.limit, start=args.start, only=only_pairs)
    logger.info("Computing indicators for %d pairs, tfs=%s", len(pairs), tfs)
    for pair in pairs:
        compute_for_pair(pair, tfs, settings.INDICATORS_DIR)


if __name__ == "__main__":
    main()
