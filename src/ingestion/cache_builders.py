from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, Any

import pandas as pd

from config import settings
from src.api.futures_client import KrakenFuturesClient
from src.api.kraken_client import KrakenPublicClient

logger = logging.getLogger(__name__)


def cache_asset_metadata(client: KrakenPublicClient) -> Dict[str, Path]:
    """Cache Assets and AssetPairs to disk."""
    assets = client.get_assets()
    pairs = client.get_asset_pairs()

    settings.ASSET_INFO_JSON.parent.mkdir(parents=True, exist_ok=True)
    settings.ASSET_INFO_JSON.write_text(json.dumps(assets, indent=2), encoding="utf-8")
    settings.ASSET_PAIRS_JSON.write_text(json.dumps(pairs, indent=2), encoding="utf-8")
    logger.info("Cached Assets -> %s; AssetPairs -> %s", settings.ASSET_INFO_JSON, settings.ASSET_PAIRS_JSON)
    return {"assets": settings.ASSET_INFO_JSON, "pairs": settings.ASSET_PAIRS_JSON}


def cache_futures_instruments(client: KrakenFuturesClient) -> Path:
    instruments = client.get_instruments()
    settings.INSTRUMENTS_JSON.parent.mkdir(parents=True, exist_ok=True)
    settings.INSTRUMENTS_JSON.write_text(json.dumps(instruments, indent=2), encoding="utf-8")
    logger.info("Cached futures instruments -> %s", settings.INSTRUMENTS_JSON)
    return settings.INSTRUMENTS_JSON


def cache_futures_tickers(client: KrakenFuturesClient) -> Path:
    tickers = client.get_tickers()
    # The payload includes a "tickers" list; keep relevant fields.
    records = []
    for item in tickers.get("tickers", []):
        records.append(
            {
                "symbol": item.get("symbol"),
                "pair": item.get("pair"),
                "markPrice": item.get("markPrice"),
                "bid": item.get("bid"),
                "ask": item.get("ask"),
                "fundingRate": item.get("fundingRate"),
                "openInterest": item.get("openInterest"),
                "premium": item.get("premium"),  # proxy for basis
                "timestamp": item.get("timestamp"),
            }
        )
    df = pd.DataFrame(records)
    settings.FUTURES_TICKERS_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(settings.FUTURES_TICKERS_PARQUET, index=False)
    logger.info("Cached futures tickers/OI/funding/basis -> %s (%d rows)", settings.FUTURES_TICKERS_PARQUET, len(df))
    return settings.FUTURES_TICKERS_PARQUET


def cache_risk_rates(client: KrakenFuturesClient) -> Path:
    rates = client.get_risk_rates()
    if not rates:
        logger.warning("Risk rates response empty; writing stub to %s", settings.RISK_RATES_JSON)
    settings.RISK_RATES_JSON.parent.mkdir(parents=True, exist_ok=True)
    settings.RISK_RATES_JSON.write_text(json.dumps(rates, indent=2), encoding="utf-8")
    logger.info("Cached risk rates -> %s", settings.RISK_RATES_JSON)
    return settings.RISK_RATES_JSON
