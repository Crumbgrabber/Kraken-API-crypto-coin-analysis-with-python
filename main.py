from __future__ import annotations

import argparse
import logging
from typing import List

from config import settings
from src.analysis.pattern_detector import PatternResult, detect_lower_highs_scored
from src.analysis.pattern_detector2 import detect_descending_rules
from src.analysis.volume_profile import compute_volume_profile
from src.api.data_fetcher import PairMeta, discover_usd_pairs, fetch_ohlc, write_pairs_csv
from src.api.futures_client import KrakenFuturesClient
from src.api.kraken_client import KrakenPublicClient
from src.ingestion.cache_builders import cache_asset_metadata, cache_futures_instruments, cache_futures_tickers, cache_risk_rates
from src.outputs.report import export_plotly, export_plotly_timeframes, export_summary_html, export_tabular, summarize_to_console
from src.scoring.coin_ranker import aggregate_score, score_timeframe
from src.types import PairResult


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


PATTERN_MIN_PEAKS = {"monthly": 3, "daily": 4, "4h": 4}
PATTERN_ORDER = {"monthly": 2, "daily": 2, "4h": 2}


def analyze_pair(client: KrakenPublicClient, pair: PairMeta, refresh: bool, timeframes: list[str]) -> PairResult | None:
    outcomes = []
    frames = {}

    for tf in timeframes:
        df = fetch_ohlc(client, pair, tf, refresh=refresh)
        frames[tf] = df
        if settings.PATTERN_DETECTOR_VERSION == 2:
            pattern = detect_descending_rules(df, tf, pair.altname)
        else:
            pattern = detect_lower_highs_scored(df, min_peaks=PATTERN_MIN_PEAKS[tf], order=PATTERN_ORDER[tf])
        vp = compute_volume_profile(df)
        outcome = score_timeframe(tf, df, pattern, vp)
        outcomes.append(outcome)

    score = aggregate_score(outcomes, pair.is_solana)
    return PairResult(pair=pair.altname, wsname=pair.wsname, score=score, is_solana=pair.is_solana, outcomes=outcomes, frames=frames)


def run(
    limit: int | None,
    start: int | None,
    refresh: bool,
    top: int,
    plotly_top: int | None,
    only_pairs: list[str] | None,
    export_pairs: bool,
    timeframes: list[str],
    refresh_metadata: bool,
    refresh_futures: bool,
    refresh_risk_rates: bool,
) -> List[PairResult]:
    client = KrakenPublicClient()
    futures_client = KrakenFuturesClient()

    if refresh_metadata:
        cache_asset_metadata(client)
    if refresh_futures:
        cache_futures_instruments(futures_client)
        cache_futures_tickers(futures_client)
    if refresh_risk_rates:
        cache_risk_rates(futures_client)

    pairs = discover_usd_pairs(client)
    if export_pairs:
        saved = write_pairs_csv(pairs, settings.PAIRS_CSV)
        logger.info("Exported %d USD pairs to %s", len(pairs), saved)
    if only_pairs:
        only_set = {p.upper() for p in only_pairs}
        pairs = [p for p in pairs if p.altname.upper() in only_set or p.wsname.replace("/", "").upper() in only_set]
        logger.info("Filtered to %d requested pairs", len(pairs))
    if start:
        pairs = pairs[start:]
    if limit:
        pairs = pairs[:limit]

    logger.info("Evaluating %d USD pairs (refresh=%s)", len(pairs), refresh)
    results: List[PairResult] = []
    for pair in pairs:
        try:
            res = analyze_pair(client, pair, refresh=refresh, timeframes=timeframes)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Skipping %s due to error: %s", pair.wsname, exc)
            continue
        if res:
            results.append(res)

    results.sort(key=lambda r: r.score, reverse=True)
    summarize_to_console(results, top_n=top)
    export_tabular(results, settings.RESULTS_CSV, settings.RESULTS_JSON)
    export_plotly(results, settings.RESULTS_DIR, top_n=plotly_top or settings.PLOTLY_TOP_N)
    export_plotly_timeframes(results, settings.RESULTS_DIR)
    export_summary_html(results, settings.RESULTS_HTML)
    logger.info("Wrote %s, %s, and %s", settings.RESULTS_CSV, settings.RESULTS_JSON, settings.RESULTS_HTML)
    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Kraken USD meme-coin analyzer")
    parser.add_argument("--start", type=int, default=None, help="start index into discovered pair list (0-based)")
    parser.add_argument("--limit", type=int, default=None, help="limit number of pairs processed")
    parser.add_argument("--refresh", action="store_true", help="ignore cache and refetch OHLC")
    parser.add_argument("--top", type=int, default=settings.TOP_N_DEFAULT, help="number of results to display")
    parser.add_argument("--plotly-top", type=int, default=None, help="number of Plotly HTML exports (default settings.PLOTLY_TOP_N)")
    parser.add_argument("--pairs", type=str, default=None, help="comma-separated pair altnames to run (e.g., JTOUSD,BONKUSD)")
    parser.add_argument("--export-pairs", action="store_true", help="export discovered USD pairs to data/pairs_usd.csv")
    parser.add_argument(
        "--timeframes",
        type=str,
        default="monthly,daily,4h",
        help="comma-separated timeframes to process (any of monthly,daily,4h)",
    )
    parser.add_argument("--refresh-metadata", action="store_true", help="refresh/caches Assets and AssetPairs")
    parser.add_argument("--refresh-futures", action="store_true", help="refresh/caches Kraken Futures instruments and tickers (OI/funding/basis)")
    parser.add_argument("--refresh-risk-rates", action="store_true", help="refresh/caches Kraken Futures risk rates")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    pairs = args.pairs.split(",") if args.pairs else None
    tfs = [tf.strip() for tf in args.timeframes.split(",") if tf.strip()]
    run(
        limit=args.limit,
        start=args.start,
        refresh=args.refresh,
        top=args.top,
        plotly_top=args.plotly_top,
        only_pairs=pairs,
        export_pairs=args.export_pairs,
        timeframes=tfs,
        refresh_metadata=args.refresh_metadata,
        refresh_futures=args.refresh_futures,
        refresh_risk_rates=args.refresh_risk_rates,
    )
